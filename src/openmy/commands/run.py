from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from openmy.config import GEMINI_MODEL, get_llm_api_key, get_stage_llm_model, has_llm_credentials


PARTIAL_SUCCESS = 2
RUN_STEPS = (
    "transcribe",
    "transcribe_enrich",
    "clean",
    "segment",
    "roles",
    "distill",
    "briefing",
    "extract_core",
    "consolidate",
    "extract_enrich",
)


def _cli():
    from openmy import cli as cli_module

    return cli_module


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _init_run_status(date_str: str, entrypoint: str) -> dict:
    cli = _cli()
    timestamp = _now_iso()
    payload = {
        "date": date_str,
        "entrypoint": entrypoint,
        "status": "running",
        "current_step": "setup",
        "started_at": timestamp,
        "finished_at": None,
        "steps": {
            step: {
                "status": "pending",
                "message": "",
                "updated_at": timestamp,
                "artifacts": [],
            }
            for step in RUN_STEPS
        },
    }
    cli.write_json(cli.ensure_day_dir(date_str) / "run_status.json", payload)
    return payload


def _save_run_status(date_str: str, payload: dict) -> None:
    cli = _cli()
    cli.write_json(cli.ensure_day_dir(date_str) / "run_status.json", payload)


def _mark_step(
    date_str: str,
    payload: dict,
    step: str,
    status: str,
    *,
    message: str = "",
    artifact: str | Path | None = None,
) -> None:
    step_payload = payload["steps"][step]
    step_payload["status"] = status
    step_payload["message"] = message
    step_payload["updated_at"] = _now_iso()
    if artifact is not None:
        artifact_str = str(artifact)
        if artifact_str not in step_payload["artifacts"]:
            step_payload["artifacts"].append(artifact_str)
    payload["current_step"] = step
    _save_run_status(date_str, payload)


def _finish_run(date_str: str, payload: dict, final_status: str, current_step: str) -> None:
    payload["status"] = final_status
    payload["current_step"] = current_step
    payload["finished_at"] = _now_iso()
    _save_run_status(date_str, payload)


def run_transcription_enrichment(day_dir: Path, *, diarize: bool = False) -> dict:
    from openmy.services.ingest.transcription_enrichment import run_transcription_enrichment as _run

    return _run(day_dir, diarize=diarize)


def apply_transcription_enrichment_to_scenes(day_dir: Path) -> None:
    from openmy.services.ingest.transcription_enrichment import (
        apply_transcription_enrichment_to_scenes as _apply,
    )

    _apply(day_dir)


def transcribe_audio_files(
    date_str: str,
    audio_files: list[str],
    *,
    stt_provider: str | None = None,
    stt_model: str | None = None,
    stt_vad: bool = False,
    stt_word_timestamps: bool = False,
) -> int:
    """把本地音频文件转成 raw transcript。"""
    cli = _cli()
    from openmy.services.ingest.audio_pipeline import transcribe_audio_files as run_ingest_pipeline

    try:
        output_path = run_ingest_pipeline(
            date_str=date_str,
            audio_files=audio_files,
            output_dir=cli.ensure_day_dir(date_str),
            provider_name=stt_provider,
            model=stt_model,
            vad_filter=stt_vad,
            word_timestamps=stt_word_timestamps,
        )
    except Exception as exc:
        cli.console.print(f"[red]❌ 转写失败[/red]: {exc}")
        return 1

    cli.console.print(f"[green]✅ 原始转写已生成[/green]: {output_path}")
    return 0


def cmd_run(args: argparse.Namespace, *, entrypoint: str = "run") -> int:
    """全流程：转写 → 清洗 → 角色 → 蒸馏 → 日报。"""
    cli = _cli()
    date_str = args.date
    run_status = _init_run_status(date_str, entrypoint)
    cli.console.print(
        cli.Panel(
            f"🎙️ OpenMy 全流程处理\n📅 日期: {date_str}",
            border_style="bright_blue",
        )
    )

    paths = cli.resolve_day_paths(date_str)
    if args.audio and not args.skip_transcribe:
        _mark_step(date_str, run_status, "transcribe", "running", message="正在转写音频")
        cli.console.print("[bold]Step 0: 🎙️ 转写音频[/bold]")
        result = transcribe_audio_files(
            date_str,
            args.audio,
            stt_provider=getattr(args, "stt_provider", None),
            stt_model=getattr(args, "stt_model", None),
            stt_vad=bool(getattr(args, "stt_vad", False)),
            stt_word_timestamps=bool(getattr(args, "stt_word_timestamps", False)),
        )
        if result != 0:
            _mark_step(date_str, run_status, "transcribe", "failed", message="转写失败")
            _finish_run(date_str, run_status, "failed", "transcribe")
            return result
        paths = cli.resolve_day_paths(date_str)
        _mark_step(date_str, run_status, "transcribe", "completed", message="转写完成", artifact=paths["raw"])
    else:
        _mark_step(date_str, run_status, "transcribe", "skipped", message="未执行新的音频转写")

    from openmy.services.ingest.transcription_enrichment import update_pipeline_meta

    update_pipeline_meta(
        cli.ensure_day_dir(date_str),
        transcription_provider=getattr(args, "stt_provider", None) or "faster-whisper",
        transcription_model=getattr(args, "stt_model", None) or "",
        transcription_vad=bool(getattr(args, "stt_vad", False)),
        transcription_word_timestamps=bool(getattr(args, "stt_word_timestamps", False)),
    )

    if bool(getattr(args, "stt_align", False)):
        _mark_step(date_str, run_status, "transcribe_enrich", "running", message="正在执行 WhisperX 精标")
        try:
            enrichment = run_transcription_enrichment(
                cli.ensure_day_dir(date_str),
                diarize=bool(getattr(args, "stt_diarize", False)),
            )
            update_pipeline_meta(
                cli.ensure_day_dir(date_str),
                transcription_enrich_status="completed",
                transcription_enrich_message="",
                transcription_diarization_status=enrichment.get("diarization_enabled", False),
            )
            _mark_step(date_str, run_status, "transcribe_enrich", "completed", message="WhisperX 精标完成")
        except Exception as exc:
            update_pipeline_meta(
                cli.ensure_day_dir(date_str),
                transcription_enrich_status="failed",
                transcription_enrich_message=str(exc),
            )
            cli.console.print(f"[yellow]⚠️ 精标失败，继续主链[/yellow]: {exc}")
            _mark_step(date_str, run_status, "transcribe_enrich", "failed", message=str(exc))
    else:
        update_pipeline_meta(
            cli.ensure_day_dir(date_str),
            transcription_enrich_status="skipped",
            transcription_enrich_message="未启用 WhisperX 精标层",
        )
        _mark_step(date_str, run_status, "transcribe_enrich", "skipped", message="未启用 WhisperX 精标层")

    if args.skip_transcribe and not paths["raw"].exists() and not paths["transcript"].exists() and not paths["scenes"].exists():
        cli.console.print(f"[red]❌ {date_str} 没有可复用的数据，至少需要 transcript/raw/scenes 之一[/red]")
        _finish_run(date_str, run_status, "failed", "transcribe")
        return 1

    if not args.audio and not args.skip_transcribe and not paths["raw"].exists() and not paths["transcript"].exists():
        cli.console.print("[red]❌ 没有输入音频，也没有现成 raw/transcript 数据[/red]")
        _finish_run(date_str, run_status, "failed", "transcribe")
        return 1

    if not paths["transcript"].exists():
        _mark_step(date_str, run_status, "clean", "running", message="正在清洗转写")
        cli.console.print("\n[bold]🧹 清洗[/bold]")
        result = cli.cmd_clean(args)
        if result != 0:
            cli.console.print("[red]❌ 清洗失败，终止[/red]")
            _mark_step(date_str, run_status, "clean", "failed", message="清洗失败")
            _finish_run(date_str, run_status, "failed", "clean")
            return result
        paths = cli.resolve_day_paths(date_str)
        _mark_step(date_str, run_status, "clean", "completed", message="清洗完成", artifact=paths["transcript"])
    else:
        cli.console.print("\n[dim]⏭️ 跳过清洗：已存在 transcript.md[/dim]")
        _mark_step(date_str, run_status, "clean", "skipped", message="复用已有 transcript.md", artifact=paths["transcript"])

    scenes_data = cli.read_json(paths["scenes"], {}) if paths["scenes"].exists() else {}
    if not paths["scenes"].exists():
        _mark_step(date_str, run_status, "segment", "running", message="正在切分场景")
        cli.console.print("\n[bold]🔪 场景切分[/bold]")
        transcript_path = paths["transcript"]
        if not transcript_path.exists():
            cli.console.print(f"[red]❌ 找不到 {date_str} 的转写文本[/red]")
            _mark_step(date_str, run_status, "segment", "failed", message="缺少 transcript.md")
            _finish_run(date_str, run_status, "failed", "segment")
            return 1

        markdown = cli.strip_document_header(transcript_path.read_text(encoding="utf-8"))
        with cli.console.status("[bold cyan]🔪 场景切分中..."):
            result = cli.build_segmented_scenes_payload(markdown)
        scene_count = int(result.get("stats", {}).get("total_scenes", len(result.get("scenes", []))))

        output_path = cli.ensure_day_dir(date_str) / "scenes.json"
        cli.write_json(output_path, result)
        cli.console.print(f"[green]✅ 场景切分完成[/green]: {scene_count} 个场景")
        cli.console.print(f"[dim]ℹ️ 自动角色识别已冻结；如需重建场景可运行 openmy roles {date_str}[/dim]")
        paths = cli.resolve_day_paths(date_str)
        scenes_data = cli.read_json(paths["scenes"], {})
        if bool(getattr(args, "stt_align", False)):
            try:
                apply_transcription_enrichment_to_scenes(cli.ensure_day_dir(date_str))
                scenes_data = cli.read_json(paths["scenes"], {})
            except Exception as exc:
                cli.console.print(f"[yellow]⚠️ 场景未附加精标证据[/yellow]: {exc}")
        _mark_step(date_str, run_status, "segment", "completed", message=f"生成 {scene_count} 个场景", artifact=output_path)
    else:
        cli.console.print("\n[dim]⏭️ 跳过场景切分：已存在 scenes.json[/dim]")
        scenes_data = cli.freeze_scene_roles(scenes_data)
        cli.write_json(paths["scenes"], scenes_data)
        if bool(getattr(args, "stt_align", False)):
            try:
                apply_transcription_enrichment_to_scenes(cli.ensure_day_dir(date_str))
                scenes_data = cli.read_json(paths["scenes"], {})
            except Exception as exc:
                cli.console.print(f"[yellow]⚠️ 场景未附加精标证据[/yellow]: {exc}")
        _mark_step(date_str, run_status, "segment", "skipped", message="复用已有 scenes.json", artifact=paths["scenes"])

    cli.console.print("\n[dim]⏭️ 跳过角色识别：功能已冻结[/dim]")
    _mark_step(date_str, run_status, "roles", "skipped", message="角色识别已冻结", artifact=paths["scenes"])

    missing_summaries = [scene for scene in scenes_data.get("scenes", []) if not scene.get("summary")]
    if missing_summaries:
        if has_llm_credentials("distill"):
            _mark_step(date_str, run_status, "distill", "running", message=f"正在蒸馏 {len(missing_summaries)} 个场景")
            cli.console.print("\n[bold]🧪 蒸馏[/bold]")
            result = cli.cmd_distill(args)
            if result != 0:
                cli.console.print("[red]❌ 蒸馏失败，终止[/red]")
                _mark_step(date_str, run_status, "distill", "failed", message="蒸馏失败")
                _finish_run(date_str, run_status, "failed", "distill")
                return result
            _mark_step(date_str, run_status, "distill", "completed", message="蒸馏完成", artifact=paths["scenes"])
        else:
            cli.console.print("\n[yellow]⏭️ 跳过蒸馏：缺少可用 LLM provider key，继续生成基础日报[/yellow]")
            _mark_step(date_str, run_status, "distill", "skipped", message="缺少可用 LLM provider key")
    else:
        cli.console.print("\n[dim]⏭️ 跳过蒸馏：场景摘要已齐全[/dim]")
        _mark_step(date_str, run_status, "distill", "skipped", message="场景摘要已齐全", artifact=paths["scenes"])

    _mark_step(date_str, run_status, "briefing", "running", message="正在生成日报")
    cli.console.print("\n[bold]📋 日报[/bold]")
    result = cli.cmd_briefing(args)
    if result != 0:
        cli.console.print("[red]❌ 日报生成失败，终止[/red]")
        _mark_step(date_str, run_status, "briefing", "failed", message="日报生成失败")
        _finish_run(date_str, run_status, "failed", "briefing")
        return result
    _mark_step(date_str, run_status, "briefing", "completed", message="日报已生成", artifact=paths["briefing"])

    extract_core_failed = False
    extract_core_payload = None
    if has_llm_credentials("extract") and paths["transcript"].exists():
        _mark_step(date_str, run_status, "extract_core", "running", message="正在提取核心结构化摘要")
        cli.console.print("\n[bold]🔍 核心提取[/bold]")
        try:
            from openmy.services.extraction.extractor import run_core_extraction, save_meta_json

            _extract_model = get_stage_llm_model("extract") or GEMINI_MODEL
            extract_core_payload = run_core_extraction(
                str(paths["transcript"]),
                date=date_str,
                model=_extract_model,
                dry_run=False,
                raise_on_error=True,
            )
            meta_path = cli.ensure_day_dir(date_str) / f"{date_str}.meta.json"
            if extract_core_payload and not meta_path.exists():
                save_meta_json(extract_core_payload, date_str, str(cli.ensure_day_dir(date_str)))
            cli.console.print("[green]✅ 核心提取完成[/green]")
            _mark_step(
                date_str,
                run_status,
                "extract_core",
                "completed",
                message="核心结构化提取完成",
                artifact=meta_path if meta_path.exists() else paths["transcript"],
            )
        except Exception as exc:
            extract_core_failed = True
            cli.console.print(f"[red]❌ 核心提取失败[/red]: {exc}")
            cli.console.print("[yellow]⚠️ 已保留前面已完成的结果，可继续查看日报与场景。[/yellow]")
            _mark_step(date_str, run_status, "extract_core", "failed", message=str(exc))
    else:
        cli.console.print("\n[dim]⏭️ 跳过核心提取：缺少 LLM provider key 或转写文件[/dim]")
        _mark_step(date_str, run_status, "extract_core", "skipped", message="缺少 LLM provider key 或 transcript.md")
        _mark_step(date_str, run_status, "extract_enrich", "skipped", message="核心提取未执行")

    if extract_core_failed:
        _mark_step(date_str, run_status, "extract_enrich", "skipped", message="核心提取失败，跳过补全提取")
        _mark_step(date_str, run_status, "consolidate", "skipped", message="提取失败，跳过 active_context 聚合")
        _finish_run(date_str, run_status, "partial", "extract_core")
        cli.console.print(
            cli.Panel(
                f"[yellow]⚠️ {date_str} 部分完成[/yellow]\n核心提取失败，已写入 run_status.json；可先查看日报和场景结果。",
                border_style="yellow",
            )
        )
        return PARTIAL_SUCCESS

    _mark_step(date_str, run_status, "consolidate", "running", message="正在聚合 active_context")
    cli.console.print("\n[bold]🧠 聚合上下文[/bold]")
    try:
        from openmy.services.context.consolidation import consolidate

        data_root = cli.ensure_day_dir(date_str).parent
        consolidate(data_root)
        cli.console.print("[green]✅ active_context 已更新[/green]")
        _mark_step(date_str, run_status, "consolidate", "completed", message="active_context 已更新")
    except Exception as exc:
        cli.console.print(f"[yellow]⚠️ 聚合异常: {exc}，继续[/yellow]")
        _mark_step(date_str, run_status, "consolidate", "failed", message=f"聚合异常: {exc}")
        _mark_step(date_str, run_status, "extract_enrich", "skipped", message="聚合失败，跳过补全提取")
        _finish_run(date_str, run_status, "partial", "consolidate")
        return PARTIAL_SUCCESS

    if has_llm_credentials("extract") and paths["transcript"].exists() and extract_core_payload:
        _mark_step(date_str, run_status, "extract_enrich", "running", message="正在补全展示/溯源字段")
        cli.console.print("\n[bold]✨ 补全提取[/bold]")
        try:
            from openmy.services.extraction.extractor import (
                mark_enrichment_status,
                run_enrichment_extraction,
                save_meta_json,
            )

            _extract_model = get_stage_llm_model("extract") or GEMINI_MODEL
            enriched_payload = run_enrichment_extraction(
                str(paths["transcript"]),
                core_payload=extract_core_payload,
                date=date_str,
                model=_extract_model,
                dry_run=False,
                raise_on_error=False,
            )
            if enriched_payload and enriched_payload.get("extract_enrich_status") == "failed":
                cli.console.print(
                    f"[yellow]⚠️ 补全提取失败[/yellow]: {enriched_payload.get('extract_enrich_message', '')}"
                )
                _mark_step(
                    date_str,
                    run_status,
                    "extract_enrich",
                    "failed",
                    message=enriched_payload.get("extract_enrich_message", "补全提取失败"),
                )
            else:
                cli.console.print("[green]✅ 补全提取完成[/green]")
                meta_path = cli.ensure_day_dir(date_str) / f"{date_str}.meta.json"
                _mark_step(
                    date_str,
                    run_status,
                    "extract_enrich",
                    "completed",
                    message="展示/溯源字段补全完成",
                    artifact=meta_path if meta_path.exists() else paths["transcript"],
                )
        except Exception as exc:
            failed_payload = mark_enrichment_status(extract_core_payload, "failed", str(exc))
            save_meta_json(failed_payload, date_str, str(cli.ensure_day_dir(date_str)))
            cli.console.print(f"[yellow]⚠️ 补全提取异常[/yellow]: {exc}")
            _mark_step(date_str, run_status, "extract_enrich", "failed", message=str(exc))
    elif run_status["steps"]["extract_enrich"]["status"] == "pending":
        _mark_step(date_str, run_status, "extract_enrich", "skipped", message="缺少核心提取结果，未执行补全")

    cli.console.print(
        cli.Panel(
            f"[green]✅ {date_str} 处理完成！[/green]\n运行 [bold]openmy view {date_str}[/bold] 查看结果",
            border_style="green",
        )
    )
    final_step = "extract_enrich" if run_status["steps"]["extract_enrich"]["status"] != "pending" else "consolidate"
    _finish_run(date_str, run_status, "completed", final_step)
    return 0


def cmd_quick_start(args: argparse.Namespace) -> int:
    """面向第一次使用者的一键入口。"""
    cli = _cli()
    audio_path = Path(args.audio_path).expanduser()
    if not audio_path.exists():
        cli.console.print(f"[red]❌ 找不到音频文件[/red]: {audio_path}")
        return 1

    try:
        cli.ensure_runtime_dependencies(stt_provider=getattr(args, "stt_provider", None))
    except cli.FriendlyCliError as exc:
        cli.console.print(f"[red]❌ {exc}[/red]")
        return 1

    target_date = cli.infer_date_from_path(audio_path)
    cli.console.print(
        cli.Panel(
            f"🚀 OpenMy quick-start\n🎙️ 音频: {audio_path.name}\n📅 自动识别日期: {target_date}",
            border_style="bright_blue",
        )
    )

    run_args = argparse.Namespace(
        date=target_date,
        audio=[str(audio_path)],
        skip_transcribe=False,
        stt_provider=getattr(args, "stt_provider", None),
        stt_model=getattr(args, "stt_model", None),
        stt_vad=bool(getattr(args, "stt_vad", False)),
        stt_word_timestamps=bool(getattr(args, "stt_word_timestamps", False)),
        stt_align=bool(getattr(args, "stt_align", False)),
        stt_diarize=bool(getattr(args, "stt_diarize", False)),
    )
    result = cli.cmd_run(run_args, entrypoint="quick-start")
    if result not in (0, PARTIAL_SUCCESS):
        return result

    try:
        cli.launch_local_report()
    except Exception as exc:
        cli.console.print(f"[yellow]⚠️ 已处理完音频，但自动打开网页失败[/yellow]: {exc}")
        cli.console.print("[dim]你可以手动打开 http://127.0.0.1:8420[/dim]")
        return result

    if result == PARTIAL_SUCCESS:
        status_path = cli.ensure_day_dir(target_date) / "run_status.json"
        cli.console.print(f"[yellow]⚠️ 已打开本地日报页面，但提取阶段未完成[/yellow]: http://127.0.0.1:8420")
        cli.console.print(f"[dim]运行状态已写入 {status_path}[/dim]")
        return PARTIAL_SUCCESS

    cli.console.print("[green]✅ 已打开本地日报页面[/green]: http://127.0.0.1:8420")
    return 0

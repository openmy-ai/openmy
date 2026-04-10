from __future__ import annotations

import argparse
import os
from pathlib import Path


def _cli():
    from openmy import cli as cli_module

    return cli_module


def transcribe_audio_files(date_str: str, audio_files: list[str]) -> int:
    """把本地音频文件转成 raw transcript。"""
    cli = _cli()
    from openmy.services.ingest.audio_pipeline import transcribe_audio_files as run_ingest_pipeline

    try:
        output_path = run_ingest_pipeline(
            date_str=date_str,
            audio_files=audio_files,
            output_dir=cli.ensure_day_dir(date_str),
        )
    except Exception as exc:
        cli.console.print(f"[red]❌ 转写失败[/red]: {exc}")
        return 1

    cli.console.print(f"[green]✅ 原始转写已生成[/green]: {output_path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """全流程：转写 → 清洗 → 角色 → 蒸馏 → 日报。"""
    cli = _cli()
    date_str = args.date
    cli.console.print(
        cli.Panel(
            f"🎙️ OpenMy 全流程处理\n📅 日期: {date_str}",
            border_style="bright_blue",
        )
    )

    paths = cli.resolve_day_paths(date_str)
    if args.audio and not args.skip_transcribe:
        cli.console.print("[bold]Step 0: 🎙️ 转写音频[/bold]")
        result = transcribe_audio_files(date_str, args.audio)
        if result != 0:
            return result
        paths = cli.resolve_day_paths(date_str)

    if args.skip_transcribe and not paths["raw"].exists() and not paths["transcript"].exists() and not paths["scenes"].exists():
        cli.console.print(f"[red]❌ {date_str} 没有可复用的数据，至少需要 transcript/raw/scenes 之一[/red]")
        return 1

    if not args.audio and not args.skip_transcribe and not paths["raw"].exists() and not paths["transcript"].exists():
        cli.console.print("[red]❌ 没有输入音频，也没有现成 raw/transcript 数据[/red]")
        return 1

    if not paths["transcript"].exists():
        cli.console.print("\n[bold]🧹 清洗[/bold]")
        result = cli.cmd_clean(args)
        if result != 0:
            cli.console.print("[red]❌ 清洗失败，终止[/red]")
            return result
        paths = cli.resolve_day_paths(date_str)
    else:
        cli.console.print("\n[dim]⏭️ 跳过清洗：已存在 transcript.md[/dim]")

    scenes_data = cli.read_json(paths["scenes"], {}) if paths["scenes"].exists() else {}
    if not paths["scenes"].exists():
        cli.console.print("\n[bold]🔪 场景切分[/bold]")
        transcript_path = paths["transcript"]
        if not transcript_path.exists():
            cli.console.print(f"[red]❌ 找不到 {date_str} 的转写文本[/red]")
            return 1

        from openmy.services.segmentation.segmenter import segment, build_scenes_payload

        markdown = cli.strip_document_header(transcript_path.read_text(encoding="utf-8"))
        with cli.console.status("[bold cyan]🔪 场景切分中..."):
            raw_scenes = segment(markdown)
            result = build_scenes_payload(raw_scenes)
            result["stats"] = {"total_scenes": len(raw_scenes)}

        output_path = cli.ensure_day_dir(date_str) / "scenes.json"
        cli.write_json(output_path, result)
        cli.console.print(f"[green]✅ 场景切分完成[/green]: {len(raw_scenes)} 个场景")
        cli.console.print("[dim]ℹ️ 角色归因已冻结，如需手动归因可运行 openmy roles {date_str}[/dim]")
        paths = cli.resolve_day_paths(date_str)
        scenes_data = cli.read_json(paths["scenes"], {})
    else:
        cli.console.print("\n[dim]⏭️ 跳过场景切分：已存在 scenes.json[/dim]")

    if os.getenv("GEMINI_API_KEY", "").strip():
        cli.console.print("\n[bold]👥 角色识别[/bold]")
        try:
            from openmy.domain.models import SceneBlock
            from openmy.services.roles.resolver import resolve_roles as _resolve_roles, scenes_to_dict

            raw_scenes_list = scenes_data.get("scenes", [])
            scene_blocks = [
                SceneBlock.from_dict(s)
                if hasattr(SceneBlock, "from_dict")
                else SceneBlock(
                    scene_id=s.get("scene_id", ""),
                    time_start=s.get("time_start", ""),
                    time_end=s.get("time_end", ""),
                    text=s.get("text", ""),
                    preview=s.get("preview", ""),
                )
                for s in raw_scenes_list
            ]
            screen_client = cli.get_screen_client()
            scene_blocks = _resolve_roles(scene_blocks, date_str=date_str, screen_client=screen_client)
            result = scenes_to_dict(scene_blocks)

            output_path = cli.ensure_day_dir(date_str) / "scenes.json"
            cli.write_json(output_path, result)
            paths = cli.resolve_day_paths(date_str)
            scenes_data = cli.read_json(paths["scenes"], {})
            cli.console.print("[green]✅ 角色识别完成[/green]")
        except Exception as exc:
            cli.console.print(f"[yellow]⚠️ 角色识别异常: {exc}，继续[/yellow]")
    else:
        cli.console.print("\n[dim]⏭️ 跳过角色识别：缺少 GEMINI_API_KEY[/dim]")

    missing_summaries = [scene for scene in scenes_data.get("scenes", []) if not scene.get("summary")]
    if missing_summaries:
        if os.getenv("GEMINI_API_KEY", "").strip():
            cli.console.print("\n[bold]🧪 蒸馏[/bold]")
            result = cli.cmd_distill(args)
            if result != 0:
                cli.console.print("[red]❌ 蒸馏失败，终止[/red]")
                return result
        else:
            cli.console.print("\n[yellow]⏭️ 跳过蒸馏：缺少 GEMINI_API_KEY，继续生成基础日报[/yellow]")
    else:
        cli.console.print("\n[dim]⏭️ 跳过蒸馏：场景摘要已齐全[/dim]")

    cli.console.print("\n[bold]📋 日报[/bold]")
    result = cli.cmd_briefing(args)
    if result != 0:
        cli.console.print("[red]❌ 日报生成失败，终止[/red]")
        return result

    if os.getenv("GEMINI_API_KEY", "").strip() and paths["transcript"].exists():
        cli.console.print("\n[bold]🔍 提取[/bold]")
        try:
            from openmy.services.extraction.extractor import run_extraction
            from openmy.config import GEMINI_MODEL as _extract_model

            run_extraction(
                str(paths["transcript"]),
                date=date_str,
                model=_extract_model,
            )
            cli.console.print("[green]✅ 提取完成[/green]")
        except Exception as exc:
            cli.console.print(f"[yellow]⚠️ 提取异常: {exc}，继续[/yellow]")
    else:
        cli.console.print("\n[dim]⏭️ 跳过提取：缺少 API key 或转写文件[/dim]")

    cli.console.print("\n[bold]🧠 聚合上下文[/bold]")
    try:
        from openmy.services.context.consolidation import consolidate

        data_root = cli.ensure_day_dir(date_str).parent
        consolidate(data_root)
        cli.console.print("[green]✅ active_context 已更新[/green]")
    except Exception as exc:
        cli.console.print(f"[yellow]⚠️ 聚合异常: {exc}，继续[/yellow]")

    cli.console.print(
        cli.Panel(
            f"[green]✅ {date_str} 处理完成！[/green]\n运行 [bold]openmy view {date_str}[/bold] 查看结果",
            border_style="green",
        )
    )
    return 0


def cmd_quick_start(args: argparse.Namespace) -> int:
    """面向第一次使用者的一键入口。"""
    cli = _cli()
    audio_path = Path(args.audio_path).expanduser()
    if not audio_path.exists():
        cli.console.print(f"[red]❌ 找不到音频文件[/red]: {audio_path}")
        return 1

    try:
        cli.ensure_runtime_dependencies()
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
    )
    result = cli.cmd_run(run_args)
    if result != 0:
        return result

    try:
        cli.launch_local_report()
    except Exception as exc:
        cli.console.print(f"[yellow]⚠️ 已处理完音频，但自动打开网页失败[/yellow]: {exc}")
        cli.console.print("[dim]你可以手动打开 http://127.0.0.1:8420[/dim]")
        return 0

    cli.console.print("[green]✅ 已打开本地日报页面[/green]: http://127.0.0.1:8420")
    return 0

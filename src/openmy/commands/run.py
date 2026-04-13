from __future__ import annotations

import argparse
import os
import signal
import subprocess
import tempfile
import time
import wave
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from dataclasses import asdict, is_dataclass

from openmy.config import (
    DEFAULT_STT_MODELS,
    GEMINI_MODEL,
    LOCAL_STT_PROVIDERS,
    get_audio_source_dir,
    get_export_provider_name,
    get_stage_llm_model,
    get_stt_api_key,
    get_stt_provider_name,
    has_llm_credentials,
    stt_provider_requires_api_key,
)
from openmy.services.feedback import record_processing_success
from openmy.services.ingest.audio_pipeline import AUDIO_SOURCE_EXTENSIONS
from openmy.utils.interactive import prompt_input, select_option, strip_dragged_path


def _discover_audio_inputs(date_str: str) -> tuple[list[str], str]:
    from openmy.services.ingest.audio_pipeline import discover_configured_audio_files

    source_dir = str(get_audio_source_dir() or "").strip()
    if not source_dir:
        return [], "missing_source_dir"
    return discover_configured_audio_files(date_str), source_dir


STALE_RUN_MIN_AGE_SECONDS = 300


def _kill_stale_runs(date_str: str) -> int:
    if os.name == "nt":
        return 0
    try:
        result = subprocess.run(
            ["ps", "-Ao", "pid=,etimes=,command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return 0
    current_pid = os.getpid()
    killed = 0
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid_text, etimes_text, command_text = parts
        if not pid_text.isdigit() or not etimes_text.isdigit():
            continue
        pid = int(pid_text)
        etimes = int(etimes_text)
        if pid == current_pid:
            continue
        if etimes < STALE_RUN_MIN_AGE_SECONDS:
            continue
        if date_str not in command_text:
            continue
        if "openmy" not in command_text:
            continue
        if " run " not in f" {command_text} " and "openmy.cli run" not in command_text:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except OSError:
            continue
    return killed


PARTIAL_SUCCESS = 2
RUN_TIMEOUT_SECONDS = 1800
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
    "aggregate",
)


def _cli():
    from openmy import cli as cli_module

    return cli_module


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _build_demo_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    duration_seconds = 3
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * sample_rate * duration_seconds)


def _prepare_demo_inputs() -> tuple[Path, str]:
    cli = _cli()
    fixture_dir = cli.ROOT_DIR / "tests" / "fixtures"
    fixture_audio = fixture_dir / "sample.wav"
    fixture_transcript = fixture_dir / "sample.transcript.txt"

    transcript_text = fixture_transcript.read_text(encoding="utf-8").strip() if fixture_transcript.exists() else "今天先体验 OpenMy 的整条主链。"
    temp_dir = Path(tempfile.mkdtemp(prefix="openmy-demo-"))
    demo_audio = temp_dir / "TX01_MIC005_20991231_120000_demo.wav"
    if fixture_audio.exists():
        demo_audio.write_bytes(fixture_audio.read_bytes())
    else:
        _build_demo_wav(demo_audio)

    try:
        with wave.open(str(demo_audio), "rb"):
            pass
    except Exception:
        _build_demo_wav(demo_audio)

    demo_audio.with_suffix(".transcript.txt").write_text(transcript_text, encoding="utf-8")
    return demo_audio, transcript_text


PROVIDER_ORDER = ["gemini", "faster-whisper", "funasr", "dashscope", "groq", "deepgram"]


PROVIDER_DESCRIPTIONS = {
    "gemini": "云端，需 API Key，速度快，推荐",
    "faster-whisper": "本地，免费，需显卡效果更好",
    "funasr": "本地，免费，中文优化",
    "dashscope": "云端，需 API Key",
    "groq": "云端，需 API Key，速度极快",
    "deepgram": "云端，需 API Key",
}


PROVIDER_KEY_ENV_MAP = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "deepgram": "DEEPGRAM_API_KEY",
}


def _provider_options() -> list[str]:
    return [f"{name:<16}（{PROVIDER_DESCRIPTIONS[name]}）" for name in PROVIDER_ORDER]


def _pick_provider(default_provider: str | None = None) -> str:
    ordered = list(PROVIDER_ORDER)
    options = _provider_options()
    chosen_index = 0
    if default_provider in ordered:
        chosen_index = ordered.index(str(default_provider))
    if chosen_index:
        options = options[chosen_index:] + options[:chosen_index]
        ordered = ordered[chosen_index:] + ordered[:chosen_index]
    selected = select_option("🚀 欢迎使用 OpenMy！\n\n第 1 步：选择你的转写引擎", options)
    return ordered[selected]


def _ensure_provider_configured(provider_name: str) -> str | None:
    cli = _cli()
    cli._upsert_project_env("OPENMY_STT_PROVIDER", provider_name)
    if not stt_provider_requires_api_key(provider_name):
        return None

    env_name = PROVIDER_KEY_ENV_MAP.get(provider_name)
    existing = get_stt_api_key(provider_name)
    if existing or not env_name:
        return None

    while True:
        raw_key = prompt_input(
            "第 1 步补充：这个引擎需要一把钥匙",
            f"把 {env_name} 粘进来。想重选引擎就输 back。",
        )
        final_key = raw_key.strip()
        if not final_key:
            continue
        if final_key.lower() == "back":
            return "back"
        cli._upsert_project_env(env_name, final_key)
        return None


def _prompt_audio_path() -> tuple[Path | None, bool]:
    while True:
        raw_value = prompt_input(
            "第 2 步：你的音频文件在哪？",
            "请输入音频文件路径（支持把文件拖进终端）。没有音频就输入 demo。",
        )
        if not raw_value:
            continue
        if raw_value.strip().lower() == "demo":
            return (None, True)

        audio_path = Path(strip_dragged_path(raw_value))
        if not audio_path.exists():
            print("没找到这个文件，再来一次。")
            continue
        if not audio_path.is_file():
            print("这不是文件，再来一次。")
            continue
        if audio_path.suffix.lower() not in AUDIO_SOURCE_EXTENSIONS:
            print("这个格式不在支持名单里，再来一次。")
            continue
        return (audio_path, False)


def _confirm_quick_start(target_date: str, audio_label: str, provider_name: str) -> str:
    options = [
        "✅ 开始处理",
        "✏️ 重新选择引擎",
        "📂 换一个文件",
        "❌ 取消",
    ]
    index = select_option(
        "第 3 步：确认信息\n\n"
        f"  📅 日期：{target_date}\n"
        f"  🎙️ 文件：{audio_label}\n"
        f"  🔧 引擎：{provider_name}",
        options,
    )
    return ["start", "provider", "audio", "cancel"][index]


def _run_quick_start_wizard(initial_provider: str | None = None) -> dict | None:
    provider_name = initial_provider or get_stt_provider_name() or "gemini"
    audio_path: Path | None = None
    use_demo = False

    while True:
        provider_name = _pick_provider(provider_name)
        provider_status = _ensure_provider_configured(provider_name)
        if provider_status == "back":
            continue

        while True:
            audio_path, use_demo = _prompt_audio_path()
            if use_demo:
                target_date = "2099-12-31"
                audio_label = "内置示例"
            else:
                assert audio_path is not None
                target_date = _cli().infer_date_from_path(audio_path)
                audio_label = audio_path.name

            action = _confirm_quick_start(target_date, audio_label, provider_name)
            if action == "start":
                return {
                    "provider_name": provider_name,
                    "audio_path": audio_path,
                    "use_demo": use_demo,
                }
            if action == "provider":
                break
            if action == "audio":
                continue
            return None


def _seed_demo_transcript(date_str: str, transcript_text: str) -> None:
    cli = _cli()
    day_dir = cli.ensure_day_dir(date_str)
    raw_path = day_dir / "transcript.raw.md"
    transcript_path = day_dir / "transcript.md"
    scenes_path = day_dir / "scenes.json"
    meta_path = day_dir / f"{date_str}.meta.json"
    briefing_path = day_dir / "daily_briefing.json"
    noisy_text = (
        "# OpenMy demo 原始转写\n\n---\n\n## 12:00\n\n"
        f"呃，那个，{transcript_text.strip()} 然后这个，啊，我晚点再整理一下。"
        "\n"
    )
    cleaned_text = "# OpenMy demo\n\n---\n\n## 12:00\n\n今晚先吃火锅，再把 OpenMy 的 day.run 成功链路验一遍。\n"
    raw_path.write_text(
        noisy_text,
        encoding="utf-8",
    )
    transcript_path.write_text(cleaned_text, encoding="utf-8")
    cli.write_json(
        scenes_path,
        {
            "scenes": [
                {
                    "scene_id": "s01",
                    "time_start": "12:00",
                    "time_end": "12:00",
                    "text": "今晚先吃火锅，再把 OpenMy 的 day.run 成功链路验一遍。",
                    "role": {
                        "category": "uncertain",
                        "entity_id": "",
                        "relation_label": "",
                        "confidence": 0.0,
                        "evidence_chain": [],
                        "scene_type": "uncertain",
                        "scene_type_label": "不确定",
                        "addressed_to": "",
                        "about": "",
                        "source": "frozen",
                        "source_label": "已冻结",
                        "evidence": "角色识别已冻结",
                        "needs_review": False,
                    },
                    "keywords_matched": [],
                    "summary": "今晚先吃火锅，再把 OpenMy 主链复验一遍。",
                    "preview": "今晚先吃火锅，再把 OpenMy 主链复验一遍。",
                    "screen_sessions": [],
                    "screen_context": {
                        "enabled": False,
                        "participation_mode": "off",
                        "aligned": False,
                        "summary": "",
                        "primary_app": "",
                        "primary_window": "",
                        "primary_domain": "",
                        "tags": [],
                        "sensitive": False,
                        "summary_only": False,
                        "has_task_signal": False,
                        "evidence_conflict": False,
                        "completion_candidates": [],
                        "evidences": [],
                    },
                }
            ],
            "stats": {
                "total_scenes": 1,
                "role_distribution": {},
                "needs_review_count": 0,
                "role_recognition_status": "frozen",
            },
        },
    )
    cli.write_json(
        meta_path,
        {
            "date": date_str,
            "daily_summary": "今晚先吃火锅，再把 OpenMy 主链复验一遍。",
            "events": [],
            "decisions": [],
            "todos": [],
            "insights": [],
            "intents": [],
            "facts": [],
            "extract_enrich_status": "skipped",
            "extract_enrich_message": "demo 预置结果",
        },
    )
    if briefing_path.exists():
        briefing_path.unlink()


def _demo_transcript_stats(day_dir: Path) -> tuple[Path | None, Path | None, int, int, int, int]:
    raw_path = day_dir / "transcript.raw.md"
    clean_path = day_dir / "transcript.md"
    if not raw_path.exists() or not clean_path.exists():
        return raw_path if raw_path.exists() else None, clean_path if clean_path.exists() else None, 0, 0, 0, 0

    raw_text = raw_path.read_text(encoding="utf-8")
    clean_text = clean_path.read_text(encoding="utf-8")
    raw_lines = len([line for line in raw_text.splitlines() if line.strip()])
    clean_lines = len([line for line in clean_text.splitlines() if line.strip()])
    raw_chars = len("".join(raw_text.split()))
    clean_chars = len("".join(clean_text.split()))
    return raw_path, clean_path, raw_lines, clean_lines, raw_chars, clean_chars


def _print_demo_before_after(date_str: str) -> None:
    cli = _cli()
    day_dir = cli.ensure_day_dir(date_str)
    raw_path, clean_path, raw_lines, clean_lines, raw_chars, clean_chars = _demo_transcript_stats(day_dir)
    if raw_path is None or clean_path is None:
        return

    raw_preview = raw_path.read_text(encoding="utf-8").splitlines()[-1].strip()
    clean_preview = clean_path.read_text(encoding="utf-8").splitlines()[-1].strip()
    retention = 0 if raw_chars <= 0 else round(clean_chars / raw_chars * 100)
    raw_full = raw_path.read_text(encoding="utf-8")
    filler_terms = ("呃", "嗯", "啊", "那个", "就是说")
    removed_fillers = sum(raw_full.count(token) for token in filler_terms)
    cli.console.print(
        cli.Panel(
            "原始转写 vs 清洗后\n\n"
            f"原始：{raw_preview}\n"
            f"清洗后：{clean_preview}\n\n"
            f"原始有效行数：{raw_lines}\n"
            f"清洗后有效行数：{clean_lines}\n"
            f"噪音过滤率：{max(0, 100 - retention)}%（去掉了约 {removed_fillers} 个填充词和重复）",
            title="🎧 demo 对比",
            border_style="magenta",
        )
    )


def _collect_quick_start_onboarding(stt_provider_override: str | None = None) -> dict:
    cli = _cli()
    from openmy.services.cleaning.cleaner import CORRECTIONS_FILE, VOCAB_FILE
    from openmy.services.context.consolidation import profile_path
    from openmy.services.onboarding.state import build_onboarding_state, save_onboarding_state

    current_stt = (stt_provider_override or get_stt_provider_name()).lower().strip()
    stt_providers: list[dict[str, object]] = []
    for name, default_model in DEFAULT_STT_MODELS.items():
        needs_key = stt_provider_requires_api_key(name)
        stt_providers.append({
            "name": name,
            "type": "local" if name in LOCAL_STT_PROVIDERS else "api",
            "default_model": default_model,
            "needs_api_key": needs_key,
            "api_key_configured": bool(get_stt_api_key(name)) if needs_key else True,
            "is_active": name == current_stt,
            "ready": bool(get_stt_api_key(name)) if needs_key else True,
        })

    payload = build_onboarding_state(
        data_root=cli.DATA_ROOT,
        stt_providers=stt_providers,
        current_stt=current_stt,
        profile_exists=profile_path(cli.DATA_ROOT).exists(),
        vocab_exists=CORRECTIONS_FILE.exists() and VOCAB_FILE.exists(),
    )
    save_onboarding_state(cli.DATA_ROOT, payload)
    return payload


def _print_quick_start_onboarding(onboarding: dict) -> None:
    cli = _cli()
    recommended = onboarding.get("recommended_label") or onboarding.get("recommended_provider") or "先做环境检查"
    reason = onboarding.get("recommended_reason") or onboarding.get("next_step") or "先把第一次使用走通。"
    provider = onboarding.get("recommended_provider") or "faster-whisper"
    cli.console.print(
        cli.Panel(
            "[yellow]⚠️ 还差一步才能开始第一次转写[/yellow]\n"
            f"推荐路线：{recommended}\n"
            f"原因：{reason}\n\n"
            f"现在直接运行 [bold]openmy skill profile.set --stt-provider {provider} --json[/bold]，\n"
            "先把这条路线定下来，再回来跑 quick-start。",
            border_style="yellow",
        )
    )


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
                "skip_reason": "",
            }
            for step in RUN_STEPS
        },
    }
    cli.write_json(cli.ensure_day_dir(date_str) / "run_status.json", payload)
    return payload


def _save_run_status(date_str: str, payload: dict) -> None:
    cli = _cli()
    cli.write_json(cli.ensure_day_dir(date_str) / "run_status.json", payload)


def _clear_downstream_artifacts(date_str: str) -> list[Path]:
    cli = _cli()
    day_dir = cli.ensure_day_dir(date_str)
    backups: list[Path] = []
    for path in [
        day_dir / "transcript.md",
        day_dir / "scenes.json",
        day_dir / "daily_briefing.json",
        day_dir / f"{date_str}.meta.json",
    ]:
        if not path.exists():
            continue
        backup_path = path.with_name(f"{path.name}.bak")
        backup_path.unlink(missing_ok=True)
        path.replace(backup_path)
        backups.append(backup_path)
    return backups


def _cleanup_downstream_backups(backups: list[Path]) -> None:
    for backup_path in backups:
        backup_path.unlink(missing_ok=True)


def _export_outputs(date_str: str, *, briefing_path: Path, context_snapshot: dict | None = None) -> None:
    export_provider_name = get_export_provider_name()
    if not export_provider_name:
        return

    cli = _cli()
    try:
        from openmy.providers.registry import ProviderRegistry

        provider = ProviderRegistry.from_env().get_export_provider()
        briefing_payload = cli.read_json(briefing_path, {})
        result = provider.export_daily_briefing(date_str, briefing_payload)
        destination = result.get("url") or result.get("path") or export_provider_name
        cli.console.print(f"[green]✅ 已导出日报[/green]: {destination}")
        if context_snapshot:
            provider.export_context_snapshot(context_snapshot)
    except Exception as exc:
        cli.console.print(f"[yellow]⚠️ 导出失败，继续主链[/yellow]: {exc}")


def _count_week_briefings(data_root: Path, date_str: str) -> tuple[str, int]:
    from openmy.services.aggregation.weekly import list_week_dates, parse_week_str
    from openmy.services.aggregation import current_week_str

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    week_str = current_week_str(target_date)
    _, week_start, week_end = parse_week_str(week_str)
    count = 0
    for day in list_week_dates(week_start, week_end):
        if (data_root / day.isoformat() / "daily_briefing.json").exists():
            count += 1
    return week_str, count


def _is_last_week_of_month(date_str: str) -> bool:
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    last_day = target_date.replace(day=monthrange(target_date.year, target_date.month)[1])
    return target_date.isocalendar()[:2] == last_day.isocalendar()[:2]


def _run_aggregation(date_str: str, run_status: dict, *, skip_aggregate: bool) -> None:
    cli = _cli()
    data_root = cli.ensure_day_dir(date_str).parent
    if skip_aggregate:
        _mark_step(
            date_str,
            run_status,
            "aggregate",
            "skipped",
            message="按参数跳过周/月聚合",
            skip_reason="disabled_by_flag",
        )
        return

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    week_str, briefing_count = _count_week_briefings(data_root, date_str)
    should_generate_weekly = target_date.isoweekday() == 7 or briefing_count >= 7
    should_generate_monthly = _is_last_week_of_month(date_str)

    if not should_generate_weekly and not should_generate_monthly:
        _mark_step(
            date_str,
            run_status,
            "aggregate",
            "skipped",
            message="本次未触发周/月聚合",
            skip_reason="not_due",
        )
        return

    labels = []
    if should_generate_weekly:
        labels.append("周回顾")
    if should_generate_monthly:
        labels.append("月回顾")
    _mark_step(
        date_str,
        run_status,
        "aggregate",
        "running",
        message=f"正在生成{' + '.join(labels)}",
    )
    try:
        from openmy.services.aggregation import current_month_str, generate_monthly_review, generate_weekly_review

        artifacts: list[str] = []
        if should_generate_weekly:
            weekly_review = generate_weekly_review(data_root, week_str)
            artifacts.append(str(data_root / "weekly" / f"{weekly_review['week']}.json"))
        if should_generate_monthly:
            month_str = current_month_str(target_date)
            monthly_review = generate_monthly_review(data_root, month_str)
            artifacts.append(str(data_root / "monthly" / f"{monthly_review['month']}.json"))
        _mark_step(
            date_str,
            run_status,
            "aggregate",
            "completed",
            message=f"已生成{' + '.join(labels)}",
        )
        for artifact in artifacts:
            _mark_step(date_str, run_status, "aggregate", run_status["steps"]["aggregate"]["status"], artifact=artifact)
    except Exception as exc:
        cli.console.print(f"[yellow]⚠️ 周/月聚合失败，继续主链[/yellow]: {exc}")
        _mark_step(date_str, run_status, "aggregate", "failed", message=str(exc))


def _mark_step(
    date_str: str,
    payload: dict,
    step: str,
    status: str,
    *,
    message: str = "",
    artifact: str | Path | None = None,
    skip_reason: str = "",
) -> None:
    step_payload = payload["steps"][step]
    step_payload["status"] = status
    step_payload["message"] = message
    step_payload["updated_at"] = _now_iso()
    step_payload["skip_reason"] = skip_reason if status == "skipped" else ""
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


def _run_timed_out(started_monotonic: float, timeout_seconds: int = RUN_TIMEOUT_SECONDS) -> bool:
    return time.monotonic() - started_monotonic > timeout_seconds


def _return_timeout_if_needed(
    date_str: str,
    payload: dict,
    current_step: str,
    started_monotonic: float,
    timeout_seconds: int = RUN_TIMEOUT_SECONDS,
) -> int | None:
    if not _run_timed_out(started_monotonic, timeout_seconds):
        return None
    message = f"处理超时（{timeout_seconds // 60}分钟），已保存当前进度"
    step_payload = payload["steps"].get(current_step)
    if step_payload is not None:
        base_message = str(step_payload.get("message", "") or "").strip()
        step_payload["message"] = f"{base_message}；{message}" if base_message else message
        step_payload["updated_at"] = _now_iso()
        _save_run_status(date_str, payload)
    _finish_run(date_str, payload, "timeout", current_step)
    _cli().console.print(f"[yellow]⏰ {message}[/yellow]")
    return PARTIAL_SUCCESS


def _load_existing_core_payload(date_str: str) -> dict | None:
    cli = _cli()
    meta_path = cli.ensure_day_dir(date_str) / f"{date_str}.meta.json"
    if not meta_path.exists():
        return None
    payload = cli.read_json(meta_path, {})
    if not isinstance(payload, dict):
        return None
    if str(payload.get("daily_summary", "") or "").strip():
        return payload
    if any(isinstance(item, dict) for item in payload.get("intents", [])):
        return payload
    if any(isinstance(item, dict) for item in payload.get("facts", [])):
        return payload
    return None


def run_transcription_enrichment(day_dir: Path, *, diarize: bool = False) -> dict:
    from openmy.services.ingest.transcription_enrichment import run_transcription_enrichment as _run

    return _run(day_dir, diarize=diarize)


def plan_transcription_enrichment(*, provider_name: str, enrich_mode: str, diarize_requested: bool) -> dict:
    from openmy.services.ingest.transcription_enrichment import plan_transcription_enrichment as _plan

    return _plan(
        provider_name=provider_name,
        enrich_mode=enrich_mode,
        diarize_requested=diarize_requested,
        diarization_token=os.getenv("HF_TOKEN", "") or os.getenv("HUGGINGFACE_TOKEN", ""),
    )


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
) -> tuple[int, str]:
    """把本地音频文件转成 raw transcript。返回 (exit_code, error_message)。"""
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
        error_msg = str(exc)
        cli.console.print(f"[red]❌ 转写失败[/red]: {error_msg}")
        return 1, error_msg

    cli.console.print(f"[green]✅ 原始转写已生成[/green]: {output_path}")
    return 0, ""


def _normalize_transcribe_result(result: object) -> tuple[int, str]:
    """兼容旧测试替身：既接受 int，也接受 (code, message)。"""
    if isinstance(result, tuple):
        if len(result) == 0:
            return 1, "unknown transcription error"
        code = int(result[0])
        message = str(result[1]) if len(result) > 1 and result[1] is not None else ""
        return code, message
    return int(result), ""


def cmd_run(args: argparse.Namespace, *, entrypoint: str = "run") -> int:
    """全流程：转写 → 清洗 → 角色 → 蒸馏 → 日报。"""
    cli = _cli()
    date_str = args.date
    started_monotonic = time.monotonic()
    if not getattr(args, "audio", None) and not getattr(args, "skip_transcribe", False):
        paths = cli.resolve_day_paths(date_str)
        has_reusable = paths["raw"].exists() or paths["transcript"].exists() or paths["scenes"].exists()
        if not has_reusable:
            discovered_audio, source_dir = _discover_audio_inputs(date_str)
            if discovered_audio:
                args.audio = discovered_audio
                cli.console.print(f"[green]✅ 已从固定录音目录找到 {len(discovered_audio)} 段音频[/green]")
            elif source_dir == "missing_source_dir":
                cli.console.print(
                    "[red]❌ 还没配置录音固定目录，也没有手动传音频。[/red]\n"
                    "请先设置 OPENMY_AUDIO_SOURCE_DIR，或这次直接传 --audio。"
                )
                return 1
            else:
                cli.console.print(
                    f"[red]❌ 固定录音目录里没有找到 {date_str} 的音频。[/red]\n"
                    f"当前目录：{source_dir}"
                )
                return 1
    run_status = _init_run_status(date_str, entrypoint)
    stale_runs_killed = _kill_stale_runs(date_str)
    if stale_runs_killed:
        cli.console.print(f"[yellow]♻️ 已结束 {stale_runs_killed} 个旧的 openmy run 进程[/yellow]")
    cli.console.print(
        cli.Panel(
            f"🎙️ OpenMy 全流程处理\n📅 日期: {date_str}",
            border_style="bright_blue",
        )
    )

    paths = cli.resolve_day_paths(date_str)
    downstream_backups: list[Path] = []
    if args.audio and not args.skip_transcribe:
        stt_provider = getattr(args, "stt_provider", None) or get_stt_provider_name()
        if not stt_provider:
            cli.console.print(
                cli.Panel(
                    "[red]❌ 尚未选择转写引擎[/red]\n"
                    "请先运行 [bold]openmy skill health.check --json[/bold] 查看可用引擎，\n"
                    "然后在 .env 中设置 OPENMY_STT_PROVIDER（如 gemini、faster-whisper、dashscope）。\n\n"
                    "本地引擎（无需 API Key）：faster-whisper、funasr\n"
                    "云端引擎（需 API Key）：gemini、dashscope、groq、deepgram",
                    border_style="red",
                )
            )
            _mark_step(date_str, run_status, "transcribe", "failed",
                       message="未选择转写引擎：请先运行 profile.set 选定推荐路线")
            _finish_run(date_str, run_status, "failed", "transcribe")
            return 1
        _mark_step(date_str, run_status, "transcribe", "running", message="正在转写音频")
        cli.console.print("[bold]Step 0: 🎙️ 转写音频[/bold]")
        raw_result = transcribe_audio_files(
            date_str,
            args.audio,
            stt_provider=getattr(args, "stt_provider", None),
            stt_model=getattr(args, "stt_model", None),
            stt_vad=bool(getattr(args, "stt_vad", False)),
            stt_word_timestamps=bool(getattr(args, "stt_word_timestamps", False)),
        )
        result, error_msg = _normalize_transcribe_result(raw_result)
        if result != 0:
            _mark_step(date_str, run_status, "transcribe", "failed", message=f"转写失败: {error_msg}")
            _finish_run(date_str, run_status, "failed", "transcribe")
            return result
        downstream_backups = _clear_downstream_artifacts(date_str)
        paths = cli.resolve_day_paths(date_str)
        _mark_step(date_str, run_status, "transcribe", "completed", message="转写完成", artifact=paths["raw"])
    else:
        _mark_step(date_str, run_status, "transcribe", "skipped", message="未执行新的音频转写", skip_reason="no_new_audio")
    timeout_result = _return_timeout_if_needed(date_str, run_status, "transcribe", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    from openmy.services.ingest.transcription_enrichment import update_pipeline_meta

    update_pipeline_meta(
        cli.ensure_day_dir(date_str),
        transcription_provider=getattr(args, "stt_provider", None) or get_stt_provider_name(),
        transcription_model=getattr(args, "stt_model", None) or "",
        transcription_vad=bool(getattr(args, "stt_vad", False)),
        transcription_word_timestamps=bool(getattr(args, "stt_word_timestamps", False)),
        transcription_enrich_mode=getattr(args, "stt_enrich_mode", "recommended"),
    )

    final_provider_name = (getattr(args, "stt_provider", None) or get_stt_provider_name()).lower()
    requested_enrich_mode = str(getattr(args, "stt_enrich_mode", "recommended") or "recommended").lower()
    enrich_mode = requested_enrich_mode
    if bool(getattr(args, "stt_align", False)):
        enrich_mode = "force"
    diarize_requested = bool(getattr(args, "stt_diarize", False) or requested_enrich_mode == "recommended")
    enrichment_plan = plan_transcription_enrichment(
        provider_name=final_provider_name,
        enrich_mode=enrich_mode,
        diarize_requested=diarize_requested,
    )

    if enrichment_plan["enabled"]:
        _mark_step(date_str, run_status, "transcribe_enrich", "running", message="正在执行 WhisperX 精标")
        try:
            run_transcription_enrichment(
                cli.ensure_day_dir(date_str),
                diarize=bool(enrichment_plan.get("diarize", False)),
            )
            update_pipeline_meta(
                cli.ensure_day_dir(date_str),
                transcription_enrich_status="completed",
                transcription_enrich_message=enrichment_plan.get("message", ""),
                transcription_diarization_status=enrichment_plan.get("diarization_status", "disabled"),
            )
            _mark_step(date_str, run_status, "transcribe_enrich", "completed", message="WhisperX 精标完成")
        except Exception as exc:
            update_pipeline_meta(
                cli.ensure_day_dir(date_str),
                transcription_enrich_status="failed",
                transcription_enrich_message=str(exc),
                transcription_diarization_status=enrichment_plan.get("diarization_status", "disabled"),
            )
            cli.console.print(f"[yellow]⚠️ 精标失败，继续主链[/yellow]: {exc}")
            _mark_step(date_str, run_status, "transcribe_enrich", "failed", message=str(exc))
    else:
        update_pipeline_meta(
            cli.ensure_day_dir(date_str),
            transcription_enrich_status=enrichment_plan.get("status", "skipped"),
            transcription_enrich_message=enrichment_plan.get("message", "未启用 WhisperX 精标层"),
            transcription_diarization_status=enrichment_plan.get("diarization_status", "disabled"),
        )
        _mark_step(
            date_str,
            run_status,
            "transcribe_enrich",
            "failed" if enrichment_plan.get("status") == "failed" else "skipped",
            message=enrichment_plan.get("message", "未启用 WhisperX 精标层"),
            skip_reason=("enrichment_unavailable" if enrichment_plan.get("status") != "failed" else ""),
        )
    timeout_result = _return_timeout_if_needed(date_str, run_status, "transcribe_enrich", started_monotonic)
    if timeout_result is not None:
        return timeout_result

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
        _mark_step(date_str, run_status, "clean", "skipped", message="复用已有 transcript.md", artifact=paths["transcript"], skip_reason="existing_transcript")
    timeout_result = _return_timeout_if_needed(date_str, run_status, "clean", started_monotonic)
    if timeout_result is not None:
        return timeout_result

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
        _mark_step(date_str, run_status, "segment", "skipped", message="复用已有 scenes.json", artifact=paths["scenes"], skip_reason="existing_scenes")
    timeout_result = _return_timeout_if_needed(date_str, run_status, "segment", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    cli.console.print("\n[dim]⏭️ 跳过角色识别：功能已冻结[/dim]")
    _mark_step(date_str, run_status, "roles", "skipped", message="角色识别已冻结", artifact=paths["scenes"], skip_reason="role_step_frozen")
    timeout_result = _return_timeout_if_needed(date_str, run_status, "roles", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    llm_available = has_llm_credentials("distill")
    missing_summaries = [scene for scene in scenes_data.get("scenes", []) if not scene.get("summary")]
    if missing_summaries:
        if llm_available:
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
            cli.console.print("\n[yellow]⏸️ 蒸馏需要 LLM，有两种方式完成：[/yellow]")
            _mark_step(
                date_str,
                run_status,
                "distill",
                "skipped",
                message="等待选择蒸馏方式：配置 Gemini API Key（便宜自动）或让 AI 代理用自身模型完成（花 agent token）",
                artifact=paths["scenes"],
                skip_reason="missing_llm_key_agent_handoff",
            )
            _finish_run(date_str, run_status, "partial", "distill")
            cli.console.print(
                cli.Panel(
                    f"[yellow]⏸️ {date_str} 已完成转写和场景切分[/yellow]\n"
                    "方式 A：配置 Gemini API Key → 用 flash-lite 小模型自动蒸馏（极便宜，有免费额度）\n"
                    "方式 B：让 AI 代理用自己的模型完成 → 零配置但消耗 agent token 预算",
                    border_style="yellow",
                )
            )
            return PARTIAL_SUCCESS
    else:
        cli.console.print("\n[dim]⏭️ 跳过蒸馏：场景摘要已齐全[/dim]")
        _mark_step(date_str, run_status, "distill", "skipped", message="场景摘要已齐全", artifact=paths["scenes"], skip_reason="summaries_already_present")
    timeout_result = _return_timeout_if_needed(date_str, run_status, "distill", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    existing_core_payload = _load_existing_core_payload(date_str)
    if not has_llm_credentials("extract") and paths["transcript"].exists() and not existing_core_payload:
        cli.console.print("\n[yellow]⏸️ 核心提取需要 LLM，有两种方式完成：[/yellow]")
        _mark_step(
            date_str,
            run_status,
            "extract_core",
            "skipped",
            message="等待选择提取方式：配置 Gemini API Key（便宜自动）或让 AI 代理用自身模型完成（花 agent token）",
            artifact=paths["transcript"],
            skip_reason="missing_llm_key_agent_handoff",
        )
        _finish_run(date_str, run_status, "partial", "extract_core")
        cli.console.print(
            cli.Panel(
                f"[yellow]⏸️ {date_str} 蒸馏已完成，等待核心提取[/yellow]\n"
                "方式 A：配置 Gemini API Key → 用 flash-lite 小模型自动提取（极便宜，有免费额度）\n"
                "方式 B：让 AI 代理用自己的模型完成 → 零配置但消耗 agent token 预算",
                border_style="yellow",
            )
        )
        return PARTIAL_SUCCESS

    _mark_step(date_str, run_status, "briefing", "running", message="正在生成日报")
    cli.console.print("\n[bold]📋 日报[/bold]")
    result = cli.cmd_briefing(args)
    if result != 0:
        cli.console.print("[red]❌ 日报生成失败，终止[/red]")
        _mark_step(date_str, run_status, "briefing", "failed", message="日报生成失败")
        _finish_run(date_str, run_status, "failed", "briefing")
        return result
    _mark_step(date_str, run_status, "briefing", "completed", message="日报已生成", artifact=paths["briefing"])
    timeout_result = _return_timeout_if_needed(date_str, run_status, "briefing", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    extract_core_failed = False
    extract_core_payload = existing_core_payload
    if extract_core_payload:
        cli.console.print("\n[dim]⏭️ 跳过核心提取：结构化结果已存在[/dim]")
        meta_path = cli.ensure_day_dir(date_str) / f"{date_str}.meta.json"
        _mark_step(
            date_str,
            run_status,
            "extract_core",
            "skipped",
            message="结构化结果已存在",
            artifact=meta_path,
            skip_reason="core_extraction_already_present",
        )
    elif has_llm_credentials("extract") and paths["transcript"].exists():
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
        _mark_step(date_str, run_status, "extract_core", "skipped", message="缺少 LLM provider key 或 transcript.md", skip_reason="missing_llm_key_or_transcript")
        _mark_step(date_str, run_status, "extract_enrich", "skipped", message="核心提取未执行", skip_reason="core_extraction_not_run")
    timeout_result = _return_timeout_if_needed(date_str, run_status, "extract_core", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    if extract_core_failed:
        _mark_step(date_str, run_status, "extract_enrich", "skipped", message="核心提取失败，跳过补全提取", skip_reason="core_extraction_failed")
        _mark_step(date_str, run_status, "consolidate", "skipped", message="提取失败，跳过 active_context 聚合", skip_reason="core_extraction_failed")
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
        consolidated = consolidate(data_root)
        cli.console.print("[green]✅ active_context 已更新[/green]")
        _mark_step(date_str, run_status, "consolidate", "completed", message="active_context 已更新")
    except Exception as exc:
        cli.console.print(f"[yellow]⚠️ 聚合异常: {exc}，继续[/yellow]")
        _mark_step(date_str, run_status, "consolidate", "failed", message=f"聚合异常: {exc}")
        _mark_step(date_str, run_status, "extract_enrich", "skipped", message="聚合失败，跳过补全提取", skip_reason="consolidation_failed")
        _finish_run(date_str, run_status, "partial", "consolidate")
        return PARTIAL_SUCCESS
    timeout_result = _return_timeout_if_needed(date_str, run_status, "consolidate", started_monotonic)
    if timeout_result is not None:
        return timeout_result

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
        if extract_core_payload and not has_llm_credentials("extract"):
            _mark_step(
                date_str,
                run_status,
                "extract_enrich",
                "skipped",
                message="已有核心结果，但没有可用大模型密钥，未执行补全提取",
                skip_reason="missing_llm_key",
            )
        else:
            _mark_step(
                date_str,
                run_status,
                "extract_enrich",
                "skipped",
                message="缺少核心提取结果，未执行补全",
                skip_reason="missing_core_extraction_output",
            )
    timeout_result = _return_timeout_if_needed(date_str, run_status, "extract_enrich", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    _export_outputs(
        date_str,
        briefing_path=paths["briefing"],
        context_snapshot=asdict(consolidated) if is_dataclass(consolidated) else None,
    )

    _run_aggregation(
        date_str,
        run_status,
        skip_aggregate=bool(getattr(args, "skip_aggregate", False)),
    )
    timeout_result = _return_timeout_if_needed(date_str, run_status, "aggregate", started_monotonic)
    if timeout_result is not None:
        return timeout_result

    cli.console.print(
        cli.Panel(
            f"[green]✅ {date_str} 处理完成！[/green]\n运行 [bold]openmy view {date_str}[/bold] 查看结果",
            border_style="green",
        )
    )
    record_processing_success(final_provider_name)
    final_step = "aggregate" if run_status["steps"]["aggregate"]["status"] != "pending" else (
        "extract_enrich" if run_status["steps"]["extract_enrich"]["status"] != "pending" else "consolidate"
    )
    _cleanup_downstream_backups(downstream_backups)
    _finish_run(date_str, run_status, "completed", final_step)
    return 0


def cmd_quick_start(args: argparse.Namespace) -> int:
    """面向第一次使用者的一键入口。"""
    cli = _cli()
    if getattr(args, "demo", False):
        audio_path, transcript_text = _prepare_demo_inputs()
        target_date = cli.infer_date_from_path(audio_path)
        _seed_demo_transcript(target_date, transcript_text)
    elif getattr(args, "audio_path", None):
        audio_path = Path(args.audio_path).expanduser()
        target_date = cli.infer_date_from_path(audio_path)
    else:
        wizard_result = _run_quick_start_wizard(getattr(args, "stt_provider", None))
        if wizard_result is None:
            cli.console.print("[yellow]⚠️ 已取消 quick-start[/yellow]")
            return 1
        args.stt_provider = wizard_result["provider_name"]
        if wizard_result["use_demo"]:
            audio_path, transcript_text = _prepare_demo_inputs()
            target_date = cli.infer_date_from_path(audio_path)
            _seed_demo_transcript(target_date, transcript_text)
            args.demo = True
        else:
            audio_path = wizard_result["audio_path"]
            target_date = cli.infer_date_from_path(audio_path)

    if not audio_path.exists():
        cli.render_friendly_error(
            cli.FriendlyCliError(
                "找不到这段音频文件。",
                code="quick_start_audio_missing",
                fix="先确认音频路径写对了，或者直接改用 `openmy quick-start --demo`。",
                doc_url=cli.doc_url("一分钟跑起来"),
                message_en=f"Audio file not found: {audio_path}",
                fix_en="Check the audio path or use openmy quick-start --demo.",
            )
        )
        return 1

    if not getattr(args, "demo", False):
        effective_provider = str(getattr(args, "stt_provider", None) or get_stt_provider_name() or "").strip()
        if not effective_provider:
            _print_quick_start_onboarding(_collect_quick_start_onboarding())
            return 1
        try:
            cli.ensure_runtime_dependencies(stt_provider=getattr(args, "stt_provider", None))
        except cli.FriendlyCliError as exc:
            cli.render_friendly_error(exc)
            return 1

    cli.console.print(
        cli.Panel(
            f"🚀 OpenMy quick-start\n🎙️ 音频: {audio_path.name}\n📅 自动识别日期: {target_date}",
            border_style="bright_blue",
        )
    )

    run_args = argparse.Namespace(
        date=target_date,
        audio=None if getattr(args, "demo", False) else [str(audio_path)],
        skip_transcribe=bool(getattr(args, "demo", False)),
        skip_aggregate=bool(getattr(args, "skip_aggregate", False)),
        stt_provider=getattr(args, "stt_provider", None),
        stt_model=getattr(args, "stt_model", None),
        stt_vad=bool(getattr(args, "stt_vad", False)),
        stt_word_timestamps=bool(getattr(args, "stt_word_timestamps", False)),
        stt_enrich_mode=getattr(args, "stt_enrich_mode", "recommended"),
        stt_align=bool(getattr(args, "stt_align", False)),
        stt_diarize=bool(getattr(args, "stt_diarize", False)),
    )
    result = cli.cmd_run(run_args, entrypoint="quick-start")
    if result not in (0, PARTIAL_SUCCESS):
        return result

    if getattr(args, "demo", False):
        _print_demo_before_after(target_date)

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

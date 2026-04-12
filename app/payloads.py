from __future__ import annotations

import json
import re
from pathlib import Path

from openmy.config import DEFAULT_STT_MODELS, LOCAL_STT_PROVIDERS, get_stt_api_key, get_stt_provider_name, stt_provider_requires_api_key
from openmy.services.onboarding.state import load_onboarding_state, save_onboarding_state
from openmy.services.screen_recognition.settings import (
    ScreenContextSettings,
    load_screen_context_settings,
    save_screen_context_settings,
)


LABELS = {
    'funasr': '本地中文优先',
    'faster-whisper': '本地通用优先',
    'dashscope': '云端中文优先',
    'gemini': '云端省事优先',
    'groq': '云端速度优先',
    'deepgram': '云端英文优先',
}
DESCRIPTIONS = {
    'funasr': '中文录音优先，而且不用密钥。',
    'faster-whisper': '本地就能跑，先成功最稳。',
    'dashscope': '中文精度更强，但要先填一次密钥。',
    'gemini': '少折腾，适合先跑通云端路线。',
    'groq': '速度快，但也要先填一次密钥。',
    'deepgram': '更偏英文场景，也要先填一次密钥。',
}
CHOICE_GROUPS = {
    'local': ['funasr', 'faster-whisper'],
    'cloud': ['dashscope', 'gemini', 'groq', 'deepgram'],
}


def _server():
    import app.server as server_module

    return server_module


def load_active_context_snapshot() -> dict:
    server = _server()
    return server.load_json(server.DATA_ROOT / "active_context.json") or {}






def _upsert_project_env(key: str, value: str) -> Path:
    server = _server()
    env_path = server.ROOT_DIR / '.env'
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding='utf-8').splitlines()

    replaced = False
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        existing_key = stripped.split('=', 1)[0].strip()
        if existing_key != key:
            continue
        lines[index] = f"{key}={value}"
        replaced = True
        break

    if not replaced:
        if lines and lines[-1].strip():
            lines.append('')
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding='utf-8')
    return env_path


def _provider_view(name: str, stt_providers: list[dict], recommended: str) -> dict:
    match = next((item for item in stt_providers if item.get('name') == name), {})
    return {
        'name': name,
        'label': LABELS.get(name, name),
        'description': DESCRIPTIONS.get(name, ''),
        'type': match.get('type', ''),
        'ready': bool(match.get('ready')),
        'is_active': bool(match.get('is_active')),
        'is_recommended': name == recommended,
        'needs_api_key': bool(match.get('needs_api_key')),
    }


def _build_choice_groups(stt_providers: list[dict], recommended: str) -> dict:
    return {group: [_provider_view(name, stt_providers, recommended) for name in names] for group, names in CHOICE_GROUPS.items()}


def _build_current_onboarding_payload(provider_override: str | None = None) -> dict:
    server = _server()
    current_stt = (provider_override or get_stt_provider_name()).strip().lower()
    stt_providers: list[dict[str, object]] = []
    for name, default_model in DEFAULT_STT_MODELS.items():
        needs_key = stt_provider_requires_api_key(name)
        stt_providers.append({
            'name': name,
            'type': 'local' if name in LOCAL_STT_PROVIDERS else 'api',
            'default_model': default_model,
            'needs_api_key': needs_key,
            'api_key_configured': bool(get_stt_api_key(name)) if needs_key else True,
            'is_active': name == current_stt,
            'ready': bool(get_stt_api_key(name)) if needs_key else True,
        })

    recommended = current_stt or next((name for name in CHOICE_GROUPS['local'] if any(item['name']==name and item['ready'] for item in stt_providers)), 'funasr')
    profile_exists = (server.DATA_ROOT / 'profile.json').exists()
    vocab_exists = (server.ROOT_DIR / 'src' / 'openmy' / 'resources' / 'corrections.json').exists() and (server.ROOT_DIR / 'src' / 'openmy' / 'resources' / 'vocab.txt').exists()

    if not current_stt:
        stage = 'choose_provider'
        headline = f'先别自己挑，先按推荐路线走：{LABELS.get(recommended, recommended)}'
        next_step = '先选转写引擎，再开始第一次转写。'
        primary_action = f'先运行 openmy skill profile.set --stt-provider {recommended} --json，先把推荐路线定下来。'
    elif not profile_exists:
        stage = 'complete_profile'
        headline = f'转写模型已经定了：{LABELS.get(current_stt, current_stt)}'
        next_step = '先补个人资料，再开始第一次转写。'
        primary_action = '先补个人资料，再开始第一次转写。'
    elif not vocab_exists:
        stage = 'init_vocab'
        headline = f'转写模型已经定了：{LABELS.get(current_stt, current_stt)}'
        next_step = '先补词库，再开始第一次转写。'
        primary_action = '先补词库，再开始第一次转写。'
    else:
        stage = 'ready'
        headline = f'现在可以直接开始第一次转写：{LABELS.get(current_stt, current_stt)}'
        next_step = '现在可以直接开始第一次转写。'
        primary_action = f'现在就可以直接试：openmy quick-start --stt-provider {current_stt} <你的音频路径>'

    return {
        'stage': stage,
        'completed': stage == 'ready',
        'recommended_provider': recommended,
        'recommended_label': LABELS.get(recommended, ''),
        'recommended_reason': DESCRIPTIONS.get(recommended, ''),
        'headline': headline,
        'primary_action': primary_action,
        'choices': _build_choice_groups(stt_providers, recommended),
        'current_provider': current_stt,
        'next_step': next_step,
        'state_path': str(server.DATA_ROOT / 'onboarding_state.json'),
    }


def update_onboarding_provider_payload(data: dict) -> dict:
    provider = str((data or {}).get('provider', '')).strip().lower()
    if not provider:
        return {'success': False, 'error': '缺少 provider'}
    if provider not in DEFAULT_STT_MODELS:
        return {'success': False, 'error': '未知 provider'}

    server = _server()
    _upsert_project_env('OPENMY_STT_PROVIDER', provider)
    onboarding = _build_current_onboarding_payload(provider_override=provider)
    save_onboarding_state(server.DATA_ROOT, onboarding)
    return {
        'success': True,
        'provider': provider,
        'onboarding': onboarding,
        'human_summary': f'STT provider set to {provider}.',
    }


def get_onboarding_payload() -> dict:
    server = _server()
    existing = load_onboarding_state(server.DATA_ROOT) or {}
    if existing:
        return existing
    payload = _build_current_onboarding_payload()
    save_onboarding_state(server.DATA_ROOT, payload)
    return payload

def get_context_payload() -> dict:
    snapshot = load_active_context_snapshot()
    rolling_context = snapshot.get("rolling_context", {})
    realtime_context = snapshot.get("realtime_context", {})
    return {
        "generated_at": snapshot.get("generated_at"),
        "status_line": snapshot.get("status_line", ""),
        "today_focus": realtime_context.get("today_focus", []),
        "today_state": realtime_context.get("today_state", {}),
        "latest_scene_refs": realtime_context.get("latest_scene_refs", []),
        "pending_followups_today": realtime_context.get("pending_followups_today", []),
        "screen_completion_candidates": realtime_context.get("screen_completion_candidates", []),
        "ingestion_health": realtime_context.get("ingestion_health", {}),
        "active_projects": rolling_context.get("active_projects", []),
        "open_loops": rolling_context.get("open_loops", []),
        "recent_decisions": rolling_context.get("recent_decisions", []),
        "stable_profile": snapshot.get("stable_profile", {}),
    }


def get_screen_context_settings_payload() -> dict:
    server = _server()
    settings = load_screen_context_settings(data_root=server.DATA_ROOT)
    return settings.to_dict()


def update_screen_context_settings_payload(data: dict) -> dict:
    server = _server()
    current = load_screen_context_settings(data_root=server.DATA_ROOT)
    merged = ScreenContextSettings.from_dict(
        {
            **current.to_dict(),
            **(data if isinstance(data, dict) else {}),
        }
    )
    save_screen_context_settings(merged, data_root=server.DATA_ROOT)
    return merged.to_dict()


def get_context_loops_payload() -> list[dict]:
    return get_context_payload().get("open_loops", [])


def get_context_projects_payload() -> list[dict]:
    return get_context_payload().get("active_projects", [])


def get_context_decisions_payload() -> list[dict]:
    return get_context_payload().get("recent_decisions", [])


def get_context_query_payload(
    kind: str,
    query: str = "",
    limit: int = 5,
    include_evidence: bool = False,
) -> dict:
    server = _server()
    from openmy.services.query.context_query import query_context

    return query_context(
        server.DATA_ROOT,
        kind=kind,
        query=query,
        limit=limit,
        include_evidence=include_evidence,
    )


def parse_segments(content: str) -> list[dict]:
    server = _server()
    if server.TIME_HEADER_RE.search(content):
        segments = server.parse_time_segments(content)
        return [
            {
                "time": seg["time"],
                "text": seg["text"],
                "preview": seg["text"][:80].replace("\n", " "),
            }
            for seg in segments
        ]

    segments = []
    paragraphs = re.split(r"\n{2,}", content.strip())
    for index, para in enumerate(paragraphs):
        text = para.strip()
        if not text or text.startswith("---"):
            continue
        segments.append({
            "time": f"段{index + 1}",
            "text": text,
            "preview": text[:80].replace("\n", " "),
        })
    return segments


def get_all_dates():
    server = _server()
    dates = []
    for date in server.list_dates():
        paths = server.resolve_day_paths(date)
        transcript_path = paths["transcript"]
        if not transcript_path.exists():
            continue

        content = transcript_path.read_text(encoding="utf-8")
        segments = parse_segments(content)
        meta = server.load_json(paths["meta"]) or {}
        scenes_data = server.load_json(paths["scenes"]) or {}

        date_info = {
            "date": date,
            "segments": len(segments),
            "word_count": len(re.sub(r"\s+", "", content)),
            "summary": meta.get("daily_summary", ""),
            "events": meta.get("events", []),
            "decisions": meta.get("decisions", []),
            "todos": meta.get("todos", []),
            "insights": meta.get("insights", []),
            "timeline": [{"time": seg["time"], "preview": seg["preview"]} for seg in segments],
            "has_scenes": bool(scenes_data),
        }
        if scenes_data:
            date_info["role_distribution"] = scenes_data.get("stats", {}).get("role_distribution", {})
        dates.append(date_info)
    return dates


def search_content(query: str, max_results: int = 20):
    server = _server()
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    for date in server.list_dates():
        transcript_path = server.resolve_day_paths(date)["transcript"]
        if not transcript_path.exists():
            continue
        content = transcript_path.read_text(encoding="utf-8")
        segments = parse_segments(content)
        for seg in segments:
            if not pattern.search(seg["text"]):
                continue
            lines = seg["text"].split("\n")
            for index, line in enumerate(lines):
                if not pattern.search(line):
                    continue
                start = max(0, index - 1)
                end = min(len(lines), index + 2)
                context = "\n".join(lines[start:end])
                highlighted = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", context)
                results.append({
                    "date": date,
                    "time": seg["time"],
                    "context": highlighted,
                    "raw_context": context,
                })
                if len(results) >= max_results:
                    return results
    return results


def get_stats():
    server = _server()
    total_dates = 0
    total_words = 0
    total_segments = 0
    role_totals: dict[str, int] = {}

    for date in server.list_dates():
        paths = server.resolve_day_paths(date)
        transcript_path = paths["transcript"]
        if not transcript_path.exists():
            continue
        total_dates += 1
        content = transcript_path.read_text(encoding="utf-8")
        total_words += len(re.sub(r"\s+", "", content))
        total_segments += len(parse_segments(content))

        scenes_data = server.load_json(paths["scenes"]) or {}
        for role, count in scenes_data.get("stats", {}).get("role_distribution", {}).items():
            role_totals[role] = role_totals.get(role, 0) + count

    return {
        "total_dates": total_dates,
        "total_words": total_words,
        "total_segments": total_segments,
        "role_distribution": role_totals,
    }


def get_date_detail(date: str):
    server = _server()
    paths = server.resolve_day_paths(date)
    transcript_path = paths["transcript"]
    if not transcript_path.exists():
        return None

    content = transcript_path.read_text(encoding="utf-8")
    segments = parse_segments(content)
    meta = server.load_json(paths["meta"])
    scenes = server.load_json(paths["scenes"])

    if scenes:
        scenes_by_time = {
            scene["time_start"]: {
                "role": scene.get("role", {}),
                "summary": scene.get("summary", ""),
            }
            for scene in scenes.get("scenes", [])
        }
        for seg in segments:
            scene_info = scenes_by_time.get(seg["time"])
            if scene_info:
                seg["role"] = scene_info["role"]
                seg["summary"] = scene_info["summary"]
            else:
                seg["role"] = None
                seg["summary"] = ""
    else:
        for seg in segments:
            seg["role"] = None
            seg["summary"] = ""

    return {
        "date": date,
        "segments": segments,
        "meta": meta,
        "scenes": scenes,
        "word_count": len(re.sub(r"\s+", "", content)),
    }


def get_date_meta_payload(date: str):
    server = _server()
    return server.load_json(server.resolve_day_paths(date)["meta"])


def get_briefing(date: str):
    server = _server()
    briefing_path = server.DATA_ROOT / date / "daily_briefing.json"
    if not briefing_path.exists():
        return None
    return server.load_json(briefing_path)


def get_date_briefing_payload(date: str):
    return get_briefing(date)


def get_corrections():
    server = _server()
    if not server.CORRECTIONS_FILE.exists():
        return {"corrections": []}
    try:
        return json.loads(server.CORRECTIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"corrections": []}


def handle_correction(data: dict) -> dict:
    server = _server()
    wrong = data.get("wrong", "").strip()
    right = data.get("right", "").strip()
    date = data.get("date", "").strip()
    context = data.get("context", "")
    sync_vocab = data.get("sync_vocab", True)

    if not wrong or not right:
        return {"success": False, "error": "wrong 和 right 不能为空"}
    if wrong == right:
        return {"success": False, "error": "纠正前后相同"}

    corrections_data = get_corrections()
    corrections = corrections_data.get("corrections", [])
    existing = next((item for item in corrections if item["wrong"] == wrong), None)
    if existing:
        existing["right"] = right
        existing["count"] = existing.get("count", 0) + 1
        existing["last_updated"] = server.datetime.now().isoformat()
    else:
        corrections.append({
            "wrong": wrong,
            "right": right,
            "context": context,
            "count": 1,
            "first_seen": server.datetime.now().strftime("%Y-%m-%d"),
            "last_updated": server.datetime.now().isoformat(),
        })

    corrections_data["corrections"] = corrections
    server.CORRECTIONS_FILE.write_text(json.dumps(corrections_data, ensure_ascii=False, indent=2), encoding="utf-8")

    replaced_in_file = 0
    if date:
        transcript_path = server.resolve_day_paths(date)["transcript"]
        if transcript_path.exists():
            content = transcript_path.read_text(encoding="utf-8")
            if wrong in content:
                transcript_path.write_text(content.replace(wrong, right), encoding="utf-8")
                replaced_in_file = content.count(wrong)

        for extra_path in (
            server.DATA_ROOT / date / "scenes.json",
            server.DATA_ROOT / date / "daily_briefing.json",
        ):
            if not extra_path.exists():
                continue
            try:
                raw = extra_path.read_text(encoding="utf-8")
            except Exception:
                continue
            if wrong not in raw:
                continue
            extra_path.write_text(raw.replace(wrong, right), encoding="utf-8")

    if sync_vocab:
        try:
            server.sync_correction_to_vocab(wrong, right, context)
        except Exception:
            pass

    return {
        "success": True,
        "correction": {"wrong": wrong, "right": right},
        "replaced_in_file": replaced_in_file,
        "total_corrections": len(corrections),
    }

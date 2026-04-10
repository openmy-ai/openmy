from __future__ import annotations

import json
import re


def _server():
    import app.server as server_module

    return server_module


def load_active_context_snapshot() -> dict:
    server = _server()
    return server.load_json(server.DATA_ROOT / "active_context.json") or {}


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
        "ingestion_health": realtime_context.get("ingestion_health", {}),
        "active_projects": rolling_context.get("active_projects", []),
        "open_loops": rolling_context.get("open_loops", []),
        "recent_decisions": rolling_context.get("recent_decisions", []),
        "stable_profile": snapshot.get("stable_profile", {}),
    }


def get_context_loops_payload() -> list[dict]:
    return get_context_payload().get("open_loops", [])


def get_context_projects_payload() -> list[dict]:
    return get_context_payload().get("active_projects", [])


def get_context_decisions_payload() -> list[dict]:
    return get_context_payload().get("recent_decisions", [])


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

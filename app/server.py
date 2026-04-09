#!/usr/bin/env python3
"""
OpenMy — 本地 Web 服务（OpenMy package 版）

提供：
  - 时间线浏览（按日期和时间段）
  - 场景角色标注显示 + 筛选
  - 全文关键词搜索
  - 结构化摘要展示
  - 角色分布统计

启动：python3 server.py
访问：http://localhost:8420
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.job_runner import JobRunner
from openmy.services.cleaning.cleaner import sync_correction_to_vocab
from openmy.services.segmentation.segmenter import parse_time_segments

try:
    from openmy.adapters.screenpipe.client import ScreenpipeClient

    _screenpipe = ScreenpipeClient()
    _screenpipe_available = _screenpipe.is_available()
except Exception:
    _screenpipe = None
    _screenpipe_available = False

DATA_ROOT = ROOT_DIR / 'data'
LEGACY_ROOT = ROOT_DIR
CORRECTIONS_FILE = ROOT_DIR / 'src' / 'openmy' / 'resources' / 'corrections.json'
PORT = 8420
TIME_HEADER_RE = re.compile(r'^##\s+(\d{1,2}:\d{2})', re.MULTILINE)
DATE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})$')
DATE_MD_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})\.md$')
JOB_RUNNER = JobRunner()


def list_dates() -> list[str]:
    dates: set[str] = set()
    if DATA_ROOT.exists():
        for child in DATA_ROOT.iterdir():
            if child.is_dir() and DATE_RE.match(child.name):
                dates.add(child.name)
    for path in LEGACY_ROOT.glob('*.md'):
        if path.name.endswith('.raw.md'):
            continue
        match = DATE_MD_RE.match(path.name)
        if match:
            dates.add(match.group(1))
    return sort_dates_for_display(list(dates))


def parse_date_value(value: str):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def sort_dates_for_display(dates: list[str], today: str | None = None) -> list[str]:
    ordered_dates = sorted(set(dates), reverse=True)
    if not ordered_dates:
        return []

    today_value = parse_date_value(today) if today else datetime.now().date()
    if today and today_value is None:
        return ordered_dates

    non_future_dates = []
    future_dates = []
    for value in ordered_dates:
        parsed = parse_date_value(value)
        if parsed and parsed <= today_value:
            non_future_dates.append(value)
        else:
            future_dates.append(value)
    return non_future_dates + future_dates


def choose_default_date(dates: list[str], today: str | None = None) -> str | None:
    ordered_dates = sort_dates_for_display(dates, today=today)
    return ordered_dates[0] if ordered_dates else None


def resolve_day_paths(date: str) -> dict[str, Path]:
    day_dir = DATA_ROOT / date
    dated_meta_path = day_dir / f'{date}.meta.json'
    legacy_meta_path = day_dir / 'meta.json'
    paths = {
        'transcript': day_dir / 'transcript.md',
        'raw': day_dir / 'transcript.raw.md',
        'meta': dated_meta_path if dated_meta_path.exists() or not legacy_meta_path.exists() else legacy_meta_path,
        'scenes': day_dir / 'scenes.json',
    }
    if paths['transcript'].exists():
        return paths

    return {
        'transcript': LEGACY_ROOT / f'{date}.md',
        'raw': LEGACY_ROOT / f'{date}.raw.md',
        'meta': LEGACY_ROOT / f'{date}.meta.json',
        'scenes': LEGACY_ROOT / f'{date}.scenes.json',
    }


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def load_active_context_snapshot() -> dict:
    return load_json(DATA_ROOT / 'active_context.json') or {}


def load_active_context_model():
    from openmy.services.context.active_context import ActiveContext

    ctx_path = DATA_ROOT / 'active_context.json'
    if not ctx_path.exists():
        return None
    return ActiveContext.load(ctx_path)


def get_context_payload() -> dict:
    snapshot = load_active_context_snapshot()
    rolling_context = snapshot.get('rolling_context', {})
    realtime_context = snapshot.get('realtime_context', {})
    return {
        'generated_at': snapshot.get('generated_at'),
        'status_line': snapshot.get('status_line', ''),
        'today_focus': realtime_context.get('today_focus', []),
        'today_state': realtime_context.get('today_state', {}),
        'latest_scene_refs': realtime_context.get('latest_scene_refs', []),
        'pending_followups_today': realtime_context.get('pending_followups_today', []),
        'ingestion_health': realtime_context.get('ingestion_health', {}),
        'active_projects': rolling_context.get('active_projects', []),
        'open_loops': rolling_context.get('open_loops', []),
        'recent_decisions': rolling_context.get('recent_decisions', []),
        'stable_profile': snapshot.get('stable_profile', {}),
    }


def get_context_loops_payload() -> list[dict]:
    return get_context_payload().get('open_loops', [])


def get_context_projects_payload() -> list[dict]:
    return get_context_payload().get('active_projects', [])


def get_context_decisions_payload() -> list[dict]:
    return get_context_payload().get('recent_decisions', [])


def _normalize_match_text(text: str) -> str:
    return re.sub(r'\s+', '', str(text or '')).strip().lower()


def _score_match(query: str, *candidates: str) -> int:
    normalized_query = _normalize_match_text(query)
    if not normalized_query:
        return -1

    best = -1
    for candidate in candidates:
        normalized_candidate = _normalize_match_text(candidate)
        if not normalized_candidate:
            continue
        if normalized_query == normalized_candidate:
            return 1000 + len(normalized_candidate)
        if normalized_query in normalized_candidate:
            best = max(best, 500 - max(0, len(normalized_candidate) - len(normalized_query)))
        elif normalized_candidate in normalized_query:
            best = max(best, 100 - max(0, len(normalized_query) - len(normalized_candidate)))
    return best


def _resolve_item(items: list, query: str, candidate_getter):
    best_item = None
    best_score = -1
    for item in items:
        score = _score_match(query, *candidate_getter(item))
        if score > best_score:
            best_score = score
            best_item = item
    if best_score < 0:
        return None
    return best_item


def refresh_active_context_snapshot() -> dict:
    from openmy.services.context.consolidation import consolidate
    from openmy.services.context.corrections import apply_corrections, load_corrections

    ctx_path = DATA_ROOT / 'active_context.json'
    corrections = load_corrections(DATA_ROOT)
    existing = load_active_context_model()

    if existing is not None:
        ctx = apply_corrections(existing, corrections) if corrections else existing
    else:
        ctx = consolidate(DATA_ROOT)

    ctx.save(ctx_path)
    return ctx.to_dict()


def _append_context_correction(op: str, target_type: str, target_id: str, payload: dict | None = None, reason: str = '') -> None:
    from openmy.services.context.corrections import append_correction, create_correction_event

    event = create_correction_event(
        actor='user',
        op=op,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        reason=reason,
    )
    append_correction(DATA_ROOT, event)


def handle_close_loop(data: dict) -> dict:
    query = str(data.get('query', '')).strip()
    status = str(data.get('status', 'done')).strip() or 'done'
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}

    loop = _resolve_item(ctx.rolling_context.open_loops, query, lambda item: [item.loop_id, item.id, item.title])
    if loop is None:
        return {'success': False, 'error': f'没找到待办：{query}'}

    target_id = loop.loop_id or loop.id or loop.title
    _append_context_correction(
        op='close_loop',
        target_type='loop',
        target_id=target_id,
        payload={'status': status, 'target_title': loop.title},
        reason=str(data.get('reason', '')).strip(),
    )
    refreshed = refresh_active_context_snapshot()
    return {'success': True, 'target_id': target_id, 'context': refreshed}


def handle_reject_loop(data: dict) -> dict:
    query = str(data.get('query', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}

    loop = _resolve_item(ctx.rolling_context.open_loops, query, lambda item: [item.loop_id, item.id, item.title])
    if loop is None:
        return {'success': False, 'error': f'没找到待办：{query}'}

    target_id = loop.loop_id or loop.id or loop.title
    _append_context_correction(
        op='reject_loop',
        target_type='loop',
        target_id=target_id,
        payload={'target_title': loop.title},
        reason=str(data.get('reason', '')).strip(),
    )
    refreshed = refresh_active_context_snapshot()
    return {'success': True, 'target_id': target_id, 'context': refreshed}


def handle_merge_project(data: dict) -> dict:
    source_query = str(data.get('source', '')).strip()
    target_query = str(data.get('target', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}

    source_project = _resolve_item(ctx.rolling_context.active_projects, source_query, lambda item: [item.project_id, item.id, item.title])
    target_project = _resolve_item(ctx.rolling_context.active_projects, target_query, lambda item: [item.project_id, item.id, item.title])
    if source_project is None or target_project is None:
        return {'success': False, 'error': '找不到要合并的项目。'}

    source_id = source_project.project_id or source_project.id or source_project.title
    target_id = target_project.project_id or target_project.id or target_project.title
    _append_context_correction(
        op='merge_project',
        target_type='project',
        target_id=source_id,
        payload={
            'target_title': source_project.title,
            'merge_into': target_id,
            'merge_into_title': target_project.title,
        },
        reason=str(data.get('reason', '')).strip(),
    )
    refreshed = refresh_active_context_snapshot()
    return {'success': True, 'target_id': source_id, 'context': refreshed}


def handle_reject_project(data: dict) -> dict:
    query = str(data.get('query', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}

    project = _resolve_item(ctx.rolling_context.active_projects, query, lambda item: [item.project_id, item.id, item.title])
    if project is None:
        return {'success': False, 'error': f'没找到项目：{query}'}

    target_id = project.project_id or project.id or project.title
    _append_context_correction(
        op='reject_project',
        target_type='project',
        target_id=target_id,
        payload={'target_title': project.title},
        reason=str(data.get('reason', '')).strip(),
    )
    refreshed = refresh_active_context_snapshot()
    return {'success': True, 'target_id': target_id, 'context': refreshed}


def handle_reject_decision(data: dict) -> dict:
    query = str(data.get('query', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}

    decision = _resolve_item(
        ctx.rolling_context.recent_decisions,
        query,
        lambda item: [item.decision_id, item.id, item.decision, item.topic],
    )
    if decision is None:
        return {'success': False, 'error': f'没找到决策：{query}'}

    target_id = decision.decision_id or decision.id or decision.decision
    _append_context_correction(
        op='reject_decision',
        target_type='decision',
        target_id=target_id,
        payload={'target_title': decision.decision},
        reason=str(data.get('reason', '')).strip(),
    )
    refreshed = refresh_active_context_snapshot()
    return {'success': True, 'target_id': target_id, 'context': refreshed}


def build_pipeline_command(kind: str, target_date: str | None) -> list[str]:
    commands = {
        'context': [sys.executable, '-m', 'openmy', 'context'],
        'run': [sys.executable, '-m', 'openmy', 'run', target_date or ''],
        'clean': [sys.executable, '-m', 'openmy', 'clean', target_date or ''],
        'roles': [sys.executable, '-m', 'openmy', 'roles', target_date or ''],
        'distill': [sys.executable, '-m', 'openmy', 'distill', target_date or ''],
        'briefing': [sys.executable, '-m', 'openmy', 'briefing', target_date or ''],
    }
    return commands[kind]


def run_pipeline_job_command(kind: str, target_date: str | None, handle) -> None:
    command = build_pipeline_command(kind, target_date)
    handle.step(f'{kind} running')
    handle.log(' '.join(command))
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=ROOT_DIR,
    )
    for line in result.stdout.splitlines():
        if line.strip():
            handle.log(line)
    for line in result.stderr.splitlines():
        if line.strip():
            handle.log(line)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f'{kind} failed')

    artifact_map = {
        'context': [str(DATA_ROOT / 'active_context.json')],
        'run': [
            str(DATA_ROOT / (target_date or '') / 'scenes.json'),
            str(DATA_ROOT / (target_date or '') / 'daily_briefing.json'),
        ],
        'clean': [str(DATA_ROOT / (target_date or '') / 'transcript.md')],
        'roles': [str(DATA_ROOT / (target_date or '') / 'scenes.json')],
        'distill': [str(DATA_ROOT / (target_date or '') / 'scenes.json')],
        'briefing': [str(DATA_ROOT / (target_date or '') / 'daily_briefing.json')],
    }
    for artifact in artifact_map.get(kind, []):
        handle.add_artifact(artifact)


def handle_create_pipeline_job(data: dict) -> dict:
    kind = str(data.get('kind', '')).strip()
    target_date = str(data.get('target_date', '')).strip() or None
    valid_kinds = {'context', 'run', 'clean', 'roles', 'distill', 'briefing'}
    if kind not in valid_kinds:
        return {'success': False, 'error': f'不支持的 pipeline kind: {kind}'}
    if kind != 'context' and not target_date:
        return {'success': False, 'error': 'target_date 不能为空'}

    return JOB_RUNNER.create_job(
        kind=kind,
        target_date=target_date,
        run_fn=lambda handle: run_pipeline_job_command(kind, target_date, handle),
    )


def get_pipeline_jobs_payload(limit: int = 20) -> list[dict]:
    return JOB_RUNNER.list_jobs(limit=limit)


def get_pipeline_job_payload(job_id: str):
    return JOB_RUNNER.get_job(job_id)


def parse_segments(content: str) -> list[dict]:
    if TIME_HEADER_RE.search(content):
        segments = parse_time_segments(content)
        return [
            {
                'time': seg['time'],
                'text': seg['text'],
                'preview': seg['text'][:80].replace('\n', ' '),
            }
            for seg in segments
        ]

    segments = []
    paragraphs = re.split(r'\n{2,}', content.strip())
    for index, para in enumerate(paragraphs):
        text = para.strip()
        if not text or text.startswith('---'):
            continue
        segments.append({
            'time': f'段{index + 1}',
            'text': text,
            'preview': text[:80].replace('\n', ' '),
        })
    return segments


def get_all_dates():
    dates = []
    for date in list_dates():
        paths = resolve_day_paths(date)
        transcript_path = paths['transcript']
        if not transcript_path.exists():
            continue

        content = transcript_path.read_text(encoding='utf-8')
        segments = parse_segments(content)
        meta = load_json(paths['meta']) or {}
        scenes_data = load_json(paths['scenes']) or {}

        date_info = {
            'date': date,
            'segments': len(segments),
            'word_count': len(re.sub(r'\s+', '', content)),
            'summary': meta.get('daily_summary', ''),
            'events': meta.get('events', []),
            'decisions': meta.get('decisions', []),
            'todos': meta.get('todos', []),
            'insights': meta.get('insights', []),
            'timeline': [{'time': seg['time'], 'preview': seg['preview']} for seg in segments],
            'has_scenes': bool(scenes_data),
        }
        if scenes_data:
            date_info['role_distribution'] = scenes_data.get('stats', {}).get('role_distribution', {})
        dates.append(date_info)
    return dates


def search_content(query: str, max_results: int = 20):
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    for date in list_dates():
        transcript_path = resolve_day_paths(date)['transcript']
        if not transcript_path.exists():
            continue
        content = transcript_path.read_text(encoding='utf-8')
        segments = parse_segments(content)
        for seg in segments:
            if not pattern.search(seg['text']):
                continue
            lines = seg['text'].split('\n')
            for index, line in enumerate(lines):
                if not pattern.search(line):
                    continue
                start = max(0, index - 1)
                end = min(len(lines), index + 2)
                context = '\n'.join(lines[start:end])
                highlighted = pattern.sub(lambda m: f'<mark>{m.group()}</mark>', context)
                results.append({
                    'date': date,
                    'time': seg['time'],
                    'context': highlighted,
                    'raw_context': context,
                })
                if len(results) >= max_results:
                    return results
    return results


def get_stats():
    total_dates = 0
    total_words = 0
    total_segments = 0
    role_totals: dict[str, int] = {}

    for date in list_dates():
        paths = resolve_day_paths(date)
        transcript_path = paths['transcript']
        if not transcript_path.exists():
            continue
        total_dates += 1
        content = transcript_path.read_text(encoding='utf-8')
        total_words += len(re.sub(r'\s+', '', content))
        total_segments += len(parse_segments(content))

        scenes_data = load_json(paths['scenes']) or {}
        for role, count in scenes_data.get('stats', {}).get('role_distribution', {}).items():
            role_totals[role] = role_totals.get(role, 0) + count

    return {
        'total_dates': total_dates,
        'total_words': total_words,
        'total_segments': total_segments,
        'role_distribution': role_totals,
    }


def get_date_detail(date: str):
    paths = resolve_day_paths(date)
    transcript_path = paths['transcript']
    if not transcript_path.exists():
        return None

    content = transcript_path.read_text(encoding='utf-8')
    segments = parse_segments(content)
    meta = load_json(paths['meta'])
    scenes = load_json(paths['scenes'])

    if scenes:
        scenes_by_time = {
            scene['time_start']: {
                'role': scene.get('role', {}),
                'summary': scene.get('summary', ''),
            }
            for scene in scenes.get('scenes', [])
        }
        for seg in segments:
            scene_info = scenes_by_time.get(seg['time'])
            if scene_info:
                seg['role'] = scene_info['role']
                seg['summary'] = scene_info['summary']
            else:
                seg['role'] = None
                seg['summary'] = ''
    else:
        for seg in segments:
            seg['role'] = None
            seg['summary'] = ''

    return {
        'date': date,
        'segments': segments,
        'meta': meta,
        'scenes': scenes,
        'word_count': len(re.sub(r'\s+', '', content)),
    }


def get_date_meta_payload(date: str):
    return load_json(resolve_day_paths(date)['meta'])


def get_briefing(date: str):
    briefing_path = DATA_ROOT / date / 'daily_briefing.json'
    if not briefing_path.exists():
        return None
    return load_json(briefing_path)


def get_date_briefing_payload(date: str):
    return get_briefing(date)


def get_corrections():
    if not CORRECTIONS_FILE.exists():
        return {'corrections': []}
    try:
        return json.loads(CORRECTIONS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {'corrections': []}


def handle_correction(data: dict) -> dict:
    wrong = data.get('wrong', '').strip()
    right = data.get('right', '').strip()
    date = data.get('date', '').strip()
    context = data.get('context', '')
    sync_vocab = data.get('sync_vocab', True)

    if not wrong or not right:
        return {'success': False, 'error': 'wrong 和 right 不能为空'}
    if wrong == right:
        return {'success': False, 'error': '纠正前后相同'}

    corrections_data = get_corrections()
    corrections = corrections_data.get('corrections', [])
    existing = next((item for item in corrections if item['wrong'] == wrong), None)
    if existing:
        existing['right'] = right
        existing['count'] = existing.get('count', 0) + 1
        existing['last_updated'] = datetime.now().isoformat()
    else:
        corrections.append({
            'wrong': wrong,
            'right': right,
            'context': context,
            'count': 1,
            'first_seen': datetime.now().strftime('%Y-%m-%d'),
            'last_updated': datetime.now().isoformat(),
        })

    corrections_data['corrections'] = corrections
    CORRECTIONS_FILE.write_text(json.dumps(corrections_data, ensure_ascii=False, indent=2), encoding='utf-8')

    replaced_in_file = 0
    if date:
        transcript_path = resolve_day_paths(date)['transcript']
        if transcript_path.exists():
            content = transcript_path.read_text(encoding='utf-8')
            if wrong in content:
                transcript_path.write_text(content.replace(wrong, right), encoding='utf-8')
                replaced_in_file = content.count(wrong)

    if sync_vocab:
        try:
            sync_correction_to_vocab(wrong, right, context)
        except Exception:
            pass

    return {
        'success': True,
        'correction': {'wrong': wrong, 'right': right},
        'replaced_in_file': replaced_in_file,
        'total_corrections': len(corrections),
    }


class BrainHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/api/context':
            self.json_response(get_context_payload())
        elif path == '/api/context/loops':
            self.json_response(get_context_loops_payload())
        elif path == '/api/context/projects':
            self.json_response(get_context_projects_payload())
        elif path == '/api/context/decisions':
            self.json_response(get_context_decisions_payload())
        elif path == '/api/dates':
            self.json_response(get_all_dates())
        elif path == '/api/search':
            query = params.get('q', [''])[0]
            self.json_response([] if not query else search_content(query))
        elif path == '/api/stats':
            self.json_response(get_stats())
        elif path.startswith('/api/briefing/'):
            date = path.split('/api/briefing/')[-1]
            briefing = get_briefing(date)
            if briefing:
                self.json_response(briefing)
            else:
                self.json_response({'error': 'no briefing', 'date': date}, status=404)
        elif path.startswith('/api/date/') and path.endswith('/meta'):
            date = path.removeprefix('/api/date/').removesuffix('/meta')
            payload = get_date_meta_payload(date)
            if payload:
                self.json_response(payload)
            else:
                self.json_response({'error': 'no meta', 'date': date}, status=404)
        elif path.startswith('/api/date/') and path.endswith('/briefing'):
            date = path.removeprefix('/api/date/').removesuffix('/briefing')
            payload = get_date_briefing_payload(date)
            if payload:
                self.json_response(payload)
            else:
                self.json_response({'error': 'no briefing', 'date': date}, status=404)
        elif path == '/api/pipeline/jobs':
            self.json_response(get_pipeline_jobs_payload())
        elif path.startswith('/api/pipeline/jobs/'):
            job_id = path.removeprefix('/api/pipeline/jobs/')
            payload = get_pipeline_job_payload(job_id)
            if payload:
                self.json_response(payload)
            else:
                self.json_response({'error': 'job not found', 'job_id': job_id}, status=404)
        elif path.startswith('/api/date/'):
            date = path.split('/api/date/')[-1]
            detail = get_date_detail(date)
            if detail:
                self.json_response(detail)
            else:
                self.send_error(404, '日期不存在')
        elif path == '/api/corrections':
            self.json_response(get_corrections())
        elif path in {'/', '/index.html'}:
            self.serve_index()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, '无效的 JSON')
            return

        if path == '/api/correct':
            self.json_response(handle_correction(data))
        elif path == '/api/correct/typo':
            self.json_response(handle_correction(data))
        elif path == '/api/context/loops/close':
            payload = handle_close_loop(data)
            self.json_response(payload, status=200 if payload.get('success') else 400)
        elif path == '/api/context/loops/reject':
            payload = handle_reject_loop(data)
            self.json_response(payload, status=200 if payload.get('success') else 400)
        elif path == '/api/context/projects/merge':
            payload = handle_merge_project(data)
            self.json_response(payload, status=200 if payload.get('success') else 400)
        elif path == '/api/context/projects/reject':
            payload = handle_reject_project(data)
            self.json_response(payload, status=200 if payload.get('success') else 400)
        elif path == '/api/context/decisions/reject':
            payload = handle_reject_decision(data)
            self.json_response(payload, status=200 if payload.get('success') else 400)
        elif path == '/api/pipeline/jobs':
            payload = handle_create_pipeline_job(data)
            self.json_response(payload, status=200 if payload.get('job_id') else 400)
        else:
            self.send_error(404, '未知接口')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def json_response(self, data, status=200):
        response = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def serve_index(self):
        index_path = Path(__file__).parent / 'index.html'
        if not index_path.exists():
            self.send_error(404, 'index.html 不存在')
            return
        content = index_path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        pass


def main():
    print('🧠 OpenMy v3（OpenMy package 版）')
    print(f'📂 数据目录: {DATA_ROOT}')
    stats = get_stats()
    print(f"📊 {stats['total_dates']} 天 | {stats['total_segments']} 段 | {stats['total_words']} 字")
    if stats['role_distribution']:
        print(f"🏷️ 角色分布: {json.dumps(stats['role_distribution'], ensure_ascii=False)}")
    if _screenpipe_available:
        print("🖥️ Screenpipe 已连接（hints 模式）")
    else:
        print("🖥️ Screenpipe 未检测到（角色归因仍正常工作）")
    print(f'🌐 http://localhost:{PORT}')
    print('按 Ctrl+C 停止\n')

    server = ThreadingHTTPServer(('', PORT), BrainHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n👋 OpenMy 已关闭')
        server.server_close()


if __name__ == '__main__':
    main()

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
import sys
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
    return sorted(dates, reverse=True)


def resolve_day_paths(date: str) -> dict[str, Path]:
    day_dir = DATA_ROOT / date
    paths = {
        'transcript': day_dir / 'transcript.md',
        'raw': day_dir / 'transcript.raw.md',
        'meta': day_dir / 'meta.json',
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


def get_briefing(date: str):
    briefing_path = DATA_ROOT / date / 'daily_briefing.json'
    if not briefing_path.exists():
        return None
    return load_json(briefing_path)


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

        if path == '/api/dates':
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

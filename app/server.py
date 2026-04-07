#!/usr/bin/env python3
"""
周瑟夫的外脑 — 本地 Web 服务（v2 角色归因版）

提供：
  - 时间线浏览（按日期和时间段）
  - 场景角色标注显示 + 筛选
  - 全文关键词搜索
  - 结构化摘要展示
  - 角色分布统计

启动：python3 server.py
访问：http://localhost:8420
"""

import json
import os
import re
import sys
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# 导入 clean.py 的词库同步函数
SCRIPTS_DIR = Path(os.path.expanduser('~/.gemini/skills/daily-context/scripts'))
sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from clean import sync_correction_to_vocab
except ImportError:
    def sync_correction_to_vocab(wrong, right, context=''):
        pass  # fallback: 无法导入时静默跳过

# 数据目录
DATA_DIR = Path(__file__).resolve().parent.parent  # ~/Desktop/周瑟夫的上下文/
CORRECTIONS_FILE = SCRIPTS_DIR / 'corrections.json'
PORT = 8420
TIME_HEADER_RE = re.compile(r'^##\s+(\d{1,2}:\d{2})')


def get_all_dates():
    """获取所有有转写文件的日期"""
    dates = []
    for f in sorted(DATA_DIR.glob("*.md"), reverse=True):
        if f.name.endswith('.raw.md'):
            continue
        match = re.match(r'(\d{4}-\d{2}-\d{2})\.md$', f.name)
        if match:
            date = match.group(1)
            meta_file = DATA_DIR / f"{date}.meta.json"
            scenes_file = DATA_DIR / f"{date}.scenes.json"
            meta = None
            scenes_data = None

            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding='utf-8'))
                except Exception:
                    pass

            if scenes_file.exists():
                try:
                    scenes_data = json.loads(scenes_file.read_text(encoding='utf-8'))
                except Exception:
                    pass

            content = f.read_text(encoding='utf-8')
            segments = parse_segments(content)
            word_count = len(re.sub(r'\s+', '', content))

            date_info = {
                "date": date,
                "segments": len(segments),
                "word_count": word_count,
                "summary": meta.get("daily_summary", "") if meta else "",
                "events": meta.get("events", []) if meta else [],
                "decisions": meta.get("decisions", []) if meta else [],
                "todos": meta.get("todos", []) if meta else [],
                "insights": meta.get("insights", []) if meta else [],
                "timeline": [{"time": s["time"], "preview": s["preview"]} for s in segments],
                "has_scenes": scenes_data is not None,
            }

            # 角色分布统计
            if scenes_data:
                date_info["role_distribution"] = scenes_data.get("stats", {}).get("role_distribution", {})

            dates.append(date_info)
    return dates


def parse_segments(content: str):
    """解析带时间头的内容为段落列表。"""
    segments = []
    current_time = None
    current_lines = []

    for line in content.split('\n'):
        m = TIME_HEADER_RE.match(line.strip())
        if m:
            if current_time and current_lines:
                text = '\n'.join(current_lines).strip()
                preview = text[:80].replace('\n', ' ') if text else ""
                segments.append({"time": current_time, "text": text, "preview": preview})
            current_time = m.group(1)
            current_lines = []
        elif current_time is not None:
            current_lines.append(line)

    if current_time and current_lines:
        text = '\n'.join(current_lines).strip()
        preview = text[:80].replace('\n', ' ') if text else ""
        segments.append({"time": current_time, "text": text, "preview": preview})

    if not segments:
        paragraphs = re.split(r'\n{2,}', content.strip())
        for i, para in enumerate(paragraphs):
            text = para.strip()
            if not text or text.startswith('---'):
                continue
            preview = text[:80].replace('\n', ' ')
            segments.append({"time": f"段{i+1}", "text": text, "preview": preview})

    return segments


def search_content(query: str, max_results: int = 20):
    """全文搜索所有转写文件"""
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    for f in sorted(DATA_DIR.glob("*.md"), reverse=True):
        if f.name.endswith('.raw.md'):
            continue
        match = re.match(r'(\d{4}-\d{2}-\d{2})\.md$', f.name)
        if not match:
            continue

        date = match.group(1)
        content = f.read_text(encoding='utf-8')
        segments = parse_segments(content)

        for seg in segments:
            if pattern.search(seg["text"]):
                lines = seg["text"].split('\n')
                for i, line in enumerate(lines):
                    if pattern.search(line):
                        start = max(0, i - 1)
                        end = min(len(lines), i + 2)
                        context = '\n'.join(lines[start:end])
                        highlighted = pattern.sub(
                            lambda m: f'<mark>{m.group()}</mark>',
                            context
                        )
                        results.append({
                            "date": date,
                            "time": seg["time"],
                            "context": highlighted,
                            "raw_context": context
                        })
                        if len(results) >= max_results:
                            return results
    return results


def get_stats():
    """获取全局统计"""
    total_dates = 0
    total_words = 0
    total_segments = 0
    role_totals = {}

    for f in DATA_DIR.glob("*.md"):
        if f.name.endswith('.raw.md'):
            continue
        match = re.match(r'(\d{4}-\d{2}-\d{2})\.md$', f.name)
        if not match:
            continue
        date = match.group(1)
        total_dates += 1
        content = f.read_text(encoding='utf-8')
        total_words += len(re.sub(r'\s+', '', content))
        total_segments += len(parse_segments(content))

        # 累计角色分布
        scenes_file = DATA_DIR / f"{date}.scenes.json"
        if scenes_file.exists():
            try:
                sd = json.loads(scenes_file.read_text(encoding='utf-8'))
                for role, count in sd.get("stats", {}).get("role_distribution", {}).items():
                    role_totals[role] = role_totals.get(role, 0) + count
            except Exception:
                pass

    return {
        "total_dates": total_dates,
        "total_words": total_words,
        "total_segments": total_segments,
        "role_distribution": role_totals,
    }


def get_date_detail(date: str):
    """获取单日详细内容，含场景角色数据"""
    md_file = DATA_DIR / f"{date}.md"
    if not md_file.exists():
        return None

    content = md_file.read_text(encoding='utf-8')
    segments = parse_segments(content)

    meta_file = DATA_DIR / f"{date}.meta.json"
    meta = None
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    # 读取场景数据
    scenes_file = DATA_DIR / f"{date}.scenes.json"
    scenes = None
    if scenes_file.exists():
        try:
            scenes = json.loads(scenes_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    # 把场景角色信息关联到时间段
    if scenes:
        scenes_by_time = {}
        for s in scenes.get("scenes", []):
            scenes_by_time[s["time_start"]] = {
                "role": s.get("role", {}),
                "summary": s.get("summary", "")
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
        "word_count": len(re.sub(r'\s+', '', content))
    }


def get_corrections():
    """获取纠错词典"""
    if not CORRECTIONS_FILE.exists():
        return {"corrections": []}
    try:
        return json.loads(CORRECTIONS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {"corrections": []}


def handle_correction(data: dict) -> dict:
    """处理纠正请求
    
    data: {wrong: str, right: str, date?: str, context?: str, sync_vocab?: bool}
    
    做三件事：
    1. 存入 corrections.json
    2. 如果给了 date，即时替换该日期的 .md 文件
    3. 如果 sync_vocab=true，同步到 vocab.txt
    """
    wrong = data.get('wrong', '').strip()
    right = data.get('right', '').strip()
    date = data.get('date', '')
    context = data.get('context', '')
    sync_vocab = data.get('sync_vocab', True)

    if not wrong or not right:
        return {"success": False, "error": "wrong 和 right 不能为空"}

    if wrong == right:
        return {"success": False, "error": "纠正前后相同"}

    # 1. 存入 corrections.json
    corrections_data = get_corrections()
    corrections = corrections_data.get('corrections', [])

    # 检查是否已存在
    existing = next((c for c in corrections if c['wrong'] == wrong), None)
    if existing:
        existing['right'] = right
        existing['count'] = existing.get('count', 0) + 1
        existing['last_updated'] = datetime.now().isoformat()
    else:
        corrections.append({
            "wrong": wrong,
            "right": right,
            "context": context,
            "count": 1,
            "first_seen": datetime.now().strftime('%Y-%m-%d'),
            "last_updated": datetime.now().isoformat(),
        })

    corrections_data['corrections'] = corrections
    CORRECTIONS_FILE.write_text(
        json.dumps(corrections_data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    # 2. 即时替换当前日期的 .md 文件
    replaced_in_file = 0
    if date:
        md_file = DATA_DIR / f"{date}.md"
        if md_file.exists():
            content = md_file.read_text(encoding='utf-8')
            if wrong in content:
                new_content = content.replace(wrong, right)
                md_file.write_text(new_content, encoding='utf-8')
                replaced_in_file = content.count(wrong)

    # 3. 同步到 vocab.txt
    if sync_vocab:
        try:
            sync_correction_to_vocab(wrong, right, context)
        except Exception:
            pass  # 静默失败

    return {
        "success": True,
        "correction": {"wrong": wrong, "right": right},
        "replaced_in_file": replaced_in_file,
        "total_corrections": len(corrections),
    }


class BrainHandler(SimpleHTTPRequestHandler):
    """外脑 HTTP 请求处理"""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/api/dates':
            self.json_response(get_all_dates())
        elif path == '/api/search':
            query = params.get('q', [''])[0]
            if not query:
                self.json_response([])
            else:
                self.json_response(search_content(query))
        elif path == '/api/stats':
            self.json_response(get_stats())
        elif path.startswith('/api/date/'):
            date = path.split('/api/date/')[-1]
            detail = get_date_detail(date)
            if detail:
                self.json_response(detail)
            else:
                self.send_error(404, "日期不存在")
        elif path == '/api/corrections':
            self.json_response(get_corrections())
        elif path == '/' or path == '/index.html':
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
            result = handle_correction(data)
            self.json_response(result)
        else:
            self.send_error(404, '未知接口')

    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def json_response(self, data):
        response = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def serve_index(self):
        index_path = Path(__file__).parent / 'index.html'
        if index_path.exists():
            content = index_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "index.html 不存在")

    def log_message(self, format, *args):
        pass


def main():
    print(f"🧠 周瑟夫的外脑 v2（角色归因版）")
    print(f"📂 数据目录: {DATA_DIR}")
    stats = get_stats()
    print(f"📊 {stats['total_dates']} 天 | {stats['total_segments']} 段 | {stats['total_words']} 字")
    if stats['role_distribution']:
        print(f"🏷️ 角色分布: {json.dumps(stats['role_distribution'], ensure_ascii=False)}")
    print(f"🌐 http://localhost:{PORT}")
    print(f"按 Ctrl+C 停止\n")

    server = ThreadingHTTPServer(('', PORT), BrainHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 外脑已关闭")
        server.server_close()


if __name__ == '__main__':
    main()

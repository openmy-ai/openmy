from __future__ import annotations

import argparse

from openmy.commands.common import DATA_ROOT, _help_text, add_stt_runtime_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openmy",
        description=_help_text("🎙️ OpenMy — 个人上下文引擎", "🎙️ OpenMy — personal context engine"),
    )
    sub = parser.add_subparsers(dest="command", help=_help_text("可用命令", "Available commands"))

    sub.add_parser("status", help=_help_text("列出所有日期及处理状态", "List all processed dates and their status."))

    p_view = sub.add_parser("view", help=_help_text("终端查看某天的概览", "View one day's summary in the terminal."))
    p_view.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_clean = sub.add_parser("clean", help=_help_text("清洗转写文本", "Clean one day's transcript text."))
    p_clean.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_roles = sub.add_parser("roles", help=_help_text("切场景 + 角色归因", "Split scenes and resolve who was speaking to whom."))
    p_roles.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_distill = sub.add_parser("distill", help=_help_text("蒸馏摘要（需要项目 `.env` 里的 LLM key）", "Create scene summaries. Requires an LLM key in the project .env file."))
    p_distill.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_brief = sub.add_parser("briefing", help=_help_text("生成日报", "Generate the daily briefing."))
    p_brief.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))

    p_extract = sub.add_parser("extract", help=_help_text("从转写中提取 intents / facts", "Extract intents and facts from a cleaned transcript."))
    p_extract.add_argument("input_file", help=_help_text("清洗后的 Markdown 文件路径", "Path to the cleaned Markdown transcript."))
    p_extract.add_argument("--date", help=_help_text("日期 YYYY-MM-DD，默认从文件名推断", "Date in YYYY-MM-DD format. Defaults to the date inferred from the filename."))
    p_extract.add_argument("--model", default=None, help=_help_text("LLM 模型（默认取项目 `.env` 或内置默认值）", "LLM model name. Defaults to the model configured in the project .env file or the built-in default."))
    p_extract.add_argument("--vault-path", help=_help_text("Obsidian Vault 路径", "Path to the Obsidian vault."))
    p_extract.add_argument("--api-key", help=_help_text("LLM API key", "LLM API key."))
    p_extract.add_argument("--dry-run", action="store_true", help=_help_text("只打印提取结果，不写入文件", "Print the extraction result without writing files."))

    p_run = sub.add_parser("run", help=_help_text("全流程处理", "Run the full daily pipeline."))
    p_run.add_argument("date", help=_help_text("日期 YYYY-MM-DD", "Date in YYYY-MM-DD format."))
    p_run.add_argument("--audio", nargs="+", help=_help_text("音频文件路径", "Audio file paths."))
    p_run.add_argument("--skip-transcribe", action="store_true", help=_help_text("跳过转写（使用已有数据）", "Skip transcription and reuse existing data."))
    p_run.add_argument("--skip-aggregate", action="store_true", help=_help_text("跳过周/月聚合", "Skip weekly and monthly aggregation."))
    add_stt_runtime_args(p_run)

    p_quick = sub.add_parser("quick-start", help=_help_text("第一次使用：自动处理音频并打开本地日报", "First-run guided flow: process audio and open the local report."))
    p_quick.add_argument("audio_path", nargs="?", help=_help_text("音频文件路径；传 --demo 时可不填", "Audio file path. Optional when you pass --demo."))
    p_quick.add_argument("--demo", action="store_true", help=_help_text("使用内置示例音频跑一遍主链", "Run the bundled demo flow."))
    p_quick.add_argument("--skip-aggregate", action="store_true", help=_help_text("跳过周/月聚合", "Skip weekly and monthly aggregation."))
    add_stt_runtime_args(p_quick)

    p_correct = sub.add_parser("correct", help=_help_text("纠正转写或活动上下文", "Correct transcripts or active context data."))
    p_correct.add_argument("correct_args", nargs="*", help=_help_text("纠错参数", "Correction arguments."))
    p_correct.add_argument("--status", default="done", choices=["done", "abandoned"], help=_help_text("close-loop 的关闭状态", "Status to use when closing a loop."))

    p_context = sub.add_parser("context", help=_help_text("生成/查看活动上下文", "Generate or inspect active context."))
    p_context.add_argument("--compact", action="store_true", help=_help_text("输出 Markdown 压缩版", "Render the compact Markdown view."))
    p_context.add_argument("--level", type=int, default=1, choices=[0, 1], help=_help_text("输出层级 (0=极简, 1=完整)", "Output level: 0 for minimal, 1 for full detail."))

    p_weekly = sub.add_parser("weekly", help=_help_text("查看本周回顾", "Show the weekly review."))
    p_weekly.add_argument("--week", help=_help_text("指定周，例如 2026-W15", "Specific ISO week, for example 2026-W15."))

    p_monthly = sub.add_parser("monthly", help=_help_text("查看本月回顾", "Show the monthly review."))
    p_monthly.add_argument("--month", help=_help_text("指定月，例如 2026-04", "Specific month, for example 2026-04."))

    p_watch = sub.add_parser("watch", help=_help_text("监控录音文件夹", "Watch an audio folder for new recordings."))
    p_watch.add_argument("directory", nargs="?", help=_help_text("监控目录；不传就用已配置的录音固定目录", "Directory to watch. Defaults to the configured audio source folder."))

    p_feedback = sub.add_parser("feedback", help=_help_text("管理本地反馈记录", "Manage local feedback tracking."))
    p_feedback.add_argument("--show", action="store_true", help=_help_text("查看当前本地反馈记录", "Show the current local feedback record."))
    p_feedback.add_argument("--opt-in", action="store_true", help=_help_text("开启本地反馈记录", "Enable local feedback tracking."))
    p_feedback.add_argument("--opt-out", action="store_true", help=_help_text("关闭本地反馈记录", "Disable local feedback tracking."))
    p_feedback.add_argument("--delete", action="store_true", help=_help_text("删除本地反馈记录", "Delete local feedback records."))

    p_screen = sub.add_parser("screen", help=_help_text("开关屏幕识别", "Turn screen recognition on or off."))
    p_screen.add_argument("action", choices=["on", "off", "status"], help=_help_text("on=开启，off=关闭，status=查看状态", "Use on to enable, off to disable, and status to inspect the current state."))

    sub.add_parser("self-update", help=_help_text("升级当前 OpenMy 安装", "Upgrade the current OpenMy installation."))

    p_screen_loop = sub.add_parser("_screen-capture-loop", help=argparse.SUPPRESS)
    p_screen_loop.add_argument("action", nargs="?", default="daemon", help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--interval", type=int, default=5, help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--retention-hours", type=int, default=24, help=argparse.SUPPRESS)
    p_screen_loop.add_argument("--data-root", default=str(DATA_ROOT), help=argparse.SUPPRESS)

    p_query = sub.add_parser("query", help=_help_text("基于结构化上下文查询项目/人物/待办/证据", "Query projects, people, open loops, or evidence from structured context."))
    p_query.add_argument("--kind", required=True, choices=["project", "person", "open", "closed", "evidence", "decision"])
    p_query.add_argument("--query", default="", help=_help_text("查询关键词（project / person / evidence 必填）", "Search keyword. Required for project, person, and evidence queries."))
    p_query.add_argument("--limit", type=int, default=5, help=_help_text("最多返回多少条命中", "Maximum number of matches to return."))
    p_query.add_argument("--include-evidence", action="store_true", help=_help_text("返回证据来源", "Include evidence references in the output."))
    p_query.add_argument("--json", action="store_true", help=_help_text("输出 JSON", "Output JSON."))

    p_agent = sub.add_parser("agent", help=_help_text("给 Agent 调用的统一入口", "Compatibility entrypoint for agents."))
    agent_mode = p_agent.add_mutually_exclusive_group(required=True)
    agent_mode.add_argument("--recent", action="store_true", help=_help_text("读取最近整体状态", "Read the recent overall status."))
    agent_mode.add_argument("--day", help=_help_text("查看某天结果 YYYY-MM-DD", "Read one processed day in YYYY-MM-DD format."))
    agent_mode.add_argument("--ingest", help=_help_text("处理某天输入 YYYY-MM-DD", "Process one day's input in YYYY-MM-DD format."))
    agent_mode.add_argument("--reject-decision", dest="reject_decision", help=_help_text("排除一条不重要的决策", "Reject one decision that should not be kept."))
    agent_mode.add_argument("--query", help=_help_text("按结构化结果查询项目/人物/待办/证据", "Query projects, people, open loops, or evidence from structured context."))
    p_agent.add_argument("--query-kind", default="project", choices=["project", "person", "open", "closed", "evidence", "decision"])
    p_agent.add_argument("--limit", type=int, default=5, help=_help_text("给 --query 使用", "Maximum results for --query."))
    p_agent.add_argument("--include-evidence", action="store_true", help=_help_text("给 --query 使用：带上证据来源", "Include evidence references for --query."))
    p_agent.add_argument("--audio", nargs="+", help=_help_text("给 --ingest 使用的音频文件路径", "Audio file paths for --ingest."))
    p_agent.add_argument("--skip-transcribe", action="store_true", help=_help_text("给 --ingest 使用：复用已有数据", "Reuse existing data for --ingest instead of transcribing again."))
    p_agent.add_argument("--skip-aggregate", action="store_true", help=_help_text("给 --ingest 使用：跳过周/月聚合", "Skip weekly and monthly aggregation for --ingest."))
    add_stt_runtime_args(p_agent)

    p_skill = sub.add_parser("skill", help=_help_text("稳定 JSON 动作入口", "Stable JSON action entrypoint."))
    p_skill.add_argument("action", help=_help_text("稳定动作名", "Stable action name."))
    p_skill.add_argument("--date", help=_help_text("给 day.get / day.run 使用的日期 YYYY-MM-DD", "Date for day.get or day.run in YYYY-MM-DD format."))
    p_skill.add_argument("--audio", nargs="+", help=_help_text("给 day.run 使用的音频文件路径", "Audio file paths for day.run."))
    p_skill.add_argument("--skip-transcribe", action="store_true", help=_help_text("给 day.run 使用：复用已有数据", "Reuse existing data for day.run instead of transcribing again."))
    p_skill.add_argument("--skip-aggregate", action="store_true", help=_help_text("给 day.run 使用：跳过周/月聚合", "Skip weekly and monthly aggregation for day.run."))
    add_stt_runtime_args(p_skill)
    p_skill.add_argument("--correct-args", nargs="*", help=_help_text("给 correction.apply 透传的参数", "Raw correction arguments for correction.apply."))
    p_skill.add_argument("--op", help=_help_text("给 correction.apply 使用的动作名，如 close-loop", "Operation name for correction.apply, for example close-loop."))
    p_skill.add_argument("--arg", action="append", help=_help_text("给 correction.apply 使用的动作参数，可重复", "Repeated operation arguments for correction.apply."))
    p_skill.add_argument("--status", default="done", choices=["done", "abandoned"], help=_help_text("给 correction.apply 使用的 close-loop 状态", "Loop-closing status for correction.apply."))
    p_skill.add_argument("--kind", choices=["project", "person", "open", "closed", "evidence", "decision"], help=_help_text("给 context.query 使用", "Query kind for context.query."))
    p_skill.add_argument("--query", default="", help=_help_text("给 context.query 使用的查询词", "Search query for context.query."))
    p_skill.add_argument("--limit", type=int, default=5, help=_help_text("给 context.query 使用的最大命中数", "Maximum number of matches for context.query."))
    p_skill.add_argument("--include-evidence", action="store_true", help=_help_text("给 context.query 返回证据来源", "Include evidence references for context.query."))
    p_skill.add_argument("--level", type=int, default=1, choices=[0, 1], help=_help_text("给 context.get 使用的层级", "Output level for context.get."))
    p_skill.add_argument("--compact", action="store_true", help=_help_text("给 context.get 输出压缩 Markdown", "Render compact Markdown for context.get."))
    p_skill.add_argument("--name", help=_help_text("给 profile.set 使用的名字", "Name for profile.set."))
    p_skill.add_argument("--language", help=_help_text("给 profile.set 使用的语言", "Language for profile.set."))
    p_skill.add_argument("--timezone", help=_help_text("给 profile.set 使用的时区", "Timezone for profile.set."))
    p_skill.add_argument("--audio-source", help=_help_text("给 profile.set 使用的录音固定目录", "Fixed audio source directory for profile.set."))
    p_skill.add_argument("--export-provider", choices=["obsidian", "notion"], help=_help_text("给 profile.set 使用的导出目标", "Export target for profile.set."))
    p_skill.add_argument("--export-path", help=_help_text("给 profile.set 使用的 Obsidian 目录", "Obsidian vault path for profile.set."))
    p_skill.add_argument("--export-key", help=_help_text("给 profile.set 使用的 Notion key", "Notion API key for profile.set."))
    p_skill.add_argument("--export-db", help=_help_text("给 profile.set 使用的 Notion 数据库编号", "Notion database ID for profile.set."))
    p_skill.add_argument("--screen-recognition", choices=["on", "off"], help=_help_text("给 profile.set 使用的屏幕识别开关", "Screen recognition toggle for profile.set."))
    p_skill.add_argument("--week", help=_help_text("给 aggregate 使用的周，例如 2026-W15", "ISO week for aggregate, for example 2026-W15."))
    p_skill.add_argument("--month", help=_help_text("给 aggregate 使用的月，例如 2026-04", "Month for aggregate, for example 2026-04."))
    p_skill.add_argument("--payload-json", help=_help_text("给 submit 类动作使用的 JSON 字符串", "JSON string payload for submit actions."))
    p_skill.add_argument("--payload-file", help=_help_text("给 submit 类动作使用的 JSON 文件路径", "JSON file payload for submit actions."))
    p_skill.add_argument("--json", action="store_true", help=_help_text("兼容参数；skill 默认输出 JSON", "Compatibility flag. Skill commands already output JSON by default."))

    return parser


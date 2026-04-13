from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from openmy.commands.common import DATA_ROOT, console, project_version
from openmy.services.onboarding.state import load_onboarding_state


def _show_main_menu() -> None:
    onboarding = load_onboarding_state(DATA_ROOT)
    sections = [
        (
            "快速开始",
            [
                ("openmy quick-start", "首次使用，自动引导"),
                ("openmy run 2026-04-12", "处理某天的录音"),
            ],
        ),
        (
            "处理流程",
            [
                ("openmy status", "查看所有日期的处理状态"),
                ("openmy view 2026-04-12", "查看某天的概览"),
                ("openmy run", "全流程处理"),
            ],
        ),
        (
            "单步操作",
            [
                ("openmy clean", "清洗转写文本"),
                ("openmy roles", "场景切分 + 角色归因"),
                ("openmy distill", "蒸馏摘要"),
                ("openmy briefing", "生成日报"),
                ("openmy extract", "提取意图 / 事实"),
            ],
        ),
        (
            "上下文",
            [
                ("openmy context", "生成/查看活动上下文"),
                ("openmy query", "查询项目/人物/待办"),
                ("openmy weekly", "查看本周回顾"),
                ("openmy monthly", "查看本月回顾"),
            ],
        ),
        (
            "工具",
            [
                ("openmy correct", "纠正转写错误"),
                ("openmy watch", "监控录音文件夹"),
                ("openmy screen on/off", "开关屏幕识别"),
            ],
        ),
        (
            "Agent 接口",
            [
                ("openmy skill ...", "稳定 JSON 动作入口"),
            ],
        ),
    ]

    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="left", ratio=2)

    for title, rows in sections:
        grid.add_row(f"[bold cyan]{title}[/bold cyan]", "")
        for command, description in rows:
            grid.add_row(f"  [green]{command}[/green]", f"[white]{description}[/white]")
        grid.add_row("", "")

    footer = f"v{project_version()} · https://github.com/openmy-ai/openmy"
    grid.add_row(f"[dim]{footer}[/dim]", "")
    if onboarding and not onboarding.get("completed", False):
        recommended = onboarding.get("recommended_label") or onboarding.get("recommended_provider") or "先做环境检查"
        reason = onboarding.get("recommended_reason") or onboarding.get("next_step") or "先把第一次使用走通。"
        console.print(Panel(f"下一步建议：{recommended}\n{reason}", title="首次使用引导", border_style="yellow"))
    console.print(Panel(grid, title="OpenMy — 你的个人上下文引擎", border_style="bright_blue"))

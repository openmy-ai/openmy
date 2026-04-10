from __future__ import annotations

import argparse


def _cli():
    from openmy import cli as cli_module

    return cli_module


def cmd_correct(args: argparse.Namespace) -> int:
    """终端纠错。"""
    cli = _cli()
    tokens = list(args.correct_args)
    if not tokens:
        cli.console.print("[yellow]用法：openmy correct <date> <wrong> <right> 或 openmy correct <action> ...[/yellow]")
        return 1

    if cli.DATE_RE.match(tokens[0]):
        if len(tokens) != 3:
            cli.console.print("[red]❌ 旧纠错命令需要 3 个参数：<date> <wrong> <right>[/red]")
            return 1
        return cli._cmd_correct_typo(tokens[0], tokens[1], tokens[2])

    action = tokens[0]

    if action == "typo":
        if len(tokens) != 4:
            cli.console.print("[red]❌ typo 用法：openmy correct typo <date> <wrong> <right>[/red]")
            return 1
        return cli._cmd_correct_typo(tokens[1], tokens[2], tokens[3])

    if action == "scene-role":
        if len(tokens) != 4:
            cli.console.print("[red]❌ scene-role 用法：openmy correct scene-role <date> <scene_id|time> <addressed_to>[/red]")
            return 1
        return cli._cmd_correct_scene_role(tokens[1], tokens[2], tokens[3])

    if action == "list":
        return cli.cmd_correct_list(args)

    ctx = cli._load_context_snapshot()
    if ctx is None:
        return 1

    if action == "close-loop":
        if len(tokens) != 2:
            cli.console.print("[red]❌ close-loop 用法：openmy correct close-loop <title> [--status done|abandoned][/red]")
            return 1
        loop = cli._resolve_item(
            ctx.rolling_context.open_loops,
            tokens[1],
            lambda item: [item.loop_id, item.id, item.title],
        )
        if loop is None:
            cli.console.print(f"[red]❌ 没找到待办：{tokens[1]}[/red]")
            return 1
        cli._append_context_correction(
            op="close_loop",
            target_type="loop",
            target_id=loop.loop_id or loop.id or loop.title,
            payload={"status": args.status, "target_title": loop.title},
        )
        cli.console.print(f"[green]✅ 已关闭待办[/green]: {loop.title}")
        cli.console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "reject-loop":
        if len(tokens) != 2:
            cli.console.print("[red]❌ reject-loop 用法：openmy correct reject-loop <title>[/red]")
            return 1
        loop = cli._resolve_item(
            ctx.rolling_context.open_loops,
            tokens[1],
            lambda item: [item.loop_id, item.id, item.title],
        )
        if loop is None:
            cli.console.print(f"[red]❌ 没找到待办：{tokens[1]}[/red]")
            return 1
        cli._append_context_correction(
            op="reject_loop",
            target_type="loop",
            target_id=loop.loop_id or loop.id or loop.title,
            payload={"target_title": loop.title},
        )
        cli.console.print(f"[green]✅ 已排除误判待办[/green]: {loop.title}")
        cli.console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "merge-project":
        if len(tokens) != 3:
            cli.console.print("[red]❌ merge-project 用法：openmy correct merge-project <from> <into>[/red]")
            return 1
        from_project = cli._resolve_item(
            ctx.rolling_context.active_projects,
            tokens[1],
            lambda item: [item.project_id, item.id, item.title],
        )
        into_project = cli._resolve_item(
            ctx.rolling_context.active_projects,
            tokens[2],
            lambda item: [item.project_id, item.id, item.title],
        )
        if from_project is None or into_project is None:
            cli.console.print("[red]❌ 找不到要合并的项目，请先运行 context 确认当前项目名[/red]")
            return 1
        cli._append_context_correction(
            op="merge_project",
            target_type="project",
            target_id=from_project.project_id or from_project.id or from_project.title,
            payload={
                "target_title": from_project.title,
                "merge_into": into_project.project_id or into_project.id or into_project.title,
                "merge_into_title": into_project.title,
            },
        )
        cli.console.print(f"[green]✅ 已合并项目[/green]: {from_project.title} → {into_project.title}")
        cli.console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "reject-project":
        if len(tokens) != 2:
            cli.console.print("[red]❌ reject-project 用法：openmy correct reject-project <title>[/red]")
            return 1
        project = cli._resolve_item(
            ctx.rolling_context.active_projects,
            tokens[1],
            lambda item: [item.project_id, item.id, item.title],
        )
        if project is None:
            cli.console.print(f"[red]❌ 没找到项目：{tokens[1]}[/red]")
            return 1
        cli._append_context_correction(
            op="reject_project",
            target_type="project",
            target_id=project.project_id or project.id or project.title,
            payload={"target_title": project.title},
        )
        cli.console.print(f"[green]✅ 已排除误判项目[/green]: {project.title}")
        cli.console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    if action == "reject-decision":
        if len(tokens) != 2:
            cli.console.print("[red]❌ reject-decision 用法：openmy correct reject-decision <text>[/red]")
            return 1
        decision = cli._resolve_item(
            ctx.rolling_context.recent_decisions,
            tokens[1],
            lambda item: [item.decision_id, item.id, item.decision, item.topic],
        )
        if decision is None:
            cli.console.print(f"[red]❌ 没找到决策：{tokens[1]}[/red]")
            return 1
        cli._append_context_correction(
            op="reject_decision",
            target_type="decision",
            target_id=decision.decision_id or decision.id or decision.decision,
            payload={"target_title": decision.decision},
        )
        cli.console.print(f"[green]✅ 已排除非关键决策[/green]: {decision.decision}")
        cli.console.print("[dim]运行 `python3 -m openmy context` 重新生成快照[/dim]")
        return 0

    cli.console.print(f"[red]❌ 不支持的纠错动作：{action}[/red]")
    return 1

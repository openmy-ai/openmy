from __future__ import annotations

import argparse


def _cli():
    from openmy import cli as cli_module

    return cli_module


def cmd_context(args: argparse.Namespace) -> int:
    """生成/查看活动上下文。"""
    cli = _cli()
    from openmy.services.context.active_context import ActiveContext
    from openmy.services.context.consolidation import consolidate
    from openmy.services.context.renderer import (
        render_compact_md,
        render_level0,
        render_level1,
    )

    ctx_path = cli.DATA_ROOT / "active_context.json"
    compact_path = cli.DATA_ROOT / "active_context.compact.md"
    existing = ActiveContext.load(ctx_path) if ctx_path.exists() else None

    with cli.console.status("[bold cyan]🧠 正在生成活动上下文..."):
        ctx = consolidate(cli.DATA_ROOT, existing_context=existing)
        ctx.save(ctx_path)

    if args.compact:
        markdown = render_compact_md(ctx)
        compact_path.write_text(markdown, encoding="utf-8")
        cli.console.print(f"[green]✅ 已保存[/green]: {compact_path}")
        cli.console.print(cli.Markdown(markdown))
    elif args.level == 0:
        cli.console.print(cli.Panel(render_level0(ctx), title="🧠 Level 0", border_style="cyan"))
    else:
        cli.console.print(cli.Panel(render_level1(ctx), title="🧠 Active Context", border_style="cyan"))

    cli.console.print(f"[dim]context_seq: {ctx.context_seq} | generated_at: {ctx.generated_at}[/dim]")
    return 0

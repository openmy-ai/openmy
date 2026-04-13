from __future__ import annotations

import argparse
import subprocess
import sys

from rich.panel import Panel

from openmy.commands.common import _help_text, console
from openmy.utils.errors import FriendlyCliError, doc_url


def cmd_self_update(args: argparse.Namespace) -> int:
    console.print(
        Panel(
            _help_text(
                "准备升级 OpenMy。会直接运行当前 Python 的 pip 安装器。",
                "Preparing to update OpenMy with pip from the current Python runtime.",
            ),
            border_style="bright_blue",
        )
    )
    command = [sys.executable, "-m", "pip", "install", "--upgrade", "openmy"]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise FriendlyCliError(
            _help_text("升级没跑成。", "The update did not finish."),
            code="self_update_failed",
            fix=_help_text("先检查网络，再运行 `openmy self-update` 重试。", "Check your network connection, then run openmy self-update again."),
            doc_url=doc_url("readme"),
            message_en="The update did not finish.",
            fix_en="Check your network connection, then run openmy self-update again.",
        )
    console.print(
        _help_text(
            "[green]✅ 已升级完成。重开一个终端窗口再跑 openmy --help 看新版本。[/green]",
            "[green]✅ Update finished. Open a new shell and run openmy --help to verify the new version.[/green]",
        )
    )
    return 0

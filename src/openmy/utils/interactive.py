from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Callable, Sequence, TextIO


KeyReader = Callable[[], str]
InputReader = Callable[[str], str]


def _supports_arrow_mode(platform_name: str | None = None, output: TextIO | None = None) -> bool:
    final_platform = (platform_name or sys.platform).lower()
    final_output = output or sys.stdout
    return not final_platform.startswith("win") and bool(getattr(final_output, "isatty", lambda: False)())


@contextmanager
def _raw_terminal_mode() -> None:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _read_key() -> str:
    with _raw_terminal_mode():
        first = sys.stdin.read(1)
        if first == "\x03":
            raise KeyboardInterrupt
        if first != "\x1b":
            if first in {"\r", "\n"}:
                return "enter"
            return first

        second = sys.stdin.read(1)
        third = sys.stdin.read(1)
        combo = first + second + third
        if combo == "\x1b[A":
            return "up"
        if combo == "\x1b[B":
            return "down"
        return combo


def _render_options(title: str, options: Sequence[str], current_index: int, output: TextIO) -> None:
    output.write("\033[2J\033[H")
    output.write(f"{title}\n\n")
    for index, option in enumerate(options):
        pointer = "▶" if index == current_index else " "
        prefix = "\033[1;36m" if index == current_index else ""
        suffix = "\033[0m" if index == current_index else ""
        output.write(f"  {prefix}{pointer} {option}{suffix}\n")
    output.write("\n  ↑↓ 移动  ↵ 确认\n")
    output.flush()


def select_option(
    title: str,
    options: Sequence[str],
    *,
    input_fn: InputReader = input,
    output: TextIO | None = None,
    key_reader: KeyReader | None = None,
    platform_name: str | None = None,
) -> int:
    final_output = output or sys.stdout
    if not options:
        raise ValueError("options must not be empty")

    if not _supports_arrow_mode(platform_name=platform_name, output=final_output):
        final_output.write(f"{title}\n\n")
        for index, option in enumerate(options, start=1):
            final_output.write(f"  {index}. {option}\n")
        final_output.flush()
        while True:
            answer = input_fn("\n请输入编号后按回车：").strip()
            if answer.isdigit():
                selected = int(answer) - 1
                if 0 <= selected < len(options):
                    return selected
            final_output.write("输入不对，再来一次。\n")
            final_output.flush()

    reader = key_reader or _read_key
    current_index = 0
    while True:
        _render_options(title, options, current_index, final_output)
        key = reader()
        if key == "up":
            current_index = (current_index - 1) % len(options)
        elif key == "down":
            current_index = (current_index + 1) % len(options)
        elif key == "enter":
            final_output.write("\n")
            final_output.flush()
            return current_index
        elif key == "\x03":
            raise KeyboardInterrupt


def prompt_input(
    title: str,
    hint: str,
    *,
    input_fn: InputReader = input,
    output: TextIO | None = None,
) -> str:
    final_output = output or sys.stdout
    final_output.write(f"{title}\n\n  {hint}\n")
    final_output.flush()
    return input_fn("  > ").strip()


def strip_dragged_path(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    if "\\ " in value:
        value = value.replace("\\ ", " ")
    return os.path.expanduser(value)

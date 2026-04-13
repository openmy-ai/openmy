from __future__ import annotations

import argparse
from pathlib import Path

from openmy.services.screen_recognition.capture_common import (
    DEFAULT_DATA_ROOT,
    DEFAULT_SCREENSHOT_RETENTION_HOURS,
    read_status,
    write_status,
)
from openmy.services.screen_recognition.capture_engine import capture_once


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openmy-screen-capture-tick")
    parser.add_argument("--retention-hours", type=int, default=DEFAULT_SCREENSHOT_RETENTION_HOURS)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.data_root)
    try:
        capture_once(data_root=root, retention_hours=max(1, int(args.retention_hours or DEFAULT_SCREENSHOT_RETENTION_HOURS)))
    except Exception as exc:
        status = read_status(root)
        status.last_error = str(exc)
        write_status(status, root)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

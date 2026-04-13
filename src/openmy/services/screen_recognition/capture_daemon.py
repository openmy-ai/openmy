from __future__ import annotations

import argparse
from pathlib import Path

from openmy.services.screen_recognition.capture_common import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    DEFAULT_SCREENSHOT_RETENTION_HOURS,
    DEFAULT_DATA_ROOT,
)
from openmy.services.screen_recognition.capture_engine import run_capture_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openmy-screen-capture")
    parser.add_argument("--interval", type=int, default=DEFAULT_CAPTURE_INTERVAL_SECONDS)
    parser.add_argument("--retention-hours", type=int, default=DEFAULT_SCREENSHOT_RETENTION_HOURS)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_capture_loop(
        data_root=args.data_root,
        interval_seconds=max(1, int(args.interval or DEFAULT_CAPTURE_INTERVAL_SECONDS)),
        retention_hours=max(1, int(args.retention_hours or DEFAULT_SCREENSHOT_RETENTION_HOURS)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

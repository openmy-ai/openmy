#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess

CANONICAL_README = "README.md"
TRANSLATED_READMES = [
    "README.en.md",
    "README.fr.md",
    "README.it.md",
    "README.ja.md",
    "README.ko.md",
]
ALL_READMES = [CANONICAL_README, *TRANSLATED_READMES]


def changed_files_from_git(base: str, head: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def validate_changed_files(changed_files: set[str]) -> tuple[bool, str]:
    relevant = changed_files & set(ALL_READMES)
    if CANONICAL_README not in relevant:
        return True, "主 README 没变，不需要同步检查。"

    missing = [path for path in TRANSLATED_READMES if path not in relevant]
    if not missing:
        return True, "主 README 和多语言 README 已一起更新。"

    joined = "、".join(missing)
    return False, f"检测到 README.md 已修改，但这些翻译文件没一起改：{joined}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guard multilingual README sync.")
    parser.add_argument("--base", help="Git base ref or sha for diff mode.")
    parser.add_argument("--head", help="Git head ref or sha for diff mode.")
    parser.add_argument("paths", nargs="*", help="Changed paths. Use this instead of git diff in local tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.paths:
        changed_files = set(args.paths)
    elif args.base and args.head:
        changed_files = changed_files_from_git(args.base, args.head)
    else:
        parser.error("要么传 --base/--head，要么直接传改动文件列表。")

    ok, message = validate_changed_files(changed_files)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

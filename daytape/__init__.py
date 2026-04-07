"""Repo-root package shim for the src/daytape layout."""

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "daytape"
__path__ = [str(_SRC_PACKAGE)]

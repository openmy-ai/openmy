"""Repo-root package shim for the src/openmy layout."""

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "openmy"
__path__ = [str(_SRC_PACKAGE)]

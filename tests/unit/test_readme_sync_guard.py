from __future__ import annotations

from scripts.check_readme_sync import validate_changed_files


def test_readme_sync_guard_allows_non_readme_change() -> None:
    ok, message = validate_changed_files({"src/openmy/cli.py"})
    assert ok is True
    assert "不需要同步检查" in message


def test_readme_sync_guard_requires_all_translations() -> None:
    ok, message = validate_changed_files({"README.md", "README.en.md", "README.fr.md"})
    assert ok is False
    assert "README.it.md" in message
    assert "README.ja.md" in message
    assert "README.ko.md" in message


def test_readme_sync_guard_passes_when_every_variant_changes() -> None:
    ok, message = validate_changed_files(
        {"README.md", "README.en.md", "README.fr.md", "README.it.md", "README.ja.md", "README.ko.md"}
    )
    assert ok is True
    assert "一起更新" in message

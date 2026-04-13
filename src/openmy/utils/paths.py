from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def find_project_root(
    start_path: Path | None = None,
    *,
    cwd: Path | None = None,
) -> Path | None:
    env_root = _env_path("OPENMY_PROJECT_ROOT")
    if env_root:
        env_candidate = env_root.resolve()
        if (env_candidate / "pyproject.toml").exists():
            return env_candidate

    candidates: list[Path] = []
    if start_path is not None:
        candidates.append(Path(start_path).resolve())
    else:
        candidates.append(Path(__file__).resolve())
    if cwd is not None:
        candidates.append(Path(cwd).resolve())
    else:
        candidates.append(Path.cwd().resolve())

    seen: set[Path] = set()
    for base in candidates:
        search_root = base if base.is_dir() else base.parent
        for candidate in [search_root, *search_root.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "pyproject.toml").exists():
                return candidate
    return None


def resolve_project_root(start_path: Path | None = None) -> Path:
    return find_project_root(start_path) or Path.home() / ".openmy"


def resolve_data_root(start_path: Path | None = None) -> Path:
    env_data_root = _env_path("OPENMY_DATA_DIR")
    if env_data_root:
        return env_data_root.resolve()

    project_root = find_project_root(start_path)
    if project_root is not None:
        return (project_root / "data").resolve()

    return (Path.home() / ".openmy" / "data").resolve()


PROJECT_ROOT = resolve_project_root()
DATA_ROOT = resolve_data_root()
LEGACY_ROOT = PROJECT_ROOT
PROJECT_ENV_PATH = PROJECT_ROOT / ".env"

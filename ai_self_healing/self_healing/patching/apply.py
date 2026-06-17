from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from self_healing.patching.safety import resolve_safe_path


def read_target(project_root: str | Path, relative_path: str, allowed_paths: list[str]) -> str:
    path = resolve_safe_path(project_root, relative_path, allowed_paths)
    return path.read_text(encoding="utf-8")


def write_target(project_root: str | Path, relative_path: str, code: str, allowed_paths: list[str]) -> Path:
    path = resolve_safe_path(project_root, relative_path, allowed_paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
        tmp.write(code)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    return path

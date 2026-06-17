from __future__ import annotations

from pathlib import Path


def resolve_safe_path(project_root: str | Path, relative_path: str, allowed_paths: list[str]) -> Path:
    root = Path(project_root).resolve()
    target = (root / relative_path).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"拒绝访问项目根目录外的路径: {relative_path}")
    normalized = target.relative_to(root).as_posix()
    allowed = allowed_paths or [normalized]
    if not any(normalized == item.rstrip("/") or normalized.startswith(item.rstrip("/") + "/") for item in allowed):
        raise ValueError(f"路径不在允许修改范围内: {normalized}")
    return target

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LSPConfig:
    command: list[str] = field(default_factory=lambda: ["pyright-langserver", "--stdio"])
    language_id: str = "python"


@dataclass(frozen=True)
class SandboxConfig:
    image: str = "python:3.11-slim"
    timeout_seconds: int = 30
    workdir: str = "/app"
    backend: str = "auto"


@dataclass(frozen=True)
class HealConfig:
    project_root: Path
    file_path: str
    test_command: list[str]
    max_iterations: int = 3
    allowed_paths: list[str] = field(default_factory=list)
    lsp: LSPConfig = field(default_factory=LSPConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)


def _load_mapping(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(raw)
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("读取 YAML 配置需要安装 pyyaml，或改用 JSON 配置。") from exc
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("配置文件顶层必须是对象。")
    return data


def load_config(path: str | Path) -> HealConfig:
    config_path = Path(path).expanduser().resolve()
    data = _load_mapping(config_path)
    root = Path(data.get("project_root", config_path.parent)).expanduser().resolve()
    test_command = data["test_command"]
    if isinstance(test_command, str):
        import shlex
        test_command = shlex.split(test_command)
    if not isinstance(test_command, list) or not all(isinstance(x, str) for x in test_command):
        raise ValueError("test_command 必须是字符串或字符串数组。")
    lsp_data = data.get("lsp", {}) or {}
    sandbox_data = data.get("sandbox", {}) or {}
    return HealConfig(
        project_root=root,
        file_path=str(data["file_path"]),
        test_command=test_command,
        max_iterations=int(data.get("max_iterations", 3)),
        allowed_paths=list(data.get("allowed_paths", [data["file_path"]])),
        lsp=LSPConfig(
            command=list(lsp_data.get("command", ["pyright-langserver", "--stdio"])),
            language_id=str(lsp_data.get("language_id", "python")),
        ),
        sandbox=SandboxConfig(
            image=str(sandbox_data.get("image", "python:3.11-slim")),
            timeout_seconds=int(sandbox_data.get("timeout_seconds", 30)),
            workdir=str(sandbox_data.get("workdir", "/app")),
            backend=str(sandbox_data.get("backend", "auto")),
        ),
    )

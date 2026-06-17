from __future__ import annotations

from pathlib import Path

from self_healing.lsp.client import StdioLSPClient


def create_pyright_client(root: str | Path, command: list[str] | None = None) -> StdioLSPClient:
    return StdioLSPClient(command or ["pyright-langserver", "--stdio"], root=root, language_id="python")

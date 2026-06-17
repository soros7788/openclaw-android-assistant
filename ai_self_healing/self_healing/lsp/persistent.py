from __future__ import annotations

"""常驻 LSP 客户端：

- 启动后一直保持连接，不用每次自愈都启/停一次 server
- 支持打开、增量更新、关闭多个文件
- 对每一个文件都能即时拉取最新诊断
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from self_healing.lsp.client import StdioLSPClient, file_uri
from self_healing.state import LSPDiagnostic


@dataclass
class OpenDocument:
    path: str
    uri: str
    version: int


class PersistentLSPClient:
    """在 daemon 生命周期内一直保持一个 LSP 进程。

    它内部维护打开的文件版本号，每次文件内容变更时发出 textDocument/didChange，
    并提供一个 `diagnostics_for_path(path)` 的便捷接口。
    """

    def __init__(self, command: list[str], root: str | Path, language_id: str = "python") -> None:
        self._client = StdioLSPClient(command=command, root=root, language_id=language_id)
        self._documents: dict[str, OpenDocument] = {}
        self._started = False

    # --- lifecycle ----------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._client.start()
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._client.stop()
        self._started = False

    def __enter__(self) -> "PersistentLSPClient":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    # --- document ops -------------------------------------------------

    def open_or_update(self, path: str | Path, text: str) -> str:
        """打开一个文件或对其发送增量更新，返回文件的 uri。

        - 若文件尚未打开：发送 didOpen，记录 version=1
        - 若已打开：版本号递增，发送 full-document didChange
          （选择全量替换是为了避免行号对齐问题，工程成本最低）
        """
        p = str(Path(path).resolve())
        if p in self._documents:
            doc = self._documents[p]
            doc.version += 1
            self._client.notify("textDocument/didChange", {
                "textDocument": {"uri": doc.uri, "version": doc.version},
                "contentChanges": [{"text": text}],
            })
            return doc.uri

        uri = self._client.open_document(p, text)
        self._documents[p] = OpenDocument(path=p, uri=uri, version=1)
        return uri

    def close(self, path: str | Path) -> None:
        p = str(Path(path).resolve())
        doc = self._documents.pop(p, None)
        if doc is None:
            return
        self._client.notify("textDocument/didClose", {"textDocument": {"uri": doc.uri}})

    # --- diagnostics --------------------------------------------------

    def diagnostics_for_path(
        self,
        path: str | Path,
        wait_seconds: float = 2.0,
    ) -> list[LSPDiagnostic]:
        p = str(Path(path).resolve())
        doc = self._documents.get(p)
        if doc is None:
            return []
        return self._client.diagnostics_for(doc.uri, wait_seconds=wait_seconds)

    # --- convenience --------------------------------------------------

    def opened_paths(self) -> list[str]:
        return list(self._documents)

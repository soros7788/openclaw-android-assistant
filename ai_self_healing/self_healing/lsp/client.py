from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from self_healing.lsp.diagnostics import normalize_diagnostic
from self_healing.state import LSPDiagnostic


def file_uri(path: str | Path) -> str:
    return "file://" + quote(str(Path(path).resolve()))


class StdioLSPClient:
    def __init__(self, command: list[str], root: str | Path, language_id: str = "python") -> None:
        self.command = command
        self.root = Path(root).resolve()
        self.language_id = language_id
        self._next_id = 1
        self._process: subprocess.Popen[bytes] | None = None
        self._diagnostics: dict[str, list[LSPDiagnostic]] = {}
        self._reader: threading.Thread | None = None
        self._responses: dict[int, dict[str, Any]] = {}

    def __enter__(self) -> "StdioLSPClient":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def start(self) -> None:
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self.request("initialize", {
            "processId": None,
            "rootUri": file_uri(self.root),
            "capabilities": {},
        }, timeout=10)
        self.notify("initialized", {})

    def stop(self) -> None:
        if not self._process:
            return
        try:
            self.request("shutdown", None, timeout=3)
            self.notify("exit", {})
        except Exception:
            pass
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def request(self, method: str, params: Any, timeout: float = 5) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.time() + timeout
        while time.time() < deadline:
            if request_id in self._responses:
                return self._responses.pop(request_id)
            time.sleep(0.02)
        raise TimeoutError(f"LSP request timed out: {method}")

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def open_document(self, path: str | Path, text: str) -> str:
        uri = file_uri(path)
        self.notify("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": self.language_id,
                "version": 1,
                "text": text,
            }
        })
        return uri

    def diagnostics_for(self, uri: str, wait_seconds: float = 2) -> list[LSPDiagnostic]:
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if uri in self._diagnostics:
                return self._diagnostics[uri]
            time.sleep(0.05)
        return self._diagnostics.get(uri, [])

    def _send(self, payload: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("LSP 进程未启动。")
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._process.stdin.write(header + body)
        self._process.stdin.flush()

    def _read_loop(self) -> None:
        assert self._process and self._process.stdout
        stdout = self._process.stdout
        while True:
            header = stdout.readline()
            if not header:
                break
            if not header.lower().startswith(b"content-length:"):
                continue
            length = int(header.split(b":", 1)[1].strip())
            while stdout.readline().strip():
                pass
            body = stdout.read(length)
            message = json.loads(body.decode("utf-8"))
            if "id" in message:
                self._responses[int(message["id"])] = message
            elif message.get("method") == "textDocument/publishDiagnostics":
                params = message.get("params", {})
                uri = params.get("uri", "")
                self._diagnostics[uri] = [normalize_diagnostic(x) for x in params.get("diagnostics", [])]

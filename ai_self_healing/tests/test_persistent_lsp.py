from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from self_healing.lsp.persistent import PersistentLSPClient


class FakeStdioLSPClient:
    """替身 StdioLSPClient：直接跟踪被调用的方法。"""

    def __init__(self, command=None, root=None, language_id="python"):
        self.command = command
        self.root = root
        self.language_id = language_id
        self.started = False
        self.stopped = False
        self.opens: list[dict] = []
        self.changes: list[dict] = []
        self.closes: list[str] = []
        self._diagnostics: dict[str, list] = {}

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def open_document(self, path, text):
        uri = f"file://{path}"
        self.opens.append({"uri": uri, "text": text})
        return uri

    def notify(self, method, params):
        if method == "textDocument/didChange":
            self.changes.append(params)
        elif method == "textDocument/didClose":
            self.closes.append(params["textDocument"]["uri"])

    def diagnostics_for(self, uri, wait_seconds=2):
        # 返回预设诊断，模拟 LSP
        return self._diagnostics.get(uri, [])

    # PersistentLSPClient 里用了 request / notify("initialized")，但当前代码里 PersistentLSPClient 只调用 start/diagnostics_for/open_or_update/stop，所以 mock 这些即可


class PersistentLSPClientTests(unittest.TestCase):
    def test_start_stop_is_idempotent(self):
        client = PersistentLSPClient(command=["fake-lsp"], root="/tmp", language_id="python")
        # 用替身替换内部 client（不走真实 subprocess）
        client._client = FakeStdioLSPClient()  # type: ignore[assignment]
        client.start()
        client.start()  # 再次调用应当是 no-op
        client.stop()
        client.stop()  # 再次 stop 也应 no-op
        self.assertTrue(client._client.started)
        self.assertTrue(client._client.stopped)

    def test_open_increments_version(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "app.py"
            target.write_text("print('hi')\n", encoding="utf-8")
            client = PersistentLSPClient(command=["fake-lsp"], root=tmp, language_id="python")
            client._client = FakeStdioLSPClient()  # type: ignore[assignment]
            uri1 = client.open_or_update(str(target), "v1")
            uri2 = client.open_or_update(str(target), "v2")
            self.assertEqual(uri1, uri2)
            # 第一次是 open_document，第二次是 didChange，且 version 递增
            self.assertEqual(len(client._client.opens), 1)
            self.assertEqual(len(client._client.changes), 1)
            change = client._client.changes[0]
            self.assertEqual(change["contentChanges"][0]["text"], "v2")

    def test_close_sends_notification(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "app.py"
            client = PersistentLSPClient(command=["fake-lsp"], root=tmp)
            client._client = FakeStdioLSPClient()  # type: ignore[assignment]
            uri = client.open_or_update(str(target), "code")
            client.close(str(target))
            self.assertIn(uri, client._client.closes)
            # 关不存在的文件应当是安全 no-op
            client.close("/tmp/nope.py")

    def test_diagnostics_for_path_returns_client_data(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "app.py"
            client = PersistentLSPClient(command=["fake-lsp"], root=tmp)
            fake = FakeStdioLSPClient()
            client._client = fake  # type: ignore[assignment]
            uri = client.open_or_update(str(target), "code")
            fake._diagnostics[uri] = [{"severity": "Error", "message": "bad", "range": {}}]
            diags = client.diagnostics_for_path(str(target), wait_seconds=0.05)
            self.assertEqual(len(diags), 1)


if __name__ == "__main__":
    unittest.main()

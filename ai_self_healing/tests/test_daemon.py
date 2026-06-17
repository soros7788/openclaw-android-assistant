from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from self_healing.config import HealConfig
from self_healing.daemon import (
    SelfHealingDaemon,
    print_status,
    run_once,
    stop_daemon,
)


class SelfHealingDaemonTests(unittest.TestCase):
    def _make_config(self, root: Path, content: str) -> HealConfig:
        (root / "target.py").write_text(content, encoding="utf-8")
        return HealConfig(
            project_root=root,
            file_path="target.py",
            test_command=["python", "-c", "import ast; ast.parse(open('target.py').read())"],
            max_iterations=2,
            allowed_paths=["target.py"],
            lsp=None,
            sandbox=None,
            healer=None,
        )

    def test_run_once_writes_state_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._make_config(root, "x = 1\n")
            daemon = SelfHealingDaemon(config, min_interval=0.0)
            summary = daemon.run_once(force=True)
            self.assertTrue("status" in summary or summary.get("runs"))
            state_path = root / ".self_healing" / "state.json"
            self.assertTrue(state_path.exists())
            data = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("pid", data)
            self.assertIn("runs", data)
            self.assertIn("fixes_applied", data)

    def test_run_once_content_dedup_by_hash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._make_config(root, "x = 1\n")
            daemon = SelfHealingDaemon(config, min_interval=0.0)
            daemon.run_once(force=True)
            first_fixes = daemon._status.fixes_applied
            # 再跑一次：内容未变且没有被修复，不继续修
            noop = daemon.run_once(force=False)
            self.assertTrue(noop.get("skipped"))
            self.assertEqual(daemon._status.fixes_applied, first_fixes)

    def test_stop_daemon_reads_pid_from_state(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._make_config(root, "x=1\n")
            # 造一个 state 文件，让 stop 能读到 pid 但发送信号失败（无此 pid）
            (root / ".self_healing").mkdir(parents=True, exist_ok=True)
            nonexistent_pid = 9999999
            (root / ".self_healing" / "state.json").write_text(
                json.dumps({"pid": nonexistent_pid}), encoding="utf-8")
            self.assertEqual(stop_daemon(config), 0)

    def test_print_status_returns_zero_without_state(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._make_config(root, "x=1\n")
            self.assertEqual(print_status(config), 0)


if __name__ == "__main__":
    unittest.main()

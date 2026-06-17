from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from self_healing.watcher import FileChange, PollingWatcher


class PollingWatcherTests(unittest.TestCase):
    def test_detects_new_file_after_start(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            received: list[list[FileChange]] = []
            w = PollingWatcher(root, suffixes={".py"}, poll_interval=0.1, debounce=0.25)
            w.start(on_change=lambda changes: received.append(list(changes)))
            try:
                time.sleep(0.2)
                (root / "a.py").write_text("print(1)\n", encoding="utf-8")
                time.sleep(0.7)
            finally:
                w.stop()
            # 至少收到一次事件，包含 a.py 的"created"
            self.assertTrue(any("a.py" in str(c.path) for batch in received for c in batch),
                            msg=f"expected a.py in {received}")

    def test_ignores_non_target_suffixes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            received: list[list[FileChange]] = []
            w = PollingWatcher(root, suffixes={".py"}, poll_interval=0.1, debounce=0.25)
            w.start(on_change=lambda changes: received.append(list(changes)))
            try:
                time.sleep(0.1)
                (root / "readme.txt").write_text("hello\n", encoding="utf-8")
                time.sleep(0.6)
            finally:
                w.stop()
            # 不应触发事件
            self.assertEqual(sum(len(b) for b in received), 0)

    def test_debounce_groups_rapid_events(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            received: list[list[FileChange]] = []
            w = PollingWatcher(root, suffixes={".py"}, poll_interval=0.05, debounce=0.3)
            w.start(on_change=lambda changes: received.append(list(changes)))
            try:
                time.sleep(0.1)
                for i in range(5):
                    (root / f"f{i}.py").write_text(f"# {i}\n", encoding="utf-8")
                    time.sleep(0.05)
                time.sleep(0.6)
            finally:
                w.stop()
            # 5 次快速写入应该被合并为 1 次回调批次
            batches_with_content = [b for b in received if b]
            self.assertLessEqual(len(batches_with_content), 2,
                                 msg=f"expected <= 2 batches, got {len(batches_with_content)}: {received}")

    def test_skips_known_noisy_dirs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "module.pyc").write_text("ignored\n", encoding="utf-8")
            received: list[list[FileChange]] = []
            w = PollingWatcher(root, suffixes={".py", ".pyc"}, poll_interval=0.1, debounce=0.25)
            w.start(on_change=lambda changes: received.append(list(changes)))
            try:
                time.sleep(0.4)
            finally:
                w.stop()
            # __pycache__ 目录应被跳过，因此没有事件
            self.assertEqual(sum(len(b) for b in received), 0)

    def test_stop_is_graceful(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            w = PollingWatcher(root, suffixes={".py"}, poll_interval=0.1, debounce=0.2)
            t = w.start(on_change=lambda changes: None)
            time.sleep(0.2)
            w.stop()
            # 等待最多 2 秒让线程退出
            deadline = time.monotonic() + 2.0
            while t.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(t.is_alive(), "watcher thread should exit after stop()")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

"""文件变动监听器：跨平台、轻量级，支持扩展名过滤与事件节流（debounce）。

目标是监听用户项目目录，当检测到源码/测试文件变动时触发一次自愈周期。
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Thread
from typing import Callable, Iterable


@dataclass(frozen=True)
class FileChange:
    path: str
    event: str  # "modified" | "created" | "deleted"


class PollingWatcher:
    """基于轮询的文件变动监听器——无需三方依赖，跨平台可用。

    用法：
        w = PollingWatcher(Path("src"), suffixes={".py", ".ts"}, poll_interval=0.5, debounce=1.0)
        w.start(on_change=lambda changes: print(changes))
        # ...
        w.stop()
    """

    def __init__(
        self,
        root: Path,
        suffixes: set[str] | None = None,
        poll_interval: float = 0.5,
        debounce: float = 1.0,
    ) -> None:
        self.root = Path(root).resolve()
        self.suffixes = {s.lower() for s in (suffixes or {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml"})}
        self.poll_interval = poll_interval
        self.debounce = debounce
        self._thread: Thread | None = None
        self._stop_flag = False
        self._snapshot: dict[str, float] = {}

    def __enter__(self) -> "PollingWatcher":
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def start(self, on_change: Callable[[list[FileChange]], None]) -> Thread:
        self._snapshot = self._take_snapshot()
        self._stop_flag = False
        self._thread = Thread(target=self._run_loop, args=(on_change,), daemon=True, name="PollingWatcher")
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop_flag = True
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval * 4 + self.debounce + 1)

    # --- internals -----------------------------------------------------

    def _iter_files(self) -> Iterable[Path]:
        """迭代目标目录里所有匹配扩展名的文件。

        为了保持简单，忽略 .git / node_modules / __pycache__ 等常见目录。
        """
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache", ".self_healing"}
        for dirpath, dirnames, filenames in os.walk(self.root):
            # 原地修改以跳过子目录
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix.lower() in self.suffixes:
                    yield p

    def _take_snapshot(self) -> dict[str, float]:
        snap: dict[str, float] = {}
        for p in self._iter_files():
            try:
                snap[str(p)] = p.stat().st_mtime
            except OSError:
                continue
        return snap

    def _diff(self, new: dict[str, float]) -> list[FileChange]:
        changes: list[FileChange] = []
        for path, mtime in new.items():
            prev = self._snapshot.get(path)
            if prev is None:
                changes.append(FileChange(path=path, event="created"))
            elif abs(mtime - prev) > 1e-6:
                changes.append(FileChange(path=path, event="modified"))
        for path in self._snapshot:
            if path not in new:
                changes.append(FileChange(path=path, event="deleted"))
        return changes

    def _run_loop(self, on_change: Callable[[list[FileChange]], None]) -> None:
        last_event_time = 0.0
        pending: list[FileChange] = []
        # 以 poll_interval 轮询，以 debounce 做批次合并
        while not self._stop_flag:
            new_snap = self._take_snapshot()
            diff = self._diff(new_snap)
            self._snapshot = new_snap
            if diff:
                pending.extend(diff)
                last_event_time = time.monotonic()
            # 有 pending 且距离最近事件已超过 debounce，则通知一次
            if pending and (time.monotonic() - last_event_time) >= self.debounce:
                batch = pending
                pending = []
                try:
                    on_change(batch)
                except Exception:
                    # 监听器不应被用户回调崩溃影响
                    pass
            time.sleep(self.poll_interval)

from __future__ import annotations

"""自愈守护进程：

- 常驻一个 LSP 客户端
- 监听项目源码目录变动
- 触发自愈图（LangGraph）并把修复写回磁盘
- 维护一份轻量状态文件（.self_healing/state.json）用于停止和查询
"""

import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field, asdict
import datetime
from pathlib import Path
from typing import Any

from self_healing.config import HealConfig
from self_healing.graph import build_graph
from self_healing.lsp.persistent import PersistentLSPClient
from self_healing.patching.apply import read_target, write_target
from self_healing.preflight import run_preflight
from self_healing.state import AgentState
from self_healing.watcher import FileChange, PollingWatcher


def _ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class DaemonStatus:
    pid: int
    started_at: str
    last_event_at: str | None = None
    files_analyzed: int = 0
    runs: int = 0
    fixes_applied: int = 0
    recent_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SelfHealingDaemon:
    """把 watcher + LSP + LangGraph 粘合起来。

    设计原则：
    1. **最小侵入**：只修改诊断/测试失败的文件
    2. **幂等**：同一文件在上一轮已被修复且无新改动则跳过
    3. **可停止**：支持 SIGINT / SIGTERM 优雅退出
    4. **可观测**：状态落盘，可随时查看
    """

    def __init__(self, config: HealConfig, *, min_interval: float = 5.0) -> None:
        self.config = config
        self.root = Path(config.project_root).resolve()
        self.state_dir = self.root / ".self_healing"
        self.state_path = self.state_dir / "state.json"
        self.min_interval = min_interval
        self._last_run_time = 0.0
        self._stop_flag = False
        self._lsp: PersistentLSPClient | None = None
        self._watcher: PollingWatcher | None = None
        self._status = DaemonStatus(pid=os.getpid(), started_at=_ts())
        # 避免重复修复同一个内容哈希
        self._seen_hashes: set[str] = set()

    # -------- public control API -----------------------------------

    def run_once(self, force: bool = False) -> dict[str, Any]:
        """执行一次完整的自愈周期：读取目标文件 → LSP → 沙盒 → 修复 → 落盘。

        当 `force=False` 且距离上次运行不足 min_interval 秒时跳过，防止重复运行。
        返回本次运行结果的摘要字典。
        """
        now = time.monotonic()
        if not force and now - self._last_run_time < self.min_interval:
            return {"status": "skipped (too soon)", "skipped": True}
        self._last_run_time = now

        config = self.config
        target = self.root / config.file_path
        try:
            code = read_target(self.root, config.file_path, config.allowed_paths)
        except Exception as exc:
            return {"status": "error", "reason": f"read_target failed: {exc}"}

        # 内容与上次处理完全一致时跳过，避免死循环
        code_hash = _hash_text(code)
        if code_hash in self._seen_hashes and not force:
            return {"status": "skipped (content unchanged)", "skipped": True}
        self._seen_hashes.add(code_hash)

        # 调用 LangGraph 自愈
        state: AgentState = {
            "project_root": str(self.root),
            "file_path": config.file_path,
            "test_command": config.test_command,
            "current_code": code,
            "lsp_diagnostics": [],
            "exec_logs": "",
            "exit_code": -1,
            "iterations": 0,
            "max_iterations": config.max_iterations,
            "is_fixed": False,
            "attempts": [],
            "allowed_paths": config.allowed_paths,
        }

        result_summary: dict[str, Any] = {}
        final: dict[str, Any] = {}
        try:
            app = build_graph(config)
            final = dict(app.invoke(state))
        except Exception as exc:
            result_summary = {"status": "graph_error", "error": str(exc)}
        else:
            fixed = bool(final.get("is_fixed"))
            result_summary = {
                "status": "fixed" if fixed else "no_fix",
                "iterations": final.get("iterations", 0),
                "exit_code": final.get("exit_code", -1),
                "attempts": final.get("attempts", []),
            }
            try:
                if fixed and final.get("current_code") and final["current_code"] != code:
                    write_target(self.root, config.file_path, final["current_code"], config.allowed_paths)
                    self._seen_hashes.add(_hash_text(final["current_code"]))
                    self._status.fixes_applied += 1
                    result_summary["applied"] = True
            except Exception as exc:
                result_summary["apply_error"] = str(exc)

        self._status.runs += 1
        self._status.last_event_at = _ts()
        self._status.files_analyzed += 1
        self._status.recent_events.append({"time": _ts(), **result_summary})
        if len(self._status.recent_events) > 20:
            self._status.recent_events = self._status.recent_events[-20:]
        self._persist_status()
        return result_summary

    def serve_forever(self) -> DaemonStatus:
        """进入监听模式：文件变动触发自愈，直到被 stop() 或信号终止。"""
        self._setup_signal_handlers()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._persist_status()
        _log(f"[daemon] starting @ {self.root}  (target: {self.config.file_path})")

        # 启动一次全量 preflight + 首轮自愈
        preflight = run_preflight(self.config)
        if not preflight.ok:
            _log(f"[daemon] preflight 有警告（将继续运行 echo/本地沙盒）: {preflight.to_dict()}")

        self.run_once(force=True)

        # 启动 watcher
        self._watcher = PollingWatcher(
            self.root,
            suffixes=self._target_suffixes(),
            poll_interval=0.5,
            debounce=1.0,
        )
        self._watcher.start(on_change=self._on_changes)

        try:
            while not self._stop_flag:
                time.sleep(0.5)
        finally:
            if self._watcher is not None:
                self._watcher.stop()
        return self._status

    def stop(self) -> None:
        self._stop_flag = True

    # -------- internals ---------------------------------------------

    def _on_changes(self, changes: list[FileChange]) -> None:
        # 只在目标文件变动时触发自愈
        target_abs = str((self.root / self.config.file_path).resolve())
        relevant = [c for c in changes if c.path == target_abs]
        if not relevant:
            return
        _log(f"[daemon] detected {len(relevant)} change(s) for target")
        summary = self.run_once()
        _log(f"[daemon] cycle result: {summary.get('status')}")

    def _target_suffixes(self) -> set[str]:
        suffix = Path(self.config.file_path).suffix.lower()
        return {suffix} if suffix else {".py"}

    def _setup_signal_handlers(self) -> None:
        for sig_name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, lambda *_: self.stop())
            except (ValueError, OSError):
                # 非主线程无法安装信号；忽略
                pass

    def _persist_status(self) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(self._status.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


def _log(msg: str) -> None:
    print(f"{_ts()} {msg}", flush=True)


def _hash_text(text: str) -> str:
    import hashlib
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# ---------- CLI-friendly helpers -----------------------------------

def run_daemon(config: HealConfig) -> int:
    daemon = SelfHealingDaemon(config)
    try:
        status = daemon.serve_forever()
    finally:
        daemon.stop()
    _log(f"[daemon] stopped -> {status.to_dict()}")
    return 0


def run_once(config: HealConfig) -> int:
    daemon = SelfHealingDaemon(config, min_interval=0.0)
    summary = daemon.run_once(force=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("status") == "fixed" else 1


def stop_daemon(config: HealConfig) -> int:
    """读取 state.json 得到 pid，尝试 SIGTERM。"""
    state_path = Path(config.project_root) / ".self_healing" / "state.json"
    if not state_path.exists():
        print("no daemon state file found; nothing to stop.")
        return 0
    try:
        pid = json.loads(state_path.read_text(encoding="utf-8")).get("pid")
    except (OSError, json.JSONDecodeError):
        pid = None
    if not pid:
        print("no pid recorded; nothing to stop.")
        return 0
    try:
        os.kill(int(pid), signal.SIGTERM)
        print(f"sent SIGTERM to pid={pid}.")
        return 0
    except ProcessLookupError:
        print(f"pid={pid} not running.")
        return 0
    except PermissionError as exc:
        print(f"permission error: {exc}")
        return 1


def print_status(config: HealConfig) -> int:
    state_path = Path(config.project_root) / ".self_healing" / "state.json"
    if not state_path.exists():
        print("no daemon state file; daemon has never run.")
        return 0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"unable to read state: {exc}")
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0

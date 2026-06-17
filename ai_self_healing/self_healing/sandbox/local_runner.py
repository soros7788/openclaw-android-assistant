from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from self_healing.sandbox.logs import filter_relevant_logs


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    logs: str
    timed_out: bool = False


class LocalSandbox:
    """本地子进程沙盒。

    这是 Docker 不可用时的降级后端，隔离性弱于 Docker，但可以让闭环系统在 CI、
    受限开发机或当前环境中继续完成测试验证。
    """

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, project_root: str | Path, command: list[str]) -> SandboxResult:
        try:
            completed = subprocess.run(
                command,
                cwd=str(Path(project_root).resolve()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            logs = completed.stdout + completed.stderr
            return SandboxResult(
                exit_code=completed.returncode,
                logs=filter_relevant_logs(logs),
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return SandboxResult(
                exit_code=124,
                logs=filter_relevant_logs(stdout + stderr + "\nLocal sandbox timed out."),
                timed_out=True,
            )

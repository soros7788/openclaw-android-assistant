from __future__ import annotations

from pathlib import Path

from self_healing.sandbox.logs import filter_relevant_logs
from self_healing.sandbox.local_runner import SandboxResult


DockerResult = SandboxResult


def docker_daemon_available() -> tuple[bool, str]:
    try:
        import docker
    except ImportError:
        return False, "未安装 docker Python SDK。"
    try:
        docker.from_env().ping()
        return True, "Docker daemon 可访问。"
    except Exception as exc:
        return False, f"Docker daemon 不可访问: {exc}"


class DockerSandbox:
    def __init__(self, image: str, timeout_seconds: int = 30, workdir: str = "/app") -> None:
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.workdir = workdir

    def run(self, project_root: str | Path, command: list[str]) -> DockerResult:
        try:
            import docker
            from requests.exceptions import ReadTimeout
        except ImportError as exc:
            raise RuntimeError("Docker 沙盒需要安装 docker Python SDK。") from exc

        client = docker.from_env()
        container = client.containers.create(
            image=self.image,
            command=command,
            volumes={str(Path(project_root).resolve()): {"bind": self.workdir, "mode": "rw"}},
            working_dir=self.workdir,
            stdout=True,
            stderr=True,
            detach=True,
        )
        try:
            container.start()
            try:
                result = container.wait(timeout=self.timeout_seconds)
                exit_code = int(result.get("StatusCode", 1))
                raw_logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                return DockerResult(exit_code=exit_code, logs=filter_relevant_logs(raw_logs), timed_out=False)
            except ReadTimeout:
                container.kill()
                raw_logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                return DockerResult(
                    exit_code=124,
                    logs=filter_relevant_logs(raw_logs + "\nSandbox timed out."),
                    timed_out=True,
                )
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass

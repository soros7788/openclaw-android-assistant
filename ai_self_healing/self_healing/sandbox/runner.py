from __future__ import annotations

from self_healing.config import SandboxConfig
from self_healing.sandbox.docker_runner import DockerSandbox, docker_daemon_available
from self_healing.sandbox.local_runner import LocalSandbox


def create_sandbox(config: SandboxConfig):
    backend = config.backend.lower()
    if backend == "docker":
        return DockerSandbox(
            image=config.image,
            timeout_seconds=config.timeout_seconds,
            workdir=config.workdir,
        )
    if backend == "local":
        return LocalSandbox(timeout_seconds=config.timeout_seconds)
    if backend == "auto":
        available, _ = docker_daemon_available()
        if available:
            return DockerSandbox(
                image=config.image,
                timeout_seconds=config.timeout_seconds,
                workdir=config.workdir,
            )
        return LocalSandbox(timeout_seconds=config.timeout_seconds)
    raise ValueError(f"未知 sandbox backend: {config.backend}")

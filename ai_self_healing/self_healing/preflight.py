from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from self_healing.config import HealConfig
from self_healing.patching.safety import resolve_safe_path
from self_healing.sandbox.docker_runner import docker_daemon_available


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    message: str


@dataclass(frozen=True)
class PreflightReport:
    ok: bool
    checks: list[PreflightCheck]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": [
                {"name": check.name, "ok": check.ok, "message": check.message}
                for check in self.checks
            ],
        }


def _check_project_root(config: HealConfig) -> PreflightCheck:
    if config.project_root.is_dir():
        return PreflightCheck("project_root", True, f"项目根目录存在: {config.project_root}")
    return PreflightCheck("project_root", False, f"项目根目录不存在: {config.project_root}")


def _check_target_file(config: HealConfig) -> PreflightCheck:
    try:
        target = resolve_safe_path(config.project_root, config.file_path, config.allowed_paths)
    except ValueError as exc:
        return PreflightCheck("target_file", False, str(exc))
    if target.is_file():
        return PreflightCheck("target_file", True, f"目标文件存在且在允许范围内: {config.file_path}")
    return PreflightCheck("target_file", False, f"目标文件不存在: {config.file_path}")


def _check_lsp_command(config: HealConfig) -> PreflightCheck:
    command = config.lsp.command[0] if config.lsp.command else ""
    if not command:
        return PreflightCheck("lsp_command", False, "LSP 命令为空。")
    if shutil.which(command):
        return PreflightCheck("lsp_command", True, f"LSP 命令可用: {command}")
    return PreflightCheck("lsp_command", False, f"找不到 LSP 命令: {command}")


def _check_openai_key() -> PreflightCheck:
    if os.environ.get("OPENAI_API_KEY"):
        return PreflightCheck("openai_api_key", True, "OPENAI_API_KEY 已配置。")
    return PreflightCheck("openai_api_key", False, "缺少 OPENAI_API_KEY，Healer 无法调用默认 LLM。")


def _check_sandbox(config: HealConfig, ping: Callable[[], bool] | None = None) -> PreflightCheck:
    backend = config.sandbox.backend.lower()
    if backend == "local":
        return PreflightCheck("sandbox", True, "使用 local 沙盒后端，不需要 Docker daemon。")
    if ping is not None:
        ok = ping()
        if ok:
            return PreflightCheck("sandbox", True, "Docker ping 已执行。")
        if backend == "auto":
            return PreflightCheck("sandbox", True, "Docker 不可用，auto 模式将降级到 local 沙盒。")
        return PreflightCheck("sandbox", False, "Docker ping 失败，且当前配置要求 docker 后端。")
    docker_ok, docker_message = docker_daemon_available()
    if docker_ok:
        return PreflightCheck("sandbox", True, docker_message)
    if backend == "auto":
        return PreflightCheck("sandbox", True, f"{docker_message}；auto 模式将降级到 local 沙盒。")
    if backend == "docker":
        return PreflightCheck("sandbox", False, docker_message)
    return PreflightCheck("sandbox", False, f"未知 sandbox backend: {config.sandbox.backend}")


def run_preflight(config: HealConfig, docker_ping: Callable[[], bool] | None = None) -> PreflightReport:
    checks = [
        _check_project_root(config),
        _check_target_file(config),
        _check_lsp_command(config),
        _check_sandbox(config, docker_ping),
        _check_openai_key(),
    ]
    return PreflightReport(ok=all(check.ok for check in checks), checks=checks)

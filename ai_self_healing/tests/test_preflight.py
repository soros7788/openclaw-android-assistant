from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from self_healing.config import HealConfig, LSPConfig, SandboxConfig
from self_healing.preflight import run_preflight


def _config(root: Path, *, command: list[str] | None = None, file_path: str = "metrics.py") -> HealConfig:
    return HealConfig(
        project_root=root,
        file_path=file_path,
        test_command=["python", "-m", "pytest", "-q"],
        max_iterations=2,
        allowed_paths=["metrics.py"],
        lsp=LSPConfig(command=command or ["python"], language_id="python"),
        sandbox=SandboxConfig(image="python:3.11-slim", timeout_seconds=30, workdir="/app"),
    )


class PreflightTests(unittest.TestCase):
    def test_preflight_passes_when_all_dependencies_are_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                report = run_preflight(_config(root), docker_ping=lambda: True)
            self.assertTrue(report.ok)
            self.assertTrue(all(check.ok for check in report.checks))

    def test_preflight_fails_without_openai_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                report = run_preflight(_config(root), docker_ping=lambda: True)
            self.assertFalse(report.ok)
            messages = [check.message for check in report.checks if check.name == "openai_api_key"]
            self.assertIn("缺少 OPENAI_API_KEY，Healer 无法调用默认 LLM。", messages)

    def test_preflight_fails_when_lsp_command_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                report = run_preflight(_config(root, command=["definitely-missing-lsp-command"]), docker_ping=lambda: True)
            self.assertFalse(report.ok)
            self.assertFalse(next(check.ok for check in report.checks if check.name == "lsp_command"))

    def test_preflight_rejects_disallowed_target_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "outside.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                report = run_preflight(_config(root, file_path="outside.py"), docker_ping=lambda: True)
            self.assertFalse(report.ok)
            self.assertFalse(next(check.ok for check in report.checks if check.name == "target_file"))

    def test_cli_preflight_only_outputs_json_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            config_path = root / "heal.json"
            config_path.write_text(
                json.dumps({
                    "project_root": str(root),
                    "file_path": "metrics.py",
                    "allowed_paths": ["metrics.py"],
                    "test_command": ["python", "-m", "pytest", "-q"],
                    "lsp": {"command": ["python"], "language_id": "python"},
                    "sandbox": {"image": "python:3.11-slim", "timeout_seconds": 30, "workdir": "/app"},
                }),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
                "self_healing.preflight._check_docker"
            ) as mock_docker:
                from self_healing.preflight import PreflightCheck
                mock_docker.return_value = PreflightCheck("docker", True, "Docker daemon 可访问。")
                from self_healing.cli import main
                with patch("sys.stdout", new_callable=StringIO) as stdout:
                    code = main(["--config", str(config_path), "--preflight-only"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()

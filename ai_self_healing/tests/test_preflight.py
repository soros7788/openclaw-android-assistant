from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from self_healing.config import HealConfig, HealerConfig, LSPConfig, SandboxConfig
from self_healing.preflight import run_preflight


def _config(
    root: Path,
    *,
    command: list[str] | None = None,
    file_path: str = "metrics.py",
    backend: str = "auto",
    healer_provider: str = "auto",
) -> HealConfig:
    return HealConfig(
        project_root=root,
        file_path=file_path,
        test_command=["python", "-m", "pytest", "-q"],
        max_iterations=2,
        allowed_paths=["metrics.py"],
        lsp=LSPConfig(command=command or ["python"], language_id="python"),
        sandbox=SandboxConfig(image="python:3.11-slim", timeout_seconds=30, workdir="/app", backend=backend),
        healer=HealerConfig(provider=healer_provider),
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

    def test_preflight_falls_back_to_echo_when_no_llm_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            env_without_keys = {k: v for k, v in os.environ.items() if k not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"}}
            with patch.dict(os.environ, env_without_keys, clear=True), patch(
                "self_healing.healer.factory.OllamaHealer.status"
            ) as mock_ollama:
                from self_healing.healer.factory import HealerProviderStatus
                mock_ollama.return_value = HealerProviderStatus("ollama", False, "Ollama 不可达。")
                report = run_preflight(_config(root), docker_ping=lambda: True)
            self.assertTrue(report.ok, msg=str(report.to_dict()))
            healer_check = next(check for check in report.checks if check.name == "healer")
            self.assertIn("echo 兜底", healer_check.message)

    def test_preflight_passes_when_explicit_provider_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                report = run_preflight(
                    _config(root, healer_provider="openai"),
                    docker_ping=lambda: True,
                )
            self.assertTrue(report.ok)
            healer_check = next(check for check in report.checks if check.name == "healer")
            self.assertIn("openai 可用", healer_check.message)

    def test_preflight_fails_when_explicit_provider_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                report = run_preflight(
                    _config(root, healer_provider="anthropic"),
                    docker_ping=lambda: True,
                )
            self.assertFalse(report.ok)
            healer_check = next(check for check in report.checks if check.name == "healer")
            self.assertFalse(healer_check.ok)

    def test_preflight_fails_when_lsp_command_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                report = run_preflight(_config(root, command=["definitely-missing-lsp-command"]), docker_ping=lambda: True)
            self.assertFalse(report.ok)
            self.assertFalse(next(check.ok for check in report.checks if check.name == "lsp_command"))

    def test_auto_backend_passes_when_docker_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                report = run_preflight(_config(root, backend="auto"), docker_ping=lambda: False)
            self.assertTrue(report.ok)
            sandbox_check = next(check for check in report.checks if check.name == "sandbox")
            self.assertIn("降级到 local 沙盒", sandbox_check.message)

    def test_docker_backend_fails_when_docker_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metrics.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                report = run_preflight(_config(root, backend="docker"), docker_ping=lambda: False)
            self.assertFalse(report.ok)
            self.assertFalse(next(check.ok for check in report.checks if check.name == "sandbox"))

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
                    "sandbox": {"image": "python:3.11-slim", "timeout_seconds": 30, "workdir": "/app", "backend": "auto"},
                }),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
                "self_healing.preflight._check_sandbox"
            ) as mock_sandbox:
                from self_healing.preflight import PreflightCheck
                mock_sandbox.return_value = PreflightCheck("sandbox", True, "Docker daemon 可访问。")
                from self_healing.cli import main
                with patch("sys.stdout", new_callable=StringIO) as stdout:
                    code = main(["preflight", "--config", str(config_path)])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()

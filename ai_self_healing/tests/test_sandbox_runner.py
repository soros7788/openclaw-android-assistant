from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from self_healing.config import SandboxConfig
from self_healing.sandbox.local_runner import LocalSandbox
from self_healing.sandbox.runner import create_sandbox


class SandboxRunnerTests(unittest.TestCase):
    def test_auto_backend_falls_back_to_local_when_docker_unavailable(self):
        with patch("self_healing.sandbox.runner.docker_daemon_available", return_value=(False, "no docker")):
            sandbox = create_sandbox(SandboxConfig(backend="auto"))
        self.assertIsInstance(sandbox, LocalSandbox)

    def test_local_sandbox_runs_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalSandbox(timeout_seconds=5).run(Path(tmp), ["python", "-c", "print('ok')"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.logs.strip(), "ok")

    def test_local_sandbox_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalSandbox(timeout_seconds=5).run(Path(tmp), ["python", "-c", "raise RuntimeError('boom')"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("RuntimeError", result.logs)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import pathlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from self_healing.config import HealConfig, LSPConfig, SandboxConfig
from self_healing.state import AgentState


def _build_config() -> HealConfig:
    return HealConfig(
        project_root="/tmp/test_project",
        file_path="metrics.py",
        test_command=["pytest", "-q"],
        max_iterations=3,
        allowed_paths=["metrics.py"],
        lsp=LSPConfig(command=["pyright-langserver", "--stdio"], language_id="python"),
        sandbox=SandboxConfig(image="python:3.11-slim", timeout_seconds=30, workdir="/app"),
    )


def _initial_state() -> AgentState:
    return {
        "project_root": "/tmp/test_project",
        "file_path": "metrics.py",
        "test_command": ["pytest", "-q"],
        "current_code": "result = undefined_variable + 10\n",
        "lsp_diagnostics": [],
        "exec_logs": "",
        "exit_code": -1,
        "iterations": 0,
        "max_iterations": 3,
        "is_fixed": False,
        "attempts": [],
        "allowed_paths": ["metrics.py"],
    }


class TestEndToEndGraph闭环(unittest.TestCase):
    """端到端验证 LangGraph 状态机的闭环流转"""

    def test_fuse_broken_lsp_and_sandbox_then_heal_until_max_iterations(self):
        mock_diagnostics = [
            {
                "severity": "Error",
                "message": "NameError: name 'undefined_variable' is not defined",
                "range": {},
            }
        ]
        mock_result = MagicMock()
        mock_result.exit_code = 1
        mock_result.logs = "FAILED test_metrics.py::test_calculate_metrics - AssertionError"

        # 关键：临时目录必须在 app.invoke 期间保持存活
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = pathlib.Path(tmpdir)

            with patch(
                "self_healing.graph.StdioLSPClient"
            ) as mock_lsp_cls, patch(
                "self_healing.graph.DockerSandbox"
            ) as mock_docker_cls, patch(
                "self_healing.graph.LLMHealer"
            ) as mock_healer_cls, patch(
                "self_healing.patching.apply.resolve_safe_path"
            ) as mock_resolve:

                mock_lsp_instance = MagicMock()
                mock_lsp_instance.diagnostics_for.return_value = mock_diagnostics
                mock_lsp_cls.return_value.__enter__.return_value = mock_lsp_instance

                mock_docker_instance = MagicMock()
                mock_docker_instance.run.return_value = mock_result
                mock_docker_cls.return_value = mock_docker_instance

                call_count = [0]

                def fake_repair(state: AgentState) -> str:
                    call_count[0] += 1
                    if call_count[0] < 3:
                        return "result = another_undefined + 10\n"
                    return "def calculate(x): return x + 1\n"

                mock_healer_instance = MagicMock()
                mock_healer_instance.repair.side_effect = fake_repair
                mock_healer_cls.return_value = mock_healer_instance

                # 真实 Path，指向存活中的临时目录
                fake_path = fake_dir / "metrics.py"
                mock_resolve.return_value = fake_path

                from self_healing.graph import build_graph, route_after_verification

                config = _build_config()
                app = build_graph(config)
                initial = _initial_state()

                final = app.invoke(initial)

                self.assertIn("current_code", final)
                self.assertIsInstance(final["attempts"], list)
                self.assertEqual(final["iterations"], 3)
                self.assertEqual(len(final["attempts"]), 3)

                end_state = {**final, "is_fixed": False, "iterations": final["max_iterations"]}
                self.assertEqual(route_after_verification(end_state), "__end__")

    def test_success_path_ends_immediately(self):
        mock_diagnostics: list = []
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.logs = "1 passed in 0.10s"

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = pathlib.Path(tmpdir)

            with patch(
                "self_healing.graph.StdioLSPClient"
            ) as mock_lsp_cls, patch(
                "self_healing.graph.DockerSandbox"
            ) as mock_docker_cls, patch(
                "self_healing.patching.apply.resolve_safe_path"
            ) as mock_resolve:

                mock_lsp_instance = MagicMock()
                mock_lsp_instance.diagnostics_for.return_value = mock_diagnostics
                mock_lsp_cls.return_value.__enter__.return_value = mock_lsp_instance

                mock_docker_instance = MagicMock()
                mock_docker_instance.run.return_value = mock_result
                mock_docker_cls.return_value = mock_docker_instance

                fake_path = fake_dir / "metrics.py"
                mock_resolve.return_value = fake_path

                from self_healing.graph import build_graph, route_after_verification

                config = _build_config()
                app = build_graph(config)
                initial = _initial_state()
                final = app.invoke(initial)

                self.assertEqual(final["exit_code"], 0)
                self.assertTrue(final["is_fixed"])
                self.assertEqual(route_after_verification(final), "__end__")

    def test_is_fixed_reset_on_failure_paths(self):
        from self_healing.graph import docker_sandbox_node

        config = _build_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = pathlib.Path(tmpdir)
            fake_path = fake_dir / "metrics.py"

            # 场景1：LSP 返回 Error，docker_sandbox_node 必须返回 is_fixed=False
            lsp_state: AgentState = {
                **_initial_state(),
                "lsp_diagnostics": [
                    {"severity": "Error", "message": "Syntax error", "range": {}}
                ],
            }
            result = docker_sandbox_node(lsp_state, config)
            self.assertFalse(result["is_fixed"])

            # 场景2：LSP 无错误但 Docker 失败，也必须 is_fixed=False
            clean_lsp_state: AgentState = {
                **_initial_state(),
                "lsp_diagnostics": [],
                "exec_logs": "Test failed",
                "exit_code": 1,
            }
            mock_result = MagicMock()
            mock_result.exit_code = 1
            mock_result.logs = "FAILED"
            with patch(
                "self_healing.graph.DockerSandbox"
            ) as mock_docker_cls, patch(
                "self_healing.patching.apply.resolve_safe_path"
            ) as mock_resolve:
                mock_docker_instance = MagicMock()
                mock_docker_instance.run.return_value = mock_result
                mock_docker_cls.return_value = mock_docker_instance
                mock_resolve.return_value = fake_path
                result2 = docker_sandbox_node(clean_lsp_state, config)
            self.assertFalse(result2["is_fixed"])

    def test_healer_increments_iteration(self):
        from self_healing.graph import healer_node

        state: AgentState = {
            **_initial_state(),
            "iterations": 1,
            "lsp_diagnostics": [
                {"severity": "Error", "message": "undefined", "range": {}}
            ],
            "exit_code": 1,
            "exec_logs": "Test failed",
            "attempts": [],
            "is_fixed": False,
        }

        with patch("self_healing.graph.LLMHealer") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.repair.return_value = "fixed_code = 42\n"
            mock_cls.return_value = mock_instance

            result = healer_node(state)

        self.assertEqual(result["iterations"], 2)
        self.assertFalse(result["is_fixed"])
        self.assertIsInstance(result["attempts"], list)
        self.assertEqual(len(result["attempts"]), 1)


if __name__ == "__main__":
    unittest.main()

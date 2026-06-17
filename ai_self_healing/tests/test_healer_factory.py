from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from self_healing.config import HealerConfig
from self_healing.healer.factory import (
    AUTO_ORDER,
    EchoHealer,
    GeminiHealer,
    HealerProviderStatus,
    OllamaHealer,
    OpenAIHealer,
    create_healer,
    detect_provider_statuses,
    resolve_provider,
)
from self_healing.state import AgentState


def _state() -> AgentState:
    return {
        "project_root": "/tmp",
        "file_path": "metrics.py",
        "test_command": ["pytest"],
        "current_code": "x = 1\n",
        "lsp_diagnostics": [
            {"severity": "Error", "message": "demo error", "range": {}}
        ],
        "exec_logs": "stack trace",
        "exit_code": 1,
        "iterations": 0,
        "max_iterations": 3,
        "is_fixed": False,
        "attempts": [],
        "allowed_paths": ["metrics.py"],
    }


class HealerFactoryTests(unittest.TestCase):
    def test_auto_order_lists_all_providers(self):
        self.assertEqual(AUTO_ORDER, ("openai", "anthropic", "gemini", "ollama", "echo"))

    def test_resolve_provider_picks_openai_when_key_available(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            with patch.object(
                OllamaHealer,
                "status",
                return_value=HealerProviderStatus("ollama", False, "n/a"),
            ):
                provider, statuses = resolve_provider(HealerConfig(provider="auto"))
        self.assertEqual(provider, "openai")
        self.assertTrue(any(s.name == "openai" and s.ok for s in statuses))

    def test_resolve_provider_falls_back_to_echo_when_nothing_available(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                OllamaHealer,
                "status",
                return_value=HealerProviderStatus("ollama", False, "n/a"),
            ):
                provider, _ = resolve_provider(HealerConfig(provider="auto"))
        self.assertEqual(provider, "echo")

    def test_explicit_provider_is_respected(self):
        with patch.dict(os.environ, {}, clear=True):
            provider, _ = resolve_provider(HealerConfig(provider="echo"))
        self.assertEqual(provider, "echo")

    def test_create_healer_returns_echo_when_no_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                OllamaHealer,
                "status",
                return_value=HealerProviderStatus("ollama", False, "n/a"),
            ):
                healer = create_healer(HealerConfig(provider="auto"))
        self.assertIsInstance(healer, EchoHealer)

    def test_create_healer_returns_openai_when_key_present(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            with patch.object(
                OllamaHealer,
                "status",
                return_value=HealerProviderStatus("ollama", False, "n/a"),
            ):
                healer = create_healer(HealerConfig(provider="auto"))
        self.assertIsInstance(healer, OpenAIHealer)

    def test_echo_healer_repair_appends_diagnostic_header(self):
        repaired = EchoHealer().repair(_state())
        self.assertIn("AI 自愈兜底", repaired)
        self.assertIn("LSP 诊断数: 1", repaired)
        self.assertIn("退出码: 1", repaired)
        self.assertTrue(repaired.endswith("x = 1\n"))

    def test_detect_provider_statuses_returns_all_known_providers(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                OllamaHealer,
                "status",
                return_value=HealerProviderStatus("ollama", False, "n/a"),
            ):
                with patch.object(
                    GeminiHealer,
                    "status",
                    return_value=HealerProviderStatus("gemini", False, "n/a"),
                ):
                    statuses = detect_provider_statuses(HealerConfig(provider="auto"))
        names = {s.name for s in statuses}
        self.assertEqual(names, {"openai", "anthropic", "gemini", "ollama", "echo"})


if __name__ == "__main__":
    unittest.main()

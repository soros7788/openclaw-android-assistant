from __future__ import annotations

"""Healer LLM 后端工厂，支持 OpenAI / Anthropic / Gemini / Ollama / Echo。

设计目标：
- 不再硬绑 OPENAI_API_KEY；任一后端可用即可完成自愈。
- 在没有任何外部 LLM 的环境，使用 EchoHealer 作为可调试的最小实现。
"""

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from self_healing.config import HealerConfig
from self_healing.healer.output_parser import clean_model_code_output
from self_healing.healer.prompts import SYSTEM_PROMPT, USER_PROMPT
from self_healing.state import AgentState


def _format_user_prompt(state: AgentState) -> str:
    return USER_PROMPT.format(
        file_path=state["file_path"],
        current_code=state["current_code"],
        lsp_diagnostics=json.dumps(state["lsp_diagnostics"], ensure_ascii=False, indent=2),
        exec_logs=state["exec_logs"],
    )


@dataclass(frozen=True)
class HealerProviderStatus:
    name: str
    ok: bool
    message: str


class BaseHealer:
    """Healer 后端公共接口。"""

    name = "base"

    def repair(self, state: AgentState) -> str:  # pragma: no cover - 抽象
        raise NotImplementedError

    @classmethod
    def status(cls, config: HealerConfig) -> HealerProviderStatus:  # pragma: no cover - 抽象
        raise NotImplementedError


class EchoHealer(BaseHealer):
    """无需外部依赖的兜底 healer：在原代码顶部添加自愈注释。

    用于本地调试与离线演示，确保闭环可以走通。
    """

    name = "echo"

    def repair(self, state: AgentState) -> str:
        diag_count = len(state.get("lsp_diagnostics", []))
        header = (
            "# AI 自愈兜底 (echo provider)：未配置真实 LLM，仅记录诊断信息以便人工修复。\n"
            f"# LSP 诊断数: {diag_count}\n"
            f"# 退出码: {state.get('exit_code')}\n"
        )
        return header + state["current_code"]

    @classmethod
    def status(cls, config: HealerConfig) -> HealerProviderStatus:
        return HealerProviderStatus("echo", True, "Echo 后端始终可用（仅做占位修复）。")


class OpenAIHealer(BaseHealer):
    name = "openai"

    def __init__(self, config: HealerConfig) -> None:
        self.config = config

    def repair(self, state: AgentState) -> str:
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - 依赖问题
            raise RuntimeError("OpenAI Healer 需要安装 langchain-openai 与 langchain-core。") from exc

        kwargs = {"model": self.config.model, "temperature": self.config.temperature}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("user", USER_PROMPT)]
        )
        chain = prompt | ChatOpenAI(**kwargs)
        response = chain.invoke({
            "file_path": state["file_path"],
            "current_code": state["current_code"],
            "lsp_diagnostics": json.dumps(state["lsp_diagnostics"], ensure_ascii=False, indent=2),
            "exec_logs": state["exec_logs"],
        })
        return clean_model_code_output(response.content)

    @classmethod
    def status(cls, config: HealerConfig) -> HealerProviderStatus:
        env_name = config.api_key_env or "OPENAI_API_KEY"
        if os.environ.get(env_name):
            return HealerProviderStatus("openai", True, f"{env_name} 已配置。")
        return HealerProviderStatus("openai", False, f"缺少环境变量 {env_name}。")


class AnthropicHealer(BaseHealer):
    name = "anthropic"

    def __init__(self, config: HealerConfig) -> None:
        self.config = config

    def repair(self, state: AgentState) -> str:  # pragma: no cover - 真实调用
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError as exc:
            raise RuntimeError("Anthropic Healer 需要安装 langchain-anthropic。") from exc
        prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("user", USER_PROMPT)]
        )
        chain = prompt | ChatAnthropic(model=self.config.model, temperature=self.config.temperature)
        response = chain.invoke({
            "file_path": state["file_path"],
            "current_code": state["current_code"],
            "lsp_diagnostics": json.dumps(state["lsp_diagnostics"], ensure_ascii=False, indent=2),
            "exec_logs": state["exec_logs"],
        })
        return clean_model_code_output(response.content)

    @classmethod
    def status(cls, config: HealerConfig) -> HealerProviderStatus:
        env_name = config.api_key_env or "ANTHROPIC_API_KEY"
        if os.environ.get(env_name):
            return HealerProviderStatus("anthropic", True, f"{env_name} 已配置。")
        return HealerProviderStatus("anthropic", False, f"缺少环境变量 {env_name}。")


class OllamaHealer(BaseHealer):
    """通过本地 Ollama HTTP API 调用本地模型，无需 API Key。"""

    name = "ollama"

    def __init__(self, config: HealerConfig) -> None:
        self.config = config
        self.endpoint = (config.base_url or "http://localhost:11434").rstrip("/")

    def repair(self, state: AgentState) -> str:  # pragma: no cover - 真实调用
        url = f"{self.endpoint}/api/generate"
        payload = {
            "model": self.config.model,
            "prompt": SYSTEM_PROMPT + "\n\n" + _format_user_prompt(state),
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return clean_model_code_output(body.get("response", ""))

    @classmethod
    def status(cls, config: HealerConfig) -> HealerProviderStatus:
        endpoint = (config.base_url or "http://localhost:11434").rstrip("/")
        try:
            with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return HealerProviderStatus("ollama", True, f"Ollama 服务可用: {endpoint}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return HealerProviderStatus("ollama", False, f"Ollama 不可达 ({endpoint}): {exc}")
        return HealerProviderStatus("ollama", False, f"Ollama 状态码异常: {endpoint}")


class GeminiHealer(BaseHealer):
    """通过 Google Gemini REST API 调用 Gemini 模型。

    使用 GOOGLE_API_KEY 环境变量（或通过 api_key_env 配置自定义变量名）。
    模型默认为 gemini-2.0-flash，性价比最高且代码能力强。
    """

    name = "gemini"

    def __init__(self, config: HealerConfig) -> None:
        self.config = config
        self._api_key = os.environ.get(config.api_key_env or "GOOGLE_API_KEY", "")
        self._model = self.config.model or "gemini-2.0-flash"

    def repair(self, state: AgentState) -> str:  # pragma: no cover - 真实调用
        if not self._api_key:
            raise RuntimeError("GeminiHealer 需要 GOOGLE_API_KEY 环境变量。")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}"
            f":generateContent?key={self._api_key}"
        )
        payload = {
            "contents": [{
                "parts": [{
                    "text": SYSTEM_PROMPT + "\n\n" + _format_user_prompt(state)
                }]
            }],
            "generationConfig": {
                "temperature": self.config.temperature,
                "candidateCount": 1,
            },
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        candidates = body.get("candidates", [])
        if not candidates:
            error_msg = body.get("error", {}).get("message", "未知错误")
            raise RuntimeError(f"Gemini API 返回错误: {error_msg}")

        parts = candidates[0].get("content", {}).get("parts", [])
        return clean_model_code_output("".join(p.get("text", "") for p in parts))

    @classmethod
    def status(cls, config: HealerConfig) -> HealerProviderStatus:
        env_name = config.api_key_env or "GOOGLE_API_KEY"
        if os.environ.get(env_name):
            model = config.model or "gemini-2.0-flash"
            return HealerProviderStatus("gemini", True, f"{env_name} 已配置，使用模型 {model}。")
        return HealerProviderStatus("gemini", False, f"缺少环境变量 {env_name}。")


PROVIDERS: dict[str, type[BaseHealer]] = {
    "openai": OpenAIHealer,
    "anthropic": AnthropicHealer,
    "gemini": GeminiHealer,
    "ollama": OllamaHealer,
    "echo": EchoHealer,
}

# auto 模式按优先级选择第一个可用的后端
AUTO_ORDER = ("openai", "anthropic", "gemini", "ollama", "echo")


def detect_provider_statuses(config: HealerConfig) -> list[HealerProviderStatus]:
    """返回所有候选后端的可用性，便于预检与诊断。"""
    return [PROVIDERS[name].status(config) for name in AUTO_ORDER]


def resolve_provider(config: HealerConfig) -> tuple[str, list[HealerProviderStatus]]:
    """根据配置解析最终使用的 provider 名称。"""
    statuses = detect_provider_statuses(config)
    requested = config.provider.lower()
    if requested in PROVIDERS and requested != "auto":
        return requested, statuses
    for status in statuses:
        if status.ok:
            return status.name, statuses
    # 兜底：echo 总是可用，不应到达这里
    return "echo", statuses


def create_healer(config: HealerConfig) -> BaseHealer:
    provider, _ = resolve_provider(config)
    cls = PROVIDERS[provider]
    if cls is EchoHealer:
        return EchoHealer()
    return cls(config)

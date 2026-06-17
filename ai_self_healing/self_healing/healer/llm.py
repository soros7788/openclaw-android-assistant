from __future__ import annotations

import json

from self_healing.healer.output_parser import clean_model_code_output
from self_healing.healer.prompts import SYSTEM_PROMPT, USER_PROMPT
from self_healing.state import AgentState


class LLMHealer:
    def __init__(self, model: str = "gpt-4o", temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature

    def repair(self, state: AgentState) -> str:
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Healer 需要安装 langchain-openai 和 langchain-core。") from exc

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", USER_PROMPT),
        ])
        chain = prompt | ChatOpenAI(model=self.model, temperature=self.temperature)
        response = chain.invoke({
            "file_path": state["file_path"],
            "current_code": state["current_code"],
            "lsp_diagnostics": json.dumps(state["lsp_diagnostics"], ensure_ascii=False, indent=2),
            "exec_logs": state["exec_logs"],
        })
        return clean_model_code_output(response.content)

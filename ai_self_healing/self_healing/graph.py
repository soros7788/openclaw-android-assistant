from __future__ import annotations

from self_healing.config import HealConfig
from self_healing.healer.factory import create_healer
from self_healing.lsp.client import StdioLSPClient
from self_healing.patching.apply import write_target
from self_healing.sandbox.runner import create_sandbox
from self_healing.state import AgentState


def lsp_analysis_node(state: AgentState, config: HealConfig) -> dict:
    target = write_target(state["project_root"], state["file_path"], state["current_code"], state["allowed_paths"])
    try:
        with StdioLSPClient(config.lsp.command, config.project_root, config.lsp.language_id) as client:
            uri = client.open_document(target, state["current_code"])
            diagnostics = client.diagnostics_for(uri)
    except Exception as exc:
        diagnostics = [{"severity": "Warning", "message": f"LSP unavailable: {exc}", "range": {}}]
    return {"lsp_diagnostics": diagnostics, "is_fixed": False}


def docker_sandbox_node(state: AgentState, config: HealConfig) -> dict:
    if any(d["severity"] == "Error" for d in state["lsp_diagnostics"]):
        return {
            "exit_code": 1,
            "exec_logs": "Skipped dynamic execution due to LSP errors.",
            "is_fixed": False,
        }
    result = create_sandbox(config.sandbox).run(state["project_root"], state["test_command"])
    return {"exit_code": result.exit_code, "exec_logs": result.logs, "is_fixed": result.exit_code == 0}


def healer_node(state: AgentState, config: HealConfig | None = None) -> dict:
    attempts = list(state.get("attempts", []))
    attempts.append({
        "iteration": state["iterations"] + 1,
        "lsp_error_count": sum(1 for d in state["lsp_diagnostics"] if d["severity"] == "Error"),
        "exit_code": state["exit_code"],
        "log_excerpt": state["exec_logs"][:1000],
    })
    healer = create_healer(config.healer) if config is not None else create_healer(_default_healer_config())
    repaired = healer.repair(state)
    return {"current_code": repaired, "iterations": state["iterations"] + 1, "attempts": attempts, "is_fixed": False}


def _default_healer_config():
    from self_healing.config import HealerConfig

    return HealerConfig()


def route_after_verification(state: AgentState):
    try:
        from langgraph.graph import END
    except ImportError:
        END = "__end__"
    if state["is_fixed"] and state["exit_code"] == 0:
        return END
    if state["iterations"] >= state["max_iterations"]:
        return END
    return "healer"


def build_graph(config: HealConfig):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise RuntimeError("运行状态机需要安装 langgraph。") from exc

    workflow = StateGraph(AgentState)
    workflow.add_node("lsp_analyzer", lambda state: lsp_analysis_node(state, config))
    workflow.add_node("docker_sandbox", lambda state: docker_sandbox_node(state, config))
    workflow.add_node("healer", lambda state: healer_node(state, config))
    workflow.set_entry_point("lsp_analyzer")
    workflow.add_edge("lsp_analyzer", "docker_sandbox")
    workflow.add_conditional_edges("docker_sandbox", route_after_verification, {END: END, "healer": "healer"})
    workflow.add_edge("healer", "lsp_analyzer")
    return workflow.compile()

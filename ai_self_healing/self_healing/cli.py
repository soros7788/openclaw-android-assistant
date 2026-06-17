from __future__ import annotations

import argparse
import json
from pathlib import Path

from self_healing.config import load_config
from self_healing.graph import build_graph
from self_healing.patching.apply import read_target, write_target
from self_healing.state import AgentState


def make_initial_state(config_path: str) -> tuple[AgentState, object]:
    config = load_config(config_path)
    code = read_target(config.project_root, config.file_path, config.allowed_paths)
    state: AgentState = {
        "project_root": str(config.project_root),
        "file_path": config.file_path,
        "test_command": config.test_command,
        "current_code": code,
        "lsp_diagnostics": [],
        "exec_logs": "",
        "exit_code": -1,
        "iterations": 0,
        "max_iterations": config.max_iterations,
        "is_fixed": False,
        "attempts": [],
        "allowed_paths": config.allowed_paths,
    }
    return state, config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行 LangGraph + LSP + Docker AI 编码自愈流程。")
    parser.add_argument("--config", required=True, help="JSON/YAML 配置文件路径。")
    parser.add_argument("--report", default="", help="可选：写入最终 JSON 报告。")
    args = parser.parse_args(argv)

    state, config = make_initial_state(args.config)
    app = build_graph(config)
    final_state = app.invoke(state)
    if final_state.get("is_fixed"):
        write_target(config.project_root, config.file_path, final_state["current_code"], config.allowed_paths)

    report = {
        "is_fixed": final_state.get("is_fixed", False),
        "iterations": final_state.get("iterations", 0),
        "exit_code": final_state.get("exit_code", -1),
        "lsp_diagnostics": final_state.get("lsp_diagnostics", []),
        "exec_logs": final_state.get("exec_logs", ""),
        "attempts": final_state.get("attempts", []),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["is_fixed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

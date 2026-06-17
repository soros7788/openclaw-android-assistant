from __future__ import annotations

"""CLI 入口：

    python -m self_healing.cli once --config examples/example.yaml
    python -m self_healing.cli daemon --config examples/example.yaml
    python -m self_healing.cli stop --config examples/example.yaml
    python -m self_healing.cli status --config examples/example.yaml
    python -m self_healing.cli preflight --config examples/example.yaml
    python -m self_healing.cli run --config examples/example.yaml   # 旧模式，等价 once + preflight
"""

import argparse
import json
from pathlib import Path

from self_healing.config import load_config
from self_healing.daemon import (
    print_status,
    run_daemon,
    run_once,
    stop_daemon,
)
from self_healing.graph import build_graph
from self_healing.patching.apply import read_target, write_target
from self_healing.preflight import run_preflight
from self_healing.state import AgentState


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------

def _make_initial_state(config_path: str) -> tuple[AgentState, object]:
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


def cmd_once(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    return run_once(config)


def cmd_daemon(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if not args.skip_preflight:
        preflight = run_preflight(config)
        if not preflight.ok:
            print(json.dumps(preflight.to_dict(), ensure_ascii=False, indent=2))
            print("[daemon] preflight has failures; proceeding with fallback backend.")
    return run_daemon(config)


def cmd_stop(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    return stop_daemon(config)


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    return print_status(config)


def cmd_preflight(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    preflight = run_preflight(config)
    print(json.dumps(preflight.to_dict(), ensure_ascii=False, indent=2))
    return 0 if preflight.ok else 2


def cmd_run(args: argparse.Namespace) -> int:
    """保留旧行为：预检 → 自愈 → 落盘 → 打印 JSON 报告。"""
    config = load_config(args.config)
    if not args.skip_preflight:
        preflight = run_preflight(config)
        if not preflight.ok and not args.preflight_only:
            print(json.dumps(preflight.to_dict(), ensure_ascii=False, indent=2))
            return 2
        if args.preflight_only:
            print(json.dumps(preflight.to_dict(), ensure_ascii=False, indent=2))
            return 0 if preflight.ok else 2

    state, config = _make_initial_state(args.config)
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


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="self-heal",
        description="LangGraph + LSP + Docker 编码自愈系统。",
    )
    sub = parser.add_subparsers(dest="command", required=True, help="子命令")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", required=True, help="JSON/YAML 配置文件路径。")

    p_run = sub.add_parser("run", parents=[common], help="一次完整的自检+自愈（旧行为）。")
    p_run.add_argument("--report", default="", help="可选：写入最终 JSON 报告。")
    p_run.add_argument("--preflight-only", action="store_true", help="只执行运行前预检。")
    p_run.add_argument("--skip-preflight", action="store_true", help="跳过预检。")

    sub.add_parser("once", parents=[common], help="执行一次自愈循环，忽略时间间隔。")

    p_daemon = sub.add_parser("daemon", parents=[common], help="常驻守护：监听文件变动自动自愈。")
    p_daemon.add_argument("--skip-preflight", action="store_true", help="跳过启动时预检。")

    sub.add_parser("stop", parents=[common], help="停止正在运行的 daemon。")
    sub.add_parser("status", parents=[common], help="查看 daemon 的运行状态与最近事件。")
    sub.add_parser("preflight", parents=[common], help="只运行预检，不执行自愈。")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "run": cmd_run,
        "once": cmd_once,
        "daemon": cmd_daemon,
        "stop": cmd_stop,
        "status": cmd_status,
        "preflight": cmd_preflight,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

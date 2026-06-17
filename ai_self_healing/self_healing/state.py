from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


Severity = Literal["Error", "Warning", "Information", "Hint"]


class LSPDiagnostic(TypedDict):
    severity: Severity
    message: str
    range: dict[str, Any]
    source: NotRequired[str]
    code: NotRequired[str]


class RepairAttempt(TypedDict):
    iteration: int
    lsp_error_count: int
    exit_code: int
    log_excerpt: str


class AgentState(TypedDict):
    project_root: str
    file_path: str
    test_command: list[str]
    current_code: str
    lsp_diagnostics: list[LSPDiagnostic]
    exec_logs: str
    exit_code: int
    iterations: int
    max_iterations: int
    is_fixed: bool
    attempts: list[RepairAttempt]
    allowed_paths: list[str]

from __future__ import annotations

from typing import Any

from self_healing.state import LSPDiagnostic

SEVERITY_MAP = {
    1: "Error",
    2: "Warning",
    3: "Information",
    4: "Hint",
}


def normalize_diagnostic(item: dict[str, Any]) -> LSPDiagnostic:
    severity = SEVERITY_MAP.get(item.get("severity", 2), "Warning")
    diagnostic: LSPDiagnostic = {
        "severity": severity,  # type: ignore[typeddict-item]
        "message": str(item.get("message", "")),
        "range": dict(item.get("range", {})),
    }
    if "source" in item:
        diagnostic["source"] = str(item["source"])
    if "code" in item:
        diagnostic["code"] = str(item["code"])
    return diagnostic

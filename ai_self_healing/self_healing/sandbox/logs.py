from __future__ import annotations

import re

ERROR_PATTERNS = re.compile(
    r"(AssertionError|Traceback|Exception|Error:|FAILED|File \".+\", line \d+|\.py:\d+|\.ts:\d+|\.go:\d+)",
    re.IGNORECASE,
)


def filter_relevant_logs(logs: str, context_lines: int = 8, max_chars: int = 6000) -> str:
    lines = logs.splitlines()
    if not lines:
        return ""
    matched: set[int] = set()
    for idx, line in enumerate(lines):
        if ERROR_PATTERNS.search(line):
            start = max(0, idx - context_lines)
            end = min(len(lines), idx + context_lines + 1)
            matched.update(range(start, end))
    selected = [lines[i] for i in sorted(matched)] if matched else lines[-min(len(lines), 80):]
    excerpt = "\n".join(selected)
    if len(excerpt) > max_chars:
        return excerpt[: max_chars - 120] + "\n...[日志已截断]...\n" + excerpt[-100:]
    return excerpt

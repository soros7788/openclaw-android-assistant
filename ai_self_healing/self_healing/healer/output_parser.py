from __future__ import annotations

import re

FENCE_RE = re.compile(r"^\s*```(?:[a-zA-Z0-9_+-]+)?\s*\n(?P<body>.*)\n```\s*$", re.DOTALL)


def clean_model_code_output(text: str) -> str:
    stripped = text.strip()
    match = FENCE_RE.match(stripped)
    if match:
        return match.group("body").strip() + "\n"
    return stripped + ("\n" if stripped else "")

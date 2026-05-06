#!/usr/bin/env python3
"""Reference implementation for plan-rev/v1."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REVIEW_LEDGER_BLOCK = re.compile(
    r"<!-- REVIEW-LEDGER:START -->.*?<!-- REVIEW-LEDGER:END -->",
    re.DOTALL,
)
EXECUTION_STATE_BLOCK = re.compile(
    r"<!-- EXECUTION-STATE:START -->.*?<!-- EXECUTION-STATE:END -->",
    re.DOTALL,
)
CHECKBOX = re.compile(r"\[(?:x|X| )\]")


def normalize_plan_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = REVIEW_LEDGER_BLOCK.sub("", text)
    text = EXECUTION_STATE_BLOCK.sub("", text)
    text = CHECKBOX.sub("[ ]", text)

    lines = [line.rstrip() for line in text.split("\n")]

    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    normalized = "\n".join(lines)
    return normalized + "\n"


def compute_plan_rev(path: Path) -> str:
    normalized = normalize_plan_text(path.read_text())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: compute_plan_rev.py <canonical-plan-path>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    print(compute_plan_rev(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

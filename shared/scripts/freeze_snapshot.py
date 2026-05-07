#!/usr/bin/env python3
"""Freeze canonical spec/plan snapshots for plan-review-implement-loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PLAN_REV_CONTRACT_ID = "plan-rev/v1"

REVIEW_LEDGER_BLOCK = re.compile(
    r"<!-- REVIEW-LEDGER:START -->.*?<!-- REVIEW-LEDGER:END -->",
    re.DOTALL,
)
EXECUTION_STATE_BLOCK = re.compile(
    r"<!-- EXECUTION-STATE:START -->.*?<!-- EXECUTION-STATE:END -->",
    re.DOTALL,
)
CHECKBOX = re.compile(r"\[(?:x|X| )\]")


class SnapshotError(ValueError):
    pass


def _sha256(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def normalize_plan_text(text: str, *, require_blocks: bool = False) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if require_blocks:
        if not REVIEW_LEDGER_BLOCK.search(text):
            raise SnapshotError("missing REVIEW-LEDGER block")
        if not EXECUTION_STATE_BLOCK.search(text):
            raise SnapshotError("missing EXECUTION-STATE block")

    text = REVIEW_LEDGER_BLOCK.sub("", text)
    text = EXECUTION_STATE_BLOCK.sub("", text)
    text = CHECKBOX.sub("[ ]", text)
    return normalize_text(text)


def compute_spec_rev(path: Path) -> str:
    return _sha256(normalize_text(path.read_text(encoding="utf-8")))


def compute_plan_rev(path: Path, *, require_blocks: bool = False) -> str:
    return _sha256(normalize_plan_text(path.read_text(encoding="utf-8"), require_blocks=require_blocks))


def freeze_snapshot(spec_path: Path, plan_path: Path) -> dict[str, object]:
    return {
        "spec_rev": compute_spec_rev(spec_path),
        "plan_rev": compute_plan_rev(plan_path, require_blocks=True),
        "plan_rev_contract_id": PLAN_REV_CONTRACT_ID,
        "excluded_blocks": ["Review Ledger", "Execution State"],
        "checkbox_normalized": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        print(json.dumps(freeze_snapshot(args.spec, args.plan), ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        print(f"freeze_snapshot: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

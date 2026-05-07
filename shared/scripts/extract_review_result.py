#!/usr/bin/env python3
"""Extract the authoritative review-result-json block from reviewer output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BLOCK = re.compile(r"```review-result-json\s*\n(.*?)\n```", re.DOTALL)


def extract_review_result(text: str) -> dict[str, object]:
    matches = BLOCK.findall(text.replace("\r\n", "\n").replace("\r", "\n"))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one review-result-json block, found {len(matches)}")
    try:
        value = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid review-result-json: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("review-result-json must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="raw reviewer output file")
    args = parser.parse_args(argv)

    try:
        result = extract_review_result(args.input.read_text(encoding="utf-8"))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        print(f"extract_review_result: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

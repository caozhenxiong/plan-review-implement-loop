#!/usr/bin/env python3
"""Compatibility wrapper for the shared plan-rev/v1 implementation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_shared():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "shared" / "scripts" / "freeze_snapshot.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("shared_freeze_snapshot", candidate)
            if spec is None or spec.loader is None:
                break
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("cannot find shared/scripts/freeze_snapshot.py")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: compute_plan_rev.py <canonical-plan-path>", file=sys.stderr)
        return 2
    module = _load_shared()
    print(module.compute_plan_rev(Path(argv[1]), require_blocks=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

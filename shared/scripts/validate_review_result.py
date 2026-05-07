#!/usr/bin/env python3
"""Validate canonical review-result JSON for plan-review-implement-loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SOURCES = {"architect_reviewer", "architecture_challenger", "reviewer"}
ARCH_SOURCES = {"architect_reviewer", "architecture_challenger"}
SEVERITIES = {"high", "medium", "low"}
STATUSES = {"open", "resolved", "superseded"}
ARCH_KINDS = {"architecture"}
CODE_KINDS = {"implementation_only", "design_affecting"}


class ValidationError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _as_list(value: Any, field: str) -> list[Any]:
    _require(isinstance(value, list), f"{field} must be a list")
    return value


def _load_prior_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    data = _load_json(path)
    if isinstance(data, list):
        return {str(item["issue_id"] if isinstance(item, dict) else item) for item in data}
    if isinstance(data, dict):
        return {str(item) for item in data.get("issue_ids", [])}
    raise ValidationError("prior-open ledger must be a JSON list or object")


def validate_review_result(
    result: dict[str, Any],
    *,
    review_round: str,
    spec_rev: str,
    plan_rev: str,
    code_rev: str | None = None,
    prior_issue_ids: set[str] | None = None,
) -> None:
    _require(isinstance(result, dict), "result must be a JSON object")
    for field in ("artifact_version", "source", "verdict", "issues"):
        _require(field in result, f"missing {field}")
    _require(result["source"] in SOURCES, "invalid source")

    artifact = result["artifact_version"]
    _require(isinstance(artifact, dict), "artifact_version must be an object")
    _require(str(artifact.get("review_round")) == review_round, "review_round mismatch")
    _require(artifact.get("spec_rev") == spec_rev, "spec_rev mismatch")
    _require(artifact.get("plan_rev") == plan_rev, "plan_rev mismatch")
    if code_rev is not None:
        _require(artifact.get("code_rev") == code_rev, "code_rev mismatch")

    issues = _as_list(result["issues"], "issues")
    open_issues = []
    seen_issue_ids: set[str] = set()
    for index, issue in enumerate(issues):
        _require(isinstance(issue, dict), f"issues[{index}] must be an object")
        for field in (
            "source",
            "reviewer_issue_id",
            "issue_id",
            "severity",
            "kind",
            "artifact_anchor",
            "summary",
            "status",
            "same_as_previous",
            "first_seen_round",
            "last_seen_round",
            "supersedes",
            "merged_into",
            "new_issue_reason",
        ):
            _require(field in issue, f"issues[{index}] missing {field}")

        source = issue["source"]
        reviewer_issue_id = issue["reviewer_issue_id"]
        issue_id = issue["issue_id"]
        _require(source in SOURCES, f"issues[{index}] invalid source")
        _require(source == result["source"], f"issues[{index}] source does not match result source")
        _require(issue_id == f"{source}:{reviewer_issue_id}", f"issues[{index}] issue_id mismatch")
        _require(issue["severity"] in SEVERITIES, f"issues[{index}] invalid severity")
        _require(issue["status"] in STATUSES, f"issues[{index}] invalid status")
        _require(isinstance(issue["same_as_previous"], bool), f"issues[{index}] same_as_previous must be bool")
        _require(isinstance(issue["artifact_anchor"], str) and issue["artifact_anchor"], f"issues[{index}] missing anchor")
        _require(isinstance(issue["summary"], str) and issue["summary"], f"issues[{index}] missing summary")
        _require(issue_id not in seen_issue_ids, f"duplicate issue_id in result: {issue_id}")
        seen_issue_ids.add(issue_id)

        if source in ARCH_SOURCES:
            _require(issue["kind"] in ARCH_KINDS, f"issues[{index}] architecture issue kind must be architecture")
        else:
            _require(issue["kind"] in CODE_KINDS, f"issues[{index}] invalid code issue kind")
        if issue["status"] == "open":
            open_issues.append(issue)

    prior_issue_ids = prior_issue_ids or set()
    missing = prior_issue_ids - seen_issue_ids
    _require(not missing, f"prior-open issues not accounted for: {', '.join(sorted(missing))}")

    source = result.get("source") or (issues[0]["source"] if issues else None)
    if source in ARCH_SOURCES:
        for field in ("unresolved_high", "unresolved_medium"):
            _require(isinstance(result.get(field), int), f"{field} must be int")
        _require(result["unresolved_high"] == sum(1 for issue in open_issues if issue["severity"] == "high"), "unresolved_high mismatch")
        _require(result["unresolved_medium"] == sum(1 for issue in open_issues if issue["severity"] == "medium"), "unresolved_medium mismatch")
        _require(result["verdict"] in {"pass", "block"}, "invalid verdict")
        _require((result["verdict"] == "pass") == (result["unresolved_high"] == 0 and result["unresolved_medium"] == 0), "architecture verdict/count mismatch")
    else:
        for field in ("actionable_issues", "requires_doc_update"):
            _require(field in result, f"missing {field}")
        _require(isinstance(result["actionable_issues"], int), "actionable_issues must be int")
        _require(isinstance(result["requires_doc_update"], bool), "requires_doc_update must be bool")
        _require(result["actionable_issues"] == len(open_issues), "actionable_issues mismatch")
        _require(result["requires_doc_update"] == any(issue["kind"] == "design_affecting" for issue in open_issues), "requires_doc_update mismatch")
        _require((result["verdict"] == "pass") == (result["actionable_issues"] == 0), "code verdict/count mismatch")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--review-round", required=True)
    parser.add_argument("--spec-rev", required=True)
    parser.add_argument("--plan-rev", required=True)
    parser.add_argument("--code-rev")
    parser.add_argument("--prior-open-ledger", type=Path)
    parser.add_argument("--anchor-remap", type=Path)
    args = parser.parse_args(argv)

    try:
        prior_issue_ids = _load_prior_ids(args.prior_open_ledger)
        if args.anchor_remap and prior_issue_ids:
            remap = _load_json(args.anchor_remap)
            remap_ids = set(remap.keys() if isinstance(remap, dict) else [])
            missing = prior_issue_ids - remap_ids
            _require(not missing, f"anchor_remap missing prior issues: {', '.join(sorted(missing))}")
        validate_review_result(
            _load_json(args.result),
            review_round=args.review_round,
            spec_rev=args.spec_rev,
            plan_rev=args.plan_rev,
            code_rev=args.code_rev,
            prior_issue_ids=prior_issue_ids,
        )
    except Exception as exc:
        print(f"validate_review_result: {exc}", file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

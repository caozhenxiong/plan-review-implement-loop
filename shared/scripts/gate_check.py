#!/usr/bin/env python3
"""Compute current workflow gate state from Review Ledger and gate-state-json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LEDGER_BLOCK = re.compile(r"<!-- REVIEW-LEDGER:START -->(.*?)<!-- REVIEW-LEDGER:END -->", re.DOTALL)
STATE_BLOCK = re.compile(r"<!-- EXECUTION-STATE:START -->(.*?)<!-- EXECUTION-STATE:END -->", re.DOTALL)
STATE_JSON = re.compile(r"```gate-state-json\s*\n(.*?)\n```", re.DOTALL)

ISSUE_HEADERS = [
    "review_round",
    "spec_rev",
    "plan_rev",
    "source",
    "reviewer_issue_id",
    "issue_id",
    "severity",
    "kind",
    "summary",
    "artifact_anchor",
    "status",
    "disposition",
    "first_seen_round",
    "last_seen_round",
    "same_as_previous",
    "supersedes",
    "merged_into",
    "new_issue_reason",
]

SEVERITIES = {"high", "medium", "low"}
KINDS = {"architecture", "implementation_only", "design_affecting"}
STATUSES = {"open", "resolved", "superseded", "accepted"}
DISPOSITIONS = {"open", "fixed", "superseded", "accepted", "escalated"}


class GateError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def _extract(pattern: re.Pattern[str], text: str, name: str) -> str:
    match = pattern.search(text)
    if not match:
        raise GateError(f"missing {name} block")
    return match.group(1)


def _parse_table_row(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def parse_issue_details(ledger: str) -> list[dict[str, str]]:
    marker = "### Issue Details"
    _require(marker in ledger, "missing Issue Details")
    section = ledger.split(marker, 1)[1]
    lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    _require(len(lines) >= 2, "Issue Details table is missing")
    headers = _parse_table_row(lines[0])
    _require(headers == ISSUE_HEADERS, "Issue Details table header mismatch")

    issues: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = _parse_table_row(line)
        _require(len(cells) == len(ISSUE_HEADERS), f"bad issue row: {line}")
        issue = dict(zip(ISSUE_HEADERS, cells))
        _require(issue["severity"] in SEVERITIES, f"invalid severity: {issue['severity']}")
        _require(issue["kind"] in KINDS, f"invalid kind: {issue['kind']}")
        _require(issue["status"] in STATUSES, f"invalid status: {issue['status']}")
        _require(issue["disposition"] in DISPOSITIONS, f"invalid disposition: {issue['disposition']}")
        expected = f"{issue['source']}:{issue['reviewer_issue_id']}"
        _require(issue["issue_id"] == expected, f"issue_id mismatch: {issue['issue_id']}")
        issues.append(issue)
    return issues


def parse_gate_state(state_block: str) -> dict[str, object]:
    matches = STATE_JSON.findall(state_block)
    _require(len(matches) == 1, f"expected exactly one gate-state-json block, found {len(matches)}")
    state = json.loads(matches[0])
    _require(isinstance(state, dict), "gate-state-json must be object")
    for field in ("current_phase", "gate_state", "review_round", "spec_rev", "plan_rev"):
        _require(isinstance(state.get(field), str) and state[field], f"{field} must be non-empty string")
    _require(isinstance(state.get("docs_synced"), bool), "docs_synced must be boolean")
    evidence = state.get("verification_evidence")
    _require(isinstance(evidence, list), "verification_evidence must be array")
    for item in evidence:
        _require(isinstance(item, dict), "verification_evidence item must be object")
        for field in ("command", "result", "artifact"):
            _require(isinstance(item.get(field), str) and item[field], f"verification_evidence.{field} must be string")
    for field in ("latest_code_review_actionable_issues",):
        value = state.get(field)
        _require(value is None or (isinstance(value, int) and value >= 0), f"{field} must be null or non-negative int")
    for field in ("latest_code_review_requires_doc_update",):
        value = state.get(field)
        _require(value is None or isinstance(value, bool), f"{field} must be null or bool")
    value = state.get("implementation_changed", False)
    _require(isinstance(value, bool), "implementation_changed must be bool when present")
    for field in ("latest_code_review_spec_rev", "latest_code_review_plan_rev", "latest_code_review_code_rev"):
        value = state.get(field)
        _require(value is None or isinstance(value, str), f"{field} must be null or string")
    return state


def fold_issues(issues: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    current: dict[str, dict[str, str]] = {}
    seen_in_round: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue["review_round"], issue["issue_id"])
        _require(key not in seen_in_round, f"duplicate issue in same round: {issue['review_round']} {issue['issue_id']}")
        seen_in_round.add(key)
        current[issue["issue_id"]] = issue
    return current


def compute_gate(plan_text: str) -> dict[str, object]:
    ledger = _extract(LEDGER_BLOCK, plan_text, "Review Ledger")
    state = parse_gate_state(_extract(STATE_BLOCK, plan_text, "Execution State"))
    current_issues = fold_issues(parse_issue_details(ledger))
    open_issues = [issue for issue in current_issues.values() if issue["status"] == "open"]
    open_arch = [issue for issue in open_issues if issue["kind"] == "architecture"]
    open_code = [issue for issue in open_issues if issue["kind"] != "architecture"]

    unresolved_high = sum(1 for issue in open_arch if issue["severity"] == "high")
    unresolved_medium = sum(1 for issue in open_arch if issue["severity"] == "medium")
    actionable_issues = len(open_code)
    requires_doc_update = any(issue["kind"] == "design_affecting" for issue in open_code)
    latest_code_rev = state.get("latest_code_rev")
    implementation_changed = bool(state.get("implementation_changed", False))
    code_review_tuple = (
        state.get("latest_code_review_spec_rev"),
        state.get("latest_code_review_plan_rev"),
        state.get("latest_code_review_code_rev"),
    )
    current_tuple = (state["spec_rev"], state["plan_rev"], latest_code_rev)
    has_code_review_tuple = any(value is not None for value in code_review_tuple)
    code_review_tuple_matches = code_review_tuple == current_tuple

    if unresolved_high or unresolved_medium:
        gate_state = "phase2_blocked"
        next_action = "update_canonical_docs_and_rerun_phase2"
    elif actionable_issues and requires_doc_update:
        gate_state = "phase4_blocked_design_affecting"
        next_action = "update_canonical_docs_and_rerun_phase2"
    elif actionable_issues:
        gate_state = "phase4_blocked_implementation_only"
        next_action = "fix_code_and_rerun_code_review"
    elif implementation_changed and not latest_code_rev:
        gate_state = "blocked"
        next_action = "write_code_rev_and_rerun_gate_check"
    elif latest_code_rev and not has_code_review_tuple:
        gate_state = "phase4_required"
        next_action = "enter_code_review"
    elif latest_code_rev and not code_review_tuple_matches:
        gate_state = "phase4_required"
        next_action = "enter_code_review"
    elif (
        state.get("latest_code_review_actionable_issues") == 0
        and latest_code_rev
        and code_review_tuple_matches
        and state.get("docs_synced")
        and state.get("verification_evidence")
    ):
        gate_state = "phase5_completed"
        next_action = "complete"
    elif state.get("implementation_confirmed_spec_rev") == state["spec_rev"] and state.get("implementation_confirmed_plan_rev") == state["plan_rev"]:
        gate_state = "phase3_allowed"
        next_action = "begin_implementation"
    else:
        gate_state = "phase2_passed_unconfirmed"
        next_action = "enter_implementation_confirmation"

    result = {
        "current_phase": state["current_phase"],
        "gate_state": gate_state,
        "unresolved_high": unresolved_high,
        "unresolved_medium": unresolved_medium,
        "actionable_issues": actionable_issues,
        "requires_doc_update": requires_doc_update,
        "next_allowed_action": next_action,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    args = parser.parse_args(argv)

    try:
        result = compute_gate(args.plan.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        print(f"gate_check: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

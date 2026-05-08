import json
import re
import tempfile
import unittest
from pathlib import Path

from shared.scripts.extract_review_result import extract_review_result
from shared.scripts.gate_check import ISSUE_HEADERS, compute_gate
from shared.scripts.validate_review_result import ValidationError, validate_review_result


ROOT = Path(__file__).resolve().parents[2]
SPEC_REV = "sha256:" + "a" * 64
PLAN_REV = "sha256:" + "b" * 64
CODE_REV = "sha256:" + "c" * 64


def plan_fixture(state_overrides=None, issues=None):
    state = {
        "current_phase": "phase4",
        "gate_state": "phase4_required",
        "review_round": "R1",
        "spec_rev": SPEC_REV,
        "plan_rev": PLAN_REV,
        "implementation_confirmed_spec_rev": SPEC_REV,
        "implementation_confirmed_plan_rev": PLAN_REV,
        "implementation_changed": False,
        "latest_architecture_review_round": "R1",
        "latest_architecture_verdict": "pass",
        "latest_code_review_round": None,
        "latest_code_rev": None,
        "latest_code_review_spec_rev": None,
        "latest_code_review_plan_rev": None,
        "latest_code_review_code_rev": None,
        "latest_code_review_actionable_issues": None,
        "latest_code_review_requires_doc_update": None,
        "docs_synced": False,
        "verification_evidence": [],
        "next_allowed_action": "enter_code_review",
        "do_not_start_coding_yet": False,
    }
    state.update(state_overrides or {})
    rows = [
        "| " + " | ".join(ISSUE_HEADERS) + " |",
        "| " + " | ".join(["---"] * len(ISSUE_HEADERS)) + " |",
    ]
    for issue in issues or []:
        rows.append("| " + " | ".join(issue.get(header, "") for header in ISSUE_HEADERS) + " |")
    return "\n".join(
        [
            "# Plan",
            "",
            "<!-- REVIEW-LEDGER:START -->",
            "## Review Ledger",
            "",
            "### Issue Details",
            "",
            *rows,
            "<!-- REVIEW-LEDGER:END -->",
            "",
            "<!-- EXECUTION-STATE:START -->",
            "## Execution State",
            "",
            "```gate-state-json",
            json.dumps(state, ensure_ascii=False, indent=2),
            "```",
            "<!-- EXECUTION-STATE:END -->",
            "",
        ]
    )


def code_issue(kind):
    return {
        "review_round": "CR1",
        "spec_rev": SPEC_REV,
        "plan_rev": PLAN_REV,
        "source": "reviewer",
        "reviewer_issue_id": "CR-001",
        "issue_id": "reviewer:CR-001",
        "severity": "medium",
        "kind": kind,
        "summary": "issue",
        "artifact_anchor": "code:file.py",
        "status": "open",
        "disposition": "open",
        "first_seen_round": "CR1",
        "last_seen_round": "CR1",
        "same_as_previous": "false",
        "supersedes": "",
        "merged_into": "",
        "new_issue_reason": "test",
    }


class GateWorkflowTests(unittest.TestCase):
    def test_implementation_changed_without_review_requires_phase4(self):
        result = compute_gate(
            plan_fixture(
                {
                    "implementation_changed": True,
                    "latest_code_rev": CODE_REV,
                }
            )
        )
        self.assertEqual(result["gate_state"], "phase4_required")
        self.assertEqual(result["next_allowed_action"], "enter_code_review")

    def test_implementation_changed_without_code_rev_fails_closed(self):
        result = compute_gate(plan_fixture({"implementation_changed": True, "latest_code_rev": None}))
        self.assertEqual(result["gate_state"], "blocked")
        self.assertEqual(result["next_allowed_action"], "write_code_rev_and_rerun_gate_check")

    def test_stale_code_review_tuple_requires_phase4(self):
        result = compute_gate(
            plan_fixture(
                {
                    "latest_code_rev": CODE_REV,
                    "latest_code_review_spec_rev": SPEC_REV,
                    "latest_code_review_plan_rev": PLAN_REV,
                    "latest_code_review_code_rev": "sha256:" + "d" * 64,
                    "latest_code_review_actionable_issues": 0,
                }
            )
        )
        self.assertEqual(result["gate_state"], "phase4_required")
        self.assertEqual(result["next_allowed_action"], "enter_code_review")

    def test_empty_issue_details_table_is_allowed_for_phase4_required(self):
        result = compute_gate(plan_fixture({"latest_code_rev": CODE_REV}))
        self.assertEqual(result["gate_state"], "phase4_required")
        self.assertEqual(result["next_allowed_action"], "enter_code_review")

    def test_implementation_only_issue_blocks_phase4_only(self):
        result = compute_gate(plan_fixture(issues=[code_issue("implementation_only")]))
        self.assertEqual(result["gate_state"], "phase4_blocked_implementation_only")
        self.assertEqual(result["next_allowed_action"], "fix_code_and_rerun_code_review")

    def test_design_affecting_issue_returns_to_phase2(self):
        result = compute_gate(plan_fixture(issues=[code_issue("design_affecting")]))
        self.assertEqual(result["gate_state"], "phase4_blocked_design_affecting")
        self.assertEqual(result["next_allowed_action"], "update_canonical_docs_and_rerun_phase2")

    def test_zero_cr_without_evidence_does_not_complete(self):
        result = compute_gate(
            plan_fixture(
                {
                    "latest_code_rev": CODE_REV,
                    "latest_code_review_spec_rev": SPEC_REV,
                    "latest_code_review_plan_rev": PLAN_REV,
                    "latest_code_review_code_rev": CODE_REV,
                    "latest_code_review_actionable_issues": 0,
                    "docs_synced": True,
                    "verification_evidence": [],
                }
            )
        )
        self.assertNotEqual(result["gate_state"], "phase5_completed")

    def test_zero_cr_without_code_rev_does_not_complete(self):
        result = compute_gate(
            plan_fixture(
                {
                    "latest_code_rev": None,
                    "latest_code_review_spec_rev": None,
                    "latest_code_review_plan_rev": None,
                    "latest_code_review_code_rev": None,
                    "latest_code_review_actionable_issues": 0,
                    "docs_synced": True,
                    "verification_evidence": [{"command": "pytest", "result": "pass", "artifact": "log"}],
                }
            )
        )
        self.assertNotEqual(result["gate_state"], "phase5_completed")
        self.assertNotEqual(result["next_allowed_action"], "complete")

    def test_zero_cr_with_docs_and_evidence_completes(self):
        result = compute_gate(
            plan_fixture(
                {
                    "latest_code_rev": CODE_REV,
                    "latest_code_review_spec_rev": SPEC_REV,
                    "latest_code_review_plan_rev": PLAN_REV,
                    "latest_code_review_code_rev": CODE_REV,
                    "latest_code_review_actionable_issues": 0,
                    "docs_synced": True,
                    "verification_evidence": [{"command": "pytest", "result": "pass", "artifact": "log"}],
                }
            )
        )
        self.assertEqual(result["gate_state"], "phase5_completed")
        self.assertEqual(result["next_allowed_action"], "complete")


class ReviewResultTests(unittest.TestCase):
    def valid_result(self):
        return {
            "artifact_version": {
                "review_round": "CR1",
                "spec_rev": SPEC_REV,
                "plan_rev": PLAN_REV,
                "code_rev": CODE_REV,
            },
            "source": "reviewer",
            "verdict": "block",
            "actionable_issues": 1,
            "requires_doc_update": False,
            "issues": [
                {
                    "source": "reviewer",
                    "reviewer_issue_id": "CR-001",
                    "issue_id": "reviewer:CR-001",
                    "severity": "medium",
                    "kind": "implementation_only",
                    "artifact_anchor": "code:file.py",
                    "summary": "bug",
                    "status": "open",
                    "same_as_previous": False,
                    "first_seen_round": "CR1",
                    "last_seen_round": "CR1",
                    "supersedes": "",
                    "merged_into": "",
                    "new_issue_reason": "test",
                }
            ],
        }

    def test_extract_review_result_accepts_one_json_fence(self):
        result = extract_review_result("```review-result-json\n{\"source\":\"reviewer\"}\n```")
        self.assertEqual(result["source"], "reviewer")

    def test_extract_review_result_rejects_wrong_fence(self):
        with self.assertRaises(ValueError):
            extract_review_result("```json\n{}\n```")

    def test_validate_review_result_accepts_consistent_counts(self):
        validate_review_result(
            self.valid_result(),
            review_round="CR1",
            spec_rev=SPEC_REV,
            plan_rev=PLAN_REV,
            code_rev=CODE_REV,
        )

    def test_validate_review_result_rejects_count_mismatch(self):
        result = self.valid_result()
        result["actionable_issues"] = 0
        with self.assertRaises(ValidationError):
            validate_review_result(
                result,
                review_round="CR1",
                spec_rev=SPEC_REV,
                plan_rev=PLAN_REV,
                code_rev=CODE_REV,
            )


class ContractParityTests(unittest.TestCase):
    def _schema_enums(self):
        schema = json.loads((ROOT / "shared/schemas/gate-state.schema.json").read_text(encoding="utf-8"))
        return {
            "gate_state": set(schema["properties"]["gate_state"]["enum"]),
            "next_allowed_action": set(schema["properties"]["next_allowed_action"]["enum"]),
        }

    def _doc_enums(self, path):
        text = (ROOT / path).read_text(encoding="utf-8")
        block = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
        self.assertIsNotNone(block, path)
        content = block.group(1)
        enums = {}
        for name in ("gate_state", "next_allowed_action"):
            match = re.search(rf"^{name}:\s*(.+)$", content, re.MULTILINE)
            self.assertIsNotNone(match, f"{path} missing {name}")
            enums[name] = set(match.group(1).split("|"))
        return enums

    def test_claude_gate_enums_match_schema(self):
        expected = self._schema_enums()
        for path in ("claude-code/SKILL.md", "claude-code/references/workflow-contract.md"):
            self.assertEqual(self._doc_enums(path), expected)

    def test_claude_code_review_dispatch_contains_hard_requirements(self):
        text = (ROOT / "claude-code/references/workflow-contract.md").read_text(encoding="utf-8")
        code_reviewer = text.split("### Code Reviewer", 1)[1].split("## Completion Contract", 1)[0]
        for keyword in (
            "code_rev",
            "actionable_issues",
            "requires_doc_update",
            "spec",
            "plan",
            "checklist",
            "scope violation",
            "accepted trade-off",
            "structure-quality",
        ):
            self.assertIn(keyword, code_reviewer)


if __name__ == "__main__":
    unittest.main()

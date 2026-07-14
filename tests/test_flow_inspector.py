from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FLOW_SCRIPTS = ROOT / "scripts" / "flow"


def load_module(name: str, path: Path):
    sys.path.insert(0, str(FLOW_SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(FLOW_SCRIPTS))


CORE = load_module("inspector_core", FLOW_SCRIPTS / "inspector_core.py")
CLI = load_module("inspect_repo_flow", FLOW_SCRIPTS / "inspect_repo_flow.py")


def check(*, status: str = "COMPLETED", conclusion: str | None = "SUCCESS", name: str = "CI Gate"):
    return {"name": name, "status": status, "conclusion": conclusion}


def pull_request(**overrides):
    value = {
        "number": 24,
        "title": "Harden inspector",
        "url": "https://example.invalid/pull/24",
        "isDraft": False,
        "author": {"login": "daedalus-omt"},
        "mergeStateStatus": "CLEAN",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [check()],
        "autoMergeRequest": {"enabledAt": "2026-07-14T00:00:00Z"},
        "latestReviews": [],
        "labels": [{"name": "lane:daedalus"}],
        "updatedAt": "2026-07-14T00:00:00Z",
    }
    value.update(overrides)
    return value


class CheckSummaryTests(unittest.TestCase):
    def test_only_completed_success_is_green(self) -> None:
        cases = [
            ("empty", [], False, "indeterminate"),
            ("pending", [check(status="IN_PROGRESS", conclusion=None)], False, "pending"),
            ("passing", [check()], True, "passing"),
            ("failing", [check(conclusion="FAILURE")], False, "failing"),
            ("neutral", [check(conclusion="NEUTRAL")], False, "indeterminate"),
            ("skipped", [check(conclusion="SKIPPED")], False, "indeterminate"),
            ("cancelled", [check(conclusion="CANCELLED")], False, "failing"),
            ("unknown", [check(conclusion="MYSTERY")], False, "indeterminate"),
        ]
        for name, rollup, expected_green, bucket in cases:
            with self.subTest(name=name):
                summary = CORE.check_summary(rollup)
                self.assertEqual(summary["green"], expected_green)
                if rollup:
                    self.assertEqual(summary[bucket], ["CI Gate"])
                else:
                    self.assertEqual(summary["observed"], 0)

    def test_one_indeterminate_check_prevents_other_successes_from_being_green(self) -> None:
        summary = CORE.check_summary([check(), check(name="Optional", conclusion="SKIPPED")])
        self.assertFalse(summary["green"])
        self.assertEqual(summary["passing"], ["CI Gate"])
        self.assertEqual(summary["indeterminate"], ["Optional"])


class PullRequestClassificationTests(unittest.TestCase):
    def test_pr_state_matrix(self) -> None:
        cases = [
            ("draft", {"isDraft": True}, "Paused", "draft"),
            (
                "changes requested",
                {"reviewDecision": "CHANGES_REQUESTED"},
                "Needs Repair",
                "changes_requested",
            ),
            ("dirty", {"mergeStateStatus": "DIRTY"}, "Needs Repair", "merge_state:dirty"),
            ("behind", {"mergeStateStatus": "BEHIND"}, "Needs Repair", "merge_state:behind"),
            (
                "failing",
                {"statusCheckRollup": [check(conclusion="FAILURE")]},
                "Needs Repair",
                "failing_checks",
            ),
            (
                "review required",
                {"reviewDecision": "REVIEW_REQUIRED"},
                "Needs Review",
                "review_required",
            ),
            (
                "pending",
                {"statusCheckRollup": [check(status="QUEUED", conclusion=None)]},
                "Approved / Waiting Checks",
                "checks_pending",
            ),
            (
                "empty",
                {"statusCheckRollup": []},
                "Approved / Waiting Checks",
                "checks_indeterminate",
            ),
            (
                "blocked",
                {"mergeStateStatus": "BLOCKED"},
                "Blocked - Infrastructure",
                "blocked",
            ),
            (
                "approved without auto merge",
                {"autoMergeRequest": None},
                "Needs Repair",
                "auto_merge_missing",
            ),
            ("auto merge", {}, "Auto-merge Armed", "clean_approved_green"),
        ]
        for name, overrides, expected_state, expected_reason in cases:
            with self.subTest(name=name):
                result = CORE.classify_pr(pull_request(**overrides))
                self.assertEqual(result["flowState"], expected_state)
                self.assertIn(expected_reason, result["reasons"])

    def test_latest_change_request_is_active_repair_evidence(self) -> None:
        result = CORE.classify_pr(
            pull_request(
                latestReviews=[
                    {
                        "state": "CHANGES_REQUESTED",
                        "author": {"login": "reviewer"},
                        "submittedAt": "2026-07-14T00:00:00Z",
                        "body": "Please fix this",
                    }
                ]
            )
        )
        self.assertEqual(result["flowState"], "Needs Repair")
        self.assertEqual(result["changeRequests"][0]["author"], "reviewer")


class IssueClassificationTests(unittest.TestCase):
    def test_explicit_intake_routes_to_planning(self) -> None:
        result = CORE.classify_issue(
            {
                "number": 24,
                "title": "Inspector",
                "url": "https://example.invalid/issues/24",
                "body": "Complete acceptance criteria",
                "labels": [{"name": "state:intake"}, {"name": "lane:daedalus"}],
            }
        )
        self.assertEqual(result["flowState"], "Intake")
        self.assertEqual(result["nextActor"], "Apollo")

    def test_unlabelled_complete_contract_is_ready_for_implementation(self) -> None:
        result = CORE.classify_issue(
            {
                "number": 25,
                "title": "Drift",
                "url": "https://example.invalid/issues/25",
                "body": "## Acceptance criteria\n- complete",
                "labels": [],
            }
        )
        self.assertEqual(result["flowState"], "Ready for Implementation")
        self.assertEqual(result["nextActor"], "Daedalus")

    def test_blocked_issue_routes_to_pheidon(self) -> None:
        result = CORE.classify_issue(
            {
                "number": 26,
                "title": "Decision",
                "url": "https://example.invalid/issues/26",
                "body": "",
                "labels": [{"name": "state:blocked-human"}, {"name": "lane:apollo"}],
            }
        )
        self.assertEqual(result["flowState"], "Blocked - Human")
        self.assertEqual(result["nextActor"], "Pheidon")


class MutationPlanningTests(unittest.TestCase):
    def test_label_plan_reconciles_mutually_exclusive_families(self) -> None:
        item = CORE.classify_pr(
            pull_request(
                reviewDecision="REVIEW_REQUIRED",
                labels=[
                    {"name": "state:implementing"},
                    {"name": "state:paused"},
                    {"name": "lane:daedalus"},
                    {"name": "kind:bug"},
                ],
            )
        )
        changes = CORE.plan_label_changes([item])
        self.assertEqual(
            changes,
            [
                {
                    "kind": "pr",
                    "number": 24,
                    "add": ["lane:ares", "state:needs-review"],
                    "remove": ["lane:daedalus", "state:implementing", "state:paused"],
                }
            ],
        )

    def test_apply_labels_executes_exact_add_and_remove_mutation(self) -> None:
        item = CORE.classify_pr(
            pull_request(
                reviewDecision="REVIEW_REQUIRED",
                labels=[{"name": "state:implementing"}, {"name": "lane:daedalus"}],
            )
        )
        completed = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(CLI, "ensure_label") as ensure, mock.patch.object(CLI, "run", return_value=completed) as run:
            result = CLI.apply_labels("OMT-Global/flow", [item])
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            sorted(call.args[1] for call in ensure.call_args_list),
            ["lane:ares", "state:needs-review"],
        )
        run.assert_called_once_with(
            [
                "gh",
                "pr",
                "edit",
                "24",
                "--repo",
                "OMT-Global/flow",
                "--add-label",
                "lane:ares,state:needs-review",
                "--remove-label",
                "lane:daedalus,state:implementing",
            ]
        )

    def test_repair_dispatch_deduplicates_existing_assignment(self) -> None:
        item = CORE.classify_pr(pull_request(autoMergeRequest=None))
        initial = CORE.default_assignments()
        updated, first = CORE.plan_repair_dispatch("OMT-Global/flow", [item], initial, max_items=10)
        _, second = CORE.plan_repair_dispatch("OMT-Global/flow", [item], updated, max_items=10)
        self.assertEqual(first, [{"lane": "daedalus", "number": 24, "title": "Harden inspector"}])
        self.assertEqual(second, [])

    def test_assignment_write_uses_exclusive_lock_and_atomic_replace(self) -> None:
        item = CORE.classify_pr(pull_request(autoMergeRequest=None))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assignments.json"
            with mock.patch.object(CLI.fcntl, "flock", wraps=CLI.fcntl.flock) as flock:
                result = CLI.dispatch_repairs("OMT-Global/flow", [item], path, max_items=10)
            self.assertEqual(result["count"], 1)
            self.assertEqual(json.loads(path.read_text())["daedalus"]["current"]["number"], 24)
            self.assertTrue(any(call.args[1] == CLI.fcntl.LOCK_EX for call in flock.call_args_list))
            self.assertTrue(any(call.args[1] == CLI.fcntl.LOCK_UN for call in flock.call_args_list))
            self.assertEqual(list(path.parent.glob(".assignments.json.*.tmp")), [])


class CliSafetyTests(unittest.TestCase):
    def test_repo_is_required(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            CLI.parse_args([])

    def test_default_mode_has_no_mutation_flags_or_implicit_paths(self) -> None:
        args = CLI.parse_args(["--repo", "OMT-Global/flow"])
        self.assertFalse(args.apply_labels)
        self.assertFalse(args.dispatch_repairs)
        self.assertIsNone(args.assignments)
        self.assertIsNone(args.json_out)
        self.assertIsNone(args.maintenance_gate)

    def test_dispatch_requires_explicit_assignment_path(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            CLI.parse_args(["--repo", "OMT-Global/flow", "--dispatch-repairs"])

    def test_default_main_reports_without_calling_mutators(self) -> None:
        output = io.StringIO()
        with (
            mock.patch.object(CLI, "gh_json", side_effect=[[], []]),
            mock.patch.object(CLI, "apply_labels") as apply_labels,
            mock.patch.object(CLI, "dispatch_repairs") as dispatch_repairs,
            redirect_stdout(output),
        ):
            CLI.main(["--repo", "OMT-Global/flow", "--issues"])
        apply_labels.assert_not_called()
        dispatch_repairs.assert_not_called()
        self.assertIn("mode: read-only", output.getvalue())
        self.assertIn("Proposed writes", output.getvalue())


if __name__ == "__main__":
    unittest.main()

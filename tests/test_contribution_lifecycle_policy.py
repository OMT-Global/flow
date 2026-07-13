from __future__ import annotations

import importlib.util
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "contribution-lifecycle-v1.json"
EVALUATOR_PATH = ROOT / "scripts" / "flow" / "evaluate_contribution.py"


def load_evaluator():
    spec = importlib.util.spec_from_file_location("evaluate_contribution", EVALUATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load evaluator: {EVALUATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_pr(lines: int = 20) -> dict:
    pr = {
        "title": "feat: add deterministic parser",
        "files": [{"path": "src/parser.py", "additions": lines, "deletions": 0}],
        "commits": [{"sha": "abc123", "message": "feat: parser\n\nSigned-off-by: A User <a@example.com>"}],
        "materialClassification": {"actions": [], "evidence": "pr:1#classification", "classifierVersion": "v1", "prId": "pr:1", "inputDigest": ""},
        "prId": "pr:1",
        "author": {"agentId": "agent:a", "evidence": "pr:1@author"},
        "approvals": [],
    }
    return seal(pr)


def seal(pr: dict) -> dict:
    payload = {"prId": pr["prId"], "files": pr["files"], "commits": pr["commits"]}
    pr["materialClassification"]["inputDigest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return pr


class ContributionLifecyclePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text())
        cls.standard = json.loads((ROOT / "policies" / "public-repository-standard-v1.json").read_text())
        cls.evaluator = load_evaluator()

    def test_policy_matches_authoritative_standard(self) -> None:
        self.assertEqual(self.evaluator.validate_policy(self.policy, self.standard), [])

    def test_size_boundaries_and_deterministic_exclusions(self) -> None:
        expected = {399: "target", 400: "normal", 800: "normal", 801: "warning", 1500: "warning", 1501: "blocking"}
        for lines, classification in expected.items():
            with self.subTest(lines=lines):
                result = self.evaluator.evaluate_pr(self.policy, self.standard, base_pr(lines))
                self.assertEqual(result["sizeClassification"], classification)
        pr = base_pr(1501)
        pr["files"].append({"path": "tests/fixtures/large.json", "additions": 5000, "deletions": 0})
        seal(pr)
        result = self.evaluator.evaluate_pr(self.policy, self.standard, pr)
        self.assertEqual(result["effectiveChangedLines"], 1501)
        self.assertEqual(result["excludedLinesByKind"], {"fixture": 5000})

    def test_caller_cannot_claim_arbitrary_exclusion(self) -> None:
        pr = base_pr(10000)
        pr["files"][0]["kind"] = "generated"
        seal(pr)
        result = self.evaluator.evaluate_pr(self.policy, self.standard, pr)
        self.assertEqual(result["effectiveChangedLines"], 10000)
        self.assertIn("PRS-PR-SIZE-001", result["blockingRuleIds"])

    def test_dco_is_parsed_from_every_commit_message(self) -> None:
        pr = base_pr()
        pr["commits"].append({"sha": "def456", "message": "fix: missing trailer"})
        seal(pr)
        result = self.evaluator.evaluate_pr(self.policy, self.standard, pr)
        self.assertIn("PRS-DCO-001", result["blockingRuleIds"])
        self.assertEqual(result["dcoFailures"], ["def456"])

    def test_placeholder_dco_signoffs_are_rejected(self) -> None:
        for trailer in (
            "Signed-off-by: Your Name <you@example.com>",
            "Signed-off-by: Your Name <your.email@example.com>",
        ):
            with self.subTest(trailer=trailer):
                pr = base_pr()
                pr["commits"][0]["message"] = f"feat: parser\n\n{trailer}"
                seal(pr)
                result = self.evaluator.evaluate_pr(self.policy, self.standard, pr)
                self.assertIn("PRS-DCO-001", result["blockingRuleIds"])

    def test_material_action_requires_independent_evidenced_approval(self) -> None:
        pr = base_pr()
        pr["materialClassification"]["actions"] = ["public-api-change"]
        pr["approvals"] = [{"agentId": "agent:a", "state": "approved", "evidence": "pr:1#review"}]
        self.assertIn("PRS-MATERIAL-001", self.evaluator.evaluate_pr(self.policy, self.standard, pr)["blockingRuleIds"])
        pr["approvals"] = [{"agentId": "agent:b", "state": "approved", "evidence": "pr:1#review2"}]
        self.assertNotIn("PRS-MATERIAL-001", self.evaluator.evaluate_pr(self.policy, self.standard, pr)["blockingRuleIds"])

    def test_unclassified_change_conservatively_requires_independent_review(self) -> None:
        pr = base_pr()
        self.assertIn("PRS-MATERIAL-001", self.evaluator.evaluate_pr(self.policy, self.standard, pr)["blockingRuleIds"])

    def test_empty_or_unknown_identity_and_material_action_are_rejected(self) -> None:
        pr = base_pr()
        pr["author"]["agentId"] = ""
        with self.assertRaisesRegex(ValueError, "author.agentId"):
            self.evaluator.evaluate_pr(self.policy, self.standard, pr)
        pr = base_pr()
        pr["materialClassification"]["actions"] = ["invented-action"]
        with self.assertRaisesRegex(ValueError, "unknown material action"):
            self.evaluator.evaluate_pr(self.policy, self.standard, pr)

    def test_size_exception_requires_complete_current_human_approval(self) -> None:
        pr = base_pr(1501)
        pr["exception"] = {
            "id": "EX-1", "policy": "quality.pullRequests.maximumChangedLines", "scope": "pr:1",
            "rationale": "Generated parser migration", "approvedBy": "human:maintainer",
            "approvalEvidence": "pr:1#approval", "issue": "issue:1", "expires": "2026-12-01"
        }
        result = self.evaluator.evaluate_pr(self.policy, self.standard, pr, today="2026-07-11")
        self.assertNotIn("PRS-PR-SIZE-001", result["blockingRuleIds"])
        pr["exception"]["expires"] = "2026-01-01"
        result = self.evaluator.evaluate_pr(self.policy, self.standard, pr, today="2026-07-11")
        self.assertIn("PRS-PR-SIZE-001", result["blockingRuleIds"])

    def test_exception_must_bind_current_pr_and_size_policy(self) -> None:
        pr = base_pr(1501)
        pr["exception"] = {
            "id": "EX-1", "policy": "unrelated", "scope": "pr:other", "rationale": "No",
            "approvedBy": "human:maintainer", "approvalEvidence": "pr:1#approval",
            "issue": "issue:1", "expires": "2026-12-01"
        }
        self.assertIn("PRS-PR-SIZE-001", self.evaluator.evaluate_pr(self.policy, self.standard, pr)["blockingRuleIds"])

    def test_signoff_must_be_in_terminal_trailer_block(self) -> None:
        pr = base_pr()
        pr["commits"][0]["message"] = "feat: parser\n\nSigned-off-by: A User <a@example.com>\nordinary body after trailer"
        seal(pr)
        self.assertIn("PRS-DCO-001", self.evaluator.evaluate_pr(self.policy, self.standard, pr)["blockingRuleIds"])
        pr["commits"][0]["message"] = "feat: parser\n\nSigned-off-by: A User <a@example.com>\nCo-authored-by: B User <b@example.com>"
        seal(pr)
        self.assertNotIn("PRS-DCO-001", self.evaluator.evaluate_pr(self.policy, self.standard, pr)["blockingRuleIds"])

    def test_issue_readiness_requires_typed_complete_contract(self) -> None:
        result = self.evaluator.evaluate_issue(self.policy, {"problem": True}, inactive_days=0, next_action=None)
        self.assertFalse(result["ready"])
        self.assertIn("problem", result["invalidFields"])
        self.assertIn("PRS-ISSUE-READY-001", result["blockingRuleIds"])

    def test_issue_aging_requires_evidenced_next_action_and_never_auto_closes(self) -> None:
        stale = self.evaluator.evaluate_issue(self.policy, {}, inactive_days=90, next_action=None)
        self.assertEqual(stale["proposedAction"], "close-or-rescope")
        self.assertTrue(stale["humanDecisionRequired"])
        self.assertFalse(stale["mutationAllowed"])
        active = self.evaluator.evaluate_issue(
            self.policy, {}, inactive_days=90,
            next_action={"outcome": "Ship resolver", "dependency": "issue:54", "checkpoint": "2026-08-01", "evidence": "issue:10#comment"},
        )
        self.assertEqual(active["proposedAction"], "review")
        outcome_only = self.evaluator.evaluate_issue(
            self.policy, {}, inactive_days=90,
            next_action={"outcome": "Ship resolver", "dependency": "", "checkpoint": "2026-08-01", "evidence": "issue:10#comment"},
        )
        self.assertEqual(outcome_only["proposedAction"], "review")

    def test_weakened_policy_is_rejected(self) -> None:
        policy = json.loads(json.dumps(self.policy)); policy["pullRequest"]["exclusionPatterns"]["generated"] = ["**"]
        self.assertNotEqual(self.evaluator.validate_policy(policy, self.standard), [])
        policy = json.loads(json.dumps(self.policy)); policy["issue"]["implementationReadyFieldTypes"] = {}
        self.assertNotEqual(self.evaluator.validate_policy(policy, self.standard), [])
        policy = json.loads(json.dumps(self.policy)); policy["version"] = "999.0.0"
        self.assertNotEqual(self.evaluator.validate_policy(policy, self.standard), [])
        policy = json.loads(json.dumps(self.policy)); policy["rules"][0]["severity"] = "informational"
        self.assertNotEqual(self.evaluator.validate_policy(policy, self.standard), [])

    def test_nested_lockfile_is_excluded(self) -> None:
        pr = base_pr(20); pr["files"].append({"path": "packages/app/package-lock.json", "additions": 2000, "deletions": 0})
        seal(pr)
        result = self.evaluator.evaluate_pr(self.policy, self.standard, pr)
        self.assertEqual(result["excludedLinesByKind"], {"lockfile": 2000})

    def test_nested_generated_output_is_excluded(self) -> None:
        for path in (
            "dist/app.js",
            "build/app.js",
            "packages/app/dist/app.js",
            "services/api/build/app.js",
        ):
            with self.subTest(path=path):
                pr = base_pr(20)
                pr["files"].append({"path": path, "additions": 2000, "deletions": 0})
                seal(pr)
                result = self.evaluator.evaluate_pr(self.policy, self.standard, pr)
                self.assertEqual(result["effectiveChangedLines"], 20)
                self.assertEqual(result["excludedLinesByKind"], {"generated": 2000})

    def test_material_path_trigger_cannot_be_omitted(self) -> None:
        pr = base_pr(); pr["files"] = [{"path": "schemas/public.json", "additions": 5, "deletions": 0}]; seal(pr)
        with self.assertRaisesRegex(ValueError, "missing required material actions"):
            self.evaluator.evaluate_pr(self.policy, self.standard, pr)

    def test_nested_runtime_manifests_require_material_classification(self) -> None:
        for path in (
            "packages/app/package.json",
            "services/api/pyproject.toml",
            "crates/core/Cargo.toml",
            "cmd/tool/go.mod",
        ):
            with self.subTest(path=path):
                pr = base_pr(); pr["files"] = [{"path": path, "additions": 5, "deletions": 0}]; seal(pr)
                with self.assertRaisesRegex(ValueError, "missing required material actions"):
                    self.evaluator.evaluate_pr(self.policy, self.standard, pr)
                pr["materialClassification"]["actions"] = ["runtime-dependency-addition"]
                pr["approvals"] = [{"agentId": "agent:b", "state": "approved", "evidence": "pr:1#review2"}]
                self.assertNotIn("PRS-MATERIAL-001", self.evaluator.evaluate_pr(self.policy, self.standard, pr)["blockingRuleIds"])

    def test_roadmap_item_requires_evidenced_action(self) -> None:
        result = self.evaluator.evaluate_issue(self.policy, {"issueKind": "roadmap"}, inactive_days=0, next_action=None)
        self.assertIn("issueKind", result["invalidFields"])


if __name__ == "__main__":
    unittest.main()

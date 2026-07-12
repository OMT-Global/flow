from __future__ import annotations

import importlib.util
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


class ContributionLifecyclePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text())
        cls.evaluator = load_evaluator()

    def test_policy_matches_standard_thresholds_and_exclusions(self) -> None:
        standard = json.loads(
            (ROOT / "policies" / "public-repository-standard-v1.json").read_text()
        )
        self.assertEqual(
            self.evaluator.validate_policy(cls_policy := self.policy, standard),
            [],
        )
        self.assertEqual(
            cls_policy["pullRequest"]["changedLines"],
            standard["quality"]["pullRequestChangedLines"],
        )

    def test_pr_size_excludes_managed_kinds_and_blocks_above_maximum(self) -> None:
        result = self.evaluator.evaluate_pr(
            self.policy,
            {
                "title": "feat: add deterministic parser",
                "changedLines": 1900,
                "excludedLines": {"generated": 200, "lockfile": 100, "fixture": 50, "vendored": 49},
                "commits": [{"signedOff": True}],
                "material": False,
                "authorAgent": "agent-a",
                "approvingAgents": [],
            },
        )
        self.assertEqual(result["effectiveChangedLines"], 1501)
        self.assertIn("PRS-PR-SIZE-001", result["blockingRuleIds"])

    def test_missing_dco_signoff_blocks(self) -> None:
        result = self.evaluator.evaluate_pr(
            self.policy,
            {
                "title": "fix: handle empty input",
                "changedLines": 20,
                "excludedLines": {},
                "commits": [{"signedOff": False}],
                "material": False,
                "authorAgent": "agent-a",
                "approvingAgents": [],
            },
        )
        self.assertIn("PRS-DCO-001", result["blockingRuleIds"])

    def test_non_conventional_title_blocks(self) -> None:
        result = self.evaluator.evaluate_pr(
            self.policy,
            {
                "title": "Add some stuff",
                "changedLines": 20,
                "excludedLines": {},
                "commits": [{"signedOff": True}],
                "material": False,
                "authorAgent": "agent-a",
                "approvingAgents": [],
            },
        )
        self.assertIn("PRS-PR-TITLE-001", result["blockingRuleIds"])

    def test_material_author_cannot_be_sole_reviewer(self) -> None:
        result = self.evaluator.evaluate_pr(
            self.policy,
            {
                "title": "feat: change public api",
                "changedLines": 100,
                "excludedLines": {},
                "commits": [{"signedOff": True}],
                "material": True,
                "authorAgent": "agent-a",
                "approvingAgents": ["agent-a"],
            },
        )
        self.assertIn("PRS-MATERIAL-001", result["blockingRuleIds"])
        result["blockingRuleIds"].clear()
        allowed = self.evaluator.evaluate_pr(
            self.policy,
            {
                "title": "feat: change public api",
                "changedLines": 100,
                "excludedLines": {},
                "commits": [{"signedOff": True}],
                "material": True,
                "authorAgent": "agent-a",
                "approvingAgents": ["agent-b"],
            },
        )
        self.assertNotIn("PRS-MATERIAL-001", allowed["blockingRuleIds"])

    def test_issue_readiness_requires_complete_contract(self) -> None:
        result = self.evaluator.evaluate_issue(
            self.policy,
            {"problem": "Undefined behavior", "acceptanceCriteria": ["Deterministic result"]},
            inactive_days=0,
            credible_next_action=True,
        )
        self.assertEqual(result["ready"], False)
        self.assertIn("securityImplications", result["missingFields"])
        self.assertIn("humanDecisionPoints", result["missingFields"])

    def test_issue_aging_reviews_at_30_and_rescopes_or_closes_at_90(self) -> None:
        review = self.evaluator.evaluate_issue(
            self.policy, {}, inactive_days=30, credible_next_action=True
        )
        stale = self.evaluator.evaluate_issue(
            self.policy, {}, inactive_days=90, credible_next_action=False
        )
        active_dependency = self.evaluator.evaluate_issue(
            self.policy, {}, inactive_days=90, credible_next_action=True
        )
        self.assertEqual(review["agingAction"], "review")
        self.assertEqual(stale["agingAction"], "close-or-rescope")
        self.assertEqual(active_dependency["agingAction"], "review")


if __name__ == "__main__":
    unittest.main()

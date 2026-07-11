from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "transitions-v1.json"
VALIDATOR_PATH = ROOT / "scripts" / "flow" / "validate_transition.py"
DIAGRAM_PATH = ROOT / "docs" / "diagrams" / "policy-transitions-v1.mmd"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_transition", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PolicyTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text())
        cls.validator = load_validator()

    def test_every_state_has_defined_inbound_and_outbound_behavior(self) -> None:
        self.assertEqual(self.validator.validate_policy(self.policy), [])

    def test_illegal_transition_has_rule_and_remediation(self) -> None:
        result = self.validator.evaluate_transition(
            self.policy, "work", "Intake", "Merged"
        )
        self.assertEqual(result["allowed"], False)
        self.assertEqual(result["ruleId"], "PRS-TRANSITION-001")
        self.assertIn("Allowed next states:", result["remediation"])

    def test_material_transition_requires_notification_then_continues(self) -> None:
        missing = self.validator.evaluate_transition(
            self.policy,
            "work",
            "Implementing",
            "PR Open",
            material=True,
        )
        self.assertEqual(missing["ruleId"], "PRS-NOTIFY-001")
        allowed = self.validator.evaluate_transition(
            self.policy,
            "work",
            "Implementing",
            "PR Open",
            material=True,
            notification_evidence="https://example.invalid/issues/1#comment",
        )
        self.assertTrue(allowed["allowed"])

    def test_hard_stop_requires_approval_evidence(self) -> None:
        blocked = self.validator.evaluate_transition(
            self.policy,
            "release",
            "Publish Approval Required",
            "Publishing",
            hard_stop="license-change",
            notification_evidence="https://example.invalid/issues/1#comment",
        )
        self.assertEqual(blocked["ruleId"], "PRS-HARDSTOP-001")
        allowed = self.validator.evaluate_transition(
            self.policy,
            "release",
            "Publish Approval Required",
            "Publishing",
            hard_stop="license-change",
            notification_evidence="https://example.invalid/issues/1#comment",
            approval_evidence="https://example.invalid/issues/1#approval",
        )
        self.assertTrue(allowed["allowed"])

    def test_publish_gate_is_not_a_universal_human_gate(self) -> None:
        result = self.validator.evaluate_transition(
            self.policy,
            "release",
            "Publish Approval Required",
            "Publishing",
            material=True,
            notification_evidence="https://example.invalid/issues/1#comment",
        )
        self.assertTrue(result["allowed"])

    def test_fail_closed_release_blocks_require_evidence(self) -> None:
        security = self.validator.evaluate_transition(
            self.policy,
            "release",
            "Release Blocked - Security",
            "Full Validation Running",
        )
        provenance = self.validator.evaluate_transition(
            self.policy,
            "release",
            "Release Blocked - Artifact",
            "Preflight Running",
        )
        self.assertEqual(security["ruleId"], "PRS-SECURITY-001")
        self.assertEqual(provenance["ruleId"], "PRS-PROV-001")

    def test_checked_in_mermaid_diagram_matches_policy(self) -> None:
        self.assertEqual(
            DIAGRAM_PATH.read_text(),
            self.validator.render_mermaid(self.policy),
        )


if __name__ == "__main__":
    unittest.main()

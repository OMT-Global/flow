from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "policies" / "public-repository-standard-v1.json"
SCHEMA_PATH = ROOT / "schemas" / "public-repository-standard-v1.schema.json"
VALIDATOR_PATH = ROOT / "scripts" / "flow" / "validate_policy_bundle.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_policy_bundle", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicRepositoryStandardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads(BUNDLE_PATH.read_text())
        cls.schema = json.loads(SCHEMA_PATH.read_text())
        cls.validator = load_validator()

    def test_bundle_has_required_classes_and_maturity_levels(self) -> None:
        self.assertEqual(
            set(self.bundle["repositoryClasses"]),
            {
                "cli",
                "library",
                "service",
                "infrastructure",
                "github-action",
                "specification",
                "documentation",
            },
        )
        self.assertEqual(
            set(self.bundle["maturityLevels"]),
            {"experimental", "alpha", "beta", "stable", "maintenance", "archived"},
        )

    def test_bundle_is_publisher_neutral(self) -> None:
        encoded = json.dumps(self.bundle).lower()
        self.assertNotIn("omt-global", encoded)
        self.assertEqual(self.bundle["publisher"]["identitySource"], "publisherKey")
        self.assertEqual(
            self.bundle["humanHardStops"]["spendThresholdSource"],
            "publisher.spendingApprovalThreshold",
        )

    def test_all_required_policy_areas_have_unique_rule_ids(self) -> None:
        required_areas = {
            "repository-classification",
            "maturity",
            "material-action",
            "notification",
            "human-hard-stop",
            "adr",
            "quality",
            "security",
            "provenance",
            "release",
            "exception",
            "conformance",
        }
        rules = self.bundle["rules"]
        self.assertTrue(required_areas.issubset({rule["area"] for rule in rules}))
        rule_ids = [rule["id"] for rule in rules]
        self.assertEqual(len(rule_ids), len(set(rule_ids)))

    def test_valid_bundle_has_no_validation_errors(self) -> None:
        self.assertEqual(self.validator.validate_bundle(self.bundle, self.schema), [])

    def test_unknown_rule_reference_fails_deterministically(self) -> None:
        invalid = copy.deepcopy(self.bundle)
        invalid["conformance"]["blockingRuleIds"].append("PRS-NOT-REAL")
        self.assertEqual(
            self.validator.validate_bundle(invalid, self.schema),
            [
                "$.conformance.blockingRuleIds[4]: unknown rule id 'PRS-NOT-REAL'",
            ],
        )

    def test_duplicate_rule_id_fails_deterministically(self) -> None:
        invalid = copy.deepcopy(self.bundle)
        invalid["rules"].append(copy.deepcopy(invalid["rules"][0]))
        self.assertEqual(
            self.validator.validate_bundle(invalid, self.schema),
            ["$.rules[12].id: duplicate rule id 'PRS-CLASS-001'"],
        )

    def test_legacy_alias_target_must_exist(self) -> None:
        invalid = copy.deepcopy(self.bundle)
        invalid["compatibility"]["repositoryClassAliases"]["tooling"] = "missing"
        self.assertEqual(
            self.validator.validate_bundle(invalid, self.schema),
            [
                "$.compatibility.repositoryClassAliases.tooling: unknown repository class 'missing'",
            ],
        )


if __name__ == "__main__":
    unittest.main()

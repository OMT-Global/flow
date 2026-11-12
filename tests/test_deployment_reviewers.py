"""Protect the owner-selected stage and production deployment gate."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeploymentReviewerPolicyTests(unittest.TestCase):
    def test_stage_and_production_list_both_reviewers_and_prevent_self_review(self):
        manifest = (ROOT / "project.bootstrap.yaml").read_text()
        sections = re.findall(r"(?ms)^environments:\n(.*?)(?=^[^\s#]|\Z)", manifest)
        self.assertEqual(len(sections), 1)
        expected = (
            "  stage:\n"
            "    reviewers:\n"
            "      - jmcte\n"
            "      - athena-omt\n"
            "    requireApproval: true\n"
            "    preventSelfReview: true\n"
            "    branches: []\n"
            "  prod:\n"
            "    reviewers:\n"
            "      - jmcte\n"
            "      - athena-omt\n"
            "    requireApproval: true\n"
            "    preventSelfReview: true\n"
            "    branches:\n"
            "      - main\n"
        )
        self.assertEqual(sections[0], expected)


if __name__ == "__main__":
    unittest.main()

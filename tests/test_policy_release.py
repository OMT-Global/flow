from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow" / "build_policy_release.py"


def load_release():
    spec = importlib.util.spec_from_file_location("build_policy_release", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PolicyReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release = load_release()

    def test_build_is_reproducible_and_verifies_offline(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = self.release.build_release(ROOT, Path(first), "1.0.0")
            two = self.release.build_release(ROOT, Path(second), "1.0.0")
            self.assertEqual(one["archiveHash"], two["archiveHash"])
            self.assertEqual(self.release.verify_release(Path(first)), [])
            manifest = json.loads((Path(first) / "policy-release-v1.0.0.json").read_text())
            self.assertIn("policies/transitions-v1.json", manifest["files"])
            self.assertIn("policies/contribution-lifecycle-v1.json", manifest["files"])
            self.assertIn("policies/security-provenance-v1.json", manifest["files"])

    def test_tampered_release_fails_verification(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            self.release.build_release(ROOT, Path(output), "1.0.0")
            archive = Path(output) / "flow-policy-v1.0.0.zip"
            archive.write_bytes(archive.read_bytes() + b"tampered")
            self.assertIn("archive digest mismatch", self.release.verify_release(Path(output)))

    def test_production_policy_references_must_be_immutable(self) -> None:
        for reference in ("v1.0.0", "a" * 40, "b" * 64):
            self.assertEqual(self.release.validate_consumer_reference(reference), [])
        for reference in ("main", "refs/heads/main", "v1", "v1.2", "latest"):
            self.assertNotEqual(self.release.validate_consumer_reference(reference), [])

    def test_upgrade_gates_match_patch_minor_major_policy(self) -> None:
        self.assertEqual(self.release.upgrade_gate("1.0.0", "1.0.1"), "tests-may-auto-merge")
        self.assertEqual(self.release.upgrade_gate("1.0.0", "1.1.0"), "independent-agent-review")
        self.assertEqual(self.release.upgrade_gate("1.0.0", "2.0.0"), "material-notification-and-adr")

    def test_incompatible_or_downgrade_versions_fail(self) -> None:
        with self.assertRaises(ValueError):
            self.release.upgrade_gate("1.1.0", "1.0.0")
        with self.assertRaises(ValueError):
            self.release.upgrade_gate("not-semver", "1.0.0")


if __name__ == "__main__":
    unittest.main()

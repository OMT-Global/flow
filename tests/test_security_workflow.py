"""Negative controls for the product-owned dependency/SBOM security boundary."""
import importlib.util
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("contract", ROOT / "scripts/ci/validate_repository_contract.py")
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


class SecurityWorkflowTests(unittest.TestCase):
    def test_reviewed_security_files_are_present_and_bound(self):
        self.assertEqual(contract.check_security_contract(ROOT), [])

    def test_security_boundary_mutations_fail_despite_comment_decoys(self):
        cases = [
            (".github/workflows/security.yml", "  pull_request:", "  pull_request_target:"),
            (".github/workflows/security.yml", "      pull-requests: read", "      pull-requests: write"),
            (".github/workflows/security.yml", "github.event_name == 'push' || github.event_name == 'schedule'", "github.event_name == 'pull_request' || github.event_name == 'push'"),
            (".github/workflows/security.yml", "runs-on: ubuntu-latest", "runs-on: [self-hosted, linux, public]"),
            (".github/workflows/security.yml", " && vars.DEPENDENCY_REVIEW_ENABLED == 'true'", ""),
            (".github/workflows/security.yml", "@11d5960a326750d5838078e36cf38b85af677262", "@main"),
            (".github/workflows/security.yml", "      contents: read", "      contents: read\n      actions: write"),
            (".github/workflows/security.yml", "  sbom:", "  sbom:\n    secrets: inherit"),
            (".github/workflows/security.yml", "          fail-on-severity: high", "          warn-only: true"),
            (".github/workflows/security.yml", "          format: spdx-json", "          format: cyclonedx-json"),
            (".github/dependabot.yml", 'package-ecosystem: "github-actions"', 'package-ecosystem: "npm"'),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / ".github", root / ".github")
            self.assertEqual(contract.check_security_contract(root), [])
            for filename, old, new in cases:
                with self.subTest(filename=filename, mutation=new):
                    path = root / filename
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new, 1) + "\n# decoy: " + old.replace("\n", " ") + "\n")
                    self.assertIn("unreviewed security contract bytes", "\n".join(contract.check_security_contract(root)))
                    path.write_text(original)
            self.assertEqual(contract.check_security_contract(root), [])

    def test_artifact_only_sbom_uses_repository_read_permission(self):
        workflow = (ROOT / ".github/workflows/security.yml").read_text()
        sbom = workflow.split("  sbom:\n", 1)[1]
        self.assertIn("      contents: read", sbom)
        self.assertNotIn("contents: write", sbom)
        self.assertIn("upload-release-assets: false", sbom)
        self.assertNotIn("dependency-snapshot: true", sbom)

    def test_existing_default_codeql_coverage_is_not_replaced_by_advanced_uploads(self):
        workflow = (ROOT / ".github/workflows/security.yml").read_text()
        self.assertNotIn("github/codeql-action/", workflow)
        self.assertNotIn("  codeql:", workflow)
        self.assertIn("CodeQL remains GitHub default setup for Actions and Python", workflow)
        manifest = (ROOT / "project.bootstrap.yaml").read_text()
        self.assertRegex(manifest, r"(?m)^  codeqlSetup: default$")
        languages = re.search(r"(?m)^  codeqlLanguages:\n((?:    - [a-z-]+\n)+)", manifest)
        self.assertIsNotNone(languages)
        self.assertEqual(re.findall(r"(?m)^    - ([a-z-]+)$", languages.group(1)), ["actions", "python"])


if __name__ == "__main__":
    unittest.main()

"""Keep Flow's manifest aligned with its published squash-merge policy."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MergePolicyTests(unittest.TestCase):
    def test_manifest_explicitly_selects_squash_only(self):
        manifest = (ROOT / "project.bootstrap.yaml").read_text()
        sections = re.findall(r"(?ms)^github:\n(.*?)(?=^[^\s#]|\Z)", manifest)
        self.assertEqual(len(sections), 1)
        fields = re.findall(r"(?m)^  (allowMergeCommit|allowSquashMerge|allowRebaseMerge): (true|false)$", sections[0])
        self.assertCountEqual(fields, [("allowMergeCommit", "false"), ("allowSquashMerge", "true"), ("allowRebaseMerge", "false")])


if __name__ == "__main__":
    unittest.main()

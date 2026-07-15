import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "validate_repository_contract.py"
SPEC = importlib.util.spec_from_file_location("repository_contract", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
repository_contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repository_contract)


class RepositoryContractTests(unittest.TestCase):
    def test_repository_contract_is_current(self):
        self.assertEqual(repository_contract.validate(ROOT), [])

    def test_generated_file_drift_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical.txt"
            projected = root / "projected.txt"
            canonical.write_text("current\n")
            projected.write_text("stale\n")

            errors = repository_contract.check_generated_file_pairs(
                root,
                (("canonical.txt", "projected.txt"),),
            )

        self.assertEqual(
            errors,
            ["generated governance drift: canonical.txt != projected.txt"],
        )


if __name__ == "__main__":
    unittest.main()

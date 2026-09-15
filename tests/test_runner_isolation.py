"""Mutation and executable aggregate-gate controls for the reviewed workflow pair."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('contract', ROOT / 'scripts/ci/validate_repository_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class RunnerIsolationTests(unittest.TestCase):
    def test_pr_and_untrusted_event_mutations_are_rejected(self):
        cases = [
            ('trusted-flow.yml', "github.event_name == 'push'", "github.event_name == 'pull_request' || github.event_name == 'push'"),
            ('trusted-flow.yml', "github.repository == 'OMT-Global/flow'", 'true'),
            ('trusted-flow.yml', "github.ref == 'refs/heads/main'", 'true'),
            ('trusted-flow.yml', 'persist-credentials: false', 'persist-credentials: true'),
            ('ci.yml', 'runs-on: ubuntu-latest', 'runs-on: [self-hosted, linux, public]'),
            ('ci.yml', '@1a7355259ec004007a8006b9879e4783d73cb9ad', '@main'),
            ('ci.yml', 'permissions:\n      contents: read', 'secrets: inherit\n    permissions:\n      contents: read'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for p in ['.github', 'docs', 'AGENTS.md', 'project.bootstrap.yaml']:
                src = ROOT / p
                if src.is_dir(): shutil.copytree(src, root / p)
                else: shutil.copy2(src, root / p)
            self.assertEqual(contract.check_runner_contract(root), [])
            for filename, old, new in cases:
                with self.subTest(filename=filename, mutation=new):
                    path = root / '.github/workflows' / filename
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new, 1) + '\n# decoy: ' + old.replace('\n', ' ') + '\n')
                    self.assertIn('unreviewed runner contract bytes', '\n'.join(contract.check_runner_contract(root)))
                    path.write_text(original)
            self.assertEqual(contract.check_runner_contract(root), [])

    def test_aggregate_checks_require_success_and_reject_skipped_failure(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        scripts = re.findall(r'        run: \|\n((?:          .*\n)+)', workflow)
        self.assertEqual(len(scripts), 3)
        for indented in scripts:
            script = '\n'.join(line[10:] for line in indented.splitlines())
            for trusted in [True, False]:
                for result in ['success', 'failure', 'cancelled', 'skipped']:
                    with self.subTest(trusted=trusted, result=result):
                        env = dict(os.environ, TRUSTED_EVENT=str(trusted).lower(),
                                   TRUSTED_RESULT=result if trusted else 'skipped',
                                   HOSTED_RESULT='skipped' if trusted else result)
                        proc = subprocess.run(['bash', '-e', '-c', script], env=env, capture_output=True)
                        self.assertEqual(proc.returncode == 0, result == 'success')
            # Contradictory scheduling must not appear green either.
            env = dict(os.environ, TRUSTED_EVENT='true', TRUSTED_RESULT='success', HOSTED_RESULT='success')
            self.assertNotEqual(subprocess.run(['bash', '-e', '-c', script], env=env).returncode, 0)

    def test_callee_has_no_inputs_or_secrets_and_checkout_is_fixed_on_bootstrap(self):
        text = (ROOT / '.github/workflows/trusted-flow.yml').read_text()
        self.assertNotIn('inputs:', text)
        self.assertNotIn('secrets:', text)
        self.assertIn("github.ref == 'refs/heads/main' && github.sha || '165ff16e2cb3cbc176a107eb1c1f99f4f925438d'", text)
        self.assertNotIn("github.event_name == 'pull_request'", text)
        for command in ['bash scripts/ci/run-fast-checks.sh', 'go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7', 'bash scripts/ci/run-extended-validation.sh']:
            self.assertIn(command, text)

if __name__ == '__main__': unittest.main()

#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

python3 -m json.tool schemas/issue-contract.schema.json >/dev/null
python3 -m json.tool schemas/pr-contract.schema.json >/dev/null
python3 -m json.tool schemas/public-repository-standard-v1.schema.json >/dev/null
python3 -m json.tool schemas/provenance-manifest-v1.schema.json >/dev/null

python3 scripts/ci/validate_repository_contract.py
python3 scripts/flow/validate_policy_bundle.py
python3 scripts/flow/validate_transition.py
python3 scripts/flow/evaluate_contribution.py
python3 scripts/flow/validate_provenance.py
python3 -m unittest discover -s tests -v

python3 -B -c 'from pathlib import Path; [compile(path.read_text(), str(path), "exec") for path in sorted(Path("scripts").rglob("*.py"))]'

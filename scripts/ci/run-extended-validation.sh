#!/usr/bin/env bash
set -euo pipefail

bash scripts/ci/run-fast-checks.sh

artifact_dir="$(mktemp -d "${TMPDIR:-/tmp}/flow-policy-release.XXXXXX")"
trap 'rm -rf "$artifact_dir"' EXIT

python3 scripts/flow/build_policy_release.py \
  --output "$artifact_dir" \
  --version 1.0.0 \
  --verify

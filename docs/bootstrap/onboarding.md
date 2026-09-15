# Bootstrap onboarding

Review this file before the first merge after Bootstrap changes repository governance.

## Managed and product-owned boundaries

`project.bootstrap.yaml` is the repository control plane. Its `repo.managedPaths` list delegates only the implementation and flow-blocker issue-form projections to Bootstrap. Their canonical `github/` inputs remain product-owned, and the repository contract requires byte-identical projections. `.bootstrap/managed-files.json` records the generated ownership hashes.

Flow owns `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, this onboarding guide, `.githooks/pre-commit`, the canonical and projected PR/release-train templates, product code, policy data, validators, and CI scripts. The generic archetype cannot currently preserve Flow's exact runner selector, immutable production-pin guidance, canonical PR template, or fast-check/cache-rejecting hook. Do not apply generic replacements to those paths. This ownership boundary does not waive any review, CI, security, or release gate.

The recovery used Bootstrap commit `99455ebc120bc91987ee2f7f9a7c097ae73021dc` through its repository-only `loadManifest` / `planRepo` / `applyRepo` APIs. No GitHub governance apply is needed. Run Bootstrap in plan mode and review the managed/product-owned inventory before apply. A clean plan must preserve both issue forms and their canonical counterparts; any content change needs matching canonical-source review before apply. Flow issue [#13](https://github.com/OMT-Global/flow/issues/13) records the current plan evidence and the external resolver/projection blocker.

## Review and merge gates

- Governing work must link a GitHub issue.
- `CI Gate` is the required repository check.
- One non-author approval from `OMT-Codeowners` is required.
- The PR author enables squash auto-merge when checks, review, and conversation gates can converge safely.
- Policy releases follow the exact-pin and independent-review rules in [Policy releases and upgrades](../policy-release-and-upgrades.md).

## Runner policy

The manifest's `hybrid-safe` policy is implemented by hosted PR checks and an immutable, input-free trusted callee. Every PR (including same-repository branches) stays hosted. Trusted main push/dispatch uses `linux-flow-trusted` with `[self-hosted, Linux, X64, shell-only]`. The callee rejects all PR events and non-main refs before assignment except the named bootstrap branch, which always checks out the fixed pre-migration trusted revision. No caller-controlled command/ref/artifact inputs or inherited secrets are accepted.

`CI Gate`, `Workflow Lint`, and `Extended Validation` report success only after the applicable real checks succeed; a skipped or cancelled required execution is not success. Release publication remains hosted and unchanged. Docker, service containers, and browser workloads remain hosted.

The server-side group must admit only Flow and the full SHA-pinned callee. Flow must be excluded from ALL other self-hosted groups that admit public repositories. Job conditions in mutable PR workflow files are not an isolation boundary. Preserve all other repositories' existing access. The selected existing slot must retain its group after turnover; do not add hosts or slots.

Retain `pheidon/flow-trusted-source` at the immutable source commit: GitHub reusable workflow discovery can fail after the source branch is removed even when the commit API remains readable. Do not delete this ref at squash merge. Callee and caller bytes are bound by the repository guard; any new version requires independent exact-head review, new digests, selector review, and new execution proof. Never repin automatically. Hosted PR CI validates the candidate; bootstrap native CI validates the fixed trusted base; post-merge native CI must validate the merged revision. A different caller-ref negative control is NOT a real fork trial.

## Local checks

```sh
git config core.hooksPath .githooks
bash scripts/ci/run-fast-checks.sh
bash scripts/ci/run-extended-validation.sh
```

The fast check validates local Markdown targets, canonical-to-projected governance drift, workflow runner labels, release-pin guidance, policy data, and unit tests. Extended validation additionally builds and verifies the deterministic policy release offline.

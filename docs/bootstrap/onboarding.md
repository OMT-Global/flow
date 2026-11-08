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

The manifest's `github-hosted-first` policy keeps every PR and the immutable, input-free trusted callee on GitHub-hosted runners. Trusted main push/dispatch uses `ubuntu-24.04` with explicit Python 3.12 and Go 1.23.12 setup. The callee retains its event restrictions and fixed bootstrap checkout; no caller-controlled inputs or inherited secrets are accepted.

`CI Gate`, `Workflow Lint`, and `Extended Validation` require the applicable real checks to succeed. Release publication remains unchanged. Server-side runner groups and repository access are outside this migration.

Keep the source branch containing the pinned callee commit available for reusable workflow discovery. Callee and caller bytes remain bound by the repository guard; updates require independent exact-head review, matching digests, and execution proof. Post-merge trusted CI must validate the merged revision.

## Local checks

```sh
git config core.hooksPath .githooks
bash scripts/ci/run-fast-checks.sh
bash scripts/ci/run-extended-validation.sh
```

The fast check validates local Markdown targets, canonical-to-projected governance drift, workflow runner labels, release-pin guidance, policy data, and unit tests. Extended validation additionally builds and verifies the deterministic policy release offline.

## Public-standard migration preparation

The additive migration governed by [Bootstrap #63](https://github.com/OMT-Global/bootstrap/issues/63) declares this repository as a `specification` with `stable` product maturity, separately from its simple release-automation profile. `policy.flow` resolves the existing `policies/public-repository-standard-v1.json` through immutable Flow release `v1.0.1` and canonical object digest `52877f4225a192c6ac2250a7f289f479be83a923ce15152c517db77ab0d5249d`. The release's internal policy version remains 1.0.0; do not relabel its data to match the release number.

The existing two-form delegation, approved MIT template/output, notices, team CODEOWNERS, product README, SECURITY policy, canonical inputs, and CI/callee trust contract remain authoritative. A repository-only Bootstrap plan must report the two forms, legal outputs, and ownership sidecar unchanged. Use an independently reviewed immutable Bootstrap revision with pinned-policy conformance support, and record its exact revision and all check results in the migration PR.

`.github/workflows/security.yml` and `.github/dependabot.yml` are product-owned additions, not new Bootstrap sidecar claims. The former adds read-only fork dependency review and trusted-push/schedule SPDX SBOM generation on GitHub-hosted runners; the artifact-only SBOM job also uses a read-only repository token and never uploads release assets or dependency snapshots. The latter schedules weekly Actions dependency updates and retains review of major upgrades. The repository validator binds their reviewed bytes, while the existing CI/callee byte guards remain unchanged. Any change to these contracts needs matching independent source review and digest updates.

Dependency review runs only when the effective `DEPENDENCY_REVIEW_ENABLED` repository/organization variable is `true`. Its activation and usable dependency-graph evidence must be verified before claiming that check operates; this source change does not modify settings or invent capability observations.

CodeQL remains the existing GitHub default setup for both Actions and Python, declared through `ci.codeqlSetup: default` and `ci.codeqlLanguages`. This workflow intentionally contains no advanced CodeQL upload. GitHub [documents that default setup blocks advanced/API uploads](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/configure-code-scanning/configure-code-scanning). Use a Bootstrap revision implementing the explicit default-setup contract; an older generator that lacks this mode is not a compatible validator for this migration.

A passing default-setup observation requires actual configured mode, successful analysis for both declared languages, and verified GitHub-hosted execution. The initial migration evidence binds successful [run 42410659313](https://github.com/OMT-Global/flow/actions/runs/42410659313), Actions/Python analyses, and GitHub-hosted jobs to `669d095891a2fa2c9772735edf3e9cdf44c1214f`; it does not attest a later revision. Reinspect configuration, analysis coverage, and runner evidence on the actual migrated head. Do not disable working scans, narrow Actions coverage, or invent capability observations. A future switch to advanced setup requires a reviewed mode/coverage plan and actual settings authorization, followed by successful analysis on that revision.

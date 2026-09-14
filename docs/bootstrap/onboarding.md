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

The manifest's `hybrid-safe` policy maps Flow's shell-safe CI Gate to `[self-hosted, linux, shell-only, public]`. The live job used to verify this contract on 2026-07-15 ran in runner group `linux-public` with those exact labels. Jobs requiring Docker, service containers, browser infrastructure, or a workflow-level `container:` declaration stay on GitHub-hosted runners.

If the workflow selector, this document, `AGENTS.md`, or live job metadata disagree, stop and reconcile the trust boundary before merging.

## Local checks

```sh
git config core.hooksPath .githooks
bash scripts/ci/run-fast-checks.sh
bash scripts/ci/run-extended-validation.sh
```

The fast check validates local Markdown targets, canonical-to-projected governance drift, workflow runner labels, release-pin guidance, policy data, and unit tests. Extended validation additionally builds and verifies the deterministic policy release offline.

# Bootstrap onboarding

Review this file before the first merge after Bootstrap changes repository governance.

## Managed and product-owned boundaries

`project.bootstrap.yaml` is the repository control plane. Its `repo.managedPaths` list identifies Bootstrap-managed guidance and GitHub templates. Product code, policy data, validators, CI scripts, and canonical `github/` inputs remain product-owned unless the manifest says otherwise.

Run Bootstrap in plan mode and review the managed/product-owned inventory before apply. Flow issue [#13](https://github.com/OMT-Global/flow/issues/13) records the current plan evidence and the external resolver/projection blocker.

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

# Contribution and issue lifecycle policy

The authoritative machine-readable contract is [`policies/contribution-lifecycle-v1.json`](../policies/contribution-lifecycle-v1.json). Validate it with `python3 scripts/flow/evaluate_contribution.py`.

## Pull requests

- Aim below 400 effective changed lines, warn above 800, and block above 1,500.
- Exclude generated files, lockfiles, fixtures, and vendored code from the effective count.
- Split blocked changes unless a valid, human-approved policy exception applies.
- Use Conventional Commit titles, squash merge, linear history, and delete branches after merge.
- Every contributed commit requires a DCO 1.1 `Signed-off-by` trailer.
- V1 does not use a CLA. Reconsider one only for dual or proprietary licensing, explicit patent terms, or copyright consolidation.
- A material change requires at least one approving agent whose identity differs from the author agent. The author cannot satisfy their own independent-review gate.
- V1 has no cryptographically trusted non-material classifier. An empty material-action list is therefore treated as unclassified, and unclassified pull requests conservatively require the same independent approval. A future policy version may relax this only after introducing verified non-material classification evidence.
- External issues and pull requests are welcome, remain subject to maintainer gates, and must use fork-safe workflows.

## Implementation-ready issues

An issue ready for execution declares an `issueKind` of `implementation`, `roadmap`, `dependency`, or `maintenance`, then states its problem, desired outcome, scope, non-goals, acceptance criteria, test expectations, security implications, documentation implications, dependencies, and human decision points.

Agents may refine vague requests into that contract and continue after required material notification. Every `roadmap` issue must include an evidenced concrete outcome or active dependency and a future checkpoint. Speculative multi-year roadmap entries are not accepted.

## Aging

- Review an inactive issue after 30 days.
- After 90 inactive days, close or rescope an issue that has no credible next action.
- An active dependency or other credible next action preserves the issue, but it remains subject to review and an explicit next checkpoint.

Automated lifecycle changes must report their evidence and proposed action before mutation. Ambiguous destructive closure remains a human decision point.

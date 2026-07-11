# Governed Release Flow

OMT governed releases use GitHub issues, release branches, validation-only workflows, explicit publish approval, and attached evidence to keep release state durable and inspectable.

## Principles

- GitHub issue is the durable release-train record.
- Release branch isolates release prep and release fixes from mainline work.
- Preflight proves package and artifact shape without publishing.
- Full validation proves release readiness without mutating production surfaces.
- Publish is the only mutating path.
- Publish consumes the same artifact proven by preflight.
- Release evidence must be attached to the GitHub Release.
- Postpublish verification closes the loop.

## Lanes

- `dev`: `main` branch, moving head.
- `rc`: `vX.Y.Z-rc.N` or `vX.Y.Z-beta.N`.
- `stable`: `vX.Y.Z`.
- `maintenance`: `release/X.Y` plus `vX.Y.Z` patch tags.

SemVer is the default OMT project versioning model because bootstrap already projects SemVer release automation.

## State Machine

Canonical release states:

1. `Release Intake`
2. `Release Scope Locked`
3. `Release Branch Open`
4. `Release Prep`
5. `Preflight Running`
6. `Preflight Passed`
7. `Full Validation Running`
8. `Full Validation Passed`
9. `Tag Ready`
10. `Publish Approval Required`
11. `Publishing`
12. `Published`
13. `Postpublish Verification`
14. `Promoted`
15. `Release Closed`
16. `Release Blocked - Human`
17. `Release Blocked - CI`
18. `Release Blocked - Security`
19. `Release Blocked - Artifact`
20. `Release Rolled Back / Superseded`

The executable transition contract is [`policies/transitions-v1.json`](../policies/transitions-v1.json). `Publish Approval Required` is retained as a compatibility state name; it records publish-gate evaluation and material notification. It requires explicit human approval only when the release includes a defined human hard stop or a configured protected-environment gate.

## Actors

- Pheidon: release controller, approval gate, final publish decision.
- Apollo: release issue quality, scope lock, release notes, changelog quality.
- Daedalus: release fixes, version bumps, artifact build repair.
- Ares: adversarial validation, regression pressure, security/risk review.
- Hephaestus: CI, lockfiles, workflow health, artifact generation, evidence, publish mechanics.
- Hermes: platform-native validation where relevant, especially macOS/native packaging.

## Done Definition

A release is done only when:

- release issue is closed or intentionally superseded;
- release branch is merged or intentionally retained for maintenance;
- exact tag exists;
- GitHub Release or prerelease exists;
- release evidence is uploaded;
- preflight run ID is recorded;
- validation run ID is recorded;
- publish run ID is recorded if publishing occurred;
- postpublish verification passed or was explicitly waived with rationale;
- floating tags/channels were promoted if applicable;
- no worker lane retains stale active state.

## Block Handling

`Release Blocked - Human`: record the decision needed, the accountable approver, and the next review checkpoint on the release issue. Do not publish until the decision is resolved.

`Release Blocked - CI`: link the failing workflow run, assign Hephaestus or the relevant implementation owner, and keep the release issue open until the rerun passes or the release is superseded.

`Release Blocked - Security`: assign Ares and the code owner, capture the risk and mitigation, and require explicit release-owner approval before continuing.

`Release Blocked - Artifact`: keep the candidate artifact immutable, repair with a new release fix commit, and rerun preflight so publish consumes newly proven artifacts.

`Release Rolled Back / Superseded`: record the successor release issue or tag, preserve the published release evidence, and close the old train as superseded. Do not delete or rewrite published prerelease tags; cut the next prerelease number.

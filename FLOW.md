# OMT-Global Flow Protocol

## Principle

Autonomy is not agents doing more random work. Autonomy is a controlled flow system where every issue and pull request has:

1. truthful state;
2. a valid next action;
3. an accountable actor;
4. a safe gate to completion.

No silent limbo.

## Source of record

- GitHub issues are the durable source of record for work.
- Pull requests are the product-building and closure units.
- GitHub Projects, labels, checks, reviews, and branch rules are the visible control plane.
- Local OpenClaw lane state is execution state, not the durable source of record.

## Actors

- Pheidon: controller, orchestrator, approval/merge gate.
- Apollo: issue quality, scope clarity, backlog synthesis.
- Daedalus: implementation and substantive code repair.
- Ares: validation, adversarial review, test pressure.
- Hephaestus: CI, lockfiles, branch hygiene, mergeability, artifacts.
- Hermes: macOS/platform-native validation and special execution.

## Flow states

Canonical states:

1. `Intake`
2. `Ready for Planning`
3. `Ready for Implementation`
4. `Implementing`
5. `PR Open`
6. `Needs Review`
7. `Needs Repair`
8. `Repairing`
9. `Ready for Approval`
10. `Approved / Waiting Checks`
11. `Auto-merge Armed`
12. `Merged`
13. `Blocked - Human`
14. `Blocked - Infrastructure`
15. `Blocked - Scope`
16. `Paused`

### Release states

Release work uses the same GitHub-visible control plane, with the detailed release state machine defined in `docs/release-flow.md`.

Canonical release states include `Release Intake`, `Release Scope Locked`, `Release Branch Open`, `Release Prep`, `Preflight Running`, `Preflight Passed`, `Full Validation Running`, `Full Validation Passed`, `Tag Ready`, `Publish Approval Required`, `Publishing`, `Published`, `Postpublish Verification`, `Promoted`, `Release Closed`, the release-specific blocked states, and `Release Rolled Back / Superseded`.

Release actor responsibilities:

- Pheidon: release controller, approval gate, final publish decision.
- Apollo: release issue quality, scope lock, release notes, changelog quality.
- Daedalus: release fixes, version bumps, artifact build repair.
- Ares: adversarial validation, regression pressure, security/risk review.
- Hephaestus: CI, lockfiles, workflow health, artifact generation, evidence, publish mechanics.
- Hermes: platform-native validation where relevant, especially macOS/native packaging.

## Controller loop

The controller repeatedly:

1. inspects live GitHub state;
2. normalizes issues and PRs into one flow state;
3. chooses one next action;
4. assigns one current actor;
5. dispatches a worker only when autonomy policy permits;
6. validates worker output;
7. updates GitHub-visible state;
8. approves or arms auto-merge only when gates are satisfied;
9. advances to the next item.

## PR-first rule

Open PR clearance has priority over starting new implementation work.

During release freeze, PR-first still applies, but release-blocking PRs take priority over net-new feature work.

Priority order:

1. merge clean approved green PRs;
2. refresh/repair dirty, behind, conflicted, or failing PRs;
3. resolve requested changes;
4. review PRs needing review;
5. start new issues only when the PR queue is healthy.

## WIP limits

Default active WIP:

- Apollo: 1 scope/backlog/governance task.
- Ares: 1 validation/repair task.
- Daedalus: 1 implementation or substantive repair task.
- Hephaestus: 1 CI/mergeability/tooling task.
- Hermes: 1 platform-native task.

## Done definition

A unit of work is done only when:

- its linked PR is merged or explicitly closed as not planned;
- the linked issue is closed or intentionally reclassified;
- flow state is updated;
- no worker lane retains stale active state for it.

A release is done only when the release issue is closed or intentionally superseded, the release branch is merged or intentionally retained, the exact tag and GitHub Release or prerelease exist, release evidence is uploaded, preflight and validation run IDs are recorded, publish and postpublish evidence are recorded when applicable, channels are promoted when applicable, and no worker lane retains stale active state.

# OMT-Global Autonomous Flow Platform — Draft

## Core thesis

The current system has agents, repos, issues, and PRs, but the missing layer is an explicit **flow operating system**: a small, enforceable state machine that turns GitHub issue/PR state into worker action, review action, repair action, and merge action.

The next level is not primarily “more agents.” It is **clearer protocol, better queue physics, and executable governance**.

## Existing primitives

- `OMT-Global` is the base GitHub organization.
- `OMT-Global/bootstrap` is the repo/governance projector: it should stamp consistent repo structure, labels, issue forms, workflows, branch rules, and docs into each product repo.
- GitHub issues are the source of record for durable work.
- PRs are the product-building mechanism.
- Pheidon is the sovereign orchestrator and gate.
- Worker agents:
  - Apollo: scope, synthesis, backlog intelligence, product/issue honesty.
  - Ares: validation, adversarial review, failure reproduction, test/CI pressure.
  - Hephaestus: repo ops, CI/tooling, mergeability, artifacts, mechanical repairs.
  - Hermes: macOS/platform-native execution and special external/native validation.
  - Daedalus: implementation, feature repair, code changes.

## Problem observed

The workers get stuck because flow is implicit.

Common failure modes:
- a PR is opened but nobody owns the repair loop strongly enough;
- a branch goes `BEHIND` or `DIRTY` and sits;
- reviews request changes but the requested-change payload is not converted into a precise repair task;
- workers start new issue work while old PRs rot;
- local assignment files drift from live GitHub truth;
- “blocked” is treated as a terminal status instead of a routed state with a next actor;
- each lane has work, but the whole system lacks a conveyor clock.

## Recommended new layer: Org Flow repo

Create a small baseline repo, likely `OMT-Global/flow` or `OMT-Global/ops`, that defines the org-level execution protocol.

This repo should not replace `bootstrap`.

Separation of responsibilities:
- `bootstrap`: projects governance and repo scaffolding into product repos.
- `flow`: defines the org-wide state machine, lane contracts, project fields, labels, automation rules, and dashboards.
- product repos: contain actual issues, PRs, code, tests, docs, and repo-local manifests.

`bootstrap` should consume `flow` as the canonical policy source and apply the relevant pieces into each repo.

## GitHub should become the visible control plane

Use GitHub more deeply, not as a passive ticket bucket.

Recommended GitHub surfaces:

### 1. GitHub Projects v2 as the flow board

Create an org-level project with fields:
- `Flow State`
- `Owner Lane`
- `Current Actor`
- `Next Action`
- `Blocked Reason`
- `Priority`
- `WIP Slot`
- `Last Progress At`
- `Stale Since`
- `PR Link`
- `Merge Train Group`
- `Autonomy Class`

Suggested `Flow State` values:
- `Intake`
- `Ready for Planning`
- `Ready for Implementation`
- `Implementing`
- `PR Open`
- `Needs Review`
- `Needs Repair`
- `Repairing`
- `Ready for Approval`
- `Approved / Waiting Checks`
- `Auto-merge Armed`
- `Merged`
- `Blocked - Human`
- `Blocked - Infrastructure`
- `Blocked - Scope`
- `Paused`

### 2. Labels as machine-readable routing hints

Baseline labels:
- `lane:apollo`
- `lane:ares`
- `lane:daedalus`
- `lane:hephaestus`
- `lane:hermes`
- `state:needs-repair`
- `state:needs-review`
- `state:blocked-human`
- `state:blocked-infra`
- `state:ready-to-merge`
- `priority:p0` / `p1` / `p2` / `p3`
- `autonomy:safe` / `autonomy:review` / `autonomy:human-required`
- `kind:feature` / `kind:bug` / `kind:test` / `kind:ci` / `kind:docs` / `kind:governance`

Labels are not the source of truth alone, but they make state visible and queryable.

### 3. Issue forms as contracts

Every implementation issue should capture:
- acceptance criteria;
- validation commands;
- autonomy class;
- owning lane recommendation;
- expected PR closure behavior;
- dependencies/blockers;
- out-of-scope notes.

A weak issue becomes a stuck PR. A strong issue gives workers a closure target.

### 4. PR template as merge contract

Every PR should include:
- linked issue;
- summary;
- validation run;
- risk class;
- ownership lane;
- repair owner;
- review target;
- auto-merge eligibility.

### 5. Branch rulesets / merge queue / auto-merge

Use GitHub to enforce:
- required checks;
- no self-approval where possible;
- linear history or squash policy;
- PR author enables auto-merge by default where GitHub allows it;
- merge queue if repo churn is high enough to keep PRs constantly behind.

For Axiom specifically, a GitHub merge queue may be worth testing if `BEHIND` churn keeps destroying flow.

Author-owned auto-merge contract:
- The PR author is responsible for enabling auto-merge as soon as the PR exists and the repo permits it.
- Standard command: `gh pr merge <number-or-url> --auto --squash` after the PR body is complete and the branch has been pushed.
- If GitHub refuses auto-merge because the repo/plan/ruleset does not allow it, the author records the exact reason in `## Merge Automation`.
- If auto-merge is unsafe because the PR is human-gated, release-sensitive, or intentionally paused, the author records that reason and Pheidon owns the explicit merge decision.
- A healthy PR with no `autoMergeRequest` and no recorded exception is flow drift; route it back to the author/owning lane for metadata repair, not to John.

## The flow state machine

The autonomous loop should run as a controller, not as independent workers polling randomly.

Controller loop:
1. Inspect live GitHub issues/PRs.
2. Normalize each item into one flow state.
3. Decide the next actor.
4. Assign exactly one next action.
5. Dispatch worker if autonomous.
6. Validate worker output.
7. Update GitHub-visible state.
8. Verify the PR author armed auto-merge where possible; otherwise record the unavailable/unsafe reason and route fallback merge approval.
9. Close loop and advance next item.

Key principle: every item must have either:
- a next actor;
- a next action;
- a declared blocker;
- or be done.

No silent limbo.

## WIP and conveyor policy

Default WIP:
- Daedalus: 1 implementation or substantive repair.
- Ares: 1 validation/repair.
- Hephaestus: 1 CI/mergeability/tooling repair.
- Hermes: 1 platform-native task.
- Apollo: 1 scope/backlog/governance synthesis task.

PR-first rule:
- open PR repair/review/merge outranks new feature work.

A healthy conveyor should prefer:
1. merge clean approved PRs;
2. repair dirty/behind/failing PRs;
3. resolve requested changes;
4. review PRs needing review;
5. only then start new issues.

## Agent contracts

### Pheidon
- owns orchestration, gate, priority, and exception handling;
- runs the controller loop;
- converts ambiguous state into explicit next actions;
- approves or escalates.

### Apollo
- turns vague issues into executable contracts;
- detects scope drift between issue and PR;
- summarizes backlog health and consolidation opportunities;
- should not be the main code repair lane.

### Ares
- reproduces failures;
- writes or demands tests;
- validates repair claims;
- performs adversarial review.

### Hephaestus
- fixes CI, lockfiles, build tooling, mergeability, branch hygiene;
- owns mechanical repo operations when safe.

### Hermes
- performs macOS/native/platform validation;
- acts as special repair/overflow node;
- should not inherit generic backlog unless platform value exists.

### Daedalus
- implements features;
- resolves substantive review changes;
- repairs product logic.

## Autonomy classes

Every issue/PR should be classified:

### Class 0: Observe only
No mutation. Report or summarize.

### Class 1: Safe autonomous
Docs, tests, formatting, conflict refresh, non-risky CI fixes. May be run by lanes automatically.

### Class 2: Review-gated autonomous
Code changes allowed, but Pheidon/Ares/Athena review required before merge.

### Class 3: Human decision required
Architecture, security-sensitive, public API, data migration, external service writes, destructive actions.

### Class 4: Forbidden unattended
Money movement, credential exposure, destructive infra, unsafe external action.

## Do we need another baseline repo?

Yes, likely.

Recommended: create `OMT-Global/flow` as the org-level flow contract.

It should contain:
- `FLOW.md` — state machine and principles;
- `agents/*.md` — lane contracts;
- `schemas/issue-contract.schema.json`;
- `schemas/pr-contract.schema.json`;
- `github/project-fields.yaml`;
- `github/labels.yaml`;
- `github/issue-forms/*.yml`;
- `github/pr-template.md`;
- `policies/autonomy-classes.md`;
- `policies/merge-gate.md`;
- `dashboards/queries.md`;
- controller scripts or specs consumed by Pheidon/OpenClaw.

Then `bootstrap` should project the repo-local subset of that into every managed repo.

## Do we leverage more GitHub features?

Yes.

Highest-value GitHub features:
1. Org Projects v2 for flow state.
2. Labels for lane/state/autonomy routing.
3. Issue forms for executable work contracts.
4. PR templates for merge contracts.
5. Branch protection/rulesets for gates.
6. Auto-merge everywhere safe.
7. Merge queue for high-churn repos like Axiom if behind-state churn dominates.
8. GitHub Actions as event sensors that comment/update labels/project state.
9. CODEOWNERS only where they help; avoid accidental human bottlenecks.
10. Webhooks/GitHub App later, if polling becomes insufficient.

## Minimal next implementation

Phase 1: Write protocol.
- Create `OMT-Global/flow` or a local draft first.
- Define flow states, labels, issue/PR templates, autonomy classes.

Phase 2: Teach bootstrap.
- Add org-flow policy inputs to bootstrap.
- Generate labels, issue forms, PR template, and repo governance docs.
- Add doctor checks for missing governance surfaces.

Phase 3: Build Pheidon controller.
- One script/controller that classifies GitHub PRs/issues into flow states.
- Writes GitHub labels/project fields.
- Dispatches exactly one next action per item.
- Enforces WIP limits and PR-first rule.

Phase 4: Add worker heartbeats.
- Workers do not free-roam.
- Each worker asks: “What is my current assigned next action?”
- On completion, worker returns a structured result.

Phase 5: Add anti-stall watchdog.
- If no progress after N minutes, controller reclassifies:
  - retry;
  - reassign;
  - pause lane;
  - escalate to Pheidon/JT.

## Design principle

Autonomy is not agents doing more random work.

Autonomy is a system where every unit of work continuously has a truthful state, a valid next action, an accountable actor, and a safe gate to completion.

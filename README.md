# OMT-Global Flow

Org-level autonomous flow protocol for OMT-Global issues, PRs, worker lanes, and merge gates.

For the high-level relationship between `flow`, `bootstrap`, `.github`, individual repos, Pheidon, and worker lanes, see [OMT-Global Operating Map](docs/omt-global-operating-map.md).

## What Flow Defines

- A GitHub-visible state machine for issues, pull requests, checks, reviews, labels, and merge readiness.
- Worker lane contracts for Pheidon, Apollo, Daedalus, Ares, Hephaestus, and Hermes.
- Autonomy classes that decide when a worker may observe, patch, repair, or must escalate.
- PR-first queue policy so open review, repair, mergeability, and CI work outrank starting new issues.
- Merge-gate rules for linked issues, validation evidence, approvals, requested changes, checks, and auto-merge.
- Baseline schemas, issue forms, labels, project fields, dashboards, and policy docs that `bootstrap` can project into product repos.

## Repository Map

- [`FLOW.md`](FLOW.md) - concise protocol and controller loop.
- [`agents/`](agents/) - lane contracts for the named worker roles.
- [`policies/`](policies/) - autonomy, WIP, stall-handling, and merge-gate policy.
- [`schemas/`](schemas/) - issue and PR contract schemas.
- [`github/`](github/) - canonical labels, issue templates, project fields, and PR template inputs.
- [`dashboards/`](dashboards/) - saved query patterns for operational review.
- [`scripts/flow/inspect_repo_flow.py`](scripts/flow/inspect_repo_flow.py) - read-only-by-default inspector for repo flow metadata; see the [operator guide](docs/flow-inspector.md).
- [`docs/autonomous-flow-platform.md`](docs/autonomous-flow-platform.md) - design rationale and rollout plan.
- [`docs/omt-global-operating-map.md`](docs/omt-global-operating-map.md) - org-level ownership map.
- [`docs/policy-index.md`](docs/policy-index.md) - current policy authority, release, and implementation evidence.
- [`docs/public-repository-standard-gap-analysis.md`](docs/public-repository-standard-gap-analysis.md) - historical discovery record and links to remaining migration work.

## Controller Loop

The controller should repeatedly:

1. Inspect live GitHub issues and pull requests.
2. Normalize each item into one flow state.
3. Choose one next action and one accountable actor.
4. Dispatch a worker only when autonomy policy permits.
5. Validate worker output.
6. Update GitHub-visible state.
7. Arm auto-merge or route approval only when gates are satisfied.

## PR-First Queue Policy

Open PR clearance has priority over starting new implementation work:

1. Merge clean approved green PRs.
2. Refresh or repair dirty, behind, conflicted, or failing PRs.
3. Resolve requested changes.
4. Review PRs needing review.
5. Start new issues only when the PR queue is healthy.

## Validation

```sh
python -m json.tool schemas/issue-contract.schema.json >/dev/null
python -m json.tool schemas/pr-contract.schema.json >/dev/null
python -m py_compile scripts/flow/inspector_core.py scripts/flow/inspect_repo_flow.py
python -m unittest discover -s tests -v
```

Inspect a repository without mutating GitHub or local assignment state:

```sh
python scripts/flow/inspect_repo_flow.py --repo OMT-Global/flow --issues
```

The inspector requires explicit mutation flags and explicit output/assignment
paths. Review the proposed writes in the default report before following the
[apply examples](docs/flow-inspector.md#apply-reviewed-writes).

## Bootstrap Relationship

`flow` defines the operating protocol. `bootstrap` projects the relevant repo-local pieces into OMT-Global repositories through `project.bootstrap.yaml`, managed templates, labels, workflows, and GitHub policy. Update policy here first, then let bootstrap reconcile downstream repos deliberately.

## Project Identity

- Product name: `OMT-Global Flow`
- Repository: `OMT-Global/flow`
- Manifest: `project.bootstrap.yaml`
- Visibility: `public`
- Default branch: `main`
- Archetype: `generic-empty`

## Release Standard

The current immutable policy release is [`v1.0.1`](https://github.com/OMT-Global/flow/releases/tag/v1.0.1). Production consumers must pin an exact SemVer release or immutable commit SHA; `main` and floating compatibility aliases are discovery aids only and are never valid production policy references.

This repository uses release maturity level `simple`. Level 1 `simple` publishes immutable exact SemVer tags such as `v1.2.3` and may advance floating discovery aliases such as `v1.2` and `v1`. Level 2 `governed` adds preflight, full validation, explicit publish approval, postpublish verification, and release evidence.

Cut patch releases from `release/X.Y` branches when you maintain an older minor line. Cut new minor and major releases from `main`.

## Repository URL

- https://github.com/OMT-Global/flow

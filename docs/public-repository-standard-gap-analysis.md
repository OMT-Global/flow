# Public Repository Standard v1 gap analysis: Flow

> **Historical analysis — superseded for current status.** This document records the repository state reviewed on 2026-07-11. The implemented policy bundle, its immutable release, and the linked follow-up issues are the current evidence; the original findings below are preserved rather than rewritten.

## Implementation outcome

As of 2026-07-15, the policy-definition lanes identified here have landed:

| Lane | Current evidence |
|---|---|
| Vocabulary and policy bundle | [Issue #8](https://github.com/OMT-Global/flow/issues/8), merged by [PR #15](https://github.com/OMT-Global/flow/pull/15) |
| Executable transitions | [Issue #9](https://github.com/OMT-Global/flow/issues/9), merged by [PR #16](https://github.com/OMT-Global/flow/pull/16) |
| Contribution lifecycle and release contract | [Issues #10](https://github.com/OMT-Global/flow/issues/10) and [#12](https://github.com/OMT-Global/flow/issues/12), merged by [PR #17](https://github.com/OMT-Global/flow/pull/17) |
| Security and provenance | [Issue #11](https://github.com/OMT-Global/flow/issues/11), merged by [PR #18](https://github.com/OMT-Global/flow/pull/18) |
| Immutable policy publication | [v1.0.1](https://github.com/OMT-Global/flow/releases/tag/v1.0.1), verified under [issue #23](https://github.com/OMT-Global/flow/issues/23) |

The current source of truth is the [policy index](policy-index.md), which points to the canonical policy data, schemas, compatibility guidance, and accepted architecture decision. Remaining migration work is intentionally tracked outside this historical snapshot: [#13](https://github.com/OMT-Global/flow/issues/13) for Flow dogfooding, [#25](https://github.com/OMT-Global/flow/issues/25) for generated governance and operator guidance, and [#26](https://github.com/OMT-Global/flow/issues/26) for human-approved stewardship surfaces. This document's retirement is tracked by [#27](https://github.com/OMT-Global/flow/issues/27).

## Outcome

Flow has solid fragments for agent roles, autonomy, issue/PR work states, merge gates, and a governed release train. It does not yet provide the single versioned, publisher-neutral, machine-readable policy model required by Public Repository Standard v1. The safe migration is additive: establish vocabulary and schemas first, test them, publish an immutable policy release, then let Bootstrap consume it.

## Baseline reviewed

This analysis is based on `origin/main` at `b6d511e` on 2026-07-11. The review covered all policy documents, schemas, agent definitions, issue and PR templates, release documentation, the repository inspector, workflows, README/CONTRIBUTING guidance, and `project.bootstrap.yaml`.

## What Flow already defines

| Capability | Existing source | Assessment |
|---|---|---|
| Work intake and state movement | `FLOW.md`, issue templates, `schemas/issue-contract.schema.json` | Useful operational baseline; states are not one validated transition model. |
| Agent roles and separation | `agents/*.md`, `policies/autonomy-classes.md` | Roles and escalation exist, but independent material review and execute-and-notify semantics are incomplete. |
| Merge readiness | `policies/merge-gate.md`, PR template | Covers checks, reviews, issue state, and risk; missing DCO, PR-size, ADR, provenance, and generated-file gates. |
| Release train | `docs/release-flow.md`, `policies/release-policy.yaml` | Detailed states and evidence exist; version pinning and v1 readiness rules are incomplete. |
| Repository inspection | `scripts/flow/inspect_repo_flow.py` | Reports GitHub-visible work state; it is not a full conformance validator. |
| Policy projection boundary | `README.md`, `project.bootstrap.yaml` | Correctly states that Bootstrap projects policy, but Flow does not publish a consumable policy bundle. |

## Required gaps

| Standard area | Current gap | Required Flow outcome | Breaking or migration impact |
|---|---|---|---|
| Vocabulary and identity | Terms are spread across prose and use OMT-specific names. | Canonical IDs and definitions with configurable publisher metadata. | Additive initially; renamed terms need aliases. |
| Repository classes | Required `cli`, `library`, `service`, `infrastructure`, `github-action`, `specification`, and `documentation` classes are absent. | Class enum plus deviation and human-approval semantics. | Existing Bootstrap classes `application` and `tooling` need mapping. |
| Product maturity | No Experimental-to-Archived contract. | Six maturity levels with support and compatibility implications. | Must distinguish product maturity from current release automation maturity. |
| Work transitions | Workflow states exist primarily in prose. | Machine-readable allowed transitions, terminal states, blockers, and notification effects. | Existing labels and issue state names need compatibility mapping. |
| Material changes | Autonomy class 2 overlaps but is not the required list. | Canonical material-action definitions and notify-and-continue behavior. | Existing approval-heavy behavior may become notification-only. |
| Human hard stops | Escalation is broader and publisher/spend policy is not modeled. | Exact hard-stop categories and configurable spend threshold reference. | Narrowing approval gates is behaviorally material. |
| Independent review | Merge policy requires approvals but does not express author-agent separation for material changes. | Reviewer-lineage and separation-of-duties rules. | Requires new PR metadata and Bootstrap enforcement. |
| Testing and typing | No complete test-first, meaningful-boundary typing, or silent-error policy. | Normative quality expectations and enforceability levels. | Language profiles need staged rollout to avoid false failures. |
| ADR triggers | No normative ADR trigger list or exception link. | Trigger taxonomy, lifecycle, notification, and review rules. | Existing architecture decisions need inventory, not retroactive invention. |
| Security | No complete response targets or required scanning/provenance set. | Security tier semantics, response clocks, fork-safety, immutable action references, and reporting policy. | GitHub plan availability and existing workflow pins need migration handling. |
| Provenance | Release evidence exists, but agent-run public/private provenance semantics do not. | Public manifest fields, private-bundle rules, redaction, lineage, signing, and fail-closed conditions. | Schema must separate public data from private sink payloads. |
| PR and issue hygiene | No line thresholds, DCO, or 30/90-day aging contract. | Normative thresholds, exclusions, issue-ready contract, and aging states. | Large generated diffs need deterministic exclusions and exceptions. |
| Releases | Strong state model, but policy currently names `main` as a release source and allows floating tags. | Exact policy consumption, immutable release rules, Conventional Commits, and upgrade-review semantics. | Existing floating compatibility tags need an explicit exception or deprecation decision. |
| Exceptions | No typed temporary/permanent exception model. | Required fields, expiry, warning, failure, and permanent-exception ADR rule. | Existing deviations need discovery and temporary migration records. |
| Conformance | No severity/remediation vocabulary or class/profile conformance contract. | Rule IDs, severities, blocking behavior, remediation, and machine-readable results. | Bootstrap must map legacy findings to stable rule IDs. |

## Conflicts requiring explicit decisions

1. Bootstrap currently calls `application` and `tooling` repository classes; v1 does not. A migration map is required rather than silently reclassifying repositories.
2. Current release guidance advances floating `v1` and `v1.2` tags, while v1 calls exact tags immutable. The policy must clarify whether floating compatibility aliases remain permitted and never serve as policy pins.
3. Existing autonomy language sometimes escalates class-2 work for approval. V1 requires notification and continued execution except for hard stops and exceptions.
4. Flow's release state `Publish Approval Required` is broader than the v1 agent-controlled publication rule. It should represent configured environment protection or a hard stop, not a universal human gate.
5. Flow itself uses Bootstrap manifest v1 and references generic generated guidance. Dogfooding requires a supported manifest migration before generated artifacts change.

## Migration risks

- **Policy drift:** prose and schemas can disagree unless CI derives or cross-validates every view.
- **Label churn:** changing state names can orphan automation and dashboards; aliases and a transition window are required.
- **False conformance failures:** adopting strict requirements before Bootstrap can detect language/class context would block healthy repositories.
- **Review identity ambiguity:** GitHub accounts do not automatically prove distinct agent lineage; provenance must define the identity boundary.
- **Plan limitations:** some GitHub security features depend on repository and organization plans; unsupported controls need explicit blocked/waived results rather than silent success.
- **Version bootstrap loop:** Flow policy and Bootstrap projection versions must be compatible without either consuming the other's `main` branch.

## Independently mergeable implementation lanes

| Order | Flow lane | Concrete outcome | Dependencies |
|---|---|---|---|
| 1 | Vocabulary and policy bundle | Publisher-neutral v1 schema/data for classes, maturity, actions, hard stops, notifications, ADRs, exceptions, quality, security, provenance, releases, and conformance. | ADR-0001 |
| 2 | Transition validator | Deterministic work/release transition validation with positive and negative tests. | Lane 1 |
| 3 | Issue, PR, and lifecycle policy | PR-size/DCO/material-review gates plus implementation-ready issue and 30/90-day hygiene rules. | Lane 1 |
| 4 | Security and provenance semantics | Response targets, fork safety, manifest/private-bundle contract, redaction, signing, and failure rules. | Lane 1 |
| 5 | Compatibility and release | Legacy mapping, immutable policy release packaging, SemVer/Conventional Commit rules, and migration guide. | Lanes 1-4 |
| 6 | Flow dogfood | Upgrade Flow's manifest and validate projected artifacts in dry-run before apply. | Bootstrap resolver and conformance work |

The implementation-ready issue set is [#8 policy bundle](https://github.com/OMT-Global/flow/issues/8), [#9 transitions](https://github.com/OMT-Global/flow/issues/9), [#10 PR and issue lifecycle](https://github.com/OMT-Global/flow/issues/10), [#11 security and provenance semantics](https://github.com/OMT-Global/flow/issues/11), [#12 immutable release and migration](https://github.com/OMT-Global/flow/issues/12), and [#13 dogfood](https://github.com/OMT-Global/flow/issues/13). Each contains problem, outcome, scope, non-goals, acceptance criteria, tests, security, documentation, dependencies, and human decision points. Behavioral work begins with a failing test.

## Recommended first slice

Land only Lane 1 after this discovery PR. It creates the contract Bootstrap can consume without prematurely rewriting templates or enforcing incomplete controls.

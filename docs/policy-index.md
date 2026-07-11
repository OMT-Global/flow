# Policy index

Flow publishes the authoritative repository policy vocabulary and work-state semantics. Bootstrap consumes released policy and projects it into managed repositories.

## Public Repository Standard v1

- Canonical bundle: [`policies/public-repository-standard-v1.json`](../policies/public-repository-standard-v1.json)
- JSON Schema: [`schemas/public-repository-standard-v1.schema.json`](../schemas/public-repository-standard-v1.schema.json)
- Architecture decision: [`decisions/ADR-0001-public-repository-standard-v1.md`](decisions/ADR-0001-public-repository-standard-v1.md)
- Compatibility map: [`public-repository-standard-compatibility.md`](public-repository-standard-compatibility.md)
- Validator: `python3 scripts/flow/validate_policy_bundle.py`

Production consumers must use an exact released version or immutable commit SHA. They must not consume `main` or a floating compatibility tag as production policy.

## Rule identifiers

Stable `PRS-<AREA>-<NUMBER>` identifiers connect policy definitions to Bootstrap conformance output. The canonical bundle is the source of truth for the complete rule list and severity.

Flow policy changes are material actions. Notify maintainers in the governing issue or pull request, obtain independent agent review, and follow SemVer compatibility rules.

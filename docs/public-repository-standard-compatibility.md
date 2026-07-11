# Public Repository Standard v1 compatibility

The v1 policy bundle is additive to existing Flow documents. Existing documents remain operational guidance until they are migrated to validated views of the bundle.

## Legacy mappings

| Existing term | V1 meaning | Migration behavior |
|---|---|---|
| Bootstrap class `application` | `service` is the closest default | Require explicit confirmation; applications that are only CLIs or libraries must choose their actual class. |
| Bootstrap class `tooling` | `cli` is the closest default | Require explicit confirmation; infrastructure control planes may select `infrastructure`. |
| Flow autonomy class 2 | Material change with independent review | Notify and continue; human approval is required only for a defined hard stop or exception. |
| Release maturity | Release automation profile | Keep separate from product maturity (`experimental` through `archived`). |
| Floating `v1` or `v1.2` tag | Compatibility alias only | Never use as a production policy pin; exact versions and immutable SHAs are required. |

The aliases in the machine-readable bundle support migration diagnostics. They do not authorize silent reclassification.

## Compatibility rules

- Patch releases clarify or repair policy without changing normative meaning.
- Minor releases add backward-compatible vocabulary or rules and require independent agent review.
- Major releases may change normative meaning and require material notification, an ADR, and migration guidance.
- Bootstrap must reject an incompatible policy bundle before rendering or applying repository changes.
- Existing repository deviations must become explicit, scoped exceptions; permanent exceptions require an ADR and explicit human approval.

# Security and provenance policy

The machine-readable policy is [`policies/security-provenance-v1.json`](../policies/security-provenance-v1.json), and the public manifest contract is [`schemas/provenance-manifest-v1.schema.json`](../schemas/provenance-manifest-v1.schema.json).

## Threat assumptions

- Fork code, artifacts, metadata, and workflow output are untrusted.
- Prompts and tool output may contain credentials even when initial input did not.
- Repository writers, provenance writers, signers, and provenance readers are separate roles.
- Public manifests are attacker-visible and contain only redacted content and hashes.
- Private bundles remain sensitive after encryption; reads and writes use separate short-lived identities and audit events.
- A digest without verified signer identity and transparency evidence is not authentic provenance.

## Response and fork safety

Private reports are acknowledged within two business days and triaged within seven calendar days. Critical findings are remediated or contained within seven days; high findings within 30 days. Medium and low findings are best-effort, with coordinated disclosure after remediation.

Untrusted pull requests receive read-only tokens and no secrets. Privileged follow-up occurs only after trusted checkout and validation; `pull_request_target` never executes untrusted code.

## Public and private boundaries

Public manifests contain redacted prompts, exact hashes, tool/model identity, artifact and test evidence, workflows, independent reviewer lineage, the encrypted private-bundle digest, and a Sigstore DSSE envelope. Literal secrets are prohibited. Flow validates canonical payload binding and requires trusted signature and lineage verifier interfaces; Bootstrap must supply the actual Sigstore trust-root, certificate-identity, issuer, transparency-log, and signed-review verification. Missing verifiers fail closed.

Private bundles may contain filtered prompts and tool I/O, commands, file activity, tests, reviews, notifications, redaction logs, and the public-manifest digest. Secret-like values become typed placeholders such as `<secret:api-token:removed>` before encryption.

Repositories reference only a logical sink. The preferred S3-compatible sink uses customer-managed keys, versioning, Object Lock, lifecycle retention, access logs, short-lived OIDC, separate read/write roles, and audited reads. Physical bucket names and credentials never enter repository configuration.

Required capture or validation failure blocks a material merge and emits notification. Bypass requires a valid human-approved exception; permanent bypass requires an ADR and explicit human approval.

See the [data-flow diagram](diagrams/security-provenance-v1.mmd).

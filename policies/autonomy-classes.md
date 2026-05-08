# Autonomy Classes

## Class 0 — Observe only

No mutation. Inspect, summarize, or report.

## Class 1 — Safe autonomous

Low-risk local/repo changes such as docs, formatting, tests, branch refreshes, non-risky CI hygiene, and conflict repairs without design choices.

## Class 2 — Review-gated autonomous

Product code changes may be made by workers, but review and gate approval are required before merge.

## Class 3 — Human decision required

Architecture shifts, public API changes, security-sensitive behavior, data migrations, external service writes, or destructive/reversible-but-impactful operations.

## Class 4 — Forbidden unattended

Credential exposure, money movement, destructive infrastructure, unsafe external action, or bypassing safeguards.

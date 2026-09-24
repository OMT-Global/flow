# Security Policy

## Supported Surface

Security fixes target the `main` branch and the latest published Flow policy release. The current immutable release is [`v1.0.1`](https://github.com/OMT-Global/flow/releases/tag/v1.0.1). The response targets below are sourced from that released policy ([`policies/security-provenance-v1.json`](policies/security-provenance-v1.json); see [docs/security-provenance-policy.md](docs/security-provenance-policy.md)) and change only through a versioned policy change.

## Reporting a Vulnerability

Please do not disclose suspected vulnerabilities in a public issue, discussion, or pull request.

Use [GitHub private vulnerability reporting](https://github.com/OMT-Global/flow/security/advisories/new) for this repository (**Security** tab → **Advisories** → **Report a vulnerability**). Include:

- the affected repository, version, commit, or deployment;
- clear reproduction steps or a proof of concept;
- the likely impact and required preconditions;
- any suggested mitigation;
- whether the report is subject to a disclosure deadline.

If the private form is unavailable, open a public issue titled `Private security contact requested` without vulnerability details; maintainers will establish a confidential channel before accepting the report. Never include exploit details in public issues or discussions.

## Response Targets

OMT-Global maintainers are the accountable security-response authority for this repository. Per released Flow policy v1.0.1:

- Acknowledge a complete private report within 2 business days.
- Triage a confirmed report within 7 calendar days.
- Remediate or contain critical findings within 7 calendar days.
- Remediate high findings within 30 calendar days.
- Medium and low findings are remediated best-effort and scheduled by maintainers.
- Coordinate public disclosure with the reporter after remediation.

## Policy Guarantees

- Reporting never requires public disclosure of a vulnerability.
- This policy embeds no credentials or machine secrets, and the private reporting route requires none.
- Good-faith research that avoids privacy violations, service disruption, data destruction, and unauthorized access is welcome.

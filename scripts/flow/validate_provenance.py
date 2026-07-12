#!/usr/bin/env python3
"""Validate security policy and provenance using trusted verifier boundaries."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "policies" / "security-provenance-v1.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "provenance-manifest-v1.schema.json"
STANDARD_PATH = ROOT / "policies" / "public-repository-standard-v1.json"
BASE_VALIDATOR_PATH = ROOT / "scripts" / "flow" / "validate_policy_bundle.py"
PLACEHOLDER = re.compile(r"<secret:[a-z0-9-]+:removed>")
SECRET_PATTERNS = (
    re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)(?:password|passwd|api[_-]?key|token|client[_-]?secret)\s*(?:is|[=:])\s*(?!<secret:)[^\s]+"),
    re.compile(r"(?i)(?:password|passwd|api[_-]?key|token|client[_-]?secret)\s+(?!<secret:)[^\s]+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
SignatureVerifier = Callable[[dict[str, Any]], bool]
LineageVerifier = Callable[[dict[str, Any]], bool]


def load_base_validator():
    spec = importlib.util.spec_from_file_location("validate_policy_bundle", BASE_VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load base validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_policy(policy: Any, standard: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["$: expected an object"]
    errors: list[str] = []
    if set(policy) != {"version", "security", "publicProvenance", "privateProvenance", "failure", "rules"}:
        errors.append("$: expected complete canonical security and provenance policy")
    if policy.get("version") != "1.0.0":
        errors.append("$.version: expected 1.0.0")
    security = policy.get("security", {})
    if set(security) != {"requiredControls", "responseTargets", "forkSafety"}:
        errors.append("$.security: expected controls, response targets, and fork safety")
    if security.get("requiredControls") != standard.get("security", {}).get("requiredControls"):
        errors.append("$.security.requiredControls: must match authoritative standard")
    expected_response = dict(standard.get("security", {}).get("responseTargets", {}))
    expected_response.update({"mediumLow": "best-effort", "publicDisclosure": "coordinated-after-remediation"})
    if security.get("responseTargets") != expected_response:
        errors.append("$.security.responseTargets: required response clocks changed")
    if security.get("forkSafety") != {"untrustedPullRequestSecrets": "prohibited", "defaultTokenPermissions": "read-only", "privilegedFollowUpEvent": "workflow_run-after-trusted-checkout", "pullRequestTargetForUntrustedCode": "prohibited"}:
        errors.append("$.security.forkSafety: required fork safeguards changed")
    public = policy.get("publicProvenance", {})
    required_fields = ["schemaVersion", "runId", "repository", "issue", "pullRequest", "agent", "tools", "redactedPrompt", "promptHash", "inputArtifactHashes", "outputArtifactHashes", "commitHash", "testResults", "workflowReferences", "reviewerLineage", "privateBundleHash", "signature"]
    if public != {"manifestPath": "provenance/runs/<run-id>.json", "schemaPath": "schemas/provenance-manifest-v1.schema.json", "signatureAlgorithm": "sigstore-dsse", "signatureVerification": "certificate-identity-and-transparency-log-required", "requiredFields": required_fields}:
        errors.append("$.publicProvenance: required public contract changed")
    expected_private = {
        "allowedContent": ["filtered-prompts", "filtered-tool-inputs-outputs", "commands", "files-read-changed", "test-output", "review-comments", "material-notifications", "redaction-log", "public-manifest-digest"],
        "literalSecrets": "prohibited",
        "secretPlaceholderPattern": "<secret:<type>:removed>",
        "encryption": "required",
        "sinkReference": "logical-name-only",
        "preferredSink": {"protocol": "s3-compatible", "customerManagedKeys": True, "versioning": True, "objectLock": True, "lifecycleRetention": True, "accessLogging": True, "shortLivedOidc": True, "separateReadWritePermissions": True, "auditedReads": True},
    }
    if policy.get("privateProvenance") != expected_private:
        errors.append("$.privateProvenance: required private provenance boundary changed")
    if policy.get("failure") != {"materialRequiredCapture": "fail-closed", "ruleId": "PRS-PROV-001", "notificationRequired": True, "bypassRequiresApprovedException": True}:
        errors.append("$.failure: required fail-closed behavior changed")
    expected_rules = [
        {"id": "PRS-SECURITY-001", "severity": "blocking", "summary": "Required security controls and response targets are configured."},
        {"id": "PRS-PROV-SECRET-001", "severity": "blocking", "summary": "Literal secrets never enter public or private provenance."},
        {"id": "PRS-PROV-DIGEST-001", "severity": "blocking", "summary": "The public manifest binds the encrypted private bundle digest."},
        {"id": "PRS-PROV-LINEAGE-001", "severity": "blocking", "summary": "Material provenance records independent reviewer lineage."},
        {"id": "PRS-PROV-SIGNATURE-001", "severity": "blocking", "summary": "The public manifest has a verifiable signed envelope."},
        {"id": "PRS-PROV-001", "severity": "blocking", "summary": "Required capture failures block material merges."},
    ]
    rules = policy.get("rules")
    if rules != expected_rules:
        errors.append("$.rules: expected complete blocking security and provenance rules")
    return sorted(errors)


def validate_private_content(policy: dict[str, Any], content: str) -> list[str]:
    sanitized = PLACEHOLDER.sub("", content)
    if any(pattern.search(sanitized) for pattern in SECRET_PATTERNS):
        return ["PRS-PROV-SECRET-001: literal secret-like content detected; replace it with a typed placeholder"]
    return []


def validate_manifest(
    policy: dict[str, Any],
    schema: dict[str, Any],
    manifest: Any,
    private_bundle: bytes,
    *,
    signature_verifier: SignatureVerifier | None = None,
    lineage_verifier: LineageVerifier | None = None,
) -> list[str]:
    canonical_schema = json.loads(DEFAULT_SCHEMA.read_text())
    errors: list[str] = []
    if schema != canonical_schema:
        errors.append("PRS-PROV-SCHEMA-001: caller schema does not match canonical manifest schema")
    errors.extend(load_base_validator().validate_schema_value(manifest, canonical_schema, canonical_schema, "$"))
    if not isinstance(manifest, dict):
        return sorted(set(errors))
    errors.extend(validate_private_content(policy, json.dumps(manifest, sort_keys=True)))
    if manifest.get("privateBundleHash") != hashlib.sha256(private_bundle).hexdigest():
        errors.append("PRS-PROV-DIGEST-001: privateBundleHash does not match encrypted private bundle bytes")
    author = manifest.get("agent", {}).get("id")
    repository, pull_request, commit = manifest.get("repository"), manifest.get("pullRequest"), manifest.get("commitHash")
    valid_review = False
    for review in manifest.get("reviewerLineage", []):
        if isinstance(review, dict) and review.get("agentId") != author and review.get("state") == "approved" and review.get("repository") == repository and review.get("pullRequest") == pull_request and review.get("commitHash") == commit and lineage_verifier is not None and lineage_verifier(review):
            valid_review = True
    if not valid_review:
        errors.append("PRS-PROV-LINEAGE-001: trusted independent reviewer lineage bound to repository, pull request, and commit is required")
    envelope = manifest.get("signature", {})
    payload = dict(manifest)
    payload.pop("signature", None)
    expected_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload_matches = False
    try:
        payload_matches = base64.b64decode(envelope.get("payload", ""), validate=True) == expected_payload
    except (ValueError, TypeError):
        payload_matches = False
    cryptographically_verified = signature_verifier is not None and signature_verifier(envelope)
    if not payload_matches or not cryptographically_verified:
        errors.append("PRS-PROV-SIGNATURE-001: canonical DSSE payload and trusted cryptographic verification are required")
    return sorted(set(errors))


def evaluate_capture(policy: dict[str, Any], *, material: bool, capture_succeeded: bool, manifest_valid: bool) -> dict[str, Any]:
    if material and (not capture_succeeded or not manifest_valid):
        return {"allowed": False, "ruleId": "PRS-PROV-001", "remediation": "Restore required provenance capture and validate the signed public manifest before merge."}
    return {"allowed": True, "ruleId": None, "remediation": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text())
    standard = json.loads(STANDARD_PATH.read_text())
    errors = validate_policy(policy, standard)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"valid: {args.policy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

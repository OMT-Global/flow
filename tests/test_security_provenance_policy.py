from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "security-provenance-v1.json"
MANIFEST_SCHEMA_PATH = ROOT / "schemas" / "provenance-manifest-v1.schema.json"
VALIDATOR_PATH = ROOT / "scripts" / "flow" / "validate_provenance.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_provenance", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(private_bundle: bytes = b"encrypted-private-bundle") -> dict:
    value = {
        "schemaVersion": "1.0.0",
        "runId": "run:01JTEST",
        "repository": "example/repository",
        "issue": "issue:11",
        "pullRequest": "pr:18",
        "agent": {"id": "agent:author", "model": "model-name", "version": "model-version"},
        "tools": [{"name": "git", "version": "2.50"}],
        "redactedPrompt": "Implement <secret:api-token:removed>",
        "promptHash": "a" * 64,
        "inputArtifactHashes": {"input.txt": "b" * 64},
        "outputArtifactHashes": {"output.txt": "c" * 64},
        "commitHash": "d" * 40,
        "testResults": [{"name": "unit", "status": "passed", "evidence": "run:123"}],
        "workflowReferences": ["run:123"],
        "reviewerLineage": [{"agentId": "agent:reviewer", "state": "approved", "evidence": "pr:18#review", "repository": "example/repository", "pullRequest": "pr:18", "commitHash": "d" * 40, "reviewDigest": "f" * 64}],
        "privateBundleHash": hashlib.sha256(private_bundle).hexdigest(),
        "signature": {
            "payloadType": "application/vnd.omt.provenance-manifest.v1+json",
            "payload": "",
            "signatures": [{"keyid": "sigstore:key", "sig": base64.b64encode(b"signed-envelope").decode()}],
            "certificateIdentity": "https://github.com/example/workflow",
            "certificateIssuer": "https://token.actions.githubusercontent.com",
            "transparencyLogEntry": "https://rekor.example/entry/1",
        },
    }
    payload = dict(value); del payload["signature"]
    value["signature"]["payload"] = base64.b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).decode()
    return value


def signature_verifier(envelope: dict) -> bool:
    return envelope["signatures"][0]["sig"] == base64.b64encode(b"signed-envelope").decode() and envelope["certificateIdentity"] == "https://github.com/example/workflow"


def lineage_verifier(review: dict) -> bool:
    return review["reviewDigest"] == "f" * 64 and review["evidence"] == "pr:18#review"


class SecurityProvenancePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text())
        cls.schema = json.loads(MANIFEST_SCHEMA_PATH.read_text())
        cls.validator = load_validator()

    def test_policy_has_exact_response_clocks_and_security_controls(self) -> None:
        standard = json.loads((ROOT / "policies" / "public-repository-standard-v1.json").read_text())
        self.assertEqual(self.validator.validate_policy(self.policy, standard), [])

    def test_weakened_private_policy_and_rules_are_rejected(self) -> None:
        standard = json.loads((ROOT / "policies" / "public-repository-standard-v1.json").read_text())
        policy = json.loads(json.dumps(self.policy)); policy["privateProvenance"]["bucket"] = "s3://physical-bucket"
        self.assertNotEqual(self.validator.validate_policy(policy, standard), [])
        policy = json.loads(json.dumps(self.policy)); del policy["privateProvenance"]["allowedContent"]
        self.assertNotEqual(self.validator.validate_policy(policy, standard), [])
        policy = json.loads(json.dumps(self.policy)); policy["rules"][0]["summary"] = "unrelated"
        self.assertNotEqual(self.validator.validate_policy(policy, standard), [])

    def test_valid_manifest_binds_private_bundle_and_independent_reviewer(self) -> None:
        bundle = b"encrypted-private-bundle"
        self.assertEqual(self.validator.validate_manifest(self.policy, self.schema, manifest(bundle), bundle, signature_verifier=signature_verifier, lineage_verifier=lineage_verifier), [])

    def test_missing_required_field_fails(self) -> None:
        value = manifest(); del value["promptHash"]
        self.assertIn("$.promptHash: required property is missing", self.validator.validate_manifest(self.policy, self.schema, value, b"encrypted-private-bundle", signature_verifier=signature_verifier, lineage_verifier=lineage_verifier))

    def test_literal_secret_patterns_fail_public_and_private_content(self) -> None:
        value = manifest(); value["redactedPrompt"] = "Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz123456"
        errors = self.validator.validate_manifest(self.policy, self.schema, value, b"encrypted-private-bundle", signature_verifier=signature_verifier, lineage_verifier=lineage_verifier)
        self.assertIn("PRS-PROV-SECRET-001", " ".join(errors))
        self.assertEqual(
            self.validator.validate_private_content(self.policy, "password=hunter2"),
            ["PRS-PROV-SECRET-001: literal secret-like content detected; replace it with a typed placeholder"],
        )

    def test_typed_secret_placeholders_are_allowed(self) -> None:
        self.assertEqual(
            self.validator.validate_private_content(self.policy, "token=<secret:api-token:removed>"),
            [],
        )

    def test_private_bundle_digest_mismatch_fails(self) -> None:
        errors = self.validator.validate_manifest(self.policy, self.schema, manifest(), b"different", signature_verifier=signature_verifier, lineage_verifier=lineage_verifier)
        self.assertIn("PRS-PROV-DIGEST-001", " ".join(errors))

    def test_author_cannot_satisfy_reviewer_lineage(self) -> None:
        value = manifest(); value["reviewerLineage"][0]["agentId"] = "agent:author"
        errors = self.validator.validate_manifest(self.policy, self.schema, value, b"encrypted-private-bundle", signature_verifier=signature_verifier, lineage_verifier=lineage_verifier)
        self.assertIn("PRS-PROV-LINEAGE-001", " ".join(errors))

    def test_invalid_signature_envelope_fails(self) -> None:
        value = manifest(); value["signature"]["signatures"][0]["sig"] = base64.b64encode(b"forged-signature").decode()
        errors = self.validator.validate_manifest(self.policy, self.schema, value, b"encrypted-private-bundle", signature_verifier=signature_verifier, lineage_verifier=lineage_verifier)
        self.assertIn("PRS-PROV-SIGNATURE-001", " ".join(errors))

    def test_missing_trusted_verifiers_fails_closed(self) -> None:
        errors = self.validator.validate_manifest(self.policy, self.schema, manifest(), b"encrypted-private-bundle")
        self.assertIn("PRS-PROV-SIGNATURE-001", " ".join(errors))
        self.assertIn("PRS-PROV-LINEAGE-001", " ".join(errors))

    def test_weakened_caller_schema_is_rejected(self) -> None:
        errors = self.validator.validate_manifest(self.policy, {"type": "object"}, manifest(), b"encrypted-private-bundle", signature_verifier=signature_verifier, lineage_verifier=lineage_verifier)
        self.assertIn("PRS-PROV-SCHEMA-001", " ".join(errors))

    def test_common_secret_families_are_rejected(self) -> None:
        samples = ["aws_access_key_id=AKIAABCDEFGHIJKLMNOP", "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturevalue", "slack=xoxb-" + "1234567890-abcdefghijklmnop", "client_secret hunter2"]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertNotEqual(self.validator.validate_private_content(self.policy, sample), [])

    def test_required_capture_failure_blocks_material_merge(self) -> None:
        result = self.validator.evaluate_capture(
            self.policy, material=True, capture_succeeded=False, manifest_valid=False
        )
        self.assertEqual(result, {"allowed": False, "ruleId": "PRS-PROV-001", "remediation": "Restore required provenance capture and validate the signed public manifest before merge."})
        self.assertTrue(self.validator.evaluate_capture(self.policy, material=False, capture_succeeded=False, manifest_valid=False)["allowed"])


if __name__ == "__main__":
    unittest.main()

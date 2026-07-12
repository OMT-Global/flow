#!/usr/bin/env python3
"""Build and verify deterministic, offline-consumable Flow policy releases."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

RELEASE_FILES = (
    "policies/public-repository-standard-v1.json",
    "policies/transitions-v1.json",
    "policies/contribution-lifecycle-v1.json",
    "policies/security-provenance-v1.json",
    "schemas/public-repository-standard-v1.schema.json",
    "schemas/provenance-manifest-v1.schema.json",
    "schemas/issue-contract.schema.json",
    "schemas/pr-contract.schema.json",
    "docs/policy-index.md",
    "docs/public-repository-standard-compatibility.md",
    "docs/contribution-lifecycle-policy.md",
    "docs/security-provenance-policy.md",
    "docs/diagrams/policy-transitions-v1.mmd",
    "docs/diagrams/security-provenance-v1.mmd",
    "docs/policy-release-and-upgrades.md",
    "FLOW.md",
    "docs/release-flow.md",
    "policies/autonomy-classes.md",
    "policies/merge-gate.md",
    "policies/release-policy.yaml",
    "policies/stall-handling.md",
    "policies/wip-limits.md",
    "scripts/flow/validate_policy_bundle.py",
    "scripts/flow/validate_transition.py",
    "scripts/flow/evaluate_contribution.py",
    "scripts/flow/validate_provenance.py",
    "scripts/flow/build_policy_release.py",
)
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
IMMUTABLE_REFERENCE = re.compile(r"^(?:v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)|[0-9a-f]{40}|[0-9a-f]{64})$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def zip_entry(name: str, data: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info, data


def build_release(root: Path, output: Path, version: str) -> dict[str, str]:
    if not SEMVER.fullmatch(version):
        raise ValueError(f"invalid semantic version: {version}")
    output.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    contents: dict[str, bytes] = {}
    for relative in RELEASE_FILES:
        data = (root / relative).read_bytes()
        contents[relative] = data
        files[relative] = sha256(data)
    manifest = {
        "schemaVersion": "1.0.0",
        "policyVersion": version,
        "consumerReference": f"v{version}",
        "compatibility": {"flowMajor": 1, "minimumBootstrapMajor": 2},
        "files": files,
    }
    manifest_bytes = canonical_json(manifest)
    manifest_name = f"policy-release-v{version}.json"
    (output / manifest_name).write_bytes(manifest_bytes)
    verifier_path = output / "verify_policy_release.py"
    verifier_path.write_bytes((root / "scripts/flow/build_policy_release.py").read_bytes())
    archive_name = f"flow-policy-v{version}.zip"
    archive_path = output / archive_name
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name in sorted(contents):
            info, data = zip_entry(name, contents[name])
            archive.writestr(info, data)
        info, data = zip_entry("policy-release.json", manifest_bytes)
        archive.writestr(info, data)
    archive_hash = sha256(archive_path.read_bytes())
    manifest_hash = sha256(manifest_bytes)
    write_sums(output, archive_path, output / manifest_name, verifier_path)
    return {"archive": str(archive_path), "archiveHash": archive_hash, "manifestHash": manifest_hash}


def write_sums(output: Path, archive_path: Path, manifest_path: Path, verifier_path: Path) -> None:
    entries = (archive_path, manifest_path, verifier_path)
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha256(path.read_bytes())}  {path.name}\n" for path in entries)
    )


def verify_release(output: Path) -> list[str]:
    errors: list[str] = []
    manifests = sorted(output.glob("policy-release-v*.json"))
    archives = sorted(output.glob("flow-policy-v*.zip"))
    if len(manifests) != 1 or len(archives) != 1:
        return ["expected exactly one policy manifest and archive"]
    manifest_path, archive_path = manifests[0], archives[0]
    verifier_path = output / "verify_policy_release.py"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid manifest: {error}"]
    if not isinstance(manifest, dict):
        return ["invalid manifest: expected an object"]
    version_match = re.fullmatch(r"policy-release-v(.+)\.json", manifest_path.name)
    archive_match = re.fullmatch(r"flow-policy-v(.+)\.zip", archive_path.name)
    filename_version = version_match.group(1) if version_match else ""
    expected_manifest_keys = {"schemaVersion", "policyVersion", "consumerReference", "compatibility", "files"}
    if set(manifest) != expected_manifest_keys:
        errors.append("manifest shape mismatch")
    if not SEMVER.fullmatch(filename_version) or not archive_match or archive_match.group(1) != filename_version:
        errors.append("release filenames do not share a valid semantic version")
    if manifest.get("schemaVersion") != "1.0.0" or manifest.get("policyVersion") != filename_version:
        errors.append("manifest policyVersion does not match release filename")
    if manifest.get("consumerReference") != f"v{filename_version}" or validate_consumer_reference(str(manifest.get("consumerReference", ""))):
        errors.append("manifest consumerReference is not the matching immutable tag")
    if manifest.get("compatibility") != {"flowMajor": 1, "minimumBootstrapMajor": 2}:
        errors.append("manifest compatibility contract mismatch")
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict) or set(manifest_files) != set(RELEASE_FILES):
        errors.append("manifest inventory does not match canonical release inventory")
        manifest_files = {}
    sums = {}
    try:
        lines = (output / "SHA256SUMS").read_text().splitlines()
        for line in lines:
            digest, name = line.split("  ", 1)
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or name in sums:
                raise ValueError("invalid or duplicate checksum entry")
            sums[name] = digest
    except (OSError, ValueError) as error:
        return errors + [f"invalid SHA256SUMS: {error}"]
    expected_sum_names = {archive_path.name, manifest_path.name, verifier_path.name}
    if set(sums) != expected_sum_names:
        errors.append("SHA256SUMS inventory mismatch")
    if sums.get(archive_path.name) != sha256(archive_path.read_bytes()):
        errors.append("archive digest mismatch")
    if sums.get(manifest_path.name) != sha256(manifest_path.read_bytes()):
        errors.append("manifest digest mismatch")
    if not verifier_path.exists() or sums.get(verifier_path.name) != sha256(verifier_path.read_bytes()):
        errors.append("standalone verifier digest mismatch")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = [info.filename for info in archive.infolist()]
            for name in sorted(set(names)):
                if names.count(name) > 1:
                    errors.append(f"duplicate archive member: {name}")
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts:
                    errors.append(f"unsafe archive member: {name}")
            expected_members = set(RELEASE_FILES) | {"policy-release.json"}
            for name in sorted(set(names) - expected_members):
                errors.append(f"unexpected archive member: {name}")
            for name in sorted(expected_members - set(names)):
                errors.append(f"missing archive member: {name}")
            archived_manifest = archive.read("policy-release.json")
            if archived_manifest != manifest_path.read_bytes():
                errors.append("archived manifest mismatch")
            for name, expected in manifest_files.items():
                try:
                    actual = sha256(archive.read(name))
                except KeyError:
                    errors.append(f"missing archive file: {name}")
                    continue
                if actual != expected:
                    errors.append(f"file digest mismatch: {name}")
    except (zipfile.BadZipFile, KeyError, OSError) as error:
        errors.append(f"invalid archive: {error}")
    return sorted(errors)


def validate_consumer_reference(reference: str) -> list[str]:
    if not IMMUTABLE_REFERENCE.fullmatch(reference):
        return ["production policy references must use an exact vX.Y.Z release or immutable 40/64-character SHA"]
    return []


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"invalid semantic version: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def upgrade_gate(current: str, target: str) -> str:
    before, after = parse_version(current), parse_version(target)
    if after <= before:
        raise ValueError("target version must be newer than current version")
    if after[0] != before[0]:
        return "material-notification-and-adr"
    if after[1] != before[1]:
        return "independent-agent-review"
    return "tests-may-auto-merge"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.verify_only:
        build_release(args.root, args.output, args.version)
    errors = verify_release(args.output) if args.verify or args.verify_only else []
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"verified: {args.output}" if args.verify_only else f"built: {args.output}/flow-policy-v{args.version}.zip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

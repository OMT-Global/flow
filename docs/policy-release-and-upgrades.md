# Policy releases and upgrades

Flow policy is released when ready as a deterministic archive containing the authoritative policy data, schemas, compatibility guidance, and diagrams. Production consumers pin an exact `vX.Y.Z` release or immutable commit SHA. `main`, `latest`, `v1`, and `v1.2` are never production policy references.

Build and verify offline:

```text
python3 scripts/flow/build_policy_release.py \
  --output /tmp/flow-policy-v1.0.0 \
  --version 1.0.0 \
  --verify
```

The output contains a reproducible ZIP archive, a versioned release manifest with every source-file SHA-256 digest, and `SHA256SUMS` binding the archive and manifest. Bootstrap must verify those digests before parsing policy.

## Upgrade gates

- Patch: tests may auto-merge after conformance succeeds.
- Minor: independent agent review is required.
- Major: material notification, an ADR, and migration guidance are required.

Compatibility aliases may exist for discovery, but never replace immutable production pins. Post-publication verification downloads the release asset without repository state, verifies `SHA256SUMS`, validates the embedded manifest and every file digest, and records the workflow evidence on the release issue.

The standalone published verifier runs without a repository checkout:

```text
python3 verify_policy_release.py --output . --verify-only
```

Publish by enabling GitHub immutable releases, creating an exact tag, and dispatching `Publish Policy Release` against that tag with the governing issue and previous version. Minor releases require the number of an approved, merged PR whose merge commit is the tagged commit and whose approval is from a non-author reviewer. Major releases also require existing repository-relative ADR and migration-guide files at that commit. The workflow confirms the previous release, derives and enforces the upgrade gate, runs the full policy suite, notifies the issue and repository-dispatch channel, refuses overwrite, publishes all assets, downloads them into a clean directory, runs the standalone verifier, verifies GitHub reports the release immutable, and records postpublication evidence. GitHub's repository endpoint is the authoritative preflight check for immutable-release enforcement. [GitHub REST API](https://docs.github.com/en/rest/repos/repos#check-if-immutable-releases-are-enabled-for-a-repository)

Release publication is a material action. Notify through the governing release issue and configured mechanism, then continue when gates pass unless a defined human hard stop applies.

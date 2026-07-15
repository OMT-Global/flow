#!/usr/bin/env python3
"""Validate Flow's product-owned and projected repository contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]

GENERATED_FILE_PAIRS = (
    ("github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md"),
    ("github/ISSUE_TEMPLATE/implementation.yml", ".github/ISSUE_TEMPLATE/implementation.yml"),
    ("github/ISSUE_TEMPLATE/flow-blocker.yml", ".github/ISSUE_TEMPLATE/flow_blocker.yml"),
    ("github/ISSUE_TEMPLATE/release-train.yml", ".github/ISSUE_TEMPLATE/release_train.yml"),
)

REQUIRED_LOCAL_PATHS = (
    ".githooks/pre-commit",
    "docs/bootstrap/onboarding.md",
    "scripts/ci/run-fast-checks.sh",
    "scripts/ci/run-extended-validation.sh",
)

RUNNER_LABELS = ("self-hosted", "linux", "shell-only", "public")
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")


def check_generated_file_pairs(
    root: Path,
    pairs: Sequence[tuple[str, str]] = GENERATED_FILE_PAIRS,
) -> list[str]:
    errors: list[str] = []
    for canonical_name, projected_name in pairs:
        canonical = root / canonical_name
        projected = root / projected_name
        if not canonical.is_file():
            errors.append(f"missing canonical governance input: {canonical_name}")
            continue
        if not projected.is_file():
            errors.append(f"missing projected governance file: {projected_name}")
            continue
        if canonical.read_bytes() != projected.read_bytes():
            errors.append(
                f"generated governance drift: {canonical_name} != {projected_name}"
            )
    return errors


def markdown_files(root: Path) -> Iterable[Path]:
    yield from sorted(root.glob("*.md"))
    yield from sorted((root / "docs").rglob("*.md"))


def check_markdown_links(root: Path) -> list[str]:
    errors: list[str] = []
    for document in markdown_files(root):
        for raw_target in MARKDOWN_LINK.findall(document.read_text()):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("#", "https://", "http://", "mailto:")):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if path_text and not (document.parent / path_text).exists():
                errors.append(
                    f"missing Markdown target in {document.relative_to(root)}: {path_text}"
                )
    return errors


def check_required_paths(root: Path) -> list[str]:
    return [
        f"operator guidance target is missing: {path}"
        for path in REQUIRED_LOCAL_PATHS
        if not (root / path).exists()
    ]


def check_runner_contract(root: Path) -> list[str]:
    errors: list[str] = []
    workflow = (root / ".github/workflows/ci.yml").read_text()
    runner_block = re.search(
        r"(?ms)^  ci-gate:.*?^    runs-on:\s*\n((?:^      - [^\n]+\n)+)",
        workflow,
    )
    if runner_block is None:
        errors.append("CI Gate does not declare a list-form runner selector")
    else:
        labels = tuple(
            line.removeprefix("      - ").strip()
            for line in runner_block.group(1).splitlines()
        )
        if labels != RUNNER_LABELS:
            errors.append(
                f"CI Gate runner labels {labels!r} do not match {RUNNER_LABELS!r}"
            )

    documented_selector = f"[{', '.join(RUNNER_LABELS)}]"
    for path in ("AGENTS.md", "docs/bootstrap/onboarding.md"):
        if documented_selector not in (root / path).read_text():
            errors.append(f"{path} does not document runner selector {documented_selector}")

    manifest = (root / "project.bootstrap.yaml").read_text()
    if "runnerPolicy: hybrid-safe" not in manifest:
        errors.append("project.bootstrap.yaml must declare ci.runnerPolicy: hybrid-safe")

    actionlint = (root / ".github/actionlint.yaml").read_text()
    for label in RUNNER_LABELS:
        if f"    - {label}\n" not in actionlint:
            errors.append(f"actionlint is missing custom runner label: {label}")
    return errors


def check_release_guidance(root: Path) -> list[str]:
    errors: list[str] = []
    readme = (root / "README.md").read_text()
    release_guide = (root / "docs/policy-release-and-upgrades.md").read_text()
    if "Production consumers must pin an exact SemVer release or immutable commit SHA" not in readme:
        errors.append("README must require an exact immutable production policy pin")
    if "Compatibility aliases may exist for discovery, but never replace immutable production pins" not in release_guide:
        errors.append("release guidance must limit floating aliases to discovery")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    checks = (
        check_generated_file_pairs,
        check_markdown_links,
        check_required_paths,
        check_runner_contract,
        check_release_guidance,
    )
    return [error for check in checks for error in check(root)]


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("repository contract valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

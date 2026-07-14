#!/usr/bin/env python3
"""Inspect Flow state safely; GitHub and assignment writes require explicit flags."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inspector_core import (
    LABEL_SPECS,
    classify_issue,
    classify_pr,
    default_assignments,
    plan_label_changes,
    plan_repair_dispatch,
)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(cmd, text=True, capture_output=True)
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or f"command failed: {cmd!r}")
    return completed


def gh_json(args: list[str]) -> Any:
    return json.loads(run(["gh", *args]).stdout)


def maintenance_gate(path: Path) -> None:
    completed = run(
        ["bash", str(path), "flow-inspect", "inspect_repo_flow", "Maintenance active, queued flow inspection."],
        check=False,
    )
    if completed.returncode:
        print(completed.stdout or completed.stderr, end="")
        raise SystemExit(10)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_label(repo: str, name: str) -> None:
    color, description = LABEL_SPECS.get(name, ("d9d9d9", "OMT-Global flow label."))
    completed = run(
        ["gh", "label", "create", name, "--repo", repo, "--color", color, "--description", description],
        check=False,
    )
    if completed.returncode and "already exists" not in (completed.stderr + completed.stdout):
        probe = run(["gh", "label", "list", "--repo", repo, "--search", name, "--json", "name"], check=False)
        if probe.returncode or name not in probe.stdout:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


def apply_labels(
    repo: str,
    items: list[dict[str, Any]],
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    changes = plan_label_changes(items, max_items=max_items)
    for label in sorted({label for change in changes for label in change["add"]}):
        ensure_label(repo, label)
    for change in changes:
        command = [
            "gh",
            "pr" if change["kind"] == "pr" else "issue",
            "edit",
            str(change["number"]),
            "--repo",
            repo,
        ]
        if change["add"]:
            command.extend(["--add-label", ",".join(change["add"])])
        if change["remove"]:
            command.extend(["--remove-label", ",".join(change["remove"])])
        run(command)
    return {"count": len(changes), "items": changes}


def load_assignments(path: Path) -> dict[str, Any]:
    if path.exists():
        parsed = json.loads(path.read_text())
        if not isinstance(parsed, dict):
            raise ValueError(f"{path} must contain a JSON object")
        return parsed
    return default_assignments()


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def dispatch_repairs(
    repo: str,
    prs: list[dict[str, Any]],
    path: Path,
    *,
    max_items: int,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            assignments = load_assignments(path)
            updated, added = plan_repair_dispatch(repo, prs, assignments, max_items=max_items)
            if added:
                atomic_write_json(path, updated)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return {"count": len(added), "path": str(path), "items": added}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect open GitHub work and report proposed Flow state changes. "
            "The default mode is read-only; mutation requires --apply-labels or --dispatch-repairs."
        )
    )
    parser.add_argument("--repo", required=True, help="GitHub repository in OWNER/NAME form")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true", help="print the complete JSON report to stdout")
    parser.add_argument("--json-out", type=Path, help="write the report atomically to this explicit path")
    parser.add_argument("--issues", action="store_true", help="include open issues as well as pull requests")
    parser.add_argument(
        "--maintenance-gate",
        type=Path,
        help="run this explicitly configured maintenance-gate script before inspection",
    )
    parser.add_argument(
        "--apply-labels",
        action="store_true",
        help="MUTATING: reconcile Flow state/lane labels on GitHub",
    )
    parser.add_argument("--label-limit", type=int, help="maximum items to mutate with --apply-labels")
    parser.add_argument(
        "--dispatch-repairs",
        action="store_true",
        help="MUTATING: write Needs Repair PRs to the configured assignment store",
    )
    parser.add_argument("--dispatch-limit", type=int, default=10)
    parser.add_argument(
        "--assignments",
        type=Path,
        help="explicit repair assignment JSON path; required by --dispatch-repairs",
    )
    args = parser.parse_args(argv)
    if args.dispatch_repairs and args.assignments is None:
        parser.error("--dispatch-repairs requires --assignments")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.maintenance_gate:
        maintenance_gate(args.maintenance_gate)

    prs = gh_json(
        [
            "pr",
            "list",
            "--repo",
            args.repo,
            "--state",
            "open",
            "--limit",
            str(args.limit),
            "--json",
            "number,title,url,isDraft,author,headRefName,mergeStateStatus,reviewDecision,statusCheckRollup,autoMergeRequest,latestReviews,labels,updatedAt",
        ]
    )
    pr_items = [classify_pr(pr) for pr in prs]
    issue_items: list[dict[str, Any]] = []
    if args.issues:
        issues = gh_json(
            [
                "issue",
                "list",
                "--repo",
                args.repo,
                "--state",
                "open",
                "--limit",
                str(args.limit),
                "--json",
                "number,title,url,labels,assignees,updatedAt,body",
            ]
        )
        issue_items = [classify_issue(issue) for issue in issues]

    sorted_prs = sorted(pr_items, key=lambda item: item["number"], reverse=True)
    sorted_issues = sorted(issue_items, key=lambda item: item["number"], reverse=True)
    all_items = [*sorted_prs, *sorted_issues]
    counts = Counter(item["flowState"] for item in all_items)
    proposed_assignments = load_assignments(args.assignments) if args.assignments else default_assignments()
    _, proposed_dispatches = plan_repair_dispatch(
        args.repo,
        sorted_prs,
        proposed_assignments,
        max_items=args.dispatch_limit,
    )
    proposed_writes = {
        "labels": plan_label_changes(all_items, max_items=args.label_limit),
        "dispatch": proposed_dispatches,
    }

    write_results = {}
    if args.apply_labels:
        write_results["labels"] = apply_labels(args.repo, all_items, max_items=args.label_limit)
    if args.dispatch_repairs:
        write_results["dispatch"] = dispatch_repairs(
            args.repo,
            sorted_prs,
            args.assignments,
            max_items=args.dispatch_limit,
        )

    report = {
        "repo": args.repo,
        "generatedAt": now(),
        "mode": "apply" if write_results else "read-only",
        "counts": dict(sorted(counts.items())),
        "proposedWrites": proposed_writes,
        "writeResults": write_results,
        "prs": sorted_prs,
        "issues": sorted_issues,
    }
    if args.json_out:
        atomic_write_json(args.json_out, report)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print(f"Flow inspection for {args.repo} (mode: {report['mode']})")
    for state, count in sorted(counts.items()):
        print(f"- {state}: {count}")
    print("\nTop PR actions:")
    for item in sorted_prs[:20]:
        print(
            f"- PR #{item['number']}: {item['flowState']} -> {item['nextActor']}: "
            f"{item['nextAction']} ({', '.join(item['reasons'])})"
        )
    print("\nProposed writes (not applied unless a MUTATING flag was supplied):")
    print(json.dumps(proposed_writes, indent=2))
    if write_results:
        print("\nApplied writes:")
        print(json.dumps(write_results, indent=2))
    if args.json_out:
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()

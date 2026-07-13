#!/usr/bin/env python3
"""Evaluate evidence-bearing pull request and issue lifecycle records."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "policies" / "contribution-lifecycle-v1.json"
STANDARD_PATH = ROOT / "policies" / "public-repository-standard-v1.json"
EVIDENCE_PATTERN = re.compile(r"^(?:https?://\S+|(?:issue|pr|run):[^\s:#@]+(?:[#@]\S+)?)$")
AGENT_PATTERN = re.compile(r"^agent:[a-z0-9][a-z0-9-]*$")
DCO_PATTERN = re.compile(r"^Signed-off-by: (?P<name>.+) <(?P<email>[^<>\s]+@[^<>\s]+)>$")
PLACEHOLDER_DCO_IDENTITIES = {
    ("your name", "you@example.com"),
    ("your name", "your.email@example.com"),
}
TRAILER_PATTERN = re.compile(r"^[A-Za-z0-9-]+: .+$")
HUMAN_PATTERN = re.compile(r"^human:[a-z0-9][a-z0-9-]*$")


def evidence(value: Any) -> bool:
    return isinstance(value, str) and bool(EVIDENCE_PATTERN.fullmatch(value.strip()))


def pr_reference(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"pr:[^\s:#@]+", value.strip()))


def bound_pr_evidence(value: Any, pr_id: str) -> bool:
    return isinstance(value, str) and value.strip().startswith((f"{pr_id}#", f"{pr_id}@")) and evidence(value)


def valid_dco_trailer(value: str) -> bool:
    match = DCO_PATTERN.fullmatch(value)
    if match is None:
        return False
    identity = (match["name"].strip().casefold(), match["email"].strip().casefold())
    return identity not in PLACEHOLDER_DCO_IDENTITIES


def validate_policy(policy: Any, standard: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["$: expected an object"]
    errors: list[str] = []
    if set(policy) != {"version", "pullRequest", "issue", "externalContributions", "rules"}:
        errors.append("$: expected the complete canonical policy surface")
    if policy.get("version") != "1.0.0":
        errors.append("$.version: expected 1.0.0")
    pr = policy.get("pullRequest", {})
    issue = policy.get("issue", {})
    external = policy.get("externalContributions", {})
    expected_pr = standard.get("quality", {}).get("pullRequestChangedLines")
    if pr.get("changedLines") != expected_pr:
        errors.append("$.pullRequest.changedLines: must match the authoritative standard")
    exact = {
        "dco": {"required": True, "version": "1.1", "scope": "commits-in-pull-request"},
        "mergeMethod": "squash-only", "linearHistory": True, "deleteBranchAfterMerge": True,
        "materialReview": {"required": True, "minimumIndependentApprovals": 1, "authorAgentMayNotSatisfyReview": True, "unclassifiedRequiresIndependentReview": True},
    }
    if set(pr) != {"changedLines", "exclusionPatterns", "materialPathTriggers", "dco", "titlePattern", "mergeMethod", "linearHistory", "deleteBranchAfterMerge", "materialReview"}:
        errors.append("$.pullRequest: unexpected or missing property")
    for key, value in exact.items():
        if pr.get(key) != value:
            errors.append(f"$.pullRequest.{key}: required policy value was weakened or changed")
    expected_exclusions = {
        "generated": ["dist/**", "build/**", "**/dist/**", "**/build/**", "**/*.generated.*", "**/generated/**"],
        "lockfile": ["package-lock.json", "**/package-lock.json", "pnpm-lock.yaml", "**/pnpm-lock.yaml", "yarn.lock", "**/yarn.lock", "Cargo.lock", "**/Cargo.lock", "uv.lock", "**/uv.lock", "Podfile.lock", "**/Podfile.lock"],
        "fixture": ["fixtures/**", "**/fixtures/**", "testdata/**", "**/testdata/**"],
        "vendored": ["vendor/**", "**/vendor/**", "third_party/**", "**/third_party/**"],
    }
    if pr.get("exclusionPatterns") != expected_exclusions:
        errors.append("$.pullRequest.exclusionPatterns: required deterministic patterns changed")
    expected_triggers = {
        "schemas/**": "public-api-change",
        "migrations/**": "database-migration",
        ".github/workflows/**": "repository-settings-change",
        "package.json": "runtime-dependency-addition",
        "**/package.json": "runtime-dependency-addition",
        "pyproject.toml": "runtime-dependency-addition",
        "**/pyproject.toml": "runtime-dependency-addition",
        "Cargo.toml": "runtime-dependency-addition",
        "**/Cargo.toml": "runtime-dependency-addition",
        "go.mod": "runtime-dependency-addition",
        "**/go.mod": "runtime-dependency-addition",
    }
    if pr.get("materialPathTriggers") != expected_triggers:
        errors.append("$.pullRequest.materialPathTriggers: required material triggers changed")
    if not isinstance(pr.get("titlePattern"), str) or pr["titlePattern"] != "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\\([a-z0-9._/-]+\\))?!?: .+":
        errors.append("$.pullRequest.titlePattern: required Conventional title pattern changed")
    if issue.get("inactiveReviewDays") != 30 or issue.get("closeOrRescopeDays") != 90:
        errors.append("$.issue: aging clocks must be 30 and 90 days")
    expected_field_types = {
        "issueKind": "issue-kind", "problem": "string", "desiredOutcome": "string", "scope": "non-empty-array",
        "nonGoals": "non-empty-array", "acceptanceCriteria": "non-empty-array",
        "testExpectations": "string", "securityImplications": "string",
        "documentationImplications": "string", "dependencies": "non-empty-array",
        "humanDecisionPoints": "non-empty-array",
    }
    field_types = issue.get("implementationReadyFieldTypes")
    if field_types != expected_field_types or issue.get("implementationReadyFields") != list(expected_field_types):
        errors.append("$.issue: implementation-ready fields and types must be complete and ordered")
    if set(issue) != {"implementationReadyFields", "implementationReadyFieldTypes", "inactiveReviewDays", "closeOrRescopeDays", "credibleNextActionPreservesIssue", "speculativeMultiYearRoadmapsProhibited"}:
        errors.append("$.issue: unexpected or missing property")
    if issue.get("credibleNextActionPreservesIssue") is not True or issue.get("speculativeMultiYearRoadmapsProhibited") is not True:
        errors.append("$.issue: lifecycle safeguards changed")
    if external != {"issuesAllowed": True, "pullRequestsAllowed": True, "maintainerGatesRequired": True, "forkSafeWorkflowsRequired": True}:
        errors.append("$.externalContributions: required external contribution safeguards changed")
    expected_rule_objects = [
        {"id": "PRS-PR-SIZE-001", "severity": "blocking", "remediation": "Split the pull request or link a valid approved exception."},
        {"id": "PRS-DCO-001", "severity": "blocking", "remediation": "Add a DCO 1.1 Signed-off-by trailer to each contributed commit."},
        {"id": "PRS-PR-TITLE-001", "severity": "blocking", "remediation": "Use a Conventional Commit-formatted pull request title."},
        {"id": "PRS-MATERIAL-001", "severity": "blocking", "remediation": "Obtain approval from an agent other than the author agent."},
        {"id": "PRS-ISSUE-READY-001", "severity": "blocking", "remediation": "Complete every implementation-ready issue field."},
        {"id": "PRS-ISSUE-AGING-001", "severity": "warning", "remediation": "Review at 30 days and close or rescope at 90 days without a credible next action."},
    ]
    rules = policy.get("rules")
    if rules != expected_rule_objects:
        errors.append("$.rules: expected complete canonical rule definitions")
    return sorted(errors)


def mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def classify_path(policy: dict[str, Any], path: str) -> str | None:
    normalized = path.replace("\\", "/")
    for kind, patterns in policy["pullRequest"]["exclusionPatterns"].items():
        if any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns):
            return kind
    return None


def valid_exception(value: Any, *, today: str, pr_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    required = {"id", "policy", "scope", "rationale", "approvedBy", "approvalEvidence", "issue", "expires"}
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required):
        return False
    if value["policy"] != "quality.pullRequests.maximumChangedLines" or value["scope"] != pr_id:
        return False
    if not HUMAN_PATTERN.fullmatch(value["approvedBy"].strip().lower()) or not bound_pr_evidence(value["approvalEvidence"], pr_id) or not re.fullmatch(r"issue:[^\s:#@]+", value["issue"]):
        return False
    try:
        return date.fromisoformat(value["expires"]) >= date.fromisoformat(today)
    except ValueError:
        return False


def evaluate_pr(policy: dict[str, Any], standard: dict[str, Any], pull_request: Any, *, today: str = "2026-07-11") -> dict[str, Any]:
    pr = mapping(pull_request, "pull request")
    author = mapping(pr.get("author"), "author")
    pr_id = pr.get("prId")
    if not pr_reference(pr_id):
        raise ValueError("prId must be a resolvable pull request reference")
    if not isinstance(author.get("agentId"), str) or not AGENT_PATTERN.fullmatch(author["agentId"].strip().lower()) or not bound_pr_evidence(author.get("evidence"), pr_id):
        raise ValueError("author.agentId and author.evidence must identify canonical lineage")
    author_id = author["agentId"].strip().lower()
    files = pr.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("files must be a non-empty array")
    effective = 0
    excluded: dict[str, int] = {}
    for index, raw_file in enumerate(files):
        item = mapping(raw_file, f"files[{index}]")
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"files[{index}].path must be non-empty")
        counts = []
        for field in ("additions", "deletions"):
            count = item.get(field)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError(f"files[{index}].{field} must be a non-negative integer")
            counts.append(count)
        changed = sum(counts)
        kind = classify_path(policy, path)
        if kind:
            excluded[kind] = excluded.get(kind, 0) + changed
        else:
            effective += changed
    blocking: list[str] = []
    warnings: list[str] = []
    limits = policy["pullRequest"]["changedLines"]
    if effective > limits["blockAbove"]:
        size_class = "blocking"
        if not valid_exception(pr.get("exception"), today=today, pr_id=pr_id):
            blocking.append("PRS-PR-SIZE-001")
    elif effective > limits["warningAbove"]:
        size_class = "warning"; warnings.append("PRS-PR-SIZE-001")
    elif effective < limits["targetBelow"]:
        size_class = "target"
    else:
        size_class = "normal"
    commits = pr.get("commits")
    if not isinstance(commits, list) or not commits:
        raise ValueError("commits must be a non-empty array")
    dco_failures = []
    for index, commit in enumerate(commits):
        item = mapping(commit, f"commits[{index}]")
        sha, message = item.get("sha"), item.get("message")
        lines = message.rstrip().splitlines() if isinstance(message, str) and message.rstrip() else []
        trailers = []
        for line in reversed(lines):
            if TRAILER_PATTERN.fullmatch(line): trailers.append(line)
            else: break
        if not isinstance(sha, str) or not sha or not any(valid_dco_trailer(line) for line in trailers):
            dco_failures.append(sha if isinstance(sha, str) and sha else f"index:{index}")
    if dco_failures:
        blocking.append("PRS-DCO-001")
    title = pr.get("title")
    if not isinstance(title, str) or not re.fullmatch(policy["pullRequest"]["titlePattern"], title):
        blocking.append("PRS-PR-TITLE-001")
    classification = mapping(pr.get("materialClassification"), "materialClassification")
    digest = classification.get("inputDigest")
    digest_payload = {"prId": pr_id, "files": files, "commits": commits}
    expected_digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if set(classification) != {"actions", "evidence", "classifierVersion", "prId", "inputDigest"} or classification.get("classifierVersion") != "v1" or classification.get("prId") != pr_id or not bound_pr_evidence(classification.get("evidence"), pr_id) or digest != expected_digest:
        raise ValueError("materialClassification requires v1, matching prId, input digest, and bound evidence")
    actions = classification.get("actions")
    if not isinstance(actions, list):
        raise ValueError("materialActions must be an explicit array")
    unknown = sorted(set(actions) - set(standard["materialActions"]))
    if unknown:
        raise ValueError(f"unknown material action: {', '.join(unknown)}")
    triggered = {
        action for path_pattern, action in policy["pullRequest"]["materialPathTriggers"].items()
        if any(fnmatch.fnmatch(item["path"].replace("\\", "/"), path_pattern) for item in files)
    }
    missing_actions = sorted(triggered - set(actions))
    if missing_actions:
        raise ValueError(f"missing required material actions: {', '.join(missing_actions)}")
    approvals = pr.get("approvals")
    if not isinstance(approvals, list):
        raise ValueError("approvals must be an array")
    independent = set()
    for index, approval in enumerate(approvals):
        item = mapping(approval, f"approvals[{index}]")
        agent_id = item.get("agentId")
        normalized = agent_id.strip().lower() if isinstance(agent_id, str) else ""
        if AGENT_PATTERN.fullmatch(normalized) and normalized != author_id and item.get("state") == "approved" and bound_pr_evidence(item.get("evidence"), pr_id):
            independent.add(normalized)
    review_required = bool(actions) or policy["pullRequest"]["materialReview"]["unclassifiedRequiresIndependentReview"]
    if review_required and len(independent) < policy["pullRequest"]["materialReview"]["minimumIndependentApprovals"]:
        blocking.append("PRS-MATERIAL-001")
    return {"effectiveChangedLines": effective, "excludedLinesByKind": excluded, "sizeClassification": size_class, "dcoFailures": dco_failures, "blockingRuleIds": sorted(set(blocking)), "warningRuleIds": sorted(set(warnings))}


def evaluate_issue(policy: dict[str, Any], issue: Any, *, inactive_days: int, next_action: Any, today: str = "2026-07-11") -> dict[str, Any]:
    item = mapping(issue, "issue")
    if not isinstance(inactive_days, int) or isinstance(inactive_days, bool) or inactive_days < 0:
        raise ValueError("inactive_days must be a non-negative integer")
    field_types = policy["issue"]["implementationReadyFieldTypes"]
    missing, invalid = [], []
    for field, expected in field_types.items():
        value = item.get(field)
        if value is None:
            missing.append(field)
        elif expected == "string" and (not isinstance(value, str) or not value.strip()):
            invalid.append(field)
        elif expected == "non-empty-array" and (not isinstance(value, list) or not value):
            invalid.append(field)
        elif expected == "issue-kind" and value not in ("implementation", "roadmap", "dependency", "maintenance"):
            invalid.append(field)
    next_valid = False
    if isinstance(next_action, dict):
        outcome = next_action.get("outcome")
        dependency = next_action.get("dependency")
        checkpoint = next_action.get("checkpoint")
        try:
            future_checkpoint = isinstance(checkpoint, str) and date.fromisoformat(checkpoint) > date.fromisoformat(today)
        except ValueError:
            future_checkpoint = False
        next_valid = bool(
            ((isinstance(outcome, str) and outcome.strip()) or (isinstance(dependency, str) and evidence(dependency)))
            and future_checkpoint and evidence(next_action.get("evidence"))
        )
    horizon = item.get("roadmapHorizonYears")
    if horizon is not None and (not isinstance(horizon, (int, float)) or isinstance(horizon, bool) or horizon < 0):
        invalid.append("roadmapHorizonYears")
    elif isinstance(horizon, (int, float)) and not next_valid:
        invalid.append("roadmapHorizonYears")
    if item.get("issueKind") == "roadmap" and not next_valid:
        invalid.append("issueKind")
    if inactive_days >= policy["issue"]["closeOrRescopeDays"] and not next_valid:
        proposed, human = "close-or-rescope", True
    elif inactive_days >= policy["issue"]["inactiveReviewDays"]:
        proposed, human = "review", False
    else:
        proposed, human = "none", False
    ready = not missing and not invalid
    return {"ready": ready, "missingFields": missing, "invalidFields": invalid, "blockingRuleIds": [] if ready else ["PRS-ISSUE-READY-001"], "proposedAction": proposed, "humanDecisionRequired": human, "mutationAllowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY); args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text()); standard = json.loads(STANDARD_PATH.read_text())
    errors = validate_policy(policy, standard)
    if errors:
        print("\n".join(errors), file=sys.stderr); return 1
    print(f"valid: {args.policy}"); return 0


if __name__ == "__main__": raise SystemExit(main())

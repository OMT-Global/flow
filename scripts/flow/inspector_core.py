"""Pure classification and mutation-planning logic for the Flow inspector."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


STATE_LABEL_BY_FLOW = {
    "Intake": "state:intake",
    "Ready for Planning": "state:ready-for-planning",
    "Ready for Implementation": "state:ready-for-implementation",
    "Implementing": "state:implementing",
    "PR Open": "state:needs-review",
    "Needs Review": "state:needs-review",
    "Needs Repair": "state:needs-repair",
    "Repairing": "state:repairing",
    "Ready for Approval": "state:ready-for-approval",
    "Approved / Waiting Checks": "state:waiting-checks",
    "Auto-merge Armed": "state:auto-merge-armed",
    "Blocked - Human": "state:blocked-human",
    "Blocked - Infrastructure": "state:blocked-infra",
    "Blocked - Scope": "state:blocked-scope",
    "Paused": "state:paused",
}

LANE_LABEL_BY_ACTOR = {
    "Pheidon": "lane:pheidon",
    "Apollo": "lane:apollo",
    "Ares": "lane:ares",
    "Daedalus": "lane:daedalus",
    "Hephaestus": "lane:hephaestus",
    "Hermes": "lane:hermes",
}

LABEL_SPECS = {
    "state:intake": ("d9d9d9", "Captured but not yet planned."),
    "state:ready-for-planning": ("ccebc5", "Ready for Apollo/Pheidon planning refinement."),
    "state:ready-for-implementation": ("bc80bd", "Issue has enough contract to assign implementation."),
    "state:implementing": ("80b1d3", "Worker lane is actively implementing."),
    "state:needs-review": ("ffffb3", "PR needs review."),
    "state:needs-repair": ("fb8072", "PR or issue needs repair before it can advance."),
    "state:repairing": ("fdb462", "Repair is actively assigned."),
    "state:ready-for-approval": ("b3de69", "Pheidon/gate approval is the next action."),
    "state:waiting-checks": ("ffffb3", "Approved or ready but waiting on checks/merge queue."),
    "state:auto-merge-armed": ("b3de69", "Auto-merge is enabled and GitHub gates own completion."),
    "state:blocked-human": ("e41a1c", "Human decision required."),
    "state:blocked-infra": ("984ea3", "Blocked by tool, auth, runner, or infrastructure failure."),
    "state:blocked-scope": ("ff7f00", "Blocked by unclear scope or acceptance criteria."),
    "state:paused": ("999999", "Intentionally paused."),
    "lane:pheidon": ("b3de69", "Orchestration, gate, governance, and controller action."),
    "lane:apollo": ("8dd3c7", "Scope, backlog, synthesis, and issue-contract work."),
    "lane:ares": ("fb8072", "Validation, adversarial review, and test-pressure work."),
    "lane:daedalus": ("80b1d3", "Implementation and substantive code repair work."),
    "lane:hephaestus": ("fdb462", "CI, build, lockfile, mergeability, and artifact work."),
    "lane:hermes": ("bebada", "macOS/platform-native or special execution work."),
}

LANE_BY_AUTHOR = {
    "apollo-omt": "Apollo",
    "ares-omt": "Ares",
    "daedalus-omt": "Daedalus",
    "hephaestus-omt": "Hephaestus",
    "hermes-omt": "Hermes",
    "pheidon-omt": "Pheidon",
    "athena-omt": "Ares",
    "athena": "Ares",
    "chatgpt-codex-connector": "Daedalus",
}

FAILURE_CONCLUSIONS = {
    "ACTION_REQUIRED",
    "CANCELLED",
    "FAILURE",
    "STARTUP_FAILURE",
    "STALE",
    "TIMED_OUT",
}


def label_names(item: dict[str, Any]) -> set[str]:
    return {label.get("name", "") for label in item.get("labels") or [] if label.get("name")}


def first_label_value(labels: set[str], prefix: str) -> str | None:
    for label in sorted(labels):
        if label.startswith(prefix):
            return label.split(":", 1)[1]
    return None


def check_summary(rollup: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Summarize checks and fail closed unless every observed check succeeded."""
    failing: list[str] = []
    pending: list[str] = []
    passing: list[str] = []
    indeterminate: list[str] = []
    checks = rollup or []
    for check in checks:
        name = check.get("name") or check.get("workflowName") or check.get("context") or "check"
        status = str(check.get("status") or "UNKNOWN").upper()
        conclusion = str(check.get("conclusion") or "UNKNOWN").upper()
        if status != "COMPLETED":
            pending.append(name)
        elif conclusion == "SUCCESS":
            passing.append(name)
        elif conclusion in FAILURE_CONCLUSIONS:
            failing.append(name)
        else:
            indeterminate.append(name)
    return {
        "green": bool(checks) and bool(passing) and not failing and not pending and not indeterminate,
        "failing": sorted(failing),
        "pending": sorted(pending),
        "passing": sorted(passing),
        "indeterminate": sorted(indeterminate),
        "observed": len(checks),
    }


def active_change_requests(pr: dict[str, Any]) -> list[dict[str, str]]:
    requests = []
    for review in pr.get("latestReviews") or []:
        if review.get("state") == "CHANGES_REQUESTED":
            requests.append(
                {
                    "author": (review.get("author") or {}).get("login") or "unknown",
                    "submittedAt": review.get("submittedAt") or "",
                    "body": (review.get("body") or "").strip()[:1000],
                }
            )
    return requests


def owner_from_author(pr: dict[str, Any]) -> str:
    login = ((pr.get("author") or {}).get("login") or "").lower()
    return LANE_BY_AUTHOR.get(login, "Pheidon")


def repair_actor_for_pr(owner_lane: str, checks: dict[str, Any], merge_state: str) -> tuple[str, str]:
    failing = {str(name).lower() for name in checks.get("failing") or []}
    metadata_markers = (
        "validate pr description",
        "ci gate",
        "validate secrets",
        "detect relevant changes",
        "attest",
    )
    if merge_state in ("BEHIND", "DIRTY"):
        return "Hephaestus", f"Restore mergeability from {merge_state.lower()} state, rerun required checks, and push with --force-with-lease when rebasing."
    if any(any(marker in name for marker in metadata_markers) for name in failing):
        return "Hephaestus", "Repair PR metadata, generated governance surfaces, or CI gate wiring, then rerun required checks."
    if owner_lane in ("Pheidon", "Apollo"):
        return "Daedalus", "Reproduce failing checks, make the minimal substantive repair, validate, and push."
    return owner_lane, "Reproduce failing checks, make the minimal repair, validate, and push."


def classify_pr(pr: dict[str, Any]) -> dict[str, Any]:
    checks = check_summary(pr.get("statusCheckRollup"))
    labels = label_names(pr)
    merge_state = pr.get("mergeStateStatus") or "UNKNOWN"
    review = pr.get("reviewDecision") or "UNKNOWN"
    changes = active_change_requests(pr)
    owner = first_label_value(labels, "lane:")
    owner_lane = owner.title() if owner else owner_from_author(pr)
    next_actor = owner_lane
    reasons: list[str] = []

    if pr.get("isDraft"):
        state = "Paused"
        next_action = "Undraft or explicitly mark as paused/not planned."
        reasons.append("draft")
    elif changes or review == "CHANGES_REQUESTED":
        state = "Needs Repair"
        next_actor = owner_lane if owner_lane not in ("Pheidon", "Apollo") else "Daedalus"
        next_action = "Convert requested changes into a repair task and push an updated PR head."
        reasons.append("changes_requested")
    elif merge_state in ("DIRTY", "BEHIND"):
        state = "Needs Repair"
        next_actor, next_action = repair_actor_for_pr(owner_lane, checks, merge_state)
        reasons.append(f"merge_state:{merge_state.lower()}")
        if checks["failing"]:
            reasons.append("failing_checks")
    elif checks["failing"]:
        state = "Needs Repair"
        next_actor, next_action = repair_actor_for_pr(owner_lane, checks, merge_state)
        reasons.append("failing_checks")
    elif review == "REVIEW_REQUIRED":
        state = "Needs Review"
        next_actor = "Ares"
        next_action = "Perform non-author review and either approve or file exact repair feedback."
        reasons.append("review_required")
    elif checks["pending"] or checks["indeterminate"] or not checks["observed"]:
        state = "Approved / Waiting Checks" if review == "APPROVED" else "PR Open"
        next_action = "Wait for complete required-check evidence; reclassify only after every observed check succeeds."
        reasons.append("checks_pending" if checks["pending"] else "checks_indeterminate")
    elif merge_state == "BLOCKED":
        state = "Blocked - Infrastructure"
        next_actor = "Pheidon"
        next_action = "Inspect branch protection, reviews, and checks and convert the blocker into an explicit next action."
        reasons.append("blocked")
    elif merge_state == "CLEAN" and review == "APPROVED" and checks["green"]:
        if pr.get("autoMergeRequest"):
            state = "Auto-merge Armed"
            next_action = "Wait for GitHub auto-merge or merge queue completion."
            reasons.append("clean_approved_green")
        else:
            state = "Needs Repair"
            next_action = "PR author should enable auto-merge where GitHub allows it, or record the unavailable or unsafe reason under Merge Automation."
            reasons.extend(["clean_approved_green", "auto_merge_missing"])
    else:
        state = "PR Open"
        next_actor = "Pheidon"
        next_action = "Inspect manually; classifier did not find a confident next state."
        reasons.append("unclassified")

    return {
        "kind": "pr",
        "number": pr["number"],
        "title": pr["title"],
        "url": pr["url"],
        "flowState": state,
        "ownerLane": owner_lane,
        "nextActor": next_actor,
        "nextAction": next_action,
        "reasons": reasons,
        "mergeStateStatus": merge_state,
        "reviewDecision": review,
        "checks": checks,
        "autoMergeArmed": bool(pr.get("autoMergeRequest")),
        "changeRequests": changes,
        "labels": sorted(labels),
        "updatedAt": pr.get("updatedAt"),
    }


def classify_issue(issue: dict[str, Any]) -> dict[str, Any]:
    labels = label_names(issue)
    state_label = first_label_value(labels, "state:")
    lane_label = first_label_value(labels, "lane:")
    autonomy = first_label_value(labels, "autonomy:")
    body = issue.get("body") or ""
    state_map = {
        "intake": "Intake",
        "ready-for-planning": "Ready for Planning",
        "ready-for-implementation": "Ready for Implementation",
        "implementing": "Implementing",
        "needs-review": "Needs Review",
        "needs-repair": "Needs Repair",
        "repairing": "Repairing",
        "blocked-human": "Blocked - Human",
        "blocked-infra": "Blocked - Infrastructure",
        "blocked-scope": "Blocked - Scope",
        "paused": "Paused",
    }
    flow_state = state_map.get(state_label or "", "")
    if not flow_state:
        has_contract = "acceptance criteria" in body.lower() or "validation" in body.lower()
        flow_state = "Ready for Implementation" if has_contract else "Intake"

    owner_lane = lane_label.title() if lane_label else "Pheidon"
    if flow_state == "Intake":
        next_actor = "Apollo"
        next_action = "Refine into an executable issue contract with acceptance criteria and validation."
    elif flow_state == "Ready for Implementation":
        next_actor = owner_lane if owner_lane != "Pheidon" else "Daedalus"
        next_action = "Assign to worker WIP slot when PR queue allows."
    elif flow_state.startswith("Blocked"):
        next_actor = "Pheidon"
        next_action = "Resolve blocker or convert it into a flow-blocker issue."
    else:
        next_actor = owner_lane
        next_action = "Continue according to current state."

    return {
        "kind": "issue",
        "number": issue["number"],
        "title": issue["title"],
        "url": issue["url"],
        "flowState": flow_state,
        "ownerLane": owner_lane,
        "nextActor": next_actor,
        "nextAction": next_action,
        "autonomy": autonomy,
        "labels": sorted(labels),
        "updatedAt": issue.get("updatedAt"),
    }


def desired_labels(item: dict[str, Any]) -> list[str]:
    labels = []
    state = STATE_LABEL_BY_FLOW.get(item.get("flowState", ""))
    lane = LANE_LABEL_BY_ACTOR.get(item.get("nextActor", "")) or LANE_LABEL_BY_ACTOR.get(item.get("ownerLane", ""))
    if state:
        labels.append(state)
    if lane:
        labels.append(lane)
    return labels


def plan_label_changes(items: list[dict[str, Any]], *, max_items: int | None = None) -> list[dict[str, Any]]:
    selected = items if max_items is None else items[:max_items]
    changes = []
    for item in selected:
        current = set(item.get("labels") or [])
        desired = set(desired_labels(item))
        stale = {label for label in current if label.startswith(("state:", "lane:")) and label not in desired}
        add = sorted(desired - current)
        remove = sorted(stale)
        if add or remove:
            changes.append({"kind": item["kind"], "number": item["number"], "add": add, "remove": remove})
    return changes


def default_assignments() -> dict[str, Any]:
    return {lane: {"current": None, "queued": []} for lane in ("apollo", "ares", "daedalus", "hephaestus", "hermes")}


def plan_repair_dispatch(
    repo: str,
    prs: list[dict[str, Any]],
    assignments: dict[str, Any],
    *,
    max_items: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    planned = deepcopy(assignments)
    existing = set()
    for bucket in planned.values():
        current = bucket.get("current") if isinstance(bucket, dict) else None
        if current:
            existing.add((current.get("repo"), current.get("number")))
        for queued in (bucket.get("queued") or []) if isinstance(bucket, dict) else []:
            existing.add((queued.get("repo"), queued.get("number")))

    added = []
    for item in prs:
        if len(added) >= max_items:
            break
        if item.get("flowState") != "Needs Repair":
            continue
        lane = str(item.get("nextActor") or "").lower()
        if lane not in ("apollo", "ares", "daedalus", "hephaestus", "hermes"):
            lane = "daedalus"
        key = (repo, item["number"])
        if key in existing:
            continue
        payload = {
            "repo": repo,
            "number": item["number"],
            "title": item["title"],
            "url": item["url"],
            "flowState": item["flowState"],
            "nextActor": item["nextActor"],
            "nextAction": item["nextAction"],
            "reasons": item.get("reasons", []),
            "mergeStateStatus": item.get("mergeStateStatus"),
            "reviewDecision": item.get("reviewDecision"),
            "failingChecks": item.get("checks", {}).get("failing", []),
            "pendingChecks": item.get("checks", {}).get("pending", []),
            "coordinationRoutine": "flow_inspector_dispatch",
        }
        bucket = planned.setdefault(lane, {"current": None, "queued": []})
        if bucket.get("current") is None:
            bucket["current"] = payload
        else:
            bucket.setdefault("queued", []).append(payload)
        existing.add(key)
        added.append({"lane": lane, "number": item["number"], "title": item["title"]})
    return planned, added

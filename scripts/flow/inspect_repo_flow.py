#!/usr/bin/env python3
"""Read-only OMT-Global flow inspector.

Classifies GitHub issues and PRs into the flow protocol without mutating GitHub.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/pheidon/.openclaw/workspace')
GATE = WORKSPACE / 'skills/openclaw-maintenance/scripts/check_maintenance_gate.sh'
DEFAULT_REPORT_DIR = WORKSPACE / 'state/flow-inspections'
DEFAULT_ASSIGNMENTS = WORKSPACE / 'state/pr-repair-assignments.json'

STATE_LABEL_BY_FLOW = {
    'Intake': 'state:intake',
    'Ready for Planning': 'state:ready-for-planning',
    'Ready for Implementation': 'state:ready-for-implementation',
    'Implementing': 'state:implementing',
    'PR Open': 'state:needs-review',
    'Needs Review': 'state:needs-review',
    'Needs Repair': 'state:needs-repair',
    'Repairing': 'state:repairing',
    'Ready for Approval': 'state:ready-for-approval',
    'Approved / Waiting Checks': 'state:waiting-checks',
    'Auto-merge Armed': 'state:auto-merge-armed',
    'Blocked - Human': 'state:blocked-human',
    'Blocked - Infrastructure': 'state:blocked-infra',
    'Blocked - Scope': 'state:blocked-scope',
    'Paused': 'state:paused',
}

LANE_LABEL_BY_ACTOR = {
    'Pheidon': 'lane:pheidon',
    'Apollo': 'lane:apollo',
    'Ares': 'lane:ares',
    'Daedalus': 'lane:daedalus',
    'Hephaestus': 'lane:hephaestus',
    'Hermes': 'lane:hermes',
}

LABEL_SPECS = {
    'state:intake': ('d9d9d9', 'Captured but not yet planned.'),
    'state:ready-for-planning': ('ccebc5', 'Ready for Apollo/Pheidon planning refinement.'),
    'state:ready-for-implementation': ('bc80bd', 'Issue has enough contract to assign implementation.'),
    'state:implementing': ('80b1d3', 'Worker lane is actively implementing.'),
    'state:needs-review': ('ffffb3', 'PR needs review.'),
    'state:needs-repair': ('fb8072', 'PR or issue needs repair before it can advance.'),
    'state:repairing': ('fdb462', 'Repair is actively assigned.'),
    'state:ready-for-approval': ('b3de69', 'Pheidon/gate approval is the next action.'),
    'state:waiting-checks': ('ffffb3', 'Approved or ready but waiting on checks/merge queue.'),
    'state:auto-merge-armed': ('b3de69', 'Auto-merge is enabled and GitHub gates own completion.'),
    'state:blocked-human': ('e41a1c', 'Human decision required.'),
    'state:blocked-infra': ('984ea3', 'Blocked by tool, auth, runner, or infrastructure failure.'),
    'state:blocked-scope': ('ff7f00', 'Blocked by unclear scope or acceptance criteria.'),
    'state:paused': ('999999', 'Intentionally paused.'),
    'lane:pheidon': ('b3de69', 'Orchestration, gate, governance, and controller action.'),
    'lane:apollo': ('8dd3c7', 'Scope, backlog, synthesis, and issue-contract work.'),
    'lane:ares': ('fb8072', 'Validation, adversarial review, and test-pressure work.'),
    'lane:daedalus': ('80b1d3', 'Implementation and substantive code repair work.'),
    'lane:hephaestus': ('fdb462', 'CI, build, lockfile, mergeability, and artifact work.'),
    'lane:hermes': ('bebada', 'macOS/platform-native or special execution work.'),
}

LANE_BY_AUTHOR = {
    'apollo-omt': 'Apollo',
    'ares-omt': 'Ares',
    'daedalus-omt': 'Daedalus',
    'hephaestus-omt': 'Hephaestus',
    'hermes-omt': 'Hermes',
    'pheidon-omt': 'Pheidon',
    'athena-omt': 'Ares',
    'athena': 'Ares',
    'chatgpt-codex-connector': 'Daedalus',
}


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(cmd, text=True, capture_output=True)
    if check and cp.returncode:
        raise RuntimeError(cp.stderr.strip() or cp.stdout.strip() or f'command failed: {cmd!r}')
    return cp


def gh_json(args: list[str]) -> Any:
    return json.loads(run(['gh', *args]).stdout)


def maintenance_gate() -> None:
    cp = run(['bash', str(GATE), 'flow-inspect', 'inspect_repo_flow', 'Maintenance active, queued flow inspection.'], check=False)
    if cp.returncode:
        print(cp.stdout or cp.stderr, end='')
        sys.exit(10)


def now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def label_names(item: dict[str, Any]) -> set[str]:
    return {l.get('name', '') for l in item.get('labels') or []}


def first_label_value(labels: set[str], prefix: str) -> str | None:
    for label in sorted(labels):
        if label.startswith(prefix):
            return label.split(':', 1)[1]
    return None


def check_summary(rollup: list[dict[str, Any]]) -> dict[str, Any]:
    failing = []
    pending = []
    passing = []
    for c in rollup or []:
        name = c.get('name') or c.get('workflowName') or c.get('context') or 'check'
        status = c.get('status')
        conclusion = c.get('conclusion')
        if status and status != 'COMPLETED':
            pending.append(name)
        elif conclusion in ('SUCCESS', 'SKIPPED', 'NEUTRAL'):
            passing.append(name)
        elif conclusion:
            failing.append(name)
    return {
        'green': not failing and not pending,
        'failing': failing,
        'pending': pending,
        'passing': passing,
    }


def active_change_requests(pr: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    for review in pr.get('latestReviews') or []:
        if review.get('state') == 'CHANGES_REQUESTED':
            out.append({
                'author': (review.get('author') or {}).get('login') or 'unknown',
                'submittedAt': review.get('submittedAt') or '',
                'body': (review.get('body') or '').strip()[:1000],
            })
    return out


def owner_from_author(pr: dict[str, Any]) -> str:
    login = ((pr.get('author') or {}).get('login') or '').lower()
    return LANE_BY_AUTHOR.get(login, 'Pheidon')


def repair_actor_for_pr(owner_lane: str, checks: dict[str, Any], merge_state: str) -> tuple[str, str]:
    failing = {str(name).lower() for name in checks.get('failing') or []}
    metadata_markers = (
        'validate pr description',
        'ci gate',
        'validate secrets',
        'detect relevant changes',
        'attest',
    )
    if merge_state in ('BEHIND', 'DIRTY'):
        return 'Hephaestus', f'Restore mergeability from {merge_state.lower()} state, rerun required checks, and push with --force-with-lease when rebasing.'
    if any(any(marker in name for marker in metadata_markers) for name in failing):
        return 'Hephaestus', 'Repair PR metadata, generated governance surfaces, or CI gate wiring, then rerun required checks.'
    if owner_lane in ('Pheidon', 'Apollo'):
        return 'Daedalus', 'Reproduce failing checks, make the minimal substantive repair, validate, and push.'
    return owner_lane, 'Reproduce failing checks, make the minimal repair, validate, and push.'


def classify_pr(pr: dict[str, Any]) -> dict[str, Any]:
    checks = check_summary(pr.get('statusCheckRollup') or [])
    labels = label_names(pr)
    merge_state = pr.get('mergeStateStatus') or 'UNKNOWN'
    review = pr.get('reviewDecision') or 'UNKNOWN'
    changes = active_change_requests(pr)
    owner = first_label_value(labels, 'lane:')
    owner_lane = owner.title() if owner else owner_from_author(pr)
    next_actor = owner_lane
    reasons: list[str] = []

    if pr.get('isDraft'):
        state = 'Paused'
        next_action = 'Undraft or explicitly mark as paused/not planned.'
        reasons.append('draft')
    elif merge_state == 'CLEAN' and review == 'APPROVED' and checks['green']:
        if pr.get('autoMergeRequest'):
            state = 'Auto-merge Armed'
            next_action = 'Wait for GitHub auto-merge or merge queue completion.'
            reasons.append('clean_approved_green')
        else:
            state = 'Needs Repair'
            next_actor = owner_lane
            next_action = 'PR author should enable auto-merge where GitHub allows it, or record the unavailable/unsafe reason under Merge Automation.'
            reasons.extend(['clean_approved_green', 'auto_merge_missing'])
    elif changes or review == 'CHANGES_REQUESTED':
        state = 'Needs Repair'
        next_actor = owner_lane if owner_lane not in ('Pheidon', 'Apollo') else 'Daedalus'
        next_action = 'Convert requested changes into a repair task and push an updated PR head.'
        reasons.append('changes_requested')
    elif merge_state in ('DIRTY', 'BEHIND'):
        state = 'Needs Repair'
        next_actor, next_action = repair_actor_for_pr(owner_lane, checks, merge_state)
        reasons.append(f'merge_state:{merge_state.lower()}')
        if checks['failing']:
            reasons.append('failing_checks')
    elif checks['failing']:
        state = 'Needs Repair'
        next_actor, next_action = repair_actor_for_pr(owner_lane, checks, merge_state)
        reasons.append('failing_checks')
    elif review == 'REVIEW_REQUIRED':
        state = 'Needs Review'
        next_actor = 'Ares'
        next_action = 'Perform non-author review and either approve or file exact repair feedback.'
        reasons.append('review_required')
    elif checks['pending']:
        state = 'Approved / Waiting Checks' if review == 'APPROVED' else 'PR Open'
        next_action = 'Wait for checks; reclassify on completion.'
        reasons.append('checks_pending')
    elif merge_state == 'BLOCKED':
        state = 'Blocked - Infrastructure'
        next_actor = 'Pheidon'
        next_action = 'Inspect branch protection/reviews/checks and convert blocker into explicit next action.'
        reasons.append('blocked')
    else:
        state = 'PR Open'
        next_actor = 'Pheidon'
        next_action = 'Inspect manually; classifier did not find a confident next state.'
        reasons.append('unclassified')

    return {
        'kind': 'pr',
        'number': pr['number'],
        'title': pr['title'],
        'url': pr['url'],
        'flowState': state,
        'ownerLane': owner_lane,
        'nextActor': next_actor,
        'nextAction': next_action,
        'reasons': reasons,
        'mergeStateStatus': merge_state,
        'reviewDecision': review,
        'checks': checks,
        'autoMergeArmed': bool(pr.get('autoMergeRequest')),
        'changeRequests': changes,
        'updatedAt': pr.get('updatedAt'),
    }


def classify_issue(issue: dict[str, Any]) -> dict[str, Any]:
    labels = label_names(issue)
    state_label = first_label_value(labels, 'state:')
    lane_label = first_label_value(labels, 'lane:')
    autonomy = first_label_value(labels, 'autonomy:')
    body = issue.get('body') or ''

    state_map = {
        'intake': 'Intake',
        'ready-for-planning': 'Ready for Planning',
        'ready-for-implementation': 'Ready for Implementation',
        'implementing': 'Implementing',
        'needs-review': 'Needs Review',
        'needs-repair': 'Needs Repair',
        'repairing': 'Repairing',
        'blocked-human': 'Blocked - Human',
        'blocked-infra': 'Blocked - Infrastructure',
        'blocked-scope': 'Blocked - Scope',
        'paused': 'Paused',
    }
    flow_state = state_map.get(state_label or '', '')
    if not flow_state:
        has_contract = 'Acceptance criteria' in body or 'Validation' in body or 'validation' in body.lower()
        flow_state = 'Ready for Implementation' if has_contract else 'Intake'

    owner_lane = lane_label.title() if lane_label else 'Pheidon'
    if flow_state == 'Intake':
        next_actor = 'Apollo'
        next_action = 'Refine into an executable issue contract with acceptance criteria and validation.'
    elif flow_state == 'Ready for Implementation':
        next_actor = owner_lane if owner_lane != 'Pheidon' else 'Daedalus'
        next_action = 'Assign to worker WIP slot when PR queue allows.'
    elif flow_state.startswith('Blocked'):
        next_actor = 'Pheidon'
        next_action = 'Resolve blocker or convert it into a flow-blocker issue.'
    else:
        next_actor = owner_lane
        next_action = 'Continue according to current state.'

    return {
        'kind': 'issue',
        'number': issue['number'],
        'title': issue['title'],
        'url': issue['url'],
        'flowState': flow_state,
        'ownerLane': owner_lane,
        'nextActor': next_actor,
        'nextAction': next_action,
        'autonomy': autonomy,
        'labels': sorted(labels),
        'updatedAt': issue.get('updatedAt'),
    }


def desired_labels(item: dict[str, Any]) -> list[str]:
    labels = []
    state = STATE_LABEL_BY_FLOW.get(item.get('flowState', ''))
    lane = LANE_LABEL_BY_ACTOR.get(item.get('nextActor', '')) or LANE_LABEL_BY_ACTOR.get(item.get('ownerLane', ''))
    if state:
        labels.append(state)
    if lane:
        labels.append(lane)
    return labels


def ensure_label(repo: str, name: str) -> None:
    color, description = LABEL_SPECS.get(name, ('d9d9d9', 'OMT-Global flow label.'))
    cp = run(['gh', 'label', 'create', name, '--repo', repo, '--color', color, '--description', description], check=False)
    if cp.returncode and 'already exists' not in (cp.stderr + cp.stdout):
        # If it exists with different metadata, keep going; label add is what matters.
        probe = run(['gh', 'label', 'list', '--repo', repo, '--search', name, '--json', 'name'], check=False)
        if probe.returncode or name not in probe.stdout:
            raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())


def apply_labels(repo: str, items: list[dict[str, Any]], *, max_items: int | None = None) -> dict[str, Any]:
    applied = []
    selected = items if max_items is None else items[:max_items]
    needed = sorted({label for item in selected for label in desired_labels(item)})
    for label in needed:
        ensure_label(repo, label)
    for item in selected:
        labels = desired_labels(item)
        if not labels:
            continue
        target = ['pr' if item['kind'] == 'pr' else 'issue', 'edit', str(item['number']), '--repo', repo, '--add-label', ','.join(labels)]
        run(['gh', *target])
        applied.append({'kind': item['kind'], 'number': item['number'], 'labels': labels})
    return {'count': len(applied), 'items': applied}


def load_assignments(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text())
    return {lane: {'current': None, 'queued': []} for lane in ('apollo', 'ares', 'daedalus', 'hephaestus', 'hermes')}


def dispatch_repairs(repo: str, prs: list[dict[str, Any]], path: Path, *, max_items: int) -> dict[str, Any]:
    assignments = load_assignments(path)
    existing = set()
    for bucket in assignments.values():
        current = bucket.get('current') if isinstance(bucket, dict) else None
        if current:
            existing.add((current.get('repo'), current.get('number')))
        for queued in (bucket.get('queued') or []) if isinstance(bucket, dict) else []:
            existing.add((queued.get('repo'), queued.get('number')))

    added = []
    for item in prs:
        if len(added) >= max_items:
            break
        if item.get('flowState') != 'Needs Repair':
            continue
        actor = item.get('nextActor')
        lane = (actor or '').lower()
        if lane not in ('apollo', 'ares', 'daedalus', 'hephaestus', 'hermes'):
            lane = 'daedalus'
        key = (repo, item['number'])
        if key in existing:
            continue
        payload = {
            'repo': repo,
            'number': item['number'],
            'title': item['title'],
            'url': item['url'],
            'flowState': item['flowState'],
            'nextActor': item['nextActor'],
            'nextAction': item['nextAction'],
            'reasons': item.get('reasons', []),
            'mergeStateStatus': item.get('mergeStateStatus'),
            'reviewDecision': item.get('reviewDecision'),
            'failingChecks': item.get('checks', {}).get('failing', []),
            'pendingChecks': item.get('checks', {}).get('pending', []),
            'coordinationRoutine': 'flow_inspector_dispatch',
        }
        bucket = assignments.setdefault(lane, {'current': None, 'queued': []})
        if bucket.get('current') is None:
            bucket['current'] = payload
        else:
            bucket.setdefault('queued', []).append(payload)
        existing.add(key)
        added.append({'lane': lane, 'number': item['number'], 'title': item['title']})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(assignments, indent=2) + '\n')
    return {'count': len(added), 'path': str(path), 'items': added}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='OMT-Global/axiom')
    ap.add_argument('--limit', type=int, default=100)
    ap.add_argument('--json-out', type=Path)
    ap.add_argument('--issues', action='store_true', help='include open issues as well as PRs')
    ap.add_argument('--apply-labels', action='store_true', help='write flow state/lane labels to GitHub')
    ap.add_argument('--label-limit', type=int, help='maximum items to label when --apply-labels is set')
    ap.add_argument('--dispatch-repairs', action='store_true', help='write Needs Repair PRs to local repair assignment state')
    ap.add_argument('--dispatch-limit', type=int, default=10)
    ap.add_argument('--assignments', type=Path, default=DEFAULT_ASSIGNMENTS)
    args = ap.parse_args()

    maintenance_gate()

    prs = gh_json(['pr', 'list', '--repo', args.repo, '--state', 'open', '--limit', str(args.limit), '--json',
                   'number,title,url,isDraft,author,headRefName,mergeStateStatus,reviewDecision,statusCheckRollup,autoMergeRequest,latestReviews,labels,updatedAt'])
    pr_items = [classify_pr(pr) for pr in prs]
    issue_items: list[dict[str, Any]] = []
    if args.issues:
        issues = gh_json(['issue', 'list', '--repo', args.repo, '--state', 'open', '--limit', str(args.limit), '--json',
                          'number,title,url,labels,assignees,updatedAt,body'])
        issue_items = [classify_issue(issue) for issue in issues]

    counts = Counter(item['flowState'] for item in [*pr_items, *issue_items])
    sorted_prs = sorted(pr_items, key=lambda x: x['number'], reverse=True)
    sorted_issues = sorted(issue_items, key=lambda x: x['number'], reverse=True)
    write_results = {}
    if args.apply_labels:
        write_results['labels'] = apply_labels(args.repo, [*sorted_prs, *sorted_issues], max_items=args.label_limit)
    if args.dispatch_repairs:
        write_results['dispatch'] = dispatch_repairs(args.repo, sorted_prs, args.assignments, max_items=args.dispatch_limit)

    report = {
        'repo': args.repo,
        'generatedAt': now(),
        'counts': dict(sorted(counts.items())),
        'writeResults': write_results,
        'prs': sorted_prs,
        'issues': sorted_issues,
    }

    out = args.json_out
    if out is None:
        safe_repo = args.repo.replace('/', '-')
        DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = DEFAULT_REPORT_DIR / f'{safe_repo}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')

    print(f'Flow inspection for {args.repo}')
    for state, count in sorted(counts.items()):
        print(f'- {state}: {count}')
    print('\nTop PR actions:')
    for item in report['prs'][:20]:
        print(f"- PR #{item['number']}: {item['flowState']} -> {item['nextActor']}: {item['nextAction']} ({', '.join(item['reasons'])})")
    if write_results:
        print('\nWrites:')
        print(json.dumps(write_results, indent=2))
    print(f'\nwrote {out}')


if __name__ == '__main__':
    main()

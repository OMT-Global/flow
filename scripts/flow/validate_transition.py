#!/usr/bin/env python3
"""Validate and evaluate Public Repository Standard v1 state transitions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "policies" / "transitions-v1.json"
STANDARD_PATH = ROOT / "policies" / "public-repository-standard-v1.json"


def validate_policy(policy: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(policy, dict):
        return ["$: expected an object"]
    domains = policy.get("domains")
    if not isinstance(domains, dict) or set(domains) != {"work", "release"}:
        return ["$.domains: expected exactly work and release domains"]
    for domain_name, domain in domains.items():
        if not isinstance(domain, dict):
            errors.append(f"$.domains.{domain_name}: expected an object")
            continue
        states = domain.get("states", {})
        initial = domain.get("initial")
        terminal = domain.get("terminal", [])
        if not isinstance(states, dict):
            errors.append(f"$.domains.{domain_name}.states: expected an object")
            continue
        if initial not in states:
            errors.append(f"$.domains.{domain_name}.initial: unknown state {initial!r}")
        if not isinstance(terminal, list):
            errors.append(f"$.domains.{domain_name}.terminal: expected an array")
            terminal = []
        for state in terminal:
            if state not in states:
                errors.append(f"$.domains.{domain_name}.terminal: unknown state {state!r}")
        inbound = {state: 0 for state in states}
        for state, outgoing in states.items():
            if not isinstance(outgoing, list):
                errors.append(f"$.domains.{domain_name}.states.{state}: expected an array")
                continue
            if state in terminal and outgoing:
                errors.append(f"$.domains.{domain_name}.states.{state}: terminal state has outgoing transitions")
            if state not in terminal and not outgoing:
                errors.append(f"$.domains.{domain_name}.states.{state}: non-terminal state has no outgoing transitions")
            for target in outgoing:
                if target not in states:
                    errors.append(f"$.domains.{domain_name}.states.{state}: unknown target {target!r}")
                else:
                    inbound[target] += 1
        for state, count in inbound.items():
            if state != initial and count == 0:
                errors.append(f"$.domains.{domain_name}.states.{state}: state has no inbound transition")
    evidence_rules = policy.get("evidenceRules")
    if not isinstance(evidence_rules, dict):
        errors.append("$.evidenceRules: expected an object")
    else:
        for key in ("material", "hardStop", "resumeFrom"):
            if key not in evidence_rules:
                errors.append(f"$.evidenceRules.{key}: required property is missing")
        for key in ("material", "hardStop"):
            rule = evidence_rules.get(key)
            if not isinstance(rule, dict):
                errors.append(f"$.evidenceRules.{key}: expected an object")
            else:
                for field in ("ruleId", "requires"):
                    if not isinstance(rule.get(field), str) or not rule[field].strip():
                        errors.append(f"$.evidenceRules.{key}.{field}: expected a non-empty string")
        resume_rules = evidence_rules.get("resumeFrom")
        if not isinstance(resume_rules, dict):
            errors.append("$.evidenceRules.resumeFrom: expected an object")
        else:
            for state, rule in resume_rules.items():
                if not isinstance(rule, dict):
                    errors.append(f"$.evidenceRules.resumeFrom.{state}: expected an object")
                    continue
                for field in ("ruleId", "requires"):
                    if not isinstance(rule.get(field), str) or not rule[field].strip():
                        errors.append(f"$.evidenceRules.resumeFrom.{state}.{field}: expected a non-empty string")
    return sorted(errors)


def denied(rule_id: str, remediation: str) -> dict[str, Any]:
    return {"allowed": False, "ruleId": rule_id, "remediation": remediation}


def evaluate_transition(
    policy: dict[str, Any],
    domain: str,
    current: str,
    target: str,
    *,
    material: bool | None = None,
    notification_evidence: str | None = None,
    hard_stop: str | None = None,
    approval_evidence: str | None = None,
    resolution_evidence: str | None = None,
) -> dict[str, Any]:
    domains = policy.get("domains", {})
    if domain not in domains:
        return denied("PRS-TRANSITION-001", f"Choose a known domain: {', '.join(sorted(domains))}.")
    states = domains[domain]["states"]
    if current not in states:
        return denied("PRS-TRANSITION-001", f"Choose a known current state in {domain}.")
    if target not in states[current]:
        allowed = ", ".join(states[current]) or "none (terminal state)"
        return denied("PRS-TRANSITION-001", f"Allowed next states: {allowed}.")

    def valid_evidence(value: str | None) -> bool:
        if not value or not value.strip():
            return False
        return value.startswith(("https://", "http://", "issue:", "pr:", "run:"))

    if material is None:
        return denied("PRS-NOTIFY-001", "Declare transition materiality explicitly.")
    if hard_stop is None:
        return denied("PRS-HARDSTOP-001", "Declare hard-stop evaluation as 'none' or a defined category.")
    if material and not valid_evidence(notification_evidence):
        return denied("PRS-NOTIFY-001", "Record material-action notification evidence on the governing issue or pull request.")
    if hard_stop != "none":
        hard_stops = json.loads(STANDARD_PATH.read_text())["humanHardStops"]["categories"]
        if hard_stop not in hard_stops:
            return denied("PRS-HARDSTOP-001", f"Unknown hard-stop category: {hard_stop}.")
        if not valid_evidence(approval_evidence):
            return denied("PRS-HARDSTOP-001", "Record explicit human approval evidence before continuing.")

    resume_rule = policy["evidenceRules"]["resumeFrom"].get(current)
    if resume_rule:
        required = resume_rule["requires"]
        evidence = approval_evidence if required == "approvalEvidence" else resolution_evidence
        if not valid_evidence(evidence):
            return denied(resume_rule["ruleId"], f"Record {resume_rule['requires']} before leaving {current}.")
        if required == "resolutionAndApprovalEvidence" and not valid_evidence(approval_evidence):
            return denied(resume_rule["ruleId"], "Record release-owner approvalEvidence before security recovery.")
    return {"allowed": True, "ruleId": None, "remediation": None}


def node_id(domain: str, state: str) -> str:
    safe = "".join(character if character.isalnum() else "_" for character in state)
    return f"{domain}_{safe}"


def render_mermaid(policy: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    for domain_name, domain in policy["domains"].items():
        lines.append(f"  subgraph {domain_name}")
        for state in domain["states"]:
            lines.append(f'    {node_id(domain_name, state)}["{state}"]')
        for state, targets in domain["states"].items():
            if targets:
                joined = " & ".join(node_id(domain_name, target) for target in targets)
                lines.append(f"    {node_id(domain_name, state)} --> {joined}")
        lines.append("  end")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--diagram", action="store_true")
    parser.add_argument("--domain", choices=("work", "release"))
    parser.add_argument("--from-state")
    parser.add_argument("--to-state")
    parser.add_argument("--materiality", choices=("material", "non-material"))
    parser.add_argument("--notification-evidence")
    parser.add_argument("--hard-stop")
    parser.add_argument("--approval-evidence")
    parser.add_argument("--resolution-evidence")
    args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text())
    errors = validate_policy(policy)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    if args.diagram:
        print(render_mermaid(policy), end="")
        return 0
    if not (args.domain and args.from_state and args.to_state):
        print(f"valid: {args.policy}")
        return 0
    result = evaluate_transition(
        policy, args.domain, args.from_state, args.to_state,
        material=None if args.materiality is None else args.materiality == "material",
        notification_evidence=args.notification_evidence,
        hard_stop=args.hard_stop,
        approval_evidence=args.approval_evidence,
        resolution_evidence=args.resolution_evidence,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

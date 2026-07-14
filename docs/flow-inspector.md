# Flow inspector operator guide

The Flow inspector classifies live GitHub issues and pull requests, chooses the
next actor, and reports proposed state, lane, and repair-assignment changes. Its
default mode is read-only: it does not edit GitHub labels or assignment state,
and it does not write a report unless an output path is supplied.

## Inspect without mutation

```sh
python scripts/flow/inspect_repo_flow.py \
  --repo OMT-Global/flow \
  --issues
```

Use `--json` for the complete report on stdout or configure an explicit,
atomic file output:

```sh
python scripts/flow/inspect_repo_flow.py \
  --repo OMT-Global/flow \
  --issues \
  --json-out /tmp/flow-inspection.json
```

Each report says `mode: read-only` and includes `proposedWrites`. A check
rollup is green only when at least one check is present and every observed check
completed successfully. Empty, pending, neutral, skipped, cancelled, malformed,
or unknown evidence cannot produce a green classification.

If the host has a maintenance gate, configure it explicitly:

```sh
python scripts/flow/inspect_repo_flow.py \
  --repo OMT-Global/flow \
  --maintenance-gate /opt/omt/check_maintenance_gate.sh
```

No repository, workspace, report directory, assignment store, or maintenance
script path is built into the inspector.

## Apply reviewed writes

These commands mutate external or local state. First run the matching read-only
inspection and review `proposedWrites`.

Reconcile GitHub state and lane labels:

```sh
python scripts/flow/inspect_repo_flow.py \
  --repo OMT-Global/flow \
  --issues \
  --apply-labels \
  --label-limit 10
```

Reconciliation adds the desired state/lane and removes every stale label in the
same mutually exclusive `state:` or `lane:` family. Other label families are
left untouched.

Dispatch repair candidates to an explicit assignment store:

```sh
python scripts/flow/inspect_repo_flow.py \
  --repo OMT-Global/flow \
  --dispatch-repairs \
  --dispatch-limit 5 \
  --assignments /var/lib/omt/pr-repair-assignments.json
```

Assignment updates hold an exclusive sidecar lock for the read/modify/write
transaction, write a temporary file in the destination directory, flush it,
and atomically replace the destination. Existing repository/PR assignments are
deduplicated while the lock is held.

## Verification

```sh
python -m py_compile scripts/flow/inspector_core.py scripts/flow/inspect_repo_flow.py
python -m unittest discover -s tests -p 'test_flow_inspector.py' -v
python scripts/flow/inspect_repo_flow.py --help
```

Never use `--apply-labels` or `--dispatch-repairs` for a smoke test. Live
mutation testing is a human decision point and must be explicitly authorized.

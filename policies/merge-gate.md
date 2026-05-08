# Merge Gate Policy

A PR is merge-ready only when:

- it is not draft;
- it has a linked issue or explicit no-issue rationale;
- required checks pass or are intentionally non-blocking;
- no active blocking `CHANGES_REQUESTED` review remains;
- at least one valid non-author approval exists when approval is required;
- the PR author does not approve their own PR;
- merge state is clean or GitHub merge queue can safely handle it;
- risk/autonomy class permits autonomous merge.

Default end state for healthy PRs is auto-merge, not manual waiting.

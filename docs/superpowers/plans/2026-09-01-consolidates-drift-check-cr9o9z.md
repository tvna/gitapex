# Branch plan: gate-proposal-umbrella Consolidates: drift check

Issue #1653. Branch `claude/consolidates-drift-check-cr9o9z`.

## Decomposition

Single task, no parallel decomposition needed (degenerate case): every
planned change lives in one new script, its one new test file, and two
small edits to already-existing files, none of which can be usefully
split across independent file-ownership scopes without introducing an
artificial dependency edge between the pieces.

### Task 1: Add gate-proposal-umbrella Consolidates: drift check

Owns:
- `.github/scripts/gitapex_scan_gate_proposal_consolidation_drift.py` (new)
- `tests/test_gitapex_scan_gate_proposal_consolidation_drift.py` (new)
- `.github/workflows/retrospective-gate-drift.yml` (edit: add a step)
- `.gitapex/ssot.json` (edit: register the new script as a `gates[]` entry)

Planned ops (quoted from issue #1653's own re-verified ACM):

> New sibling script gitapex_scan_gate_proposal_consolidation_drift.py:
> import label_exists and list_labelled_issue_records directly from
> gitapex_scan_retrospective_gate_drift.py (the same cross-import
> precedent gitapex_compute_gprr.py already uses for the identical
> function), regex-match a `Consolidates:\s*(#\d+(?:,\s*#\d+)*)` line
> per OPEN gate-proposal issue body, then call the already-existing,
> already-tested _gitapex_github_http.graphql_call helper (confirmed
> present in this repository, moved there from a retired
> gitapex_sync_pr_publish.py per issue #729) once per referenced issue
> number to fetch state/stateReason/duplicateOf.number and compare
> against the umbrella's own issue number.
>
> Add a report-formatting function analogous to the existing
> format_closed_integrity_report, listing every non-conforming
> referenced issue number, sorted, per offending umbrella.
>
> Add a new step to retrospective-gate-drift.yml invoking the sibling
> script, tee'd into GITHUB_STEP_SUMMARY like the existing passes; no
> continue-on-error, matching the existing step's own fail-the-job
> posture.
>
> Unit-test the pure-logic matching/comparison function against fixture
> issue records (a mocked Consolidates line plus mocked referenced-issue
> state/stateReason/duplicateOf), including one fixture shaped like the
> actual #1566-#1575 defect (source issue still OPEN) and one shaped
> like its resolved state (source issue closed duplicate pointing at the
> umbrella).
>
> Add a gates[] entry (id, kind: script, script path, rule, planes: [ci],
> trigger, cluster, tracking_issue: this issue's own number, target: the
> new script path plus the workflow-event and file-glob it watches).

Proof method: pytest (fixture reproducing the exact #1566-#1575 defect
class fails before the check exists / before duplicate-closure, passes
after); plus a live run of the new script against the real
tvna/gitapex repository confirming it goes green against the current,
already-fixed #1566-#1575 state.

Irreversibility: none of this task's ops are irreversible (new files,
additive workflow step, additive ssot.json registration -- all plain
`git revert`-able).

## Wave assignment

Wave 1: Task 1 (only task).

## Execution mode

Sequential main-thread fallback (no `Workflow` tool dispatch): this is
a single, tightly file-coupled task with no parallelism to gain, and
the `Workflow` tool's own usage contract requires explicit
multi-agent-orchestration opt-in from the user, which this session does
not have. Implemented directly in the main thread instead, with the
same main-thread-only discipline this skill's own steps 4-9 already
require (GitHub writes, `git push`, and merge/PR operations stay
main-thread actions regardless of dispatch mode).

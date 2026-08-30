# Branch Plan: file missing-deterministic-gate findings as standalone issues

Refs #1406. Branch: `claude/gitapex-pr-1395-f1t7w4`. Source Acceptance
Criteria Map: issue #1406 (re-verified `planning-a-branch-from-an-issue`,
2026-08-29T17:58:38Z), grounded in
`docs/superpowers/specs/2026-08-29-flat-gate-proposal-issues-design.md`.

## Shared contract (fixed at decomposition time, not discovered task-to-task)

To let Tasks A/B/C run in the same wave without an interface-dependency
edge between them, the following is fixed here, verbatim from the ACM,
rather than left for one task to discover from another's output:

- New module `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`
  exposes a label constant, e.g. `GATE_PROPOSAL_LABEL = "gate-proposal"`,
  and a pure function building the deterministic title
  `gate-proposal: retro #<retrospective-issue-number> repair <1-based
  index>: <repair's own one-line label>` plus the ACM-populated body, from
  inputs: retrospective issue number, repair index (1-based), repair
  label, and the repair's own Classification/Proposed-gate/Residual-risk
  text.
- `.github/scripts/gitapex_scan_retrospective_gate_drift.py` defines its
  own independent copy of the same literal, `GATE_PROPOSAL_LABEL =
  "gate-proposal"` -- a parallel copy, never an import of the skill-side
  module (Decision 6; `.github/` never ships with the installed plugin).
- `SKILL.md`'s own Step 5 prose invokes the new script for
  {title, body, label}, then performs the actual search/create/verify via
  direct `mcp__github__*` tool calls itself -- the script never calls
  `issue_write`/`issue_read`.

## Tasks

### Task A -- rewrite `skills/merge-retrospective/SKILL.md`

Files: `skills/merge-retrospective/SKILL.md`

ACM row cited (row 1), Planned ops verbatim: "Edit
`skills/merge-retrospective/SKILL.md` (Steps 0-5, unchanged Step 0
branching)"

Steps:
1. Step 1 becomes a no-op for a routine cycle (legacy backlog stays out
   of scope per Non-goals).
2. Step 2-4 assign each repair its own 1-based index in-memory during
   classification (no separate pre-write to the issue body -- see the
   design doc's own Decision 1 residual-risk framing).
3. Step 5's one existing body write (create fresh, or update-replacing-
   stub per Step 0's own unchanged marker-based branching -- do not
   modify Step 0's own text) includes the enumerated repair list (index +
   label) up front, then invokes the new helper script (Task B) once per
   `missing-deterministic-gate` repair per the shared contract above,
   performs the search-then-create-then-verify sequence itself via direct
   `mcp__github__*` tool calls, and records a `Filed as:` line naming the
   filed issue's own number as each filing is confirmed -- preserve each
   repair's own inline `Status: missing-deterministic-gate` line verbatim
   alongside it (row 6, GPRR compatibility -- do not remove or replace
   it).
4. Close follows the existing attended/unattended confirm rule, extended
   from the zero-repair-only case to every close.
5. `unclear-agent-instruction`/`external-human-decision` repairs stay
   recorded inline unchanged -- no issue filed, no script invoked.

Proof method (row 1): new `evals/merge-retrospective/tasks/*.yaml`
fixtures (Task E) cover this; manual diff review confirms Step 0's own
marker-based branching text is untouched.

### Task B -- new `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`

Files: `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`,
`skills/merge-retrospective/scripts/test_gitapex_file_gate_proposal.py`

ACM row cited (row 2), Planned ops verbatim: "Create the new script
(title builder, ACM-body template, label constant)"

Steps:
1. Pure, network-free module per the shared contract above -- no
   `issue_write`/`issue_read` calls, no network access.
2. Unit tests: deterministic-title construction from
   index/label/retrospective-number; the ACM-body template; a test
   asserting two repairs in the same cycle with an identical one-line
   label still produce two distinct titles (index-keyed, not
   label-keyed); a test asserting the produced ACM body satisfies
   `hooks/gitapex_check_acm_present_or_waiver.py`'s `has_acm_disclosure`.

Proof method (row 2): the unit tests above; defeat-test the title-collision
case explicitly (same label, different index -> different title).

### Task C -- rescope `.github/scripts/gitapex_scan_retrospective_gate_drift.py` + `.github/workflows/retrospective-gate-drift.yml`

Files: `.github/scripts/gitapex_scan_retrospective_gate_drift.py`, its
existing test file, `.github/workflows/retrospective-gate-drift.yml`

ACM row cited (row 4), Planned ops verbatim: "Edit
`gitapex_scan_retrospective_gate_drift.py` and
`retrospective-gate-drift.yml`; carries its own copy of the
`gate-proposal` label constant"

Steps:
1. Label-liveness guard: fail loudly if the `gate-proposal` label does
   not exist, rather than reporting a false clean zero.
2. Primary pass (a): threshold-gated (20, unchanged) open-count report
   over labelled issues.
3. Secondary pass (b): unbounded, zero-tolerance pass over every closed
   labelled issue (no `closed_at` time window, no reopen action),
   exempting `state_reason` `not_planned`/`duplicate`, failing the CI run
   on any remaining issue that closed without passing the two-signal
   check.
4. Workflow permissions in `retrospective-gate-drift.yml` stay `contents:
   read` / `issues: read` / `pull-requests: read` -- do not widen them.

Proof method (row 4): unit tests for the label-liveness guard (missing
label fails loudly), the open-count threshold report (mocked label
search), and the closed-issue zero-tolerance integrity pass (mocked label
search over every closed labelled issue, `state_reason` exemption
applied, two-signal check applied to the remainder).

### Task D -- new `tests/test_gitapex_retro_gate_label_sync.py`

Files: `tests/test_gitapex_retro_gate_label_sync.py`

Interface-dependency edge: on Task B and Task C (imports each module's
real, on-disk `GATE_PROPOSAL_LABEL` constant by file path) -- sequenced
after both, wave 2.

ACM row cited (row 5), Planned ops verbatim: "Create
`tests/test_gitapex_retro_gate_label_sync.py`"

Steps:
1. Load both constants by file path (same shape as
   `tests/test_gitapex_pr_title_convention_regex_sync.py`), assert
   equality.
2. Defeat test: confirmed via a deliberate mutation of one copy (fails),
   then restored (passes).

Proof method (row 5): the test itself, defeat-tested per above.

### Task E -- eval fixtures + GPRR-compatibility test

Files: `evals/merge-retrospective/tasks/*.yaml` (new fixtures),
`.github/scripts/test_gitapex_compute_gprr.py` (or the nearest existing
GPRR test file -- add a case, do not create a duplicate test module if one
already exists)

Interface-dependency edge: on Task A (fixtures encode Task A's own final
Step 0-5 wording/behavior) -- sequenced after it, wave 2. No edge with
Task D (disjoint files).

ACM rows cited (row 1's proof method, and row 6), Planned ops verbatim
(row 6): "No change to `gitapex_compute_gprr.py`; `SKILL.md`'s Step 5
rewrite must preserve the `Status:` line verbatim"

Steps:
1. New `evals/merge-retrospective/tasks/*.yaml` fixtures per the design
   doc's own Testing section: zero-repair fast-close (unchanged);
   zero-repair with pre-existing legacy backlog present but out of scope
   (still fast-closes); one-or-more `missing-deterministic-gate` repairs,
   attended (each filed, verified, retrospective closes); same but
   unattended (filed and verified, retrospective stays open); a resumed
   run after a partial filing failure (only unfiled repairs retried, no
   duplication).
2. A dedicated test asserting a retrospective issue's own inline `Status:
   missing-deterministic-gate` line for a repair survives unchanged
   alongside its new `Filed as:` line; confirm
   `gitapex_compute_gprr.py`'s own existing test suite still passes
   unmodified (no code change to that file).

Proof method (row 6): the dedicated test above; `gitapex_compute_gprr.py`'s
existing suite green, unmodified file.

## File-ownership map

| File | Task |
|---|---|
| `skills/merge-retrospective/SKILL.md` | A |
| `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py` | B |
| `skills/merge-retrospective/scripts/test_gitapex_file_gate_proposal.py` | B |
| `.github/scripts/gitapex_scan_retrospective_gate_drift.py` | C |
| `.github/scripts/gitapex_scan_retrospective_gate_drift.py`'s test file | C |
| `.github/workflows/retrospective-gate-drift.yml` | C |
| `tests/test_gitapex_retro_gate_label_sync.py` | D |
| `evals/merge-retrospective/tasks/*.yaml` | E |
| GPRR test file | E |

No two tasks share a file -- no file-ownership edges.

## Interface-dependency map

- D -> B, D -> C (imports real on-disk constants)
- E -> A (fixtures/tests encode A's own final behavior)
- No edge among A, B, C themselves: the shared contract above is fixed
  at decomposition time, not discovered from a sibling task's actual
  output (Decision 6 deliberately keeps B and C as independent copies,
  never one importing the other).

## Wave assignment

- **Wave 1:** {A, B, C} -- no file or interface edge among them.
- **Wave 2:** {D, E} -- D depends on B+C (wave 1, already complete); E
  depends on A (wave 1, already complete); no edge between D and E.

## Irreversibility classification

All five tasks are ordinary file edits/additions (skill doc, two
scripts, two test files, YAML fixtures) -- none irreversible. No task
requires a fresh irreversible-task confirmation beyond this Branch Plan's
own step-1 authorization.

## Known operational gap (not a task -- explicit residual, disclosed in the PR body)

The `gate-proposal` GitHub label does not yet exist on this repository
(confirmed via `get_label` -- not found), and no available tool in this
session can create a repository label without a raw, unauthorized API
write. This is a one-time manual bootstrap a human with repo-admin access
must perform once before this mechanism's first real filing. No task
above attempts to create it; disclosed explicitly in the PR body instead.

## Known external state

PR #1416 (a different, concurrent session) targets issue #1406's own
pre-reframe, narrower scope and cites `Closes #1406`. A comment explaining
the conflict is posted on that PR. Per explicit operator direction
(2026-08-29, in-session), this Branch Plan proceeds regardless -- if PR
#1416 merges first and closes #1406 prematurely, a new issue carrying
this same Acceptance Criteria Map is filed to continue, rather than
stopping.

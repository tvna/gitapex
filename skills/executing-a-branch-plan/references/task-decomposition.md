# Task Decomposition

Step 3's own detail. Source: design doc Decisions 3, 15, 19.

## Contents

- [Malformed or empty ACM](#malformed-or-empty-acm-precondition-checked-before-any-of-the-below)
- [Fan-out bound](#fan-out-bound-blast-radius-control-checked-once-the-task-list-exists)
- [Row-to-task mapping](#row-to-task-mapping-many-to-many-not-one-to-one)
- [Two dependency-edge types](#two-dependency-edge-types-both-computed-before-wave-assignment)
- [Irreversibility classification](#irreversibility-classification)
- [Per-task diff BASE](#per-task-diff-base-screening-precondition-used-at-step-6)
- [Worked example](#worked-example)

## Malformed or empty ACM (precondition, checked before any of the below)

Before building the row-to-task mapping, verify the ACM itself is
well-formed: at least one row, and every row carries a non-empty
Criterion, Interpretation, and Planned ops column (a Proof method or
Residual risk column reading "unknown, pending X" is fine -- an
`planning-a-branch-from-an-issue`/`drafting-an-acm-issue` convention, not malformed; a
genuinely empty or missing column is). An ACM with zero rows, or any row
missing a required column, is not decomposed -- stop and escalate the
same way an absent step-1 authorization signal does (fail closed, not an
assumed-empty task list or a silently-skipped row).

## Fan-out bound (blast-radius control, checked once the task list exists)

**Scope, stated precisely rather than implied broader than it is:** the
two caps below bound task/wave *headcount* and *re-plan recurrence*
only. They do not bound actual token, turn, or wall-clock consumption
per task, and neither does anything else in this skill -- design doc
Decision 9 explicitly and deliberately declines to invent a numeric
cost/token ceiling ("no numeric cost/token ceiling is invented here ...
Flagged as an open input, to be measured from a real dry run"), the same
precedent `2026-07-18-llm-budget-gate-design.md` already set. A 5-task
ACM well under the count threshold below whose Planned-ops text induces
one task to consume unusually many turns before hitting its one-retry-
then-escalate failure path is not caught by either cap -- this is a
named, accepted residual gap, not a solved one, tracked as an open input
in the design doc rather than invented here. Two concrete caps for what
*is* bounded:

- **Task/wave count.** If decomposition would produce more tasks than
  the Workflow tool's own documented "Large workflow" informational
  threshold (25+ agents, per design doc Decision 9), treat that as a
  signal requiring the same authorization-gate confirmation an
  irreversible task requires below -- not a hard block, since a
  genuinely large Branch Plan is a real, legitimate case, but not a
  silent auto-proceed either.
- **Re-plan recurrence.** `stop-and-replan` firing more than once for
  the same parent issue/Branch Plan (design doc Decision 8's failure
  dispatch) escalates instead of re-planning a third time -- a Branch
  Plan that fails to converge after one correction is a signal for human
  judgment, not another autonomous attempt.

## Row-to-task mapping (many-to-many, not one-to-one)

- One ACM row decomposes into more than one task when its Planned ops
  touch independent files or independent concerns (e.g. "add a script and
  update two docs" becomes three tasks).
- Multiple ACM rows collapse into one shared task when their Planned ops
  touch the same file -- this is the file-contention rule; two tasks that
  would write the same file are merged into one task or made
  sequential-dependent, never run in the same parallel wave.

Write the task list in the same
`docs/superpowers/plans/<date>-<branch-name>.md` shape this repository
already uses for other design-then-implement passes (Task / Files /
numbered Step). Each task line cites the
ACM row(s) it satisfies, so the row-to-task mapping stays traceable in
both directions.

## Two dependency-edge types, both computed before wave assignment

1. **File-ownership edge.** Build a file path -> task ID map before
   wave/pipeline assignment; any two tasks that would write the same file
   share an edge.
2. **Interface-dependency edge.** At decomposition time, check each
   task's own Planned ops against every other task's Planned ops for a
   stated or clearly implied producer/consumer relationship (a function
   signature, an exported type, a config key, a schema one task's output
   another task's own text consumes). Where genuinely ambiguous (neither
   task's own text settles whether the edge exists), treat the pair as
   dependent -- the same fail-closed default this skill uses at every
   other uncertain-classification point.

A task pair connected by either edge type is sequenced, never co-assigned
to the same parallel wave -- each wave, in this sense, is simply the set
of tasks with no edge of either type between any pair, a plain
consequence of this step's own output, not a separately named concept
elsewhere in this skill's vocabulary (see `docs/glossary.md`'s `Task`
entry; design doc Decision 10 resolves "wave" itself the same way --
described in prose only, never adopted as a formal term).

## Irreversibility classification

Classify each task's own Planned ops for irreversibility at this same
decomposition step (a schema migration, a data deletion, and similar
one-way operations are irreversible; most file edits are not). A task
classified irreversible carries that flag into step 6/7: it requires the
same authorization-gate confirmation step 1 already defines, re-run for
that specific task, before its own wave dispatches -- not only at the
Branch-Plan-wide entry point.

## Per-task diff BASE (screening precondition, used at step 6)

Record the BASE commit immediately before each task's own dispatch, and
screen `BASE..HEAD` from that task's own worktree at merge-back time --
never `HEAD~1`. With worktree merge-backs landing on the shared branch
out of task-dispatch order, `HEAD~1` is not reliably that task's own
diff.

## Worked example

ACM row: "add a config field, wire it into two call sites, document it."

- Task A: add the field to the config schema file.
- Task B: wire call site 1 (interface edge on Task A -- reads the field's
  final name).
- Task C: wire call site 2 (interface edge on Task A; no file or
  interface edge with Task B -- disjoint call sites).
- Task D: document the field (interface edge on Task A; no edge with B or
  C).

wave 1: {A}. wave 2: {B, C} (no edge between them). wave 3: {D} (edge on
A only, but A already completed by wave 1 -- D could in principle join
wave 2 if its own interface edge is only on A, not on B/C; whether D
joins wave 2 or gets its own wave 3 depends on whether D's own Planned
ops also read something B or C produces -- if not, collapsing D into wave
2 is correct and this worked example's 3-wave shape is the more
conservative, not the only correct, wave assignment).

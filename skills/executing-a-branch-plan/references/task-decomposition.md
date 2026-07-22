# Task Decomposition

Step 3's own detail. Source: design doc Decisions 3, 15, 19.

## Row-to-task mapping (many-to-many, not one-to-one)

- One ACM row decomposes into more than one task when its Planned ops
  touch independent files or independent concerns (e.g. "add a script and
  update two docs" becomes three tasks).
- Multiple ACM rows collapse into one shared task when their Planned ops
  touch the same file -- this is the file-contention rule; two tasks that
  would write the same file are merged into one task or made
  sequential-dependent, never run in the same parallel wave.

Write the task list in the same `docs/superpowers/plans/<date>-<branch-
name>.md` shape this repository already uses for other design-then-
implement passes (Task / Files / numbered Step). Each task line cites the
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
to the same parallel wave. A "wave" is the set of tasks with no edge of
either type between any pair, computed from this step's own output --
not a separately named concept elsewhere in this skill's vocabulary (see
`docs/glossary.md`'s `Task` entry).

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

Wave 1: {A}. Wave 2: {B, C} (no edge between them). Wave 3: {D} (edge on
A only, but A already completed by wave 1 -- D could in principle join
wave 2 if its own interface edge is only on A, not on B/C; whether D
joins wave 2 or gets its own wave 3 depends on whether D's own Planned
ops also read something B or C produces -- if not, collapsing D into wave
2 is correct and this worked example's 3-wave shape is the more
conservative, not the only correct, wave assignment).

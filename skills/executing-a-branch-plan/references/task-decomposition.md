# Task Decomposition

Step 3's own detail. Source: design doc Decisions 3, 15, 19.

## Contents

- [Malformed or empty ACM](#malformed-or-empty-acm-precondition-checked-before-any-of-the-below)
- [Fan-out bound](#fan-out-bound-blast-radius-control-checked-once-the-task-list-exists)
- [Row-to-task mapping](#row-to-task-mapping-many-to-many-not-one-to-one)
- [Verbatim-quotation discipline](#verbatim-quotation-discipline)
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

## Verbatim-quotation discipline

The task-list writer quotes each ACM row's own Planned-ops text into
that row's task record (an explicit citation field naming the row and
quoting its Planned-ops column) rather than paraphrasing it. This
grounds the pinned interface-dependency-edge judgment (above) in the
ACM's actual source text, not a summary that may have silently dropped
or reworded the detail the judgment depends on -- a weak-tier paraphrase
is exactly the failure mode this discipline exists to close, since the
pinned judgment reads whatever the task record actually says, not the
original ACM. The quoted text still goes through [domain-events-and-
failure-handling.md's own "Escape before
interpolating"](domain-events-and-failure-handling.md#event-vocabulary-closed-set-append-only-one-line-per-event)
rule before it is written into the committed, GitHub-rendered task-list
file -- verbatim quotation is not an exemption from that rule, since a
row's Planned-ops text carries the same untrusted-issue-body provenance
every other quoted field there already accounts for.

A task decomposing one ACM row into several tasks (the many-to-many
case above) quotes the same source text into each of those tasks; a
task merging several ACM rows (the file-contention case above) quotes
each contributing row's own text into that one task's record, not a
fused paraphrase combining them.

**Residual risk, named explicitly rather than left implicit (found by an
adversarial `battle-testing-a-skill` pass on this discipline's own
addition).** Verbatim quotation is safe only because step 2's own
`untrusted-input-triage` pass already ran against the ACM's text before
any row reaches this step -- see
[threat-model-and-authorization.md's Per-task
screening](threat-model-and-authorization.md#per-task-screening). A row
that step 2 false-negatives on now propagates unparaphrased into its own
task record and, from there, into that task's own dispatched
`agent()` prompt -- where a paraphrase step might previously have
diluted or reworded an injected instruction as an unintended side
effect, verbatim quotation no longer does. This discipline does not add
a new screening layer at the task-agent level; it deliberately trades
away that incidental, unreliable side effect for the ACM-row-fidelity
this section exists to guarantee, on the premise that step 2's own
pinned judgment (not an accidental paraphrase) is the actual control
this skill relies on to catch an injected row before it is ever quoted
anywhere.

## Two dependency-edge types, both computed before wave assignment

1. **File-ownership edge.** Build a file path -> task ID map before
   wave/pipeline assignment; any two tasks that would write the same file
   share an edge. `scripts/check_file_ownership_conflicts.py` mechanizes
   this map-building/conflict-detection step -- a deterministic
   pre-filter, not a full replacement: a clean result from it is never
   itself grounds to skip the interface-dependency edge judgment below
   for the same task pair, since that is a different edge type entirely
   (a shared-file conflict and a producer/consumer relationship are
   independent judgments -- a task pair can carry one, the other, both,
   or neither).
2. **Interface-dependency edge.** At decomposition time, check each
   task's own Planned ops against every other task's Planned ops for a
   stated or clearly implied producer/consumer relationship (a function
   signature, an exported type, a config key, a schema one task's output
   another task's own text consumes). Where genuinely ambiguous (neither
   task's own text settles whether the edge exists), treat the pair as
   dependent -- the same fail-closed default this skill uses at every
   other uncertain-classification point. **Model/effort pin.** Unlike
   the file-ownership edge above (pure string matching, no pin needed),
   this is a semantic judgment over free-text descriptions that no
   deterministic check can make -- pinned to the same stronger-reasoning
   tier and default-or-higher effort as the Authorization gate and
   Per-task screening's residual judgment
   (`references/threat-model-and-authorization.md`), for the same
   reason: a missed edge here lets two genuinely dependent tasks
   co-dispatch into the same wave, racing on an interface neither task's
   own worktree-isolated diff reveals until merge-back.

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

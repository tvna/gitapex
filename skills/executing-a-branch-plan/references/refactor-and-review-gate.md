# Refactor and Review Gate

Steps 6 and 8's own detail. Source: design doc Decisions 12, 14.

## Per-task Red-Green (step 6, not this gate)

For a task whose inherited proof method is an automatable test (a unit
test, a command assertion), reuse `issue-to-fix/SKILL.md` steps 3-4
verbatim rather than inventing a new discipline:

- **Red.** Write that test first and run it to confirm it fails for the
  right reason, before touching any implementation code.
- **Green.** Implement the smallest change that makes the test pass -- no
  surrounding refactor, no unrelated cleanup bundled in.

**Scope boundary.** Not every task's inherited proof method is an
automatable test -- a task decomposed from an ACM row whose proof method
is inherently manual (e.g. "design doc reviewed and approved") has no Red
step to run. Red-Green applies only when the inherited proof method is
genuinely code-verifiable; this is a per-task judgment made at
decomposition time (`task-decomposition.md`), not a blanket rule forced
onto every task regardless of what its own row actually asks for.

**Refactor is deliberately NOT per-task.** Doing it inside each task's
own isolated context would duplicate this gate's own aggregate pass below
and reintroduce the exact blind spot that pass exists to close: a task
refactoring only what it can see cannot catch the cross-task redundancy
two independently-executed parallel tasks can produce with no visibility
into each other's diff. Refactor happens exactly once, in the aggregate
pass below, after all tasks complete -- not duplicated per task and not
skipped.

## Mandatory aggregate refactor + adversarial review (step 8)

Inserted between "all tasks complete" and "mark ready for review" --
sequence-gated, not a step this skill can rationalize skipping under time
pressure, the same fail-closed shape as the step-1 authorization gate and
step-2/6 screening.

1. **Refactor/simplify pass**, over the full accumulated diff (every
   task's own diff combined), not per-task. A fresh subagent dispatch,
   distinct from the task agents that wrote the code -- the same agent
   grading its own homework is a weaker check than an independent one.
   This pass finds and fixes reuse, redundancy, and dead code that
   parallel/pipeline task execution can hide, but may not change
   behavior -- any behavior-affecting finding is out of this sub-step's
   scope and routes to sub-step 2 instead.
2. **Adversarial code review**, a separate fresh subagent dispatch (not
   the refactor pass's own subagent, same independence reason) reviewing
   the full accumulated diff for correctness bugs. Findings -> verify
   each -> fix confirmed ones -> validate the fix.

**Distinct from step 2/6's screening.** That screening checks each task's
own diff for *security* threats as each task completes. This gate reviews
the *whole* accumulated diff for *correctness* (logic bugs, missed edge
cases, inconsistency introduced by independently-executed parallel tasks)
once, after all tasks are done. Both run; neither substitutes for the
other.

**Not itself parallelized.** This stage runs once, after step 6's own
wave-by-wave execution has already completed: a single reviewer needs the
full accumulated diff to catch cross-task inconsistencies no one task's
own context can see.

**Full re-verification after any fix.** After every CONFIRMED finding's
fix is applied, re-run every task's own Red-Green test above -- not only
the one related to the fix -- before step 9. The last gate before
hand-off does not rest on an unverified "the fix didn't break anything
else" assumption. An outstanding CONFIRMED finding, or a re-verification
failure, blocks step 9.

**Push every fix commit as it lands, same as step 6's per-wave push.** A
fix applied and verified only in the local working copy leaves the
ready-for-review PR (step 9) not actually containing what it claims to
-- step 9's own remote-state check exists specifically to catch a fix
commit that never made it to the remote.

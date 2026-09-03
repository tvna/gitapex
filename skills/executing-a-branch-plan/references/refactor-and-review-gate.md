# Refactor and Review Gate

Steps 6 and 8's own detail. Source: design doc Decisions 12, 14.

## Contents

- [Per-task Red-Green](#per-task-red-green-step-6-not-this-gate)
- [Mandatory aggregate refactor + adversarial review](#mandatory-aggregate-refactor--adversarial-review-step-8)

## Per-task Red-Green (step 6, not this gate)

For a task whose inherited proof method is an automatable test (a unit
test, a command assertion), apply the Red/Green discipline described
immediately below -- this gate's own definition, not borrowed from
elsewhere:

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

**Model/effort pin.** Both dispatches below carry the same pin as the
Authorization gate and Per-task screening's residual judgment
(`references/threat-model-and-authorization.md`): a stronger-reasoning
model tier at default-or-higher effort. The adversarial-review dispatch
is the specific carrier: its own Stop boundary below already requires
constructing a case built to defeat a diff's own detection logic
whenever the diff touches a deterministic gate/check script -- itself a
judgment-heavy bar no weaker tier is pinned to attempt reliably, and a
missed defeat-case here ships a checker script that looks tested but
silently does not catch what it claims to.

1. **Refactor/simplify pass**, over the full accumulated diff (every
   task's own diff combined), not per-task. A fresh subagent dispatch
   (`agentType: 'branch-plan-task'` -- this agent type's own second
   sanctioned call site, alongside Step 6's per-task dispatch; see
   `agents/branch-plan-task.md`'s own "Sanctioned call sites" section),
   distinct from the task agents that wrote the code -- the same agent
   grading its own homework is a weaker check than an independent one.
   This pass finds and fixes reuse, redundancy, and dead code that
   parallel/pipeline task execution can hide, but may not change
   behavior -- any behavior-affecting finding is out of this sub-step's
   scope and routes to sub-step 2 instead.
2. **Adversarial code review**, a separate fresh subagent dispatch (not
   the refactor pass's own subagent, same independence reason;
   `subagent_type: 'review-persona'` -- that agent's own 4th sanctioned
   call site, see `agents/review-persona.md`'s own "Sanctioned call
   sites" section) reviewing the full accumulated diff for correctness
   bugs, and returning findings only. `review-persona`'s own `tools: Read, Grep, Glob` allow-list means this dispatch cannot itself verify
   a finding against a live check, apply a fix, or validate one -- it is
   read-only by construction, not merely by convention. That work
   happens outside this dispatch, in the calling main thread: verify
   each returned finding, fix the confirmed ones, and validate the fix
   -- never inside the review dispatch itself, which has no tool that
   could perform any of the three, and never dispatched to the refactor
   pass's own subagent (sub-step 1 above), whose own "Sanctioned call
   sites" entry restricts it to behavior-preserving edits only -- a
   confirmed correctness-bug fix is behavior-affecting by definition and
   so falls outside that entry's own scope.

**Deterministic gate/check script scrutiny.** When the diff adds,
extends, *or narrows* a deterministic gate or check script -- a CI
workflow script, a new check function in a shape-checker, or any code
whose job is to detect or validate a defined condition in a diff, tree,
or document -- happy-path tests passing is not sufficient grounds to
call that script done. A narrowing edit (loosening a regex, deleting a
deny pattern, adding an exemption, raising a threshold) is in scope
exactly like an additive one; "no new detection logic was added" is not
an exit from this sub-step.

Before this sub-step can clear it, construct at least one case built
specifically to defeat the script's detection logic on its own terms:
the exact condition the check exists to catch, reshaped to fall just
outside whatever heuristic it applies (for example: a rename bundled
with enough of a rewrite to break a similarity-based rename detector, a
text scan bounded to the wrong section of a document, a claim written
into a comment or docstring that was never actually verified against
real behavior). For a narrowing edit, the case instead targets the
newly-widened boundary: an input sitting just inside the new exemption
or threshold that must still not smuggle through anything the check's
own purpose says it must keep catching -- ground that purpose in the
originating issue or design decision, not only a docstring the same diff
is free to write narrowly. Commit the case to the script's own test
suite as a regression test asserting the correct outcome -- one only
constructed and run once, then discarded, can be silently reintroduced
by a later edit with nothing left to catch it.

A defeat-case that still succeeds must either be fixed before step 9, or
explicitly disclosed as a known limitation next to the script's own
documentation -- and disclosure is only acceptable for a structural
limit of the check's own approach (the same class of ceiling
`scripts/check_task_bash_safety.sh` discloses for regex-based
obfuscation), not an ordinary, fixable gap the current diff itself
introduced or loosened. Leaving it neither fixed nor disclosed does not
clear this sub-step.

When a sibling script in the repository already implements matching
parsing or detection logic over the same data shape, diff the new logic
against that sibling's own and determine, from actual behavior against a
real case, which side is correct before reconciling -- mere agreement is
not the bar, and a pre-existing sibling is not automatically ground
truth (the same install-time-versus-runtime-content-trust question this
skill's Notes section already applies elsewhere, not something this step
gets to assume away). Treat a reconciliation-driven edit as a fix subject
to this gate's own re-verification rule below. If it is genuinely
unclear which side is correct, that is a step-7 escalation, not a guess
made in place.

A check whose own stated purpose (what its docstring or description says
it exists to catch) is not actually exercised end-to-end by at least one
such adversarial case is not yet complete, regardless of how many
happy-path tests already pass.

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

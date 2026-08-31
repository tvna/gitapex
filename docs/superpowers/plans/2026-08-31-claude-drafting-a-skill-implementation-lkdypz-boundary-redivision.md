# Branch Plan: redivide drafting-a-skill/scorer-gated-skill-edits boundary

Branch: `claude/drafting-a-skill-implementation-lkdypz` (existing, reused
-- no new branch or PR; lands on PR #1632 per issue #1648's own
Constraints/ACM row 5)
Issue: https://github.com/tvna/gitapex/issues/1648
Design doc: `docs/superpowers/specs/2026-08-31-drafting-a-skill-scorer-gated-boundary-design.md`

This is the second Branch Plan executed on this branch this session --
the first (`2026-08-31-claude-drafting-a-skill-implementation-lkdypz.md`,
issue #1630) is unaffected and stays as historical record. This plan's
own commits land on top of that work's already-pushed HEAD (`3d656d93`).

## Row-to-task mapping

ACM rows 1 and 2 (issue #1648) both write to
`skills/drafting-a-skill/SKILL.md` and its `metadata/gitapex.yaml` --
collapsed into one task (Task A), the same file-contention rule the
prior plan on this branch already applied. ACM row 3 writes to
`skills/scorer-gated-skill-edits/SKILL.md` and its own
`metadata/gitapex.yaml` (Task B) -- a disjoint file set from Task A, but
**connected to it by an interface-dependency edge**, not file-ownership
alone: both tasks describe the same cross-skill dispatch contract (the
Step 7-deferral branch Task A writes into `drafting-a-skill/SKILL.md`,
and the "dispatches drafting-a-skill, deferring Step 7" wording Task B
writes into `scorer-gated-skill-edits/SKILL.md`) and must state it
identically. The prior Branch Plan on this same branch judged an
analogous pair of tasks (row 8 / the edit floor) to have no
interface-dependency edge, and Step 8's own adversarial review later
found a real cross-task collision anyway -- this plan does not repeat
that miss: Task A and Task B are sequenced, not parallelized, and Task
B's own dispatch prompt quotes Task A's actual committed wording
verbatim rather than re-deriving it independently. ACM row 4 writes to
`skills/executing-a-branch-plan/references/task-decomposition.md`,
`skills/executing-a-branch-plan/SKILL.md`, and
`evals/drafting-a-skill/tasks/existing-skill-routes-away.yaml` (Task C)
-- a disjoint file set from both A and B, and no interface-dependency
edge on either (the floor-removal and routing-consolidation text is
generic, referencing `drafting-a-skill` by name/convention rather than
consuming any specific new wording Task A or B produce). ACM row 5 is a
process/sequencing constraint (land on the existing PR #1632 branch, no
new PR), not a file-edit criterion -- it is satisfied by this plan's own
execution approach (below), not a fourth task.

## Task A (ACM rows 1 + 2)

**Files:** `skills/drafting-a-skill/SKILL.md`,
`skills/drafting-a-skill/metadata/gitapex.yaml`

**Quoted Planned ops (row 1):** "Rewrite `drafting-a-skill/SKILL.md`'s
Precondition, Step 1 wording, Postcondition, and Related skills'
`scorer-gated-skill-edits` row per the design doc's own Scope/Design
sections."

**Quoted Planned ops (row 2):** "Add the branch to
`drafting-a-skill/SKILL.md` Step 7 and restate the Postcondition's Step
7 completion condition to cover both cases."

**Steps:**
1. Precondition: remove "If the target `SKILL.md` already exists, this
   is `scorer-gated-skill-edits`'s job, not this skill's -- it does not
   loop back into iterative editing once a first draft is done." Add a
   second legitimate dispatch context: "dispatched by
   `scorer-gated-skill-edits`'s own Step 3, as one bounded iteration
   within its own measured gate loop." Keep the existing
   "already a finished draft awaiting judgment" routing bullet
   unchanged.
2. Step 1: adjust wording so capturing "the candidate's job" reads
   naturally whether the target is a brand-new skill or a change to an
   existing one (no behavior change, wording only).
3. Step 7: add a new branch, gated strictly on dispatch-context identity
   (which skill's own procedure issued the call), never on any claim in
   the ACM/Planned-ops text -- dispatched from `scorer-gated-skill-
   edits`'s Step 3, Step 7's handoff is deferred to that skill's own
   final pre-ship step; dispatched from `executing-a-branch-plan`, Step
   7 runs exactly as today, unconditionally, no exceptions. Re-read
   every existing Stop boundary asserting Step 7 runs "unconditionally"
   after this edit to confirm none of them are weakened for the
   ordinary dispatch path.
4. Postcondition: restate the Step 7 completion condition to cover both
   cases (handoff completed, or structurally deferred per the new
   branch).
5. Related skills: rewrite the `scorer-gated-skill-edits` row to
   describe the new relationship (dispatches this skill per iteration
   for patch-authoring) rather than "iterates an existing SKILL.md ...
   this skill only authors from a blank page."
6. Add a `kind: decision` entry to `drafting-a-skill/metadata/
   gitapex.yaml`'s own decision log, citing issue #1648, recording this
   redivision and its rationale (read the sidecar's current content
   first; append, never regenerate).
7. Run `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   and `python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
   against `skills/drafting-a-skill/`; fix until both exit clean. This
   also satisfies the still-currently-active "Existing-skill-file edit
   floor" (`task-decomposition.md`, not yet removed until Task C lands)
   for this task's own edit to an existing `SKILL.md` -- also sweep
   every touched section against `formative-quality-dimensions.md`
   (excluding row 8, per that floor's own exclusion) before reporting
   complete.
8. Report Task A's own final, committed wording for the Step 7 branch
   and the Precondition's new dispatch-context entry in this task's own
   completion message -- Task B's own dispatch prompt (wave 2) quotes
   this verbatim.

**Proof method:** deterministic checkers clean; every "unconditionally"
Stop boundary re-read; formative-quality-dimensions.md sweep (floor
still active for this task).

**Irreversibility:** none (documentation/skill-definition edits only).

## Task B (ACM row 3)

**Depends on Task A (interface-dependency edge) -- wave 2, dispatched
only after Task A's own commit lands and its final wording is known.**

**Files:** `skills/scorer-gated-skill-edits/SKILL.md`,
`skills/scorer-gated-skill-edits/metadata/gitapex.yaml`

**Quoted Planned ops:** "Rewrite `scorer-gated-skill-edits/SKILL.md`
Step 3 and add the new pre-ship full-review requirement per the design
doc."

**Steps:**
1. Step 3 ("Propose bounded edits"): add that the bounded candidate
   patch for this iteration is authored by dispatching
   `drafting-a-skill`, through its own Step 6 only (shape/drift checkers
   clean), with Step 7 explicitly deferred per Task A's own committed
   branch wording (quoted verbatim from Task A's completion message, not
   re-derived). Every existing constraint in this step (edit-count cap,
   localized-patch preference, pruning-only predeclaration and its
   context-cost measure, the cross-reference sweep for a changed
   enumerated/ordinal item) stays unchanged.
2. Add a new requirement near Step 8's existing recommended
   adversarial-prose pass: once the iteration loop concludes and the
   accepted content is about to ship, run `drafting-a-skill`'s own Step
   7 exactly once against that final content, before filing the PR.
   Exact placement (adjacent to Step 8, a new step, or folded into Step
   8) is this task's own judgment call, per the design doc's own
   disclosed open point.
3. Stop boundaries: clarify "it does not review a skill for merge" to
   state `drafting-a-skill`'s own Step 7 carries that final review once;
   clarify "never edits [the skill under test] on the strength of its
   own gate result" to name `drafting-a-skill` as the one skill that
   performs the actual edit.
4. Confirm by diff that the Precondition gate (scorer + held-out split),
   Steps 4-7 (gate, log, transfer-check, record), and the run-record
   schema are unchanged -- issue #1648's own Constraints forbid touching
   them.
5. Add a `kind: decision` entry to `scorer-gated-skill-edits/metadata/
   gitapex.yaml`'s own decision log, citing issue #1648 (read current
   content first; append, never regenerate).
6. Run `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   and `python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
   against `skills/scorer-gated-skill-edits/`; fix until both exit
   clean. Also satisfies the still-currently-active edit floor for this
   existing-`SKILL.md` edit (formative-quality-dimensions.md sweep,
   excluding row 8).

**Proof method:** deterministic checkers clean; diff confirms Steps
4-7/Precondition/run-record schema untouched; Task A's exact wording
reproduced verbatim, not paraphrased.

**Irreversibility:** none (documentation/skill-definition edits only).

## Task C (ACM row 4)

**Files:** `skills/executing-a-branch-plan/references/task-decomposition.md`,
`skills/executing-a-branch-plan/SKILL.md`,
`evals/drafting-a-skill/tasks/existing-skill-routes-away.yaml`

**Quoted Planned ops:** "Edit `task-decomposition.md` and
`executing-a-branch-plan/SKILL.md` Step 3's own pointer to the floor;
re-verify `evals/drafting-a-skill/tasks/existing-skill-routes-away.yaml`
(added this session for the floor's own Stop boundary) against the new
routing rule, updating or retiring it as the review finds necessary."

**Steps:**
1. Delete `task-decomposition.md`'s "## Existing-skill-file edit floor"
   section in its entirety, including the classification step it
   introduced.
2. Add a single, unified routing rule in its place (or adjacent to the
   existing "brand-new-directory trigger" text this section's own
   opening sentence already cites): any task whose Planned ops create or
   edit a `SKILL.md`, new or existing, routes to `drafting-a-skill`.
   `scorer-gated-skill-edits` stays a separate, opt-in route reached
   only when a task's own Planned ops state a scorer and a held-out
   split.
3. Update `executing-a-branch-plan/SKILL.md` Step 3's own existing
   pointer (line 70: "Classify each task's Planned ops for
   irreversibility and for an *existing* `SKILL.md` edit") so it reads
   consistently with the new unified rule rather than the removed
   floor's own classification step -- reword only if the removal
   actually makes this line stale; if it still reads correctly against
   the new rule, leave it unchanged and say so.
4. Re-read `evals/drafting-a-skill/tasks/existing-skill-routes-away.yaml`
   against the new routing rule. Its own scenario ("the existing
   `scanning-leaked-secrets` skill already exists... I want you to
   improve it") and its `expected.exercises` entry (the "Never loop back
   into `scorer-gated-skill-edits`-shaped iterative editing" Stop
   boundary) both still describe real, current `drafting-a-skill`
   behavior under the new rule -- confirm this holds, and update or
   retire the fixture only if it does not.
5. Grep both edited files, and `evals/drafting-a-skill/tasks/`, for any
   remaining reference to the removed floor or its own section anchor
   (`#existing-skill-file-edit-floor`) -- fix any dangling link.
6. Run `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   against `skills/executing-a-branch-plan/` if `SKILL.md` itself was
   touched; fix until clean.

**Proof method:** grep confirms no dangling reference to the removed
floor; fixture re-verification result stated explicitly (held or
updated); deterministic checker clean if `SKILL.md` was touched.

**Irreversibility:** none (documentation/skill-definition edits only).

## File-ownership map

| Task | Files |
|---|---|
| A | `skills/drafting-a-skill/SKILL.md`, `skills/drafting-a-skill/metadata/gitapex.yaml` |
| B | `skills/scorer-gated-skill-edits/SKILL.md`, `skills/scorer-gated-skill-edits/metadata/gitapex.yaml` |
| C | `skills/executing-a-branch-plan/references/task-decomposition.md`, `skills/executing-a-branch-plan/SKILL.md`, `evals/drafting-a-skill/tasks/existing-skill-routes-away.yaml` |

No overlap between A, B, and C.

## Interface-dependency map

**A -> B**, one edge: both tasks state the same cross-skill dispatch
contract (the Step 7-deferral branch) in their own file. Task B is
sequenced after Task A and quotes Task A's own final committed wording
verbatim.

No edge between C and either A or B: Task C's routing-consolidation text
is generic (references `drafting-a-skill` by name/convention), consuming
no specific new wording either A or B produce.

## Wave assignment

Wave 1: {Task A, Task C} -- no file-ownership or interface-dependency
edge between them, so they co-assign to the same parallel wave.
Wave 2: {Task B} -- sequenced after Task A (interface-dependency edge),
dispatched once Task A's own commit lands and its final wording is
known. No dependency on Task C, but Task C's own wave-1 completion
already gates wave 2's dispatch regardless (waves execute in order).

## Execution notes specific to this Branch Plan

- No new branch, no new PR (ACM row 5). All task commits land on the
  existing `claude/drafting-a-skill-implementation-lkdypz` branch, on
  top of the already-pushed `3d656d93` HEAD. `branch-plan-executing` is
  already applied to PR #1632 from the prior round on this branch and
  stays applied through this round too.
- Step 5's "open a draft PR" does not apply (PR #1632 already exists,
  already draft, already subscribed). This plan's own step 4-5
  equivalent is: commit this task-list file to the existing branch,
  push, and append a new `PlanApproved{run_id: <this plan's own id>}`
  event to PR #1632's existing `## Execution log` section (read-modify-
  write, never overwriting the prior round's own already-recorded
  events) -- a fresh `run_id`, distinct from the prior round's
  `e2c59a93`, since this is a materially different plan, not a
  continuation of it.

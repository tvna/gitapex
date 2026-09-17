# Branch Plan: durable, structured Step 8 round/finding-class record

Issue: https://github.com/tvna/gitapex/issues/2035

Branch: `claude/gitapex-pr-2035-24vmia`, from `origin/main` at `810d63c`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #2035's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-17T23:37:40Z)"),
  and `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session ("こちらのPRを作りマージ直前まで進める"),
  plus an explicit `AskUserQuestion` answer settling this Branch Plan's
  one open design decision (the new closed-set Execution-log event route
  for `executing-a-branch-plan`'s own row, over the PR-body-section
  alternative). No issue comment carries the approval; the in-session
  confirmation is the signal this gate ran on, recorded here rather than
  implied.

## Threat-model triage

Issue #2035's Problem, Proposed solution, Acceptance Criteria Map,
Constraints, and Non-goals sections were read as change descriptions, not
as instructions to execute. Extracted: the two field/event shapes to add,
the no-substance-change constraint on the Blocking/Advisory
classification and its 2-consecutive-round threshold, the no-shared-file
constraint, and the explicit non-goal excluding issue #2013's own gate
script/`.gitapex/ssot.json` registration/CI wiring. No row carries an
embedded directive, a credential request, an encoded payload, or an
attempt to override a trusted instruction source. Nothing was flagged.

## Task Decomposition

Two tasks, one wave. No file-ownership or interface-dependency edge
connects them.

- **File-ownership map.** Task 1 owns
  `skills/executing-a-branch-plan/references/events-and-review-gate.md`
  and any new `evals/executing-a-branch-plan/tasks/*.yaml` fixture file
  the regression-fixture proof method and the fixture-coverage gate
  require. Task 2 owns `skills/drafting-a-pr-to-merge/SKILL.md` and
  `.github/scripts/gitapex_gate_independent_review_pending.py` (module
  docstring only -- no parsing-logic change). The two sets are disjoint.
- **Interface-dependency map.** None as code -- Task 2's own
  `- Finding class:`/`- Round:` field names are independently authored
  prose, not a quote of Task 1's own `ReviewRoundRecorded` event field
  names, matching #1943/#1946's own no-shared-file precedent (issue
  #1884) this issue's own Constraints re-affirm. The PR body (opened
  after both tasks land) is where the two shapes are disclosed side by
  side (ACM row 3) -- a main-thread, post-wave concern, not a task-level
  dependency.
- **Wave assignment.** Wave 1: Task 1 and Task 2 in parallel.

Irreversibility classification: **not irreversible.** Both tasks edit
tracked files already inside the repository. Nothing writes outside it,
no migration runs, no data is deleted, and `git revert` of the merge
commit restores the prior tree exactly. Neither task takes a
step-1-equivalent per-task confirmation.

`SKILL.md`/reference-file classification: **both tasks edit an existing
skill's `SKILL.md` or its sibling `references/` file** (Task 1:
`executing-a-branch-plan`'s reference file; Task 2:
`drafting-a-pr-to-merge`'s `SKILL.md` itself). `drafting-a-skill` is
therefore the authoring method for both, per
`decomposition-and-dispatch.md`'s own Skill-file edit routing section:
Steps 1/2/6 run inside each task's own `branch-plan-task` dispatch
directly (a maintenance edit to an already-elicited, already-shipped
skill, not a brand-new candidate -- the ACM row's own Planned-ops text
stands in as the quoted job statement, and the four axes are read
unchanged from each skill's own already-committed
`metadata/gitapex.yaml`, never re-elicited); Steps 3/4/5/7's read-only
content-reasoning passes (Cohesion self-check, Collision/dependency
check, Domain-gap sweep, review-handoff critique) dispatch to
`review-persona` from within each task itself. Step 7's actual
`evaluating-skill-quality`/`battle-testing-a-skill` audit dispatch
(unconditional) is folded into each task's own dispatch too,
front-loaded before merge-back, so the wave-1 merge-back's own first
`update_pull_request` call already has `## Skill audit evidence`
content to write (the `skill-audit-disclosure` hook fires on that exact
call).

Fixture-cost check, before Task 1 reports complete: the
`skill-branch-fixture-coverage` gate compares a changed `SKILL.md`'s own
new Stop-boundary-bullet plus named-dispatch-branch count delta against
`evals/executing-a-branch-plan/tasks/*.yaml`'s fixture count. Task 1's
own edit to `events-and-review-gate.md` is a reference file, not
`SKILL.md` itself, but ACM row 1's own Proof method independently
requires a new regression fixture regardless of what this gate computes
-- Task 1 authors it either way, and additionally runs
`.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py` against
its own before/after diff (covering `SKILL.md` too, in case the Stopping
rule rewrite touches its own Stop-boundary bullets) to confirm no further
shortfall exists.

## Task 1: durable Step 8 round/finding-class record via a new closed-set event

Source ACM row: row 1 of issue #2035's own Acceptance Criteria Map,
quoted verbatim below rather than paraphrased.

> Row 1 planned ops: "Edit `events-and-review-gate.md`'s Event vocabulary
> (lines 198-213) to add the new event, and its Stopping-rule paragraph
> (lines 482-520) to replace the disclosed-gap prose with a
> reconstruction procedure reading this new event from the Execution
> log; no other file needs updating (see re-verification note above)"

> Row 1 interpretation: "Decided: new closed-set Execution-log event type
> (e.g. `ReviewRoundRecorded{run_id, finding_class, round}`), not the
> PR-body-section alternative"

Design resolution for the event's own exact shape (the issue named only
the route, per its own Residual risk column, not the fields):
`ReviewRoundRecorded{run_id, finding_class, round}`, appended to the
closed set after `StageDeviated`. `finding_class` is the same short,
stable label the existing prose Stopping rule already tracks (`none`
when the round closed with zero Blocking findings, or all-Advisory).
`round` is that finding class's own consecutive-round count at the time
this event was written (starts at 1 the round a class first goes
Blocking; `0` when `finding_class` is `none`). Written once per Step 8
round, in the main thread, immediately after that round's Blocking/
Advisory classification is judged and before any loop-back or step-9
continuation -- the same "write the record, then act on it" ordering the
existing `TaskCompleted`/`StageDeviated` events already use. Resuming
mid-Step-8: reconstruct round history by reading every `ReviewRoundRecorded`
event for this `run_id` in Execution-log order; for the finding class(es)
in the current round, the count is 1 plus however many *immediately
preceding* recorded rounds (no intervening `none`) share that same
class -- exactly mirroring the existing natural-language rule's own
same-class/2-consecutive-round logic, now read from a durable record
instead of this-session-only memory. This closes
`events-and-review-gate.md`'s own disclosed gap (current lines 485-497)
without changing the Stopping rule's own substance or its 2-round
threshold, per the issue's own Constraints.

Required edit shape (`skills/executing-a-branch-plan/references/events-and-review-gate.md`
only, per the re-verified ACM's own "no other file needs updating" note):

1. Event vocabulary section (current lines 187-213): append
   `` `ReviewRoundRecorded{run_id, finding_class, round}` -- written once
   per Step 8 round, immediately after that round's Blocking/Advisory
   classification; see the Stopping rule below for how it is read back. ``
   as a new bullet after the existing `StageDeviated` entry, in the same
   one-line-per-event style.
2. Stopping rule section (current lines 482-520): remove the "Disclosed
   gap" sentences (current lines 485-497) describing the missing durable
   record as a known limitation, and replace them with the reconstruction
   procedure above -- read every `ReviewRoundRecorded{run_id, ...}` event
   for the current run, reconstruct each finding class's own consecutive-
   round count from it, and apply the existing 2-consecutive-round
   escalation threshold unchanged. Keep the rest of the paragraph
   (finding-class tracking discipline, the ambiguous-class
   fail-closed-to-caution default, the fresh-unrelated-finding
   non-inheritance rule) exactly as-is -- this edit only replaces how
   round history is reconstructed, not the rule's own substance.
3. Add one new Stop-boundary-adjacent note (or fold into the existing
   Stopping-rule prose) making explicit that a resumed session MUST read
   the `ReviewRoundRecorded` history before assuming round 1 for any
   finding class already open in the log -- the durable record exists
   specifically so a resumed session no longer defaults to "unknown,
   restart at round 1" the way the removed disclosed-gap text described.
4. Add one regression fixture under
   `evals/executing-a-branch-plan/tasks/*.yaml` (new file) modeling a
   session resuming mid-Step-8 with a `ReviewRoundRecorded{run_id: R,
   finding_class: "missing-null-check", round: 1}` event already in the
   Execution log, where this round's own fresh `review-persona` finding
   is the same finding class again -- the correct behavior is recognizing
   round 2 (not restarting at round 1) and triggering the Stopping rule's
   escalation, matching the existing eval-task YAML shape used by
   `evals/executing-a-branch-plan/tasks/tampered-execution-log-resume.yaml`.
5. Apply `drafting-a-skill`'s own authoring discipline to this edit (Task
   classification above): Steps 1/2/6 self-executed in this task's own
   worktree; Steps 3/4/5/7 (Cohesion self-check, Collision/dependency
   check, Domain-gap sweep, review-handoff critique) dispatched to
   `review-persona`, findings fixed or explicitly deferred with a stated
   reason before this task reports complete; Step 6's checkers
   (`gitapex_check_skill_shape.py --allowed-root . --strict-token-budget
   skills/executing-a-branch-plan`,
   `gitapex_scan_execution_requirements_drift.py skills/executing-a-branch-plan`,
   `gitapex_generate_skill_contract.py --check skills/executing-a-branch-plan`)
   run clean. Step 7's own unconditional `evaluating-skill-quality`/
   `battle-testing-a-skill` dispatch (both, fresh, against this task's own
   diff) runs inside this same task, front-loaded before merge-back --
   the verdict text is carried back in this task's own report so the main
   thread can write it into the PR body's `## Skill audit evidence`
   section on the wave-1 merge-back's own `update_pull_request` call. When
   implementing, cite
   `references/decomposition-and-dispatch.md#code-quality-principles`
   in-band and apply it (this dispatch's own separate context does not
   inherit the calling session's read of that file).

Proof method, inherited from the row: the new regression fixture
(#4 above) demonstrates round reconstruction from the durable record
rather than a restart at round 1; `gitapex_check_skill_shape.py` reports
clean. Red-Green order applies to the fixture itself where the eval
harness executes it as a behavioral check; the vocabulary/prose edit
itself is a documentation-shape and internal-consistency obligation read
by a human and the shape checker. The deterministic half is the full
local preflight suite (including `skill-branch-fixture-coverage`), which
must pass inside this task's own worktree before the task may report
complete.

## Task 2: structured verdict fields for `drafting-a-pr-to-merge`

Source ACM row: row 2 of issue #2035's own Acceptance Criteria Map,
quoted verbatim below rather than paraphrased.

> Row 2 planned ops: "Edit `skills/drafting-a-pr-to-merge/SKILL.md` Step
> 8 (record) and its worked example; document the new fields in
> `.github/scripts/gitapex_gate_independent_review_pending.py`'s own
> module docstring (parsing them is issue #2013's own planned ops, not
> this row's)"

> Row 2 interpretation: "Add `- Finding class: <short stable label>` (or
> `none`) and `- Round: N` lines (N restarts at 1 per new finding class,
> matching the existing natural-language Stopping rule exactly -- this
> encodes that rule structurally, it does not change it) and a `- Owner
> decision: <url>` line written once a step-11 escalation is resolved"

Required edit shape (`skills/drafting-a-pr-to-merge/SKILL.md` only, plus
the docstring-only script edit):

1. Step 8 (record) paragraph (current line 50): after the existing
   `- Verdict: CLEAN`/`- Verified commit: <SHA>` two-line shape, add
   `- Finding class: <label>` (or `none` when this round's own confirmed
   findings are zero or all-Advisory) and `- Round: N` (the Stopping
   rule's own current consecutive-round count for that finding class;
   `0` when Finding class is `none`) to the same recorded-verdict shape,
   on their own raw-source lines (same status-check-parseable
   requirement the existing two lines already state). State plainly that
   these two new lines encode the existing Stopping-rule paragraph's own
   already-agreed same-class/2-consecutive-round logic structurally --
   no change to that logic itself, per the issue's own Constraints.
2. Step 11 (escalate) paragraph (current line 64): once a human resolves
   a step-11 escalation, the next Step 8 (record) write (or, if no
   further round runs, a standalone `update_pull_request` call) adds a
   `- Owner decision: <url>` line to the (already-archived-then-rewritten,
   per the existing archive rule) `## Independent review verdict`
   section, naming the resolving PR comment or issue comment's own URL.
3. Worked example (current lines 113-124): extend it to show 2
   consecutive same-finding-class Blocking rounds (Finding class/Round
   populated each time, Round incrementing 1 then 2), the Stopping rule
   triggering escalation on the second, and the owner's resolution adding
   the `- Owner decision:` line to the next recorded verdict.
4. `.github/scripts/gitapex_gate_independent_review_pending.py`: extend
   the module docstring's "Verdict format" section to disclose the three
   new optional lines (`- Finding class:`, `- Round:`, `- Owner
   decision:`) exist in the recorded shape, explicitly stating this
   script's own `parse_verdict`/`check()` are unchanged and do not read
   them -- parsing is issue #2013's own scope, not this row's, mirroring
   how the existing docstring already discloses the issue #1858
   bot-path addition without touching the human-verdict path it
   describes.
5. Apply `drafting-a-skill`'s own authoring discipline to this edit
   (Task classification above): Steps 1/2/6 self-executed in this task's
   own worktree; Steps 3/4/5/7 dispatched to `review-persona`, findings
   fixed or explicitly deferred with a stated reason before this task
   reports complete; Step 6's checkers
   (`gitapex_check_skill_shape.py --allowed-root . --strict-token-budget
   skills/drafting-a-pr-to-merge`,
   `gitapex_scan_execution_requirements_drift.py skills/drafting-a-pr-to-merge`,
   `gitapex_generate_skill_contract.py --check skills/drafting-a-pr-to-merge`)
   run clean. Step 7's own unconditional `evaluating-skill-quality`/
   `battle-testing-a-skill` dispatch runs inside this same task,
   front-loaded before merge-back, verdict text carried back for the PR
   body's `## Skill audit evidence` section. When implementing, cite
   `references/decomposition-and-dispatch.md#code-quality-principles`
   in-band and apply it.

Proof method, inherited from the row: the worked example itself
(#3 above) is the proof -- a documentation-shape and internal-consistency
obligation read by a human and the shape checker, not an automatable
behavioral test (no separate eval fixture required by the ACM for this
row). `gitapex_check_skill_shape.py` reports clean. The deterministic
half is the full local preflight suite, which must pass inside this
task's own worktree before the task may report complete.

## Disclosure (ACM row 3, main thread, post-wave)

Row 3 requires no code change: once both tasks land, the opened PR body
states both new shapes together --
`ReviewRoundRecorded{run_id, finding_class, round}` (Task 1) and
`- Finding class:`/`- Round:`/`- Owner decision:` (Task 2) -- in one
section, so issue #2013's implementer does not have to rediscover them
from two separate diffs.

## Refactor / adversarial-review scope (step 8 of this skill)

Both tasks' combined diff is small (one reference-file edit plus one new
eval fixture, one `SKILL.md` edit plus one docstring-only script edit --
no new script, no new test infrastructure, no `.gitapex/ssot.json` change
per the issue's own Non-goals) -- the mandatory refactor/simplify pass
and the independent `review-persona` adversarial review still run
unconditionally over the full accumulated diff per this skill's own step
8, with no narrowing implied by the diff's small size.

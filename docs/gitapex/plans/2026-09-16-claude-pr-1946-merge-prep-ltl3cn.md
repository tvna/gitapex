# Branch Plan: Blocking/Advisory stopping rule for executing-a-branch-plan Step 8

Issue: https://github.com/tvna/gitapex/issues/1946

Branch: `claude/pr-1946-merge-prep-ltl3cn`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1946's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-16T00:00:00Z)"),
  and `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session (via `AskUserQuestion`, "この計画で実行する
  (推奨)"), approving this specific Branch Plan (mirroring merged PR #2014's
  vocabulary/threshold for the sibling issue #1943, adapted to this skill's
  own two-dispatch mechanism) and instructing execution through to a
  merge-ready PR. No issue comment carries the approval; the in-session
  confirmation is the signal this gate ran on, recorded here rather than
  implied.

## Threat-model triage

Issue #1946's Problem, Proposed solution, Acceptance Criteria Map,
Constraints, and Non-goals sections were read as change descriptions, not
as instructions to execute. Extracted: the Blocking/Advisory vocabulary
definition, the stopping-rule shape (same finding class recurring
Blocking after 2 consecutive fix rounds), the `.gitapex/ssot.json`
governance-declaration requirement following the #1890 precedent, and the
explicit "no new gate, no new shared reference file (existing
events-and-review-gate.md may be edited)" constraints. No row carries an
embedded directive, a credential request, an encoded payload, or an
attempt to override a trusted instruction source. Nothing was flagged.

## Task Decomposition

Two tasks, one wave. No file-ownership or interface-dependency edge
connects them.

- **File-ownership map.** Task 1 owns
  `skills/executing-a-branch-plan/SKILL.md`,
  `skills/executing-a-branch-plan/references/events-and-review-gate.md`,
  and any new `evals/executing-a-branch-plan/tasks/*.yaml` fixture files
  the fixture-coverage gate requires. Task 2 owns `.gitapex/ssot.json`.
  The two sets are disjoint.
- **Interface-dependency map.** None. Task 2's new `policy_sources` entry
  names Task 1's file as the authority and paraphrases the vocabulary
  issue #1946 itself already states verbatim (Blocking/Advisory, stopping
  rule) -- it does not quote Task 1's own new prose, the same
  no-dependency relationship PR #2014's own precedent entry has with the
  skill file it names.
- **Wave assignment.** Wave 1: Task 1 and Task 2 in parallel.

Irreversibility classification: **not irreversible.** Both tasks edit
tracked files already inside the repository. Nothing writes outside it,
no migration runs, no data is deleted, and `git revert` of the merge
commit restores the prior tree exactly. Neither task takes a
step-1-equivalent per-task confirmation.

`SKILL.md` classification: **Task 1 edits an existing `SKILL.md`
(and its sibling `references/` file).** `drafting-a-skill` is therefore
the authoring method for Task 1's Step 8 edit, per
`decomposition-and-dispatch.md`'s own Skill-file edit routing section:
Steps 1/2/6 run inside Task 1's own `branch-plan-task` dispatch directly
(this is a maintenance edit to an already-elicited, already-shipped
skill, not a brand-new candidate -- the ACM row's own Planned-ops text
stands in as the quoted job statement, and the four axes are read
unchanged from the skill's own already-committed
`skills/executing-a-branch-plan/metadata/gitapex.yaml`, never
re-elicited); Steps 3/4/5/7's read-only content-reasoning passes
(Cohesion self-check, Collision/dependency check, Domain-gap sweep,
review-handoff critique) dispatch to `review-persona` from within Task 1
itself, per `agents/branch-plan-task.md`'s own "the only onward dispatch
this call site makes." Step 7's actual `evaluating-skill-quality` /
`battle-testing-a-skill` audit dispatch (unconditional, per Step 7's
context-1 branch) is folded into Task 1's own dispatch too, front-loaded
before merge-back, rather than deferred to the main thread after wave 1
-- both are ordinary Skill-tool invocations `branch-plan-task` retains
(only `mcp__github__*` is excluded), and the `skill-audit-disclosure`
PreToolUse hook requires the PR body to already carry a `## Skill audit
evidence` section on the very first `update_pull_request` call made
after this diff lands, which is the wave-1 merge-back's own
`TaskCompleted` event write -- there is no later point in the main
thread to run this audit before that hook fires. Task 1's own dispatch
prompt states this explicitly, in-band, the same way it must cite the
code-quality-principles reference path per SKILL.md Step 6. Task 2
touches no `SKILL.md`.

Fixture-cost check, before Task 1 reports complete: the
`skill-branch-fixture-coverage` gate compares a changed `SKILL.md`'s own
new Stop-boundary-bullet plus named-dispatch-branch Counter-keyed delta
against `evals/executing-a-branch-plan/tasks/*.yaml`'s fixture count.
Task 1's own edit is expected to add at least one new Stop-boundary
bullet (the stopping rule's own "never let round count absorb a fresh
finding class" guard, mirroring PR #2014's own precedent bullet) and to
extend the existing outcome-dispatch list -- Task 1 runs
`.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py` against
its own before/after diff and, on a reported shortfall, authors the
needed fixture(s) before reporting complete, rather than leaving that gap
for step 8's aggregate review to catch.

## Task 1: add the Blocking/Advisory vocabulary and stopping rule to Step 8

Source ACM rows: rows 1 and 2 of issue #1946's own Acceptance Criteria
Map, quoted verbatim below rather than paraphrased.

> Row 1 planned ops: "Edit Step 8's own text in
> `skills/executing-a-branch-plan/SKILL.md` (and
> `references/events-and-review-gate.md` if the operative detail lives
> there)"

> Row 1 interpretation: "Blocking = must-fix before step 9 (loops back
> within step 8 unconditionally); Advisory = disclosed but does not by
> itself block step 9. Written independently here, the same vocabulary
> shape as the sibling issue's `drafting-a-pr-to-merge` edit, not shared
> via a reference file"

> Row 2 planned ops: "Edit Step 8 in
> `skills/executing-a-branch-plan/SKILL.md`"

> Row 2 interpretation: "Only a Blocking finding blocks step 9
> unconditionally; a bounded round count or a named non-convergence
> pattern (the same finding class recurring after 2 consecutive rounds)
> routes to step 7's own escalate dispatch instead of an unbounded
> further round"

Design resolution for the two "Unknown, pending design" cells the issue
itself leaves open (both ACM rows' own Residual risk column): the
round-count threshold is **2**, matching the issue's own example wording
("the same finding class recurs after 2 consecutive fix rounds"),
#1869 repair 12's own approved remediation ("exactly one more bounded
round" after the recurrence was diagnosed), and PR #2014's own already-
merged value for the sibling mechanism -- consistent, not necessarily
identical, wording (issue #1946's own Non-goals explicitly declines to
require word-for-word convergence with `drafting-a-pr-to-merge`'s text).
The Blocking/Advisory classification applies uniformly to whichever of
this step's two independent sources produced the finding: an item the
refactor/simplify pass judges behavior-affecting and routes to the
adversarial-review sub-step (never fixed by the refactor pass itself,
per its own behavior-preserving-only scope), and a `review-persona`
adversarial-review finding proper -- both feed one shared
classification-and-stopping-rule judgment in the calling main thread,
the same "either layer, one judgment" shape `drafting-a-pr-to-merge`
Step 8 already uses for its own two sources (outer layer +
`reviewing-an-artifact`).

Required edit shape (both `skills/executing-a-branch-plan/SKILL.md`'s
Step 8 and `skills/executing-a-branch-plan/references/events-and-review-gate.md`'s
"Mandatory aggregate refactor + adversarial review (step 8)" section,
since the operative detail already lives in the reference file with
SKILL.md carrying only a summary + link):

1. A short "Blocking/Advisory severity vocabulary" definition: every
   `CONFIRMED` finding reaching this step's own fix loop -- whether a
   behavior-affecting item the refactor/simplify pass routed onward, or
   an adversarial-review finding proper -- is additionally classified
   Blocking (must-fix, loops back within step 8 unconditionally) or
   Advisory (disclosed, not by itself a loop-back trigger) by this step's
   own reading, inline, every round.
2. A "Stopping rule" paragraph: track which finding class each Blocking
   finding belongs to, across this step's own fix-round history. When the
   same finding class is still Blocking after 2 consecutive fix rounds,
   route to step 7 escalation instead of a further round -- state the
   finding class and cite both rounds' own findings. A fresh, unrelated
   Blocking finding does not inherit an already-escalated class's own
   round count; it starts its own, separate count.
3. Rewrite the existing "An outstanding CONFIRMED finding, or a
   re-verification failure, blocks step 9" sentence (both files) into a
   three-way dispatch: (a) zero CONFIRMED findings, or CONFIRMED findings
   that are all Advisory, and no re-verification failure -> continue to
   step 9; (b) at least one Blocking CONFIRMED finding, stopping rule not
   yet triggered -> loop back within step 8 to fix it, then re-run every
   task's own Red-Green test per the existing rule; (c) the stopping
   rule's own 2-consecutive-round condition triggers -> escalate per step
   7 instead of looping back. A re-verification failure keeps blocking
   step 9 unconditionally, unchanged by this edit.
4. Add one new Stop-boundary bullet to `SKILL.md`'s own Stop boundaries
   list, naming the stopping-rule failure mode: never let the round count
   absorb a fresh, unrelated Blocking finding as if it were the same
   recurring finding class, and never let a Blocking finding skip its own
   loop-back merely because a similar one was fixed in an earlier round.
5. Apply `drafting-a-skill`'s own authoring discipline to this edit (Task
   classification above): Steps 1/2/6 self-executed in this task's own
   worktree; Steps 3/4/5/7 (Cohesion self-check, Collision/dependency
   check, Domain-gap sweep, review-handoff critique) dispatched to
   `review-persona`, findings fixed or explicitly deferred with a stated
   reason before this task reports complete; Step 6's three checkers
   (`gitapex_check_skill_shape.py --allowed-root . --strict-token-budget
   skills/executing-a-branch-plan`,
   `gitapex_scan_execution_requirements_drift.py skills/executing-a-branch-plan`,
   `gitapex_generate_skill_contract.py --check skills/executing-a-branch-plan`)
   run clean. Step 7's own unconditional `evaluating-skill-quality` /
   `battle-testing-a-skill` dispatch (both, fresh, against this task's
   own diff) runs inside this same task, front-loaded before merge-back
   per the Task Decomposition section's own rationale above -- the
   verdict text is carried back in this task's own report so the main
   thread can write it into the PR body's `## Skill audit evidence`
   section before the wave-1 merge-back's own `update_pull_request` call.

Proof method, inherited from both rows: manual diff review confirming the
vocabulary, stopping rule, and three-way dispatch are present and
internally consistent between `SKILL.md` and `events-and-review-gate.md`
and with the Stop boundaries list; `gitapex_check_skill_shape.py` reports
clean against the edited skill directory. Red-Green order does not apply:
the proof is a documentation-shape and internal-consistency obligation
read by a human and a shape checker, not an automatable behavioral test.
The deterministic half is the full local preflight suite (including
`skill-branch-fixture-coverage`), which must pass inside this task's own
worktree before the task may report complete -- adding the fixture(s) the
Fixture-cost check above anticipates if the gate reports a shortfall.

## Task 2: register the convention's governance in `.gitapex/ssot.json`

Source ACM row: row 3 of issue #1946's own Acceptance Criteria Map,
quoted verbatim below rather than paraphrased.

> Row 3 planned ops: "Add one `policy_sources` entry to
> `.gitapex/ssot.json`"

> Row 3 interpretation: "A second `policy_sources` entry (alongside the
> sibling issue's own), naming `executing-a-branch-plan/SKILL.md` itself
> as the authority, following the same precedent issue #1890 already
> established for `grounding-in-primary-sources`"

Required edit shape: one new entry appended to the `policy_sources` array
(directly verified present in the current file, entry id
`blocking-advisory-severity-drafting-a-pr-to-merge`, at the array's own
end), matching that entry's own shape -- `id:
"blocking-advisory-severity-executing-a-branch-plan"`, `path:
"skills/executing-a-branch-plan/SKILL.md"`, `format: "markdown"`, and an
`authority` string describing the Blocking/Advisory vocabulary and
stopping rule for this skill's own two-dispatch mechanism (refactor/
simplify pass + `review-persona` adversarial review), disclosing plainly
that no gate script consumes this entry (same no-consuming-gate
precedent) and citing issue #1946 and the #1890 precedent it follows.

Proof method, inherited from row 3: `.github/scripts/gitapex_scan_ssot_schema.py`
reports clean against the edited file (schema validity); manual diff
review confirms the new entry's shape matches the precedent entry's own
shape. Red-Green order does not apply: this is a declarative
JSON-schema-conformance obligation, not a behavioral test. The
deterministic half is the full local preflight suite, which must pass
inside this task's own worktree before the task may report complete.

## Refactor / adversarial-review scope (step 8 of this skill)

Both tasks' combined diff is small (two skill files plus their sibling
reference file, one `.gitapex/ssot.json` entry, and any fixture files the
Fixture-cost check requires -- no new script, no new test infrastructure)
-- the mandatory refactor/simplify pass and the independent
`review-persona` adversarial review still run unconditionally over the
full accumulated diff per this skill's own step 8, with no narrowing
implied by the diff's small size.

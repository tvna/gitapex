# Branch Plan: close formative-process gaps in drafting-a-skill

Branch: `claude/drafting-a-skill-implementation-lkdypz`
Issue: https://github.com/tvna/gitapex/issues/1630
Design doc: `docs/superpowers/specs/2026-08-31-drafting-a-skill-formative-process-gaps-design.md`

## Row-to-task mapping

ACM rows 1 and 2 (issue #1630) both write to
`skills/drafting-a-skill/references/formative-quality-dimensions.md` and
`skills/drafting-a-skill/SKILL.md` -- collapsed into one shared task
(the file-contention rule) rather than run as two tasks racing on the
same files. ACM row 3 writes to a disjoint file set
(`skills/executing-a-branch-plan/`) with no interface-dependency edge on
Task A's own output (Task B's new rule is general prose, not consuming
any specific content Task A adds) -- kept as its own task.

## Task A (ACM rows 1 + 2)

**Files:** `skills/drafting-a-skill/references/formative-quality-dimensions.md`,
`skills/drafting-a-skill/SKILL.md`

**Quoted Planned ops (row 1):** "Extend row 4 with the missing bullets
(consistent terminology; workflows as ordered/copyable checklists;
feedback loops on quality-critical steps; templates matched to
strictness; distinct/complete branch triggers, reusing Step 3's own
cohesion enumeration). Add one style bullet to `SKILL.md` Step 2
cross-referencing row 4. Restructure the Worked example section's three
candidates from prose paragraphs into per-candidate Step-keyed bullet
lists, preserving every stated fact unchanged."

**Quoted Planned ops (row 2):** "Extend row 5 (reference naming,
link-context requirement), row 6 (forward-slash paths, `Server:tool`
naming, no-install-assumed phrasing, default+escape-hatch framing,
Portable-declaration convention/authority-path rules), and row 7
(script error handling, no unexplained constants, Interface-vs-
Implementation comment discipline, single ownership). Rewrite row 8
into an eval-preparation instruction (>= 3 scenarios including the
guardrail case, an `evals/<skill>/` fixture skeleton) and move its
displaced concrete-example content into row 4. Add a new sub-step under
`SKILL.md` Step 6 for the scaffolding (preparation only; no
before/after run, no new eval-execution infra)."

**Steps:**
1. Extend `formative-quality-dimensions.md` row 4 with the five missing
   bullets named above.
2. Extend rows 5, 6, and 7 with the bullets named in row 2's Planned ops.
3. Rewrite row 8 into the eval-preparation instruction; move its
   displaced concrete-example content into row 4 instead.
4. Add the Step 2 style bullet to `drafting-a-skill/SKILL.md`
   cross-referencing row 4 (never restate row 4's content in the body,
   per this repository's own "never both" duplication rule).
5. Restructure the Worked example section's three candidates from prose
   paragraphs into per-candidate Step-keyed bullet lists -- every stated
   fact preserved unchanged, layout only.
6. Add the new eval-scaffolding sub-step under Step 6 (scenario
   enumeration + `evals/<skill>/` skeleton; preparation only).
7. Run `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   and `python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
   against `skills/drafting-a-skill/`; fix until both exit clean.
8. Check each new row-4 bullet against `evaluating-skill-quality/references/rubric.md`
   Dimension 4's own Fail/Pass bullets (and rows 5-8 against their own
   mapped dimensions) to confirm no requirement is left unmapped.
9. Diff the restructured Worked example against its prior prose form,
   fact-for-fact, to confirm no candidate's content changed.

**Proof method:** deterministic checkers clean; manual cross-check
against `rubric.md`'s own Fail/Pass bullets per dimension; fact-for-fact
Worked-example diff.

**Irreversibility:** none (documentation/skill-definition edits only).

## Task B (ACM row 3)

**Files:** `skills/executing-a-branch-plan/references/task-decomposition.md`
or `skills/executing-a-branch-plan/SKILL.md` (placement is this task's
own judgment call, per the design doc's own Assumptions)

**Quoted Planned ops:** "Add a rule to `executing-a-branch-plan`
(`task-decomposition.md` or `SKILL.md` Step 3, placement left to the
implementing task's judgment) alongside the existing 'new skill
directory -> apply `drafting-a-skill`' sentence: a task that edits an
existing `SKILL.md`, not otherwise routed to `scorer-gated-skill-edits`
by a stated scorer/held-out-split precondition, must run
`gitapex_check_skill_shape.py` and sweep edited sections against
`formative-quality-dimensions.md` before reporting complete."

**Steps:**
1. Decide placement (`task-decomposition.md` vs. `SKILL.md` Step 3)
   based on where the existing "new skill directory -> drafting-a-skill"
   sentence lives and how this rule reads alongside it.
2. Add the new rule, quoted above, in that location.
3. Cross-check against `task-decomposition.md`'s existing row-to-task
   mapping rules for placement consistency.
4. Cross-check against `drafting-a-skill`'s own Related-skills section
   (the `scorer-gated-skill-edits` boundary) to confirm the new floor
   does not duplicate or contradict that skill's own Precondition gate.
5. Run `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   against `skills/executing-a-branch-plan/` if `SKILL.md` itself was
   touched; fix until clean.

**Proof method:** cross-checks above pass; deterministic checker clean
if `SKILL.md` was touched.

**Irreversibility:** none (documentation/skill-definition edit only).

## File-ownership map

| Task | Files |
|---|---|
| A | `skills/drafting-a-skill/references/formative-quality-dimensions.md`, `skills/drafting-a-skill/SKILL.md` |
| B | `skills/executing-a-branch-plan/references/task-decomposition.md` (or `skills/executing-a-branch-plan/SKILL.md`) |

No overlap between A and B.

## Interface-dependency map

None. Task B's new rule is general prose referencing `drafting-a-skill`
and `formative-quality-dimensions.md` by name/convention, not consuming
any specific new content Task A adds -- both were already stable,
pre-existing references before this branch.

## Wave assignment

Wave 1: {Task A, Task B} -- no file-ownership or interface-dependency
edge between them, so they co-assign to the same parallel wave.

## Worked-example precedent

Matches this skill's own "Worked example" shape: a 2-task decomposition
with no edges, both tasks in wave 1.

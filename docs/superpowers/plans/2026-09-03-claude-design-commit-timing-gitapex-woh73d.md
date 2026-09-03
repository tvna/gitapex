# Branch Plan: fix(eliciting-a-design): commit design doc after issue creation, use docs/gitapex path convention

Issue: #1700 (tvna/gitapex)

## Task 1: Fix commit timing and superpowers->gitapex path convention

### Files

- `skills/eliciting-a-design/SKILL.md`
- `skills/executing-a-branch-plan/SKILL.md`
- `skills/executing-a-branch-plan/references/task-decomposition.md`

### ACM row citations (verbatim, from issue #1700)

**Row 1 (commit timing) - Planned ops:**
> Remove "and commit" from Checklist item 11. Remove the "Commit only the
> design document..." sentence from the "Documentation" subsection and
> add an equivalent commit step to the "Issue formalization handoff"
> section (or immediately after it), to run once the issue exists.
> Reconcile with issue #1378's own edit to the same section (see
> Residual risk).

**Row 2 (path convention) - Planned ops:**
> Change `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` to
> `docs/gitapex/specs/YYYY-MM-DD-<topic>-design.md` at
> `skills/eliciting-a-design/SKILL.md` lines 52 and 330. Change
> `docs/superpowers/plans/<date>-<branch-name>.md` to
> `docs/gitapex/plans/<date>-<branch-name>.md` at
> `skills/executing-a-branch-plan/SKILL.md` line 60 and
> `skills/executing-a-branch-plan/references/task-decomposition.md` line
> 69. Re-grep the repository at implementation time for any other
> save-path-convention occurrence missed by this issue's own grep pass.

### Steps

1. In `skills/eliciting-a-design/SKILL.md` Checklist item 11 (line 52):
   remove "and commit" from the end of the line; change the path to
   `docs/gitapex/specs/YYYY-MM-DD-<topic>-design.md`.
2. In the "Documentation" subsection (lines 328-333): change the path
   to `docs/gitapex/specs/YYYY-MM-DD-<topic>-design.md`; remove the
   "Commit only the design document..." bullet.
3. In the "User Review Gate" section (lines 347-352): reword "Spec
   written and committed to `<path>`" to reflect that the spec is
   written but not yet committed at that point (commit now happens
   later, after issue formalization).
4. In the "Issue formalization handoff" section (lines 354-360): add a
   commit step that runs once `drafting-issues` (or its fallback) has
   created the issue -- stage and commit only the design doc path,
   never `git add -A`/`git commit -a` (carry forward the existing
   staging discipline from the removed bullet).
5. Keep this edit textually separate from where issue #1378's own
   future `outward-artifact-preflight` Check 1/Check 3 addition would
   land in the same "Documentation" subsection, so the two do not
   collide.
6. In `skills/executing-a-branch-plan/SKILL.md` line 60: change
   `docs/superpowers/plans/<date>-<branch-name>.md` to
   `docs/gitapex/plans/<date>-<branch-name>.md`.
7. In `skills/executing-a-branch-plan/references/task-decomposition.md`
   line 69: same path change as step 6.
8. Re-grep `skills/` for `docs/superpowers` and confirm the only
   remaining hits are the same 15 already-existing-file citations
   present before this change (unchanged content).
9. Grep the 3 edited files for the old convention-shaped strings
   (`docs/superpowers/specs/YYYY-MM-DD`, `docs/superpowers/plans/<date>`)
   and confirm zero matches.
10. Read the updated `eliciting-a-design/SKILL.md` end to end and
    confirm the stated order is: write spec file -> spec self-review
    -> user review -> `drafting-issues` invocation (issue created) ->
    commit the spec file, with no step instructing a commit before
    that point.

### Proof method

Direct read of both files confirming the ordering and path changes
above; grep confirmation per steps 8-9. No automated test suite covers
this skill's own prose (process/documentation fix only).

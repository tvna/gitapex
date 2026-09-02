# Branch Plan: claude/pr-draft-previous-round-results-pp3vfr

Source issue: https://github.com/tvna/gitapex/issues/1649
Design doc: `docs/superpowers/specs/2026-09-01-drafting-a-pr-to-merge-round-archive-comment-design.md`

## Task list (1 task, 1 wave -- single-task degenerate case)

### Task A: archive prior Step 8 round to a PR comment before body overwrite

**Owns:**
- `skills/drafting-a-pr-to-merge/SKILL.md`
- `evals/drafting-a-pr-to-merge/tasks/*.yaml` -- both new fixtures and a
  Check-E-driven `exercises:` field addition to pre-existing fixtures
  whose cited Stop-boundary bullet's own text shifts

**File-ownership / interface-dependency edges:** none -- single task,
no sibling to conflict or sequence against.

**Source ACM rows (quoted verbatim from issue #1649's re-verified
Acceptance Criteria Map):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| Step 8 re-running after a `confirmed finding` (Step 3 loop-back) archives the immediately-prior round's `## Independent review verdict` section to a PR comment before overwriting it in the body. | Add a new leading sub-step to Step 8's record procedure in `skills/drafting-a-pr-to-merge/SKILL.md`, gated on the section already existing in the body. | Edit `skills/drafting-a-pr-to-merge/SKILL.md`'s record paragraph (the `Record the validated, preflighted verdict...` paragraph, currently starting at line 232) to add the check-and-archive sub-step. |
| Step 8's very first run on a PR (no existing `## Independent review verdict` section yet) skips the archive step entirely. | The new sub-step's existence check short-circuits to the unchanged, existing record behavior when the section is absent. | Same edit as above; the check is a simple existence guard at the top of the new sub-step. |
| The archive rule applies only to Step 8's own loop, never to Step 7's `"unstable"/"blocked"`/`"dirty"` Step-3 return paths. | The new sub-step is added only inside Step 8's own record procedure; Step 7's branches and its existing `"dirty"` comment rule are untouched. | No edits to Step 7's own text. |
| The archived comment carries the prior round's `## Independent review verdict` content verbatim, with no re-summarization. | The new sub-step posts the existing body section's text unchanged into the comment body. | Same edit as above. |
| The new (post-overwrite) body section carries no reference (link or mention) back to the archived comment. | No cross-reference text is added to the new verdict record. | Same edit as above -- the record sub-step's existing composition is otherwise unchanged. |
| `skills/drafting-a-pr-to-merge/SKILL.md`'s Stop boundaries gain a new bullet: never overwrite an existing `## Independent review verdict` section without first archiving it to a PR comment, except on Step 8's first run. | Add one Stop-boundary bullet stating this rule. | Edit the Stop boundaries section of `skills/drafting-a-pr-to-merge/SKILL.md`. |

**Proof method:**
- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  and `gitapex_scan_execution_requirements_drift.py` clean against the
  edited `SKILL.md`.
- New `evals/drafting-a-pr-to-merge/tasks/*.yaml` fixtures: (a) Step 8's
  first run on a PR (no existing verdict section) -- assert no archive
  comment is posted; (b) Step 8's second run (confirmed finding -> fix ->
  re-clean -> Step 8 re-run) -- assert the archive comment is posted
  with the prior round's exact content before the body section is
  overwritten, and the new body carries no reference back to it. Design
  review may add further fixtures beyond these two if it finds the
  Mechanism has more branches than this table's rows anticipate -- see
  the design doc's own Verification section for the final, authoritative
  fixture count.
- Existing `evals/drafting-a-pr-to-merge/tasks/conflict-comment.yaml`
  (Step 7 `"dirty"` regression) still passes -- its own assertions are
  unchanged, though it (like every other pre-existing fixture citing a
  Stop-boundary bullet whose text shifts) gains a new `exercises:` field
  per this task's own `Owns:` scope above.
- `gitapex_gate_skill_branch_fixture_coverage.py`'s delta-scoped check
  passes (new Stop-boundary bullet has a citing fixture).

**Residual risk (carried from the issue):** `github:add_issue_comment`
failure-handling (retry/escalation) is not specified in the design;
follow this skill's existing conventions for a failed tool call
elsewhere in the same step rather than inventing a new failure mode.

## Verification plan

- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  and `python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
  pass clean against `skills/drafting-a-pr-to-merge/`.
- `python3 .github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`
  passes (delta-scoped, against `origin/main`).
- `uv run --frozen python3 -m pytest --no-cov -q` (full suite, excluding
  the real-bash-oracle test files per `.github/workflows/test.yml`'s own
  exclusion) passes.
- `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`
  passes.
- PR body carries the ACM; validated via
  `python3 skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`.
- PR body carries a `## Skill audit evidence` section disclosing
  `evaluating-skill-quality`/`battle-testing-a-skill` verdicts (this PR
  modifies a `skills/*/SKILL.md`).
- Two independent fresh-context reviews (step 8): a behavior-preserving
  refactor/simplify pass, and an adversarial code review -- both over the
  full accumulated diff, findings fixed before the PR leaves draft.

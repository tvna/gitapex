# Task list: SKILL.md body cost controls

Branch: `claude/skill-quality-char-limit-18b0s4`
Issue: [#1698](https://github.com/tvna/gitapex/issues/1698)
Design doc: `docs/superpowers/specs/2026-09-02-skill-body-cost-controls-design.md`

## Wave 1

### Task 1: SKILL.md body cost controls (code-span integrity, Notes/metadata axis, token budget)

Satisfies ACM rows 1, 2, 3 (issue #1698). Collapsed into one task per the
task-decomposition file-contention rule: all three rows write
`references/rubric.md` and/or
`skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`, so
splitting them would only create sequential-dependent tasks with no
parallelism benefit.

Quoted ACM Planned ops (verbatim, per row):

- Row 1: "Add the check function; wire into `orchestrator.py`'s
  `_references_dir_checks` (for `references/*.md`) and into
  `gitapex_check_skill_shape.py`'s own SKILL.md-body scan; add
  corresponding `references/rubric.md` prose"
- Row 2: "Edit `references/rubric.md` prose at the four cited locations
  (no code change)"
- Row 3: "Add the check function + `BODY_MAX_TOKENS = 5000` constant;
  add the new CLI flag; wire `drafting-a-skill/SKILL.md:184`'s own
  invocation to pass it; without the flag the check always returns
  `passed=True` with a warning string in `evidence` (advisory, never
  fails the run); with the flag, `passed` reflects the real threshold
  comparison"

Files:

- `skills/evaluating-skill-quality/scripts/shape_checks/` (new module(s)
  for the code-span check and the token-budget check)
- `skills/evaluating-skill-quality/scripts/shape_checks/orchestrator.py`
- `skills/evaluating-skill-quality/scripts/shape_checks/constants.py`
- `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
- `skills/evaluating-skill-quality/references/rubric.md`
- `skills/drafting-a-skill/SKILL.md`
- `skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py`

Steps:

1. Add a code-span-line-break-integrity check function following the
   existing `CheckResult`-returning pattern (`field_checks.py`'s
   `_no_xml_check`/`_length_check`); detect an inline code span (single
   backtick pair) opening on one line without closing on the same line.
2. Wire it into `orchestrator.py`'s `_references_dir_checks` (covers
   `references/*.md`) and into `gitapex_check_skill_shape.py`'s SKILL.md
   body scan.
3. Add `BODY_MAX_TOKENS = 5000` to `constants.py` and a token-budget
   check function (`len(content)//4` against the SKILL.md body only).
4. Add a new CLI flag (e.g. `--strict-token-budget`) to
   `gitapex_check_skill_shape.py`: absent, the token-budget check always
   returns `passed=True`, with a warning in `evidence` when over
   threshold; present, `passed` reflects the real comparison.
5. Update `drafting-a-skill/SKILL.md:184`'s own invocation line to pass
   the new flag.
6. Edit `references/rubric.md`: replace lines 779/816/276's
   unconditional "belongs in `## Notes`" and lines 1072-1073's "Notes
   section or metadata" with the explicit axis ("does a reader need this
   at the moment of reading SKILL.md"); add prose for the new code-span
   rule.
7. Add unit tests: a synthetic split-code-span fixture (code-span check),
   a synthetic over-budget SKILL.md fixture exercised both with and
   without the new flag (token-budget check).
8. Run the full test suite plus both checkers against every real
   `SKILL.md`/`references/*.md` in this repository; confirm zero false
   positives from the code-span check and that all 30 existing skills
   still exit 0 (no flag) on the token-budget check.

Proof method (from the ACM): zero false positives on the existing
corpus; all 30 existing `SKILL.md` files exit 0 without the new flag;
synthetic fixtures confirm both FAIL paths (split span; flagged
over-budget).

Irreversibility: none of this task's ops are irreversible (file edits,
a new opt-in CLI flag, no data deletion or migration).

# Branch Plan: claude/pr-1466-prep-xtpkaa

Source issue: https://github.com/tvna/gitapex/issues/1466

## Task list (1 task, wave 1 -- single-task degenerate case)

### Task 1: Add a Durability example to rubric.md for stale-reference-vs-commit-provenance-annotation

**Owns:**
- `skills/evaluating-skill-quality/references/rubric.md`
- `evals/evaluating-skill-quality/tasks/durability-stale-reference-annotation-selection.yaml`
- `evals/evaluating-skill-quality/split.json`
- `evals/evaluating-skill-quality/split.md`
- `evals/evaluating-skill-quality/eval-status.md`
- `evals/evaluating-skill-quality/results/2026-08-30-issue-1466-durability-stale-reference/` (new)
- `docs/skill-eval-status.md` (regenerated, derived output only)

**File-ownership / interface-dependency edges:** none -- single-task plan,
no sibling task in this wave.

**Source ACM row (quoted verbatim from issue #1466's re-verified Acceptance
Criteria Map):**

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Add a short example naming: when fixing a stale/dangling reference to something the repo's own commit history already tracks, prefer removing/generalizing the reference over annotating it with commit provenance | Extend `skills/evaluating-skill-quality/references/rubric.md`'s Dimension 6 (Durability) section with a new bullet (with a Fail/Pass-style illustrative example matching the section's existing convention) illustrating this exact pattern; the repository's root instruction file is excluded as an edit target since it is machine-produced, not hand-maintained | Add one bullet to rubric.md's Durability section; since this edits an existing skill's `references/` content, route it through `scorer-gated-skill-edits`'s held-out train/selection/test procedure the same way issues #149/#155/#165/#185/#537/#1346/#1347 did for prior `references/rubric.md`-only additions to this exact skill | Re-run `evaluating-skill-quality`'s own `gitapex_check_skill_shape.py` after the edit to confirm no regression, plus a fresh isolated before/after `claude -p` dispatch pair against a new selection fixture, scored via `gitapex_score_contract.py --compare-to`; manually confirm the new bullet is grep-locatable and introduces no bare `#N` citation inside Portable-declared content | A prose durability rule cannot be deterministically enforced -- accepted per issue #260's own "unclear agent instruction" classification (no gate proposed) |

**Implementation guidance (this session's own pre-execution investigation,
not part of the quoted ACM row):**

- `rubric.md`'s Dimension 6 (Durability) section (pre-edit lines 1678-1748)
  gains one new bullet (placed after the existing "No time-sensitive
  content" bullet) plus one clause each in the section's existing combined
  Fail:/Pass: block, matching the section's established convention.
- `SKILL.md` needs no companion edit -- it does not restate per-dimension
  rubric content (confirmed via grep), matching issue #185's precedent.
- One new selection-split fixture,
  `durability-stale-reference-annotation-selection.yaml`, registered in
  `split.json`'s `assignment.selection` list. `split.json`'s own
  `partition` field must account for `split_arithmetic_exclusions`
  (`dispatch-required-negative-control.yaml` is excluded from the train
  count by `gitapex_gate_split_fixture_coverage.py`'s Check D) --
  confirmed live: the correct declared partition is `35:41:18`, not a
  naive `len()` of the raw `assignment.train` list (36).
  `tests/test_gitapex_gate_split_fixture_coverage.py`'s
  `test_real_split_json_partition_declarations_are_pinned_exactly` pins
  this exact tuple by hand and must be updated in the same commit.
- `docs/skill-eval-status.md` is machine-generated
  (`.github/scripts/gitapex_generate_skill_eval_status.py`, derived from
  `split.json`'s partition among other live-derived facts) -- regenerate
  it (`uv run python3 .github/scripts/gitapex_generate_skill_eval_status.py`)
  rather than hand-editing, and commit the regenerated output.
- Gate dispatch mechanism: isolated `claude -p` subprocess (matching
  `references/adversarial-self-audit.md`'s Known entries registry, the
  `2026-08-30`/`2.1.251`/`CLAUDE_CODE_REMOTE=true`/
  `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default` Same-run entry,
  identifying signal directly confirmed to match this session) -- one
  fresh before/after dispatch pair against the new selection fixture
  only; pre-existing selection fixtures reused unchanged (content-
  disjointness confirmed by direct inspection, matching the #185/#1346/
  #1347 precedent already in `split.md`).
- Full run record (`manifest.json` + score files + before/after
  transcripts) under `evals/evaluating-skill-quality/results/
  2026-08-30-issue-1466-durability-stale-reference/`, plus a new
  `## Iteration: issue #1466, ...` section in `split.md` and a
  corresponding entry in `eval-status.md`, matching the #1346/#1347
  entries' own shape.

**Irreversibility classification:** reversible (a documentation/rubric
edit plus an eval-corpus fixture addition and its own gate record; no
destructive or outward-facing operation beyond the PR itself).

**Proof method:** `gitapex_score_contract.py --compare-to` strict
improve-or-reject gate (live before/after dispatch, not a test suite);
`gitapex_check_skill_shape.py` and the full `pytest` suite as regression
proof.

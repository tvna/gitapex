# evaluating-skill-quality: extract the deterministic shape lane into a bundled script

Date: 2026-07-13
Status: approved (design), pending implementation plan

## Problem

The `evaluating-skill-quality` skill separates a **deterministic shape**
lane (mechanically decidable rules) from a **probabilistic maturity** lane
(nine model-judged dimensions). The deterministic lane is real and
mechanically checkable, but it is executed as prose the reviewing model
applies by hand, and its concrete rule values are duplicated across four
files:

- `SKILL.md` "Two lanes" -> Deterministic shape bullet (exact values)
- `references/rubric.md` dimension 1
- `references/worked-example-explaining-the-work.md` (hand-computed table)
- `references/worked-example-self-review.md` (hand-computed table)

This violates the repository's own standard (CLAUDE.md section 3): a
deterministic gate must be a built gate, never substituted by agent
memory, and an invariant needs a single source of truth with a drift gate
shipped in the same change. The duplication also weakens encapsulation
(no single owner for the constants), leaks implementation detail into the
interface layer (`SKILL.md` carries exact numeric limits), and leaves the
deterministic path unexercised (remembered, not run).

A secondary, in-scope correctness defect: `rubric.md` dimension 8 asserts
"gitapex has neither an `evals/evals.json` nor an `evals/` directory
committed to the repo today," which is now stale -- `evals/issue-to-branch`
exists.

## Goals

Address four author-requested qualities for this skill:

1. **Deterministic mechanism as a bundled script** -- extract the shape
   lane into a script the skill calls, not prose it remembers.
2. **Encapsulation** -- the script becomes the single source of truth for
   the shape constants and rules.
3. **Separation of concerns** -- interface (`SKILL.md` prose + the script's
   CLI contract) is separated from implementation (script internals +
   rubric judgment); the nine dimensions stay model-judged and are never
   scripted.
4. **Side-effect isolation** -- the script is read-only (no writes, no
   network); the skill's existing Stop-boundary isolation is preserved.

## Non-goals (YAGNI / scope boundary)

- No automated scoring of the nine dimensions; they remain model-judged.
- No JSON output (text report + exit code is sufficient for a model reader
  and a CI gate).
- No eval harness, no `waza` install, no general-purpose linter.
- No new CI job that walks every skill in the repo -- deferred to a
  separate issue if wanted. This change wires the script into the existing
  `pytest`/coverage harness only.

## Architecture

```
skills/evaluating-skill-quality/
  SKILL.md                     # interface; shape bullet shrinks to a script call
  scripts/
    check_skill_shape.py       # NEW: canonical deterministic shape checker (stdlib only)
    test_check_skill_shape.py  # NEW: bundled with the skill so it travels on vendoring
  references/
    rubric.md                  # dim1 defers exact values to the script; dim8 staleness fixed
    worked-example-*.md        # hand-computed shape tables -> real script-run transcripts
```

- The script body lives inside the skill folder (portability; consistent
  with rubric dimensions 6-7). The repository's `pyproject.toml`
  (`pythonpath`, `testpaths`, coverage `source`) is extended to point at
  the skill's `scripts/` path so the repo `pytest`/CI also covers it.
- A vendored copy needs no `pyproject.toml`: `python3
  check_skill_shape.py <path>` runs standalone. Only CI coverage is
  repo-scoped; execution portability is preserved.

## Script interface contract

- **Invocation:** `python3 check_skill_shape.py <skill-dir-or-SKILL.md>`.
  Accepts either a skill directory or a direct `SKILL.md` path, so it is
  reusable against any target skill, not just this one.
- **Checks (deterministic only, the single canonical list):**
  - `description`: present/non-empty, no XML tags, <= 1024 chars.
  - `name` (only if present): lowercase-hyphenated, <= 64 chars, no XML
    tags, not a reserved word (`anthropic`, `claude`).
  - `SKILL.md` body: <= 500 lines.
  - `references/`: files exactly one level deep.
  - Any `references/` file over 100 lines: must contain a table of
    contents, detected deterministically as a Markdown heading line
    matching `table of contents` case-insensitively (e.g.
    `## Table of contents`).
- **Output:** a human-readable table to stdout -- one row per check with
  its rule, PASS/FAIL, and the observed evidence (measured value). The
  script's module docstring / `--help` enumerates the full check list, so
  a reviewer on a Python-less surface applies the same rules by reading the
  script -- the manual fallback consults the script, keeping it the single
  source of truth.
- **Exit code:** non-zero if any check FAILs (linter convention), so a hook
  or CI step can gate on it.
- **Explicitly not scripted:** the nine maturity dimensions. The script
  decides shape; the model decides judgment. This boundary is the
  separation of concerns.

## Side-effect isolation

- The script reads target files only: no writes, no network, no mutation,
  deterministic. Its only effects are stdout and the exit code. This is
  stated in the module docstring.
- The skill's existing Stop boundaries (e.g. never install eval tooling
  without operator go-ahead) remain unchanged; adding a read-only checker
  does not weaken that invariant. Contrast `waza`'s live HTTP link check,
  which the rubric already flags as an environment-dependent side effect --
  this checker performs no external access.

## Testing and repo wiring

- `test_check_skill_shape.py` is bundled inside the skill so the test
  travels on vendoring. It uses `pytest` `tmp_path` to synthesize a
  passing `SKILL.md` and one fixture per failure mode (missing/oversized
  description, XML tag in description, bad `name` case, reserved-word
  `name`, over-500-line body, nested `references/`, >100-line reference
  with no TOC), asserting both the per-check verdict and the process exit
  code.
- `pyproject.toml`: add the skill's `scripts/` path to `pythonpath`,
  `testpaths`, and coverage `source`, following the existing
  `scripts/sync_pr_publish.py` + `tests/test_sync_pr_publish.py`
  convention.

## Prose changes (single-source-of-truth collapse)

- **`SKILL.md`** "Two lanes" Deterministic shape bullet: drop the enumerated
  numeric values; replace with "run `scripts/check_skill_shape.py`
  (or, on a Python-less surface, apply the same rules from that script's
  check list by hand)."
- **`rubric.md` dimension 1:** keep the division of labour ("the script
  confirms a trigger *exists*; this dimension judges whether it is the
  *right* one"); defer the exact values to the script rather than
  restating them.
- **`rubric.md` dimension 8:** correct the stale claim -- `evals/`
  (`evals/issue-to-branch`) now exists in the repo.
- **`worked-example-*.md`:** replace the hand-computed shape tables with a
  real `check_skill_shape.py` run transcript, so the examples demonstrate
  running the deterministic path rather than remembering it.

## Verification

- `pytest` (repo harness) passes, including the new test and coverage for
  `check_skill_shape.py`.
- The script run against this skill itself and against a deliberately
  malformed fixture produces the expected PASS/FAIL rows and exit codes
  (live proof, not a type-check proxy; CLAUDE.md section 1).
- Net line delta is reported: prose deletions (collapsed duplication)
  offset script/test additions; a net increase is justified explicitly
  before commit (CLAUDE.md section 5).

## Delivery preconditions

- A GitHub issue is opened before any branch/commit/PR and its number is
  cited in every commit and PR (CLAUDE.md section 3). The design commit and
  all implementation commits reference it.

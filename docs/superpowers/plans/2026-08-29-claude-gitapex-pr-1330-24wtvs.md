# Split gitapex_check_skill_shape.py into a shape_checks package (issue #1330)

**Goal:** split `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
(6321 lines) into a `shape_checks/` package along its existing check-family
boundaries, behind the same single unchanged CLI entry point, then narrow or
remove that file's blanket `xenon` complexity-gate exclude in
`.github/workflows/test.yml` once its two named functions (`_parse_manifest`,
`check_shape`) are refactored below rank F. Source: https://github.com/tvna/gitapex/issues/1330.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 5):** performed this session, recorded as a re-verification marker on
issue #1330's own body (2026-08-29T19:36:24Z). One correction: the file is
now 6321 lines, not 6149 as the issue's own Facts section states -- drift
since the issue was drafted; the core claim (large, already excluded from
the `xenon` gate) still holds. The `xenon` exclude for this file exists in
exactly one place (`.github/workflows/test.yml:70-79`), with an explicit
re-measure trigger already stated in its own comment: drop the exclude once
`_parse_manifest` and `check_shape` (currently CC 99/64, rank F, MI 0.00)
are refactored below rank F. Four test files reach into this module's
private names directly (`import gitapex_check_skill_shape as css`, then
`css._parse_manifest`, `css.BODY_MAX_LINES`, etc.):
`skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py`,
`tests/test_gitapex_check_skill_shape_properties.py`,
`tests/test_gitapex_skill_metadata_sidecar.py`,
`tests/test_gitapex_repository_skill_shape.py` -- the split must keep every
name those files reach into importable from `gitapex_check_skill_shape`
(re-export) or they break. PR #1074 (the issue's own cited precedent for a
"behavior-preserving refactor" proof method) is a large multi-file squash
merge, not a scoped comment-only change, so it is not a usable precedent;
PR #596 does not appear in local git history. A dedicated differential
output-diff script (compare `check_shape()` results across every real
`skills/*/SKILL.md` before/after) is built instead, as Task 1's own Files
list states.

**Authorization record:** no approval comment exists yet on issue #1330 (0
comments as of this run). Authorization is satisfied instead by explicit,
current-session confirmation from the active human operator: the operator's
own opening instruction this session named issue #1330's URL directly and
asked to open its PR and drive it to just-before-merge -- the same
outward-facing, hard-to-reverse action class this repository's own
confirm-before-acting rule covers, satisfying the Authorization gate's
second branch (`references/threat-model-and-authorization.md`).

**File-ownership check (mechanized):**
`gitapex_check_file_ownership_conflicts.py` against the 3 tasks' file lists
below -> 2 conflicts: `gitapex_check_skill_shape.py` and
`shape_checks/manifest.py` are each written by both task-1 and task-2 ->
sequenced (never co-assigned to the same wave), matching the file-contention
rule. task-3 (`.github/workflows/test.yml`) shares no file with either.

**Canonical-governance-paths pre-filter (mechanized):**
`gitapex_check_canonical_governance_paths.py` against the 16 planned changed
paths -> 15 `hook-script` matches (every file under
`skills/evaluating-skill-quality/scripts/`) and 1 `workflow` match
(`.github/workflows/test.yml`) -- both hard-flag categories, so the model's
own full review (the `untrusted-input-triage` Extract/Ignore/Flag/Tag pass
over the ACM's own text, step 2 of `executing-a-branch-plan`, plus per-task
screening at each task's own diff, step 6) still runs regardless. Nothing in
issue #1330's Facts, Requested outcome, Acceptance Criteria Map, Constraints,
or Non-goals reads as an injected instruction rather than a change
description -- a straightforward, well-scoped refactor request from the
repository's own OWNER-author, consistent with every other ACM this
repository's `planning-a-branch-from-an-issue` has produced. The two
imperative-style Planned-ops cells quoted verbatim into task-1/2/3 below are
task descriptions authored by that OWNER, not a payload attempting to
redirect this skill's own procedure.

## Task 1 -- mechanical package split (pure move, zero behavior change)

**Cites ACM row 1** ("The file is large (6149 lines, 17 checks) and already
excluded from the complexity gate"). **Quoted Planned ops (verbatim):**
"Refactor into a package (for example
`skills/evaluating-skill-quality/scripts/shape_checks/` with one submodule
per check family); update the imports inside `check_shape()`; update any
test files that import internal functions directly."

**Files:**
- `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  (rewritten as a thin CLI entry point: `main()`, `format_report()`,
  `check_shape()` -- `check_shape()`'s own body stays exactly as-is in this
  task, moved verbatim, not yet internally decomposed -- plus a re-export of
  every private name the 4 consumer test files listed above reach into)
- `skills/evaluating-skill-quality/scripts/shape_checks/__init__.py` (new)
- `skills/evaluating-skill-quality/scripts/shape_checks/constants.py` (new
  -- module-level constants and the `CheckResult`/`FrontmatterParse`
  dataclasses)
- `skills/evaluating-skill-quality/scripts/shape_checks/frontmatter.py`
  (new -- `_parse_frontmatter`, `_unquote`, `_strip_bare_comment`,
  `_match_key_line`)
- `skills/evaluating-skill-quality/scripts/shape_checks/manifest.py` (new --
  `ManifestParse`, `_parse_manifest`, `spec_of`, moved verbatim in this
  task)
- `skills/evaluating-skill-quality/scripts/shape_checks/links_portability.py`
  (new -- link/anchor/portability helpers and `SidecarPortability`)
- `skills/evaluating-skill-quality/scripts/shape_checks/citations.py` (new
  -- inline/portable citation-offender helpers)
- `skills/evaluating-skill-quality/scripts/shape_checks/field_checks.py`
  (new -- `_no_xml_check`, `_length_check`, `_yaml_plain_scalar_safety_check`,
  `_references_grammar_check`, `_invocation_mode_check`, plus
  `_resolve_skill_md`/`_owning_skill_dir`/`_validate_read_scope`)
- `skills/evaluating-skill-quality/scripts/shape_checks/citation_checks.py`
  (new -- the issue/cross-skill/mechanism-fit/model-id/placeholder/
  step-location/portable-path/demonstrative-repository citation check
  families)
- `skills/evaluating-skill-quality/scripts/shape_checks/bundled_scripts.py`
  (new -- out-of-skill-scripts, voodoo-constant, script-execution-intent
  checks)
- `skills/evaluating-skill-quality/scripts/shape_checks/skill_dependencies.py`
  (new -- `_skill_dependency_checks` and its validators)
- `skills/evaluating-skill-quality/scripts/shape_checks/lifecycle.py` (new
  -- `_lifecycle_checks` and its validators)
- `skills/evaluating-skill-quality/scripts/shape_checks/execution_requirements.py`
  (new -- `_execution_requirements_checks` and its validators)
- `skills/evaluating-skill-quality/scripts/verify_shape_check_output_diff.py`
  (new -- differential-output verification script: runs `check_shape()`
  against every real `skills/*/SKILL.md` in this repository against the
  pre-refactor commit and the working tree, and fails loud on any non-empty
  diff of the resulting `CheckResult` lists)

**Steps:**
1. Run `git log -n1 --format=%H -- skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   to record the pre-refactor blob as this task's own BASE reference for the
   differential script.
2. Confirm the current function/class layout with
   `grep -n '^def \|^class \|^@dataclass' skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   before moving anything -- the file may have drifted slightly from the
   line numbers cited above; treat the family groupings above as the
   authoritative boundary, exact line numbers as approximate.
3. Move code with exact line-range extraction (`sed -n 'START,ENDp'` or
   equivalent), never by retyping logic from memory -- every check's exact
   behavior, comments, and docstrings must survive byte-for-byte.
4. Build the re-export hub in `gitapex_check_skill_shape.py`: import every
   public and private name the 4 consumer test files reach into (see the
   Independent re-verification note above for the concrete name list) so
   `import gitapex_check_skill_shape as css; css._parse_manifest(...)` etc.
   keeps working with zero test-file changes.
5. Write `verify_shape_check_output_diff.py` and run it: for every
   `skills/*/SKILL.md` in this repository, compare `check_shape()`'s
   returned `CheckResult` list against the pre-refactor version (checked out
   from step 1's BASE into a scratch copy) -- must be byte-identical.
6. Run the full test suite: `uv run --frozen pytest skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py tests/test_gitapex_check_skill_shape_properties.py tests/test_gitapex_skill_metadata_sidecar.py tests/test_gitapex_repository_skill_shape.py` --
   must be green with zero test-content changes beyond import-path
   adjustments (none should be needed given the re-export hub).
7. Run `uv run --frozen ruff check` / `ruff format --check` (or this
   repository's own equivalent lint gate) against every new/changed file.

**Proof method (from the ACM):** "`pytest` suite green with zero
test-content changes required beyond import-path updates ... an
`ast.dump()` or output-diff comparison of the checker's actual PASS/FAIL
output before and after, on a fixed set of real skill directories, proving
identical results" -- realized here as step 5's differential script plus
step 6's full pytest run.

## Task 2 -- decompose check_shape() and _parse_manifest() internally

**Cites ACM row 1**, its own Interpretation column ("... so individual
checks become small enough to re-enter this repository's own `xenon`
complexity gate") and Residual-risk column (permits a narrower, justified
per-module exclude if one check's logic is inherently complex). **Quoted
Planned ops (verbatim, shared with row 1 above, this task's own share of
it):** "Refactor into a package ... with one submodule per check family;
update the imports inside `check_shape()`."

**Interface-dependency edge:** depends on task-1's finished package layout
(reads `shape_checks/manifest.py` and the re-export hub's own current
shape) -- sequenced after task-1, not merely file-contended with it.

**Files:**
- `skills/evaluating-skill-quality/scripts/shape_checks/manifest.py`
  (decompose `_parse_manifest`'s ~1157-line body into smaller,
  per-section-of-the-manifest delegated functions it calls, without
  changing any parsed result)
- `skills/evaluating-skill-quality/scripts/shape_checks/orchestrator.py`
  (new -- `check_shape()`'s own ~818-line body decomposed into smaller,
  per-field/per-section delegated functions it calls in the same order,
  producing the exact same `CheckResult` list)
- `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  (updated to import `check_shape` from `shape_checks/orchestrator.py`)

**Steps:**
1. Re-run `verify_shape_check_output_diff.py` (task-1's own script) after
   the decomposition -- must still be byte-identical; this task changes
   internal structure only, never detection logic, per the ACM's own
   Constraints ("Must not change any check's detection logic or
   behavior").
2. Re-run the full test suite from task-1 step 6 -- must stay green.
3. Measure `uv run --frozen xenon --max-absolute E --max-modules B --max-average A .`
   (no exclude) against the new layout; record each module/function's own
   rank.

**Proof method (from the ACM):** the differential-output script and full
pytest suite (unchanged from task-1's proof method, re-run here) plus the
xenon measurement step-3 feeds directly into task-3's own decision below.

## Task 3 -- narrow or remove the xenon exclude

**Cites ACM row 2** ("The file is already excluded from `xenon`'s
complexity gate"). **Quoted Planned ops (verbatim):** "Update the `xenon`
command (wherever it is invoked -- CI workflow and/or local pre-push hook)
to drop or narrow the exclude entry once the split lands."

**Interface-dependency edge:** depends on task-2's own xenon measurement
(step 3 above) to decide whether the exclude is dropped entirely or
narrowed to a specific still-rank-F module -- sequenced after task-2.

**Files:**
- `.github/workflows/test.yml` (the `--exclude` flag and its own preceding
  comment block, lines ~61-79)

**Steps:**
1. If task-2's measurement shows every module in the new layout below rank
   F: drop the `gitapex_check_skill_shape.py`-specific exclude entirely
   (keep `apm_modules/*`), and rewrite the preceding comment to record the
   new measurement and drop the now-resolved re-measure-trigger sentence.
2. If one specific module remains rank F despite task-2's decomposition:
   narrow the exclude to name that module specifically (not the whole
   original file), and rewrite the comment to state which module remains
   excluded, its own measured rank, and why (per the ACM's own Residual-risk
   column: "a deliberate, justified choice ... not an accidental leftover
   of the old blanket exclude").
3. Re-run `uv run --frozen xenon --max-absolute E --max-modules B --max-average A --exclude "apm_modules/*<, narrowed entry if any>" .`
   -- must pass clean with the new/narrowed exclude.

**Proof method (from the ACM):** "`xenon` run against the new module layout
with the narrowed/removed exclude passes clean."

## Waves

wave 1: {task-1}. wave 2: {task-2} (file-ownership edge on task-1, plus an
interface-dependency edge). wave 3: {task-3} (interface-dependency edge on
task-2's own xenon measurement; no file-ownership edge with either prior
task).

## Execution mode

`Workflow` tool, one run per wave, each task dispatched with `agentType:
'branch-plan-task'` and `isolation: 'worktree'` -- this session's own
`gitapex:executing-a-branch-plan` skill invocation is itself the
skill-instructed opt-in this environment's `Workflow`-tool policy requires.
Screening, merge-back, push, and Execution-log events for each wave happen
in the main thread only, never inside a dispatched task agent, per SKILL.md
step 6.

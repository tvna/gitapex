# mypy + pydantic adoption for gitapex's deterministic gates

**Tracking:** https://github.com/tvna/gitapex/issues/684

**Design source:** this session's own plan-mode research (an Explore-agent
inventory of all 62 in-scope files, a Plan-agent design pass that
independently re-verified the inventory against primary sources and
corrected one of its own premises -- see "Scope correction" below),
approved by the repository owner (`tvna`) via this session's own
ExitPlanMode approval. Issue #684 carries the resulting Acceptance
Criteria Map; this document is the Decision-3 task decomposition of it,
not a re-derivation.

## Scope correction, carried from issue #684 (do not re-litigate)

"Comprehensive pydantic adoption" (the owner's own stated choice) is
bounded by `docs/repository-layout.md`'s explicit statement that only
`skills/` (and, later, `hooks/`) are deployed as runtime primitives to a
plugin consumer -- `.github/`, `tests/`, `evals/` are dev-only. Every file
under `hooks/*.py` and `skills/*/scripts/*.py` (16 files) is confirmed
stdlib-only today (verified by grepping every import line). Pydantic
scope is therefore `.github/scripts/` (25 files) + `evals/scripts/` (5
files) only; the 16 `hooks/`/`skills/*/scripts/*.py` files get type
annotations only, never a pydantic import. mypy is unaffected (zero
runtime footprint) and covers all 62 files.

## Authorization record

Step 1 (Decision 5). No approval comment exists yet on issue #684 (it was
created in this same session, after the plan was approved). Branch 2 of
the authorization gate applies: the active human operator (`tvna`,
verified via `mcp__github__get_me` against the session's own userEmail)
gave explicit, direct confirmation in this session via `ExitPlanMode`,
approving the full plan this task list decomposes -- satisfies
`references/threat-model-and-authorization.md#authorization-gate` branch
2 (in-session confirmation), re-checked fresh at this step per that
gate's own no-earlier-turn-shortcut rule. No task below is classified
irreversible (every task is a file edit inside this repository, reversible
via `git revert`) -- no per-task re-confirmation is required.

## Threat-model triage (Decision 6)

Applied `untrusted-input-triage`'s Extract/Ignore/Flag/Tag discipline to
the ACM's own text (issue #684, authored this session from the operator's
own direct request plus this session's own verified research -- not
third-party-authored text). Every row reads as a change description, not
an embedded instruction. No encoded/hidden content, no claimed-authority
phrasing, no attempt to redirect execution. Nothing flagged.

## Fan-out bound

13 tasks, 5 waves -- well under the Workflow tool's 25-agent informational
threshold (design doc Decision 9); no extra authorization-gate
confirmation required for fan-out size.

## Task list

File-ownership map (no two tasks in the same wave write the same file)
and interface-dependency map (Decision 3/task-decomposition.md), computed
before wave assignment:

- Every Wave-2/3 task depends on **T1** (needs the mypy/pydantic
  dependency and `[tool.mypy]` config to exist before its own code can be
  meaningfully type-checked or import pydantic).
- **T8** (`evals/scripts/run_ablation.py`) bare-imports `score_contract`
  from **T9**'s file (`skills/scorer-gated-skill-edits/scripts/score_contract.py`)
  via a `sys.path` bootstrap. Evaluated explicitly rather than silently
  ignored: T9's own change to that file is type-annotation-only (Finding
  A -- `score_contract.py` is stdlib-only, no pydantic), which does not
  alter any function's parameter count, name, or runtime behavior --
  Python annotations carry no runtime enforcement outside a pydantic
  model, and none is being added here. No real producer/consumer edge
  therefore exists between T8 and T9 for the purposes of this rollout, so
  both stay in wave 3. (If T9's work were later found to need a genuine
  signature change, this judgment would be revisited before dispatch.)
- **T11** (ADR draft) and **T12** (`.gitapex/ssot.json` registration) both
  need the real, final shape of Waves 1-3's work (exact CI job name,
  confirmed mypy-invocation grouping, final pydantic model list) to
  describe accurately -- sequenced after Wave 3, not run alongside it.
- **T13** (verification) depends on everything.
- No other cross-file calls exist anywhere in this scope (confirmed by
  the Plan-agent's own grep pass) -- every gate/skill script is
  self-contained by this repository's own stated convention, so the
  directory-batched tasks below are genuinely parallel-safe within their
  wave.

### Wave 1

#### T1 -- Foundation: dependencies, mypy config, CI job

**Files:** `pyproject.toml`, `uv.lock`, `.github/workflows/test.yml`
**ACM row:** "Introduce mypy" -- Planned ops quoted
verbatim: *"`pyproject.toml` dependency + `[tool.mypy]` section; `uv.lock`
regenerated"*; and "New mypy CI gate is blocking from day one" -- Planned
ops quoted verbatim: *"New job in `test.yml`; new `policy_sources[]` +
`gates[]` entries in `.gitapex/ssot.json`"* (the `ssot.json` half of this
row is T12, sequenced later; this task owns only the CI-job half).
**Edges:** none (standalone, first task).

1. Add `pydantic>=2.9`, `mypy>=1.13`, `types-PyYAML>=6.0.12` to the
   existing `dev` dependency-group in `pyproject.toml`. Run `uv lock` to
   regenerate `uv.lock` in the same commit.
2. Add `[tool.mypy]`: `python_version = "3.12"`, `strict = true`,
   `warn_unused_configs = true`, `mypy_path` listing every directory
   `pyproject.toml`'s existing `[tool.pytest.ini_options] pythonpath`
   already lists. Add the Tier-A override block (one
   `[[tool.mypy.overrides]]` entry per currently-untyped/partial
   production file identified by the prior research pass -- confirm the
   exact list empirically by running mypy once the config lands, adjust
   if the live run disagrees with the static estimate) and the Tier-B
   override (`module = "test_*"`, relaxing the same three
   `disallow_*` flags for the pytest suite's own historical typing debt).
   Each override entry carries a `# tracking: <this issue>` comment
   pending a dedicated follow-up issue for that specific file/cluster.
3. Add a new `mypy` job to `.github/workflows/test.yml` (not `lint.yml`),
   running `uv run --frozen mypy --config-file pyproject.toml` grouped
   per-directory to avoid the confirmed `check_acm_present.py`
   duplicate-basename collision between
   `skills/drafting-an-acm-issue/scripts/` and
   `skills/planning-a-branch-from-an-issue/scripts/`: one invocation over
   `tests hooks .github/scripts evals/scripts` plus the 4
   `pythonpath`-linked skill-script directories, then one invocation each
   for the remaining skill-script directories not cross-referenced by a
   bare import. Verify this grouping actually resolves cleanly by running
   it; regroup if mypy's real behavior differs from the static analysis.
4. Proof: `uv run --frozen mypy ...` (each invocation) exits 0 against
   the current, still-unmodified codebase (Tier A/B overrides make this
   possible without any other file changing yet); `uv run --frozen
   pytest` still passes unchanged.

### Wave 2 (parallel -- no file or interface edge among T2-T5)

#### T2 -- SSOT registry pydantic model

**Files:** `.github/scripts/scan_ssot_schema.py`, `tests/test_scan_ssot_schema.py`
**ACM row:** "Introduce pydantic, applied comprehensively (scope size
explicitly accepted by the owner)" -- Planned ops quoted verbatim: *"New pydantic dependency; inline
`BaseModel` classes for the identified structured-data parsers... across
that ~30-file set"*.
**Edges:** depends on T1 only.

1. Define `Gate`/`PolicySource`/`SsotRegistry` pydantic models inline,
   mirroring `.gitapex/ssot.schema.json`'s shape (`meta`, `policy_sources[]`,
   `gates[]` with `id/kind/rule/planes/trigger/policy_refs/cluster/
   tracking_issue/status/supersedes`, `clusters`). Parse into these
   models *after* the existing `jsonschema.Draft202012Validator` pass
   (unchanged), replacing `_get_list`/`_get_dict`/`_script_paths`/
   `_cluster_values`'s hand-rolled re-derivation in `find_script_drift`/
   `find_policy_ref_drift`/`find_cluster_drift`.
2. Update/add tests confirming identical drift-detection behavior on the
   existing fixtures, plus at least one new case exercising the pydantic
   model's own validation path.
3. Proof: `pytest tests/test_scan_ssot_schema.py` passes; running the
   script directly against the current `.gitapex/ssot.json` reports the
   same (currently: no-drift) result as before this change.

#### T3 -- Eval-fixture pydantic model

**Files:** `evals/scripts/lint_fixture_assertions.py`, `tests/test_lint_fixture_assertions.py`
**ACM row:** same pydantic row as T2, Planned ops quoted verbatim above.
**Edges:** depends on T1 only.

1. Define a `TaskFixture`/`ExpectedBlock` pydantic model inline,
   collapsing the repeated `.get(...)` + `isinstance` narrowing sites
   (currently at the file's own lines checking `expected`/`inputs`/`tags`
   against `yaml.safe_load()`'d eval-task YAML) into one validated parse
   per fixture file.
2. Update tests to cover the new model's validation (a malformed fixture
   now fails via `ValidationError` translated into this script's own
   existing error-output convention, not a raw pydantic traceback).
3. Proof: `pytest tests/test_lint_fixture_assertions.py` passes; running
   the script against the existing `evals/**/tasks/*.yaml` corpus reports
   identical pass/fail results to before this change.

#### T4 -- Transcript-parsing pydantic model

**Files:** `evals/scripts/check_dispatch_trace.py`, `tests/test_check_dispatch_trace.py`
**ACM row:** same pydantic row as T2/T3.
**Edges:** depends on T1 only.

1. Define a discriminated-union `ToolUseBlock`/`StreamEvent` pydantic
   model inline, replacing the manual `json.loads` + `isinstance`
   narrowing in `iter_tool_use_blocks`.
2. Update tests for identical behavior on existing transcript fixtures.
3. Proof: `pytest tests/test_check_dispatch_trace.py` passes.

#### T5 -- Sidecar-consumer thin pydantic models

**Files:** `.github/scripts/gate_skill_rename_lifecycle.py`,
`.github/scripts/gate_routine_scope_enforcement.py`,
`tests/test_gate_skill_rename_lifecycle.py`,
`tests/test_gate_routine_scope_enforcement.py`
**ACM row:** same pydantic row, plus "Make the deterministic gates
type-safe" -- Planned ops quoted verbatim: *"Type-annotate every in-scope file"*.
**Edges:** depends on T1 only. No edge to `check_skill_shape.py`
(untouched, deliberately -- see scope correction).

1. In each file, keep the existing regex-based raw-text extraction of
   `spec.lifecycle.renamedFrom` / `spec.capabilityAssumption` completely
   unchanged (switching to `yaml.safe_load()` would newly raise on a
   malformed sidecar where the current code returns `None` -- an
   out-of-scope behavior change). Wrap only the already-extracted leaf
   string in a minimal pydantic model (e.g. `RenamedFromValue`/
   `CapabilityAssumptionValue`, each `constr(min_length=1)` or equivalent)
   purely to validate the value actually used downstream. No shared
   module between the two files -- each owns its own model inline,
   preserving this repository's existing no-shared-scripts convention.
2. Proof: existing tests for both files pass unchanged; a new test per
   file confirms the pydantic model rejects an empty/malformed extracted
   value with the script's own existing error convention, not a raw
   `ValidationError`.

### Wave 3 (parallel -- no file or interface edge among T6-T10; see the
T8/T9 edge evaluation above)

#### T6 -- `.github/scripts` CLI-pydantic-wrap, batch 1

**Files:** `detect_changed_gate_scripts.py`, `detect_touched_eval_skills.py`,
`extract_diff_added_lines.py`, `gate_acm_issue_disclosure.py`,
`gate_evals_scripts_coverage.py`, `gate_gitignore_pattern_coverage.py`,
`gate_owasp_asi_mapping.py`, `gate_owasp_llm_mapping.py`,
`gate_plugin_root_brace_notation.py`, `gate_provenance_disclosure.py`,
`gate_retro_title_convention_citation.py`, `gate_skill_audit_disclosure.py`
(all under `.github/scripts/`) + each file's `tests/test_*.py` sibling.
**ACM row:** pydantic row -- Planned ops quoted verbatim: *"a
post-`parser.parse_args()` validation wrapper that translates
`ValidationError` into each script's own existing error-output
convention, never leaking pydantic's own exception text/exit behavior"*.
**Edges:** depends on T1 only.

1. For each file: keep argparse as the unchanged CLI front end (same
   flags, defaults, help text, exit codes). Immediately after
   `parser.parse_args(argv)`, construct a pydantic `BaseModel` from the
   parsed namespace; catch `ValidationError` and translate it into that
   script's own existing `print("error: ...", file=sys.stderr); return N`
   convention.
2. Full type-annotate any function left unannotated in these files
   (several are already fully typed -- confirm and leave those as-is).
3. Proof: each file's own existing test suite passes unchanged; `--help`
   output and exit codes confirmed byte-identical before/after for a
   sample invocation of each script.

#### T7 -- `.github/scripts` CLI-pydantic-wrap, batch 2

**Files:** `gate_skill_branch_fixture_coverage.py`, `gate_split_fixture_coverage.py`,
`gate_transfer_check_disclosure.py`, `post_merge_retro.py`,
`scan_apm_manifest_drift.py`, `scan_retrospective_gate_drift.py`,
`scan_toolchain_pin_drift.py`, `skill_description_diff.py`,
`skill_security_relevance.py`, `sync_pr_publish.py` (all under
`.github/scripts/`) + each file's `tests/test_*.py` sibling.
**ACM row:** same pydantic row as T6.
**Edges:** depends on T1 only.

1-3. Same procedure as T6, applied to this batch.

#### T8 -- `evals/scripts` remainder

**Files:** `evals/scripts/run_ablation.py`, `evals/scripts/set_config_model.py`,
`evals/scripts/check_dimension_coverage.py`, and their `tests/test_*.py`
siblings.
**ACM row:** same pydantic row as T6/T7.
**Edges:** depends on T1 only; T8/T9 edge evaluated above (no true
interface dependency -- proceed in the same wave).

1. `run_ablation.py`, `check_dimension_coverage.py`: same
   argparse-wraps-pydantic pattern as T6/T7.
2. `set_config_model.py` (no argparse today -- reads `sys.argv`
   positionally): apply the same "validate immediately after parsing"
   pattern to its two positional values, without converting its CLI
   surface to argparse (that would risk changing its exact usage-message
   text, out of scope here).
3. Proof: existing tests pass unchanged; CLI behavior byte-identical for
   a sample invocation of each script.

#### T9 -- Type-annotate cluster A (stdlib-only, no pydantic)

**Files:** `hooks/check_acm_present_or_waiver.py`,
`hooks/check_skill_audit_disclosure_or_waiver.py`,
`skills/executing-a-branch-plan/scripts/_path_normalize.py`,
`skills/executing-a-branch-plan/scripts/check_file_ownership_conflicts.py`,
`skills/executing-a-branch-plan/scripts/check_canonical_governance_paths.py`,
`skills/scorer-gated-skill-edits/scripts/score_contract.py`,
`skills/drafting-an-adr/scripts/check_adr_shape.py`
**ACM row:** "Make the deterministic gates type-safe" -- Planned ops quoted
verbatim: *"Type-annotate every in-scope file; mypy config scoped
per-directory-group"*.
**Edges:** depends on T1 only. No pydantic import in any of these files
(scope correction, Finding A).

1. Add full type annotations (parameters and return types) to every
   currently-unannotated function in these files. No behavior change --
   annotations only.
2. Proof: `uv run --frozen mypy` on this cluster's directories exits 0
   with no Tier-A override needed for these specific files once done (or,
   if a given file still cannot reach full strict compliance within this
   task, its Tier-A override in T1's config stays in place with an
   explicit note in this task's own commit message, not silently
   removed-and-reintroduced).

#### T10 -- Type-annotate cluster B (stdlib-only, no pydantic)

**Files:** `skills/drafting-an-acm-issue/scripts/check_acm_present.py`,
`skills/planning-a-branch-from-an-issue/scripts/check_acm_present.py`,
`skills/outward-artifact-preflight/scripts/scan_provenance.py`,
`skills/auditing-agent-product-scope/scripts/check_axis_shape.py`,
`skills/auditing-agent-product-scope/scripts/check_middleware_table_shape.py`,
`skills/auditing-git-hosting-surface/scripts/scan_unpinned_actions.py`,
`skills/battle-testing-a-skill/scripts/route_test_model.py`
**ACM row:** same as T9.
**Edges:** depends on T1 only.

1. Same procedure as T9, applied to this cluster. `check_acm_present.py`'s
   two copies are edited independently (each is its own file with its own
   task-visible worktree) -- `tests/test_check_acm_present_sync.py`'s
   existing sync check (Wave 5) is what confirms they stay behaviorally
   identical, not a shared edit here.
2. Proof: same as T9.

### Wave 4 (depends on Waves 1-3 completing -- both tasks document/
register the final shape)

#### T11 -- ADR-0001

**Files:** `docs/adr/0001-adopt-mypy-and-pydantic-for-deterministic-gates.md`
(new)
**ACM row:** "Draft ADR-0001" -- Planned ops quoted verbatim: *"New
`docs/adr/0001-....md` file"*.
**Edges:** depends on T1-T10 (documents their final, verified shape).

1. Draft per `skills/drafting-an-adr/references/adr-template.md`'s
   sections: Context and Problem Statement, Decision Drivers, Considered
   Options, Decision Outcome, Consequences (Good/Bad), Confirmation.
   `Status: Proposed`.
2. Proof: `python3 skills/drafting-an-adr/scripts/check_adr_shape.py`
   passes on the drafted body before commit.

#### T12 -- `.gitapex/ssot.json` gate registration

**Files:** `.gitapex/ssot.json`
**ACM row:** "New mypy CI gate is blocking from day one" -- Planned ops
quoted verbatim: *"New job in `test.yml`; new `policy_sources[]` +
`gates[]` entries in `.gitapex/ssot.json`"*.
**Edges:** depends on T1 (needs the real CI job name/invocation shape).

1. Add a `policy_sources[]` entry for `pyproject.toml`'s `[tool.mypy]`
   section (`id: "pyproject-mypy-config"`). Add a `gates[]` entry
   (`id: "mypy-type-check"`, `kind: "script"`, `script:
   ".github/workflows/test.yml"`, `planes: ["ci"]`, `policy_refs:
   ["pyproject-mypy-config"]`, `tracking_issue: 684`, `status: "active"`,
   `supersedes: null`), matching the existing schema's required fields
   exactly.
2. Proof: `python3 .github/scripts/scan_ssot_schema.py` (or its pytest
   gate) reports no drift against `.gitapex/ssot.schema.json`.

### Wave 5

#### T13 -- Full-suite verification

**Files:** none exclusively owned (verification only).
**ACM row:** "Preserve existing gate/test behavior" -- Planned ops quoted
verbatim: *"Run full suite + coverage gate after every implementation
wave"*.
**Edges:** depends on T1-T12.

1. `uv run --frozen pytest --cov-report=xml --cov-report=json` -- full
   suite green.
2. `uv run --frozen python3 .github/scripts/gate_evals_scripts_coverage.py --coverage-json coverage.json` --
   coverage floor unaffected.
3. Every mypy invocation from T1's CI job, run locally, exits 0.
4. `python3 .github/scripts/scan_ssot_schema.py` -- no drift.
5. For every script touched in T6/T7/T8: confirm `--help` output and
   exit codes are unchanged from before this branch (spot check against
   a pre-change git stash or the `main` branch copy).

## Refactor + adversarial review (Decision 12, step 8 -- mandatory,
non-skippable)

After all 13 tasks complete: one fresh-subagent behavior-preserving
refactor/simplify pass over the full accumulated diff, then one
independent fresh-subagent adversarial code review -- including at least
one constructed case built to defeat the new/modified gates' own
detection logic (per this skill's own Stop boundary for deterministic-gate
scrutiny), not only happy-path confirmation. Every CONFIRMED finding gets
fixed and every task's own Red-Green test re-run, not only the one related
to the fix. Push every fix commit to the remote as it lands.

## Verification plan (summary)

- All of T13 above, green.
- `## Skill audit evidence` in the PR body: this change does not modify
  any `SKILL.md`, so per `hooks/check-pr-skill-audit-disclosure.sh`'s own
  scope this section states an explicit non-applicability waiver rather
  than a battle-testing-a-skill/evaluating-skill-quality verdict.
- Residual, flagged explicitly in the PR body: registering the new
  `mypy` check as a *required* branch-protection status check needs a
  repo-admin action outside this PR's own diff.

# Skill metadata validator consolidation: migrate gitapex_check_skill_shape.py's manifest checks onto the JSON Schema (design + implementation)

**Date:** 2026-08-29
**Status:** Design updated and re-verified against current `main`; supersedes the
2026-08-06 design (PR #795, closed unmerged 2026-08-29). Implementation
proceeds in this same change -- issue #758 was reframed on 2026-08-29 to
own delivery through a merged migration, not design alone.
**Scope:** Full migration design, re-derived check-name audit, and the
implementation itself, per issue #758 (reframed) and issue #734's own
acceptance criteria ("Leaving both validators running in parallel
indefinitely is a known, named risk, not an accepted end state").

Refs #734, #745, #747, #758, #804, #1055. Supersedes the design in closed
PR #795 (branch `claude/gitapex-pr-758-v8ixpy`, never merged).

## 1. Why this supersedes the 2026-08-06 design

The original design (PR #795) got repository-owner sign-off on full
migration, single PR, and `pyyaml`/`jsonschema` adoption, then was closed
without merging. Roughly 1,200 commits landed on `main` in the interim.
Re-verifying the original design against current source (this document's
own research, 2026-08-29) found:

- **File moves**: `check_skill_shape.py` -> `gitapex_check_skill_shape.py`
  (repo-wide `gitapex_` prefix convention). The schema moved out of
  `.gitapex/` to `skills/evaluating-skill-quality/references/skill-metadata.schema.json`
  (commit `838894ae`, "so it travels with the evaluating-skill-quality
  skill when this repository is installed as a plugin elsewhere").
- **The vendoring/portability conflict PR #795 hit is already resolved**:
  issue #804 (filed and merged during that PR's own review) added
  `spec.dependencyPolicy` (`StdlibOnly`/`Declared`) and
  `spec.executionRequirements.packages` (ecosystem-keyed runtime package
  lists), both independent of `spec.portability`. Confirmed live
  (`skills/evaluating-skill-quality/references/skill-metadata.schema.json:51-54`):
  `dependencyPolicy` enum is exactly `["StdlibOnly", "Declared"]`.
- **The hand-rolled checker already recognizes `packages`/`network`
  for shape** (`gitapex_check_skill_shape.py:4106-4121`): today's
  `execution-requirements-well-formed` evidence string reads "spec.executionRequirements,
  if present, is a mapping with only the tools/packages/network keys" --
  this is *not* stale from 2026-08-06; it was updated by intervening work
  (issue #1022-adjacent commits). This changes one sequencing conclusion
  from the original design: declaring `executionRequirements.packages.pip`
  on this checker's own sidecar does **not** need to wait for this
  migration to land first, unlike the original design assumed.
- **The check-name set grew from 15 to 18**, confirmed live via
  `grep`/multiline match against every `CheckResult(...)` call site:
  `dependency-policy-declared` (structural/enum, added alongside
  `dependencyPolicy`) and `external-citations-well-formed` (structural
  shape, added alongside `spec.externalCitations`, issue #1055) are new
  MIGRATE-shaped checks; `external-citations-resolve` (cross-file, matches
  a declared path against a real SKILL.md/references/*.md citation) is a
  new RETAIN check, same shape as `skill-dependencies-resolve`.
- `pyproject.toml`'s Tier C mypy override (lines 151-166) is unchanged in
  substance, though its own "~4,440 lines" comment is now stale (the file
  is 6,230 lines, 113 total `CheckResult(` call sites across the 18 unique
  names plus non-manifest checks).

Nothing found contradicts the original decisions; they carry forward
(section 6). The check-name table (4.3) and the dependency-declaration
step (4.2/4.4) are the two places this document materially differs from
PR #795's version.

## 2. Goals (unchanged from the 2026-08-06 design)

- End the "known, named risk" status by fully migrating schema-expressible
  manifest checks onto the JSON Schema.
- Preserve the external check-name contract: every check name a caller,
  test, or doc currently observes keeps firing under the same name.
- Preserve gate strength: no manifest defect caught today goes uncaught
  after migration.
- Preserve or improve test coverage: manifest-related unit tests in
  `test_gitapex_check_skill_shape.py` are ported or deliberately retired
  (with a stated reason), not silently dropped.

## 3. Non-goals

- The checker's non-manifest checks (SKILL.md/references/*.md prose:
  bare-issue-citation scanning, Markdown link/anchor resolution,
  cross-skill citation resolution, illustrative-model-identifier/
  placeholder scanning, step-location-contradiction detection, the
  `portable-no-*` family, `no-voodoo-constant`, `script-execution-intent-stated`)
  are untouched -- out of scope by kind, not by gap, matching this
  schema's own top-level description.
- No change to `.github/scripts/gitapex_scan_skill_metadata_schema.py`'s
  own cross-file checks (`find_name_mismatch`, `find_skill_dependency_drift`,
  `find_deprecated_replacement_drift`, `find_requires_cycle`) beyond any
  reuse opportunity noted in 4.4.
- No change to `spec.portability`'s own definition or enum -- issue #804
  already settled that it stays a path/instruction-locality axis,
  independent of runtime dependencies.

## 4. Design

### 4.1 Decision: target end state -- full migration (carried forward)

Same decision as PR #795's 4.1: the checker deletes its own structural
parsing/checking logic for schema-expressible checks, replacing it with
`jsonschema.Draft202012Validator`-backed validation, translating each
schema violation back into today's exact `CheckResult` check-name strings.
It keeps its own logic, unmigrated, for checks the schema cannot express:
file-existence, YAML-parse-failure, and cross-file resolution checks.

**Carried-forward owner sign-off**: recorded 2026-08-06 on PR #795 via an
explicit 3-option decision prompt (full migration/single PR chosen over
full migration/staged, and over permanent split). Re-affirmed by the
2026-08-29 reframe of issue #758, which explicitly asked for this work to
proceed through implementation rather than staying design-only.

### 4.2 Decision: dependency reversal -- adopt pyyaml + jsonschema (updated)

**Decision:** `gitapex_check_skill_shape.py` adds `import yaml` and
`import jsonschema` (or the shared `.github/scripts/_gitapex_schema_validation.py`
helper, issue #755, to dedupe against `gitapex_scan_skill_metadata_schema.py`'s
identical validation call), reversing this file's stdlib-only property.

**Dependency-disclosure resolution (already available, no new decision
needed):** declare on this checker's own
`skills/evaluating-skill-quality/metadata/gitapex.yaml`:
- `spec.dependencyPolicy: Declared`
- `spec.executionRequirements.packages.pip: [pyyaml, jsonschema]`
- `spec.portability` unchanged (`Portable`) -- its own instructions still
  resolve entirely inside its own directory; only its runtime package
  footprint changes, and issue #804 built exactly this field for that
  purpose.

Live-verified (this document's own research, 2026-08-29) against the real
schema: a `Declared` + `executionRequirements.packages.pip: [pyyaml,
jsonschema]` instance validates with zero errors; `gitapex_check_skill_shape.py`'s
own current `execution-requirements-well-formed` implementation already
shape-checks the `packages` key today (line 4106-4121) -- so, unlike PR
#795's plan, this sidecar edit does not need to wait for step 2 of the
implementation plan (4.4) to land first. It can land as soon as this
migration's PR opens.

**Why the runtime risk is low inside this repository's own CI/pytest
path:** `pyyaml>=6.0` and `jsonschema>=4.23` are already declared in
`pyproject.toml`'s dev dependency group (added for
`gitapex_scan_skill_metadata_schema.py`, issue #734, and its shared helper,
issue #755); `gitapex_check_skill_shape.py` already runs inside the same
`uv`-managed environment.

**Follow-on cleanup:** once the hand-rolled parser the Tier C mypy
override exists for is deleted (for the MIGRATE checks), narrow or remove
that override -- a consequence of 4.1/4.2, not a new decision.

### 4.3 Decision: check-name contract (re-derived, 18 checks)

All 18 manifest-related check names, confirmed live via multiline `grep`
against every `CheckResult(...)` call site in `gitapex_check_skill_shape.py`
(not docstring prose), and their migration disposition. The 15 rows
carried forward from PR #795 are unchanged in classification; the 3 new
rows are marked accordingly.

| Check name | Classification | Disposition | Rationale |
|---|---|---|---|
| `manifest-envelope` | structural (`const`) | **MIGRATE** | Schema expresses via `properties.apiVersion.const`/`properties.kind.const`. |
| `portability-declared` | structural/enum | **MIGRATE** | Schema expresses via `$defs.spec.properties.portability.enum`. |
| `capability-assumption-declared` | structural/enum | **MIGRATE** | Schema expresses via `capabilityAssumption.enum`. |
| `dependency-policy-declared` | structural/enum (NEW since 2026-08-06) | **MIGRATE** | Schema expresses via `dependencyPolicy.enum` (`StdlibOnly`/`Declared`); live-verified 2026-08-29: a bad value produces exactly one error at `spec.dependencyPolicy`. |
| `references-well-formed` | structural | **MIGRATE** | Schema expresses shape/`minItems`/required subkeys/`maxLength`. |
| `references-grammar` | structural/enum | **MIGRATE** | Schema expresses via `referenceItem.properties.kind.enum`. |
| `external-citations-well-formed` | structural (NEW since 2026-08-06, issue #1055) | **MIGRATE** | Schema expresses via `externalCitationItem` (`required: [path, role]`, path pattern, role enum, `additionalProperties: false`); live-verified 2026-08-29: a bad role or bad path prefix each produce exactly one error at the matching instance path. |
| `skill-dependencies-well-formed` | structural | **MIGRATE** | Schema expresses mapping/array/`uniqueItems`/pattern shape. |
| `requires-portability-compatible` | cross-field, single document | **MIGRATE** | Schema expresses via `allOf`/`if`/`then`; cross-*field*, not cross-*file* -- a single instance can see it. |
| `lifecycle-well-formed` | structural | **MIGRATE** | Schema expresses subfield shape, date `pattern`+`format`, issue-URL pattern, enum. |
| `experimental-stable-compatible` | structural, cross-field | **MIGRATE** | Schema expresses via `not: {required: [experimental, stable]}`. |
| `execution-requirements-well-formed` | structural | **MIGRATE** | Schema expresses mapping/list/tag shape for all three current subkeys (`tools`, `packages`, `network`). |
| `metadata-file-present` | filesystem existence | **RETAIN** | A schema validates a parsed document's shape; it cannot assert the file exists. |
| `manifest-parsable` | parser-specific | **RETAIN, reimplemented** | Check name/gate boundary stay; hand-rolled malformed-line detection replaced by `yaml.safe_load(...)` `try`/`except`, since the migration adopts a real YAML parser anyway. |
| `metadata-name-matches-dir` | cross-file | **RETAIN** | Compares `metadata.name` to the real directory name; a schema instance never sees its own file path. `gitapex_scan_skill_metadata_schema.py::find_name_mismatch` already reimplements this independently. |
| `skill-dependencies-resolve` | cross-file | **RETAIN** | Requires reading sibling directories. `find_skill_dependency_drift` already reimplements this independently. |
| `lifecycle-deprecated-replacement-resolves` | cross-file | **RETAIN** | Requires reading sibling directories. `find_deprecated_replacement_drift` already reimplements this independently. |
| `external-citations-resolve` | cross-file (NEW since 2026-08-06, issue #1055) | **RETAIN** | Matches a declared `path` against a real citation found in this skill's own SKILL.md/references/*.md prose -- content-scanning, not sidecar shape; no JSON Schema instance can see another file's prose. |

**Net:** 12 MIGRATE, 6 RETAIN (1 reimplemented, 5 unchanged). No check
name is renamed, removed, or newly introduced by this migration -- the
external check-name contract is unchanged; only the mechanism behind 12 of
the 18 names changes.

Out of scope, confirmed unaffected by this migration (non-manifest checks):
`skill-md-readable`, `description-present`, `description-no-xml`,
`description-length`, `description-yaml-safe`, `name-pattern`,
`name-no-xml`, `name-length`, `name-not-reserved`,
`invocation-mode-well-formed`, `body-length`, `references-flat`, `toc:*`,
`links-inside-skill`, `anchor-targets-resolve`,
`related-skill-references-resolve`, `cross-skill-citation-resolves`,
`mechanism-fit-subsections-cite-sources`, `no-bare-issue-citation`,
`no-illustrative-model-identifier`, `no-raw-angle-bracket-placeholder`,
`no-step-location-contradiction`, `no-voodoo-constant`,
`script-execution-intent-stated`, and the five `portable-no-*` checks
(`portable-no-repo-path-citation`,
`portable-no-unhedged-inline-path-citation`,
`portable-no-unhedged-inline-issue-citation`,
`portable-no-unhedged-skill-fact-claim`,
`portable-no-out-of-skill-scripts-citation`).

### 4.4 Decision: migration sequencing -- single PR (carried forward), updated implementation plan

**Decision:** the migration lands as one implementation PR, matching the
recorded owner sign-off (4.1) and the 2026-08-29 reframe of issue #758.

**Implementation plan:**

1. Add `yaml`/`jsonschema` imports (or the shared
   `_gitapex_schema_validation.py` helper) to `gitapex_check_skill_shape.py`;
   load `skills/evaluating-skill-quality/references/skill-metadata.schema.json`
   once.
2. For each of the 12 MIGRATE checks, replace the hand-rolled shape logic
   with a call into the shared schema validator, mapping the resulting
   `jsonschema` validation errors' instance paths back to the existing
   check-name strings (4.3) so `CheckResult` output is unchanged in shape.
   `manifest-envelope`'s two-constraint merge (`apiVersion.const`,
   `kind.const`) needs a many-to-one combine, same as PR #795's own
   finding: 0/1/2 errors combine into one `CheckResult` with combined
   evidence.
3. Reimplement `manifest-parsable` via `yaml.safe_load(...)` with a
   `try`/`except yaml.YAMLError`, replacing the hand-rolled malformed-line
   scan.
4. Delete the now-dead hand-rolled parsing helpers that existed solely to
   support the 12 migrated checks; keep only what still backs the 6 RETAIN
   checks.
5. Narrow or remove `pyproject.toml`'s `[tool.mypy.overrides]` Tier C
   carve-out for this module once the code it was written for is gone.
6. Declare `spec.dependencyPolicy: Declared` and
   `spec.executionRequirements.packages.pip: [pyyaml, jsonschema]` on
   `skills/evaluating-skill-quality/metadata/gitapex.yaml`; leave
   `spec.portability` at `Portable`. Unlike PR #795's plan, this step does
   **not** need to wait for step 2 -- today's hand-rolled
   `execution-requirements-well-formed` already shape-checks `packages`
   (4.2). Update `SKILL.md`'s usage line to state the new `pyyaml`/
   `jsonschema` runtime requirement explicitly. Re-run
   `gitapex_check_skill_shape.py` against
   `skills/evaluating-skill-quality/` itself afterward.
7. Port `test_gitapex_check_skill_shape.py`'s manifest-related unit tests:
   for MIGRATE checks, retire tests that only exercised deleted hand-rolled
   logic (the schema-side equivalent already exists in
   `tests/test_gitapex_scan_skill_metadata_schema.py`), keeping one smoke
   test per check name confirming it still fires under its existing name
   through the new path. For RETAIN checks, keep tests unchanged.
8. Re-run the "kitchen sink" test asserting every canonical check name
   fires at least once on a maximally-populated fixture, confirming no
   check name silently disappeared.
9. Re-run `tests/test_gitapex_scan_skill_metadata_schema.py`'s real-repo
   gate and any equivalent real-tree gate for
   `gitapex_check_skill_shape.py` -- both must pass with zero regressions
   against the actual repository tree, not only synthetic fixtures.
10. Update any doc or worked example citing a specific manifest check-name
    list or count in the same change.

### 4.5 Backward compatibility and risks

- **Check-name contract preserved:** no caller, test, or doc that cites a
  check name by string needs updating for that reason; names are stable by
  design (4.3).
- **Evidence-string churn is expected, not a regression:** `jsonschema`
  validation error messages will not read identically to the hand-rolled
  reader's evidence strings; tests asserting exact evidence text need
  updating (scoped work item 7 in 4.4).
- **`skill-dependencies-well-formed` gains a real, disclosed
  strengthening:** the schema's `uniqueItems: true` on
  `skillDependencies.requires`/`relatedTo` and `executionRequirements.tools.*`
  rejects a duplicate entry the hand-rolled equivalents silently accept --
  carried forward from PR #795's own live spike (2026-08-06); worth
  re-confirming against the current 25-plus-sidecar tree as part of step 9.
- **mypy Tier C removal risk:** removing the override could resurface
  annotation gaps; mitigated by running `mypy` as an explicit verification
  step (4.6).
- **Rollback:** a single `git revert` of this PR's commit(s) restores the
  hand-rolled parser and the stdlib-only property in one step.

### 4.6 Verification

- `uv run pytest` full suite green, before/after pass counts stated
  explicitly.
- `python3 .github/scripts/gitapex_scan_skill_metadata_schema.py` still
  reports no drift (unchanged -- this migration does not touch the
  scanner).
- `gitapex_check_skill_shape.py` run against every real `skills/*/`
  directory with zero regressions versus the pre-migration baseline (same
  check names fire, same pass/fail per sidecar) -- a live proof against
  the real tree, not a mocked fixture.
- `uv run mypy` / `uv run ruff check` clean on the modified files.
- Diff the full set of check names observed in a real run before and
  after to confirm the check-name contract is unchanged.

## 5. Sequencing

This document closes issue #758's reframed acceptance criteria (target
end state, dependency decision, re-audited check-name contract, and the
migration itself, executed in this same change per the 2026-08-29
reframe) rather than spawning a separate follow-up implementation issue,
as the original (superseded) scope would have.

## 6. Decision record

| Criterion | Decision | Recorded by |
|---|---|---|
| Target end state | Full migration (12 checks migrate to the schema, 6 retained) | Repository owner, 2026-08-06 decision prompt (PR #795); reaffirmed by the 2026-08-29 reframe of issue #758 |
| Dependency reversal | Adopt `pyyaml`/`jsonschema` in `gitapex_check_skill_shape.py` | Repository owner, same 2026-08-06 decision prompt |
| Dependency-disclosure mechanism | `spec.dependencyPolicy: Declared` + `spec.executionRequirements.packages.pip`; `spec.portability` unchanged | Resolved by issue #804 (merged); no re-decision needed |
| Check-name contract | 12 MIGRATE / 6 RETAIN, enumerated in 4.3 (up from 10/5 in PR #795 -- 3 checks added by issues #804/#1055 since), zero renames | This document, re-derived from a direct 2026-08-29 source read of `gitapex_check_skill_shape.py` and the current schema, live-verified for the 2 new MIGRATE checks |
| Migration sequencing | Single PR, not staged; implementation proceeds in this same PR (issue #758's 2026-08-29 reframe) | Repository owner, same 2026-08-06 decision prompt; scope-widened 2026-08-29 |

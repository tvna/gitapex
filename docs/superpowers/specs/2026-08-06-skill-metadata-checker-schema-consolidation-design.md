# Skill metadata validator consolidation: migrate check_skill_shape.py's manifest checks onto the JSON Schema

**Date:** 2026-08-06
**Status:** Design decided; owner sign-off recorded below. No code change in this document.
**Scope:** Design only, per issue #758. Decides the target end state, the dependency
reversal, the check-name contract, and the migration sequencing for the
dual-source-of-truth risk issue #734's own acceptance criteria flagged and left
open ("Leaving both validators running in parallel indefinitely is a known,
named risk, not an accepted end state"). This document does not implement the
migration; a follow-up implementation issue/PR executes the plan recorded here.

Refs #734, #745, #747, #758.

## 1. Motivation

`skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py` (4,600
lines) validates the `metadata/gitapex.yaml` sidecar via a hand-rolled,
stdlib-only, indentation-aware reader (`_parse_manifest`), a deliberate design
choice recorded in `docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md`
("The checker stays stdlib-only and read-only"). Issue #734 added
`.gitapex/skill-metadata.schema.json` plus
`.github/scripts/gitapex_scan_skill_metadata_schema.py`, a real
`jsonschema.Draft202012Validator`-backed validator for the same sidecar,
explicitly as an *additive* parallel validator, naming the resulting
dual-source-of-truth risk in its own acceptance criteria without resolving it.
That risk is not hypothetical: `spec.executionRequirements` was added to
`gitapex_check_skill_shape.py` before the corresponding schema field existed,
demonstrating the two can independently drift.

A direct read of both validators (this document's own research) shows the
drift risk is now largely *latent* rather than starting from a genuine gap:
of `gitapex_check_skill_shape.py`'s 15 manifest-related check names, 10 are
already structurally duplicated in the schema, and the schema's own field
descriptions already state, field by field, why each duplicated rule is
schema-expressible and why each retained cross-file rule is not. The
consolidation this document decides is closer to deleting proven-redundant
code than designing new validation behavior.

## 2. Goals

- Record a single target end state for the two validators, ending the
  "known, named risk" status issue #734 left open.
- Preserve the external check-name contract: every check name a caller,
  test, or doc currently observes keeps firing under the same name.
- Preserve gate strength: no manifest defect that is caught today goes
  uncaught after migration.
- Preserve or improve test coverage: the ~163 manifest-related unit tests in
  `test_gitapex_check_skill_shape.py` are ported or deliberately retired
  (with a stated reason), not silently dropped.

## 3. Non-goals

- `gitapex_check_skill_shape.py`'s non-manifest checks (SKILL.md
  name/description/body, `references/` directory flatness, Markdown
  link/anchor resolution, cross-skill citation resolution, bare-issue-number
  scanning, illustrative-model-identifier/placeholder scanning,
  step-location-contradiction detection) are untouched. These inspect prose,
  not the sidecar's shape, and the schema's own top-level description
  already states they are "out of scope, permanently, by kind rather than by
  gap."
- No change to the schema's own structural rules, `$defs`, or `additionalProperties`
  posture.
- No change to `.github/scripts/gitapex_scan_skill_metadata_schema.py`'s
  cross-file checks (`find_name_mismatch`, `find_skill_dependency_drift`,
  `find_deprecated_replacement_drift`, `find_requires_cycle`) beyond the
  reuse opportunity noted in 4.3 -- collapsing them into
  `gitapex_check_skill_shape.py` is out of scope for this migration.
- This document is not the implementation. It authorizes and specifies a
  follow-up implementation issue/PR; no manifest-parsing code changes here.

## 4. Design

### 4.1 Decision: target end state -- full migration

**Decision:** `gitapex_check_skill_shape.py` deletes its own structural
parsing/checking logic for the 10 checks classified MIGRATE in section 4.3,
and instead validates the parsed sidecar against
`.gitapex/skill-metadata.schema.json` via `jsonschema.Draft202012Validator`,
translating each schema violation back into today's exact `CheckResult`
check-name strings so the external contract (4.3, section 5 of issue #758)
is unchanged. It keeps its own logic, unmigrated, for the 5 checks
classified RETAIN: file-existence, YAML-parse-failure, and the three
cross-file resolution checks a single schema instance cannot see (it never
observes its own file path or sibling directories).

**Recorded owner sign-off:** presented as one of three options (full
migration/single PR, full migration/staged sub-project, permanent split)
during this issue's design work; the repository owner selected **"Full
migration, single PR"** via an explicit decision prompt on 2026-08-06. This
satisfies issue #758's criterion "Target end state decided and recorded"
and its required proof method ("Repository owner sign-off, matching
#734/#745's own bar for this class of decision").

**Rejected alternative -- permanent split:** documenting today's de facto
split as an accepted trade-off was considered and rejected. Given 10 of 15
checks are already provably redundant (identical rule, independently
verified against all 24 real sidecars per issue #734's own claim), keeping
both permanently would mean maintaining two implementations of the same 10
rules indefinitely, with no proportional safety benefit -- the schema is not
weaker than the hand-rolled parser for these checks; it is the same rule
expressed once, formally, with `format_checker` validation the hand-rolled
reader does not attempt (e.g. calendar-invalid `lifecycle` dates).

### 4.2 Decision: dependency reversal -- adopt pyyaml + jsonschema

**Decision:** `gitapex_check_skill_shape.py` adds `import yaml` and
`import jsonschema` (or, preferably, imports the shared
`.github/scripts/_gitapex_schema_validation.py` helper introduced in issue
#755 to dedupe against `gitapex_scan_skill_metadata_schema.py`'s identical
validation call), reversing the stdlib-only decision recorded in the
2026-07-19 spec's section 4.1 ("Parsing (stdlib-only preserved)") and
reflected today in `pyproject.toml`'s dedicated `[tool.mypy.overrides]`
"Tier C" carve-out for this module.

**Recorded owner sign-off:** the same 2026-08-06 decision that selected
"Full migration" explicitly named this dependency reversal in its option
description ("reversing its recorded stdlib-only decision... pyyaml/jsonschema
are already dev dependencies used elsewhere in the repo -- this adds an
import site, not a new dependency"); the repository owner's selection of
that option is the recorded sign-off, satisfying issue #758's "Dependency
decision recorded" criterion and its proof method (owner sign-off, "a
silent/implicit dependency change would violate this repo's own
declarative-dependency-management principle" -- this is not silent: it is
named and approved here).

**Why the risk is low:** `pyyaml>=6.0` and `jsonschema>=4.23` (plus
`types-PyYAML`, `types-jsonschema` for mypy) are already declared in
`pyproject.toml`'s dev dependency group, added for
`gitapex_scan_skill_metadata_schema.py` (issue #734) and its shared helper
`_gitapex_schema_validation.py` (issue #755). `gitapex_check_skill_shape.py`
already runs inside the same `uv`-managed dev environment (same
`testpaths`/`pythonpath` in `pyproject.toml`), so no `pyproject.toml` edit
is required -- only a new import site in code that already executes where
both packages are installed and already exercised on every CI run via the
scanner's own tests.

**Follow-on cleanup implied, not separately decided here:** once the
hand-rolled parser the Tier C mypy override exists for is deleted (for the
10 MIGRATE checks), the implementation PR should remove or narrow that
override -- called out here so the migration plan (4.4) includes it, not
because it needs separate owner sign-off (it is a consequence of 4.1/4.2,
not a new decision).

### 4.3 Decision: check-name contract

All 15 manifest-related check names, confirmed by direct grep against
`CheckResult(...)` call sites in `gitapex_check_skill_shape.py` (not
docstring prose), and their migration disposition:

| Check name | Today's classification | Disposition | Rationale |
|---|---|---|---|
| `manifest-envelope` | structural (`const`) | **MIGRATE** | Schema already expresses via `properties.apiVersion.const` / `properties.kind.const`. |
| `portability-declared` | structural/enum | **MIGRATE** | Schema already expresses via `$defs.spec.properties.portability.enum`. |
| `capability-assumption-declared` | structural/enum | **MIGRATE** | Schema already expresses via `capabilityAssumption.enum`. |
| `references-well-formed` | structural | **MIGRATE** | Schema already expresses shape/`minItems`/required subkeys/`maxLength`. |
| `references-grammar` | structural/enum | **MIGRATE** | Schema already expresses via `referenceItem.properties.kind.enum`. |
| `skill-dependencies-well-formed` | structural | **MIGRATE** | Schema already expresses mapping/array/`uniqueItems`/pattern shape. |
| `requires-portability-compatible` | cross-field, single document | **MIGRATE** | Schema already expresses via `allOf`/`if`/`then`; this is a cross-*field*, not cross-*file*, rule -- a single schema instance can see it. |
| `lifecycle-well-formed` | structural | **MIGRATE** | Schema already expresses subfield shape, date `pattern`+`format`, issue-URL pattern, enum. |
| `experimental-stable-compatible` | structural, cross-field | **MIGRATE** | Schema already expresses via `not: {required: [experimental, stable]}`. |
| `execution-requirements-well-formed` | structural | **MIGRATE** | Schema already expresses mapping/list/tag shape. |
| `metadata-file-present` | filesystem existence | **RETAIN** | A schema validates a parsed document's shape; it cannot assert the file exists. No schema-side analog. |
| `manifest-parsable` | parser-specific | **RETAIN, reimplemented** | Check name and gate boundary stay; the hand-rolled malformed-line detector is replaced by a `yaml.safe_load(...)` `try`/`except`, since the migration adopts a real YAML parser anyway (4.2). |
| `metadata-name-matches-dir` | cross-file | **RETAIN** | Compares `metadata.name` to the real directory name; a schema instance never sees its own file path. `gitapex_scan_skill_metadata_schema.py::find_name_mismatch` already reimplements this independently -- reusing it (rather than a third implementation) is a follow-up dedup opportunity, not required to close this issue's risk. |
| `skill-dependencies-resolve` | cross-file | **RETAIN** | Requires reading sibling directories. `find_skill_dependency_drift` already reimplements this independently -- same dedup note as above. |
| `lifecycle-deprecated-replacement-resolves` | cross-file | **RETAIN** | Requires reading sibling directories. `find_deprecated_replacement_drift` already reimplements this independently -- same dedup note as above. |

**Net:** 10 MIGRATE, 5 RETAIN (1 reimplemented, 4 unchanged). No check name
is renamed, removed, or newly introduced by this migration -- the
implementation PR's diff to the check-name contract is empty by design;
only the mechanism behind 10 of the 15 names changes.

Out of scope, confirmed unaffected by this migration (non-manifest checks,
listed for completeness so no reader mistakes silence for an oversight):
`skill-md-readable`, `description-present`, `description-no-xml`,
`description-length`, `name-pattern`, `name-no-xml`, `name-length`,
`name-not-reserved`, `invocation-mode-well-formed`, `body-length`,
`references-flat`, `toc:*`, `links-inside-skill`,
`anchor-targets-resolve`, `related-skill-references-resolve`,
`cross-skill-citation-resolves`, `mechanism-fit-subsections-cite-sources`,
`no-bare-issue-citation`, `no-illustrative-model-identifier`,
`no-raw-angle-bracket-placeholder`, `no-step-location-contradiction`, and
the four `portable-no-*` checks.

### 4.4 Decision: migration sequencing -- single PR

**Decision:** the migration lands as one implementation PR, not a staged
A/B/C/D-style sub-project, per the recorded owner sign-off (4.1).

**Why single-PR is safe here** (distinguishing this from cases that do
warrant staging, like the original four-part metadata-sidecar sub-project):
the blast radius is checker-internal only (no external interface changes
beyond the check-name contract, which section 4.3 keeps stable by
construction); both validators already agree on all 24 real sidecars today
(issue #734's own verified claim, re-confirmed by
`test_real_repository_skill_sidecars_have_no_schema_drift`); and the
migration reuses proven validation code (`_gitapex_schema_validation.py`,
issue #755) rather than writing new logic, so there is no independent
design surface that benefits from being split into reviewable increments.

**Implementation plan (executed by the follow-up PR, not this document):**

1. Add `yaml`/`jsonschema` imports (or the shared `_gitapex_schema_validation.py`
   helper) to `gitapex_check_skill_shape.py`; load
   `.gitapex/skill-metadata.schema.json` once.
2. For each of the 10 MIGRATE checks, replace the hand-rolled shape logic
   with a call into the shared schema validator, mapping the resulting
   `jsonschema` validation errors' instance paths back to the existing
   check-name strings (4.3) so `CheckResult` output is unchanged in shape.
3. Reimplement `manifest-parsable` via `yaml.safe_load(...)` with a
   `try`/`except yaml.YAMLError`, replacing the hand-rolled malformed-line
   scan.
4. Delete the now-dead hand-rolled parsing helpers that existed solely to
   support the 10 migrated checks; keep only what still backs the 5 RETAIN
   checks.
5. Narrow or remove `pyproject.toml`'s `[tool.mypy.overrides]` Tier C
   carve-out for this module once the code it was written for is gone.
6. Port `test_gitapex_check_skill_shape.py`'s manifest-related unit tests:
   for MIGRATE checks, retire tests that only exercised deleted hand-rolled
   logic (the schema-side equivalent already exists in
   `test_gitapex_scan_skill_metadata_schema.py`), keeping one smoke test per
   check name confirming it still fires under its existing name through the
   new path, so a future accidental check-name drop is still caught. For
   RETAIN checks, keep tests unchanged.
7. Re-run the "kitchen sink" test that asserts every canonical check name
   fires at least once on a maximally-populated fixture, confirming no
   check name silently disappeared.
8. Re-run `tests/test_gitapex_repository_skill_shape.py` (the live,
   parametrized-over-every-real-`skills/*/`-directory gate) and
   `test_gitapex_scan_skill_metadata_schema.py`'s real-repo gate -- both
   must still pass with zero regressions against the actual repository
   tree, not only synthetic fixtures.
9. Update any doc or worked example citing a specific manifest check-name
   list or count in the same change (issue #758's criterion 3 explicitly
   requires this, not a follow-up).

### 4.5 Backward compatibility and risks

- **Check-name contract preserved:** no caller, test, or doc that cites a
  check name by string (including issue #758's own body, which cites
  several) needs updating for that reason; names are stable by design (4.3).
- **Evidence-string churn is expected, not a regression:** `jsonschema`
  validation error messages will not read identically to the hand-rolled
  reader's evidence strings. Tests asserting exact evidence text (as
  opposed to check name + pass/fail) will need updating; this is scoped
  work item 6 in 4.4, not an unplanned surprise.
- **mypy Tier C removal risk:** removing the override could resurface
  annotation gaps if third-party stub coverage differs from the fully
  hand-annotated code it replaces; mitigated by running `mypy` as an
  explicit verification step (4.6) before the implementation PR claims
  completion.
- **Rollback:** a single `git revert` of the implementation PR's commit(s)
  restores the hand-rolled parser and the stdlib-only property in one step,
  matching this repository's revert-over-reimplementation preference for
  undoing a merged change.

### 4.6 Verification (for the follow-up implementation PR, not this document)

- `uv run pytest` full suite green, with before/after pass counts stated
  explicitly (matching issue #747's own precedent of citing exact counts).
- `python3 .github/scripts/gitapex_scan_skill_metadata_schema.py` still
  reports `No skill metadata schema drift found.` (unchanged -- this
  migration does not touch the scanner).
- `gitapex_check_skill_shape.py` run against all 24 real `skills/*/`
  directories with zero regressions versus the pre-migration baseline (same
  check names fire, same pass/fail per sidecar) -- a live proof against the
  real tree, not a mocked fixture, per this repository's own
  indirect-signal ban on completion claims.
- `uv run mypy` / `uv run ruff check` clean on the modified files.
- Confirm the check-name contract is unchanged by diffing the full set of
  check names observed in a real run before and after.

## 5. Sequencing

This design document closes issue #758's three "design only" acceptance
criteria: target end state decided and recorded (4.1), dependency decision
recorded (4.2), and migration plan sequenced (4.4). Issue #758 itself is
explicitly scoped to design only ("No code change in this issue -- design
and decision only"); the code change specified in 4.4 belongs to a
follow-up implementation issue, opened separately per this repository's
issue-first rule, that cites this document as its plan.

## 6. Decision record

| Criterion | Decision | Recorded by |
|---|---|---|
| Target end state | Full migration (10 checks migrate to the schema, 5 retained for file-existence/cross-file reasons) | Repository owner, explicit 3-option decision prompt, 2026-08-06 |
| Dependency reversal | Adopt `pyyaml`/`jsonschema` in `gitapex_check_skill_shape.py` (already dev dependencies) | Repository owner, same decision prompt |
| Check-name contract | 10 MIGRATE / 5 RETAIN, enumerated in 4.3, zero renames | This document, derived from direct source read of `gitapex_check_skill_shape.py` and `.gitapex/skill-metadata.schema.json` |
| Migration sequencing | Single PR, not staged | Repository owner, same decision prompt |

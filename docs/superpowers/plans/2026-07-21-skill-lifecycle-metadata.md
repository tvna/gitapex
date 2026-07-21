# Skill Lifecycle Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `spec.lifecycle` (two independent, optional sub-blocks --
`experimental` and `deprecated`) to the skill metadata sidecar, enforced
by the deterministic shape checker, with no migration of any existing
skill.

**Architecture:** One nesting level deeper than the existing
`spec.skillDependencies` handling in `check_skill_shape.py`'s
stdlib-only manifest parser: `spec` -> `lifecycle` -> `experimental`/
`deprecated` -> scalar fields, instead of `spec` -> `skillDependencies`
-> `requires`/`relatedTo` -> list items.

**Tech Stack:** Python 3 standard library only (`datetime.date` for real
calendar-date validation, no new dependency), pytest for the checker's
tests, Markdown for the skills.

## Global Constraints

- Spec of record:
  `docs/superpowers/specs/2026-07-21-skill-lifecycle-metadata-design.md`
- Sidecar path unchanged: `skills/<skill-name>/metadata/gitapex.yaml`
- `spec.lifecycle.experimental`: `reason`/`trackingIssue` required,
  `since` optional
- `spec.lifecycle.deprecated`: `reason`/`replacement` required,
  `since`/`removeAfter` optional
- `since`/`removeAfter`, when present, are real `YYYY-MM-DD` dates
- `trackingIssue`, when present, is an anchored `#123` or
  `owner/repo#123` reference (shape only, never resolved live)
- `replacement`, when present, resolves to an existing sibling skill
  directory (dangling-reference gate, same as `spec.skillDependencies`)
- No mutual-exclusion gate between `experimental` and `deprecated`
- `check_skill_shape.py` stays stdlib-only, read-only, and its 0/1/2
  exit-code contract is unchanged
- Behavior-neutrality invariant holds: no skill's runtime procedure may
  read or branch on `spec.lifecycle`
- Every commit cites `Refs #236`

## Task 1: Parser + checks + docstring + tests (one commit)

These four sub-parts land together, not as separate commits: the tests
and the feature they exercise must be green as a unit, and an
intermediate commit with the parser but not the checks (or vice versa)
would be either untested or dead code.

- [ ] **Step 1: Add the new constants**

  In `skills/evaluating-skill-quality/scripts/check_skill_shape.py`,
  next to `SKILL_DEPENDENCY_SUBKEYS`/`SKILL_DEP_SUBKEY_RE`: add
  `LIFECYCLE_SUBKEYS`, `LIFECYCLE_FIELDS`, `LIFECYCLE_REQUIRED_FIELDS`,
  `LIFECYCLE_SUBKEY_RE`, `LIFECYCLE_UNKNOWN_SUBKEY_RE`,
  `LIFECYCLE_FIELD_RE`, `LIFECYCLE_DATE_RE`, `LIFECYCLE_ISSUE_REF_RE`.
  Add `import datetime` near the top.

  Verify: `python3 -c "import ast; ast.parse(open('skills/evaluating-skill-quality/scripts/check_skill_shape.py').read())"`
  parses without error.

- [ ] **Step 2: Extend `ManifestParse` and `_parse_manifest`**

  Add `unknown_lifecycle_keys`/`unknown_lifecycle_fields` fields to
  `ManifestParse`. Add `in_lifecycle`/`lifecycle`/`lifecycle_subkey`/
  `lifecycle_field_buffer` state and `_finalize_lifecycle_subkey`/
  `_finalize_lifecycle` helpers to `_parse_manifest`, mirroring
  `in_skill_deps`/`skill_deps`/`_finalize_skill_deps` one nesting level
  deeper. Insert the new per-line handling immediately after the
  existing `if in_skill_deps:` block; extend the generic 2-space
  nested-scalar branch with a third `elif key == "lifecycle" ...`
  case; call `_finalize_lifecycle()` at loop end and include the two new
  fields in the `return ManifestParse(...)` call.

  Verify: a scratch script parsing a hand-written two-block
  `spec.lifecycle` fixture returns the expected nested dict (or write
  the `test_manifest_parser_parses_spec_lifecycle` case from Step 4
  first and run it standalone).

- [ ] **Step 3: Add `_valid_lifecycle_date`, `_valid_tracking_issue`,
  `_lifecycle_checks`, and wire them in**

  Add the two validators next to `_valid_skill_dependency_list`. Add
  `_lifecycle_checks` right after `_skill_dependency_checks`, mirroring
  its early-return ladder. In `check_shape()`: unpack
  `unknown_lifecycle_keys`/`unknown_lifecycle_fields` from `parsed`
  (and initialize both to `[]` in the `except` mirror); call
  `_lifecycle_checks(...)` right after the `_skill_dependency_checks`
  call; add `lifecycle-well-formed`/
  `lifecycle-deprecated-replacement-resolves` FAILing entries to the
  unreadable/malformed-sidecar fallback branch.

  Verify: `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality`
  still exits 0 (no `lifecycle` key on any real skill yet, so both new
  checks report "not declared (optional)").

- [ ] **Step 4: Update the module docstring**

  Add a description of the two new checks to the "Checks (the canonical
  list...)" bullet list, in the same descriptive style as the
  `spec.skillDependencies` paragraph already there.

- [ ] **Step 5: Add the test suite**

  In `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`:
  two `_parse_manifest`-level unit tests
  (`test_manifest_parser_parses_spec_lifecycle`,
  `test_manifest_parser_lifecycle_unknown_keys_are_collected`) placed
  after `test_manifest_parser_parses_spec_skill_dependencies`; a
  `_LIFECYCLE_CHECKS` tuple and `_write_lifecycle_sidecar` helper
  mirroring `_SKILL_DEP_CHECKS`/`_write_skill_deps_sidecar`; and the
  full valid/absent/invalid test triad at the end of the file (absent;
  experimental-only; deprecated-only; both blocks present; missing
  required fields x2; unknown field; unknown top-level key; dangling
  replacement; wrong-shape date; wrong-but-shaped calendar date;
  malformed trackingIssue; whole-field wrong type; sub-block wrong type;
  unreadable sidecar; spec not a mapping).

  Verify: `uv run pytest skills/evaluating-skill-quality/scripts/test_check_skill_shape.py -q --no-cov`
  -- all new and existing cases pass.

- [ ] **Step 6: Run the full suite and commit**

  `uv run pytest -q --no-cov` -- zero regressions across the whole
  repository (in particular `tests/test_skill_metadata_sidecar.py`,
  which needs no changes: it already exercises the new checks against
  all 17 real sidecars for free, since none declares `lifecycle`).
  Commit message: `feat(skill-metadata): parse and gate spec.lifecycle`,
  body summarizing the schema/checks, `Refs #236`.

## Task 2: Documentation (separate commit)

- [ ] **Step 1: Add the `## Lifecycle` section to `SKILL.md`**

  Insert between the existing `## Capability assumption` and
  `## Procedure` headings: the schema example, required/optional fields
  per sub-block, and a link to `references/rubric.md`'s Lifecycle
  section.

- [ ] **Step 2: Add the `## Lifecycle` section to `rubric.md`**

  Add a `- [Lifecycle](#lifecycle)` Table of contents entry after
  `Capability assumption`. Insert the full section between
  `## Capability assumption` and `## 1. Discovery`, explicitly stating
  (unlike Portability level/Capability assumption) that this field has
  no per-dimension grading effect.

- [ ] **Step 3: Re-run the shape checker and full suite**

  `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py
  skills/evaluating-skill-quality` -- confirm 28/28 checks still pass,
  including the Portable self-citation scan against the new prose (that
  skill declares `portability: Portable`). `uv run pytest -q --no-cov`
  -- zero regressions.

- [ ] **Step 4: Commit**

  Message: `docs(skill-metadata): document spec.lifecycle in
  SKILL.md/rubric.md`, `Refs #236`.

## Done when

- `spec.lifecycle` parses and is gated exactly as specified above.
- No existing skill's sidecar is modified.
- `SKILL.md`/`rubric.md` document the field in the established
  paired-heading convention.
- Full test suite green; `check_skill_shape.py` still stdlib-only,
  read-only, 0/1/2 exit-code contract unchanged.

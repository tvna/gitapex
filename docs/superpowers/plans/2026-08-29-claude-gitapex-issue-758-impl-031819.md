# Task list: issue #758 manifest-checker/JSON-Schema migration

Source: `docs/superpowers/specs/2026-08-29-skill-metadata-checker-schema-consolidation-design.md`
section 4.4 (10-step plan) and section 4.3 (12 MIGRATE / 6 RETAIN table),
and issue #758's re-verified Acceptance Criteria Map.

Execution mode: **sequential main-thread fallback** (Workflow tool not
opted into by the user this session; per this skill's own Notes section,
the fallback is architecturally equivalent, just without wave-level
parallelism). Tasks below are still recorded with a file-ownership map and
interface-dependency edges for the record, even though no parallel wave
actually dispatches.

## File-ownership map

| Task | Owned file(s) |
|---|---|
| 1 | `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py` |
| 2 | `skills/evaluating-skill-quality/metadata/gitapex.yaml`, `skills/evaluating-skill-quality/SKILL.md` |
| 3 | `pyproject.toml` |
| 4 | `skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py` |
| 5 | (no file ownership -- verification + dogfooding only) |

## Interface-dependency edges

- Task 3 (Tier C mypy override) depends on Task 1 (needs the dead code
  actually deleted first).
- Task 4 (test porting) depends on Task 1 (needs the final evidence-string
  shapes and check-name mapping).
- Task 5 (verification, dogfooding, PR) depends on Tasks 1-4 all complete.
- Task 2 has **no** interface dependency on Task 1 (design doc 4.2/4.4
  step 6 correction: the hand-rolled checker already shape-recognizes
  `executionRequirements.packages`/`network` today) -- could run in
  parallel with Task 1 under a real wave dispatch; runs first here purely
  because it is small and unblocks nothing else.

## Wave assignment (for the record; executed sequentially, not dispatched)

- Wave 1: Task 2 (no dependencies).
- Wave 2: Task 1 (no dependencies, but shares no file with Task 2 -- would
  be co-assignable to wave 1 under real parallel dispatch).
- Wave 3: Task 3, Task 4 (both depend only on Task 1; no shared file
  between them, so co-assignable to the same wave).
- Wave 4: Task 5 (depends on everything above).

## Tasks

1. **Migrate the 12 MIGRATE checks onto the schema; reimplement
   `manifest-parsable`; delete dead hand-rolled helpers.** Add
   `yaml`/`jsonschema` imports and schema loading;
   for each of `manifest-envelope`, `portability-declared`,
   `capability-assumption-declared`, `dependency-policy-declared`,
   `references-well-formed`, `references-grammar`,
   `external-citations-well-formed`, `skill-dependencies-well-formed`,
   `requires-portability-compatible`, `lifecycle-well-formed`,
   `experimental-stable-compatible`, `execution-requirements-well-formed`,
   replace hand-rolled logic with schema-backed validation, preserving
   exact `CheckResult` check-name strings and PASS/FAIL semantics.
   Reimplement `manifest-parsable` via `yaml.safe_load`. Delete the
   now-dead helper functions that existed solely for the 12 migrated
   checks. Irreversibility: high (large deletion inside a
   heavily-relied-on gate file) -- proceeds only under this task's own
   fresh confirmation, granted via the already-approved Branch Plan
   (Authorization record below); every deletion is covered by re-running
   the full test suite immediately after.
2. **Declare the new runtime dependency on this skill's own sidecar.**
   `spec.dependencyPolicy: Declared`,
   `spec.executionRequirements.packages.pip: [pyyaml, jsonschema]` in
   `skills/evaluating-skill-quality/metadata/gitapex.yaml` (`portability`
   unchanged); update `SKILL.md`'s usage line. Irreversibility: low
   (additive metadata declaration).
3. **Narrow/remove `pyproject.toml`'s Tier C mypy override.** Depends on
   Task 1's deletions; re-run `uv run mypy` to confirm the narrower (or
   removed) override still passes clean. Irreversibility: low.
4. **Port `test_gitapex_check_skill_shape.py`'s manifest-related tests.**
   Retire tests that only exercised deleted hand-rolled logic (the
   schema-side equivalent already exists in
   `tests/test_gitapex_scan_skill_metadata_schema.py`); keep one smoke
   test per migrated check name. Leave RETAIN-check tests unchanged.
   Irreversibility: medium (test deletion -- justified per-test in the
   commit message, not a blanket removal).
5. **Verification and mandatory dogfooding.** `uv run pytest` (full
   suite, before/after counts), `uv run mypy`, `uv run ruff check`,
   `.github/scripts/gitapex_scan_skill_metadata_schema.py` (no drift),
   live `gitapex_check_skill_shape.py` run against every real
   `skills/*/` directory (zero regressions), then this skill's own
   mandatory isolated self-review (`evaluating-skill-quality` applied to
   its own current state) and `battle-testing-a-skill` adversarial pass,
   per Step 8's aggregate refactor/adversarial-review gate plus this
   skill's own established per-change dogfooding convention.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s
  re-verification marker present on issue #758's body, confirmed via
  `gitapex_check_branch_plan_reverified.py` (PASS).
- Semantic judgment: no OWNER/MEMBER/COLLABORATOR comment exists on issue
  #758 (comment list empty at authorization-gate time). Authorization
  instead rests on explicit human confirmation in the current interactive
  session: the repository owner directly requested this reframe-and-
  implement scope change in this conversation, then approved the
  resulting Branch Plan (`/root/.claude/plans/buzzing-gliding-squirrel.md`,
  covering these same five task groups) via this session's plan-mode
  approval flow before this task list was written. No scope beyond that
  approved plan is introduced here.

## Execution log

- `PlanApproved` -- 2026-08-29T19:xx:xxZ, plan mode exit, branch
  `claude/gitapex-issue-758-impl-031819` already created and design doc
  committed as its first commit.

# Pilot allpairspy pairwise coverage for evaluate/classify_issue

**Goal:** Demonstrate, on a single pilot file, the benefit of pairwise
(2-way) combinatorial test generation over the repository's current
one-factor-at-a-time (OAT) test style, per the requester's own question
about the benefits of parameterized/pairwise testing. Source:
https://github.com/tvna/gitapex/issues/1005.

**File-ownership check (mechanized):**
`echo '{"task-A": ["pyproject.toml", "uv.lock"], "task-B":
["tests/test_gitapex_check_pr_issue_acm_disclosure.py"]}' | python3
skills/executing-a-branch-plan/scripts/gitapex_check_file_ownership_conflicts.py`
-> `no file-ownership conflicts found`.

**Interface-dependency edge:** Task B imports `allpairspy`, which only
exists once Task A's `uv add` lands -- Task B is sequenced after Task A
(wave 2), never co-assigned to Task A's wave.

## Task A -- add `allpairspy` as a declarative dev dependency

**Cites ACM row:** "Pairwise tooling: add `allpairspy` as a new
dependency, managed declaratively" (issue #1005).

**Quoted Planned ops (verbatim from the issue's ACM):** "Add `allpairspy`
to `pyproject.toml`'s `[dependency-groups] dev` list via `uv add --group
dev allpairspy`, letting `uv` update `uv.lock` in the same commit, per
this repo's existing declarative-dependency convention (see the
ruff/radon/xenon/hypothesis pins already in `pyproject.toml`, each with
an inline rationale comment)."

**Files:** `pyproject.toml`, `uv.lock`.

**Steps:**
1. Run `uv add --group dev allpairspy`.
2. Add an inline comment next to the new `allpairspy` entry in
   `pyproject.toml`'s dev group stating its purpose (pairwise pilot for
   issue #1005), matching the file's existing pin-rationale-comment
   convention.
3. Run the CI mypy invocation verbatim (`.github/workflows/test.yml`'s
   "mypy (tests + pythonpath-linked roots)" step): `uv run --frozen mypy
   --config-file pyproject.toml tests hooks .github/scripts evals/scripts
   skills/battle-testing-a-skill/scripts skills/scorer-gated-skill-edits/scripts
   skills/evaluating-skill-quality/scripts
   skills/auditing-agent-product-scope/scripts
   skills/evaluating-deterministic-gate-quality/scripts`. `allpairspy`
   2.5.1 ships no `py.typed` marker (verified against PyPI's JSON API),
   so this will likely raise an import-untyped error the moment Task B's
   `import allpairspy` lands -- check first whether a `types-allpairspy`
   stub package exists on PyPI; if not, add a
   `[[tool.mypy.overrides]]` block (`module = "allpairspy"`,
   `ignore_missing_imports = true`) to `pyproject.toml`, the minimal fix
   for an unstubbed third-party import under this repo's `strict = true`
   config.

**Proof method:** step 3's mypy command exits 0. `uv run --frozen pytest
--collect-only -q` still collects (no import breakage repo-wide).

**Irreversibility:** not irreversible (a dependency addition + config
edit, fully revertable via git).

## Task B -- pairwise-generate `evaluate`/`classify_issue` test coverage

**Cites ACM row:** "Pilot scope: 1 candidate file (within the approved
'1-2 files' range)" (issue #1005).

**Quoted Planned ops (verbatim from the issue's ACM):** "Add
`allpairspy`; replace the OAT-style `test_evaluate_*` /
`test_classify_issue_*` functions with an `allpairspy`-generated
`@pytest.mark.parametrize` table covering all 2-way interactions of the
dimensions above; keep named regression tests that pin a specific past
defect (e.g. `test_evaluate_does_not_bypass_a_same_repo_qualified_resolving_citation`,
issue #657's regression) as separate, explicitly-labeled cases rather
than folding them into the generated table."

**Files:** `tests/test_gitapex_check_pr_issue_acm_disclosure.py`.

**Steps:**
1. In `tests/test_gitapex_check_pr_issue_acm_disclosure.py`, build an
   `allpairspy.AllPairs(...)` combination list over the three independent
   dimensions identified against `hooks/gitapex_check_pr_issue_acm_disclosure.py`'s
   `classify_issue` (lines 308-337) and `evaluate` (lines 340-381):
   citation shape (none / context-only / single-resolving /
   same-repo-qualified-resolving / multi-resolving), token presence
   (present/absent), and per-cited-issue outcome (open+valid-ACM /
   open+non-tracking-waiver / open+tracking-waiver / open+no-disclosure /
   closed / fetch-404 / fetch-500).
2. Feed the generated combinations into `@pytest.mark.parametrize` with
   readable `ids=`, asserting the `(passed, message)` tuple the same way
   the existing individual tests do (reusing their substring assertions:
   `"context-only"`, `"GH_TOKEN"`, `"tracking"`, `"already closed"`,
   `"issue not found"`, `"could not fetch"`).
3. Keep `test_evaluate_does_not_bypass_a_same_repo_qualified_resolving_citation`
   and `test_evaluate_denies_and_aggregates_multiple_failures` as their
   own named functions, unfolded into the generated table (per the
   issue's Constraints: no reduction in existing regression coverage).
4. Skip or normalize any `AllPairs`-generated combination that does not
   correspond to a real code path (e.g. token=absent only matters when a
   resolving citation exists) -- document the skip reason rather than
   forcing a mismatched assertion.

**Proof method:** `uv run --frozen pytest
tests/test_gitapex_check_pr_issue_acm_disclosure.py -v` passes.
`uv run --frozen pytest tests/test_gitapex_check_pr_issue_acm_disclosure.py
--collect-only -q` case count recorded and compared against the
pre-change baseline of 91 tests. Task A's mypy command (step A.3) still
passes with zero errors.

**Irreversibility:** not irreversible.

## Final gate (after both tasks land)

`uv run --frozen pytest --cov-report=xml --cov-report=json` (CI's own
full-suite invocation) passes with no regressions elsewhere in the repo.

## Wave assignment

- **Wave 1:** Task A alone.
- **Wave 2:** Task B alone (interface edge on Task A's `allpairspy`
  import; no other task to co-assign with).

## Execution log

(Populated by the draft PR's own `## Execution log` section as waves
complete; this file is the static task-list input, not the running log.)

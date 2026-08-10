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
3. Confirm no `types-allpairspy` stub package exists on PyPI (a cleaner
   fix than an override, if it did). It does not, so add a
   `[[tool.mypy.overrides]]` block (`module = "allpairspy"`,
   `ignore_missing_imports = true`) to `pyproject.toml` in this same
   task: `allpairspy` 2.5.1's published wheel carries no `py.typed`
   marker and no "Typing :: Typed" PyPI classifier (verified by
   inspecting the wheel's own file listing, not merely its metadata
   classifiers -- the PyPI JSON API's classifier list alone is a
   self-declared field, not authoritative for `py.typed` presence),
   so `strict = true` will otherwise fail on `import allpairspy` the
   moment Task B adds it -- this is deterministic, not something to
   discover by first running mypy against code that does not import the
   package yet.
4. Run the CI mypy invocation verbatim (`.github/workflows/test.yml`'s
   "mypy (tests + pythonpath-linked roots)" step): `uv run --frozen mypy
   --config-file pyproject.toml tests hooks .github/scripts evals/scripts
   skills/battle-testing-a-skill/scripts skills/scorer-gated-skill-edits/scripts
   skills/evaluating-skill-quality/scripts
   skills/auditing-agent-product-scope/scripts
   skills/evaluating-deterministic-gate-quality/scripts`. This step
   only confirms the override doesn't break anything *else* -- since no
   file imports `allpairspy` yet at the end of Task A, the override's
   own effect is not fully exercised until Task B's proof method
   (below) re-runs this exact command after adding `import allpairspy`.

**Proof method:** step 4's mypy command exits 0 at the end of Task A
(pre-import baseline); `uv run --frozen pytest --collect-only -q` still
collects (no import breakage repo-wide). Not a substitute for Task B's
own re-run of the same mypy command once the import exists.

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
   `allpairspy.AllPairs(...)` combination list over two independent
   dimensions identified against `hooks/gitapex_check_pr_issue_acm_disclosure.py`'s
   `classify_issue` (lines 308-337) and `evaluate` (lines 340-381):
   citation shape (none / context-only / single-resolving /
   same-repo-qualified-resolving) and per-cited-issue outcome
   (token-absent / open+valid-ACM / open+non-tracking-waiver /
   open+tracking-waiver / open+no-disclosure / closed / fetch-404 /
   fetch-500). "Multi-resolving" (e.g. `Closes #1, Fixes #2`) is
   deliberately excluded from this generated dimension, not skipped
   post-generation: `evaluate` calls `classify_issue` once per resolving
   number and joins every failure, so a multi-issue case needs its own
   per-issue outcome pair, not one flat "per-cited-issue outcome" value
   -- exactly what the already-kept
   `test_evaluate_denies_and_aggregates_multiple_failures` (step 3 below)
   exists to cover; adding a second, weaker representation of the same
   scenario into the generated table would not add coverage, only
   ambiguity about which cited issue a generated case's outcome value
   applies to.
2. Constrain generation with `AllPairs(..., filter_func=...)` so only
   combinations matching a real code path are ever produced -- e.g. a
   `token-absent` outcome value is only valid when citation shape is one
   of the three resolving shapes (`evaluate` short-circuits on a missing
   token before ever calling `classify_issue`); a non-resolving citation
   shape (none/context-only) is only valid paired with the
   `token-absent` outcome placeholder, since `evaluate` never reaches
   `classify_issue` for those shapes regardless of token. Filtering
   during generation (not discarding rows afterward) is required so the
   pairwise algorithm's own coverage accounting stays accurate: removing
   a generated row after the fact can silently drop the only row that
   carried a required 2-way pair, defeating the coverage guarantee
   pairwise generation exists to provide.
3. Feed the generated combinations into `@pytest.mark.parametrize` with
   readable `ids=`, asserting the `(passed, message)` tuple the same way
   the existing individual tests do (reusing their substring assertions:
   `"context-only"`, `"GH_TOKEN"`, `"tracking"`, `"already closed"`,
   `"issue not found"`, `"could not fetch"`).
4. Keep `test_evaluate_does_not_bypass_a_same_repo_qualified_resolving_citation`
   and `test_evaluate_denies_and_aggregates_multiple_failures` as their
   own named functions, unfolded into the generated table (per the
   issue's Constraints: no reduction in existing regression coverage).

**Proof method:** `uv run --frozen pytest
tests/test_gitapex_check_pr_issue_acm_disclosure.py -v` passes.
`uv run --frozen pytest tests/test_gitapex_check_pr_issue_acm_disclosure.py
--collect-only -q` case count recorded and compared against the
pre-change baseline of 91 tests, pinned to base revision `bf8f4bd`
(this branch's merge-base with `main`) -- reproducible by anyone via
`git checkout bf8f4bd -- tests/test_gitapex_check_pr_issue_acm_disclosure.py
&& uv run --frozen pytest tests/test_gitapex_check_pr_issue_acm_disclosure.py
--collect-only -q`. Task A's mypy command (step A.4) still passes with
zero errors, re-run after this task's `import allpairspy` lands.

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

## Reviewer feedback disposition (CodeRabbit, this PR, pre-implementation pass)

CodeRabbit reviewed this plan file while Task A/B were still blocked
(see the draft PR's `## Execution log`). Each finding checked against
the actual code and this plan, independently -- not applied verbatim:

- **mypy timing / py.typed claim (accepted, fixed above).** Task A's
  mypy step ran before any file imported `allpairspy`, so it never
  actually exercised the override it was meant to add reactively, and
  the "verified against PyPI's JSON API" phrasing overstated what that
  API's classifier metadata alone proves. Fixed: the override is now
  added deterministically in Task A (grounded in an actual wheel
  file-listing check, not classifier metadata), and Task A's proof
  method is explicit that Task B's own mypy re-run is the real
  confirmation once `import allpairspy` exists.
- **`AllPairs(filter_func=...)` over post-hoc skip/normalize (accepted,
  fixed above).** Correct and demonstrated: removing a generated row
  after the fact can silently drop the only row carrying a required
  2-way pair, defeating the coverage guarantee pairwise generation
  exists to provide. Task B step 2 now constrains generation with
  `filter_func` instead.
- **Multi-issue outcome representation (accepted, fixed above).**
  Correct that a single flat "per-cited-issue outcome" dimension cannot
  represent `evaluate`'s per-resolving-number aggregation. Resolved by
  removing "multi-resolving" from the generated dimension entirely
  (rather than adopting the suggested heavier `issue_outcomes` sequence
  model) -- the only multi-resolving scenario this pilot covers was
  already the kept, explicitly-named
  `test_evaluate_denies_and_aggregates_multiple_failures` regression
  test (step 4), so the generated table never needed to represent it.
- **Wire the file-ownership check into a hook/pre-commit/CI job
  (declined, out of scope).** A real improvement in general, but issue
  #1005 scopes this pilot to one test file plus dependency metadata; a
  new standing CI gate is a separate change with its own review surface
  this narrow pilot's ACM never asked for. Left as the one-time,
  human-run check already recorded above, matching this repository's
  own existing `docs/superpowers/plans/*.md` convention (e.g.
  `2026-08-09-gitapex-pr-978-sz9qv5.md`) of documenting a manually-run
  verification rather than building new automation for every plan.
- **Reproducible before/after artifact with full valid/covered pair-set
  diff (declined, out of proportion to a pilot).** The core ask --
  pinning the baseline to a specific revision -- is cheap and adopted
  above (`bf8f4bd`). Building a dedicated valid-pair-set /
  covered-pair-set / set-difference artifact is a heavier-lift
  measurement tool disproportionate to a single-file pilot; the
  generated table's own `ids=` already make its actual 2-way coverage
  inspectable directly from `pytest --collect-only -v` output without a
  separate computed artifact.

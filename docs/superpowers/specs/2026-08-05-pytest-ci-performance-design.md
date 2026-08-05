# pytest CI performance: xdist parallelization + a `slow` marker

Date: 2026-08-05

Refs #770. Design-then-implement doc, per this repo's own plan-first
discipline; the implementing PR carries this same commit.

## Context

CI's `pytest` job wall clock has started to drift upward as the suite has
grown to 2677 tests (`[tool.pytest.ini_options] testpaths` spans `tests/`,
five `skills/*/scripts` directories, and `hooks/`). The job runs as a single
pytest process today (`.github/workflows/test.yml`'s `Run pytest` step:
`uv run --frozen pytest --cov-report=xml --cov-report=json`), with no
parallelization and no custom markers beyond pytest's builtin
`parametrize`/`skipif`.

Measured locally (4 vCPU, matching GitHub's `ubuntu-latest` hosted runner):

- Current invocation, single-process, with the same `--cov-report` flags CI
  passes: **35.3s**.
- The same invocation with `pytest-xdist`'s `-n auto` added: **15.3s** (all
  2677 tests pass; `coverage.json`/`coverage.xml` report the identical
  totals -- 127 lines missed, 99% -- confirming `pytest-cov`'s xdist
  integration combines worker coverage data with no extra config).
- `-n auto` alone accounts for the win; no test needed reordering or
  isolation changes to pass under parallel workers.

The request that opened #770 also asked for "marker-based splitting."
Clarified with the requester during brainstorming: the immediate CI
wall-clock win comes from xdist parallelization alone; markers here target a
fast *local* dev loop (skip subprocess-spawning tests), not a second CI job
matrix. Splitting CI itself into marker-based matrix jobs was explicitly
declined for this change -- it would trade wall clock for added runner
minutes and a coverage-combine step this repo's per-file coverage gate
doesn't need yet, in a suite that will drop under ~15s from xdist alone.

## Decisions

### 1. Parallelize with `pytest-xdist -n auto` in `addopts`, not a CI matrix

Add `pytest-xdist` to `[dependency-groups].dev` and append `-n auto` to
`[tool.pytest.ini_options].addopts`. This benefits both CI and local runs
from one config change, with no new CI job, no matrix, and no coverage
recombination step -- `pytest-cov` already merges per-worker coverage data
automatically when `pytest-xdist` is active, verified empirically (Context
above).

Rejected (for now): actually turning on a GitHub Actions `matrix` split by
marker (e.g. `pytest-split` or a hand-rolled `-m slow` / `-m "not slow"` job
pair). At this suite's size the fixed per-job overhead (checkout, `uv`
install/sync) would eat into or exceed the wall-clock saved versus xdist
alone, and it would require teaching
`.github/scripts/gitapex_gate_evals_scripts_coverage.py` and the Codecov
upload step to combine coverage across jobs instead of reading one
`coverage.json`.

Groundwork only, laid now per the requester's follow-up: `pytest-split`
itself is added as a dev dependency and a committed `.test_durations` file
records real per-test timings, so a future PR that *does* turn on a matrix
split has balanced groups to split on without a first throwaway
data-collection run. See Decision 5.

### 2. `-n auto`, not a pinned worker count

`auto` asks `pytest-xdist` to size the worker pool to the host's detected
CPU count. This tracks whatever `ubuntu-latest` provides without a
hardcoded number going stale if GitHub changes the runner's CPU count, and
matches what was measured in Context (4 workers locally).

### 3. `slow` marker on subprocess-spawning modules, not a duration threshold

Register a `slow` marker in `[tool.pytest.ini_options]` (with
`--strict-markers` added to `addopts` to fail loudly on a typo'd marker
name) and set `pytestmark = pytest.mark.slow` at module level in the three
test files that spawn real subprocesses (git, `uv`, or shell scripts) end
to end:

- `tests/test_gitapex_skill_audit_gate_diff_step_shell.py`
- `hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py`
- `tests/test_gitapex_session_start_hook_shell.py`

Together these are ~44 of 2677 tests. Contributors get a fast loop via
`pytest -m "not slow"`; CI's own invocation is unfiltered (no `-m` flag),
so the full suite -- slow tests included -- still runs and still gates
merges exactly as it does today.

Rejected: marking by measured wall-clock duration (e.g., everything over a
fixed threshold from `--durations`). Individual test timings on this
machine varied by 2-4x between otherwise-identical runs (system jitter,
not algorithmic cost), which would make tests flap between marked and
unmarked on unrelated re-measurement. Grouping by *mechanism* -- does this
test fork/exec a real subprocess -- is deterministic and stable across
runs, and it's exactly the class of test that dominates the wall-clock
tail (Context's measured durations cluster in these three files).

### 4. CI workflow itself is unchanged

`.github/workflows/test.yml`'s `Run pytest` step keeps its existing command
verbatim. Both changes (Decision 1 and 3) live entirely in
`pyproject.toml`'s `[tool.pytest.ini_options]`, so the same invocation
picks up parallelization automatically and continues running the full,
unfiltered suite. No new step, no new job, no new permissions.

### 5. `pytest-split` groundwork: dependency + committed durations file, CI still unchanged

Add `pytest-split` to `[dependency-groups].dev` and commit a `.test_durations`
file (pytest-split's own default path, JSON mapping each test's nodeid to
its last-recorded wall-clock duration) at the repo root, generated via
`uv run --frozen pytest --store-durations`. Verified empirically that
`--store-durations` still records every one of the 2677 tests' individual
durations correctly with `-n auto` active (Decision 1) -- no `-p no:xdist`
workaround needed.

This is groundwork only: `.test_durations` is not read by anything today.
`.github/workflows/test.yml` gains no matrix, no `--splits`/`--group`
flags, no coverage-combine step -- Decision 1's rejection of turning on a
matrix split *now* still stands. What changes is that the day this suite
does grow enough to justify a matrix, that follow-up PR starts from real
timing data instead of first needing its own throwaway
`--store-durations` run, and `pytest-split`'s own default balancing
(largest-first bin-packing across `--splits N`) can produce genuinely
even groups rather than a naive file-count split.

`.test_durations` is committed, not gitignored -- it is meant to be read
by a future workflow change, and a stale-but-present file still balances
groups far better than no data at all (pytest-split falls back to
splitting untimed tests evenly across groups). It will drift as the suite
changes; refreshing it is `uv run --frozen pytest --store-durations`,
documented as a comment at its own point of use once a matrix actually
consumes it -- adding a scheduled refresh workflow now would be scope
beyond "groundwork," per this decision's own request.

## Mechanism

### `pyproject.toml`

- `[dependency-groups].dev`: add `"pytest-xdist>=3.6"` (matches this repo's
  `>=` + no upper-bound convention for dev tooling that isn't already
  pinned for a stated reason, per the neighboring `pytest`/`pytest-cov`
  entries).
- `[tool.pytest.ini_options]`:
  - `addopts`: append ` -n auto --strict-markers` to the existing string.
  - New `markers = ["slow: spawns a real subprocess (git/uv/shell); skip locally with -m \"not slow\" for a fast dev loop"]`.

### Test modules

Add `pytestmark = pytest.mark.slow` near the top of each of the three files
named in Decision 3 (alongside existing imports, matching this repo's
existing module-level `pytestmark` usage pattern where present).

### `.test_durations`

Generated once via `uv run --frozen pytest --store-durations` (Decision 5)
and committed as-is; no code reads it yet.

### Verification

- `uv lock` then `uv run --frozen pytest` (full suite, matching CI's own
  invocation) passes with the same pass count (2677) and the same coverage
  totals as today.
- `uv run --frozen pytest -m "not slow"` passes and collects 2677 minus the
  ~44 newly-marked tests.
- `uv run --frozen python3 .github/scripts/gitapex_gate_evals_scripts_coverage.py --coverage-json coverage.json`
  and the xenon complexity step still pass unchanged against the xdist-
  produced `coverage.json`.
- `.test_durations` contains exactly 2677 entries, one per collected test
  nodeid, each a positive float.

## Non-goals

- Does not split CI into multiple jobs or a matrix (Decision 1) -- Decision
  5 lays groundwork for that future change, it does not turn it on.
- Does not change `.github/workflows/test.yml` (Decision 4).
- Does not mark every test whose duration crosses some threshold -- only
  the subprocess-spawning modules named in Decision 3 (further `slow`
  candidates can be added later by the same mechanism-based rule).
- Does not reduce the job's `timeout-minutes: 10` -- the measured win is
  well within existing headroom and isn't this change's goal.
- Does not add a scheduled workflow to keep `.test_durations` fresh
  (Decision 5) -- out of scope for groundwork; add one alongside whatever
  PR first makes a workflow actually depend on the file.

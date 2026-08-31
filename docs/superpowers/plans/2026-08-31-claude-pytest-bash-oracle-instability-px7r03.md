# Branch Plan: claude/pytest-bash-oracle-instability-px7r03

Source issue: https://github.com/tvna/gitapex/issues/1606

## Task list (1 task, wave 1 -- single-task degenerate case)

### Task 1: Dynamic RLIMIT_NPROC headroom in the real-bash oracle harness

**Owns:**
- `tests/_gitapex_bash_oracle.py`

**File-ownership / interface-dependency edges:** none -- single-task plan,
no sibling task in this wave.

**Source ACM rows (quoted verbatim from issue #1606's re-verified
Acceptance Criteria Map):**

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| The oracle harness's `RLIMIT_NPROC` ceiling no longer collides with ambient, unrelated per-UID process load on the invoking host | Replace the fixed absolute `nproc=64` default with a ceiling computed as "the real UID's own current ambient process count, measured immediately before the child is forked (in the parent, not inside `preexec_fn`), plus a fixed headroom budget" -- the headroom continues to bound how many *additional* processes one oracle invocation's own generated command may fork, which is the property the ceiling exists to enforce. `preexec_fn` itself stays a simple `setrlimit` call with a precomputed integer, consistent with this module's own existing "keep `preexec_fn` minimal" design note. | Add a helper in `tests/_gitapex_bash_oracle.py` that counts processes owned by `os.getuid()` (e.g. via a `/proc` scan) at call time; change `run_bash_oracle()` to pass `ambient_count + headroom` (headroom defaulting to today's `nproc=64` value, i.e. behavior on a quiet host is unchanged) into `_resource_limit_prologue` instead of the bare `nproc` parameter | A new regression test that inflates the real UID's ambient process count via unrelated background processes (mirroring this issue's own sandboxed reproduction) and asserts `run_bash_oracle()` no longer times out under the same load that reproduces the bug on today's code; existing proof-method tests (`test_stand_in_tool_resolves_but_real_system_binary_is_unreachable`, `test_concurrent_invocations_use_isolated_paths`) stay green unmodified | The ambient-count measurement itself has a small window between counting and the actual `setrlimit`/fork where the count could still rise (TOCTOU); mitigated, not eliminated, by a headroom budget -- named explicitly, not silently accepted |
| The resource-limit prologue's original defense-in-depth purpose (bounding a pathological, fork-bomb-shaped *generated* command) is preserved after the fix | The effective ceiling after the fix is still finite (ambient count + headroom, not unbounded), so a generated command that itself tries to fork far beyond the headroom budget is still caught | Keep `_resource_limit_prologue`'s own `RLIMIT_CPU` handling and its existing failure-swallowing behavior (`contextlib.suppress(ValueError, OSError)`) unchanged; only the `nproc` value computation changes | `test_timeout_kills_the_whole_process_group` (the existing fork-bomb-shaped proof-method test) stays green unmodified after the change | Too generous a headroom could let a genuinely pathological generated command through further than before; the proof method above only re-confirms the existing test's own threshold, not a stronger one -- named as accepted, not solved |
| `pytest-bash-oracle-hooks-pins` / `pytest-bash-oracle-task-pins` (and the two `*-differential` jobs) run green across ordinary CI load without requiring a manual re-run | The fix is exercised on the PR's own CI, not only in the sandboxed reproduction | No new CI job needed; the existing 4 `pytest-bash-oracle-*` jobs in `.github/workflows/test.yml` already exercise this code path on every PR | Observe the PR's own CI runs (ideally more than one, across the 4 jobs) passing without a fork-exhaustion-signature failure; a single green run is suggestive, not conclusive, given the bug is load-dependent | CI runner ambient load is itself variable and outside this repository's control; a green run does not prove the fix for all possible ambient-load levels, only that it no longer fails at levels close to what was actually observed -- named, not solved |

**Implementation guidance (this session's own pre-execution investigation,
not part of the quoted ACM rows):**

- Add a module-level helper, e.g. `_ambient_process_count_for_real_uid() -> int`,
  scanning `/proc/*/status` (or `/proc/*` entries via `os.stat` ownership)
  for processes whose real UID matches `os.getuid()`. Keep it a plain
  function in the parent process -- never inside `_resource_limit_prologue`'s
  own `preexec_fn` closure, per the module's existing "keep `preexec_fn`
  minimal" design note (this repository's own diagnosed root cause: the
  fixed `nproc=64` collides with real ambient per-UID load on CI runners).
- `run_bash_oracle()`'s own `nproc: int = 64` parameter becomes the
  headroom budget added on top of the freshly-measured ambient count,
  computed once per call, immediately before `subprocess.Popen` --
  `effective_nproc = _ambient_process_count_for_real_uid() + nproc`,
  passed to `_resource_limit_prologue(cpu_seconds, effective_nproc)`.
  Default `nproc=64` keeps a quiet host's own behavior unchanged (ambient
  count near 0 -> effective ceiling near 64, same as today).
- Do not change `_resource_limit_prologue`'s own signature/body beyond
  what the effective-nproc plumbing requires, and do not touch
  `RLIMIT_CPU` handling, `resolve_bash`, `write_stand_ins`,
  `parse_capture_file`, `run_oracle_in`, `assert_closed_vocabulary`, or
  any existing proof-method test.
- New regression test: mirror this issue's own sandboxed disconfirmation
  -- spawn unrelated background processes (e.g. via `multiprocessing` or
  `subprocess.Popen(["sleep", ...])`) to inflate the current process's
  real UID process count past the harness's headroom, call
  `run_bash_oracle()` with the harness's actual default `nproc=64`, and
  assert `not result.timed_out`. Clean up every spawned process
  (terminate + wait) even on assertion failure -- this is CI-run
  instrumentation, not leftover debug code (must not linger after the
  test, matching CLAUDE.md's own instrumentation-cleanup discipline).
  Guard this test's own resource cost (avoid spawning an unreasonable
  process count in CI) -- a few dozen `sleep` processes is enough to
  demonstrate the ambient-count effect without approaching any real
  system-wide ceiling.

**Wave assignment:** wave 1 (only task).

## Deterministic gates this plan's criteria require

- `uv run --frozen pytest tests/_gitapex_bash_oracle.py -v` (and, once the
  regression test lands, the full `tests/test_gitapex_check_bash_safety_oracle_pins.py`
  / `tests/test_gitapex_check_task_bash_safety_oracle_pins.py` /
  `tests/test_gitapex_check_bash_safety_differential.py` /
  `tests/test_gitapex_check_task_bash_safety_differential.py` suite,
  matching `.github/workflows/test.yml`'s own 4 `pytest-bash-oracle-*`
  jobs)
- `uv run --frozen mypy --config-file pyproject.toml tests hooks .github/scripts evals/scripts ...`
  (the group that includes `tests/`)
- `uv run --frozen xenon --max-absolute E --max-modules B --max-average A ...`
  (cyclomatic-complexity ceiling; the new helper must stay simple)
- CI: `pytest`, `pytest-bash-oracle-hooks-pins`, `pytest-bash-oracle-task-pins`,
  `pytest-bash-oracle-hooks-differential`, `pytest-bash-oracle-task-differential`,
  `mypy` all green on the opened PR

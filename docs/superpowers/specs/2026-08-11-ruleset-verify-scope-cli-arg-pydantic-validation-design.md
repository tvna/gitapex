# CLI-arg pydantic validation for gitapex_compute_ruleset_verify_scope.py: design

Date: 2026-08-11

## Superseded

Implemented (commit df00458), then reverted (commit 180c648) the same day:
`.github/workflows/ruleset-verify.yml`'s "Resolve scan scope and source of
truth" step invokes this script via bare `python3`, with no
dependency-install step at all (no `setup-python`, no `uv sync`/`astral-sh/
setup-uv`, no `pip install`) -- so the module-level `import pydantic` this
design added raised `ModuleNotFoundError` on every real run, live-confirmed
via CI check run 93696199208 and by extracting the script and running it
under the bare system interpreter. This was masked locally because both the
implementer and the task-level review verified only via `uv run pytest`,
which supplies pydantic from the project's managed venv -- not this script's
actual production invocation path. The precedent this design followed
(`evals/scripts/gitapex_run_ablation.py`'s own pydantic CLI-arg wrap) is
itself only ever run via `uv run pytest` (its only reference in any workflow
file is inside `test.yml`'s pytest step); it does not transfer to a script
invoked as a standalone `python3` CI step with no dependency install. The
rest of this document is kept for its rationale, not as a plan to implement
as written -- any revisit must start from that invocation-context constraint
(see the branch's whole-branch review, PR #1031, for the corrected invariant
and options).

**Corrected invariant** (the revert commit's own message overstated this --
whole-branch review finding C2, independently re-verified directly against
every workflow file rather than trusted as stated): it is not true that
every pydantic-importing `.github/scripts/*.py` file is exercised only
through the `uv`-managed pytest suite. `gitapex_sync_pr_publish.py` and
`gitapex_gate_evals_scripts_coverage.py` both import pydantic (`from
pydantic import ...` at module scope) *and* are invoked directly from a
workflow (`sync-agent-instructions.yml:108`, `test.yml:47`) -- safely,
because both call sites use `uv run --frozen python3 ...` in a job that
first runs `astral-sh/setup-uv`, not bare `python3`. The other three
pydantic-importing scripts (`gitapex_gate_ruleset_required_checks.py`,
`gitapex_scan_eval_results_schema.py`, `gitapex_scan_ssot_schema.py`) are
not directly invoked by any workflow at all -- exercised only via `uv run
pytest`. Checked every `python3 .github/scripts/*.py` invocation across
`.github/workflows/*.yml` not preceded by `uv run` (24 call sites, live
`grep` count) against the 5-script pydantic-import list (`grep -l "^from
pydantic import\|^import pydantic"`): zero overlap. The real, generalizable
invariant a future gate should encode is:

> A `.github/scripts/*.py` file invoked from a workflow step whose `run:`
> does not start with `uv run` must import stdlib only.

not "pydantic scripts are pytest-only," which is the weaker, factually
wrong claim the revert commit stated.

Refs #1024 (the PR #1031 fix). Small, scoped follow-up requested directly
after that PR: add pydantic validation to
`.github/scripts/gitapex_compute_ruleset_verify_scope.py`, following this
repo's own established "argparse-wraps-pydantic CLI-arg wrap" convention
(issue #684, tasks T6/T7/T8 -- see `evals/scripts/gitapex_run_ablation.py`'s
`_RunAblationArgs` for the precedent this design follows).

## Context

`main()` currently builds its `argparse.ArgumentParser`, calls
`parser.parse_args(argv)`, and passes the raw `Path` values straight into
`compute_scope()` with no validation at all -- unlike the T6/T7/T8
precedent scripts, which had pre-existing hand-rolled checks this pattern
formalized, this script has no CLI-shape validation of any kind today.
Passing a nonexistent `--repo-root` or `--runner-temp` currently fails
deep inside a `git` subprocess call or a `Path.write_text()` call, with a
message that does not point back to the CLI flag that caused it.

## Decision: validate `repo_root` and the resolved `runner_temp` only

Add a `_ComputeRulesetVerifyScopeArgs` pydantic `BaseModel`, instantiated
in `main()` immediately after `parser.parse_args()` (and after
`runner_temp`'s existing `$RUNNER_TEMP`-env/cwd fallback resolution, so
the same validator covers both an explicit bad `--runner-temp` flag and a
bad `$RUNNER_TEMP` environment value):

- `repo_root: Path` -- field validator requires `value.is_dir()`, raising
  `--repo-root does not exist or is not a directory: <value>`.
- `runner_temp: Path` -- field validator requires `value.is_dir()`,
  raising `--runner-temp does not exist or is not a directory: <value>`.

On `pydantic.ValidationError`, `main()` prints `error: <message>` to
stderr (unwrapped via the same `_validation_error_message`-style helper
`gitapex_run_ablation.py` uses) and returns exit code **`1`**, matching
the existing `RulesetVerifyScopeError` path -- NOT exit code `2`, despite
`gitapex_run_ablation.py`'s own precedent using `2` for this same kind of
CLI-validation failure. Adversarial re-read of this design against the
surrounding workflow caught why the precedent does not transfer here:
`.github/workflows/ruleset-verify.yml`'s own "Compare the live ruleset..."
step (the sibling script `gitapex_scan_ruleset_drift.py`) already
establishes, in that workflow file's own comment, that exit code `2`
specifically means "the scan never got to look... a warning rather than
a failure" within *this* workflow. Reusing `2` for "bad CLI input" in the
sibling step this design touches would collide with that established,
documented meaning even though the two scripts are otherwise independent
-- a reader grepping this workflow file for "exit 2" would find two
contradictory meanings. Exit code `1` carries no such conflicting meaning
here and already matches this file's own `RulesetVerifyScopeError` exit
path, so both of `main()`'s error paths return the same code; only the
stderr message format differs (plain `error: ...` for a CLI-shape
problem vs. `::error::...` for a resolved-but-unsatisfiable git state).

### Rejected: also validating `event_name` / `base_sha` here

`compute_scope()` already owns `base_sha`'s conditional-required check
(`--base-sha is required ... for a pull_request event`) and the
base-commit/path-existence checks, each covered by its own direct unit
test (20+ tests call `compute_scope()` directly, not through `main()`).
Moving that check into the CLI-layer pydantic model would either
duplicate it (two competing validators for the same condition, the
precedent's own stated anti-pattern) or remove it from `compute_scope()`
and break its existing standalone-callable contract and tests. Per this
repo's defense-in-depth principle, `compute_scope()` keeps this check as
its own layer; the new CLI model only covers the two checks that
currently have *no* validation anywhere.

### Rejected: also validating `step_summary_file`

Opened via `.open("a", encoding="utf-8")`, which creates the file if
absent -- no existence precondition on the file itself to validate. Out
of scope (YAGNI) for this change. Known, disclosed limitation left
un-hardened: a `step_summary_file` whose *parent directory* is missing
still raises an uncaught `FileNotFoundError` from that `.open()` call,
with no clear message pointing back to `--step-summary-file` or
`$GITHUB_STEP_SUMMARY`. Not fixed here because it is not the gap this
change was requested for, and in the one production caller
(`ruleset-verify.yml`) the parent directory is always the GitHub
Actions-provided runner temp directory, which always exists -- the gap is
real only for local/manual invocation with a hand-supplied path. Revisit
if that changes.

## Testing

- Two new unit tests: `main()` invoked with a nonexistent `--repo-root`,
  and with a nonexistent explicit `--runner-temp`, each asserting exit
  code `1` and the expected `error: ...` message on stderr.
- Existing `compute_scope()`-level tests are unaffected (that function's
  own signature and behavior do not change).
- Full `uv run pytest` suite, `ruff check`, `ruff format --check`, `mypy`
  must all still pass.

## Rollout

Lands as a follow-up commit on the same branch/PR (`claude/gitapex-pr-1024-ynm562`,
PR #1031) rather than a new issue/branch, since it is a small, directly
related strengthening of the file that PR already touches.

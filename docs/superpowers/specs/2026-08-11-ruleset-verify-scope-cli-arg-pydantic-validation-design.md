# CLI-arg pydantic validation for gitapex_compute_ruleset_verify_scope.py: design

Date: 2026-08-11

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

- `repo_root: Path` -- field validator requires `value.is_dir()`.
- `runner_temp: Path` -- field validator requires `value.is_dir()`.

On `pydantic.ValidationError`, `main()` prints `error: <message>` to
stderr (unwrapped via the same `_validation_error_message`-style helper
`gitapex_run_ablation.py` uses) and returns exit code `2` -- distinct from
the existing `RulesetVerifyScopeError` path's exit code `1` with an
`::error::`-prefixed message, so a CI log can tell "bad CLI input" apart
from "the requested git state could not be resolved."

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
absent -- no existence precondition to validate. Out of scope (YAGNI);
revisit only if a concrete gap surfaces (e.g. a missing parent directory).

## Testing

- Two new unit tests: `main()` invoked with a nonexistent `--repo-root`,
  and with a nonexistent explicit `--runner-temp`, each asserting exit
  code `2` and the expected `error: ...` message on stderr.
- Existing `compute_scope()`-level tests are unaffected (that function's
  own signature and behavior do not change).
- Full `uv run pytest` suite, `ruff check`, `ruff format --check`, `mypy`
  must all still pass.

## Rollout

Lands as a follow-up commit on the same branch/PR (`claude/gitapex-pr-1024-ynm562`,
PR #1031) rather than a new issue/branch, since it is a small, directly
related strengthening of the file that PR already touches.

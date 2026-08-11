# Ruleset-Verify-Scope CLI-Arg Pydantic Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate `--repo-root` and the resolved `--runner-temp` in `.github/scripts/gitapex_compute_ruleset_verify_scope.py`'s `main()` via a pydantic model immediately after `parser.parse_args()`, so a nonexistent path fails with a clear, flag-naming message instead of a confusing error deep inside a `git` subprocess call or a file write.

**Architecture:** Add one small pydantic `BaseModel` (`_ComputeRulesetVerifyScopeArgs`) with two `field_validator`s, instantiated in `main()` right after CLI parsing and after `runner_temp`'s existing `$RUNNER_TEMP`/cwd fallback resolution. On `pydantic.ValidationError`, print `error: <message>` to stderr and return exit code `1` (same exit code as the file's existing `RulesetVerifyScopeError` path, kept distinct in message *format* only -- see the design doc for why exit code `2` was rejected). `compute_scope()`'s own signature, tests, and internal `--base-sha`/base-commit validation are untouched.

**Tech Stack:** Python 3, `pydantic>=2.9` (already a project dependency), `argparse`, `pytest` (`uv run pytest`).

## Global Constraints

- Design doc (already approved and committed): `docs/superpowers/specs/2026-08-11-ruleset-verify-scope-cli-arg-pydantic-validation-design.md`.
- Exit code for the new validation-error path is **`1`**, not `2` -- exit code `2` already means "no live ruleset yet, a warning not a failure" elsewhere in `.github/workflows/ruleset-verify.yml`, and reusing it here would collide with that established meaning.
- Do **not** add validation for `--event-name`, `--base-sha`, or `--step-summary-file` -- explicitly out of scope per the design doc's "Rejected" sections.
- Do **not** change `compute_scope()`'s signature or remove any of its existing internal checks (`--base-sha` required, `_commit_exists`, `_path_exists_at_commit`) -- those stay as `compute_scope()`'s own layer, covered by its own existing direct unit tests.
- Follow this repo's TDD discipline: write the failing test(s) first, confirm they fail for the right reason, then implement.
- After implementation: `uv run pytest` (full suite), `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` must all pass with zero regressions.
- This is a follow-up commit on the existing branch `claude/gitapex-pr-1024-ynm562` (PR #1031, issue #1024) -- not a new branch or PR.

---

### Task 1: Add `_ComputeRulesetVerifyScopeArgs` pydantic model and wire it into `main()`

**Files:**
- Modify: `.github/scripts/gitapex_compute_ruleset_verify_scope.py:46-52` (imports), `:152-198` (`main()`)
- Test: `tests/test_gitapex_compute_ruleset_verify_scope.py` (append new tests after the existing `main()` test block, which currently ends at line 352)

**Interfaces:**
- Consumes: `compute_scope(event_name, base_sha, repo_root, runner_temp, step_summary_file) -> dict[str, str]` (existing, unchanged signature, `.github/scripts/gitapex_compute_ruleset_verify_scope.py:111-117`).
- Produces: `_ComputeRulesetVerifyScopeArgs` (new pydantic `BaseModel`, fields `repo_root: pathlib.Path`, `runner_temp: pathlib.Path`) and `_validation_error_message(exc: pydantic.ValidationError) -> str` (new private helper). Neither is imported by any other file -- both are private to this script, matching this repo's existing per-script-duplicated-helper convention (e.g. `_git` is duplicated across scripts rather than shared).

- [ ] **Step 1: Write the failing test for a nonexistent `--repo-root`**

Open `tests/test_gitapex_compute_ruleset_verify_scope.py` and add this test immediately after `test_main_explicit_runner_temp_flag_overrides_the_environment` (the last test in the file, ending at line 352):

```python


def test_main_returns_one_for_a_nonexistent_repo_root(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # New CLI-shape validation (issue #1024 follow-up): --repo-root must
    # exist. Fires unconditionally in main(), before compute_scope() is
    # even reached, regardless of --event-name.
    nonexistent = tmp_path / "does-not-exist"
    rc = scope_module.main(["--event-name", "schedule", "--repo-root", str(nonexistent)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == f"error: --repo-root does not exist or is not a directory: {nonexistent}"
    assert "::error::" not in captured.err


def test_main_returns_one_for_a_nonexistent_explicit_runner_temp(
    repo: pathlib.Path, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Same new validation, applied to the *resolved* --runner-temp (after
    # its own $RUNNER_TEMP-env/cwd fallback) -- covers an explicit bad
    # --runner-temp flag here; a bad $RUNNER_TEMP env value is the same
    # code path, not separately tested.
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    nonexistent = tmp_path / "does-not-exist"
    rc = scope_module.main(
        [
            "--event-name",
            "pull_request",
            "--base-sha",
            base_sha,
            "--repo-root",
            str(repo),
            "--runner-temp",
            str(nonexistent),
        ]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == f"error: --runner-temp does not exist or is not a directory: {nonexistent}"
    assert "::error::" not in captured.err
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_gitapex_compute_ruleset_verify_scope.py -k "nonexistent_repo_root or nonexistent_explicit_runner_temp" -v --no-cov`

Expected: Both `FAIL`. The first fails because `main()` currently runs `compute_scope()` unconditionally for a non-`pull_request` event without ever touching `repo_root`, so it returns `0` with normal output, not `1` with the expected stderr message (assertion `rc == 1` fails). The second fails because `main()` currently only fails once `_show_at_commit`/`sot_file.write_text()` raises deep inside `compute_scope()`, producing a different (or no) stderr message than the expected `error: --runner-temp does not exist or is not a directory: ...` text.

- [ ] **Step 3: Add the pydantic import**

In `.github/scripts/gitapex_compute_ruleset_verify_scope.py`, change the import block at lines 46-52 from:

```python
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

MAIN_RULESET_PATH = ".github/rulesets/main.json"
```

to:

```python
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

from pydantic import BaseModel, ValidationError, field_validator

MAIN_RULESET_PATH = ".github/rulesets/main.json"
```

- [ ] **Step 4: Add `_ComputeRulesetVerifyScopeArgs` and `_validation_error_message`**

Insert this new class and helper function immediately before `def main(` (currently at line 152), i.e. right after `_render`'s closing line (currently line 149, blank line 150-151):

```python
class _ComputeRulesetVerifyScopeArgs(BaseModel):
    """Validates the two `main()` CLI values that previously had no
    validation at all: `--repo-root` and the resolved `--runner-temp`
    (after its own $RUNNER_TEMP-env/cwd fallback) must each be an
    existing directory. `--event-name`/`--base-sha` are deliberately not
    modeled here: `compute_scope()` already owns their own validation,
    covered by that function's own direct unit tests -- duplicating it
    here would either compete with that check or remove it from a
    function this file's own tests call directly (see issue #1024's
    follow-up design doc,
    docs/superpowers/specs/2026-08-11-ruleset-verify-scope-cli-arg-pydantic-validation-design.md).
    `--step-summary-file` is also not modeled: opened via `.open("a")`,
    which creates the file if absent, so it carries no existence
    precondition (a missing *parent* directory is a known, disclosed,
    out-of-scope limitation -- see that same design doc)."""

    repo_root: pathlib.Path
    runner_temp: pathlib.Path

    @field_validator("repo_root")
    @classmethod
    def _repo_root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--repo-root does not exist or is not a directory: {value}")
        return value

    @field_validator("runner_temp")
    @classmethod
    def _runner_temp_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--runner-temp does not exist or is not a directory: {value}")
        return value


def _validation_error_message(exc: ValidationError) -> str:
    """The first error's original message, unwrapped from pydantic's own
    "Value error, " prefix -- same helper shape as
    evals/scripts/gitapex_run_ablation.py's own `_validation_error_message`,
    duplicated rather than imported (this file has no dependency on that
    unrelated CLI script)."""
    error = exc.errors()[0]
    ctx = error.get("ctx") or {}
    original = ctx.get("error")
    if isinstance(original, Exception):
        return str(original)
    return str(error["msg"])


```

- [ ] **Step 5: Wire the model into `main()`**

In `.github/scripts/gitapex_compute_ruleset_verify_scope.py`, change `main()`'s body (currently lines 184-195) from:

```python
    runner_temp = args.runner_temp
    if runner_temp is None:
        runner_temp = pathlib.Path(os.environ.get("RUNNER_TEMP", "."))
    step_summary_file = args.step_summary_file
    if step_summary_file is None and os.environ.get("GITHUB_STEP_SUMMARY"):
        step_summary_file = pathlib.Path(os.environ["GITHUB_STEP_SUMMARY"])

    try:
        outputs = compute_scope(args.event_name, args.base_sha, args.repo_root, runner_temp, step_summary_file)
    except RulesetVerifyScopeError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
```

to:

```python
    runner_temp = args.runner_temp
    if runner_temp is None:
        runner_temp = pathlib.Path(os.environ.get("RUNNER_TEMP", "."))
    step_summary_file = args.step_summary_file
    if step_summary_file is None and os.environ.get("GITHUB_STEP_SUMMARY"):
        step_summary_file = pathlib.Path(os.environ["GITHUB_STEP_SUMMARY"])

    try:
        validated_args = _ComputeRulesetVerifyScopeArgs(repo_root=args.repo_root, runner_temp=runner_temp)
    except ValidationError as exc:
        print(f"error: {_validation_error_message(exc)}", file=sys.stderr)
        return 1

    try:
        outputs = compute_scope(
            args.event_name, args.base_sha, validated_args.repo_root, validated_args.runner_temp, step_summary_file
        )
    except RulesetVerifyScopeError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_gitapex_compute_ruleset_verify_scope.py -k "nonexistent_repo_root or nonexistent_explicit_runner_temp" -v --no-cov`

Expected: Both `PASS`.

- [ ] **Step 7: Run the full test file to check for regressions**

Run: `uv run pytest tests/test_gitapex_compute_ruleset_verify_scope.py -v --no-cov`

Expected: All tests `PASS` (23 existing + 2 new = 25 total). In particular confirm `test_main_defaults_runner_temp_from_environment`, `test_main_defaults_step_summary_file_from_environment`, and `test_main_explicit_runner_temp_flag_overrides_the_environment` still pass unchanged -- they exercise the happy path through the new validation and must not be affected by it.

- [ ] **Step 8: Run the full project test suite and linters**

Run:
```bash
uv run pytest --no-cov -q
uv run ruff check .github/scripts/gitapex_compute_ruleset_verify_scope.py tests/test_gitapex_compute_ruleset_verify_scope.py
uv run ruff format --check .github/scripts/gitapex_compute_ruleset_verify_scope.py tests/test_gitapex_compute_ruleset_verify_scope.py
uv run mypy .github/scripts/gitapex_compute_ruleset_verify_scope.py
```

Expected: `pytest` reports all tests passing (4133 existing + 2 new, no `--no-cov` regressions elsewhere); `ruff check` and `ruff format --check` report no issues; `mypy` reports `Success: no issues found in 1 source file`.

- [ ] **Step 9: Commit**

```bash
git add .github/scripts/gitapex_compute_ruleset_verify_scope.py tests/test_gitapex_compute_ruleset_verify_scope.py
git commit -m "$(cat <<'EOF'
Add pydantic CLI-arg validation for --repo-root/--runner-temp (#1024)

Implements docs/superpowers/specs/2026-08-11-ruleset-verify-scope-
cli-arg-pydantic-validation-design.md: main() previously passed
--repo-root and the resolved --runner-temp straight into
compute_scope() with no validation, so a nonexistent path failed
deep inside a git subprocess call or a file write with no message
pointing back to the CLI flag. Add a
_ComputeRulesetVerifyScopeArgs pydantic model (matching this repo's
existing argparse-wraps-pydantic CLI-arg convention, issue #684
T6/T7/T8) validating both are existing directories, following
evals/scripts/gitapex_run_ablation.py's own
_validation_error_message helper shape. Exit code 1 on failure,
matching the file's existing RulesetVerifyScopeError path (not exit
code 2 -- see the design doc for why that code was rejected).
compute_scope()'s own signature and internal validation are
unchanged.
EOF
)"
```

- [ ] **Step 10: Push**

```bash
git push -u origin claude/gitapex-pr-1024-ynm562
```

Expected: Push succeeds; PR #1031's CI re-runs (`pytest`, `ruff`, `mypy`, `skill-audit-disclosure`, etc.) against the new commit.

"""Regression suite for gitapex_check_task_full_verification.py and its
check_task_full_verification.sh wrapper (issue #1476, retro #1475 repair
2): a `branch-plan-task` dispatch must run the full repo verification
suite as an exit condition before it is allowed to report complete.

Two layers, mirroring test_gitapex_gate_local_preflight.py's own split:

- **Fixture-step tests** call `run_verification`/`main` with small,
  fast, controllable commands (`python3 -c "...; sys.exit(N)"`) standing
  in for a real pytest/local-preflight run -- exercising the decision
  logic (deny-on-first-failure, allow-when-clean, reason formatting) in
  well under a second, with no dependence on this repository's real,
  multi-minute verification suite. `test_deny_when_pytest_fails...` is
  this file's own direct regression pin for the issue's proof method: a
  failing step must now deny, where before this gate existed nothing
  would have denied it at all.
- **Real-command tests** assert `DEFAULT_STEPS` pins the exact
  pytest/local-preflight commands issue #1476's own proof method names,
  without ever running them (the same "assert the wiring, never execute
  the real heavy thing" split gitapex_gate_local_preflight.py's own test
  suite already uses for its 42 real wired gates).
- **Wrapper-level tests** invoke the shipped `check_task_full_verification.sh`
  via subprocess with the real SubagentStop JSON shape, for the cheap
  defensive paths only (event-name gating, malformed input) -- mirroring
  test_gitapex_check_task_bash_safety.py's own subprocess-invocation style
  for its sibling hook.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import gitapex_check_task_full_verification as under_test
import pytest

SCRIPT = pathlib.Path(__file__).parent / "check_task_full_verification.sh"
CLASSIFIER = pathlib.Path(__file__).parent / "gitapex_check_task_full_verification.py"


def _step(label: str, exit_code: int, output: str = "") -> under_test.VerificationStep:
    code = f"import sys; sys.stdout.write({output!r}); sys.exit({exit_code})"
    return under_test.VerificationStep(label, ("python3", "-c", code))


# --------------------------------------------------------------------------
# run_verification: decision logic
# --------------------------------------------------------------------------


def test_allow_when_every_step_passes(tmp_path: pathlib.Path) -> None:
    steps = (_step("pytest", 0), _step("local-preflight", 0))
    assert under_test.run_verification(steps, tmp_path) == {"decision": "allow"}


def test_deny_when_pytest_fails_reintroducing_the_original_defect(tmp_path: pathlib.Path) -> None:
    """Direct regression pin for issue #1476's own proof method: retro
    #1475 repair 2's own stale-schema-assertion and shape-check-regression
    defects both surface as a nonzero pytest exit inside the task's own
    worktree. Before this gate existed, a task dispatch had no exit
    condition that would ever deny on this -- confirm it now does."""
    steps = (_step("pytest", 1, "1 failed, 42 passed"), _step("local-preflight", 0))
    result = under_test.run_verification(steps, tmp_path)
    reason = str(result["reason"])
    assert result["decision"] == "deny"
    assert "pytest" in reason
    assert "1 failed" in reason


def test_deny_when_local_preflight_fails_after_pytest_passes(tmp_path: pathlib.Path) -> None:
    steps = (_step("pytest", 0), _step("local-preflight", 1, "FAIL some-gate"))
    result = under_test.run_verification(steps, tmp_path)
    reason = str(result["reason"])
    assert result["decision"] == "deny"
    assert "local-preflight" in reason
    assert "FAIL some-gate" in reason


def test_stops_at_first_failure_never_runs_the_next_step(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    original = under_test.run_step

    def spy(step: under_test.VerificationStep, cwd: pathlib.Path, timeout: int) -> under_test.StepResult:
        calls.append(step.label)
        return original(step, cwd, timeout)

    monkeypatch.setattr(under_test, "run_step", spy)
    steps = (_step("pytest", 1), _step("local-preflight", 0))
    under_test.run_verification(steps, tmp_path)
    assert calls == ["pytest"]


def test_run_step_reports_failure_when_command_does_not_exist(tmp_path: pathlib.Path) -> None:
    step = under_test.VerificationStep("missing", ("gitapex-command-that-does-not-exist",))
    result = under_test.run_step(step, tmp_path, timeout=5)
    assert result.passed is False
    assert "failed to run" in result.output


# --------------------------------------------------------------------------
# _resolve_cwd
# --------------------------------------------------------------------------


def test_resolve_cwd_prefers_payload_cwd_when_it_is_a_real_directory(tmp_path: pathlib.Path) -> None:
    assert under_test._resolve_cwd({"cwd": str(tmp_path)}) == tmp_path


def test_resolve_cwd_falls_back_to_process_cwd_when_payload_cwd_missing() -> None:
    assert under_test._resolve_cwd({}) == pathlib.Path.cwd()


def test_resolve_cwd_falls_back_when_payload_cwd_is_not_a_directory(tmp_path: pathlib.Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert under_test._resolve_cwd({"cwd": str(missing)}) == pathlib.Path.cwd()


def test_resolve_cwd_falls_back_when_payload_cwd_is_not_a_string() -> None:
    assert under_test._resolve_cwd({"cwd": 12345}) == pathlib.Path.cwd()


# --------------------------------------------------------------------------
# _steps_from_json
# --------------------------------------------------------------------------


def test_steps_from_json_round_trips_a_valid_payload() -> None:
    raw = json.dumps([["a", ["true"]], ["b", ["false", "-x"]]])
    steps = under_test._steps_from_json(raw)
    assert steps == (
        under_test.VerificationStep("a", ("true",)),
        under_test.VerificationStep("b", ("false", "-x")),
    )


def test_steps_from_json_rejects_malformed_input() -> None:
    for bad in ["not json", "{}", "[]", '[[1, ["true"]]]', '[["a", []]]', '[["a", [1]]]', '[["a"]]']:
        assert under_test._steps_from_json(bad) is None


# --------------------------------------------------------------------------
# main(): CLI entry point, via subprocess (real stdin handling)
# --------------------------------------------------------------------------


def _run_main(payload: dict[str, object], *, steps_json: str | None = None) -> dict[str, str]:
    argv = [sys.executable, str(CLASSIFIER)]
    if steps_json is not None:
        argv += ["--steps-json", steps_json]
    result = subprocess.run(
        argv,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"classifier exited {result.returncode}: {result.stderr}"
    decoded: dict[str, str] = json.loads(result.stdout)
    return decoded


def test_main_allows_when_steps_json_override_all_pass(tmp_path: pathlib.Path) -> None:
    steps_json = json.dumps([["fast-pass", ["true"]]])
    result = _run_main({"cwd": str(tmp_path)}, steps_json=steps_json)
    assert result == {"decision": "allow"}


def test_main_denies_when_steps_json_override_fails(tmp_path: pathlib.Path) -> None:
    steps_json = json.dumps([["fast-fail", ["false"]]])
    result = _run_main({"cwd": str(tmp_path)}, steps_json=steps_json)
    assert result["decision"] == "deny"
    assert "fast-fail" in result["reason"]


def test_main_denies_on_malformed_stdin() -> None:
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input="not json",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "deny"


def test_main_denies_on_non_object_stdin() -> None:
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input="[1, 2, 3]",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "deny"


def test_main_denies_on_malformed_steps_json(tmp_path: pathlib.Path) -> None:
    result = _run_main({"cwd": str(tmp_path)}, steps_json="not json")
    assert result["decision"] == "deny"


# --------------------------------------------------------------------------
# DEFAULT_STEPS: pin the real production commands (never executed here)
# --------------------------------------------------------------------------


def test_default_steps_pin_the_real_production_commands() -> None:
    """A future edit that silently drops --no-cov, the ignore list, or the
    local-preflight call entirely must fail this test, not go unnoticed --
    the same wiring-pin discipline gitapex_gate_local_preflight.py's own
    test suite already applies to its 42 real wired gates."""
    assert (
        under_test.VerificationStep(
            "pytest",
            (
                "uv",
                "run",
                "--frozen",
                "python3",
                "-m",
                "pytest",
                "--no-cov",
                "-q",
                "--ignore=tests/test_gitapex_check_bash_safety_oracle_pins.py",
                "--ignore=tests/test_gitapex_check_task_bash_safety_oracle_pins.py",
                "--ignore=tests/test_gitapex_check_bash_safety_differential.py",
                "--ignore=tests/test_gitapex_check_task_bash_safety_differential.py",
            ),
        ),
        under_test.VerificationStep(
            "local-preflight",
            ("uv", "run", "--frozen", "python3", ".github/scripts/gitapex_gate_local_preflight.py"),
        ),
    ) == under_test.DEFAULT_STEPS


# --------------------------------------------------------------------------
# check_task_full_verification.sh: wrapper-level defensive paths
# --------------------------------------------------------------------------


def _run_sh(payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_sh_allows_and_does_nothing_for_a_non_subagent_stop_event() -> None:
    result = _run_sh({"hook_event_name": "PreToolUse"})
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_sh_denies_on_malformed_json_payload() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not json",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["decision"] == "block"
    assert payload["hookSpecificOutput"]["hookEventName"] == "SubagentStop"
    assert payload["hookSpecificOutput"]["reason"]


def test_sh_denies_on_non_object_json_payload() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="[1, 2, 3]",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2


def test_sh_denies_when_hook_event_name_is_not_a_string() -> None:
    result = _run_sh({"hook_event_name": 12345})
    assert result.returncode == 2


def test_sh_runs_the_real_classifier_end_to_end_and_allows_on_a_clean_worktree(tmp_path: pathlib.Path) -> None:
    """The one genuinely end-to-end path through the real classifier with
    no override: point `cwd` at an empty scratch directory and confirm
    the wrapper reaches the classifier and returns a well-formed decision
    (deny, since neither `uv` nor a pytest/preflight setup exists there --
    proving the plumbing runs the real gitapex_check_task_full_verification.py,
    not that an empty directory passes verification)."""
    result = _run_sh({"hook_event_name": "SubagentStop", "cwd": str(tmp_path)})
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    reason = payload["hookSpecificOutput"]["reason"]
    assert "issue #1476" in reason

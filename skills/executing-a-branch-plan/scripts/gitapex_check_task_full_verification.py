"""Classifier backing check_task_full_verification.sh (issue #1476).

Retro #1475 repair 2: a `branch-plan-task` dispatch verified only what it
judged relevant to its own file-ownership scope, so a pre-existing test
asserting against a schema one task's own rewrite removed, and a
script-execution-intent-stated shape-check regression, both surfaced only
later -- in the main thread's own merge-back screening after the wave had
already reported complete -- rather than inside the task's own dispatch
that actually caused them. Design doc Decision 20
(docs/superpowers/specs/2026-07-22-plan-execution-handoff-design.md):
require each task-level dispatch to run the full repo verification suite
(pytest plus every deterministic shape/gate checker) inside its own
isolated worktree as an exit condition before it is allowed to report
complete.

Self-contained duplicate, not a shared import: this repository's
convention (see check_task_bash_safety.sh's own header, and
skills/drafting-issues/scripts/gitapex_check_acm_present.py's docstring)
is that no skill shares a scripts/ directory with another.

Two commands, run in order from the task's own worktree root, matching
issue #1476's own proof method verbatim:

  1. ``uv run --frozen python3 -m pytest --no-cov -q`` -- with the same
     four real-bash-oracle test files excluded that
     ``.github/workflows/test.yml``'s own ``pytest`` job already excludes
     (issue #1365): each spawns genuine ``bash -c`` subprocesses under
     this runner's own harden-runner eBPF tracer and has caused resource-
     exhaustion flakes and, once, a full job hang there. That job already
     runs them in 4 separate, isolated jobs instead; paying that same
     heavy cost again inside every task-level worktree dispatch (and
     potentially several of them concurrently, once per parallel wave)
     would multiply exactly the contention CI's own job split exists to
     avoid, for files this gate's own motivating defect never involved.
     This is a deliberate, disclosed deviation from the issue's own
     literal proof-method text, not an oversight -- see
     references/threat-model-and-authorization.md for the same
     Decision-deviation discipline applied elsewhere in this skill.
  2. ``uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py``
     -- the existing consolidated runner for every deterministic gate that
     carries a working-tree-only form (issue #876); this already *is* "every
     deterministic shape/gate checker" the issue's own proof method names,
     not a new enumeration invented here.

Stops at the first failing step (no reason to pay for local-preflight's own
run once pytest has already failed) and returns
``{"decision": "deny", "reason": "..."}`` naming which step failed and its
captured output, or ``{"decision": "allow"}`` once every step passes.
Always exits 0 -- the real decision travels in the JSON printed to stdout,
never in this process's own exit code; ``check_task_full_verification.sh``
is what turns a "deny" into the actual SubagentStop block (exit 2), the
same division of labor gitapex_check_task_bash_safety.py already
establishes for its own sibling hook.

Known, disclosed limitation, not solved here: a genuinely persistent
failure (an unrelated pre-existing repo-wide break, or an environment
issue such as `uv` missing from PATH) denies every stop attempt with no
built-in bound on how many times the subagent may retry before a human
notices -- this gate does not implement a retry ceiling or circuit
breaker of its own. `drafting-a-pr-to-merge`'s own Step 10 freshness/hang
check (see
skills/executing-a-branch-plan/references/domain-events-and-failure-handling.md#freshness-and-hang-detection)
is the existing backstop for a wave that never returns for this reason,
named here rather than assumed away.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Matches .github/workflows/test.yml's own "pytest" job --ignore list
# (issue #1365) -- see this module's own docstring for why.
_IGNORED_ORACLE_TESTS = (
    "tests/test_gitapex_check_bash_safety_oracle_pins.py",
    "tests/test_gitapex_check_task_bash_safety_oracle_pins.py",
    "tests/test_gitapex_check_bash_safety_differential.py",
    "tests/test_gitapex_check_task_bash_safety_differential.py",
)

DEFAULT_PYTEST_ARGV: tuple[str, ...] = (
    "uv",
    "run",
    "--frozen",
    "python3",
    "-m",
    "pytest",
    "--no-cov",
    "-q",
    *(f"--ignore={path}" for path in _IGNORED_ORACLE_TESTS),
)

# The existing consolidated runner for every deterministic gate carrying
# a working-tree-only form (issue #876) -- already "every deterministic
# shape/gate checker" the issue's own proof method names.
DEFAULT_PREFLIGHT_ARGV: tuple[str, ...] = (
    "uv",
    "run",
    "--frozen",
    "python3",
    ".github/scripts/gitapex_gate_local_preflight.py",
)

# Matches gitapex_gate_local_preflight.py's own DEFAULT_TIMEOUT_SECONDS and
# its rationale: a hang guard, not a budget -- a cold mypy cache (run inside
# the local-preflight step) can legitimately take longer than a warm-run
# measurement would suggest. Applied PER STEP to two sequential steps
# (pytest, then local-preflight) -- .claude/agents/branch-plan-task.md's
# own SubagentStop hook `timeout` (the OUTER Claude Code hook-process
# ceiling, a materially different thing from this per-subprocess value)
# must stay comfortably above 2x this number, or a legitimately slow
# (not failing) run can hit Claude Code's own hook timeout first, which
# discards this classifier's output entirely and silently fails OPEN
# (SubagentStop is not one of the two documented exceptions -- only
# PreModelSwitch, and Agent-SDK PreToolUse callbacks -- that still block
# on a timeout) rather than denying. Keep the two values in sync if
# either changes.
DEFAULT_TIMEOUT_SECONDS = 1800


@dataclass(frozen=True)
class VerificationStep:
    """One command to run, in order, from the task's own worktree root."""

    label: str
    argv: tuple[str, ...]


DEFAULT_STEPS: tuple[VerificationStep, ...] = (
    VerificationStep("pytest", DEFAULT_PYTEST_ARGV),
    VerificationStep("local-preflight", DEFAULT_PREFLIGHT_ARGV),
)


# Bounds how much of a step's own captured stdout+stderr reaches the
# SubagentStop deny reason (issue #1476, evaluating-deterministic-gate-
# quality dimension 18): this hook has no secret-redaction pass of its
# own, so an unbounded embed would carry forward any credential a
# verification command's own output happened to echo, straight into a
# chat-visible field. Truncating to the tail (where a real failure's own
# signal usually lives, matching how CI tooling generally surfaces "last N
# lines") bounds exposure; it does not solve secret redaction in general --
# a secret inside the retained tail still leaks. Full detection is this
# repository's own dedicated `scanning-leaked-secrets`/`betterleaks`
# mechanism's job, not reinvented here.
_MAX_OUTPUT_CHARS = 4000


@dataclass(frozen=True)
class StepResult:
    label: str
    passed: bool
    output: str
    timed_out: bool = False


def run_step(step: VerificationStep, cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> StepResult:
    """Run one verification step. Every way the command can fail to
    produce a real exit code (a missing executable, a timeout, an OSError
    from the spawn itself) becomes a failing StepResult carrying the
    underlying error text, never a silent pass."""
    try:
        completed = subprocess.run(  # noqa: S603
            list(step.argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return StepResult(step.label, False, f"timed out after {timeout}s", timed_out=True)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return StepResult(step.label, False, f"failed to run: {error}")
    output = f"{completed.stdout}{completed.stderr}".strip()
    if len(output) > _MAX_OUTPUT_CHARS:
        output = f"...(truncated, {len(output)} chars total)...\n{output[-_MAX_OUTPUT_CHARS:]}"
    return StepResult(step.label, completed.returncode == 0, output)


def run_verification(
    steps: tuple[VerificationStep, ...], cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> dict[str, object]:
    """Run each step in order; stop at the first failure."""
    for step in steps:
        result = run_step(step, cwd, timeout)
        if not result.passed:
            # A timeout is flagged as possibly transient (a slow but not
            # broken run, or a momentarily overloaded machine) rather than
            # phrased identically to a genuine command failure -- a task
            # reading this reason should retry once before assuming its
            # own change is the regression (evaluating-deterministic-gate-
            # quality dimension 24, issue #1476).
            transient_note = (
                " -- this may be a transient timeout rather than a real "
                "regression; retry once before assuming your own change "
                "broke this"
                if result.timed_out
                else ""
            )
            reason = (
                f"task-level full verification failed at '{result.label}' "
                f"(exit condition per issue #1476, design doc Decision 20){transient_note}: "
                f"{result.output or '(no output)'}"
            )
            return {"decision": "deny", "reason": reason}
    return {"decision": "allow"}


def _resolve_cwd(payload: dict[str, object]) -> Path:
    """The SubagentStop hook payload's own `cwd` field when it names a real
    directory (the task's own worktree root, per Claude Code's documented
    hook input schema); this process's own working directory otherwise --
    matching the empirically-verified fallback
    check_task_bash_safety.sh's own `${CLAUDE_PROJECT_DIR:-$(pwd)}` uses
    for the sibling PreToolUse hook (see
    references/threat-model-and-authorization.md)."""
    raw = payload.get("cwd")
    if isinstance(raw, str) and raw:
        candidate = Path(raw)
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def _steps_from_json(raw: str) -> tuple[VerificationStep, ...] | None:
    """Parse `--steps-json`'s `[[label, [argv...]], ...]` shape. Returns
    None (never raises) on any malformed input -- the caller treats that
    as a fail-closed deny, the same discipline every other malformed-input
    path in this module already applies."""
    try:
        raw_steps = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw_steps, list) or not raw_steps:
        return None
    steps: list[VerificationStep] = []
    for entry in raw_steps:
        if not isinstance(entry, list) or len(entry) != 2:
            return None
        label, argv = entry
        if not isinstance(label, str) or not label:
            return None
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            return None
        steps.append(VerificationStep(label, tuple(argv)))
    return tuple(steps)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: read the SubagentStop hook payload from stdin,
    print a `{"decision": ...}` JSON verdict to stdout, and always exit 0
    -- check_task_full_verification.sh, not this process's own exit code,
    is what turns a "deny" into an actual block."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-step subprocess ceiling (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--steps-json",
        help="Test-only escape hatch: a JSON-encoded [[label, [argv...]], ...] "
        "overriding the default verification steps. The production hook "
        "never passes this -- it always runs the real pytest/local-preflight "
        "commands.",
    )
    args = parser.parse_args(argv)

    try:
        raw_input = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError as error:
        print(json.dumps({"decision": "deny", "reason": f"stdin is not valid UTF-8: {error}. Failing closed."}))
        return 0

    try:
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except json.JSONDecodeError as error:
        print(json.dumps({"decision": "deny", "reason": f"stdin is not valid JSON: {error}. Failing closed."}))
        return 0

    if not isinstance(payload, dict):
        print(json.dumps({"decision": "deny", "reason": "stdin JSON is not an object. Failing closed."}))
        return 0

    if args.steps_json is not None:
        steps = _steps_from_json(args.steps_json)
        if steps is None:
            print(json.dumps({"decision": "deny", "reason": "--steps-json could not be parsed. Failing closed."}))
            return 0
    else:
        steps = DEFAULT_STEPS

    cwd = _resolve_cwd(payload)
    result = run_verification(steps, cwd, args.timeout_seconds)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

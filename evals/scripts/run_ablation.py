"""In-repo runner that compares a task fixture's output with a skill
available/injected against the same run with the skill withheld (issue
#583).

Before this script, no file anywhere in this repository matched a live
model-execution pattern (`claude -p`, `subprocess.run` against a model
CLI, `--append-system-prompt-file`, or equivalent) capable of running a
committed eval task with and without a skill and comparing the two --
every `evals/*/eval.yaml` declares `executor: copilot-sdk`, an external
harness (`waza`) not vendored into this repository, whose tasks assert
only `output_contains`/`output_not_contains` substrings against a supplied
transcript, never producing one. Per the ablation-capability distinction
`evaluating-skill-quality`'s dimension 8 requires (issue #185): this
script is what moves a skill's own `eval-status.md` from "no ablation
mechanism exists in this repository" to "ablation-capable, not yet run".
Provisioning the credentials to actually execute it end to end is a
separate, disclosed precondition (issue #124's own owner-provisioning
scope, though #124 itself targets a different mechanism -- the external
copilot-sdk cross-model matrix, not this one) -- this script's shape and
interface are built and unit-tested against a stub executor first, per
issue #583's own explicit constraint that this not be blocked on
credentials existing yet.

Skill toggle mechanism -- `--bare` plus `--append-system-prompt-file`,
not a staged `.claude/skills/` directory: Claude Code's own headless-mode
docs (https://code.claude.com/docs/en/headless.md, fetched directly
while designing this script) confirm `--bare` "skip[s] auto-discovery of
hooks, skills, plugins, MCP servers, auto memory, and CLAUDE.md" and is
"the recommended mode for scripted and SDK calls". Without it, invoking
`claude -p` from a checkout of this very repository would auto-load this
repository's own CLAUDE.md and its other ~23 skills into *both* arms of
the comparison, which would make the "without skill" arm not actually
mean "without skill" -- undermining the whole premise of an ablation run.
`--bare` and skill auto-discovery are therefore not a fidelity dial with
a middle setting: `--bare` explicitly disables the very discovery
mechanism a staged `.claude/skills/<name>/` directory would depend on, so
the two approaches are mutually exclusive, not MVP-vs-full-fidelity
points on one spectrum. `--append-system-prompt-file` is documented as
available even in bare mode (the "System prompt additions" row of bare
mode's own "To load" table) and appends its file's content to the system
prompt for one invocation, which is this script's "skill available" arm;
omitting the flag entirely is the "skill withheld" arm. This is a real,
disclosed fidelity tradeoff, not an oversight: a live run through this
mechanism measures the effect of the skill's instructions being present
in context, not the effect of the model choosing to invoke the skill as
a discoverable tool (the Skill tool never appears in bare mode's tool
list at all, per the same docs page).

Undecided, disclosed residual risk for whoever runs this live: what
`--permission-mode`/`--allowedTools` a real run should pass is not yet
determined -- headless mode's tool-approval behavior with no attached
terminal was not verified against a live run while building this script,
and guessing a specific value here would be an unverified claim of
exactly the kind this repository's own reviewers flag. A live run also
needs `ANTHROPIC_API_KEY` (or an `apiKeyHelper`) explicitly configured,
since bare mode skips OAuth/keychain reads entirely (same docs page).

Standard library plus PyYAML (already a dev dependency used by this
repository's other fixture tooling) and this repository's own
`score_contract.score` (`skills/scorer-gated-skill-edits/scripts/
score_contract.py`, importable as a bare `import score_contract` because
both that directory and `evals/scripts` are already on `pythonpath` in
`pyproject.toml`).

Exit code contract (matching the majority pattern across this
repository's other `evals/scripts/*.py` CLIs -- `route_test_model.py`,
`lint_fixture_assertions.py`, `gate_evals_scripts_coverage.py` -- not
`set_config_model.py`, whose flat single-`ValueError`-type contract is an
outlier that predates argparse in that script): 2 means the input itself
was malformed (bad usage, a missing file, a fixture that does not match
the expected shape, a blank/padded `--model-cli`); 1 means the input was
valid but the model CLI invocation itself failed (nonzero exit, could not
be launched, or timed out); 0 means success.

Usage::

    python3 evals/scripts/run_ablation.py --task TASK.yaml --skill-md SKILL.md
                                           [--model-cli claude] [--timeout 300]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

import score_contract

DEFAULT_MODEL_CLI = "claude"
# Matches evals/*/eval.yaml's own config.timeout_seconds convention for a
# single task, so this script's default is consistent with the committed
# suites' own budget rather than an arbitrary new number.
DEFAULT_TIMEOUT_SECONDS = 300

# Always applied, not CLI-exposed: --bare is what makes the "without skill"
# arm actually mean that (see module docstring). Making it overridable would
# let a caller silently reintroduce this repository's own skills/CLAUDE.md
# into the comparison without realizing it breaks the ablation's premise.
_FIXED_FLAGS = ["--bare"]

# (argv, timeout_seconds) -> captured stdout text. Swappable so this script's
# plumbing is unit-testable without a live model CLI or credentials.
Executor = Callable[[Sequence[str], int], str]


def _require_nonblank_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def load_task_fixture(path: Path) -> dict:
    """Load and minimally validate a committed task fixture (``evals/*/tasks/
    *.yaml`` shape: a top-level ``id``, ``inputs.prompt``, and ``expected``).

    Only the three fields this script actually consumes are validated --
    ``name``/``description``/``tags`` are not, since checking fields this
    script never reads would make it a second, unrequested fixture-shape
    linter duplicating ``lint_fixture_assertions.py``'s own job. ``expected``
    is checked only for being a mapping; the per-assertion-list validation
    (e.g. ``output_contains`` must be a list) is ``score_contract.score``'s
    own responsibility, not duplicated here.

    Raises ``ValueError`` on any malformed shape, including invalid YAML
    syntax (wrapped from ``yaml.YAMLError`` so callers only ever need to
    catch one exception type from this function).
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except OSError as exc:
        raise ValueError(f"cannot read task fixture {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in task fixture {path}: {exc}") from exc

    if not isinstance(data, Mapping):
        raise ValueError(f"task fixture {path} must be a YAML mapping")

    task_id = _require_nonblank_str(data.get("id"), "id")

    inputs = data.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError(f"task fixture {path}: 'inputs' must be a mapping")
    prompt = _require_nonblank_str(inputs.get("prompt"), "inputs.prompt")

    expected = data.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError(f"task fixture {path}: 'expected' must be a mapping")

    return {"id": task_id, "prompt": prompt, "expected": expected}


def build_command(model_cli: str, prompt: str, skill_md: Path | None) -> list[str]:
    """Build the argv for one model-CLI invocation.

    ``skill_md`` given appends ``--append-system-prompt-file <skill_md>``
    (the "skill available" arm); ``None`` omits it entirely (the "skill
    withheld" arm). ``--bare`` is always included -- see module docstring.
    """
    model_cli = _require_nonblank_str(model_cli, "model_cli")
    if model_cli != model_cli.strip():
        raise ValueError("model_cli must be unpadded")
    argv = [model_cli, "-p", prompt, *_FIXED_FLAGS]
    if skill_md is not None:
        argv += ["--append-system-prompt-file", str(skill_md)]
    return argv


def subprocess_executor(argv: Sequence[str], timeout: int) -> str:
    """Default executor: run ``argv`` as a real subprocess and return its
    captured stdout.

    Raises ``RuntimeError`` (with stderr included) on a nonzero exit --
    silently returning empty/partial output on a failed model-CLI call
    would let a broken invocation score as if the model simply produced a
    bad answer, masking the real failure. ``subprocess.TimeoutExpired``
    propagates as-is; callers already handle it as a distinct failure mode.
    """
    result = subprocess.run(
        list(argv), capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"model CLI exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def run_once(
    model_cli: str,
    prompt: str,
    skill_md: Path | None,
    executor: Executor,
    timeout: int,
) -> str:
    """Build the command for one arm and run it through ``executor``."""
    argv = build_command(model_cli, prompt, skill_md)
    return executor(argv, timeout)


@dataclass(frozen=True)
class AblationResult:
    """Both arms of one task's comparison: raw outputs and their scores."""

    task_id: str
    with_skill_output: str
    without_skill_output: str
    with_skill_score: float
    without_skill_score: float

    @property
    def delta(self) -> float:
        """with-skill score minus without-skill score."""
        return self.with_skill_score - self.without_skill_score


def run_ablation(
    fixture: Mapping,
    skill_md: Path,
    *,
    executor: Executor,
    model_cli: str = DEFAULT_MODEL_CLI,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> AblationResult:
    """Run ``fixture``'s prompt twice (with ``skill_md`` injected, then
    without) through ``executor``, scoring each output against the
    fixture's own ``expected`` assertions via ``score_contract.score``.

    ``fixture`` is the mapping ``load_task_fixture`` returns (or an
    equivalent ``{"id", "prompt", "expected"}`` mapping).
    """
    prompt = fixture["prompt"]
    expected = fixture["expected"]

    with_skill_output = run_once(model_cli, prompt, skill_md, executor, timeout)
    without_skill_output = run_once(model_cli, prompt, None, executor, timeout)

    return AblationResult(
        task_id=fixture["id"],
        with_skill_output=with_skill_output,
        without_skill_output=without_skill_output,
        with_skill_score=score_contract.score(with_skill_output, expected),
        without_skill_score=score_contract.score(without_skill_output, expected),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a task fixture's prompt with and without a skill "
        "injected, and print both outputs' comparable scores as JSON."
    )
    parser.add_argument("--task", required=True, type=Path, help="Path to a task fixture YAML.")
    parser.add_argument(
        "--skill-md", required=True, type=Path, help="Path to the skill's SKILL.md."
    )
    parser.add_argument("--model-cli", default=DEFAULT_MODEL_CLI)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    if not args.skill_md.is_file():
        print(f"error: skill file not found: {args.skill_md}", file=sys.stderr)
        return 2

    try:
        fixture = load_task_fixture(args.task)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        result = run_ablation(
            fixture,
            args.skill_md,
            executor=subprocess_executor,
            model_cli=args.model_cli,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "task_id": result.task_id,
                "with_skill_score": result.with_skill_score,
                "without_skill_score": result.without_skill_score,
                "delta": result.delta,
                "with_skill_output": result.with_skill_output,
                "without_skill_output": result.without_skill_output,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

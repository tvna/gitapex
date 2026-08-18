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
list at all, per the same docs page). `_FIXED_FLAGS` below is therefore
not CLI-overridable -- see that constant's own comment.

Hermetic-by-default execution (issue #1132, resolving this section's
former "Undecided" status): `_FIXED_FLAGS` includes `--tools ""`, which
this environment's own installed `claude --help` documents as disabling
every tool ("Use \"\" to disable all tools"). `--bare` alone is not
enough -- the same `--help` output states bare mode still leaves Bash and
file read/edit available -- which is exactly the hole PR #1099's
live-proxy trials hit: an executed agent with tool access cross-checked a
fixture's fictional PR number against real repo state instead of staying
inside the fixture's own scope (issue #1132's own tracking comment).
`subprocess_executor` additionally passes an explicit, allowlisted
environment (`_HERMETIC_ENV_ALLOWLIST`) rather than inheriting the
calling process's full environment, so an ambient CI credential (e.g.
`GITHUB_TOKEN`) set in the parent process is never visible to the
invoked model CLI even if a future change reintroduced tool access by
mistake -- defense in depth, not a substitute for `--tools ""`. A live
run still needs `ANTHROPIC_API_KEY` (or an `apiKeyHelper`) explicitly
configured and allowlisted, since bare mode skips OAuth/keychain reads
entirely (same docs page). This is the same repository-level secret
`CONTRIBUTING.md`'s "ranking-the-open-queue weekly digest API key"
section already documents end to end (issuance at
console.anthropic.com, storage as a repository secret, minimum
permissions, rotation cadence, and a verification procedure) -- not a
new credential this script introduces, so its lifecycle is not
re-documented a second time here. The vendored eval schema's `mcp_mocks` field
(`.gitapex/waza-eval.schema.json`) stays declarable but unimplemented
here: with zero tools ever granted, there is nothing for it to mock.

Standard library plus PyYAML (already a dev dependency used by this
repository's other fixture tooling), pydantic (`_RunAblationArgs`'
CLI-argument validation), and this repository's own
`gitapex_score_contract.score` (`skills/scorer-gated-skill-edits/scripts/
gitapex_score_contract.py`). That module is imported by bare name below; the
`sys.path` bootstrap right before the import exists because
`pyproject.toml`'s `pythonpath` entry that would otherwise resolve it is
pytest-only and has no effect on a direct `python3 evals/scripts/
gitapex_run_ablation.py ...` invocation -- see the bootstrap's own comment.

Exit code contract: 2 means the input itself was malformed (bad usage, a
missing file, a fixture or `expected` block that does not match the
required shape, a blank/padded `--model-cli`, or a non-positive
`--timeout`); 1 means the input was valid but the model CLI invocation
itself failed (nonzero exit, could not be launched, or timed out); 0
means success. This malformed-input-vs-execution-failure split matches
`evals/scripts/gitapex_lint_fixture_assertions.py`'s own 2/1 convention more
closely than `evals/scripts/gitapex_set_config_model.py`'s flat single-
exception-type contract (that script's own outlier, predating argparse
there).

Usage::

    python3 evals/scripts/gitapex_run_ablation.py --task TASK.yaml --skill-md SKILL.md
                                           [--model-cli claude] [--timeout 300]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError, field_validator

# gitapex_score_contract.py lives in a sibling skill's scripts/ directory, not this
# one. pyproject.toml's `pythonpath` entry resolves the bare `import
# gitapex_score_contract` below under pytest, but that setting is a pytest-only
# mechanism -- it has no effect when this file is run directly the way its
# own Usage:: block documents, so a plain `python3 evals/scripts/
# gitapex_run_ablation.py ...` crashed with ModuleNotFoundError before this
# bootstrap existed (confirmed by direct execution while reviewing this
# script). Insert the directory explicitly so both invocation styles
# resolve identically, without depending on pytest ever having run first.
_SCORE_CONTRACT_DIR = Path(__file__).resolve().parents[2] / "skills" / "scorer-gated-skill-edits" / "scripts"
if str(_SCORE_CONTRACT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORE_CONTRACT_DIR))

import gitapex_score_contract  # noqa: E402 -- path bootstrap above must run first

DEFAULT_MODEL_CLI = "claude"
# Matches evals/*/eval.yaml's own config.timeout_seconds convention for a
# single task, so this script's default is consistent with the committed
# suites' own budget rather than an arbitrary new number.
DEFAULT_TIMEOUT_SECONDS = 300

# Always applied, not CLI-exposed -- see the module docstring's "Skill
# toggle mechanism" section for why --bare must stay non-overridable, and
# its "Hermetic-by-default execution" section for why --tools "" is here
# too: --bare alone still leaves Bash and file read/edit available.
_FIXED_FLAGS = ["--bare", "--tools", ""]

# Only these variables are ever passed through to the invoked model-CLI
# subprocess -- see module docstring's "Hermetic-by-default execution"
# section. An allowlist, not a denylist of known-bad names: a denylist
# would miss any ambient CI credential not already anticipated.
_HERMETIC_ENV_ALLOWLIST = ("PATH", "HOME", "ANTHROPIC_API_KEY", "TMPDIR", "TMP", "TEMP")


def _hermetic_env() -> dict[str, str]:
    """The minimal environment a model-CLI subprocess actually needs,
    filtered from the calling process's own environment -- never the full
    inherited environment, so an ambient CI credential (``GITHUB_TOKEN``,
    a ``gh``-related variable, ...) set in the parent process is never
    visible to the invoked subprocess."""
    return {key: value for key, value in os.environ.items() if key in _HERMETIC_ENV_ALLOWLIST}


# (argv, timeout_seconds) -> captured stdout text. Swappable so this script's
# plumbing is unit-testable without a live model CLI or credentials.
Executor = Callable[[Sequence[str], int], str]


def _require_nonblank_str(value: object, field: str) -> str:
    """Reject anything that isn't a non-empty string. Deliberately does
    NOT also reject leading/trailing whitespace -- unlike
    ``_require_unpadded_str`` below, this is used for ``inputs.prompt``,
    whose real committed fixtures universally end with a trailing newline
    from YAML's ``|`` block-scalar chomping (verified against all 258
    committed task fixtures while fixing this), so an unpadded check here
    would reject nearly every real fixture in this repository.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_unpadded_str(value: object, field: str) -> str:
    """Like ``_require_nonblank_str``, but also rejects leading/trailing
    whitespace. Used only for short, single-token fields (a fixture's
    ``id``, a CLI executable name) where padding is always an authoring
    mistake -- confirmed none of the 258 committed task fixtures' ``id``
    fields carry padding, unlike ``inputs.prompt`` (see
    ``_require_nonblank_str``'s own docstring for why that field is
    exempted instead of sharing this stricter check).
    """
    value = _require_nonblank_str(value, field)
    if value != value.strip():
        raise ValueError(f"{field} must be unpadded")
    return value


def load_yaml_mapping(path: Path, label: str) -> Mapping[str, Any]:
    """Read ``path`` as YAML and return its top-level mapping.

    ``label`` names the artifact being read ("task fixture", "eval suite",
    ...) in every error message, so this module's own ``load_task_fixture``
    and ``gitapex_run_eval_suite.load_eval_suite`` raise identically worded
    read/parse/not-a-mapping failures from one place rather than each
    re-spelling the same three messages. Every failure -- unreadable file,
    non-UTF-8 bytes, invalid YAML, a non-mapping document -- surfaces as
    ``ValueError``, so callers only ever catch one exception type.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {label} {path}: {exc}") from exc

    if not isinstance(data, Mapping):
        raise ValueError(f"{label} {path} must be a YAML mapping")
    return data


def load_task_fixture(path: Path) -> dict:
    """Load and minimally validate a committed task fixture (``evals/*/tasks/
    *.yaml`` shape: a top-level ``id``, ``inputs.prompt``, ``expected``, and
    optional ``graders``).

    Only the four fields this script (and ``gitapex_run_eval_suite.py``, which
    reuses this loader) actually consume are validated --
    ``name``/``description``/``tags`` are not, since checking fields this
    script never reads would make it a second, unrequested fixture-shape
    linter duplicating ``gitapex_lint_fixture_assertions.py``'s own job. ``expected``
    is checked only for being a mapping here; the deeper per-assertion-list
    shape validation (e.g. ``output_contains`` must be a list) happens in
    ``gitapex_run_ablation()`` via a cheap dry run against ``gitapex_score_contract.score``,
    before any live model call -- not duplicated in this loader. ``graders``
    (per ``.gitapex/waza-task.schema.json``'s own optional top-level array)
    is returned as-is when present, ``[]`` when absent -- its own per-entry
    shape validation happens in ``gitapex_run_eval_suite.py``, the only
    consumer that dispatches on it.

    Raises ``ValueError`` on any malformed shape, including invalid or
    non-UTF-8 file content, so callers only ever need to catch one
    exception type from this function.
    """
    data = load_yaml_mapping(path, "task fixture")

    task_id = _require_unpadded_str(data.get("id"), "id")

    inputs = data.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError(f"task fixture {path}: 'inputs' must be a mapping")
    prompt = _require_nonblank_str(inputs.get("prompt"), "inputs.prompt")

    expected = data.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError(f"task fixture {path}: 'expected' must be a mapping")

    graders = data.get("graders")
    if graders is None:
        graders = []
    elif not isinstance(graders, list):
        raise ValueError(f"task fixture {path}: 'graders' must be a list")

    return {"id": task_id, "prompt": prompt, "expected": expected, "graders": graders}


def build_command(model_cli: str, prompt: str, skill_md: Path | None, *, model: str | None = None) -> list[str]:
    """Build the argv for one model-CLI invocation.

    ``skill_md`` given appends ``--append-system-prompt-file <skill_md>``
    (the "skill available" arm); ``None`` omits it entirely (the "skill
    withheld" arm). ``--bare``/``--tools ""`` are always included -- see
    module docstring's "Hermetic-by-default execution" section. ``model``
    given appends ``--model <model>`` (verified live against this
    environment's own ``claude --help``: accepts a full model id, e.g.
    ``claude-sonnet-5``); ``None`` (the default) omits it entirely,
    preserving every existing caller's behavior unchanged --
    ``gitapex_run_ablation()``'s own two call sites stay ``model=None``.
    """
    model_cli = _require_unpadded_str(model_cli, "model_cli")
    argv = [model_cli, "-p", prompt, *_FIXED_FLAGS]
    if skill_md is not None:
        argv += ["--append-system-prompt-file", str(skill_md)]
    if model is not None:
        argv += ["--model", model]
    return argv


def subprocess_executor(argv: Sequence[str], timeout: int) -> str:
    """Default executor: run ``argv`` as a real subprocess and return its
    captured stdout.

    Raises ``RuntimeError`` (with stderr included) on a nonzero exit --
    silently returning empty/partial output on a failed model-CLI call
    would let a broken invocation score as if the model simply produced a
    bad answer, masking the real failure. ``subprocess.TimeoutExpired``
    propagates as-is; callers already handle it as a distinct failure mode.
    ``errors="replace"`` on stdout/stderr decoding means a stray non-UTF-8
    byte in live model output degrades to a replacement character instead
    of raising ``UnicodeDecodeError`` (a ``ValueError`` subclass that would
    otherwise be indistinguishable from a malformed-input failure to this
    function's caller).
    """
    # S603 waived: an explicit argv list from the caller, no shell.
    result = subprocess.run(  # noqa: S603
        list(argv),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=_hermetic_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"model CLI exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def redact_executor_failure_reason(exc: Exception) -> str:
    """A safe, disclosed reason string for ``exc`` -- never the raw text of
    a ``RuntimeError`` or ``subprocess.TimeoutExpired``, both of which can
    embed live, externally-produced content a caller's own result blob
    must not republish verbatim: ``subprocess_executor``'s own
    ``RuntimeError`` message above includes the invoked model CLI's raw
    stderr (issue #1143 adversarial review round), and
    ``TimeoutExpired``'s own string form includes the full argv it ran,
    which itself carries a fixture's prompt text (``build_command``).
    Neither is safe to echo into a result a caller's own docstring calls
    "loud and visible" -- CLAUDE.md's own rule against echoing untrusted/
    external content into a generated artifact. A ``ValueError``/
    ``OSError``, in contrast, is always this module's or the standard
    library's own deterministic, code-controlled text (a missing-file
    path, a malformed-YAML complaint) -- never a live model's own output
    -- so those stay verbatim, genuinely useful and genuinely safe. The
    split is by exception type, not a per-instance guess.

    Hoisted here (issue #1144) rather than duplicated across callers:
    every ``evals/scripts/*.py`` module that records a skipped entry's or
    fixture's own reason (``gitapex_run_effectiveness_correlation.py``,
    ``gitapex_run_eval_suite.py``) already imports this module, so this
    is zero new import edges and one single definition of the redaction
    rule.
    """
    if isinstance(exc, (RuntimeError, subprocess.TimeoutExpired)):
        return f"{type(exc).__name__}: model CLI invocation failed or timed out (detail intentionally not republished here)"
    return str(exc)


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


def _validate_expected_shape(expected: Mapping) -> None:
    """Raise ``ValueError`` if ``expected`` is not a well-formed assertion
    set, without spending a live model call to find out.

    Dry-runs ``gitapex_score_contract.score("", expected)``: an empty output text
    exercises exactly the same shape checks (assertion set non-empty, each
    list correctly typed) ``gitapex_score_contract.score`` would otherwise only
    raise partway through scoring a real, already-obtained model output.
    Converts a plain ``TypeError`` (a non-string entry in an
    ``output_contains`` list, which ``in`` rejects) or ``AttributeError``
    (the same entry in the case-insensitive ``output_icontains`` /
    ``output_not_icontains`` lists, which reach ``str.casefold()`` instead)
    into ``ValueError`` so this function, like ``load_task_fixture``, raises
    only one exception type.
    """
    try:
        gitapex_score_contract.score("", expected)
    except (TypeError, AttributeError) as exc:
        raise ValueError(f"'expected' assertions are malformed: {exc}") from exc


def gitapex_run_ablation(
    fixture: Mapping,
    skill_md: Path,
    *,
    executor: Executor,
    model_cli: str = DEFAULT_MODEL_CLI,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> AblationResult:
    """Run ``fixture``'s prompt twice (with ``skill_md`` injected, then
    without) through ``executor``, scoring each output against the
    fixture's own ``expected`` assertions via ``gitapex_score_contract.score``.

    ``fixture`` is the mapping ``load_task_fixture`` returns (or an
    equivalent ``{"id", "prompt", "expected"}`` mapping). ``expected``'s
    shape is validated (see ``_validate_expected_shape``) before either
    live call, so a malformed or empty assertion set is rejected without
    spending a single model-CLI invocation on it.
    """
    prompt = fixture["prompt"]
    expected = fixture["expected"]
    _validate_expected_shape(expected)

    with_skill_output = executor(build_command(model_cli, prompt, skill_md), timeout)
    without_skill_output = executor(build_command(model_cli, prompt, None), timeout)

    return AblationResult(
        task_id=fixture["id"],
        with_skill_output=with_skill_output,
        without_skill_output=without_skill_output,
        with_skill_score=gitapex_score_contract.score(with_skill_output, expected),
        without_skill_score=gitapex_score_contract.score(without_skill_output, expected),
    )


class _RunAblationArgs(BaseModel):
    """Validates the two ``main()`` CLI values that were previously checked
    by hand immediately after ``parser.parse_args()`` (``--skill-md`` must
    name an existing file; ``--timeout`` must be a positive number of
    seconds), replacing those two hand-rolled checks with field validators
    that raise the exact same message text. ``--task`` and ``--model-cli``
    are deliberately not modeled here: ``--task`` keeps its own existing
    validation in ``load_task_fixture`` (which already raises ``ValueError``
    with its own distinct message for a missing/malformed file), and
    ``--model-cli`` keeps its own existing validation in ``build_command``
    (exercised by every caller of that function, not only this CLI entry
    point) -- duplicating either here would diverge from those functions'
    own error text or leave two competing validators for the same value.
    """

    skill_md: Path
    timeout: int

    @field_validator("skill_md")
    @classmethod
    def _skill_md_must_exist(cls, value: Path) -> Path:
        if not value.is_file():
            raise ValueError(f"skill file not found: {value}")
        return value

    @field_validator("timeout")
    @classmethod
    def _timeout_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(f"--timeout must be a positive number of seconds, got {value}")
        return value


def _validation_error_message(exc: ValidationError) -> str:
    """The first error's original message, unwrapped from pydantic's own
    "Value error, " prefix -- reproduces the exact text a replaced
    hand-validation printed, not pydantic's own formatted error text."""
    error = exc.errors()[0]
    ctx = error.get("ctx") or {}
    original = ctx.get("error")
    if isinstance(original, Exception):
        return str(original)
    return str(error["msg"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a task fixture's prompt with and without a skill "
        "injected, and print both outputs' comparable scores as JSON."
    )
    parser.add_argument("--task", required=True, type=Path, help="Path to a task fixture YAML.")
    parser.add_argument("--skill-md", required=True, type=Path, help="Path to the skill's SKILL.md.")
    parser.add_argument("--model-cli", default=DEFAULT_MODEL_CLI)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    try:
        validated_args = _RunAblationArgs(skill_md=args.skill_md, timeout=args.timeout)
    except ValidationError as exc:
        print(f"error: {_validation_error_message(exc)}", file=sys.stderr)
        return 2

    try:
        fixture = load_task_fixture(args.task)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        result = gitapex_run_ablation(
            fixture,
            validated_args.skill_md,
            executor=subprocess_executor,
            model_cli=args.model_cli,
            timeout=validated_args.timeout,
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

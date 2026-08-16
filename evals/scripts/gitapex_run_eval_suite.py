"""Suite-level eval runner: executes a whole ``evals/<skill>/`` suite --
every task fixture its ``eval.yaml`` names, each repeated ``trials_per_task``
times, scored by both ``expected.*`` substring assertions and any declared
``graders:`` -- and writes an aggregate result (issue #1132).

Before this script, ``gitapex_run_ablation.py`` ran exactly one task fixture,
exactly once per arm, comparing a skill present against a skill withheld.
This script is a different, single-arm capability layered on top of that
file's own low-level primitives (``build_command``, ``subprocess_executor``,
``load_task_fixture``, the ``Executor`` type): the skill is always injected,
matching what ``waza run <skill>`` did in this repository's own CI before
this script existed (a single command, no with/without split) -- not
``gitapex_run_ablation()``'s own separate two-arm comparison, which this
script does not modify and does not call.

Hermetic-by-default execution, ``--model`` support, and the fixture-level
``graders`` key are all provided by ``gitapex_run_ablation.py`` itself (its
own "Hermetic-by-default execution" docstring section); this script adds no
executor-construction logic of its own; every model-CLI invocation this file
makes goes through that module's ``build_command``/``subprocess_executor``
unchanged.

Score composition, specified explicitly rather than left implicit: one
trial's score is the arithmetic mean of the fixture's ``expected.*``
substring score (via ``gitapex_score_contract.score``, unchanged, always one
value regardless of how many individual assertions it aggregates) and each
declared ``graders:`` entry's own pass (1.0) / fail (0.0) outcome -- so a
fixture declaring zero graders scores exactly as it did before this script
existed (the substring score alone), and each additional grader is one more
equally-weighted vote. A fixture's own score is the mean of its
``trials_per_task`` trial scores; the suite's ``mean_score`` is the mean of
its fixtures' own scores -- matching ``eval-scores.schema.json``'s own
``mean_score`` definition ("mean of this file's per-fixture scores").

Aggregate output shape: modeled on
``skills/scorer-gated-skill-edits/references/eval-scores.schema.json``
(``model_id``/``n_fixtures``/``mean_score``/``scores[]``, each entry
``fixture_id``/``score``), not on waza's own undocumented
``results/<skill>.json`` shape -- that schema does not restrict additional
properties, so a ``trials`` key carrying per-trial/per-grader detail is added
to each ``scores[]`` entry without breaking conformance. ``scores[]`` is
sorted by ``fixture_id`` (not filesystem/glob discovery order) because the
schema's own field description states this explicitly: "sorted by
fixture_id so two runs of the same corpus produce a stable diff."

``config.executor`` (every real committed ``eval.yaml`` declares
``copilot-sdk``, waza's own executor concept) is read through
``load_eval_suite`` but never enforced or dispatched on: this script always
executes through the Claude Code CLI path
(``gitapex_run_ablation.build_command``/``subprocess_executor``), an explicit,
disclosed scope decision (issue #1132's own resolved "execution backend
reach" question) rather than a silently ignored field. A future non-Claude
backend can be plugged in behind the existing ``Executor`` DI type this
script reuses unchanged, without a redesign.

``mcp_mocks`` (a top-level ``eval.yaml`` field waza's own schema still
vendors) is rejected outright when non-empty: this script's executor grants
zero tools (``gitapex_run_ablation.py``'s own ``--tools ""``), so a declared
mock has nothing to attach to, and silently ignoring it would let a fixture
score as though its mocked condition held when it never ran.

Grader coverage: every real committed task fixture that declares
``graders:`` (``evals/untrusted-input-triage/tasks/*.yaml``, 4 files) uses
only ``type: text`` with ``contains``/``not_contains`` -- issue #1132's own
stated non-goal is reproducing all 12 of waza's grader ``type`` values on day
one, scoped instead to what this repository's own fixtures actually use.
``run_text_grader`` implements exactly that one type/config-key subset and
raises ``ValueError`` (never silently skips) for anything else, so a future
fixture that needs a wider type is a loud, visible gap rather than an
invisible pass.

Disclosed, out-of-scope residual risk (this repository's own resolved ACM
decision, issue #1132): a retried dispatch (a session usage limit, the same
class of event ``evals/untrusted-input-triage/behavioral-eval-2026-08-01.md``
already recorded once) is indistinguishable from a genuine trial here. This
script does not attempt to detect or exclude one -- ``trials_per_task``
variance data can be corrupted by an unnoticed retry, a known limitation, not
solved by this script.

Usage::

    python3 evals/scripts/gitapex_run_eval_suite.py --eval-yaml EVAL.yaml \\
        --skill-md SKILL.md [--model-cli claude] [-o results.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# gitapex_run_ablation.py lives in this same directory, resolved without a
# bootstrap under both invocation styles (pytest's own pythonpath entry, and
# the sys.path[0]-is-the-script's-own-directory behavior a direct
# `python3 evals/scripts/gitapex_run_eval_suite.py ...` invocation already
# gets for free). gitapex_score_contract.py does not get that same free
# resolution -- it lives in a sibling skill's own scripts/ directory -- so it
# needs the identical bootstrap gitapex_run_ablation.py's own module docstring
# already explains.
_SCORE_CONTRACT_DIR = Path(__file__).resolve().parents[2] / "skills" / "scorer-gated-skill-edits" / "scripts"
if str(_SCORE_CONTRACT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORE_CONTRACT_DIR))

import gitapex_run_ablation  # noqa: E402 -- path bootstrap above must run first
import gitapex_score_contract  # noqa: E402 -- path bootstrap above must run first

DEFAULT_MODEL_CLI = gitapex_run_ablation.DEFAULT_MODEL_CLI

# Module-level rebinding (not a call inside main()) so tests can
# monkeypatch this name directly, the same pattern
# tests/test_gitapex_run_ablation.py already uses against that module.
subprocess_executor = gitapex_run_ablation.subprocess_executor

# text grader config keys this script implements -- see module docstring's
# "Grader coverage" section for why the other 4 (contains_cs/not_contains_cs/
# regex_match/regex_not_match) are an explicit, loud gap rather than silently
# accepted or silently ignored.
_SUPPORTED_TEXT_CONFIG_KEYS = ("contains", "not_contains")


def _require_positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer, got {value!r}")
    return value


def _require_nonblank_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string, got {value!r}")
    return value


def load_eval_suite(path: Path) -> dict[str, Any]:
    """Load and minimally validate a committed suite spec (``evals/*/eval.yaml``
    shape): ``name``, ``skill``, ``config`` (``trials_per_task``,
    ``timeout_seconds``, ``model``, and ``executor`` -- read through, never
    enforced, see module docstring), and ``tasks`` (a non-empty list of glob
    patterns). Rejects a non-empty ``mcp_mocks`` (see module docstring).

    Only the fields this script actually consumes are validated, the same
    scoping rule ``gitapex_run_ablation.load_task_fixture`` already states for
    itself. Raises ``ValueError`` on any malformed shape, including invalid
    or non-UTF-8 file content, so callers only ever need to catch one
    exception type.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read eval suite {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in eval suite {path}: {exc}") from exc

    if not isinstance(data, Mapping):
        raise ValueError(f"eval suite {path} must be a YAML mapping")

    config = data.get("config")
    if not isinstance(config, Mapping):
        raise ValueError(f"eval suite {path}: 'config' must be a mapping")

    trials_per_task = _require_positive_int(config.get("trials_per_task"), "trials_per_task")
    timeout_seconds = _require_positive_int(config.get("timeout_seconds"), "timeout_seconds")
    model = _require_nonblank_str(config.get("model"), "model")
    executor = config.get("executor")  # read through, never enforced -- see module docstring

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"eval suite {path}: 'tasks' must be a non-empty list")
    for entry in tasks:
        _require_nonblank_str(entry, "each 'tasks' entry")

    mcp_mocks = data.get("mcp_mocks")
    if isinstance(mcp_mocks, list) and mcp_mocks:
        raise ValueError(
            f"eval suite {path}: mcp_mocks is not supported -- this runner grants zero tools "
            '(--tools "" in gitapex_run_ablation.py), so a declared mock has nothing to attach to'
        )

    return {
        "name": data.get("name"),
        "skill": data.get("skill"),
        "config": {
            "trials_per_task": trials_per_task,
            "timeout_seconds": timeout_seconds,
            "model": model,
            "executor": executor,
        },
        "tasks": tasks,
    }


def discover_task_fixtures(eval_yaml_path: Path, task_globs: list[str]) -> list[Path]:
    """Resolve ``task_globs`` (an ``eval.yaml``'s own ``tasks:`` list) relative
    to ``eval_yaml_path``'s own directory, deduplicated and sorted.

    Raises ``ValueError`` if the combined match set across every glob is
    empty -- a suite whose ``tasks:`` glob matches zero files must fail
    loudly, never silently report an empty pass (issue #1132's own ACM row 2
    residual-risk column).
    """
    base_dir = eval_yaml_path.parent
    matched: set[Path] = set()
    for pattern in task_globs:
        matched.update(base_dir.glob(pattern))
    if not matched:
        raise ValueError(f"eval suite {eval_yaml_path}: tasks: glob {task_globs!r} matched zero files under {base_dir}")
    return sorted(matched)


@dataclass(frozen=True)
class GraderResult:
    """One ``graders:`` entry's outcome against one trial's output."""

    name: str
    passed: bool
    detail: str


def _validate_graders_shape(graders: object) -> None:
    """Raise ``ValueError`` if ``graders`` is not a well-formed list of
    grader entries, without spending a live model call to find out --
    mirrors ``gitapex_run_ablation._validate_expected_shape``'s own dry-run
    precondition, applied to ``graders:`` instead of ``expected:``.

    Dry-runs ``run_text_grader("", entry)`` for each entry: an empty output
    text exercises exactly the same shape checks that function would
    otherwise only raise partway through grading a real, already-obtained
    trial output.
    """
    if not isinstance(graders, list):
        raise ValueError(f"'graders' must be a list, got {type(graders).__name__}")
    for entry in graders:
        run_text_grader("", entry)


def run_text_grader(output: str, grader_entry: object) -> GraderResult:
    """Grade ``output`` against one ``graders:`` entry.

    Implements exactly ``type: text`` with ``contains``/``not_contains``
    (case-insensitive per ``.gitapex/waza-task.schema.json``'s own
    ``textGraderConfig`` description -- delegated to
    ``gitapex_score_contract.score``'s existing ``output_icontains``/
    ``output_not_icontains`` keys, a different, case-insensitive contract
    from that module's own case-sensitive ``output_contains``/
    ``output_not_contains``). Any other declared ``type``, or any other
    ``text``-config key (``contains_cs``, ``not_contains_cs``,
    ``regex_match``, ``regex_not_match`` -- none used by any committed
    fixture today), raises ``ValueError`` rather than being silently
    ignored -- see module docstring's "Grader coverage" section.
    """
    if not isinstance(grader_entry, Mapping):
        raise ValueError(f"grader entry must be a mapping, got {type(grader_entry).__name__}")
    name = grader_entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"grader entry missing 'name': {grader_entry!r}")
    grader_type = grader_entry.get("type", "text")
    if grader_type != "text":
        raise ValueError(f"grader {name!r}: unsupported grader type {grader_type!r} (only 'text' is implemented)")
    config = grader_entry.get("config")
    if not isinstance(config, Mapping):
        raise ValueError(f"grader {name!r}: grader 'config' must be a mapping, got {type(config).__name__}")
    unsupported = [key for key in config if key not in _SUPPORTED_TEXT_CONFIG_KEYS]
    if unsupported:
        raise ValueError(
            f"grader {name!r}: unsupported text grader config key(s) {sorted(unsupported)!r} "
            f"(only {_SUPPORTED_TEXT_CONFIG_KEYS} are implemented)"
        )

    assertions = {}
    if "contains" in config:
        assertions["output_icontains"] = config["contains"]
    if "not_contains" in config:
        assertions["output_not_icontains"] = config["not_contains"]
    score = gitapex_score_contract.score(output, assertions) if assertions else 1.0
    passed = score >= 1.0
    return GraderResult(name=name, passed=passed, detail=f"score={score:.6f}")


@dataclass(frozen=True)
class SuiteResult:
    """A whole suite run's aggregate: one entry per fixture in ``scores``,
    sorted by ``fixture_id`` (see module docstring's "Aggregate output
    shape" section)."""

    model_id: str
    n_fixtures: int
    mean_score: float
    scores: list[dict[str, Any]]


def run_eval_suite(
    eval_yaml_path: Path,
    skill_md: Path,
    *,
    executor: gitapex_run_ablation.Executor,
    model_cli: str = DEFAULT_MODEL_CLI,
) -> SuiteResult:
    """Run every task fixture ``eval_yaml_path``'s own ``tasks:`` glob
    matches, ``trials_per_task`` times each, skill always injected (see
    module docstring's own "single-arm" note), scored via both
    ``expected.*`` and any declared ``graders:``, aggregated into a
    ``SuiteResult``.

    All shape validation (suite load, fixture load, every fixture's
    ``expected``/``graders`` shape) happens before the first trial of any
    fixture dispatches -- a malformed fixture three suites in must not have
    let the first two already spend real executor calls.
    """
    suite = load_eval_suite(eval_yaml_path)
    fixture_paths = discover_task_fixtures(eval_yaml_path, suite["tasks"])
    fixtures = [gitapex_run_ablation.load_task_fixture(p) for p in fixture_paths]
    for fixture in fixtures:
        gitapex_run_ablation._validate_expected_shape(fixture["expected"])
        _validate_graders_shape(fixture["graders"])

    trials_per_task = suite["config"]["trials_per_task"]
    timeout_seconds = suite["config"]["timeout_seconds"]
    model = suite["config"]["model"]

    scores: list[dict[str, Any]] = []
    for fixture in fixtures:
        trials: list[dict[str, Any]] = []
        for trial_index in range(trials_per_task):
            argv = gitapex_run_ablation.build_command(model_cli, fixture["prompt"], skill_md, model=model)
            output = executor(argv, timeout_seconds)
            substring_score = gitapex_score_contract.score(output, fixture["expected"])
            grader_results = [run_text_grader(output, entry) for entry in fixture["graders"]]
            trial_score = statistics.mean([substring_score] + [1.0 if gr.passed else 0.0 for gr in grader_results])
            trials.append(
                {
                    "trial_index": trial_index,
                    "score": trial_score,
                    "grader_results": [
                        {"name": gr.name, "passed": gr.passed, "detail": gr.detail} for gr in grader_results
                    ],
                }
            )
        fixture_score = statistics.mean(trial["score"] for trial in trials)
        scores.append({"fixture_id": fixture["id"], "score": fixture_score, "trials": trials})

    scores.sort(key=lambda entry: entry["fixture_id"])
    mean_score = statistics.mean(entry["score"] for entry in scores)
    return SuiteResult(model_id=model, n_fixtures=len(scores), mean_score=mean_score, scores=scores)


def to_eval_scores_json(result: SuiteResult) -> dict[str, Any]:
    """Serialize ``result`` into the ``eval-scores.schema.json``-compatible
    shape (see module docstring's "Aggregate output shape" section)."""
    return {
        "model_id": result.model_id,
        "n_fixtures": result.n_fixtures,
        "mean_score": result.mean_score,
        "scores": result.scores,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run every task fixture an eval.yaml's tasks: glob matches, "
        "trials_per_task times each, and print the aggregate result as JSON."
    )
    parser.add_argument("--eval-yaml", required=True, type=Path, help="Path to an evals/<skill>/eval.yaml.")
    parser.add_argument("--skill-md", required=True, type=Path, help="Path to the skill's SKILL.md.")
    parser.add_argument("--model-cli", default=DEFAULT_MODEL_CLI)
    parser.add_argument("-o", "--output", type=Path, help="Write the aggregate JSON here; stdout when omitted.")
    args = parser.parse_args(argv)

    if not args.skill_md.is_file():
        print(f"error: skill file not found: {args.skill_md}", file=sys.stderr)
        return 2

    try:
        result = run_eval_suite(
            args.eval_yaml,
            args.skill_md,
            executor=subprocess_executor,
            model_cli=args.model_cli,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(to_eval_scores_json(result), sort_keys=True, indent=2)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

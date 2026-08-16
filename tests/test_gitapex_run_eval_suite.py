"""Tests for evals/scripts/gitapex_run_eval_suite.py (issue #1132).

Same stub-executor discipline as test_gitapex_run_ablation.py: a live model run
is out of scope for this environment (no credentials), matching issue #1132's
own Constraints section and gitapex_run_ablation.py's own established precedent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import gitapex_run_eval_suite
import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_SCORES_SCHEMA_PATH = REPO_ROOT / "skills" / "scorer-gated-skill-edits" / "references" / "eval-scores.schema.json"

BASE_EVAL_YAML = """\
name: demo-eval
skill: demo-skill
config:
  trials_per_task: 2
  timeout_seconds: 120
  model: claude-sonnet-5
  executor: copilot-sdk
tasks:
  - "tasks/*.yaml"
"""

TASK_A_TEXT = """\
id: task-a
inputs:
  prompt: Say ok.
expected:
  output_contains: ["ok"]
"""

TASK_B_TEXT = """\
id: task-b
inputs:
  prompt: Say ok.
expected:
  output_contains: ["ok"]
graders:
  - name: has-ok
    type: text
    config:
      contains: ["OK"]
"""


def _write_suite(tmp_path: Path, *, eval_yaml_text: str = BASE_EVAL_YAML, tasks: dict[str, str] | None = None) -> Path:
    eval_yaml = tmp_path / "eval.yaml"
    eval_yaml.write_text(eval_yaml_text, encoding="utf-8")
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    for name, text in (tasks or {"a.yaml": TASK_A_TEXT}).items():
        (tasks_dir / name).write_text(text, encoding="utf-8")
    return eval_yaml


# ---------------------------------------------------------------------------
# _ensure_importable
# ---------------------------------------------------------------------------


def test_ensure_importable_inserts_directory_not_already_on_path(tmp_path: Path, monkeypatch):
    directory = tmp_path / "not-on-path-yet"
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(directory)])
    assert str(directory) not in sys.path

    gitapex_run_eval_suite._ensure_importable(directory)

    assert sys.path[0] == str(directory)


def test_ensure_importable_is_a_noop_when_already_on_path(monkeypatch):
    already_present = sys.path[len(sys.path) // 2]  # any real, already-present entry
    before = list(sys.path)

    gitapex_run_eval_suite._ensure_importable(Path(already_present))

    assert sys.path == before  # unchanged -- not re-inserted or duplicated


# ---------------------------------------------------------------------------
# load_eval_suite
# ---------------------------------------------------------------------------


def test_load_eval_suite_happy_path(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path)
    suite = gitapex_run_eval_suite.load_eval_suite(eval_yaml)
    assert suite["name"] == "demo-eval"
    assert suite["skill"] == "demo-skill"
    assert suite["config"]["trials_per_task"] == 2
    assert suite["config"]["timeout_seconds"] == 120
    assert suite["config"]["model"] == "claude-sonnet-5"
    assert suite["tasks"] == ["tasks/*.yaml"]


def test_load_eval_suite_rejects_non_mapping(tmp_path: Path):
    eval_yaml = tmp_path / "eval.yaml"
    eval_yaml.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


def test_load_eval_suite_rejects_missing_config(tmp_path: Path):
    eval_yaml = tmp_path / "eval.yaml"
    eval_yaml.write_text("name: x\nskill: y\ntasks: ['tasks/*.yaml']\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'config' must be a mapping"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


def test_load_eval_suite_rejects_missing_tasks(tmp_path: Path):
    eval_yaml = tmp_path / "eval.yaml"
    eval_yaml.write_text(
        "name: x\nskill: y\nconfig:\n  trials_per_task: 1\n  timeout_seconds: 60\n  model: claude-sonnet-5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'tasks' must be a non-empty list"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


def test_load_eval_suite_rejects_empty_tasks_list(tmp_path: Path):
    eval_yaml = tmp_path / "eval.yaml"
    eval_yaml.write_text(
        "name: x\nskill: y\nconfig:\n  trials_per_task: 1\n  timeout_seconds: 60\n  model: claude-sonnet-5\ntasks: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'tasks' must be a non-empty list"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


@pytest.mark.parametrize("trials_per_task", [0, -1])
def test_load_eval_suite_rejects_non_positive_trials_per_task(tmp_path: Path, trials_per_task: int):
    text = BASE_EVAL_YAML.replace("trials_per_task: 2", f"trials_per_task: {trials_per_task}")
    eval_yaml = _write_suite(tmp_path, eval_yaml_text=text)
    with pytest.raises(ValueError, match="trials_per_task must be a positive integer"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


@pytest.mark.parametrize("timeout_seconds", [0, -5])
def test_load_eval_suite_rejects_non_positive_timeout(tmp_path: Path, timeout_seconds: int):
    text = BASE_EVAL_YAML.replace("timeout_seconds: 120", f"timeout_seconds: {timeout_seconds}")
    eval_yaml = _write_suite(tmp_path, eval_yaml_text=text)
    with pytest.raises(ValueError, match="timeout_seconds must be a positive integer"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


@pytest.mark.parametrize("model_line", ["model: ''", "model: '   '"])
def test_load_eval_suite_rejects_blank_model(tmp_path: Path, model_line: str):
    text = BASE_EVAL_YAML.replace("model: claude-sonnet-5", model_line)
    eval_yaml = _write_suite(tmp_path, eval_yaml_text=text)
    with pytest.raises(ValueError, match="model must be a non-empty string"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


def test_load_eval_suite_rejects_non_empty_mcp_mocks(tmp_path: Path):
    # mcp_mocks declares a mocked MCP server for a run to use -- but this
    # runner grants zero tools (--tools "" in gitapex_run_ablation.py), so
    # there is nothing for a declared mock to attach to. Silently ignoring
    # it would let a fixture score as if its mock applied when it never ran.
    text = (
        BASE_EVAL_YAML + "mcp_mocks:\n  - name: fake\n    tools:\n      t:\n        responses:\n          - return: 1\n"
    )
    eval_yaml = _write_suite(tmp_path, eval_yaml_text=text)
    with pytest.raises(ValueError, match="mcp_mocks is not supported"):
        gitapex_run_eval_suite.load_eval_suite(eval_yaml)


def test_load_eval_suite_accepts_empty_mcp_mocks(tmp_path: Path):
    text = BASE_EVAL_YAML + "mcp_mocks: []\n"
    eval_yaml = _write_suite(tmp_path, eval_yaml_text=text)
    gitapex_run_eval_suite.load_eval_suite(eval_yaml)  # no raise


def test_load_eval_suite_records_executor_field_without_enforcing_it(tmp_path: Path):
    # Every real committed eval.yaml declares executor: copilot-sdk (waza's
    # own concept); this runner always dispatches through the Claude Code
    # CLI path regardless (this session's own resolved execution-backend
    # scope decision) -- the field is read through, never rejected, so a
    # real committed suite still loads.
    eval_yaml = _write_suite(tmp_path)
    suite = gitapex_run_eval_suite.load_eval_suite(eval_yaml)
    assert suite["config"]["executor"] == "copilot-sdk"


# ---------------------------------------------------------------------------
# discover_task_fixtures
# ---------------------------------------------------------------------------


def test_discover_task_fixtures_happy_path(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT, "b.yaml": TASK_B_TEXT})
    fixtures = gitapex_run_eval_suite.discover_task_fixtures(eval_yaml, ["tasks/*.yaml"])
    assert [p.name for p in fixtures] == ["a.yaml", "b.yaml"]


def test_discover_task_fixtures_rejects_zero_matches(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path)
    with pytest.raises(ValueError, match="matched zero files"):
        gitapex_run_eval_suite.discover_task_fixtures(eval_yaml, ["tasks/no-such-*.yaml"])


def test_discover_task_fixtures_dedupes_overlapping_globs(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT})
    fixtures = gitapex_run_eval_suite.discover_task_fixtures(eval_yaml, ["tasks/*.yaml", "tasks/a.*"])
    assert [p.name for p in fixtures] == ["a.yaml"]


# ---------------------------------------------------------------------------
# run_text_grader
# ---------------------------------------------------------------------------


def _text_grader(config: dict) -> dict:
    return {"name": "g", "type": "text", "config": config}


def test_run_text_grader_contains_pass():
    result = gitapex_run_eval_suite.run_text_grader("the OK is here", _text_grader({"contains": ["ok"]}))
    assert result.passed is True


def test_run_text_grader_contains_fail():
    result = gitapex_run_eval_suite.run_text_grader("nothing here", _text_grader({"contains": ["ok"]}))
    assert result.passed is False


def test_run_text_grader_not_contains_pass():
    result = gitapex_run_eval_suite.run_text_grader("clean output", _text_grader({"not_contains": ["leaked"]}))
    assert result.passed is True


def test_run_text_grader_not_contains_fail():
    result = gitapex_run_eval_suite.run_text_grader("this LEAKED info", _text_grader({"not_contains": ["leaked"]}))
    assert result.passed is False


def test_run_text_grader_is_case_insensitive():
    # waza-task.schema.json's own textGraderConfig description: contains/
    # not_contains are case-insensitive -- a different contract from
    # gitapex_score_contract's own case-sensitive output_contains.
    result = gitapex_run_eval_suite.run_text_grader("Result: OK", _text_grader({"contains": ["ok"]}))
    assert result.passed is True


def test_run_text_grader_rejects_unsupported_type():
    with pytest.raises(ValueError, match="unsupported grader type"):
        gitapex_run_eval_suite.run_text_grader("x", {"name": "g", "type": "program", "config": {"command": "x"}})


@pytest.mark.parametrize("key", ["contains_cs", "not_contains_cs", "regex_match", "regex_not_match"])
def test_run_text_grader_rejects_unsupported_config_key(key: str):
    with pytest.raises(ValueError, match="unsupported text grader config key"):
        gitapex_run_eval_suite.run_text_grader("x", _text_grader({key: ["x"]}))


def test_run_text_grader_rejects_non_mapping_entry():
    with pytest.raises(ValueError, match="grader entry must be a mapping"):
        gitapex_run_eval_suite.run_text_grader("x", "not-a-mapping")


def test_run_text_grader_rejects_missing_name():
    with pytest.raises(ValueError, match="grader entry missing 'name'"):
        gitapex_run_eval_suite.run_text_grader("x", {"type": "text", "config": {"contains": ["x"]}})


def test_run_text_grader_rejects_non_mapping_config():
    with pytest.raises(ValueError, match="grader 'config' must be a mapping"):
        gitapex_run_eval_suite.run_text_grader("x", {"name": "g", "type": "text", "config": "nope"})


# ---------------------------------------------------------------------------
# _validate_graders_shape (pre-flight, before any live call)
# ---------------------------------------------------------------------------


def test_validate_graders_shape_accepts_well_formed_list():
    gitapex_run_eval_suite._validate_graders_shape([_text_grader({"contains": ["a"]})])  # no raise


def test_validate_graders_shape_rejects_non_list():
    with pytest.raises(ValueError, match="'graders' must be a list"):
        gitapex_run_eval_suite._validate_graders_shape("not-a-list")


def test_validate_graders_shape_rejects_malformed_entry_without_calling_executor(tmp_path: Path):
    # Mirrors gitapex_run_ablation._validate_expected_shape's own "fail before
    # any live model call" precondition.
    eval_yaml = _write_suite(
        tmp_path,
        tasks={"a.yaml": TASK_A_TEXT + "graders:\n  - not-a-mapping\n"},
    )
    executor = _RecordingExecutor([])
    with pytest.raises(ValueError, match="grader entry must be a mapping"):
        gitapex_run_eval_suite.run_eval_suite(eval_yaml, tmp_path / "SKILL.md", executor=executor, model_cli="claude")
    assert executor.calls == []


# ---------------------------------------------------------------------------
# run_eval_suite (hand-written recording stub executor)
# ---------------------------------------------------------------------------


class _RecordingExecutor:
    """Stand-in for a live model CLI, same interface as
    test_gitapex_run_ablation.py's own _RecordingExecutor: records every
    (argv, timeout) and returns the pre-canned outputs in order. Unlike that
    one, it cycles once the list runs out -- so a single canned output covers
    every trial of a multi-trial, multi-fixture suite -- and returns "" when
    no outputs were given at all (the "must not dispatch" tests)."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, argv, timeout) -> str:
        self.calls.append((list(argv), timeout))
        index = len(self.calls) - 1
        return self._outputs[index % len(self._outputs)] if self._outputs else ""


def _skill_md(tmp_path: Path) -> Path:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    return skill_md


def test_run_eval_suite_dispatches_trials_per_task_times_per_fixture(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT, "b.yaml": TASK_A_TEXT})
    executor = _RecordingExecutor(["ok output"])

    gitapex_run_eval_suite.run_eval_suite(eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude")

    # 2 fixtures * trials_per_task=2 (BASE_EVAL_YAML) = 4 dispatches.
    assert len(executor.calls) == 4


def test_run_eval_suite_forwards_configured_timeout_to_every_dispatch(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path)
    executor = _RecordingExecutor(["ok output"])

    gitapex_run_eval_suite.run_eval_suite(eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude")

    assert all(timeout == 120 for _argv, timeout in executor.calls)  # BASE_EVAL_YAML's timeout_seconds


def test_run_eval_suite_forwards_configured_model_to_every_dispatch(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path)
    executor = _RecordingExecutor(["ok output"])

    gitapex_run_eval_suite.run_eval_suite(eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude")

    for argv, _timeout in executor.calls:
        assert argv[argv.index("--model") + 1] == "claude-sonnet-5"  # BASE_EVAL_YAML's config.model


def test_run_eval_suite_always_injects_skill_single_arm(tmp_path: Path):
    # Single-arm: skill always present, matching what `waza run <skill>` did
    # in CI -- NOT gitapex_run_ablation()'s own separate with/without-skill
    # comparison (unmodified, untouched by this new runner).
    eval_yaml = _write_suite(tmp_path)
    skill_md = _skill_md(tmp_path)
    executor = _RecordingExecutor(["ok output"])

    gitapex_run_eval_suite.run_eval_suite(eval_yaml, skill_md, executor=executor, model_cli="claude")

    for argv, _timeout in executor.calls:
        assert "--append-system-prompt-file" in argv
        assert str(skill_md) in argv


def test_run_eval_suite_score_with_no_graders_is_substring_score_alone(tmp_path: Path):
    eval_yaml = _write_suite(
        tmp_path,
        eval_yaml_text=BASE_EVAL_YAML.replace("trials_per_task: 2", "trials_per_task: 1"),
        tasks={"a.yaml": TASK_A_TEXT},
    )
    executor = _RecordingExecutor(["ok output"])  # satisfies expected.output_contains: ["ok"]

    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    assert result.scores[0]["score"] == pytest.approx(1.0)


def test_run_eval_suite_score_averages_substring_and_grader_results(tmp_path: Path):
    # TASK_B_TEXT: expected.output_contains: ["ok"] (satisfied, score 1.0)
    # AND one graders: entry (contains: ["OK"], also satisfied, passed=True)
    # -> trial_score = mean([1.0, 1.0]) = 1.0.
    eval_yaml = _write_suite(
        tmp_path,
        eval_yaml_text=BASE_EVAL_YAML.replace("trials_per_task: 2", "trials_per_task: 1"),
        tasks={"b.yaml": TASK_B_TEXT},
    )
    executor = _RecordingExecutor(["ok output"])

    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    assert result.scores[0]["score"] == pytest.approx(1.0)
    assert result.scores[0]["trials"][0]["grader_results"][0]["passed"] is True


def test_run_eval_suite_score_reflects_a_failing_grader(tmp_path: Path):
    # expected.output_contains: ["ok"] is satisfied (1.0, case-sensitive),
    # but the grader's own contains: ["OK"] (case-INSENSITIVE) is not, since
    # the output contains neither "ok" nor "OK" in any casing -- trial_score
    # = mean([1.0, 0.0]) = 0.5.
    eval_yaml = _write_suite(
        tmp_path,
        eval_yaml_text=BASE_EVAL_YAML.replace("trials_per_task: 2", "trials_per_task: 1"),
        tasks={
            "b.yaml": TASK_B_TEXT.replace(
                'expected:\n  output_contains: ["ok"]', 'expected:\n  output_contains: ["yes"]'
            )
        },
    )
    executor = _RecordingExecutor(["yes, confirmed"])  # satisfies expected but not the grader's "OK"

    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    assert result.scores[0]["score"] == pytest.approx(0.5)


def test_run_eval_suite_fixture_score_is_mean_across_trials(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT})  # BASE_EVAL_YAML's trials_per_task: 2
    executor = _RecordingExecutor(["ok output", "no match at all"])  # trial 1: 1.0, trial 2: 0.0

    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    assert result.scores[0]["score"] == pytest.approx(0.5)
    assert len(result.scores[0]["trials"]) == 2


def test_run_eval_suite_mean_score_is_mean_across_fixtures(tmp_path: Path):
    eval_yaml = _write_suite(
        tmp_path,
        eval_yaml_text=BASE_EVAL_YAML.replace("trials_per_task: 2", "trials_per_task: 1"),
        tasks={"a.yaml": TASK_A_TEXT, "b.yaml": TASK_A_TEXT.replace("task-a", "task-b")},
    )
    executor = _RecordingExecutor(["ok output", "no match"])  # fixture a: 1.0, fixture b: 0.0

    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    assert result.mean_score == pytest.approx(0.5)
    assert result.n_fixtures == 2


def test_run_eval_suite_scores_sorted_by_fixture_id_not_discovery_order(tmp_path: Path):
    # A task fixture's own declared id need not match its filename's sort
    # order -- eval-scores.schema.json's own scores[] contract requires
    # sorting by fixture_id "so two runs of the same corpus produce a
    # stable diff," independent of filesystem glob order.
    task_z_first_file = "id: zzz-last-alphabetically\ninputs:\n  prompt: hi\nexpected:\n  output_contains: ['x']\n"
    task_a_second_file = "id: aaa-first-alphabetically\ninputs:\n  prompt: hi\nexpected:\n  output_contains: ['x']\n"
    eval_yaml = _write_suite(
        tmp_path,
        eval_yaml_text=BASE_EVAL_YAML.replace("trials_per_task: 2", "trials_per_task: 1"),
        tasks={"1-first-file.yaml": task_z_first_file, "2-second-file.yaml": task_a_second_file},
    )
    executor = _RecordingExecutor(["x"])

    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    assert [s["fixture_id"] for s in result.scores] == ["aaa-first-alphabetically", "zzz-last-alphabetically"]


def test_run_eval_suite_raises_on_zero_matched_fixtures_without_calling_executor(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path, eval_yaml_text=BASE_EVAL_YAML.replace("tasks/*.yaml", "tasks/none-*.yaml"))
    executor = _RecordingExecutor([])

    with pytest.raises(ValueError, match="matched zero files"):
        gitapex_run_eval_suite.run_eval_suite(eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude")

    assert executor.calls == []


# ---------------------------------------------------------------------------
# to_eval_scores_json / eval-scores.schema.json conformance
# ---------------------------------------------------------------------------


def test_to_eval_scores_json_validates_against_the_real_schema(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT, "b.yaml": TASK_B_TEXT})
    executor = _RecordingExecutor(["ok output"])
    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    payload = gitapex_run_eval_suite.to_eval_scores_json(result)
    schema = json.loads(EVAL_SCORES_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)  # no raise


def test_to_eval_scores_json_shape(tmp_path: Path):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT})
    executor = _RecordingExecutor(["ok output"])
    result = gitapex_run_eval_suite.run_eval_suite(
        eval_yaml, _skill_md(tmp_path), executor=executor, model_cli="claude"
    )

    payload = gitapex_run_eval_suite.to_eval_scores_json(result)
    assert payload["model_id"] == "claude-sonnet-5"
    assert payload["n_fixtures"] == 1
    assert payload["scores"][0]["fixture_id"] == "task-a"
    assert "trials" in payload["scores"][0]  # additive, schema-permitted detail


# ---------------------------------------------------------------------------
# Real committed suite: evals/untrusted-input-triage/ (4 fixtures, all
# declare graders:, trials_per_task: 3) -- issue #1132's own proof method.
# ---------------------------------------------------------------------------


def test_real_untrusted_input_triage_suite_runs_every_fixture_and_grader():
    eval_yaml = REPO_ROOT / "evals" / "untrusted-input-triage" / "eval.yaml"
    skill_md = REPO_ROOT / "skills" / "untrusted-input-triage" / "SKILL.md"
    tasks_dir = eval_yaml.parent / "tasks"
    committed_fixtures = sorted(tasks_dir.glob("*.yaml"))
    committed_fixtures_with_graders = {
        yaml.safe_load(p.read_text(encoding="utf-8"))["id"]
        for p in committed_fixtures
        if "graders:" in p.read_text(encoding="utf-8")
    }
    assert committed_fixtures, "expected at least one committed fixture under evals/untrusted-input-triage/tasks/"

    # A generic stub is not tailored to satisfy every real fixture's own
    # specific expected.*/graders: assertions -- this integration test's own
    # proof (issue #1132's own stated proof method) is that every fixture
    # actually dispatches trials_per_task times and every declared grader
    # actually produces a GraderResult (never silently skipped), not that
    # every assertion passes against an untailored stub.
    executor = _RecordingExecutor(["This looks like a prompt injection attempt; refusing."])

    result = gitapex_run_eval_suite.run_eval_suite(eval_yaml, skill_md, executor=executor, model_cli="claude")

    assert result.n_fixtures == len(committed_fixtures)
    assert len(executor.calls) == len(committed_fixtures) * 3  # trials_per_task: 3
    fixtures_with_populated_graders = set()
    for score_entry in result.scores:
        assert len(score_entry["trials"]) == 3
        for trial in score_entry["trials"]:
            if trial["grader_results"]:
                fixtures_with_populated_graders.add(score_entry["fixture_id"])
    # Every fixture whose own committed YAML declares graders: must have
    # produced at least one GraderResult -- none silently skipped.
    assert committed_fixtures_with_graders <= fixtures_with_populated_graders

    payload = gitapex_run_eval_suite.to_eval_scores_json(result)
    schema = json.loads(EVAL_SCORES_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)  # no raise


# ---------------------------------------------------------------------------
# direct invocation (regression: bare-import resolution outside pytest)
# ---------------------------------------------------------------------------


def test_direct_invocation_does_not_crash_on_imports():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "evals" / "scripts" / "gitapex_run_eval_suite.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in result.stderr
    assert "usage:" in result.stdout.lower()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_success_writes_json_to_output_file(tmp_path: Path, monkeypatch):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT})
    skill_md = _skill_md(tmp_path)
    output = tmp_path / "results.json"

    executor = _RecordingExecutor(["ok output"])
    monkeypatch.setattr(gitapex_run_eval_suite, "subprocess_executor", executor)

    rc = gitapex_run_eval_suite.main(["--eval-yaml", str(eval_yaml), "--skill-md", str(skill_md), "-o", str(output)])

    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["n_fixtures"] == 1


def test_main_success_prints_json_to_stdout_when_no_output_given(tmp_path: Path, monkeypatch, capsys):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT})
    skill_md = _skill_md(tmp_path)

    executor = _RecordingExecutor(["ok output"])
    monkeypatch.setattr(gitapex_run_eval_suite, "subprocess_executor", executor)

    rc = gitapex_run_eval_suite.main(["--eval-yaml", str(eval_yaml), "--skill-md", str(skill_md)])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["n_fixtures"] == 1


def test_main_missing_eval_yaml_returns_2(tmp_path: Path, capsys):
    skill_md = _skill_md(tmp_path)
    rc = gitapex_run_eval_suite.main(["--eval-yaml", str(tmp_path / "no-such.yaml"), "--skill-md", str(skill_md)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_main_missing_skill_md_returns_2(tmp_path: Path, capsys):
    eval_yaml = _write_suite(tmp_path)
    rc = gitapex_run_eval_suite.main(["--eval-yaml", str(eval_yaml), "--skill-md", str(tmp_path / "no-such.md")])
    assert rc == 2
    assert "skill file not found" in capsys.readouterr().err


def test_main_zero_matched_fixtures_returns_2(tmp_path: Path, capsys):
    eval_yaml = _write_suite(tmp_path, eval_yaml_text=BASE_EVAL_YAML.replace("tasks/*.yaml", "tasks/none-*.yaml"))
    skill_md = _skill_md(tmp_path)
    rc = gitapex_run_eval_suite.main(["--eval-yaml", str(eval_yaml), "--skill-md", str(skill_md)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_main_executor_runtime_error_returns_1(tmp_path: Path, monkeypatch, capsys):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT})
    skill_md = _skill_md(tmp_path)

    def failing_executor(argv, timeout):
        raise RuntimeError("model CLI exited 1: something went wrong")

    monkeypatch.setattr(gitapex_run_eval_suite, "subprocess_executor", failing_executor)

    rc = gitapex_run_eval_suite.main(["--eval-yaml", str(eval_yaml), "--skill-md", str(skill_md)])

    assert rc == 1
    assert "something went wrong" in capsys.readouterr().err


def test_main_executor_timeout_returns_1(tmp_path: Path, monkeypatch, capsys):
    eval_yaml = _write_suite(tmp_path, tasks={"a.yaml": TASK_A_TEXT})
    skill_md = _skill_md(tmp_path)

    def timing_out_executor(argv, timeout):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(gitapex_run_eval_suite, "subprocess_executor", timing_out_executor)

    rc = gitapex_run_eval_suite.main(["--eval-yaml", str(eval_yaml), "--skill-md", str(skill_md)])

    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_default_model_cli(tmp_path: Path):
    assert gitapex_run_eval_suite.DEFAULT_MODEL_CLI == "claude"

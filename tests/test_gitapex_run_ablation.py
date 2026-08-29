"""Tests for evals/scripts/gitapex_run_ablation.py (issue #583).

The stub-executor tests here are the concrete stand-in for issue #583's own
ACM proof method ("run it against one already-committed task fixture and
confirm it produces two distinct, inspectable outputs") -- a live model run
is out of scope for this environment (no credentials), which the issue's
own Constraints section explicitly pre-authorizes.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import gitapex_run_ablation
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_FIXTURE_TEXT = """\
id: demo-task
name: Demo task
description: A demo fixture for gitapex_run_ablation tests.
tags:
  - demo
inputs:
  prompt: |
    Say the magic word.
expected:
  output_contains:
    - magic-word-present
"""


# ---------------------------------------------------------------------------
# load_task_fixture
# ---------------------------------------------------------------------------


def test_load_task_fixture_happy_path(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(BASE_FIXTURE_TEXT, encoding="utf-8")
    fixture = gitapex_run_ablation.load_task_fixture(p)
    assert fixture == {
        "id": "demo-task",
        "prompt": "Say the magic word.\n",
        "expected": {"output_contains": ["magic-word-present"]},
        "graders": [],
    }


def test_load_task_fixture_returns_graders_when_present(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(
        BASE_FIXTURE_TEXT + "graders:\n  - name: check\n    type: text\n    config:\n      contains: [ok]\n",
        encoding="utf-8",
    )
    fixture = gitapex_run_ablation.load_task_fixture(p)
    assert fixture["graders"] == [{"name": "check", "type": "text", "config": {"contains": ["ok"]}}]


def test_load_task_fixture_rejects_non_list_graders(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(BASE_FIXTURE_TEXT + "graders: not-a-list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'graders' must be a list"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_non_mapping(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_missing_id(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text("inputs:\n  prompt: hi\nexpected:\n  output_contains: [a]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="id must be a non-empty string"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_non_string_id(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(
        "id: 123\ninputs:\n  prompt: hi\nexpected:\n  output_contains: [a]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id must be a non-empty string"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_blank_id(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(
        "id: '   '\ninputs:\n  prompt: hi\nexpected:\n  output_contains: [a]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id must be a non-empty string"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_missing_inputs(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text("id: x\nexpected:\n  output_contains: [a]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'inputs' must be a mapping"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_non_mapping_inputs(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(
        "id: x\ninputs: not-a-mapping\nexpected:\n  output_contains: [a]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'inputs' must be a mapping"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_missing_prompt(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(
        "id: x\ninputs:\n  other: y\nexpected:\n  output_contains: [a]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"inputs\.prompt must be a non-empty string"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_blank_prompt(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(
        "id: x\ninputs:\n  prompt: '   '\nexpected:\n  output_contains: [a]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"inputs\.prompt must be a non-empty string"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_padded_id(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text(
        "id: ' padded '\ninputs:\n  prompt: hi\nexpected:\n  output_contains: [a]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id must be unpadded"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_accepts_prompt_with_trailing_newline(tmp_path: Path):
    # Regression: inputs.prompt must NOT be unpadded-checked -- every real
    # committed fixture's `prompt: |` block scalar ends with a trailing
    # newline (YAML's default chomping), so an unpadded check here would
    # reject nearly every real fixture in this repository.
    p = tmp_path / "task.yaml"
    p.write_text(
        "id: x\ninputs:\n  prompt: |\n    hi\nexpected:\n  output_contains: [a]\n",
        encoding="utf-8",
    )
    fixture = gitapex_run_ablation.load_task_fixture(p)
    assert fixture["prompt"] == "hi\n"


def test_load_task_fixture_wraps_non_utf8_file(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_bytes(b"id: \xff\xfe bad\n")
    with pytest.raises(ValueError, match="cannot read task fixture"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_missing_expected(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text("id: x\ninputs:\n  prompt: hi\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'expected' must be a mapping"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_non_mapping_expected(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text("id: x\ninputs:\n  prompt: hi\nexpected: not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'expected' must be a mapping"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_invalid_yaml_syntax(tmp_path: Path):
    p = tmp_path / "task.yaml"
    p.write_text("id: [unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid YAML"):
        gitapex_run_ablation.load_task_fixture(p)


def test_load_task_fixture_rejects_missing_file(tmp_path: Path):
    missing = tmp_path / "does-not-exist.yaml"
    with pytest.raises(ValueError, match="cannot read task fixture"):
        gitapex_run_ablation.load_task_fixture(missing)


def test_load_task_fixture_real_committed_suite_shape():
    # Regression: every real committed task fixture must parse under this
    # script's shape assumptions, the same way test_gitapex_set_config_model.py's
    # test_real_committed_suite_shape guards against drift for eval.yaml.
    fixtures = sorted((REPO_ROOT / "evals").glob("*/tasks/*.yaml"))
    assert fixtures, "no committed task fixtures found"
    for path in fixtures:
        fixture = gitapex_run_ablation.load_task_fixture(path)
        assert fixture["id"]
        assert fixture["prompt"]
        assert isinstance(fixture["expected"], dict)


# ---------------------------------------------------------------------------
# build_command
# ---------------------------------------------------------------------------


def test_build_command_without_skill_md():
    argv = gitapex_run_ablation.build_command("claude", "hello", None)
    assert argv == ["claude", "-p", "hello", "--bare", "--tools", ""]


def test_build_command_with_skill_md():
    skill_md = Path("/tmp/SKILL.md")
    argv = gitapex_run_ablation.build_command("claude", "hello", skill_md)
    assert argv == [
        "claude",
        "-p",
        "hello",
        "--bare",
        "--tools",
        "",
        "--append-system-prompt-file",
        str(skill_md),
    ]


def test_build_command_always_includes_bare_flag():
    assert "--bare" in gitapex_run_ablation.build_command("claude", "p", None)
    assert "--bare" in gitapex_run_ablation.build_command("claude", "p", Path("x.md"))


def test_build_command_always_includes_hermetic_tools_flag():
    # Regression: --bare alone still leaves Bash and file read/edit
    # available (confirmed against a live `claude --help`) -- --tools ""
    # is the actual "no tools at all" mechanism, and must survive
    # regardless of skill_md/model.
    argv = gitapex_run_ablation.build_command("claude", "p", None)
    assert argv[argv.index("--tools") + 1] == ""
    argv_with_skill = gitapex_run_ablation.build_command("claude", "p", Path("x.md"), model="claude-sonnet-5")
    assert argv_with_skill[argv_with_skill.index("--tools") + 1] == ""


def test_build_command_with_model():
    argv = gitapex_run_ablation.build_command("claude", "hello", None, model="claude-sonnet-5")
    assert argv == ["claude", "-p", "hello", "--bare", "--tools", "", "--model", "claude-sonnet-5"]


def test_build_command_without_model_omits_flag():
    argv = gitapex_run_ablation.build_command("claude", "hello", None)
    assert "--model" not in argv


def test_build_command_with_model_and_skill_md():
    skill_md = Path("/tmp/SKILL.md")
    argv = gitapex_run_ablation.build_command("claude", "hello", skill_md, model="claude-sonnet-5")
    assert argv == [
        "claude",
        "-p",
        "hello",
        "--bare",
        "--tools",
        "",
        "--append-system-prompt-file",
        str(skill_md),
        "--model",
        "claude-sonnet-5",
    ]


def test_build_command_rejects_empty_model_cli():
    with pytest.raises(ValueError, match="non-empty"):
        gitapex_run_ablation.build_command("", "hello", None)


def test_build_command_rejects_padded_model_cli():
    with pytest.raises(ValueError, match="unpadded"):
        gitapex_run_ablation.build_command(" claude ", "hello", None)


# ---------------------------------------------------------------------------
# build_skill_context_file (issue #1046)
# ---------------------------------------------------------------------------


def _skill_with_references(tmp_path: Path, *, ref_files: dict[str, str] | None = None) -> Path:
    skill_dir = tmp_path / "some-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Some skill\n\nBody text.\n", encoding="utf-8")
    if ref_files:
        refs_dir = skill_dir / "references"
        refs_dir.mkdir()
        for name, content in ref_files.items():
            (refs_dir / name).write_text(content, encoding="utf-8")
    return skill_md


def test_build_skill_context_file_returns_skill_md_unchanged_when_flag_off(tmp_path: Path):
    skill_md = _skill_with_references(tmp_path, ref_files={"rubric.md": "rubric text"})
    result = gitapex_run_ablation.build_skill_context_file(skill_md, include_references=False)
    assert result == skill_md


def test_build_skill_context_file_returns_skill_md_unchanged_when_no_references_dir(tmp_path: Path):
    skill_md = _skill_with_references(tmp_path, ref_files=None)
    result = gitapex_run_ablation.build_skill_context_file(skill_md, include_references=True)
    assert result == skill_md


def test_build_skill_context_file_returns_skill_md_unchanged_when_references_dir_empty(tmp_path: Path):
    skill_md = _skill_with_references(tmp_path, ref_files=None)
    (skill_md.parent / "references").mkdir()
    result = gitapex_run_ablation.build_skill_context_file(skill_md, include_references=True)
    assert result == skill_md


def test_build_skill_context_file_concatenates_skill_and_references(tmp_path: Path):
    skill_md = _skill_with_references(
        tmp_path,
        ref_files={"rubric.md": "rubric contents here", "other.md": "other reference contents"},
    )
    result = gitapex_run_ablation.build_skill_context_file(skill_md, include_references=True)
    try:
        assert result != skill_md
        assert result.is_file()
        combined = result.read_text(encoding="utf-8")
        assert "# Some skill" in combined
        assert "Body text." in combined
        assert "rubric contents here" in combined
        assert "other reference contents" in combined
        assert "references/rubric.md" in combined
        assert "references/other.md" in combined
        # other.md sorts before rubric.md
        assert combined.index("other reference contents") < combined.index("rubric contents here")
    finally:
        result.unlink(missing_ok=True)


def test_build_skill_context_file_wraps_non_utf8_skill_md_as_value_error(tmp_path: Path):
    # Defeat test (not merely happy-path coverage): a stray non-UTF-8 byte
    # must surface as this module's own malformed-input ValueError
    # contract, not escape as an uncaught UnicodeDecodeError.
    skill_dir = tmp_path / "some-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_bytes(b"# Some skill\n\xff\xfe bad bytes\n")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "rubric.md").write_text("fine", encoding="utf-8")

    with pytest.raises(ValueError, match="cannot read"):
        gitapex_run_ablation.build_skill_context_file(skill_md, include_references=True)


def test_build_skill_context_file_wraps_non_utf8_reference_file_as_value_error(tmp_path: Path):
    skill_md = _skill_with_references(tmp_path, ref_files={"rubric.md": "fine"})
    (skill_md.parent / "references" / "bad.md").write_bytes(b"\xff\xfe bad bytes")

    with pytest.raises(ValueError, match="cannot read"):
        gitapex_run_ablation.build_skill_context_file(skill_md, include_references=True)


def test_build_skill_context_file_ignores_subdirectories_under_references(tmp_path: Path):
    skill_md = _skill_with_references(tmp_path, ref_files={"rubric.md": "top level ref"})
    nested_dir = skill_md.parent / "references" / "nested"
    nested_dir.mkdir()
    (nested_dir / "deep.md").write_text("nested content should not appear", encoding="utf-8")
    result = gitapex_run_ablation.build_skill_context_file(skill_md, include_references=True)
    try:
        combined = result.read_text(encoding="utf-8")
        assert "top level ref" in combined
        assert "nested content should not appear" not in combined
    finally:
        result.unlink(missing_ok=True)


def test_build_skill_context_file_cleans_up_and_wraps_write_failure(tmp_path: Path, monkeypatch):
    # Defeat test: a write failure after mkstemp already created the file
    # (e.g. a full disk) must not leak that temp file, and must surface as
    # this module's own ValueError contract, not an uncaught OSError.
    skill_md = _skill_with_references(tmp_path, ref_files={"rubric.md": "fine"})

    real_fdopen = gitapex_run_ablation.os.fdopen

    def failing_fdopen(fd, *args, **kwargs):
        handle = real_fdopen(fd, *args, **kwargs)
        handle.close()
        raise OSError("simulated disk-full failure")

    monkeypatch.setattr(gitapex_run_ablation.os, "fdopen", failing_fdopen)

    created_before = set(Path(tempfile.gettempdir()).glob("gitapex-skill-context-*"))
    with pytest.raises(ValueError, match="cannot write combined skill context"):
        gitapex_run_ablation.build_skill_context_file(skill_md, include_references=True)
    created_after = set(Path(tempfile.gettempdir()).glob("gitapex-skill-context-*"))
    assert created_after == created_before, "a failed write must not leak a temp file"


# ---------------------------------------------------------------------------
# subprocess_executor (real subprocess, no `claude` binary needed)
# ---------------------------------------------------------------------------


def test_subprocess_executor_captures_stdout_on_success():
    argv = [sys.executable, "-c", "print('hello from stand-in model cli')"]
    out = gitapex_run_ablation.subprocess_executor(argv, timeout=10)
    assert out == "hello from stand-in model cli\n"


def test_subprocess_executor_raises_runtime_error_on_nonzero_exit():
    argv = [
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('boom'); sys.exit(3)",
    ]
    with pytest.raises(RuntimeError, match="exited 3: boom"):
        gitapex_run_ablation.subprocess_executor(argv, timeout=10)


def test_subprocess_executor_propagates_timeout_expired():
    argv = [sys.executable, "-c", "import time; time.sleep(5)"]
    with pytest.raises(subprocess.TimeoutExpired):
        gitapex_run_ablation.subprocess_executor(argv, timeout=0.1)


def test_subprocess_executor_does_not_leak_ambient_credentials(monkeypatch):
    # Regression (issue #1132, hermetic-by-default): an ambient CI
    # credential set in the parent process (GITHUB_TOKEN, gh-related
    # variables, ...) must never reach the invoked model-CLI subprocess,
    # even though subprocess.run inherits the full parent environment by
    # default when no env= override is given.
    monkeypatch.setenv("GITHUB_TOKEN", "fake-secret-token-value")
    argv = [
        sys.executable,
        "-c",
        "import os, sys; sys.stdout.write('TOKEN=' + os.environ.get('GITHUB_TOKEN', '<absent>'))",
    ]
    out = gitapex_run_ablation.subprocess_executor(argv, timeout=10)
    assert out == "TOKEN=<absent>"


def test_subprocess_executor_passes_allowlisted_env_vars(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-api-key-for-test")
    argv = [
        sys.executable,
        "-c",
        "import os, sys; sys.stdout.write('KEY=' + os.environ.get('ANTHROPIC_API_KEY', '<absent>'))",
    ]
    out = gitapex_run_ablation.subprocess_executor(argv, timeout=10)
    assert out == "KEY=fake-api-key-for-test"


def test_hermetic_env_allowlist_filters_arbitrary_variables(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-secret-token-value")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-api-key-for-test")
    env = gitapex_run_ablation._hermetic_env()
    assert "GITHUB_TOKEN" not in env
    assert env.get("ANTHROPIC_API_KEY") == "fake-api-key-for-test"


def test_subprocess_executor_replaces_invalid_utf8_instead_of_raising():
    # Regression: subprocess.run(text=True) with no explicit errors= policy
    # raises UnicodeDecodeError (a ValueError subclass) on a stray non-UTF-8
    # byte in the child's stdout, which main() would then misclassify as a
    # malformed-input failure (exit 2) instead of a live-execution failure.
    argv = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(b'ok \\xff\\xfe bad bytes')",
    ]
    out = gitapex_run_ablation.subprocess_executor(argv, timeout=10)
    assert "ok " in out
    assert "\ufffd" in out  # the Unicode replacement character


# ---------------------------------------------------------------------------
# redact_executor_failure_reason (issue #1144 -- hoisted from
# gitapex_run_effectiveness_correlation.py's own former _skip_reason, same
# defeat-test discipline as that module's own test suite)
# ---------------------------------------------------------------------------


def test_redact_executor_failure_reason_redacts_runtime_error_with_embedded_stderr():
    exc = RuntimeError("model CLI exited 1: ACME_SECRET_TOKEN=sk-live-deadbeef leaked in stderr")
    reason = gitapex_run_ablation.redact_executor_failure_reason(exc)
    assert "ACME_SECRET_TOKEN" not in reason
    assert "sk-live-deadbeef" not in reason
    assert "RuntimeError" in reason


def test_redact_executor_failure_reason_redacts_timeout_expired_with_embedded_prompt():
    exc = subprocess.TimeoutExpired(cmd=["claude", "-p", "the fixture's own private prompt text"], timeout=300)
    reason = gitapex_run_ablation.redact_executor_failure_reason(exc)
    assert "private prompt text" not in reason
    assert "TimeoutExpired" in reason


def test_redact_executor_failure_reason_keeps_value_error_verbatim():
    reason = gitapex_run_ablation.redact_executor_failure_reason(
        ValueError("skill_md not found: skills/ghost/SKILL.md")
    )
    assert reason == "skill_md not found: skills/ghost/SKILL.md"


def test_redact_executor_failure_reason_keeps_os_error_verbatim():
    reason = gitapex_run_ablation.redact_executor_failure_reason(
        OSError("[Errno 2] No such file or directory: 'x.yaml'")
    )
    assert "No such file or directory" in reason


# ---------------------------------------------------------------------------
# direct invocation (regression: `import gitapex_score_contract` must resolve even
# outside pytest's own pythonpath configuration)
# ---------------------------------------------------------------------------


def test_direct_invocation_does_not_crash_on_score_contract_import():
    # Regression: gitapex_score_contract.py lives in a sibling skill's scripts/
    # directory. pyproject.toml's pythonpath entry resolves the bare
    # `import gitapex_score_contract` under pytest only -- running this script
    # exactly as its own Usage:: block documents (a real subprocess, not an
    # in-process pytest import) crashed with ModuleNotFoundError before the
    # sys.path bootstrap at the top of gitapex_run_ablation.py existed.
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "evals" / "scripts" / "gitapex_run_ablation.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in result.stderr
    assert "usage:" in result.stdout.lower()


# ---------------------------------------------------------------------------
# _validate_expected_shape / gitapex_run_ablation pre-flight validation
# ---------------------------------------------------------------------------


def test_validate_expected_shape_accepts_well_formed_assertions():
    gitapex_run_ablation._validate_expected_shape({"output_contains": ["a"]})  # no raise


def test_validate_expected_shape_rejects_empty_assertion_set():
    with pytest.raises(ValueError, match="empty assertion set"):
        gitapex_run_ablation._validate_expected_shape({})


def test_validate_expected_shape_rejects_non_list_output_contains():
    with pytest.raises(ValueError, match="must be a list"):
        gitapex_run_ablation._validate_expected_shape({"output_contains": "not-a-list"})


def test_validate_expected_shape_converts_type_error_to_value_error():
    # gitapex_score_contract.score("", {"output_contains": [123]}) raises TypeError
    # (`123 in ""` is not a valid `in` comparison) -- this must surface as
    # ValueError like every other shape defect this function catches.
    with pytest.raises(ValueError, match="'expected' assertions are malformed"):
        gitapex_run_ablation._validate_expected_shape({"output_contains": [123]})


@pytest.mark.parametrize("key", ["output_icontains", "output_not_icontains"])
def test_validate_expected_shape_converts_attribute_error_to_value_error(key: str):
    # Regression: the case-INSENSITIVE keys reach the same malformed entry
    # through str.casefold() instead of `in`, so a non-string substring (an
    # unquoted YAML year/version/issue number) raises AttributeError, not
    # TypeError -- which escaped this function's single-ValueError contract
    # and surfaced as an uncaught traceback in both runners' main().
    with pytest.raises(ValueError, match="'expected' assertions are malformed"):
        gitapex_run_ablation._validate_expected_shape({key: [2024]})


def test_run_ablation_rejects_empty_expected_without_calling_executor(tmp_path: Path):
    # This is the concrete fix for the cross-verified finding: a malformed
    # `expected` block must fail before either live model call, not after
    # both have already run and spent real cost.
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor([])

    fixture = {"id": "x", "prompt": "hi", "expected": {}}
    with pytest.raises(ValueError, match="empty assertion set"):
        gitapex_run_ablation.gitapex_run_ablation(fixture, skill_md, executor=executor, model_cli="claude")

    assert executor.calls == []


def test_run_ablation_rejects_malformed_expected_without_calling_executor(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor([])

    fixture = {"id": "x", "prompt": "hi", "expected": {"output_contains": "not-a-list"}}
    with pytest.raises(ValueError, match="must be a list"):
        gitapex_run_ablation.gitapex_run_ablation(fixture, skill_md, executor=executor, model_cli="claude")

    assert executor.calls == []


# ---------------------------------------------------------------------------
# gitapex_run_ablation (hand-written recording stub executor)
# ---------------------------------------------------------------------------


class _RecordingExecutor:
    """Stand-in for a live model CLI: returns pre-canned output per call and
    records every (argv, timeout) it was invoked with, so tests can assert on
    exactly what gitapex_run_ablation asked it to run without a real model or
    credentials."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, argv, timeout) -> str:
        self.calls.append((list(argv), timeout))
        return self._outputs[len(self.calls) - 1]


def _demo_fixture() -> dict:
    return {
        "id": "demo-task",
        "prompt": "Say the magic word.",
        "expected": {"output_contains": ["magic-word-present"]},
    }


def test_run_ablation_calls_executor_exactly_twice_with_and_without_skill_flag(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])

    gitapex_run_ablation.gitapex_run_ablation(
        _demo_fixture(), skill_md, executor=executor, model_cli="claude", timeout=42
    )

    assert len(executor.calls) == 2
    first_argv, first_timeout = executor.calls[0]
    second_argv, second_timeout = executor.calls[1]
    assert "--append-system-prompt-file" in first_argv
    assert str(skill_md) in first_argv
    assert "--append-system-prompt-file" not in second_argv
    assert first_timeout == 42
    assert second_timeout == 42


def test_run_ablation_computes_distinct_scores_from_stub_outputs(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])

    result = gitapex_run_ablation.gitapex_run_ablation(_demo_fixture(), skill_md, executor=executor, model_cli="claude")

    assert result.with_skill_score == 1.0
    assert result.without_skill_score == 0.0


def test_run_ablation_delta_is_with_minus_without(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])

    result = gitapex_run_ablation.gitapex_run_ablation(_demo_fixture(), skill_md, executor=executor, model_cli="claude")

    assert result.delta == pytest.approx(1.0)
    assert result.delta == result.with_skill_score - result.without_skill_score


def test_run_ablation_preserves_raw_outputs_verbatim(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])

    result = gitapex_run_ablation.gitapex_run_ablation(_demo_fixture(), skill_md, executor=executor, model_cli="claude")

    assert result.with_skill_output == "magic-word-present here"
    assert result.without_skill_output == "no magic here"


def test_run_ablation_task_id_comes_from_fixture(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])

    result = gitapex_run_ablation.gitapex_run_ablation(_demo_fixture(), skill_md, executor=executor, model_cli="claude")

    assert result.task_id == "demo-task"


def test_run_ablation_rejects_invalid_model_cli(tmp_path: Path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor(["a", "b"])

    with pytest.raises(ValueError, match="non-empty"):
        gitapex_run_ablation.gitapex_run_ablation(_demo_fixture(), skill_md, executor=executor, model_cli="")


# ---------------------------------------------------------------------------
# gitapex_run_ablation + include_references (issue #1046)
# ---------------------------------------------------------------------------


def test_run_ablation_include_references_injects_combined_context_and_cleans_up(tmp_path: Path):
    skill_dir = tmp_path / "some-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Some skill\n", encoding="utf-8")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "rubric.md").write_text("distinctive-rubric-marker", encoding="utf-8")

    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])

    gitapex_run_ablation.gitapex_run_ablation(
        _demo_fixture(), skill_md, executor=executor, model_cli="claude", include_references=True
    )

    first_argv, _ = executor.calls[0]
    context_index = first_argv.index("--append-system-prompt-file") + 1
    context_path = Path(first_argv[context_index])
    assert context_path != skill_md
    # The temporary file must be cleaned up by the time gitapex_run_ablation returns.
    assert not context_path.exists()


def test_run_ablation_include_references_false_keeps_original_skill_md_path(tmp_path: Path):
    skill_dir = tmp_path / "some-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Some skill\n", encoding="utf-8")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "rubric.md").write_text("distinctive-rubric-marker", encoding="utf-8")

    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])

    gitapex_run_ablation.gitapex_run_ablation(
        _demo_fixture(), skill_md, executor=executor, model_cli="claude", include_references=False
    )

    first_argv, _ = executor.calls[0]
    assert str(skill_md) in first_argv


# ---------------------------------------------------------------------------
# AblationResult
# ---------------------------------------------------------------------------


def test_ablation_result_delta_property():
    result = gitapex_run_ablation.AblationResult(
        task_id="t",
        with_skill_output="a",
        without_skill_output="b",
        with_skill_score=0.75,
        without_skill_score=0.25,
    )
    assert result.delta == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def _write_demo_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "task.yaml"
    p.write_text(BASE_FIXTURE_TEXT, encoding="utf-8")
    return p


def test_main_success_prints_json(tmp_path: Path, monkeypatch, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")

    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])
    monkeypatch.setattr(gitapex_run_ablation, "subprocess_executor", executor)

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md), "--timeout", "5"])

    assert rc == 0
    out = capsys.readouterr().out
    import json

    payload = json.loads(out)
    assert payload["task_id"] == "demo-task"
    assert payload["with_skill_score"] == 1.0
    assert payload["without_skill_score"] == 0.0
    assert payload["delta"] == 1.0
    assert payload["with_skill_output"] == "magic-word-present here"
    assert payload["without_skill_output"] == "no magic here"
    assert executor.calls[0][1] == 5


def test_main_include_references_flag_injects_combined_context(tmp_path: Path, monkeypatch, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_dir = tmp_path / "some-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "rubric.md").write_text("distinctive-rubric-marker", encoding="utf-8")

    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])
    monkeypatch.setattr(gitapex_run_ablation, "subprocess_executor", executor)

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md), "--include-references"])

    assert rc == 0
    first_argv, _ = executor.calls[0]
    context_index = first_argv.index("--append-system-prompt-file") + 1
    assert first_argv[context_index] != str(skill_md)


def test_main_without_include_references_flag_uses_skill_md_directly(tmp_path: Path, monkeypatch, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_dir = tmp_path / "some-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "rubric.md").write_text("distinctive-rubric-marker", encoding="utf-8")

    executor = _RecordingExecutor(["magic-word-present here", "no magic here"])
    monkeypatch.setattr(gitapex_run_ablation, "subprocess_executor", executor)

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md)])

    assert rc == 0
    first_argv, _ = executor.calls[0]
    assert str(skill_md) in first_argv


def test_main_missing_task_file_returns_2(tmp_path: Path, capsys):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    missing_task = tmp_path / "no-such-task.yaml"

    rc = gitapex_run_ablation.main(["--task", str(missing_task), "--skill-md", str(skill_md)])

    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_main_missing_skill_md_file_returns_2(tmp_path: Path, capsys):
    task = _write_demo_fixture(tmp_path)
    missing_skill_md = tmp_path / "no-such-skill.md"

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(missing_skill_md)])

    assert rc == 2
    assert "skill file not found" in capsys.readouterr().err


def test_main_malformed_fixture_returns_2(tmp_path: Path, capsys):
    task = tmp_path / "task.yaml"
    task.write_text("id: x\n", encoding="utf-8")  # missing inputs/expected
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md)])

    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_main_blank_model_cli_returns_2(tmp_path: Path, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md), "--model-cli", "   "])

    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_main_rejects_zero_timeout_without_launching_subprocess(tmp_path: Path, monkeypatch, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")
    executor = _RecordingExecutor([])
    monkeypatch.setattr(gitapex_run_ablation, "subprocess_executor", executor)

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md), "--timeout", "0"])

    assert rc == 2
    assert "positive" in capsys.readouterr().err
    assert executor.calls == []


def test_main_rejects_negative_timeout(tmp_path: Path, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md), "--timeout", "-5"])

    assert rc == 2
    assert "positive" in capsys.readouterr().err


def test_main_executor_runtime_error_returns_1(tmp_path: Path, monkeypatch, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")

    def failing_executor(argv, timeout):
        raise RuntimeError("model CLI exited 1: something went wrong")

    monkeypatch.setattr(gitapex_run_ablation, "subprocess_executor", failing_executor)

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md)])

    assert rc == 1
    assert "something went wrong" in capsys.readouterr().err


def test_main_executor_timeout_returns_1(tmp_path: Path, monkeypatch, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")

    def timing_out_executor(argv, timeout):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(gitapex_run_ablation, "subprocess_executor", timing_out_executor)

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md)])

    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_executor_os_error_returns_1(tmp_path: Path, monkeypatch, capsys):
    task = _write_demo_fixture(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Demo skill\n", encoding="utf-8")

    def unlaunchable_executor(argv, timeout):
        raise OSError("no such file or directory: claude")

    monkeypatch.setattr(gitapex_run_ablation, "subprocess_executor", unlaunchable_executor)

    rc = gitapex_run_ablation.main(["--task", str(task), "--skill-md", str(skill_md)])

    assert rc == 1
    assert "error:" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# module-level defaults
# ---------------------------------------------------------------------------


def test_default_constants():
    assert gitapex_run_ablation.DEFAULT_MODEL_CLI == "claude"
    assert gitapex_run_ablation.DEFAULT_TIMEOUT_SECONDS == 300

"""Tests for evals/scripts/score_semantic_rationale.py (issue #625).

The stub-executor tests here are the same kind of stand-in test_run_ablation.py
uses for issue #583's own live-credentials gap: a live model run needing a
JSON-Schema-constrained `claude -p` call is out of scope for this environment
(confirmed directly: `claude --bare -p ...` returns an authentication error
here, since ANTHROPIC_API_KEY is unset and --bare skips OAuth/keychain reads).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import score_semantic_rationale as ssr


class _RecordingExecutor:
    """Stand-in for a live model CLI: returns pre-canned stdout per call and
    records every (argv, timeout) it was invoked with -- same shape as
    test_run_ablation.py's own _RecordingExecutor."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, argv, timeout) -> str:
        self.calls.append((list(argv), timeout))
        return self._outputs[len(self.calls) - 1]


def _envelope(structured_output: dict) -> str:
    """A minimal stand-in for `claude -p --output-format json`'s envelope,
    carrying only the field this script actually reads."""
    return json.dumps({"result": "ignored", "structured_output": structured_output})


# ---------------------------------------------------------------------------
# build_extraction_command / build_comparison_command
# ---------------------------------------------------------------------------


def test_build_extraction_command_includes_bare_and_json_schema():
    argv = ssr.build_extraction_command("claude", "some text")
    assert argv[0] == "claude"
    assert "--bare" in argv
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--json-schema" in argv
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema == ssr._DECISION_RECORD_SCHEMA


def test_build_extraction_command_disables_all_tools():
    # Closed-book requirement (issue #626): --bare alone still grants
    # Bash/Read/Edit by default (confirmed against Claude Code's own
    # docs), so this call must also explicitly disable every tool.
    argv = ssr.build_extraction_command("claude", "some text")
    assert "--tools" in argv
    assert argv[argv.index("--tools") + 1] == ""


def test_build_extraction_command_embeds_the_text_in_the_prompt():
    argv = ssr.build_extraction_command("claude", "the actual source text")
    prompt = argv[argv.index("-p") + 1]
    assert "the actual source text" in prompt


def test_build_extraction_command_rejects_blank_model_cli():
    with pytest.raises(ValueError, match="model_cli must be a non-empty string"):
        ssr.build_extraction_command("   ", "text")


def test_build_comparison_command_embeds_both_records():
    candidate = {"rejected_alternative": "A", "reason": "slow", "cited_ref": "#1"}
    source = {"rejected_alternative": "A", "reason": "slow", "cited_ref": "#1"}
    argv = ssr.build_comparison_command("claude", candidate, source)
    prompt = argv[argv.index("-p") + 1]
    assert '"rejected_alternative": "A"' in prompt
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema == ssr._VERDICT_SCHEMA


def test_build_comparison_command_disables_all_tools():
    # Closed-book requirement (issue #626): the compare step is the one a
    # real Workflow-tool load test caught using the GitHub MCP tool and
    # git history mid-comparison, so this call must explicitly disable
    # every tool rather than relying on --bare's default grant.
    candidate = {"rejected_alternative": "A", "reason": "slow", "cited_ref": "#1"}
    source = {"rejected_alternative": "A", "reason": "slow", "cited_ref": "#1"}
    argv = ssr.build_comparison_command("claude", candidate, source)
    assert "--tools" in argv
    assert argv[argv.index("--tools") + 1] == ""


# ---------------------------------------------------------------------------
# _parse_structured_output
# ---------------------------------------------------------------------------


def test_parse_structured_output_happy_path():
    raw = _envelope({"a": 1})
    assert ssr._parse_structured_output(raw, step="test") == {"a": 1}


def test_parse_structured_output_rejects_invalid_json():
    with pytest.raises(ValueError, match="did not return valid JSON"):
        ssr._parse_structured_output("not json at all", step="test")


def test_parse_structured_output_rejects_missing_structured_output_field():
    with pytest.raises(ValueError, match="no 'structured_output' field"):
        ssr._parse_structured_output(json.dumps({"result": "text only"}), step="test")


# ---------------------------------------------------------------------------
# score_semantic_rationale (stub executor)
# ---------------------------------------------------------------------------


def test_score_semantic_rationale_calls_executor_exactly_three_times():
    executor = _RecordingExecutor(
        [
            _envelope({"rejected_alternative": "X", "reason": "slow", "cited_ref": "#1"}),
            _envelope({"rejected_alternative": "X", "reason": "slow", "cited_ref": "#1"}),
            _envelope(
                {
                    "rejected_alternative_match": True,
                    "reason_match": True,
                    "cited_ref_match": True,
                    "fabrication_detected": False,
                    "explanation": "agrees",
                }
            ),
        ]
    )

    verdict = ssr.score_semantic_rationale(
        "candidate text", "source text", executor=executor, timeout=42
    )

    assert len(executor.calls) == 3
    assert verdict.score == 1.0
    assert verdict.fabrication_detected is False
    for _, timeout in executor.calls:
        assert timeout == 42


def test_score_semantic_rationale_detects_partial_mismatch():
    executor = _RecordingExecutor(
        [
            _envelope({"rejected_alternative": "X", "reason": "made up reason", "cited_ref": "#1"}),
            _envelope({"rejected_alternative": "X", "reason": "actual reason", "cited_ref": "#1"}),
            _envelope(
                {
                    "rejected_alternative_match": True,
                    "reason_match": False,
                    "cited_ref_match": True,
                    "fabrication_detected": True,
                    "explanation": "the candidate's stated reason is not supported by the source",
                }
            ),
        ]
    )

    verdict = ssr.score_semantic_rationale(
        "candidate text", "source text", executor=executor
    )

    assert verdict.score == pytest.approx(2 / 3)
    assert verdict.fabrication_detected is True
    assert verdict.reason_match is False


def test_score_semantic_rationale_zero_score_does_not_double_penalize_fabrication():
    """score is the fraction of the three match fields, independent of
    fabrication_detected -- the two are reported separately (see
    SemanticVerdict.score's own docstring) rather than one collapsing into
    the other."""
    executor = _RecordingExecutor(
        [
            _envelope({"rejected_alternative": None, "reason": None, "cited_ref": None}),
            _envelope({"rejected_alternative": "X", "reason": "actual", "cited_ref": "#1"}),
            _envelope(
                {
                    "rejected_alternative_match": False,
                    "reason_match": False,
                    "cited_ref_match": False,
                    "fabrication_detected": True,
                    "explanation": "candidate cites nothing real",
                }
            ),
        ]
    )

    verdict = ssr.score_semantic_rationale("candidate text", "source text", executor=executor)

    assert verdict.score == 0.0
    assert verdict.fabrication_detected is True


# ---------------------------------------------------------------------------
# main (CLI)
# ---------------------------------------------------------------------------


def test_main_rejects_missing_candidate_file(tmp_path: Path, capsys):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    rc = ssr.main(["--candidate", str(tmp_path / "missing.txt"), "--source", str(source)])
    assert rc == 2
    assert "candidate file not found" in capsys.readouterr().err


def test_main_rejects_missing_source_file(tmp_path: Path, capsys):
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("candidate", encoding="utf-8")
    rc = ssr.main(["--candidate", str(candidate), "--source", str(tmp_path / "missing.txt")])
    assert rc == 2
    assert "source file not found" in capsys.readouterr().err


def test_main_rejects_non_positive_timeout(tmp_path: Path, capsys):
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("candidate", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    rc = ssr.main(
        ["--candidate", str(candidate), "--source", str(source), "--timeout", "0"]
    )
    assert rc == 2
    assert "--timeout must be a positive number of seconds" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# subprocess_executor (real subprocess, no `claude` binary needed) -- same
# technique as test_run_ablation.py's own subprocess_executor tests.
# ---------------------------------------------------------------------------


def test_subprocess_executor_captures_stdout_on_success():
    argv = [sys.executable, "-c", "print('hello from stand-in model cli')"]
    out = ssr.subprocess_executor(argv, timeout=10)
    assert out == "hello from stand-in model cli\n"


def test_subprocess_executor_raises_runtime_error_on_nonzero_exit():
    argv = [sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"]
    with pytest.raises(RuntimeError, match="exited 3: boom"):
        ssr.subprocess_executor(argv, timeout=10)


def test_subprocess_executor_propagates_timeout_expired():
    argv = [sys.executable, "-c", "import time; time.sleep(5)"]
    with pytest.raises(subprocess.TimeoutExpired):
        ssr.subprocess_executor(argv, timeout=0.1)


def test_subprocess_executor_replaces_invalid_utf8_instead_of_raising():
    argv = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'ok \\xff\\xfe bad bytes')"]
    out = ssr.subprocess_executor(argv, timeout=10)
    assert "ok " in out
    assert "�" in out


# ---------------------------------------------------------------------------
# main (real subprocess_executor path, model CLI faked via monkeypatched
# subprocess.run so the three-call round trip runs for real without a live
# `claude` binary or credentials)
# ---------------------------------------------------------------------------


class _FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def test_main_success_path_runs_real_subprocess_executor_three_times(tmp_path, monkeypatch, capsys):
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("candidate text", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text("source text", encoding="utf-8")

    responses = [
        _envelope({"rejected_alternative": "X", "reason": "slow", "cited_ref": "#1"}),
        _envelope({"rejected_alternative": "X", "reason": "slow", "cited_ref": "#1"}),
        _envelope(
            {
                "rejected_alternative_match": True,
                "reason_match": True,
                "cited_ref_match": True,
                "fabrication_detected": False,
                "explanation": "agrees",
            }
        ),
    ]
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return _FakeCompletedProcess(stdout=responses[len(calls) - 1])

    monkeypatch.setattr(subprocess, "run", fake_run)

    rc = ssr.main(["--candidate", str(candidate), "--source", str(source)])

    assert rc == 0
    assert len(calls) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["score"] == 1.0
    assert payload["fabrication_detected"] is False


def test_main_reports_runtime_error_from_a_failed_model_cli_call(tmp_path, monkeypatch, capsys):
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("candidate text", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text("source text", encoding="utf-8")

    def fake_run(argv, **kwargs):
        return _FakeCompletedProcess(stdout="", returncode=1, stderr="model CLI blew up")

    monkeypatch.setattr(subprocess, "run", fake_run)

    rc = ssr.main(["--candidate", str(candidate), "--source", str(source)])

    assert rc == 1
    assert "model CLI blew up" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# direct invocation (regression: `import score_contract` must resolve even
# outside pytest's own pythonpath configuration) -- mirrors
# test_run_ablation.py's own equivalent test.
# ---------------------------------------------------------------------------


def test_direct_invocation_does_not_crash_on_score_contract_import():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "evals" / "scripts" / "score_semantic_rationale.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in result.stderr
    assert "usage:" in result.stdout.lower()

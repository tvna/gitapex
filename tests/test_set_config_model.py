from pathlib import Path

import pytest
import set_config_model as scm

# A minimal eval.yaml shaped like the committed suites: a top-level config
# block carrying model, followed by another top-level key.
BASE = """\
name: demo-eval
description: Demo suite.
skill: demo
version: "0.1.0"
config:
  trials_per_task: 3
  timeout_seconds: 300
  parallel: false
  executor: copilot-sdk
  model: claude-sonnet-4.6
metrics:
  - name: demo_quality
    weight: 1.0
"""


def test_replaces_config_model_only():
    out = scm.set_config_model(BASE, "claude-opus-4.6")
    assert "  model: claude-opus-4.6\n" in out
    assert "claude-sonnet-4.6" not in out


def test_preserves_everything_else_byte_for_byte():
    out = scm.set_config_model(BASE, "claude-haiku-4.6")
    # Only the single model line differs; all other lines are untouched.
    before = BASE.splitlines()
    after = out.splitlines()
    assert len(before) == len(after)
    diffs = [(b, a) for b, a in zip(before, after, strict=True) if b != a]
    assert diffs == [("  model: claude-sonnet-4.6", "  model: claude-haiku-4.6")]


def test_preserves_indentation():
    indented = BASE.replace("  model: claude-sonnet-4.6", "    model: claude-sonnet-4.6")
    out = scm.set_config_model(indented, "m2")
    assert "    model: m2\n" in out


def test_leaves_grader_model_untouched():
    # A grader-level model outside the config block must not be rewritten.
    text = BASE + "graders:\n  - type: llm\n    model: gpt-4o-mini\n"
    out = scm.set_config_model(text, "claude-opus-4.6")
    assert "  model: claude-opus-4.6\n" in out  # config block rewritten
    assert "    model: gpt-4o-mini\n" in out  # grader model preserved


def test_missing_config_block_raises():
    with pytest.raises(ValueError, match="config:"):
        scm.set_config_model("name: x\nmetrics: []\n", "m")


def test_missing_model_in_config_raises():
    text = "config:\n  trials_per_task: 3\nmetrics: []\n"
    with pytest.raises(ValueError, match="no 'model:' line"):
        scm.set_config_model(text, "m")


def test_duplicate_config_model_raises():
    text = "config:\n  model: a\n  model: b\nmetrics: []\n"
    with pytest.raises(ValueError, match="exactly one"):
        scm.set_config_model(text, "m")


def test_empty_or_padded_model_raises():
    with pytest.raises(ValueError, match="non-empty"):
        scm.set_config_model(BASE, "")
    with pytest.raises(ValueError, match="unpadded"):
        scm.set_config_model(BASE, " spaced ")


def test_override_file_roundtrip(tmp_path: Path):
    p = tmp_path / "eval.yaml"
    p.write_text(BASE, encoding="utf-8")
    scm.override_file(p, "claude-opus-4.6")
    assert "  model: claude-opus-4.6\n" in p.read_text(encoding="utf-8")


def test_real_committed_suite_shape(tmp_path: Path):
    # Guards against drift between this tool's block-parser and the actual
    # committed eval.yaml layout: every real suite must round-trip.
    repo = Path(__file__).resolve().parents[1]
    suites = sorted((repo / "evals").glob("*/eval.yaml"))
    assert suites, "no committed eval.yaml suites found"
    for suite in suites:
        out = scm.set_config_model(suite.read_text(encoding="utf-8"), "probe-model")
        assert "  model: probe-model\n" in out


def test_config_block_tolerates_blank_and_comment_lines():
    # A blank line or a comment line inside the config: block must not be
    # mistaken for the start of the next top-level key.
    text = (
        "config:\n"
        "  trials_per_task: 3\n"
        "\n"
        "  # pinned for the matrix\n"
        "  model: claude-sonnet-4.6\n"
        "metrics:\n"
        "  - name: x\n"
    )
    out = scm.set_config_model(text, "claude-opus-4.6")
    assert "  model: claude-opus-4.6\n" in out
    assert "  # pinned for the matrix\n" in out
    assert "metrics:\n  - name: x\n" in out


def test_main_wrong_arg_count(capsys: pytest.CaptureFixture[str]):
    assert scm.main(["set_config_model.py", "only-one-arg"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_missing_file(capsys: pytest.CaptureFixture[str], tmp_path: Path):
    missing = tmp_path / "does-not-exist.yaml"
    assert scm.main(["set_config_model.py", str(missing), "m"]) == 1
    assert "not a file" in capsys.readouterr().err


def test_main_value_error_from_override(capsys: pytest.CaptureFixture[str], tmp_path: Path):
    p = tmp_path / "eval.yaml"
    p.write_text("name: x\nmetrics: []\n", encoding="utf-8")
    assert scm.main(["set_config_model.py", str(p), "m"]) == 1
    assert "error:" in capsys.readouterr().err


def test_main_non_utf8_file_fails_cleanly(capsys: pytest.CaptureFixture[str], tmp_path: Path):
    # override_file()'s own read_text() carries no try/except (waived inline,
    # exception-handler-gap: WAIVED, on that line): its only caller, main(),
    # wraps the call in except ValueError, and UnicodeDecodeError is a
    # ValueError subclass, so a non-UTF-8 eval.yaml must still exit 1 with
    # this script's own error message rather than an uncaught traceback.
    p = tmp_path / "eval.yaml"
    p.write_bytes(b"config:\n  model: \xff\xfebad\n")
    assert scm.main(["set_config_model.py", str(p), "m"]) == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert str(p) in err


def test_main_success(capsys: pytest.CaptureFixture[str], tmp_path: Path):
    p = tmp_path / "eval.yaml"
    p.write_text(BASE, encoding="utf-8")
    assert scm.main(["set_config_model.py", str(p), "claude-opus-4.6"]) == 0
    out = capsys.readouterr().out
    assert "config.model -> claude-opus-4.6" in out
    assert "  model: claude-opus-4.6\n" in p.read_text(encoding="utf-8")

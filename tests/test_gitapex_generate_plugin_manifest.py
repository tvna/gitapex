"""Tests for the .claude-plugin/plugin.json generator
(.github/scripts/gitapex_generate_plugin_manifest.py).

Issue #1028. The final test is the drift check itself: regenerating
into memory from the real repository-root plugin.json must produce exactly
the committed .claude-plugin/plugin.json -- the mirror this migration
introduces, replacing .claude-plugin/plugin.json as the plugin-identity
single source of truth (see that script's own module docstring). The rest
unit-test each layer: $schema-stripping/key-order preservation, rendering,
and --check-mode drift detection, following the same fixture style as
tests/test_gitapex_generate_skill_eval_status.py.
"""

from __future__ import annotations

import json
import pathlib

import gitapex_generate_plugin_manifest as generator
import pytest

# ---------------------------------------------------------------------------
# strip_schema_key
# ---------------------------------------------------------------------------


def test_strip_schema_key_removes_schema_key() -> None:
    source_text = json.dumps({"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "foo"})
    assert generator.strip_schema_key(source_text) == {"name": "foo"}


def test_strip_schema_key_preserves_remaining_key_order() -> None:
    source_text = '{"$schema": "x", "c": 1, "a": 2, "b": 3}'
    assert list(generator.strip_schema_key(source_text).keys()) == ["c", "a", "b"]


def test_strip_schema_key_missing_schema_key_is_a_no_op() -> None:
    source_text = json.dumps({"name": "foo"})
    assert generator.strip_schema_key(source_text) == {"name": "foo"}


def test_strip_schema_key_invalid_json_raises_generation_error(tmp_path: pathlib.Path) -> None:
    source_path = tmp_path / "plugin.json"
    with pytest.raises(generator.GenerationError, match="is not valid JSON"):
        generator.strip_schema_key("{not valid json,,,}", source_path)


def test_strip_schema_key_non_object_json_raises_generation_error(tmp_path: pathlib.Path) -> None:
    source_path = tmp_path / "plugin.json"
    with pytest.raises(generator.GenerationError, match="must be a JSON object"):
        generator.strip_schema_key("42", source_path)


# ---------------------------------------------------------------------------
# render_mirror
# ---------------------------------------------------------------------------


def test_render_mirror_two_space_indent_and_trailing_newline() -> None:
    rendered = generator.render_mirror({"name": "foo"})
    assert rendered == '{\n  "name": "foo"\n}\n'


def test_render_mirror_empty_dict_renders_empty_object() -> None:
    assert generator.render_mirror({}) == "{}\n"


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


def test_generate_strips_schema_and_renders(tmp_path: pathlib.Path) -> None:
    source_path = tmp_path / "plugin.json"
    source_path.write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "foo",
                "version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    rendered = generator.generate(source_path)
    assert rendered == '{\n  "name": "foo",\n  "version": "0.1.0"\n}\n'


def test_generate_missing_source_file_raises_generation_error(tmp_path: pathlib.Path) -> None:
    source_path = tmp_path / "does-not-exist.json"
    with pytest.raises(generator.GenerationError, match="cannot be read"):
        generator.generate(source_path)


def test_generate_non_utf8_source_file_raises_generation_error(tmp_path: pathlib.Path) -> None:
    source_path = tmp_path / "plugin.json"
    source_path.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(generator.GenerationError, match="not valid UTF-8"):
        generator.generate(source_path)


# ---------------------------------------------------------------------------
# main() -- --check drift detection
# ---------------------------------------------------------------------------


def test_main_check_mode_passes_when_output_matches(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_path = tmp_path / "plugin.json"
    source_path.write_text(json.dumps({"$schema": "x", "name": "foo"}), encoding="utf-8")
    output_path = tmp_path / "output.json"

    monkeypatch.setattr(generator, "SOURCE_PATH", source_path)
    monkeypatch.setattr(generator, "OUTPUT_PATH", output_path)

    assert generator.main([]) == 0  # writes output_path
    assert generator.main(["--check"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_check_mode_fails_when_output_is_stale(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_path = tmp_path / "plugin.json"
    source_path.write_text(json.dumps({"$schema": "x", "name": "foo"}), encoding="utf-8")
    output_path = tmp_path / "output.json"
    output_path.write_text("stale content that a fresh regeneration will not match\n", encoding="utf-8")

    monkeypatch.setattr(generator, "SOURCE_PATH", source_path)
    monkeypatch.setattr(generator, "OUTPUT_PATH", output_path)

    assert generator.main(["--check"]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_check_mode_missing_output_file_fails_cleanly(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_path = tmp_path / "plugin.json"
    source_path.write_text(json.dumps({"$schema": "x", "name": "foo"}), encoding="utf-8")

    monkeypatch.setattr(generator, "SOURCE_PATH", source_path)
    monkeypatch.setattr(generator, "OUTPUT_PATH", tmp_path / "nonexistent-output.json")

    assert generator.main(["--check"]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_check_mode_non_utf8_output_file_fails_cleanly(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_path = tmp_path / "plugin.json"
    source_path.write_text(json.dumps({"$schema": "x", "name": "foo"}), encoding="utf-8")
    output_path = tmp_path / "output.json"
    output_path.write_bytes(b"\xff\xfe not utf-8")

    monkeypatch.setattr(generator, "SOURCE_PATH", source_path)
    monkeypatch.setattr(generator, "OUTPUT_PATH", output_path)

    assert generator.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "not valid UTF-8" in err


def test_main_missing_source_file_fails_cleanly(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(generator, "SOURCE_PATH", tmp_path / "does-not-exist.json")

    assert generator.main([]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "cannot be read" in err


def test_main_write_failure_fails_cleanly(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A CodeRabbit review finding: OUTPUT_PATH.write_text's OSError (e.g.
    the output path is a directory, or the disk is full) must fail cleanly
    with FAIL: and exit 1, not surface as an uncaught traceback."""
    source_path = tmp_path / "plugin.json"
    source_path.write_text(json.dumps({"$schema": "x", "name": "foo"}), encoding="utf-8")
    output_path = tmp_path / "output-is-a-directory"
    output_path.mkdir()

    monkeypatch.setattr(generator, "SOURCE_PATH", source_path)
    monkeypatch.setattr(generator, "OUTPUT_PATH", output_path)

    assert generator.main([]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "cannot be written" in err


# ---------------------------------------------------------------------------
# Real-repository self-validation (the gate itself)
# ---------------------------------------------------------------------------


def test_real_repository_generated_mirror_matches_committed_file() -> None:
    assert generator.main(["--check"]) == 0

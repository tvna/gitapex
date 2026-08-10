"""Tests for the docs/skill-eval-status.md generator
(.github/scripts/gitapex_generate_skill_eval_status.py).

Issue #928, T14. The final test is the drift check itself: regenerating
into memory from the real docs/skill-eval-status-narrative.md and the
real evals/ tree must produce exactly the committed docs/skill-eval-
status.md -- the file this migration replaces was hand-maintained and
drifted stale (a hardcoded "All 12 ... trials_per_task: 3" sentence) with
nothing catching it; this test is that catch. The rest unit-test each
derivation layer with fixtures: trials/fixture-count/model-extraction/
result-record-presence, and placeholder substitution.
"""

from __future__ import annotations

import json
import pathlib

import gitapex_generate_skill_eval_status as generator
import pytest


def _write_eval_yaml(evals_dir: pathlib.Path, skill: str, trials_per_task: object = 3) -> None:
    skill_dir = evals_dir / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    config_line = f"  trials_per_task: {trials_per_task}\n" if trials_per_task is not None else ""
    (skill_dir / "eval.yaml").write_text(f"name: {skill}-eval\nconfig:\n{config_line}", encoding="utf-8")


def _write_fixtures(evals_dir: pathlib.Path, skill: str, count: int) -> None:
    tasks_dir = evals_dir / skill / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (tasks_dir / f"fixture-{index}.yaml").write_text("id: x\n", encoding="utf-8")


def _write_manifest(evals_dir: pathlib.Path, skill: str, run_name: str, models: object) -> None:
    results_dir = evals_dir / skill / "results" / run_name
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "manifest.json").write_text(json.dumps({"models": models}), encoding="utf-8")


# ---------------------------------------------------------------------------
# load_trials_per_task
# ---------------------------------------------------------------------------


def test_load_trials_per_task_reads_config_value(tmp_path: pathlib.Path) -> None:
    _write_eval_yaml(tmp_path, "foo", trials_per_task=3)
    assert generator.load_trials_per_task("foo", tmp_path) == 3


def test_load_trials_per_task_missing_file_returns_none(tmp_path: pathlib.Path) -> None:
    assert generator.load_trials_per_task("nonexistent", tmp_path) is None


def test_load_trials_per_task_malformed_yaml_returns_none(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "eval.yaml").write_text("{not: valid: yaml:", encoding="utf-8")
    assert generator.load_trials_per_task("foo", tmp_path) is None


def test_load_trials_per_task_missing_config_key_returns_none(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "eval.yaml").write_text("name: foo-eval\n", encoding="utf-8")
    assert generator.load_trials_per_task("foo", tmp_path) is None


# ---------------------------------------------------------------------------
# count_fixtures
# ---------------------------------------------------------------------------


def test_count_fixtures_counts_task_yaml_files(tmp_path: pathlib.Path) -> None:
    _write_fixtures(tmp_path, "foo", 4)
    assert generator.count_fixtures("foo", tmp_path) == 4


def test_count_fixtures_missing_tasks_dir_returns_zero(tmp_path: pathlib.Path) -> None:
    assert generator.count_fixtures("nonexistent", tmp_path) == 0


# ---------------------------------------------------------------------------
# find_evaluated_models
# ---------------------------------------------------------------------------


def test_find_evaluated_models_extracts_identifiers_from_free_text(tmp_path: pathlib.Path) -> None:
    _write_manifest(
        tmp_path,
        "foo",
        "run-1",
        {"tester_model_requested": "claude-fable-5 (explicit --model flag)"},
    )
    assert generator.find_evaluated_models("foo", tmp_path) == ["claude-fable-5"]


def test_find_evaluated_models_dedupes_and_sorts_across_manifests(tmp_path: pathlib.Path) -> None:
    _write_manifest(tmp_path, "foo", "run-1", {"default": "claude-sonnet-5"})
    _write_manifest(tmp_path, "foo", "run-2", {"tier": "inferred claude-sonnet-5, then claude-opus-5"})
    assert generator.find_evaluated_models("foo", tmp_path) == ["claude-opus-5", "claude-sonnet-5"]


def test_find_evaluated_models_withheld_model_name_contributes_nothing(tmp_path: pathlib.Path) -> None:
    # A real committed manifest withholds the orchestrating session's model
    # per its own disclosure policy -- that must not fabricate a false
    # entry, and must not crash.
    _write_manifest(tmp_path, "foo", "run-1", {"orchestrating_session_model": "intentionally not disclosed"})
    assert generator.find_evaluated_models("foo", tmp_path) == []


def test_find_evaluated_models_no_results_dir_returns_empty(tmp_path: pathlib.Path) -> None:
    assert generator.find_evaluated_models("nonexistent", tmp_path) == []


def test_find_evaluated_models_malformed_manifest_json_is_skipped_not_raised(tmp_path: pathlib.Path) -> None:
    run_dir = tmp_path / "foo" / "results" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")
    assert generator.find_evaluated_models("foo", tmp_path) == []


def test_find_evaluated_models_non_dict_models_field_is_skipped(tmp_path: pathlib.Path) -> None:
    _write_manifest(tmp_path, "foo", "run-1", "claude-sonnet-5")
    assert generator.find_evaluated_models("foo", tmp_path) == []


# ---------------------------------------------------------------------------
# has_result_record
# ---------------------------------------------------------------------------


def test_has_result_record_true_when_manifest_exists(tmp_path: pathlib.Path) -> None:
    _write_manifest(tmp_path, "foo", "run-1", {"default": "claude-sonnet-5"})
    assert generator.has_result_record("foo", tmp_path) is True


def test_has_result_record_false_when_no_results_dir(tmp_path: pathlib.Path) -> None:
    assert generator.has_result_record("nonexistent", tmp_path) is False


def test_has_result_record_false_when_results_dir_has_no_manifest(tmp_path: pathlib.Path) -> None:
    (tmp_path / "foo" / "results" / "run-1").mkdir(parents=True)
    assert generator.has_result_record("foo", tmp_path) is False


# ---------------------------------------------------------------------------
# discover_skill_names
# ---------------------------------------------------------------------------


def test_discover_skill_names_is_the_intersection(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    for name in ("foo", "bar", "skill-only"):
        (skills_dir / name).mkdir(parents=True)
    for name in ("foo", "bar", "eval-only"):
        _write_eval_yaml(evals_dir, name)
    assert generator.discover_skill_names(skills_dir, evals_dir) == ["bar", "foo"]


# ---------------------------------------------------------------------------
# substitute_placeholders
# ---------------------------------------------------------------------------


def test_substitute_placeholders_replaces_both_tokens(tmp_path: pathlib.Path) -> None:
    _write_eval_yaml(tmp_path, "a", trials_per_task=3)
    _write_eval_yaml(tmp_path, "b", trials_per_task=3)
    _write_eval_yaml(tmp_path, "c", trials_per_task=1)
    text = "{{TRIALS_3_COUNT}} of {{TOTAL_EVAL_YAML_COUNT}} declare 3."
    assert generator.substitute_placeholders(text, tmp_path) == "2 of 3 declare 3."


def test_substitute_placeholders_leaves_unknown_token_literal(tmp_path: pathlib.Path) -> None:
    text = "value is {{SOME_UNKNOWN_TOKEN}}."
    assert generator.substitute_placeholders(text, tmp_path) == text


# ---------------------------------------------------------------------------
# render_index_table
# ---------------------------------------------------------------------------


def test_render_index_table_includes_every_derived_column(tmp_path: pathlib.Path) -> None:
    _write_eval_yaml(tmp_path, "foo", trials_per_task=3)
    _write_fixtures(tmp_path, "foo", 2)
    _write_manifest(tmp_path, "foo", "run-1", {"default": "claude-sonnet-5"})
    table = generator.render_index_table(["foo"], tmp_path)
    assert "| `foo` | 3 | 2 | `claude-sonnet-5` | yes |" in table
    assert "eval-status.md" in table


def test_render_index_table_missing_trials_renders_question_mark(tmp_path: pathlib.Path) -> None:
    _write_eval_yaml(tmp_path, "foo", trials_per_task=None)
    table = generator.render_index_table(["foo"], tmp_path)
    assert "| `foo` | ? |" in table


# ---------------------------------------------------------------------------
# generate() / main() -- --check drift detection
# ---------------------------------------------------------------------------


def test_generate_appends_index_after_narrative(tmp_path: pathlib.Path) -> None:
    narrative_path = tmp_path / "narrative.md"
    narrative_path.write_text("# Title\n\nSome narrative.\n", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    (skills_dir / "foo").mkdir(parents=True)
    _write_eval_yaml(evals_dir, "foo")
    rendered = generator.generate(narrative_path, skills_dir, evals_dir)
    assert rendered.startswith("# Title\n\nSome narrative.\n")
    assert "\n## Index\n\n" in rendered
    assert "| `foo` |" in rendered


def test_generate_adds_trailing_newline_when_narrative_lacks_one(tmp_path: pathlib.Path) -> None:
    narrative_path = tmp_path / "narrative.md"
    narrative_path.write_text("# Title, no trailing newline", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    (skills_dir / "foo").mkdir(parents=True)
    _write_eval_yaml(evals_dir, "foo")
    rendered = generator.generate(narrative_path, skills_dir, evals_dir)
    assert rendered.startswith("# Title, no trailing newline\n\n## Index\n\n")


def test_generate_missing_narrative_file_raises_generation_error(tmp_path: pathlib.Path) -> None:
    narrative_path = tmp_path / "does-not-exist.md"
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    with pytest.raises(generator.GenerationError, match="cannot be read"):
        generator.generate(narrative_path, skills_dir, evals_dir)


def test_generate_non_utf8_narrative_file_raises_generation_error(tmp_path: pathlib.Path) -> None:
    narrative_path = tmp_path / "narrative.md"
    narrative_path.write_bytes(b"\xff\xfe not utf-8")
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    with pytest.raises(generator.GenerationError, match="not valid UTF-8"):
        generator.generate(narrative_path, skills_dir, evals_dir)


def test_main_check_mode_passes_when_output_matches(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    narrative_path = tmp_path / "narrative.md"
    narrative_path.write_text("# Title\n\nNo tokens here.\n", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    (skills_dir / "foo").mkdir(parents=True)
    _write_eval_yaml(evals_dir, "foo")
    output_path = tmp_path / "output.md"

    monkeypatch.setattr(generator, "NARRATIVE_PATH", narrative_path)
    monkeypatch.setattr(generator, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(generator, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(generator, "OUTPUT_PATH", output_path)

    assert generator.main([]) == 0  # writes output_path
    assert generator.main(["--check"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_check_mode_fails_when_output_is_stale(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    narrative_path = tmp_path / "narrative.md"
    narrative_path.write_text("# Title\n\nNo tokens here.\n", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    (skills_dir / "foo").mkdir(parents=True)
    _write_eval_yaml(evals_dir, "foo")
    output_path = tmp_path / "output.md"
    output_path.write_text("stale content that a fresh regeneration will not match\n", encoding="utf-8")

    monkeypatch.setattr(generator, "NARRATIVE_PATH", narrative_path)
    monkeypatch.setattr(generator, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(generator, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(generator, "OUTPUT_PATH", output_path)

    assert generator.main(["--check"]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_check_mode_missing_output_file_fails_cleanly(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    narrative_path = tmp_path / "narrative.md"
    narrative_path.write_text("# Title\n\nNo tokens here.\n", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    (skills_dir / "foo").mkdir(parents=True)
    _write_eval_yaml(evals_dir, "foo")

    monkeypatch.setattr(generator, "NARRATIVE_PATH", narrative_path)
    monkeypatch.setattr(generator, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(generator, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(generator, "OUTPUT_PATH", tmp_path / "nonexistent-output.md")

    assert generator.main(["--check"]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_check_mode_non_utf8_output_file_fails_cleanly(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    narrative_path = tmp_path / "narrative.md"
    narrative_path.write_text("# Title\n\nNo tokens here.\n", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    (skills_dir / "foo").mkdir(parents=True)
    _write_eval_yaml(evals_dir, "foo")
    output_path = tmp_path / "output.md"
    output_path.write_bytes(b"\xff\xfe not utf-8")

    monkeypatch.setattr(generator, "NARRATIVE_PATH", narrative_path)
    monkeypatch.setattr(generator, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(generator, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(generator, "OUTPUT_PATH", output_path)

    assert generator.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "not valid UTF-8" in err


def test_main_missing_narrative_file_fails_cleanly(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(generator, "NARRATIVE_PATH", tmp_path / "does-not-exist.md")
    monkeypatch.setattr(generator, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(generator, "EVALS_DIR", tmp_path / "evals")

    assert generator.main([]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "cannot be read" in err


# ---------------------------------------------------------------------------
# Real-repository self-validation (the gate itself)
# ---------------------------------------------------------------------------


def test_real_repository_generated_doc_matches_committed_file() -> None:
    assert generator.main(["--check"]) == 0

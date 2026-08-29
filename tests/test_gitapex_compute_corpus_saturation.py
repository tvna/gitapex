"""Tests for `evals/scripts/gitapex_compute_corpus_saturation.py` (issue #1461).

Two layers, deliberately: hermetic `tmp_path` fixtures cover every branch of
the parsing and classification logic, and three tests pin the figures this
issue's own Acceptance Criteria Map cites as its proof method against the
real committed run directories. The pinned tests are what would catch a
silent change in meaning -- a refactor that still parses but no longer
reproduces 5-of-23 saturated would pass every synthetic case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gitapex_compute_corpus_saturation as mod
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE1 = REPO_ROOT / "evals/evaluating-skill-quality/results/2026-07-28-issue-500-phase1"
SINGLE_MODEL_RUN = (
    REPO_ROOT / "evals/evaluating-skill-quality/results/2026-08-26-issue-1347-structural-identifier-portability"
)


def write_result(
    run_dir: Path,
    name: str,
    model_id: str | None,
    # Deliberately `list[Any]`, not `list[dict[str, Any]]`: several tests feed
    # a malformed entry (a bare string) to exercise the loud-failure path.
    scores: list[Any] | None,
    **extra: Any,
) -> Path:
    """Write one result JSON, omitting keys passed as None."""
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = dict(extra)
    if model_id is not None:
        payload["model_id"] = model_id
    if scores is not None:
        payload["scores"] = scores
    path = run_dir / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def entry(fixture_id: str, score: Any, condition: str | None = None) -> dict[str, Any]:
    e: dict[str, Any] = {"fixture_id": fixture_id, "score": score}
    if condition is not None:
        e["condition"] = condition
    return e


# --------------------------------------------------------------------------
# Pinned against the real committed corpus -- the issue's own proof method
# --------------------------------------------------------------------------


def test_phase1_reproduces_the_saturation_figures_the_issue_cites() -> None:
    report = mod.compute_saturation(PHASE1)

    assert report.model_ids == (
        "claude-haiku-4-5-20251001",
        "claude-opus-5",
        "claude-sonnet-5",
    )
    assert len(report.complete) == 23
    assert len(report.saturated) == 5
    assert len(report.discriminating) == 18
    assert report.computable is True


def test_phase1_flags_uniformly_hard_fixtures_outside_the_saturated_list() -> None:
    report = mod.compute_saturation(PHASE1)
    uniformly_hard = {f.fixture_id for f in report.uniformly_hard}
    saturated = {f.fixture_id for f in report.saturated}

    assert "evaluating-skill-quality-scoring-axis-uncontrolled-speed-claim" in uniformly_hard
    assert "evaluating-skill-quality-scoring-axis-uncontrolled-speed-claim" not in saturated
    # A uniformly-hard fixture is a labelled subset of the discriminating set,
    # never a fourth bucket.
    assert uniformly_hard <= {f.fixture_id for f in report.discriminating}


def test_single_model_committed_run_is_reported_as_not_computable() -> None:
    report = mod.compute_saturation(SINGLE_MODEL_RUN)

    assert report.model_ids == ("claude-sonnet-5",)
    assert report.computable is False
    assert "NOT COMPUTABLE" in mod.format_report(report)


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def test_saturated_and_discriminating_partition_the_complete_set(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f1", 1.0), entry("f2", 0.5)])
    write_result(tmp_path, "b.json", "model-b", [entry("f1", 1.0), entry("f2", 1.0)])

    report = mod.compute_saturation(tmp_path)

    assert [f.fixture_id for f in report.saturated] == ["f1"]
    assert [f.fixture_id for f in report.discriminating] == ["f2"]
    assert len(report.saturated) + len(report.discriminating) == len(report.complete)


def test_uniformly_hard_requires_agreement_below_one(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "a.json",
        "model-a",
        [entry("agree-low", 0.75), entry("disagree", 0.75), entry("agree-high", 1.0)],
    )
    write_result(
        tmp_path,
        "b.json",
        "model-b",
        [entry("agree-low", 0.75), entry("disagree", 1.0), entry("agree-high", 1.0)],
    )

    report = mod.compute_saturation(tmp_path)

    assert [f.fixture_id for f in report.uniformly_hard] == ["agree-low"]


def test_fixture_missing_from_one_model_is_excluded_and_listed(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("shared", 1.0), entry("only-a", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("shared", 1.0)])

    report = mod.compute_saturation(tmp_path)

    assert [f.fixture_id for f in report.complete] == ["shared"]
    assert [f.fixture_id for f in report.incomplete] == ["only-a"]
    assert "not scored by every model" in mod.format_report(report)


# --------------------------------------------------------------------------
# Which files and entries participate
# --------------------------------------------------------------------------


def test_manifest_and_trace_shaped_files_do_not_participate(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 0.5)])
    # manifest.json shape: provenance, no model_id/scores.
    write_result(tmp_path, "manifest.json", None, None, date="2026-08-29")
    # dispatch-trace-check.json shape: a model_id, but no scores.
    write_result(tmp_path, "dispatch-trace-check.json", "model-c", None)
    # A scores-carrying file with no model_id is not a per-model record.
    write_result(tmp_path, "orphan.json", None, [entry("f", 0.0)])

    report = mod.compute_saturation(tmp_path)

    assert report.model_ids == ("model-a", "model-b")


def test_a_json_document_that_is_not_an_object_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "list.json").write_text("[1, 2, 3]", encoding="utf-8")
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 1.0)])

    report = mod.compute_saturation(tmp_path)

    assert report.model_ids == ("model-a", "model-b")


def test_blank_model_id_does_not_participate(tmp_path: Path) -> None:
    write_result(tmp_path, "blank.json", "   ", [entry("f", 1.0)])

    report = mod.compute_saturation(tmp_path)

    assert report.model_ids == ()
    assert report.computable is False


def test_artifacts_subdirectory_is_never_read(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 1.0)])
    write_result(tmp_path / "artifacts", "c.json", "model-c", [entry("f", 0.0)])

    report = mod.compute_saturation(tmp_path)

    assert report.model_ids == ("model-a", "model-b")


def test_before_arm_of_a_gate_record_is_ignored(tmp_path: Path) -> None:
    write_result(
        tmp_path,
        "a-detail.json",
        "model-a",
        [entry("f", 0.0, condition="before"), entry("f", 1.0, condition="after")],
    )
    write_result(tmp_path, "b.json", "model-b", [entry("f", 1.0)])

    report = mod.compute_saturation(tmp_path)

    assert len(report.saturated) == 1


def test_agreeing_duplicate_entries_are_deduplicated(tmp_path: Path) -> None:
    write_result(tmp_path, "a-after.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "a-detail.json", "model-a", [entry("f", 1.0, condition="after")])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 0.5)])

    report = mod.compute_saturation(tmp_path)

    assert report.model_ids == ("model-a", "model-b")
    assert report.complete[0].scores == {"model-a": 1.0, "model-b": 0.5}


# --------------------------------------------------------------------------
# Loud failures
# --------------------------------------------------------------------------


def test_a_model_that_scored_nothing_still_counts_as_a_model(tmp_path: Path) -> None:
    """Regression: the property layer found this one.

    A file with an empty `scores[]` used to vanish from the model list, so a
    fixture only one of two models scored was reported as saturated across
    "every model" -- unmeasured read as measured.
    """
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [])

    report = mod.compute_saturation(tmp_path)

    assert report.model_ids == ("model-a", "model-b")
    assert report.saturated == ()
    assert [f.fixture_id for f in report.incomplete] == ["f"]


def test_a_model_contributing_only_before_arms_still_counts_as_a_model(
    tmp_path: Path,
) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 1.0, condition="before")])

    report = mod.compute_saturation(tmp_path)

    assert report.model_ids == ("model-a", "model-b")
    assert report.saturated == ()


def test_conflicting_duplicate_entries_fail_loudly(tmp_path: Path) -> None:
    write_result(tmp_path, "a-after.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "a-detail.json", "model-a", [entry("f", 0.5, condition="after")])

    with pytest.raises(mod.SaturationInputError, match="two different scores"):
        mod.compute_saturation(tmp_path)


def test_a_boolean_is_not_accepted_as_a_score(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", True)])

    with pytest.raises(mod.SaturationInputError, match="non-numeric score"):
        mod.compute_saturation(tmp_path)


def test_a_string_is_not_accepted_as_a_score(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", "1.0")])

    with pytest.raises(mod.SaturationInputError, match="non-numeric score"):
        mod.compute_saturation(tmp_path)


def test_a_missing_fixture_id_fails_loudly(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [{"score": 1.0}])

    with pytest.raises(mod.SaturationInputError, match="no fixture_id"):
        mod.compute_saturation(tmp_path)


def test_a_blank_fixture_id_fails_loudly(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("  ", 1.0)])

    with pytest.raises(mod.SaturationInputError, match="no fixture_id"):
        mod.compute_saturation(tmp_path)


def test_a_non_object_scores_entry_fails_loudly(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", ["not-an-object"])

    with pytest.raises(mod.SaturationInputError, match="is not an object"):
        mod.compute_saturation(tmp_path)


def test_unparseable_json_fails_loudly(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(mod.SaturationInputError, match="could not read"):
        mod.compute_saturation(tmp_path)


def test_a_path_that_is_not_a_directory_fails_loudly(tmp_path: Path) -> None:
    lone_file = tmp_path / "a.json"
    lone_file.write_text("{}", encoding="utf-8")

    with pytest.raises(mod.SaturationInputError, match="not a readable directory"):
        mod.compute_saturation(lone_file)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_an_unqualified_model_id_is_flagged_not_normalized(tmp_path: Path) -> None:
    suffixed = "claude-sonnet-5 (inferred, not independently confirmed)"
    write_result(tmp_path, "a.json", suffixed, [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "claude-opus-5", [entry("f", 1.0)])

    report = mod.compute_saturation(tmp_path)
    text = mod.format_report(report)

    assert report.unqualified_model_ids == (suffixed,)
    assert "is not a bare identifier" in text
    # Counted verbatim as its own responder rather than merged.
    assert len(report.model_ids) == 2


def test_report_names_zero_models_when_no_file_participates(tmp_path: Path) -> None:
    write_result(tmp_path, "manifest.json", None, None, date="2026-08-29")

    text = mod.format_report(mod.compute_saturation(tmp_path))

    assert "models (0): none" in text
    assert "NOT COMPUTABLE" in text


def test_two_models_sharing_no_fixture_are_not_computable(tmp_path: Path) -> None:
    """Enough models, but no fixture both of them scored -- a rate over an
    empty set would read as a real 0 percent rather than as no measurement."""
    write_result(tmp_path, "a.json", "model-a", [entry("only-a", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("only-b", 1.0)])

    report = mod.compute_saturation(tmp_path)
    text = mod.format_report(report)

    assert len(report.model_ids) == 2
    assert report.complete == ()
    assert report.computable is False
    assert "NOT COMPUTABLE" in text
    assert "fixtures not scored by every model: 2" in text
    # The stated reason must name the condition that actually failed, not
    # the model minimum -- which is satisfied here.
    assert "no fixture was scored by every model" in text
    assert "needs at least" not in text


def test_not_computable_names_the_model_minimum_when_that_is_what_failed(
    tmp_path: Path,
) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])

    text = mod.format_report(mod.compute_saturation(tmp_path))

    assert "needs at least 2 models" in text
    assert "no fixture was scored by every model" not in text


def test_report_disclaims_being_an_irt_estimate(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 0.5)])

    text = mod.format_report(mod.compute_saturation(tmp_path))

    assert "not an item-response difficulty or discrimination estimate" in text


def test_report_lists_saturated_fixture_ids(tmp_path: Path) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("solved", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("solved", 1.0)])

    text = mod.format_report(mod.compute_saturation(tmp_path))

    assert "saturated fixtures (no information in this run):" in text
    assert "  solved" in text


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_main_prints_the_report_and_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", 1.0)])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 1.0)])

    exit_code = mod.main([str(tmp_path)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "saturated (every model 1.0): 1 of 1 (100.0 percent)" in out


def test_main_exits_zero_on_a_fully_discriminating_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_result(tmp_path, "a.json", "model-a", [entry("f", 0.1)])
    write_result(tmp_path, "b.json", "model-b", [entry("f", 0.9)])

    assert mod.main([str(tmp_path)]) == 0
    assert "saturated (every model 1.0): 0 of 1 (0.0 percent)" in capsys.readouterr().out


def test_main_exits_two_on_malformed_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    exit_code = mod.main([str(tmp_path)])

    assert exit_code == 2
    assert "error:" in capsys.readouterr().err

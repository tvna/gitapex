"""Tests for evals/scripts/gitapex_check_suite_threshold.py (issue #1259).

Covers ``check_suite_threshold`` (the pure comparison, extracted from an
inline ``python3 -c "..."`` one-liner ``waza-eval-matrix.yml``'s
``eval-matrix`` and ``eval-matrix-hf-gemma4`` jobs both carried duplicated)
and ``main()``'s own CLI wrapper against real files on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gitapex_check_suite_threshold as check_threshold
import pytest
import yaml


def _write_result(tmp_path: Path, **fields: Any) -> Path:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(fields), encoding="utf-8")
    return path


def _write_suite(tmp_path: Path, metrics: list[dict[str, Any]]) -> Path:
    path = tmp_path / "eval.yaml"
    path.write_text(yaml.safe_dump({"metrics": metrics}), encoding="utf-8")
    return path


# --- check_suite_threshold() -------------------------------------------------


def test_check_suite_threshold_passes_when_mean_score_meets_threshold() -> None:
    passed, message = check_threshold.check_suite_threshold(
        {"mean_score": 0.9}, {"metrics": [{"name": "quality", "threshold": 0.8}]}
    )
    assert passed is True
    assert message == "mean_score=0.9 threshold=0.8"


def test_check_suite_threshold_passes_at_exact_boundary() -> None:
    passed, _ = check_threshold.check_suite_threshold(
        {"mean_score": 0.8}, {"metrics": [{"name": "quality", "threshold": 0.8}]}
    )
    assert passed is True


def test_check_suite_threshold_fails_when_mean_score_below_threshold() -> None:
    passed, message = check_threshold.check_suite_threshold(
        {"mean_score": 0.5}, {"metrics": [{"name": "quality", "threshold": 0.8}]}
    )
    assert passed is False
    assert message == "mean_score=0.5 threshold=0.8"


def test_check_suite_threshold_rejects_zero_metrics_entries() -> None:
    with pytest.raises(ValueError, match="expected exactly 1 metrics"):
        check_threshold.check_suite_threshold({"mean_score": 0.9}, {"metrics": []})


def test_check_suite_threshold_rejects_multiple_metrics_entries() -> None:
    with pytest.raises(ValueError, match="expected exactly 1 metrics"):
        check_threshold.check_suite_threshold(
            {"mean_score": 0.9},
            {"metrics": [{"name": "a", "threshold": 0.5}, {"name": "b", "threshold": 0.5}]},
        )


def test_check_suite_threshold_rejects_missing_metrics_key() -> None:
    with pytest.raises(ValueError, match="expected exactly 1 metrics"):
        check_threshold.check_suite_threshold({"mean_score": 0.9}, {})


def test_check_suite_threshold_rejects_metrics_entry_missing_threshold() -> None:
    with pytest.raises(ValueError, match="threshold"):
        check_threshold.check_suite_threshold({"mean_score": 0.9}, {"metrics": [{"name": "quality"}]})


def test_check_suite_threshold_rejects_result_missing_mean_score() -> None:
    with pytest.raises(ValueError, match="mean_score"):
        check_threshold.check_suite_threshold({}, {"metrics": [{"name": "quality", "threshold": 0.8}]})


def test_check_suite_threshold_rejects_non_mapping_suite() -> None:
    # Defeat test: a YAML file that parses to a list/scalar rather than a
    # mapping must not raise a raw AttributeError from `suite.get(...)`.
    with pytest.raises(ValueError, match="mapping"):
        check_threshold.check_suite_threshold({"mean_score": 0.9}, ["not", "a", "mapping"])


# --- main() -------------------------------------------------------------


def test_main_exits_0_when_passing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = _write_result(tmp_path, mean_score=0.9)
    suite = _write_suite(tmp_path, [{"name": "quality", "threshold": 0.8}])

    rc = check_threshold.main(["prog", str(result), str(suite)])

    assert rc == 0
    assert "mean_score=0.9 threshold=0.8" in capsys.readouterr().err


def test_main_exits_1_when_below_threshold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = _write_result(tmp_path, mean_score=0.1)
    suite = _write_suite(tmp_path, [{"name": "quality", "threshold": 0.8}])

    rc = check_threshold.main(["prog", str(result), str(suite)])

    assert rc == 1
    assert "mean_score=0.1 threshold=0.8" in capsys.readouterr().err


def test_main_exits_1_on_malformed_metrics_with_clear_message_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _write_result(tmp_path, mean_score=0.9)
    suite = _write_suite(tmp_path, [])

    rc = check_threshold.main(["prog", str(result), str(suite)])

    assert rc == 1
    assert "error: expected exactly 1 metrics" in capsys.readouterr().err


def test_main_exits_1_on_missing_result_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    suite = _write_suite(tmp_path, [{"name": "quality", "threshold": 0.8}])

    rc = check_threshold.main(["prog", str(tmp_path / "does-not-exist.json"), str(suite)])

    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_exits_1_on_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = tmp_path / "result.json"
    result.write_text("{not valid json", encoding="utf-8")
    suite = _write_suite(tmp_path, [{"name": "quality", "threshold": 0.8}])

    rc = check_threshold.main(["prog", str(result), str(suite)])

    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_exits_2_on_wrong_argument_count(capsys: pytest.CaptureFixture[str]) -> None:
    rc = check_threshold.main(["prog", "only-one-arg"])

    assert rc == 2
    assert "usage:" in capsys.readouterr().err

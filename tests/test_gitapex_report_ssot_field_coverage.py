"""Tests for the non-blocking fail_mode/target coverage report
(.github/scripts/gitapex_report_ssot_field_coverage.py, issue #1232).

The central contract under test throughout this file: incomplete coverage
is never a failure. Every "missing field" fixture below still asserts
main() == 0 -- asserting anything else would turn this report quietly
fail-closed, defeating the reason issue #1232 asked for a report instead of
a gate. The only exit-1 path is a genuine read/parse failure.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import gitapex_report_ssot_field_coverage as coverage
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_INSTANCE: dict[str, Any] = {
    "gates": [
        {"id": "gate-with-both", "fail_mode": {"on_error": "fail-open", "rationale": "x"}, "target": []},
        {"id": "gate-with-target-only", "target": []},
        {"id": "gate-with-neither"},
    ]
}


def test_field_coverage_splits_present_and_missing_correctly() -> None:
    present, missing = coverage.field_coverage(_INSTANCE, "target")
    assert present == ["gate-with-both", "gate-with-target-only"]
    assert missing == ["gate-with-neither"]

    present, missing = coverage.field_coverage(_INSTANCE, "fail_mode")
    assert present == ["gate-with-both"]
    assert missing == ["gate-with-neither", "gate-with-target-only"]


def test_field_coverage_returns_empty_without_raising_when_gates_is_absent() -> None:
    assert coverage.field_coverage({}, "target") == ([], [])


def test_field_coverage_returns_empty_without_raising_when_gates_is_not_a_list() -> None:
    assert coverage.field_coverage({"gates": "not-a-list"}, "target") == ([], [])


def test_field_coverage_skips_non_dict_gate_entries_without_raising() -> None:
    instance = {"gates": [None, 1, "x", {"id": "real-gate", "target": []}]}
    present, missing = coverage.field_coverage(instance, "target")
    assert present == ["real-gate"]
    assert missing == []


def test_field_coverage_skips_entries_with_a_non_string_id() -> None:
    instance = {"gates": [{"id": 123, "target": []}, {"target": []}, {"id": "real-gate"}]}
    present, missing = coverage.field_coverage(instance, "target")
    assert present == []
    assert missing == ["real-gate"]


def test_build_report_includes_percentage_and_missing_list_for_each_field() -> None:
    report = coverage.build_report(_INSTANCE)
    assert "target: 2/3 gates (66%)" in report
    assert "missing: gate-with-neither" in report
    assert "fail_mode: 1/3 gates (33%)" in report


def test_build_report_handles_a_zero_gate_registry_without_a_zero_division_error() -> None:
    report = coverage.build_report({"gates": []})
    assert "target: 0/0 gates (0%)" in report
    assert "fail_mode: 0/0 gates (0%)" in report


def test_main_returns_zero_even_when_every_gate_lacks_both_fields(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The central non-blocking contract: 0% coverage is still exit 0."""
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text(json.dumps({"gates": [{"id": "bare-gate"}]}))
    monkeypatch.setattr(coverage, "SSOT_PATH", instance_path)
    assert coverage.main() == 0
    out = capsys.readouterr().out
    assert "target: 0/1 gates (0%)" in out


@pytest.mark.parametrize("bad_top_level_json", ["[]", '"a string"', "1", "null"])
def test_main_returns_zero_when_the_registry_top_level_is_not_an_object(
    bad_top_level_json: str,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Adversarial review found this exact end-to-end path (main() reading a
    non-dict-but-valid-JSON file from disk) was untested: field_coverage()
    had direct unit coverage for a non-dict top-level value, but nothing
    exercised main() itself with one, so a plausible defensive-programming
    regression (an isinstance(instance, dict) guard added to main() that
    returns 1) left all other tests green. Schema-invalid but still valid,
    readable JSON must not be treated as the read/parse failure that earns
    exit 1 -- ssot-schema-drift's own schema check is what a malformed
    registry shape should fail, not this always-0 report."""
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text(bad_top_level_json)
    monkeypatch.setattr(coverage, "SSOT_PATH", instance_path)
    assert coverage.main() == 0
    out = capsys.readouterr().out
    assert "target: 0/0 gates (0%)" in out


def test_main_returns_one_on_unreadable_registry_path(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(coverage, "SSOT_PATH", tmp_path / "does-not-exist.json")
    assert coverage.main() == 1
    assert "cannot run" in capsys.readouterr().out


def test_main_returns_one_on_invalid_json_syntax(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text("{not valid json")
    monkeypatch.setattr(coverage, "SSOT_PATH", instance_path)
    assert coverage.main() == 1
    assert "cannot run" in capsys.readouterr().out


def test_main_returns_one_on_non_utf8_registry(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    instance_path = tmp_path / "ssot.json"
    instance_path.write_bytes(b"\xff\xfe not utf-8")
    monkeypatch.setattr(coverage, "SSOT_PATH", instance_path)
    assert coverage.main() == 1
    assert "cannot run" in capsys.readouterr().out


@pytest.mark.parametrize("bad_top_level", [[], "a string", 1, None])
def test_field_coverage_handles_non_dict_top_level_without_raising(bad_top_level: Any) -> None:
    assert coverage.field_coverage(bad_top_level, "target") == ([], [])


def test_report_runs_clean_against_the_real_repository_registry() -> None:
    """Smoke test against the real .gitapex/ssot.json -- must run and
    return 0 regardless of the real registry's actual coverage level."""
    assert coverage.main() == 0

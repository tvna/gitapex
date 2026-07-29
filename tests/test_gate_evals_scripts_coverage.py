"""Tests for the evals/scripts coverage-minimum gate
(.github/scripts/gate_evals_scripts_coverage.py).

Refs #536 (retrospective for PR #512, "CI-enforced minimum test coverage
for evals/scripts/*.py"): this gate asserts a per-file coverage floor for
evals/scripts/*.py from a `coverage json` report, so a low-coverage CLI
surface (the PR #512 finding this follow-up closes) fails CI instead of
depending on a manually dispatched review to catch it.
"""

from __future__ import annotations

import json

import pytest

import gate_evals_scripts_coverage as gate


def _report(files: dict[str, float]) -> dict:
    return {
        "files": {
            path: {"summary": {"percent_covered": pct}}
            for path, pct in files.items()
        }
    }


def test_select_files_filters_by_include_glob():
    data = _report({
        "evals/scripts/a.py": 100.0,
        "evals/scripts/b.py": 80.0,
        "skills/foo/scripts/c.py": 10.0,
    })
    selected = gate.select_files(data, "evals/scripts/*.py", "test_")
    assert selected == {"evals/scripts/a.py": 100.0, "evals/scripts/b.py": 80.0}


def test_select_files_excludes_test_prefixed_files():
    data = _report({
        "evals/scripts/a.py": 100.0,
        "evals/scripts/test_a.py": 0.0,
    })
    selected = gate.select_files(data, "evals/scripts/*.py", "test_")
    assert selected == {"evals/scripts/a.py": 100.0}


def test_select_files_normalizes_backslash_paths():
    data = _report({"evals\\scripts\\a.py": 55.0})
    selected = gate.select_files(data, "evals/scripts/*.py", "test_")
    assert selected == {"evals/scripts/a.py": 55.0}


def test_select_files_raises_on_missing_files_key():
    with pytest.raises(ValueError, match="no 'files' object"):
        gate.select_files({}, "evals/scripts/*.py", "test_")


def test_select_files_raises_on_non_dict_top_level():
    with pytest.raises(ValueError, match="not a JSON object"):
        gate.select_files(["not", "a", "dict"], "evals/scripts/*.py", "test_")


def test_select_files_raises_on_missing_percent_covered():
    data = {"files": {"evals/scripts/a.py": {"summary": {}}}}
    with pytest.raises(ValueError, match="no numeric summary.percent_covered"):
        gate.select_files(data, "evals/scripts/*.py", "test_")


def test_find_offenders_reports_only_below_threshold():
    covered = {"a.py": 95.0, "b.py": 60.0, "c.py": 90.0}
    offenders = gate.find_offenders(covered, 90.0)
    assert offenders == [("b.py", 60.0)]


def test_find_offenders_empty_when_all_meet_threshold():
    covered = {"a.py": 95.0, "b.py": 90.0}
    assert gate.find_offenders(covered, 90.0) == []


def test_main_missing_report_file_fails_closed(capsys, tmp_path):
    missing = tmp_path / "no-such-report.json"
    rc = gate.main(["--coverage-json", str(missing)])
    assert rc == 2
    assert "could not read" in capsys.readouterr().err


def test_main_malformed_json_fails_closed(capsys, tmp_path):
    bad = tmp_path / "coverage.json"
    bad.write_text("not json{{{", encoding="utf-8")
    rc = gate.main(["--coverage-json", str(bad)])
    assert rc == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_main_malformed_file_entry_fails_closed(capsys, tmp_path):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps({"files": {"evals/scripts/a.py": {"summary": {}}}}),
        encoding="utf-8",
    )
    rc = gate.main(["--coverage-json", str(report_path)])
    assert rc == 2
    assert "no numeric summary.percent_covered" in capsys.readouterr().err


def test_main_no_matching_files_fails_closed(capsys, tmp_path):
    # A coverage report generated with the wrong scope must not silently
    # pass as "nothing to check" -- that would make this gate a no-op.
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({"skills/foo/scripts/c.py": 10.0})), encoding="utf-8"
    )
    rc = gate.main(["--coverage-json", str(report_path)])
    assert rc == 2
    assert "no files matching" in capsys.readouterr().err


def test_main_passes_when_all_files_meet_threshold(capsys, tmp_path):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({
            "evals/scripts/a.py": 100.0,
            "evals/scripts/b.py": 92.0,
        })),
        encoding="utf-8",
    )
    rc = gate.main(["--coverage-json", str(report_path), "--min-percent", "90"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PASS: all 2 file(s)" in out


def test_main_fails_and_lists_offenders(capsys, tmp_path):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({
            "evals/scripts/a.py": 100.0,
            "evals/scripts/b.py": 71.0,
        })),
        encoding="utf-8",
    )
    rc = gate.main(["--coverage-json", str(report_path), "--min-percent", "90"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "FAIL: evals/scripts/b.py -- 71.0%" in captured.out
    assert "1 of 2 file(s)" in captured.err


def test_main_default_min_percent_is_90():
    assert gate.DEFAULT_MIN_PERCENT == 90.0


def test_main_default_include_glob_is_evals_scripts():
    assert gate.DEFAULT_INCLUDE_GLOB == "evals/scripts/*.py"

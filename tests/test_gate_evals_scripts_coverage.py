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
    selected = gate.select_files(data, "evals/scripts/*.py")
    assert selected == {"evals/scripts/a.py": 100.0, "evals/scripts/b.py": 80.0}


def test_select_files_does_not_silently_drop_test_prefixed_production_files():
    # Regression: an earlier version excluded any file whose basename
    # started with "test_", which would have silently dropped a real
    # production script from the coverage floor with no diagnostic --
    # exactly the silent-gap failure mode this gate exists to close.
    # No evals/scripts/*.py test lives outside tests/, so nothing should
    # be excluded by name.
    data = _report({
        "evals/scripts/a.py": 100.0,
        "evals/scripts/test_config_generator.py": 12.0,
    })
    selected = gate.select_files(data, "evals/scripts/*.py")
    assert selected == {
        "evals/scripts/a.py": 100.0,
        "evals/scripts/test_config_generator.py": 12.0,
    }


def test_select_files_normalizes_backslash_paths():
    data = _report({"evals\\scripts\\a.py": 55.0})
    selected = gate.select_files(data, "evals/scripts/*.py")
    assert selected == {"evals/scripts/a.py": 55.0}


def test_select_files_raises_on_missing_files_key():
    with pytest.raises(ValueError, match="no 'files' object"):
        gate.select_files({}, "evals/scripts/*.py")


def test_select_files_raises_on_non_dict_top_level():
    with pytest.raises(ValueError, match="not a JSON object"):
        gate.select_files(["not", "a", "dict"], "evals/scripts/*.py")


def test_select_files_raises_on_missing_percent_covered():
    data = {"files": {"evals/scripts/a.py": {"summary": {}}}}
    with pytest.raises(ValueError, match="no numeric summary.percent_covered"):
        gate.select_files(data, "evals/scripts/*.py")


def test_select_files_raises_on_bool_percent_covered():
    # Regression: bool is a subclass of int in Python, so
    # isinstance(True, (int, float)) is True -- a malformed report saying
    # percent_covered: true/false must not be silently accepted as a
    # numeric score.
    data = {"files": {"evals/scripts/a.py": {"summary": {"percent_covered": True}}}}
    with pytest.raises(ValueError, match="no numeric summary.percent_covered"):
        gate.select_files(data, "evals/scripts/*.py")


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


def test_main_non_utf8_report_fails_closed(capsys, tmp_path):
    # Regression: a UnicodeDecodeError while reading the file body is
    # neither an OSError nor a json.JSONDecodeError -- an earlier version
    # only caught those two, so a non-UTF-8 report crashed with an
    # uncaught traceback instead of the documented exit 2.
    bad = tmp_path / "coverage.json"
    bad.write_bytes(b"\xff\xfe{\"files\": {}}")
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
    assert "PASS: evals/scripts/a.py -- 100.0% (minimum 90.0%)" in captured.out
    assert "FAIL: evals/scripts/b.py -- 71.0% (minimum 90.0%)" in captured.out
    assert (
        "FAIL: 1 of 2 file(s) matching 'evals/scripts/*.py' are below the "
        "90.0% minimum coverage threshold"
    ) in captured.err


def test_main_default_min_percent_is_90():
    assert gate.DEFAULT_MIN_PERCENT == 90.0


def test_main_default_include_glob_is_evals_scripts():
    assert gate.DEFAULT_INCLUDE_GLOB == "evals/scripts/*.py"


def test_main_custom_include_glob(capsys, tmp_path):
    # --include-glob stays a real CLI parameter (not hardcoded) so a
    # future repo-wide extension can reuse this script unchanged against
    # a wider glob.
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({"skills/foo/scripts/c.py": 50.0})), encoding="utf-8"
    )
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--include-glob", "skills/*/scripts/*.py",
        "--min-percent", "90",
    ])
    assert rc == 1
    assert "FAIL: skills/foo/scripts/c.py -- 50.0%" in capsys.readouterr().out

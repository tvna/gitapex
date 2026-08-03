"""Tests for the repo-wide coverage-minimum gate
(.github/scripts/gate_evals_scripts_coverage.py).

Refs #536 (retrospective for PR #512, "CI-enforced minimum test coverage
for evals/scripts/*.py"): this gate asserts a per-file coverage floor
from a `coverage json` report, so a low-coverage CLI surface (the PR
#512 finding this follow-up closes) fails CI instead of depending on a
manually dispatched review to catch it.

Refs #562: the gate was originally narrowed to evals/scripts/*.py alone
(several of pyproject.toml's other --cov= targets sat below the 90%
floor at the time). This follow-up widens it to every
pyproject.toml [tool.coverage.run] source directory, deriving that scope
from pyproject.toml itself (read_coverage_sources/source_include_globs)
rather than a second hardcoded copy of the list, so a future new --cov=
target is picked up automatically instead of silently falling outside
this gate.
"""

from __future__ import annotations

import json
import pathlib

import gate_evals_scripts_coverage as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _report(files: dict[str, float]) -> dict:
    return {
        "files": {
            path: {"summary": {"percent_covered": pct}}
            for path, pct in files.items()
        }
    }


# ---------------------------------------------------------------------------
# select_files
# ---------------------------------------------------------------------------


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
    with pytest.raises(ValueError, match=r"no numeric summary\.percent_covered"):
        gate.select_files(data, "evals/scripts/*.py")


def test_select_files_raises_on_bool_percent_covered():
    # Regression: bool is a subclass of int in Python, so
    # isinstance(True, (int, float)) is True -- a malformed report saying
    # percent_covered: true/false must not be silently accepted as a
    # numeric score.
    data = {"files": {"evals/scripts/a.py": {"summary": {"percent_covered": True}}}}
    with pytest.raises(ValueError, match=r"no numeric summary\.percent_covered"):
        gate.select_files(data, "evals/scripts/*.py")


# ---------------------------------------------------------------------------
# select_files_in_source
# ---------------------------------------------------------------------------


def test_select_files_in_source_matches_immediate_children_only():
    data = _report({
        "evals/scripts/a.py": 100.0,
        "evals/scripts/b.py": 80.0,
        "skills/foo/scripts/c.py": 10.0,
    })
    selected = gate.select_files_in_source(data, "evals/scripts")
    assert selected == {"evals/scripts/a.py": 100.0, "evals/scripts/b.py": 80.0}


def test_select_files_in_source_does_not_match_nested_subdirectory_files():
    # The exact bug an adversarial review round caught in this gate's
    # rewrite (issue #562): select_files(data, "evals/*.py") would
    # incorrectly ALSO match "evals/scripts/a.py", since fnmatch's '*'
    # matches '/' too. A source that is a path-prefix of another source's
    # directory must not swallow that other source's files.
    data = _report({
        "evals/top_level.py": 100.0,
        "evals/scripts/a.py": 100.0,
    })
    selected = gate.select_files_in_source(data, "evals")
    assert selected == {"evals/top_level.py": 100.0}


def test_select_files_in_source_does_not_match_sibling_prefixed_directory():
    # "evals" must not match files under a differently-named directory
    # that merely starts with the same characters.
    data = _report({"evals_extra/x.py": 100.0})
    selected = gate.select_files_in_source(data, "evals")
    assert selected == {}


def test_select_files_in_source_ignores_non_py_files_in_the_same_directory():
    data = _report({"evals/scripts/a.py": 100.0, "evals/scripts/README.md": 0.0})
    selected = gate.select_files_in_source(data, "evals/scripts")
    assert selected == {"evals/scripts/a.py": 100.0}


def test_select_files_in_source_strips_trailing_slash_from_source():
    data = _report({"evals/scripts/a.py": 100.0})
    assert gate.select_files_in_source(data, "evals/scripts/") == {"evals/scripts/a.py": 100.0}


def test_select_files_in_source_normalizes_backslash_paths():
    data = _report({"evals\\scripts\\a.py": 55.0})
    selected = gate.select_files_in_source(data, "evals/scripts")
    assert selected == {"evals/scripts/a.py": 55.0}


def test_select_files_in_source_raises_on_missing_files_key():
    with pytest.raises(ValueError, match="no 'files' object"):
        gate.select_files_in_source({}, "evals/scripts")


def test_select_files_in_source_raises_on_non_dict_top_level():
    with pytest.raises(ValueError, match="not a JSON object"):
        gate.select_files_in_source(["not", "a", "dict"], "evals/scripts")


def test_select_files_in_source_raises_on_missing_percent_covered():
    data = {"files": {"evals/scripts/a.py": {"summary": {}}}}
    with pytest.raises(ValueError, match=r"no numeric summary\.percent_covered"):
        gate.select_files_in_source(data, "evals/scripts")


def test_select_files_in_source_raises_on_bool_percent_covered():
    data = {"files": {"evals/scripts/a.py": {"summary": {"percent_covered": False}}}}
    with pytest.raises(ValueError, match=r"no numeric summary\.percent_covered"):
        gate.select_files_in_source(data, "evals/scripts")


# ---------------------------------------------------------------------------
# read_coverage_sources / source_include_globs
# ---------------------------------------------------------------------------


def test_read_coverage_sources_reads_real_pyproject():
    sources = gate.read_coverage_sources(str(REPO_ROOT / "pyproject.toml"))
    # A live tie to the real config, not a hardcoded snapshot: only assert
    # the anchors this gate's own docstring and the .github/scripts
    # self-coverage requirement (issue #562 criterion 3) depend on.
    assert ".github/scripts" in sources
    assert "evals/scripts" in sources


def test_read_coverage_sources_picks_up_a_new_source(tmp_path):
    # Issue #562 criterion 4: a future new --cov= target must not be
    # silently excluded. Simulated here by adding one to a fixture
    # pyproject.toml and confirming it flows straight through.
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.coverage.run]\nsource = ["a/scripts", "b/scripts", "c/new_target"]\n',
        encoding="utf-8",
    )
    sources = gate.read_coverage_sources(str(pyproject))
    assert sources == ["a/scripts", "b/scripts", "c/new_target"]
    assert gate.source_include_globs(sources) == [
        "a/scripts/*.py", "b/scripts/*.py", "c/new_target/*.py",
    ]


def test_source_include_globs_strips_trailing_slash():
    assert gate.source_include_globs(["a/scripts/"]) == ["a/scripts/*.py"]


def test_read_coverage_sources_rejects_missing_file(tmp_path):
    missing = tmp_path / "no-such-pyproject.toml"
    with pytest.raises(ValueError, match="could not read"):
        gate.read_coverage_sources(str(missing))


def test_read_coverage_sources_rejects_malformed_toml(tmp_path):
    bad = tmp_path / "pyproject.toml"
    bad.write_text("not valid toml {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid TOML"):
        gate.read_coverage_sources(str(bad))


def test_read_coverage_sources_rejects_missing_source_key(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.coverage.run]\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"no \[tool\.coverage\.run\] source list"):
        gate.read_coverage_sources(str(pyproject))


def test_read_coverage_sources_rejects_missing_coverage_table(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"no \[tool\.coverage\.run\] source list"):
        gate.read_coverage_sources(str(pyproject))


def test_read_coverage_sources_rejects_non_list_source(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.coverage.run]\nsource = "not-a-list"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a non-empty list of non-blank strings"):
        gate.read_coverage_sources(str(pyproject))


def test_read_coverage_sources_rejects_empty_source_list(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.coverage.run]\nsource = []\n', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a non-empty list of non-blank strings"):
        gate.read_coverage_sources(str(pyproject))


def test_read_coverage_sources_rejects_non_string_source_entries(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.coverage.run]\nsource = ["ok/scripts", 1]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a non-empty list of non-blank strings"):
        gate.read_coverage_sources(str(pyproject))


def test_read_coverage_sources_rejects_a_blank_source_entry(tmp_path):
    # Regression: an earlier version only checked isinstance(item, str),
    # which accepted "" (or whitespace-only) as a source. select_files_in_
    # source(data, "") normalizes to parent="", which matches every
    # top-level *.py file in the coverage report via rpartition("/") --
    # e.g. a stray "setup.py" entry -- silently widening this gate's scope
    # to files nobody declared as a coverage target. Caught by an
    # independent adversarial review round dispatched via /code-review.
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.coverage.run]\nsource = ["ok/scripts", ""]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a non-empty list of non-blank strings"):
        gate.read_coverage_sources(str(pyproject))


def test_read_coverage_sources_rejects_a_whitespace_only_source_entry(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.coverage.run]\nsource = ["ok/scripts", "   "]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a non-empty list of non-blank strings"):
        gate.read_coverage_sources(str(pyproject))


# ---------------------------------------------------------------------------
# main() -- coverage-report handling
# ---------------------------------------------------------------------------


def test_main_missing_report_file_fails_closed(capsys, tmp_path):
    missing = tmp_path / "no-such-report.json"
    rc = gate.main(["--coverage-json", str(missing), "--include-glob", "evals/scripts/*.py"])
    assert rc == 2
    assert "could not read" in capsys.readouterr().err


def test_main_malformed_json_fails_closed(capsys, tmp_path):
    bad = tmp_path / "coverage.json"
    bad.write_text("not json{{{", encoding="utf-8")
    rc = gate.main(["--coverage-json", str(bad), "--include-glob", "evals/scripts/*.py"])
    assert rc == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_main_non_utf8_report_fails_closed(capsys, tmp_path):
    # Regression: a UnicodeDecodeError while reading the file body is
    # neither an OSError nor a json.JSONDecodeError -- an earlier version
    # only caught those two, so a non-UTF-8 report crashed with an
    # uncaught traceback instead of the documented exit 2.
    bad = tmp_path / "coverage.json"
    bad.write_bytes(b"\xff\xfe{\"files\": {}}")
    rc = gate.main(["--coverage-json", str(bad), "--include-glob", "evals/scripts/*.py"])
    assert rc == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_main_malformed_file_entry_fails_closed(capsys, tmp_path):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps({"files": {"evals/scripts/a.py": {"summary": {}}}}),
        encoding="utf-8",
    )
    rc = gate.main(["--coverage-json", str(report_path), "--include-glob", "evals/scripts/*.py"])
    assert rc == 2
    assert "no numeric summary.percent_covered" in capsys.readouterr().err


def test_main_no_matching_files_fails_closed(capsys, tmp_path):
    # A coverage report generated with the wrong scope must not silently
    # pass as "nothing to check" -- that would make this gate a no-op.
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({"skills/foo/scripts/c.py": 10.0})), encoding="utf-8"
    )
    rc = gate.main(["--coverage-json", str(report_path), "--include-glob", "evals/scripts/*.py"])
    assert rc == 2
    assert "no files matching" in capsys.readouterr().err


def test_main_no_matching_files_fails_closed_on_the_first_empty_glob(capsys, tmp_path):
    # With multiple --include-glob targets, a single one matching nothing
    # must still fail closed even though the others matched fine -- this is
    # the per-target version of the check above (issue #562 criterion 4:
    # narrowing any one --cov= target must not hide behind the others).
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({"evals/scripts/a.py": 100.0})), encoding="utf-8"
    )
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--include-glob", "evals/scripts/*.py",
        "--include-glob", ".github/scripts/*.py",
    ])
    assert rc == 2
    assert "no files matching '.github/scripts/*.py'" in capsys.readouterr().err


def test_main_passes_when_all_files_meet_threshold(capsys, tmp_path):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({
            "evals/scripts/a.py": 100.0,
            "evals/scripts/b.py": 92.0,
        })),
        encoding="utf-8",
    )
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--include-glob", "evals/scripts/*.py",
        "--min-percent", "90",
    ])
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
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--include-glob", "evals/scripts/*.py",
        "--min-percent", "90",
    ])
    assert rc == 1
    captured = capsys.readouterr()
    assert "PASS: evals/scripts/a.py -- 100.0% (minimum 90.0%)" in captured.out
    assert "FAIL: evals/scripts/b.py -- 71.0% (minimum 90.0%)" in captured.out
    assert (
        "FAIL: 1 of 2 file(s) matching ['evals/scripts/*.py'] are below the "
        "90.0% minimum coverage threshold"
    ) in captured.err


def test_main_default_min_percent_is_90():
    assert gate.DEFAULT_MIN_PERCENT == 90.0


def test_main_custom_include_glob(capsys, tmp_path):
    # --include-glob stays a real CLI parameter (not hardcoded), overriding
    # the pyproject.toml-derived default so a narrower, one-off check (or
    # this test suite) does not depend on the real repository's coverage.
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


def test_main_include_glob_is_repeatable(capsys, tmp_path):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({
            "evals/scripts/a.py": 100.0,
            ".github/scripts/b.py": 95.0,
        })),
        encoding="utf-8",
    )
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--include-glob", "evals/scripts/*.py",
        "--include-glob", ".github/scripts/*.py",
        "--min-percent", "90",
    ])
    assert rc == 0
    assert "PASS: all 2 file(s)" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main() -- default scope derived from pyproject.toml (issue #562)
# ---------------------------------------------------------------------------


def test_main_default_scope_comes_from_pyproject(capsys, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.coverage.run]\nsource = ["a/scripts", "b/scripts"]\n',
        encoding="utf-8",
    )
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({
            "a/scripts/x.py": 100.0,
            "b/scripts/y.py": 95.0,
        })),
        encoding="utf-8",
    )
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--pyproject", str(pyproject),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PASS: all 2 file(s)" in out


def test_main_default_scope_fails_closed_when_a_source_is_unmeasured(capsys, tmp_path):
    # The drift scenario criterion 4 exists to catch: pyproject.toml grows a
    # new --cov= target, but the coverage report handed to this gate was
    # produced before that target's tests started running (or the pytest
    # invocation's own --cov flags fell out of sync). The gate must not
    # silently pass on the sources it does have data for.
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.coverage.run]\nsource = ["a/scripts", "b/scripts", "c/new_target"]\n',
        encoding="utf-8",
    )
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({
            "a/scripts/x.py": 100.0,
            "b/scripts/y.py": 95.0,
            # c/new_target has no entry at all in this report.
        })),
        encoding="utf-8",
    )
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--pyproject", str(pyproject),
    ])
    assert rc == 2
    assert "no files matching 'c/new_target/*.py'" in capsys.readouterr().err


def test_main_missing_pyproject_fails_closed(capsys, tmp_path):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps(_report({"evals/scripts/a.py": 100.0})), encoding="utf-8")
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--pyproject", str(tmp_path / "no-such-pyproject.toml"),
    ])
    assert rc == 2
    assert "could not read" in capsys.readouterr().err


def test_main_default_scope_handles_a_nested_source_pair_correctly(capsys, tmp_path):
    # End-to-end regression for the nested-source bug (see
    # test_select_files_in_source_does_not_match_nested_subdirectory_files):
    # "evals" is a path-prefix of "evals/scripts". The outer source
    # ("evals") has no file of its own in this report -- it must fail
    # closed reporting itself as unmatched, not silently pass by having
    # its glob swallow "evals/scripts"'s file.
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.coverage.run]\nsource = ["evals", "evals/scripts"]\n',
        encoding="utf-8",
    )
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({"evals/scripts/a.py": 100.0})), encoding="utf-8"
    )
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--pyproject", str(pyproject),
    ])
    assert rc == 2
    assert "no files matching 'evals/*.py'" in capsys.readouterr().err


def test_main_uses_real_pyproject_by_default(capsys, tmp_path, monkeypatch):
    # No --include-glob and no --pyproject given: the default DEFAULT_PYPROJECT
    # ("pyproject.toml") is read relative to the current working directory,
    # same as this gate's real CI invocation from the repository root.
    monkeypatch.chdir(REPO_ROOT)
    sources = gate.read_coverage_sources("pyproject.toml")
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(_report({f"{source}/x.py": 100.0 for source in sources})),
        encoding="utf-8",
    )
    rc = gate.main(["--coverage-json", str(report_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"PASS: all {len(sources)} file(s)" in out


# ---------------------------------------------------------------------------
# main() -- EvalsScriptsCoverageArgs validation (new pydantic-model behavior)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("min_percent", ["-1", "100.1"])
def test_main_rejects_min_percent_outside_0_to_100(capsys, tmp_path, min_percent):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps(_report({"evals/scripts/a.py": 100.0})), encoding="utf-8")
    rc = gate.main([
        "--coverage-json", str(report_path),
        "--include-glob", "evals/scripts/*.py",
        "--min-percent", min_percent,
    ])
    assert rc == 2
    assert "--min-percent must be between 0 and 100" in capsys.readouterr().err

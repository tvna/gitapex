"""Tests for the .gitignore pattern coverage gate
(.github/scripts/gate_gitignore_pattern_coverage.py).

Refs #330 (cited by #519): a `.gitignore` pattern added in a PR must be
referenced by some test under tests/ -- this gate grades the added-pattern
list the calling workflow's merge-base diff hands it, closing the gap left
by tests/test_gitignore_worktrees.py covering only one hardcoded pattern.
"""

from __future__ import annotations

import gate_gitignore_pattern_coverage as gate
from conftest import FakeStdin as _FakeStdin


def _write_test_file(tmp_path, name, content):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / name).write_text(content, encoding="utf-8")


def test_parse_patterns_reads_one_per_line():
    assert gate.parse_patterns("build/\n*.log\n") == ["build/", "*.log"]


def test_parse_patterns_ignores_blank_lines():
    assert gate.parse_patterns("\nbuild/\n\n\n*.log\n\n") == ["build/", "*.log"]


def test_parse_patterns_ignores_comment_lines():
    assert gate.parse_patterns("# a comment\nbuild/\n  # indented comment\n*.log\n") == [
        "build/",
        "*.log",
    ]


def test_parse_patterns_dedupes_preserving_order():
    assert gate.parse_patterns("build/\n*.log\nbuild/\n") == ["build/", "*.log"]


def test_parse_patterns_empty_input_is_empty_list():
    assert gate.parse_patterns("") == []
    assert gate.parse_patterns("\n\n# only comments\n") == []


def test_core_strips_leading_and_trailing_slash():
    assert gate._core("/.claude/worktrees/") == ".claude/worktrees"


def test_core_strips_negation_marker():
    assert gate._core("!important.log") == "important.log"


def test_core_strips_whitespace():
    assert gate._core("  build/  ") == "build"


def test_core_handles_pattern_with_no_slashes():
    assert gate._core("*.log") == "*.log"


def test_find_offenders_pattern_referenced_by_test_passes(tmp_path):
    _write_test_file(
        tmp_path, "test_new_pattern.py",
        'PATTERN = "build/output"\n',
    )
    assert gate.find_offenders(["/build/output/"], tmp_path) == []


def test_find_offenders_pattern_not_referenced_fails(tmp_path):
    _write_test_file(tmp_path, "test_unrelated.py", "def test_x():\n    assert True\n")
    offenders = gate.find_offenders(["/build/output/"], tmp_path)
    assert len(offenders) == 1
    assert "/build/output/" in offenders[0]


def test_find_offenders_no_tests_directory_fails(tmp_path):
    offenders = gate.find_offenders(["/build/"], tmp_path)
    assert len(offenders) == 1


def test_find_offenders_multiple_patterns_reported_independently(tmp_path):
    _write_test_file(tmp_path, "test_covered.py", 'PATTERN = "covered/path"\n')
    offenders = gate.find_offenders(["/covered/path/", "/uncovered/path/"], tmp_path)
    assert len(offenders) == 1
    assert "/uncovered/path/" in offenders[0]


def test_find_offenders_does_not_match_substring_within_larger_word(tmp_path):
    # Regression: a plain `core in source` substring check would treat
    # "build" as covered merely because "rebuild_step" and "build_id"
    # contain it as a fragment -- neither actually references the
    # "/build/" pattern itself.
    _write_test_file(
        tmp_path, "test_unrelated_words.py",
        'REBUILD = "rebuild_step"\nBUILD_ID = "build_id"\n',
    )
    offenders = gate.find_offenders(["/build/"], tmp_path)
    assert len(offenders) == 1
    assert "/build/" in offenders[0]


def test_find_offenders_matches_core_as_standalone_token(tmp_path):
    # Same core ("build") as above, but this time genuinely referenced as
    # its own token (quoted path segment) -- must still be found.
    _write_test_file(tmp_path, "test_real_reference.py", 'PATTERN = "build/output"\n')
    assert gate.find_offenders(["/build/"], tmp_path) == []


def test_find_offenders_searches_nested_test_files(tmp_path):
    nested_dir = tmp_path / "tests" / "sub"
    nested_dir.mkdir(parents=True)
    (nested_dir / "test_nested.py").write_text('PATTERN = "nested/path"\n', encoding="utf-8")
    assert gate.find_offenders(["/nested/path/"], tmp_path) == []


def test_main_no_added_patterns_passes(capsys):
    assert gate.main(["--added", "/dev/null"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reads_patterns_from_stdin(monkeypatch, tmp_path, capsys):
    _write_test_file(tmp_path, "test_covered.py", 'PATTERN = "covered/path"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"/covered/path/\n"))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reports_error_for_non_utf8_stdin(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert gate.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "could not read" in err
    assert "Traceback" not in err


def test_main_reads_patterns_from_file(monkeypatch, tmp_path, capsys):
    _write_test_file(tmp_path, "test_covered.py", 'PATTERN = "covered/path"\n')
    monkeypatch.chdir(tmp_path)
    added_file = tmp_path / "added.txt"
    added_file.write_text("/covered/path/\n", encoding="utf-8")
    assert gate.main(["--added", str(added_file)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_and_reports_offenders(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    added_file = tmp_path / "added.txt"
    added_file.write_text("/uncovered/path/\n", encoding="utf-8")
    assert gate.main(["--added", str(added_file)]) == 1
    err = capsys.readouterr().err
    assert "/uncovered/path/" in err


def test_main_reports_error_for_missing_added_file(capsys):
    assert gate.main(["--added", "/no/such/file.txt"]) == 1
    assert "could not read" in capsys.readouterr().err


def test_main_reports_error_for_unreadable_added_path(tmp_path, capsys):
    # Regression: a directory path raises IsADirectoryError, not
    # FileNotFoundError -- only catching FileNotFoundError let this class
    # of OSError crash with an unhandled traceback instead of the intended
    # graceful error message.
    assert gate.main(["--added", str(tmp_path)]) == 1
    assert "could not read" in capsys.readouterr().err


def test_main_reports_error_for_undecodable_added_file(tmp_path, capsys):
    # Regression: a non-UTF-8 added-lines file raised an unhandled
    # UnicodeDecodeError instead of the intended graceful error message.
    added_file = tmp_path / "added.txt"
    added_file.write_bytes(b"\xff\xfe bad")
    assert gate.main(["--added", str(added_file)]) == 1
    assert "could not read" in capsys.readouterr().err

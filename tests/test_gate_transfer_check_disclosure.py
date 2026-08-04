"""Tests for the Transfer-check disclosure gate
(.github/scripts/gate_transfer_check_disclosure.py).

Issue #517 (refs #487): every newly-added Kept-edit-log '**Iteration:'
entry in a diff over evals/*/split.md must disclose a 'Transfer check'
line within its own entry span, computed against the *current* on-disk
file content (never a diff hunk), diff-scoped to only entries whose own
header line is new in this diff.
"""

from __future__ import annotations

import gate_transfer_check_disclosure as gate
from conftest import FakeStdin as _FakeStdin

_ENTRY_WITH_TRANSFER_CHECK = """\
## Kept-edit log

**Iteration: issue #1, first edit.**
Some prose about the edit.

**Transfer check:** PASS, recorded here.

## Rejected-edit log
"""

_ENTRY_WITHOUT_TRANSFER_CHECK = """\
## Kept-edit log

**Iteration: issue #2, second edit.**
Some prose about the edit, nothing else disclosed in this span.

## Rejected-edit log
"""

_TWO_ENTRIES_SECOND_MISSING = """\
## Kept-edit log

**Iteration: issue #1, first edit.**
**Transfer check:** not run this iteration.

**Iteration: issue #2, second edit.**
Nothing else disclosed here.
"""


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_entry_with_transfer_check_passes(tmp_path):
    path = _write(tmp_path, "split.md", _ENTRY_WITH_TRANSFER_CHECK)
    entries = [(path, "**Iteration: issue #1, first edit.**")]
    assert gate.find_missing_transfer_checks(entries) == []


def test_entry_without_transfer_check_fails(tmp_path):
    path = _write(tmp_path, "split.md", _ENTRY_WITHOUT_TRANSFER_CHECK)
    entries = [(path, "**Iteration: issue #2, second edit.**")]
    assert gate.find_missing_transfer_checks(entries) == entries


def test_entry_span_stops_at_next_iteration_line(tmp_path):
    path = _write(tmp_path, "split.md", _TWO_ENTRIES_SECOND_MISSING)
    entries = [
        (path, "**Iteration: issue #1, first edit.**"),
        (path, "**Iteration: issue #2, second edit.**"),
    ]
    missing = gate.find_missing_transfer_checks(entries)
    assert missing == [(path, "**Iteration: issue #2, second edit.**")]


def test_transfer_check_match_is_case_insensitive(tmp_path):
    content = "## Kept-edit log\n\n**Iteration: X.**\ntransfer CHECK: ran fine.\n"
    path = _write(tmp_path, "split.md", content)
    entries = [(path, "**Iteration: X.**")]
    assert gate.find_missing_transfer_checks(entries) == []


def test_missing_file_reported_as_failure(tmp_path):
    entries = [(str(tmp_path / "does-not-exist.md"), "**Iteration: X.**")]
    assert gate.find_missing_transfer_checks(entries) == entries


def test_missing_file_warning_surfaces_the_actual_reason(tmp_path, capsys):
    missing_path = str(tmp_path / "does-not-exist.md")
    gate.find_missing_transfer_checks([(missing_path, "**Iteration: X.**")])
    err = capsys.readouterr().err
    assert missing_path in err
    assert "No such file" in err or "not found" in err.lower()


def test_unmatched_iteration_line_reported_as_failure(tmp_path):
    path = _write(tmp_path, "split.md", _ENTRY_WITH_TRANSFER_CHECK)
    entries = [(path, "**Iteration: does not exist in file.**")]
    assert gate.find_missing_transfer_checks(entries) == entries


def test_no_entries_is_a_no_op():
    assert gate.find_missing_transfer_checks([]) == []


def test_entry_under_rejected_edit_log_is_out_of_scope(tmp_path):
    # Issue #517 review finding: the requirement is scoped specifically to
    # '## Kept-edit log', not any '##' section a split.md happens to
    # contain. A candidate edit rejected before a transfer check was ever
    # relevant must not be flagged.
    content = (
        "## Kept-edit log\n\n"
        "None yet.\n\n"
        "## Rejected-edit log\n\n"
        "**Iteration: rejected candidate, no transfer check.**\n"
        "Rejected for an unrelated reason, nothing else disclosed here.\n"
    )
    path = _write(tmp_path, "split.md", content)
    entries = [(path, "**Iteration: rejected candidate, no transfer check.**")]
    assert gate.find_missing_transfer_checks(entries) == []


def test_entry_with_no_heading_above_it_is_out_of_scope(tmp_path):
    content = "**Iteration: no heading above this at all.**\nNo section heading precedes this entry.\n"
    path = _write(tmp_path, "split.md", content)
    entries = [(path, "**Iteration: no heading above this at all.**")]
    assert gate.find_missing_transfer_checks(entries) == []


def test_duplicate_header_text_first_occurrence_compliant_second_is_not(tmp_path):
    # Two entries share byte-identical '**Iteration:' header text: the
    # first (earlier in the file) discloses a Transfer check, the second
    # (the genuinely new one) does not. Naive first-match text search
    # would wrongly grade the second against the first's (compliant) span.
    content = (
        "## Kept-edit log\n\n"
        "**Iteration: dup.**\n"
        "**Transfer check:** PASS, recorded here.\n\n"
        "**Iteration: dup.**\n"
        "Nothing else disclosed for this one.\n"
    )
    path = _write(tmp_path, "split.md", content)
    entries = [(path, "**Iteration: dup.**"), (path, "**Iteration: dup.**")]
    missing = gate.find_missing_transfer_checks(entries)
    assert missing == [(path, "**Iteration: dup.**")]
    assert len(missing) == 1


def test_duplicate_header_text_both_missing_reports_both(tmp_path):
    content = (
        "## Kept-edit log\n\n"
        "**Iteration: dup.**\n"
        "Nothing disclosed for the first.\n\n"
        "**Iteration: dup.**\n"
        "Nothing disclosed for the second either.\n"
    )
    path = _write(tmp_path, "split.md", content)
    entries = [(path, "**Iteration: dup.**"), (path, "**Iteration: dup.**")]
    missing = gate.find_missing_transfer_checks(entries)
    assert missing == entries


def test_third_duplicate_beyond_actual_occurrences_reported_as_unmatched(tmp_path):
    # Only two physical '**Iteration: dup.**' lines exist in the file, but
    # three tuples are supplied (e.g. a bash-side miscount) -- the third
    # must not silently re-match an already-consumed line.
    content = (
        "## Kept-edit log\n\n"
        "**Iteration: dup.**\n"
        "**Transfer check:** PASS.\n\n"
        "**Iteration: dup.**\n"
        "**Transfer check:** PASS.\n"
    )
    path = _write(tmp_path, "split.md", content)
    entries = [
        (path, "**Iteration: dup.**"),
        (path, "**Iteration: dup.**"),
        (path, "**Iteration: dup.**"),
    ]
    missing = gate.find_missing_transfer_checks(entries)
    assert missing == [(path, "**Iteration: dup.**")]


def test_reworded_but_untouched_transfer_check_line_still_counts(tmp_path):
    # The entry's own header line is "new" in this diff (e.g. a rename or
    # rewording), but its pre-existing Transfer check line a few lines
    # below was not itself touched -- reading current on-disk content
    # (not a diff hunk) must still find it.
    content = (
        "## Kept-edit log\n\n"
        "**Iteration: issue #3, reworded header.**\n"
        "Unrelated prose line one.\n"
        "Unrelated prose line two.\n"
        "**Transfer check:** not run this iteration, unchanged from before.\n"
    )
    path = _write(tmp_path, "split.md", content)
    entries = [(path, "**Iteration: issue #3, reworded header.**")]
    assert gate.find_missing_transfer_checks(entries) == []


# --- _parse_entries ---


def test_parse_entries_splits_on_first_tab():
    text = "evals/foo/split.md\t**Iteration: a.**\nevals/bar/split.md\t**Iteration: b\tc.**\n"
    assert gate._parse_entries(text) == [
        ("evals/foo/split.md", "**Iteration: a.**"),
        ("evals/bar/split.md", "**Iteration: b\tc.**"),
    ]


def test_parse_entries_skips_blank_lines_and_lines_with_no_tab():
    text = "\nno-tab-here\nevals/foo/split.md\t**Iteration: a.**\n\n"
    assert gate._parse_entries(text) == [("evals/foo/split.md", "**Iteration: a.**")]


# --- main() ---


def test_main_passes_with_no_entries(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b""))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_passes_when_all_entries_disclose_transfer_check(tmp_path, monkeypatch, capsys):
    path = _write(tmp_path, "split.md", _ENTRY_WITH_TRANSFER_CHECK)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"{path}\t**Iteration: issue #1, first edit.**\n".encode()))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_when_an_entry_is_missing_transfer_check(tmp_path, monkeypatch, capsys):
    path = _write(tmp_path, "split.md", _ENTRY_WITHOUT_TRANSFER_CHECK)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"{path}\t**Iteration: issue #2, second edit.**\n".encode()))
    assert gate.main([]) == 1
    err = capsys.readouterr().err
    assert "Transfer check" in err
    assert path in err


def test_main_reads_entries_from_file(tmp_path, capsys):
    split_path = _write(tmp_path, "split.md", _ENTRY_WITH_TRANSFER_CHECK)
    entries_path = tmp_path / "entries.tsv"
    entries_path.write_text(f"{split_path}\t**Iteration: issue #1, first edit.**\n", encoding="utf-8")
    assert gate.main(["--entries", str(entries_path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reports_error_for_missing_entries_file(capsys):
    assert gate.main(["--entries", "/no/such/file.tsv"]) == 1
    assert "not found" in capsys.readouterr().err


def test_main_reports_error_for_non_utf8_entries_file(tmp_path, capsys):
    path = tmp_path / "entries.tsv"
    path.write_bytes(b"\xff\xfe bad")
    assert gate.main(["--entries", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert gate.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_truncates_long_iteration_snippets_in_failure_output(tmp_path, monkeypatch, capsys):
    long_line = "**Iteration: " + ("x" * 200) + ".**"
    content = f"## Kept-edit log\n\n{long_line}\nNothing else disclosed here.\n"
    path = _write(tmp_path, "split.md", content)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"{path}\t{long_line}\n".encode()))
    assert gate.main([]) == 1
    err = capsys.readouterr().err
    assert "..." in err

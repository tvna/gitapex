"""Tests for the Transfer-check disclosure gate
(.github/scripts/gitapex_gate_transfer_check_disclosure.py).

Issue #928 (split.md/split.json migration, task T10): every `##
Iteration:` entry in every `evals/*/split.md` file must disclose a
non-empty `### Transfer check` subsection within its own span -- a
whole-file audit, every entry, not scoped to a diff, and no longer scoped
to a `## Kept-edit log` heading (that heading no longer exists after the
migration; the widened requirement covers REJECT entries too). The old
`**Iteration:` bold-paragraph form is no longer recognized at all.
"""

from __future__ import annotations

import gitapex_gate_transfer_check_disclosure as gate
from conftest import FakeStdin as _FakeStdin

_ENTRY_WITH_TRANSFER_CHECK = """\
## Iteration: issue #1, first edit.

Some prose about the edit.

### Transfer check

Re-ran on an adjacent tier: PASS, recorded here.

### Verdict

KEEP.
"""

_ENTRY_WITHOUT_TRANSFER_CHECK_HEADING = """\
## Iteration: issue #2, second edit.

Some prose about the edit, nothing else disclosed in this span.

### Verdict

KEEP.
"""

_ENTRY_WITH_EMPTY_TRANSFER_CHECK_HEADING = """\
## Iteration: issue #3, third edit.

Some prose about the edit.

### Transfer check

### Verdict

KEEP.
"""

_TWO_ENTRIES_SECOND_MISSING = """\
## Iteration: issue #1, first edit.

### Transfer check

Not run this iteration.

## Iteration: issue #2, second edit.

Nothing else disclosed here.
"""

_OLD_BOLD_PARAGRAPH_FORM = """\
## Kept-edit log

**Iteration: issue #4, old convention.**
Some prose about the edit.

**Transfer check:** PASS, recorded here.

## Rejected-edit log
"""


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_entry_with_transfer_check_passes(tmp_path):
    path = _write(tmp_path, "split.md", _ENTRY_WITH_TRANSFER_CHECK)
    assert gate.find_missing_transfer_checks([path]) == []


def test_entry_missing_transfer_check_heading_fails(tmp_path):
    path = _write(tmp_path, "split.md", _ENTRY_WITHOUT_TRANSFER_CHECK_HEADING)
    missing = gate.find_missing_transfer_checks([path])
    assert missing == [(path, "## Iteration: issue #2, second edit.")]


def test_entry_with_empty_transfer_check_heading_fails(tmp_path):
    # The heading exists but discloses nothing -- exactly as non-compliant
    # as a wholly-absent heading, not silently treated as compliant merely
    # because the markup is present.
    path = _write(tmp_path, "split.md", _ENTRY_WITH_EMPTY_TRANSFER_CHECK_HEADING)
    missing = gate.find_missing_transfer_checks([path])
    assert missing == [(path, "## Iteration: issue #3, third edit.")]


def test_old_bold_paragraph_iteration_form_is_no_longer_recognized(tmp_path):
    # Drop the old '**Iteration:' bold-paragraph recognition entirely --
    # after the split.md/split.json migration, no file uses it any more.
    # A file still carrying that convention (e.g. mid-migration, or a
    # test fixture) must be scanned as having zero '## Iteration:'
    # entries, not matched against the old form.
    path = _write(tmp_path, "split.md", _OLD_BOLD_PARAGRAPH_FORM)
    assert gate.find_missing_transfer_checks([path]) == []


def test_entry_span_stops_at_next_h2_heading(tmp_path):
    path = _write(tmp_path, "split.md", _TWO_ENTRIES_SECOND_MISSING)
    missing = gate.find_missing_transfer_checks([path])
    assert missing == [(path, "## Iteration: issue #2, second edit.")]


def test_transfer_check_heading_matched_case_insensitively(tmp_path):
    content = "## Iteration: X.\n\n### transfer CHECK\n\nran fine on Haiku.\n"
    path = _write(tmp_path, "split.md", content)
    assert gate.find_missing_transfer_checks([path]) == []


def test_iteration_heading_matched_case_insensitively(tmp_path):
    content = "## iteration: lowercase heading word.\n\n### Transfer check\n\nran fine.\n"
    path = _write(tmp_path, "split.md", content)
    assert gate.find_missing_transfer_checks([path]) == []


def test_title_less_iteration_heading_is_still_recognized_and_flagged(tmp_path):
    # issue #928 adversarial review finding 2: a heading of bare
    # '## Iteration:' (or with only trailing whitespace -- a plausible
    # authoring mistake where the entry was added before its title was
    # filled in) must not be invisible to this scan. Before the fix, the
    # stricter `(\S.*)$` pattern failed to match this line at all, so the
    # entry's own missing Transfer check went completely unreported.
    content = "## Iteration:\n\nNothing else disclosed here.\n"
    path = _write(tmp_path, "split.md", content)
    missing = gate.find_missing_transfer_checks([path])
    assert missing == [(path, "## Iteration:")]


def test_title_less_iteration_heading_with_trailing_whitespace_is_recognized(tmp_path):
    content = "## Iteration:   \n\nNothing else disclosed here.\n"
    path = _write(tmp_path, "split.md", content)
    missing = gate.find_missing_transfer_checks([path])
    assert missing == [(path, "## Iteration:")]


def test_missing_file_reported_as_failure(tmp_path):
    missing_path = str(tmp_path / "does-not-exist.md")
    assert gate.find_missing_transfer_checks([missing_path]) == [(missing_path, "<file unreadable>")]


def test_missing_file_warning_surfaces_the_actual_reason(tmp_path, capsys):
    missing_path = str(tmp_path / "does-not-exist.md")
    gate.find_missing_transfer_checks([missing_path])
    err = capsys.readouterr().err
    assert missing_path in err
    assert "No such file" in err or "not found" in err.lower()


def test_no_entries_is_a_no_op(tmp_path):
    path = _write(tmp_path, "split.md", "# Held-out split\n\nNo iterations recorded yet.\n")
    assert gate.find_missing_transfer_checks([path]) == []


def test_whole_file_scan_checks_every_entry_not_only_the_last(tmp_path):
    # Whole-file, not diff-scoped: every '## Iteration:' entry the file
    # currently contains is in scope, regardless of position -- an
    # earlier, pre-existing entry missing its Transfer check is flagged
    # exactly as a newly-added one would be.
    content = (
        "## Iteration: issue #1, oldest, non-compliant.\n\n"
        "Nothing disclosed here.\n\n"
        "## Iteration: issue #2, middle, compliant.\n\n"
        "### Transfer check\n\nran fine.\n\n"
        "## Iteration: issue #3, newest, non-compliant.\n\n"
        "Nothing disclosed here either.\n"
    )
    path = _write(tmp_path, "split.md", content)
    missing = gate.find_missing_transfer_checks([path])
    assert missing == [
        (path, "## Iteration: issue #1, oldest, non-compliant."),
        (path, "## Iteration: issue #3, newest, non-compliant."),
    ]


def test_multiple_files_are_all_scanned(tmp_path):
    good_path = _write(tmp_path, "good.md", _ENTRY_WITH_TRANSFER_CHECK)
    bad_path = _write(tmp_path, "bad.md", _ENTRY_WITHOUT_TRANSFER_CHECK_HEADING)
    missing = gate.find_missing_transfer_checks([good_path, bad_path])
    assert missing == [(bad_path, "## Iteration: issue #2, second edit.")]


def test_transfer_check_content_only_looks_within_its_own_entry(tmp_path):
    # A '### Transfer check' subsection belonging to one entry must never
    # be credited to a different entry that has none of its own, even
    # when the compliant one comes first in the file.
    content = (
        "## Iteration: issue #1, has a transfer check.\n\n"
        "### Transfer check\n\nran fine.\n\n"
        "## Iteration: issue #2, has none of its own.\n\n"
        "Nothing here.\n"
    )
    path = _write(tmp_path, "split.md", content)
    missing = gate.find_missing_transfer_checks([path])
    assert missing == [(path, "## Iteration: issue #2, has none of its own.")]


# --- _default_paths / main() ---


def test_default_paths_globs_evals_split_md(tmp_path, monkeypatch):
    (tmp_path / "evals" / "some-skill").mkdir(parents=True)
    (tmp_path / "evals" / "other-skill").mkdir(parents=True)
    (tmp_path / "evals" / "some-skill" / "split.md").write_text(_ENTRY_WITH_TRANSFER_CHECK, encoding="utf-8")
    (tmp_path / "evals" / "other-skill" / "split.md").write_text(
        _ENTRY_WITHOUT_TRANSFER_CHECK_HEADING, encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    paths = gate._default_paths()
    assert paths == sorted(
        [
            "evals/some-skill/split.md",
            "evals/other-skill/split.md",
        ]
    )


def test_main_fails_closed_with_no_matching_files(tmp_path, monkeypatch, capsys):
    # issue #928 adversarial review finding 3: zero files matched by the
    # default glob (wrong working directory, or a checkout that lost most
    # of evals/) must not read as "nothing to check, PASS" -- that is the
    # same fail-open shape PR #651's own precedent named.
    monkeypatch.chdir(tmp_path)
    assert gate.main([]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_fails_closed_below_min_expected_split_md_floor(tmp_path, monkeypatch, capsys):
    # One real file found is still a discovery-failure shape, not a
    # legitimately tiny repository -- same floor rationale as
    # gitapex_scan_split_schema.py's own MIN_EXPECTED_SPLIT_JSON_FILES.
    monkeypatch.chdir(tmp_path)
    skill_dir = tmp_path / "evals" / "only-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "split.md").write_text(_ENTRY_WITH_TRANSFER_CHECK, encoding="utf-8")
    assert gate.main([]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_explicit_paths_are_never_subject_to_the_min_expected_floor(tmp_path, capsys):
    # The floor applies only to default-glob discovery; a caller passing an
    # explicit (even short) path list is trusted as-is.
    path = _write(tmp_path, "split.md", _ENTRY_WITH_TRANSFER_CHECK)
    assert gate.main([path]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_passes_when_all_entries_disclose_transfer_check(tmp_path, capsys):
    path = _write(tmp_path, "split.md", _ENTRY_WITH_TRANSFER_CHECK)
    assert gate.main([path]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_when_an_entry_is_missing_transfer_check(tmp_path, capsys):
    path = _write(tmp_path, "split.md", _ENTRY_WITHOUT_TRANSFER_CHECK_HEADING)
    assert gate.main([path]) == 1
    err = capsys.readouterr().err
    assert "Transfer check" in err
    assert path in err


def test_main_checks_multiple_explicit_paths(tmp_path, capsys):
    good_path = _write(tmp_path, "good.md", _ENTRY_WITH_TRANSFER_CHECK)
    bad_path = _write(tmp_path, "bad.md", _ENTRY_WITHOUT_TRANSFER_CHECK_HEADING)
    assert gate.main([good_path, bad_path]) == 1
    err = capsys.readouterr().err
    assert bad_path in err
    assert good_path not in err


def test_main_truncates_long_iteration_headings_in_failure_output(tmp_path, capsys):
    long_heading = "## Iteration: " + ("x" * 200) + "."
    content = f"{long_heading}\n\nNothing else disclosed here.\n"
    path = _write(tmp_path, "split.md", content)
    assert gate.main([path]) == 1
    err = capsys.readouterr().err
    assert "..." in err


def test_args_defaults_paths_to_empty_list():
    validated = gate.TransferCheckDisclosureArgs()
    assert validated.paths == []


def test_args_accepts_an_explicit_paths_list():
    validated = gate.TransferCheckDisclosureArgs(paths=["a.md", "b.md"])
    assert validated.paths == ["a.md", "b.md"]


def test_main_uses_stdin_free_cli(tmp_path, monkeypatch):
    # This gate no longer reads a workflow-computed entries list from
    # stdin at all -- confirm gate.sys.stdin is simply never touched,
    # even by a no-args invocation that falls back to the default glob.
    # Above MIN_EXPECTED_SPLIT_MD_FILES so the discovery-floor check (a
    # separate concern from this test) does not also fire here.
    monkeypatch.chdir(tmp_path)
    for skill in ("skill-a", "skill-b", "skill-c"):
        skill_dir = tmp_path / "evals" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "split.md").write_text(_ENTRY_WITH_TRANSFER_CHECK, encoding="utf-8")
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"should never be read"))
    assert gate.main([]) == 0

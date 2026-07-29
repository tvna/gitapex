"""Tests for .github/scripts/extract_diff_added_lines.py.

Issue #552: the prior bash `grep -E '^\\+[^+]' | sed 's/^\\+//'` extraction
dropped every blank-line-only diff addition, collapsing per-file paragraph
structure -- and file-to-file boundaries -- into one blob, producing false
positives in gate_provenance_disclosure.py's own paragraph-scoped check.

A fresh adversarial review (before this fix ever merged) found the first
cut of this fix left one more instance of the identical defect class:
two non-adjacent hunks within the *same* file also collapsed into one
paragraph, since only file boundaries forced a separator, not hunk
boundaries. `test_multiple_hunks_in_same_file_get_a_separator` and the
hunk-boundary branch in `extract_diff_added_lines.py` close that gap.
"""

from __future__ import annotations

import re

import extract_diff_added_lines as extractor
import gate_provenance_disclosure as gate

_SINGLE_FILE_DIFF = """\
diff --git a/docs/foo.md b/docs/foo.md
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/docs/foo.md
@@ -0,0 +1,5 @@
+# Title
+
+Paragraph one.
+
+Paragraph two.
"""

_TWO_FILE_DIFF = """\
diff --git a/docs/a.md b/docs/a.md
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/docs/a.md
@@ -0,0 +1,1 @@
+File A's own last line, not blank.
diff --git a/docs/b.md b/docs/b.md
new file mode 100644
index 0000000..2222222
--- /dev/null
+++ b/docs/b.md
@@ -0,0 +1,1 @@
+File B's own first line.
"""

_LITERAL_PLUS_CONTENT_DIFF = """\
diff --git a/docs/c.md b/docs/c.md
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/docs/c.md
@@ -0,0 +1,1 @@
++1 to this idea.
"""

_DELETION_ONLY_DIFF = """\
diff --git a/docs/d.md b/docs/d.md
deleted file mode 100644
index 4444444..0000000
--- a/docs/d.md
+++ /dev/null
@@ -1,1 +0,0 @@
-This line was removed, not added.
"""

_MULTI_HUNK_SAME_FILE_DIFF = """\
diff --git a/docs/crosshunk.md b/docs/crosshunk.md
index 4444444..5555555 100644
--- a/docs/crosshunk.md
+++ b/docs/crosshunk.md
@@ -3 +3 @@
-Old placeholder line near the top of the file.
+This hunk's own edit, unrelated to the second one below.
@@ -13 +13 @@
-Old placeholder line near the bottom of the file.
+A second, physically distant edit in the very same file.
"""

_MULTI_HUNK_SECOND_HUNK_PURE_DELETION_DIFF = """\
diff --git a/docs/e.md b/docs/e.md
index 6666666..7777777 100644
--- a/docs/e.md
+++ b/docs/e.md
@@ -1 +1 @@
-Old first line.
+New first line, the only added content in this file.
@@ -9 +8,0 @@
-A line deleted with no replacement -- this hunk adds nothing.
"""

_THREE_FILE_DIFF_WITH_RENAME = """\
diff --git a/docs/old-name.md b/docs/new-name.md
similarity index 60%
rename from docs/old-name.md
rename to docs/new-name.md
index 8888888..9999999 100644
--- a/docs/old-name.md
+++ b/docs/new-name.md
@@ -1 +1 @@
-Original first line before the rename-with-rewrite.
+Rewritten first line after the rename.
"""


def _split_paragraphs(text: str) -> list[str]:
    """Match gate_provenance_disclosure's own `_paragraphs()` blank-line
    split, without reaching into that module's private function."""
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def test_single_file_preserves_blank_lines():
    files = extractor.extract_added_lines_by_file(_SINGLE_FILE_DIFF)
    assert files == [["# Title", "", "Paragraph one.", "", "Paragraph two."]]


def test_corpus_has_blank_line_between_paragraphs():
    corpus = extractor.build_added_corpus(_SINGLE_FILE_DIFF)
    assert _split_paragraphs(corpus) == ["# Title", "Paragraph one.", "Paragraph two."]


def test_two_files_get_a_separator_even_when_first_file_ends_non_blank():
    corpus = extractor.build_added_corpus(_TWO_FILE_DIFF)
    assert _split_paragraphs(corpus) == [
        "File A's own last line, not blank.",
        "File B's own first line.",
    ]


def test_content_line_starting_with_literal_plus_is_preserved_not_dropped():
    files = extractor.extract_added_lines_by_file(_LITERAL_PLUS_CONTENT_DIFF)
    assert files == [["+1 to this idea."]]


def test_deletion_only_file_contributes_nothing():
    files = extractor.extract_added_lines_by_file(_DELETION_ONLY_DIFF)
    assert files == [[]]
    assert extractor.build_added_corpus(_DELETION_ONLY_DIFF) == ""


def test_empty_diff_produces_empty_corpus():
    assert extractor.build_added_corpus("") == ""


def test_preamble_before_first_diff_git_line_is_ignored():
    diff_text = (
        "some notice line git diff itself would never emit, defensively "
        "ignored rather than assumed impossible\n" + _SINGLE_FILE_DIFF
    )
    assert extractor.extract_added_lines_by_file(diff_text) == [
        ["# Title", "", "Paragraph one.", "", "Paragraph two."]
    ]


def test_multiple_hunks_in_same_file_get_a_separator():
    """Two edits ~10 lines apart in the same file, with an untouched
    paragraph physically between them -- must not collapse into one
    paragraph just because both belong to the same file."""
    corpus = extractor.build_added_corpus(_MULTI_HUNK_SAME_FILE_DIFF)
    assert _split_paragraphs(corpus) == [
        "This hunk's own edit, unrelated to the second one below.",
        "A second, physically distant edit in the very same file.",
    ]
    assert gate.find_offending_paragraphs(corpus) == []


def test_hunk_contributing_nothing_does_not_force_a_stray_separator():
    """A pure-deletion hunk between two content-bearing hunks (or, as
    here, after the only content-bearing one) must not leave a dangling
    blank-line artifact -- the separator is only inserted ahead of a
    *later* hunk that goes on to contribute its own content, and an
    already-blank tail is never doubled."""
    files = extractor.extract_added_lines_by_file(
        _MULTI_HUNK_SECOND_HUNK_PURE_DELETION_DIFF
    )
    assert files == [["New first line, the only added content in this file."]]


def test_rename_with_rewrite_and_second_file_both_extract_correctly():
    corpus = extractor.build_added_corpus(_THREE_FILE_DIFF_WITH_RENAME)
    assert _split_paragraphs(corpus) == ["Rewritten first line after the rename."]


def _old_buggy_extraction(diff_text: str) -> str:
    """Reimplementation of the pre-#552 bash pipeline
    (`grep -E '^\\+[^+]' | sed 's/^\\+//'`), kept only to demonstrate the
    contrast the regression test below relies on -- not used by the
    shipped fix."""
    lines = []
    for line in diff_text.splitlines():
        if re.match(r"^\+[^+]", line):
            lines.append(line[1:])
    return "\n".join(lines)


_REGRESSION_TWO_FILE_DIFF = """\
diff --git a/docs/one.md b/docs/one.md
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/docs/one.md
@@ -0,0 +1,3 @@
+# Notes
+
+This confirms by reading the source -- never by the absence of a
+mention in its documentation -- that state is read correctly.
diff --git a/docs/two.md b/docs/two.md
new file mode 100644
index 0000000..2222222
--- /dev/null
+++ b/docs/two.md
@@ -0,0 +1,2 @@
+## Subagent dispatch
+
+Run this skill's Procedure inside a fresh, isolated subagent dispatch.
"""


def test_regression_multi_file_addition_no_longer_false_positives():
    """The exact failure shape issue #552 reports: two unrelated
    sentences -- one carrying a limitation cue, one carrying a tool cue --
    land in different files/paragraphs of the same PR. The old extraction
    collapsed them into one blob and falsely combined the two cues; the
    new extraction keeps them in separate paragraphs, so
    find_offending_paragraphs must report zero matches."""
    old_corpus = _old_buggy_extraction(_REGRESSION_TWO_FILE_DIFF)
    assert gate.find_offending_paragraphs(old_corpus), (
        "the old extraction's own blank-line-stripping bug is expected to "
        "still merge these two files into one falsely-flagged paragraph -- "
        "if this assertion ever fails, the contrast this regression test "
        "relies on no longer holds and the test itself needs revisiting"
    )

    new_corpus = extractor.build_added_corpus(_REGRESSION_TWO_FILE_DIFF)
    assert gate.find_offending_paragraphs(new_corpus) == []


def test_main_reads_stdin_and_writes_corpus(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(_SINGLE_FILE_DIFF))
    exit_code = extractor.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "# Title" in out
    assert "\n\n" in out  # paragraph separator survived to stdout


def test_main_empty_diff_writes_nothing(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    exit_code = extractor.main()
    assert exit_code == 0
    assert capsys.readouterr().out == ""

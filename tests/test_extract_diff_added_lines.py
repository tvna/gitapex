"""Tests for .github/scripts/extract_diff_added_lines.py.

Issue #552: the prior bash `grep -E '^\\+[^+]' | sed 's/^\\+//'` extraction
dropped every blank-line-only diff addition, collapsing per-file paragraph
structure -- and file-to-file boundaries -- into one blob, producing false
positives in gate_provenance_disclosure.py's own paragraph-scoped check.
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


def test_single_file_preserves_blank_lines():
    files = extractor.extract_added_lines_by_file(_SINGLE_FILE_DIFF)
    assert files == [["# Title", "", "Paragraph one.", "", "Paragraph two."]]


def test_corpus_has_blank_line_between_paragraphs():
    corpus = extractor.build_added_corpus(_SINGLE_FILE_DIFF)
    paragraphs = [p for p in re.split(r"\n\s*\n", corpus) if p.strip()]
    assert paragraphs == ["# Title", "Paragraph one.", "Paragraph two."]


def test_two_files_get_a_separator_even_when_first_file_ends_non_blank():
    corpus = extractor.build_added_corpus(_TWO_FILE_DIFF)
    paragraphs = [p for p in re.split(r"\n\s*\n", corpus) if p.strip()]
    assert paragraphs == [
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


def test_regression_multi_file_addition_no_longer_false_positives():
    """The exact failure shape issue #552 reports: two unrelated
    sentences -- one carrying a limitation cue, one carrying a tool cue --
    land in different files/paragraphs of the same PR. The old extraction
    collapsed them into one blob and falsely combined the two cues; the
    new extraction keeps them in separate paragraphs, so
    find_offending_paragraphs must report zero matches."""
    diff_text = (
        "diff --git a/docs/one.md b/docs/one.md\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        "+++ b/docs/one.md\n"
        "@@ -0,0 +1,3 @@\n"
        "+# Notes\n"
        "+\n"
        "+This confirms by reading the source -- never by the absence of a\n"
        "+mention in its documentation -- that state is read correctly.\n"
        "diff --git a/docs/two.md b/docs/two.md\n"
        "new file mode 100644\n"
        "index 0000000..2222222\n"
        "--- /dev/null\n"
        "+++ b/docs/two.md\n"
        "@@ -0,0 +1,2 @@\n"
        "+## Subagent dispatch\n"
        "+\n"
        "+Run this skill's Procedure inside a fresh, isolated subagent dispatch.\n"
    )

    old_corpus = _old_buggy_extraction(diff_text)
    assert gate.find_offending_paragraphs(old_corpus), (
        "the old extraction's own blank-line-stripping bug is expected to "
        "still merge these two files into one falsely-flagged paragraph -- "
        "if this assertion ever fails, the contrast this regression test "
        "relies on no longer holds and the test itself needs revisiting"
    )

    new_corpus = extractor.build_added_corpus(diff_text)
    assert gate.find_offending_paragraphs(new_corpus) == []


def test_main_reads_stdin_and_writes_corpus(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(_SINGLE_FILE_DIFF))
    exit_code = extractor.main([])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "# Title" in out
    assert "\n\n" in out  # paragraph separator survived to stdout


def test_main_empty_diff_writes_nothing(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    exit_code = extractor.main([])
    assert exit_code == 0
    assert capsys.readouterr().out == ""

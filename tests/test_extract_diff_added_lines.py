"""Tests for .github/scripts/extract_diff_added_lines.py.

Issue #552: the prior bash `grep -E '^\\+[^+]' | sed 's/^\\+//'` extraction
dropped every blank-line-only diff addition, collapsing per-file paragraph
structure -- and file-to-file boundaries -- into one blob, producing false
positives in gate_provenance_disclosure.py's own paragraph-scoped check.

A fresh adversarial review (before this fix ever merged) found the first
cut of this fix left one more instance of the identical defect class: two
non-adjacent hunks within the *same* file also collapsed into one
paragraph under `-U0`, since only file boundaries forced a separator, not
hunk boundaries. That review's own suggested remedy -- force a separator
at every hunk-to-hunk transition -- was itself disproven by a second,
independent review (this repo's mandatory Step 8, via `/code-review`):
`-U0` shows zero context, so two edits inside the *same* real paragraph,
separated only by an untouched non-blank line, are ALSO reported as two
separate hunks, indistinguishable under zero context from two edits in
genuinely different paragraphs. Forcing a separator at every hunk boundary
therefore introduced a false NEGATIVE (a real cue-combination paragraph
silently split into two innocuous halves, passing CI) -- more dangerous
for a disclosure gate than the false positive #552 originally reported.

The shipped fix instead requests full diff context (`git diff -U1000000`,
wired in `provenance-disclosure-gate.yml`) and detects real paragraph
breaks from actual blank context/added lines, never from hunk boundaries
alone. `test_same_file_two_edits_with_a_blank_line_between_them_get_a_
separator` and `test_same_file_two_edits_with_no_blank_line_between_them_
are_joined_without_a_separator` cover the two directions of that fix
directly; `test_multi_hunk_without_context_is_joined_without_a_forced_
separator` documents the module's own named, deliberately accepted
residual limitation (a file so large it still splits into multiple hunks
even under `-U1000000`).
"""

from __future__ import annotations

import io
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

# Full-context (-U1000000) single-hunk fixture: two edited lines with only
# an untouched, NON-blank connecting line between them -- the exact shape
# the superseded hunk-boundary fix (f6bcf84) would have wrongly split into
# two paragraphs had it seen this as two separate -U0 hunks. No real blank
# line exists between the two edits, so no separator must be inserted.
# A real git-diff blank *context* line is a single space character with
# nothing following -- built by concatenation (not a triple-quoted
# literal) so that single space is never silently trimmed as trailing
# whitespace.
_SAME_FILE_TWO_EDITS_NO_BLANK_BETWEEN_DIFF = (
    "diff --git a/docs/samepara.md b/docs/samepara.md\n"
    "index 4444444..5555555 100644\n"
    "--- a/docs/samepara.md\n"
    "+++ b/docs/samepara.md\n"
    "@@ -1,7 +1,7 @@\n"
    " # Title\n"
    " \n"
    "-Old first edit line.\n"
    "+New first edit line, part of one continuous paragraph.\n"
    " Untouched connecting line, same paragraph.\n"
    "-Old second edit line.\n"
    "+New second edit line, still the same paragraph as above.\n"
    " \n"
    " Footer paragraph.\n"
)

# Full-context (-U1000000) single-hunk fixture: two edited lines with a
# real blank line between them -- a genuine paragraph break the extractor
# must preserve as a separator.
_SAME_FILE_TWO_EDITS_WITH_BLANK_BETWEEN_DIFF = (
    "diff --git a/docs/twopara.md b/docs/twopara.md\n"
    "index 6666666..7777777 100644\n"
    "--- a/docs/twopara.md\n"
    "+++ b/docs/twopara.md\n"
    "@@ -1,5 +1,5 @@\n"
    " # Title\n"
    " \n"
    "-Old paragraph A line.\n"
    "+New paragraph A line.\n"
    " \n"
    "-Old paragraph B line.\n"
    "+New paragraph B line.\n"
)

# No-context (-U0-style) fixture representing the module's own named,
# deliberately accepted residual limitation: a file so large that git
# still splits it into more than one hunk even under a large -U value.
# The elided gap between the two hunks is not visible to this script at
# all, so no separator is forced there -- this is a documented trade-off,
# not a regression.
_MULTI_HUNK_NO_CONTEXT_BETWEEN_DIFF = """\
diff --git a/docs/hugefile.md b/docs/hugefile.md
index 8888888..9999999 100644
--- a/docs/hugefile.md
+++ b/docs/hugefile.md
@@ -3 +3 @@
-Old placeholder line near the top of the file.
+This hunk's own edit, unrelated to the second one below.
@@ -13 +13 @@
-Old placeholder line near the bottom of the file.
+A second, physically distant edit in the very same file.
"""

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

# A single "+" line whose own text contains a literal, embedded carriage
# return -- never emitted by real `git diff` as a line *terminator* (which
# is strictly "\n"), but reachable as ordinary content inside an added
# line. Built by concatenation (not a triple-quoted literal) so the
# embedded "\r" is unambiguous in this source file.
_EMBEDDED_CR_DIFF = (
    "diff --git a/docs/cr.md b/docs/cr.md\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "--- /dev/null\n"
    "+++ b/docs/cr.md\n"
    "@@ -0,0 +1,1 @@\n"
    "+Before the embedded CR\rafter the embedded CR, same added line.\n"
)


class _FakeStdin:
    """Minimal stand-in for `sys.stdin` exposing only the `.buffer.read()`
    surface `main()` actually uses. A plain `io.StringIO` (the pre-rewrite
    fixture's stand-in) has no `.buffer` attribute at all and would raise
    `AttributeError` against the rewritten `main()`, which now reads raw
    bytes and decodes them itself instead of relying on the platform's
    default text-mode decoding."""

    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


def test_single_file_preserves_blank_lines():
    files = extractor.extract_added_lines_by_file(_SINGLE_FILE_DIFF)
    assert files == [["# Title", "", "Paragraph one.", "", "Paragraph two."]]


def test_corpus_has_blank_line_between_paragraphs():
    corpus = extractor.build_added_corpus(_SINGLE_FILE_DIFF)
    assert gate._paragraphs(corpus) == ["# Title", "Paragraph one.", "Paragraph two."]


def test_two_files_get_a_separator_even_when_first_file_ends_non_blank():
    corpus = extractor.build_added_corpus(_TWO_FILE_DIFF)
    assert gate._paragraphs(corpus) == [
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
    assert extractor.extract_added_lines_by_file(diff_text) == [["# Title", "", "Paragraph one.", "", "Paragraph two."]]


def test_rename_with_rewrite_and_second_file_both_extract_correctly():
    corpus = extractor.build_added_corpus(_THREE_FILE_DIFF_WITH_RENAME)
    assert gate._paragraphs(corpus) == ["Rewritten first line after the rename."]


def test_same_file_two_edits_with_no_blank_line_between_them_are_joined_without_a_separator():
    """The core of the false-negative fix: two edits in the same real
    paragraph, separated only by an untouched non-blank connecting line,
    must NOT get a separator forced between them -- unlike the superseded
    hunk-boundary-based fix, which could not tell this case apart from two
    edits in genuinely different paragraphs."""
    files = extractor.extract_added_lines_by_file(_SAME_FILE_TWO_EDITS_NO_BLANK_BETWEEN_DIFF)
    assert files == [
        [
            "New first edit line, part of one continuous paragraph.",
            "New second edit line, still the same paragraph as above.",
        ]
    ]
    corpus = extractor.build_added_corpus(_SAME_FILE_TWO_EDITS_NO_BLANK_BETWEEN_DIFF)
    assert gate._paragraphs(corpus) == [
        "New first edit line, part of one continuous paragraph.\n"
        "New second edit line, still the same paragraph as above."
    ]


def test_same_file_two_edits_with_a_blank_line_between_them_get_a_separator():
    """The other direction of the same fix: a genuine blank line between
    two edits is real evidence of a paragraph break and must be preserved,
    even though both edits are in the same file and the same (full-context)
    hunk."""
    files = extractor.extract_added_lines_by_file(_SAME_FILE_TWO_EDITS_WITH_BLANK_BETWEEN_DIFF)
    assert files == [["New paragraph A line.", "", "New paragraph B line."]]
    corpus = extractor.build_added_corpus(_SAME_FILE_TWO_EDITS_WITH_BLANK_BETWEEN_DIFF)
    assert gate._paragraphs(corpus) == ["New paragraph A line.", "New paragraph B line."]


def test_multi_hunk_without_context_is_joined_without_a_forced_separator():
    """Known, deliberately accepted limitation (see the module docstring):
    if a file's total line count exceeds the requested context depth, git
    can still split it into more than one hunk, and the gap git elides is
    not visible to this script at all. Unlike the superseded fix, which
    forced a separator at every hunk boundary and thereby caused the
    false-negative bug this redesign fixes, the current design makes no
    claim about content it cannot see -- it joins the two hunks' added
    lines with no separator, accepting a theoretical miss on an
    extreme-scale file rather than asserting an unverified break."""
    files = extractor.extract_added_lines_by_file(_MULTI_HUNK_NO_CONTEXT_BETWEEN_DIFF)
    assert files == [
        [
            "This hunk's own edit, unrelated to the second one below.",
            "A second, physically distant edit in the very same file.",
        ]
    ]


def test_embedded_carriage_return_in_added_line_is_preserved_not_truncated():
    """`str.splitlines()` splits on more terminators than plain "\\n" --
    a bare \\r, \\v, \\f, U+0085, U+2028, and U+2029 among them -- none of
    which `git diff` itself ever emits as a line *terminator*, but any of
    which can appear embedded inside a real added line's own text. The
    superseded splitlines()-based parse would have silently shredded this
    single "+" line into two at the embedded \\r and dropped everything
    after it; explicit "\\n"-splitting must keep it intact."""
    whole_added_line = "+Before the embedded CR\rafter the embedded CR, same added line."
    assert whole_added_line not in _EMBEDDED_CR_DIFF.splitlines(), (
        "this fixture must actually exercise the splitlines()-vs-split('\\n') "
        "gap it claims to -- if splitlines() stops over-splitting on a bare "
        "\\r, this fixture no longer demonstrates the pitfall it names"
    )
    assert whole_added_line in _EMBEDDED_CR_DIFF.split("\n")
    files = extractor.extract_added_lines_by_file(_EMBEDDED_CR_DIFF)
    assert files == [["Before the embedded CR\rafter the embedded CR, same added line."]]


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


def _old_buggy_extraction(diff_text: str) -> str:
    """Reimplementation of the pre-#552 bash pipeline
    (`grep -E '^\\+[^+]' | sed 's/^\\+//'`), kept only to demonstrate the
    contrast the regression test above relies on -- not used by the
    shipped fix."""
    lines = []
    for line in diff_text.splitlines():
        if re.match(r"^\+[^+]", line):
            lines.append(line[1:])
    return "\n".join(lines)


def test_main_reads_stdin_and_writes_corpus(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _FakeStdin(_SINGLE_FILE_DIFF.encode("utf-8")))
    exit_code = extractor.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "# Title" in out
    assert "\n\n" in out  # paragraph separator survived to stdout


def test_main_empty_diff_writes_nothing(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _FakeStdin(b""))
    exit_code = extractor.main()
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_main_replaces_invalid_utf8_bytes_instead_of_crashing(monkeypatch, capsys):
    """`main()` now reads stdin as bytes and decodes with an explicit
    `errors="replace"` policy, rather than relying on the platform/
    locale's own default text-mode decoding -- which would either raise an
    uncaught UnicodeDecodeError on a real but non-UTF-8 byte, or silently
    pass through an unpaired surrogate on a surrogateescape locale. A
    single invalid byte inside an otherwise well-formed added line must
    become U+FFFD, not a crash and not silent corruption."""
    diff_bytes = (
        b"diff --git a/docs/bad.md b/docs/bad.md\n"
        b"new file mode 100644\n"
        b"index 0000000..1234567\n"
        b"--- /dev/null\n"
        b"+++ b/docs/bad.md\n"
        b"@@ -0,0 +1,1 @@\n"
        b"+Invalid byte follows: \xff end of line.\n"
    )
    monkeypatch.setattr("sys.stdin", _FakeStdin(diff_bytes))
    exit_code = extractor.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Invalid byte follows: " + "\ufffd" + " end of line." in out

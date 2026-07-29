#!/usr/bin/env python3
"""Extract added lines from a unified diff, preserving per-file paragraph
structure.

Issue #552: `provenance-disclosure-gate.yml`'s own added-line extraction
was `git diff -U0 ... | grep -E '^\\+[^+]' | sed 's/^\\+//'`. `grep -E
'^\\+[^+]'` requires a character after the leading `+` that is itself not
`+`, so a blank-line addition (a bare `+` with nothing following it in the
diff) matches neither branch and is silently dropped. `gate_provenance_
disclosure.py`'s own `_paragraphs()` splits its corpus on blank-line
boundaries to scope its cue-combination check to one real Markdown
paragraph at a time; once every blank line is stripped from the corpus,
every paragraph in every added file -- and every different file's own
added content, concatenated back to back with nothing separating them --
collapses into a single blob, producing false positives on unrelated
sentences that happen to co-occur once paragraph boundaries are gone.
Reproduced live against a real PR: see issue #552 for the full repro.

This script replaces that grep/sed pipeline. It parses `git diff -U0`
output directly, tracking three boundaries a prefix-based heuristic
cannot:

1. **Per-file boundaries** (`diff --git a/... b/...` lines). Each file's
   own extracted content is joined back together with an explicit
   blank-line separator before the next file's content, so two different
   files' added prose can never merge into one paragraph even when the
   first file's own last added line is not itself blank.
2. **Header-vs-hunk boundaries** (`@@ ... @@` lines). A line is only ever
   treated as added content once a hunk marker for its own file has
   actually been seen -- this correctly extracts a real content line whose
   own first character happens to be a literal `+` (e.g. a Markdown line
   reading "+1 to this idea"), which a naive "reject any line starting
   with two `+` characters" fix would still misclassify as the diff's own
   `+++ b/file` header line, the same way the original bug misclassified
   it as non-content for the unrelated reason of requiring a second
   character to exist at all.
3. **Hunk-to-hunk boundaries within the same file.** An earlier version of
   this fix (caught by a fresh adversarial review before merge, not by any
   automated check -- every fixture at that point had exactly one `@@` per
   file, so line coverage could not discriminate a first-hunk-in-file from
   a later one) still joined two non-adjacent hunks of the *same* file
   with a bare newline, no separator. Two edits ten lines apart in the
   same file, with an untouched paragraph physically between them in the
   real file, collapsed into one paragraph here -- the identical defect
   class issue #552 was filed to eliminate, one level down. Fixed by
   inserting an explicit blank-line marker whenever a new hunk begins for
   a file that has already contributed content from an earlier hunk.

Deliberately stdlib-only, matching this repository's existing
`.github/scripts/*.py` convention.

Usage::

    git diff -U0 "$BASE_SHA...$HEAD_SHA" -- <pathspec...> \\
      | python3 .github/scripts/extract_diff_added_lines.py > added_lines.txt
"""

from __future__ import annotations

import sys


def extract_added_lines_by_file(diff_text: str) -> list[list[str]]:
    """Parse unified diff text (as produced by `git diff -U0`) into a list
    of per-file added-line lists, each entry being one file's own added
    content (blank-line additions included, the leading `+` stripped, in
    diff order). A file with zero added lines (a pure deletion, or a mode
    -only change) is still listed as an empty list, not dropped -- callers
    that want only non-empty files should filter explicitly.
    """
    files: list[list[str]] = []
    current: list[str] | None = None
    in_hunk = False
    pending_hunk_separator = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current is not None:
                files.append(current)
            current = []
            in_hunk = False
            pending_hunk_separator = False
            continue
        if current is None:
            # Preamble before the first "diff --git" line (e.g. a
            # `git diff` invocation with no matching paths produces no
            # such line at all) -- nothing to extract yet.
            continue
        if line.startswith("@@"):
            # A later hunk in the same file starts a new, physically
            # separate span of the real file -- force a paragraph break
            # here too, the same reason build_added_corpus forces one
            # between files, so two non-adjacent edits in one file are
            # never read as one continuous paragraph. `in_hunk` already
            # being True here (not just "a hunk was seen before") is what
            # distinguishes this file's own *later* hunk from its first.
            # Deferred, not applied immediately: a hunk that turns out to
            # contribute no "+" line at all (a pure deletion) must not
            # leave a dangling trailing separator behind it.
            if in_hunk:
                pending_hunk_separator = True
            in_hunk = True
            continue
        if not in_hunk:
            # Still inside this file's own header block (`index ...`,
            # `--- a/file`, `+++ b/file`, `new file mode ...`, etc.) --
            # none of this is the file's own added content.
            continue
        if line.startswith("+"):
            if pending_hunk_separator:
                if current and current[-1] != "":
                    current.append("")
                pending_hunk_separator = False
            current.append(line[1:])
    if current is not None:
        files.append(current)
    return files


def build_added_corpus(diff_text: str) -> str:
    """Join every file's own added lines (per `extract_added_lines_by_
    file`) with an explicit blank-line separator between files, so a
    downstream paragraph-splitting consumer never merges two different
    files' own content into one paragraph. Files with zero added lines
    contribute nothing (not even a stray separator)."""
    per_file = [lines for lines in extract_added_lines_by_file(diff_text) if lines]
    return "\n\n".join("\n".join(lines) for lines in per_file)


def main() -> int:
    diff_text = sys.stdin.read()
    corpus = build_added_corpus(diff_text)
    if corpus:
        sys.stdout.write(corpus + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

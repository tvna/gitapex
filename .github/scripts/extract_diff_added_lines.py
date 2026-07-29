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
output directly, tracking two boundaries a prefix-based heuristic cannot:

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
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current is not None:
                files.append(current)
            current = []
            in_hunk = False
            continue
        if current is None:
            # Preamble before the first "diff --git" line (e.g. a
            # `git diff` invocation with no matching paths produces no
            # such line at all) -- nothing to extract yet.
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            # Still inside this file's own header block (`index ...`,
            # `--- a/file`, `+++ b/file`, `new file mode ...`, etc.) --
            # none of this is the file's own added content.
            continue
        if line.startswith("+"):
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


def main(argv: list[str] | None = None) -> int:
    diff_text = sys.stdin.read()
    corpus = build_added_corpus(diff_text)
    if corpus:
        sys.stdout.write(corpus + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

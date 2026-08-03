#!/usr/bin/env python3
"""Extract added lines from a unified diff, preserving real paragraph
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

First fix attempt (superseded, kept here as provenance): forced a
paragraph break at every hunk-to-hunk transition within one file, on the
theory that a later hunk always means "a different, physically separate
part of the file." A fresh adversarial review (this repo's mandatory Step
8, before merge) disproved that theory with real `git diff -U0` output:
`-U0` shows zero context, so two edits inside the *same* real paragraph,
separated only by an untouched, non-blank line, are reported as two
separate hunks -- indistinguishable, under zero context, from two edits
in genuinely different paragraphs. Forcing a break at every hunk boundary
therefore introduced a new failure in the opposite, more dangerous
direction for a disclosure gate: a **false negative** (a real
cue-combination paragraph silently split into two innocuous halves,
passing CI). Three independent review angles reproduced this
independently with real `git`.

Current fix: request enough diff context (`git diff -U<large>`, wired in
`provenance-disclosure-gate.yml`) that git never needs to split a single
file's changes into more than one hunk for any realistic file size, and
walk the *actual* context lines this produces -- not hunk boundaries --
to find real paragraph breaks. A paragraph break is real if and only if
an actual blank line exists in the file at that point: either a blank
*context* line (an unchanged blank line the diff shows verbatim, prefixed
with a single space) or a blank *added* line (a bare `+`). Non-blank
context lines carry no signal and are not extracted -- pre-existing,
already-reviewed prose stays out of this gate's scope, matching its own
stated rationale; only what the diff actually adds is graded.

This also still correctly preserves a real content line whose own first
character happens to be a literal `+` (e.g. a Markdown line reading "+1
to this idea"), which a naive "reject any line starting with two `+`
characters" fix would still misclassify as the diff's own `+++ b/file`
header line.

Two further fixes from the same adversarial round, unrelated to the
paragraph-boundary question: this module now splits raw diff text on
`"\n"` explicitly rather than `str.splitlines()`, which also breaks on a
bare `\r`, `\v`, `\f`, U+0085, U+2028, and U+2029 -- none of which `git
diff` itself ever emits as a line terminator, but any of which can appear
*embedded inside* a real added line's own text, and `splitlines()` would
silently shred that line and drop everything after the embedded
character. And `main()` now reads stdin as bytes and decodes with an
explicit `errors="replace"` policy, rather than relying on the
platform/locale's own default text-mode decoding -- which either raises
an uncaught `UnicodeDecodeError` on a real but non-UTF-8 byte (misreported
by the calling workflow as a generic "git diff/extraction failed") or, on
a locale that coerces to `surrogateescape`, silently passes through an
unpaired surrogate instead of failing loudly or substituting a safe
placeholder.

**Known, deliberately accepted limitation:** if a single file's total
line count exceeds the requested context depth, git may still split it
into more than one hunk, and the (very large) gap git elides between them
is not visible to this script at all -- a real blank line inside that
elided gap cannot be detected, and no paragraph break is forced there
either. This trades a theoretical miss on an extreme-scale file for never
inventing an unverified break, which is the safer default in the same
direction dimension 10's own live-testing discipline already argues for
elsewhere in this repository: an unconfirmed claim should not be asserted
as fact. Not expected to matter at any realistic size of `docs/`/`evals/`/
`skills/` Markdown this gate actually scopes to.

Deliberately stdlib-only, matching this repository's existing
`.github/scripts/*.py` convention.

Usage::

    git diff -U<large> "$BASE_SHA...$HEAD_SHA" -- <pathspec...> \\
      | python3 .github/scripts/extract_diff_added_lines.py > added_lines.txt
"""

from __future__ import annotations

import sys


def extract_added_lines_by_file(diff_text: str) -> list[list[str]]:
    """Parse unified diff text (as produced by `git diff -U<large>`, i.e.
    with enough context that a single file's changes are not split across
    multiple hunks for any realistic file size) into a list of per-file
    added-line lists, each entry being one file's own added content
    (blank-line additions included, the leading `+` stripped, in diff
    order). A file with zero added lines (a pure deletion, or a mode-only
    change) is still listed as an empty list, not dropped -- callers that
    want only non-empty files should filter explicitly.

    A paragraph break is inserted into a file's own list only where a
    real blank line exists in the file at that point -- a blank added
    line, or a blank *unchanged* line the diff's own context reveals --
    never merely because a new hunk began. The break is deferred until
    the next added line actually arrives, so a blank line with no further
    added content after it (in this file, or ever) never leaves a
    dangling trailing separator behind.
    """
    files: list[list[str]] = []
    current: list[str] | None = None
    in_hunk = False
    pending_separator = False
    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            if current is not None:
                files.append(current)
            current = []
            in_hunk = False
            pending_separator = False
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
            if pending_separator:
                if current and current[-1] != "":
                    current.append("")
                pending_separator = False
            current.append(line[1:])
        elif line.startswith(" "):
            # An unchanged context line. Its own content is never
            # extracted (pre-existing prose is out of this gate's own
            # scope) -- but if it is itself blank, it is real, live
            # evidence of an actual paragraph break at this exact point
            # in the file, which a later added line must respect.
            if line == " " and current and current[-1] != "":
                pending_separator = True
        # A "-" (removed) line contributes nothing to the new file and
        # carries no paragraph-structure signal for it either.
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
    diff_text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    corpus = build_added_corpus(diff_text)
    if corpus:
        sys.stdout.write(corpus + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

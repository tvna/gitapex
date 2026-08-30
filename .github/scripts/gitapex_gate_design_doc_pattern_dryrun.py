#!/usr/bin/env python3
"""Dry-run a design doc's own stated literal-text resolution pattern
against the live repository corpus.

Issue #1507 (retro #1504 repair 3, refs #1499): the design doc that became
`docs/superpowers/specs/2026-08-30-issue-192-untrusted-consistency-and-item-coverage-design.md`
first specified resolving a fixture's declared "Step N" label via a
literal-text search for the string "Step N:". A dispatched adversarial-
review subagent found no skill in this repository actually writes a
Procedure/Steps item's own text that way (every skill uses bare "1.", "2."
numbering) -- so the as-specified mechanism would have resolved against
nothing in any current skill. No deterministic check dry-ran the design's
own stated pattern against the live repository before the design was
treated as final; a human/subagent had to think to check by hand, and
the fix landed only because that round happened to do so.

This gate automates exactly that dry run for one concrete pattern class:
a design doc stating that a not-yet-implemented checker will resolve or
match content via a **literal-text search** for a specific quoted string.
("literal-text search" is the term both issue #1507 and the design doc's
own corrected text use; the vocabulary is deliberately narrow rather than
attempting to also cover a regex/verb-pattern violation-detection class --
that is a structurally different extraction target, scoped to the sibling
gate-proposal issue #1506, filed separately per this repository's own
one-issue-per-repair rule. Residual risk, same class already disclosed for
this shape of heuristic: detecting "a design doc states a concrete
text-matching pattern" from free-form prose needs a heuristic that could
miss some phrasings.)

For each such stated pattern found in a diff's *added* design-doc lines,
this script greps the live `skills/**/*.md` corpus (the same "every skill
directory" scope this repository's own PR #578 / item-4 shipping bar
already uses) for the literal quoted string, case-insensitively. A pattern
with zero live matches is flagged: a resolution mechanism that matches
nothing in the real corpus is exactly the defect class repair 3 exists to
prevent, surfaced automatically instead of depending on a reviewer's own
initiative to think to check.

A paragraph that both carries the "literal-text search" cue and states,
in the same paragraph, that the reading would resolve/match against
nothing (the pattern this design doc's own *corrected* prose now uses to
explain why it rejected that reading) is not flagged -- it is already a
live disclosure of the same fact this gate would otherwise compute, not a
proposal. A `corpus-dryrun-disclosure: WAIVED: <reason>` line anywhere in
the combined corpus (diff-added design-doc text, plus an optional PR body)
is an explicit escape hatch for any case this narrow heuristic still gets
wrong, matching the same `<name>: WAIVED: <reason>` vocabulary
`gitapex_gate_provenance_disclosure.py` and `gitapex_gate_skill_audit_disclosure.py`
already use elsewhere in this repository.

Deliberately stdlib-only, matching this repository's existing
`.github/scripts/*.py` convention of not importing across files.

Usage::

    git diff -U1000000 "$BASE_SHA...$HEAD_SHA" -- 'docs/superpowers/specs/*.md' \\
      | python3 .github/scripts/gitapex_extract_diff_added_lines.py > added_lines.txt
    python3 .github/scripts/gitapex_gate_design_doc_pattern_dryrun.py \\
        --diff-added added_lines.txt [--diff-added ...] [--body PR_BODY.txt] \\
        [--repo-root .] [--corpus-glob 'skills/**/*.md']

Exit codes:
    0  No stated literal-text-search pattern found, every stated pattern
       has at least one live corpus match, or a disclosure marker is
       present.
    1  A stated pattern has zero live corpus matches and no disclosure
       marker is present, or a given file could not be read.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Deliberately narrow and specific to the vocabulary this repository's own
# issue #1507 and its grounding design doc actually use, not a general
# "propose a pattern" detector -- see the module docstring's own scoping
# rationale. Both separator positions independently allow a hyphen or a
# space: the design doc's own corrected text uses the fully-hyphenated
# compound-adjective form ("a literal-text-search reading of"), while
# issue #1507's own body and a first-draft proposal read more naturally as
# "a literal-text search" (hyphen then space) -- verified live against
# `docs/superpowers/specs/2026-08-30-issue-192-untrusted-consistency-and-item-coverage-design.md`'s
# own real text, not assumed. Extend as new phrasings are observed, same
# convention gitapex_gate_provenance_disclosure.py's own vocabulary comment states.
_SEARCH_INTENT_RE = re.compile(r"\bliteral[- ]text[- ]search\b", re.IGNORECASE)

# A paragraph that already discloses, in its own prose, that the reading
# would match/resolve against nothing is describing a rejected mechanism,
# not proposing a live one -- the same declaration/violation-minus-hedge
# shape this design doc's own `no-untrusted-authority-crossover` item uses
# elsewhere. Non-exhaustive by design; extend as new rejection phrasings
# are observed.
_REJECTION_RE = re.compile(
    r"\b(?:"
    r"resolves? against nothing|"
    r"resolve against nothing|"
    r"match(?:es)? nothing|"
    r"does not work|"
    r"doesn't work|"
    r"not part of this design|"
    r"is infeasible|"
    r"not viable"
    r")\b",
    re.IGNORECASE,
)

# A short quoted literal, single line only (the resolution targets this
# gate cares about -- e.g. "Step N", `Step N:` -- are always short labels,
# never a multi-line excerpt).
_QUOTED_LITERAL_RE = re.compile(
    r"`([^`\n]{1,80})`" r'|"([^"\n]{1,80})"' r"|“([^”\n]{1,80})”",
)

_WAIVER_RE = re.compile(
    r"^[ \t]*[-*]?[ \t]*`?corpus-dryrun-disclosure`?[ \t]*:[ \t]*WAIVED[ \t]*:[ \t]*\S.*$",
    re.IGNORECASE | re.MULTILINE,
)

_DEFAULT_CORPUS_GLOB = "skills/**/*.md"


@dataclass(frozen=True)
class Candidate:
    """One stated literal-text-search pattern found in a design doc's
    added prose."""

    pattern: str
    paragraph_first_line: str


def _paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [p for p in re.split(r"\n\s*\n", normalized) if p.strip()]


# How far past a "literal-text search" cue's own end this script looks for
# the quoted string that cue names as its target (e.g. "...search for the
# string "Step N:"", "...literal-text-search reading of "Step N""). Bounded
# deliberately narrow: a paragraph naming its target pattern typically does
# so within a few words of the cue phrase itself; a wider or unbounded
# window would instead pick up an unrelated later quote in the same
# sentence (e.g. a heading name cited afterward, such as "`## Procedure`"
# in issue #1507's own grounding incident) as if it were the stated
# pattern, a real false-positive class found while building this gate's
# own regression tests against that incident's reconstructed wording.
_TARGET_WINDOW_CHARS = 60


def find_candidate_patterns(text: str) -> list[Candidate]:
    """Return every stated literal-text-search pattern in `text`: for each
    paragraph carrying a "literal-text search" cue with no rejection cue
    of its own, the first quoted literal found within
    `_TARGET_WINDOW_CHARS` characters after each cue occurrence -- not
    every quoted span anywhere in the paragraph, which would also catch
    an unrelated later quote (e.g. a heading name cited afterward) as if
    it were the stated pattern."""
    candidates: list[Candidate] = []
    for paragraph in _paragraphs(text):
        if _REJECTION_RE.search(paragraph):
            continue
        first_line = paragraph.strip().splitlines()[0]
        for cue_match in _SEARCH_INTENT_RE.finditer(paragraph):
            window = paragraph[cue_match.end() : cue_match.end() + _TARGET_WINDOW_CHARS]
            quote_match = _QUOTED_LITERAL_RE.search(window)
            if quote_match is None:
                continue
            literal = next(group for group in quote_match.groups() if group is not None)
            if literal:
                candidates.append(Candidate(pattern=literal, paragraph_first_line=first_line))
    return candidates


def dry_run_corpus(pattern: str, repo_root: Path, corpus_glob: str) -> list[Path]:
    """Return every file under `repo_root` matching `corpus_glob` whose
    text contains `pattern` as a case-insensitive literal substring."""
    needle = pattern.lower()
    matches: list[Path] = []
    for candidate_file in sorted(repo_root.glob(corpus_glob)):
        if not candidate_file.is_file():
            continue
        try:
            content = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if needle in content.lower():
            matches.append(candidate_file)
    return matches


def find_zero_match_candidates(text: str, repo_root: Path, corpus_glob: str = _DEFAULT_CORPUS_GLOB) -> list[Candidate]:
    """Return every candidate pattern in `text` with zero live matches
    under `repo_root`'s `corpus_glob`."""
    zero_match = []
    seen_patterns: set[str] = set()
    for candidate in find_candidate_patterns(text):
        if candidate.pattern in seen_patterns:
            continue
        seen_patterns.add(candidate.pattern)
        if not dry_run_corpus(candidate.pattern, repo_root, corpus_glob):
            zero_match.append(candidate)
    return zero_match


def has_disclosure_marker(text: str) -> bool:
    """Return True iff `text` carries a
    `corpus-dryrun-disclosure: WAIVED: <reason>` line."""
    return bool(_WAIVER_RE.search(text.replace("\r\n", "\n").replace("\r", "\n")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run a design doc's own stated literal-text-search pattern against the "
        "live repository corpus and flag any pattern with zero matches."
    )
    parser.add_argument(
        "--diff-added",
        action="append",
        default=[],
        help="Path to a file of this diff's added design-doc lines (e.g. from "
        "gitapex_extract_diff_added_lines.py); repeatable. Reads standard input when omitted.",
    )
    parser.add_argument(
        "--body",
        help="Optional path to the PR body text; contributes to disclosure-marker detection only.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to dry-run patterns against (default: current directory).",
    )
    parser.add_argument(
        "--corpus-glob",
        default=_DEFAULT_CORPUS_GLOB,
        help=f"Glob (relative to --repo-root) of the live corpus to search (default: {_DEFAULT_CORPUS_GLOB!r}).",
    )
    args = parser.parse_args(argv)

    added_sources: list[str] = []
    body_source: str = ""
    reading: str = "standard input"
    try:
        if args.diff_added:
            for diff_path in args.diff_added:
                reading = diff_path
                added_sources.append(Path(diff_path).read_text(encoding="utf-8"))
        else:
            added_sources.append(sys.stdin.buffer.read().decode("utf-8"))
        if args.body:
            reading = args.body
            body_source = Path(args.body).read_text(encoding="utf-8")
    except FileNotFoundError as error:
        print(f"error: file not found: {error.filename}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        print(f"error: {reading} is not valid UTF-8: {error}", file=sys.stderr)
        return 1

    # Detection only ever runs against the diff-added design-doc text,
    # never the PR body -- a PR body is not design-doc prose, so scanning
    # it for stated patterns would be meaningless. The PR body still
    # contributes to the combined corpus used for disclosure-marker
    # detection below.
    added_only = "\n\n".join(added_sources)
    corpus = "\n\n".join([*added_sources, body_source]) if body_source else added_only
    repo_root = Path(args.repo_root)
    zero_match = find_zero_match_candidates(added_only, repo_root, args.corpus_glob)

    if not zero_match:
        print("PASS: no stated literal-text-search pattern with zero live corpus matches")
        return 0

    if has_disclosure_marker(corpus):
        print("PASS: zero-match pattern(s) found, but disclosed via corpus-dryrun-disclosure: WAIVED")
        return 0

    print(
        f"FAIL: {len(zero_match)} stated literal-text-search pattern(s) match nothing in the live "
        f"{args.corpus_glob!r} corpus:",
        file=sys.stderr,
    )
    for candidate in zero_match:
        print(f'  - "{candidate.pattern}" (paragraph: {candidate.paragraph_first_line})', file=sys.stderr)
    print(
        "Specify a resolution mechanism that matches real content (e.g. positional resolution), "
        "or add 'corpus-dryrun-disclosure: WAIVED: <reason>' if the owner has explicitly approved "
        "shipping a pattern with no current live match.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

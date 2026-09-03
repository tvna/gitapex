"""Code-span line-break integrity check (design doc:
docs/superpowers/specs/2026-09-02-skill-body-cost-controls-design.md,
Decision 1) -- a single-backtick inline code span must open and close on
the same line, in both SKILL.md and references/*.md. A Markdown renderer
collapses an embedded line break inside a code span into a literal
space, so a span split by this repository's own ~70-74 character wrap
habit renders as a corrupted string (an injected space) that no longer
matches the literal path/identifier/command a reader would copy or grep
verbatim -- see the design doc's own Evidence section for two concrete,
now-fixed examples of exactly this defect.

Deliberately scoped to single-backtick spans only, matching the design
doc's own stated scope ("NOT a triple-backtick fenced code block"): a
double- or triple-backtick delimited span (rare in this corpus, used to
let a span's own content contain a literal backtick) is a different
delimiter shape the design does not target, and a real corpus example
(`skills/planning-a-branch-from-an-issue/SKILL.md`'s own double-backtick
span quoting a re-verification marker) legitimately crosses a line break
today -- flagging it would be a false positive, not a defect this check
exists to catch.
"""

from __future__ import annotations

import bisect
import re

from shape_checks.citations import _blank_fenced_blocks
from shape_checks.constants import CheckResult

# A well-formed double- or triple-backtick code span (content may itself
# contain single backticks, e.g. a span quoting a literal backtick
# character) -- blanked out first so its interior single backticks are
# never mistaken for single-backtick delimiters below. `re.DOTALL` is
# deliberate: this span's own delimiter pair is legitimately allowed to
# cross a line break (module docstring above), so the scan must match it
# across the whole document, not line-by-line -- an earlier per-line
# revision missed exactly this and mis-flagged a nested single-backtick
# pair inside such a span as a genuine violation (independent review,
# see test_nested_single_backtick_inside_cross_line_double_backtick_
# span_does_not_false_positive). Not widened to also match single-backtick
# spans (INLINE_CODE_RE's own {1,3} range, no DOTALL): a leading
# double/triple-backtick run that never finds a same-width close anywhere
# must stay untouched here so the real defect class (a genuine cross-line
# double/triple-backtick span, out of this check's own scope) is not
# mis-parsed as a single-backtick match by this pass -- and INLINE_CODE_RE
# itself is deliberately not reused: giving it DOTALL for this pass would
# also let it swallow a genuinely split single-backtick span (the exact
# defect this check exists to catch) as if it were well-formed.
_MULTI_BACKTICK_SPAN_RE = re.compile(r"(`{2,3})(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_BACKTICK_RUN_RE = re.compile(r"`+")


def _blank_preserving_newlines(match: re.Match[str]) -> str:
    """Replace a match with spaces, keeping every embedded newline intact
    so a later line-number computation over the blanked text stays
    accurate -- a plain ``" " * len(match.group(0))`` would flatten an
    embedded newline into a space and silently shift every subsequent
    line number."""
    return "".join(ch if ch == "\n" else " " for ch in match.group(0))


def _split_single_backtick_span_lines(text: str) -> list[int]:
    """Return the 1-indexed line numbers where a single-backtick code span
    opens without a matching single-backtick close on that same line.

    Two passes over ``text`` (already fence-blanked via
    ``_blank_fenced_blocks``, which also normalizes CRLF/CR line endings
    to bare '\\n'): first, blank every well-formed double/triple-backtick
    span (which may itself cross a line break) across the whole document
    so its own nested single backticks cannot be mistaken for
    single-backtick delimiters; second, walk every remaining backtick run
    in document order, pairing up only the runs of length exactly 1 (a
    run of any other length here is itself a leftover, unclosed
    double/triple-backtick span -- out of this check's own scope per the
    module docstring, so it is skipped rather than mis-paired).

    Line numbers are read via `bisect` against a precomputed newline-offset
    table rather than `blanked.count("\\n", 0, match.start())` per match --
    the latter is O(document length) per lookup, making the whole scan
    O(matches x document length) on an adversarial document with many
    isolated backtick characters (independent review flagged this as a
    CWE-1333 resource-consumption risk for a repository-wide gate run
    against externally-contributed content); `bisect` makes each lookup
    O(log line count) instead.
    """
    defenced = _blank_fenced_blocks(text)
    blanked = _MULTI_BACKTICK_SPAN_RE.sub(_blank_preserving_newlines, defenced)
    newline_offsets = [i for i, ch in enumerate(blanked) if ch == "\n"]

    offenders: list[int] = []
    open_line: int | None = None
    for match in _BACKTICK_RUN_RE.finditer(blanked):
        if len(match.group(0)) != 1:
            continue
        line_no = bisect.bisect_right(newline_offsets, match.start()) + 1
        if open_line is None:
            open_line = line_no
        elif line_no == open_line:
            open_line = None  # closed on the same line: well-formed
        else:
            offenders.append(open_line)
            open_line = None
    if open_line is not None:
        # A single backtick opened and never found any later single-
        # backtick close anywhere in the document -- also a violation
        # (it certainly did not close on its own opening line).
        offenders.append(open_line)
    return offenders


def _code_span_integrity_check(name: str, text: str) -> CheckResult:
    """A ``CheckResult``-returning wrapper around
    ``_split_single_backtick_span_lines``, following the established
    ``field_checks.py`` pattern (``_no_xml_check``/``_length_check``): a
    rule name, a pass/fail bool, a human-readable rule statement, and an
    evidence string. ``name`` lets the caller supply the bare check name
    for SKILL.md or the ``:{ref.name}``-suffixed per-file name for a
    references/*.md file, matching every other per-file check in this
    package (``toc:{ref.name}``, ``links-inside-skill:{ref.name}``)."""
    rule = "every single-backtick inline code span opens and closes on the same line (no embedded line break)"
    offenders = _split_single_backtick_span_lines(text)
    if not offenders:
        return CheckResult(name, True, rule, "all code spans close on their own line")
    count = len(offenders)
    lines_str = ", ".join(str(n) for n in offenders)
    span_noun = "span" if count == 1 else "spans"
    line_noun = "line" if count == 1 else "lines"
    return CheckResult(
        name, False, rule, f"{count} code {span_noun} split across a line break, opening at {line_noun} {lines_str}"
    )

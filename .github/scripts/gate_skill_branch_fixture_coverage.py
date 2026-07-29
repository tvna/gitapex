#!/usr/bin/env python3
"""Gate: a SKILL.md's own Stop-boundary bullets and named dispatch
branches must not outgrow its `evals/<skill>/tasks/*.yaml` fixture count
as a result of the current diff.

Issue #49 repair 1: the first `waza` eval-authoring pass bulk-authored a
fixed 3-fixture quota per skill regardless of how many Stop-boundary
bullets or N-way dispatch branches that skill's own SKILL.md actually
declared (e.g. `driving-pr-to-merge` tested 1 of 6 `mergeable_state`
values; `evaluating-skill-quality` tested 3 of 7 Stop boundaries at the
time). Issue #49 proposed, but never built, "a script that parses each
SKILL.md's 'Stop boundar*' bullets and named dispatch branches, counts
them, and fails if the skill's own evals/*/tasks/*.yaml count is below
that number." Re-escalated, unbuilt, across four consecutive
merge-retrospective cycles (#419, #440, #454, #548) -- this script is
that gate, restated in each of those issues' own words.

Mechanical definition of a "decision branch" (never precisely defined in
any prior retrospective; this is this issue's own reasoned extension,
derived from the two concrete precedents #49/#419 actually cite):

  1. Stop-boundary bullets: every top-level `- ` bullet (column 0 --
     every real Stop-boundary/Stop-boundaries section in this repository
     writes its bullets flush-left; a further-indented `- ` line is a
     nested sub-bullet clarifying the one above it, not its own branch)
     directly under a
     `## Stop boundary` or `## Stop boundaries` heading (any heading
     level, case-insensitive), up to the next heading of any level.
     `merge-retrospective/SKILL.md` uses the singular heading with 5
     bullets; `driving-pr-to-merge/SKILL.md` uses the plural heading with
     7 -- both real, both counted the same way.
  2. Named dispatch branches: a `- ` bullet (any indentation -- unlike
     Stop-boundary bullets, a dispatch bullet is conventionally nested
     under its own numbered "Dispatch on `X`" procedure step, e.g.
     `driving-pr-to-merge/SKILL.md`'s `mergeable_state` dispatch) whose
     own first line names one or more backtick/quote-wrapped tokens
     immediately before a `->` arrow later on that same line (e.g.
     `` - `"clean"` -> proceed to step 7.``, or two tokens in one bullet:
     `` - `"unstable"` or `"blocked"` -> ...``, each still counted
     separately). An ordinary `-> ` arrow in narrative prose with no
     quoted token before it (e.g. this skill's own "Clean/approved ...
     -> continue to step 8" bullet) is deliberately NOT a match -- this
     gate only counts a *named* branch, not every arrow-shaped sentence.
     Bullets already counted as a Stop-boundary bullet (case 1 above) are
     excluded from this scan, so a Stop-boundary bullet that happens to
     also contain a quoted token and an arrow is never double-counted.

A fixture-count->=-branch-count comparison is a NECESSARY, not
SUFFICIENT, proxy for genuine per-branch coverage (the same limitation
issue #49's own proposal already named: "this would not have caught the
two logical contradictions, but would have flagged the under-coverage
instances deterministically"). This gate cannot verify that N fixtures
actually exercise N *distinct* branches, only that there are at least as
many fixtures as branches -- a skill could still pass this gate with
every fixture covering the same one branch. Left as a known residual
risk, not silently overclaimed.

Delta-scoped, not absolute-scoped: this gate only fires when THIS diff
increases a skill's own decision-branch count (a brand-new SKILL.md
counts every branch as new; a modified SKILL.md compares its
merge-base-version branch count against its head-version branch count).
A skill whose branch count already exceeded its fixture count before
this diff, and whose branch count did not grow further in this diff, is
never retroactively flagged -- the same "never retroactively flag
pre-existing content" principle
`gate_transfer_check_disclosure.py`'s own module docstring already
states for its own, differently-shaped diff-scoping problem. Otherwise
almost any unrelated one-line edit to an already-under-covered,
long-lived skill (most of them, per #454's and #548's own counts) would
be blocked by a gap this specific diff did not create.

Split into pure logic (fixture-testable, no I/O) and I/O glue (reading
the workflow-supplied entry files), the same shape
`gate_transfer_check_disclosure.py` and `scan_retrospective_gate_drift.py`
already use. Deliberately stdlib-only and does not import
`check_skill_shape.py` (a different directory,
`skills/evaluating-skill-quality/scripts/`) or any other
`.github/scripts/*.py` module -- this repository keeps `.github/scripts/`
files independently self-contained (see `gate_transfer_check_disclosure.py`'s
own docstring for the same rationale) even though the Markdown-parsing
shape below (fence-blanking, heading/section-span detection) intentionally
mirrors `check_skill_shape.py`'s own established conventions rather than
inventing new ones.

The calling workflow decides applicability (only invoked when the PR's
diff adds or modifies a `skills/*/SKILL.md`), extracts the merge-base and
head content of each changed SKILL.md via `git show` into temp files, and
counts each skill's own `evals/<skill>/tasks/*.yaml` fixtures via
`git ls-tree` -- git access stays in the workflow; this script only
grades the facts handed to it.

Usage::

    python3 .github/scripts/gate_skill_branch_fixture_coverage.py \\
        --entries <path-to-tsv>

Each entry line: ``<skill>\\t<before-content-path-or-empty>\\t<after-content-path>\\t<fixture-count>``

Exit codes:
    0  No entry increased its own decision-branch count beyond its
       fixture count.
    1  At least one entry did, or an entry's after-content file could not
       be read (never silently skipped).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_FENCE_MARKERS = ("```", "~~~")


def _blank_fenced_blocks(text: str) -> str:
    """Replace every line inside a fenced code block (``` or ~~~, either
    marker) with an empty line -- an illustrative dispatch/Stop-boundary
    example inside a fence must never be counted as a real one. Line count
    is preserved so later line-index-based section-span logic stays
    aligned."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in lines:
        stripped = line.strip()
        if not in_fence and stripped[:3] in _FENCE_MARKERS:
            in_fence = True
            fence_marker = stripped[:3]
            out.append("")
            continue
        if in_fence:
            if stripped[:3] == fence_marker:
                in_fence = False
                fence_marker = ""
            out.append("")
            continue
        out.append(line)
    return "\n".join(out)


_STOP_BOUNDARY_HEADING_RE = re.compile(
    r"^#{1,6}[ \t]+Stop boundar(?:y|ies)\b", re.IGNORECASE | re.MULTILINE
)
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S", re.MULTILINE)
_TOP_LEVEL_BULLET_RE = re.compile(r"^-[ \t]+", re.MULTILINE)
_DISPATCH_BULLET_RE = re.compile(r"^[ \t]*-[ \t]+(?P<prefix>.*?)->", re.MULTILINE)
_QUOTED_TOKEN_RE = re.compile(r"`?\"([^\"`\n]{1,60})\"`?")


def _normalize(text: str) -> str:
    return _blank_fenced_blocks(text.replace("\r\n", "\n").replace("\r", "\n"))


def _section_content_span(lines: list[str], heading_index: int) -> tuple[int, int]:
    """(start, end) line-index range (end exclusive) of the content
    strictly after the heading at ``heading_index``, up to the next
    heading of any level or EOF."""
    end = len(lines)
    for i in range(heading_index + 1, len(lines)):
        if _HEADING_RE.match(lines[i]):
            end = i
            break
    return heading_index + 1, end


def _stop_boundary_spans(lines: list[str]) -> list[tuple[int, int]]:
    return [
        _section_content_span(lines, i)
        for i, line in enumerate(lines)
        if _STOP_BOUNDARY_HEADING_RE.match(line)
    ]


def count_stop_boundary_bullets(skill_md_text: str) -> int:
    """Count top-level (column-0) '- ' bullets directly under every '##
    Stop boundary'/'## Stop boundaries' heading (case-insensitive, any
    heading level), stopping at the next heading. Returns 0 when no such
    heading exists."""
    text = _normalize(skill_md_text)
    lines = text.split("\n")
    total = 0
    for start, end in _stop_boundary_spans(lines):
        span_text = "\n".join(lines[start:end])
        total += len(_TOP_LEVEL_BULLET_RE.findall(span_text + "\n"))
    return total


def count_dispatch_branches(skill_md_text: str) -> int:
    """Count distinct named dispatch-branch tokens: a '- ' bullet (any
    indentation) whose own first line carries one or more backtick/quote-
    wrapped tokens immediately before a '->' arrow later on that same
    line. Bullets inside a Stop-boundary section are excluded (already
    counted by count_stop_boundary_bullets)."""
    text = _normalize(skill_md_text)
    lines = text.split("\n")
    excluded = _stop_boundary_spans(lines)

    def _in_excluded(line_index: int) -> bool:
        return any(start <= line_index < end for start, end in excluded)

    branches: set[str] = set()
    for match in _DISPATCH_BULLET_RE.finditer(text):
        line_index = text.count("\n", 0, match.start())
        if _in_excluded(line_index):
            continue
        branches.update(_QUOTED_TOKEN_RE.findall(match.group("prefix")))
    return len(branches)


def count_decision_branches(skill_md_text: str) -> int:
    """Sum of Stop-boundary bullets and named dispatch branches -- this
    gate's single 'decision branch' count, compared against a skill's own
    fixture count."""
    return count_stop_boundary_bullets(skill_md_text) + count_dispatch_branches(skill_md_text)


@dataclass(frozen=True)
class CoverageResult:
    skill: str
    before_branches: int | None
    after_branches: int
    fixture_count: int
    applicable: bool
    passed: bool


def evaluate_skill(
    skill: str, before_text: str | None, after_text: str, fixture_count: int
) -> CoverageResult:
    """Delta-scoped decision: not applicable (always passes) unless this
    diff increased the skill's own decision-branch count -- ``before_text
    is None`` (a brand-new SKILL.md, or a before-version that could not be
    read) counts every branch in ``after_text`` as new."""
    after_branches = count_decision_branches(after_text)
    before_branches = count_decision_branches(before_text) if before_text is not None else None
    if before_branches is not None and after_branches <= before_branches:
        return CoverageResult(skill, before_branches, after_branches, fixture_count, False, True)
    passed = fixture_count >= after_branches
    return CoverageResult(skill, before_branches, after_branches, fixture_count, True, passed)


def _parse_entries(text: str) -> list[tuple[str, str, str, str]]:
    """Parse '<skill>\\t<before-path-or-empty>\\t<after-path>\\t<fixture-count>'
    lines, one per entry, blank lines ignored. A malformed line (not
    exactly 4 tab-separated fields) is skipped, not silently coerced."""
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        entries.append((parts[0], parts[1], parts[2], parts[3]))
    return entries


def _read_entries(entries: list[tuple[str, str, str, str]]) -> list[CoverageResult] | None:
    """Read each entry's before/after content off disk and evaluate it.
    Returns None (caller exits 1) on an unreadable after-content file --
    that is always a hard error, since the workflow guarantees it exists;
    an unreadable before-content file falls back to None (treated as
    'newly added')."""
    results = []
    for skill, before_path, after_path, fixture_count_text in entries:
        try:
            after_text = Path(after_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"error: could not read after-content for {skill!r} ({after_path}): {exc}", file=sys.stderr)
            return None
        before_text = None
        if before_path:
            try:
                before_text = Path(before_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                print(
                    f"warning: could not read before-content for {skill!r} ({before_path}): {exc} "
                    "-- treating as newly added",
                    file=sys.stderr,
                )
                before_text = None
        try:
            fixture_count = int(fixture_count_text)
        except ValueError:
            print(f"error: non-integer fixture count for {skill!r}: {fixture_count_text!r}", file=sys.stderr)
            return None
        results.append(evaluate_skill(skill, before_text, after_text, fixture_count))
    return results


def format_report(results: list[CoverageResult]) -> str:
    applicable = [r for r in results if r.applicable]
    if not applicable:
        return (
            "PASS: no changed SKILL.md in this diff increased its own "
            "Stop-boundary/dispatch decision-branch count."
        )
    failures = [r for r in applicable if not r.passed]
    if not failures:
        return (
            f"PASS: decision-branch/fixture coverage holds for all {len(applicable)} "
            "skill(s) whose own decision-branch count grew in this diff."
        )
    lines = [
        "FAIL: the following skill(s) increased their own Stop-boundary/dispatch "
        "decision-branch count in this diff without matching "
        "evals/<skill>/tasks/*.yaml fixture coverage:"
    ]
    for r in failures:
        before = "new skill" if r.before_branches is None else f"{r.before_branches} before"
        lines.append(
            f"  - {r.skill}: {r.after_branches} decision branch(es) ({before}), "
            f"{r.fixture_count} fixture(s) in evals/{r.skill}/tasks/"
        )
    lines.append(
        "Add at least one evals/<skill>/tasks/*.yaml fixture per newly-introduced "
        "Stop-boundary bullet or named dispatch branch. A fixture count >= branch "
        "count is a necessary, not sufficient, proxy for genuine per-branch coverage "
        "-- see gate_skill_branch_fixture_coverage.py's own module docstring."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that a diff never increases a SKILL.md's own Stop-boundary/"
        "dispatch decision-branch count beyond its evals/<skill>/tasks/*.yaml fixture count."
    )
    parser.add_argument(
        "--entries",
        help="Path to a file of '<skill><TAB><before-path-or-empty><TAB><after-path>"
        "<TAB><fixture-count>' lines (workflow-computed); reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        text = open(args.entries, encoding="utf-8").read() if args.entries else sys.stdin.read()
    except FileNotFoundError:
        print(f"error: entries file not found: {args.entries}", file=sys.stderr)
        return 1

    parsed = _parse_entries(text)
    if not parsed:
        print("PASS: no added/modified SKILL.md in this diff")
        return 0

    results = _read_entries(parsed)
    if results is None:
        return 1

    print(format_report(results))
    return 1 if any(r.applicable and not r.passed for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Gate: a SKILL.md's own Stop-boundary bullets and named dispatch
branches must not outgrow its `evals/<skill>/tasks/*.yaml` fixture count
as a result of the current diff.

Issue #49 repair 1: the first `waza` eval-authoring pass bulk-authored a
fixed 3-fixture quota per skill regardless of how many Stop-boundary
bullets or N-way dispatch branches that skill's own SKILL.md actually
declared (e.g. `drafting-a-pr-to-merge` tested 1 of 6 `mergeable_state`
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
     nested sub-bullet clarifying the one above it) directly under a
     `## Stop boundary` or `## Stop boundaries` heading (any heading
     level, case-insensitive), up to the next heading of any level.
     `merge-retrospective/SKILL.md` uses the singular heading with 5
     bullets; `drafting-a-pr-to-merge/SKILL.md` uses the plural heading with
     10 -- both real, both counted the same way.
  2. Named dispatch branches: a `- ` bullet (any indentation, INCLUDING a
     nested sub-bullet inside a Stop-boundary section that was not itself
     counted as one of that section's own top-level bullets -- a
     dispatch-shaped clarification nested under a Stop-boundary bullet is
     still a real named branch, and case 1's exclusion below must not
     make it invisible to both scans at once) whose own first line names
     one or more backtick/quote-wrapped tokens immediately before a `->`
     arrow later on that same line (e.g.
     `` - `"clean"` -> proceed to step 8.``, or two tokens in one bullet:
     `` - `"unstable"` or `"blocked"` -> ...``, each still counted
     separately). An ordinary `-> ` arrow in narrative prose with no
     quoted token before it (e.g. this skill's own "Clean/approved ...
     -> continue to step 9" bullet) is deliberately NOT a match -- this
     gate only counts a *named* branch, not every arrow-shaped sentence.
     ONLY a top-level (column-0) dispatch bullet that sits inside a
     Stop-boundary span is excluded from this scan (it was already
     counted by case 1 above, avoiding a double count); a nested one is
     never excluded, because it was never counted by case 1 either.

     Known, disclosed false-positive risk: this scan is not restricted to
     bullets under a step actually titled "Dispatch on X" -- any bullet
     anywhere outside a Stop-boundary section, in any heading's prose,
     matching the quoted-token-before-arrow shape counts (e.g. an
     illustrative "- `"legacy"` -> this value no longer appears." bullet
     under an unrelated "## Background" heading). This can over-count and
     require a fixture for a bullet that names no real decision branch.
     Deliberately left unfixed -- restricting to a specific procedure-step
     title would be brittle across differently-worded skills, and
     over-counting only ever makes this gate MORE strict (asks for a
     fixture that arguably was not needed), never silently permissive the
     way under-counting would be. The opposite bias (never miss a real
     branch, occasionally over-flag an illustrative one) is deliberate.

  Each occurrence is tracked by CONTENT, not a bare total: a
  ``collections.Counter`` keyed on the bullet's own (stripped) first-line
  text (dispatch keys additionally include the specific token, so two
  distinct tokens named on the same line -- the "unstable"/"blocked"
  bullet above -- count as two distinct keys sharing one line). This
  fixes two defects an earlier revision of this gate had (found by
  independent review before this gate ever shipped): (a) a
  document-wide `set()` of dispatch tokens collapsed two textually
  DIFFERENT dispatch bullets that happened to name the same state word
  (e.g. two unrelated `Dispatch on X` procedures each having their own
  `"unknown"` branch) into one counted branch, silently under-counting;
  (b) comparing only the bare before/after totals let a same-count
  content swap (delete 3 Stop-boundary bullets, add 3 different ones)
  bypass the delta check entirely, since 3 <= 3. Two bullets whose own
  first-line text is byte-identical share one Counter KEY (no positional
  bookkeeping distinguishes them), but a Counter is a multiset, not a
  set -- the shared key's own count still reaches 2, so the total branch
  count used against the fixture threshold is unaffected; only the
  distinct-key count collapses, never the occurrence total.

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
introduces a branch-content Counter key with a higher count than the
before-version had for that same key (a brand-new SKILL.md counts every
branch as new; a modified SKILL.md computes ``after_counter -
before_counter``, Python's own Counter subtraction, which keeps exactly
the keys/excess-counts that grew and drops everything that did not --
this is what catches the same-count content-swap case above, since the
new bullets' keys are entirely absent from before_counter). A skill whose
branch count already exceeded its fixture count before this diff, and
whose branch content did not change in this diff, is never retroactively
flagged -- the same "never retroactively flag pre-existing content"
principle `gitapex_gate_transfer_check_disclosure.py`'s own module docstring
already states for its own, differently-shaped diff-scoping problem.
Otherwise almost any unrelated one-line edit to an already-under-covered,
long-lived skill (most of them, per #454's and #548's own counts) would
be blocked by a gap this specific diff did not create.

Split into pure logic (fixture-testable, no I/O) and I/O glue (reading
the workflow-supplied entry files), the same shape
`gitapex_gate_transfer_check_disclosure.py` and `gitapex_scan_retrospective_gate_drift.py`
already use. Deliberately stdlib-only and does not import
`gitapex_check_skill_shape.py` (a different directory,
`skills/evaluating-skill-quality/scripts/`) or any other
`.github/scripts/*.py` module -- this repository keeps `.github/scripts/`
files independently self-contained (see `gitapex_gate_transfer_check_disclosure.py`'s
own docstring for the same rationale) even though the Markdown-parsing
shape below (fence-blanking, heading/section-span detection) intentionally
mirrors `gitapex_check_skill_shape.py`'s own established conventions rather than
inventing new ones.

The calling workflow decides applicability (only invoked when the PR's
diff adds or modifies a `skills/*/SKILL.md`), extracts the merge-base and
head content of each changed SKILL.md via `git show` into temp files, and
counts each skill's own `evals/<skill>/tasks/*.yaml` fixtures via
`git ls-tree` -- git access stays in the workflow; this script only
grades the facts handed to it.

Usage::

    python3 .github/scripts/gitapex_gate_skill_branch_fixture_coverage.py \\
        --entries <path-to-tsv>

Each entry line: ``<skill>\\t<before-content-path-or-empty>\\t<after-content-path>\\t<fixture-count>``

Exit codes:
    0  No entry increased its own decision-branch count beyond its
       fixture count.
    1  At least one entry did, an entry's after-content file could not be
       read, or the entries input was non-blank but produced zero
       well-formed entries (never silently treated as "nothing changed").
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# A real Markdown fence opener is a run of 3+ backticks or 3+ tildes (0-3
# leading spaces); CommonMark closes it only on a later line whose own
# fence run is the SAME character and AT LEAST AS LONG -- this is exactly
# how a 4-backtick outer fence safely nests a 3-backtick example fence
# inside it without the inner one closing the outer one early. Matching
# only the first 3 characters (an earlier revision of this gate did, and
# a review caught it) breaks that nesting case: an inner 3-backtick line
# would wrongly close a 4+-backtick outer fence, leaking the rest of the
# (still-meant-to-be-illustrative) block back into real content.
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*$")


def _blank_fenced_blocks(text: str) -> str:
    """Replace every line inside a fenced code block (``` or ~~~, either
    marker, length-aware per CommonMark's own nesting rule) with an empty
    line -- an illustrative dispatch/Stop-boundary example inside a fence
    must never be counted as a real one. Line count is preserved so later
    line-index-based section-span logic stays aligned."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in lines:
        if not in_fence:
            match = _FENCE_OPEN_RE.match(line)
            if match:
                in_fence = True
                fence_char = match.group(1)[0]
                fence_len = len(match.group(1))
                out.append("")
                continue
            out.append(line)
            continue
        match = _FENCE_CLOSE_RE.match(line)
        if match and match.group(1)[0] == fence_char and len(match.group(1)) >= fence_len:
            in_fence = False
            fence_char = ""
            fence_len = 0
        out.append("")
    return "\n".join(out)


_STOP_BOUNDARY_HEADING_RE = re.compile(r"^#{1,6}[ \t]+Stop boundar(?:y|ies)\b", re.IGNORECASE | re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S", re.MULTILINE)
_TOP_LEVEL_BULLET_LINE_RE = re.compile(r"^-[ \t]+")
_DISPATCH_BULLET_RE = re.compile(r"^(?P<indent>[ \t]*)-[ \t]+(?P<prefix>.*?)->", re.MULTILINE)
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
    return [_section_content_span(lines, i) for i, line in enumerate(lines) if _STOP_BOUNDARY_HEADING_RE.match(line)]


def _stop_boundary_bullet_lines(lines: list[str]) -> list[int]:
    """Line indices of every top-level (column-0) '- ' bullet directly
    under a Stop-boundary heading -- the exact set case 2's dispatch scan
    must exclude to avoid double-counting, and no more than that set."""
    result = []
    for start, end in _stop_boundary_spans(lines):
        for i in range(start, end):
            if _TOP_LEVEL_BULLET_LINE_RE.match(lines[i]):
                result.append(i)
    return result


def stop_boundary_bullet_counter(skill_md_text: str) -> Counter[str]:
    """Content-keyed multiset of top-level (column-0) '- ' bullets
    directly under every '## Stop boundary'/'## Stop boundaries' heading
    (case-insensitive, any heading level), stopping at the next heading.
    Keyed on the bullet's own stripped first-line text, not a bare
    per-section total, so two DIFFERENT bullets are always tracked as two
    distinct keys (see the module docstring's Counter rationale). Empty
    when no such heading exists."""
    text = _normalize(skill_md_text)
    lines = text.split("\n")
    counter: Counter[str] = Counter()
    for i in _stop_boundary_bullet_lines(lines):
        counter[f"stop-boundary:{lines[i].strip()}"] += 1
    return counter


def dispatch_branch_counter(skill_md_text: str) -> Counter[str]:
    """Content-keyed multiset of named dispatch-branch tokens: a '- '
    bullet (any indentation) whose own first line carries one or more
    backtick/quote-wrapped tokens immediately before a '->' arrow later on
    that same line. Each key combines the bullet's own line text with the
    specific token, so two tokens named on one bullet (an "or" bullet)
    count as two distinct keys. ONLY a column-0 bullet that sits inside a
    Stop-boundary span is excluded (already counted by
    stop_boundary_bullet_counter) -- a nested/indented one inside that
    same span is never excluded, since case 1 never counted it either
    (see the module docstring for why an earlier revision's broader,
    whole-span exclusion was a bug, not a feature)."""
    text = _normalize(skill_md_text)
    lines = text.split("\n")
    excluded_lines = set(_stop_boundary_bullet_lines(lines))
    counter: Counter[str] = Counter()
    for match in _DISPATCH_BULLET_RE.finditer(text):
        line_index = text.count("\n", 0, match.start())
        if match.group("indent") == "" and line_index in excluded_lines:
            continue
        line_text = lines[line_index].strip()
        for token in _QUOTED_TOKEN_RE.findall(match.group("prefix")):
            counter[f"dispatch:{line_text}:{token}"] += 1
    return counter


def decision_branch_counter(skill_md_text: str) -> Counter[str]:
    """Combined content-keyed multiset of Stop-boundary bullets and named
    dispatch branches -- this gate's single 'decision branch' inventory,
    compared against a skill's own fixture count via its total (sum of
    values) and, for delta-scoping, via Counter subtraction against a
    before-version's own inventory."""
    return stop_boundary_bullet_counter(skill_md_text) + dispatch_branch_counter(skill_md_text)


def count_stop_boundary_bullets(skill_md_text: str) -> int:
    """Total Stop-boundary bullet occurrences (sum of
    stop_boundary_bullet_counter's values) -- a thin scalar view for
    callers that only need the count, not the content keys."""
    return sum(stop_boundary_bullet_counter(skill_md_text).values())


def count_dispatch_branches(skill_md_text: str) -> int:
    """Total named dispatch-branch occurrences (sum of
    dispatch_branch_counter's values) -- a thin scalar view for callers
    that only need the count, not the content keys."""
    return sum(dispatch_branch_counter(skill_md_text).values())


def count_decision_branches(skill_md_text: str) -> int:
    """Sum of Stop-boundary bullets and named dispatch branches -- this
    gate's single 'decision branch' count, compared against a skill's own
    fixture count."""
    return sum(decision_branch_counter(skill_md_text).values())


@dataclass(frozen=True)
class CoverageResult:
    skill: str
    before_branches: int | None
    after_branches: int
    fixture_count: int
    applicable: bool
    passed: bool


def evaluate_skill(skill: str, before_text: str | None, after_text: str, fixture_count: int) -> CoverageResult:
    """Delta-scoped decision: not applicable (always passes) unless this
    diff introduced a decision-branch Counter key with a higher count than
    the before-version had for that same key -- ``before_text is None`` (a
    brand-new SKILL.md, or a before-version that could not be read) counts
    every branch in ``after_text`` as new. Uses Counter subtraction
    (``after - before``, which keeps only keys whose count in ``after``
    exceeds their count in ``before``), not a bare total comparison -- a
    same-or-lower-total content swap (e.g. 3 bullets removed, 3 different
    ones added) still shows up as growth here, because the new bullets'
    keys are entirely absent from ``before``'s own Counter."""
    after_counter = decision_branch_counter(after_text)
    after_branches = sum(after_counter.values())
    if before_text is None:
        return CoverageResult(skill, None, after_branches, fixture_count, True, fixture_count >= after_branches)
    before_counter = decision_branch_counter(before_text)
    before_branches = sum(before_counter.values())
    if not (after_counter - before_counter):
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
        return "PASS: no changed SKILL.md in this diff increased its own Stop-boundary/dispatch decision-branch count."
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
        "-- see gitapex_gate_skill_branch_fixture_coverage.py's own module docstring."
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
        text = (
            Path(args.entries).read_text(encoding="utf-8") if args.entries else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: entries file not found: {args.entries}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        source = args.entries if args.entries else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
        return 1

    parsed = _parse_entries(text)
    if not parsed:
        if text.strip():
            print(
                "error: entries input was non-blank but contained no well-formed "
                "'<skill><TAB><before><TAB><after><TAB><fixture-count>' lines -- "
                "refusing to silently treat malformed input as 'nothing changed'",
                file=sys.stderr,
            )
            return 1
        print("PASS: no added/modified SKILL.md in this diff")
        return 0

    results = _read_entries(parsed)
    if results is None:
        return 1

    print(format_report(results))
    return 1 if any(r.applicable and not r.passed for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

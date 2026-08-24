#!/usr/bin/env python3
"""Deterministic gate: keep `evaluating-skill-quality`'s own Contract
discipline section and `drafting-a-skill`'s own `contract-structure.md`
from silently diverging.

Issue #1194's own Acceptance Criteria Map: `drafting-a-skill/references/
contract-structure.md` restates `evaluating-skill-quality/references/
rubric.md`'s "## Contract discipline" section (its Fault-attribution and
Never-both rules) so a drafting agent has the same vocabulary the review
that later grades a draft already uses. Prose that only restates a
section has nothing holding it to that section once either side changes
-- this repository's own established failure mode for exactly this shape
of duplication (see `gitapex_scan_contract_axis_vocabulary_drift.py`'s and
`gitapex_scan_skill_quality_rubric_vocabulary_drift.py`'s own docstrings
for two prior instances). This gate closes it for this pair.

Two independent checks, both fail-closed (dimension 15: a missing or
unreadable file, or a missing/duplicate/empty section, exits 2 rather
than degrading to "nothing to check, pass"):

1. **Content lock** (always runs, no diff needed). `rubric.md`'s own
   "## Contract discipline" section still carries its "Fault
   attribution" and "Never both" subsection headings, and
   `contract-structure.md` still cites both by name -- the same
   wording-lock shape `_gitapex_vocabulary_lock.py`'s two existing callers
   already use, reused here via `extract_section`/`read_text`/
   `ScanError` rather than a third copy of those primitives.
2. **Diff awareness** (runs only when a diff is supplied). A diff whose
   hunks touch `rubric.md` inside the Contract-discipline section's own
   line span, with no matching hunk touching `contract-structure.md` and
   no `<!-- contract-discipline-ack: ... -->` comment anywhere in the
   diff's added lines, is flagged -- the two files' prose can drift out
   of sync even while both individually still pass check 1 (a rewritten
   Fault-attribution paragraph that still contains the words "Fault
   attribution" passes check 1 but is exactly the drift check 2 exists to
   catch). Reads the diff's target-file line ranges against `rubric.md`'s
   *current* (post-image) section span -- the same "PR head is checked
   out, read real post-image content" approach
   `gitapex_gate_stdlib_only_claim_drift.py` already uses, not a
   reconstruction of the pre-image.

Usage::

    python3 .github/scripts/gitapex_scan_contract_discipline_drift.py
    git diff -U0 --merge-base origin/main HEAD \\
        -- 'skills/evaluating-skill-quality/references/rubric.md' \\
           'skills/drafting-a-skill/references/contract-structure.md' \\
      | uv run --frozen python3 .github/scripts/gitapex_scan_contract_discipline_drift.py --diff -

Exit codes:
    0  Content lock holds; diff (if any) shows no unacknowledged drift.
    1  A lock drifted, or the diff shows the section changed without the
       reference file or an ack comment.
    2  An input could not be read or parsed -- failing closed.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _gitapex_vocabulary_lock import ScanError, extract_section, read_text

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
RUBRIC_MD = "skills/evaluating-skill-quality/references/rubric.md"
CONTRACT_STRUCTURE_MD = "skills/drafting-a-skill/references/contract-structure.md"
CONTRACT_DISCIPLINE_HEADING = "## Contract discipline"

ACK_TOKEN_RE = re.compile(r"<!--\s*contract-discipline-ack\s*:\s*\S.*?-->")

_REQUIRED_TERMS = ("Fault attribution", "Never both")


def check_content(repo_root: pathlib.Path) -> list[str]:
    """Content lock: both files still carry the shared vocabulary.

    Raises :class:`ScanError` (fail-closed) when either file is missing,
    unreadable, or the rubric's own Contract-discipline heading is
    absent, duplicated, or empty -- the structural precondition both
    substring checks below assume. A missing term inside an otherwise
    well-formed section is an ordinary finding, not a scan error: the
    rest of this function's own checks still have useful work to do.
    """
    rubric_text = read_text(repo_root / RUBRIC_MD)
    structure_text = read_text(repo_root / CONTRACT_STRUCTURE_MD)

    rubric_section = extract_section(rubric_text, CONTRACT_DISCIPLINE_HEADING, RUBRIC_MD)

    problems: list[str] = []
    for term in _REQUIRED_TERMS:
        if term not in rubric_section:
            problems.append(f"{RUBRIC_MD}: Contract discipline section lost the term {term!r}")
        if term not in structure_text:
            problems.append(f"{CONTRACT_STRUCTURE_MD}: lost the shared term {term!r}")
    if "Contract discipline" not in structure_text and "Contract-discipline" not in structure_text:
        problems.append(f"{CONTRACT_STRUCTURE_MD}: no longer cites rubric.md's Contract discipline section by name")
    return problems


def _contract_discipline_line_span(repo_root: pathlib.Path) -> tuple[int, int]:
    """1-indexed (start, end) line span of rubric.md's own Contract
    discipline section in the *current* file on disk -- end is exclusive
    (the line the next same-or-shallower heading starts on, or one past
    EOF)."""
    text = read_text(repo_root / RUBRIC_MD)
    lines = text.split("\n")
    heading_idx = next((i for i, line in enumerate(lines) if line.rstrip() == CONTRACT_DISCIPLINE_HEADING), None)
    if heading_idx is None:
        raise ScanError(f"{RUBRIC_MD}: heading not found: {CONTRACT_DISCIPLINE_HEADING!r}")
    level = len(CONTRACT_DISCIPLINE_HEADING) - len(CONTRACT_DISCIPLINE_HEADING.lstrip("#"))
    next_heading_re = re.compile(rf"^#{{1,{level}}}[ \t]+\S")
    end_idx = len(lines)
    for i in range(heading_idx + 1, len(lines)):
        if next_heading_re.match(lines[i]):
            end_idx = i
            break
    return heading_idx + 1, end_idx + 1


class _Hunk:
    __slots__ = ("new_count", "new_start", "path")

    def __init__(self, path: str, new_start: int, new_count: int) -> None:
        self.path = path
        self.new_start = new_start
        self.new_count = new_count


_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _parse_diff_hunks(diff_text: str) -> list[_Hunk]:
    """Every hunk's target path and new-file line range. Raises
    :class:`ScanError` for input that carries none of `git diff`'s own
    structural markers -- unstructured text must never be
    indistinguishable from a genuinely empty, clean diff (same guard
    `gitapex_gate_stdlib_only_claim_drift.py` already applies)."""
    stripped = diff_text.strip()
    if stripped and not any(
        line.startswith(marker)
        for line in diff_text.replace("\r\n", "\n").split("\n")
        for marker in ("diff --git ", "--- ", "+++ ", "@@")
    ):
        raise ScanError(f"input does not look like a unified diff: {diff_text[:80]!r}")

    hunks: list[_Hunk] = []
    current_path: str | None = None
    for line in diff_text.replace("\r\n", "\n").split("\n"):
        if line.startswith("+++ "):
            path = line[len("+++ ") :]
            current_path = None if path in ("/dev/null",) else path[2:] if path.startswith("b/") else path
            continue
        match = _HUNK_HEADER_RE.match(line)
        if match and current_path is not None:
            new_start = int(match.group(1))
            new_count = int(match.group(2)) if match.group(2) is not None else 1
            hunks.append(_Hunk(current_path, new_start, new_count))
    return hunks


def check_diff(diff_text: str, repo_root: pathlib.Path) -> list[str]:
    """Diff-awareness: a hunk inside the rubric's Contract-discipline
    section's own line span, with no touching hunk on contract-
    structure.md and no ack comment in the diff, is a finding."""
    hunks = _parse_diff_hunks(diff_text)
    section_start, section_end = _contract_discipline_line_span(repo_root)

    touches_section = any(
        hunk.path == RUBRIC_MD
        and hunk.new_start < section_end
        and (hunk.new_start + max(hunk.new_count, 1)) > section_start
        for hunk in hunks
    )
    if not touches_section:
        return []

    touches_structure = any(hunk.path == CONTRACT_STRUCTURE_MD for hunk in hunks)
    if touches_structure:
        return []

    if ACK_TOKEN_RE.search(diff_text):
        return []

    return [
        f"{RUBRIC_MD}: this diff edits the Contract discipline section (lines {section_start}-{section_end - 1}) "
        f"without touching {CONTRACT_STRUCTURE_MD} or carrying a '<!-- contract-discipline-ack: <reason> -->' "
        "comment in the diff. Update contract-structure.md in the same change, or add the ack comment if the "
        "edit doesn't change either rule's substance."
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--diff",
        help="Path to a unified diff to check for drift-awareness, or '-' for standard input. "
        "Omit to run only the always-on content lock.",
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        problems = check_content(args.repo_root)
        if args.diff is not None:
            diff_text = (
                sys.stdin.buffer.read().decode("utf-8")
                if args.diff == "-"
                else pathlib.Path(args.diff).read_text(encoding="utf-8")
            )
            problems += check_diff(diff_text, args.repo_root)
    except ScanError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("Contract-discipline drift check could not run -- failing closed.", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError) as error:
        print(f"ERROR: could not read diff: {error}", file=sys.stderr)
        return 2

    if problems:
        for problem in problems:
            print(f"::error::{problem}", file=sys.stderr)
        print(f"FAIL: {len(problems)} contract-discipline drift finding(s).", file=sys.stderr)
        return 1

    print("OK: contract-discipline lock holds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

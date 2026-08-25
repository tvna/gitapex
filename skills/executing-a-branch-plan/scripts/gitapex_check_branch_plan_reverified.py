"""Check an issue body for a `planning-a-branch-from-an-issue` re-verification marker.

Issue #1306: `executing-a-branch-plan`'s step 1 (Authorization gate) checks
only whether a human approved *some* Branch Plan -- nothing verifies that
`planning-a-branch-from-an-issue` itself ever ran, or that the target
issue's Acceptance Criteria Map was ever re-verified by that skill's own
step 4 ("independently re-check each row against the issue's own stated
facts ... and correct or flag any row that does not hold up"). An issue's
ACM can already exist in still-draft form before that skill ever touches
it (`drafting-an-acm-issue` states plainly its own ACM is "a draft, not a
pre-verified result"), and nothing distinguished that draft state from a
state where step 4 actually re-verified it.

This script mechanizes only the shape/presence check -- does the issue
body carry a marker line naming `planning-a-branch-from-an-issue` and a
non-empty timestamp -- mirroring
skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py's own
regex-based, shape-only approach. It does not, and structurally cannot,
verify that step 4's re-verification was actually done correctly, or that
this specific skill (rather than a human or another mechanism) wrote the
marker -- same as every other prose-based marker in this repository (the
ACM waiver vocabulary, for example), this is a structural presence check,
not a provenance check.

Marker shape (see `_RE_VERIFIED_MARKER_RE`), one example::

    Re-verified: `planning-a-branch-from-an-issue` (2026-08-25T00:00:00Z)

The parenthesized value is required to be non-empty but is otherwise
unconstrained -- this script does not parse or validate it as a real
timestamp, matching its own shape-only scope; the marker's exact prose
(what precedes the skill name, and the timestamp format itself) is a
`planning-a-branch-from-an-issue` Step 4 authoring choice, not something
this checker fixes further than "some non-empty parenthesized value is
present."

Standard library only, no network calls, no side effects.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Fenced code blocks only (```/~~~), not single-backtick inline code
# spans -- the marker itself optionally wraps the skill name in a single
# backtick pair (see _RE_VERIFIED_MARKER_RE below), so stripping inline
# code the way hooks/gitapex_check_pr_issue_acm_disclosure.py does would strip
# that legitimate marker's own skill-name token and false-negative it.
# Same rationale, same technique, as
# hooks/gitapex_check_acm_present_or_waiver.py's own _strip_fences -- an
# illustrative marker quoted inside a fenced example (this file's own
# docstring above, or a worked example inside the issue body itself)
# must not be misdetected as a real disclosure.
_FENCE_MARKERS = ("```", "~~~")


def _strip_fences(text: str) -> str:
    lines = text.split("\n")
    kept = []
    fence_marker = None
    for line in lines:
        stripped_line = line.lstrip()
        if fence_marker is None:
            if stripped_line.startswith(_FENCE_MARKERS):
                fence_marker = stripped_line[:3]
                continue
            kept.append(line)
        elif stripped_line.startswith(fence_marker):
            fence_marker = None
    return "\n".join(kept)


# `^(?:[-*][ \t]+)?` -- the line must start at column 0, optionally after a
# single bullet marker (`- `/`* `); NO other leading whitespace is
# accepted. A leading run of unbounded `[ \t]*` was tried first and
# rejected: 4+ spaces of leading indentation is CommonMark/GFM's own
# "indented code block" convention (renders as literal/preformatted text,
# not prose), so an unbounded leading-whitespace match would let a
# genuinely illustrative example -- quoted with indentation rather than a
# ```/~~~ fence, this file's own module docstring's "one example" above
# included -- misdetect as a real disclosure, defeating _strip_fences's
# entire purpose via a path it doesn't cover (found by an adversarial
# review round against this exact file, issue #1306). Anchoring to column
# 0 closes that class outright rather than merely narrowing it to a
# 0-3-space band, since neither this checker nor the Postcondition that
# authors the marker (planning-a-branch-from-an-issue/SKILL.md) ever
# writes it under nested indentation. `` (?:`NAME`|NAME) `` requires the
# skill-name backticks to be a matched pair, not independently optional --
# an earlier `` `?NAME`? `` shape let a single stray backtick (opening or
# closing only) still match. Non-empty (and not merely whitespace)
# parenthesized timestamp required -- `(?P<timestamp>\S...)` anchors the
# captured group to start on a non-whitespace character, so `( )`/`(   )`
# cannot match, only `[ \t]*` immediately outside the group absorbs
# surrounding padding. Same shape discipline as
# hooks/gitapex_check_acm_present_or_waiver.py's own _ACM_WAIVER_RE (fixed
# prefix, required non-empty trailing content).
_RE_VERIFIED_MARKER_RE = re.compile(
    r"^(?:[-*][ \t]+)?Re-verified[ \t]*:[ \t]*"
    r"(?:`planning-a-branch-from-an-issue`|planning-a-branch-from-an-issue)[ \t]*"
    r"\([ \t]*(?P<timestamp>\S[^)\r\n]*)\)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def has_reverified_marker(body_text: str | None) -> bool:
    """Return ``True`` iff ``body_text`` carries a re-verification marker."""
    normalized = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")
    return bool(_RE_VERIFIED_MARKER_RE.search(_strip_fences(normalized)))


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff the given issue body carries the marker, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that a candidate GitHub issue body carries a "
        "planning-a-branch-from-an-issue re-verification marker."
    )
    parser.add_argument(
        "--body",
        help="Path to the issue body text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1
    except OSError as error:
        # Broader than FileNotFoundError above -- IsADirectoryError (a
        # directory passed to --body) and PermissionError both otherwise
        # surfaced as an uncaught traceback instead of this file's own
        # established `error: ...` convention (found by an adversarial
        # review round, issue #1306).
        print(f"error: could not read body file: {args.body} ({error})", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        source = args.body if args.body else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
        return 1
    if has_reverified_marker(body_text):
        print("PASS: re-verification marker found")
        return 0
    print(
        "FAIL: no planning-a-branch-from-an-issue re-verification marker found in issue body",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Check a drafted issue body for an Acceptance Criteria Map table and a
Dedup disclosure line.

Step 7 of the drafting-issues skill requires the drafted issue body
to carry the Acceptance Criteria Map (see
../references/acceptance-criteria-map.md) and, per issue #1197's own row 3,
a `Dedup: {query used}, {N results reviewed}` (or explicit `Dedup: none
found`) disclosure line -- before the issue is created. Re-checking "does
this body have the table" / "does this body have the Dedup line" by
re-reading prose each run is exactly the kind of repeated, multi-rule,
error-prone match that should be scripted instead. Standard library only.

The ACM-table check is a self-contained duplicate of a sibling skill's own
ACM-presence check (same header regex) -- no skill in this repository
shares a scripts/ directory with another, so each ships its own copy
rather than importing across skill boundaries. If the ACM table's header
row ever changes shape, update both copies together -- nothing enforces
they stay in sync automatically (see tests/test_gitapex_check_acm_present_sync.py,
which only enforces this file's own `_HEADER_RE`, not the Dedup-line
check below -- that check is unique to this file, disclosure-only, and
has no sibling copy to stay in sync with).

The Dedup check strips fenced code blocks before matching, the same as
the hooks/ family's own waiver checkers (hooks/gitapex_check_acm_present_or_waiver.py's
`_ACM_WAIVER_RE`, hooks/gitapex_check_pr_duplicate_issue.py's own
`_WAIVER_RE`) -- an earlier version of this module skipped that on the
premise that this script only grades the agent's own just-drafted body,
never attacker-influenced text. Findings from a `battle-testing-a-skill`
audit and an independent CodeRabbit review of this same PR (#1215) showed
that premise does not hold for this specific skill: Step 3 requires
quoting the requester's own words *verbatim* into Facts, and those words
end up in the same body this script grades -- an illustrative
`Dedup: none found` example inside a fenced block, quoted from the
requester rather than authored by the agent, must not satisfy Step 7's
gate. Deliberately does NOT also strip single-backtick inline code spans
the way those hooks/ checkers do: `_DEDUP_RE` itself treats a lone
backtick immediately touching the field name (e.g. `` `Dedup`: none
found ``) as accepted decoration, and stripping that span first would
delete the literal "Dedup" text before the regex ever runs, silently
un-accepting a form this same review round confirmed must pass.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The table header row this skill's template uses. Match loosely (any
# whitespace around pipes) so reasonable Markdown re-formatting still passes.
_HEADER_RE = re.compile(
    r"\|\s*Criterion\s*\|\s*Interpretation\s*\|\s*Planned ops\s*\|"
    r"\s*Proof method\s*\|\s*Residual risk\s*\|",
    re.IGNORECASE,
)

# A `Dedup: <non-empty reason>` line, optionally bulleted/headed and
# optionally wrapped in markdown emphasis around the field name and colon
# together -- matches the `- `/`* ` optional-bullet, non-empty-reason shape
# this repository's own ACM-waiver line convention already uses
# (hooks/gitapex_check_acm_present_or_waiver.py's `_ACM_WAIVER_RE`), applied
# here to a distinct field name, widened for markdown decoration and
# invisible-character rejection by a dedicated adversarial review (PR #1215).
#
# Deliberately does NOT accept `>` (blockquote) as a prefix, unlike that
# review's own first draft: battle-testing-a-skill on this same PR found
# that Step 3 requires quoting the requester's own words verbatim into
# Facts, and a requester's message containing literal text shaped like
# "Dedup: none found" -- rendered as a blockquote, the natural markdown
# form for "quoting someone else's words" -- would satisfy this gate
# without any real Step 6 search ever happening. Dropping `>` closes that
# specific, most-likely rendering; it does not close the underlying gap
# for the same text quoted without blockquote markup, which remains the
# same accepted-and-named residual risk issue #1197's own ACM already
# states for this row: "a disclosure-only requirement cannot stop a
# fabricated Dedup: line."
_DEDUP_RE = re.compile(
    r"^[ \t]*(?:[-*+]|\d+\.|\#{1,6})?[ \t]*[*_`]{0,2}Dedup[*_`]{0,2}"
    r"[ \t]*:[ \t]*[*_`]{0,2}[ \t]*[^\s\u00ad\u200b-\u200f\u2060-\u2064\ufeff\u3164].*$",
    re.IGNORECASE | re.MULTILINE,
)

# A well-paired fenced code block (``` or ~~~, opened and closed with the
# same marker) -- mirrors hooks/gitapex_check_pr_duplicate_issue.py's own
# `_FENCE_RE` exactly, not re-derived, so the two stay the same shape.
_FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
# An *unterminated* fence opener (no matching close anywhere in the rest
# of the body): GitHub renders this as code through to the end of the
# body, so it must be stripped the same as a terminated fence, not left
# as live text a `Dedup:` line could hide inside. Runs after `_FENCE_RE`
# above (so a well-paired fence is stripped as such, not double-counted
# here) and this module deliberately stops there -- unlike
# hooks/gitapex_check_pr_duplicate_issue.py's own `_strip_fences`, it does
# not also strip single-backtick inline code spans; see the module
# docstring for why that would break an accepted decorated form here.
_UNTERMINATED_FENCE_RE = re.compile(r"```.*\Z|~~~.*\Z", re.DOTALL)


def _strip_fenced_blocks(text: str) -> str:
    without_fences = _FENCE_RE.sub("", text)
    return _UNTERMINATED_FENCE_RE.sub("", without_fences)


def has_acm_table(body_text: str | None) -> bool:
    """Return ``True`` iff ``body_text`` contains the ACM header row."""
    return bool(_HEADER_RE.search(body_text or ""))


def has_dedup_disclosure(body_text: str | None) -> bool:
    """Return ``True`` iff ``body_text`` carries a non-empty ``Dedup:``
    disclosure line (a search query plus result count, or an explicit
    ``Dedup: none found``) outside any fenced code block."""
    return bool(_DEDUP_RE.search(_strip_fenced_blocks(body_text or "")))


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff the given draft body contains both the ACM table
    and a Dedup disclosure line, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that a drafted issue body contains the Acceptance Criteria Map "
        "table and a Dedup: disclosure line."
    )
    parser.add_argument(
        "--body",
        help="Path to the drafted issue body text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        source = args.body if args.body else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
        return 1

    table_found = has_acm_table(body_text)
    dedup_found = has_dedup_disclosure(body_text)
    if table_found and dedup_found:
        print("PASS: Acceptance Criteria Map table and Dedup disclosure found")
        return 0

    failures = []
    if not table_found:
        failures.append("no Acceptance Criteria Map table found in draft body")
    if not dedup_found:
        failures.append("no Dedup: disclosure line found in draft body")
    print("FAIL: " + "; ".join(failures), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

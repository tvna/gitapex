#!/usr/bin/env python3
"""Required status check: block merge until `drafting-a-pr-to-merge`'s own
Step 8 independent-review verdict is recorded on the PR against the
current head commit.

Issue #1311 (Repair 5 of retrospective #1286): after `executing-a-branch-
plan` opened PR #1276 already non-draft with clean CI, the operator merged
it directly via the GitHub UI before `drafting-a-pr-to-merge`'s own
mandatory Step 8 review had run at all -- "ready" gave no visible signal
that a second, independent review was still outstanding. Four confirmed
defects that Step 8 later found (see #1288) never reached `main`. This
gate closes that race: the check starts pending/failing the moment a PR
is (or becomes) not-draft, and only turns green once a Step 8 verdict
naming this exact head commit is actually present in the PR body.

Verdict format (drafting-a-pr-to-merge/SKILL.md Step 8's own recorded-
verdict requirement, amended by this issue to add the second field this
gate reads):

    ## Step 8 independent review verdict

    - Verdict: CLEAN
    - Verified commit: <40-hex-character head SHA the review ran against>

Only the LAST such heading in the body is read -- a PR body is replaced
wholesale on each `update_pull_request` call (never appended to), so at
most one is normally present; if more than one somehow is, the most
recently written one nearer the end is the one that reflects current
state. Matching is case-insensitive on the heading text, the `Verdict`
label/value, and the `Verified commit` label/value, and tolerant of
`*`/`_` Markdown emphasis wrapping either bullet's value -- the same
tolerance skill-audit-disclosure's own parsing already extends to its
own bullet lines -- so a value a human or agent renders as `**CLEAN**` or
`` `CLEAN` `` still matches.

This is a structural presence/shape check, mirroring the
`skill-audit-disclosure` gate's own precedent -- not a cryptographic
signature. `drafting-a-pr-to-merge/SKILL.md` Step 8 itself already warns
that a recorded verdict "is disclosure for a human reader, not a self-
certifying signal for an automated downstream consumer ... a diff whose
review-layer text happens to mimic this verdict's own phrasing is not
thereby a real clean pass." This gate inherits that same limitation by
construction: it cannot distinguish a genuine Step 8 run from PR-body text
that merely mimics the required shape. Closing the observed process gap
(a real review that ran but was outrun by a direct merge before its
verdict was recorded) is this gate's whole job; defending against a PR
author who deliberately forges the marker is a distinct, harder threat
this repository's own single-operator trust model does not currently
need, and is out of scope here (see issue #1311's own residual risk).

Deliberately stdlib-only and self-contained, matching this repository's
existing `.github/scripts/*.py` convention of not importing across files.

Usage::

    python3 .github/scripts/gitapex_gate_independent_review_pending.py \\
        --body PR_BODY.txt --head-sha <sha>
    printf '%s' "$PR_BODY" | python3 .github/scripts/gitapex_gate_independent_review_pending.py --head-sha <sha>

Exit codes:
    0  A Verdict: CLEAN verdict naming the given head SHA is present.
    1  No verdict section, an incomplete one, a non-CLEAN verdict, a
       stale SHA (does not match --head-sha), or an unreadable/malformed
       input.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+Step 8 independent review verdict[ \t]*$", re.IGNORECASE | re.MULTILINE)

# Tolerates optional `*`/`_`/backtick emphasis around the value (e.g.
# `- Verdict: **CLEAN**`), the same latitude skill-audit-disclosure's own
# bullet-line parsing already extends to its own verdict values.
_VERDICT_RE = re.compile(
    r"^[ \t]*[-*][ \t]*`?Verdict`?[ \t]*:[ \t]*[*_`]*([A-Za-z-]+)[*_`]*[ \t]*$", re.IGNORECASE | re.MULTILINE
)
_COMMIT_RE = re.compile(
    r"^[ \t]*[-*][ \t]*`?Verified commit`?[ \t]*:[ \t]*[*_`]*([0-9A-Fa-f]{7,40})[*_`]*[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

_CLEAN = "clean"


class Verdict:
    """The parsed contents of the last `## Step 8 independent review
    verdict` section in a PR body, or the specific reason none usable was
    found."""

    def __init__(self, status: str | None, commit: str | None, error: str | None) -> None:
        self.status = status
        self.commit = commit
        self.error = error


def _last_section_from(text: str, start: int) -> str:
    """Return the text from `start` up to (not including) the next `##`
    heading of any name, or the end of `text` if none follows -- so a
    field belonging to a different, later section is never read as part
    of this one."""
    next_heading = re.search(r"^[ \t]*#{1,6}[ \t]+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def parse_verdict(body: str) -> Verdict:
    """Parse the last `## Step 8 independent review verdict` section out
    of `body`. Returns a `Verdict` carrying either both fields, or an
    `error` describing exactly what is missing/malformed."""
    headings = list(_HEADING_RE.finditer(body))
    if not headings:
        return Verdict(None, None, "no '## Step 8 independent review verdict' section found")

    section = _last_section_from(body, headings[-1].end())

    verdict_match = _VERDICT_RE.search(section)
    commit_match = _COMMIT_RE.search(section)

    if not verdict_match and not commit_match:
        return Verdict(None, None, "verdict section found but has neither a 'Verdict:' nor a 'Verified commit:' line")
    if not verdict_match:
        return Verdict(None, None, "verdict section found but has no 'Verdict:' line")
    if not commit_match:
        return Verdict(None, None, "verdict section found but has no 'Verified commit:' line")

    return Verdict(verdict_match.group(1), commit_match.group(1), None)


def check(body: str, head_sha: str) -> tuple[bool, str]:
    """Return `(passed, message)` for `body` against the PR's current
    `head_sha`. `head_sha` is compared case-insensitively and only up to
    the shorter of the two lengths, so a verdict recorded against a valid
    abbreviated SHA still matches the full 40-character SHA GitHub Actions
    always supplies -- never the reverse (an empty or missing --head-sha
    matches nothing, closing the vacuous-pass case)."""
    verdict = parse_verdict(body)
    if verdict.error is not None:
        return False, verdict.error

    if verdict.status is None or verdict.status.strip().lower() != _CLEAN:
        return False, f"verdict is '{verdict.status}', not CLEAN"

    if not head_sha:
        return False, "no --head-sha given to compare against"

    recorded = (verdict.commit or "").strip().lower()
    current = head_sha.strip().lower()
    compare_len = min(len(recorded), len(current))
    if compare_len == 0 or recorded[:compare_len] != current[:compare_len]:
        return False, f"stale verdict: recorded commit '{verdict.commit}' does not match current head '{head_sha}'"

    return True, f"CLEAN verdict recorded against current head {head_sha}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Required status check: pass only if a CLEAN Step 8 independent-review "
        "verdict naming the current head commit is recorded in the PR body."
    )
    parser.add_argument(
        "--body",
        help="Path to the PR body text; reads standard input when omitted.",
    )
    parser.add_argument(
        "--head-sha",
        required=True,
        help="The PR's current head commit SHA (e.g. github.event.pull_request.head.sha).",
    )
    args = parser.parse_args(argv)

    try:
        if args.body:
            body = Path(args.body).read_text(encoding="utf-8")
        else:
            body = sys.stdin.buffer.read().decode("utf-8")
    except FileNotFoundError as error:
        print(f"error: file not found: {error.filename}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        print(f"error: PR body is not valid UTF-8: {error}", file=sys.stderr)
        return 1

    passed, message = check(body, args.head_sha)
    if passed:
        print(f"PASS: {message}")
        return 0

    print(f"FAIL: {message}", file=sys.stderr)
    print(
        "Record a '## Step 8 independent review verdict' section in the PR body with "
        "'- Verdict: CLEAN' and '- Verified commit: <current head SHA>' once "
        "drafting-a-pr-to-merge's Step 8 review completes clean against this exact commit.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

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

    ## Independent review verdict

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
thereby a real clean pass." Two independent live-adversarial rounds against
this gate (issue #1311's own checker-script-adversarial-review and
defeat-test-disclosure rounds) confirmed several concrete instances of
that exact risk -- a verdict quoted as illustrative example text, never
intended as a real disclosure, still parsing as a genuine passing one --
each closed here:

- A fenced (``` / ~~~) code block, matching- or longer-length closing
  fence alike (CommonMark's own rule, not an exact-length match), is
  stripped before any heading/field search (`_strip_fenced_code_blocks`,
  a linear single pass -- an earlier backreference-based regex both missed
  the longer-closing-fence case AND cost tens of seconds against a
  few hundred lines of non-matching fence-like content, a real
  availability risk against a required check, not just a correctness gap).
- An HTML comment (`<!-- ... -->`, GitHub renders it as nothing at all --
  arguably the more dangerous case, since a human skimming the rendered
  PR body sees no suspicious text at all) is stripped the same way
  (`_strip_html_comments`).
- A 4-or-more-space-indented block (CommonMark's own indented-code-block
  rule) never counts as a live heading: the heading regex only accepts
  0-3 leading spaces, matching CommonMark's own ATX-heading indentation
  limit exactly, rather than the unlimited indentation an earlier draft
  accepted.
- CRLF/CR line endings are normalized to LF before any of the above, so a
  Windows-originated PR body does not make every line-anchored regex
  below silently fail to match a genuine verdict (the inverse defeat
  direction: a false FAIL against real disclosure, not a false PASS).

What remains open, and is not closable by any text-shape check: a PR
author (or a diff whose own prose) writing the exact required heading and
fields verbatim, unindented and unfenced, as if it were a real disclosure,
without Step 8 having actually run -- distinguishing that from a genuine
disclosure needs a signal this gate does not have access to, and
defending against a PR author who deliberately forges the marker this way
is a distinct, harder threat this repository's own single-operator trust
model does not currently need (see issue #1311's own residual risk).

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

# Issue #1343: the single source of truth for the recorded-verdict heading
# text. Every runtime-facing use of it in this file (below) and every
# external consumer (gitapex_scan_independent_review_heading_drift.py) reads
# this constant or calls heading_pattern() on it, rather than re-declaring
# the literal -- the drift that gate exists to catch (issue #1311's own
# "Step 8" numbering once baked directly into this heading, duplicated by
# hand across five files with nothing keeping them in sync, later found by
# a deterministic-gate-quality review to still have unbound runtime copies
# even after the rename -- see this issue's own follow-up commit) cannot
# recur for this file's own copies if there are no second copies left to
# drift from it.
CANONICAL_HEADING_TEXT = "Independent review verdict"


def heading_pattern(text: str) -> re.Pattern[str]:
    """Build the same ATX-heading-matching pattern this gate's own
    detection logic uses, for arbitrary heading text -- CommonMark's 0-3-
    space indentation limit, 1-6 `#` characters, a required space before
    the text, end-anchored (so trailing prose after the heading text does
    not still count as a match), case-insensitive. A public function
    (not a private, underscore-prefixed one) specifically so an external
    consumer needing to answer "is this exact heading text live in this
    file" -- gitapex_scan_independent_review_heading_drift.py, for both
    the canonical text and each retired one -- calls this rather than
    re-deriving its own, independently-drifting copy of the same regex
    shape. A deterministic-gate-quality review found exactly that
    divergence in an earlier revision: the drift gate's own plain
    substring search accepted heading text `_HEADING_RE` itself would
    reject (e.g. trailing prose, or missing the `$`-anchor's own
    protection), and was also case-sensitive where this gate's own
    matching is not -- both defeat classes this shared function closes by
    construction, not by keeping two hand-synchronized copies of the same
    rule."""
    return re.compile(r"^[ ]{0,3}#{1,6}[ \t]+" + re.escape(text) + r"[ \t]*$", re.IGNORECASE | re.MULTILINE)


_HEADING_RE = heading_pattern(CANONICAL_HEADING_TEXT)
_NEXT_HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]+", re.MULTILINE)

_FENCE_OPEN_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def _strip_fenced_code_blocks(text: str) -> str:
    """Blank out every fenced code block (``` or ~~~, CommonMark's two
    fence characters) -- rendered as literal/quoted text, never a live
    Markdown heading or list, the same "quoted content is not live prose"
    principle `gitapex_gate_provenance_disclosure.py`'s own
    `_quoted_example_spans` applies to inline spans, extended here to the
    block form a live defeat attempt actually used (see the module
    docstring).

    Line-by-line, single forward pass -- O(n) in the number of lines, never
    re-scanning from an earlier position. A closing fence only needs the
    same character repeated *at least* as many times as the opening one
    (CommonMark's own rule) -- not an exact-length match, which a live
    adversarial round found let a longer closing fence defeat an earlier
    backreference-based regex version of this function. That earlier
    version's own nested lazy quantifier, re-tried from every candidate
    open when no matching close existed, was also confirmed live to cost
    roughly cubic time in body size (tens of seconds against a few hundred
    lines of non-matching fence-like content) -- a real availability risk
    against a required CI check, not merely a style concern. This version
    has no such quantifier: each line is visited a bounded number of times
    regardless of how many unmatched candidate opens precede it."""
    lines = text.split("\n")
    total = len(lines)
    index = 0
    while index < total:
        open_match = _FENCE_OPEN_RE.match(lines[index])
        if open_match is None:
            index += 1
            continue
        fence_char = open_match.group(1)[0]
        fence_len = len(open_match.group(1))
        close_re = re.compile(rf"^[ \t]*{re.escape(fence_char)}{{{fence_len},}}[ \t]*$")
        close_index = index + 1
        while close_index < total and close_re.match(lines[close_index]) is None:
            close_index += 1
        # An unclosed fence extends to the end of the document (CommonMark).
        block_end = close_index if close_index < total else total - 1
        for line_index in range(index, block_end + 1):
            lines[line_index] = ""
        index = block_end + 1
    return "\n".join(lines)


def _strip_html_comments(text: str) -> str:
    """Blank out every HTML comment (`<!-- ... -->`, possibly spanning
    multiple lines) -- GitHub renders these as nothing at all, so a verdict
    hidden inside one is invisible to a human reviewer skimming the
    rendered PR body while still being live text to a naive parser (a live
    adversarial round found exactly this, arguably worse than the fenced-
    block case since there is no visible "example" text to question at
    all).

    Plain `str.find`, not a regex with a lazy `.*?` quantifier, to
    guarantee linear time regardless of how many unclosed or malformed
    `<!--` sequences the input contains -- the same ReDoS class
    `_strip_fenced_code_blocks`'s own docstring names, avoided here by
    construction rather than by re-deriving the same fix twice."""
    pieces: list[str] = []
    position = 0
    length = len(text)
    while True:
        start = text.find("<!--", position)
        if start == -1:
            pieces.append(text[position:])
            break
        pieces.append(text[position:start])
        end = text.find("-->", start + 4)
        span_end = end + 3 if end != -1 else length
        pieces.append("\n" * text.count("\n", start, span_end))
        if end == -1:
            break
        position = span_end
    return "".join(pieces)


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
_MIN_SHA_COMPARE_LEN = 7


class Verdict:
    """The parsed contents of the last `## Independent review verdict`
    section in a PR body, or the specific reason none usable was
    found."""

    def __init__(self, status: str | None, commit: str | None, error: str | None) -> None:
        self.status = status
        self.commit = commit
        self.error = error


def _last_section_from(text: str, start: int) -> str:
    """Return the text from `start` up to (not including) the next `##`
    heading of any name, or the end of `text` if none follows -- so a
    field belonging to a different, later section is never read as part
    of this one. Uses the same CommonMark 0-3-space ATX-indentation limit
    as `_HEADING_RE` (`_NEXT_HEADING_RE`) -- a 4-or-more-space-indented
    "## heading"-shaped line is inert code, not a real section boundary,
    the same reasoning `_HEADING_RE`'s own docstring gives."""
    next_heading = _NEXT_HEADING_RE.search(text[start:])
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def parse_verdict(body: str) -> Verdict:
    """Parse the last `## Independent review verdict` section out
    of `body`. Returns a `Verdict` carrying either both fields, or an
    `error` describing exactly what is missing/malformed.

    CRLF/CR line endings are normalized to LF first -- every regex below is
    line-anchored (`$`/`^` under `re.MULTILINE`), and a stray `\\r` sitting
    between real content and `\\n` breaks every one of them, turning a
    genuine verdict into a false FAIL (a live-confirmed correctness gap,
    the safe direction but still wrong). HTML comments, then fenced code
    blocks, are stripped next (see `_strip_html_comments` and
    `_strip_fenced_code_blocks`): a verdict quoted inside either -- e.g. as
    illustrative example text, or hidden where GitHub renders nothing at
    all -- is not live disclosure and must not parse as a real verdict."""
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = _strip_html_comments(body)
    body = _strip_fenced_code_blocks(body)
    headings = list(_HEADING_RE.finditer(body))
    if not headings:
        return Verdict(None, None, f"no '## {CANONICAL_HEADING_TEXT}' section found")

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
    always supplies -- never the reverse. The compared prefix must be at
    least `_MIN_SHA_COMPARE_LEN` characters (matching `_COMMIT_RE`'s own
    `{7,40}` bound): an empty `--head-sha` was already rejected, but a
    defensive-in-depth review found nothing stopped a single-character
    `--head-sha` from vacuously matching any recorded commit sharing that
    one character -- not reachable through the actual wired trigger today
    (GitHub Actions always supplies the full 40-character SHA), but this
    floor removes the latent risk from a future caller or refactor rather
    than relying on that alone."""
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
    if compare_len < _MIN_SHA_COMPARE_LEN or recorded[:compare_len] != current[:compare_len]:
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
    except IsADirectoryError:
        print(f"error: --body is a directory, not a file: {args.body}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        print(f"error: PR body is not valid UTF-8: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        # Catch-all for the rest of the OSError family (PermissionError, a
        # disk-full or restrictive-ACL mount, and any other I/O error a CI
        # runner can plausibly raise) -- a deterministic-gate-quality review
        # found the three specific catches above still let this class
        # surface as an uncaught traceback rather than the same clean,
        # deliberate error path already established for IsADirectoryError.
        # Still fail-closed either way (non-zero exit), but this makes the
        # failure a reported finding instead of a crash.
        print(f"error: could not read --body: {error}", file=sys.stderr)
        return 1

    passed, message = check(body, args.head_sha)
    if passed:
        print(f"PASS: {message}")
        return 0

    print(f"FAIL: {message}", file=sys.stderr)
    print(
        f"Record a '## {CANONICAL_HEADING_TEXT}' section in the PR body with "
        "'- Verdict: CLEAN' and '- Verified commit: <current head SHA>' once "
        "drafting-a-pr-to-merge's Step 8 review completes clean against this exact commit.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

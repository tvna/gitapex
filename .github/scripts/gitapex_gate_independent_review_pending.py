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
  stripped before any heading/field search (`strip_fenced_code_blocks`,
  a linear single pass -- an earlier backreference-based regex both missed
  the longer-closing-fence case AND cost tens of seconds against a
  few hundred lines of non-matching fence-like content, a real
  availability risk against a required check, not just a correctness gap).
- An HTML comment (`<!-- ... -->`, GitHub renders it as nothing at all --
  arguably the more dangerous case, since a human skimming the rendered
  PR body sees no suspicious text at all) is stripped the same way
  (`strip_html_comments`).
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

The `parse_verdict`/`check()` human-verdict path above is unmodified by
issue #1858 (below) -- every paragraph above still describes exactly what
it always described. Only a new branch, tried BEFORE that path and only
ever falling through to it (never around it), was added.

Trusted-bot exemption (issue #1858, design:
docs/gitapex/specs/2026-09-06-dependabot-trusted-bot-gate-exemption-design.md).
Dependabot's own PRs never carry a `## Independent review verdict` section
-- nobody runs `drafting-a-pr-to-merge` against them -- so the human-verdict
path above fails permanently for every Dependabot PR. `main()` now also
accepts the PR author's identity (`--pr-author-login`/`--pr-author-id`/
`--pr-author-type`) and, when given, tries `evaluate_bot_path` first:

1. `is_trusted_bot`: the PR author's (login, id, type) must match ALL
   THREE fields of one `.github/trusted-bots.yml` entry -- login alone is
   never sufficient (a same-named non-bot account is a distinct GitHub
   user id).
2. A bot-identity match on the PR's opener is not itself sufficient:
   `dependabot/*` branches carry no branch protection of their own, so
   anyone with push access could append a human commit to an open
   Dependabot PR after the fact, and the PR's `user` field stays
   `dependabot[bot]` regardless (GitHub never changes it on
   `synchronize`). `head_commit_identity_matches_bot` additionally
   requires the head commit's OWN author and committer email (not the
   PR-level identity) to match `.github/rulesets/main.json`'s existing
   `commit_author_email_pattern`/`committer_email_pattern` rules (PR
   #1843) -- the single source of truth for this repository's
   trusted-committer emails, not a second copy in `trusted-bots.yml`
   that could drift from it. A mismatch here falls through to the
   human-verdict path above, never straight to FAIL: a legitimate human
   fix pushed to a bot-opened PR should still be reviewable the normal
   way.
3. Both `.github/trusted-bots.yml` and `.github/rulesets/main.json` are
   fetched via the GitHub Contents API (`fetch_repo_file_at_ref`) at the
   PR's own base commit (`--trust-anchor-ref`, the workflow passes
   `github.event.pull_request.base.sha`), never read from this job's own
   working tree -- which for a `pull_request`-triggered workflow is the
   PR's own proposed content, and could otherwise let a PR widen its own
   bot-exemption eligibility by editing either file within its own diff.
   That ref is trusted only when `--trust-anchor-base-ref`
   (`github.event.pull_request.base.ref`) equals `--repo-default-branch`
   (`github.event.repository.default_branch`, not PR-influenceable) -- a
   PR retargeted to a different, possibly unprotected base branch cannot
   supply forged trust-anchor content instead. An empty or unresolved
   value for any of these three flags refuses the bot path the same way
   every other bot-path failure does, rather than silently falling back
   to the local-disk read below (that fallback is reserved for
   `--trust-anchor-ref` being omitted entirely). Both files also carry a
   CODEOWNERS entry as defense in depth on top of this, not a substitute
   for it (a live GitHub Settings toggle this repository's own tracked
   files cannot themselves confirm is enabled).
4. Only once all the above match: `required_check_contexts` reads the
   required status-check context list straight out of `main.json`'s own
   `required_status_checks` rule (mirroring, not importing,
   `gitapex_gate_ruleset_required_checks.py`'s own `rule_of_type()`
   pattern), drops this check's own name, and `poll_bot_required_checks`
   polls GitHub's Checks API for the head SHA until every remaining
   context is `completed` -- PASS iff all conclude `success`/`neutral`/
   `skipped`, FAIL immediately on any other conclusion, FAIL on timeout
   naming whichever contexts never completed. A transient GitHub API
   error while polling is retried within the same timeout budget, not
   treated as an immediate FAIL or silently ignored. Every context's own
   conclusion is re-derived from the latest full check-runs snapshot on
   every poll iteration, never cached once seen passing -- a context
   re-run mid-poll into a worse conclusion is still caught.

No change to `parse_verdict`/`check()` themselves, and every existing
`--body`/`--head-sha`-only invocation (no `--pr-author-*` given at all)
behaves exactly as before -- this is an additive branch ahead of the
existing path, not a replacement of it.

Issue #1858 gives this file a real third-party dependency for the first
time: it now also imports `yaml` (already a dependency of
`.github/scripts/gitapex_gate_ruleset_required_checks.py`, used the same
way here -- parsing `.github/trusted-bots.yml`) and `_gitapex_github_http`
(issue #729's shared GitHub REST retry/pagination client -- explicitly
exempted from this repository's own `.github/scripts/*.py`
no-cross-file-imports convention by that module's own docstring;
`gitapex_gate_retro_title_convention_citation.py` already sets this
precedent). Still self-contained in the sense that matters: no other
`.github/scripts/gitapex_*.py` gate/report file is imported. Run via
`uv run` accordingly (needed for the `yaml` import -- a bare `python3`
invocation without it installed fails at import time, before argparse
even runs), matching every Usage example below.

Usage (existing, human-verdict path -- unchanged)::

    uv run --frozen python3 .github/scripts/gitapex_gate_independent_review_pending.py \\
        --body PR_BODY.txt --head-sha <sha>
    printf '%s' "$PR_BODY" | uv run --frozen python3 .github/scripts/gitapex_gate_independent_review_pending.py --head-sha <sha>

A bare pipe here masks `printf`'s own exit status in a non-`pipefail` shell
(issue #1531) -- harmless for a literal `printf` producer, which cannot
itself fail in ordinary use, but add `set -o pipefail` first if this
recipe's producer is ever swapped for a command that can.

Usage (trusted-bot exemption path; falls through to the above whenever the
identity/email checks above do not both hold)::

    GITHUB_TOKEN=... uv run --frozen python3 .github/scripts/gitapex_gate_independent_review_pending.py \\
        --body PR_BODY.txt --head-sha <sha> \\
        --pr-author-login "dependabot[bot]" --pr-author-id 49699333 --pr-author-type Bot \\
        --owner tvna --repo gitapex --trust-anchor-ref <base branch sha> \\
        --trust-anchor-base-ref main --repo-default-branch main

Exit codes:
    0  A Verdict: CLEAN verdict naming the given head SHA is present
       (human-verdict path), OR the PR author is a trusted bot whose head
       commit's own author/committer email matches `main.json`'s
       email-pattern rules AND every other required check has completed
       successfully for that head SHA (bot-exemption path).
    1  Neither of the above holds, or an unreadable/malformed input.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from _gitapex_github_http import GitHubApiError, default_opener, fetch_json_document

# Issue #1343: the single source of truth for the recorded-verdict heading
# text. Every runtime-facing use of it in this file (below) reads this
# constant rather than re-declaring the literal -- the drift that gate
# exists to catch (issue #1311's own "Step 8" numbering once baked
# directly into this heading, duplicated by hand across five files with
# nothing keeping them in sync, later found by a deterministic-gate-
# quality review to still have unbound runtime copies even after the
# rename -- see this issue's own follow-up commit) cannot recur for this
# file's own copies if there are no second copies left to drift from it.
# gitapex_scan_independent_review_heading_drift.py -- the drift gate that
# closed that gap -- reads this constant too, but does its own text-
# presence matching rather than reusing `_HEADING_RE` below: a reuse/
# simplification review found an earlier revision made `_HEADING_RE`'s
# own pattern-building logic a public `heading_pattern()` function
# specifically for that gate to call, but the call never actually
# happened (none of the drift gate's own targets carry this text as a
# live heading, only as quoted prose/JSON/YAML -- see that gate's own
# module docstring) -- a public function built for one caller that
# never materializes is unjustified surface area, reverted here.
CANONICAL_HEADING_TEXT = "Independent review verdict"

# CommonMark's own ATX-heading rule: the opening `#` may be indented at
# most 3 spaces; 4 or more makes the line an indented code block instead,
# never a live heading. A live adversarial round found that an earlier
# `[ \t]*` (unlimited indentation, tabs included) let a 4-space-indented
# "illustrative example" heading parse as a real, live one -- restricting
# to `[ ]{0,3}` (spaces only) closes that class the same way GitHub's own
# renderer already treats it as inert.
_HEADING_RE = re.compile(
    r"^[ ]{0,3}#{1,6}[ \t]+" + re.escape(CANONICAL_HEADING_TEXT) + r"[ \t]*$", re.IGNORECASE | re.MULTILINE
)
_NEXT_HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]+", re.MULTILINE)

_FENCE_OPEN_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def strip_fenced_code_blocks(text: str) -> str:
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
    regardless of how many unmatched candidate opens precede it.

    Public (issue #1343): `gitapex_scan_independent_review_heading_drift.py`
    needs this exact "is this text live, not fenced-off as an example"
    definition for its own Markdown targets, and reaching into another
    script's underscore-prefixed function is not a pattern used anywhere
    else in this repository's own cross-script imports."""
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


def strip_html_comments(text: str) -> str:
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
    `strip_fenced_code_blocks`'s own docstring names, avoided here by
    construction rather than by re-deriving the same fix twice.

    Public for the same reason `strip_fenced_code_blocks` is (see its own
    docstring) -- issue #1343's drift gate reuses this one too."""
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
    blocks, are stripped next (see `strip_html_comments` and
    `strip_fenced_code_blocks`): a verdict quoted inside either -- e.g. as
    illustrative example text, or hidden where GitHub renders nothing at
    all -- is not live disclosure and must not parse as a real verdict."""
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = strip_html_comments(body)
    body = strip_fenced_code_blocks(body)
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


# ---------------------------------------------------------------------------
# Trusted-bot exemption (issue #1858). Everything below is new; nothing
# above this point (parse_verdict/check and their own helpers) is touched.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRUSTED_BOTS_PATH = _REPO_ROOT / ".github" / "trusted-bots.yml"
DEFAULT_RULESET_PATH = _REPO_ROOT / ".github" / "rulesets" / "main.json"

#: This check's own required-status-check context name -- excluded from
#: `required_check_contexts`'s own return value so the bot path never
#: waits on itself.
_SELF_CHECK_CONTEXT = "independent-review-pending"

_API_ROOT = "https://api.github.com"

#: Design doc "Timing" section: "poll interval (e.g. every 15-30s)" and a
#: "~15 min" extended job timeout (Decision logic detail's own "Poll
#: outcome" section, matching this issue's own ACM).
DEFAULT_POLL_TIMEOUT_SECONDS = 900.0
DEFAULT_POLL_INTERVAL_SECONDS = 20.0

#: Design doc's own "Poll outcome" bullet: a `skipped` conclusion does not
#: block a required status check on GitHub's own native merge logic --
#: matching `gitapex_gate_ruleset_required_checks.py`'s own documented
#: principle (that module's own module docstring) -- so this poll outcome
#: must not be stricter than GitHub's own blocking behavior for the same
#: required-check list.
_PASSING_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})


def _github_repository_part(index: int) -> str | None:
    """Read the owner (index 0) or repo (index 1) half of the standard
    GitHub Actions `$GITHUB_REPOSITORY` env var ("owner/repo"), or `None`
    if unset/malformed. Lets a caller (Task C's workflow) omit
    `--owner`/`--repo` entirely -- every GitHub Actions job already has
    this env var set -- while an explicit `--owner`/`--repo` still
    overrides it (argparse `default=` is only consulted when the flag is
    omitted)."""
    parts = os.environ.get("GITHUB_REPOSITORY", "").split("/", 1)
    return parts[index] if len(parts) == 2 and parts[index] else None


def _read_utf8_or_raise(path: Path) -> str:
    """Read `path` as UTF-8 text, converting an unreadable file or invalid
    UTF-8 content into `ValueError` at this read boundary -- matching
    `gitapex_detect_changed_gate_scripts.py`'s own `registered_gate_paths`
    pattern rather than leaving the read boundary unguarded. Shared by
    `load_trusted_bots`/`load_ruleset` below: both need the identical
    read-or-raise step before parsing their own, different format (YAML vs
    JSON)."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"{path} could not be read: {error}") from error
    except UnicodeDecodeError as error:
        raise ValueError(f"{path} is not valid UTF-8: {error}") from error


def _parse_trusted_bots(text: str, source: str) -> list[dict[str, Any]]:
    """Parse `text` (the raw content of `.github/trusted-bots.yml`, read
    from either local disk or `fetch_repo_file_at_ref`) into a list of
    entry dicts. Raises `ValueError`/`yaml.YAMLError` on malformed
    content, `source` naming where it came from for the error message
    only -- shared by `load_trusted_bots` (local disk) and `main()`'s own
    `--trust-anchor-ref` branch (the GitHub Contents API) so both paths
    parse identically."""
    document = yaml.safe_load(text)
    if not isinstance(document, list):
        raise ValueError(f"{source} must contain a YAML list of entries, found {type(document).__name__}")
    return [entry for entry in document if isinstance(entry, dict)]


def load_trusted_bots(path: Path) -> list[dict[str, Any]]:
    """Parse `.github/trusted-bots.yml` off local disk into a list of
    entry dicts.

    Raises `ValueError` (an unreadable or non-UTF-8 file, see
    `_read_utf8_or_raise`) or `yaml.YAMLError` (malformed YAML) on a bad
    file -- `main()`'s own bot-path wiring treats any of these as "cannot
    confirm a bot-path candidate" and falls through to the strict
    human-verdict path, never crashing and never silently trusting
    everything or nothing.

    Reads whatever this job's own working tree currently has checked
    out -- for a `pull_request`-triggered workflow, that is the PR's own
    proposed content, not a ref the PR itself cannot influence. `main()`
    only calls this when `--trust-anchor-ref` is omitted (every unit test,
    and any caller without a GitHub API token available); the real
    workflow always passes `--trust-anchor-ref` instead, routing through
    `fetch_repo_file_at_ref`/`_parse_trusted_bots` so a PR cannot widen its
    own bot-exemption eligibility merely by editing this file within its
    own diff -- see that flag's own `main()` help text and the design
    doc's own Decision logic detail section."""
    text = _read_utf8_or_raise(path)
    return _parse_trusted_bots(text, str(path))


def is_trusted_bot(login: str, user_id: int, user_type: str, entries: list[dict[str, Any]]) -> bool:
    """Return True iff `(login, user_id, user_type)` matches ALL THREE
    fields of at least one `.github/trusted-bots.yml` entry.

    Design doc's own Decision logic detail: "Login alone is not
    sufficient -- GitHub's own user id is immutable and namespace-unique,
    closing the theoretical risk of a same-named non-bot account." A
    forged entry whose `login` matches but whose `id`/`type` does not is
    therefore a non-match, by construction (`and`, not `or`)."""
    return any(
        entry.get("login") == login and entry.get("id") == user_id and entry.get("type") == user_type
        for entry in entries
    )


def _parse_ruleset(text: str, source: str) -> dict[str, Any]:
    """Parse `text` (the raw content of `.github/rulesets/main.json`, read
    from either local disk or `fetch_repo_file_at_ref`) into a dict.
    Raises `ValueError`/`json.JSONDecodeError` on malformed content,
    `source` naming where it came from for the error message only --
    shared by `load_ruleset` (local disk) and `main()`'s own
    `--trust-anchor-ref` branch (the GitHub Contents API)."""
    document = json.loads(text)
    if not isinstance(document, dict):
        raise ValueError(f"{source} must contain a JSON object, found {type(document).__name__}")
    return document


def load_ruleset(path: Path) -> dict[str, Any]:
    """Parse `.github/rulesets/main.json` off local disk. Raises
    `ValueError` (an unreadable or non-UTF-8 file, see
    `_read_utf8_or_raise`) or `json.JSONDecodeError` (malformed JSON) on a
    bad file -- same fall-through contract as `load_trusted_bots`, and the
    same "PR's own working tree, not a ref it cannot influence" caveat:
    `main()` only calls this when `--trust-anchor-ref` is omitted; see
    `load_trusted_bots`'s own docstring."""
    text = _read_utf8_or_raise(path)
    return _parse_ruleset(text, str(path))


def fetch_repo_file_at_ref(
    owner: str,
    repo: str,
    path: str,
    ref: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """GET the UTF-8 text content of `path` at `ref` via GitHub's Contents
    API (`GET /repos/{owner}/{repo}/contents/{path}?ref={ref}`).

    This exists so the two bot-path trust anchors
    (`.github/trusted-bots.yml`, `.github/rulesets/main.json`) can be read
    from a ref the PR under evaluation cannot itself move -- `main()`'s own
    `--trust-anchor-ref` wiring always passes the PR's base commit SHA
    (`github.event.pull_request.base.sha`), never the PR's own head, so a
    PR cannot widen its own bot-exemption eligibility merely by editing
    either file within its own diff (the CODEOWNERS review gate on both
    paths is defense in depth on top of this, not a substitute for it --
    see the design doc's own Decision logic detail section).

    Raises `GitHubApiError` (via `fetch_json_document`, which already
    retries transient 5xx/network failures) on any HTTP failure or
    unexpected/non-base64 response shape -- the caller (`main()`) catches
    this and falls through to the human-verdict path, the same
    fail-closed contract every other bot-path GitHub API call in this file
    already has."""
    url = f"{_API_ROOT}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    document = fetch_json_document(url, token, opener, sleeper)
    if not isinstance(document, dict):
        raise GitHubApiError(f"GET {url} returned an unexpected shape: {type(document).__name__}")
    encoded = document.get("content")
    encoding = document.get("encoding")
    if not isinstance(encoded, str) or encoding != "base64":
        raise GitHubApiError(f"GET {url} response has no base64-encoded 'content' field")
    try:
        return base64.b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise GitHubApiError(f"GET {url} content could not be base64/UTF-8 decoded: {error}") from error


def _rule_of_type(ruleset: dict[str, Any], rule_type: str) -> dict[str, Any] | None:
    """The single rule of `rule_type` in `ruleset["rules"]`, or `None`.

    Mirrors `gitapex_gate_ruleset_required_checks.py`'s own `rule_of_type()`
    pattern -- not imported, per this repository's own `.github/scripts/*.py`
    convention of not importing across gate/report files (`_gitapex_github_http`
    is the one shared exception, per that module's own docstring, used
    elsewhere in this file instead)."""
    for rule in ruleset.get("rules") or []:
        if isinstance(rule, dict) and rule.get("type") == rule_type:
            return rule
    return None


def required_check_contexts(ruleset: dict[str, Any]) -> list[str]:
    """The required-status-check context names from `ruleset`'s own
    `required_status_checks` rule, minus `_SELF_CHECK_CONTEXT`.

    Type-discriminated by construction (`_rule_of_type` matches on
    `type == "required_status_checks"` specifically): a `main.json`
    fixture also carrying `deletion`/`pull_request`/
    `commit_author_email_pattern`/`committer_email_pattern` rules never has
    any of those read as check contexts, since only the one rule whose own
    `type` is `"required_status_checks"` is ever inspected here.

    Returns an empty list if that rule is absent or malformed (including a
    rule present but carrying no `required_status_checks` entries at all).
    This is deliberately indistinguishable from "the rule is present but
    genuinely names zero other contexts" -- `poll_bot_required_checks`
    below treats an empty list as a fail-closed condition either way,
    mirroring `gitapex_gate_ruleset_required_checks.py`'s own
    `find_unreachable_contexts`: "a pull request rule with nothing to
    check blocks nothing" is itself a finding there, never a silent pass,
    and this design's own residual-risk section names the same
    fail-closed default for this gate."""
    rule = _rule_of_type(ruleset, "required_status_checks")
    if rule is None:
        return []
    parameters = rule.get("parameters")
    if not isinstance(parameters, dict):
        return []
    entries = parameters.get("required_status_checks")
    if not isinstance(entries, list):
        return []
    contexts = [
        entry["context"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("context"), str)
    ]
    return [context for context in contexts if context != _SELF_CHECK_CONTEXT]


def _email_matches_pattern(email: str, operator: Any, pattern: Any) -> bool:
    """Whether `email` matches `pattern` under `operator`, GitHub's own
    four `commit_author_email_pattern`/`committer_email_pattern` operators
    (`EmailPatternParameters` in `gitapex_gate_ruleset_required_checks.py`).
    An unrecognized/missing operator or a non-string/empty pattern is
    fail-closed to "no match", never treated as vacuously true -- this
    function has no caller that should ever proceed on an ambiguous
    schema."""
    if not isinstance(pattern, str) or not pattern:
        return False
    if operator == "starts_with":
        return email.startswith(pattern)
    if operator == "ends_with":
        return email.endswith(pattern)
    if operator == "contains":
        return pattern in email
    if operator == "regex":
        try:
            return re.search(pattern, email) is not None
        except re.error:  # except-fail-open: WAIVED: a malformed regex here is a main.json config bug scoped only to the bot-exemption path (this function is reached only from a bot-identity-matched candidate) -- returning False safely falls through to the strict, pre-existing human-verdict path (evaluate_bot_path), never a silent pass; re-raising would crash this required check for every PR, bot or not, over a config bug in a file this diff does not own.
            return False
    return False


def _email_satisfies_rule(email: str, rule: dict[str, Any] | None) -> bool:
    """Whether `email` is ALLOWED by `rule` (a `commit_author_email_pattern`/
    `committer_email_pattern` rule dict), honoring `negate` the same way
    GitHub's own schema documents it (`EmailPatternParameters`'s own
    docstring, quoted there): "If true, the rule will fail if the pattern
    matches" -- so with `negate` true, `email` is allowed only when the
    pattern does NOT match; with `negate` false/absent (this repository's
    actual `main.json` today), `email` is allowed only when it DOES
    match. `rule is None` (the rule type is missing from `main.json`
    entirely) is always a non-match -- fail-closed, never vacuously
    true."""
    if rule is None:
        return False
    parameters = rule.get("parameters")
    if not isinstance(parameters, dict):
        return False
    matched = _email_matches_pattern(email, parameters.get("operator"), parameters.get("pattern"))
    return (not matched) if parameters.get("negate") else matched


def head_commit_identity_matches_bot(
    author_email: str, committer_email: str, ruleset: dict[str, Any]
) -> tuple[bool, str]:
    """The critical-defect fix this issue's own design-doc Revision
    section exists for: a PR-opener identity match is never, by itself,
    sufficient to take the bot path. This additionally requires the head
    commit's OWN author and committer email (not the PR's `user` field,
    which GitHub never updates on a later `synchronize`) to BOTH match
    `ruleset`'s own `commit_author_email_pattern`/`committer_email_pattern`
    rules (`.github/rulesets/main.json`, PR #1843) -- the single source of
    truth for this repository's trusted-committer emails, not a second,
    separately-maintained copy in `trusted-bots.yml`.

    Returns `(False, reason)` -- never raises, never a hard FAIL -- on any
    mismatch, missing rule, or malformed ruleset: the caller
    (`evaluate_bot_path`) falls through to the existing human-verdict path
    in every one of these cases, exactly matching the design doc's own
    "fall through, never a silent pass and never an outright hard FAIL
    either" resolution -- a legitimate human fix pushed to a bot-opened PR
    should still be reviewable the normal way, not permanently blocked by
    a bot-only code path that no longer applies to it."""
    author_rule = _rule_of_type(ruleset, "commit_author_email_pattern")
    committer_rule = _rule_of_type(ruleset, "committer_email_pattern")
    if author_rule is None or committer_rule is None:
        return False, (
            "main.json is missing a commit_author_email_pattern and/or committer_email_pattern rule; "
            "cannot verify head-commit identity"
        )
    if not _email_satisfies_rule(author_email, author_rule):
        return (
            False,
            f"head commit author email {author_email!r} does not match main.json's commit_author_email_pattern rule",
        )
    if not _email_satisfies_rule(committer_email, committer_rule):
        return (
            False,
            f"head commit committer email {committer_email!r} does not match main.json's committer_email_pattern rule",
        )
    return True, "head commit author and committer email both match main.json's email-pattern rules"


def fetch_head_commit_emails(
    owner: str,
    repo: str,
    head_sha: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[str, str]:
    """GET `/repos/{owner}/{repo}/commits/{head_sha}` and return
    `(author_email, committer_email)` from the commit object's OWN
    `commit.author.email`/`commit.committer.email` fields -- deliberately
    NOT the GitHub *user* account fields (`author.email`/`committer.email`
    at the top level, which describe the linked GitHub account, not the
    raw commit metadata). That distinction is exactly what
    `head_commit_identity_matches_bot` needs: an account claiming to be
    `dependabot[bot]` is a different fact from what emails this specific
    commit was actually authored/committed with.

    Raises `GitHubApiError` (via `_gitapex_github_http.fetch_json_document`,
    which already retries transient 5xx/network failures) on any HTTP
    failure or unexpected response shape -- the caller
    (`evaluate_bot_path`) catches this and falls through to the
    human-verdict path rather than propagating."""
    url = f"{_API_ROOT}/repos/{owner}/{repo}/commits/{head_sha}"
    document = fetch_json_document(url, token, opener, sleeper)
    if not isinstance(document, dict):
        raise GitHubApiError(f"GET {url} returned an unexpected shape: {type(document).__name__}")
    commit = document.get("commit")
    if not isinstance(commit, dict):
        raise GitHubApiError(f"GET {url} response has no 'commit' object")
    raw_author = commit.get("author")
    raw_committer = commit.get("committer")
    author: dict[str, Any] = raw_author if isinstance(raw_author, dict) else {}
    committer: dict[str, Any] = raw_committer if isinstance(raw_committer, dict) else {}
    author_email = author.get("email")
    committer_email = committer.get("email")
    if not isinstance(author_email, str) or not isinstance(committer_email, str):
        raise GitHubApiError(f"GET {url} response is missing commit.author.email/commit.committer.email")
    return author_email, committer_email


def _fetch_check_runs(
    owner: str,
    repo: str,
    head_sha: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
) -> list[dict[str, Any]]:
    """Every check-run GitHub reports for `head_sha`, paging through
    `total_count` if more than one page's worth exist (defensive: this
    repository's own required-check list is well under one page today,
    but a response that silently dropped later pages would be a real
    correctness gap, not merely untidy)."""
    runs: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{_API_ROOT}/repos/{owner}/{repo}/commits/{head_sha}/check-runs?per_page=100&page={page}"
        document = fetch_json_document(url, token, opener, sleeper)
        if not isinstance(document, dict):
            raise GitHubApiError(f"GET {url} returned an unexpected shape: {type(document).__name__}")
        page_runs = document.get("check_runs")
        if not isinstance(page_runs, list):
            raise GitHubApiError(f"GET {url} response has no 'check_runs' array")
        runs.extend(run for run in page_runs if isinstance(run, dict))
        total_count = document.get("total_count")
        if not isinstance(total_count, int) or len(runs) >= total_count or not page_runs:
            break
        page += 1
    return runs


def _latest_run_for_context(runs: list[dict[str, Any]], context: str) -> dict[str, Any] | None:
    """The most-recent (by `started_at`, falling back to `id`) check run
    named `context`, or `None` if none exists yet. Design doc's own
    residual risks section: "most-recent-by-timestamp is the natural
    default, matching how GitHub's own required-status-check evaluation
    already behaves" for a re-run producing more than one run under the
    same context name."""
    matches = [run for run in runs if run.get("name") == context]
    if not matches:
        return None

    def _sort_key(  # function-body-test-coverage: WAIVED: a private closure nested inside _latest_run_for_context, with no name accessible from outside this function to reference directly; its ordering is exercised through _latest_run_for_context's own most-recent-by-started_at test instead.
        run: dict[str, Any],
    ) -> tuple[str, int]:
        started_at = run.get("started_at")
        run_id = run.get("id")
        return (started_at if isinstance(started_at, str) else "", run_id if isinstance(run_id, int) else 0)

    return max(matches, key=_sort_key)


def poll_bot_required_checks(
    *,
    owner: str,
    repo: str,
    head_sha: str,
    contexts: list[str],
    token: str,
    timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[bool, str]:
    """Poll GitHub's Checks API for `head_sha` until every context in
    `contexts` is `completed`, per the design doc's own "Poll outcome"
    section:

    - all `completed` with conclusion in `_PASSING_CONCLUSIONS` -> PASS.
    - any `completed` with any other conclusion -> FAIL immediately,
      naming that context and its actual conclusion (no more polling).
    - `timeout_seconds` elapses with contexts still not `completed` ->
      FAIL, naming which contexts never completed.
    - a transient `GitHubApiError` while polling is retried within the
      same `timeout_seconds` budget (via `sleeper`/another loop
      iteration), never treated as an immediate FAIL nor silently
      ignored; if errors persist until `timeout_seconds`, the FAIL
      message says so explicitly rather than being conflated with an
      ordinary pending-check timeout.

    An empty `contexts` -- whether because `main.json`'s own
    `required_status_checks` rule is entirely absent, or because it is
    present but names nothing else -- is itself a fail-closed FAIL, never
    silently treated as "nothing to check" (see `required_check_contexts`'s
    own docstring and this issue's own defeat-test requirement).

    Every context's own conclusion is re-read from the latest full
    check-runs snapshot on EVERY poll iteration -- never cached as
    permanently "concluded" once seen passing once. GitHub's own
    check-runs endpoint always returns the complete, current set for
    `head_sha` (never a delta), so a context that reports `success` on one
    iteration but is later re-run (a real, GitHub-supported action) and
    concludes `failure` on a subsequent iteration must still be caught
    while this same poll call is still open waiting on some other
    context."""
    if not contexts:
        return False, (
            "no required status checks to verify: main.json's required_status_checks rule is either "
            "missing entirely or names no context besides independent-review-pending itself -- "
            'refusing to treat this as "nothing to check"'
        )

    deadline = clock() + timeout_seconds
    last_error: str | None = None
    unresolved: list[str] = list(contexts)

    while True:
        try:
            runs = _fetch_check_runs(owner, repo, head_sha, token, opener, sleeper)
        except GitHubApiError as error:
            last_error = str(error)
        else:
            last_error = None
            unresolved = []
            for context in contexts:
                run = _latest_run_for_context(runs, context)
                if run is None or run.get("status") != "completed":
                    unresolved.append(context)
                    continue
                conclusion = run.get("conclusion")
                if conclusion not in _PASSING_CONCLUSIONS:
                    return False, (
                        f"required check {context!r} completed with conclusion {conclusion!r} for head "
                        f"{head_sha} (expected one of {sorted(_PASSING_CONCLUSIONS)})"
                    )
            if not unresolved:
                return True, f"all {len(contexts)} required check(s) completed successfully for head {head_sha}"

        remaining = deadline - clock()
        if remaining <= 0:
            if last_error is not None:
                return False, (
                    f"timed out after {timeout_seconds}s polling GitHub check-runs for head {head_sha}: "
                    f"GitHub API errors persisted (last error: {last_error}); could not confirm status "
                    f"for: {sorted(unresolved)}"
                )
            return False, (
                f"timed out after {timeout_seconds}s waiting for required checks on head {head_sha} to "
                f"complete; still not completed: {sorted(unresolved)}"
            )
        sleeper(min(poll_interval_seconds, remaining))


def evaluate_bot_path(
    *,
    pr_author_login: str | None,
    pr_author_id: int | None,
    pr_author_type: str | None,
    owner: str | None,
    repo: str | None,
    head_sha: str,
    trusted_bots: list[dict[str, Any]],
    ruleset: dict[str, Any],
    token: str,
    head_commit_author_email: str | None = None,
    head_commit_committer_email: str | None = None,
    poll_timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[bool, str] | None:
    """Return `(passed, message)` for the trusted-bot merge-gate path, or
    `None` if this PR is not a bot-path candidate at all -- signalling
    `main()` to fall back completely to the existing `check(body,
    head_sha)` human-verdict path. Every `return None` below is a
    deliberate fall-through, never a hard FAIL: only `main()`'s own
    existing path decides FAIL once this function opts out.

    Never returns a PASS unless ALL of the following hold, matching the
    design doc's own architecture end to end:

    1. The PR author's identity matches `.github/trusted-bots.yml` on all
       three fields (`is_trusted_bot`).
    2. `owner`/`repo` are resolvable (needed for every GitHub API call
       below).
    3. The head commit's own author/committer email match `ruleset`'s
       `commit_author_email_pattern`/`committer_email_pattern` rules
       (`head_commit_identity_matches_bot`) -- the critical-defect fix.
    4. Every other required check has completed successfully for
       `head_sha` (`poll_bot_required_checks`)."""
    if pr_author_login is None or pr_author_id is None or pr_author_type is None:
        return None
    if not is_trusted_bot(pr_author_login, pr_author_id, pr_author_type, trusted_bots):
        return None
    if not owner or not repo:
        print(
            f"note: PR author {pr_author_login!r} matches a trusted-bots.yml entry, but --owner/--repo "
            "could not be resolved (no $GITHUB_REPOSITORY and no explicit --owner/--repo) -- falling "
            "back to the human-verdict path",
            file=sys.stderr,
        )
        return None

    author_email = head_commit_author_email
    committer_email = head_commit_committer_email
    if author_email is None or committer_email is None:
        if not token:
            print(
                f"note: PR author {pr_author_login!r} matches a trusted-bots.yml entry, but no "
                "head-commit email was given and GITHUB_TOKEN is unset to fetch it -- falling back to "
                "the human-verdict path",
                file=sys.stderr,
            )
            return None
        try:
            fetched_author, fetched_committer = fetch_head_commit_emails(owner, repo, head_sha, token, opener, sleeper)
        except GitHubApiError as error:  # except-fail-open: WAIVED: cannot confirm the head commit's own identity at all here -- design doc's own Revision section requires falling through to the strict human-verdict path on any inability to verify, never a silent bot-path pass and never a hard FAIL that would block every PR (bot or not) over a transient GitHub API failure.
            print(
                f"note: PR author {pr_author_login!r} matches a trusted-bots.yml entry, but the head "
                f"commit {head_sha} email could not be fetched ({error}) -- falling back to the "
                "human-verdict path",
                file=sys.stderr,
            )
            return None
        author_email = author_email if author_email is not None else fetched_author
        committer_email = committer_email if committer_email is not None else fetched_committer

    email_ok, email_message = head_commit_identity_matches_bot(author_email, committer_email, ruleset)
    if not email_ok:
        print(
            f"note: PR author {pr_author_login!r} matches a trusted-bots.yml entry, but {email_message} "
            "-- falling back to the human-verdict path (this specific commit was not actually "
            "authored/committed by that bot)",
            file=sys.stderr,
        )
        return None

    if not token:
        return False, "GITHUB_TOKEN is not set; cannot poll GitHub check-runs for the bot merge-gate path"

    contexts = required_check_contexts(ruleset)
    return poll_bot_required_checks(
        owner=owner,
        repo=repo,
        head_sha=head_sha,
        contexts=contexts,
        token=token,
        timeout_seconds=poll_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        opener=opener,
        sleeper=sleeper,
        clock=clock,
    )


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

    bot_group = parser.add_argument_group(
        "trusted-bot exemption (issue #1858)",
        "Optional. When the PR author's identity matches .github/trusted-bots.yml AND the head "
        "commit's own author/committer email match main.json's email-pattern rules, this gate polls "
        "required check-runs directly instead of requiring a recorded human verdict. Omitting "
        "--pr-author-login/--pr-author-id/--pr-author-type (or an identity that does not match) keeps "
        "the existing --body/--head-sha-only behavior completely unchanged.",
    )
    bot_group.add_argument("--pr-author-login", help="github.event.pull_request.user.login")
    bot_group.add_argument("--pr-author-id", type=int, help="github.event.pull_request.user.id")
    bot_group.add_argument("--pr-author-type", help="github.event.pull_request.user.type")
    bot_group.add_argument(
        "--owner", default=_github_repository_part(0), help="Repository owner; defaults from $GITHUB_REPOSITORY."
    )
    bot_group.add_argument(
        "--repo", default=_github_repository_part(1), help="Repository name; defaults from $GITHUB_REPOSITORY."
    )
    bot_group.add_argument(
        "--trusted-bots-path", default=str(DEFAULT_TRUSTED_BOTS_PATH), help="Path to .github/trusted-bots.yml."
    )
    bot_group.add_argument(
        "--ruleset-path", default=str(DEFAULT_RULESET_PATH), help="Path to .github/rulesets/main.json."
    )
    bot_group.add_argument(
        "--head-commit-author-email",
        help="Overrides the fetched commit.author.email (skips the GitHub API fetch when given).",
    )
    bot_group.add_argument(
        "--head-commit-committer-email",
        help="Overrides the fetched commit.committer.email (skips the GitHub API fetch when given).",
    )
    bot_group.add_argument(
        "--trust-anchor-ref",
        help=(
            "Git ref (e.g. github.event.pull_request.base.sha) to fetch .github/trusted-bots.yml and "
            ".github/rulesets/main.json from via the GitHub Contents API, instead of this checkout's own "
            "working tree -- so a PR cannot widen its own bot-exemption eligibility merely by editing "
            "either trust-anchor file within its own diff. Requires --owner/--repo (or $GITHUB_REPOSITORY), "
            "GITHUB_TOKEN, and --trust-anchor-base-ref/--repo-default-branch to actually agree (see those "
            "flags' own help); a failure to resolve any of these, or a GitHub API error while fetching, "
            "falls through to the human-verdict path like any other bot-path failure below -- an "
            "explicitly-given-but-empty value is treated the same as a resolution failure, never silently "
            "as 'flag omitted'. Omitting this flag entirely keeps reading "
            "--trusted-bots-path/--ruleset-path from local disk, unchanged (used by this script's own test "
            "suite, which has no real GitHub API to call)."
        ),
    )
    bot_group.add_argument(
        "--trust-anchor-base-ref",
        help=(
            "github.event.pull_request.base.ref -- the PR's own current base branch name. Required "
            "alongside --trust-anchor-ref; must equal --repo-default-branch or the ref is refused (a PR "
            "retargeted to a different, possibly branch-protection-free base branch could otherwise supply "
            "forged trust-anchor content at that base's own tip)."
        ),
    )
    bot_group.add_argument(
        "--repo-default-branch",
        help=(
            "github.event.repository.default_branch -- this repository's own default branch name, per "
            "the GitHub Actions event payload (not attacker-influenceable by the PR itself). Compared "
            "against --trust-anchor-base-ref; see that flag's own help."
        ),
    )
    bot_group.add_argument(
        "--poll-timeout-seconds",
        type=float,
        default=DEFAULT_POLL_TIMEOUT_SECONDS,
        help="How long to poll GitHub check-runs before failing on a still-pending required check.",
    )
    bot_group.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Delay between successive check-run polls.",
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

    bot_result: tuple[bool, str] | None = None
    if args.pr_author_login is not None or args.pr_author_id is not None or args.pr_author_type is not None:
        # Both loads must succeed before the bot path is even attempted --
        # deliberately not "load what we can and default the rest", since
        # `ruleset` in particular backs the critical-defect fix
        # (`head_commit_identity_matches_bot`): a corrupted/unreadable
        # main.json must never let `evaluate_bot_path` run at all here,
        # only ever fall through to the existing, unaffected human-verdict
        # path below (fail closed to the strict path, not a falsy
        # placeholder passed into the bot-path logic).
        try:
            if args.trust_anchor_ref is not None:
                # Read both trust anchors from a ref the PR under
                # evaluation cannot move (the PR's own base commit), never
                # from this job's own working tree -- see
                # fetch_repo_file_at_ref's own docstring for why. Every
                # check below raises ValueError
                # (never silently falls back to the local-disk `else`
                # branch, which is reserved for --trust-anchor-ref being
                # omitted entirely) -- a given-but-untrustworthy value
                # must refuse the bot path, not quietly downgrade to the
                # exact local-disk read this flag exists to replace.
                if not args.trust_anchor_ref:
                    raise ValueError("--trust-anchor-ref was given but is empty")
                if not args.trust_anchor_base_ref or not args.repo_default_branch:
                    raise ValueError(
                        "--trust-anchor-ref given but --trust-anchor-base-ref/--repo-default-branch "
                        "could not be resolved -- refusing to trust a ref without confirming it is this "
                        "repository's own default branch"
                    )
                if args.trust_anchor_base_ref != args.repo_default_branch:
                    raise ValueError(
                        f"--trust-anchor-ref given, but the PR's base ref {args.trust_anchor_base_ref!r} "
                        f"is not this repository's own default branch {args.repo_default_branch!r} -- "
                        "refusing to trust anchor files from a base branch a PR could itself retarget to"
                    )
                token_for_anchors = os.environ.get("GITHUB_TOKEN", "")
                if not args.owner or not args.repo:
                    raise ValueError(
                        "--trust-anchor-ref given but --owner/--repo could not be resolved "
                        "(no $GITHUB_REPOSITORY and no explicit --owner/--repo)"
                    )
                if not token_for_anchors:
                    raise ValueError("--trust-anchor-ref given but GITHUB_TOKEN is unset")
                trusted_bots_text = fetch_repo_file_at_ref(
                    args.owner, args.repo, ".github/trusted-bots.yml", args.trust_anchor_ref, token_for_anchors
                )
                trusted_bots = _parse_trusted_bots(
                    trusted_bots_text, f".github/trusted-bots.yml@{args.trust_anchor_ref}"
                )
                ruleset_text = fetch_repo_file_at_ref(
                    args.owner, args.repo, ".github/rulesets/main.json", args.trust_anchor_ref, token_for_anchors
                )
                ruleset = _parse_ruleset(ruleset_text, f".github/rulesets/main.json@{args.trust_anchor_ref}")
            else:
                trusted_bots = load_trusted_bots(Path(args.trusted_bots_path))
                ruleset = load_ruleset(Path(args.ruleset_path))
        except (yaml.YAMLError, json.JSONDecodeError, ValueError, GitHubApiError) as error:
            print(
                f"warning: could not load the bot-path allowlist/ruleset ({error}); the bot path is "
                "never attempted this run -- falling back to the human-verdict path",
                file=sys.stderr,
            )
        else:
            bot_result = evaluate_bot_path(
                pr_author_login=args.pr_author_login,
                pr_author_id=args.pr_author_id,
                pr_author_type=args.pr_author_type,
                owner=args.owner,
                repo=args.repo,
                head_sha=args.head_sha,
                trusted_bots=trusted_bots,
                ruleset=ruleset,
                token=os.environ.get("GITHUB_TOKEN", ""),
                head_commit_author_email=args.head_commit_author_email,
                head_commit_committer_email=args.head_commit_committer_email,
                poll_timeout_seconds=args.poll_timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )

    took_bot_path = bot_result is not None
    passed, message = bot_result if bot_result is not None else check(body, args.head_sha)
    if passed:
        print(f"PASS: {message}")
        return 0

    print(f"FAIL: {message}", file=sys.stderr)
    if took_bot_path:
        # The bot path's own FAIL (a required check failed/timed out) has
        # nothing to do with the human-verdict heading below -- printing
        # that hint here would be actively misleading remediation advice.
        print(
            "This is the trusted-bot merge-gate path (issue #1858): fix or re-run the named required "
            "check(s) against this exact head commit; recording a "
            f"'## {CANONICAL_HEADING_TEXT}' section does not apply here.",
            file=sys.stderr,
        )
    else:
        print(
            f"Record a '## {CANONICAL_HEADING_TEXT}' section in the PR body with "
            "'- Verdict: CLEAN' and '- Verified commit: <current head SHA>' once "
            "drafting-a-pr-to-merge's Step 8 review completes clean against this exact commit.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

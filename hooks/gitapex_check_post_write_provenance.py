#!/usr/bin/env python3
"""Re-scan the body GitHub actually stored, after a PR/issue write returns.

Issue #878: every provenance/ASCII scan in this repository runs against
the *drafted* text, before `mcp__github__create_pull_request` /
`mcp__github__update_pull_request` / `mcp__github__issue_write` executes
-- `hooks/check-bash-safety.sh`'s `git push` path scans the outgoing
commit range, and `skills/outward-artifact-preflight/SKILL.md`'s checks 1
and 3 are a manual checklist applied to the draft. Nothing re-scanned
what the platform actually stored afterwards, so a template
substitution, a downstream trailer injection, or an API-side transform
between drafting and posting shipped unscanned. That is not
hypothetical: outward-artifact-preflight's own second worked example
records the platform appending a session-URL trailer that was never in
the submitted `body`, "confirmed twice, on two independent PRs merged
the same day". Its Stop boundary states the gap plainly -- "no hook
re-checks what the platform actually stores" -- and makes the manual
post-creation re-check mandatory. This script is the deterministic
backstop for that manual step; raised and left unresolved across #677,
#566, #228, #212 before this one.

**Detective, not preventive, by design.** This runs on PostToolUse: the
write has already succeeded and the content is already public, so there
is nothing left to block (see
skills/evaluating-deterministic-gate-quality/references/dimensions.md
dimension 7 -- a post-action event cannot undo the action). Issue #878
states the same constraint in its own Constraints section. What this
gate *can* do is refuse to let the finding pass silently, which is
exactly what the pre-write gates cannot cover.

**Why it surfaces in-session instead of posting a comment.** Issue
#878's own Planned ops column proposed posting a corrective comment on
the PR/issue. Rejected on the owner's explicit decision, for three
reasons: it would require a *write*-scoped token for a check that
otherwise needs only read (least privilege), it would have an automated
gate perform an unconfirmed outward-facing write (CLAUDE.md section 4),
and re-posting a flagged provenance string into a second public comment
would widen the very exposure the scan exists to catch. The finding goes
to the agent (a `decision: block` reason) and to the operator (a
`systemMessage`) instead -- both in-session sinks, neither public. See
`check-post-write-provenance.sh` for the two-channel emission.

**Reuse, not re-implementation.** Both scans this runs are the existing
ones, not parallel copies:

- Provenance: `skills/outward-artifact-preflight/scripts/gitapex_scan_provenance.py`'s
  own `scan()`, loaded by file path (that directory is not on
  pyproject.toml's `pythonpath`, the same reason
  tests/test_gitapex_scan_provenance.py loads it that way). It is the
  identical function `check-bash-safety.sh` runs on `git push`, so a
  fixture that trips the pre-write path trips this one too by
  construction.
- Fetch: `hooks/gitapex_check_pr_issue_acm_disclosure.py`'s own public
  `fetch_issue()` (plain sibling import, the same way that module
  imports `gitapex_check_acm_present_or_waiver`). Deliberately NOT
  `.github/scripts/_gitapex_github_http.py`, which issue #878's own
  Acceptance Criteria Map named: per docs/repository-layout.md only
  `skills/` and `hooks/` are deployed with the plugin, `.github/` never
  is, so that import always misses in an installed-plugin consumer
  checkout.

The one scan authored here is the ASCII check (outward-artifact-preflight
checklist item 3), which had no reusable implementation: the repository's
existing character checks are `gitapex_gate_hidden_characters.py` (tracked
*files*, and only the invisible subset) and the raw-angle-bracket
placeholder check in `gitapex_check_skill_shape.py` (SKILL.md prose,
via a `Path`-taking checker) -- neither is a PR/issue-body check. Issue
#878's Acceptance Criteria Map cited the latter as the reusable pair
member; that citation does not hold up, and the checklist's own item 3
(ASCII-only) is what actually applies to an outward-facing body.

**Endpoint.** Always `/repos/{owner}/{repo}/issues/{number}`, for pull
requests as well as issues. GitHub's REST API considers every pull
request an issue (docs.github.com, "List issues": "GitHub's REST API
considers every pull request an issue, but not every issue is a pull
request"), and that endpoint returns the pull request's own `body` for a
PR number. One endpoint, one already-tested fetch helper, no `pulls`
special case.

**How the target number is resolved, and why the create path needed a
second route.** The update calls submit their own target
(`pullNumber`, `issue_number`) in `tool_input`. The create calls submit
none, and their real response carries none either -- issue #908 records
both observed verbatim: `{"id": "4235739033", "url":
"https://github.com/tvna/gitapex/pull/884"}` and `{"id": "5100051513",
"url": "https://github.com/tvna/gitapex/issues/905"}`. Until #908 this
module read only number *fields*, so every create firing reported
INDETERMINATE and never re-scanned -- on exactly the path #878's own
motivating defect lives on. The number is therefore parsed from the URL
tail when no field matched; `id` is the internal database identifier, not
the artifact number, and is never read. That first version was written
tolerant across three *hypothesised* envelopes without observing the real
one (evaluating-deterministic-gate-quality dimension 10, empirical
verification over assumed behavior); the URL shape is likewise the MCP
server's contract, not this repository's, so a future server change can
break resolution again -- the INDETERMINATE path below is what keeps that
loud rather than silent.

**Expect a hit on every PR body carrying a ratified trailer, and do not
suppress it.** A calling repository may have ratified a specific
attribution-trailer shape as a disclosed convention (this one has: see
`CONTRIBUTING.md`'s "outward-artifact-preflight: PR-body trailer
disclosure" section, and `outward-artifact-preflight/SKILL.md` check 1
items 2 and 5). `gitapex_scan_provenance.py` still flags such a trailer
on every hit **by design** -- that is CONTRIBUTING.md's own stated rule,
which explicitly bars adding "an ignore pattern, allowlist, or
`--exclude` flag" to silence it. So this gate reports FLAGGED on a
routine PR whose only hit is that trailer, and the operator's job is the
per-hit judgment call: is this the ratified instance, or a lookalike?
Verified live against this gate's own PR, whose submitted body was clean
and whose stored body had the trailer appended downstream. Reading a
FLAGGED verdict as automatically meaning "undisclosed leak" is the
misreading to avoid; the verdict means "a candidate needs your
judgment", exactly as the underlying scanner's own docstring says.

**Fail-loud on inability to verify.** A missing token, an unreachable
API, a body that cannot be resolved to an owner/repo/number, a payload
that is not a JSON object, or a missing provenance scanner all report
INDETERMINATE and exit non-zero -- never a silent PASS. The gate cannot
deny (the write already happened), so dimension 15's fail-closed default
takes its escalate form here: an unverifiable artifact is reported as
unverified, not assumed clean.

**Timeout budget, and the one fail-open this module cannot close from
inside itself.** The reused fetch path's own worst case is 45s of network
wait (`_HTTP_TIMEOUT_SECONDS = 20` x `_MAX_ATTEMPTS = 2`, plus one 5s
backoff between them), against a measured 0.1s of fixed local overhead.
`hooks/hooks.json` therefore budgets 60s, not 45: an adversarial review
of this file's own v1 found the earlier 45s budget was exactly the
network worst case with no headroom, so a fully stalled fetch raced its
own deadline. Residual risk, stated the way the sibling
`gitapex_check_pr_issue_acm_disclosure.py` already states it for itself:
a hard hook-runner timeout that kills this process before it emits its
report would functionally fail *open*, and no amount of headroom removes
that class -- it only makes it rarer.

Standard library only.

Usage (matches the JSON the .sh wrapper pipes in)::

    printf '%s' '{"tool_name":"mcp__github__update_pull_request",
                  "tool_input":{"owner":"tvna","repo":"gitapex","pullNumber":1}}' \\
        | python3 hooks/gitapex_check_post_write_provenance.py

Exit codes:
    0  PASS (the stored body scanned clean), or SKIP (the payload names a
       tool this gate does not cover -- self-revalidation, dimension 3).
    1  CONTENT_LOSS (the stored body is missing content the submitted
       body had, beyond an append-only addition or CRLF/trailing-
       whitespace normalization -- issue #1327), FLAGGED (a candidate
       marker or a non-ASCII character is in the stored body), or
       INDETERMINATE (the body could not be verified at all). All three
       carry a one-line reason on stderr; none is ever a raw traceback.

Issue #1327: this module's fetch already reads the true, unsanitized
stored body (`fetch_issue()` hits the REST API directly, never an MCP
read tool -- see that function's own module for why an MCP read is not
authoritative here). What it did not do until this issue is compare that
stored body against the body the same tool call actually submitted
(`tool_input["body"]`, present in the same PostToolUse payload and
previously unread by this module). `detect_content_loss()` closes that
gap: a coarse, conservative comparison that flags only the shape
#1088/#1302/#1313 actually hit before their own diagnosis was corrected
-- content present in the submission that is simply absent from the
stored body -- while staying silent on an append-only addition (the
ratified-attribution-trailer case the provenance scan already owns as
its own separate judgment call) and on CRLF/per-line-trailing-whitespace
normalization. It is not a general diff: a body edited in the middle by
a legitimate follow-up call between submission and this re-check is out
of scope, since nothing about two bare strings can distinguish
"downstream loss" from "deliberate follow-up edit" for that shape.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any

import gitapex_check_pr_issue_acm_disclosure as pr_issue_checker

# The provenance scanner's location relative to this file. hooks/ and
# skills/ are siblings at the package root in both layouts this hook ships
# in -- this repository checked out directly, and an apm/Claude-installed
# plugin bundle (docs/repository-layout.md) -- so resolving from this
# script's own path travels correctly with the bundle, unlike a
# CLAUDE_PROJECT_DIR-relative lookup.
_SCANNER_RELATIVE_PATH = Path("skills") / "outward-artifact-preflight" / "scripts" / "gitapex_scan_provenance.py"

# The three write tools issue #878 names. issue_write covers both its
# "create" and "update" methods: both submit a body, so both can have one
# transformed downstream. A method this gate does not recognize is treated
# as in scope rather than skipped -- an unknown future method that writes a
# body should be scanned, not silently exempted.
_COVERED_TOOLS = frozenset(
    {
        "mcp__github__create_pull_request",
        "mcp__github__update_pull_request",
        "mcp__github__issue_write",
    }
)

# tool_input field names carrying the target number, most specific first.
# `pullNumber` is mcp__github__update_pull_request's own spelling and
# `issue_number` is mcp__github__issue_write's; `pull_number`/`number` are
# tolerated spellings so a server-side rename degrades to a still-working
# lookup rather than a silent INDETERMINATE.
_NUMBER_FIELDS = ("pullNumber", "pull_number", "issue_number", "issueNumber", "number")

# tool_response field names carrying the created artifact's own URL. The
# create calls submit no number and their real response carries no number
# field either -- observed verbatim, twice (issue #908 fact 1):
# create_pull_request returned {"id": "4235739033", "url":
# "https://github.com/tvna/gitapex/pull/884"} and issue_write method create
# returned {"id": "5100051513", "url":
# "https://github.com/tvna/gitapex/issues/905"}. The number exists only in
# the URL tail. `html_url` is the tolerated alternate spelling, for the same
# reason _NUMBER_FIELDS tolerates several.
_URL_FIELDS = ("url", "html_url")

# The artifact-number tail of a GitHub issue/PR URL. Anchored on the
# `/issues/` or `/pull/` path segment (plus `/pulls/`, the REST spelling)
# rather than on "the last number in the string", so a digit anywhere else
# in the URL -- a repository named after a number, a commit-range fragment
# -- cannot be read as the artifact number. The tail is bounded by a path
# separator, a query, a fragment, or end-of-string so `/pull/884/files` and
# `/issues/905#issuecomment-1` still resolve.
_URL_NUMBER_RE = re.compile(r"/(?:issues|pulls?)/(\d+)(?:[/?#]|$)")

# Reported hits are capped so a pathological body cannot produce a
# multi-megabyte systemMessage. The count is always reported in full; only
# the per-hit detail is truncated.
_MAX_REPORTED_HITS = 20

# ASCII characters an outward-facing body may legitimately carry:
# printable ASCII plus the three whitespace characters a Markdown body
# really does contain. Everything else is a check-3 hit. Mirrors
# outward-artifact-preflight checklist item 3's own `[^ -~\t]` class, plus
# newline/carriage-return, which that checklist's line-oriented `grep`
# never sees as content but a whole-body scan does.
_ALLOWED_CONTROL_CHARACTERS = frozenset("\t\n\r")


class VerificationError(RuntimeError):
    """The stored body could not be verified at all (INDETERMINATE)."""


def load_provenance_scanner(scanner_path: Path | None = None) -> ModuleType:
    """Import gitapex_scan_provenance.py by file path and return the module.

    Raises VerificationError when the file is absent or cannot be
    executed -- a missing scan dependency is an inability to verify, never
    an implicit clean verdict (dimension 15).
    """
    path = scanner_path if scanner_path is not None else Path(__file__).resolve().parents[1] / _SCANNER_RELATIVE_PATH
    if not path.is_file():
        raise VerificationError(
            f"the provenance scanner was not found at {path} -- this looks like a corrupted or incomplete bundle"
        )
    spec = importlib.util.spec_from_file_location("_gitapex_post_write_scan_provenance", path)
    if spec is None or spec.loader is None:
        raise VerificationError(f"the provenance scanner at {path} could not be loaded as a Python module")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    # Deliberately broad: any import-time failure of the scanner (a syntax
    # error, a missing transitive import, an exception raised at module
    # level) is an inability to verify, and must reach the INDETERMINATE
    # path rather than escape as a traceback that reads as a crash.
    except Exception as error:
        raise VerificationError(f"the provenance scanner at {path} failed to import: {error}") from error
    # A file can exist at the expected path, import cleanly, and still not be
    # the scanner -- a rename, a truncated bundle, or a shadowing file. Without
    # this contract check the mismatch surfaces as an AttributeError raised
    # from scan_body(), which the wrapper then forwards as a raw traceback in
    # its report rather than the documented INDETERMINATE line.
    if not callable(getattr(module, "scan", None)):
        raise VerificationError(f"the module at {path} imported but exposes no callable scan() -- not the scanner")
    return module


def scan_non_ascii(text: str) -> list[tuple[int, int, str]]:
    """Return ``(line_no, column, codepoint_label)`` for every non-ASCII
    character, one entry per occurrence.

    The offending character is never echoed back: it is reported as its
    codepoint plus its formal Unicode name (``U+2014 EM DASH``), the same
    convention gitapex_gate_hidden_characters.py uses and for a related
    reason -- an invisible character echoed into a message is exactly as
    invisible there as it was in the body, and this script's own output
    has to stay ASCII regardless.
    """
    hits: list[tuple[int, int, str]] = []
    # `split("\n")`, deliberately not `splitlines()`: the latter also splits on
    # vertical tab, form feed, the file/group/record separators, NEL (U+0085),
    # and the Unicode line/paragraph separators (U+2028/U+2029) -- consuming
    # exactly the characters this scan exists to report. A body consisting of
    # a single U+2028 splits to [''] under `splitlines()` and scans clean, a
    # false negative found by an adversarial review of this file's own v1.
    # `\r` survives the `\n` split and is skipped as an allowed character, so
    # a CRLF body still reports nothing extra.
    for line_no, line in enumerate(text.split("\n"), start=1):
        for column, character in enumerate(line, start=1):
            if character in _ALLOWED_CONTROL_CHARACTERS:
                continue
            if " " <= character <= "~":
                continue
            name = unicodedata.name(character, "unnamed character")
            hits.append((line_no, column, f"U+{ord(character):04X} {name}"))
    return hits


def normalize_for_content_loss(text: str) -> str:
    """Fold CRLF/LF and per-line trailing whitespace, so a cosmetic
    normalization difference between the submitted body and the stored
    body is never read as content loss (issue #1327's own tolerance
    requirement). Trailing blank lines at the very end are folded too --
    the same reason a diff tool ignores a trailing newline.
    """
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in unified.split("\n")).rstrip("\n")


def detect_content_loss(submitted: str, stored: str) -> str | None:
    """Return a one-line reason when `stored` is missing content that was
    present in `submitted`, or None when no loss is detected.

    Two shapes are tolerated, deliberately, and both fall through to
    None:

    - Trivial normalization (CRLF/LF, per-line trailing whitespace) --
      not a defect this check exists to report.
    - An append-only addition: `stored` still contains `submitted` as a
      prefix, plus something after it. This is the ratified-attribution-
      trailer shape `hooks/check-post-write-provenance.sh`'s own
      provenance scan already owns as a separate, disclosure-aware
      judgment call (skills/outward-artifact-preflight/SKILL.md check 1
      item 5) -- this comparison must not re-flag it as loss.

    Anything else -- `stored` not starting with `submitted` after
    normalization -- is content loss: some or all of what was submitted
    is simply not present in what got stored, the exact shape
    #1088/#1302/#1313 originally (and, per issue #1327, incorrectly)
    attributed to GitHub's storage layer stripping Markdown.
    """
    norm_submitted = normalize_for_content_loss(submitted)
    norm_stored = normalize_for_content_loss(stored)
    if norm_submitted == norm_stored:
        return None
    if norm_stored.startswith(norm_submitted):
        return None
    return (
        "the STORED body is missing content present in the SUBMITTED body "
        "(beyond an append-only addition or CRLF/trailing-whitespace normalization)"
    )


def _coerce_mapping(value: Any) -> dict[str, Any]:
    """Return `value` when it is a JSON object, else an empty dict.

    Every caller reads optional fields off a payload sub-object that an
    upstream harness controls; a non-object there (a list, a string, null)
    is a shape this gate tolerates by falling through to its own
    INDETERMINATE path, never by raising an AttributeError past the
    documented exit codes.
    """
    return value if isinstance(value, dict) else {}


def response_payload(tool_response: Any) -> dict[str, Any]:
    """Best-effort normalization of a PostToolUse `tool_response` into the
    object the tool actually returned.

    Four shapes are accepted. The first is the one the harness actually
    delivers, captured from a live PostToolUse firing of
    `mcp__github__update_pull_request` in this repository (issue #908);
    the other three were hypothesised by this function's first version and
    are kept because the envelope is the MCP server's own contract rather
    than something this repository controls:

    - a bare MCP text-block list at the top level --
      ``[{"type": "text", "text": "<json>"}]`` -- **the observed one**;
    - the returned object itself;
    - an MCP ``{"content": "<json>"}`` string;
    - an MCP ``{"content": [{"type": "text", "text": "<json>"}, ...]}``
      block list.

    The bare list was the gap #908's own fix first missed: `_coerce_mapping`
    normalizes a list to ``{}``, so the response's `url` was unreachable no
    matter how well the number was parsed out of it, and the create path
    stayed INDETERMINATE. Anything else still normalizes to ``{}`` and the
    caller falls through to INDETERMINATE -- an unrecognized envelope must
    not read as "no number found, therefore nothing to scan".
    """
    payload = _coerce_mapping(tool_response)
    content = tool_response if isinstance(tool_response, list) else payload.get("content")

    candidates: list[str] = []
    if isinstance(content, str):
        candidates.append(content)
    elif isinstance(content, list):
        candidates.extend(
            block["text"] for block in content if isinstance(block, dict) and isinstance(block.get("text"), str)
        )

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed

    return payload


def _positive_int(text: str) -> int | None:
    """Return `text` as a positive int, or None when it is not one.

    The one conversion guard both number sources share. `int()` raises
    ValueError on a decimal string longer than `sys.int_max_str_digits`
    (4300 by default since CPython 3.11), and this module's runtime floor
    is 3.12, so a 5000-digit `issue_number` field or URL path segment
    escaped every handler in `evaluate()` -- which catches
    VerificationError around resolution -- and surfaced as a raw traceback,
    contradicting this module's own documented "never a raw traceback"
    contract. An oversized value is not a plausible artifact number
    anyway, so it reads as "no number here" and the caller falls through
    to INDETERMINATE. Found by an automated review of this change's own
    first push.
    """
    if not text.isdigit():
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return number if number > 0 else None


def _reports_error(response: dict[str, Any]) -> bool:
    """True when `response` carries an explicit write-failure marker.

    One definition, applied to both envelope levels by evaluate() -- the
    outer MCP envelope and the tool's own returned object -- so the two
    checks cannot drift into recognizing different markers.
    """
    return response.get("status") == "error" or response.get("is_error") is True or response.get("isError") is True


def _first_number(*sources: dict[str, Any]) -> int | None:
    """Return the first plausible issue/PR number found across `sources`.

    A bool is rejected explicitly: ``isinstance(True, int)`` is True in
    Python, so a ``{"number": true}`` payload would otherwise resolve to
    PR #1 and scan an unrelated artifact.
    """
    for source in sources:
        for field in _NUMBER_FIELDS:
            value = source.get(field)
            if isinstance(value, bool):
                continue
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str):
                number = _positive_int(value)
                if number is not None:
                    return number
    return None


def _number_from_url(*sources: dict[str, Any]) -> int | None:
    """Return the issue/PR number parsed from an artifact URL's tail.

    The fallback for the create calls, which carry no number field
    anywhere in the payload: not in `tool_input` (there is nothing to
    submit yet) and, as issue #908 records from direct observation, not in
    the real response either. Without this the gate reported INDETERMINATE
    on every create -- the exact path it was built for, since #878's own
    motivating defect is a trailer appended between the submitted draft
    and the stored body.

    `id` is deliberately never consulted, and must not be added to
    _NUMBER_FIELDS as a shortcut: it is GitHub's internal database
    identifier, not the artifact number (5100051513 versus 905 in the same
    observed response), so reading it would re-scan an unrelated artifact
    or 404 -- a trap rather than a usable fallback.
    """
    for source in sources:
        for field in _URL_FIELDS:
            value = source.get(field)
            if not isinstance(value, str):
                continue
            match = _URL_NUMBER_RE.search(value)
            if match is None:
                continue
            number = _positive_int(match.group(1))
            if number is not None:
                return number
    return None


def resolve_target(payload: dict[str, Any]) -> tuple[str, str, int]:
    """Return ``(owner, repo, number)`` for the artifact just written.

    owner/repo come from `tool_input` first (every covered tool takes both
    as required arguments) and from the normalized response only as a
    fallback. They are deliberately not cross-checked against the response
    URL, which carries them too: on the owner's explicit decision for issue
    #908, since a legitimate rename or redirect would then mismatch and
    report a real write as unverifiable, for a threat that has not been
    observed.

    The number comes from a number field for the update paths (`tool_input`
    carries the submitted `pullNumber`/`issue_number`) and, for the create
    paths, from the tail of the response URL -- the only place it appears
    at all. Raises VerificationError when any of the three cannot be
    resolved.
    """
    tool_input = _coerce_mapping(payload.get("tool_input"))
    response = response_payload(payload.get("tool_response"))

    owner = tool_input.get("owner") or response.get("owner") or ""
    repo = tool_input.get("repo") or response.get("repo") or ""
    if not isinstance(owner, str) or not isinstance(repo, str) or not owner or not repo:
        raise VerificationError(
            "could not resolve the target owner/repo from the tool call payload, so the stored body was never re-scanned"
        )

    number = _first_number(tool_input, response)
    if number is None:
        number = _number_from_url(response)
    if number is None:
        raise VerificationError(
            f"could not resolve the {owner}/{repo} issue/PR number from the tool call payload "
            "(no number field in tool_input or tool_response, and no parseable issue/PR URL in the "
            "response), so the stored body was never re-scanned"
        )

    return owner, repo, number


def _format_hits(provenance_hits: list[tuple[int, str, str]], ascii_hits: list[tuple[int, int, str]]) -> str:
    parts: list[str] = []
    if provenance_hits:
        shown = provenance_hits[:_MAX_REPORTED_HITS]
        detail = "; ".join(f"line {line_no}: {label}: {matched}" for line_no, label, matched in shown)
        if len(provenance_hits) > len(shown):
            detail += f"; ... and {len(provenance_hits) - len(shown)} more"
        parts.append(f"{len(provenance_hits)} candidate provenance marker(s) [{detail}]")
    if ascii_hits:
        shown_ascii = ascii_hits[:_MAX_REPORTED_HITS]
        detail = "; ".join(f"line {line_no} col {column}: {label}" for line_no, column, label in shown_ascii)
        if len(ascii_hits) > len(shown_ascii):
            detail += f"; ... and {len(ascii_hits) - len(shown_ascii)} more"
        parts.append(f"{len(ascii_hits)} non-ASCII character(s) [{detail}]")
    return " and ".join(parts)


def scan_body(body: str, scanner: ModuleType) -> tuple[bool, str]:
    """Run both checklist scans against `body`; return (clean, message)."""
    provenance_hits = list(scanner.scan(body))
    ascii_hits = scan_non_ascii(body)
    if not provenance_hits and not ascii_hits:
        return True, "no candidate provenance markers and no non-ASCII characters"
    return False, _format_hits(provenance_hits, ascii_hits)


def evaluate(
    payload: dict[str, Any],
    token: str | None,
    fetcher: Any = None,
    scanner_path: Path | None = None,
) -> tuple[str, str]:
    """Return ``(verdict, message)`` where verdict is SKIP, PASS,
    CONTENT_LOSS, FLAGGED, or INDETERMINATE.

    `fetcher` is the injection seam for the network call: it takes
    ``(owner, repo, number, token)`` and returns the fetched issue/PR
    mapping. Defaults to hooks/gitapex_check_pr_issue_acm_disclosure.py's
    own `fetch_issue`, so the retry/backoff behavior here is that
    already-tested one, not a second copy.
    """
    tool_name = payload.get("tool_name")
    tool_input = _coerce_mapping(payload.get("tool_input"))

    # Dimension 3 (self-revalidation): the hooks.json matcher already
    # restricts this hook to the three covered tools, but the matcher is
    # not this gate's own check.
    if not isinstance(tool_name, str) or tool_name not in _COVERED_TOOLS:
        return "SKIP", f"tool_name {tool_name!r} is not one this gate covers"

    # A failed write has no stored body to re-scan, and reporting one as
    # unverifiable would be noise on a call that never posted anything.
    # Only an explicit failure marker skips -- an absent or unrecognized
    # status is treated as a successful write and scanned.
    #
    # Both envelope levels are checked, and neither replaces the other. The
    # outer mapping is where an MCP-level `isError` sits, alongside a
    # `content` list; the failure marker of the tool's own returned object
    # is inside that list, and only response_payload() reaches it. Reading
    # the outer level alone was a real defect, not a theoretical one: on the
    # bare text-block list the harness actually delivers, _coerce_mapping
    # returns {} and this branch was dead. Reproduced in-process on both
    # covered paths -- a failed create whose error payload carried a `url`
    # resolved that URL and reported FLAGGED against a pre-existing,
    # unrelated pull request, and a failed update scanned the target's
    # pre-existing body and reported a verdict about a write that never
    # landed. Found by review of this change's own second push.
    if _reports_error(_coerce_mapping(payload.get("tool_response"))) or _reports_error(
        response_payload(payload.get("tool_response"))
    ):
        return "SKIP", f"{tool_name} reported an error, so no body was stored"

    try:
        owner, repo, number = resolve_target(payload)
        scanner = load_provenance_scanner(scanner_path)
    except VerificationError as error:
        return "INDETERMINATE", str(error)

    if not token:
        return "INDETERMINATE", (
            f"cannot re-fetch {owner}/{repo}#{number}'s stored body: no GH_TOKEN/GITHUB_TOKEN in the environment, "
            "so the artifact this call just published is unverified"
        )

    fetch = fetcher if fetcher is not None else _default_fetcher
    try:
        fetched = fetch(owner, repo, number, token)
    # Deliberately broader than GitHubApiError. The shared fetch path parses
    # its response with a bare `json.loads`, so a 2xx carrying a proxy
    # interstitial or a WAF page raises JSONDecodeError -- a ValueError, not
    # a GitHubApiError. An adversarial review of this file's own v1
    # confirmed in-process that it escaped every handler here and surfaced
    # through the wrapper as a raw traceback in the report's `reason` field,
    # contradicting this module's own documented "never a raw traceback"
    # contract. The direction was still fail-loud; the contract was not.
    except Exception as error:
        return "INDETERMINATE", (
            f"cannot re-fetch {owner}/{repo}#{number}'s stored body "
            f"({type(error).__name__}: {error}), "
            "so the artifact this call just published is unverified"
        )

    # A 2xx whose payload is not an issue at all -- an empty object, which
    # the shared fetch path returns for an empty response body -- would
    # otherwise scan as an empty string and report PASS. That was the one
    # path where "could not verify" rendered as "clean", contradicting this
    # module's own fail-loud rule. Every real issue or pull request carries
    # a non-empty `state`, so its absence means the response cannot be
    # confirmed to be the artifact just written.
    if not fetched.get("state"):
        return "INDETERMINATE", (
            f"the API response for {owner}/{repo}#{number} carries no issue state, so it cannot be "
            "confirmed to be the artifact just written; the artifact this call just published is unverified"
        )

    # `or ""` alone only coerces a *falsy* value (None, ""); a truthy
    # non-string body (a dict/list/int from a malformed or unexpected 2xx
    # response) would sail through unguarded and crash the first `.replace()`
    # call inside detect_content_loss()/scan_non_ascii() with a raw
    # AttributeError -- contradicting this module's own documented "never a
    # raw traceback" contract, which every other resolution step in this
    # function already upholds. Found live by an adversarial gate-quality
    # review of this issue's own change: a fetcher returning
    # {"body": {"unexpected": "shape"}, "state": "open"} reproduced the crash
    # before this guard existed.
    raw_body = fetched.get("body")
    if raw_body is not None and not isinstance(raw_body, str):
        return "INDETERMINATE", (
            f"the API response for {owner}/{repo}#{number} carries a non-string body "
            f"({type(raw_body).__name__}), so it cannot be verified"
        )
    body = raw_body or ""

    # Issue #1327: compare against what this same tool call actually
    # submitted, when it submitted a body at all. Some covered-tool calls
    # (e.g. an issue_write method that only changes labels/state) carry no
    # body field, and there is nothing to compare in that case -- silently
    # skipped, not INDETERMINATE, since no submission means no possible loss.
    submitted_body = tool_input.get("body")
    loss_reason = None
    if isinstance(submitted_body, str) and submitted_body:
        loss_reason = detect_content_loss(submitted_body, body)

    # The provenance/ASCII scan always runs, even when content loss already
    # fired: a truncated-and-still-leaking body (a stored body that lost
    # content AND still carries a provenance marker or non-ASCII character in
    # what remains) must not have the leak silently masked just because loss
    # is reported first. Found live by the same adversarial gate-quality
    # review: a fetcher returning a truncated body that still carried an
    # em dash and a candidate marker reported only CONTENT_LOSS before this
    # combination existed, with the co-occurring leak never surfaced.
    clean, message = scan_body(body, scanner)

    if loss_reason is not None:
        also_leaking = f" The stored body ALSO carries {message} -- both defects need remediation." if not clean else ""
        return "CONTENT_LOSS", (
            f"{owner}/{repo}#{number}'s STORED body: {loss_reason}.{also_leaking} This is a defect, not a "
            "judgment call: per issue #1327, do not re-check via an MCP read tool "
            "(pull_request_read/issue_read), whose own response sanitizer can independently "
            "strip content that storage still holds intact and would misreport this as clean or "
            "as a different problem. Re-submit the missing content via update_pull_request / "
            "issue_write, then re-fetch through this same raw channel to confirm."
        )

    if clean:
        return "PASS", f"{owner}/{repo}#{number}'s stored body re-scanned clean -- {message}"
    return "FLAGGED", (
        f"{owner}/{repo}#{number}'s STORED body (not the draft that was submitted) carries {message}. "
        "This surfaces candidates; it does not decide. Per skills/outward-artifact-preflight/SKILL.md check 1 "
        "items 2 and 5, first check whether each hit is a disclosure trailer this repository has already "
        "ratified in its own contributor-facing docs -- if so, it is agreed, not a leak, and must not be "
        "suppressed with an ignore pattern or allowlist. Otherwise the content is already public: per that "
        "skill's check 2, strip it via mcp__github__update_pull_request / mcp__github__issue_write, then "
        "re-fetch and re-scan to confirm it was not force-reinjected."
    )


def _default_fetcher(owner: str, repo: str, number: int, token: str) -> dict[str, str]:
    return pr_issue_checker.fetch_issue(owner, repo, number, token)


def main(argv: list[str] | None = None) -> int:
    """CLI: re-scan the stored body for the write described on stdin."""
    parser = argparse.ArgumentParser(
        description="Re-scan the body GitHub actually stored after a PR/issue write tool call succeeded."
    )
    parser.add_argument(
        "--payload",
        help="Path to a JSON file with the PostToolUse payload; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    payload_source = args.payload or "stdin"
    try:
        raw = Path(args.payload).read_text(encoding="utf-8") if args.payload else sys.stdin.read()
    except FileNotFoundError:
        print(f"error: payload file not found: {args.payload}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        print(f"error: payload ({payload_source}) is not valid UTF-8: {error}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(raw) if raw.strip() else {}
    # Deliberately ValueError, not json.JSONDecodeError. JSONDecodeError is a
    # ValueError subclass, but not every ValueError json.loads raises is one:
    # a numeric literal longer than sys.int_max_str_digits (4300) fails in
    # int parsing, which raises a plain ValueError. That escaped this handler
    # and reached the shell wrapper as a raw traceback, which the wrapper
    # forwards verbatim as its block reason -- the same "never a raw
    # traceback" contract _positive_int was added to uphold, one layer up
    # and still open. Reproduced through this CLI before widening.
    except ValueError as error:
        print(f"INDETERMINATE: payload ({payload_source}) could not be parsed as JSON: {error}", file=sys.stderr)
        return 1

    # `[]`, `"x"`, `1`, and `null` all parse as valid JSON. Without this
    # guard a non-object payload raises an uncaught AttributeError on the
    # first `.get` and exits 1 with a raw traceback instead of the
    # documented INDETERMINATE line.
    if not isinstance(payload, dict):
        print(
            f"INDETERMINATE: payload ({payload_source}) must be a JSON object, got {type(payload).__name__}",
            file=sys.stderr,
        )
        return 1

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    verdict, message = evaluate(payload, token)
    if verdict in ("SKIP", "PASS"):
        print(f"{verdict}: {message}")
        return 0
    print(f"{verdict}: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

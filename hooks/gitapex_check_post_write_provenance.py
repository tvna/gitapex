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
    1  FLAGGED (a candidate marker or a non-ASCII character is in the
       stored body) or INDETERMINATE (the body could not be verified at
       all). Both carry a one-line reason on stderr; neither is ever a
       raw traceback.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
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

    Deliberately tolerant across three observed/documented shapes, because
    the exact envelope is the MCP server's own contract rather than
    something this repository controls: the object itself, an MCP
    ``{"content": "<json>"}`` string, and an MCP
    ``{"content": [{"type": "text", "text": "<json>"}, ...]}`` block list.
    Anything else normalizes to ``{}`` and the caller falls through to
    INDETERMINATE -- an unrecognized envelope must not read as "no number
    found, therefore nothing to scan".
    """
    payload = _coerce_mapping(tool_response)
    content = payload.get("content")

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
            if isinstance(value, str) and value.isdigit() and int(value) > 0:
                return int(value)
    return None


def resolve_target(payload: dict[str, Any]) -> tuple[str, str, int]:
    """Return ``(owner, repo, number)`` for the artifact just written.

    owner/repo come from `tool_input` first (every covered tool takes both
    as required arguments) and from the normalized response only as a
    fallback. The number comes from `tool_input` for the update paths and
    from the response for `create_pull_request`, which has no number to
    submit. Raises VerificationError when any of the three cannot be
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
        raise VerificationError(
            f"could not resolve the {owner}/{repo} issue/PR number from the tool call payload "
            "(neither tool_input nor tool_response carried one), so the stored body was never re-scanned"
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
    """Return ``(verdict, message)`` where verdict is SKIP, PASS, FLAGGED,
    or INDETERMINATE.

    `fetcher` is the injection seam for the network call: it takes
    ``(owner, repo, number, token)`` and returns the fetched issue/PR
    mapping. Defaults to hooks/gitapex_check_pr_issue_acm_disclosure.py's
    own `fetch_issue`, so the retry/backoff behavior here is that
    already-tested one, not a second copy.
    """
    tool_name = payload.get("tool_name")

    # Dimension 3 (self-revalidation): the hooks.json matcher already
    # restricts this hook to the three covered tools, but the matcher is
    # not this gate's own check.
    if not isinstance(tool_name, str) or tool_name not in _COVERED_TOOLS:
        return "SKIP", f"tool_name {tool_name!r} is not one this gate covers"

    # A failed write has no stored body to re-scan, and reporting one as
    # unverifiable would be noise on a call that never posted anything.
    # Only an explicit failure marker skips -- an absent or unrecognized
    # status is treated as a successful write and scanned.
    response = _coerce_mapping(payload.get("tool_response"))
    if response.get("status") == "error" or response.get("is_error") is True or response.get("isError") is True:
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

    body = fetched.get("body") or ""
    clean, message = scan_body(body, scanner)
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
    except json.JSONDecodeError as error:
        print(f"INDETERMINATE: payload ({payload_source}) is not valid JSON: {error}", file=sys.stderr)
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

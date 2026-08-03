#!/usr/bin/env python3
"""Flag a "this repo's own convention" title/identity claim with no
resolvable issue citation in the same file.

Issue #520 (row 1, refs #344): retrospective #344 found that
`docs/superpowers/specs/2026-07-18-cicd-gate-cluster-design.md` asserted a
`title_pattern`/`title_prefixes` value was "this repo's own convention"
while actually copying another doc's fallback example -- a wrong
convention that PR #341/#342 had to correct twice (shipped code, then the
design doc itself). The proposed gate: any file asserting a title/identity
string is "this repo's own convention" / "established convention" /
"actual convention" must also cite a real, resolvable issue number as
evidence in the same file, not merely cross-reference another doc's say-so.

Scope, deliberately narrow: only a convention-claim phrase that also names
a title/identity concept (the word "title" or "identity" in the same
paragraph) counts -- a bare "gitapex's own convention" about, say, ASCII
formatting (skills/outward-artifact-preflight/SKILL.md) or a scoring rubric
(skills/ranking-the-open-queue/SKILL.md) is a different claim class this
gate does not police. Narrowing to the paragraph (a blank-line-delimited
block) rather than the whole file avoids requiring every file that happens
to mention both "title" and "convention" anywhere to carry a citation.

"Resolvable" (issue #520's own named residual risk: a stale cache could
false-pass a since-closed/renumbered issue) is checked two ways:

- ``--check-only``: pure text check -- the paragraph's file must contain
  at least one ``#<number>`` citation somewhere in the file. No network
  call, matching gate_acm_issue_disclosure.py's own --check-only shape.
- Full mode: additionally resolves each cited number against the GitHub
  API (a bare GET, matching scan_retrospective_gate_drift.py's own
  read-only issues-list pattern) and fails if every citation in an
  offending file is unresolvable (deleted, or never existed).

Deliberately stdlib-only and self-contained, matching this repository's
existing .github/scripts/*.py convention of not importing across files.
The GitHub API retry/error shape is copied from scan_retrospective_gate_drift.py
rather than shared, for the same reason that script gives for not importing
sync_pr_publish.py.

Usage (the check alone, no network calls, no side effects)::

    python3 .github/scripts/gate_retro_title_convention_citation.py --check-only FILE [FILE ...]

Usage (full run: also resolves each citation against the GitHub API)::

    python3 .github/scripts/gate_retro_title_convention_citation.py \\
        --owner tvna --repo gitapex FILE [FILE ...]

Environment variables:
    GITHUB_TOKEN  GitHub token with issues:read (the default Actions
                  token's read permission suffices). Not read at all in
                  --check-only mode.

Exit codes:
    0  No offending paragraph, or every offending file cites at least one
       resolvable issue number.
    1  An offending paragraph exists with no (resolvable) citation in its
       file, or a required argument/token is missing, or a GitHub API call
       failed.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30

# A convention-claim phrase: "this repo('s)? own/actual/established
# convention" (repo/repository, with or without a possessive apostrophe --
# Markdown sources in this repo use both "repo's" and a bare "repository").
# Up to two extra qualifier words (each optionally comma-separated) are
# allowed between the required modifier and "convention" -- e.g. "own,
# long-established convention" or "own established naming convention" --
# a natural paraphrase of the same claim this gate exists to catch, not
# just the single-adjective template.
_CONVENTION_CLAIM_RE = re.compile(
    r"\bthis\s+repo(?:sitory)?(?:'s)?\s+(?:own|actual|established)\b"
    r"(?:[,\s]+[A-Za-z-]+){0,2}\s+convention\b",
    re.IGNORECASE,
)

# The claim must also be about a title/identity string, not an unrelated
# convention (formatting, scoring, tooling) -- narrowed per this module's
# own docstring. Plural forms included ("titles", "identities") -- a claim
# about "this repo's own convention for retrospective titles" is the same
# claim class as one about "the title", not a different one.
_TITLE_IDENTITY_RE = re.compile(r"\b(titles?|identit(?:y|ies))\b", re.IGNORECASE)

# Digit-boundary-aware, matching scan_retrospective_gate_drift.py's own
# _citation_pattern rationale: "#341" must not match inside "#3410" or
# "#12341".
_CITATION_RE = re.compile(r"(?<!\d)#(\d+)(?!\d)")


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


def _paragraphs(text: str) -> list[str]:
    """Split `text` into blank-line-delimited paragraphs."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [p for p in re.split(r"\n\s*\n", normalized) if p.strip()]


def find_offending_paragraphs(text: str) -> list[str]:
    """Return every paragraph in `text` that claims a title/identity string
    is "this repo's own convention" (or actual/established), regardless of
    whether the file cites an issue anywhere -- citation is checked
    file-wide by `has_citation`, not paragraph-by-paragraph, since a doc
    may reasonably cite its evidence once near the top (e.g. "Refs #341")
    rather than repeating it inline at every claim.
    """
    return [
        paragraph
        for paragraph in _paragraphs(text)
        if _CONVENTION_CLAIM_RE.search(paragraph) and _TITLE_IDENTITY_RE.search(paragraph)
    ]


def cited_issue_numbers(text: str) -> list[int]:
    """Every distinct issue/PR number cited anywhere in `text`, in order of
    first appearance."""
    seen: list[int] = []
    for match in _CITATION_RE.finditer(text):
        number = int(match.group(1))
        if number not in seen:
            seen.append(number)
    return seen


def has_citation(text: str) -> bool:
    """Return True iff `text` cites at least one issue/PR number anywhere."""
    return bool(_CITATION_RE.search(text))


def _no_citation_message(path: Path) -> str:
    """Shared offender message for both --check-only and full mode, so the
    two never drift into subtly different wording for the same defect."""
    return f"{path}: title/identity convention claim with no #<number> citation anywhere in the file"


# ---------------------------------------------------------------------------
# GitHub API side effect: resolve a citation (full mode only)
# ---------------------------------------------------------------------------


def _default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller builds `request` from a fixed
    # https://api.github.com URL plus trusted owner/repo/issue-number
    # segments.
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310


def _format_code(code: int) -> str:
    return str(code) if code else "network error"


def is_resolvable_issue(
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> bool:
    """Return True iff `issue_number` resolves to a real issue or PR
    (the issues-list endpoint covers both) in `owner/repo`. A 404 means
    "not found" (never existed, or was deleted) -- not resolvable. Any
    other non-2xx status after retries raises, since that is a check
    failure, not a citation failure, and must not be silently reported as
    "not resolvable".
    """
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}"
    last_code = 0
    last_body = ""
    for attempt in range(1, 4):
        request = urllib.request.Request(url, method="GET")  # noqa: S310 -- fixed https://api.github.com URL
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", _API_VERSION)
        try:
            with opener(request) as response:
                last_code = int(response.status)
                last_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            last_code = int(error.code)
            last_body = error.read().decode("utf-8", errors="replace")
        except (OSError, http.client.IncompleteRead) as error:
            last_code = 0
            last_body = str(error)

        if last_code == 404:
            return False
        if 200 <= last_code < 300:
            return True
        print(f"Attempt {attempt}: HTTP {_format_code(last_code)} for GET {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < 3:
            sleeper(attempt * 5)

    raise GitHubApiError(f"GET {url} failed: HTTP {_format_code(last_code)}: {last_body}")


def find_unresolvable_offenders(
    path: Path,
    text: str,
    owner: str,
    repo: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> str | None:
    """Return a human-readable offender line for `path` if it has an
    offending paragraph and none of its cited issue numbers resolve, else
    None. A file with no offending paragraph is never an offender,
    regardless of citations."""
    if not find_offending_paragraphs(text):
        return None
    numbers = cited_issue_numbers(text)
    if not numbers:
        return _no_citation_message(path)
    if any(is_resolvable_issue(owner, repo, n, token, opener, sleeper) for n in numbers):
        return None
    cited = ", ".join(f"#{n}" for n in numbers)
    return f"{path}: title/identity convention claim cites {cited}, but none resolve to a real issue/PR"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag a file claiming a title/identity string is this repo's "
        "own convention with no resolvable issue citation."
    )
    parser.add_argument("files", nargs="+", help="Paths to skill/doc files to check.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check that an offending file cites a #<number> somewhere "
        "(no GitHub API call, no resolvability check).",
    )
    parser.add_argument("--owner", help="Repository owner, e.g. tvna. Required unless --check-only.")
    parser.add_argument("--repo", help="Repository name, e.g. gitapex. Required unless --check-only.")
    args = parser.parse_args(argv)

    texts: dict[Path, str] = {}
    for raw_path in args.files:
        path = Path(raw_path)
        try:
            texts[path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"error: could not read {path}: {error}", file=sys.stderr)
            return 1

    if args.check_only:
        offenders = [
            _no_citation_message(path)
            for path, text in texts.items()
            if find_offending_paragraphs(text) and not has_citation(text)
        ]
        if not offenders:
            print("PASS: no uncited title/identity convention claim found")
            return 0
        print("FAIL: the following file(s) claim a title/identity convention with no citation:", file=sys.stderr)
        for offender in offenders:
            print(f"  - {offender}", file=sys.stderr)
        print(
            "Cite the real issue number this convention derives from (e.g. 'Refs #341'), "
            "or drop the 'this repo's own convention' framing if it is not actually backed by one.",
            file=sys.stderr,
        )
        return 1

    if not args.owner or not args.repo:
        print("error: --owner and --repo are required outside --check-only", file=sys.stderr)
        return 1
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        unresolvable_offenders: list[str] = [
            unresolvable
            for path, text in texts.items()
            if (unresolvable := find_unresolvable_offenders(path, text, args.owner, args.repo, token)) is not None
        ]
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not unresolvable_offenders:
        print("PASS: every title/identity convention claim cites a resolvable issue")
        return 0
    print("FAIL: the following file(s) fail the convention-citation check:", file=sys.stderr)
    for offender in unresolvable_offenders:
        print(f"  - {offender}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

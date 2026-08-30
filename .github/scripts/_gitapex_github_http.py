#!/usr/bin/env python3
"""Shared GitHub REST API pagination/retry client for `.github/scripts/*.py`.

Issue #726 (repair to a /code-review finding on the GPRR PR): the first
version of this reuse had `gitapex_compute_gprr.py` import
`gitapex_scan_retrospective_gate_drift.py` directly for its low-level HTTP
fetch (`fetch_json_page`/`GitHubApiError`), which broke this
repository's established `.github/scripts/*.py` independence
convention -- see `gitapex_scan_retrospective_gate_drift.py`'s own docstring,
`gitapex_gate_skill_rename_lifecycle.py`, and `gitapex_gate_acm_issue_disclosure.py` for
that same convention stated elsewhere. Extracting the generic,
endpoint-agnostic retry/pagination client here (issue-specific and
pull-specific fetch logic stay in their own scripts) keeps every
gate/report script independent of every OTHER gate/report script, while
still satisfying issue #726's own "reuse the existing fetch logic rather
than re-implementing GitHub API pagination" mandate. Both
`gitapex_scan_retrospective_gate_drift.py` and `gitapex_compute_gprr.py` depend on this
one small shared module; they do not depend on each other for this.

`gitapex_compute_gprr.py` still imports `gitapex_scan_retrospective_gate_drift`
directly for `list_labelled_issue_records` -- that one is
issue-specific business logic issue #726 explicitly named as the thing
to reuse, not something this module can absorb without duplicating that
logic instead.
"""

from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30
_GRAPHQL_URL = "https://api.github.com/graphql"
_GRAPHQL_TRANSIENT_ERROR_MARKER = "something went wrong while executing your query"


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


def build_headers(token: str, *, content_type: str | None = None) -> dict[str, str]:
    """The `Authorization`/`Accept`/`X-GitHub-Api-Version` headers every
    caller in this repository sends, plus `Content-Type` when given.

    Shared by this module's own REST and GraphQL paths and by
    `gitapex_apply_rulesets.py`'s write path (`send_write`) -- previously
    two independent copies of the same three header literals plus this
    module's own `_API_VERSION`/`_HTTP_TIMEOUT_SECONDS` constants,
    re-declared verbatim in that file.
    Only header-literal construction is shared: the actual mutating
    request (URL, method, body, the `urlopen` call, and its own exception
    handling) stays entirely inside `send_write`, so "what in this
    repository can mutate GitHub state" still reads as one function, not a
    shared module used by every read-only caller too.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
    }
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers


def default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller builds `request` from a fixed
    # https://api.github.com URL plus trusted env-var-derived segments.
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310


def fetch_json_page(
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
) -> list[dict[str, Any]]:
    """GET one page of a GitHub REST list endpoint that returns a JSON
    array, retrying transient failures. Generic across endpoints (issues,
    pulls, ...) -- the retry/backoff shape has nothing endpoint-specific
    about it.

    Contract: the return value is unvalidated parsed JSON (this function
    only checks HTTP status and JSON-parseability, not shape) -- every
    caller must shape-check it before use (a non-list response, or a list
    containing a non-dict item) rather than assume the annotated type
    holds at runtime. `_gitapex_rulesets.py` is the existing example to
    follow (issue #995)."""
    page: list[dict[str, Any]] = fetch_json_document(url, token, opener, sleeper)
    return page


def fetch_json_document(
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
) -> Any:
    """GET one GitHub REST endpoint that returns *any* JSON document --
    object or array -- retrying transient failures exactly as
    :func:`fetch_json_page` does.

    Issue #439 (the ruleset source-of-truth work) needs
    `GET /repos/{owner}/{repo}/rulesets/{id}`, whose body is a JSON
    *object*, not the array every prior caller here fetched.
    `fetch_json_page`'s own `-> list[dict[str, Any]]` annotation is not a
    runtime check (it is a plain `json.loads` assignment), so calling it
    for an object endpoint would "work" while lying to mypy and to every
    reader. Rather than widen that established signature -- three modules
    plus a hook already depend on the list contract -- the retry/backoff
    body moved here and `fetch_json_page` became a typed wrapper over it.
    Behaviour for existing callers is byte-for-byte unchanged; they still
    get `list[dict[str, Any]]`, still raise `GitHubApiError` on the same
    conditions.

    Contract: like `fetch_json_page`, the return value is unvalidated
    parsed JSON -- every caller must shape-check it before use.
    `_gitapex_rulesets.py` is the existing example to follow (issue #995).

    Issue #729: the HTTP/retry work itself now delegates to
    `request_with_retry` (the generalized, non-raising core this and
    `call_json` both sit on top of) -- this function's own public
    behaviour and raise conditions are unchanged, only the retry loop's
    body moved.
    """
    last_code, last_body = request_with_retry("GET", url, token, opener, sleeper)
    if 200 <= last_code < 300:
        try:
            document: Any = json.loads(last_body)
        except json.JSONDecodeError as error:
            # A 200 response is not proof of a parseable body -- a
            # flaky proxy/CDN in front of api.github.com can return
            # HTTP 200 with a truncated or empty body. Without this,
            # a JSONDecodeError would escape every caller's own
            # `except GitHubApiError` and crash as a raw traceback
            # instead of the documented clean error/exit-1 path.
            raise GitHubApiError(f"GET {url} returned HTTP {last_code} with unparseable JSON: {error}") from error
        return document
    raise GitHubApiError(f"GET {url} failed: HTTP {format_code(last_code)}: {last_body}")


def request_with_retry(
    method: str,
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
    *,
    body: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> tuple[int, str]:
    """Call the GitHub REST API with `method`, retrying transient
    (network / 5xx) failures up to `max_attempts` times. This is the core
    retry/backoff primitive `fetch_json_document` and `call_json` both sit
    on top of -- generalized from `fetch_json_document`'s own former
    inline loop plus the near-identical `_call` implementations
    hand-copied across `gitapex_gate_acm_issue_disclosure.py`,
    `gitapex_post_merge_retro.py`, and `gitapex_stale_retro_stub_autoclose.py`
    (issue #729).

    Unlike `fetch_json_document`/`call_json`, this function does NOT raise
    on a non-2xx status after retries are exhausted -- it always returns
    the final `(status_code, body_text)` pair, success or not. That is
    the key design difference enabling a caller that needs to branch on
    the raw status code itself (a 404-special-case check, for instance,
    the way `gitapex_gate_retro_title_convention_citation.py`'s own
    `is_resolvable_issue` does) to call this directly instead of catching
    `GitHubApiError`.
    """
    data = json.dumps(body).encode("utf-8") if body is not None else None
    content_type = "application/json" if body is not None else None
    last_code = 0
    last_body = ""
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 -- fixed https://api.github.com URL
        for name, value in build_headers(token, content_type=content_type).items():
            request.add_header(name, value)
        try:
            with opener(request) as response:
                last_code = int(response.status)
                last_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            last_code = int(error.code)
            last_body = error.read().decode("utf-8", errors="replace")
        except (OSError, http.client.IncompleteRead) as error:
            # Covers urllib.error.URLError (an OSError subclass, e.g. DNS/
            # connection failures) and TimeoutError/ConnectionError, plus a
            # body read that starts (headers arrive, `last_code` gets set)
            # but stalls or is cut short -- IncompleteRead is not an OSError
            # subclass, so it needs its own arm. Without this, a body-read
            # failure escapes retry entirely and crashes the whole scan
            # instead of getting the attempts promised below.
            last_code = 0
            last_body = str(error)

        if 200 <= last_code < 300:
            break
        print(f"Attempt {attempt}: HTTP {format_code(last_code)} for {method} {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < max_attempts:
            sleeper(attempt * 5)

    return last_code, last_body


def call_json(
    method: str,
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
    *,
    body: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> Any:
    """Call the GitHub REST API via `request_with_retry`, returning the
    parsed JSON body on a 2xx status, or raising `GitHubApiError` (with
    the exact message text `gitapex_gate_acm_issue_disclosure.py`,
    `gitapex_post_merge_retro.py`, and `gitapex_stale_retro_stub_autoclose.py`'s
    own `_call` functions already raise) once retries are exhausted on a
    non-2xx status.

    `max_attempts` defaults to 3, which is correct for an idempotent call
    (GET/search, or a PATCH that sets an already-final state). A caller
    creating a non-idempotent resource -- an issue or a comment POST --
    must pass `max_attempts=1` instead: a lost or truncated response
    after GitHub has already created the resource would otherwise be
    retried into a duplicate (RFC 9110 SS9.2.2). This paragraph is the
    rationale `gitapex_post_merge_retro.py`'s `open_retro_issue` and
    `gitapex_stale_retro_stub_autoclose.py`'s `close_stub_issue` cite at
    their own `max_attempts=1` call sites; it moved here with the retry
    loop itself (issue #729) rather than staying behind in the deleted
    per-carrier `_call` docstrings.

    Deliberately does NOT guard the `json.loads` call below with a
    try/except: this preserves an existing, deliberately-not-fixed-in-
    this-PR bug already present in every one of those three carriers'
    own `_call` functions -- a 2xx response with an unparseable body
    raises a raw `json.JSONDecodeError` here, not `GitHubApiError`.
    Issue #729's criterion 3, a separate later PR, owns fixing it; adding
    a guard here would silently fix it early and diverge from what those
    carriers are being migrated to reproduce exactly.
    """
    last_code, last_body = request_with_retry(method, url, token, opener, sleeper, body=body, max_attempts=max_attempts)
    if 200 <= last_code < 300:
        return json.loads(last_body) if last_body else {}
    raise GitHubApiError(f"{method} {url} failed: HTTP {format_code(last_code)}: {last_body}")


def _graphql_is_transient(code: int, body: dict[str, Any]) -> bool:
    if code == 0 or code >= 500:
        return True
    errors = body.get("errors")
    if isinstance(errors, list):
        for err in errors:
            message = err.get("message", "") if isinstance(err, dict) else ""
            if isinstance(message, str) and _GRAPHQL_TRANSIENT_ERROR_MARKER in message.lower():
                return True
    return False


def graphql_call(
    *,
    query: str,
    variables: dict[str, Any],
    token: str,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Execute a GitHub GraphQL query/mutation, retrying transient
    failures.

    Moved from `gitapex_sync_pr_publish.py` (issue #729, criterion 1),
    with two edits made on arrival rather than a verbatim copy: it
    retries on 5xx/network failures AND on a 200 response whose body
    contains a GraphQL transient-error marker
    (`_GRAPHQL_TRANSIENT_ERROR_MARKER`, via `_graphql_is_transient`), and
    it already guards its own `json.loads` with `try/except
    json.JSONDecodeError`, degrading to an empty dict on an
    unparseable/empty body -- that part really was already correct. But
    its own network-failure handling was narrower than
    `request_with_retry`'s: `except urllib.error.URLError` alone misses
    `http.client.IncompleteRead` (not a `URLError`/`OSError` subclass),
    so a body read that starts but stalls or is cut short escaped
    uncaught here instead of retrying (found by this issue's own Step 8
    adversarial review, fixed to match `request_with_retry`'s own
    `except (OSError, http.client.IncompleteRead)` shape). Its four
    hand-written `add_header` calls also now go through this module's
    own `build_headers`, which already produced that exact header set for
    the REST path -- keeping them re-declared here would have re-created,
    inside the shared module, the very header duplication this module
    exists to remove.
    `gitapex_sync_pr_publish.py`'s own `_CREATE_COMMIT_ON_BRANCH_MUTATION`
    string stays there -- it is business logic specific to that carrier,
    not generic retry-client mechanics.
    """
    sleeper = sleeper if sleeper is not None else time.sleep
    payload = json.dumps({"query": query, "variables": variables}, separators=(",", ":"))
    last_code = 0
    last_body: dict[str, Any] = {}

    for attempt in range(1, 4):
        request = urllib.request.Request(_GRAPHQL_URL, data=payload.encode("utf-8"), method="POST")
        for name, value in build_headers(token, content_type="application/json").items():
            request.add_header(name, value)
        try:
            with opener(request) as response:
                code = int(response.status)
                body_str = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            code = int(error.code)
            body_str = error.read().decode("utf-8", errors="replace")
        except (OSError, http.client.IncompleteRead) as error:
            # Matches request_with_retry's own except clause (issue #729,
            # Step 8 adversarial review): http.client.IncompleteRead is
            # not an OSError subclass, so a body read that starts but
            # stalls or is cut short needs its own arm here too -- the
            # narrower `except urllib.error.URLError` this function
            # carried on arrival (URLError IS an OSError subclass, so it
            # stays covered) missed that case, and an IncompleteRead
            # would otherwise escape this loop uncaught instead of
            # retrying like every other failure mode here does.
            code = 0
            body_str = str(error)
        try:
            parsed = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            parsed = {}
        last_code = code
        last_body = parsed if isinstance(parsed, dict) else {}

        if not _graphql_is_transient(last_code, last_body):
            break
        print(f"Attempt {attempt}: transient GraphQL response HTTP {format_code(last_code)}", file=sys.stderr)
        if attempt < 3:
            sleeper(attempt * 5)

    return last_code, last_body


def format_code(code: int) -> str:
    """Render a status code for a human: the number itself, or
    "network error" for the sentinel 0 this module uses when no HTTP
    response arrived at all.

    Public (not `_format_code`) because it is part of this module's
    contract with its callers, not an implementation detail: every
    `GitHubApiError` message and retry-attempt log line in this
    repository -- including the one
    `gitapex_gate_retro_title_convention_citation.py` raises itself, from
    a `request_with_retry` result this module never sees again -- has to
    render a code the same way, or the same failure reads differently
    depending on which caller reported it. `gitapex_apply_rulesets.py`
    (pre-existing, untouched by issue #729) is this repository's one
    established exception, importing the private `_HTTP_TIMEOUT_SECONDS`
    alongside this module's public symbols -- a narrower gap this
    function's own publicness does not need to repeat.
    """
    return str(code) if code else "network error"

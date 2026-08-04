#!/usr/bin/env python3
"""Shared GitHub REST API pagination/retry client for `.github/scripts/*.py`.

Issue #726 (repair to a /code-review finding on the GPRR PR): the first
version of this reuse had `compute_gprr.py` import
`scan_retrospective_gate_drift.py` directly for its low-level HTTP
fetch (`fetch_json_page`/`GitHubApiError`), which broke this
repository's established `.github/scripts/*.py` independence
convention -- see `scan_retrospective_gate_drift.py`'s own docstring,
`gate_skill_rename_lifecycle.py`, and `gate_acm_issue_disclosure.py` for
that same convention stated elsewhere. Extracting the generic,
endpoint-agnostic retry/pagination client here (issue-specific and
pull-specific fetch logic stay in their own scripts) keeps every
gate/report script independent of every OTHER gate/report script, while
still satisfying issue #726's own "reuse the existing fetch logic rather
than re-implementing GitHub API pagination" mandate. Both
`scan_retrospective_gate_drift.py` and `compute_gprr.py` depend on this
one small shared module; they do not depend on each other for this.

`compute_gprr.py` still imports `scan_retrospective_gate_drift`
directly for `list_labelled_issue_records` -- that one is
issue-specific business logic issue #726 explicitly named as the thing
to reuse, not something this module can absorb without duplicating that
logic instead.
"""

from __future__ import annotations

import http.client
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


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
    about it."""
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
            # Covers urllib.error.URLError (an OSError subclass, e.g. DNS/
            # connection failures) and TimeoutError/ConnectionError, plus a
            # body read that starts (headers arrive, `last_code` gets set)
            # but stalls or is cut short -- IncompleteRead is not an OSError
            # subclass, so it needs its own arm. Without this, a body-read
            # failure escapes retry entirely and crashes the whole scan
            # instead of getting the three attempts promised below.
            last_code = 0
            last_body = str(error)

        if 200 <= last_code < 300:
            try:
                page: list[dict[str, Any]] = json.loads(last_body)
            except json.JSONDecodeError as error:
                # A 200 response is not proof of a parseable body -- a
                # flaky proxy/CDN in front of api.github.com can return
                # HTTP 200 with a truncated or empty body. Without this,
                # a JSONDecodeError would escape every caller's own
                # `except GitHubApiError` and crash as a raw traceback
                # instead of the documented clean error/exit-1 path.
                raise GitHubApiError(f"GET {url} returned HTTP {last_code} with unparseable JSON: {error}") from error
            return page
        print(f"Attempt {attempt}: HTTP {_format_code(last_code)} for GET {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < 3:
            sleeper(attempt * 5)

    raise GitHubApiError(f"GET {url} failed: HTTP {_format_code(last_code)}: {last_body}")


def _format_code(code: int) -> str:
    return str(code) if code else "network error"

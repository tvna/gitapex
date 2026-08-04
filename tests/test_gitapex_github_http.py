"""Tests for the shared GitHub REST API pagination/retry client
(.github/scripts/_gitapex_github_http.py).

Refs #726: extracted out of gitapex_scan_retrospective_gate_drift.py so
gitapex_compute_gprr.py depends on this generic client instead of importing
gitapex_scan_retrospective_gate_drift.py's low-level HTTP plumbing directly.
test_gitapex_scan_retrospective_gate_drift.py and test_gitapex_compute_gprr.py already
exercise `fetch_json_page` extensively through their own callers; this
file covers the parts specific to this module -- in particular the
malformed-JSON-on-HTTP-200 path neither sibling test file reaches.
"""

from __future__ import annotations

import json
import urllib.request

import _gitapex_github_http
import pytest


class Response:
    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self.body = body.encode()

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        return None


def test_fetch_json_page_returns_parsed_array() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps([{"number": 1}]))

    result = _gitapex_github_http.fetch_json_page("https://example.test", "tok", opener, lambda _: None)
    assert result == [{"number": 1}]


def test_fetch_json_page_raises_github_api_error_on_unparseable_200_body() -> None:
    # A flaky proxy/CDN can return HTTP 200 with a truncated or empty
    # body -- this must surface as the documented GitHubApiError, not an
    # uncaught json.JSONDecodeError escaping into every caller's main().
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "not json")

    with pytest.raises(_gitapex_github_http.GitHubApiError, match="unparseable JSON"):
        _gitapex_github_http.fetch_json_page("https://example.test", "tok", opener, lambda _: None)


def test_fetch_json_page_raises_github_api_error_on_empty_200_body() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "")

    with pytest.raises(_gitapex_github_http.GitHubApiError, match="unparseable JSON"):
        _gitapex_github_http.fetch_json_page("https://example.test", "tok", opener, lambda _: None)


def test_fetch_json_page_sends_expected_headers() -> None:
    captured: list[urllib.request.Request] = []

    def opener(request: urllib.request.Request) -> Response:
        captured.append(request)
        return Response(200, "[]")

    _gitapex_github_http.fetch_json_page("https://example.test", "sekrit", opener, lambda _: None)
    assert captured[0].headers["Authorization"] == "Bearer sekrit"
    assert captured[0].headers["Accept"] == "application/vnd.github+json"
    assert captured[0].headers["X-github-api-version"] == "2022-11-28"

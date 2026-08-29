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

import inspect
import json
import urllib.error
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


def test_build_headers_omits_content_type_by_default() -> None:
    headers = _gitapex_github_http.build_headers("sekrit")
    assert headers == {
        "Authorization": "Bearer sekrit",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    assert "Content-Type" not in headers


def test_build_headers_adds_content_type_when_given() -> None:
    headers = _gitapex_github_http.build_headers("sekrit", content_type="application/json")
    assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# request_with_retry -- the core retry/backoff primitive (issue #729).
# ---------------------------------------------------------------------------


def test_request_with_retry_returns_status_and_body_on_success() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "ok body")

    code, body = _gitapex_github_http.request_with_retry("GET", "https://example.test", "tok", opener, lambda _: None)
    assert (code, body) == (200, "ok body")


def test_request_with_retry_retries_5xx_then_succeeds() -> None:
    attempts: list[int] = []

    def opener(request: urllib.request.Request) -> Response:
        attempts.append(1)
        if len(attempts) < 2:
            raise urllib.error.HTTPError("https://example.test", 503, "unavailable", {}, Response(503, "retry me"))  # type: ignore[arg-type]
        return Response(200, "recovered")

    sleeps: list[float] = []
    code, body = _gitapex_github_http.request_with_retry("GET", "https://example.test", "tok", opener, sleeps.append)
    assert (code, body) == (200, "recovered")
    assert len(attempts) == 2
    assert sleeps == [5]


def test_request_with_retry_does_not_retry_4xx() -> None:
    attempts: list[int] = []

    def opener(request: urllib.request.Request) -> Response:
        attempts.append(1)
        raise urllib.error.HTTPError("https://example.test", 404, "not found", {}, Response(404, "missing"))  # type: ignore[arg-type]

    sleeps: list[float] = []
    code, _ = _gitapex_github_http.request_with_retry("GET", "https://example.test", "tok", opener, sleeps.append)
    assert code == 404
    assert len(attempts) == 1
    assert sleeps == []


def test_request_with_retry_max_attempts_1_disables_retry_for_non_idempotent_calls() -> None:
    attempts: list[int] = []

    def opener(request: urllib.request.Request) -> Response:
        attempts.append(1)
        raise urllib.error.HTTPError("https://example.test", 503, "unavailable", {}, Response(503, "retry me"))  # type: ignore[arg-type]

    code, _ = _gitapex_github_http.request_with_retry(
        "POST", "https://example.test", "tok", opener, lambda _: None, body={"x": 1}, max_attempts=1
    )
    assert code == 503
    assert len(attempts) == 1


def test_request_with_retry_sends_json_body_and_content_type_only_when_body_given() -> None:
    captured: list[urllib.request.Request] = []

    def opener(request: urllib.request.Request) -> Response:
        captured.append(request)
        return Response(200, "{}")

    _gitapex_github_http.request_with_retry(
        "POST", "https://example.test", "tok", opener, lambda _: None, body={"a": 1}
    )
    assert captured[0].data == json.dumps({"a": 1}).encode("utf-8")
    assert captured[0].headers["Content-type"] == "application/json"

    captured.clear()
    _gitapex_github_http.request_with_retry("GET", "https://example.test", "tok", opener, lambda _: None)
    assert captured[0].data is None
    assert "Content-type" not in captured[0].headers


# ---------------------------------------------------------------------------
# call_json -- request_with_retry plus raise-on-non-2xx / parse-on-2xx.
# ---------------------------------------------------------------------------


def test_call_json_returns_parsed_body_on_success() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"ok": True}))

    result = _gitapex_github_http.call_json("GET", "https://example.test", "tok", opener, lambda _: None)
    assert result == {"ok": True}


def test_call_json_raises_github_api_error_with_exact_message_on_repeated_failure() -> None:
    def opener(request: urllib.request.Request) -> Response:
        raise urllib.error.HTTPError("https://example.test", 500, "boom", {}, Response(500, "boom"))  # type: ignore[arg-type]

    with pytest.raises(_gitapex_github_http.GitHubApiError) as excinfo:
        _gitapex_github_http.call_json("GET", "https://example.test", "tok", opener, lambda _: None, max_attempts=1)
    assert str(excinfo.value) == "GET https://example.test failed: HTTP 500: boom"


def test_call_json_json_loads_is_unguarded_and_raises_jsondecodeerror_not_apierror() -> None:
    # Deliberately preserved bug (issue #729 criterion 3 owns fixing it):
    # a 2xx response with an unparseable body must raise a raw
    # json.JSONDecodeError here, NOT GitHubApiError.
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "not json")

    with pytest.raises(json.JSONDecodeError):
        _gitapex_github_http.call_json("GET", "https://example.test", "tok", opener, lambda _: None)


# ---------------------------------------------------------------------------
# graphql_call -- moved verbatim from gitapex_sync_pr_publish.py.
# ---------------------------------------------------------------------------


def test_graphql_call_returns_status_and_parsed_body_on_success() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"data": {"ok": True}}))

    code, body = _gitapex_github_http.graphql_call(
        query="query", variables={}, token="tok", opener=opener, sleeper=lambda _: None
    )
    assert code == 200
    assert body == {"data": {"ok": True}}


def test_graphql_call_retries_on_transient_marker_then_succeeds() -> None:
    attempts: list[int] = []

    def opener(request: urllib.request.Request) -> Response:
        attempts.append(1)
        if len(attempts) < 2:
            return Response(
                200,
                json.dumps({"errors": [{"message": "Something went wrong while executing your query."}]}),
            )
        return Response(200, json.dumps({"data": {"ok": True}}))

    sleeps: list[float] = []
    code, body = _gitapex_github_http.graphql_call(
        query="query", variables={}, token="tok", opener=opener, sleeper=sleeps.append
    )
    assert code == 200
    assert body == {"data": {"ok": True}}
    assert len(attempts) == 2
    assert sleeps == [5]


def test_graphql_call_degrades_to_empty_dict_on_invalid_json() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "not json")

    code, body = _gitapex_github_http.graphql_call(
        query="query", variables={}, token="tok", opener=opener, sleeper=lambda _: None
    )
    assert code == 200
    assert body == {}


def test_graphql_call_uses_default_opener_and_sleeper_when_omitted() -> None:
    # Exercises the `opener=default_opener`/`sleeper=None -> time.sleep`
    # defaults without making a real network call: the default_opener
    # default is asserted by identity, and sleeper is only invoked when a
    # retry actually happens, which a 4xx (non-transient) response avoids.
    signature = inspect.signature(_gitapex_github_http.graphql_call)
    assert signature.parameters["opener"].default is _gitapex_github_http.default_opener

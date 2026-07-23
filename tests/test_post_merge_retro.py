"""Tests for the post-merge-auto-retro minimal slice
(.github/scripts/post_merge_retro.py).

Refs #314 (sub-issue of #140): opens (with dedup) a `Merge retrospective:
PR #N` issue, labeled `retrospective`, when a PR merges.

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring
test_scan_retrospective_gate_drift.py's own fixture style.
"""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request

import post_merge_retro as pmr
import pytest


class Response:
    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self.body = body.encode()

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        return None


def http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test", code, "err", {}, Response(code, body))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# dedup_query
# ---------------------------------------------------------------------------


def test_dedup_query_matches_creation_identity_predicate():
    query = pmr.dedup_query("tvna", "gitapex", 314)
    assert query == (
        'repo:tvna/gitapex type:issue in:title "Merge retrospective: PR #314" '
        "label:retrospective"
    )


# ---------------------------------------------------------------------------
# find_existing_retro_issue
# ---------------------------------------------------------------------------


def test_find_existing_retro_issue_returns_number_when_found():
    def opener(request: urllib.request.Request) -> Response:
        assert request.headers["Authorization"] == "Bearer tok"
        assert "search/issues" in request.full_url
        return Response(200, json.dumps({"total_count": 1, "items": [{"number": 42}]}))

    result = pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener)
    assert result == 42


def test_find_existing_retro_issue_returns_none_when_no_match():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"total_count": 0, "items": []}))

    result = pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener)
    assert result is None


def test_find_existing_retro_issue_retries_5xx_then_succeeds():
    responses = [http_error(503, "{}"), Response(200, json.dumps({"items": []}))]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    result = pmr.find_existing_retro_issue(
        "tvna", "gitapex", 314, "tok", opener=opener, sleeper=sleeps.append
    )
    assert result is None
    assert sleeps == [5]


def test_find_existing_retro_issue_raises_on_persistent_4xx():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(422, "unprocessable")

    with pytest.raises(pmr.GitHubApiError):
        pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener)


def test_find_existing_retro_issue_raises_after_repeated_network_failure():
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    with pytest.raises(pmr.GitHubApiError):
        pmr.find_existing_retro_issue(
            "tvna", "gitapex", 314, "tok", opener=opener, sleeper=lambda _: None
        )
    assert calls == 3


def test_find_existing_retro_issue_retries_incomplete_body_read_then_succeeds():
    class FlakyResponse(Response):
        def read(self) -> bytes:
            raise http.client.IncompleteRead(b"partial")

    responses = [FlakyResponse(200), Response(200, json.dumps({"items": []}))]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    result = pmr.find_existing_retro_issue(
        "tvna", "gitapex", 314, "tok", opener=opener, sleeper=sleeps.append
    )
    assert result is None
    assert sleeps == [5]


# ---------------------------------------------------------------------------
# open_retro_issue
# ---------------------------------------------------------------------------


def test_open_retro_issue_posts_expected_title_and_label():
    captured: dict = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, json.dumps({"number": 99}))

    result = pmr.open_retro_issue(
        "tvna", "gitapex", 314, "feat: thing", "https://github.com/tvna/gitapex/pull/314", "tok", opener=opener
    )
    assert result == 99
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/issues"
    assert captured["payload"]["title"] == "Merge retrospective: PR #314"
    assert captured["payload"]["labels"] == ["retrospective"]
    assert "#314" in captured["payload"]["body"]


def test_open_retro_issue_never_republishes_the_untrusted_pr_title():
    """A fork-controlled PR title (with an @mention / Markdown) must never
    reach the issue body -- see the mention/markdown-injection finding."""
    captured: dict = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, json.dumps({"number": 99}))

    pmr.open_retro_issue(
        "tvna",
        "gitapex",
        314,
        "@evil-org/team please **look** at this",
        "https://github.com/tvna/gitapex/pull/314",
        "tok",
        opener=opener,
    )
    assert "@evil-org/team" not in captured["payload"]["body"]
    assert "**look**" not in captured["payload"]["body"]


def test_open_retro_issue_raises_on_api_error():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "server error")

    with pytest.raises(pmr.GitHubApiError):
        pmr.open_retro_issue(
            "tvna", "gitapex", 314, "t", "u", "tok", opener=opener, sleeper=lambda _: None
        )


def test_open_retro_issue_does_not_retry_the_non_idempotent_post():
    """Issue creation must not be blindly retried: a lost/truncated
    response after GitHub already created the issue would otherwise
    retry into a duplicate."""
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise http_error(503, "server error")

    with pytest.raises(pmr.GitHubApiError):
        pmr.open_retro_issue(
            "tvna", "gitapex", 314, "t", "u", "tok", opener=opener, sleeper=lambda _: None
        )
    assert calls == 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_exits_one_on_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"]) == 1


def test_main_skips_create_when_dedup_finds_existing(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(pmr, "find_existing_retro_issue", lambda *a, **k: 7)

    def fail_if_called(*a, **k):
        raise AssertionError("open_retro_issue should not be called when a dup exists")

    monkeypatch.setattr(pmr, "open_retro_issue", fail_if_called)
    exit_code = pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 0
    assert "already exists" in capsys.readouterr().out


def test_main_opens_issue_when_no_existing_found(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(pmr, "find_existing_retro_issue", lambda *a, **k: None)
    monkeypatch.setattr(pmr, "open_retro_issue", lambda *a, **k: 55)
    exit_code = pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 0
    assert "Opened retrospective issue #55" in capsys.readouterr().out


def test_main_exits_one_on_github_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*a, **k):
        raise pmr.GitHubApiError("boom")

    monkeypatch.setattr(pmr, "find_existing_retro_issue", raise_api_error)
    assert pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"]) == 1

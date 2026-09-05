"""Tests for .github/scripts/gitapex_isolation_registry_open_contamination_issue.py
(issue #1809, Step 8 follow-up).

Replaces the workflow's own former raw `gh issue create` call with this
repository's established REST-wrapper convention -- see that script's own
module docstring for the full rationale. No test here makes a real network
call -- the network layer is exercised through an injected `opener`,
mirroring tests/test_gitapex_post_merge_retro.py's own fixture style.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import gitapex_isolation_registry_open_contamination_issue as oci
import pytest


def _payload(request: urllib.request.Request) -> Any:
    assert isinstance(request.data, bytes)
    return json.loads(request.data.decode())


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


def http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test", code, "err", {}, Response(code, body))  # type: ignore[arg-type]


def test_open_contamination_issue_posts_expected_title_and_label() -> None:
    captured: dict[str, Any] = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = _payload(request)
        return Response(201, json.dumps({"number": 99}))

    result = oci.open_contamination_issue(
        "tvna", "gitapex", "https://github.com/tvna/gitapex/actions/runs/1", "tok", opener=opener
    )

    assert result == 99
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/issues"
    assert captured["payload"]["labels"] == ["bug"]
    assert "possible new contamination pattern found" in captured["payload"]["title"]
    assert "https://github.com/tvna/gitapex/actions/runs/1" in captured["payload"]["body"]


def test_open_contamination_issue_raises_on_api_error() -> None:
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "server error")

    with pytest.raises(oci.GitHubApiError):
        oci.open_contamination_issue("tvna", "gitapex", "u", "tok", opener=opener, sleeper=lambda _: None)


def test_open_contamination_issue_does_not_retry_the_non_idempotent_post() -> None:
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise http_error(503, "server error")

    with pytest.raises(oci.GitHubApiError):
        oci.open_contamination_issue("tvna", "gitapex", "u", "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 1


def test_main_exits_one_on_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert oci.main(["--owner", "tvna", "--repo", "gitapex", "--run-url", "u"]) == 1


def test_main_opens_issue(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(oci, "open_contamination_issue", lambda *a, **k: 55)

    exit_code = oci.main(["--owner", "tvna", "--repo", "gitapex", "--run-url", "u"])

    assert exit_code == 0
    assert "Opened contamination-finding issue #55" in capsys.readouterr().out


def test_main_exits_one_on_github_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_error(*a: object, **k: object) -> int:
        raise oci.GitHubApiError("boom")

    monkeypatch.setattr(oci, "open_contamination_issue", raise_error)

    assert oci.main(["--owner", "tvna", "--repo", "gitapex", "--run-url", "u"]) == 1

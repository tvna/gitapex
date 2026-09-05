"""Tests for .github/scripts/gitapex_isolation_registry_propose_pr.py
(issue #1809, Step 8 follow-up).

Replaces the workflow's own former raw `gh pr create` call with this
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

import gitapex_isolation_registry_propose_pr as pp
import pytest
from conftest import Response, http_error, payload_of


def test_propose_registry_pr_posts_expected_head_and_base() -> None:
    captured: dict[str, Any] = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = payload_of(request)
        return Response(201, json.dumps({"number": 42}))

    result = pp.propose_registry_pr(
        "tvna",
        "gitapex",
        "isolation-registry-refresh/2026-09-05-1",
        "main",
        "https://github.com/tvna/gitapex/actions/runs/1",
        "tok",
        opener=opener,
    )

    assert result == 42
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/pulls"
    assert captured["payload"]["head"] == "isolation-registry-refresh/2026-09-05-1"
    assert captured["payload"]["base"] == "main"
    assert "https://github.com/tvna/gitapex/actions/runs/1" in captured["payload"]["body"]


def test_propose_registry_pr_raises_on_api_error() -> None:
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "server error")

    with pytest.raises(pp.GitHubApiError):
        pp.propose_registry_pr("tvna", "gitapex", "h", "main", "u", "tok", opener=opener, sleeper=lambda _: None)


def test_propose_registry_pr_does_not_retry_the_non_idempotent_post() -> None:
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise http_error(503, "server error")

    with pytest.raises(pp.GitHubApiError):
        pp.propose_registry_pr("tvna", "gitapex", "h", "main", "u", "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 1


def test_main_exits_one_on_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert pp.main(["--owner", "tvna", "--repo", "gitapex", "--head", "h", "--base", "main", "--run-url", "u"]) == 1


def test_main_opens_pr(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(pp, "propose_registry_pr", lambda *a, **k: 7)

    exit_code = pp.main(["--owner", "tvna", "--repo", "gitapex", "--head", "h", "--base", "main", "--run-url", "u"])

    assert exit_code == 0
    assert "Opened PR #7" in capsys.readouterr().out


def test_main_exits_one_on_github_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_error(*a: object, **k: object) -> int:
        raise pp.GitHubApiError("boom")

    monkeypatch.setattr(pp, "propose_registry_pr", raise_error)

    assert pp.main(["--owner", "tvna", "--repo", "gitapex", "--head", "h", "--base", "main", "--run-url", "u"]) == 1


def test_main_rejects_blank_head(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # argparse's own required=True only guarantees the flag was passed, not
    # that its value is non-empty -- the pydantic model must reject this
    # before it ever reaches a GitHub API URL.
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    exit_code = pp.main(["--owner", "tvna", "--repo", "gitapex", "--head", " ", "--base", "main", "--run-url", "u"])

    assert exit_code == 1
    assert "--head" in capsys.readouterr().err

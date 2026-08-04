"""Tests for the stale-retro-stub auto-close script
(.github/scripts/stale_retro_stub_autoclose.py).

Refs #694 (completing #314/#140's post-merge-auto-retro gate cluster):
closes open `retrospective`-labelled issues whose body still carries
post_merge_retro.py's own unenriched-stub marker text and whose
`created_at` is older than the stale-hours threshold (default 48),
posting an explanatory comment on every close.

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring
test_post_merge_retro.py's own fixture style.
"""

from __future__ import annotations

import http.client
import json
import pathlib
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest
import stale_retro_stub_autoclose as sra
import yaml


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


NOW = datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC)
STUB_BODY = (
    "Retrospective for PR #314.\n\nRefs #314\n\n"
    "Automated stub opened by the post-merge-auto-retro gate "
    "(issue #314, minimal slice of #140). This slice only opens and dedups."
)
ENRICHED_BODY = "## Repairs\n\n1. [Fixed lint] ...\n   Classification: missing deterministic gate."


# ---------------------------------------------------------------------------
# is_unenriched_stub
# ---------------------------------------------------------------------------


def test_is_unenriched_stub_true_when_marker_present():
    assert sra.is_unenriched_stub(STUB_BODY) is True


def test_is_unenriched_stub_false_when_already_enriched():
    assert sra.is_unenriched_stub(ENRICHED_BODY) is False


def test_is_unenriched_stub_false_on_none_body():
    assert sra.is_unenriched_stub(None) is False


# ---------------------------------------------------------------------------
# is_stale
# ---------------------------------------------------------------------------


def test_is_stale_true_when_older_than_threshold():
    created = (NOW - timedelta(hours=49)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert sra.is_stale(created, NOW, 48) is True


def test_is_stale_false_when_younger_than_threshold():
    created = (NOW - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert sra.is_stale(created, NOW, 48) is False


def test_is_stale_true_at_exact_boundary():
    created = (NOW - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert sra.is_stale(created, NOW, 48) is True


# ---------------------------------------------------------------------------
# find_stale_stub_issues
# ---------------------------------------------------------------------------


def _issue(number: int, body: str, hours_old: float) -> dict:
    return {
        "number": number,
        "body": body,
        "created_at": (NOW - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def test_find_stale_stub_issues_filters_on_both_conditions():
    issues = [
        _issue(1, STUB_BODY, 49),  # stale + unenriched -> match
        _issue(2, STUB_BODY, 10),  # unenriched but fresh -> no match
        _issue(3, ENRICHED_BODY, 49),  # stale but enriched -> no match
        _issue(4, ENRICHED_BODY, 10),  # neither -> no match
    ]
    result = sra.find_stale_stub_issues(issues, NOW, 48)
    assert [i["number"] for i in result] == [1]


def test_find_stale_stub_issues_returns_empty_for_no_matches():
    issues = [_issue(2, STUB_BODY, 1)]
    assert sra.find_stale_stub_issues(issues, NOW, 48) == []


# ---------------------------------------------------------------------------
# format_close_comment / format_report
# ---------------------------------------------------------------------------


def test_format_close_comment_names_threshold_and_reopen_path():
    comment = sra.format_close_comment(48)
    assert "48 hours" in comment
    assert "merge-retrospective" in comment
    assert "reopen" in comment


def test_format_report_empty():
    assert "No stale" in sra.format_report([])


def test_format_report_lists_closed_numbers():
    report = sra.format_report([3, 1])
    assert "#1" in report
    assert "#3" in report
    assert "2" in report  # count


# ---------------------------------------------------------------------------
# list_open_retro_issues
# ---------------------------------------------------------------------------


def test_list_open_retro_issues_requests_open_state_and_label():
    def opener(request: urllib.request.Request) -> Response:
        assert "labels=retrospective" in request.full_url
        assert "state=open" in request.full_url
        return Response(200, json.dumps([]))

    result = sra.list_open_retro_issues("tvna", "gitapex", "tok", opener=opener)
    assert result == []


def test_list_open_retro_issues_excludes_pull_requests():
    def opener(request: urllib.request.Request) -> Response:
        return Response(
            200,
            json.dumps(
                [{"number": 1, "body": "x", "created_at": "2026-01-01T00:00:00Z"}, {"number": 2, "pull_request": {}}]
            ),
        )

    result = sra.list_open_retro_issues("tvna", "gitapex", "tok", opener=opener)
    assert [i["number"] for i in result] == [1]


def test_list_open_retro_issues_paginates():
    page1 = [{"number": n, "body": "", "created_at": "2026-01-01T00:00:00Z"} for n in range(100)]
    page2 = [{"number": 100, "body": "", "created_at": "2026-01-01T00:00:00Z"}]
    pages = [page1, page2]

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(pages.pop(0)))

    result = sra.list_open_retro_issues("tvna", "gitapex", "tok", opener=opener, sleeper=lambda _: None)
    assert len(result) == 101


def test_list_open_retro_issues_retries_5xx_then_succeeds():
    responses = [http_error(503, "{}"), Response(200, json.dumps([]))]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    result = sra.list_open_retro_issues("tvna", "gitapex", "tok", opener=opener, sleeper=sleeps.append)
    assert result == []
    assert sleeps == [5]


def test_list_open_retro_issues_raises_on_persistent_4xx():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(422, "unprocessable")

    with pytest.raises(sra.GitHubApiError):
        sra.list_open_retro_issues("tvna", "gitapex", "tok", opener=opener, sleeper=lambda _: None)


def test_list_open_retro_issues_raises_after_repeated_network_failure():
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    with pytest.raises(sra.GitHubApiError):
        sra.list_open_retro_issues("tvna", "gitapex", "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 3


def test_list_open_retro_issues_retries_incomplete_body_read_then_succeeds():
    class FlakyResponse(Response):
        def read(self) -> bytes:
            raise http.client.IncompleteRead(b"partial")

    responses = [FlakyResponse(200), Response(200, json.dumps([]))]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    result = sra.list_open_retro_issues("tvna", "gitapex", "tok", opener=opener, sleeper=sleeps.append)
    assert result == []
    assert sleeps == [5]


# ---------------------------------------------------------------------------
# close_stub_issue
# ---------------------------------------------------------------------------


def test_close_stub_issue_comments_before_closing():
    calls: list[tuple] = []

    def opener(request: urllib.request.Request) -> Response:
        calls.append((request.get_method(), request.full_url, request.data))
        if request.get_method() == "POST":
            return Response(201, json.dumps({"id": 1}))
        return Response(200, json.dumps({"number": 314, "state": "closed"}))

    sra.close_stub_issue("tvna", "gitapex", 314, 48, "tok", opener=opener, sleeper=lambda _: None)

    assert calls[0][0] == "POST"
    assert calls[0][1] == "https://api.github.com/repos/tvna/gitapex/issues/314/comments"
    comment_payload = json.loads(calls[0][2].decode())
    assert "48 hours" in comment_payload["body"]

    assert calls[1][0] == "PATCH"
    assert calls[1][1] == "https://api.github.com/repos/tvna/gitapex/issues/314"
    patch_payload = json.loads(calls[1][2].decode())
    assert patch_payload["state"] == "closed"


def test_close_stub_issue_raises_on_comment_failure_without_closing():
    calls: list[str] = []

    def opener(request: urllib.request.Request) -> Response:
        calls.append(request.get_method())
        raise http_error(500, "server error")

    with pytest.raises(sra.GitHubApiError):
        sra.close_stub_issue("tvna", "gitapex", 314, 48, "tok", opener=opener, sleeper=lambda _: None)
    assert calls.count("PATCH") == 0


def test_close_stub_issue_raises_immediately_on_persistent_4xx():
    calls: list[str] = []

    def opener(request: urllib.request.Request) -> Response:
        calls.append(request.get_method())
        raise http_error(422, "unprocessable")

    with pytest.raises(sra.GitHubApiError):
        sra.close_stub_issue("tvna", "gitapex", 314, 48, "tok", opener=opener, sleeper=lambda _: None)
    assert calls == ["POST"]


def test_close_stub_issue_does_not_retry_the_non_idempotent_comment_post():
    """The comment POST is not idempotent: a lost/truncated response after
    GitHub already created the comment must never be retried into a
    duplicate -- mirrors post_merge_retro.py's own
    test_open_retro_issue_does_not_retry_the_non_idempotent_post."""
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise http_error(503, "server error")

    with pytest.raises(sra.GitHubApiError):
        sra.close_stub_issue("tvna", "gitapex", 314, 48, "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 1


def test_close_stub_issue_patch_close_still_retries_5xx_then_succeeds():
    """The PATCH close is naturally idempotent and keeps the default retry
    count, unlike the comment POST above."""
    responses = [Response(201, "{}"), http_error(503, "{}"), Response(200, "{}")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    sra.close_stub_issue("tvna", "gitapex", 314, 48, "tok", opener=opener, sleeper=sleeps.append)
    assert sleeps == [5]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_exits_one_on_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert sra.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_rejects_blank_owner(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = sra.main(["--owner", "", "--repo", "gitapex"])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_blank_repo(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = sra.main(["--owner", "tvna", "--repo", ""])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_non_positive_stale_hours(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = sra.main(["--owner", "tvna", "--repo", "gitapex", "--stale-hours", "0"])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_closes_stale_issues_and_reports(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(sra, "list_open_retro_issues", lambda *a, **k: [_issue(314, STUB_BODY, 49)])
    closed: list[int] = []
    monkeypatch.setattr(
        sra, "close_stub_issue", lambda owner, repo, number, stale_hours, token, **k: closed.append(number)
    )
    exit_code = sra.main(["--owner", "tvna", "--repo", "gitapex", "--stale-hours", "48"])
    assert exit_code == 0
    assert closed == [314]
    assert "#314" in capsys.readouterr().out


def test_main_skips_fresh_or_enriched_issues(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(
        sra,
        "list_open_retro_issues",
        lambda *a, **k: [_issue(1, STUB_BODY, 1), _issue(2, ENRICHED_BODY, 49)],
    )

    def fail_if_called(*a, **k):
        raise AssertionError("close_stub_issue should not be called")

    monkeypatch.setattr(sra, "close_stub_issue", fail_if_called)
    exit_code = sra.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    assert "No stale" in capsys.readouterr().out


def test_main_exits_one_on_github_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*a, **k):
        raise sra.GitHubApiError("boom")

    monkeypatch.setattr(sra, "list_open_retro_issues", raise_api_error)
    assert sra.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


# ---------------------------------------------------------------------------
# Marker drift gate: _STUB_MARKER is a literal copy of the phrase
# post_merge_retro.py's own open_retro_issue embeds in every stub body, not
# an import (this repo keeps .github/scripts/*.py files independent of one
# another) -- assert directly against that module's source so the two
# cannot silently re-diverge the way the title/query pair did before #341.
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_stub_marker_matches_post_merge_retro_source():
    source = (REPO_ROOT / ".github" / "scripts" / "post_merge_retro.py").read_text(encoding="utf-8")
    assert sra._STUB_MARKER in source


# ---------------------------------------------------------------------------
# Drift gate: the new workflow's own "permanent human-review-of-merge"
# posture must hold the same way post-merge-retro.yml's own does -- see
# test_post_merge_retro.py's identical guard for that workflow.
# ---------------------------------------------------------------------------

WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "stale-retro-stub-autoclose.yml"

_MERGE_CAPABLE_MARKERS = (
    "gh pr merge",
    "gh pr merge --auto",
    "merge_pull_request",
    "enable_pr_auto_merge",
    "/merge",
    "pulls/merge",
)


def _load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _iter_permissions_blocks(workflow):
    top_level = workflow.get("permissions")
    if top_level is not None:
        yield "top-level", top_level
    for job_name, job in (workflow.get("jobs") or {}).items():
        job_permissions = job.get("permissions")
        if job_permissions is not None:
            yield f"job:{job_name}", job_permissions


def test_workflow_file_exists_and_parses():
    assert WORKFLOW_PATH.is_file(), f"expected {WORKFLOW_PATH} to exist"
    workflow = _load_workflow()
    assert workflow.get("jobs"), f"{WORKFLOW_PATH} has no jobs -- parse likely broke"


def test_workflow_never_grants_pull_requests_write():
    workflow = _load_workflow()
    offenders = []
    for scope_name, permissions in _iter_permissions_blocks(workflow):
        if not isinstance(permissions, dict):
            offenders.append((scope_name, permissions))
            continue
        pr_permission = permissions.get("pull-requests")
        if pr_permission is not None and pr_permission != "read" and pr_permission != "none":
            offenders.append((scope_name, permissions))
    assert not offenders, (
        f"{WORKFLOW_PATH} grants pull-requests write (or an unparseable blanket "
        f"permission) in: {offenders} -- this workflow may only ever comment on "
        "and close a stale stub issue; a merge-capable permission here would "
        "violate this repository's permanent human-review-of-merge posture."
    )


def test_workflow_has_no_merge_capable_step():
    workflow = _load_workflow()
    offenders = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            haystack = " ".join(str(step.get(key, "")) for key in ("run", "uses", "with")).lower()
            hits = [marker for marker in _MERGE_CAPABLE_MARKERS if marker in haystack]
            if hits:
                offenders.append((job_name, step.get("name", "<unnamed step>"), hits))
    assert not offenders, (
        f"{WORKFLOW_PATH} has a step that looks merge-capable: {offenders} -- this "
        "repository's 100% human review of merges is a permanent architectural "
        "feature; this workflow may never merge a pull request itself."
    )

"""Tests for the retrospective gate-drift meta-check
(.github/scripts/scan_retrospective_gate_drift.py).

Refs #297 (refs #187, #242, #246): this script mechanizes
merge-retrospective's Step 0 (find retrospective-labelled issues with no
citing commit on main) and fails CI when the count exceeds a threshold.

No test in this file makes a real network or subprocess call -- the
network layer is exercised through an injected `opener`, and the git
layer through an injected `runner`, mirroring test_sync_pr_publish.py's
own fixture style.
"""

from __future__ import annotations

import http.client
import subprocess
import urllib.error
import urllib.request

import pytest
import scan_retrospective_gate_drift as gate


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


# ---------------------------------------------------------------------------
# citation_count / find_no_citation_issues
# ---------------------------------------------------------------------------


def test_citation_count_matches_bare_hash_number():
    assert gate.citation_count(["fix(gate): close gaps (Refs #187)"], 187) == 1


def test_citation_count_matches_multiple_bracketed_citations_in_one_message():
    message = "docs(skills): re-escalate (refs #242, #246)"
    assert gate.citation_count([message], 242) == 1
    assert gate.citation_count([message], 246) == 1


def test_citation_count_does_not_match_longer_number_containing_target_as_prefix():
    assert gate.citation_count(["Refs #1870"], 187) == 0


def test_citation_count_does_not_match_longer_number_containing_target_as_suffix():
    assert gate.citation_count(["Refs #2187"], 187) == 0


def test_citation_count_sums_across_multiple_citing_commits():
    messages = ["feat: a (Refs #242)", "fix: b (Refs #242)", "chore: c"]
    assert gate.citation_count(messages, 242) == 2


def test_citation_count_zero_when_no_commit_cites_it():
    assert gate.citation_count(["chore: unrelated"], 118) == 0


def test_find_no_citation_issues_returns_only_uncited_numbers():
    messages = ["Refs #242", "Refs #187"]
    assert gate.find_no_citation_issues([242, 187, 118], messages) == [118]


def test_find_no_citation_issues_empty_when_all_cited():
    messages = ["Refs #1", "Refs #2"]
    assert gate.find_no_citation_issues([1, 2], messages) == []


# ---------------------------------------------------------------------------
# evaluate / format_report
# ---------------------------------------------------------------------------


def test_evaluate_false_when_count_equals_threshold():
    assert gate.evaluate(20, 20) is False


def test_evaluate_true_when_count_exceeds_threshold():
    assert gate.evaluate(21, 20) is True


def test_evaluate_false_when_count_below_threshold():
    assert gate.evaluate(5, 20) is False


def test_format_report_lists_no_citation_issues_and_passes():
    report = gate.format_report([118, 191], 22, 20)
    assert "2 of 22" in report
    assert "#118" in report
    assert "#191" in report
    assert "PASS" in report


def test_format_report_fails_when_over_threshold():
    report = gate.format_report(list(range(21)), 22, 20)
    assert "FAIL" in report


def test_format_report_empty_backlog_states_every_issue_cited():
    report = gate.format_report([], 4, 20)
    assert "Every" in report
    assert "PASS" in report


# ---------------------------------------------------------------------------
# list_labelled_issues
# ---------------------------------------------------------------------------


def test_list_labelled_issues_single_page():
    page = [{"number": 118}, {"number": 187}]

    def opener(request: urllib.request.Request) -> Response:
        assert request.headers["Authorization"] == "Bearer tok"
        return Response(200, __import__("json").dumps(page))

    result = gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener)
    assert result == [118, 187]


def test_list_labelled_issues_paginates_until_short_page():
    full_page = [{"number": n} for n in range(100)]
    short_page = [{"number": 999}]
    pages = [full_page, short_page]

    def opener(request: urllib.request.Request) -> Response:
        page_data = pages.pop(0)
        return Response(200, __import__("json").dumps(page_data))

    result = gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener)
    assert result == [n for n in range(100)] + [999]


def test_list_labelled_issues_stops_on_empty_page():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "[]")

    result = gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener)
    assert result == []


def test_list_labelled_issues_excludes_pull_requests():
    page = [{"number": 1, "pull_request": {}}, {"number": 2}]

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, __import__("json").dumps(page))

    result = gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener)
    assert result == [2]


def test_list_labelled_issues_retries_5xx_then_succeeds():
    responses = [http_error(503, "["), Response(200, "[]")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    result = gate.list_labelled_issues(
        "tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=sleeps.append
    )
    assert result == []
    assert sleeps == [5]


def test_list_labelled_issues_raises_on_persistent_4xx():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(404, "not found")

    with pytest.raises(gate.GitHubApiError):
        gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener)


def test_list_labelled_issues_retries_incomplete_body_read_then_succeeds():
    # Headers arrive (status set) but the body read itself fails -- not an
    # HTTPError or URLError, so it must still hit the retry path rather
    # than escaping uncaught.
    class FlakyResponse(Response):
        def read(self) -> bytes:
            raise http.client.IncompleteRead(b"partial")

    responses = [FlakyResponse(200), Response(200, "[]")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    result = gate.list_labelled_issues(
        "tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=sleeps.append
    )
    assert result == []
    assert sleeps == [5]


def test_list_labelled_issues_retries_body_read_timeout_then_succeeds():
    class TimingOutResponse(Response):
        def read(self) -> bytes:
            raise TimeoutError("timed out")

    responses = [TimingOutResponse(200), Response(200, "[]")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    result = gate.list_labelled_issues(
        "tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=sleeps.append
    )
    assert result == []
    assert sleeps == [5]


def test_list_labelled_issues_raises_after_repeated_network_failure():
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    with pytest.raises(gate.GitHubApiError):
        gate.list_labelled_issues(
            "tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=lambda _: None
        )
    assert calls == 3


# ---------------------------------------------------------------------------
# git_commit_messages
# ---------------------------------------------------------------------------


def _fake_runner(stdout: str, returncode: int = 0, stderr: str = ""):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    return runner


def test_git_commit_messages_parses_multiple_commits():
    raw = (
        "\x1eaaa\x1fMerge pull request #292\n\nfeat(skill): add thing\n"
        "\x1ebbb\x1ffeat(skill): adversarial-hardening round\n"
    )
    runner = _fake_runner(raw)
    messages = gate.git_commit_messages("HEAD", ".", runner=runner)
    assert messages == [
        "Merge pull request #292\n\nfeat(skill): add thing",
        "feat(skill): adversarial-hardening round",
    ]


def test_git_commit_messages_handles_empty_body():
    raw = "\x1eaaa\x1fchore: typo\n"
    runner = _fake_runner(raw)
    assert gate.git_commit_messages("HEAD", ".", runner=runner) == ["chore: typo"]


def test_git_commit_messages_empty_log():
    runner = _fake_runner("")
    assert gate.git_commit_messages("HEAD", ".", runner=runner) == []


def test_git_commit_messages_raises_on_nonzero_exit():
    runner = _fake_runner("", returncode=128, stderr="unknown revision")
    with pytest.raises(gate.GitLogError):
        gate.git_commit_messages("bad-ref", ".", runner=runner)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_exits_zero_when_count_at_threshold(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: [1, 2])
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: ["Refs #1", "Refs #2"])
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "0"])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_exits_one_when_count_exceeds_threshold(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: [1, 2, 3])
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "1"])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_exits_one_on_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_github_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*a, **k):
        raise gate.GitHubApiError("boom")

    monkeypatch.setattr(gate, "list_labelled_issues", raise_api_error)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_git_log_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: [1])

    def raise_git_error(*a, **k):
        raise gate.GitLogError("boom")

    monkeypatch.setattr(gate, "git_commit_messages", raise_git_error)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_uses_default_threshold_when_unspecified(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: list(range(18)))
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    assert f"threshold: {gate.DEFAULT_THRESHOLD}" in capsys.readouterr().out

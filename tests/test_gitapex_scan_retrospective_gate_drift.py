"""Tests for the retrospective gate-drift meta-check
(.github/scripts/gitapex_scan_retrospective_gate_drift.py).

Refs #1406 (refs #297, #187, #242, #246, #709): this script audits the
`gate-proposal` label the flat gate-proposal-issues design
(docs/superpowers/specs/2026-08-29-flat-gate-proposal-issues-design.md)
introduces -- a label-liveness guard, a threshold-gated open-issue-count
report, and an unbounded zero-tolerance integrity pass over every closed
labelled issue (the existing two-signal check, issue #709, re-run over
that narrower set instead of the prior full `retrospective`-label sweep).

No test in this file makes a real network or subprocess call -- the
network layer is exercised through an injected `opener`, and the git
layer through an injected `runner`, mirroring test_gitapex_sync_pr_publish.py's
own fixture style.
"""

from __future__ import annotations

import http.client
import json
import pathlib
import subprocess
import urllib.error
import urllib.request

import gitapex_scan_retrospective_gate_drift as gate
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


def http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test", code, "err", {}, Response(code, body))  # type: ignore[arg-type]


def _url_capturing_opener(captured: dict, body: str = "[]"):
    """An `opener` that records the request URL under `captured["url"]` and
    answers 200 with `body`. Shared by every test below whose only subject
    is the URL a fetch helper builds (which label it quotes, which `state=`
    it asks for) rather than the response it gets back."""

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        return Response(200, body)

    return opener


# ---------------------------------------------------------------------------
# citation_count / find_no_citation_issues (issue #709's two-signal check --
# unchanged logic, now reused by the closed-issue integrity pass below)
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
    assert gate.find_no_citation_issues([242, 187, 118], messages, {242, 187, 118}) == [118]


def test_find_no_citation_issues_empty_when_all_cited():
    messages = ["Refs #1", "Refs #2"]
    assert gate.find_no_citation_issues([1, 2], messages, {1, 2}) == []


# ---------------------------------------------------------------------------
# find_no_citation_issues: corroborating-signal cases (issue #709)
# ---------------------------------------------------------------------------


def test_find_no_citation_issues_keeps_issue_314_shape_when_citing_commit_lacks_corroboration():
    # Reproduces #314's real false negative: a66ccbc cited "#314" while
    # changing an unrelated workflow comment/doc, and no ssot.json gate
    # was ever registered with tracking_issue == 314.
    messages = ["chore(gates): document budget caps and permanent human-review-of-merge (#318)"]
    assert gate.find_no_citation_issues([314], ["Refs #314", *messages], set()) == [314]


def test_find_no_citation_issues_keeps_multi_proposal_issue_665_shape_when_only_one_subproposal_has_a_tracking_entry():
    # Reproduces #665's real false negative: PR #703's commits cited
    # "refs #665 repair 6" (repair 6 landed as the hidden-characters gate,
    # tracking_issue 702 -- not 665), while #665's other three proposed
    # repairs (2, 3, 4) remain unimplemented. 665 itself must stay
    # uncleared even though a commit cites it.
    messages = ["feat(ci): add a repository-wide hidden-character gate (refs #665 repair 6)"]
    assert gate.find_no_citation_issues([665], messages, {702}) == [665]


def test_find_no_citation_issues_clears_when_citation_and_tracking_issue_both_present():
    # Guards the opposite regression: a genuine single-proposal, citing +
    # registry-backed issue must still clear normally.
    messages = ["fix(gates): close gaps (Refs #650)"]
    assert gate.find_no_citation_issues([650], messages, {650}) == []


# ---------------------------------------------------------------------------
# evaluate / format_open_count_report (pass (a): threshold-gated open count)
# ---------------------------------------------------------------------------


def test_evaluate_false_when_count_equals_threshold():
    assert gate.evaluate(20, 20) is False


def test_evaluate_true_when_count_exceeds_threshold():
    assert gate.evaluate(21, 20) is True


def test_evaluate_false_when_count_below_threshold():
    assert gate.evaluate(5, 20) is False


def test_format_open_count_report_passes_at_threshold():
    report = gate.format_open_count_report(20, 20, "gate-proposal")
    assert "20" in report
    assert "gate-proposal" in report
    assert "PASS" in report


def test_format_open_count_report_passes_below_threshold():
    report = gate.format_open_count_report(5, 20, "gate-proposal")
    assert "PASS" in report


def test_format_open_count_report_fails_over_threshold():
    report = gate.format_open_count_report(21, 20, "gate-proposal")
    assert "FAIL" in report


# ---------------------------------------------------------------------------
# is_exempt_closed_issue / partition_exempt_closed_issues (Decision 5's
# state_reason exemption) / format_closed_integrity_report (pass (b))
# ---------------------------------------------------------------------------


def test_is_exempt_closed_issue_true_for_not_planned():
    assert gate.is_exempt_closed_issue("not_planned") is True


def test_is_exempt_closed_issue_true_for_duplicate():
    assert gate.is_exempt_closed_issue("duplicate") is True


def test_is_exempt_closed_issue_false_for_completed():
    assert gate.is_exempt_closed_issue("completed") is False


def test_is_exempt_closed_issue_false_for_none():
    assert gate.is_exempt_closed_issue(None) is False


def test_partition_exempt_closed_issues_separates_records_preserving_order():
    records = [
        {"number": 1, "state_reason": "not_planned"},
        {"number": 2, "state_reason": "completed"},
        {"number": 3, "state_reason": "duplicate"},
        {"number": 4, "state_reason": None},
    ]
    exempt, remaining = gate.partition_exempt_closed_issues(records)
    assert exempt == [1, 3]
    assert remaining == [2, 4]


def test_partition_exempt_closed_issues_treats_missing_state_reason_as_not_exempt():
    records = [{"number": 5}]
    exempt, remaining = gate.partition_exempt_closed_issues(records)
    assert exempt == []
    assert remaining == [5]


def test_format_closed_integrity_report_passes_when_no_unverified_issues():
    report = gate.format_closed_integrity_report([], 5, 2, "gate-proposal")
    assert "PASS" in report
    assert "0 of 5" in report
    assert "2 exempted" in report


def test_format_closed_integrity_report_fails_and_lists_unverified_issues():
    report = gate.format_closed_integrity_report([118, 191], 5, 1, "gate-proposal")
    assert "FAIL" in report
    assert "#118" in report
    assert "#191" in report
    assert "1 exempted" in report


def test_format_closed_integrity_report_never_mentions_reopening():
    # Decision 5: no reopen action of any kind -- this pass only detects
    # and fails loudly.
    #
    # Asserted as an occurrence count, not as
    # `"reopen" not in report or "no reopen action taken" in report`: that
    # disjunction is satisfied outright by the disclaimer the FAIL branch
    # already prints, so it would still pass after a line promising or
    # describing a reopen was added right next to it. Counting pins the
    # disclaimer as the *only* place the word may appear.
    fail_report = gate.format_closed_integrity_report([118], 5, 0, "gate-proposal").lower()
    assert fail_report.count("reopen") == 1
    assert "no reopen action taken" in fail_report

    # The PASS branch has no disclaimer line at all, so it must not
    # mention reopening even once.
    pass_report = gate.format_closed_integrity_report([], 5, 0, "gate-proposal").lower()
    assert pass_report.count("reopen") == 0


# ---------------------------------------------------------------------------
# format_missing_label_error
# ---------------------------------------------------------------------------


def test_format_missing_label_error_names_label_and_repo():
    message = gate.format_missing_label_error("tvna", "gitapex", "gate-proposal")
    assert "gate-proposal" in message
    assert "tvna/gitapex" in message
    assert "does not exist" in message


# ---------------------------------------------------------------------------
# label_exists (the label-liveness guard both passes require)
# ---------------------------------------------------------------------------


def test_label_exists_requests_expected_url():
    captured = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        assert request.headers["Authorization"] == "Bearer tok"
        return Response(200, json.dumps({"name": "gate-proposal"}))

    gate.label_exists("tvna", "gitapex", "gate-proposal", "tok", opener=opener)
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/labels/gate-proposal"


def test_label_exists_returns_true_on_200():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"name": "gate-proposal"}))

    assert gate.label_exists("tvna", "gitapex", "gate-proposal", "tok", opener=opener) is True


def test_label_exists_returns_false_on_404():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(404, "not found")

    assert gate.label_exists("tvna", "gitapex", "gate-proposal", "tok", opener=opener) is False


def test_label_exists_raises_rather_than_reporting_missing_on_persistent_5xx():
    # The guard must fail loudly on an inconclusive result -- a server
    # error is not evidence the label is missing, and treating it as such
    # would let a transient outage masquerade as "label deleted."
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "boom")

    with pytest.raises(gate.GitHubApiError):
        gate.label_exists("tvna", "gitapex", "gate-proposal", "tok", opener=opener, sleeper=lambda _: None)


def test_label_exists_raises_on_persistent_4xx_other_than_404():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(403, "forbidden")

    with pytest.raises(gate.GitHubApiError):
        gate.label_exists("tvna", "gitapex", "gate-proposal", "tok", opener=opener)


def test_label_exists_quotes_a_label_name_with_special_characters():
    captured = {}
    gate.label_exists(
        "tvna", "gitapex", "a/b", "tok", opener=_url_capturing_opener(captured, json.dumps({"name": "a/b"}))
    )
    assert "a/b" not in captured["url"]
    assert "a%2Fb" in captured["url"]


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

    result = gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=sleeps.append)
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

    result = gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=sleeps.append)
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

    result = gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=sleeps.append)
    assert result == []
    assert sleeps == [5]


def test_list_labelled_issues_raises_after_repeated_network_failure():
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    with pytest.raises(gate.GitHubApiError):
        gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 3


def test_list_labelled_issues_still_defaults_to_state_all_via_positional_call():
    # list_labelled_issues calls list_labelled_issue_records positionally
    # through `sleeper` -- confirms `state` being appended *after*
    # opener/sleeper (rather than before) did not shift that positional
    # call onto the wrong parameter.
    captured = {}
    gate.list_labelled_issues("tvna", "gitapex", "gate-proposal", "tok", opener=_url_capturing_opener(captured))
    assert "state=all" in captured["url"]


# ---------------------------------------------------------------------------
# list_labelled_issue_records (issue #726: shared fetch for gitapex_compute_gprr.py)
# ---------------------------------------------------------------------------


def test_list_labelled_issue_records_returns_full_records():
    page = [
        {"number": 118, "body": "Status: `missing-deterministic-gate`", "created_at": "2026-07-01T00:00:00Z"},
        {"number": 187, "body": "Status: `carried-forward`", "created_at": "2026-07-08T00:00:00Z"},
    ]

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(page))

    result = gate.list_labelled_issue_records("tvna", "gitapex", "retrospective", "tok", opener=opener)
    assert result == page


def test_list_labelled_issue_records_excludes_pull_requests():
    page = [{"number": 1, "pull_request": {}}, {"number": 2, "body": "x", "created_at": "2026-07-01T00:00:00Z"}]

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(page))

    result = gate.list_labelled_issue_records("tvna", "gitapex", "retrospective", "tok", opener=opener)
    assert [record["number"] for record in result] == [2]


def test_list_labelled_issue_records_paginates_until_short_page():
    full_page = [{"number": n, "body": "", "created_at": "2026-07-01T00:00:00Z"} for n in range(100)]
    short_page = [{"number": 999, "body": "", "created_at": "2026-07-01T00:00:00Z"}]
    pages = [full_page, short_page]

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(pages.pop(0)))

    result = gate.list_labelled_issue_records("tvna", "gitapex", "retrospective", "tok", opener=opener)
    assert [record["number"] for record in result] == [*range(100), 999]


def test_list_labelled_issues_delegates_to_records(monkeypatch):
    records = [{"number": 5, "body": "", "created_at": "2026-07-01T00:00:00Z"}]
    monkeypatch.setattr(gate, "list_labelled_issue_records", lambda *a, **k: records)
    assert gate.list_labelled_issues("tvna", "gitapex", "retrospective", "tok") == [5]


def test_list_labelled_issue_records_defaults_to_state_all():
    # gitapex_compute_gprr.py calls this positionally with exactly four
    # arguments (owner, repo, label, token) and depends on this default
    # staying "all" -- see this function's own docstring.
    captured = {}
    gate.list_labelled_issue_records("tvna", "gitapex", "gate-proposal", "tok", opener=_url_capturing_opener(captured))
    assert "state=all" in captured["url"]


@pytest.mark.parametrize("state", ["open", "closed"])
def test_list_labelled_issue_records_uses_given_state(state):
    # `main`'s two passes ask for exactly these two states explicitly.
    captured = {}
    gate.list_labelled_issue_records(
        "tvna", "gitapex", "gate-proposal", "tok", opener=_url_capturing_opener(captured), state=state
    )
    assert f"state={state}" in captured["url"]


def test_list_labelled_issue_records_quotes_a_label_containing_a_space():
    # Defeat case for the label-liveness guard: `label_exists` quotes the
    # label, so a space-bearing label name (GitHub's own default
    # "good first issue" has two) passes the guard. If this fetch then
    # interpolated the label raw, it would emit a bare space into the
    # request line -- the guard reporting "the label is live" while the
    # pass it guards asks a malformed question.
    captured = {}
    gate.list_labelled_issue_records(
        "tvna", "gitapex", "gate proposal", "tok", opener=_url_capturing_opener(captured), state="open"
    )
    assert " " not in captured["url"]
    assert "labels=gate%20proposal" in captured["url"]


def test_list_labelled_issue_records_label_cannot_inject_a_second_query_parameter():
    # The sharper half of the same defeat: a label named `x&state=all`
    # passes the (quoting) liveness guard, and a raw interpolation here
    # would silently query label `x` with an injected `state=all` ahead of
    # this call's own `state=closed` -- a clean-looking report about a
    # label and state neither pass ever asked for.
    captured = {}
    gate.list_labelled_issue_records(
        "tvna", "gitapex", "x&state=all", "tok", opener=_url_capturing_opener(captured), state="closed"
    )
    assert captured["url"].count("state=") == 1
    assert "labels=x%26state%3Dall" in captured["url"]


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
# load_gate_tracking_issues
# ---------------------------------------------------------------------------


def test_load_gate_tracking_issues_parses_ints_and_skips_null_or_missing(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": 650},
                    {"id": "b", "tracking_issue": None},
                    {"id": "c"},
                    {"id": "d", "tracking_issue": 297},
                ]
            }
        )
    )
    assert gate.load_gate_tracking_issues(str(ssot)) == {650, 297}


def test_load_gate_tracking_issues_raises_on_missing_file(tmp_path):
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issues(str(tmp_path / "nonexistent.json"))


def test_load_gate_tracking_issues_raises_on_undecodable_file(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_bytes(b"\xff\xfe bad")
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_on_malformed_json(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text("{not valid json")
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_when_not_a_json_object(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text("[]")
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_when_gates_list_missing_or_empty(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": []}))
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_excludes_non_int_and_bool_values(tmp_path):
    # `bool` is an `int` subclass in Python -- a stray `true`/`false` must
    # not be silently coerced into corroborating issue #1/#0. Strings and
    # floats are equally malformed and must also be excluded rather than
    # crashing or being accepted.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": True},
                    {"id": "b", "tracking_issue": False},
                    {"id": "c", "tracking_issue": "297"},
                    {"id": "d", "tracking_issue": 297.0},
                    {"id": "f", "tracking_issue": 650},
                ]
            }
        )
    )
    assert gate.load_gate_tracking_issues(str(ssot)) == {650}


def test_load_gate_tracking_issues_flattens_list_values(tmp_path):
    # Issue #1425: a gate legitimately tracked under more than one issue
    # (a shared umbrella issue plus the issue whose repair actually
    # implemented it) stores tracking_issue as a list -- every int in it
    # corroborates, and non-int/bool entries within the list are excluded
    # the same as a bare scalar value would be.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": [520, 344]},
                    {"id": "b", "tracking_issue": [297, 422, 426]},
                    {"id": "c", "tracking_issue": [650, True, "297", 297.0]},
                    {"id": "d", "tracking_issue": 999},
                ]
            }
        )
    )
    assert gate.load_gate_tracking_issues(str(ssot)) == {520, 344, 297, 422, 426, 650, 999}


def test_load_gate_tracking_issues_flatten_rejects_nested_list_and_empty_list(tmp_path):
    # Defeat case (dimension 15, fail-closed on malformed input): a
    # schema-invalid but not-impossible hand-edited shape -- a list
    # nested inside the tracking_issue list, or an empty list -- must be
    # excluded rather than crashing the flatten loop or silently
    # corroborating something it never named.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": [[297], 344]},
                    {"id": "b", "tracking_issue": []},
                    {"id": "c", "tracking_issue": 650},
                ]
            }
        )
    )
    assert gate.load_gate_tracking_issues(str(ssot)) == {344, 650}


# ---------------------------------------------------------------------------
# main: label-liveness guard, open-count threshold report (pass a), and
# closed-issue zero-tolerance integrity pass (pass b)
# ---------------------------------------------------------------------------


def _open_records(*numbers):
    return [{"number": n} for n in numbers]


def _closed_record(number, state_reason=None):
    return {"number": number, "state_reason": state_reason}


def _fake_records_by_state(open_records=(), closed_records=()):
    """A `list_labelled_issue_records` stand-in that dispatches on the
    `state=` keyword `main` passes for each of its two passes."""

    def fake(owner, repo, label, token, state="all", **kwargs):
        if state == "open":
            return list(open_records)
        if state == "closed":
            return list(closed_records)
        raise AssertionError(f"unexpected state: {state!r}")

    return fake


def test_main_fails_loudly_when_label_does_not_exist(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: False)
    argv = ["--owner", "tvna", "--repo", "gitapex", "--label", "gate-proposal"]
    assert gate.main(argv) == 1
    stderr = capsys.readouterr().err
    # main prints exactly the shared format_missing_label_error text, not a
    # locally re-derived copy of it -- this is the touched call site's own
    # test, not merely a substring check.
    assert stderr.strip() == gate.format_missing_label_error("tvna", "gitapex", "gate-proposal")


def test_main_does_not_fetch_issues_when_label_missing(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: False)

    def fail_if_called(*a, **k):
        raise AssertionError("list_labelled_issue_records must not run when the label is missing")

    monkeypatch.setattr(gate, "list_labelled_issue_records", fail_if_called)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_label_exists_github_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*a, **k):
        raise gate.GitHubApiError("boom")

    monkeypatch.setattr(gate, "label_exists", raise_api_error)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_open_count_over_threshold_fails(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gate, "list_labelled_issue_records", _fake_records_by_state(open_records=_open_records(*range(21)))
    )
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "20"])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_open_count_at_threshold_passes(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gate, "list_labelled_issue_records", _fake_records_by_state(open_records=_open_records(*range(20)))
    )
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "20"])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_open_count_below_threshold_passes(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(gate, "list_labelled_issue_records", _fake_records_by_state(open_records=_open_records(1, 2)))
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "20"])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_passes_when_all_closed_issues_verified_or_exempt(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    closed = [
        _closed_record(100),
        _closed_record(101, state_reason="not_planned"),
        _closed_record(102, state_reason="duplicate"),
    ]
    monkeypatch.setattr(gate, "list_labelled_issue_records", _fake_records_by_state(closed_records=closed))
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: ["Refs #100"])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: {100})
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "20"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "PASS: every closed issue" in out


def test_main_fails_when_single_non_exempt_closed_issue_is_unverified(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    closed = [_closed_record(200), _closed_record(201)]
    monkeypatch.setattr(gate, "list_labelled_issue_records", _fake_records_by_state(closed_records=closed))
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: ["Refs #200"])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: {200})
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "20"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "#201" in out
    assert "#200" not in out.split("Closed issues with no verified gate")[-1]
    assert "FAIL" in out


def test_main_fails_a_closed_issue_that_has_a_citing_commit_but_no_ssot_entry(monkeypatch, capsys):
    # Defeat case for the closed-issue integrity pass: half of the
    # two-signal check is not enough. A closed issue whose number is cited
    # by a commit on the checked ref, but which no `.gitapex/ssot.json`
    # `gates[].tracking_issue` entry names, is exactly issue #709's
    # false-negative shape -- it must still fail here.
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gate, "list_labelled_issue_records", _fake_records_by_state(closed_records=[_closed_record(910)])
    )
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: ["feat(gates): something related (Refs #910)"])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1
    assert "#910" in capsys.readouterr().out


def test_main_fails_a_closed_issue_that_has_an_ssot_entry_but_no_citing_commit(monkeypatch, capsys):
    # The mirror-image half of the same defeat: a registry entry alone,
    # with no commit on the checked ref citing the issue, must also still
    # fail. Both signals are required, never either.
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gate, "list_labelled_issue_records", _fake_records_by_state(closed_records=[_closed_record(911)])
    )
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: ["chore: unrelated"])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: {911})
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1
    assert "#911" in capsys.readouterr().out


@pytest.mark.parametrize("state_reason", ["reopened", "completed", "resolved", "NOT_PLANNED", "not_planned "])
def test_main_fails_a_closed_issue_whose_state_reason_is_not_one_of_the_two_exempt_values(
    monkeypatch, capsys, state_reason
):
    # Defeat case for the exemption: only the two literal values
    # `not_planned` and `duplicate` excuse a closed issue. A different
    # GitHub value, a future one, and a case- or whitespace-variant of an
    # exempt one all stay non-exempt -- the exemption fails closed rather
    # than widening on anything that merely resembles a declined proposal.
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gate,
        "list_labelled_issue_records",
        _fake_records_by_state(closed_records=[_closed_record(912, state_reason=state_reason)]),
    )
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1
    out = capsys.readouterr().out
    assert "#912" in out
    assert "0 exempted by state_reason" in out


def test_main_exempts_declined_closed_issues_while_still_failing_on_a_genuine_unverified_one(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    closed = [
        _closed_record(300, state_reason="not_planned"),
        _closed_record(301, state_reason="duplicate"),
        _closed_record(302),
    ]
    monkeypatch.setattr(gate, "list_labelled_issue_records", _fake_records_by_state(closed_records=closed))
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "20"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "2 exempted by state_reason" in out
    assert "#302" in out
    assert "FAIL: 1 closed issue(s) never passed" in out


def test_main_open_count_failure_and_closed_integrity_failure_both_reported(monkeypatch, capsys):
    # Both passes run and are both reported regardless of which one fails
    # first -- neither short-circuits the other.
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gate,
        "list_labelled_issue_records",
        _fake_records_by_state(open_records=_open_records(*range(25)), closed_records=[_closed_record(400)]),
    )
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "20"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "Retrospective gate-drift report" in out
    assert "Closed 'gate-proposal'-labelled issue integrity" in out
    assert out.count("FAIL") == 2


def test_main_exits_one_on_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_github_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)

    def raise_api_error(*a, **k):
        raise gate.GitHubApiError("boom")

    monkeypatch.setattr(gate, "list_labelled_issue_records", raise_api_error)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_git_log_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(gate, "list_labelled_issue_records", lambda *a, **k: [])

    def raise_git_error(*a, **k):
        raise gate.GitLogError("boom")

    monkeypatch.setattr(gate, "git_commit_messages", raise_git_error)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_ssot_ledger_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(gate, "list_labelled_issue_records", lambda *a, **k: [])
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])

    def raise_ssot_error(*a, **k):
        raise gate.SsotLedgerError("boom")

    monkeypatch.setattr(gate, "load_gate_tracking_issues", raise_ssot_error)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_uses_default_threshold_when_unspecified(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gate, "list_labelled_issue_records", _fake_records_by_state(open_records=_open_records(*range(18)))
    )
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    assert f"threshold: {gate.DEFAULT_THRESHOLD}" in capsys.readouterr().out


def test_main_uses_gate_proposal_label_by_default(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(gate, "list_labelled_issue_records", lambda *a, **k: [])
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    assert f"'{gate.GATE_PROPOSAL_LABEL}'" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _CliArgs pydantic validation (new in this batch's CLI-pydantic-wrap)
# ---------------------------------------------------------------------------


def test_main_rejects_blank_owner(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "", "--repo", "gitapex"])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_blank_repo(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", ""])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_blank_ssot_path(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--ssot-path", ""])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_whitespace_only_owner(monkeypatch, capsys):
    """Issue #1087: min_length=1 alone accepts a whitespace-only value;
    the field must reject it the same as a truly blank one."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", " ", "--repo", "gitapex"])
    assert exit_code == 1
    assert "error: invalid arguments: --owner (must not be blank)" in capsys.readouterr().err


def test_main_rejects_whitespace_only_repo(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "\t"])
    assert exit_code == 1
    assert "error: invalid arguments: --repo (must not be blank)" in capsys.readouterr().err


def test_main_rejects_whitespace_only_ref(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--ref", " "])
    assert exit_code == 1
    assert "error: invalid arguments: --ref (must not be blank)" in capsys.readouterr().err


def test_main_rejects_whitespace_only_cwd(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--cwd", " "])
    assert exit_code == 1
    assert "error: invalid arguments: --cwd (must not be blank)" in capsys.readouterr().err


def test_main_rejects_whitespace_only_label(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--label", "  "])
    assert exit_code == 1
    assert "error: invalid arguments: --label (must not be blank)" in capsys.readouterr().err


def test_main_rejects_whitespace_only_ssot_path(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--ssot-path", "\t"])
    assert exit_code == 1
    assert "error: invalid arguments: --ssot-path (must not be blank)" in capsys.readouterr().err


def test_main_names_every_whitespace_only_flag_in_declaration_order(monkeypatch, capsys):
    """Issue #1087: mirrors the pre-existing all-blank defeat test above --
    all six whitespace-only flags are reported at once, in the model's own
    field-declaration order."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    argv = ["--owner", " ", "--repo", " ", "--ref", " ", "--cwd", " ", "--label", " ", "--ssot-path", " "]
    assert gate.main(argv) == 1
    blank = "(must not be blank)"
    assert (
        f"error: invalid arguments: --owner {blank}, --repo {blank}, --ref {blank}, "
        f"--cwd {blank}, --label {blank}, --ssot-path {blank}" in capsys.readouterr().err
    )


# ---------------------------------------------------------------------------
# Issue #1094: str.strip() alone leaves Unicode Format-category (Cf)
# characters in place (confirmed for U+200B ZERO WIDTH SPACE, U+FEFF
# ZERO WIDTH NO-BREAK SPACE, and U+180E MONGOLIAN VOWEL SEPARATOR), so a
# value composed solely of Cf marks passed issue #1087's whitespace-only
# guard unrejected.
# ---------------------------------------------------------------------------


def test_main_rejects_invisible_only_owner(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "\u200b", "--repo", "gitapex"])
    assert exit_code == 1
    assert "error: invalid arguments: --owner (must not be blank)" in capsys.readouterr().err


def test_main_rejects_invisible_only_repo(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "\ufeff"])
    assert exit_code == 1
    assert "error: invalid arguments: --repo (must not be blank)" in capsys.readouterr().err


def test_main_rejects_invisible_only_ref(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--ref", "\u180e"])
    assert exit_code == 1
    assert "error: invalid arguments: --ref (must not be blank)" in capsys.readouterr().err


def test_main_rejects_invisible_only_cwd(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--cwd", "\u200b"])
    assert exit_code == 1
    assert "error: invalid arguments: --cwd (must not be blank)" in capsys.readouterr().err


def test_main_rejects_invisible_only_label(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--label", "\ufeff"])
    assert exit_code == 1
    assert "error: invalid arguments: --label (must not be blank)" in capsys.readouterr().err


def test_main_rejects_invisible_only_ssot_path(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--ssot-path", "\u180e"])
    assert exit_code == 1
    assert "error: invalid arguments: --ssot-path (must not be blank)" in capsys.readouterr().err


def test_main_names_every_invisible_only_flag_in_declaration_order(monkeypatch, capsys):
    """Issue #1094: mirrors the pre-existing all-whitespace defeat test
    above -- all six Cf-only flags are reported at once, in the model's
    own field-declaration order."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    argv = [
        "--owner",
        "\u200b",
        "--repo",
        "\u200b",
        "--ref",
        "\u200b",
        "--cwd",
        "\u200b",
        "--label",
        "\u200b",
        "--ssot-path",
        "\u200b",
    ]
    assert gate.main(argv) == 1
    blank = "(must not be blank)"
    assert (
        f"error: invalid arguments: --owner {blank}, --repo {blank}, --ref {blank}, "
        f"--cwd {blank}, --label {blank}, --ssot-path {blank}" in capsys.readouterr().err
    )


def _install_recording_fakes(monkeypatch) -> dict:
    """Replace `main`'s four I/O collaborators with recording fakes and
    return the dict they record into.

    Shared by the two "validation never silently trims" tests below (issues
    #1087 and #1094), which differ only in the padding characters they feed
    each flag -- ordinary whitespace versus Unicode Format-category marks.
    """
    received: dict = {}

    def fake_label_exists(owner, repo, label, token):
        received["label_exists_owner"] = owner
        received["label_exists_repo"] = repo
        received["label_exists_label"] = label
        return True

    def fake_list_labelled_issue_records(owner, repo, label, token, state="all", **kwargs):
        received[f"records_{state}_owner"] = owner
        received[f"records_{state}_repo"] = repo
        received[f"records_{state}_label"] = label
        return []

    def fake_git_commit_messages(ref, cwd):
        received["ref"] = ref
        received["cwd"] = cwd
        return []

    def fake_load_gate_tracking_issues(path):
        received["ssot_path_joined"] = path
        return set()

    monkeypatch.setattr(gate, "label_exists", fake_label_exists)
    monkeypatch.setattr(gate, "list_labelled_issue_records", fake_list_labelled_issue_records)
    monkeypatch.setattr(gate, "git_commit_messages", fake_git_commit_messages)
    monkeypatch.setattr(gate, "load_gate_tracking_issues", fake_load_gate_tracking_issues)
    return received


def test_main_keeps_invisible_padded_but_meaningful_values_unmutated(monkeypatch, capsys):
    """A value padded with a Cf mark rather than ASCII whitespace must
    keep working, unmutated -- only an entirely invisible/non-printing
    value changes verdict (issue #1094)."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    received = _install_recording_fakes(monkeypatch)
    exit_code = gate.main(
        [
            "--owner",
            "\u200btvna\u200b",
            "--repo",
            "\ufeffgitapex\ufeff",
            "--ref",
            "\u200bHEAD\u200b",
            "--cwd",
            "\ufeff.\ufeff",
            "--label",
            "\u200bgate-proposal-gate\u200b",
            "--ssot-path",
            "\ufeff.gitapex/ssot.json\ufeff",
        ]
    )
    assert exit_code == 0
    assert received["label_exists_owner"] == "\u200btvna\u200b"
    assert received["label_exists_label"] == "\u200bgate-proposal-gate\u200b"
    assert received["records_open_repo"] == "\ufeffgitapex\ufeff"
    assert received["records_closed_label"] == "\u200bgate-proposal-gate\u200b"
    assert received["ref"] == "\u200bHEAD\u200b"
    assert received["cwd"] == "\ufeff.\ufeff"
    assert received["ssot_path_joined"] == str(pathlib.Path("\ufeff.\ufeff") / "\ufeff.gitapex/ssot.json\ufeff")


def test_main_keeps_padded_but_meaningful_values_unmutated(monkeypatch, capsys):
    """Issue #1087: validation must not silently trim -- a value with real
    content plus surrounding whitespace reaches every downstream call
    exactly as typed."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    received = _install_recording_fakes(monkeypatch)
    exit_code = gate.main(
        [
            "--owner",
            " tvna ",
            "--repo",
            " gitapex ",
            "--ref",
            " HEAD ",
            "--cwd",
            " . ",
            "--label",
            " gate-proposal ",
            "--ssot-path",
            " .gitapex/ssot.json ",
        ]
    )
    assert exit_code == 0
    assert received["label_exists_owner"] == " tvna "
    assert received["records_open_label"] == " gate-proposal "
    assert received["records_closed_repo"] == " gitapex "
    assert received["ref"] == " HEAD "
    assert received["cwd"] == " . "
    assert received["ssot_path_joined"] == str(pathlib.Path(" . ") / " .gitapex/ssot.json ")


def test_main_renders_underscored_field_as_its_hyphenated_flag(monkeypatch, capsys):
    """Issue #822: `ssot_path` is the model's field name but `--ssot-path`
    is the flag an operator actually typed, so the `ValidationError`
    handler must report the hyphenated flag, never the raw field name and
    never pydantic's own message text."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    assert gate.main(["--owner", "tvna", "--repo", "gitapex", "--ssot-path", ""]) == 1
    stderr = capsys.readouterr().err
    assert "error: invalid arguments: --ssot-path (must not be blank)" in stderr
    assert "ssot_path" not in stderr
    assert "String should have at least 1 character" not in stderr


def test_main_names_every_offending_flag_in_declaration_order(monkeypatch, capsys):
    """Issue #822: all six blank flags are reported at once, in the model's
    own field-declaration order -- matching what the hand-rolled
    `_validate_cli_args` this replaces reported."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    argv = ["--owner", "", "--repo", "", "--ref", "", "--cwd", "", "--label", "", "--ssot-path", ""]
    assert gate.main(argv) == 1
    blank = "(must not be blank)"
    assert (
        f"error: invalid arguments: --owner {blank}, --repo {blank}, --ref {blank}, "
        f"--cwd {blank}, --label {blank}, --ssot-path {blank}" in capsys.readouterr().err
    )

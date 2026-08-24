"""Tests for the retrospective gate-drift meta-check
(.github/scripts/gitapex_scan_retrospective_gate_drift.py).

Refs #297 (refs #187, #242, #246): this script mechanizes
merge-retrospective's Step 0 (find retrospective-labelled issues with no
citing commit on main) and fails CI when the count exceeds a threshold.

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
    counts = {242: 1, 187: 1, 118: 1}
    assert gate.find_no_citation_issues([242, 187, 118], messages, counts, {}) == [118]


def test_find_no_citation_issues_empty_when_all_cited():
    messages = ["Refs #1", "Refs #2"]
    assert gate.find_no_citation_issues([1, 2], messages, {1: 1, 2: 1}, {}) == []


# ---------------------------------------------------------------------------
# find_no_citation_issues: corroborating-signal cases (issue #709)
# ---------------------------------------------------------------------------


def test_find_no_citation_issues_keeps_issue_314_shape_when_citing_commit_lacks_corroboration():
    # Reproduces #314's real false negative: a66ccbc cited "#314" while
    # changing an unrelated workflow comment/doc, and no ssot.json gate
    # was ever registered with tracking_issue == 314.
    messages = ["chore(gates): document budget caps and permanent human-review-of-merge (#318)"]
    assert gate.find_no_citation_issues([314], ["Refs #314", *messages], {}, {}) == [314]


def test_find_no_citation_issues_keeps_multi_proposal_issue_665_shape_when_only_one_subproposal_has_a_tracking_entry():
    # Reproduces #665's real false negative: PR #703's commits cited
    # "refs #665 repair 6" (repair 6 landed as the hidden-characters gate,
    # tracking_issue 702 -- not 665), while #665's other three proposed
    # repairs (2, 3, 4) remain unimplemented. 665 itself must stay
    # uncleared even though a commit cites it.
    messages = ["feat(ci): add a repository-wide hidden-character gate (refs #665 repair 6)"]
    assert gate.find_no_citation_issues([665], messages, {702: 1}, {}) == [665]


def test_find_no_citation_issues_clears_when_citation_and_tracking_issue_both_present():
    # Guards the opposite regression: a genuine single-proposal, citing +
    # registry-backed issue must still clear normally.
    messages = ["fix(gates): close gaps (Refs #650)"]
    assert gate.find_no_citation_issues([650], messages, {650: 1}, {}) == []


# ---------------------------------------------------------------------------
# find_no_citation_issues: per-gate granularity (issue #1177)
# ---------------------------------------------------------------------------


def test_find_no_citation_issues_stays_uncleared_when_multi_proposal_manifest_is_only_partially_built():
    # Issue #1129 shape: 6 distinct gates proposed, only 1 registered and
    # cited so far. Partial implementation must not clear the issue.
    messages = ["fix(gates): close one of six gaps (Refs #1129)"]
    requirements = {1129: 6}
    assert gate.find_no_citation_issues([1129], messages, {1129: 1}, requirements) == [1129]


def test_find_no_citation_issues_clears_when_multi_proposal_manifest_is_fully_built():
    # The other direction: once the registered-and-cited count meets the
    # manifest's declared requirement, the issue clears like any other.
    messages = ["fix(gates): close the last of two gaps (Refs #1130)"]
    requirements = {1130: 2}
    assert gate.find_no_citation_issues([1130], messages, {1130: 2}, requirements) == []


def test_find_no_citation_issues_stays_uncleared_when_gate_count_falls_one_short():
    messages = ["fix(gates): close gaps (Refs #1131)"]
    requirements = {1131: 3}
    assert gate.find_no_citation_issues([1131], messages, {1131: 2}, requirements) == [1131]


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
# load_gate_tracking_issue_counts
# ---------------------------------------------------------------------------


def test_load_gate_tracking_issue_counts_parses_ints_and_skips_null_or_missing(tmp_path):
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
    assert gate.load_gate_tracking_issue_counts(str(ssot)) == {650: 1, 297: 1}


def test_load_gate_tracking_issue_counts_counts_multiple_gates_per_issue(tmp_path):
    # Issue #1177's own motivating shape: several distinct gates[] entries
    # already share one tracking_issue (e.g. real #520/#928/#439 today).
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": 520},
                    {"id": "b", "tracking_issue": 520},
                    {"id": "c", "tracking_issue": 520},
                    {"id": "d", "tracking_issue": 650},
                ]
            }
        )
    )
    assert gate.load_gate_tracking_issue_counts(str(ssot)) == {520: 3, 650: 1}


def test_load_gate_tracking_issue_counts_raises_on_missing_file(tmp_path):
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issue_counts(str(tmp_path / "nonexistent.json"))


def test_load_gate_tracking_issue_counts_raises_on_undecodable_file(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_bytes(b"\xff\xfe bad")
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issue_counts(str(ssot))


def test_load_gate_tracking_issue_counts_raises_on_malformed_json(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text("{not valid json")
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issue_counts(str(ssot))


def test_load_gate_tracking_issue_counts_raises_when_not_a_json_object(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text("[]")
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issue_counts(str(ssot))


def test_load_gate_tracking_issue_counts_raises_when_gates_list_missing_or_empty(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": []}))
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_tracking_issue_counts(str(ssot))


def test_load_gate_tracking_issue_counts_excludes_non_int_and_bool_values(tmp_path):
    # `bool` is an `int` subclass in Python -- a stray `true`/`false` must
    # not be silently coerced into corroborating issue #1/#0. Strings,
    # floats, and lists are equally malformed and must also be excluded
    # rather than crashing or being accepted.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": True},
                    {"id": "b", "tracking_issue": False},
                    {"id": "c", "tracking_issue": "297"},
                    {"id": "d", "tracking_issue": 297.0},
                    {"id": "e", "tracking_issue": [297]},
                    {"id": "f", "tracking_issue": 650},
                ]
            }
        )
    )
    assert gate.load_gate_tracking_issue_counts(str(ssot)) == {650: 1}


# ---------------------------------------------------------------------------
# load_proposed_gate_requirements (issue #1177)
# ---------------------------------------------------------------------------


def test_load_proposed_gate_requirements_returns_proposal_counts(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "proposed_gates": [
                    {"tracking_issue": 1129, "proposals": ["a", "b", "c", "d", "e", "f"]},
                    {"tracking_issue": 1130, "proposals": ["x", "y"]},
                ]
            }
        )
    )
    assert gate.load_proposed_gate_requirements(str(ssot)) == {1129: 6, 1130: 2}


def test_load_proposed_gate_requirements_empty_when_field_missing(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": []}))
    assert gate.load_proposed_gate_requirements(str(ssot)) == {}


def test_load_proposed_gate_requirements_empty_when_field_empty(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": []}))
    assert gate.load_proposed_gate_requirements(str(ssot)) == {}


def test_load_proposed_gate_requirements_raises_when_field_not_a_list(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": "not-a-list"}))
    with pytest.raises(gate.SsotLedgerError):
        gate.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_duplicate_tracking_issue(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "proposed_gates": [
                    {"tracking_issue": 1129, "proposals": ["a", "b"]},
                    {"tracking_issue": 1129, "proposals": ["c", "d"]},
                ]
            }
        )
    )
    with pytest.raises(gate.SsotLedgerError):
        gate.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_non_dict_entry(tmp_path):
    # Issue #1177 adversarial-gate-quality review: unlike gates[]'s tolerant
    # skip of a malformed tracking_issue (safe -- under-counts a citation),
    # silently skipping a malformed proposed_gates[] entry would fall its
    # requirement back to the weaker default of 1, which can falsely
    # resolve a multi-gate issue -- so a malformed entry raises instead.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": ["not-a-dict", {"tracking_issue": 1131, "proposals": ["a", "b"]}]}))
    with pytest.raises(gate.SsotLedgerError):
        gate.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_non_integer_tracking_issue(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": [{"tracking_issue": "1129", "proposals": ["a", "b"]}]}))
    with pytest.raises(gate.SsotLedgerError):
        gate.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_non_list_proposals(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": [{"tracking_issue": 1130, "proposals": "not-a-list"}]}))
    with pytest.raises(gate.SsotLedgerError):
        gate.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_missing_file(tmp_path):
    with pytest.raises(gate.SsotLedgerError):
        gate.load_proposed_gate_requirements(str(tmp_path / "nonexistent.json"))


# ---------------------------------------------------------------------------
# load_gate_and_proposed_gate_corroboration (issue #1177)
# ---------------------------------------------------------------------------


def test_load_gate_and_proposed_gate_corroboration_matches_the_two_separate_readers(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": 520},
                    {"id": "b", "tracking_issue": 520},
                ],
                "proposed_gates": [{"tracking_issue": 1129, "proposals": ["a", "b", "c"]}],
            }
        )
    )
    counts, requirements = gate.load_gate_and_proposed_gate_corroboration(str(ssot))
    assert counts == gate.load_gate_tracking_issue_counts(str(ssot))
    assert requirements == gate.load_proposed_gate_requirements(str(ssot))
    assert counts == {520: 2}
    assert requirements == {1129: 3}


def test_load_gate_and_proposed_gate_corroboration_reads_the_file_only_once(tmp_path, monkeypatch):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": [{"id": "a", "tracking_issue": 1}], "proposed_gates": []}))
    read_calls = []
    original_read_text = pathlib.Path.read_text

    def counting_read_text(self, *args, **kwargs):
        if self == ssot:
            read_calls.append(1)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", counting_read_text)
    gate.load_gate_and_proposed_gate_corroboration(str(ssot))
    assert len(read_calls) == 1


def test_load_gate_and_proposed_gate_corroboration_raises_on_missing_file(tmp_path):
    with pytest.raises(gate.SsotLedgerError):
        gate.load_gate_and_proposed_gate_corroboration(str(tmp_path / "nonexistent.json"))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_exits_zero_when_count_at_threshold(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: [1, 2])
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: ["Refs #1", "Refs #2"])
    monkeypatch.setattr(gate, "load_gate_and_proposed_gate_corroboration", lambda *a, **k: ({1: 1, 2: 1}, {}))
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", "--threshold", "0"])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_exits_one_when_count_exceeds_threshold(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: [1, 2, 3])
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_and_proposed_gate_corroboration", lambda *a, **k: ({}, {}))
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


def test_main_exits_one_on_ssot_ledger_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: [1])
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: ["Refs #1"])

    def raise_ssot_error(*a, **k):
        raise gate.SsotLedgerError("boom")

    monkeypatch.setattr(gate, "load_gate_and_proposed_gate_corroboration", raise_ssot_error)
    assert gate.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_uses_default_threshold_when_unspecified(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate, "list_labelled_issues", lambda *a, **k: list(range(18)))
    monkeypatch.setattr(gate, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(gate, "load_gate_and_proposed_gate_corroboration", lambda *a, **k: ({}, {}))
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    assert f"threshold: {gate.DEFAULT_THRESHOLD}" in capsys.readouterr().out


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


def test_main_keeps_invisible_padded_but_meaningful_values_unmutated(monkeypatch, capsys):
    """A value padded with a Cf mark rather than ASCII whitespace must
    keep working, unmutated -- only an entirely invisible/non-printing
    value changes verdict (issue #1094)."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    received = {}

    def fake_list_labelled_issues(owner, repo, label, token):
        received["owner"] = owner
        received["repo"] = repo
        received["label"] = label
        return []

    def fake_git_commit_messages(ref, cwd):
        received["ref"] = ref
        received["cwd"] = cwd
        return []

    def fake_load_gate_and_proposed_gate_corroboration(path):
        received["ssot_path_joined"] = path
        return {}, {}

    monkeypatch.setattr(gate, "list_labelled_issues", fake_list_labelled_issues)
    monkeypatch.setattr(gate, "git_commit_messages", fake_git_commit_messages)
    monkeypatch.setattr(
        gate, "load_gate_and_proposed_gate_corroboration", fake_load_gate_and_proposed_gate_corroboration
    )
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
            "\u200bretrospective-gate\u200b",
            "--ssot-path",
            "\ufeff.gitapex/ssot.json\ufeff",
        ]
    )
    assert exit_code == 0
    assert received["owner"] == "\u200btvna\u200b"
    assert received["repo"] == "\ufeffgitapex\ufeff"
    assert received["ref"] == "\u200bHEAD\u200b"
    assert received["cwd"] == "\ufeff.\ufeff"
    assert received["label"] == "\u200bretrospective-gate\u200b"
    assert received["ssot_path_joined"] == str(pathlib.Path("\ufeff.\ufeff") / "\ufeff.gitapex/ssot.json\ufeff")


def test_main_keeps_padded_but_meaningful_values_unmutated(monkeypatch, capsys):
    """Issue #1087: validation must not silently trim -- a value with real
    content plus surrounding whitespace reaches every downstream call
    exactly as typed."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    received = {}

    def fake_list_labelled_issues(owner, repo, label, token):
        received["owner"] = owner
        received["repo"] = repo
        received["label"] = label
        return []

    def fake_git_commit_messages(ref, cwd):
        received["ref"] = ref
        received["cwd"] = cwd
        return []

    def fake_load_gate_and_proposed_gate_corroboration(path):
        received["ssot_path_joined"] = path
        return {}, {}

    monkeypatch.setattr(gate, "list_labelled_issues", fake_list_labelled_issues)
    monkeypatch.setattr(gate, "git_commit_messages", fake_git_commit_messages)
    monkeypatch.setattr(
        gate, "load_gate_and_proposed_gate_corroboration", fake_load_gate_and_proposed_gate_corroboration
    )
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
            " retrospective ",
            "--ssot-path",
            " .gitapex/ssot.json ",
        ]
    )
    assert exit_code == 0
    assert received["owner"] == " tvna "
    assert received["repo"] == " gitapex "
    assert received["label"] == " retrospective "
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

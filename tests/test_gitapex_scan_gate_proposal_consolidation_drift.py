"""Tests for the gate-proposal-umbrella Consolidates: drift check
(.github/scripts/gitapex_scan_gate_proposal_consolidation_drift.py).

Refs #1653: #1566-#1575 (10 umbrella issues, 32 referenced source issues
total) sat with an unverified `Consolidates:` claim for roughly a day --
every referenced source issue was still OPEN -- before a human caught it
and closed them by hand. This script closes that gap; the tests below
reproduce the exact defect class as a fixture (a referenced issue still
OPEN) confirming the check fails, then confirm it passes once that issue
is properly closed as the umbrella's duplicate -- this repository's own
fixed Proof-method convention.

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring
test_gitapex_scan_retrospective_gate_drift.py's own fixture style. GitHub
writes (`label_exists`, `list_labelled_issue_records`, both imported
directly from gitapex_scan_retrospective_gate_drift.py) are monkeypatched
at the module level the same way that file's own test suite already
monkeypatches them.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import gitapex_scan_gate_proposal_consolidation_drift as csd
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
# extract_consolidates_issue_numbers
# ---------------------------------------------------------------------------


def test_extract_consolidates_issue_numbers_matches_real_1566_body_shape() -> None:
    # The exact literal line confirmed live against issue #1566's own body
    # during issue #1653's own primary-source research.
    body = (
        "This issue consolidates several individual gate-proposal issues...\n\n"
        "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
        "|---|---|---|---|---|\n"
        "| ... | ... | ... | ... | ... |\n\n"
        "Consolidates: #1547, #1546, #1489, #1508\n\n"
        "Re-verified: `planning-a-branch-from-an-issue` (2026-08-30T16:46:19Z)"
    )
    assert csd.extract_consolidates_issue_numbers(body) == [1547, 1546, 1489, 1508]


def test_extract_consolidates_issue_numbers_single_reference() -> None:
    assert csd.extract_consolidates_issue_numbers("Consolidates: #42\n") == [42]


def test_extract_consolidates_issue_numbers_empty_when_no_such_line() -> None:
    assert csd.extract_consolidates_issue_numbers("An ordinary gate-proposal issue body.") == []


def test_extract_consolidates_issue_numbers_ignores_similar_prose_mid_paragraph() -> None:
    # "Consolidates:" must be the start of its own line -- a sentence that
    # merely mentions consolidation mid-paragraph is not this line.
    body = "This finding consolidates: nothing in particular, just prose."
    assert csd.extract_consolidates_issue_numbers(body) == []


def test_extract_consolidates_issue_numbers_does_not_cross_into_next_paragraph() -> None:
    body = "Consolidates: #1\n\nRefs #999 unrelated paragraph"
    assert csd.extract_consolidates_issue_numbers(body) == [1]


def test_extract_consolidates_issue_numbers_collects_every_matching_line() -> None:
    # An issue body edited to append a second Consolidates: line (e.g. a
    # follow-up edit consolidating a further finding) must not leave that
    # second line's own references unchecked.
    body = "Consolidates: #1547, #1546\n\nSome intervening text.\n\nConsolidates: #1600\n"
    assert csd.extract_consolidates_issue_numbers(body) == [1547, 1546, 1600]


def test_extract_consolidates_issue_numbers_deduplicates_across_lines() -> None:
    body = "Consolidates: #1547\n\nConsolidates: #1547, #1600\n"
    assert csd.extract_consolidates_issue_numbers(body) == [1547, 1600]


# ---------------------------------------------------------------------------
# find_unverified_consolidation_claims
# ---------------------------------------------------------------------------


def _verified_state(umbrella_number: int) -> dict[str, Any]:
    return {"state": "CLOSED", "state_reason": "DUPLICATE", "duplicate_of_number": umbrella_number}


def _open_state() -> dict[str, Any]:
    return {"state": "OPEN", "state_reason": None, "duplicate_of_number": None}


def test_find_unverified_consolidation_claims_empty_when_all_verified() -> None:
    states: dict[int, dict[str, Any] | None] = {1547: _verified_state(1566), 1546: _verified_state(1566)}
    assert csd.find_unverified_consolidation_claims(1566, [1547, 1546], states) == []


def test_find_unverified_consolidation_claims_flags_still_open_issue() -> None:
    # The exact #1566-#1575 defect shape: a referenced issue still OPEN.
    states: dict[int, dict[str, Any] | None] = {1547: _open_state()}
    assert csd.find_unverified_consolidation_claims(1566, [1547], states) == [1547]


def test_find_unverified_consolidation_claims_flags_closed_for_different_reason() -> None:
    states: dict[int, dict[str, Any] | None] = {
        1547: {"state": "CLOSED", "state_reason": "COMPLETED", "duplicate_of_number": None}
    }
    assert csd.find_unverified_consolidation_claims(1566, [1547], states) == [1547]


def test_find_unverified_consolidation_claims_flags_duplicate_of_a_different_issue() -> None:
    states: dict[int, dict[str, Any] | None] = {1547: _verified_state(1571)}
    assert csd.find_unverified_consolidation_claims(1566, [1547], states) == [1547]


def test_find_unverified_consolidation_claims_flags_unresolvable_issue() -> None:
    states: dict[int, dict[str, Any] | None] = {1547: None}
    assert csd.find_unverified_consolidation_claims(1566, [1547], states) == [1547]


def test_find_unverified_consolidation_claims_reports_only_the_violating_subset() -> None:
    states: dict[int, dict[str, Any] | None] = {1547: _verified_state(1566), 1546: _open_state()}
    assert csd.find_unverified_consolidation_claims(1566, [1547, 1546], states) == [1546]


# ---------------------------------------------------------------------------
# find_consolidation_violations
# ---------------------------------------------------------------------------


def test_find_consolidation_violations_empty_for_umbrella_with_no_referenced_numbers() -> None:
    assert csd.find_consolidation_violations({1500: []}, {}) == {}


def test_find_consolidation_violations_reports_offending_umbrella() -> None:
    states: dict[int, dict[str, Any] | None] = {1547: _verified_state(1566), 1546: _open_state()}
    assert csd.find_consolidation_violations({1566: [1547, 1546]}, states) == {1566: [1546]}


def test_find_consolidation_violations_skips_umbrella_with_no_violations() -> None:
    states: dict[int, dict[str, Any] | None] = {1547: _verified_state(1566)}
    assert csd.find_consolidation_violations({1566: [1547]}, states) == {}


def test_find_consolidation_violations_reports_multiple_umbrellas_independently() -> None:
    states: dict[int, dict[str, Any] | None] = {1547: _verified_state(1566), 1600: _open_state()}
    assert csd.find_consolidation_violations({1566: [1547], 1568: [1600]}, states) == {1568: [1600]}


# ---------------------------------------------------------------------------
# format_consolidation_drift_report
# ---------------------------------------------------------------------------


def test_format_consolidation_drift_report_pass_when_no_violations() -> None:
    report = csd.format_consolidation_drift_report({}, "gate-proposal")
    assert "PASS" in report
    assert "gate-proposal" in report


def test_format_consolidation_drift_report_fail_names_umbrella_and_violating_issues() -> None:
    report = csd.format_consolidation_drift_report({1566: [1547, 1546]}, "gate-proposal")
    assert "FAIL" in report
    assert "#1566" in report
    assert "#1547" in report
    assert "#1546" in report


def test_format_consolidation_drift_report_sorts_umbrellas_and_violations() -> None:
    report = csd.format_consolidation_drift_report({1568: [1600], 1566: [1547, 1489]}, "gate-proposal")
    lines = report.splitlines()
    umbrella_lines = [line for line in lines if line.strip().startswith("#")]
    assert umbrella_lines[0].startswith("  #1566")
    assert "#1489" in umbrella_lines[0]
    assert umbrella_lines[0].index("#1489") < umbrella_lines[0].index("#1547")
    assert umbrella_lines[1].startswith("  #1568")


# ---------------------------------------------------------------------------
# fetch_issue_duplicate_state (I/O, mocked opener)
# ---------------------------------------------------------------------------


def test_fetch_issue_duplicate_state_returns_parsed_fields_on_success() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(
            200,
            json.dumps(
                {
                    "data": {
                        "repository": {
                            "issue": {
                                "number": 1547,
                                "state": "CLOSED",
                                "stateReason": "DUPLICATE",
                                "duplicateOf": {"number": 1566},
                            }
                        }
                    }
                }
            ),
        )

    result = csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)
    assert result == {"state": "CLOSED", "state_reason": "DUPLICATE", "duplicate_of_number": 1566}


def test_fetch_issue_duplicate_state_returns_none_when_issue_not_found() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"data": {"repository": {"issue": None}}}))

    result = csd.fetch_issue_duplicate_state("tvna", "gitapex", 999999, "tok", opener=opener, sleeper=lambda _: None)
    assert result is None


def test_fetch_issue_duplicate_state_returns_none_when_duplicate_of_is_absent() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(
            200,
            json.dumps(
                {
                    "data": {
                        "repository": {
                            "issue": {
                                "number": 1547,
                                "state": "CLOSED",
                                "stateReason": "COMPLETED",
                                "duplicateOf": None,
                            }
                        }
                    }
                }
            ),
        )

    result = csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)
    assert result == {"state": "CLOSED", "state_reason": "COMPLETED", "duplicate_of_number": None}


def test_fetch_issue_duplicate_state_raises_on_200_with_errors_field() -> None:
    # A 200 response can still carry a GraphQL "errors" entry with
    # data.repository: null (e.g. a scope or field error unrelated to any
    # one issue number) -- this is a systemic failure that must stop the
    # run, never be silently read as "issue unresolvable, one violation"
    # (found by an adversarial review pass against this script's own diff).
    def opener(request: urllib.request.Request) -> Response:
        return Response(
            200,
            json.dumps({"data": {"repository": None}, "errors": [{"message": "Field 'duplicateOf' does not exist"}]}),
        )

    with pytest.raises(csd.GitHubApiError, match="errors"):
        csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)


def test_fetch_issue_duplicate_state_raises_on_persistent_http_error() -> None:
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "boom")

    with pytest.raises(csd.GitHubApiError):
        csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)


# ---------------------------------------------------------------------------
# fetch_issue_duplicate_state -- defeat tests against malformed GraphQL
# responses (dimension 15 of evaluating-deterministic-gate-quality:
# fail-closed on malformed input, independently constructed and run
# directly against the gate rather than only exercising happy-path
# fixtures). A 200 response with a well-formed HTTP envelope but a
# GraphQL body shaped nothing like the expected schema must never be
# misread as "verified" -- it must resolve to None, which
# find_unverified_consolidation_claims already treats as a violation.
# ---------------------------------------------------------------------------


def test_fetch_issue_duplicate_state_returns_none_on_completely_empty_body() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "{}")

    result = csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)
    assert result is None


def test_fetch_issue_duplicate_state_returns_none_when_repository_is_null() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"data": {"repository": None}}))

    result = csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)
    assert result is None


def test_fetch_issue_duplicate_state_returns_none_when_data_is_wrong_type() -> None:
    # Type confusion attempt: `data` is a list, not the expected object.
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"data": ["unexpected", "array"]}))

    result = csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)
    assert result is None


def test_fetch_issue_duplicate_state_returns_none_when_issue_is_wrong_type() -> None:
    # Type confusion attempt: `issue` is a bare string, not the expected object.
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"data": {"repository": {"issue": "not-a-dict"}}}))

    result = csd.fetch_issue_duplicate_state("tvna", "gitapex", 1547, "tok", opener=opener, sleeper=lambda _: None)
    assert result is None


def test_unresolvable_referenced_issue_is_always_a_violation_not_a_silent_pass() -> None:
    # Ties the malformed-input cases above to the actual fail-closed
    # consequence: a None state must never be read as "nothing to
    # report" -- it is exactly as much a violation as a confirmed-open
    # issue is.
    assert csd.find_unverified_consolidation_claims(1566, [1547], {1547: None}) == [1547]


# ---------------------------------------------------------------------------
# main -- CLI arg validation
# ---------------------------------------------------------------------------


def test_main_exits_one_on_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert csd.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_rejects_blank_owner(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = csd.main(["--owner", "", "--repo", "gitapex"])
    assert exit_code == 1
    assert "--owner" in capsys.readouterr().err


def test_main_rejects_blank_repo(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = csd.main(["--owner", "tvna", "--repo", ""])
    assert exit_code == 1
    assert "--repo" in capsys.readouterr().err


def test_main_rejects_whitespace_only_label(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = csd.main(["--owner", "tvna", "--repo", "gitapex", "--label", "  "])
    assert exit_code == 1
    assert "--label" in capsys.readouterr().err


def test_main_uses_gate_proposal_label_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    seen: dict[str, str] = {}

    def fake_label_exists(owner: str, repo: str, label: str, token: str, **kwargs: Any) -> bool:
        seen["label"] = label
        return True

    monkeypatch.setattr(csd.gate_drift, "label_exists", fake_label_exists)
    monkeypatch.setattr(csd.gate_drift, "list_labelled_issue_records", lambda *a, **k: [])
    csd.main(["--owner", "tvna", "--repo", "gitapex"])
    assert seen["label"] == csd.gate_drift.GATE_PROPOSAL_LABEL


# ---------------------------------------------------------------------------
# main -- label-liveness guard
# ---------------------------------------------------------------------------


def test_main_fails_loudly_when_label_does_not_exist(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(csd.gate_drift, "label_exists", lambda *a, **k: False)
    exit_code = csd.main(["--owner", "tvna", "--repo", "gitapex", "--label", "gate-proposal"])
    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "gate-proposal" in stderr
    assert "does not exist" in stderr


def test_main_does_not_fetch_issues_when_label_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(csd.gate_drift, "label_exists", lambda *a, **k: False)

    def fail_if_called(*a: Any, **k: Any) -> None:
        raise AssertionError("list_labelled_issue_records must not run when the label is missing")

    monkeypatch.setattr(csd.gate_drift, "list_labelled_issue_records", fail_if_called)
    assert csd.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_label_exists_github_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*a: Any, **k: Any) -> bool:
        raise csd.GitHubApiError("boom")

    monkeypatch.setattr(csd.gate_drift, "label_exists", raise_api_error)
    assert csd.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


# ---------------------------------------------------------------------------
# _is_blank / ScanConsolidationDriftArgs._reject_whitespace_only (issue #1094's
# own invisible-character finding, reproduced here as this script's own
# independent copy of the check -- see the module docstring for why)
# ---------------------------------------------------------------------------


def test_is_blank_true_for_empty_string() -> None:
    assert csd._is_blank("") is True


def test_is_blank_true_for_ordinary_whitespace() -> None:
    assert csd._is_blank("   \t\n") is True


def test_is_blank_true_for_zero_width_space() -> None:
    assert csd._is_blank("\u200b") is True


def test_is_blank_false_for_meaningful_text() -> None:
    assert csd._is_blank("tvna") is False


def test_is_blank_false_for_padded_but_meaningful_text() -> None:
    assert csd._is_blank("  tvna  ") is False


def test_reject_whitespace_only_returns_value_unchanged_when_meaningful() -> None:
    assert csd.ScanConsolidationDriftArgs._reject_whitespace_only("tvna") == "tvna"


def test_reject_whitespace_only_raises_on_blank_value() -> None:
    with pytest.raises(ValueError):
        csd.ScanConsolidationDriftArgs._reject_whitespace_only("")


def test_scan_consolidation_drift_args_rejects_blank_owner() -> None:
    with pytest.raises(csd.ValidationError):
        csd.ScanConsolidationDriftArgs(owner="", repo="gitapex", label="gate-proposal")


def test_scan_consolidation_drift_args_rejects_whitespace_only_repo() -> None:
    with pytest.raises(csd.ValidationError):
        csd.ScanConsolidationDriftArgs(owner="tvna", repo="   ", label="gate-proposal")


def test_scan_consolidation_drift_args_rejects_invisible_only_label() -> None:
    with pytest.raises(csd.ValidationError):
        csd.ScanConsolidationDriftArgs(owner="tvna", repo="gitapex", label="\u200b")


def test_scan_consolidation_drift_args_accepts_meaningful_values() -> None:
    args = csd.ScanConsolidationDriftArgs(owner="tvna", repo="gitapex", label="gate-proposal")
    assert args.owner == "tvna"
    assert args.repo == "gitapex"
    assert args.label == "gate-proposal"


# ---------------------------------------------------------------------------
# main -- end-to-end regression: the exact #1566-#1575 defect class
# ---------------------------------------------------------------------------


def _umbrella_record(number: int, consolidates: list[int]) -> dict[str, Any]:
    refs = ", ".join(f"#{n}" for n in consolidates)
    return {"number": number, "body": f"This umbrella consolidates several findings.\n\nConsolidates: {refs}\n"}


def test_main_fails_when_a_referenced_issue_is_still_open(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reproduces the exact original defect (issue #1653): an umbrella's
    Consolidates: line names an issue that is not closed as its
    duplicate -- here, still OPEN, exactly #1566-#1575's own shape before
    a human closed the 32 referenced issues by hand."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(csd.gate_drift, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(csd.gate_drift, "list_labelled_issue_records", lambda *a, **k: [_umbrella_record(1566, [1547])])
    monkeypatch.setattr(
        csd,
        "fetch_issue_duplicate_state",
        lambda owner, repo, number, token: _open_state(),
    )
    exit_code = csd.main(["--owner", "tvna", "--repo", "gitapex"])
    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL" in stdout
    assert "#1566" in stdout
    assert "#1547" in stdout


def test_main_passes_once_referenced_issue_is_closed_as_duplicate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same fixture as the failing case above, once #1547 is properly
    closed as #1566's own duplicate -- confirms the check clears once the
    original defect is actually fixed."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(csd.gate_drift, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(csd.gate_drift, "list_labelled_issue_records", lambda *a, **k: [_umbrella_record(1566, [1547])])
    monkeypatch.setattr(
        csd,
        "fetch_issue_duplicate_state",
        lambda owner, repo, number, token: _verified_state(1566),
    )
    exit_code = csd.main(["--owner", "tvna", "--repo", "gitapex"])
    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS" in stdout


def test_main_passes_for_issue_with_no_consolidates_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(csd.gate_drift, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        csd.gate_drift,
        "list_labelled_issue_records",
        lambda *a, **k: [{"number": 1500, "body": "An ordinary gate-proposal issue."}],
    )

    def fail_if_called(owner: str, repo: str, number: int, token: str) -> dict[str, Any] | None:
        raise AssertionError("fetch_issue_duplicate_state must not run for an issue with no Consolidates: line")

    monkeypatch.setattr(csd, "fetch_issue_duplicate_state", fail_if_called)
    exit_code = csd.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_deduplicates_a_referenced_issue_shared_by_two_umbrellas(monkeypatch: pytest.MonkeyPatch) -> None:
    """A referenced issue named by more than one umbrella's Consolidates:
    line must be fetched only once, not once per umbrella."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(csd.gate_drift, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        csd.gate_drift,
        "list_labelled_issue_records",
        lambda *a, **k: [_umbrella_record(1566, [1547]), _umbrella_record(1568, [1547])],
    )
    calls: list[int] = []

    def counting_fetch(owner: str, repo: str, number: int, token: str) -> dict[str, Any] | None:
        calls.append(number)
        return _verified_state(1566)

    monkeypatch.setattr(csd, "fetch_issue_duplicate_state", counting_fetch)
    csd.main(["--owner", "tvna", "--repo", "gitapex"])
    assert calls == [1547]


def test_main_exits_one_on_github_api_error_during_graphql_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(csd.gate_drift, "label_exists", lambda *a, **k: True)
    monkeypatch.setattr(csd.gate_drift, "list_labelled_issue_records", lambda *a, **k: [_umbrella_record(1566, [1547])])

    def raise_api_error(owner: str, repo: str, number: int, token: str) -> dict[str, Any] | None:
        raise csd.GitHubApiError("boom")

    monkeypatch.setattr(csd, "fetch_issue_duplicate_state", raise_api_error)
    assert csd.main(["--owner", "tvna", "--repo", "gitapex"]) == 1

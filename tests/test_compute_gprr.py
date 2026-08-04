"""Tests for the GPRR computation script
(.github/scripts/compute_gprr.py).

Refs #726: computes the Gate-Preventable Repair Rate from existing
`label:retrospective` issues, reusing
scan_retrospective_gate_drift.py's fetch machinery per the issue's own
constraint.

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring
test_scan_retrospective_gate_drift.py's own fixture style. Fully typed
(unlike its sibling test_scan_retrospective_gate_drift.py, a
pre-existing, separately tracked exception in
`pyproject.toml`'s `[tool.mypy.overrides]` Tier B): this is a new file,
so it carries no historical typing debt to inherit.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import compute_gprr as gprr
import pytest
import scan_retrospective_gate_drift as gate_drift


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


# ---------------------------------------------------------------------------
# parse_status_tags
# ---------------------------------------------------------------------------


def test_parse_status_tags_matches_each_vocabulary_slug() -> None:
    body = (
        "1. [thing] repair.\n"
        "   Classification: missing deterministic gate.\n"
        "   Status: `missing-deterministic-gate`\n"
        "   Proposed gate: text.\n"
        "\n"
        "2. [other] repair.\n"
        "   Classification: unclear agent instruction.\n"
        "   Status: `unclear-agent-instruction`\n"
    )
    assert gprr.parse_status_tags(body) == ["missing-deterministic-gate", "unclear-agent-instruction"]


def test_parse_status_tags_matches_external_human_decision_and_carried_forward() -> None:
    body = "   Status: `external-human-decision`\n- carried gate\n  Status: `carried-forward`\n"
    assert gprr.parse_status_tags(body) == ["external-human-decision", "carried-forward"]


def test_parse_status_tags_ignores_mid_sentence_mention() -> None:
    # SKILL.md's own injection concern: untrusted free-prose text that
    # merely *mentions* a Status-shaped string must not count as a real
    # field line -- only its own dedicated line does.
    body = 'The reviewer wrote "the commit said Status: `missing-deterministic-gate` but that was wrong" here.'
    assert gprr.parse_status_tags(body) == []


def test_parse_status_tags_ignores_unknown_slug() -> None:
    body = "   Status: `some-future-category`\n"
    assert gprr.parse_status_tags(body) == []


def test_parse_status_tags_empty_body() -> None:
    assert gprr.parse_status_tags("") == []


# ---------------------------------------------------------------------------
# week_key
# ---------------------------------------------------------------------------


def test_week_key_ordinary_date() -> None:
    assert gprr.week_key("2026-07-28T10:00:00Z") == "2026-W31"


def test_week_key_crosses_iso_year_boundary() -> None:
    # 2025-12-29 falls in the ISO week-numbering year 2026, not calendar
    # year 2025 -- using isocalendar()'s own year avoids a late-December
    # timestamp silently bucketing into the wrong year.
    assert gprr.week_key("2025-12-29T00:00:00Z") == "2026-W01"


# ---------------------------------------------------------------------------
# _ratio
# ---------------------------------------------------------------------------


def test_ratio_returns_none_for_zero_denominator() -> None:
    assert gprr._ratio(5, 0) is None


def test_ratio_computes_fraction() -> None:
    assert gprr._ratio(1, 4) == 0.25


# ---------------------------------------------------------------------------
# build_weekly_series
# ---------------------------------------------------------------------------


def _issue(body: str, created_at: str) -> dict[str, str]:
    return {"body": body, "created_at": created_at}


def test_build_weekly_series_buckets_by_week_and_computes_ratios() -> None:
    issues: list[dict[str, Any]] = [
        _issue("Status: `missing-deterministic-gate`", "2026-07-28T00:00:00Z"),
        _issue("Status: `unclear-agent-instruction`", "2026-07-29T00:00:00Z"),
        _issue("Status: `missing-deterministic-gate`", "2026-08-03T00:00:00Z"),
    ]
    merged = ["2026-07-30T00:00:00Z", "2026-08-01T00:00:00Z"]

    series = gprr.build_weekly_series(issues, merged)
    assert [point["week"] for point in series] == ["2026-W31", "2026-W32"]

    week31 = series[0]
    assert week31["missing_deterministic_gate"] == 1
    assert week31["unclear_agent_instruction"] == 1
    assert week31["total_classified"] == 2
    assert week31["merged_pr_count"] == 2
    assert week31["gate_share_of_classified"] == 0.5
    assert week31["gate_share_of_merged_prs"] == 0.5

    week32 = series[1]
    assert week32["missing_deterministic_gate"] == 1
    assert week32["total_classified"] == 1
    assert week32["merged_pr_count"] == 0
    assert week32["gate_share_of_classified"] == 1.0
    assert week32["gate_share_of_merged_prs"] is None


def test_build_weekly_series_excludes_carried_forward_from_classified_total() -> None:
    issues: list[dict[str, Any]] = [_issue("Status: `carried-forward`", "2026-07-28T00:00:00Z")]
    series = gprr.build_weekly_series(issues, [])
    assert series[0]["carried_forward"] == 1
    assert series[0]["total_classified"] == 0
    assert series[0]["gate_share_of_classified"] is None


def test_build_weekly_series_reports_na_when_no_merged_prs_that_week() -> None:
    issues: list[dict[str, Any]] = [_issue("Status: `missing-deterministic-gate`", "2026-07-28T00:00:00Z")]
    series = gprr.build_weekly_series(issues, [])
    assert series[0]["merged_pr_count"] == 0
    assert series[0]["gate_share_of_merged_prs"] is None


def test_build_weekly_series_unions_weeks_from_both_inputs() -> None:
    # A week with a merged PR but zero retrospective issues still gets a
    # row, and vice versa.
    issues: list[dict[str, Any]] = [_issue("Status: `missing-deterministic-gate`", "2026-07-28T00:00:00Z")]
    merged = ["2026-08-03T00:00:00Z"]
    series = gprr.build_weekly_series(issues, merged)
    assert [point["week"] for point in series] == ["2026-W31", "2026-W32"]
    assert series[1]["total_classified"] == 0
    assert series[1]["merged_pr_count"] == 1


def test_build_weekly_series_skips_malformed_created_at() -> None:
    issues: list[dict[str, Any]] = [
        {"body": "Status: `missing-deterministic-gate`", "created_at": None},
        {"body": "Status: `missing-deterministic-gate`"},
        _issue("Status: `missing-deterministic-gate`", "2026-07-28T00:00:00Z"),
    ]
    series = gprr.build_weekly_series(issues, [])
    assert len(series) == 1
    assert series[0]["missing_deterministic_gate"] == 1


def test_build_weekly_series_skips_malformed_merged_at() -> None:
    merged_timestamps: list[Any] = [None, "", "2026-07-28T00:00:00Z"]
    series = gprr.build_weekly_series([], merged_timestamps)
    assert len(series) == 1
    assert series[0]["merged_pr_count"] == 1


def test_build_weekly_series_treats_non_string_body_as_empty() -> None:
    issues: list[dict[str, Any]] = [{"body": None, "created_at": "2026-07-28T00:00:00Z"}]
    series = gprr.build_weekly_series(issues, [])
    assert series[0]["total_classified"] == 0


def test_build_weekly_series_empty_inputs() -> None:
    assert gprr.build_weekly_series([], []) == []


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_empty_series() -> None:
    report = gprr.format_report([], label="retrospective")
    assert "0 of 0 classified" in report
    assert "No 'retrospective'-labelled issue" in report


def test_format_report_leads_with_headline_and_lists_weeks() -> None:
    issues: list[dict[str, Any]] = [
        _issue("Status: `missing-deterministic-gate`", "2026-07-28T00:00:00Z"),
        _issue("Status: `unclear-agent-instruction`", "2026-07-28T00:00:00Z"),
        _issue("Status: `carried-forward`", "2026-07-28T00:00:00Z"),
    ]
    series = gprr.build_weekly_series(issues, ["2026-07-28T00:00:00Z"])
    report = gprr.format_report(series, label="retrospective")
    lines = report.splitlines()
    assert lines[0].startswith("Gate-Preventable Repair Rate (GPRR), all-time: 1 of 2 classified")
    assert "50.0%" in lines[0]
    assert "1 carried-forward gate mention(s)" in report
    assert "2026-W31: missing-deterministic-gate=1 of 2 classified (50.0%)" in report


def test_format_report_shows_na_for_zero_denominators() -> None:
    issues: list[dict[str, Any]] = [_issue("Status: `carried-forward`", "2026-07-28T00:00:00Z")]
    series = gprr.build_weekly_series(issues, [])
    report = gprr.format_report(series, label="retrospective")
    assert "n/a" in report


# ---------------------------------------------------------------------------
# list_merged_pull_requests
# ---------------------------------------------------------------------------


def test_list_merged_pull_requests_filters_unmerged() -> None:
    page = [
        {"number": 1, "merged_at": "2026-07-28T00:00:00Z"},
        {"number": 2, "merged_at": None},
        {"number": 3},
    ]

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(page))

    result = gprr.list_merged_pull_requests("tvna", "gitapex", "tok", opener=opener)
    assert result == ["2026-07-28T00:00:00Z"]


def test_list_merged_pull_requests_paginates_until_short_page() -> None:
    full_page = [{"number": n, "merged_at": "2026-07-28T00:00:00Z"} for n in range(100)]
    short_page = [{"number": 999, "merged_at": "2026-08-03T00:00:00Z"}]
    pages = [full_page, short_page]

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(pages.pop(0)))

    result = gprr.list_merged_pull_requests("tvna", "gitapex", "tok", opener=opener)
    assert len(result) == 101


def test_list_merged_pull_requests_stops_on_empty_page() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "[]")

    assert gprr.list_merged_pull_requests("tvna", "gitapex", "tok", opener=opener) == []


def test_list_merged_pull_requests_raises_on_persistent_4xx() -> None:
    def opener(request: urllib.request.Request) -> Response:
        raise urllib.error.HTTPError("https://example.test", 404, "err", {}, Response(404, "not found"))  # type: ignore[arg-type]

    with pytest.raises(gate_drift.GitHubApiError):
        gprr.list_merged_pull_requests("tvna", "gitapex", "tok", opener=opener)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_prints_report_and_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(
        gate_drift,
        "list_labelled_issue_records",
        lambda *a, **k: [_issue("Status: `missing-deterministic-gate`", "2026-07-28T00:00:00Z")],
    )
    monkeypatch.setattr(gprr, "list_merged_pull_requests", lambda *a, **k: ["2026-07-28T00:00:00Z"])
    exit_code = gprr.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Gate-Preventable Repair Rate (GPRR)" in out
    assert "2026-W31" in out


def test_main_exits_one_on_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert gprr.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_rejects_blank_owner(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gprr.main(["--owner", "", "--repo", "gitapex"])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_blank_repo(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gprr.main(["--owner", "tvna", "--repo", ""])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_blank_label(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = gprr.main(["--owner", "tvna", "--repo", "gitapex", "--label", ""])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_exits_one_on_issue_fetch_github_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*args: object, **kwargs: object) -> None:
        raise gate_drift.GitHubApiError("boom")

    monkeypatch.setattr(gate_drift, "list_labelled_issue_records", raise_api_error)
    assert gprr.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_exits_one_on_merged_pr_fetch_github_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate_drift, "list_labelled_issue_records", lambda *a, **k: [])

    def raise_api_error(*args: object, **kwargs: object) -> None:
        raise gate_drift.GitHubApiError("boom")

    monkeypatch.setattr(gprr, "list_merged_pull_requests", raise_api_error)
    assert gprr.main(["--owner", "tvna", "--repo", "gitapex"]) == 1


def test_main_uses_default_label_when_unspecified(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate_drift, "list_labelled_issue_records", lambda *a, **k: [])
    monkeypatch.setattr(gprr, "list_merged_pull_requests", lambda *a, **k: [])
    exit_code = gprr.main(["--owner", "tvna", "--repo", "gitapex"])
    assert exit_code == 0
    assert f"'{gate_drift.DEFAULT_LABEL}'" in capsys.readouterr().out

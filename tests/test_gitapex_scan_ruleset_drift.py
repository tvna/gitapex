"""Tests for the live-vs-committed ruleset comparison
(.github/scripts/gitapex_scan_ruleset_drift.py).

Refs #439. The behaviour worth pinning here is the three-valued exit code and
the deliberate one-directionality of the pull-request-time scope: exit 2 must
stay distinguishable from exit 1, or a state no pull request can fix becomes a
merge blocker (collapse to 1) or vanishes (collapse to 0).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import gitapex_scan_ruleset_drift as drift
import pytest

SOT: dict[str, Any] = {
    "name": "main-protection",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "bypass_actors": [],
    "rules": [
        {"type": "deletion"},
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": "pytest"}, {"context": "ruff"}]},
        },
    ],
}


def write_sot(tmp_path: pathlib.Path, document: Any = SOT) -> pathlib.Path:
    path = tmp_path / "main.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def fetcher(list_body: Any, detail_body: Any = None) -> Any:
    def fetch(url: str) -> Any:
        return detail_body if "/rulesets/" in url else list_body

    return fetch


def live_fetcher(live: dict[str, Any]) -> Any:
    return fetcher([{"id": 7, "name": SOT["name"]}], dict(live, id=7))


def test_matching_live_ruleset_is_in_sync_in_both_scopes(tmp_path: pathlib.Path) -> None:
    for scope in ("required-checks", "full"):
        report, code = drift.run("o/r", write_sot(tmp_path), scope, live_fetcher(dict(SOT)))
        assert code == drift.EXIT_IN_SYNC, scope
        assert "matches" in report or "requires every status check" in report


def test_absent_live_ruleset_is_unverified_not_drift(tmp_path: pathlib.Path) -> None:
    # Exit 2, not 1: applying the committed file is a human dispatch, so no
    # pull request can clear this state and none should be blocked by it.
    report, code = drift.run("o/r", write_sot(tmp_path), "full", fetcher([]))
    assert code == drift.EXIT_UNVERIFIED
    assert "has not been applied to GitHub yet" in report


def test_required_checks_scope_fails_when_the_live_ruleset_lags(tmp_path: pathlib.Path) -> None:
    live = dict(
        SOT,
        rules=[
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": [{"context": "pytest"}]},
            }
        ],
    )
    report, code = drift.run("o/r", write_sot(tmp_path), "required-checks", live_fetcher(live))
    assert code == drift.EXIT_DRIFT
    assert "`ruff`" in report
    assert "missing 1 required status check" in report


def test_required_checks_scope_ignores_extra_live_contexts(tmp_path: pathlib.Path) -> None:
    # A context live but absent from the committed file is the shape of an
    # in-flight removal; failing it here would block the removal from landing.
    live = dict(
        SOT,
        rules=[
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [{"context": "pytest"}, {"context": "ruff"}, {"context": "mypy"}]
                },
            }
        ],
    )
    _, code = drift.run("o/r", write_sot(tmp_path), "required-checks", live_fetcher(live))
    assert code == drift.EXIT_IN_SYNC


def test_full_scope_catches_what_the_required_checks_scope_ignores(tmp_path: pathlib.Path) -> None:
    # A rule silently removed in the Settings UI: invisible to the one-
    # directional pull-request-time scope, caught by the scheduled scan.
    live = dict(SOT, rules=[rule for rule in SOT["rules"] if rule["type"] != "deletion"])
    _, pr_code = drift.run("o/r", write_sot(tmp_path), "required-checks", live_fetcher(live))
    report, full_code = drift.run("o/r", write_sot(tmp_path), "full", live_fetcher(live))
    assert pr_code == drift.EXIT_IN_SYNC
    assert full_code == drift.EXIT_DRIFT
    assert "```diff" in report


def test_full_scope_ignores_api_only_fields(tmp_path: pathlib.Path) -> None:
    live = dict(SOT, created_at="2026-08-09", node_id="R_x", _links={})
    _, code = drift.run("o/r", write_sot(tmp_path), "full", live_fetcher(live))
    assert code == drift.EXIT_IN_SYNC


def test_compare_required_checks_is_one_directional() -> None:
    sot = {"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "a"}]}}]}
    live = {"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "b"}]}}]}
    assert drift.compare_required_checks(live, sot) == ["a"]
    assert drift.compare_required_checks(sot, live) == ["b"]


def test_main_treats_a_missing_token_as_unverified(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    code = drift.main(["--repo", "o/r", "--sot", str(write_sot(tmp_path)), "--scope", "full"])
    assert code == drift.EXIT_UNVERIFIED
    assert "nothing was verified" in capsys.readouterr().out


def test_main_prints_the_report_and_returns_the_scan_code(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(drift, "default_fetch", lambda url, token: [])
    code = drift.main(["--repo", "o/r", "--sot", str(write_sot(tmp_path)), "--scope", "full"])
    assert code == drift.EXIT_UNVERIFIED
    assert "main-protection" in capsys.readouterr().out


def test_main_reports_a_ruleset_error_as_an_annotated_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    code = drift.main(["--repo", "o/r", "--sot", str(tmp_path / "absent.json"), "--scope", "full"])
    assert code == drift.EXIT_DRIFT
    assert "::error::" in capsys.readouterr().err


def test_default_fetch_delegates_to_the_shared_client(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_fetch(url: str, token: str, opener: Any, sleeper: Any) -> Any:
        seen.update({"url": url, "token": token})
        return []

    monkeypatch.setattr(drift, "fetch_json_document", fake_fetch)
    assert drift.default_fetch("https://api.github.test/x", "tok") == []
    assert seen == {"url": "https://api.github.test/x", "token": "tok"}


def test_an_api_read_failure_is_unverified_not_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Exit 1 would make the workflow assert what the live ruleset contains,
    # which during an outage or with a rejected credential is a claim this scan
    # has no evidence for. A warning naming the real HTTP failure is honest.
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def boom(url: str, token: str) -> Any:
        raise drift.GitHubApiError("GET https://api.github.test/x failed: HTTP 403: Resource not accessible")

    monkeypatch.setattr(drift, "default_fetch", boom)
    code = drift.main(["--repo", "o/r", "--sot", str(write_sot(tmp_path)), "--scope", "full"])
    assert code == drift.EXIT_UNVERIFIED
    out = capsys.readouterr().out
    # On stdout, because that is the stream both workflows tee into the job
    # summary -- a stderr-only diagnostic leaves the summary blank exactly when
    # someone needs to read it.
    assert "HTTP 403" in out
    assert "Nothing was verified" in out


def test_an_unusable_committed_file_still_fails_the_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # RulesetError is not a read failure: the repository's own file is broken,
    # or two live rulesets share one name. Both are real and actionable.
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    code = drift.main(["--repo", "o/r", "--sot", str(broken), "--scope", "full"])
    assert code == drift.EXIT_DRIFT
    captured = capsys.readouterr()
    assert "::error::" in captured.err
    assert "not valid JSON" in captured.out

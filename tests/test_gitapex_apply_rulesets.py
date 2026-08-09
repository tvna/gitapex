"""Tests for the ruleset plan/apply CLI
(.github/scripts/gitapex_apply_rulesets.py).

Refs #439. This is the only script in the repository that writes to the GitHub
Rulesets API, so the properties under test are safety properties, not
formatting ones: plan mode must never invoke the writer, the create-vs-replace
decision must come from what is live rather than from an operator-supplied id,
and a missing credential must stop the run instead of quietly changing the
plan.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
from typing import Any

import gitapex_apply_rulesets as apply_rulesets
import pytest

SOT = {
    "name": "main-protection",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "bypass_actors": [],
    "rules": [{"type": "deletion"}],
}


class RecordingWriter:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.response = response if response is not None else {"id": 7}

    def __call__(self, url: str, method: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((url, method, body))
        return self.response


class Response:
    def __init__(self, body: str) -> None:
        self.body = body.encode()

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def write_sot(tmp_path: pathlib.Path, document: Any = SOT) -> pathlib.Path:
    path = tmp_path / "main.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def fetcher(list_body: Any, detail_body: Any = None) -> Any:
    def fetch(url: str) -> Any:
        return detail_body if "/rulesets/" in url else list_body

    return fetch


def test_plan_mode_never_calls_the_writer(tmp_path: pathlib.Path) -> None:
    # The whole dry-run guarantee in apply-rulesets.yml rests on this.
    writer = RecordingWriter()
    summary = apply_rulesets.run("o/r", write_sot(tmp_path), "plan", fetcher([]), writer)
    assert writer.calls == []
    assert "POST" in summary


def test_absent_live_ruleset_plans_a_create(tmp_path: pathlib.Path) -> None:
    summary = apply_rulesets.run("o/r", write_sot(tmp_path), "plan", fetcher([]), RecordingWriter())
    assert "nothing to diff against" in summary


def test_existing_live_ruleset_plans_a_replace_onto_its_own_id(tmp_path: pathlib.Path) -> None:
    live = dict(SOT, id=42, enforcement="disabled")
    plan = apply_rulesets.plan_write("o/r", SOT, live)
    assert plan["method"] == "PUT"
    assert plan["url"].endswith("/repos/o/r/rulesets/42")
    assert plan["live_id"] == 42


def test_apply_mode_sends_the_planned_request(tmp_path: pathlib.Path) -> None:
    writer = RecordingWriter({"id": 42})
    live = dict(SOT, id=42, enforcement="disabled")
    summary = apply_rulesets.run(
        "o/r", write_sot(tmp_path), "apply", fetcher([{"id": 42, "name": SOT["name"]}], live), writer
    )
    assert len(writer.calls) == 1
    url, method, body = writer.calls[0]
    assert (method, url) == ("PUT", "https://api.github.com/repos/o/r/rulesets/42")
    # The body is the projection of the committed file, not the live state --
    # applying must move GitHub toward git, never echo GitHub back at itself.
    assert body["enforcement"] == "active"
    assert "id" not in body
    assert "| 42 |" in summary


def test_summary_shows_a_diff_when_live_differs(tmp_path: pathlib.Path) -> None:
    live = dict(SOT, id=42, enforcement="disabled")
    summary = apply_rulesets.run(
        "o/r", write_sot(tmp_path), "plan", fetcher([{"id": 42, "name": SOT["name"]}], live), RecordingWriter()
    )
    assert "```diff" in summary
    assert "disabled" in summary


def test_summary_says_no_op_when_live_already_matches(tmp_path: pathlib.Path) -> None:
    live = dict(SOT, id=42)
    summary = apply_rulesets.run(
        "o/r", write_sot(tmp_path), "plan", fetcher([{"id": 42, "name": SOT["name"]}], live), RecordingWriter()
    )
    assert "no-op replace" in summary


def test_read_token_refuses_to_fall_back_to_an_anonymous_request(monkeypatch: pytest.MonkeyPatch) -> None:
    # An anonymous rulesets GET 404s for a repository the caller cannot see,
    # which this script would then read as "no live ruleset -> POST".
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(apply_rulesets.RulesetError, match="GITHUB_TOKEN is empty"):
        apply_rulesets.read_token()


def test_send_write_posts_the_body_and_parses_the_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    seen: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int = 0) -> Response:
        seen["method"] = request.method
        seen["body"] = json.loads(request.data.decode())
        seen["auth"] = request.get_header("Authorization")
        return Response(json.dumps({"id": 7}))

    monkeypatch.setattr(apply_rulesets.urllib.request, "urlopen", fake_urlopen)
    assert apply_rulesets.send_write("https://api.github.test/x", "POST", {"name": "n"}) == {"id": 7}
    assert seen["method"] == "POST"
    assert seen["body"] == {"name": "n"}
    assert seen["auth"] == "Bearer tok"


def test_send_write_surfaces_an_http_error_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def fake_urlopen(request: Any, timeout: int = 0) -> Response:
        raise urllib.error.HTTPError("u", 422, "Unprocessable", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(apply_rulesets.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(apply_rulesets.RulesetError, match="HTTP 422"):
        apply_rulesets.send_write("https://api.github.test/x", "POST", {})


def test_send_write_surfaces_a_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def fake_urlopen(request: Any, timeout: int = 0) -> Response:
        raise OSError("connection reset")

    monkeypatch.setattr(apply_rulesets.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(apply_rulesets.RulesetError, match="connection reset"):
        apply_rulesets.send_write("https://api.github.test/x", "POST", {})


def test_send_write_rejects_a_non_object_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(
        apply_rulesets.urllib.request, "urlopen", lambda request, timeout=0: Response(json.dumps(["x"]))
    )
    with pytest.raises(apply_rulesets.RulesetError, match="expected a JSON object"):
        apply_rulesets.send_write("https://api.github.test/x", "POST", {})


def test_default_fetch_reads_the_token_and_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    seen: dict[str, Any] = {}

    def fake_fetch(url: str, token: str, opener: Any, sleeper: Any) -> Any:
        seen["url"] = url
        seen["token"] = token
        return []

    monkeypatch.setattr(apply_rulesets, "fetch_json_document", fake_fetch)
    assert apply_rulesets.default_fetch("https://api.github.test/x") == []
    assert seen == {"url": "https://api.github.test/x", "token": "tok"}


def test_main_writes_the_summary_file_and_exits_zero(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(apply_rulesets, "default_fetch", lambda url: [])
    summary_file = tmp_path / "summary.md"
    code = apply_rulesets.main(
        [
            "--repo",
            "o/r",
            "--sot",
            str(write_sot(tmp_path)),
            "--mode",
            "plan",
            "--summary-file",
            str(summary_file),
        ]
    )
    assert code == 0
    assert "main-protection" in summary_file.read_text(encoding="utf-8")
    assert "main-protection" in capsys.readouterr().out


def test_main_reports_a_ruleset_error_as_an_annotated_failure(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = apply_rulesets.main(["--repo", "o/r", "--sot", str(tmp_path / "absent.json"), "--mode", "plan"])
    assert code == 1
    assert "::error::" in capsys.readouterr().err

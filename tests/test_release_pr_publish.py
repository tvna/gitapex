from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request

import pytest
import release_pr_publish as rpp


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
    # Response duck-types urlopen's context-manager response, not the stdlib
    # IO[bytes] HTTPError expects for its `fp` argument; mypy can't see the
    # structural match.
    return urllib.error.HTTPError("https://example.test", code, "err", {}, Response(code, body))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# apply_call
# ---------------------------------------------------------------------------


def test_apply_call_happy_path() -> None:
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        assert request.headers["Authorization"] == "Bearer tok"
        return Response(201, '{"ok":true}')

    code, body = rpp.apply_call(
        method="POST",
        url="https://api.github.com/x",
        payload={"a": 1},
        token="tok",
        opener=opener,
        sleeper=sleeps.append,
    )
    assert code == 201
    assert body == '{"ok":true}'
    assert sleeps == []


def test_apply_call_retries_5xx_then_succeeds() -> None:
    responses: list[urllib.error.HTTPError | Response] = [http_error(503, "one"), Response(200, "ok")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    code, body = rpp.apply_call(
        method="GET",
        url="https://api.github.com/x",
        payload=None,
        token="tok",
        opener=opener,
        sleeper=sleeps.append,
    )
    assert code == 200
    assert body == "ok"
    assert sleeps == [5]


def test_apply_call_breaks_on_4xx() -> None:
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise http_error(422, "bad")

    code, body = rpp.apply_call(method="GET", url="https://api.github.com/x", payload=None, token="tok", opener=opener)
    assert code == 422
    assert body == "bad"
    assert calls == 1


def test_apply_call_network_failure_retries_three_times() -> None:
    calls = 0
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    code, body = rpp.apply_call(
        method="GET",
        url="https://api.github.com/x",
        payload=None,
        token="tok",
        opener=opener,
        sleeper=sleeps.append,
    )
    assert code == 0
    assert body == "boom"
    assert calls == 3
    assert sleeps == [5, 10]


def test_apply_call_uses_default_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None) -> Response:
        captured["timeout"] = timeout
        return Response(200, "ok")

    monkeypatch.setattr(rpp.urllib.request, "urlopen", fake_urlopen)
    code, _body = rpp.apply_call(method="GET", url="https://api.github.com/x", payload=None, token="tok")
    assert code == 200
    assert captured["timeout"] == rpp._HTTP_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# graphql_call
# ---------------------------------------------------------------------------


def test_graphql_call_happy_path() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, '{"data":{"x":1}}')

    code, body = rpp.graphql_call(query="q", variables={}, token="tok", opener=opener)
    assert code == 200
    assert body == {"data": {"x": 1}}


def test_graphql_call_retries_5xx_then_succeeds() -> None:
    responses: list[urllib.error.HTTPError | Response] = [http_error(502, ""), Response(200, '{"data":{}}')]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    code, _body = rpp.graphql_call(query="q", variables={}, token="tok", opener=opener, sleeper=sleeps.append)
    assert code == 200
    assert sleeps == [5]


def test_graphql_call_retries_transient_marker_then_succeeds() -> None:
    transient_body = json.dumps({"errors": [{"message": "Something went wrong while executing your query."}]})
    responses = [Response(200, transient_body), Response(200, '{"data":{}}')]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    code, body = rpp.graphql_call(query="q", variables={}, token="tok", opener=opener, sleeper=sleeps.append)
    assert code == 200
    assert body == {"data": {}}
    assert sleeps == [5]


def test_graphql_call_non_transient_error_no_retry() -> None:
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        return Response(200, json.dumps({"errors": [{"message": "Validation failed"}]}))

    code, body = rpp.graphql_call(query="q", variables={}, token="tok", opener=opener)
    assert calls == 1
    assert code == 200
    assert "errors" in body


def test_graphql_call_network_failure_degrades_to_empty_body() -> None:
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        raise urllib.error.URLError("boom")

    code, body = rpp.graphql_call(query="q", variables={}, token="tok", opener=opener, sleeper=sleeps.append)
    assert code == 0
    assert body == {}
    assert sleeps == [5, 10]


def test_graphql_call_invalid_json_body() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "not json")

    code, body = rpp.graphql_call(query="q", variables={}, token="tok", opener=opener)
    assert code == 200
    assert body == {}


def test_graphql_call_uses_default_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None) -> Response:
        return Response(200, '{"data":{}}')

    monkeypatch.setattr(rpp.urllib.request, "urlopen", fake_urlopen)
    code, _body = rpp.graphql_call(query="q", variables={}, token="tok")
    assert code == 200


# ---------------------------------------------------------------------------
# _format_code
# ---------------------------------------------------------------------------


def test_format_code() -> None:
    assert rpp._format_code(0) == "000"
    assert rpp._format_code(404) == "404"


# ---------------------------------------------------------------------------
# Low-level GitHub REST helpers (apply_call injected directly)
# ---------------------------------------------------------------------------


def _fake_apply_call(responses: dict[str, tuple[int, str]]):
    calls: list[tuple[str, str]] = []

    def fake(*, method: str, url: str, payload, token: str) -> tuple[int, str]:
        calls.append((method, url))
        key = f"{method} {url}"
        if key in responses:
            return responses[key]
        return responses[url]

    return fake, calls


def test_get_ref_sha_success() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/git/ref/heads/main": (200, json.dumps({"object": {"sha": "abc"}}))}
    )
    sha = rpp._get_ref_sha(repo="o/r", ref="heads/main", token="tok", apply_call=fake)
    assert sha == "abc"


def test_get_ref_sha_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/main": (404, "nope")})
    with pytest.raises(RuntimeError, match="Get ref"):
        rpp._get_ref_sha(repo="o/r", ref="heads/main", token="tok", apply_call=fake)


def test_get_ref_sha_missing_sha_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/git/ref/heads/main": (200, json.dumps({"object": {}}))}
    )
    with pytest.raises(RuntimeError, match=r"missing object\.sha"):
        rpp._get_ref_sha(repo="o/r", ref="heads/main", token="tok", apply_call=fake)


def test_get_branch_head_oid_absent() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/chore": (404, "")})
    assert rpp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake) is None


def test_get_branch_head_oid_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/chore": (500, "boom")})
    with pytest.raises(RuntimeError, match="Get branch ref"):
        rpp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_get_branch_head_oid_success() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/git/ref/heads/chore": (200, json.dumps({"object": {"sha": "xyz"}}))}
    )
    assert rpp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake) == "xyz"


def test_get_branch_head_oid_missing_sha_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/git/ref/heads/chore": (200, json.dumps({"object": {}}))}
    )
    with pytest.raises(RuntimeError, match=r"missing object\.sha"):
        rpp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_create_branch_ref_success() -> None:
    fake, calls = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs": (201, "")})
    rpp._create_branch_ref(repo="o/r", branch="chore", sha="abc", token="tok", apply_call=fake)
    assert calls == [("POST", "https://api.github.com/repos/o/r/git/refs")]


def test_create_branch_ref_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs": (422, "exists")})
    with pytest.raises(RuntimeError, match="Create branch ref"):
        rpp._create_branch_ref(repo="o/r", branch="chore", sha="abc", token="tok", apply_call=fake)


def test_delete_branch_success() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs/heads/chore": (204, "")})
    rpp._delete_branch(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_delete_branch_already_gone_is_success() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs/heads/chore": (404, "")})
    rpp._delete_branch(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_delete_branch_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs/heads/chore": (500, "boom")})
    with pytest.raises(RuntimeError, match="Delete branch"):
        rpp._delete_branch(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_get_file_bytes_absent() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/contents/plugin.json?ref=main": (404, "")})
    assert rpp._get_file_bytes(repo="o/r", path="plugin.json", ref="main", token="tok", apply_call=fake) is None


def test_get_file_bytes_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/contents/plugin.json?ref=main": (500, "boom")})
    with pytest.raises(RuntimeError, match="Get contents"):
        rpp._get_file_bytes(repo="o/r", path="plugin.json", ref="main", token="tok", apply_call=fake)


def test_get_file_bytes_success() -> None:
    content = base64.b64encode(b"hello").decode("ascii")
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/plugin.json?ref=main": (
                200,
                json.dumps({"encoding": "base64", "content": content}),
            )
        }
    )
    assert rpp._get_file_bytes(repo="o/r", path="plugin.json", ref="main", token="tok", apply_call=fake) == b"hello"


def test_get_file_bytes_unexpected_encoding_raises() -> None:
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/plugin.json?ref=main": (
                200,
                json.dumps({"encoding": "none", "content": None}),
            )
        }
    )
    with pytest.raises(RuntimeError, match="unexpected encoding"):
        rpp._get_file_bytes(repo="o/r", path="plugin.json", ref="main", token="tok", apply_call=fake)


# ---------------------------------------------------------------------------
# _ref_drifts
# ---------------------------------------------------------------------------


def test_ref_drifts_true_when_content_differs() -> None:
    encoded = base64.b64encode(b"old").decode("ascii")
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/plugin.json?ref=main": (
                200,
                json.dumps({"encoding": "base64", "content": encoded}),
            )
        }
    )
    assert rpp._ref_drifts(repo="o/r", ref="main", additions=[("plugin.json", b"new")], token="tok", apply_call=fake)


def test_ref_drifts_false_when_content_matches() -> None:
    encoded = base64.b64encode(b"same").decode("ascii")
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/plugin.json?ref=main": (
                200,
                json.dumps({"encoding": "base64", "content": encoded}),
            )
        }
    )
    assert not rpp._ref_drifts(
        repo="o/r", ref="main", additions=[("plugin.json", b"same")], token="tok", apply_call=fake
    )


# ---------------------------------------------------------------------------
# _create_commit_on_branch
# ---------------------------------------------------------------------------


def test_create_commit_on_branch_success() -> None:
    def fake_graphql(*, query, variables, token):
        assert variables["input"]["message"]["body"] == "body text"
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": "newoid"}}}}

    oid = rpp._create_commit_on_branch(
        repo="o/r",
        branch="chore",
        expected_head_oid="base",
        headline="subject",
        body="body text",
        additions=[{"path": "a", "contents": "x"}],
        token="tok",
        graphql_call=fake_graphql,
    )
    assert oid == "newoid"


def test_create_commit_on_branch_no_body_omits_message_body() -> None:
    def fake_graphql(*, query, variables, token):
        assert "body" not in variables["input"]["message"]
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": "newoid"}}}}

    rpp._create_commit_on_branch(
        repo="o/r",
        branch="chore",
        expected_head_oid="base",
        headline="subject",
        body="",
        additions=[],
        token="tok",
        graphql_call=fake_graphql,
    )


def test_create_commit_on_branch_http_failure_raises() -> None:
    def fake_graphql(*, query, variables, token):
        return 500, {}

    with pytest.raises(RuntimeError, match="createCommitOnBranch HTTP"):
        rpp._create_commit_on_branch(
            repo="o/r",
            branch="chore",
            expected_head_oid="base",
            headline="s",
            body="",
            additions=[],
            token="tok",
            graphql_call=fake_graphql,
        )


def test_create_commit_on_branch_errors_in_response_raises() -> None:
    def fake_graphql(*, query, variables, token):
        return 200, {"errors": [{"message": "bad"}]}

    with pytest.raises(RuntimeError, match="createCommitOnBranch errors"):
        rpp._create_commit_on_branch(
            repo="o/r",
            branch="chore",
            expected_head_oid="base",
            headline="s",
            body="",
            additions=[],
            token="tok",
            graphql_call=fake_graphql,
        )


def test_create_commit_on_branch_unexpected_response_raises() -> None:
    def fake_graphql(*, query, variables, token):
        return 200, {"data": {}}

    with pytest.raises(RuntimeError, match="unexpected response"):
        rpp._create_commit_on_branch(
            repo="o/r",
            branch="chore",
            expected_head_oid="base",
            headline="s",
            body="",
            additions=[],
            token="tok",
            graphql_call=fake_graphql,
        )


def test_create_commit_on_branch_missing_oid_raises() -> None:
    def fake_graphql(*, query, variables, token):
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": ""}}}}

    with pytest.raises(RuntimeError, match="missing commit oid"):
        rpp._create_commit_on_branch(
            repo="o/r",
            branch="chore",
            expected_head_oid="base",
            headline="s",
            body="",
            additions=[],
            token="tok",
            graphql_call=fake_graphql,
        )


# ---------------------------------------------------------------------------
# PR helpers
# ---------------------------------------------------------------------------


def test_list_open_prs_success() -> None:
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (
                200,
                json.dumps([{"number": 1}]),
            )
        }
    )
    prs = rpp._list_open_prs(repo="o/r", head="chore", token="tok", apply_call=fake)
    assert prs == [{"number": 1}]


def test_list_open_prs_failure_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (500, "boom")}
    )
    with pytest.raises(RuntimeError, match="List PRs failed"):
        rpp._list_open_prs(repo="o/r", head="chore", token="tok", apply_call=fake)


def test_list_open_prs_unexpected_shape_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (200, json.dumps({"x": 1}))}
    )
    with pytest.raises(RuntimeError, match="Expected list"):
        rpp._list_open_prs(repo="o/r", head="chore", token="tok", apply_call=fake)


def test_create_pr_success() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/pulls": (201, json.dumps({"number": 7}))})
    number = rpp._create_pr(repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake)
    assert number == 7


def test_create_pr_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/pulls": (422, "bad")})
    with pytest.raises(RuntimeError, match="Create PR failed"):
        rpp._create_pr(repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake)


def test_update_pr_success() -> None:
    fake, calls = _fake_apply_call({"https://api.github.com/repos/o/r/pulls/7": (200, "")})
    rpp._update_pr(repo="o/r", number=7, title="t", body="b", token="tok", apply_call=fake)
    assert calls == [("PATCH", "https://api.github.com/repos/o/r/pulls/7")]


def test_update_pr_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/pulls/7": (500, "boom")})
    with pytest.raises(RuntimeError, match="Update PR failed"):
        rpp._update_pr(repo="o/r", number=7, title="t", body="b", token="tok", apply_call=fake)


def test_upsert_pr_creates_when_absent() -> None:
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (200, json.dumps([])),
            "https://api.github.com/repos/o/r/pulls": (201, json.dumps({"number": 9})),
        }
    )
    verb, number = rpp._upsert_pr(repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake)
    assert (verb, number) == ("created", 9)


def test_upsert_pr_updates_when_present() -> None:
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (
                200,
                json.dumps([{"number": 5}]),
            ),
            "https://api.github.com/repos/o/r/pulls/5": (200, ""),
        }
    )
    verb, number = rpp._upsert_pr(repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake)
    assert (verb, number) == ("updated", 5)


# ---------------------------------------------------------------------------
# build_pr_body
# ---------------------------------------------------------------------------

_NOTES_SPAN_RE = re.compile(
    re.escape(rpp._RELEASE_NOTES_START_MARKER) + r"\n(.*?)\n" + re.escape(rpp._RELEASE_NOTES_END_MARKER),
    re.DOTALL,
)


def _extract_notes_span(body: str) -> str:
    match = _NOTES_SPAN_RE.search(body)
    assert match is not None, "release-notes markers not found in PR body"
    return match.group(1)


def test_build_pr_body_marker_span_round_trips_exactly() -> None:
    notes = "### Features\n- add widget (abc1234)\n\n### Fixes\n- fix bug (def5678)\n"
    body = rpp.build_pr_body("0.1.0", "0.2.0", "minor", notes)
    assert _extract_notes_span(body) == notes


def test_build_pr_body_marker_span_round_trips_no_trailing_newline() -> None:
    notes = "### Features\n- add widget (abc1234)"
    body = rpp.build_pr_body("0.1.0", "0.2.0", "minor", notes)
    assert _extract_notes_span(body) == notes


def test_build_pr_body_marker_span_round_trips_empty_notes() -> None:
    notes = ""
    body = rpp.build_pr_body("0.1.0", "0.2.0", "patch", notes)
    assert _extract_notes_span(body) == notes


def test_build_pr_body_contains_markers_on_their_own_lines() -> None:
    body = rpp.build_pr_body("0.1.0", "0.2.0", "minor", "notes here")
    lines = body.splitlines()
    assert rpp._RELEASE_NOTES_START_MARKER in lines
    assert rpp._RELEASE_NOTES_END_MARKER in lines


def test_build_pr_body_contains_version_summary() -> None:
    body = rpp.build_pr_body("1.2.3", "1.3.0", "minor", "notes")
    assert "`1.2.3`" in body
    assert "`1.3.0`" in body
    assert "minor" in body


def test_build_pr_body_contains_release_act_trailer_and_warning() -> None:
    body = rpp.build_pr_body("0.1.0", "0.2.0", "minor", "notes")
    assert "release-tag.yml" in body
    assert "gitapex--vX.Y.Z" in body
    assert "GitHub Release" in body
    assert ".claude-plugin/plugin.json" in body
    assert "apm.yml" in body
    assert "Do not edit" in body


# ---------------------------------------------------------------------------
# publish_release_pr
# ---------------------------------------------------------------------------


def test_publish_release_pr_empty_additions_is_up_to_date() -> None:
    result = rpp.publish_release_pr(
        repo="o/r",
        additions=[],
        base="main",
        branch="chore/release-plugin-bump",
        title="t",
        body="b",
        commit_subject="s",
        commit_body="",
        token="tok",
    )
    assert result == "up-to-date"


def test_publish_release_pr_no_open_pr_no_existing_branch_creates() -> None:
    responses = {
        "https://api.github.com/repos/o/r/pulls?head=o:chore/release-plugin-bump&state=open&per_page=1": (
            200,
            json.dumps([]),
        ),
        "https://api.github.com/repos/o/r/git/refs/heads/chore/release-plugin-bump": (404, ""),
        "https://api.github.com/repos/o/r/git/ref/heads/chore/release-plugin-bump": (404, ""),
        "https://api.github.com/repos/o/r/git/ref/heads/main": (200, json.dumps({"object": {"sha": "basesha"}})),
        "https://api.github.com/repos/o/r/git/refs": (201, ""),
        "https://api.github.com/repos/o/r/pulls": (201, json.dumps({"number": 3})),
    }
    fake, calls = _fake_apply_call(responses)
    captured_additions: list[dict[str, str]] = []

    def fake_graphql(*, query, variables, token):
        assert variables["input"]["expectedHeadOid"] == "basesha"
        captured_additions.extend(variables["input"]["fileChanges"]["additions"])
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": "newsha"}}}}

    result = rpp.publish_release_pr(
        repo="o/r",
        additions=[(".claude-plugin/plugin.json", b'{"version": "0.2.0"}'), ("apm.yml", b"version: 0.2.0")],
        base="main",
        branch="chore/release-plugin-bump",
        title="chore(plugin): bump version to 0.2.0",
        body="b",
        commit_subject="chore(plugin): bump version to 0.2.0",
        commit_body="",
        token="tok",
        apply_call=fake,
        graphql_call=fake_graphql,
    )

    assert result == "created:3"
    # Both manifest paths land in a single createCommitOnBranch call, never
    # as two separate commits.
    assert len(captured_additions) == 2
    assert {addition["path"] for addition in captured_additions} == {".claude-plugin/plugin.json", "apm.yml"}
    assert ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/chore/release-plugin-bump") in calls


def test_publish_release_pr_open_pr_updates_and_leaves_branch_alone() -> None:
    responses = {
        "https://api.github.com/repos/o/r/pulls?head=o:chore/release-plugin-bump&state=open&per_page=1": (
            200,
            json.dumps([{"number": 4}]),
        ),
        "https://api.github.com/repos/o/r/git/ref/heads/chore/release-plugin-bump": (
            200,
            json.dumps({"object": {"sha": "branchtip"}}),
        ),
        "https://api.github.com/repos/o/r/contents/.claude-plugin/plugin.json?ref=chore/release-plugin-bump": (
            404,
            "",
        ),
        "https://api.github.com/repos/o/r/pulls/4": (200, ""),
    }
    fake, calls = _fake_apply_call(responses)
    captured_additions: list[dict[str, str]] = []

    def fake_graphql(*, query, variables, token):
        assert variables["input"]["expectedHeadOid"] == "branchtip"
        captured_additions.extend(variables["input"]["fileChanges"]["additions"])
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": "newsha"}}}}

    result = rpp.publish_release_pr(
        repo="o/r",
        additions=[(".claude-plugin/plugin.json", b'{"version": "0.2.0"}'), ("apm.yml", b"version: 0.2.0")],
        base="main",
        branch="chore/release-plugin-bump",
        title="chore(plugin): bump version to 0.2.0",
        body="b",
        commit_subject="chore(plugin): bump version to 0.2.0",
        commit_body="",
        token="tok",
        apply_call=fake,
        graphql_call=fake_graphql,
    )

    assert result == "updated:4"
    assert len(captured_additions) == 2
    assert {addition["path"] for addition in captured_additions} == {".claude-plugin/plugin.json", "apm.yml"}
    assert ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/chore/release-plugin-bump") not in calls


def test_publish_release_pr_open_pr_branch_already_current_skips_commit() -> None:
    plugin_encoded = base64.b64encode(b'{"version": "0.2.0"}').decode("ascii")
    apm_encoded = base64.b64encode(b"version: 0.2.0").decode("ascii")
    responses = {
        "https://api.github.com/repos/o/r/pulls?head=o:chore/release-plugin-bump&state=open&per_page=1": (
            200,
            json.dumps([{"number": 5}]),
        ),
        "https://api.github.com/repos/o/r/git/ref/heads/chore/release-plugin-bump": (
            200,
            json.dumps({"object": {"sha": "branchtip"}}),
        ),
        "https://api.github.com/repos/o/r/contents/.claude-plugin/plugin.json?ref=chore/release-plugin-bump": (
            200,
            json.dumps({"encoding": "base64", "content": plugin_encoded}),
        ),
        "https://api.github.com/repos/o/r/contents/apm.yml?ref=chore/release-plugin-bump": (
            200,
            json.dumps({"encoding": "base64", "content": apm_encoded}),
        ),
        "https://api.github.com/repos/o/r/pulls/5": (200, ""),
    }
    fake, calls = _fake_apply_call(responses)

    def fake_graphql(*, query, variables, token):
        raise AssertionError("no commit should be created when the branch already matches the desired content")

    result = rpp.publish_release_pr(
        repo="o/r",
        additions=[(".claude-plugin/plugin.json", b'{"version": "0.2.0"}'), ("apm.yml", b"version: 0.2.0")],
        base="main",
        branch="chore/release-plugin-bump",
        title="chore(plugin): bump version to 0.2.0",
        body="b",
        commit_subject="chore(plugin): bump version to 0.2.0",
        commit_body="",
        token="tok",
        apply_call=fake,
        graphql_call=fake_graphql,
    )

    assert result == "updated:5"
    assert ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/chore/release-plugin-bump") not in calls


# ---------------------------------------------------------------------------
# _collect_additions
# ---------------------------------------------------------------------------


def test_collect_additions_success(tmp_path) -> None:
    plugin = tmp_path / ".claude-plugin"
    plugin.mkdir()
    (plugin / "plugin.json").write_text('{"version": "0.2.0"}')
    (tmp_path / "apm.yml").write_text("version: 0.2.0\n")

    additions = rpp._collect_additions(tmp_path, [".claude-plugin/plugin.json", "apm.yml"])
    assert additions == [
        (".claude-plugin/plugin.json", b'{"version": "0.2.0"}'),
        ("apm.yml", b"version: 0.2.0\n"),
    ]


def test_collect_additions_missing_file_raises(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="not a readable file"):
        rpp._collect_additions(tmp_path, ["missing.json"])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_missing_gh_token(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("REPO", raising=False)
    rc = rpp.main(
        ["--old-version", "0.1.0", "--new-version", "0.2.0", "--bump-kind", "minor", "--notes-file", "x"]
    )
    assert rc == 1
    assert "GH_TOKEN" in capsys.readouterr().err


def test_main_missing_repo(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.delenv("REPO", raising=False)
    rc = rpp.main(
        ["--old-version", "0.1.0", "--new-version", "0.2.0", "--bump-kind", "minor", "--notes-file", "x"]
    )
    assert rc == 1
    assert "REPO" in capsys.readouterr().err


def test_main_missing_notes_file(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    rc = rpp.main(
        [
            "--old-version",
            "0.1.0",
            "--new-version",
            "0.2.0",
            "--bump-kind",
            "minor",
            "--notes-file",
            str(tmp_path / "missing.md"),
        ]
    )
    assert rc == 1
    assert "notes file not found" in capsys.readouterr().err


def test_main_runtime_error_from_collect_additions(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    notes_file = tmp_path / "notes.md"
    notes_file.write_text("notes")
    rc = rpp.main(
        [
            "--repo-root",
            str(tmp_path),
            "--old-version",
            "0.1.0",
            "--new-version",
            "0.2.0",
            "--bump-kind",
            "minor",
            "--notes-file",
            str(notes_file),
            "--plugin-manifest",
            "missing-plugin.json",
            "--apm-manifest",
            "missing-apm.yml",
        ]
    )
    assert rc == 1
    assert "Error:" in capsys.readouterr().err


def test_main_success_created(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    # publish_release_pr's own `apply_call`/`graphql_call` parameters default
    # to the module-level functions bound at *definition* time, so
    # monkeypatching `rpp.apply_call`/`rpp.graphql_call` after import would
    # not reach this call path. Faking at the `urllib.request.urlopen` layer
    # instead (same technique as test_apply_call_uses_default_opener /
    # test_graphql_call_uses_default_opener above) exercises main()'s real
    # wiring end to end without a real network call.
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")

    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"version": "0.2.0"}')
    (tmp_path / "apm.yml").write_text("version: 0.2.0\n")
    notes_file = tmp_path / "notes.md"
    notes_file.write_text("### Features\n- add widget (abc1234)\n")

    rest_responses: dict[tuple[str, str], tuple[int, str]] = {
        (
            "GET",
            "https://api.github.com/repos/o/r/pulls?head=o:chore/release-plugin-bump&state=open&per_page=1",
        ): (200, "[]"),
        ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/chore/release-plugin-bump"): (404, ""),
        ("GET", "https://api.github.com/repos/o/r/git/ref/heads/chore/release-plugin-bump"): (404, ""),
        ("GET", "https://api.github.com/repos/o/r/git/ref/heads/main"): (
            200,
            json.dumps({"object": {"sha": "basesha"}}),
        ),
        ("POST", "https://api.github.com/repos/o/r/git/refs"): (201, ""),
        ("POST", "https://api.github.com/repos/o/r/pulls"): (201, json.dumps({"number": 11})),
    }
    graphql_responses = [(200, json.dumps({"data": {"createCommitOnBranch": {"commit": {"oid": "newsha"}}}}))]
    graphql_call_count = {"n": 0}

    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None) -> Response:
        method = request.get_method()
        url = request.full_url
        if url == rpp._GRAPHQL_URL:
            code, body = graphql_responses[graphql_call_count["n"]]
            graphql_call_count["n"] += 1
        else:
            code, body = rest_responses[(method, url)]
        if 200 <= code < 300:
            return Response(code, body)
        raise http_error(code, body)

    monkeypatch.setattr(rpp.urllib.request, "urlopen", fake_urlopen)

    rc = rpp.main(
        [
            "--repo-root",
            str(tmp_path),
            "--old-version",
            "0.1.0",
            "--new-version",
            "0.2.0",
            "--bump-kind",
            "minor",
            "--notes-file",
            str(notes_file),
        ]
    )
    assert rc == 0
    assert "created:11" in capsys.readouterr().err
    assert graphql_call_count["n"] == 1

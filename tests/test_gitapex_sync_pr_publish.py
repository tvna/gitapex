from __future__ import annotations

import json
import urllib.error
import urllib.request

import gitapex_sync_pr_publish as spp
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

    code, body = apply_call_result = spp.apply_call(
        method="POST",
        url="https://api.github.com/x",
        payload={"a": 1},
        token="tok",
        opener=opener,
        sleeper=sleeps.append,
    )
    assert apply_call_result == (201, '{"ok":true}')
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

    code, body = spp.apply_call(
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

    code, body = spp.apply_call(method="GET", url="https://api.github.com/x", payload=None, token="tok", opener=opener)
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

    code, body = spp.apply_call(
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

    monkeypatch.setattr(spp.urllib.request, "urlopen", fake_urlopen)
    code, _body = spp.apply_call(method="GET", url="https://api.github.com/x", payload=None, token="tok")
    assert code == 200
    assert captured["timeout"] == spp._HTTP_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# graphql_call
# ---------------------------------------------------------------------------


def test_graphql_call_happy_path() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, '{"data":{"x":1}}')

    code, body = spp.graphql_call(query="q", variables={}, token="tok", opener=opener)
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

    code, _body = spp.graphql_call(query="q", variables={}, token="tok", opener=opener, sleeper=sleeps.append)
    assert code == 200
    assert sleeps == [5]


def test_graphql_call_retries_transient_marker_then_succeeds() -> None:
    transient_body = json.dumps({"errors": [{"message": "Something went wrong while executing your query."}]})
    responses = [Response(200, transient_body), Response(200, '{"data":{}}')]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    code, body = spp.graphql_call(query="q", variables={}, token="tok", opener=opener, sleeper=sleeps.append)
    assert code == 200
    assert body == {"data": {}}
    assert sleeps == [5]


def test_graphql_call_non_transient_error_no_retry() -> None:
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        return Response(200, json.dumps({"errors": [{"message": "Validation failed"}]}))

    code, body = spp.graphql_call(query="q", variables={}, token="tok", opener=opener)
    assert calls == 1
    assert code == 200
    assert "errors" in body


def test_graphql_call_network_failure_degrades_to_empty_body() -> None:
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        raise urllib.error.URLError("boom")

    code, body = spp.graphql_call(query="q", variables={}, token="tok", opener=opener, sleeper=sleeps.append)
    assert code == 0
    assert body == {}
    assert sleeps == [5, 10]


def test_graphql_call_invalid_json_body() -> None:
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, "not json")

    code, body = spp.graphql_call(query="q", variables={}, token="tok", opener=opener)
    assert code == 200
    assert body == {}


def test_graphql_call_uses_default_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None) -> Response:
        return Response(200, '{"data":{}}')

    monkeypatch.setattr(spp.urllib.request, "urlopen", fake_urlopen)
    code, _body = spp.graphql_call(query="q", variables={}, token="tok")
    assert code == 200


# ---------------------------------------------------------------------------
# _format_code
# ---------------------------------------------------------------------------


def test_format_code() -> None:
    assert spp._format_code(0) == "000"
    assert spp._format_code(404) == "404"


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
    sha = spp._get_ref_sha(repo="o/r", ref="heads/main", token="tok", apply_call=fake)
    assert sha == "abc"


def test_get_ref_sha_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/main": (404, "nope")})
    with pytest.raises(RuntimeError, match="Get ref"):
        spp._get_ref_sha(repo="o/r", ref="heads/main", token="tok", apply_call=fake)


def test_get_ref_sha_missing_sha_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/git/ref/heads/main": (200, json.dumps({"object": {}}))}
    )
    with pytest.raises(RuntimeError, match=r"missing object\.sha"):
        spp._get_ref_sha(repo="o/r", ref="heads/main", token="tok", apply_call=fake)


def test_get_ref_sha_non_object_body_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/main": (200, "[]")})
    with pytest.raises(RuntimeError, match="Expected object from get ref"):
        spp._get_ref_sha(repo="o/r", ref="heads/main", token="tok", apply_call=fake)


def test_get_branch_head_oid_absent() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/chore": (404, "")})
    assert spp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake) is None


def test_get_branch_head_oid_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/chore": (500, "boom")})
    with pytest.raises(RuntimeError, match="Get branch ref"):
        spp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_get_branch_head_oid_success() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/git/ref/heads/chore": (200, json.dumps({"object": {"sha": "xyz"}}))}
    )
    assert spp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake) == "xyz"


def test_get_branch_head_oid_missing_sha_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/git/ref/heads/chore": (200, json.dumps({"object": {}}))}
    )
    with pytest.raises(RuntimeError, match=r"missing object\.sha"):
        spp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_get_branch_head_oid_non_object_body_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/ref/heads/chore": (200, "null")})
    with pytest.raises(RuntimeError, match="Expected object from get branch ref"):
        spp._get_branch_head_oid(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_create_branch_ref_success() -> None:
    fake, calls = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs": (201, "")})
    spp._create_branch_ref(repo="o/r", branch="chore", sha="abc", token="tok", apply_call=fake)
    assert calls == [("POST", "https://api.github.com/repos/o/r/git/refs")]


def test_create_branch_ref_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs": (422, "exists")})
    with pytest.raises(RuntimeError, match="Create branch ref"):
        spp._create_branch_ref(repo="o/r", branch="chore", sha="abc", token="tok", apply_call=fake)


def test_delete_branch_success() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs/heads/chore": (204, "")})
    spp._delete_branch(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_delete_branch_already_gone_is_success() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs/heads/chore": (404, "")})
    spp._delete_branch(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_delete_branch_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/git/refs/heads/chore": (500, "boom")})
    with pytest.raises(RuntimeError, match="Delete branch"):
        spp._delete_branch(repo="o/r", branch="chore", token="tok", apply_call=fake)


def test_get_file_bytes_absent() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (404, "")})
    assert spp._get_file_bytes(repo="o/r", path="CLAUDE.md", ref="main", token="tok", apply_call=fake) is None


def test_get_file_bytes_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (500, "boom")})
    with pytest.raises(RuntimeError, match="Get contents"):
        spp._get_file_bytes(repo="o/r", path="CLAUDE.md", ref="main", token="tok", apply_call=fake)


def test_get_file_bytes_success() -> None:
    import base64

    content = base64.b64encode(b"hello").decode("ascii")
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (
                200,
                json.dumps({"encoding": "base64", "content": content}),
            )
        }
    )
    assert spp._get_file_bytes(repo="o/r", path="CLAUDE.md", ref="main", token="tok", apply_call=fake) == b"hello"


def test_get_file_bytes_unexpected_encoding_raises() -> None:
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (
                200,
                json.dumps({"encoding": "none", "content": None}),
            )
        }
    )
    with pytest.raises(RuntimeError, match="unexpected encoding"):
        spp._get_file_bytes(repo="o/r", path="CLAUDE.md", ref="main", token="tok", apply_call=fake)


def test_get_file_bytes_non_object_body_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (200, '"just a string"')}
    )
    with pytest.raises(RuntimeError, match="Expected object from get contents"):
        spp._get_file_bytes(repo="o/r", path="CLAUDE.md", ref="main", token="tok", apply_call=fake)


# ---------------------------------------------------------------------------
# _ref_drifts
# ---------------------------------------------------------------------------


def test_ref_drifts_true_when_content_differs() -> None:
    import base64

    encoded = base64.b64encode(b"old").decode("ascii")
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (
                200,
                json.dumps({"encoding": "base64", "content": encoded}),
            )
        }
    )
    assert spp._ref_drifts(repo="o/r", ref="main", additions=[("CLAUDE.md", b"new")], token="tok", apply_call=fake)


def test_ref_drifts_false_when_content_matches() -> None:
    import base64

    encoded = base64.b64encode(b"same").decode("ascii")
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (
                200,
                json.dumps({"encoding": "base64", "content": encoded}),
            )
        }
    )
    assert not spp._ref_drifts(repo="o/r", ref="main", additions=[("CLAUDE.md", b"same")], token="tok", apply_call=fake)


# ---------------------------------------------------------------------------
# _create_commit_on_branch
# ---------------------------------------------------------------------------


def test_create_commit_on_branch_success() -> None:
    def fake_graphql(*, query, variables, token):
        assert variables["input"]["message"]["body"] == "body text"
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": "newoid"}}}}

    oid = spp._create_commit_on_branch(
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

    spp._create_commit_on_branch(
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
        spp._create_commit_on_branch(
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
        spp._create_commit_on_branch(
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
        spp._create_commit_on_branch(
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
        spp._create_commit_on_branch(
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
    prs = spp._list_open_prs(repo="o/r", head="chore", token="tok", apply_call=fake)
    assert prs == [{"number": 1}]


def test_list_open_prs_failure_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (500, "boom")}
    )
    with pytest.raises(RuntimeError, match="List PRs failed"):
        spp._list_open_prs(repo="o/r", head="chore", token="tok", apply_call=fake)


def test_list_open_prs_unexpected_shape_raises() -> None:
    fake, _ = _fake_apply_call(
        {"https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (200, json.dumps({"x": 1}))}
    )
    with pytest.raises(RuntimeError, match="Expected list"):
        spp._list_open_prs(repo="o/r", head="chore", token="tok", apply_call=fake)


def test_create_pr_success() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/pulls": (201, json.dumps({"number": 7}))})
    number = spp._create_pr(repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake)
    assert number == 7


def test_create_pr_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/pulls": (422, "bad")})
    with pytest.raises(RuntimeError, match="Create PR failed"):
        spp._create_pr(repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake)


def test_update_pr_success() -> None:
    fake, calls = _fake_apply_call({"https://api.github.com/repos/o/r/pulls/7": (200, "")})
    spp._update_pr(repo="o/r", number=7, title="t", body="b", token="tok", apply_call=fake)
    assert calls == [("PATCH", "https://api.github.com/repos/o/r/pulls/7")]


def test_update_pr_failure_raises() -> None:
    fake, _ = _fake_apply_call({"https://api.github.com/repos/o/r/pulls/7": (500, "boom")})
    with pytest.raises(RuntimeError, match="Update PR failed"):
        spp._update_pr(repo="o/r", number=7, title="t", body="b", token="tok", apply_call=fake)


def test_upsert_pr_creates_when_absent() -> None:
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (200, json.dumps([])),
            "https://api.github.com/repos/o/r/pulls": (201, json.dumps({"number": 9})),
        }
    )
    verb, number = spp._upsert_pr(
        repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake
    )
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
    verb, number = spp._upsert_pr(
        repo="o/r", head="chore", base="main", title="t", body="b", token="tok", apply_call=fake
    )
    assert (verb, number) == ("updated", 5)


# ---------------------------------------------------------------------------
# publish_files_pr
# ---------------------------------------------------------------------------


def test_publish_files_pr_empty_additions_is_up_to_date() -> None:
    result = spp.publish_files_pr(
        repo="o/r",
        additions=[],
        base="main",
        branch="chore",
        title="t",
        body="b",
        commit_subject="s",
        commit_body="",
        token="tok",
    )
    assert result == "up-to-date"


def test_publish_files_pr_no_drift_is_up_to_date() -> None:
    import base64

    encoded = base64.b64encode(b"same").decode("ascii")
    fake, _ = _fake_apply_call(
        {
            "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (
                200,
                json.dumps({"encoding": "base64", "content": encoded}),
            )
        }
    )
    result = spp.publish_files_pr(
        repo="o/r",
        additions=[("CLAUDE.md", b"same")],
        base="main",
        branch="chore",
        title="t",
        body="b",
        commit_subject="s",
        commit_body="",
        token="tok",
        apply_call=fake,
    )
    assert result == "up-to-date"


def test_publish_files_pr_drift_no_open_pr_recreates_branch_and_creates_pr() -> None:
    responses = {
        "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (404, ""),
        "https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (200, json.dumps([])),
        "https://api.github.com/repos/o/r/git/refs/heads/chore": (404, ""),
        "https://api.github.com/repos/o/r/git/ref/heads/chore": (404, ""),
        "https://api.github.com/repos/o/r/git/ref/heads/main": (200, json.dumps({"object": {"sha": "basesha"}})),
        "https://api.github.com/repos/o/r/git/refs": (201, ""),
        "https://api.github.com/repos/o/r/pulls": (201, json.dumps({"number": 3})),
    }
    fake, calls = _fake_apply_call(responses)

    def fake_graphql(*, query, variables, token):
        assert variables["input"]["expectedHeadOid"] == "basesha"
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": "newsha"}}}}

    result = spp.publish_files_pr(
        repo="o/r",
        additions=[("CLAUDE.md", b"new")],
        base="main",
        branch="chore",
        title="t",
        body="b",
        commit_subject="s",
        commit_body="",
        token="tok",
        apply_call=fake,
        graphql_call=fake_graphql,
    )
    assert result == "created:3"
    assert ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/chore") in calls


def test_publish_files_pr_drift_with_open_pr_appends_without_deleting() -> None:
    # An open PR already targets the branch: deleting it would risk closing
    # that PR and losing its review history, so the commit must append onto
    # the existing tip instead (Refs the codex review on PR #33).
    responses = {
        "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (404, ""),
        "https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (200, json.dumps([{"number": 4}])),
        "https://api.github.com/repos/o/r/git/ref/heads/chore": (200, json.dumps({"object": {"sha": "branchtip"}})),
        "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=chore": (404, ""),
        "https://api.github.com/repos/o/r/pulls/4": (200, ""),
    }
    fake, calls = _fake_apply_call(responses)

    def fake_graphql(*, query, variables, token):
        assert variables["input"]["expectedHeadOid"] == "branchtip"
        return 200, {"data": {"createCommitOnBranch": {"commit": {"oid": "newsha"}}}}

    result = spp.publish_files_pr(
        repo="o/r",
        additions=[("CLAUDE.md", b"new")],
        base="main",
        branch="chore",
        title="t",
        body="b",
        commit_subject="s",
        commit_body="",
        token="tok",
        apply_call=fake,
        graphql_call=fake_graphql,
    )
    assert result == "updated:4"
    assert ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/chore") not in calls


def test_publish_files_pr_drift_with_open_pr_branch_already_current_skips_commit() -> None:
    import base64

    encoded = base64.b64encode(b"new").decode("ascii")
    responses = {
        "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=main": (404, ""),
        "https://api.github.com/repos/o/r/pulls?head=o:chore&state=open&per_page=1": (200, json.dumps([{"number": 5}])),
        "https://api.github.com/repos/o/r/git/ref/heads/chore": (200, json.dumps({"object": {"sha": "branchtip"}})),
        "https://api.github.com/repos/o/r/contents/CLAUDE.md?ref=chore": (
            200,
            json.dumps({"encoding": "base64", "content": encoded}),
        ),
        "https://api.github.com/repos/o/r/pulls/5": (200, ""),
    }
    fake, calls = _fake_apply_call(responses)

    def fake_graphql(*, query, variables, token):
        raise AssertionError("no commit should be created when the branch already matches the desired content")

    result = spp.publish_files_pr(
        repo="o/r",
        additions=[("CLAUDE.md", b"new")],
        base="main",
        branch="chore",
        title="t",
        body="b",
        commit_subject="s",
        commit_body="",
        token="tok",
        apply_call=fake,
        graphql_call=fake_graphql,
    )
    assert result == "updated:5"
    assert ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/chore") not in calls


# ---------------------------------------------------------------------------
# _collect_additions
# ---------------------------------------------------------------------------


def test_collect_additions_success(tmp_path) -> None:
    f = tmp_path / "CLAUDE.md"
    f.write_text("hello")
    additions = spp._collect_additions([str(f)])
    assert additions == [(str(f), b"hello")]


def test_collect_additions_missing_file_raises(tmp_path) -> None:
    missing = tmp_path / "missing.md"
    with pytest.raises(RuntimeError, match="not a readable file"):
        spp._collect_additions([str(missing)])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_missing_gh_token(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("REPO", raising=False)
    rc = spp.main(["--base", "main", "--branch", "chore", "--title", "t", "--body-file", "x", "--commit-subject", "s"])
    assert rc == 1
    assert "GH_TOKEN" in capsys.readouterr().err


def test_main_missing_repo(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.delenv("REPO", raising=False)
    rc = spp.main(["--base", "main", "--branch", "chore", "--title", "t", "--body-file", "x", "--commit-subject", "s"])
    assert rc == 1
    assert "REPO" in capsys.readouterr().err


def test_main_missing_body_file(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    rc = spp.main(
        [
            "--base",
            "main",
            "--branch",
            "chore",
            "--title",
            "t",
            "--body-file",
            str(tmp_path / "missing.md"),
            "--commit-subject",
            "s",
        ]
    )
    assert rc == 1
    # Exact text, not just a substring: this is the pre-existing hand-check
    # message (see _CliArgs' docstring) and must not drift back to the
    # generic "body_file: body file not found: ..." pydantic-prefixed form
    # a Decision-12 adversarial review caught once already.
    err = capsys.readouterr().err
    assert err == f"Error: body file not found: {tmp_path / 'missing.md'}\n"


def test_main_blank_body_file_keeps_field_label(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    # A second adversarial pass (post-merge) found the body_file special
    # case keyed on loc alone, not also error type -- so a *blank*
    # --body-file (Field(min_length=1)'s generic, non-self-describing
    # message, not the custom field_validator's self-describing one) had
    # its field label silently stripped too, confirmed by direct
    # execution to read as an unattributable duplicate when combined with
    # another blank field's identical message. This must keep the
    # "body_file: " label since, unlike the not-found message, the
    # min_length text alone does not say which field failed.
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    rc = spp.main(["--base", "main", "--branch", "chore", "--title", "t", "--body-file", "", "--commit-subject", "s"])
    assert rc == 1
    assert capsys.readouterr().err == "Error: body_file: String should have at least 1 character\n"


def test_main_blank_title_and_body_file_both_labeled(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    # Two fields sharing pydantic's identical generic blank-value message
    # must not collapse into one unattributable, seemingly-duplicated
    # line -- each keeps its own "field: " label.
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    rc = spp.main(["--base", "main", "--branch", "chore", "--title", "", "--body-file", "", "--commit-subject", "s"])
    assert rc == 1
    assert capsys.readouterr().err == (
        "Error: title: String should have at least 1 character; body_file: String should have at least 1 character\n"
    )


def test_main_body_file_oserror_reports_as_clean_body_file_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    # A THIRD adversarial pass found _body_file_must_exist's own
    # Path(value).exists() call can raise OSError directly (e.g.
    # ENAMETOOLONG for an over-long path component) rather than returning
    # False -- pydantic only converts a validator's own ValueError/
    # TypeError/AssertionError into a ValidationError, so an OSError raised
    # by a stdlib call inside the validator used to propagate straight
    # through main()'s except ValidationError as a raw traceback. Confirmed
    # by direct execution with a 5000-character path component.
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    over_long = "a" * 5000
    rc = spp.main(
        ["--base", "main", "--branch", "chore", "--title", "t", "--body-file", over_long, "--commit-subject", "s"]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith(f"Error: body file not found: {over_long} (")
    assert "Traceback" not in err


def test_main_body_file_directory_reports_as_clean_error_not_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path
) -> None:
    # CodeRabbit review on this PR (issue #1087): Path.exists() accepts a
    # directory, so the pre-existing exists()-based check let a directory
    # path through to main()'s body_path.read_text(), which raises an
    # uncaught IsADirectoryError -- the exact class of raw-traceback
    # failure this issue exists to eliminate. is_file() rejects it in the
    # validator instead, before read_text() is ever reached. Confirmed by
    # direct execution before this test was written.
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_dir = tmp_path / "body-as-a-directory"
    body_dir.mkdir()
    rc = spp.main(
        ["--base", "main", "--branch", "chore", "--title", "t", "--body-file", str(body_dir), "--commit-subject", "s"]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert err == f"Error: body file not found: {body_dir}\n"
    assert "Traceback" not in err
    assert "IsADirectoryError" not in err


def test_main_runtime_error_from_collect_additions(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_text("body")
    rc = spp.main(
        [
            "--base",
            "main",
            "--branch",
            "chore",
            "--title",
            "t",
            "--body-file",
            str(body_file),
            "--commit-subject",
            "s",
            "--add",
            str(tmp_path / "missing.md"),
        ]
    )
    assert rc == 1
    assert "Error:" in capsys.readouterr().err


def test_main_body_file_non_utf8_reports_as_error(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_bytes(b"\xff\xfe not valid utf-8 \x80")
    rc = spp.main(
        ["--base", "main", "--branch", "chore", "--title", "t", "--body-file", str(body_file), "--commit-subject", "s"]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("Error: ")
    assert "Traceback" not in err


def test_main_success_up_to_date(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_text("body")
    rc = spp.main(
        ["--base", "main", "--branch", "chore", "--title", "t", "--body-file", str(body_file), "--commit-subject", "s"]
    )
    assert rc == 0
    assert "up-to-date" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# _CliArgs pydantic validation (new in this batch's CLI-pydantic-wrap)
# ---------------------------------------------------------------------------


def test_main_rejects_blank_title(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_text("body")
    rc = spp.main(
        ["--base", "main", "--branch", "chore", "--title", "", "--body-file", str(body_file), "--commit-subject", "s"]
    )
    assert rc == 1
    assert "Error:" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Issue #1087: min_length=1 alone accepts a whitespace-only string. Each of
# base/branch/title/commit_subject shares this file's generic "field:
# message" rendering (see the ValidationError handler's own comment), so a
# whitespace-only value renders self-describing and field-labeled, same
# shape as their blank-value siblings above. body_file's own validator
# raises a distinct, self-describing message (not the shared "must not be
# blank" text) specifically so its own field-label-stripping special case
# in the ValidationError handler can never collapse it into an
# unattributable duplicate alongside another blank/whitespace-only field --
# the exact defect class the tests above (test_main_blank_title_and_
# body_file_both_labeled) already guard for the blank case.
# ---------------------------------------------------------------------------


def test_main_rejects_whitespace_only_base(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_text("body")
    rc = spp.main(
        ["--base", " ", "--branch", "chore", "--title", "t", "--body-file", str(body_file), "--commit-subject", "s"]
    )
    assert rc == 1
    assert capsys.readouterr().err == "Error: base: must not be blank\n"


def test_main_rejects_whitespace_only_branch(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_text("body")
    rc = spp.main(
        ["--base", "main", "--branch", "\t", "--title", "t", "--body-file", str(body_file), "--commit-subject", "s"]
    )
    assert rc == 1
    assert capsys.readouterr().err == "Error: branch: must not be blank\n"


def test_main_rejects_whitespace_only_title(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_text("body")
    rc = spp.main(
        ["--base", "main", "--branch", "chore", "--title", "  ", "--body-file", str(body_file), "--commit-subject", "s"]
    )
    assert rc == 1
    assert capsys.readouterr().err == "Error: title: must not be blank\n"


def test_main_rejects_whitespace_only_commit_subject(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    body_file = tmp_path / "body.md"
    body_file.write_text("body")
    rc = spp.main(
        ["--base", "main", "--branch", "chore", "--title", "t", "--body-file", str(body_file), "--commit-subject", " "]
    )
    assert rc == 1
    assert capsys.readouterr().err == "Error: commit_subject: must not be blank\n"


def test_main_rejects_whitespace_only_body_file(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    rc = spp.main(["--base", "main", "--branch", "chore", "--title", "t", "--body-file", " ", "--commit-subject", "s"])
    assert rc == 1
    # No "body_file: " prefix (matching this field's existing "not found"
    # message shape), but the message itself names the field: distinct text
    # from the other four fields' shared "must not be blank" so it can
    # never read as an unattributable duplicate when combined with one of
    # them (see test_main_whitespace_only_title_and_body_file_both_labeled
    # below).
    assert capsys.readouterr().err == "Error: body file path must not be blank\n"


def test_main_whitespace_only_title_and_body_file_both_labeled(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Defeats the collapse this file's ValidationError handler was
    specifically hardened against for the blank case (see
    test_main_blank_title_and_body_file_both_labeled): two fields failing
    the same whitespace-only check in the same run must not collapse into
    one unattributable, seemingly-duplicated line."""
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    rc = spp.main(["--base", "main", "--branch", "chore", "--title", " ", "--body-file", " ", "--commit-subject", "s"])
    assert rc == 1
    assert capsys.readouterr().err == "Error: title: must not be blank; body file path must not be blank\n"


def test_main_keeps_padded_but_meaningful_values_unmutated(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    """Issue #1087: validation must not silently trim -- a value with real
    content plus surrounding whitespace reaches publish_files_pr() exactly
    as typed.

    body_file is proven the same way at the filesystem level, not just by
    string equality: the padding is on the *filename itself* (via a chdir
    plus a relative name), so a future validator that stripped-and-stored
    the value would look up a different, non-existent file and fail --
    a prior version of this test padded only the directory component,
    which Path.is_file() does not care about either way, so it would not
    actually have caught that regression (CodeRabbit review on this PR)."""
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    monkeypatch.chdir(tmp_path)
    padded_name = " body.md "
    (tmp_path / padded_name).write_text("body")
    received = {}

    def fake_publish_files_pr(**kwargs: object) -> str:
        received.update(kwargs)
        return "up-to-date"

    monkeypatch.setattr(spp, "publish_files_pr", fake_publish_files_pr)
    rc = spp.main(
        [
            "--base",
            " main ",
            "--branch",
            " chore ",
            "--title",
            " t ",
            "--body-file",
            padded_name,
            "--commit-subject",
            " s ",
        ]
    )
    assert rc == 0
    assert received["base"] == " main "
    assert received["branch"] == " chore "
    assert received["title"] == " t "
    assert received["commit_subject"] == " s "
    assert received["body"] == "body"

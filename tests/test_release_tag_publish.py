from __future__ import annotations

import json
import urllib.error

import pytest
import release_tag_publish as rtp


class Response:
    """Test double for the urlopen response `apply_call` expects: a
    context-managed, status+read()-bearing object. Shared across every
    `apply_call` test below (previously each test defined its own
    near-identical inline class) and doubles as the `fp` argument to a
    constructed `HTTPError` via `http_error()`, matching
    test_release_pr_publish.py's equivalent test double for the sibling
    script."""

    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self._body = body.encode()

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test", code, "err", {}, Response(code, body))  # type: ignore[arg-type]


class _FakeApplyCall:
    """Records every call and returns a canned ``(code, body)`` response
    keyed by ``"METHOD url"`` (or bare ``url`` as a fallback), mirroring
    test_sync_pr_publish.py's ``_fake_apply_call`` test-double pattern.

    Raises ``AssertionError`` on any call with no matching response, so an
    end-to-end test can prove a code path never reaches an unexpected API
    call (e.g. the no-op path never reaching a publish call) just by using
    a responses dict that only covers the calls it expects.
    """

    def __init__(self, responses: dict[str, tuple[int, str]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, *, method: str, url: str, payload: dict | None, token: str) -> tuple[int, str]:
        self.calls.append((method, url, payload))
        key = f"{method} {url}"
        if key in self._responses:
            return self._responses[key]
        if url in self._responses:
            return self._responses[url]
        raise AssertionError(f"unexpected call: {method} {url}")


def _write_manifest(tmp_path, version: str, rel_path: str = ".claude-plugin/plugin.json"):
    manifest = tmp_path / rel_path
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"version": version}), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# apply_call
# ---------------------------------------------------------------------------


def test_apply_call_happy_path() -> None:
    sleeps: list[float] = []

    def opener(request):
        assert request.headers["Authorization"] == "Bearer tok"
        return Response(201, '{"ok":true}')

    code, body = rtp.apply_call(
        method="POST", url="https://api.github.com/x", payload={"a": 1}, token="tok", opener=opener, sleeper=sleeps.append
    )
    assert code == 201
    assert body == '{"ok":true}'
    assert sleeps == []


def test_apply_call_breaks_on_4xx() -> None:
    calls = 0

    def opener(request):
        nonlocal calls
        calls += 1
        raise http_error(422, "bad")

    code, body = rtp.apply_call(method="GET", url="https://api.github.com/x", payload=None, token="tok", opener=opener)
    assert code == 422
    assert body == "bad"
    assert calls == 1


def test_apply_call_retries_5xx_then_succeeds() -> None:
    responses: list[urllib.error.HTTPError | Response] = [http_error(503, "one"), Response(200, "ok")]
    sleeps: list[float] = []

    def opener(request):
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    code, body = rtp.apply_call(
        method="GET", url="https://api.github.com/x", payload=None, token="tok", opener=opener, sleeper=sleeps.append
    )
    assert code == 200
    assert body == "ok"
    assert sleeps == [5]


def test_apply_call_network_failure_retries_three_times() -> None:
    calls = 0
    sleeps: list[float] = []

    def opener(request):
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    code, body = rtp.apply_call(
        method="GET", url="https://api.github.com/x", payload=None, token="tok", opener=opener, sleeper=sleeps.append
    )
    assert code == 0
    assert body == "boom"
    assert calls == 3
    assert sleeps == [5, 10]


def test_apply_call_uses_default_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["timeout"] = timeout
        return Response(200, "ok")

    monkeypatch.setattr(rtp.urllib.request, "urlopen", fake_urlopen)
    code, _body = rtp.apply_call(method="GET", url="https://api.github.com/x", payload=None, token="tok")
    assert code == 200
    assert captured["timeout"] == rtp._HTTP_TIMEOUT_SECONDS


def test_format_code() -> None:
    assert rtp._format_code(0) == "000"
    assert rtp._format_code(404) == "404"


# ---------------------------------------------------------------------------
# tag_exists
# ---------------------------------------------------------------------------


def test_tag_exists_true_on_200() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (200, "{}")})
    assert rtp.tag_exists("o/r", "1.2.3", "tok", apply_call=fake) is True


def test_tag_exists_false_on_404() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (404, "not found")})
    assert rtp.tag_exists("o/r", "1.2.3", "tok", apply_call=fake) is False


def test_tag_exists_raises_on_500() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (500, "boom")})
    with pytest.raises(RuntimeError, match="500"):
        rtp.tag_exists("o/r", "1.2.3", "tok", apply_call=fake)


# ---------------------------------------------------------------------------
# release_exists
# ---------------------------------------------------------------------------


def test_release_exists_true_on_200() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (200, "{}")})
    assert rtp.release_exists("o/r", "1.2.3", "tok", apply_call=fake) is True


def test_release_exists_false_on_404() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (404, "not found")})
    assert rtp.release_exists("o/r", "1.2.3", "tok", apply_call=fake) is False


def test_release_exists_raises_on_500() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (500, "boom")})
    with pytest.raises(RuntimeError, match="500"):
        rtp.release_exists("o/r", "1.2.3", "tok", apply_call=fake)


# ---------------------------------------------------------------------------
# extract_release_notes
# ---------------------------------------------------------------------------


def test_extract_release_notes_success() -> None:
    body = "intro text\n<!-- release-notes:start -->\nline one\nline two\n<!-- release-notes:end -->\noutro text"
    assert rtp.extract_release_notes(body) == "line one\nline two"


def test_extract_release_notes_missing_start_marker_raises() -> None:
    body = "no start marker here\n<!-- release-notes:end -->\n"
    with pytest.raises(RuntimeError, match="release-notes:start"):
        rtp.extract_release_notes(body)


def test_extract_release_notes_missing_end_marker_raises() -> None:
    body = "<!-- release-notes:start -->\nno end marker here\n"
    with pytest.raises(RuntimeError, match="release-notes:end"):
        rtp.extract_release_notes(body)


def test_extract_release_notes_missing_both_markers_raises() -> None:
    with pytest.raises(RuntimeError, match="release-notes:start"):
        rtp.extract_release_notes("plain body, no markers at all")


def test_extract_release_notes_empty_body_raises() -> None:
    with pytest.raises(RuntimeError, match="release-notes:start"):
        rtp.extract_release_notes("")


def test_extract_release_notes_markers_out_of_order_raises() -> None:
    # Both marker strings are present (so the presence checks pass), but the
    # end marker appears before the start marker -- the regex search must
    # still fail closed rather than matching across the wrong span.
    body = "<!-- release-notes:end -->middle<!-- release-notes:start -->"
    with pytest.raises(RuntimeError, match="out of order"):
        rtp.extract_release_notes(body)


# ---------------------------------------------------------------------------
# find_merged_pr_for_commit
# ---------------------------------------------------------------------------


def test_find_merged_pr_for_commit_found() -> None:
    prs = [{"number": 1, "merged_at": None}, {"number": 2, "merged_at": "2026-08-01T00:00:00Z", "body": "x"}]
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, json.dumps(prs))})
    pr = rtp.find_merged_pr_for_commit("o/r", "deadbeef", "tok", apply_call=fake)
    assert pr == prs[1]


def test_find_merged_pr_for_commit_not_found_empty_list() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, "[]")})
    assert rtp.find_merged_pr_for_commit("o/r", "deadbeef", "tok", apply_call=fake) is None


def test_find_merged_pr_for_commit_only_open_prs_returns_none() -> None:
    prs = [{"number": 1, "merged_at": None}, {"number": 2, "merged_at": None}]
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, json.dumps(prs))})
    assert rtp.find_merged_pr_for_commit("o/r", "deadbeef", "tok", apply_call=fake) is None


def test_find_merged_pr_for_commit_failure_raises() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (500, "boom")})
    with pytest.raises(RuntimeError, match="500"):
        rtp.find_merged_pr_for_commit("o/r", "deadbeef", "tok", apply_call=fake)


def test_find_merged_pr_for_commit_unexpected_shape_raises() -> None:
    fake = _FakeApplyCall({"GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, json.dumps({"x": 1}))})
    with pytest.raises(RuntimeError, match="Expected list"):
        rtp.find_merged_pr_for_commit("o/r", "deadbeef", "tok", apply_call=fake)


# ---------------------------------------------------------------------------
# publish_tag_and_release
# ---------------------------------------------------------------------------


def test_publish_tag_and_release_success_posts_expected_bodies() -> None:
    fake = _FakeApplyCall(
        {
            "POST https://api.github.com/repos/o/r/git/tags": (201, json.dumps({"sha": "tagsha123"})),
            "POST https://api.github.com/repos/o/r/git/refs": (201, "{}"),
            "POST https://api.github.com/repos/o/r/releases": (201, "{}"),
        }
    )
    rtp.publish_tag_and_release("o/r", "1.2.3", "deadbeef", "notes text", "tok", apply_call=fake)

    tag_call = next(c for c in fake.calls if c[1].endswith("/git/tags"))
    assert tag_call[2] == {"tag": "gitapex--v1.2.3", "message": "gitapex v1.2.3", "object": "deadbeef", "type": "commit"}

    ref_call = next(c for c in fake.calls if c[1].endswith("/git/refs"))
    assert ref_call[2] == {"ref": "refs/tags/gitapex--v1.2.3", "sha": "tagsha123"}

    release_call = next(c for c in fake.calls if c[1].endswith("/releases"))
    assert release_call[2] == {"tag_name": "gitapex--v1.2.3", "name": "gitapex v1.2.3", "body": "notes text"}


def test_publish_tag_and_release_tag_creation_failure_raises_and_stops() -> None:
    fake = _FakeApplyCall({"POST https://api.github.com/repos/o/r/git/tags": (422, "bad")})
    with pytest.raises(RuntimeError, match="422"):
        rtp.publish_tag_and_release("o/r", "1.2.3", "deadbeef", "notes", "tok", apply_call=fake)
    assert len(fake.calls) == 1


def test_publish_tag_and_release_missing_tag_sha_raises() -> None:
    fake = _FakeApplyCall({"POST https://api.github.com/repos/o/r/git/tags": (201, json.dumps({}))})
    with pytest.raises(RuntimeError, match="missing sha"):
        rtp.publish_tag_and_release("o/r", "1.2.3", "deadbeef", "notes", "tok", apply_call=fake)


def test_publish_tag_and_release_ref_creation_failure_stops_before_release() -> None:
    fake = _FakeApplyCall(
        {
            "POST https://api.github.com/repos/o/r/git/tags": (201, json.dumps({"sha": "tagsha123"})),
            "POST https://api.github.com/repos/o/r/git/refs": (422, "exists"),
        }
    )
    with pytest.raises(RuntimeError, match="422"):
        rtp.publish_tag_and_release("o/r", "1.2.3", "deadbeef", "notes", "tok", apply_call=fake)
    assert len(fake.calls) == 2


def test_publish_tag_and_release_release_creation_failure_raises() -> None:
    fake = _FakeApplyCall(
        {
            "POST https://api.github.com/repos/o/r/git/tags": (201, json.dumps({"sha": "tagsha123"})),
            "POST https://api.github.com/repos/o/r/git/refs": (201, "{}"),
            "POST https://api.github.com/repos/o/r/releases": (500, "boom"),
        }
    )
    with pytest.raises(RuntimeError, match="500"):
        rtp.publish_tag_and_release("o/r", "1.2.3", "deadbeef", "notes", "tok", apply_call=fake)


# ---------------------------------------------------------------------------
# _read_version
# ---------------------------------------------------------------------------


def test_read_version_success(tmp_path) -> None:
    manifest = _write_manifest(tmp_path, "2.0.0")
    assert rtp._read_version(manifest) == "2.0.0"


def test_read_version_missing_file_raises(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="Could not read"):
        rtp._read_version(tmp_path / "missing.json")


def test_read_version_invalid_json_raises(tmp_path) -> None:
    manifest = tmp_path / "plugin.json"
    manifest.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        rtp._read_version(manifest)


def test_read_version_missing_field_raises(tmp_path) -> None:
    manifest = tmp_path / "plugin.json"
    manifest.write_text(json.dumps({"name": "x"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="version"):
        rtp._read_version(manifest)


def test_read_version_non_string_field_raises(tmp_path) -> None:
    manifest = tmp_path / "plugin.json"
    manifest.write_text(json.dumps({"version": 123}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="version"):
        rtp._read_version(manifest)


# ---------------------------------------------------------------------------
# main -- argument/env validation
# ---------------------------------------------------------------------------


def test_main_missing_gh_token(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    rc = rtp.main(["--sha", "deadbeef", "--repo", "o/r"])
    assert rc == 1
    assert "GH_TOKEN" in capsys.readouterr().err


def test_main_missing_repo(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.delenv("REPO", raising=False)
    rc = rtp.main(["--sha", "deadbeef"])
    assert rc == 1
    assert "REPO" in capsys.readouterr().err


def test_main_repo_env_var_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _write_manifest(tmp_path, "1.2.3")
    monkeypatch.setenv("GH_TOKEN", "tok")
    monkeypatch.setenv("REPO", "o/r")
    fake = _FakeApplyCall(
        {
            "GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (200, "{}"),
            "GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (200, "{}"),
        }
    )
    rc = rtp.main(["--repo-root", str(tmp_path), "--sha", "deadbeef"], apply_call=fake)
    assert rc == 0


def test_main_manifest_error_surfaces_as_error(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("GH_TOKEN", "tok")
    rc = rtp.main(["--repo-root", str(tmp_path), "--sha", "deadbeef", "--repo", "o/r"])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main -- end-to-end paths
# ---------------------------------------------------------------------------


def test_main_no_op_when_tag_and_release_already_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys
) -> None:
    _write_manifest(tmp_path, "1.2.3")
    monkeypatch.setenv("GH_TOKEN", "tok")
    # Only the two existence GETs are legal calls here -- _FakeApplyCall
    # raises AssertionError on anything else, so this proves the no-op path
    # never reaches find_merged_pr_for_commit or publish_tag_and_release.
    fake = _FakeApplyCall(
        {
            "GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (200, "{}"),
            "GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (200, "{}"),
        }
    )

    rc = rtp.main(["--repo-root", str(tmp_path), "--sha", "deadbeef", "--repo", "o/r"], apply_call=fake)

    assert rc == 0
    assert "already published" in capsys.readouterr().out
    assert fake.calls == [
        ("GET", "https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3", None),
        ("GET", "https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3", None),
    ]


def test_main_completes_missing_release_when_tag_already_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys
) -> None:
    # Regression: a run that created the tag ref and then failed on the
    # Release POST used to be unrecoverable. The tag alone was treated as
    # "already published", so every retry exited 0 (green) while the
    # GitHub Release stayed permanently missing. A retry must instead
    # finish the job -- create the Release, and NOT re-create the tag.
    _write_manifest(tmp_path, "1.2.3")
    monkeypatch.setenv("GH_TOKEN", "tok")
    pr_body = "<!-- release-notes:start -->\nNotable change.\n<!-- release-notes:end -->"
    prs = [{"number": 9, "merged_at": "2026-08-01T00:00:00Z", "body": pr_body}]
    fake = _FakeApplyCall(
        {
            "GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (200, "{}"),
            "GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (404, ""),
            "GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, json.dumps(prs)),
            "POST https://api.github.com/repos/o/r/releases": (201, "{}"),
        }
    )

    rc = rtp.main(["--repo-root", str(tmp_path), "--sha", "deadbeef", "--repo", "o/r"], apply_call=fake)

    assert rc == 0
    posts = [c for c in fake.calls if c[0] == "POST"]
    # Exactly one POST, and it is the Release -- the already-existing tag
    # object/ref must not be created a second time.
    assert len(posts) == 1
    assert posts[0][1] == "https://api.github.com/repos/o/r/releases"
    assert posts[0][2]["body"] == "Notable change."
    assert "published gitapex--v1.2.3" in capsys.readouterr().err


def test_main_publishes_tag_and_release_when_absent(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    _write_manifest(tmp_path, "1.2.3")
    monkeypatch.setenv("GH_TOKEN", "tok")
    pr_body = (
        "## Summary\nSome PR description text.\n\n"
        "<!-- release-notes:start -->\n"
        "Notable change one.\nNotable change two.\n"
        "<!-- release-notes:end -->\n\nRefs #642"
    )
    prs = [{"number": 9, "merged_at": "2026-08-01T00:00:00Z", "body": pr_body}]
    fake = _FakeApplyCall(
        {
            "GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (404, ""),
            "GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (404, ""),
            "GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, json.dumps(prs)),
            "POST https://api.github.com/repos/o/r/git/tags": (201, json.dumps({"sha": "tagsha123"})),
            "POST https://api.github.com/repos/o/r/git/refs": (201, "{}"),
            "POST https://api.github.com/repos/o/r/releases": (201, "{}"),
        }
    )

    rc = rtp.main(["--repo-root", str(tmp_path), "--sha", "deadbeef", "--repo", "o/r"], apply_call=fake)

    assert rc == 0
    tag_call = next(c for c in fake.calls if c[1].endswith("/git/tags"))
    # Regression guard: the tag must use the "gitapex--v{version}" prefix,
    # never the earlier "plugin-v{version}" convention.
    assert tag_call[2]["tag"] == "gitapex--v1.2.3"
    release_call = next(c for c in fake.calls if c[1].endswith("/releases"))
    assert release_call[2]["body"] == "Notable change one.\nNotable change two."
    assert "published gitapex--v1.2.3" in capsys.readouterr().err


def test_main_raises_when_no_merged_pr_found(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    _write_manifest(tmp_path, "1.2.3")
    monkeypatch.setenv("GH_TOKEN", "tok")
    fake = _FakeApplyCall(
        {
            "GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (404, ""),
            "GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (404, ""),
            "GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, "[]"),
        }
    )

    rc = rtp.main(["--repo-root", str(tmp_path), "--sha", "deadbeef", "--repo", "o/r"], apply_call=fake)

    assert rc == 1
    assert "No merged PR found" in capsys.readouterr().err


def test_main_missing_release_notes_markers_raises(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    _write_manifest(tmp_path, "1.2.3")
    monkeypatch.setenv("GH_TOKEN", "tok")
    prs = [{"number": 9, "merged_at": "2026-08-01T00:00:00Z", "body": "no markers here"}]
    fake = _FakeApplyCall(
        {
            "GET https://api.github.com/repos/o/r/git/ref/tags/gitapex--v1.2.3": (404, ""),
            "GET https://api.github.com/repos/o/r/releases/tags/gitapex--v1.2.3": (404, ""),
            "GET https://api.github.com/repos/o/r/commits/deadbeef/pulls": (200, json.dumps(prs)),
        }
    )

    rc = rtp.main(["--repo-root", str(tmp_path), "--sha", "deadbeef", "--repo", "o/r"], apply_call=fake)

    assert rc == 1
    assert "release-notes:start" in capsys.readouterr().err

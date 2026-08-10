"""Tests for the ACM issue disclosure gate
(.github/scripts/gitapex_gate_acm_issue_disclosure.py).

Issue #414 (sub-issue of #357): flags a GitHub issue whose body carries
neither an Acceptance Criteria Map table nor an explicit
`ACM: not-applicable (chore|docs|tracking|defect): <reason>` waiver line
(the `defect` category added by issue #657), via a label (`needs-acm`)
and a one-time comment, regardless of which session or environment
created the issue.

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring
test_gitapex_post_merge_retro.py's own fixture style.
"""

from __future__ import annotations

import http.client
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

import gitapex_gate_acm_issue_disclosure as gate
import pytest
import yaml

_VALID_ACM_TABLE = """\
## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Thing works | It should do X | Add Y | Run Z | None |
"""


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
# has_acm_disclosure
# ---------------------------------------------------------------------------


def test_missing_table_and_waiver_fails():
    assert gate.has_acm_disclosure("# My issue\n\nJust a description.\n") is False


def test_none_body_is_treated_as_empty():
    assert gate.has_acm_disclosure(None) is False


def test_acm_table_passes():
    assert gate.has_acm_disclosure(_VALID_ACM_TABLE) is True


@pytest.mark.parametrize(
    "category",
    ["chore", "docs", "tracking", "defect", "Chore", "DOCS", "Tracking", "Defect"],
)
def test_waiver_line_passes_for_each_named_category_case_insensitively(category):
    body = f"Some issue text.\n\nACM: not-applicable ({category}): docs-only rewording.\n"
    assert gate.has_acm_disclosure(body) is True


def test_waiver_with_no_reason_does_not_satisfy():
    body = "ACM: not-applicable (chore):\n"
    assert gate.has_acm_disclosure(body) is False


def test_waiver_with_unrecognized_category_does_not_satisfy():
    body = "ACM: not-applicable (bug): this is a bug report.\n"
    assert gate.has_acm_disclosure(body) is False


def test_waiver_accepts_leading_bullet_and_backticks():
    body = "- `ACM`: not-applicable (docs): typo fix in README.\n"
    assert gate.has_acm_disclosure(body) is True


@pytest.mark.parametrize("category", ["chore", "docs", "tracking", "defect"])
def test_acm_waiver_re_captures_the_matched_category(category):
    body = f"ACM: not-applicable ({category}): some reason.\n"
    match = gate._ACM_WAIVER_RE.search(body)
    assert match is not None
    assert match.group("category").lower() == category


def test_crlf_line_endings_do_not_break_the_waiver_match():
    body = "ACM: not-applicable (chore): housekeeping.\r\n".replace("\n", "\r\n")
    assert gate.has_acm_disclosure(body) is True


def test_bare_cr_line_endings_do_not_break_the_waiver_match():
    body = "ACM: not-applicable (chore): housekeeping.\r"
    assert gate.has_acm_disclosure(body) is True


# ---------------------------------------------------------------------------
# ensure_label_exists
# ---------------------------------------------------------------------------


def test_ensure_label_exists_creates_the_label():
    captured = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, "{}")

    gate.ensure_label_exists("tvna", "gitapex", "tok", opener=opener)
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/labels"
    assert captured["payload"]["name"] == "needs-acm"


def test_ensure_label_exists_treats_already_exists_as_success():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(422, '{"message": "already_exists"}')

    gate.ensure_label_exists("tvna", "gitapex", "tok", opener=opener, sleeper=lambda _: None)


def test_ensure_label_exists_reraises_other_errors():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "server error")

    with pytest.raises(gate.GitHubApiError):
        gate.ensure_label_exists("tvna", "gitapex", "tok", opener=opener, sleeper=lambda _: None)


# ---------------------------------------------------------------------------
# add_label / remove_label
# ---------------------------------------------------------------------------


def test_add_label_posts_expected_payload():
    captured = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = json.loads(request.data.decode())
        return Response(200, "[]")

    gate.add_label("tvna", "gitapex", 414, "tok", opener=opener)
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/issues/414/labels"
    assert captured["payload"]["labels"] == ["needs-acm"]


def test_remove_label_deletes_expected_url():
    captured = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return Response(200, "[]")

    gate.remove_label("tvna", "gitapex", 414, "tok", opener=opener)
    assert captured["method"] == "DELETE"
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/issues/414/labels/needs-acm"


def test_remove_label_treats_404_as_success():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(404, "not found")

    gate.remove_label("tvna", "gitapex", 414, "tok", opener=opener, sleeper=lambda _: None)


def test_remove_label_reraises_other_errors():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "server error")

    with pytest.raises(gate.GitHubApiError):
        gate.remove_label("tvna", "gitapex", 414, "tok", opener=opener, sleeper=lambda _: None)


# ---------------------------------------------------------------------------
# _call retry behavior (exercised via add_label, mirroring
# test_gitapex_post_merge_retro.py's own retry-path coverage)
# ---------------------------------------------------------------------------


def test_call_retries_5xx_then_succeeds():
    responses = [http_error(503, "{}"), Response(200, "[]")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    gate.add_label("tvna", "gitapex", 414, "tok", opener=opener, sleeper=sleeps.append)
    assert sleeps == [5]


def test_call_retries_incomplete_body_read_then_succeeds():
    class FlakyResponse(Response):
        def read(self) -> bytes:
            raise http.client.IncompleteRead(b"partial")

    responses = [FlakyResponse(200), Response(200, "[]")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    gate.add_label("tvna", "gitapex", 414, "tok", opener=opener, sleeper=sleeps.append)
    assert sleeps == [5]


def test_call_raises_after_repeated_network_failure():
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    with pytest.raises(gate.GitHubApiError):
        gate.add_label("tvna", "gitapex", 414, "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 3


# ---------------------------------------------------------------------------
# has_marker_comment / post_comment
# ---------------------------------------------------------------------------


def test_has_marker_comment_true_when_present():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps([{"body": f"hello {gate._MARKER}"}]))

    assert gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener) is True


def test_has_marker_comment_false_when_absent():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps([{"body": "unrelated comment"}]))

    assert gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener) is False


def test_has_marker_comment_paginates_past_a_full_first_page():
    """Regression for a Codex review finding on PR #425: a full first page
    (== _COMMENTS_PAGE_SIZE items, none matching) must not be treated as
    "no marker" -- it must fetch page 2, where the marker actually is."""
    full_page = [{"body": f"filler {i}"} for i in range(gate._COMMENTS_PAGE_SIZE)]
    second_page = [{"body": f"hello {gate._MARKER}"}]
    pages = {1: full_page, 2: second_page}
    requested_pages = []

    def opener(request: urllib.request.Request) -> Response:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        page = int(query["page"][0])
        requested_pages.append(page)
        return Response(200, json.dumps(pages[page]))

    assert gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener) is True
    assert requested_pages == [1, 2]


def test_has_marker_comment_returns_false_after_exhausting_all_pages():
    full_page = [{"body": f"filler {i}"} for i in range(gate._COMMENTS_PAGE_SIZE)]
    partial_last_page = [{"body": "filler last"}]
    pages = {1: full_page, 2: partial_last_page}

    def opener(request: urllib.request.Request) -> Response:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        page = int(query["page"][0])
        return Response(200, json.dumps(pages[page]))

    assert gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener) is False


def test_has_marker_comment_raises_cleanly_on_non_list_response():
    # Issue #995: `comments` used to be iterated on trust -- a non-list
    # comments-list response (e.g. a malformed/unexpected GitHub API body)
    # raised an uncaught error deep inside the `any(...)` generator instead
    # of this gate's own documented GitHubApiError.
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"not": "a list"}))

    with pytest.raises(gate.GitHubApiError, match="expected a JSON array"):
        gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener)


def test_has_marker_comment_raises_cleanly_on_non_dict_list_item():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(["not a dict"]))

    with pytest.raises(gate.GitHubApiError, match="expected an object"):
        gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener)


def test_has_marker_comment_tolerates_a_null_body_field():
    # A /code-review finding on this same PR: a comment dict with a
    # present-but-null "body" (valid GitHub API JSON) passes the dict-item
    # shape check above but used to crash `in` on None instead of just
    # being treated as no-marker-here.
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps([{"id": 1, "body": None}]))

    assert gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener) is False


def test_has_marker_comment_raises_cleanly_on_a_non_string_body():
    # A CodeRabbit review finding on this same PR: the dict-item shape check
    # says nothing about "body"'s own type -- a truthy non-string body
    # (e.g. an int) used to crash `in` with an uncaught TypeError; a dict
    # body would silently check key membership instead of raising, a wrong
    # marker decision rather than a loud one.
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps([{"id": 1, "body": 12345}]))

    with pytest.raises(gate.GitHubApiError, match="non-string 'body'"):
        gate.has_marker_comment("tvna", "gitapex", 414, "tok", opener=opener)


def test_post_comment_includes_marker_and_waiver_guidance():
    captured = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, "{}")

    gate.post_comment("tvna", "gitapex", 414, "tok", opener=opener)
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/issues/414/comments"
    assert gate._MARKER in captured["payload"]["body"]
    assert "ACM: not-applicable" in captured["payload"]["body"]


def test_post_comment_waiver_guidance_lists_all_four_categories():
    # Regression: the substring check above ("ACM: not-applicable" alone)
    # would stay green even if a future wording edit dropped a category
    # from the displayed example while the regex itself kept accepting it
    # -- assert the full category list is actually shown to the requester.
    captured = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, "{}")

    gate.post_comment("tvna", "gitapex", 414, "tok", opener=opener)
    assert "(chore|docs|tracking|defect)" in captured["payload"]["body"]


# ---------------------------------------------------------------------------
# main -- --check-only mode
# ---------------------------------------------------------------------------


def test_main_check_only_reads_body_from_stdin(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(_VALID_ACM_TABLE))
    assert gate.main(["--check-only"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_check_only_reads_body_from_file(tmp_path, capsys):
    path = tmp_path / "body.md"
    path.write_text(_VALID_ACM_TABLE, encoding="utf-8")
    assert gate.main(["--check-only", "--body", str(path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_check_only_fails_on_missing_disclosure(capsys):
    assert gate.main(["--check-only", "--body", "/dev/null"]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_check_only_reports_error_for_missing_file(capsys):
    assert gate.main(["--check-only", "--body", "/no/such/file.md"]) == 1
    assert "not found" in capsys.readouterr().err


def test_main_check_only_reports_error_for_non_utf8_body_file(tmp_path, capsys):
    # Issue #680 Shape 2: main() caught FileNotFoundError around this same
    # read_text(encoding="utf-8") but not UnicodeDecodeError, so a non-UTF-8
    # body file raised an uncaught traceback instead of the documented
    # exit-1 error path.
    path = tmp_path / "body.bin"
    path.write_bytes(b"\xff\xfe\x00\x01")
    assert gate.main(["--check-only", "--body", str(path)]) == 1
    assert "not valid UTF-8" in capsys.readouterr().err


def test_main_check_only_never_touches_github_token(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert gate.main(["--check-only", "--body", "/dev/null"]) == 1


# ---------------------------------------------------------------------------
# main -- full mode
# ---------------------------------------------------------------------------


def test_main_full_mode_requires_owner_repo_issue_number(tmp_path, capsys):
    path = tmp_path / "body.md"
    path.write_text(_VALID_ACM_TABLE, encoding="utf-8")
    assert gate.main(["--body", str(path)]) == 1
    assert "required" in capsys.readouterr().err


def test_main_full_mode_requires_github_token(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    path = tmp_path / "body.md"
    path.write_text(_VALID_ACM_TABLE, encoding="utf-8")
    exit_code = gate.main(["--body", str(path), "--owner", "tvna", "--repo", "gitapex", "--issue-number", "414"])
    assert exit_code == 1


def test_main_full_mode_pass_removes_label(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    calls = []
    monkeypatch.setattr(gate, "remove_label", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(
        gate, "add_label", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not label on pass"))
    )

    path = tmp_path / "body.md"
    path.write_text(_VALID_ACM_TABLE, encoding="utf-8")
    exit_code = gate.main(["--body", str(path), "--owner", "tvna", "--repo", "gitapex", "--issue-number", "414"])
    assert exit_code == 0
    assert len(calls) == 1
    assert "PASS" in capsys.readouterr().out


def test_main_full_mode_fail_labels_and_comments_when_no_marker_yet(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    ensure_calls = []
    add_calls = []
    comment_calls = []
    monkeypatch.setattr(gate, "ensure_label_exists", lambda *a, **k: ensure_calls.append(a))
    monkeypatch.setattr(gate, "add_label", lambda *a, **k: add_calls.append(a))
    monkeypatch.setattr(gate, "has_marker_comment", lambda *a, **k: False)
    monkeypatch.setattr(gate, "post_comment", lambda *a, **k: comment_calls.append(a))

    path = tmp_path / "body.md"
    path.write_text("no acm here", encoding="utf-8")
    exit_code = gate.main(["--body", str(path), "--owner", "tvna", "--repo", "gitapex", "--issue-number", "414"])
    assert exit_code == 1
    assert len(ensure_calls) == 1
    assert len(add_calls) == 1
    assert len(comment_calls) == 1
    assert "Flagged issue #414" in capsys.readouterr().out


def test_main_full_mode_fail_does_not_repost_when_marker_already_present(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    comment_calls = []
    monkeypatch.setattr(gate, "ensure_label_exists", lambda *a, **k: None)
    monkeypatch.setattr(gate, "add_label", lambda *a, **k: None)
    monkeypatch.setattr(gate, "has_marker_comment", lambda *a, **k: True)
    monkeypatch.setattr(gate, "post_comment", lambda *a, **k: comment_calls.append(a))

    path = tmp_path / "body.md"
    path.write_text("no acm here", encoding="utf-8")
    exit_code = gate.main(["--body", str(path), "--owner", "tvna", "--repo", "gitapex", "--issue-number", "414"])
    assert exit_code == 1
    assert len(comment_calls) == 0
    assert "already present" in capsys.readouterr().out


def test_main_full_mode_exits_one_on_github_api_error(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*a, **k):
        raise gate.GitHubApiError("boom")

    monkeypatch.setattr(gate, "ensure_label_exists", raise_api_error)
    path = tmp_path / "body.md"
    path.write_text("no acm here", encoding="utf-8")
    exit_code = gate.main(["--body", str(path), "--owner", "tvna", "--repo", "gitapex", "--issue-number", "414"])
    assert exit_code == 1


# ---------------------------------------------------------------------------
# Workflow shape (issue #414's own security constraints: harden-runner,
# SHA-pinned actions, minimum-scoped permissions -- mirroring
# test_gitapex_post_merge_retro.py's own drift-gate section against a real
# workflow file rather than trusting a comment).
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "acm-issue-gate.yml"


def _load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_file_exists_and_parses():
    assert WORKFLOW_PATH.is_file(), f"expected {WORKFLOW_PATH} to exist"
    workflow = _load_workflow()
    assert workflow.get("jobs"), f"{WORKFLOW_PATH} has no jobs -- parse likely broke"


def test_workflow_triggers_on_issues_opened_and_edited():
    workflow = _load_workflow()
    # PyYAML's default (YAML 1.1) resolver treats the bare `on` scalar key
    # as the boolean True, not the string "on" -- this parses the same way
    # actionlint's own workflow-schema check treats it, so this asserts
    # against the value PyYAML actually produces rather than the literal
    # source spelling.
    on_block = workflow.get("on", workflow.get(True))
    assert on_block is not None, f"could not find the `on:` trigger block in {WORKFLOW_PATH}"
    assert "issues" in on_block
    assert sorted(on_block["issues"]["types"]) == ["edited", "opened"]


def test_workflow_uses_harden_runner_and_pinned_checkout():
    # Issue #813: the Harden runner + checkout step pair moved into the
    # shared .github/actions/harden-checkout composite action -- this
    # workflow now calls it rather than referencing step-security/harden-runner
    # or actions/checkout directly. What this test actually guards (hardened
    # runner + a checkout pinned by commit SHA, not a mutable tag) is
    # unchanged; it just checks it one level of indirection later.
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "tvna/gitapex/.github/actions/harden-checkout@" in text
    # Pinned by commit SHA, not a mutable tag: a `@vN` or `@main` ref right
    # after the action path would fail this.
    assert re.search(r"tvna/gitapex/\.github/actions/harden-checkout@[0-9a-f]{40}\b", text)


def test_workflow_scopes_permissions_to_issues_write_only():
    workflow = _load_workflow()
    for job_name, job in (workflow.get("jobs") or {}).items():
        permissions = job.get("permissions")
        assert isinstance(permissions, dict), f"job {job_name} has no explicit permissions mapping"
        assert permissions.get("issues") == "write", f"job {job_name} must have issues: write"
        # No broader write scope than this gate needs.
        for scope, level in permissions.items():
            if scope == "issues":
                continue
            assert level in ("read", "none"), f"job {job_name} grants unexpected {scope}: {level}"

"""Tests for the post-merge-auto-retro minimal slice
(.github/scripts/gitapex_post_merge_retro.py).

Refs #314 (sub-issue of #140), #341: opens (with dedup) a
`chore(retrospective): merge retrospective for PR #N` issue -- this
repository's own actual title convention, not
skills/merge-retrospective/SKILL.md's generic fallback shape -- labeled
`retrospective`, when a PR merges.

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring
test_gitapex_scan_retrospective_gate_drift.py's own fixture style.
"""

from __future__ import annotations

import http.client
import json
import pathlib
import urllib.error
import urllib.request

import gitapex_post_merge_retro as pmr
import pytest
import yaml


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
# dedup_query
# ---------------------------------------------------------------------------


def test_dedup_query_matches_creation_identity_predicate():
    query = pmr.dedup_query("tvna", "gitapex", 314)
    assert query == (
        "repo:tvna/gitapex type:issue in:title "
        '"chore(retrospective): merge retrospective for PR #314" '
        "label:retrospective"
    )


def test_retro_title_matches_this_repos_actual_convention_not_the_skill_fallback():
    """Issue #341: the shape `Merge retrospective: PR #N` is
    skills/merge-retrospective/SKILL.md's generic *fallback* title, not
    this repository's own convention (established since issue #118). This
    guards against reverting to that mistaken shape."""
    title = pmr._retro_title(314)
    assert title == "chore(retrospective): merge retrospective for PR #314"
    assert title != "Merge retrospective: PR #314"


def test_dedup_query_and_open_retro_issue_title_cannot_diverge():
    """Regression for issue #341: both functions must derive the title
    phrase from the same `_retro_title` source, so a future edit to one
    cannot silently leave the other searching for/creating a different
    string than the one actually used."""
    captured: dict = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, json.dumps({"number": 99}))

    pmr.open_retro_issue("tvna", "gitapex", 314, "t", "https://github.com/tvna/gitapex/pull/314", "tok", opener=opener)
    created_title = captured["payload"]["title"]
    assert f'"{created_title}"' in pmr.dedup_query("tvna", "gitapex", 314)


# ---------------------------------------------------------------------------
# find_existing_retro_issue
# ---------------------------------------------------------------------------


def test_find_existing_retro_issue_returns_number_when_found():
    def opener(request: urllib.request.Request) -> Response:
        assert request.headers["Authorization"] == "Bearer tok"
        assert "search/issues" in request.full_url
        return Response(200, json.dumps({"total_count": 1, "items": [{"number": 42}]}))

    result = pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener)
    assert result == 42


def test_find_existing_retro_issue_returns_none_when_no_match():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"total_count": 0, "items": []}))

    result = pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener)
    assert result is None


def test_find_existing_retro_issue_retries_5xx_then_succeeds():
    responses = [http_error(503, "{}"), Response(200, json.dumps({"items": []}))]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    result = pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener, sleeper=sleeps.append)
    assert result is None
    assert sleeps == [5]


def test_find_existing_retro_issue_raises_on_persistent_4xx():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(422, "unprocessable")

    with pytest.raises(pmr.GitHubApiError):
        pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener)


def test_find_existing_retro_issue_raises_after_repeated_network_failure():
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("boom")

    with pytest.raises(pmr.GitHubApiError):
        pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 3


def test_find_existing_retro_issue_retries_incomplete_body_read_then_succeeds():
    class FlakyResponse(Response):
        def read(self) -> bytes:
            raise http.client.IncompleteRead(b"partial")

    responses = [FlakyResponse(200), Response(200, json.dumps({"items": []}))]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    result = pmr.find_existing_retro_issue("tvna", "gitapex", 314, "tok", opener=opener, sleeper=sleeps.append)
    assert result is None
    assert sleeps == [5]


# ---------------------------------------------------------------------------
# open_retro_issue
# ---------------------------------------------------------------------------


def test_open_retro_issue_posts_expected_title_and_label():
    captured: dict = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, json.dumps({"number": 99}))

    result = pmr.open_retro_issue(
        "tvna", "gitapex", 314, "feat: thing", "https://github.com/tvna/gitapex/pull/314", "tok", opener=opener
    )
    assert result == 99
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.github.com/repos/tvna/gitapex/issues"
    assert captured["payload"]["title"] == "chore(retrospective): merge retrospective for PR #314"
    assert captured["payload"]["labels"] == ["retrospective"]
    assert "#314" in captured["payload"]["body"]


def test_open_retro_issue_never_republishes_the_untrusted_pr_title():
    """A fork-controlled PR title (with an @mention / Markdown) must never
    reach the issue body -- see the mention/markdown-injection finding."""
    captured: dict = {}

    def opener(request: urllib.request.Request) -> Response:
        captured["payload"] = json.loads(request.data.decode())
        return Response(201, json.dumps({"number": 99}))

    pmr.open_retro_issue(
        "tvna",
        "gitapex",
        314,
        "@evil-org/team please **look** at this",
        "https://github.com/tvna/gitapex/pull/314",
        "tok",
        opener=opener,
    )
    assert "@evil-org/team" not in captured["payload"]["body"]
    assert "**look**" not in captured["payload"]["body"]


def test_open_retro_issue_raises_on_api_error():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "server error")

    with pytest.raises(pmr.GitHubApiError):
        pmr.open_retro_issue("tvna", "gitapex", 314, "t", "u", "tok", opener=opener, sleeper=lambda _: None)


def test_open_retro_issue_does_not_retry_the_non_idempotent_post():
    """Issue creation must not be blindly retried: a lost/truncated
    response after GitHub already created the issue would otherwise
    retry into a duplicate."""
    calls = 0

    def opener(request: urllib.request.Request) -> Response:
        nonlocal calls
        calls += 1
        raise http_error(503, "server error")

    with pytest.raises(pmr.GitHubApiError):
        pmr.open_retro_issue("tvna", "gitapex", 314, "t", "u", "tok", opener=opener, sleeper=lambda _: None)
    assert calls == 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_exits_one_on_missing_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"]) == 1


def test_main_skips_create_when_dedup_finds_existing(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(pmr, "find_existing_retro_issue", lambda *a, **k: 7)

    def fail_if_called(*a, **k):
        raise AssertionError("open_retro_issue should not be called when a dup exists")

    monkeypatch.setattr(pmr, "open_retro_issue", fail_if_called)
    exit_code = pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 0
    assert "already exists" in capsys.readouterr().out


def test_main_opens_issue_when_no_existing_found(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(pmr, "find_existing_retro_issue", lambda *a, **k: None)
    monkeypatch.setattr(pmr, "open_retro_issue", lambda *a, **k: 55)
    exit_code = pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 0
    assert "Opened retrospective issue #55" in capsys.readouterr().out


def test_main_exits_one_on_github_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    def raise_api_error(*a, **k):
        raise pmr.GitHubApiError("boom")

    monkeypatch.setattr(pmr, "find_existing_retro_issue", raise_api_error)
    assert pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "314"]) == 1


# ---------------------------------------------------------------------------
# _CliArgs pydantic validation (new in this batch's CLI-pydantic-wrap)
# ---------------------------------------------------------------------------


def test_main_rejects_blank_owner(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = pmr.main(["--owner", "", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_non_positive_pr_number(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "0"])
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err


def test_main_rejects_whitespace_only_owner(monkeypatch, capsys):
    """Issue #1087: min_length=1 alone accepts a whitespace-only value;
    the field must reject it the same as a truly blank one."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = pmr.main(["--owner", " ", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 1
    assert "error: invalid arguments: --owner (must not be blank)" in capsys.readouterr().err


def test_main_rejects_whitespace_only_repo(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = pmr.main(["--owner", "tvna", "--repo", "\t", "--pr-number", "314"])
    assert exit_code == 1
    assert "error: invalid arguments: --repo (must not be blank)" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Issue #1094: str.strip() alone leaves Unicode Format-category (Cf)
# characters in place (confirmed for U+200B ZERO WIDTH SPACE, U+FEFF
# ZERO WIDTH NO-BREAK SPACE, and U+180E MONGOLIAN VOWEL SEPARATOR), so a
# value composed solely of Cf marks passed issue #1087's whitespace-only
# guard unrejected.
# ---------------------------------------------------------------------------


def test_main_rejects_invisible_only_owner(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = pmr.main(["--owner", "\u200b", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 1
    assert "error: invalid arguments: --owner (must not be blank)" in capsys.readouterr().err


def test_main_rejects_invisible_only_repo(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    exit_code = pmr.main(["--owner", "tvna", "--repo", "\ufeff", "--pr-number", "314"])
    assert exit_code == 1
    assert "error: invalid arguments: --repo (must not be blank)" in capsys.readouterr().err


def test_main_keeps_invisible_padded_but_meaningful_owner_unmutated(monkeypatch, capsys):
    """A value padded with a Cf mark rather than ASCII whitespace must
    keep working, unmutated -- only an entirely invisible/non-printing
    value changes verdict (issue #1094)."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    received = {}

    def fake_find(owner, repo, pr_number, token):
        received["owner"] = owner
        received["repo"] = repo
        return

    def fake_open(owner, repo, pr_number, pr_title, pr_url, token):
        received["owner"] = owner
        return 999

    monkeypatch.setattr(pmr, "find_existing_retro_issue", fake_find)
    monkeypatch.setattr(pmr, "open_retro_issue", fake_open)
    exit_code = pmr.main(["--owner", "\u200btvna\u200b", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 0
    assert received["owner"] == "\u200btvna\u200b"


def test_main_keeps_padded_but_meaningful_owner_unmutated(monkeypatch, capsys):
    """Issue #1087: validation must not silently trim -- a value with real
    content plus surrounding whitespace reaches the downstream call exactly
    as typed."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    received = {}

    def fake_find(owner, repo, pr_number, token):
        received["owner"] = owner
        received["repo"] = repo
        return

    def fake_open(owner, repo, pr_number, pr_title, pr_url, token):
        received["owner"] = owner
        return 999

    monkeypatch.setattr(pmr, "find_existing_retro_issue", fake_find)
    monkeypatch.setattr(pmr, "open_retro_issue", fake_open)
    exit_code = pmr.main(["--owner", " tvna ", "--repo", "gitapex", "--pr-number", "314"])
    assert exit_code == 0
    assert received["owner"] == " tvna "


def test_main_renders_underscored_field_as_its_hyphenated_flag(monkeypatch, capsys):
    """Issue #822: `pr_number` is the model's field name but `--pr-number`
    is the flag an operator actually typed, so the `ValidationError`
    handler must report the hyphenated flag, never the raw field name,
    never pydantic's own message text, and never the rejected value."""
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    assert pmr.main(["--owner", "tvna", "--repo", "gitapex", "--pr-number", "-7"]) == 1
    stderr = capsys.readouterr().err
    # The constraint wording, not just the flag name: naming only
    # `--pr-number` would tell an operator which flag was rejected but not
    # what it needed, which is the actionability the replaced hand-rolled
    # message carried and this handler must not drop.
    assert "error: invalid arguments: --pr-number (must be a positive integer)" in stderr
    assert "pr_number" not in stderr
    assert "-7" not in stderr
    assert "Input should be greater than 0" not in stderr


# ---------------------------------------------------------------------------
# Drift gate: the workflow's own "permanent human-review-of-merge" posture
# (issue #318's own commit on post-merge-retro.yml) is enforced here, not
# just stated in a comment. Per Codex review on PR #354: nothing previously
# guarded this workflow's permissions or steps -- a future edit adding
# `pull-requests: write` or a merge-capable step could ship green despite
# violating the declared permanent architecture. This asserts it directly
# against the real workflow file.
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "post-merge-retro.yml"

# Any of these appearing in a step's `run:` string or `uses:` action ref is
# treated as a merge capability -- deliberately broad substrings (not an
# exhaustive parse of every possible merge mechanism) so a new merge-shaped
# step is more likely to trip this than to slip through unnoticed.
_MERGE_CAPABLE_MARKERS = (
    "gh pr merge",
    "gh pr merge --auto",
    "merge_pull_request",
    "enable_pr_auto_merge",
    "/merge",  # e.g. a raw REST call to PUT /repos/.../pulls/{n}/merge
    "pulls/merge",
)


def _load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _iter_permissions_blocks(workflow):
    """Yield every `permissions:` mapping in the workflow -- the top-level
    one and each job's own, since either scope could grant a capability."""
    top_level = workflow.get("permissions")
    if top_level is not None:
        yield "top-level", top_level
    for job_name, job in (workflow.get("jobs") or {}).items():
        job_permissions = job.get("permissions")
        if job_permissions is not None:
            yield f"job:{job_name}", job_permissions


def test_workflow_file_exists_and_parses():
    assert WORKFLOW_PATH.is_file(), f"expected {WORKFLOW_PATH} to exist"
    workflow = _load_workflow()
    assert workflow.get("jobs"), f"{WORKFLOW_PATH} has no jobs -- parse likely broke"


def test_workflow_never_grants_pull_requests_write():
    workflow = _load_workflow()
    offenders = []
    for scope_name, permissions in _iter_permissions_blocks(workflow):
        if not isinstance(permissions, dict):
            # A bare `permissions: write-all` (or similar scalar) implicitly
            # grants everything, including pull-requests -- treat any
            # non-mapping form as an offender rather than trying to parse
            # GitHub Actions' shorthand scalar forms.
            offenders.append((scope_name, permissions))
            continue
        pr_permission = permissions.get("pull-requests")
        if pr_permission is not None and pr_permission != "read" and pr_permission != "none":
            offenders.append((scope_name, permissions))
    assert not offenders, (
        f"{WORKFLOW_PATH} grants pull-requests write (or an unparseable "
        f"blanket permission) in: {offenders} -- this workflow's own header "
        "comment declares it may only ever open an issue; a merge-capable "
        "permission here would violate that permanently-declared invariant."
    )


def test_workflow_has_no_merge_capable_step():
    workflow = _load_workflow()
    offenders = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            haystack = " ".join(str(step.get(key, "")) for key in ("run", "uses", "with")).lower()
            hits = [marker for marker in _MERGE_CAPABLE_MARKERS if marker in haystack]
            if hits:
                offenders.append((job_name, step.get("name", "<unnamed step>"), hits))
    assert not offenders, (
        f"{WORKFLOW_PATH} has a step that looks merge-capable: {offenders} -- "
        "this workflow's own header comment declares 100% human review of "
        "merges as a permanent architectural feature; it may never merge a "
        "pull request itself."
    )

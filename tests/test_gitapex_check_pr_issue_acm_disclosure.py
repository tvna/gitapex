"""Direct-import, opener-injection unit suite for
hooks/gitapex_check_pr_issue_acm_disclosure.py (issue #657).

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring
tests/test_gitapex_gate_acm_issue_disclosure.py's own fixture style (the one
existing precedent in this repository for a network-calling module's
test suite). `hooks` is on pyproject.toml's `pythonpath`, so this module
imports the same way tests/test_gitapex_gate_acm_issue_disclosure.py imports
gitapex_gate_acm_issue_disclosure -- as a plain top-level module, not via
importlib.util.

Subprocess-level `.sh`-wrapper tests (the paths that don't need a fake
network: tool_name filtering, no-citation deny, missing-checker,
no-token) live in hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py
instead -- see that file's own docstring for why the split. (Named
`_shell` specifically to avoid a pytest basename collision with this
file -- both `tests/` and `hooks/` are on `testpaths` with no
`__init__.py` in either, so two files sharing a basename fail collection
with "import file mismatch".)
"""

from __future__ import annotations

import http.client
import io
import json
import urllib.error
import urllib.request

import gitapex_check_pr_issue_acm_disclosure as checker
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


_VALID_ACM_TABLE = (
    "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
    "|---|---|---|---|---|\n"
    "| Thing works | It should do X | Add Y | Run Z | None |\n"
)


# ---------------------------------------------------------------------------
# extract_citations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "keyword",
    ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"],
)
def test_every_github_closing_keyword_resolves(keyword):
    resolving, context = checker.extract_citations("o", "r", "title", f"{keyword} #12")
    assert resolving == (12,)
    assert context == ()


@pytest.mark.parametrize("keyword", ["CLOSES", "Fixes", "RESOLVED"])
def test_resolving_keywords_are_case_insensitive(keyword):
    resolving, _ = checker.extract_citations("o", "r", "title", f"{keyword} #7")
    assert resolving == (7,)


def test_resolving_keyword_colon_is_optional():
    assert checker.extract_citations("o", "r", "t", "Closes: #10")[0] == (10,)
    assert checker.extract_citations("o", "r", "t", "Closes #10")[0] == (10,)


def test_comma_separated_list_only_first_number_resolves():
    # GitHub's own docs: "use full syntax for each issue" -- a keyword
    # followed by a bare comma-separated list does not resolve every
    # number, only the one directly following the keyword. The second
    # number still counts as a context-only citation.
    resolving, context = checker.extract_citations("o", "r", "t", "Closes #12, #34")
    assert resolving == (12,)
    assert context == (34,)


def test_refs_keyword_is_context_only():
    resolving, context = checker.extract_citations("o", "r", "t", "Refs #5")
    assert resolving == ()
    assert context == (5,)


def test_bare_number_is_context_only():
    resolving, context = checker.extract_citations("o", "r", "t", "See #5 for background.")
    assert resolving == ()
    assert context == (5,)


def test_title_bare_number_counts_as_context_but_never_resolving():
    resolving, context = checker.extract_citations("o", "r", "Follow-up to #5", "Closes #12")
    assert resolving == (12,)
    assert context == (5,)


def test_resolving_keyword_in_title_is_not_resolving():
    # GitHub never treats a title keyword as auto-closing -- only the body.
    resolving, context = checker.extract_citations("o", "r", "Closes #12", "no citation here")
    assert resolving == ()
    assert context == (12,)


def test_number_cited_both_ways_stays_resolving_only():
    resolving, context = checker.extract_citations("o", "r", "t", "Closes #12. Also see Refs #12.")
    assert resolving == (12,)
    assert context == ()


def test_cross_repo_citation_is_excluded_from_both_buckets():
    # A genuinely foreign repo (not the PR's own tvna/gitapex) stays
    # excluded from both buckets -- see the same-repo-qualified tests
    # below for the PR's-own-repo case, which is now normalized instead.
    resolving, context = checker.extract_citations("tvna", "gitapex", "t", "Closes tvna/other-repo#99")
    assert resolving == ()
    assert context == ()


def test_same_repo_qualified_citation_resolves():
    # Regression for issue #657's own adversarial review: a same-repo-
    # qualified citation ("Fixes tvna/gitapex#12") auto-closes on GitHub
    # exactly like a bare "Fixes #12" -- excluding it would be a real
    # bypass of this hook's whole purpose, the same class of gap as
    # excluding "Resolves" (see this module's own docstring).
    resolving, context = checker.extract_citations("tvna", "gitapex", "t", "Fixes tvna/gitapex#12")
    assert resolving == (12,)
    assert context == ()


def test_same_repo_qualified_citation_is_case_insensitive():
    resolving, _ = checker.extract_citations("tvna", "gitapex", "t", "Fixes TVNA/GitApex#12")
    assert resolving == (12,)


def test_same_repo_qualified_bare_number_is_context_only():
    resolving, context = checker.extract_citations("tvna", "gitapex", "t", "See tvna/gitapex#5 for background.")
    assert resolving == ()
    assert context == (5,)


def test_same_repo_qualified_refs_keyword_is_context_only():
    resolving, context = checker.extract_citations("tvna", "gitapex", "t", "Refs tvna/gitapex#5")
    assert resolving == ()
    assert context == (5,)


def test_same_repo_qualified_citation_does_not_match_a_longer_repo_name():
    # "tvna/gitapex-extra#12" must not be treated as a same-repo citation
    # of tvna/gitapex -- the normalization only strips an exact
    # "owner/repo" immediately followed by "#digit".
    resolving, context = checker.extract_citations("tvna", "gitapex", "t", "Fixes tvna/gitapex-extra#12")
    assert resolving == ()
    assert context == ()


def test_missing_owner_or_repo_does_not_normalize_anything():
    # extract_citations must not crash or misbehave when owner/repo are
    # falsy (e.g. an incomplete payload) -- same-repo normalization is
    # simply skipped, matching pre-fix behavior for that input shape.
    resolving, context = checker.extract_citations("", "", "t", "Fixes tvna/gitapex#12")
    assert resolving == ()
    assert context == ()


def test_fenced_code_block_is_stripped_before_scanning():
    body = "no real citation.\n```\nCloses #12\n```\nRefs #34"
    resolving, context = checker.extract_citations("o", "r", "t", body)
    assert resolving == ()
    assert context == (34,)


def test_tilde_fenced_code_block_is_stripped_before_scanning():
    body = "~~~\nCloses #12\n~~~\nRefs #34"
    resolving, context = checker.extract_citations("o", "r", "t", body)
    assert resolving == ()
    assert context == (34,)


def test_no_citation_at_all_yields_two_empty_tuples():
    assert checker.extract_citations("o", "r", "plain title", "plain body, nothing here") == ((), ())


def test_inline_code_span_citation_is_stripped_before_scanning():
    # Regression: found via live-exercise against this hook's own PR body,
    # which documents its own citation syntax with illustrative examples
    # like `Closes #123`. A backtick-quoted example is documentation about
    # the syntax, not a resolution claim -- must not be misdetected as a
    # real citation of #123.
    body = "The `Closes #123` syntax auto-closes an issue. See Refs #34 too."
    resolving, context = checker.extract_citations("o", "r", "t", body)
    assert resolving == ()
    assert context == (34,)


def test_inline_code_span_does_not_swallow_content_after_it():
    body = "`Closes #12` then a real citation: Fixes #99"
    resolving, _context = checker.extract_citations("o", "r", "t", body)
    assert resolving == (99,)


def test_multiple_inline_code_spans_on_one_line_are_each_stripped():
    body = "See `hooks/gitapex_check_acm_present_or_waiver.py`'s `has_acm_disclosure` -- Closes #7"
    resolving, _context = checker.extract_citations("o", "r", "t", body)
    assert resolving == (7,)


# ---------------------------------------------------------------------------
# _call / fetch_issue retry behavior
# ---------------------------------------------------------------------------


def test_call_succeeds_first_try():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"body": "x", "state": "open"}))

    result = checker._call("https://api.github.com/repos/o/r/issues/1", "tok", opener, lambda _: None)
    assert result == {"body": "x", "state": "open"}


def test_call_retries_5xx_then_succeeds():
    responses = [http_error(503, "{}"), Response(200, "{}")]
    sleeps: list[float] = []

    def opener(request: urllib.request.Request) -> Response:
        response = responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response

    checker._call("https://api.github.com/repos/o/r/issues/1", "tok", opener, sleeps.append)
    assert sleeps == [5]


def test_call_retries_network_error_then_succeeds():
    calls = {"n": 0}

    def opener(request: urllib.request.Request) -> Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("boom")
        return Response(200, "{}")

    checker._call("https://api.github.com/repos/o/r/issues/1", "tok", opener, lambda _: None)
    assert calls["n"] == 2


def test_call_retries_incomplete_read_then_succeeds():
    class FlakyResponse(Response):
        def read(self) -> bytes:
            raise http.client.IncompleteRead(b"partial")

    responses = [FlakyResponse(200), Response(200, "{}")]

    def opener(request: urllib.request.Request) -> Response:
        return responses.pop(0)

    checker._call("https://api.github.com/repos/o/r/issues/1", "tok", opener, lambda _: None)


def test_call_404_raises_not_found_without_retry():
    calls = {"n": 0}

    def opener(request: urllib.request.Request) -> Response:
        calls["n"] += 1
        raise http_error(404, "{}")

    with pytest.raises(checker.GitHubApiError, match="not-found"):
        checker._call("https://api.github.com/repos/o/r/issues/1", "tok", opener, lambda _: None)
    assert calls["n"] == 1


def test_call_403_fails_without_retry():
    calls = {"n": 0}

    def opener(request: urllib.request.Request) -> Response:
        calls["n"] += 1
        raise http_error(403, "{}")

    with pytest.raises(checker.GitHubApiError, match="HTTP 403"):
        checker._call("https://api.github.com/repos/o/r/issues/1", "tok", opener, lambda _: None)
    assert calls["n"] == 1


def test_call_raises_after_exhausting_retries_on_repeated_5xx():
    calls = {"n": 0}

    def opener(request: urllib.request.Request) -> Response:
        calls["n"] += 1
        raise http_error(500, "{}")

    with pytest.raises(checker.GitHubApiError, match="HTTP 500"):
        checker._call("https://api.github.com/repos/o/r/issues/1", "tok", opener, lambda _: None)
    assert calls["n"] == checker._MAX_ATTEMPTS


def test_fetch_issue_returns_body_and_state():
    def opener(request: urllib.request.Request) -> Response:
        assert request.full_url == "https://api.github.com/repos/tvna/gitapex/issues/657"
        assert request.get_header("Authorization") == "Bearer tok"
        return Response(200, json.dumps({"body": "the body", "state": "open"}))

    result = checker.fetch_issue("tvna", "gitapex", 657, "tok", opener=opener, sleeper=lambda _: None)
    assert result == {"body": "the body", "state": "open"}


# ---------------------------------------------------------------------------
# classify_issue
# ---------------------------------------------------------------------------


def _opener_for(body: str, state: str = "open"):
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"body": body, "state": state}))

    return opener


def test_classify_issue_passes_with_acm_table():
    reason = checker.classify_issue("o", "r", 1, "tok", opener=_opener_for(_VALID_ACM_TABLE), sleeper=lambda _: None)
    assert reason is None


@pytest.mark.parametrize("category", ["chore", "docs", "defect"])
def test_classify_issue_passes_with_non_tracking_waiver(category):
    body = f"ACM: not-applicable ({category}): reason here.\n"
    reason = checker.classify_issue("o", "r", 1, "tok", opener=_opener_for(body), sleeper=lambda _: None)
    assert reason is None


def test_classify_issue_fails_with_tracking_waiver():
    body = "ACM: not-applicable (tracking): umbrella issue.\n"
    reason = checker.classify_issue("o", "r", 1, "tok", opener=_opener_for(body), sleeper=lambda _: None)
    assert reason is not None
    assert "tracking" in reason
    assert "#1" in reason


def test_classify_issue_fails_with_no_disclosure():
    reason = checker.classify_issue(
        "o", "r", 1, "tok", opener=_opener_for("just a plain issue body"), sleeper=lambda _: None
    )
    assert reason is not None
    assert "no Acceptance Criteria Map" in reason


def test_classify_issue_fails_when_closed_even_with_valid_acm():
    reason = checker.classify_issue(
        "o", "r", 1, "tok", opener=_opener_for(_VALID_ACM_TABLE, state="closed"), sleeper=lambda _: None
    )
    assert reason is not None
    assert "already closed" in reason


def test_classify_issue_reports_not_found_distinctly():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(404, "{}")

    reason = checker.classify_issue("o", "r", 999, "tok", opener=opener, sleeper=lambda _: None)
    assert reason == "#999: issue not found"


def test_classify_issue_reports_fetch_failure_without_echoing_body():
    def opener(request: urllib.request.Request) -> Response:
        raise http_error(500, "{}")

    reason = checker.classify_issue("o", "r", 999, "tok", opener=opener, sleeper=lambda _: None)
    assert reason is not None
    assert "#999" in reason
    assert "could not fetch" in reason


def test_classify_issue_never_echoes_issue_body_into_the_reason():
    secret_looking_body = "SUPER-SECRET-MARKER-1234 no disclosure here"
    reason = checker.classify_issue("o", "r", 1, "tok", opener=_opener_for(secret_looking_body), sleeper=lambda _: None)
    assert "SUPER-SECRET-MARKER-1234" not in reason


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------


def test_evaluate_denies_when_nothing_cited():
    passed, message = checker.evaluate("o", "r", "title", "no citation", "tok")
    assert passed is False
    assert "cites no issue" in message


def test_evaluate_passes_context_only_citation_without_any_token_or_network():
    # token=None and no opener that would ever be called for a resolving
    # fetch -- if this reaches the network layer at all, the default
    # opener would attempt a real connection and this test would hang or
    # error, not silently pass.
    passed, message = checker.evaluate("o", "r", "title", "Refs #5", None)
    assert passed is True
    assert "context-only" in message


def test_evaluate_denies_when_resolving_citation_but_no_token():
    passed, message = checker.evaluate("o", "r", "title", "Closes #5", None)
    assert passed is False
    assert "#5" in message
    assert "GH_TOKEN" in message and "GITHUB_TOKEN" in message


def test_evaluate_passes_when_resolving_issue_is_clean():
    passed, _message = checker.evaluate(
        "o", "r", "title", "Closes #1", "tok", opener=_opener_for(_VALID_ACM_TABLE), sleeper=lambda _: None
    )
    assert passed is True


def test_evaluate_does_not_bypass_a_same_repo_qualified_resolving_citation():
    # End-to-end regression for issue #657's own adversarial review: before
    # the fix, extract_citations excluded "Fixes tvna/gitapex#12" from
    # both buckets entirely, so evaluate() never reached the network fetch
    # at all and silently allowed a PR that should have been ACM-gated.
    called = {"n": 0}

    def opener(request: urllib.request.Request) -> Response:
        called["n"] += 1
        return Response(200, json.dumps({"body": "no disclosure here", "state": "open"}))

    passed, message = checker.evaluate(
        "tvna", "gitapex", "t", "Fixes tvna/gitapex#12", "tok", opener=opener, sleeper=lambda _: None
    )
    assert called["n"] == 1
    assert passed is False
    assert "#12" in message


def test_evaluate_denies_and_aggregates_multiple_failures():
    def opener(request: urllib.request.Request) -> Response:
        number = request.full_url.rsplit("/", 1)[-1]
        if number == "1":
            return Response(200, json.dumps({"body": "no disclosure", "state": "open"}))
        return Response(200, json.dumps({"body": "ACM: not-applicable (tracking): x.", "state": "open"}))

    passed, message = checker.evaluate(
        "o", "r", "title", "Closes #1, Fixes #2", "tok", opener=opener, sleeper=lambda _: None
    )
    assert passed is False
    assert "#1" in message
    assert "#2" in message
    assert "tracking" in message


# ---------------------------------------------------------------------------
# main -- CLI entry point
# ---------------------------------------------------------------------------


def test_main_reads_payload_from_stdin_and_denies(monkeypatch, capsys):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    payload = json.dumps({"owner": "o", "repo": "r", "title": "t", "body": "no citation"})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert checker.main([]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_reads_payload_from_file(monkeypatch, tmp_path, capsys):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps({"owner": "o", "repo": "r", "title": "t", "body": "Refs #1"}), encoding="utf-8")
    assert checker.main(["--payload", str(path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reports_error_for_missing_payload_file(capsys):
    assert checker.main(["--payload", "/no/such/file.json"]) == 1
    assert "not found" in capsys.readouterr().err


def test_main_reports_error_for_malformed_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert checker.main([]) == 1
    assert "not valid JSON" in capsys.readouterr().err


@pytest.mark.parametrize("payload", ["[]", '"a string"', "1", "null", "true"])
def test_main_reports_error_for_non_object_json_payload(monkeypatch, capsys, payload):
    # Issue #680 Shape 1: json.loads("[]") etc. all parse fine, so
    # payload.get("owner") used to raise an uncaught AttributeError instead
    # of the documented FAIL:/error: exit path.
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert checker.main([]) == 1
    err = capsys.readouterr().err
    assert "must be a JSON object" in err
    assert "stdin" in err


def test_main_reports_error_for_non_object_json_payload_names_the_file(tmp_path, capsys):
    # Companion to the stdin case above: --payload's error message must
    # name the offending file too, matching every other fix in this issue
    # (found by adversarial review -- the first version of this message
    # named neither stdin nor the file).
    path = tmp_path / "payload.json"
    path.write_text("[]", encoding="utf-8")
    assert checker.main(["--payload", str(path)]) == 1
    assert str(path) in capsys.readouterr().err


def test_main_reports_error_for_non_utf8_payload_file(tmp_path, capsys):
    # Issue #680 Shape 2, for this same file's own --payload read path
    # (not one of the six originally-named lines, but the identical
    # UnicodeDecodeError-on-a-decoded-read shape, one function above the
    # Shape 1 fix in this file -- found by adversarial review).
    path = tmp_path / "payload.bin"
    path.write_bytes(b"\xff\xfe\x00\x01")
    assert checker.main(["--payload", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert str(path) in err


def test_main_prefers_gh_token_over_github_token(monkeypatch):
    # gh CLI's own documented precedence: GH_TOKEN, GITHUB_TOKEN (in that
    # order) -- see this module's docstring for the primary-source citation.
    monkeypatch.setenv("GH_TOKEN", "gh-token-value")
    monkeypatch.setenv("GITHUB_TOKEN", "github-token-value")
    captured = {}

    def fake_evaluate(owner, repo, title, body, token, **kwargs):
        captured["token"] = token
        return True, "ok"

    monkeypatch.setattr(checker, "evaluate", fake_evaluate)
    payload = json.dumps({"owner": "o", "repo": "r", "title": "t", "body": "Closes #1"})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    checker.main([])
    assert captured["token"] == "gh-token-value"


def test_main_falls_back_to_github_token_when_gh_token_absent(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "github-token-value")
    captured = {}

    def fake_evaluate(owner, repo, title, body, token, **kwargs):
        captured["token"] = token
        return True, "ok"

    monkeypatch.setattr(checker, "evaluate", fake_evaluate)
    payload = json.dumps({"owner": "o", "repo": "r", "title": "t", "body": "Closes #1"})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    checker.main([])
    assert captured["token"] == "github-token-value"

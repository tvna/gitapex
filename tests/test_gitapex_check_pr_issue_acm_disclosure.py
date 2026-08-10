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
from allpairspy import AllPairs


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


def test_fetch_issue_raises_cleanly_on_non_dict_response():
    # Issue #995: `_call`'s return value is unvalidated parsed JSON
    # (`_gitapex_github_http.py`'s own contract) -- a non-dict response body
    # used to raise an uncaught AttributeError on `data.get(...)` instead of
    # this module's own documented GitHubApiError.
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(["not", "a", "dict"]))

    with pytest.raises(checker.GitHubApiError, match="expected a JSON object"):
        checker.fetch_issue("tvna", "gitapex", 657, "tok", opener=opener, sleeper=lambda _: None)


@pytest.mark.parametrize("field_name", ["body", "state"])
def test_fetch_issue_raises_cleanly_on_non_string_field(field_name):
    # A CodeRabbit review finding on this PR: the dict-shape check on `data`
    # says nothing about `body`/`state`'s own types -- a truthy non-string
    # value (e.g. an int) used to pass `data.get(field) or ""` unchanged,
    # later crashing `acm_checker.has_acm_disclosure`'s `.replace()` call
    # with an uncaught AttributeError instead of this documented error.
    payload = {"body": "the body", "state": "open"}
    payload[field_name] = 12345

    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps(payload))

    with pytest.raises(checker.GitHubApiError, match=f"non-string issue '{field_name}'"):
        checker.fetch_issue("tvna", "gitapex", 657, "tok", opener=opener, sleeper=lambda _: None)


def test_fetch_issue_allows_null_body_and_state():
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"body": None, "state": None}))

    result = checker.fetch_issue("tvna", "gitapex", 657, "tok", opener=opener, sleeper=lambda _: None)
    assert result == {"body": "", "state": ""}


# ---------------------------------------------------------------------------
# classify_issue
# ---------------------------------------------------------------------------


def _opener_for(body: str, state: str = "open"):
    def opener(request: urllib.request.Request) -> Response:
        return Response(200, json.dumps({"body": body, "state": state}))

    return opener


@pytest.mark.parametrize("category", ["chore", "docs", "defect"])
def test_classify_issue_passes_with_non_tracking_waiver(category):
    # Not part of the generated table below: "category" isn't one of its
    # two dimensions -- the outcome dimension only distinguishes
    # "non_tracking_waiver" as one bucket, deliberately not per-category
    # (see the table's own module docstring), so this enumeration of
    # waiver_category's three non-tracking values would otherwise lose
    # coverage if folded in.
    body = f"ACM: not-applicable ({category}): reason here.\n"
    reason = checker.classify_issue("o", "r", 1, "tok", opener=_opener_for(body), sleeper=lambda _: None)
    assert reason is None


def test_classify_issue_never_echoes_issue_body_into_the_reason():
    # Not part of the generated table below: a security property (no
    # leakage of arbitrary body content), not a citation-shape/outcome
    # interaction the two dimensions model.
    secret_looking_body = "SUPER-SECRET-MARKER-1234 no disclosure here"
    reason = checker.classify_issue("o", "r", 1, "tok", opener=_opener_for(secret_looking_body), sleeper=lambda _: None)
    assert "SUPER-SECRET-MARKER-1234" not in reason


# ---------------------------------------------------------------------------
# evaluate / classify_issue -- allpairspy pairwise (2-way) generated table
# ---------------------------------------------------------------------------
#
# Pilot for issue #1005/#1008: generates coverage for the prior OAT
# (one-factor-at-a-time) test_evaluate_*/test_classify_issue_* functions
# above via two independent dimensions, exercised end-to-end through
# evaluate() (which itself calls classify_issue once per resolving
# citation number):
#
#   - citation shape: what evaluate()'s own extract_citations call sees in
#     the PR title/body.
#   - outcome: what classify_issue resolves a single cited issue number to,
#     once evaluate() actually reaches the network layer ("token_absent"
#     doubles as the placeholder outcome for the two shapes -- none,
#     context_only -- that never reach classify_issue at all).
#
# "Multi-resolving" (e.g. "Closes #1, Fixes #2") is deliberately excluded
# from these dimensions: evaluate() calls classify_issue once per resolving
# number and joins every failure, so a multi-issue case needs its own
# per-issue outcome pair, not one flat "outcome" value -- exactly what the
# kept test_evaluate_denies_and_aggregates_multiple_failures below exists
# to cover, not a generated dimension.
#
# "none"/"context_only" are only ever valid paired with the single
# "token_absent" placeholder outcome (see _is_valid_pair below) -- a
# degenerate, non-combinatorial case with nothing for a pairwise algorithm
# to search, so those two rows are listed directly rather than generated.
# allpairspy's own IPO-style search (allpairspy/allpairs.py: __next__ stops
# once one pass finds no *new* unique pair, not once every *reachable*
# valid pair is covered) got stranded early when asked to search this
# highly-asymmetric-validity space directly -- confirmed empirically:
# feeding all four shapes plus a filter_func into one AllPairs call silently
# returned only 6 of the 18 valid pairs, which is exactly the gap this
# file's own test_pairwise_table_covers_every_valid_2_way_pair below exists
# to catch rather than assume away. The two resolving shapes are valid with
# every outcome, so that genuinely combinatorial subspace (2x8 = 16 pairs)
# is what AllPairs generates below.

_TRIVIAL_SHAPES = ["none", "context_only"]
_RESOLVING_SHAPES = ["single_resolving", "same_repo_qualified_resolving"]
_CITATION_SHAPES = _TRIVIAL_SHAPES + _RESOLVING_SHAPES
_OUTCOMES = [
    "token_absent",
    "valid_acm",
    "non_tracking_waiver",
    "tracking_waiver",
    "no_disclosure",
    "closed",
    "fetch_404",
    "fetch_500",
]


def _is_valid_pair(shape, outcome):
    # evaluate() never reaches classify_issue for a non-resolving shape
    # (none/context_only) regardless of token -- only the "token_absent"
    # placeholder outcome is meaningful there.
    if shape in _TRIVIAL_SHAPES:
        return outcome == "token_absent"
    return True


def _allpairs_filter(row):
    # The resolving-shapes subspace below is fully valid today (every
    # outcome applies to both resolving shapes), so this is a no-op in
    # practice -- kept so a future change narrowing _RESOLVING_SHAPES' or
    # _OUTCOMES' validity is still caught by generation, not silently
    # under-covered.
    if len(row) < 2:
        return True
    return _is_valid_pair(row[0], row[1])


def _scenario_for(shape, outcome):
    """Build the evaluate() call kwargs plus the expected (passed, message
    substrings) for one generated (shape, outcome) pair."""
    if shape == "none":
        return (
            {"owner": "o", "repo": "r", "title": "title", "body": "no citation here", "token": "tok"},
            False,
            ("cites no issue",),
        )
    if shape == "context_only":
        # token=None and no opener -- if evaluate() reached the network
        # layer at all for this shape, the default opener would attempt a
        # real connection and this case would hang or error, not pass.
        return (
            {"owner": "o", "repo": "r", "title": "title", "body": "Refs #5", "token": None},
            True,
            ("context-only",),
        )

    if shape == "single_resolving":
        owner, repo, number, body = "o", "r", 1, "Closes #1"
    else:
        owner, repo, number, body = "tvna", "gitapex", 12, "Fixes tvna/gitapex#12"

    if outcome == "token_absent":
        return (
            {"owner": owner, "repo": repo, "title": "title", "body": body, "token": None},
            False,
            (f"#{number}", "GH_TOKEN", "GITHUB_TOKEN"),
        )

    # outcome -> (issue body, issue state, HTTP error code or None, expected passed, expected message substrings)
    outcome_specs = {
        "valid_acm": (_VALID_ACM_TABLE, "open", None, True, ()),
        "non_tracking_waiver": ("ACM: not-applicable (chore): reason.\n", "open", None, True, ()),
        "tracking_waiver": ("ACM: not-applicable (tracking): x.\n", "open", None, False, (f"#{number}", "tracking")),
        "no_disclosure": (
            "just a plain issue body",
            "open",
            None,
            False,
            (f"#{number}", "no Acceptance Criteria Map"),
        ),
        "closed": (_VALID_ACM_TABLE, "closed", None, False, (f"#{number}", "already closed")),
        "fetch_404": ("", "", 404, False, (f"#{number}", "issue not found")),
        "fetch_500": ("", "", 500, False, (f"#{number}", "could not fetch")),
    }
    resp_body, state, http_code, expect_passed, expect_substrings = outcome_specs[outcome]

    def opener(request: urllib.request.Request) -> Response:
        if http_code is not None:
            raise http_error(http_code, "{}")
        return Response(200, json.dumps({"body": resp_body, "state": state}))

    return (
        {
            "owner": owner,
            "repo": repo,
            "title": "title",
            "body": body,
            "token": "tok",
            "opener": opener,
            "sleeper": lambda _: None,
        },
        expect_passed,
        expect_substrings,
    )


_REQUIRED_PAIRS = {
    (shape, outcome) for shape in _CITATION_SHAPES for outcome in _OUTCOMES if _is_valid_pair(shape, outcome)
}
_PAIRWISE_TABLE = [(shape, "token_absent") for shape in _TRIVIAL_SHAPES] + [
    tuple(row) for row in AllPairs([_RESOLVING_SHAPES, _OUTCOMES], filter_func=_allpairs_filter)
]


def test_pairwise_table_covers_every_valid_2_way_pair():
    # filter_func only prevents an *invalid* row from being emitted; it
    # does not by itself prove the emitted, valid rows still cover every
    # required pair -- recompute both sets independently and diff them.
    # Missing rows aren't the only way this table could silently drift: a
    # future generator change could also emit a duplicate or an invalid
    # row without breaking the missing-pair check above, so check those
    # too rather than assuming the two counts stay in lockstep.
    covered = set(_PAIRWISE_TABLE)
    missing = _REQUIRED_PAIRS - covered
    unexpected = covered - _REQUIRED_PAIRS
    duplicates = len(_PAIRWISE_TABLE) - len(covered)
    assert not missing, f"generated pairwise table is missing required 2-way pairs: {sorted(missing)}"
    assert not unexpected, f"generated pairwise table has unexpected rows: {sorted(unexpected)}"
    assert not duplicates, f"generated pairwise table has {duplicates} duplicate row(s)"


@pytest.mark.parametrize(
    ("shape", "outcome"), _PAIRWISE_TABLE, ids=[f"{shape}-{outcome}" for shape, outcome in _PAIRWISE_TABLE]
)
def test_evaluate_pairwise(shape, outcome):
    kwargs, expect_passed, expect_substrings = _scenario_for(shape, outcome)
    passed, message = checker.evaluate(**kwargs)
    assert passed is expect_passed
    for substring in expect_substrings:
        assert substring in message


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


@pytest.mark.parametrize("field_name", ["owner", "repo", "title", "body"])
@pytest.mark.parametrize("bad_value", [123, ["a", "list"], {"a": "dict"}, True])
def test_main_reports_error_for_non_string_payload_field(monkeypatch, capsys, field_name, bad_value):
    # Issue #995: `payload.get(field) or ""` tolerates an absent/None field
    # but passes a truthy non-string value (e.g. an int from a malformed
    # hook-stdin payload) through unchanged. owner/repo then crash
    # `re.escape()` inside `_normalize_same_repo_citations`; title/body
    # crash `_FENCE_RE.sub()` inside `_strip_fences` (found by a
    # /code-review pass on this same PR: the first version of this guard
    # covered owner/repo only) -- both an uncaught TypeError.
    payload = {"owner": "o", "repo": "r", "title": "t", "body": "Closes #1"}
    payload[field_name] = bad_value
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert checker.main([]) == 1
    err = capsys.readouterr().err
    assert f"field '{field_name}'" in err
    assert type(bad_value).__name__ in err


def test_main_allows_owner_and_repo_absent_or_null(monkeypatch, capsys):
    # Absent/None must keep falling through to the existing `or ""`
    # fallback, not the new type-check deny path -- owner/repo null with a
    # real title/body citation still passes.
    payload = json.dumps({"title": "t", "body": "Refs #1", "owner": None, "repo": None})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert checker.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_allows_all_fields_absent_or_null(monkeypatch, capsys):
    # Same fallback, all four fields null at once: falls through to the
    # normal "cites nothing" deny verdict, not a crash.
    payload = json.dumps({"owner": None, "repo": None, "title": None, "body": None})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert checker.main([]) == 1
    assert "cites no issue" in capsys.readouterr().err


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

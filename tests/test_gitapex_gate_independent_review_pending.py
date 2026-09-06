"""Tests for the independent-review-pending required status check
(.github/scripts/gitapex_gate_independent_review_pending.py).

Issue #1311 (Repair 5 of retrospective #1286): a PR must not be mergeable
between transitioning out of draft and drafting-a-pr-to-merge's own Step 8
independent-review verdict actually being recorded against the PR's
current head commit.
"""

from __future__ import annotations

import json
import pathlib
import re
import urllib.error
import urllib.request
from typing import Any

import gitapex_gate_independent_review_pending as gate
import pytest
import yaml
from conftest import FakeStdin as _FakeStdin

_SHA = "abc123def456abc123def456abc123def456abc"
_OTHER_SHA = "1111111111111111111111111111111111111111"[:40]

_CLEAN_BODY = f"""## Summary

Some PR body text.

## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}

## Checklist

- [x] Tests pass locally
"""

_NO_SECTION_BODY = "## Summary\n\nJust a normal PR body, no verdict section at all.\n"

_MISSING_VERDICT_FIELD_BODY = f"""## Independent review verdict

- Verified commit: {_SHA}
"""

_MISSING_COMMIT_FIELD_BODY = """## Independent review verdict

- Verdict: CLEAN
"""

_NOT_CLEAN_BODY = f"""## Independent review verdict

- Verdict: FINDING-PENDING
- Verified commit: {_SHA}
"""

_STALE_BODY = f"""## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_OTHER_SHA}
"""

_EMPHASIS_BODY = f"""## Independent review verdict

- Verdict: **CLEAN**
- Verified commit: `{_SHA}`
"""

_TWO_SECTIONS_BODY = f"""## Independent review verdict

- Verdict: FINDING-PENDING
- Verified commit: {_OTHER_SHA}

## Fixed and re-reviewed

## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""

_HEADING_DIFFERENT_LEVEL_BODY = f"""### Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""

_SECTION_FOLLOWED_BY_ANOTHER_HEADING_BODY = f"""## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}

## Related Issue

Closes #1311
"""


def test_parse_verdict_finds_clean_section() -> None:
    verdict = gate.parse_verdict(_CLEAN_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA
    assert verdict.error is None


def test_parse_verdict_no_section() -> None:
    verdict = gate.parse_verdict(_NO_SECTION_BODY)
    assert verdict.error == "no '## Independent review verdict' section found"


def test_parse_verdict_missing_verdict_field() -> None:
    verdict = gate.parse_verdict(_MISSING_VERDICT_FIELD_BODY)
    assert verdict.error == "verdict section found but has no 'Verdict:' line"


def test_parse_verdict_missing_commit_field() -> None:
    verdict = gate.parse_verdict(_MISSING_COMMIT_FIELD_BODY)
    assert verdict.error == "verdict section found but has no 'Verified commit:' line"


def test_parse_verdict_missing_both_fields() -> None:
    verdict = gate.parse_verdict("## Independent review verdict\n\nNothing here.\n")
    assert verdict.error == "verdict section found but has neither a 'Verdict:' nor a 'Verified commit:' line"


def test_parse_verdict_tolerates_emphasis_markup() -> None:
    verdict = gate.parse_verdict(_EMPHASIS_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_parse_verdict_uses_last_section_when_multiple_present() -> None:
    verdict = gate.parse_verdict(_TWO_SECTIONS_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_parse_verdict_does_not_leak_into_next_heading() -> None:
    # A body where the verdict section is immediately followed by another
    # heading must not accidentally read fields from that next section.
    verdict = gate.parse_verdict(_SECTION_FOLLOWED_BY_ANOTHER_HEADING_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_parse_verdict_matches_any_heading_level() -> None:
    verdict = gate.parse_verdict(_HEADING_DIFFERENT_LEVEL_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_check_passes_on_matching_clean_verdict() -> None:
    passed, message = gate.check(_CLEAN_BODY, _SHA)
    assert passed is True
    assert _SHA in message


def test_check_fails_on_no_section() -> None:
    passed, message = gate.check(_NO_SECTION_BODY, _SHA)
    assert passed is False
    assert "no '## Independent" in message


def test_check_fails_on_non_clean_verdict() -> None:
    passed, message = gate.check(_NOT_CLEAN_BODY, _SHA)
    assert passed is False
    assert "not CLEAN" in message


def test_check_fails_on_stale_commit() -> None:
    passed, message = gate.check(_STALE_BODY, _SHA)
    assert passed is False
    assert "stale verdict" in message


def test_check_fails_on_empty_head_sha() -> None:
    passed, message = gate.check(_CLEAN_BODY, "")
    assert passed is False
    assert "no --head-sha" in message


def test_check_is_case_insensitive_on_verdict_and_commit() -> None:
    body = f"""## Independent review verdict

- verdict: clean
- verified commit: {_SHA.upper()}
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is True


def test_check_matches_abbreviated_recorded_sha_against_full_head_sha() -> None:
    body = f"""## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA[:12]}
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is True


def test_main_body_file_pass(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = gate.main(["--body", str(body_file), "--head-sha", _SHA])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_body_file_fail(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text(_NO_SECTION_BODY, encoding="utf-8")
    exit_code = gate.main(["--body", str(body_file), "--head-sha", _SHA])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_missing_body_file_errors(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = gate.main(["--body", "/nonexistent/path.txt", "--head-sha", _SHA])
    assert exit_code == 1
    assert "file not found" in capsys.readouterr().err


def test_main_stdin_pass(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_CLEAN_BODY.encode("utf-8")))
    exit_code = gate.main(["--head-sha", _SHA])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_stdin_undecodable_errors(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    exit_code = gate.main(["--head-sha", _SHA])
    assert exit_code == 1
    assert "not valid UTF-8" in capsys.readouterr().err


def test_main_body_directory_errors_cleanly(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Dimension-15 boundary case (evaluating-deterministic-gate-quality):
    # a live adversarial run against a pre-fix draft of this gate raised an
    # uncaught IsADirectoryError traceback for this exact input -- still
    # fail-closed (non-zero exit) but not a deliberate, clean error path.
    exit_code = gate.main(["--body", str(tmp_path), "--head-sha", _SHA])
    assert exit_code == 1
    assert "is a directory" in capsys.readouterr().err


def test_defeat_attempt_fenced_example_verdict_does_not_pass() -> None:
    # Defeat-test-disclosure (issue #1311): a real live attempt to defeat
    # this gate's own detection logic, not merely exercise its happy path.
    # A pre-fix draft of this gate treated a verdict quoted inside a fenced
    # code block -- exactly the "diff whose review-layer text happens to
    # mimic this verdict's own phrasing" class drafting-a-pr-to-merge/
    # SKILL.md's own Step 8 text already warns about -- as a genuine
    # passing verdict, even though the surrounding prose explicitly says
    # it is illustrative only. This must fail, not pass.
    body = f"""## Summary

This PR is not actually reviewed yet. Here is an example of the format,
quoted for illustration only, NOT a real disclosure:

```
## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
```

Do not treat the above as a real verdict.
"""
    passed, message = gate.check(body, _SHA)
    assert passed is False
    assert "no '## Independent" in message


def test_defeat_attempt_tilde_fenced_example_verdict_does_not_pass() -> None:
    # Same defeat attempt, the other CommonMark fence character.
    body = f"""## Summary

~~~
## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
~~~
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is False


def test_strip_fenced_code_blocks_leaves_surrounding_prose_intact() -> None:
    text = "before\n\n```\nfenced content\nmore fenced\n```\n\nafter\n"
    stripped = gate.strip_fenced_code_blocks(text)
    assert "before" in stripped
    assert "after" in stripped
    assert "fenced content" not in stripped
    assert "more fenced" not in stripped


def test_real_verdict_outside_fence_still_passes_with_unrelated_fenced_block_present() -> None:
    # A real, live verdict elsewhere in the body must not be collateral
    # damage from fenced-block stripping.
    body = f"""```
some unrelated fenced example, nothing to do with verdicts
```

## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is True


def test_defeat_attempt_unterminated_fence_does_not_pass() -> None:
    # checker-script-adversarial-review (issue #1311): an opened but never
    # closed fence -- a plausible authoring slip, not only a deliberate
    # attack -- must not leave its own contents unstripped. CommonMark
    # treats an unclosed fence as extending to end-of-document.
    body = f"""## Summary

This is only an example of the format, shown fenced for illustration --
the fence below is never closed, whether by slip or by design.

```
## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""
    passed, message = gate.check(body, _SHA)
    assert passed is False
    assert "no '## Independent" in message


def test_defeat_attempt_html_comment_does_not_pass() -> None:
    # checker-script-adversarial-review (issue #1311): GitHub renders an
    # HTML comment as nothing at all -- a verdict hidden inside one is
    # invisible to a human reviewer skimming the rendered PR body, arguably
    # worse than the fenced-block case since there is no visible "example"
    # text to question at all. Must not parse as a real verdict.
    body = f"""## Summary

The actual Step 8 review has NOT run yet. Nothing below should count.

<!--
## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
-->
"""
    passed, message = gate.check(body, _SHA)
    assert passed is False
    assert "no '## Independent" in message


def test_defeat_attempt_unclosed_html_comment_does_not_pass() -> None:
    body = f"""<!--
## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is False


def test_defeat_attempt_four_space_indented_heading_does_not_pass() -> None:
    # checker-script-adversarial-review (issue #1311): CommonMark treats a
    # 4-or-more-space-indented line as an indented code block, never a live
    # heading. An earlier draft's unlimited-indentation heading regex let
    # this parse as a genuine verdict.
    body = f"""## Summary

Here is the expected format, shown indented as a code sample:

    ## Independent review verdict

    - Verdict: CLEAN
    - Verified commit: {_SHA}

The actual Step 8 review has NOT run yet.
"""
    passed, message = gate.check(body, _SHA)
    assert passed is False
    assert "no '## Independent" in message


def test_three_space_indented_heading_still_passes() -> None:
    # The CommonMark ATX-heading indentation limit is 0-3 spaces, not 0 --
    # a real verdict indented up to 3 spaces (e.g. a reply-quoted PR
    # comment) must still be recognized.
    body = f"""   ## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is True


def test_crlf_line_endings_still_pass() -> None:
    # A live-confirmed correctness gap (safe direction, but still wrong):
    # every regex here is line-anchored, and an unstripped stray '\r'
    # before each '\n' broke every one of them against an otherwise
    # perfectly genuine, completed verdict.
    body = f"## Independent review verdict\r\n\r\n- Verdict: CLEAN\r\n- Verified commit: {_SHA}\r\n"
    passed, message = gate.check(body, _SHA)
    assert passed is True, message


def test_single_character_head_sha_never_vacuously_matches() -> None:
    # checker-script-adversarial-review (issue #1311): defense-in-depth --
    # not reachable through the real wired trigger (GitHub Actions always
    # supplies the full 40-character SHA), but nothing previously stopped
    # a single-character --head-sha from vacuously matching any recorded
    # commit sharing that one leading character.
    body = f"""## Independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""
    passed, message = gate.check(body, _SHA[0])
    assert passed is False
    assert "stale verdict" in message


def test_main_body_permission_error_reported_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # deterministic-gate-quality review (issue #1311): the specific
    # IsADirectoryError catch does not generalize to the rest of the
    # OSError family (PermissionError, a disk-full or restrictive-ACL
    # mount) -- confirmed via monkeypatch rather than a real chmod-0 file,
    # which is unreliable under a root-run CI container.
    def _raise_permission_error(*_args: object, **_kwargs: object) -> str:
        raise PermissionError("permission denied")

    monkeypatch.setattr(gate.Path, "read_text", _raise_permission_error)
    exit_code = gate.main(["--body", "/some/path", "--head-sha", _SHA])
    assert exit_code == 1
    assert "could not read --body" in capsys.readouterr().err


_MALFORMED_HEADING_CASES = [
    # issue #1343: each is a heading line superficially close to the real
    # '## Independent review verdict' heading that must never pass -- one
    # per specific relaxation of `_HEADING_RE` a live adversarial/
    # deterministic-gate-quality review round confirmed by mutation would
    # otherwise leave the pre-existing 43-test suite green (i.e. nothing
    # else pinned it).
    "## Step 8 independent review verdict",  # retired pre-#1343 heading -- rename does not dual-accept it
    "## Independent review verdict (illustrative example)",  # trailing prose -- exercises the `$` end anchor
    "## Independent review verdict notes",  # same end-anchor class, a trailing word
    "## Independent review verdicts",  # same end-anchor class, a one-character suffix
    "## Independent review verdict -- pending",  # same end-anchor class, an em-dash-led suffix
    "##Independent review verdict",  # no space after the hashes -- CommonMark requires one
    "####### Independent review verdict",  # seven hashes -- CommonMark caps ATX headings at six
    "\t## Independent review verdict",  # tab indentation -- CommonMark counts only spaces, not tabs
]


@pytest.mark.parametrize("heading_line", _MALFORMED_HEADING_CASES)
def test_malformed_heading_variant_does_not_pass(heading_line: str) -> None:
    body = f"""{heading_line}

- Verdict: CLEAN
- Verified commit: {_SHA}
"""
    passed, message = gate.check(body, _SHA)
    assert passed is False, f"heading line {heading_line!r} must not parse as the verdict section"
    assert "no '## Independent review verdict' section found" in message


# ---------------------------------------------------------------------------
# Trusted-bot exemption (issue #1858, design:
# docs/gitapex/specs/2026-09-06-dependabot-trusted-bot-gate-exemption-design.md).
# Everything above this point is the pre-existing 42-test suite, run
# completely unmodified (regression guard) -- see the top-of-file assertion
# in this PR's own commit message. Everything below is new.
# ---------------------------------------------------------------------------

_DEPENDABOT_LOGIN = "dependabot[bot]"
_DEPENDABOT_ID = 49699333
_DEPENDABOT_TYPE = "Bot"
_DEPENDABOT_EMAIL = "49699333+dependabot[bot]@users.noreply.github.com"

_TRUSTED_BOTS: list[dict[str, Any]] = [
    {"login": _DEPENDABOT_LOGIN, "id": _DEPENDABOT_ID, "type": _DEPENDABOT_TYPE, "purpose": "test fixture"},
]

# A main.json-shaped fixture carrying every rule type the real file does
# (deletion/non_fast_forward/pull_request/required_status_checks/
# commit_author_email_pattern/committer_email_pattern) -- the ACM's own
# "must not misread deletion/pull_request/... as check contexts" test needs
# every other type actually present to be a real test of that, not merely
# absent-by-omission.
_RULESET_WITH_ALL_RULE_TYPES: dict[str, Any] = {
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": "pytest"},
                    {"context": "ruff"},
                    {"context": "independent-review-pending"},
                ]
            },
        },
        {
            "type": "commit_author_email_pattern",
            "parameters": {"operator": "regex", "pattern": rf"^{re.escape(_DEPENDABOT_EMAIL)}$"},
        },
        {
            "type": "committer_email_pattern",
            "parameters": {"operator": "regex", "pattern": rf"^{re.escape(_DEPENDABOT_EMAIL)}$"},
        },
    ]
}


def _without_rule_type(ruleset: dict[str, Any], rule_type: str) -> dict[str, Any]:
    return {"rules": [rule for rule in ruleset["rules"] if rule["type"] != rule_type]}


class _FakeResponse:
    """Mirrors test_gitapex_github_http.py's own `Response` fixture class --
    just the surface `_gitapex_github_http.request_with_retry` uses."""

    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self._body = body.encode()

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        return None


class _FakeClock:
    """A deterministic, injectable stand-in for `time.monotonic` --
    advances by `step` on every call, so a timeout test can force the
    poll loop's own deadline to elapse without a real sleep."""

    def __init__(self, start: float = 0.0, step: float = 1000.0) -> None:
        self._now = start
        self._step = step

    def __call__(self) -> float:
        value = self._now
        self._now += self._step
        return value


def _check_runs_body(entries: list[dict[str, Any]]) -> str:
    return json.dumps({"total_count": len(entries), "check_runs": entries})


def _commit_body(author_email: str, committer_email: str) -> str:
    return json.dumps({"commit": {"author": {"email": author_email}, "committer": {"email": committer_email}}})


# ---------------------------------------------------------------------------
# is_trusted_bot: positive/negative matches (ACM's own literal wording).
# ---------------------------------------------------------------------------


def test_is_trusted_bot_positive_match_all_three_fields_agree() -> None:
    assert gate.is_trusted_bot(_DEPENDABOT_LOGIN, _DEPENDABOT_ID, _DEPENDABOT_TYPE, _TRUSTED_BOTS) is True


@pytest.mark.parametrize(
    ("login", "user_id", "user_type"),
    [
        pytest.param("someone-else[bot]", _DEPENDABOT_ID, _DEPENDABOT_TYPE, id="login-disagrees"),
        pytest.param(_DEPENDABOT_LOGIN, 1, _DEPENDABOT_TYPE, id="id-disagrees"),
        pytest.param(_DEPENDABOT_LOGIN, _DEPENDABOT_ID, "User", id="type-disagrees"),
    ],
)
def test_is_trusted_bot_negative_match_when_one_field_disagrees(login: str, user_id: int, user_type: str) -> None:
    # Defeat test (design doc's own Testing section + this issue's ACM): a
    # forged/different login, id, or type must never be treated as a match
    # even though the other two fields agree.
    assert gate.is_trusted_bot(login, user_id, user_type, _TRUSTED_BOTS) is False


def test_is_trusted_bot_false_on_empty_allowlist() -> None:
    assert gate.is_trusted_bot(_DEPENDABOT_LOGIN, _DEPENDABOT_ID, _DEPENDABOT_TYPE, []) is False


# ---------------------------------------------------------------------------
# _read_utf8_or_raise: the shared read-boundary helper load_trusted_bots/
# load_ruleset both sit on top of.
# ---------------------------------------------------------------------------


def test_read_utf8_or_raise_returns_file_contents(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "some.txt"
    path.write_text("hello", encoding="utf-8")
    assert gate._read_utf8_or_raise(path) == "hello"


def test_read_utf8_or_raise_converts_missing_file_to_value_error(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="could not be read"):
        gate._read_utf8_or_raise(tmp_path / "nonexistent.txt")


def test_read_utf8_or_raise_converts_undecodable_file_to_value_error(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\xff\xfe bad")
    with pytest.raises(ValueError, match="not valid UTF-8"):
        gate._read_utf8_or_raise(path)


# ---------------------------------------------------------------------------
# load_trusted_bots / load_ruleset
# ---------------------------------------------------------------------------


def test_load_trusted_bots_parses_real_shaped_yaml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "trusted-bots.yml"
    path.write_text(yaml.safe_dump(_TRUSTED_BOTS), encoding="utf-8")
    assert gate.load_trusted_bots(path) == _TRUSTED_BOTS


def test_load_trusted_bots_rejects_non_list_yaml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "trusted-bots.yml"
    path.write_text("not-a-list: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a YAML list"):
        gate.load_trusted_bots(path)


def test_load_ruleset_rejects_non_object_json(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "main.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        gate.load_ruleset(path)


# ---------------------------------------------------------------------------
# required_check_contexts: must read only required_status_checks, never the
# other rule types (the PR #1843 concern this design explicitly guards
# against), and must exclude this check's own name.
# ---------------------------------------------------------------------------


def test_required_check_contexts_excludes_self_and_other_rule_types() -> None:
    contexts = gate.required_check_contexts(_RULESET_WITH_ALL_RULE_TYPES)
    assert contexts == ["pytest", "ruff"]
    for other_type in (
        "deletion",
        "non_fast_forward",
        "pull_request",
        "commit_author_email_pattern",
        "committer_email_pattern",
        "independent-review-pending",
    ):
        assert other_type not in contexts


def test_required_check_contexts_empty_when_rule_absent_entirely() -> None:
    # Defeat test (design doc's own Testing section): required_status_checks
    # missing entirely must not be misread as "zero checks required" by
    # accident -- this function's own contract is that its caller
    # (poll_bot_required_checks) treats an empty result as fail-closed,
    # never as a vacuous pass, checked below.
    ruleset = _without_rule_type(_RULESET_WITH_ALL_RULE_TYPES, "required_status_checks")
    assert gate.required_check_contexts(ruleset) == []


def test_rule_of_type_finds_the_matching_rule_by_type() -> None:
    rule = gate._rule_of_type(_RULESET_WITH_ALL_RULE_TYPES, "required_status_checks")
    assert rule is not None
    assert rule["type"] == "required_status_checks"


def test_rule_of_type_returns_none_when_no_rule_of_that_type_exists() -> None:
    assert gate._rule_of_type({"rules": []}, "required_status_checks") is None


# ---------------------------------------------------------------------------
# head_commit_identity_matches_bot: the critical-defect fix itself.
# ---------------------------------------------------------------------------


def test_head_commit_identity_matches_bot_when_both_emails_match() -> None:
    ok, _message = gate.head_commit_identity_matches_bot(
        _DEPENDABOT_EMAIL, _DEPENDABOT_EMAIL, _RULESET_WITH_ALL_RULE_TYPES
    )
    assert ok is True


@pytest.mark.parametrize(
    ("author_email", "committer_email", "expected_substring"),
    [
        pytest.param("someone@example.com", _DEPENDABOT_EMAIL, "author email", id="author-mismatch"),
        pytest.param(_DEPENDABOT_EMAIL, "someone@example.com", "committer email", id="committer-mismatch"),
    ],
)
def test_head_commit_identity_matches_bot_fails_on_email_mismatch(
    author_email: str, committer_email: str, expected_substring: str
) -> None:
    ok, message = gate.head_commit_identity_matches_bot(author_email, committer_email, _RULESET_WITH_ALL_RULE_TYPES)
    assert ok is False
    assert expected_substring in message


def test_head_commit_identity_matches_bot_fails_when_email_pattern_rules_absent() -> None:
    ruleset = _without_rule_type(
        _without_rule_type(_RULESET_WITH_ALL_RULE_TYPES, "commit_author_email_pattern"), "committer_email_pattern"
    )
    ok, message = gate.head_commit_identity_matches_bot(_DEPENDABOT_EMAIL, _DEPENDABOT_EMAIL, ruleset)
    assert ok is False
    assert "missing" in message


def test_email_matches_pattern_supports_every_operator() -> None:
    assert gate._email_matches_pattern("foo@bar.com", "starts_with", "foo@") is True
    assert gate._email_matches_pattern("foo@bar.com", "ends_with", "bar.com") is True
    assert gate._email_matches_pattern("foo@bar.com", "contains", "@bar") is True
    assert gate._email_matches_pattern("foo@bar.com", "regex", r"^foo@") is True
    assert gate._email_matches_pattern("foo@bar.com", "unknown-operator", "foo") is False


def test_email_satisfies_rule_honors_negate() -> None:
    allow_rule = {"parameters": {"operator": "contains", "pattern": "bar", "negate": False}}
    deny_rule = {"parameters": {"operator": "contains", "pattern": "bar", "negate": True}}
    assert gate._email_satisfies_rule("foo@bar.com", allow_rule) is True
    assert gate._email_satisfies_rule("foo@bar.com", deny_rule) is False
    assert gate._email_satisfies_rule("foo@baz.com", deny_rule) is True


# ---------------------------------------------------------------------------
# fetch_head_commit_emails
# ---------------------------------------------------------------------------


def test_fetch_head_commit_emails_reads_commit_author_committer() -> None:
    def opener(_request: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(200, _commit_body("a@example.com", "c@example.com"))

    author, committer = gate.fetch_head_commit_emails("o", "r", "sha", "tok", opener=opener, sleeper=lambda _s: None)
    assert (author, committer) == ("a@example.com", "c@example.com")


def test_fetch_head_commit_emails_raises_on_missing_commit_object() -> None:
    def opener(_request: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(200, json.dumps({}))

    with pytest.raises(gate.GitHubApiError, match="no 'commit' object"):
        gate.fetch_head_commit_emails("o", "r", "sha", "tok", opener=opener, sleeper=lambda _s: None)


# ---------------------------------------------------------------------------
# _fetch_check_runs / _latest_run_for_context
# ---------------------------------------------------------------------------


def test_fetch_check_runs_pages_through_multiple_pages() -> None:
    page1 = json.dumps(
        {"total_count": 2, "check_runs": [{"name": "pytest", "status": "completed", "conclusion": "success", "id": 1}]}
    )
    page2 = json.dumps(
        {"total_count": 2, "check_runs": [{"name": "ruff", "status": "completed", "conclusion": "success", "id": 2}]}
    )
    calls = {"n": 0}

    def opener(_request: urllib.request.Request) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(200, page1 if calls["n"] == 1 else page2)

    runs = gate._fetch_check_runs("o", "r", "sha", "tok", opener, lambda _s: None)
    assert [run["name"] for run in runs] == ["pytest", "ruff"]
    assert calls["n"] == 2


def test_fetch_check_runs_raises_on_missing_check_runs_array() -> None:
    def opener(_request: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(200, json.dumps({"total_count": 0}))

    with pytest.raises(gate.GitHubApiError, match="no 'check_runs' array"):
        gate._fetch_check_runs("o", "r", "sha", "tok", opener, lambda _s: None)


def test_latest_run_for_context_picks_most_recent_by_started_at() -> None:
    runs = [
        {
            "name": "pytest",
            "status": "completed",
            "conclusion": "failure",
            "id": 1,
            "started_at": "2026-01-01T00:00:00Z",
        },
        {
            "name": "pytest",
            "status": "completed",
            "conclusion": "success",
            "id": 2,
            "started_at": "2026-01-01T01:00:00Z",
        },
    ]
    latest = gate._latest_run_for_context(runs, "pytest")
    assert latest is not None
    assert latest["id"] == 2


def test_latest_run_for_context_returns_none_when_no_run_matches() -> None:
    assert gate._latest_run_for_context([], "pytest") is None


# ---------------------------------------------------------------------------
# poll_bot_required_checks: simulated-bot-PR tests (ACM's own literal
# wording) plus the fail-closed-on-empty-contexts defeat test.
# ---------------------------------------------------------------------------


def test_poll_bot_required_checks_passes_when_all_contexts_complete_successfully() -> None:
    body = _check_runs_body(
        [
            {"name": "pytest", "status": "completed", "conclusion": "success", "id": 1, "started_at": "t"},
            {"name": "ruff", "status": "completed", "conclusion": "neutral", "id": 2, "started_at": "t"},
            {"name": "mypy", "status": "completed", "conclusion": "skipped", "id": 3, "started_at": "t"},
        ]
    )

    def opener(_request: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(200, body)

    passed, message = gate.poll_bot_required_checks(
        owner="o",
        repo="r",
        head_sha="sha",
        contexts=["pytest", "ruff", "mypy"],
        token="tok",
        opener=opener,
        sleeper=lambda _s: None,
    )
    assert passed is True
    assert "sha" in message


def test_poll_bot_required_checks_fails_immediately_on_a_failing_check() -> None:
    body = _check_runs_body(
        [
            {"name": "pytest", "status": "completed", "conclusion": "success", "id": 1, "started_at": "t"},
            {"name": "ruff", "status": "completed", "conclusion": "failure", "id": 2, "started_at": "t"},
        ]
    )

    def opener(_request: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(200, body)

    passed, message = gate.poll_bot_required_checks(
        owner="o",
        repo="r",
        head_sha="sha",
        contexts=["pytest", "ruff"],
        token="tok",
        opener=opener,
        sleeper=lambda _s: None,
    )
    assert passed is False
    assert "ruff" in message
    assert "failure" in message


def test_poll_bot_required_checks_times_out_naming_only_the_pending_contexts() -> None:
    body = _check_runs_body(
        [
            {"name": "pytest", "status": "completed", "conclusion": "success", "id": 1, "started_at": "t"},
            {"name": "slow-check", "status": "in_progress", "id": 2, "started_at": "t"},
        ]
    )

    def opener(_request: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(200, body)

    passed, message = gate.poll_bot_required_checks(
        owner="o",
        repo="r",
        head_sha="sha",
        contexts=["pytest", "slow-check"],
        token="tok",
        timeout_seconds=1.0,
        opener=opener,
        sleeper=lambda _s: None,
        clock=_FakeClock(step=1000.0),
    )
    assert passed is False
    assert "timed out" in message
    assert "slow-check" in message
    assert "pytest" not in message


def test_poll_bot_required_checks_fails_closed_on_empty_contexts() -> None:
    # Defeat test (design doc's own Testing section + this issue's ACM):
    # required_status_checks absent entirely -- or present but naming
    # nothing besides independent-review-pending itself -- must never be
    # silently read as "nothing to check". No opener/network call is even
    # reached: this is checked before anything else.
    passed, message = gate.poll_bot_required_checks(owner="o", repo="r", head_sha="sha", contexts=[], token="tok")
    assert passed is False
    assert "nothing to check" in message


def test_bot_path_fails_closed_end_to_end_when_required_status_checks_rule_is_absent() -> None:
    # Same defeat test, chained through required_check_contexts exactly the
    # way evaluate_bot_path itself calls it, proving the fail-closed
    # behavior holds for the real "main.json fixture missing the rule"
    # shape, not only for a hand-constructed empty list.
    ruleset = _without_rule_type(_RULESET_WITH_ALL_RULE_TYPES, "required_status_checks")
    contexts = gate.required_check_contexts(ruleset)
    passed, message = gate.poll_bot_required_checks(owner="o", repo="r", head_sha="sha", contexts=contexts, token="tok")
    assert passed is False
    assert "nothing to check" in message


def test_poll_bot_required_checks_retries_transient_api_errors_within_budget() -> None:
    # Defeat test (design doc's own "Poll outcome" bullet + this issue's
    # ACM): a transient GitHub API error (5xx) while polling must be
    # retried within the same timeout budget, not treated as an immediate
    # FAIL nor silently ignored. request_with_retry's own inner loop
    # already retries 3 times per _fetch_check_runs call -- this drives it
    # to exhaust all 3 (round 1), then succeeds on poll_bot_required_checks'
    # own next outer-loop round.
    calls = {"n": 0}
    success_body = _check_runs_body(
        [{"name": "pytest", "status": "completed", "conclusion": "success", "id": 1, "started_at": "t"}]
    )

    def opener(request: urllib.request.Request) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] <= 3:
            raise urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, _FakeResponse(503, "retry me"))  # type: ignore[arg-type]
        return _FakeResponse(200, success_body)

    passed, message = gate.poll_bot_required_checks(
        owner="o",
        repo="r",
        head_sha="sha",
        contexts=["pytest"],
        token="tok",
        timeout_seconds=5.0,
        poll_interval_seconds=0,
        opener=opener,
        sleeper=lambda _s: None,
    )
    assert passed is True, message
    assert calls["n"] == 4


def test_poll_bot_required_checks_times_out_when_errors_persist() -> None:
    def opener(request: urllib.request.Request) -> _FakeResponse:
        raise urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, _FakeResponse(503, "still down"))  # type: ignore[arg-type]

    passed, message = gate.poll_bot_required_checks(
        owner="o",
        repo="r",
        head_sha="sha",
        contexts=["pytest"],
        token="tok",
        timeout_seconds=1.0,
        opener=opener,
        sleeper=lambda _s: None,
        clock=_FakeClock(step=1000.0),
    )
    assert passed is False
    assert "timed out" in message
    assert "GitHub API errors persisted" in message
    assert "pytest" in message


# ---------------------------------------------------------------------------
# evaluate_bot_path: the orchestration function main() calls.
# ---------------------------------------------------------------------------


def test_evaluate_bot_path_returns_none_when_no_author_identity_given() -> None:
    assert (
        gate.evaluate_bot_path(
            pr_author_login=None,
            pr_author_id=None,
            pr_author_type=None,
            owner="o",
            repo="r",
            head_sha="sha",
            trusted_bots=_TRUSTED_BOTS,
            ruleset={},
            token="tok",
        )
        is None
    )


def test_evaluate_bot_path_returns_none_when_identity_does_not_match() -> None:
    assert (
        gate.evaluate_bot_path(
            pr_author_login="mallory",
            pr_author_id=1,
            pr_author_type="User",
            owner="o",
            repo="r",
            head_sha="sha",
            trusted_bots=_TRUSTED_BOTS,
            ruleset={},
            token="tok",
        )
        is None
    )


def test_evaluate_bot_path_returns_none_when_owner_repo_unresolved() -> None:
    assert (
        gate.evaluate_bot_path(
            pr_author_login=_DEPENDABOT_LOGIN,
            pr_author_id=_DEPENDABOT_ID,
            pr_author_type=_DEPENDABOT_TYPE,
            owner=None,
            repo=None,
            head_sha="sha",
            trusted_bots=_TRUSTED_BOTS,
            ruleset=_RULESET_WITH_ALL_RULE_TYPES,
            token="tok",
        )
        is None
    )


def test_evaluate_bot_path_falls_through_on_head_commit_email_mismatch() -> None:
    # The critical-defect fix itself (design doc's own Revision section): a
    # bot-identity match on the PR opener alone must never be enough. Emails
    # are given directly here (no fetch), isolating this from network
    # concerns entirely.
    result = gate.evaluate_bot_path(
        pr_author_login=_DEPENDABOT_LOGIN,
        pr_author_id=_DEPENDABOT_ID,
        pr_author_type=_DEPENDABOT_TYPE,
        owner="tvna",
        repo="gitapex",
        head_sha=_SHA,
        trusted_bots=_TRUSTED_BOTS,
        ruleset=_RULESET_WITH_ALL_RULE_TYPES,
        token="tok",
        head_commit_author_email="someone-else@example.com",
        head_commit_committer_email=_DEPENDABOT_EMAIL,
    )
    assert result is None


def test_evaluate_bot_path_falls_through_when_head_commit_email_fetch_raises_api_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Coverage gap flagged by Codecov (issue #1858): the `except
    # GitHubApiError: ... return None` branch inside evaluate_bot_path
    # (guarding the fetch_head_commit_emails call) was confirmed correct
    # only by code reading, never exercised at runtime. The design doc's
    # own Revision section requires falling through to the strict,
    # pre-existing human-verdict path when the head commit's own identity
    # cannot even be fetched -- never a silent bot-path PASS, and never a
    # hard FAIL that would block every PR (bot or not) over a transient
    # GitHub API failure (see this exact except clause's own
    # except-fail-open WAIVED comment). No --head-commit-author-email/
    # --head-commit-committer-email override is given, forcing the fetch;
    # the injected opener makes fetch_head_commit_emails's own
    # fetch_json_document call raise GitHubApiError (a non-5xx status,
    # e.g. commit-not-found, so request_with_retry's own retry loop
    # returns after exactly one attempt rather than retrying).
    def _raising_opener(request: urllib.request.Request) -> _FakeResponse:
        raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, _FakeResponse(404, "commit not found"))  # type: ignore[arg-type]

    result = gate.evaluate_bot_path(
        pr_author_login=_DEPENDABOT_LOGIN,
        pr_author_id=_DEPENDABOT_ID,
        pr_author_type=_DEPENDABOT_TYPE,
        owner="tvna",
        repo="gitapex",
        head_sha=_SHA,
        trusted_bots=_TRUSTED_BOTS,
        ruleset=_RULESET_WITH_ALL_RULE_TYPES,
        token="tok",
        opener=_raising_opener,
        sleeper=lambda _s: None,
    )

    assert result is None
    err = capsys.readouterr().err
    assert _DEPENDABOT_LOGIN in err
    assert "head" in err and "could not be fetched" in err
    assert "falling back to the human-verdict path" in err


def test_evaluate_bot_path_full_flow_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    # required_check_contexts(_RULESET_WITH_ALL_RULE_TYPES) yields
    # ["pytest", "ruff"] (independent-review-pending excluded) -- both
    # need a completed/success check run for this end-to-end PASS.
    commit_body = _commit_body(_DEPENDABOT_EMAIL, _DEPENDABOT_EMAIL)
    checks_body = _check_runs_body(
        [
            {"name": "pytest", "status": "completed", "conclusion": "success", "id": 1, "started_at": "t"},
            {"name": "ruff", "status": "completed", "conclusion": "success", "id": 2, "started_at": "t"},
        ]
    )

    def opener(request: urllib.request.Request) -> _FakeResponse:
        if "check-runs" in request.full_url:
            return _FakeResponse(200, checks_body)
        return _FakeResponse(200, commit_body)

    result = gate.evaluate_bot_path(
        pr_author_login=_DEPENDABOT_LOGIN,
        pr_author_id=_DEPENDABOT_ID,
        pr_author_type=_DEPENDABOT_TYPE,
        owner="tvna",
        repo="gitapex",
        head_sha="sha",
        trusted_bots=_TRUSTED_BOTS,
        ruleset=_RULESET_WITH_ALL_RULE_TYPES,
        token="tok",
        opener=opener,
        sleeper=lambda _s: None,
    )
    assert result == (True, "all 2 required check(s) completed successfully for head sha")


def test_evaluate_bot_path_falls_through_when_token_missing_and_no_email_override() -> None:
    result = gate.evaluate_bot_path(
        pr_author_login=_DEPENDABOT_LOGIN,
        pr_author_id=_DEPENDABOT_ID,
        pr_author_type=_DEPENDABOT_TYPE,
        owner="tvna",
        repo="gitapex",
        head_sha=_SHA,
        trusted_bots=_TRUSTED_BOTS,
        ruleset=_RULESET_WITH_ALL_RULE_TYPES,
        token="",
    )
    assert result is None


# ---------------------------------------------------------------------------
# _github_repository_part
# ---------------------------------------------------------------------------


def test_github_repository_part_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "tvna/gitapex")
    assert gate._github_repository_part(0) == "tvna"
    assert gate._github_repository_part(1) == "gitapex"


def test_github_repository_part_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert gate._github_repository_part(0) is None


# ---------------------------------------------------------------------------
# main(): CLI wiring for the bot path, and the fall-through/regression
# contract with the pre-existing --body/--head-sha-only behavior.
# ---------------------------------------------------------------------------


def test_main_without_pr_author_args_never_calls_evaluate_bot_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    called: list[object] = []

    def _must_not_be_called(**_kwargs: object) -> tuple[bool, str]:
        called.append(1)
        return True, "should never run"

    monkeypatch.setattr(gate, "evaluate_bot_path", _must_not_be_called)
    body_file = tmp_path / "body.txt"
    body_file.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = gate.main(["--body", str(body_file), "--head-sha", _SHA])
    assert exit_code == 0
    assert called == []
    assert "PASS: CLEAN verdict" in capsys.readouterr().out


def test_main_falls_back_to_human_verdict_when_bot_path_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "evaluate_bot_path", lambda **_kwargs: None)
    body_file = tmp_path / "body.txt"
    body_file.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = gate.main(
        [
            "--body",
            str(body_file),
            "--head-sha",
            _SHA,
            "--pr-author-login",
            _DEPENDABOT_LOGIN,
            "--pr-author-id",
            str(_DEPENDABOT_ID),
            "--pr-author-type",
            _DEPENDABOT_TYPE,
        ]
    )
    assert exit_code == 0
    assert "PASS: CLEAN verdict" in capsys.readouterr().out


def test_main_bot_path_pass_via_full_wiring(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    trusted_bots_path = tmp_path / "trusted-bots.yml"
    trusted_bots_path.write_text(yaml.safe_dump(_TRUSTED_BOTS), encoding="utf-8")
    ruleset_path = tmp_path / "main.json"
    ruleset_path.write_text(json.dumps(_RULESET_WITH_ALL_RULE_TYPES), encoding="utf-8")
    body_file = tmp_path / "body.txt"
    body_file.write_text("irrelevant for the bot path", encoding="utf-8")

    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPOSITORY", "tvna/gitapex")

    captured: dict[str, object] = {}

    def fake_evaluate_bot_path(**kwargs: object) -> tuple[bool, str]:
        captured.update(kwargs)
        return True, "all good"

    monkeypatch.setattr(gate, "evaluate_bot_path", fake_evaluate_bot_path)

    exit_code = gate.main(
        [
            "--body",
            str(body_file),
            "--head-sha",
            _SHA,
            "--pr-author-login",
            _DEPENDABOT_LOGIN,
            "--pr-author-id",
            str(_DEPENDABOT_ID),
            "--pr-author-type",
            _DEPENDABOT_TYPE,
            "--trusted-bots-path",
            str(trusted_bots_path),
            "--ruleset-path",
            str(ruleset_path),
        ]
    )
    assert exit_code == 0
    assert "PASS: all good" in capsys.readouterr().out
    assert captured["pr_author_login"] == _DEPENDABOT_LOGIN
    assert captured["pr_author_id"] == _DEPENDABOT_ID
    assert captured["pr_author_type"] == _DEPENDABOT_TYPE
    assert captured["owner"] == "tvna"
    assert captured["repo"] == "gitapex"
    assert captured["token"] == "tok"
    assert captured["trusted_bots"] == _TRUSTED_BOTS
    assert captured["ruleset"] == _RULESET_WITH_ALL_RULE_TYPES


def test_main_bot_path_fail_prints_bot_specific_hint_not_the_verdict_hint(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "evaluate_bot_path", lambda **_kwargs: (False, "required check 'ruff' failed"))
    body_file = tmp_path / "body.txt"
    body_file.write_text("irrelevant for the bot path", encoding="utf-8")

    exit_code = gate.main(
        [
            "--body",
            str(body_file),
            "--head-sha",
            _SHA,
            "--pr-author-login",
            _DEPENDABOT_LOGIN,
            "--pr-author-id",
            str(_DEPENDABOT_ID),
            "--pr-author-type",
            _DEPENDABOT_TYPE,
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL: required check 'ruff' failed" in err
    assert "trusted-bot merge-gate path" in err
    assert "Record a '##" not in err


def test_main_bot_path_falls_back_when_trusted_bots_file_missing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = gate.main(
        [
            "--body",
            str(body_file),
            "--head-sha",
            _SHA,
            "--pr-author-login",
            _DEPENDABOT_LOGIN,
            "--pr-author-id",
            str(_DEPENDABOT_ID),
            "--pr-author-type",
            _DEPENDABOT_TYPE,
            "--trusted-bots-path",
            str(tmp_path / "nonexistent.yml"),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "could not load the bot-path allowlist/ruleset" in captured.err
    assert "PASS: CLEAN verdict" in captured.out


def test_main_never_calls_evaluate_bot_path_when_ruleset_load_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression guard for the except-fail-open fix: a load failure must
    # skip evaluate_bot_path entirely (never call it with a falsy
    # placeholder ruleset/trusted_bots and continue), not merely default
    # its arguments and proceed.
    called: list[object] = []

    def _must_not_be_called(**_kwargs: object) -> tuple[bool, str]:
        called.append(1)
        return True, "should never run"

    monkeypatch.setattr(gate, "evaluate_bot_path", _must_not_be_called)
    trusted_bots_path = tmp_path / "trusted-bots.yml"
    trusted_bots_path.write_text(yaml.safe_dump(_TRUSTED_BOTS), encoding="utf-8")
    body_file = tmp_path / "body.txt"
    body_file.write_text(_CLEAN_BODY, encoding="utf-8")

    exit_code = gate.main(
        [
            "--body",
            str(body_file),
            "--head-sha",
            _SHA,
            "--pr-author-login",
            _DEPENDABOT_LOGIN,
            "--pr-author-id",
            str(_DEPENDABOT_ID),
            "--pr-author-type",
            _DEPENDABOT_TYPE,
            "--trusted-bots-path",
            str(trusted_bots_path),
            "--ruleset-path",
            str(tmp_path / "nonexistent-main.json"),
        ]
    )
    assert exit_code == 0
    assert called == []
    captured = capsys.readouterr()
    assert "could not load the bot-path allowlist/ruleset" in captured.err
    assert "PASS: CLEAN verdict" in captured.out

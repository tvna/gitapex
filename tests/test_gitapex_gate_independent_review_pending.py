"""Tests for the independent-review-pending required status check
(.github/scripts/gitapex_gate_independent_review_pending.py).

Issue #1311 (Repair 5 of retrospective #1286): a PR must not be mergeable
between transitioning out of draft and drafting-a-pr-to-merge's own Step 8
independent-review verdict actually being recorded against the PR's
current head commit.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_independent_review_pending as gate
import pytest
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
    stripped = gate._strip_fenced_code_blocks(text)
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

"""Read-path tests for hooks/gitapex_check_skill_audit_disclosure_or_waiver.py's
main().

tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py already covers this
module's regex/verdict parity with the CI gate it partially mirrors; it
does not exercise main()'s own --body/stdin read path. This file pins
that path's documented non-UTF-8 behavior only -- kept separate to keep
the sync test focused on parity, matching this repo's convention of one
concern per test module.
"""

from __future__ import annotations

import pathlib

import gitapex_check_skill_audit_disclosure_or_waiver as checker
import pytest
from conftest import FakeStdin as _FakeStdin


def test_main_reports_error_for_non_utf8_body_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "body.md"
    path.write_bytes(b"\xff\xfe bad")
    assert checker.main(["--body", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(checker.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert checker.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


# --- Issue #1571 (refs #1888, #1784): _line_pattern's punctuation-adjacency
# widening, ported here since this module keeps its own copy of
# _line_pattern in sync with the CI gate's (see
# tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py). Uses
# battle-testing-a-skill/evaluating-skill-quality, the only two checks this
# module's own find_missing_disclosures grades -- checker-script-
# adversarial-review does not exist in this standalone copy.


def test_verdict_followed_by_trailing_period_is_accepted() -> None:
    """Issue #1888's own reported shape: a verdict token directly followed
    by a sentence-ending period and nothing else."""
    body = "## Skill audit evidence\n\n- battle-testing-a-skill: PASS.\n- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
    assert checker.find_missing_disclosures(body) == []


def test_verdict_wrapped_in_one_shared_code_span_is_accepted() -> None:
    """Issue #1784's own reported shape: the whole 'name: VERDICT' text
    sharing one Markdown code span, so the closing backtick lands directly
    after the verdict token."""
    body = (
        "## Skill audit evidence\n\n"
        "`battle-testing-a-skill: PASS`\n"
        "- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
    )
    assert checker.find_missing_disclosures(body) == []


def test_verdict_word_extended_by_more_letters_still_rejected() -> None:
    """Defeat test: a longer word merely starting with a valid verdict
    token, with no punctuation and no word boundary, must still be
    rejected -- the \\b requirement itself must not have been weakened by
    the punctuation escape."""
    body = "## Skill audit evidence\n\n- battle-testing-a-skill: PASSED\n- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
    assert checker.find_missing_disclosures(body) == ["battle-testing-a-skill"]


@pytest.mark.parametrize("trailing", ["..", ".,"])
def test_verdict_followed_by_two_punctuation_characters_still_rejected(trailing: str) -> None:
    """The punctuation escape accepts exactly one trailing character, not a
    run of them."""
    body = (
        "## Skill audit evidence\n\n"
        f"- battle-testing-a-skill: PASS{trailing}\n"
        "- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
    )
    assert checker.find_missing_disclosures(body) == ["battle-testing-a-skill"]

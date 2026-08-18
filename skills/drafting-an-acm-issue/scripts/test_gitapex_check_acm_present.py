"""Regression suite for gitapex_check_acm_present.py's own has_acm_table()/
has_dedup_disclosure()/main() (issue #1197's Dedup-line extension; the ACM
table check itself predates this file and had no dedicated test suite of
its own until now).

Direct-import suite -- pytest.ini's own testpaths/pythonpath entries for
this directory make `import gitapex_check_acm_present` resolve the same
way hooks/ own test suites import their sibling modules.
"""

from __future__ import annotations

import io
import sys

import gitapex_check_acm_present as checker

# --- has_acm_table (pre-existing behavior, now under test) --------------


def test_has_acm_table_true_when_header_present() -> None:
    body = "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n|---|---|---|---|---|\n"
    assert checker.has_acm_table(body)


def test_has_acm_table_false_when_absent() -> None:
    assert not checker.has_acm_table("just a plain description, no table")


def test_has_acm_table_false_on_none() -> None:
    assert not checker.has_acm_table(None)


# --- has_dedup_disclosure (new) ------------------------------------------


def test_has_dedup_disclosure_true_with_query_and_count() -> None:
    assert checker.has_dedup_disclosure("Dedup: 'flaky test retry' search_issues query, 3 results reviewed")


def test_has_dedup_disclosure_true_with_none_found() -> None:
    assert checker.has_dedup_disclosure("Some text\n\nDedup: none found\n")


def test_has_dedup_disclosure_false_when_absent() -> None:
    assert not checker.has_dedup_disclosure("no dedup line anywhere in this body")


def test_has_dedup_disclosure_false_on_none() -> None:
    assert not checker.has_dedup_disclosure(None)


def test_has_dedup_disclosure_requires_a_non_empty_reason() -> None:
    assert not checker.has_dedup_disclosure("Dedup:\n")
    assert not checker.has_dedup_disclosure("Dedup:   \n")


def test_has_dedup_disclosure_case_insensitive_and_bulleted() -> None:
    assert checker.has_dedup_disclosure("- dedup: none found")


def test_has_dedup_disclosure_stays_anchored_to_the_start_of_a_line() -> None:
    """Guard rail on `_DEDUP_RE`'s `^...[-*]?` prefix.

    `_DEDUP_RE` currently rejects several decorated-but-genuine renderings of
    the field label (`**Dedup:**`, `` `Dedup`: ``, `## Dedup:`) because
    `[-*]?` admits exactly one optional bullet character. The obvious way to
    widen that -- dropping the `^` anchor, or letting arbitrary characters
    precede the field name -- would silently turn prose that merely *mentions*
    the field into a passing disclosure. These are the cases any such widening
    must keep rejecting, pinned here so the trade-off stays visible rather
    than being discovered after the gate has already let a body through.
    """
    # Mid-line mention inside an ordinary sentence: not a disclosure line.
    assert not checker.has_dedup_disclosure("I ran a Dedup: none found\n")
    # Field name glued to a longer identifier: not this field.
    assert not checker.has_dedup_disclosure("PreDedup: none found\n")
    # A longer field name that merely starts with the same letters.
    assert not checker.has_dedup_disclosure("Deduplication: none found\n")
    # The genuine bulleted form still matches, so the anchor is not overtight.
    assert checker.has_dedup_disclosure("  - Dedup: none found\n")


def test_has_dedup_disclosure_rejects_a_line_inside_a_fenced_code_block() -> None:
    """Regression test (CodeRabbit review, PR #1215): a `Dedup:` line
    inside a fenced code block -- illustrating the field's own syntax, the
    same false-positive class this module's docstring names as already
    found live against a sibling hook's PR body -- must not be detected.
    Also covers an *unterminated* fence: GitHub renders that as code
    through to the end of the body too, so it must be stripped the same
    way (mirrors hooks/gitapex_check_pr_duplicate_issue.py's own
    regression coverage for the identical bug class)."""
    assert not checker.has_dedup_disclosure("```text\nDedup: none found\n```\n")
    assert not checker.has_dedup_disclosure("```\nDedup: 'x' search, 0 results reviewed\n```\n")
    assert not checker.has_dedup_disclosure("```text\nDedup: none found\n")


def test_has_dedup_disclosure_before_an_unrelated_fence_still_counts() -> None:
    """Guards against the fence-stripping fix over-stripping: a genuine
    disclosure line appearing *before* an unrelated fenced block elsewhere
    in the body must still be detected."""
    assert checker.has_dedup_disclosure("Dedup: real reason\n```\nexample text\n```\n")


def test_has_dedup_disclosure_rejects_a_blockquoted_line() -> None:
    """Regression test (battle-testing-a-skill audit, PR #1215 Finding A/B):
    Step 3 requires quoting the requester's own words verbatim into Facts,
    and a blockquote (`>`) is the natural markdown rendering for that. A
    requester's own message containing text shaped like "Dedup: none
    found" must not satisfy this gate merely because it got quoted -- no
    real Step 6 search happened just because the requester happened to
    type that phrase. `>` was deliberately dropped from the accepted
    bullet/heading prefixes for this reason; pinned here so a future
    "widen the decoration" change does not silently reintroduce it."""
    assert not checker.has_dedup_disclosure("> Dedup: none found\n")
    assert not checker.has_dedup_disclosure("> **Dedup:** none found\n")


def test_has_dedup_disclosure_accepts_the_skill_s_own_documented_output_line() -> None:
    """Round-trip guard (battle-testing-a-skill audit, PR #1215 Finding E):
    SKILL.md's own Output section (line 123) documents this field as
    "- **Dedup:** the search query run and result count, or `none found`"
    -- bold decoration wrapping the field name *and* its colon together, not
    just the bare label. An agent that follows the skill's own template
    verbatim must not be blocked by the gate the same skill bundles; pinned
    here as its own case rather than left to be covered only incidentally by
    the other decorated-form tests above.
    """
    assert checker.has_dedup_disclosure("- **Dedup:** the search query run and result count, or `none found`")
    assert checker.has_dedup_disclosure("**Dedup:** none found")


def test_has_dedup_disclosure_handles_crlf_line_endings() -> None:
    """`has_dedup_disclosure` does no CR/CRLF normalization of its own, unlike
    the sibling `hooks/gitapex_check_acm_present_or_waiver.py`, which rewrites
    `\\r\\n`/`\\r` to `\\n` before matching. CRLF bodies happen to work anyway
    (`.` consumes the `\\r`; MULTILINE `$` sits before the `\\n`), and the
    non-empty-reason requirement survives CRLF too (`\\r` is `\\s`, so it
    cannot satisfy `\\S`). Both behaviors are incidental to the current
    pattern rather than stated intent, so pin them: if normalization is ever
    added, this test says what must not change.
    """
    assert checker.has_dedup_disclosure("Some drafted issue body.\r\nDedup: none found\r\n")
    assert not checker.has_dedup_disclosure("Dedup:\r\n")
    assert not checker.has_dedup_disclosure("Dedup:  \r\n")


# --- main(): the combined CLI gate ---------------------------------------


class _FakeStdin:
    """Mimics the one attribute checker.main() actually reads:
    sys.stdin.buffer.read() -> bytes."""

    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


def _run_main(body: str, monkeypatch: object, capsys: object) -> int:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(body.encode("utf-8")))  # type: ignore[attr-defined]
    return checker.main([])


def test_main_passes_when_both_table_and_dedup_present(monkeypatch: object, capsys: object) -> None:
    body = (
        "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
        "|---|---|---|---|---|\n"
        "| a | b | c | d | e |\n\n"
        "Dedup: 'topic X' search, 0 results reviewed\n"
    )
    exit_code = _run_main(body, monkeypatch, capsys)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 0
    assert "PASS" in captured.out


def test_main_fails_when_table_present_but_dedup_missing(monkeypatch: object, capsys: object) -> None:
    body = "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n|---|---|---|---|---|\n"
    exit_code = _run_main(body, monkeypatch, capsys)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 1
    assert "Dedup" in captured.err


def test_main_fails_when_dedup_present_but_table_missing(monkeypatch: object, capsys: object) -> None:
    body = "Dedup: none found\n"
    exit_code = _run_main(body, monkeypatch, capsys)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 1
    assert "Acceptance Criteria Map" in captured.err


def test_main_fails_and_reports_both_when_neither_present(monkeypatch: object, capsys: object) -> None:
    exit_code = _run_main("nothing here at all", monkeypatch, capsys)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 1
    assert "Acceptance Criteria Map" in captured.err
    assert "Dedup" in captured.err


# --- main(): the --body <file> CLI path (evaluating-skill-quality audit, ---
# --- PR #1215, dimension 7 -- every test above exercises stdin only, ---
# --- leaving the file-argument branch and both its error handlers ---
# --- (lines 133-139) completely uncovered) --------------------------------


def test_main_reads_body_from_a_file_argument(tmp_path: object, capsys: object) -> None:
    body = (
        "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
        "|---|---|---|---|---|\n"
        "| a | b | c | d | e |\n\n"
        "Dedup: none found\n"
    )
    body_file = tmp_path / "draft-body.md"  # type: ignore[operator]
    body_file.write_text(body, encoding="utf-8")
    exit_code = checker.main(["--body", str(body_file)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 0
    assert "PASS" in captured.out


def test_main_reports_file_not_found_for_a_missing_body_file(tmp_path: object, capsys: object) -> None:
    missing = tmp_path / "does-not-exist.md"  # type: ignore[operator]
    exit_code = checker.main(["--body", str(missing)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 1
    assert "error: body file not found" in captured.err
    assert str(missing) in captured.err


def test_main_reports_invalid_utf8_for_a_body_file(tmp_path: object, capsys: object) -> None:
    body_file = tmp_path / "not-utf8.md"  # type: ignore[operator]
    body_file.write_bytes(b"\xff\xfe not valid utf-8")
    exit_code = checker.main(["--body", str(body_file)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 1
    assert "is not valid UTF-8" in captured.err
    assert str(body_file) in captured.err

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

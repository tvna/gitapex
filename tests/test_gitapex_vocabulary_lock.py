"""Tests for the shared vocabulary/structure drift-lock primitives
(.github/scripts/_gitapex_vocabulary_lock.py).

Refs #1013 (task 6): `check_number_word_matches` is the new addition this
task generalizes out of `gitapex_scan_contract_axis_vocabulary_drift.py`
and `gitapex_scan_skill_quality_rubric_vocabulary_drift.py`'s own,
previously-duplicated count-lock loops. `read_text`/`extract_section`
predate this task and stay covered indirectly through those two gates'
own existing test suites.
"""

from __future__ import annotations

import _gitapex_vocabulary_lock as lock


def _mismatch(word: str, stated: int) -> str:
    return f"mismatch: {word}={stated}"


def test_check_number_word_matches_reports_nothing_when_all_match() -> None:
    assert lock.check_number_word_matches(["three", "three"], 3, str, _mismatch) == []


def test_check_number_word_matches_reports_unrecognized_word() -> None:
    problems = lock.check_number_word_matches(["eleventy"], 3, lambda word: f"unrecognized: {word}", _mismatch)
    assert problems == ["unrecognized: eleventy"]


def test_check_number_word_matches_reports_mismatch_with_original_word_and_parsed_value() -> None:
    problems = lock.check_number_word_matches(["Four"], 3, str, _mismatch)
    assert problems == ["mismatch: Four=4"]


def test_check_number_word_matches_is_case_insensitive() -> None:
    assert lock.check_number_word_matches(["Three"], 3, str, _mismatch) == []


def test_check_number_word_matches_empty_input_reports_nothing() -> None:
    assert lock.check_number_word_matches([], 3, str, _mismatch) == []

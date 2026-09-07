"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_skill_audit_disclosure.py`` (issue #1571 Step
6, closing issue #1178's own ``detection-logic-property-coverage`` gap for
the punctuation-adjacency ``_line_pattern`` widening and the new
emphasis-wrap diagnostic helpers ``_name_line_remainder_re`` and
``_is_emphasis_wrapped_verdict``).

This module resolves via ``import gitapex_gate_skill_audit_disclosure`` --
``.github/scripts`` is on pyproject.toml's own ``pythonpath``, the same
resolution ``tests/test_gitapex_gate_skill_audit_disclosure.py`` already
uses.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import gitapex_gate_skill_audit_disclosure as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=300, deadline=None)

# A single ordinary word (letters/digits/hyphens), used both as a stand-in
# check name and as a stand-in verdict token -- neither needs to be a real
# check/verdict for these properties, which are about the regex's own
# structural behavior (word-boundary safety, single-punctuation tolerance),
# not about this file's closed verdict vocabulary.
_WORD = st.text(alphabet=st.characters(min_codepoint=0x41, max_codepoint=0x5A), min_size=2, max_size=12)
_NARROW_PUNCTUATION = st.sampled_from(list(".,;:!?`"))
_EXTRA_LETTERS = st.text(alphabet=st.characters(min_codepoint=0x41, max_codepoint=0x5A), min_size=1, max_size=6)


@_PROPERTIES
@given(name=_WORD, verdict=_WORD, punctuation=_NARROW_PUNCTUATION)
def test_line_pattern_accepts_verdict_with_one_trailing_punctuation(name: str, verdict: str, punctuation: str) -> None:
    """For ANY check name and ANY verdict token, `_line_pattern` accepts a
    line where the verdict is followed by exactly one narrow-punctuation
    character and nothing else -- the issue #1571/#1888/#1784 widening,
    driven across generated names/verdicts rather than the hand-picked
    fixtures in the example suite."""
    pattern = gate._line_pattern(name, (verdict,))
    assert pattern.search(f"{name}: {verdict}{punctuation}")


@_PROPERTIES
@given(name=_WORD, verdict=_WORD, extra=_EXTRA_LETTERS)
def test_line_pattern_rejects_verdict_extended_by_more_letters(name: str, verdict: str, extra: str) -> None:
    """For ANY check name and ANY verdict token, `_line_pattern` must NOT
    accept a longer word that merely starts with the verdict token and is
    immediately followed by more letters, with no punctuation and no word
    boundary -- the defeat property for the #1571 widening (it must not
    have weakened the pre-existing `\\b` requirement)."""
    pattern = gate._line_pattern(name, (verdict,))
    assert not pattern.search(f"{name}: {verdict}{extra}")


@_PROPERTIES
@given(name=_WORD, remainder=_WORD)
def test_name_line_remainder_re_round_trips_the_remainder(name: str, remainder: str) -> None:
    """For ANY check name and ANY single-word remainder, `_name_line_remainder_re`
    captures that exact remainder back out of a line built from the two."""
    match = gate._name_line_remainder_re(name).search(f"- {name}: {remainder}\n")
    assert match is not None
    assert match.group(1) == remainder


@_PROPERTIES
@given(verdict=_WORD, marker=st.sampled_from(["**", "_"]))
def test_is_emphasis_wrapped_verdict_true_for_any_verdict_wrapped_in_a_marker(verdict: str, marker: str) -> None:
    """For ANY verdict token in the accepted set, wrapping it in either
    emphasis marker is detected as emphasis-wrapped."""
    wrapped = f"{marker}{verdict}{marker}"
    assert gate._is_emphasis_wrapped_verdict(wrapped, (verdict,)) is True


@_PROPERTIES
@given(verdict=_WORD, other=_WORD)
def test_is_emphasis_wrapped_verdict_false_for_bare_unwrapped_verdict(verdict: str, other: str) -> None:
    """A bare, unwrapped verdict token (no emphasis markers at all) is
    never reported as emphasis-wrapped, regardless of the verdict set's
    own contents."""
    assert gate._is_emphasis_wrapped_verdict(verdict, (verdict, other)) is False

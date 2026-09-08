"""Hypothesis property-based layer for
``hooks/gitapex_check_skill_audit_disclosure_or_waiver.py``'s own
``_line_pattern`` (issue #1571 Step 6, closing issue #1178's own
``detection-logic-property-coverage`` gap for the punctuation-adjacency
widening applied to this module's byte-identical copy of
``.github/scripts/gitapex_gate_skill_audit_disclosure.py``'s own
``_line_pattern``).

tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py already pins
byte-for-byte parity between the two modules' own regex-construction
functions; this file's job is only the property-coverage gate's own
per-module requirement, not a second copy of that sync test.

This module resolves via ``import gitapex_check_skill_audit_disclosure_or_waiver``
-- ``hooks`` is on pyproject.toml's own ``pythonpath``, the same resolution
``tests/test_gitapex_check_skill_audit_disclosure_or_waiver.py`` already
uses.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import gitapex_check_skill_audit_disclosure_or_waiver as checker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=300, deadline=None)

_WORD = st.text(alphabet=st.characters(min_codepoint=0x41, max_codepoint=0x5A), min_size=2, max_size=12)
_NARROW_PUNCTUATION = st.sampled_from(list(".,;:!?`"))
_EXTRA_LETTERS = st.text(alphabet=st.characters(min_codepoint=0x41, max_codepoint=0x5A), min_size=1, max_size=6)


@_PROPERTIES
@given(name=_WORD, verdict=_WORD, punctuation=_NARROW_PUNCTUATION)
def test_line_pattern_accepts_verdict_with_one_trailing_punctuation(name: str, verdict: str, punctuation: str) -> None:
    """For ANY check name and ANY verdict token, this module's own
    `_line_pattern` accepts a line where the verdict is followed by
    exactly one narrow-punctuation character and nothing else -- the
    issue #1571/#1888/#1784 widening, mirrored from the CI gate script."""
    pattern = checker._line_pattern(name, (verdict,))
    assert pattern.search(f"{name}: {verdict}{punctuation}")


@_PROPERTIES
@given(name=_WORD, verdict=_WORD, extra=_EXTRA_LETTERS)
def test_line_pattern_rejects_verdict_extended_by_more_letters(name: str, verdict: str, extra: str) -> None:
    """For ANY check name and ANY verdict token, this module's own
    `_line_pattern` must NOT accept a longer word that merely starts with
    the verdict token and is immediately followed by more letters -- the
    defeat property for the #1571 widening."""
    pattern = checker._line_pattern(name, (verdict,))
    assert not pattern.search(f"{name}: {verdict}{extra}")

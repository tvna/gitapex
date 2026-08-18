"""Hypothesis property-based layer for
``skills/drafting-an-acm-issue/scripts/gitapex_check_acm_present.py``'s
``has_dedup_disclosure`` (issue #1197, closing issue #1178's own
``detection-logic-property-coverage`` gap for this new module-level
``_DEDUP_RE`` compile and the ``has_dedup_disclosure`` function).

This module resolves via `import gitapex_check_acm_present` against
``skills/drafting-an-acm-issue/scripts`` specifically (that directory's own
new ``pyproject.toml`` ``pythonpath`` entry, issue #1197) -- the sibling
copy at ``skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py``
is not on ``pythonpath`` at all, so there is no module-name collision.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import gitapex_check_acm_present as checker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_HANGUL_FILLER = chr(0x3164)  # category Lo (not Cf), so the blacklist below misses it without this
_REASON_ALPHABET = st.characters(blacklist_categories=("Cc", "Cs", "Cf"), blacklist_characters="\n\r" + _HANGUL_FILLER)
_NON_EMPTY_REASON = st.text(alphabet=_REASON_ALPHABET, min_size=1).filter(lambda s: not s[0].isspace())

_WHITESPACE_ONLY = st.text(alphabet=st.sampled_from([" ", "\t"]), max_size=10)
_CASINGS = ("Dedup", "dedup", "DEDUP", "DeDuP")
_BULLETS = ("", "- ", "* ", "  - ")


@_PROPERTIES
@given(reason=_NON_EMPTY_REASON, casing=st.sampled_from(_CASINGS), bullet=st.sampled_from(_BULLETS))
def test_any_non_empty_reason_is_detected_regardless_of_casing_or_bullet(reason: str, casing: str, bullet: str) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    the fixed examples in test_gitapex_check_acm_present.py only assert
    against a handful of hand-picked disclosure strings (a search-query
    phrase, "none found") -- this drives the disclosed text itself across a
    wide space of Unicode content, casing, and bullet style, confirming the
    "non-empty reason" requirement holds for content shape generally.

    Confirmed to have teeth: replacing `_DEDUP_RE`'s `\\S.*$` with a
    stricter `[A-Za-z].*$` (still passing every hand-written example) makes
    this property FAIL on the first generated example whose disclosed text
    starts with a digit, quote, or punctuation character -- exactly the
    class of narrowing a fixed-example suite would not catch.
    """
    body = f"Some drafted issue body.\n\n{bullet}{casing}: {reason}\n"
    assert checker.has_dedup_disclosure(body)


@_PROPERTIES
@given(whitespace=_WHITESPACE_ONLY, casing=st.sampled_from(_CASINGS))
def test_whitespace_only_reason_is_never_detected(whitespace: str, casing: str) -> None:
    """Robustness: any amount of trailing whitespace with no actual
    disclosure content never counts -- the `\\S` requirement in `_DEDUP_RE`
    is not satisfiable by whitespace alone, checked across a range of
    whitespace lengths rather than the single hand-picked `"Dedup:\\n"`
    example."""
    body = f"{casing}:{whitespace}\n"
    assert not checker.has_dedup_disclosure(body)


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_arbitrary_text_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text produces a result rather than an
    exception, and the same input produces the same output -- this script
    runs as a local pre-issue-creation gate, where an uncaught exception is
    a crashed check, not a reported finding."""
    first = checker.has_dedup_disclosure(text)
    second = checker.has_dedup_disclosure(text)
    assert first == second
    assert isinstance(first, bool)


@_PROPERTIES
@given(text=st.text(max_size=200).filter(lambda s: "dedup" not in s.lower()))
def test_text_never_containing_the_field_name_is_never_detected(text: str) -> None:
    """No false positive: text that never contains the field name at all
    (case-insensitively, checked by the filter above) is never detected as
    carrying a Dedup disclosure, regardless of other content."""
    assert not checker.has_dedup_disclosure(text)


@_PROPERTIES
@given(reason=_NON_EMPTY_REASON)
def test_has_acm_table_is_unaffected_by_an_unrelated_dedup_line(reason: str) -> None:
    """Cross-check: adding a Dedup line never flips `has_acm_table`'s own
    verdict either way -- the two checks are independent presence tests
    over the same body text, sharing no state. Exercises `has_acm_table`
    (pre-existing, module-level `_HEADER_RE`) inside this same @given test
    so this file's own module-level property coverage is unambiguous."""
    with_table = "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n|---|---|---|---|---|\n"
    body = f"{with_table}\nDedup: {reason}\n"
    assert checker.has_acm_table(body) == checker.has_acm_table(with_table)

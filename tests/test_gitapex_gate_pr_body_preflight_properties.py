"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_pr_body_preflight.py``'s
``check_ascii_only`` (issue #1725, closing issue #1178's own
``detection-logic-property-coverage`` gap for this new module's
``_NON_ASCII_RE`` compile and this function's own regex-search call).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import gitapex_gate_pr_body_preflight as preflight
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# The exact range check_ascii_only's own _NON_ASCII_RE permits: printable
# ASCII (0x20-0x7E) plus a bare tab. Deliberately excludes "\n" -- lines
# are split on it before matching, so it never reaches the regex itself.
_ASCII_CLEAN_ALPHABET = st.sampled_from([chr(code) for code in range(0x20, 0x7F)] + ["\t"])
_ASCII_CLEAN_TEXT = st.text(alphabet=_ASCII_CLEAN_ALPHABET, max_size=200)

# Any single codepoint outside the permitted range above, and outside "\n"
# (which check_ascii_only never sees mid-line either, per splitlines()).
_NON_ASCII_CHAR = st.characters(
    blacklist_categories=(),
    min_codepoint=0x00A0,
    max_codepoint=0x10FFFF,
).filter(lambda c: c not in "\n")


@_PROPERTIES
@given(text=_ASCII_CLEAN_TEXT)
def test_ascii_clean_text_always_passes(text: str) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    the fixed examples in test_gitapex_gate_pr_body_preflight.py only
    assert a small handful of hand-picked ASCII strings -- this drives
    the checked text across the full printable-ASCII-plus-tab alphabet,
    confirming the "never a false positive on clean text" property holds
    generally, not merely for those examples.

    Confirmed to have teeth: narrowing check_ascii_only's own
    `_NON_ASCII_RE` range from `[^ -~\\t]` to `[^ -~]` (dropping the tab
    exemption) makes this property FAIL on the first generated example
    containing a tab -- exactly the class of narrowing a fixed-example
    suite would not catch.
    """
    result = preflight.check_ascii_only(text)
    assert result.passed
    assert not result.skipped


@_PROPERTIES
@given(prefix=_ASCII_CLEAN_TEXT, offending=_NON_ASCII_CHAR, suffix=_ASCII_CLEAN_TEXT)
def test_any_single_non_ascii_character_is_always_flagged(prefix: str, offending: str, suffix: str) -> None:
    """Robustness: exactly one non-ASCII character anywhere in an
    otherwise-clean body -- at the start, middle, or end -- is always
    caught, across a wide space of surrounding ASCII content and of which
    non-ASCII codepoint is used (not only a hand-picked em dash)."""
    text = f"{prefix}{offending}{suffix}"
    result = preflight.check_ascii_only(text)
    assert not result.passed
    assert offending in result.output or repr(offending) in result.output


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_check_ascii_only_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text (any Unicode, any line structure)
    produces a result rather than an exception, and the same input
    produces the same verdict -- this sub-check runs as part of a
    PreToolUse gate, where an uncaught exception fails the whole
    consolidated preflight rather than reporting one clean sub-check
    result."""
    first = preflight.check_ascii_only(text)
    second = preflight.check_ascii_only(text)
    assert first.passed == second.passed
    assert isinstance(first.passed, bool)

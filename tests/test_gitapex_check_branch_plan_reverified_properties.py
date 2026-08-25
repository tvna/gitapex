"""Hypothesis property-based layer for
``skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py``
(issue #1306, closing issue #1178's own ``detection-logic-property-coverage``
gap for this new module-level ``_RE_VERIFIED_MARKER_RE`` compile, its
``_strip_fences`` string-comparison allowlist checks, and
``has_reverified_marker``'s regex search).

This module resolves via `import gitapex_check_branch_plan_reverified`
against `skills/executing-a-branch-plan/scripts` (that directory's own new
`pyproject.toml` `pythonpath` entry) -- no other module anywhere in this
repository shares that literal name, so there is no module-name collision
risk the way the two `gitapex_check_acm_present.py` copies have.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py`` and
``tests/test_gitapex_check_acm_present_properties.py``.
"""

from __future__ import annotations

import gitapex_check_branch_plan_reverified as checker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_TIMESTAMP_ALPHABET = st.characters(blacklist_categories=("Cc", "Cs", "Cf"), blacklist_characters="()\n\r")
_NON_EMPTY_TIMESTAMP = st.text(alphabet=_TIMESTAMP_ALPHABET, min_size=1).filter(lambda s: not s[0].isspace())
_WHITESPACE_ONLY = st.text(alphabet=st.sampled_from([" ", "\t"]), max_size=10)
_CASINGS = ("Re-verified", "re-verified", "RE-VERIFIED", "Re-Verified")
_BULLETS = ("", "- ", "* ")
_INDENTS = ("    ", "     ", "\t", "        ")  # 4+ columns -- CommonMark's own indented-code-block threshold


@_PROPERTIES
@given(timestamp=_NON_EMPTY_TIMESTAMP, casing=st.sampled_from(_CASINGS), bullet=st.sampled_from(_BULLETS))
def test_any_non_empty_timestamp_is_detected_regardless_of_casing_or_bullet(
    timestamp: str, casing: str, bullet: str
) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    the fixed examples in test_gitapex_check_branch_plan_reverified.py only
    assert against a handful of hand-picked timestamp strings -- this drives
    the parenthesized content itself across a wide space of Unicode
    content, casing, and bullet style, confirming the "non-empty
    parenthesized value" requirement holds for content shape generally.

    Confirmed to have teeth: replacing `_RE_VERIFIED_MARKER_RE`'s
    `\\S[^)\\r\\n]*` with a stricter `[A-Za-z][^)\\r\\n]*` (still passing every
    hand-written example) makes this property FAIL on the first generated
    example whose timestamp starts with a digit or punctuation character --
    exactly the class of narrowing a fixed-example suite would not catch.
    """
    body = f"{bullet}{casing}: `planning-a-branch-from-an-issue` ({timestamp})\n"
    assert checker.has_reverified_marker(body)


@_PROPERTIES
@given(whitespace=_WHITESPACE_ONLY, casing=st.sampled_from(_CASINGS))
def test_whitespace_only_timestamp_is_never_detected(whitespace: str, casing: str) -> None:
    """Robustness: any amount of whitespace with no actual timestamp content
    never counts -- the `\\S` requirement in `_RE_VERIFIED_MARKER_RE` is not
    satisfiable by whitespace alone, checked across a range of whitespace
    lengths rather than the single hand-picked `"( )"` example."""
    body = f"{casing}: `planning-a-branch-from-an-issue` ({whitespace})\n"
    assert not checker.has_reverified_marker(body)


@_PROPERTIES
@given(timestamp=_NON_EMPTY_TIMESTAMP, casing=st.sampled_from(_CASINGS))
def test_a_marker_inside_a_fenced_code_block_is_never_detected(timestamp: str, casing: str) -> None:
    """Containment: a syntactically valid marker, wrapped in a fenced code
    block (an illustrative example of the marker's own syntax), is never
    misdetected as a real disclosure -- across generated timestamp text,
    not only a hand-picked example. Exercises `_strip_fences` by name.

    Confirmed to have teeth: removing `_strip_fences`'s call from
    `has_reverified_marker` makes this property FAIL on every generated
    example, since the unstripped fenced line still matches
    `_RE_VERIFIED_MARKER_RE` directly.
    """
    body = f"Example marker syntax:\n\n```\n{casing}: `planning-a-branch-from-an-issue` ({timestamp})\n```\n"
    assert not checker.has_reverified_marker(body)
    # Exercise the helper directly too, so this file's own module-level
    # property coverage names it explicitly rather than only indirectly
    # through has_reverified_marker's own call.
    assert checker._strip_fences(body).count("Re-verified") == 0 or "```" not in body


@_PROPERTIES
@given(timestamp=_NON_EMPTY_TIMESTAMP, casing=st.sampled_from(_CASINGS), indent=st.sampled_from(_INDENTS))
def test_a_marker_only_quoted_via_indentation_is_never_detected(timestamp: str, casing: str, indent: str) -> None:
    """Containment (issue #1306's own adversarial-review finding): a
    marker quoted via 4+ column indentation -- CommonMark/GFM's own
    "indented code block" convention, not a ```/~~~ fence -- must never be
    misdetected as a genuine disclosure either, across generated timestamp
    text and indentation width, not only the one hand-picked 4-space
    example in the fixed-example suite.

    Confirmed to have teeth: reverting `_RE_VERIFIED_MARKER_RE`'s leading
    `^(?:[-*][ \\t]+)?` anchor back to the pre-fix `^[ \\t]*[-*]?[ \\t]*` shape
    makes this property FAIL on every generated example -- the whole point
    of the fix this property exists to pin.
    """
    body = f"Here's an example:\n\n{indent}{casing}: `planning-a-branch-from-an-issue` ({timestamp})\n\nNot real.\n"
    assert not checker.has_reverified_marker(body)


@_PROPERTIES
@given(timestamp=_NON_EMPTY_TIMESTAMP, casing=st.sampled_from(_CASINGS))
def test_a_single_unpaired_backtick_is_never_detected(timestamp: str, casing: str) -> None:
    """Containment (issue #1306's own adversarial-review finding): the
    skill-name backticks must be a matched pair, not independently
    optional -- checked across generated timestamp text for both the
    opening-only and closing-only shapes."""
    opening_only = f"{casing}: `planning-a-branch-from-an-issue ({timestamp})\n"
    closing_only = f"{casing}: planning-a-branch-from-an-issue` ({timestamp})\n"
    assert not checker.has_reverified_marker(opening_only)
    assert not checker.has_reverified_marker(closing_only)


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_arbitrary_text_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text produces a result rather than an
    exception, and the same input produces the same output -- this script
    runs as a local pre-execution gate, where an uncaught exception is a
    crashed check, not a reported finding."""
    first = checker.has_reverified_marker(text)
    second = checker.has_reverified_marker(text)
    assert first == second
    assert isinstance(first, bool)


@_PROPERTIES
@given(text=st.text(max_size=200).filter(lambda s: "re-verified" not in s.lower()))
def test_text_never_containing_the_marker_prefix_is_never_detected(text: str) -> None:
    """No false positive: text that never contains the marker's own prefix
    at all (case-insensitively, checked by the filter above) is never
    detected as carrying a re-verification marker, regardless of other
    content."""
    assert not checker.has_reverified_marker(text)

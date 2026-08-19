"""Hypothesis property-based layer for
``hooks/gitapex_check_pr_duplicate_issue.py``'s ``has_duplicate_waiver``
(issue #1197, closing issue #1178's own ``detection-logic-property-coverage``
gap for this new module's ``_FENCE_RE``/``_INLINE_CODE_RE``/``_WAIVER_RE``
module-level compiles and the ``has_duplicate_waiver`` function).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own
established rationale (this repository runs pytest under ``pytest-xdist``,
where a randomly-seeded generator turns a latent failure into an
intermittently red suite).
"""

from __future__ import annotations

import gitapex_check_pr_duplicate_issue as checker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# A single logical line, non-control-character, and guaranteed to start with
# a non-whitespace character by construction (`filter` on the first char) --
# exactly what `_WAIVER_RE`'s own `\S.*$` requires after the colon. No
# newline/carriage-return so this stays one line the `re.MULTILINE` anchors
# treat as such. Backtick is excluded too: `_strip_fences` runs body-wide
# before `_WAIVER_RE` ever sees the text, and `_INLINE_CODE_RE` treats any
# backtick-delimited span -- including one that is, by construction, the
# entire generated reason (e.g. a bare "`x`") -- as inline code to strip,
# which can leave nothing non-whitespace behind for a reason that would
# otherwise be perfectly valid content. Confirmed live: without this
# exclusion, hypothesis finds the reason "``" (two backticks, an empty
# inline-code span) as a counterexample to this property.
_REASON_ALPHABET = st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="\n\r`")
_NON_EMPTY_REASON = st.text(alphabet=_REASON_ALPHABET, min_size=1).filter(lambda s: not s[0].isspace())

_WHITESPACE_ONLY = st.text(alphabet=st.sampled_from([" ", "\t"]), max_size=10)
_CASINGS = ("Duplicate-PR-waiver", "duplicate-pr-waiver", "DUPLICATE-PR-WAIVER", "Duplicate-Pr-Waiver")
_BULLETS = ("", "- ", "* ", "  - ")


@_PROPERTIES
@given(reason=_NON_EMPTY_REASON, casing=st.sampled_from(_CASINGS), bullet=st.sampled_from(_BULLETS))
def test_any_non_empty_reason_is_detected_regardless_of_casing_or_bullet(reason: str, casing: str, bullet: str) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    the fixed examples in test_gitapex_check_pr_duplicate_issue.py only ever
    assert against a handful of hand-picked reason strings -- this drives
    the reason text itself, across a wide space of Unicode content, casing,
    and bullet style, confirming the "non-empty reason" requirement holds
    for content shape generally, not just the examples an author happened
    to think of.

    Confirmed to have teeth: replacing `_WAIVER_RE`'s `\\S.*$` with a
    stricter `[A-Za-z].*$` (still passing every hand-written example, since
    those all start with a letter) makes this property FAIL on the first
    generated example starting with a digit or punctuation character --
    exactly the class of narrowing a fixed-example suite would not catch.
    """
    body = f"Some PR description.\n\n{bullet}{casing}: {reason}\n"
    assert checker.has_duplicate_waiver(body)


@_PROPERTIES
@given(whitespace=_WHITESPACE_ONLY, casing=st.sampled_from(_CASINGS))
def test_whitespace_only_reason_is_never_detected(whitespace: str, casing: str) -> None:
    """Robustness: any amount of trailing whitespace with no actual reason
    content never counts as a waiver -- the `\\S` requirement in
    `_WAIVER_RE` is not satisfiable by whitespace alone, checked across a
    range of whitespace lengths and styles rather than the single
    hand-picked `"Duplicate-PR-waiver:\\n"` example."""
    body = f"{casing}:{whitespace}\n"
    assert not checker.has_duplicate_waiver(body)


@_PROPERTIES
@given(reason=_NON_EMPTY_REASON, casing=st.sampled_from(_CASINGS))
def test_a_waiver_line_inside_a_fenced_code_block_is_never_detected(reason: str, casing: str) -> None:
    """Containment: a syntactically valid waiver line, wrapped in a fenced
    code block (an illustrative example of the waiver's own syntax, the
    exact false-positive class this module's own docstring names as
    already found live against its sibling hook's PR body), is never
    misdetected as a real waiver -- across generated reason text, not only
    the one hand-picked "example only" string.

    Confirmed to have teeth: removing `_strip_fences`'s call from
    `has_duplicate_waiver` makes this property FAIL on every generated
    example, since the unstripped fenced line still matches `_WAIVER_RE`
    directly.
    """
    body = f"Example usage:\n```\n{casing}: {reason}\n```\n"
    assert not checker.has_duplicate_waiver(body)


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_arbitrary_text_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text (including text containing stray `#`,
    backticks, or partial "Duplicate-PR-waiver" fragments) produces a
    result rather than an exception, and the same input produces the same
    output -- this function runs inside a PreToolUse hook, where an
    uncaught exception is a crashed gate, not a reported finding."""
    first = checker.has_duplicate_waiver(text)
    second = checker.has_duplicate_waiver(text)
    assert first == second
    assert isinstance(first, bool)


@_PROPERTIES
@given(text=st.text(max_size=200).filter(lambda s: "duplicate-pr-waiver" not in s.lower()))
def test_text_never_containing_the_field_name_is_never_detected(text: str) -> None:
    """No false positive: text that never contains the field name at all
    (case-insensitively, checked by the filter above) is never detected as
    carrying a waiver, regardless of what other punctuation or structure it
    happens to contain."""
    assert not checker.has_duplicate_waiver(text)

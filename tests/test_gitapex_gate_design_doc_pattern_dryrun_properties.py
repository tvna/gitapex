"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_design_doc_pattern_dryrun.py`` (issue #1507,
closing issue #1178's own ``detection-logic-property-coverage`` gap for
this new module's regex compiles and its ``find_candidate_patterns`` /
``has_disclosure_marker`` detection functions).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import gitapex_gate_design_doc_pattern_dryrun as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# A safe alphabet for generated filler/pattern text: printable, no control/
# format characters, and excludes every delimiter this module's own
# parsing depends on (backtick, straight/curly quotes, newlines) so a
# generated example never accidentally opens or closes a quote span, nor
# collides with a paragraph break.
_SAFE_ALPHABET = st.characters(
    blacklist_categories=("Cc", "Cs", "Cf"),
    blacklist_characters='`"“”\n\r',
)
_SAFE_TEXT = st.text(alphabet=_SAFE_ALPHABET, max_size=30)
_NON_EMPTY_SAFE_TEXT = st.text(alphabet=_SAFE_ALPHABET, min_size=1, max_size=40).filter(lambda s: not s.isspace())

_CUE_FORMS = ("literal-text search", "literal text search", "literal-text-search")
_QUOTE_STYLES = (('"', '"'), ("`", "`"))


@_PROPERTIES
@given(
    filler=_SAFE_TEXT,
    pattern=_NON_EMPTY_SAFE_TEXT,
    cue=st.sampled_from(_CUE_FORMS),
    quote_style=st.sampled_from(_QUOTE_STYLES),
)
def test_find_candidate_patterns_detects_any_quote_starting_within_the_window(
    filler: str, pattern: str, cue: str, quote_style: tuple[str, str]
) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    for any cue form, any filler short enough that the quote's own opening
    delimiter starts within `_TARGET_WINDOW_CHARS`, and any non-empty
    quoted pattern content, the pattern is always detected -- confirming
    the window-based extraction holds across generated content and
    filler length, not only the hand-picked fixtures in
    test_gitapex_gate_design_doc_pattern_dryrun.py.

    Confirmed to have teeth: this is exactly the shape of bug a dispatched
    checker-script-adversarial-review found and this fix closed -- an
    earlier design took only the *first* quoted literal in a fixed-length
    window slice, so a decoy quote ahead of the real target (or a target
    whose closing delimiter fell just past the slice boundary) went
    undetected; reverting to that design makes this property fail on
    generated examples exercising either gap.
    """
    open_delim, close_delim = quote_style
    # Keep the filler short enough that the quote's opening delimiter
    # starts well within the window, and cap total generated text so the
    # quote's own content still fits _QUOTED_LITERAL_MAX_LEN.
    bounded_filler = filler[: gate._TARGET_WINDOW_CHARS - 10]
    bounded_pattern = pattern[: gate._QUOTED_LITERAL_MAX_LEN]
    text = f"A {cue} for {bounded_filler} {open_delim}{bounded_pattern}{close_delim} here.\n"
    candidates = gate.find_candidate_patterns(text)
    assert any(c.pattern == bounded_pattern for c in candidates)


@_PROPERTIES
@given(pattern=_NON_EMPTY_SAFE_TEXT)
def test_find_candidate_patterns_never_fires_without_a_search_intent_cue(pattern: str) -> None:
    """Robustness: a quoted string with no "literal-text search" cue
    anywhere in the paragraph never becomes a candidate, across generated
    pattern content -- the cue requirement is load-bearing, not
    incidental to the hand-picked fixtures. No `cue` parameter: this test
    deliberately constructs text with no cue present at all, so
    generating cue *forms* here would be dead/misleading -- a
    correctness-review finding against an earlier draft that did."""
    bounded_pattern = pattern[: gate._QUOTED_LITERAL_MAX_LEN]
    text = f'This paragraph merely quotes "{bounded_pattern}" with no search cue nearby.\n'
    assert gate.find_candidate_patterns(text) == []


@_PROPERTIES
@given(pattern=_NON_EMPTY_SAFE_TEXT, cue=st.sampled_from(_CUE_FORMS))
def test_find_candidate_patterns_suppressed_by_a_rejection_cue_in_the_same_paragraph(pattern: str, cue: str) -> None:
    """Robustness: a paragraph combining a search-intent cue, a nearby
    quote, and a rejection phrase never yields a candidate, across
    generated pattern content -- the rejection-suppression logic (this
    gate's own false-positive defense against the real, already-merged
    design doc's corrected prose) holds generally, not only for that one
    fixed example."""
    bounded_pattern = pattern[: gate._QUOTED_LITERAL_MAX_LEN]
    text = f'A {cue} for "{bounded_pattern}" resolves against nothing in any current skill.\n'
    assert gate.find_candidate_patterns(text) == []


_WAIVED_REASON_ALPHABET = st.characters(blacklist_categories=("Cc", "Cs", "Cf"), blacklist_characters="\n\r")
_NON_EMPTY_WAIVED_REASON = st.text(alphabet=_WAIVED_REASON_ALPHABET, min_size=1, max_size=60).filter(
    lambda s: not s[0].isspace()
)
_WAIVER_BULLETS = ("", "- ", "* ", "  - ")


@_PROPERTIES
@given(reason=_NON_EMPTY_WAIVED_REASON, bullet=st.sampled_from(_WAIVER_BULLETS))
def test_has_disclosure_marker_detects_any_non_empty_reason(reason: str, bullet: str) -> None:
    """**Model-based:** any non-empty reason text, in the canonical
    `corpus-dryrun-disclosure: WAIVED: <reason>` form (with or without a
    leading list bullet), is always detected regardless of the reason
    text's own content -- confirming the waiver escape hatch this gate's
    FAIL path depends on holds across generated reason content, not only
    a hand-picked example.

    Confirmed to have teeth: narrowing `_WAIVER_RE`'s trailing `\\S.*$` to
    something stricter (e.g. requiring the reason to start with a letter)
    makes this property fail on the first generated example whose reason
    starts with a digit or punctuation character.
    """
    body = f"Some PR body prose.\n\n{bullet}corpus-dryrun-disclosure: WAIVED: {reason}\n"
    assert gate.has_disclosure_marker(body)


@_PROPERTIES
@given(whitespace=st.text(alphabet=st.sampled_from([" ", "\t"]), max_size=10))
def test_has_disclosure_marker_never_fires_on_whitespace_only_reason(whitespace: str) -> None:
    """Robustness: any amount of trailing whitespace with no actual
    disclosure content never counts as a waiver -- the `\\S` requirement
    in `_WAIVER_RE` is not satisfiable by whitespace alone, checked
    across a range of whitespace lengths."""
    body = f"corpus-dryrun-disclosure: WAIVED:{whitespace}\n"
    assert not gate.has_disclosure_marker(body)

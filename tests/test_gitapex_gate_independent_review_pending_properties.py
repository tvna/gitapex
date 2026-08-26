"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_independent_review_pending.py`` (issue #1311,
closing issue #1178's own ``detection-logic-property-coverage`` gap for
this new module's ``_HEADING_RE``/``_FENCED_BLOCK_RE``/``_VERDICT_RE``/
``_COMMIT_RE`` module-level compiles and the ``_last_section_from``/
``parse_verdict`` functions), extended (issue #1343) to also cover the
public ``heading_pattern()`` function directly -- added so
``gitapex_scan_independent_review_heading_drift.py`` could reuse this
module's own ATX-heading regex shape for arbitrary text, then flagged by
the same ``detection-logic-property-coverage`` gate this module's own
docstring cites as a new regex-compiling call site with no property
coverage of its own.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching
``tests/test_gitapex_check_pr_duplicate_issue_properties.py``'s own
established rationale (this repository runs pytest under ``pytest-xdist``,
where a randomly-seeded generator turns a latent failure into an
intermittently red suite).
"""

from __future__ import annotations

import re

import gitapex_gate_independent_review_pending as gate
from hypothesis import assume, given, settings
from hypothesis import strategies as st

_ANY_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_HEX = "0123456789abcdefABCDEF"
_SHAS = st.text(alphabet=_HEX, min_size=7, max_size=40)
_HEADING_LEVELS = ("##", "###", "####")
_EMPHASIS = ("", "*", "_", "`")
_BULLETS = ("-", "*")


@_PROPERTIES
@given(text=st.text(max_size=500))
def test_arbitrary_text_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: this module runs inside a required CI status check, where
    an uncaught exception in `parse_verdict`/`check` is a crashed gate, not
    a reported finding -- confirmed live this session against a directory
    path via `main`'s own file-reading branch (now caught there), but
    `parse_verdict`/`check` themselves take an in-memory string and must
    never raise regardless of its content."""
    first = gate.parse_verdict(text)
    second = gate.parse_verdict(text)
    assert first.status == second.status
    assert first.commit == second.commit
    assert first.error == second.error

    passed_first, message_first = gate.check(text, "abc123")
    passed_second, message_second = gate.check(text, "abc123")
    assert passed_first == passed_second
    assert message_first == message_second
    assert isinstance(passed_first, bool)


@_PROPERTIES
@given(text=st.text(max_size=300).filter(lambda s: "independent review verdict" not in s.lower()))
def test_text_never_containing_the_heading_phrase_never_parses(text: str) -> None:
    """No false positive: text that never contains the heading phrase at all
    (case-insensitively) never yields a usable verdict, regardless of what
    other Markdown structure it happens to contain."""
    verdict = gate.parse_verdict(text)
    assert verdict.error is not None


@_PROPERTIES
@given(
    level=st.sampled_from(_HEADING_LEVELS),
    sha=_SHAS,
    verdict_emphasis=st.sampled_from(_EMPHASIS),
    commit_emphasis=st.sampled_from(_EMPHASIS),
    bullet=st.sampled_from(_BULLETS),
    casing=st.sampled_from(("Independent review verdict", "INDEPENDENT REVIEW VERDICT", "independent review verdict")),
)
def test_a_real_clean_verdict_is_always_detected_and_passes(
    level: str, sha: str, verdict_emphasis: str, commit_emphasis: str, bullet: str, casing: str
) -> None:
    """**Model-based, detects a real gap fixed examples cannot:** a genuine,
    unfenced verdict section is always recognized as CLEAN against its own
    stated commit, across heading level, verdict/commit emphasis markup,
    bullet style, and heading casing -- not only the handful of hand-picked
    combinations in test_gitapex_gate_independent_review_pending.py.

    Confirmed to have teeth: narrowing `_HEADING_RE`'s `#{1,6}` to a literal
    `##` makes this property FAIL on every `###`/`####`-level generated
    example."""
    body = (
        f"{level} {casing}\n\n"
        f"{bullet} Verdict: {verdict_emphasis}CLEAN{verdict_emphasis}\n"
        f"{bullet} Verified commit: {commit_emphasis}{sha}{commit_emphasis}\n"
    )
    passed, message = gate.check(body, sha)
    assert passed is True, f"expected PASS for body={body!r}, got: {message}"


@_PROPERTIES
@given(sha=_SHAS, fence=st.sampled_from(("```", "~~~", "````", "~~~~")))
def test_a_verdict_inside_a_fenced_code_block_is_never_detected(sha: str, fence: str) -> None:
    """Containment: a syntactically valid CLEAN verdict section, wrapped in
    a fenced code block (an illustrative example only), is never
    misdetected as a real, live verdict -- across generated SHAs and fence
    styles/lengths, not only the one hand-picked example in
    test_gitapex_gate_independent_review_pending.py's own defeat-attempt
    tests. This is a live-confirmed defeat class (see the module docstring
    and issue #1311's own defeat-test-disclosure round), not a theoretical
    one.

    Confirmed to have teeth: removing `_strip_fenced_code_blocks`'s call
    from `parse_verdict` makes this property FAIL on every generated
    example, since the unstripped fenced section still matches
    `_HEADING_RE`/`_VERDICT_RE`/`_COMMIT_RE` directly."""
    body = f"Example usage:\n{fence}\n## Independent review verdict\n\n- Verdict: CLEAN\n- Verified commit: {sha}\n{fence}\n"
    passed, _ = gate.check(body, sha)
    assert passed is False


@_PROPERTIES
@given(
    open_len=st.integers(min_value=3, max_value=6),
    extra_close_len=st.integers(min_value=0, max_value=4),
    fence_char=st.sampled_from(("`", "~")),
    inner=st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="`~"), max_size=100),
)
def test_strip_fenced_code_blocks_direct_call_handles_any_valid_close_length(
    open_len: int, extra_close_len: int, fence_char: str, inner: str
) -> None:
    """Direct call into `_strip_fenced_code_blocks` itself: CommonMark's own
    rule is that a closing fence needs the same character repeated *at
    least* as many times as the opening one, not an exact-length match --
    a live adversarial round found an earlier backreference-based version
    only recognized an exact-length close, letting a longer one defeat it.
    `close_len` is always `>= open_len` by construction (`extra_close_len`
    is a non-negative offset), so every generated example is a valid
    CommonMark close, never filtered away by an `assume`/early-return that
    would leave this property under-exercised."""
    close_len = open_len + extra_close_len
    open_fence = fence_char * open_len
    close_fence = fence_char * close_len
    marker = f"MARKER_START{inner}MARKER_END"  # a sentinel `inner` alone can't coincidentally match "before"/"after"
    text = f"before\n{open_fence}\n{marker}\n{close_fence}\nafter\n"
    stripped = gate._strip_fenced_code_blocks(text)
    assert "before" in stripped
    assert "after" in stripped
    assert marker not in stripped


@_PROPERTIES
@given(
    fence_char=st.sampled_from(("`", "~")), inner=st.text(max_size=100).filter(lambda s: "`" not in s and "~" not in s)
)
def test_strip_fenced_code_blocks_direct_call_unclosed_fence_extends_to_eof(fence_char: str, inner: str) -> None:
    """Direct call: an opened but never-closed fence (a plausible authoring
    slip, not only a deliberate attack -- a live adversarial round found
    this defeated an earlier version) extends to end-of-document, per
    CommonMark, rather than leaving its own contents unstripped."""
    fence = fence_char * 3
    marker = f"MARKER_START{inner}MARKER_END"  # a sentinel `inner` alone can't coincidentally match "before"
    text = f"before\n{fence}\n{marker}"
    stripped = gate._strip_fenced_code_blocks(text)
    assert "before" in stripped
    assert marker not in stripped


_TRAILING_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")), max_size=200).filter(
    lambda s: "independent review verdict" not in s.lower()
)


@_PROPERTIES
@given(sha=_SHAS, other_sha=_SHAS, trailing=_TRAILING_TEXT)
def test_last_section_from_never_crosses_the_next_heading(sha: str, other_sha: str, trailing: str) -> None:
    """`_last_section_from` (used by `parse_verdict` to isolate the matched
    heading's own section) never lets a field belonging to a later,
    different section leak into the current one -- checked across
    generated trailing content that itself might coincidentally contain
    `##`-shaped text or verdict-field-shaped lines."""
    body = (
        f"## Independent review verdict\n\n"
        f"- Verdict: CLEAN\n- Verified commit: {sha}\n\n"
        f"## Some later section\n\n"
        f"- Verdict: CLEAN\n- Verified commit: {other_sha}\n{trailing}\n"
    )
    verdict = gate.parse_verdict(body)
    assert verdict.commit == sha


_HEADING_FREE_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")), max_size=100).filter(
    lambda s: not _ANY_HEADING_RE.search(s)
)


@_PROPERTIES
@given(before=_HEADING_FREE_TEXT, after=_HEADING_FREE_TEXT)
def test_last_section_from_direct_call_stops_at_next_heading(before: str, after: str) -> None:
    """Direct call into `_last_section_from` itself (not only via
    `parse_verdict`): the returned slice from `start` never includes any
    `##`-shaped heading line or anything past it, across generated
    heading-free `before`/`after` content."""
    marker = "## Next heading here\nunreachable content"
    text = f"{before}\n{marker}\n{after}" if after else f"{before}\n{marker}"
    start = len(before) + 1  # just after "before\n"
    section = gate._last_section_from(text, start)
    assert "Next heading here" not in section
    assert "unreachable content" not in section


_ARBITRARY_HEADING_TEXT = (
    st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="\n\r"), min_size=1, max_size=60
    )
    .map(str.strip)
    .filter(lambda s: len(s) > 0)
)
_HEADING_LEVEL_MARKS = ("#", "##", "###", "####", "#####", "######")


@_PROPERTIES
@given(
    text=_ARBITRARY_HEADING_TEXT,
    level=st.sampled_from(_HEADING_LEVEL_MARKS),
    indent=st.integers(min_value=0, max_value=3),
)
def test_heading_pattern_matches_a_live_heading_using_that_exact_text(text: str, level: str, indent: int) -> None:
    """`gitapex_scan_independent_review_heading_drift.py` calls
    `heading_pattern(text)` for text it does not control the shape of
    (this gate's own canonical/retired marker strings) -- across
    generated heading text, level (1-6 `#`), and CommonMark's own 0-3-
    space indentation allowance, a well-formed live heading using exactly
    that text is always matched."""
    body = f"{' ' * indent}{level} {text}\n"
    assert gate.heading_pattern(text).search(body) is not None


_CASE_STABLE_HEADING_TEXT = _ARBITRARY_HEADING_TEXT.filter(lambda s: all(len(c.swapcase()) == 1 for c in s))


@_PROPERTIES
@given(text=_CASE_STABLE_HEADING_TEXT, level=st.sampled_from(_HEADING_LEVEL_MARKS))
def test_heading_pattern_is_case_insensitive(text: str, level: str) -> None:
    """The sibling gate's own `_HEADING_RE` is case-insensitive (module
    docstring); `heading_pattern` builds that same shape for arbitrary
    text, so a same-meaning casing change to the live heading must still
    match -- confirmed to have teeth: dropping `re.IGNORECASE` from
    `heading_pattern`'s own `re.compile` call makes this property FAIL on
    every generated example whose text contains a cased letter.

    Restricted to case-stable text (`str.swapcase()` maps each character
    to exactly one character): Python's `str.swapcase()` is not
    length-preserving for every character (e.g. German sharp-S `'ß'`
    swapcases to the two-character `'SS'`), where `re.IGNORECASE`
    matches per-character and cannot follow a multi-character case
    fold -- confirmed live generating this exact failure -- a property of
    `str.swapcase()`, not a `heading_pattern` defect."""
    body = f"{level} {text.swapcase()}\n"
    assert gate.heading_pattern(text).search(body) is not None


@_PROPERTIES
@given(
    text=_ARBITRARY_HEADING_TEXT, level=st.sampled_from(_HEADING_LEVEL_MARKS), trailing=st.text(min_size=1, max_size=20)
)
def test_heading_pattern_end_anchor_rejects_trailing_prose(text: str, level: str, trailing: str) -> None:
    """End-anchored (module docstring's own CommonMark rationale): a live
    heading line carrying `text` plus *more* text after it (an
    illustrative example referencing the phrase, not a genuine heading
    consisting of exactly that phrase) is never matched -- confirmed to
    have teeth: relaxing `heading_pattern`'s own trailing `[ \\t]*$` to
    `.*$` makes this property FAIL on every generated example."""
    assume("\n" not in trailing)
    body = f"{level} {text} {trailing}\n"
    assert gate.heading_pattern(text).search(body) is None


@_PROPERTIES
@given(
    text=_ARBITRARY_HEADING_TEXT,
    level=st.sampled_from(_HEADING_LEVEL_MARKS),
    extra_indent=st.integers(min_value=1, max_value=6),
)
def test_heading_pattern_rejects_four_or_more_spaces_of_indentation(text: str, level: str, extra_indent: int) -> None:
    """CommonMark: 4+ leading spaces makes the line an indented code
    block, never a live heading, regardless of the text `heading_pattern`
    was built for -- confirmed to have teeth: widening
    `heading_pattern`'s own `[ ]{0,3}` to `[ \\t]*` makes this property
    FAIL on every generated example."""
    body = f"{' ' * (3 + extra_indent)}{level} {text}\n"
    assert gate.heading_pattern(text).search(body) is None

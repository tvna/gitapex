"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_independent_review_pending.py`` (issue #1311,
closing issue #1178's own ``detection-logic-property-coverage`` gap for
this new module's ``_HEADING_RE``/``_FENCED_BLOCK_RE``/``_VERDICT_RE``/
``_COMMIT_RE`` module-level compiles and the ``_last_section_from``/
``parse_verdict`` functions).

Issue #1343 briefly extended this file with property tests for a public
``heading_pattern()`` function, added to this module so
``gitapex_scan_independent_review_heading_drift.py`` could reuse its
ATX-heading regex shape for arbitrary text -- reverted (both the
function and these tests) once a reuse/simplification review found the
call that justified making it public never actually happened (see that
module's own history), leaving a public function with no caller. One
property survives, adapted to exercise ``_HEADING_RE`` directly instead:
case-insensitivity of the heading text itself, which no pre-existing
test covered (only the Verdict/commit field values' own casing was
pinned).

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
from hypothesis import given, settings
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

    Confirmed to have teeth: removing `strip_fenced_code_blocks`'s call
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
    """Direct call into `strip_fenced_code_blocks` itself: CommonMark's own
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
    stripped = gate.strip_fenced_code_blocks(text)
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
    stripped = gate.strip_fenced_code_blocks(text)
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


_HEADING_LEVEL_MARKS = ("#", "##", "###", "####", "#####", "######")


@_PROPERTIES
@given(level=st.sampled_from(_HEADING_LEVEL_MARKS))
def test_heading_re_is_case_insensitive(level: str) -> None:
    """`_HEADING_RE` is case-insensitive (module docstring); no
    pre-existing test exercised case-insensitivity of the heading text
    itself, only of the Verdict/commit field values' own casing (see
    `test_check_is_case_insensitive_on_verdict_and_commit` in
    tests/test_gitapex_gate_independent_review_pending.py). Confirmed to
    have teeth: dropping `re.IGNORECASE` from `_HEADING_RE`'s own
    `re.compile` call makes this property FAIL for every generated level.

    `CANONICAL_HEADING_TEXT` ("Independent review verdict") is plain
    ASCII, so `str.swapcase()` is safe here -- unlike arbitrary Unicode
    text, it maps every character to exactly one character, with no
    length-changing special case (e.g. German sharp-S `'ß'` swapcasing to
    the two-character `'SS'`) to work around."""
    body = f"{level} {gate.CANONICAL_HEADING_TEXT.swapcase()}\n"
    assert gate._HEADING_RE.search(body) is not None

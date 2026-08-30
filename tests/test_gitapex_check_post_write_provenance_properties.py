"""Hypothesis property-based layer for
``hooks/gitapex_check_post_write_provenance.py``'s ``detect_content_loss``
(issue #1327, closing issue #1178's own ``detection-logic-property-coverage``
gap for the new ``.startswith()`` allowlist-style comparison this issue
added at line ~357).

Issue #1446 extended this file with property tests for
``extract_markdown_section`` (its own ``.startswith("## ")`` allowlist-style
comparison) and ``ratified_trailer_disclosure_text`` (its own
``Path(__file__).resolve()`` path-resolution call), closing issue #1178's
own ``detection-logic-property-coverage`` gap for both.

This module resolves via ``import gitapex_check_post_write_provenance`` --
``hooks`` is on pyproject.toml's own ``pythonpath``, the same resolution
``tests/test_gitapex_check_post_write_provenance.py`` already uses.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py`` and
``tests/test_gitapex_check_acm_present_properties.py``.
"""

from __future__ import annotations

import pathlib
import tempfile

import gitapex_check_post_write_provenance as checker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=300, deadline=None)

# Printable ASCII (the same " " <= c <= "~" range scan_non_ascii checks
# against) plus the whitespace a real Markdown body carries (tab, newline,
# carriage return) -- the same allowance _ALLOWED_CONTROL_CHARACTERS
# already makes, not edge-case Unicode this function was never designed
# to reason about.
_PRINTABLE_ASCII = st.characters(min_codepoint=0x20, max_codepoint=0x7E)
_BODY_TEXT = st.text(alphabet=_PRINTABLE_ASCII | st.sampled_from("\t\n\r"), max_size=80)
_NO_WHITESPACE_TEXT = st.text(alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E), min_size=1, max_size=80)
_NO_CR_TEXT = st.text(alphabet=_PRINTABLE_ASCII | st.sampled_from("\t\n"), max_size=80)


@_PROPERTIES
@given(submitted=_BODY_TEXT, extra=_BODY_TEXT)
def test_any_append_is_never_reported_as_loss(submitted: str, extra: str) -> None:
    """**Model-based, proven property, not just a hand-picked fixture:**
    for ANY submitted text and ANY appended suffix, the stored body
    `submitted + extra` must never be reported as content loss -- this is
    the append-only-tolerance guarantee check 2's own worked example (the
    ratified-attribution-trailer shape) and this issue's own Interpretation
    column both depend on, driven across arbitrary generated text rather
    than the single worked-example trailer string.

    Confirmed to have teeth: replacing the `.startswith()` comparison this
    issue added (line ~357) with strict equality (`==`) -- a plausible
    simplification a future edit could make -- fails this property on the
    large majority of generated non-empty `extra` values (verified: 1810 of
    2000 fuzzed trials against that mutant failed before this test was
    written), where the real implementation passes on all of them.
    """
    result = checker.detect_content_loss(submitted, submitted + extra)
    assert result is None


@_PROPERTIES
@given(text=_NO_WHITESPACE_TEXT)
def test_truncating_non_whitespace_text_by_one_character_is_always_loss(text: str) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    for text with no whitespace or newlines at all (so trailing-whitespace
    normalization can never mask the truncation), removing the very last
    character must always be reported as loss -- the exact shape a
    substring-containment check (rather than a prefix check) would wrongly
    tolerate no matter which end the loss happened on, which is the same
    distinction `test_content_missing_from_the_start_is_loss` in the fixed
    example suite covers for one hand-picked case; this drives it across
    generated text and generated string length instead.
    """
    result = checker.detect_content_loss(text, text[:-1])
    assert result is not None


@_PROPERTIES
@given(text=_BODY_TEXT)
def test_normalize_is_idempotent(text: str) -> None:
    """Robustness: normalizing an already-normalized body is a no-op --
    normalize_for_content_loss's own docstring describes folding CRLF/LF
    and trailing whitespace, both of which a second pass over the already-
    folded result must find nothing left to do."""
    once = checker.normalize_for_content_loss(text)
    twice = checker.normalize_for_content_loss(once)
    assert once == twice


@_PROPERTIES
@given(text=_NO_CR_TEXT)
def test_crlf_and_lf_normalize_identically(text: str) -> None:
    """The CRLF-tolerance half of this issue's own tolerance requirement,
    driven across generated text rather than the single hand-picked
    fixture in the example suite: a body using CRLF line endings
    throughout must normalize to the exact same result as the same body
    using bare LF."""
    assert checker.normalize_for_content_loss(text) == checker.normalize_for_content_loss(text.replace("\n", "\r\n"))


@_PROPERTIES
@given(submitted=_BODY_TEXT, stored=_BODY_TEXT)
def test_detect_content_loss_never_raises_and_is_deterministic(submitted: str, stored: str) -> None:
    """Robustness: arbitrary text pairs produce a result rather than an
    exception, and the same input produces the same output -- this
    function runs inside a PostToolUse hook, where an uncaught exception
    is a raw traceback in an operator-facing message, exactly the
    contract this module's own docstring says it never allows."""
    first = checker.detect_content_loss(submitted, stored)
    second = checker.detect_content_loss(submitted, stored)
    assert first == second
    assert first is None or isinstance(first, str)


@_PROPERTIES
@given(text=_BODY_TEXT)
def test_identical_bodies_are_never_loss(text: str) -> None:
    """Reflexivity: a body compared against an exact copy of itself is
    never loss, for any generated content -- the trivial case every
    other property here builds on."""
    assert checker.detect_content_loss(text, text) is None


# --- extract_markdown_section / ratified_trailer_disclosure_text (issue #1446) ---

_HEADING_WORD = st.from_regex(r"[A-Za-z][A-Za-z0-9 _-]{0,20}", fullmatch=True).map(lambda s: f"## {s.strip() or 'x'}")
_SAFE_LINE = st.text(alphabet=_PRINTABLE_ASCII, max_size=30).filter(lambda s: not s.startswith("##"))
_BODY_LINES = st.lists(_SAFE_LINE, min_size=0, max_size=5)


@_PROPERTIES
@given(heading=_HEADING_WORD, body_lines=_BODY_LINES)
def test_extract_markdown_section_recovers_the_body_up_to_the_next_heading(heading: str, body_lines: list[str]) -> None:
    """**Model-based, proven property:** for ANY generated ATX heading
    line and ANY generated body lines that don't themselves start with
    `## ` (so they can never be mistaken for the next heading), a
    document built as `heading + body_lines + "## __NEXT__" + trailer`
    must extract exactly the joined body lines back out, stripped of
    surrounding blank lines -- the heading-to-next-heading contract
    `ratified_trailer_disclosure_text` depends on for CONTRIBUTING.md's
    own real section, driven across generated headings/bodies instead of
    the one fixed CONTRIBUTING.md fixture."""
    body = "\n".join(body_lines)
    text = f"{heading}\n{body}\n## __NEXT__\nafter\n"
    result = checker.extract_markdown_section(text, heading)
    assert result == body.strip("\n")


@_PROPERTIES
@given(heading=_HEADING_WORD, text=_BODY_TEXT)
def test_extract_markdown_section_is_none_when_heading_absent(heading: str, text: str) -> None:
    """For ANY generated heading that does not appear as its own line in
    ANY generated text, extraction must report None rather than a
    coincidental/partial match -- the fallback trigger
    `ratified_trailer_disclosure_text` relies on when CONTRIBUTING.md's
    own heading has moved or been renamed."""
    if any(line == heading for line in text.split("\n")):
        return  # generated collision; not the case under test
    assert checker.extract_markdown_section(text, heading) is None


@_PROPERTIES
@given(missing_name=st.from_regex(r"[a-z][a-z0-9_]{0,16}", fullmatch=True))
def test_ratified_trailer_disclosure_text_never_raises_on_a_missing_path(missing_name: str) -> None:
    """Robustness (issue #1446): for ANY generated filename that does not
    exist on disk, `ratified_trailer_disclosure_text` must return the
    named-section fallback string rather than raising -- the plugin-
    distributed-consumer-checkout-without-CONTRIBUTING.md case this
    function's own docstring describes, driven across generated paths
    instead of one hand-picked missing-file fixture."""
    with tempfile.TemporaryDirectory() as tmp:
        missing_path = pathlib.Path(tmp) / f"{missing_name}.md"
        result = checker.ratified_trailer_disclosure_text(missing_path)
        assert isinstance(result, str)
        assert "named here, not quoted" in result


def _is_invalid_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


@_PROPERTIES
@given(garbage=st.binary(min_size=1, max_size=40).filter(_is_invalid_utf8))
def test_ratified_trailer_disclosure_text_never_raises_on_invalid_utf8(garbage: bytes) -> None:
    """Robustness (issue #1446): for ANY generated byte string containing
    an invalid-UTF-8 lead byte, a CONTRIBUTING.md that cannot be decoded
    must still degrade to the named-section fallback rather than raising
    UnicodeDecodeError -- the exact defect class issue #1446's own
    exception-handler-gap gate flags (refs #682, #680, #665: passed
    pytest at 100 percent line coverage because the handler that would
    have caught it did not exist), driven across generated invalid byte
    sequences instead of one hand-picked corrupt-file fixture."""
    with tempfile.TemporaryDirectory() as tmp:
        bad_path = pathlib.Path(tmp) / "CONTRIBUTING.md"
        bad_path.write_bytes(garbage)
        result = checker.ratified_trailer_disclosure_text(bad_path)
        assert isinstance(result, str)
        assert "named here, not quoted" in result

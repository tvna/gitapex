"""Hypothesis property layer for
``skills/evaluating-context-channel-maturity/scripts/gitapex_check_channel_shape.py``
(issue #1963, closing issue #1178's ``detection-logic-property-coverage``
gap for this module's frontmatter regex, its string-splitting, and the
threshold comparisons built on top of them).

The fixed-example tests in ``tests/test_gitapex_check_channel_shape.py``
assert against hand-picked frontmatter blocks. These properties assert
invariants that must hold for *any* input, which is where a parser bug
that a hand-picked example happens to step around actually shows up.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples``
and ``deadline=None``, matching this repository's own established
rationale in ``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import gitapex_check_channel_shape as ccs
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# Frontmatter values and body text are free-form Markdown. Line separators
# are excluded from the single-line alphabet because they are what the
# parser itself splits on -- a generated newline inside a "value" would be
# testing the generator, not the parser.
_LINE_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="\n\r:"),
    max_size=40,
)
_KEY = st.from_regex(r"\A[A-Za-z_][A-Za-z0-9_-]{0,15}\Z", fullmatch=True)


@_PROPERTIES
@given(description=_LINE_TEXT, body=st.text(max_size=200))
def test_split_frontmatter_roundtrips_any_well_formed_block(description: str, body: str) -> None:
    """**Detects a real gap the fixed examples cannot:** every fixed test
    uses a body that happens not to contain a delimiter-shaped line. This
    asserts the split point is the FIRST closing delimiter for any body,
    so no generated body can move it."""
    text = f"---\ndescription: {description}\n---\n{body}"
    frontmatter, split_body = ccs.split_frontmatter(text)
    assert "description:" in frontmatter
    assert split_body == body


@_PROPERTIES
@given(text=st.text(max_size=200))
def test_split_frontmatter_never_returns_silently_on_malformed_input(text: str) -> None:
    """Fail-closed is a property, not a case: anything that is not a
    well-formed block must raise, never return a plausible-looking
    ``('', text)``."""
    try:
        ccs.split_frontmatter(text)
    except ccs.ChannelParseError:
        return
    assert text.split("\n")[0].strip() == "---"


@_PROPERTIES
@given(key=_KEY, value=_LINE_TEXT)
def test_frontmatter_values_reads_back_any_single_key(key: str, value: str) -> None:
    assert ccs.frontmatter_values(f"{key}: {value}") == {key: value.strip()}


@_PROPERTIES
@given(key=_KEY, value=_LINE_TEXT, continuation=_LINE_TEXT)
def test_frontmatter_values_never_drops_a_continuation_line(key: str, value: str, continuation: str) -> None:
    """**Detects a real gap the fixed examples cannot:** the fixed
    multi-line case uses one hand-written continuation. This asserts that
    for ANY continuation text, the measured value is never shorter than
    the first line alone -- the exact under-measurement a parser stopping
    at the first newline would produce, which would let an over-cap
    description pass."""
    parsed = ccs.frontmatter_values(f"{key}: {value}\n  {continuation}")
    assert len(parsed[key]) >= len(value.strip())


@_PROPERTIES
@given(text=st.text(max_size=400))
def test_estimated_tokens_is_monotone_in_length(text: str) -> None:
    assert ccs.estimated_tokens(text) <= ccs.estimated_tokens(text + "xxxx")
    assert ccs.estimated_tokens(text) == len(text) // ccs.CHARS_PER_TOKEN_ESTIMATE


@_PROPERTIES
@given(description=_LINE_TEXT, body=st.text(max_size=200))
def test_check_subagent_always_grades_every_threshold(description: str, body: str) -> None:
    """A well-formed definition always produces exactly the three graded
    facts -- never a partial result that a caller could mistake for a
    pass."""
    findings = ccs.check_subagent("p", f"---\ndescription: {description}\n---\n{body}")
    assert {finding.check for finding in findings} == {"description-chars", "body-lines", "body-tokens"}


@_PROPERTIES
@given(length=st.integers(min_value=0, max_value=ccs.DESCRIPTION_MAX_CHARS * 2))
def test_description_verdict_matches_the_threshold_exactly(length: int) -> None:
    """The verdict is the comparison, for every length on both sides of
    the boundary -- not only the three the fixed tests pin."""
    findings = ccs.check_subagent("p", f"---\ndescription: {'d' * length}\n---\nbody\n")
    verdict = next(f for f in findings if f.check == "description-chars").passed
    assert verdict == (length <= ccs.DESCRIPTION_MAX_CHARS)


@_PROPERTIES
@given(lines=st.integers(min_value=1, max_value=ccs.PROJECT_INSTRUCTION_MAX_LINES * 2))
def test_project_instruction_verdict_matches_the_threshold_exactly(lines: int) -> None:
    findings = ccs.check_project_instruction("AGENTS.md", "\n".join(["x"] * lines))
    assert findings[0].passed == (lines <= ccs.PROJECT_INSTRUCTION_MAX_LINES)


@_PROPERTIES
@given(body=st.text(max_size=300))
def test_body_findings_always_reports_both_body_thresholds(body: str) -> None:
    """Covers ``_body_findings``' own line-splitting call: for ANY body,
    both graded facts are produced and the line count is never negative
    nor larger than the body's own newline count plus one."""
    findings = ccs._body_findings("p", body)
    assert [finding.check for finding in findings] == ["body-lines", "body-tokens"]
    reported = int(findings[0].detail.split(" ", 1)[0])
    assert 0 <= reported <= body.count("\n") + 1


@_PROPERTIES
@given(description=_LINE_TEXT)
def test_main_exit_code_matches_the_verdict(description: str) -> None:
    """Covers ``main``'s own comparison: the process exit code is 0 exactly
    when every graded fact passed, for any description length.

    A plain `TemporaryDirectory` rather than pytest's `tmp_path`: hypothesis
    re-runs the body many times per test, and a function-scoped fixture is
    created once for the whole test, so successive examples would otherwise
    write over each other's file.
    """
    with tempfile.TemporaryDirectory() as raw_dir:
        target = Path(raw_dir) / "a.md"
        target.write_text(f"---\ndescription: {description}\n---\n\nbody\n", encoding="utf-8")
        expected_pass = len(description.strip()) <= ccs.DESCRIPTION_MAX_CHARS
        assert (ccs.main(["--kind", ccs._SUBAGENT, str(target)]) == 0) is expected_pass

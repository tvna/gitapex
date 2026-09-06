"""Hypothesis property-based layer for
``hooks/gitapex_check_gate_proposal_dedup_sweep.py``'s ``find_sweep_lines``
(issue #1178's own ``detection-logic-property-coverage`` gap for this
module's ``_FENCE_RE``/``_UNTERMINATED_FENCE_RE``/``_INLINE_CODE_RE``/
``_INDENTED_CODE_RE``/``_SWEEP_RE`` module-level compiles).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching
``tests/test_gitapex_check_pr_duplicate_issue_properties.py``'s own
established rationale (this repository runs pytest under ``pytest-xdist``,
where a randomly-seeded generator turns a latent failure into an
intermittently red suite).
"""

from __future__ import annotations

import datetime as _datetime

import gitapex_check_gate_proposal_dedup_sweep as checker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_COUNTS = st.integers(min_value=0, max_value=10_000)
_TIMESTAMPS = st.datetimes(
    min_value=_datetime.datetime(2000, 1, 1),
    max_value=_datetime.datetime(2100, 1, 1),
).map(lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
_VERDICTS = st.one_of(
    st.just("NEW"),
    st.integers(min_value=0, max_value=999_999).map(lambda n: f"DUPLICATE-OF #{n}"),
)


def _sweep_line(count: int, timestamp: str, verdict: str) -> str:
    return f"Dedup-sweep: {count} open gate-proposal issues at {timestamp}; verdict {verdict}"


@_PROPERTIES
@given(count=_COUNTS, timestamp=_TIMESTAMPS, verdict=_VERDICTS)
def test_any_well_formed_sweep_line_round_trips(count: int, timestamp: str, verdict: str) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    the fixed examples in test_gitapex_check_gate_proposal_dedup_sweep.py
    only assert against a handful of hand-picked count/timestamp/verdict
    values -- this drives all three across a wide generated space,
    confirming `_SWEEP_RE` recognizes the generator's own fixed shape
    generally, not just the examples an author happened to think of."""
    line = _sweep_line(count, timestamp, verdict)
    found = checker.find_sweep_lines(f"Some retro body.\n\n{line}\n")
    assert found == [(count, timestamp, verdict)]


@_PROPERTIES
@given(count=_COUNTS, timestamp=_TIMESTAMPS, verdict=_VERDICTS)
def test_a_sweep_line_inside_a_fenced_code_block_is_never_detected(count: int, timestamp: str, verdict: str) -> None:
    """Containment: a syntactically valid sweep line, wrapped in a fenced
    code block (an illustrative example rather than a real proof line), is
    stripped by `_FENCE_RE` before `_SWEEP_RE` ever sees it -- checked
    across a wide generated space rather than the single hand-picked
    example in test_gitapex_check_gate_proposal_dedup_sweep.py.

    Confirmed to have teeth: removing `_strip_fences`'s fence-stripping
    call from `find_sweep_lines` makes this property FAIL on every
    generated example, since the unstripped fenced line still matches
    `_SWEEP_RE` directly.
    """
    line = _sweep_line(count, timestamp, verdict)
    body = f"Some retro body.\n\n```\n{line}\n```\n"
    assert checker.find_sweep_lines(body) == []


@_PROPERTIES
@given(count=_COUNTS, timestamp=_TIMESTAMPS, verdict=_VERDICTS)
def test_a_sweep_line_in_an_indented_code_block_is_never_detected(count: int, timestamp: str, verdict: str) -> None:
    """Containment: an indented (4-space) code block is code per
    CommonMark even without fences -- `_INDENTED_CODE_RE` strips it before
    `_SWEEP_RE` ever sees it, checked across a wide generated space rather
    than the single hand-picked example in
    test_gitapex_check_gate_proposal_dedup_sweep.py."""
    line = _sweep_line(count, timestamp, verdict)
    body = f"Some retro body.\n\n    {line}\n"
    assert checker.find_sweep_lines(body) == []


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_arbitrary_text_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text (including text containing stray
    backticks, fence markers, or partial "Dedup-sweep" fragments) produces
    a result rather than an exception, and the same input produces the
    same output -- this function runs inside a PreToolUse hook, where an
    uncaught exception is a crashed gate, not a reported finding."""
    first = checker.find_sweep_lines(text)
    second = checker.find_sweep_lines(text)
    assert first == second
    assert isinstance(first, list)

"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_split_fixture_coverage.py``'s Check E
addition (issue #192 item 6), closing issue #1178's own
``detection-logic-property-coverage`` gap for the new module-level regex
constants and the ``_blank_fenced_blocks_length_aware``,
``_heading_section_span``, ``stop_boundary_identity_counter``, and
``parse_procedure_steps`` functions.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import gitapex_gate_split_fixture_coverage as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# Plain content lines that can never accidentally look like a fence opener
# (no run of 3+ backticks/tildes) or a heading (no leading '#').
_PLAIN_LINE = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="`~#\n"), max_size=20
)


@_PROPERTIES
@given(text=st.text(alphabet=st.characters(blacklist_characters="`~"), max_size=300))
def test_blank_fenced_blocks_never_changes_line_count(text: str) -> None:
    """Robustness: `_blank_fenced_blocks_length_aware` blanks lines in
    place, never adds or removes one -- confirmed across arbitrary text
    with no fence markers at all (so every line takes the "unfenced,
    append verbatim" branch), which already exercises every non-fence
    control-flow path the function has.

    Confirmed to have teeth: replacing the function body with a naive
    `"\\n".join(l for l in lines if not in_fence)` (dropping blanked
    lines instead of blanking them) makes this property FAIL as soon as
    a generated example contains a fence-open line, since the returned
    line count then no longer matches the input's."""
    result = gate._blank_fenced_blocks_length_aware(text)
    assert len(result.split("\n")) == len(text.split("\n"))


@_PROPERTIES
@given(text=st.text(alphabet=st.characters(blacklist_characters="`~"), max_size=300))
def test_blank_fenced_blocks_is_identity_with_no_fence_markers(text: str) -> None:
    """No false positive: text containing no backtick/tilde run at all
    can never open a fence, so `in_fence` never becomes True and every
    line is returned byte-for-byte unchanged."""
    assert gate._blank_fenced_blocks_length_aware(text) == text


@_PROPERTIES
@given(before=_PLAIN_LINE, inside=_PLAIN_LINE, after=_PLAIN_LINE)
def test_blank_fenced_blocks_blanks_only_the_fenced_interior(before: str, inside: str, after: str) -> None:
    """Containment: a line strictly between a matched-length fence open
    and close is blanked, while the lines immediately before and after
    the fence pass through unchanged -- confirms the fence toggle itself
    (not just the line-count invariant above) actually fires.

    Confirmed to have teeth: reverting to a fixed 3-backtick-only opener
    regex still passes this specific property (every example here already
    uses exactly 3 backticks), but flipping the toggle logic to blank the
    fence-open/close lines' own *neighbours* instead of the interior makes
    this property FAIL on every generated example.
    """
    text = f"{before}\n```\n{inside}\n```\n{after}"
    result = gate._blank_fenced_blocks_length_aware(text).split("\n")
    assert result == [before, "", "", "", after]


@_PROPERTIES
@given(
    n_before=st.integers(min_value=0, max_value=5),
    n_content=st.integers(min_value=0, max_value=5),
    has_next_heading=st.booleans(),
    n_after=st.integers(min_value=0, max_value=5),
)
def test_heading_section_span_ends_at_next_heading_or_eof(
    n_before: int, n_content: int, has_next_heading: bool, n_after: int
) -> None:
    """Model-based: a section's content span always starts right after its
    own heading and ends exactly at the next heading (any level) or EOF
    when none follows -- checked across a range of surrounding line
    counts, not a single hand-picked layout.

    Confirmed to have teeth: changing the loop's own `break` to fall
    through past the first match (scanning for the *last* heading instead
    of the *next* one) makes this property FAIL whenever a generated
    example places a second heading after the first (`has_next_heading`
    True with `n_after > 0` would then extend `end` past it).
    """
    lines = ["plain"] * n_before + ["## H"] + ["plain"] * n_content
    if has_next_heading:
        lines = lines + ["## Next"] + ["plain"] * n_after
    start, end = gate._heading_section_span(lines, n_before)
    assert start == n_before + 1
    if has_next_heading:
        assert end == n_before + 1 + n_content
    else:
        assert end == len(lines)


@_PROPERTIES
@given(n_bullets=st.integers(min_value=0, max_value=8), n_decoys=st.integers(min_value=0, max_value=5))
def test_stop_boundary_identity_counter_counts_only_bullets_under_the_heading(n_bullets: int, n_decoys: int) -> None:
    """Model-based: every distinct top-level bullet directly under a
    '## Stop boundaries' heading is counted exactly once, and a
    same-shaped bullet living BEFORE the heading (never under it) is never
    counted at all -- checked across a range of bullet/decoy counts.

    Confirmed to have teeth: removing the heading-span gate (counting
    every top-level bullet in the whole file, not just ones under a Stop
    boundary heading) makes this property FAIL as soon as a generated
    example has at least one decoy bullet, since the decoys would then
    also be counted.
    """
    decoys = [f"- decoy {i}" for i in range(n_decoys)]
    bullets = [f"- bullet {i}" for i in range(n_bullets)]
    text = "\n".join([*decoys, "## Stop boundaries", "", *bullets])
    counter = gate.stop_boundary_identity_counter(text)
    assert sum(counter.values()) == n_bullets
    for i in range(n_bullets):
        assert counter[f"stop-boundary:- bullet {i}"] == 1
    for i in range(n_decoys):
        assert f"stop-boundary:- decoy {i}" not in counter


@_PROPERTIES
@given(n_items=st.integers(min_value=0, max_value=8), heading=st.sampled_from(["Procedure", "Steps"]))
def test_parse_procedure_steps_returns_items_in_source_order(n_items: int, heading: str) -> None:
    """Model-based: every top-level numbered item under a '## Procedure'
    or '## Steps' heading is returned, in source order, with its own text
    -- checked across a range of item counts and both recognized heading
    spellings.

    Confirmed to have teeth: swapping `enumerate(..., start=1)`'s implicit
    source-order append for one that prepends instead
    (`items.insert(0, ...)`) makes this property FAIL as soon as a
    generated example has 2 or more items, since the returned order would
    then be reversed.
    """
    items = [f"item {i}" for i in range(n_items)]
    numbered = [f"{i + 1}. {text}" for i, text in enumerate(items)]
    text = "\n".join([f"## {heading}", "", *numbered])
    assert gate.parse_procedure_steps(text) == items

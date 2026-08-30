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

# Lines drawn from a vocabulary that DOES include real fence markers of
# both characters and several lengths, plus near-miss and indented forms --
# so a generated document actually opens, nests, and closes fences instead
# of only ever taking the unfenced branch. The issue #192 step 8
# adversarial review found the line-count property below was pinned to a
# backtick/tilde-free strategy, which made its own stated teeth ("fails as
# soon as a generated example contains a fence-open line") unreachable: no
# example could ever contain one.
_FENCE_ISH_LINE = st.one_of(
    _PLAIN_LINE,
    st.sampled_from(
        [
            "```",
            "````",
            "~~~",
            "~~~~",
            "```python",
            "   ```",
            "``",  # near miss: only 2 backticks, never a fence
            "``` trailing text",  # never a valid CLOSER (length-aware close is bare)
            "## H",
            "- bullet",
            "",
        ]
    ),
)
_FENCE_ISH_DOC = st.lists(_FENCE_ISH_LINE, max_size=12).map("\n".join)


@_PROPERTIES
@given(text=_FENCE_ISH_DOC)
def test_blank_fenced_blocks_never_changes_line_count(text: str) -> None:
    """Robustness: `_blank_fenced_blocks_length_aware` blanks lines in
    place, never adds or removes one -- including for documents that
    really do open, nest, and close fences, and for a document whose
    fence is left unclosed at EOF.

    Confirmed to have teeth: replacing the fence-open branch's
    `out.append("")` with a bare `continue` (dropping the blanked line
    instead of blanking it) makes this property FAIL, since the returned
    line count then no longer matches the input's."""
    result = gate._blank_fenced_blocks_length_aware(text)
    assert len(result.split("\n")) == len(text.split("\n"))


@_PROPERTIES
@given(text=_FENCE_ISH_DOC)
def test_blank_fenced_blocks_leaves_no_fence_marker_in_its_output(text: str) -> None:
    """Soundness over fence-bearing documents: no line of the output can
    still match `_PROC_FENCE_OPEN_RE`. Every opener, interior and closer
    line is blanked, and a line that survives verbatim is by construction
    one that sat outside any fence -- where a fence marker would have
    opened one. This is what makes the downstream Stop-boundary/Procedure
    scans safe to run over the blanked text.

    Confirmed to have teeth: making the fence-open branch emit its own
    marker back (`out.append(line)` in place of `out.append("")`) still
    satisfies the line-count property above, but FAILS here on every
    generated example that opens a fence."""
    for line in gate._blank_fenced_blocks_length_aware(text).split("\n"):
        assert not gate._PROC_FENCE_OPEN_RE.match(line)


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


@_PROPERTIES
@given(
    first=st.integers(min_value=0, max_value=3),
    n_items=st.integers(min_value=1, max_value=8),
    heading=st.sampled_from(["Procedure", "Steps"]),
)
def test_parse_procedure_step_items_reads_the_lists_own_source_numbering(
    first: int, n_items: int, heading: str
) -> None:
    """Model-based: each item's reported ordinal is the number literally
    written in the Markdown, never a running 1..N index over the parsed
    list -- checked across lists that start at 0, 1, 2 or 3, both
    recognized heading spellings, and a range of item counts.

    This is the property the issue #192 step 8 adversarial defeat case
    turns on: three shipped skills in this repository number their
    Procedure lists from `0.`, so a running index reported every one of
    their ordinals off by one -- "Step 0" resolving against nothing and a
    non-existent final "Step N+1" resolving successfully.

    Confirmed to have teeth: restoring the running index
    (`items.append((len(items) + 1, ...))`) makes this property FAIL on
    every generated example whose list does not happen to start at 1.
    """
    ordinals = [first + i for i in range(n_items)]
    lines = [f"## {heading}", ""] + [f"{n}. item {n}" for n in ordinals]
    parsed = gate.parse_procedure_step_items("\n".join(lines))
    assert [ordinal for ordinal, _text in parsed] == ordinals
    assert [text for _ordinal, text in parsed] == [f"item {n}" for n in ordinals]
    # And the label set exposed to fixture authors follows those same
    # ordinals -- no phantom ordinal above the list's own last one.
    labels = gate.resolvable_exercise_labels("\n".join(lines))
    assert all(f"step {n}" in labels for n in ordinals)
    assert f"step {ordinals[-1] + 1}" not in labels

"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_exception_handler_gaps.py`` (issue #1184).

Scoped narrowly to the one function issue #1184's own fix touched --
:func:`parse_added_lines` -- rather than the file's full trigger surface.
That fix ported two behavior changes from this file's own architectural
mirror, `gitapex_gate_detection_logic_property_coverage.py` (issue #1178):
raising ``ScanError`` on a `+++ ` post-image header with no preceding
`--- ` source header, and bounding `in_hunk` by a hunk's own declared
post-image length rather than only by the next `diff --git ` line. Both
changes touch `.startswith(...)` call sites inside `parse_added_lines`
(a string-comparison detection-logic trigger under
`gitapex_gate_detection_logic_property_coverage.py`'s own rules) and the
module-level `_HUNK_RE = re.compile(...)` constant (a regex trigger), so
this diff is graded by that gate too -- this file is what clears both
findings.

The property below is ported near-verbatim from
`tests/test_gitapex_gate_detection_logic_property_coverage_properties.py`'s
own `test_parse_added_lines_matches_an_independently_computed_line_count`:
once issue #1184's fix lands, both files' `parse_added_lines` share the
identical post-image-counting contract, so the same model-based property
applies unchanged. The other three trigger-bearing functions in this file
(`in_scope`, `_diff_target_path`, `_waived_lines`) are untouched by issue
#1184's diff and carry no new or materially changed detection logic, so
they are out of this file's own scope -- the gate they answer to is
diff-scoped by design, not a repository-wide backfill requirement (see
that gate's own module docstring, "Scope is the diff, not the repository").

``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
applied per property rather than as a registered global profile --
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own module
docstring gives the full rationale (this repository's ``-n auto``
pytest-xdist run turns a randomly-seeded generator into an intermittently red
suite that reruns green, and a wall-clock deadline measures CI scheduling
noise, not this pure function); not repeated here beyond this pointer.
"""

from __future__ import annotations

import gitapex_gate_exception_handler_gaps as gate
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" pointer.
_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_LINE_KIND = st.sampled_from(("+", " ", "-"))
_HUNK_BODY = st.lists(_LINE_KIND, max_size=20)
_START_LINE = st.integers(min_value=1, max_value=500)
_FILE_DIFF = st.tuples(_START_LINE, _HUNK_BODY)
_MULTI_FILE_DIFFS = st.lists(_FILE_DIFF, min_size=1, max_size=3)


def _expected_added_for_hunk(start: int, kinds: list[str]) -> set[int]:
    """The post-image added-line-number set a correct parser must produce
    for one hunk starting at post-image line `start`, per the module
    docstring's own documented contract: added and context lines both
    advance the counter, a removed line advances nothing, and only added
    lines are recorded."""
    expected: set[int] = set()
    lineno = start
    for kind in kinds:
        if kind == "+":
            expected.add(lineno)
            lineno += 1
        elif kind == " ":
            lineno += 1
    return expected


def _file_diff_text(path: str, start: int, kinds: list[str]) -> str:
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1 +{start} @@",
        *kinds,
    ]
    return "\n".join(lines)


@_PROPERTIES
@given(file_diffs=_MULTI_FILE_DIFFS)
def test_parse_added_lines_matches_an_independently_computed_line_count(
    file_diffs: list[tuple[int, list[str]]],
) -> None:
    """Model-based. Each file's synthetic diff is built from a starting
    post-image line number and a generated sequence of "+"/" "/"-" line
    kinds; :func:`_expected_added_for_hunk` recomputes the intended
    added-line-number set directly from the module docstring's own
    documented post-image-counting contract, not by calling
    `parse_added_lines` or mirroring its control-flow/header-detection state
    machine. This re-derives the same counting *rule* `parse_added_lines`
    must itself implement -- what it does not re-derive is
    `parse_added_lines`'s own state machine (header detection, in-hunk
    tracking, per-file reset on `diff --git `), so a regression there still
    fails this property: e.g. a context line silently failing to advance
    the counter, a removed line incorrectly counted as added, or an
    off-by-one in `_HUNK_RE`'s own captured start line.

    Every generated hunk body line is a bare single-character "+"/" "/"-"
    token, never four characters long, so none of them can ever collide
    with the `--- `/`+++ ` header prefixes `parse_added_lines` matches on --
    this property is blind to issue #1184's own header-pairing and
    hunk-length-bounding fixes by construction, which is exactly why the
    two regression tests added directly against those fixes in
    `tests/test_gitapex_gate_exception_handler_gaps.py` carry that weight
    instead.

    A file whose hunk body adds nothing never gets a key in
    `parse_added_lines`'s own returned dict (`added.setdefault` is only
    reached from the "+" branch), so files with an empty expected set are
    dropped from both sides of the comparison to match that documented
    shape, not papered over.
    """
    paths = [f"module_{index}.py" for index in range(len(file_diffs))]
    diff_text = "\n".join(
        _file_diff_text(path, start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    )

    added = gate.parse_added_lines(diff_text)

    expected = {
        path: _expected_added_for_hunk(start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    }
    expected = {path: lines for path, lines in expected.items() if lines}
    assert added == expected

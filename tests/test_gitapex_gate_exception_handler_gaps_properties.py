"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_exception_handler_gaps.py`` (issue #1184,
extended by issue #1193).

Scoped narrowly to the functions each fix actually touched, not the file's
full trigger surface -- the gate this file answers to is diff-scoped by
design, not a repository-wide backfill requirement (see that gate's own
module docstring, "Scope is the diff, not the repository"). Issue #1184's
own fix touched :func:`parse_added_lines`, porting two behavior changes
from this file's own architectural mirror,
`gitapex_gate_detection_logic_property_coverage.py` (issue #1178): raising
``ScanError`` on a `+++ ` post-image header with no preceding `--- ` source
header, and bounding `in_hunk` by a hunk's own declared post-image length
rather than only by the next `diff --git ` line. Both changes touch
`.startswith(...)` call sites inside `parse_added_lines` (a
string-comparison detection-logic trigger under
`gitapex_gate_detection_logic_property_coverage.py`'s own rules) and the
module-level `_HUNK_RE = re.compile(...)` constant (a regex trigger).

Issue #1193 later added a second function to this file's own scope:
:func:`_looks_like_real_header_pair`, ported from the same architectural
mirror, with its own two `.startswith(...)` call sites (string-comparison).

The first property below is ported near-verbatim from
`tests/test_gitapex_gate_detection_logic_property_coverage_properties.py`'s
own `test_parse_added_lines_matches_an_independently_computed_line_count`:
both files' `parse_added_lines` share the identical post-image-counting
contract, so the same model-based property applies unchanged. The second
is ported near-verbatim from that same file's own
`test_looks_like_real_header_pair_recognises_every_real_shape_and_rejects_the_rest`,
for the identical reason -- both files' `_looks_like_real_header_pair` are
byte-identical. The other two trigger-bearing functions in this file
(`in_scope`, `_waived_lines`) remain untouched by either issue's diff and
carry no new or materially changed detection logic, so they stay out of
this file's own scope.

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
import unidiff
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" pointer.
_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)


def _unidiff_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Issue #1316: an independent oracle for `parse_added_lines`'s own
    `{path: added-lines}` contract, computed by `unidiff`'s own parser --
    a genuinely different mechanism from this file's hand-rolled
    header/hunk state machine, unlike `_expected_added_for_hunk` below
    (which re-derives the same counting *rule* `parse_added_lines` must
    itself implement, not an independent parse). A file whose hunk body
    adds nothing is dropped, matching `parse_added_lines`'s own documented
    shape (`added.setdefault` is only reached from the "+" branch)."""
    result: dict[str, set[int]] = {}
    for patched_file in unidiff.PatchSet(diff_text):
        # `target_line_no` is `int | None` per unidiff's own stub, but is
        # always a real int for an added line -- only a removed line ever
        # carries `target_line_no is None`.
        added = {
            line.target_line_no
            for hunk in patched_file
            for line in hunk
            if line.is_added and line.target_line_no is not None
        }
        if added:
            result[patched_file.path] = added
    return result


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
    # Explicit, accurate pre- and post-image counts -- not the bare/
    # implicit-1 shorthand this helper used before issue #1193 -- since
    # `kinds` can contain any mix of "+"/" "/"-" lines, or none at all.
    # `parse_added_lines` now tracks both sides (issue #1193, this file's
    # own dual-counter fix) and rejects a hunk whose header's declared
    # count on either side does not match its own real body, so a still-
    # bare or post-image-only-accurate header here would make this
    # generator produce a malformed diff whenever `kinds` doesn't happen
    # to carry exactly one pre-image (" "/"-") or post-image ("+"/" ")
    # line, which `parse_added_lines` would then correctly raise
    # `ScanError` on -- not the counting behavior this property means to
    # exercise.
    pre_image_count = sum(1 for kind in kinds if kind != "+")
    post_image_count = sum(1 for kind in kinds if kind != "-")
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1,{pre_image_count} +{start},{post_image_count} @@",
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


# unidiff's own hunk parser cannot handle a zero/zero declared hunk with an
# empty body (`@@ -1,0 +1,0 @@` followed immediately by the next file's own
# `diff --git ` line) -- confirmed directly against the installed unidiff
# 1.0.0 (`UnidiffParseError: Hunk diff line expected: diff --git a/...`).
# Real `git diff` output never emits a hunk with nothing in it, so this is
# not a gap in the oracle's real-world coverage; the differential property
# below uses a non-empty-hunk-body variant of the shared strategy above so
# every generated diff stays within unidiff's own parseable shape. The
# empty-hunk-body case stays covered by the self-consistency property
# above, which needs no external parser.
_NON_EMPTY_HUNK_BODY = st.lists(_LINE_KIND, min_size=1, max_size=20)
_NON_EMPTY_FILE_DIFF = st.tuples(_START_LINE, _NON_EMPTY_HUNK_BODY)
_NON_EMPTY_MULTI_FILE_DIFFS = st.lists(_NON_EMPTY_FILE_DIFF, min_size=1, max_size=3)


@_PROPERTIES
@given(file_diffs=_NON_EMPTY_MULTI_FILE_DIFFS)
def test_parse_added_lines_matches_unidiffs_independent_parse(
    file_diffs: list[tuple[int, list[str]]],
) -> None:
    """Differential-oracle property (issue #1316). Compares
    `parse_added_lines`'s own `{path: added-lines}` output against
    `unidiff`'s own independent parse of the identical generated diff
    text -- a genuinely independent parser, catching a misattribution-
    class defect the sibling property above cannot, since that property
    recomputes the same post-image-counting *rule* `parse_added_lines`
    must itself implement, never an independent parse of the diff text
    itself. True-negative coverage across many well-formed generated
    diffs; the corresponding true-positive check (does this oracle catch
    the real header-misattribution defect class issue #1184/#1193 fixed)
    is recorded as a fixed regression case rather than a Hypothesis
    property, since it needs a specific adversarial input shape (a
    disguised header mid-hunk) this property's own generator does not
    construct -- see this file's own regression suite
    (`tests/test_gitapex_gate_exception_handler_gaps.py`) and this task's
    own commit message for that proof.
    """
    paths = [f"module_{index}.py" for index in range(len(file_diffs))]
    diff_text = "\n".join(
        _file_diff_text(path, start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    )
    assert gate.parse_added_lines(diff_text) == _unidiff_added_lines(diff_text)


# ---------------------------------------------------------------------------
# _looks_like_real_header_pair -- string-comparison (startswith, x2) trigger
# ---------------------------------------------------------------------------

_HEADER_PATH_TEXT = st.text(max_size=60)
_NOT_A_PREFIXED_TEXT = st.text(max_size=80).filter(lambda s: s != "/dev/null" and not s.startswith("a/"))
_NOT_B_PREFIXED_TEXT = st.text(max_size=80).filter(lambda s: s != "/dev/null" and not s.startswith("b/"))


@_PROPERTIES
@given(
    matching_path=_HEADER_PATH_TEXT,
    rename_source_path=_HEADER_PATH_TEXT,
    rename_target_path=_HEADER_PATH_TEXT,
    not_a_prefixed=_NOT_A_PREFIXED_TEXT,
    not_b_prefixed=_NOT_B_PREFIXED_TEXT,
)
def test_looks_like_real_header_pair_recognises_every_real_shape_and_rejects_the_rest(
    matching_path: str,
    rename_source_path: str,
    rename_target_path: str,
    not_a_prefixed: str,
    not_b_prefixed: str,
) -> None:
    """Ported from this file's own architectural mirror
    `gitapex_gate_detection_logic_property_coverage.py`. Model-based for
    every case. Each input pair is built to have a known answer by
    construction, not by recomputing `_looks_like_real_header_pair`'s own
    `a/`/`b/`/`/dev/null` formula:

    * A same-stem `a/<path>`/`b/<path>` pair is exactly the shape a real,
      unrenamed file's own header pair always has -- True.
    * `/dev/null` on either side alone (source for a new file, target for a
      deleted one) is a real header shape too -- True, independent of what
      the other side names.
    * A *different*-stem `a/<path1>`/`b/<path2>` pair is still real-shaped --
      a renamed file's own header pair never has matching stems, and the
      function's own docstring states plainly it is "deliberately silent on
      whether the two paths match." True.
    * `not_a_prefixed`/`not_b_prefixed` are built to structurally avoid both
      the `/dev/null` and `a/`/`b/`-prefixed shapes on their own side, so
      pairing either with anything real-shaped on the other side still makes
      the whole pair False -- ordinary hunk content (a changelog marker, a
      divider) never has this shape by construction, which is the exact
      property this function exists to tell apart from a real absorbed
      header.

    Real defect class this would catch: the `a/`/`b/`-prefix check or the
    `/dev/null` special case on either side being loosened or dropped -- e.g.
    a future change that starts requiring matching stems, which would
    silently stop catching a renamed file's own absorbed header pair, or one
    that drops the `/dev/null` case, which would silently stop catching an
    absorbed new-file or deleted-file header.
    """
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair("--- /dev/null", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", "+++ /dev/null") is True
    assert gate._looks_like_real_header_pair(f"--- a/{rename_source_path}", f"+++ b/{rename_target_path}") is True
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ b/{matching_path}") is False
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ {not_b_prefixed}") is False
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ {not_b_prefixed}") is False

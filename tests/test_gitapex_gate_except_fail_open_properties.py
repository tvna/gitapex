"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_except_fail_open.py`` (issue #1722, satisfying
``gitapex_gate_detection_logic_property_coverage.py``'s own coverage
requirement, issue #1178).

The first three properties below are ported near-verbatim from
`tests/test_gitapex_gate_exception_handler_gaps_properties.py`: this file's
own `parse_added_lines` and `_looks_like_real_header_pair` are verbatim ports
of that sibling gate's identically-named functions (same state machine, same
hardening -- see this gate's own module docstring), so the identical
properties apply unchanged. The rest are new -- covering `_diff_target_path`
(also a verbatim-ported function, per this gate's own module docstring, but
one the sibling's own property file has no property coverage for) and the
two functions this gate does not share with that sibling at all: `in_scope`
(a narrower, two-directory scope than the sibling's four) and `_waived_lines`
(byte-identical logic, but a distinct module-level `_WAIVER_RE`).

``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
matching every sibling property file's own "Reproducibility" convention
(`tests/test_gitapex_gate_metadata_outcome_lines_properties.py`'s own module
docstring gives the full rationale) -- not repeated here beyond this
pointer.
"""

from __future__ import annotations

import os

import gitapex_gate_except_fail_open as gate
import pytest
import unidiff
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" pointer.
#
# Issue #1316: the PR-blocking gate's own invocation (this default branch)
# stays pinned exactly as before -- fast and deterministic. A separate,
# scheduled, non-PR-blocking workflow can set GITAPEX_HYPOTHESIS_DEEP_SCAN=1
# to re-run these same properties with much higher, randomized exploration
# instead, matching every sibling property file's own identical switch.
_PROPERTIES = (
    settings(derandomize=False, max_examples=5000, deadline=None)
    if os.environ.get("GITAPEX_HYPOTHESIS_DEEP_SCAN") == "1"
    else settings(derandomize=True, max_examples=200, deadline=None)
)


# ---------------------------------------------------------------------------
# parse_added_lines -- regex (_HUNK_RE) and string-comparison (multiple
# .startswith() call sites) trigger, ported near-verbatim from
# gitapex_gate_exception_handler_gaps_properties.py
# ---------------------------------------------------------------------------

_LINE_KIND = st.sampled_from(("+", " ", "-"))
_HUNK_BODY = st.lists(_LINE_KIND, max_size=20)
_START_LINE = st.integers(min_value=1, max_value=500)
_FILE_DIFF = st.tuples(_START_LINE, _HUNK_BODY)
_MULTI_FILE_DIFFS = st.lists(_FILE_DIFF, min_size=1, max_size=3)


def _expected_added_for_hunk(start: int, kinds: list[str]) -> set[int]:
    """The post-image added-line-number set a correct parser must produce
    for one hunk starting at post-image line `start`: added and context
    lines both advance the counter, a removed line advances nothing, and
    only added lines are recorded."""
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
    """Model-based. Recomputes the intended added-line-number set directly
    from the documented post-image-counting contract, not by calling
    `parse_added_lines` or mirroring its own state machine -- so a
    regression there (a context line failing to advance the counter, a
    removed line miscounted as added, an off-by-one in `_HUNK_RE`'s own
    captured start line) still fails this property."""
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


def _unidiff_added_lines(diff_text: str) -> dict[str, set[int]]:
    """An independent oracle for `parse_added_lines`'s own `{path:
    added-lines}` contract, computed by `unidiff`'s own parser -- a
    genuinely different mechanism from this file's hand-rolled
    header/hunk state machine."""
    result: dict[str, set[int]] = {}
    for patched_file in unidiff.PatchSet(diff_text):
        added = {
            line.target_line_no
            for hunk in patched_file
            for line in hunk
            if line.is_added and line.target_line_no is not None
        }
        if added:
            result[patched_file.path] = added
    return result


# unidiff cannot parse a zero/zero declared hunk with an empty body -- see
# the sibling property file's own identical note. min_size=1 keeps every
# generated hunk within unidiff's own parseable shape.
_NON_EMPTY_HUNK_BODY = st.lists(_LINE_KIND, min_size=1, max_size=20)
_NON_EMPTY_FILE_DIFF = st.tuples(_START_LINE, _NON_EMPTY_HUNK_BODY)
_NON_EMPTY_MULTI_FILE_DIFFS = st.lists(_NON_EMPTY_FILE_DIFF, min_size=1, max_size=3)


@_PROPERTIES
@given(file_diffs=_NON_EMPTY_MULTI_FILE_DIFFS)
def test_parse_added_lines_matches_unidiffs_independent_parse(
    file_diffs: list[tuple[int, list[str]]],
) -> None:
    """Differential-oracle property: compares `parse_added_lines`'s own
    output against `unidiff`'s own independent parse of the identical
    generated diff text -- catches a misattribution-class defect the
    self-consistency property above cannot, since that one recomputes the
    same counting rule `parse_added_lines` must itself implement rather
    than independently parsing the diff text."""
    paths = [f"module_{index}.py" for index in range(len(file_diffs))]
    diff_text = "\n".join(
        _file_diff_text(path, start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    )
    assert gate.parse_added_lines(diff_text) == _unidiff_added_lines(diff_text)


# ---------------------------------------------------------------------------
# _looks_like_real_header_pair -- string-comparison (startswith, x2) trigger,
# ported near-verbatim from gitapex_gate_exception_handler_gaps_properties.py
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
    """Model-based for every case: a same-stem or `/dev/null`-carrying pair
    is real-shaped regardless of whether the two paths match (the function's
    own docstring states this plainly); a pair built to structurally avoid
    both the `/dev/null` and `a/`/`b/`-prefixed shapes on one side is not."""
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair("--- /dev/null", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", "+++ /dev/null") is True
    assert gate._looks_like_real_header_pair(f"--- a/{rename_source_path}", f"+++ b/{rename_target_path}") is True
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ b/{matching_path}") is False
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ {not_b_prefixed}") is False
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ {not_b_prefixed}") is False


# ---------------------------------------------------------------------------
# in_scope -- regex (_IN_SCOPE_RE.fullmatch) and string-comparison
# (.startswith("test_"), == "conftest.py") trigger
# ---------------------------------------------------------------------------

_STEM = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=20).filter(
    lambda s: not s.startswith("test_") and s != "conftest"
)
_IN_SCOPE_DIR = st.sampled_from([".github/scripts", "hooks"])
_OUT_OF_SCOPE_DIR = st.sampled_from(
    ["evals/scripts", "skills/a-skill/scripts", "docs", ".github/scripts/nested", "hooks/nested", "tests"]
)


@_PROPERTIES
@given(directory=_IN_SCOPE_DIR, stem=_STEM, is_test=st.booleans())
def test_in_scope_admits_every_in_scope_directory_except_test_files(directory: str, stem: str, is_test: bool) -> None:
    """Model-based: a `.py` file directly under either in-scope directory is
    graded, except one whose own basename starts with `test_` -- exactly the
    property `in_scope`'s own two directories/one exclusion rule states."""
    basename = f"test_{stem}.py" if is_test else f"{stem}.py"
    assert gate.in_scope(f"{directory}/{basename}") is not is_test


@_PROPERTIES
@given(directory=_IN_SCOPE_DIR)
def test_in_scope_excludes_conftest_py_in_every_in_scope_directory(directory: str) -> None:
    assert gate.in_scope(f"{directory}/conftest.py") is False


@_PROPERTIES
@given(directory=_OUT_OF_SCOPE_DIR, stem=_STEM)
def test_in_scope_excludes_every_directory_outside_the_two_named_ones(directory: str, stem: str) -> None:
    """A `.py` file anywhere other than directly under `.github/scripts/` or
    `hooks/` is never in scope -- including a nested subdirectory of either,
    which `_IN_SCOPE_RE`'s own `[^/]+` segments deliberately exclude."""
    assert gate.in_scope(f"{directory}/{stem}.py") is False


# ---------------------------------------------------------------------------
# _diff_target_path -- string-comparison (== "/dev/null", .startswith("b/"))
# trigger
# ---------------------------------------------------------------------------

_STRIP_INVARIANT_TEXT = st.text(max_size=60).filter(lambda s: s == s.strip())
_B_PREFIXED_PATH_TEXT = _STRIP_INVARIANT_TEXT.map(lambda s: f"b/{s}")
_NEITHER_B_PREFIXED_NOR_DEV_NULL_TEXT = _STRIP_INVARIANT_TEXT.filter(
    lambda s: s != "/dev/null" and not s.startswith("b/")
)


@_PROPERTIES
@given(path=_B_PREFIXED_PATH_TEXT)
def test_diff_target_path_strips_the_b_prefix_for_any_b_prefixed_text(path: str) -> None:
    assert gate._diff_target_path(path) == path[2:]


@_PROPERTIES
@given(path=_NEITHER_B_PREFIXED_NOR_DEV_NULL_TEXT)
def test_diff_target_path_raises_for_anything_not_b_prefixed_or_dev_null(path: str) -> None:
    with pytest.raises(gate.ScanError, match="not a plain b/-prefixed path"):
        gate._diff_target_path(path)


# The /dev/null case itself is a fixed-value assertion, not a property --
# tests/test_gitapex_gate_except_fail_open.py's own
# test_diff_target_path_returns_none_for_dev_null already covers it; no
# duplicate here (Step 8 independent-review dispatch, issue #1722).


# ---------------------------------------------------------------------------
# _waived_lines -- regex (_WAIVER_RE.search) trigger
# ---------------------------------------------------------------------------

_REASON = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=30).map(str.strip).filter(len)


@_PROPERTIES
@given(reason=_REASON, prefix_lines=st.integers(min_value=0, max_value=5))
def test_waived_lines_finds_a_real_trailing_comment_at_its_own_line(reason: str, prefix_lines: int) -> None:
    """Model-based: a real `# except-fail-open: WAIVED: <reason>` trailing
    comment is recorded at its own 1-based line number, regardless of how
    many ordinary statement lines precede it."""
    filler = "".join(f"x{i} = {i}\n" for i in range(prefix_lines))
    marker_line = prefix_lines + 1
    source = f"{filler}y = 1  # except-fail-open: WAIVED: {reason}\n"
    assert gate._waived_lines(source) == {marker_line}


@_PROPERTIES
@given(reason=_REASON)
def test_waived_lines_ignores_the_marker_inside_a_string_literal(reason: str) -> None:
    """The same marker text, spelled inside a string literal rather than a
    comment, is never recorded -- read through `tokenize`, a quoted marker
    is text, not a comment."""
    source = f'z = "# except-fail-open: WAIVED: {reason}"\n'
    assert gate._waived_lines(source) == set()

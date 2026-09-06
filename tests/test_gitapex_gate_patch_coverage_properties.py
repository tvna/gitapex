"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_patch_coverage.py`` (issue #1568). Covers
the functions in that file which, per this repository's own
``detection-logic-property-coverage`` gate (issue #1178), actually
contain a regex-, path-resolution-, or string-comparison-shaped call:
:func:`in_scope`, :func:`_diff_target_path`,
:func:`_looks_like_real_header_pair`, :func:`parse_added_lines`, and
:func:`_waived_lines`.

Ported from ``tests/test_gitapex_gate_function_body_test_coverage_properties.py``'s
own property suite for the identical (byte-for-byte copied) parser
functions -- `in_scope` is the one exception, adapted for this gate's own
`in_scope(path, sources)` signature (an explicit source-directory list,
rather than a single fixed regex).

Self-referential by design: this gate's own source file matches its own
``.github/scripts/*.py`` in-scope pattern (this gate grades itself) and
ALSO matches ``detection-logic-property-coverage``'s own narrower
``.github/scripts/gitapex_gate_*.py`` pattern.

Module-scope triggers need no dedicated property
--------------------------------------------------
The source file's own module level carries real triggers too (``REPO_ROOT
= pathlib.Path(__file__).resolve().parents[2]``, several ``re.compile(...)``
constants). None needs a property mentioning it by name: any
``@given``-decorated function in this file clears the ``"<module>"`` scope
as a side effect of existing at all -- the same rule the sibling gate's
own properties file already documents.

Reproducibility
----------------
``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
applied per property rather than as a registered global profile.
"""

from __future__ import annotations

import gitapex_gate_patch_coverage as gate
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)


# ---------------------------------------------------------------------------
# in_scope -- string-comparison (startswith/endswith) trigger
# ---------------------------------------------------------------------------

_IDENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=16)
_PATH_IDENT = _IDENT.filter(lambda s: not s.startswith("test_") and s != "conftest")
_SOURCE_DIR = st.sampled_from((".github/scripts", "skills/some-skill/scripts", "evals/scripts"))


@_PROPERTIES
@given(source=_SOURCE_DIR, other_source=_SOURCE_DIR, ident=_PATH_IDENT)
def test_in_scope_matches_its_own_scope_rules(source: str, other_source: str, ident: str) -> None:
    """Model-based. The expected answer for each path is known
    independently of `in_scope`'s own implementation: it follows directly
    from this gate's own module docstring "Scope" section (exact parent
    directory match, `.py` extension, `test_`/`conftest.py` excluded).

    Real defect classes this would catch: a regression from the exact
    parent-directory comparison to a path-prefix or glob-shaped match (the
    `other_source`-nested case), the `test_`/`conftest.py` exclusion being
    dropped, or the `.py`-suffix check being dropped.
    """
    assert gate.in_scope(f"{source}/{ident}.py", [source]) is True
    assert gate.in_scope(f"{source}/test_{ident}.py", [source]) is False
    assert gate.in_scope(f"{source}/conftest.py", [source]) is False
    assert gate.in_scope(f"{source}/{ident}.txt", [source]) is False
    assert gate.in_scope(f"{source}/nested/{ident}.py", [source]) is False
    if source != other_source:
        assert gate.in_scope(f"{other_source}/{ident}.py", [source]) is False


# ---------------------------------------------------------------------------
# _diff_target_path -- string-comparison (startswith) trigger
# ---------------------------------------------------------------------------

_NO_WHITESPACE_TEXT = st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), max_size=80)
_NON_B_PREFIXED_TEXT = st.text(max_size=80).filter(
    lambda s: s.strip() != "/dev/null" and not s.strip().startswith("b/")
)


@_PROPERTIES
@given(suffix=_NO_WHITESPACE_TEXT, other=_NON_B_PREFIXED_TEXT)
def test_diff_target_path_strips_b_prefix_and_rejects_everything_else(suffix: str, other: str) -> None:
    """Model-based for both halves, independent of `_diff_target_path`'s own
    implementation. Real defect class this would catch: the `b/`-prefix
    check or the `/dev/null` special case being loosened."""
    assert gate._diff_target_path("b/" + suffix) == suffix
    assert gate._diff_target_path("/dev/null") is None
    with pytest.raises(gate.ScanError):
        gate._diff_target_path(other)


# ---------------------------------------------------------------------------
# _looks_like_real_header_pair -- string-comparison (startswith, x2) trigger
# ---------------------------------------------------------------------------

_HEADER_PATH_TEXT = st.text(max_size=60)
_NOT_A_PREFIXED_TEXT = st.text(max_size=80).filter(lambda s: s != "/dev/null" and not s.startswith("a/"))
_NOT_B_PREFIXED_TEXT = st.text(max_size=80).filter(lambda s: s != "/dev/null" and not s.startswith("b/"))


@_PROPERTIES
@given(
    matching_path=_HEADER_PATH_TEXT,
    not_a_prefixed=_NOT_A_PREFIXED_TEXT,
    not_b_prefixed=_NOT_B_PREFIXED_TEXT,
)
def test_looks_like_real_header_pair_recognises_every_real_shape_and_rejects_the_rest(
    matching_path: str, not_a_prefixed: str, not_b_prefixed: str
) -> None:
    """Model-based for every case, independent of
    `_looks_like_real_header_pair`'s own `a/`/`b/`/`/dev/null` formula. Real
    defect class this would catch: either prefix check or the `/dev/null`
    special case on either side being loosened or dropped."""
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair("--- /dev/null", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", "+++ /dev/null") is True
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ b/{matching_path}") is False
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ {not_b_prefixed}") is False
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ {not_b_prefixed}") is False


# ---------------------------------------------------------------------------
# parse_added_lines -- string-comparison (startswith, x6) + regex (match)
# ---------------------------------------------------------------------------

_LINE_KIND = st.sampled_from(("+", " ", "-"))
_HUNK_BODY = st.lists(_LINE_KIND, max_size=20)
_START_LINE = st.integers(min_value=1, max_value=500)
_FILE_DIFF = st.tuples(_START_LINE, _HUNK_BODY)
_MULTI_FILE_DIFFS = st.lists(_FILE_DIFF, min_size=1, max_size=3)


def _expected_added_for_hunk(start: int, kinds: list[str]) -> set[int]:
    """The post-image added-line-number set a correct parser must produce
    for one hunk starting at post-image line `start`, per the module
    docstring's own documented contract."""
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
    """Model-based. `_expected_added_for_hunk` recomputes the intended
    added-line-number set directly from the module docstring's own
    documented post-image-counting contract, not by calling
    `parse_added_lines` or mirroring its own state machine. A file whose
    hunk body adds nothing never gets a key in `parse_added_lines`'s own
    returned dict, so files with an empty expected set are dropped from
    both sides of the comparison to match that documented shape.
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


# ---------------------------------------------------------------------------
# _waived_lines -- regex (search) trigger
# ---------------------------------------------------------------------------

_REASON_TEXT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=24,
)


def _source_with_waiver_at_line(before: int, after: int, reason: str) -> tuple[str, int]:
    """A `before + 1 + after`-line source where exactly one line -- number
    `before + 1` -- carries a real waiver comment with `reason`; every other
    line is a plain assignment statement carrying no comment at all."""
    lines = [f"x{i} = {i}" for i in range(before)]
    waiver_line = before + 1
    lines.append(f"y = 1  # patch-coverage: WAIVED: {reason}")
    lines.extend(f"z{i} = {i}" for i in range(after))
    return "\n".join(lines) + "\n", waiver_line


@_PROPERTIES
@given(before=st.integers(0, 5), after=st.integers(0, 5), reason=_REASON_TEXT)
def test_waived_lines_finds_exactly_the_real_comment_line(before: int, after: int, reason: str) -> None:
    """Model-based. The expected waived-line set is known by construction:
    a real comment carrying the marker waives exactly that line.

    Real defect class this would catch: switching from a `tokenize`-based
    scan to a raw-text/regex-over-lines scan, which the module docstring's
    own "Waiver" section says must not happen.
    """
    comment_source, waiver_line = _source_with_waiver_at_line(before, after, reason)
    assert gate._waived_lines(comment_source) == {waiver_line}

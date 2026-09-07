"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_network_exception_set_drift.py`` (issue
#1512, consolidated into #1572).

This gate's own source is entirely new, so -- unlike
`tests/test_gitapex_gate_exception_handler_gaps_properties.py`, which scopes
itself only to the functions its own issue actually touched -- every
regex-, path-resolution-, or string-comparison-shaped call this file
contains is "newly added by this diff" the first time it lands, and
`gitapex_gate_detection_logic_property_coverage.py`'s own scope
(`.github/scripts/gitapex_gate_*.py`) covers this file's own path.

Five functions in this file's own source carry a trigger under that gate's
own strict AST rules -- copied verbatim (mechanics, not the historical
docstring) from `gitapex_gate_exception_handler_gaps.py`, whose own trigger
surface is identical for the identical reason (the same functions, copied
the same way):

* :func:`in_scope` -- ``_IN_SCOPE_RE.fullmatch(path)`` (regex) and
  ``name.startswith("test_")`` (string-comparison).
* :func:`_diff_target_path` -- ``target.startswith("b/")``
  (string-comparison).
* :func:`_looks_like_real_header_pair` -- two ``.startswith(...)`` call
  sites (string-comparison).
* :func:`parse_added_lines` -- six ``.startswith(...)`` call sites
  (string-comparison) plus ``_HUNK_RE.match(line)`` (regex).
* :func:`_waived_lines` -- ``_WAIVER_RE.search(token.string)`` (regex).

The module level also carries three ``re.compile(...)`` constants
(``_IN_SCOPE_RE``, ``_WAIVER_RE``, ``_HUNK_RE``) and one
``pathlib.Path(__file__).resolve().parents[2]`` (path-resolution) --
needing no dedicated property, since the covering gate treats the
``"<module>"`` scope as covered by *any* ``@given``-decorated function in
this file, once this file both imports the source module and contains at
least one such function. Every property below clears it as a side effect
of existing at all.

No other function in this gate's own source contains a trigger-shaped call
under the covering gate's own strict rules: `_handler_names`, `_dotted_name`,
`_network_call_shape`, `_iter_excluding_nested_defs`,
`_contains_network_call_shape`, `_try_body_network_shape`,
`_first_network_try`, `_module_candidates`, `_drift_pairs`, `_try_span`,
`findings_for_source`, and `find_violations` use only `isinstance`,
`ast.iter_child_nodes`, dict/set operations, and `in`/`not in` comparisons
against local-variable names (never an inline collection literal) -- the
same "name reference to a previously-defined collection" miss the covering
gate's own module docstring discloses for its own category (c).

The first four properties below are ported near-verbatim from
`tests/test_gitapex_gate_detection_logic_property_coverage_properties.py`
(`_diff_target_path`, `_looks_like_real_header_pair`, `parse_added_lines`
x2) or from `gitapex_gate_exception_handler_gaps_properties.py`, since all
of `_diff_target_path`, `_looks_like_real_header_pair`, and
`parse_added_lines` are byte-identical copies in this file. `in_scope`'s
own property is written fresh: this gate's `_IN_SCOPE_RE` is the *four*-
directory, any-``.py``-name pattern
`gitapex_gate_exception_handler_gaps.py` uses, not
`gitapex_gate_detection_logic_property_coverage.py`'s own narrower
three-directory, ``gitapex_check_``/``gitapex_gate_``-prefixed one, so the
existing `in_scope` property in either mirror file does not transfer
as-is. `_waived_lines`'s own property is ported from
`test_gitapex_gate_detection_logic_property_coverage_properties.py`'s
`test_waived_lines_finds_exactly_the_real_comment_line`, with the waiver
marker text swapped to this gate's own rule name.

Reproducibility
----------------
``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
applied per property rather than as a registered global profile -- see
`tests/test_gitapex_gate_metadata_outcome_lines_properties.py`'s own module
docstring for the full rationale, not repeated here beyond this pointer.
"""

from __future__ import annotations

import os

import gitapex_gate_network_exception_set_drift as gate
import pytest
import unidiff
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = (
    settings(derandomize=False, max_examples=5000, deadline=None)
    if os.environ.get("GITAPEX_HYPOTHESIS_DEEP_SCAN") == "1"
    else settings(derandomize=True, max_examples=200, deadline=None)
)


def _unidiff_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Independent oracle for `parse_added_lines`'s own `{path: added-lines}`
    contract, computed by `unidiff`'s own parser -- ported verbatim from
    both mirror files' own copy of this helper."""
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


# ---------------------------------------------------------------------------
# in_scope -- regex (fullmatch) + string-comparison (startswith) triggers
# ---------------------------------------------------------------------------

_IDENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=16)
# Unlike gitapex_gate_detection_logic_property_coverage.py's own
# `gitapex_check_`/`gitapex_gate_`-prefixed `_IDENT` (which structurally
# cannot start with "test_" or equal "conftest"), this gate's own
# `_IN_SCOPE_RE` accepts any basename -- so an unfiltered `_IDENT` can
# generate exactly "test_" or "conftest", which `in_scope`'s own exclusion
# then legitimately rejects. Filtered here to keep the "in scope by
# construction" builder honest; the exclusion itself is exercised directly
# by this property's own fixed `test_`/`conftest.py` assertions below.
_IN_SCOPE_IDENT = _IDENT.filter(lambda s: not s.startswith("test_") and s != "conftest")
_SKILL_NAME = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=12)

_IN_SCOPE_DIR = st.sampled_from((".github/scripts", "hooks", "evals/scripts"))


def _in_scope_path(kind: str, skill: str, ident: str, directory: str) -> str:
    """A path built from one of this gate's own `_IN_SCOPE_RE` alternatives
    -- always in scope by construction. Unlike
    `gitapex_gate_detection_logic_property_coverage.py`'s own narrower
    scope, this gate's own pattern accepts *any* `.py` basename under the
    four directories, not only a `gitapex_check_`/`gitapex_gate_`-prefixed
    one."""
    if kind == "skills":
        return f"skills/{skill}/scripts/{ident}.py"
    return f"{directory}/{ident}.py"


def _out_of_scope_path(kind: str, skill: str, ident: str) -> str:
    """A path built to violate exactly one documented scope boundary --
    always out of scope by construction."""
    if kind == "wrong_directory":
        return f"src/{ident}.py"
    if kind == "extra_path_segment":
        # Breaks the single-`[^/]+`-segment requirement between `skills/`
        # and `/scripts/`.
        return f"skills/{skill}/extra/scripts/{ident}.py"
    # A real in-scope-shaped name with a further suffix appended: the last
    # three characters are "bak", not "py", so re.fullmatch must reject it,
    # even though "...ident.py" is a genuine *prefix* a re.match()-based
    # regression would wrongly accept.
    return f"hooks/{ident}.py.bak"


@_PROPERTIES
@given(
    in_kind=st.sampled_from(("skills", "directory")),
    out_kind=st.sampled_from(("wrong_directory", "extra_path_segment", "trailing_suffix")),
    directory=_IN_SCOPE_DIR,
    skill=_SKILL_NAME,
    ident=_IN_SCOPE_IDENT,
)
def test_in_scope_matches_its_own_scope_rules(
    in_kind: str, out_kind: str, directory: str, skill: str, ident: str
) -> None:
    """Model-based. The expected answer for each path is known independently
    of `in_scope`'s own implementation, directly from this gate's own module
    docstring "In-scope paths" sentence.

    Real defect classes this would catch: a typo or accidental narrowing/
    widening in one of `_IN_SCOPE_RE`'s four fixed literal prefixes; a
    widened `[^/]+` letting a path cross a directory separator (the
    `extra_path_segment` case); a dropped directory anchor (the
    `wrong_directory` case); a regression from `re.fullmatch` to `re.match`
    (the `trailing_suffix` case, the same fullmatch-vs-match distinction
    issue #1129's own motivating defect turned on).

    `name.startswith("test_") or name == "conftest.py"` is exercised
    separately by the fixed-input assertions below -- every path either
    generator here builds carries no `test_`/`conftest.py` basename by
    construction.
    """
    assert gate.in_scope(_in_scope_path(in_kind, skill, ident, directory)) is True
    assert gate.in_scope(_out_of_scope_path(out_kind, skill, ident)) is False
    assert gate.in_scope(f"{directory}/test_{ident}.py") is False
    assert gate.in_scope(f"{directory}/conftest.py") is False


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
    """Ported from `test_gitapex_gate_detection_logic_property_coverage_
    properties.py`'s own property of the same name -- `_diff_target_path` is
    a byte-identical copy in both files. Model-based for both halves: the
    `b/`-stripped output is known from how the input was built, and `other`
    is built to structurally avoid both accepted shapes, so it must reach
    the documented `raise ScanError(...)` branch.
    """
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
    """Ported verbatim (adapted to this module's own `gate` import) from
    both mirror files' own property of the same name -- see either for the
    full case-by-case rationale."""
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair("--- /dev/null", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", "+++ /dev/null") is True
    assert gate._looks_like_real_header_pair(f"--- a/{rename_source_path}", f"+++ b/{rename_target_path}") is True
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
    """Ported verbatim from both mirror files' own property of the same
    name -- `parse_added_lines` is a byte-identical copy in all three
    files, so the same model-based property applies unchanged."""
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


_NON_EMPTY_HUNK_BODY = st.lists(_LINE_KIND, min_size=1, max_size=20)
_NON_EMPTY_FILE_DIFF = st.tuples(_START_LINE, _NON_EMPTY_HUNK_BODY)
_NON_EMPTY_MULTI_FILE_DIFFS = st.lists(_NON_EMPTY_FILE_DIFF, min_size=1, max_size=3)


@_PROPERTIES
@given(file_diffs=_NON_EMPTY_MULTI_FILE_DIFFS)
def test_parse_added_lines_matches_unidiffs_independent_parse(
    file_diffs: list[tuple[int, list[str]]],
) -> None:
    """Differential-oracle property, ported verbatim from both mirror
    files' own property of the same name."""
    paths = [f"module_{index}.py" for index in range(len(file_diffs))]
    diff_text = "\n".join(
        _file_diff_text(path, start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    )
    assert gate.parse_added_lines(diff_text) == _unidiff_added_lines(diff_text)


# ---------------------------------------------------------------------------
# _waived_lines -- regex (search) trigger
# ---------------------------------------------------------------------------

_REASON_TEXT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=24,
)


def _source_with_waiver_at_line(before: int, after: int, reason: str) -> tuple[str, int]:
    lines = [f"x{i} = {i}" for i in range(before)]
    waiver_line = before + 1
    lines.append(f"y = 1  # network-exception-set-drift: WAIVED: {reason}")
    lines.extend(f"z{i} = {i}" for i in range(after))
    return "\n".join(lines) + "\n", waiver_line


def _source_with_waiver_text_only_in_a_string_literal(reason: str) -> str:
    return f'DOC = "# network-exception-set-drift: WAIVED: {reason}"\n'


@_PROPERTIES
@given(before=st.integers(0, 5), after=st.integers(0, 5), reason=_REASON_TEXT)
def test_waived_lines_finds_exactly_the_real_comment_line(before: int, after: int, reason: str) -> None:
    """Ported from `test_gitapex_gate_detection_logic_property_coverage_
    properties.py`'s own property of the same name, with the marker text
    swapped to this gate's own rule name. Model-based in both halves: a
    real comment line waives exactly itself, and the identical text inside
    a string literal waives nothing -- `tokenize` emits a STRING token
    there, never a COMMENT one.
    """
    comment_source, waiver_line = _source_with_waiver_at_line(before, after, reason)
    assert gate._waived_lines(comment_source) == {waiver_line}

    string_literal_source = _source_with_waiver_text_only_in_a_string_literal(reason)
    assert gate._waived_lines(string_literal_source) == set()

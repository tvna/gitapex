"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_function_body_test_coverage.py`` (issue
#1498). Covers the six functions in that file which, per its own AST-shape
trigger rules (this repository's own ``detection-logic-property-coverage``
gate, issue #1178, which this file's source also matches the in-scope
pattern of), actually contain a regex-, path-resolution-, or string-
comparison-shaped call reached by a diff: :func:`in_scope`,
:func:`_diff_target_path`, :func:`_looks_like_real_header_pair`,
:func:`parse_added_lines`, :func:`_diff_adds_a_covering_test`, and
:func:`_waived_lines`.

Self-referential by design: the gate's own source file matches its own
``skills/*/scripts/*.py``/``.github/scripts/*.py`` in-scope pattern (this
gate grades itself) and ALSO matches ``detection-logic-property-coverage``'s
own narrower ``.github/scripts/gitapex_gate_*.py`` pattern, so both gates
grade this file once their workflows are wired. Every property below is
written to be genuine coverage first; satisfying either gate's own
self-check against this file is a consequence of that, not the design goal.

Verified enumeration of trigger-bearing functions
--------------------------------------------------
Confirmed by running ``gitapex_gate_detection_logic_property_coverage.py``
directly against this PR's own diff (not merely traced by eye):
:func:`in_scope` (regex ``.fullmatch``, string-comparison ``.startswith``),
:func:`_diff_target_path` (string-comparison ``.startswith``),
:func:`_looks_like_real_header_pair` (string-comparison ``.startswith`` x2,
both on one physical line so they dedupe to one finding),
:func:`parse_added_lines` (string-comparison ``.startswith`` x6 + regex
``.match``), :func:`_diff_adds_a_covering_test` (string-comparison
``.startswith``), and :func:`_waived_lines` (regex ``.search``). No other
function in the source file contains a trigger-shaped call under that
gate's own strict AST rules -- ``_touched_functions``, ``_function_ranges``,
``_mentions_name_in_body``, ``_test_tree``, ``findings_for_source``, and
``main`` all resolve cleanly with no findings reported against them.

Module-scope triggers need no dedicated property
--------------------------------------------------
The source file's own module level carries real triggers too (``REPO_ROOT
= pathlib.Path(__file__).resolve().parents[2]``, three ``re.compile(...)``
constants). None needs a property mentioning it by name: any
``@given``-decorated function in this file clears the ``"<module>"`` scope
as a side effect of existing at all, the same rule
``gitapex_gate_detection_logic_property_coverage.py``'s own ``_covered``
already applies (see that source's own module docstring's
"Existing-coverage check" section).

Filesystem-touching property
-----------------------------
:func:`_diff_adds_a_covering_test` reads real files, unlike the other five
functions here. Its own property below creates a fresh
``tempfile.TemporaryDirectory()`` inside the decorated function body itself,
not a pytest ``tmp_path`` fixture -- a fixture is set up once per pytest test
*invocation*, but Hypothesis re-invokes this same function body many times
per invocation with different generated arguments, so reusing one
fixture-provided directory across draws would leak state between examples
(a file one draw wrote still present, wrongly, when the next draw runs). A
directory created and torn down inside the body itself is genuinely fresh
every draw.

Reproducibility
----------------
``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
applied per property rather than as a registered global profile --
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own module
docstring gives the full rationale, not repeated here beyond this pointer.
"""

from __future__ import annotations

import keyword
import pathlib
import tempfile

import gitapex_gate_function_body_test_coverage as gate
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" section.
_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)


# ---------------------------------------------------------------------------
# in_scope -- regex (fullmatch) + string-comparison (startswith) triggers
# ---------------------------------------------------------------------------

_IDENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=16)
_SKILL_NAME = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=12)

# `in_scope`'s own basename check excludes anything starting with "test_" or
# equal to "conftest.py", regardless of directory -- filtered out here so
# `_in_scope_path` below stays "always in scope by construction" rather than
# accidentally building a basename `in_scope` itself is required to reject.
_PATH_IDENT = _IDENT.filter(lambda s: not s.startswith("test_") and s != "conftest")

_IN_SCOPE_KIND = st.sampled_from(("skills_scripts", "github_scripts"))
_OUT_OF_SCOPE_KIND = st.sampled_from(
    ("test_prefix", "conftest", "wrong_directory", "extra_path_segment", "trailing_suffix")
)


def _in_scope_path(kind: str, skill: str, ident: str) -> str:
    """A path built from `_IN_SCOPE_RE`'s own two documented alternatives --
    always in scope by construction, with no `gitapex_check_`/`gitapex_gate_`
    prefix requirement (this gate's own broader scope, unlike
    `gitapex_gate_detection_logic_property_coverage.py`'s narrower one)."""
    if kind == "skills_scripts":
        return f"skills/{skill}/scripts/{ident}.py"
    return f".github/scripts/{ident}.py"


def _out_of_scope_path(kind: str, skill: str, ident: str) -> str:
    """A path built to violate exactly one documented scope boundary --
    always out of scope by construction."""
    if kind == "test_prefix":
        return f"skills/{skill}/scripts/test_{ident}.py"
    if kind == "conftest":
        return f"skills/{skill}/scripts/conftest.py"
    if kind == "wrong_directory":
        return f"hooks/{ident}.py"
    if kind == "extra_path_segment":
        return f"skills/{skill}/extra/scripts/{ident}.py"
    # A real in-scope-shaped name with a further suffix appended: the last
    # three characters are "bak", not "py", so re.fullmatch must reject it,
    # even though the prefix alone would be a genuine in-scope path.
    return f".github/scripts/{ident}.py.bak"


@_PROPERTIES
@given(in_kind=_IN_SCOPE_KIND, out_kind=_OUT_OF_SCOPE_KIND, skill=_SKILL_NAME, ident=_PATH_IDENT)
def test_in_scope_matches_its_own_scope_rules(in_kind: str, out_kind: str, skill: str, ident: str) -> None:
    """Model-based. The expected answer for each path is known independently
    of `in_scope`'s own implementation: it follows directly from the scope
    rules the gate's own module docstring states in its "Scope" section.

    Real defect classes this would catch: a typo or accidental narrowing/
    widening in either of `_IN_SCOPE_RE`'s two fixed directory prefixes; a
    widened `[^/]+` letting a path cross a directory separator (the
    `extra_path_segment` case); the `test_`/`conftest.py` exclusion being
    dropped; and a regression from `re.fullmatch` to `re.match` (the
    `trailing_suffix` case, the same fullmatch-vs-match distinction issue
    #1129 turned on, applied here to this gate's own scope check).
    """
    assert gate.in_scope(_in_scope_path(in_kind, skill, ident)) is True
    assert gate.in_scope(_out_of_scope_path(out_kind, skill, ident)) is False


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
# _diff_adds_a_covering_test -- string-comparison (startswith) trigger
# ---------------------------------------------------------------------------

# Must be real, importable Python identifiers here (unlike `_IDENT` above,
# which only ever becomes a path segment or filename): `stem` and
# `function_name` are spliced directly into a real `import {stem}` statement
# and a real `{stem}.{function_name}` attribute access this property parses
# as Python. `keyword.iskeyword` is excluded since a keyword can be neither
# a valid module name nor a valid attribute name.
_PY_IDENT = st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]{0,15}", fullmatch=True).filter(lambda s: not keyword.iskeyword(s))


@_PROPERTIES
@given(
    stem=_PY_IDENT,
    function_name=_PY_IDENT,
    other_name=_PY_IDENT,
    use_properties_file=st.booleans(),
    covering_line_included=st.booleans(),
)
def test_diff_adds_a_covering_test_matches_the_three_part_condition(
    stem: str,
    function_name: str,
    other_name: str,
    use_properties_file: bool,
    covering_line_included: bool,
) -> None:
    """Model-based. Writes a real `test_<name>()` function, at line 5 of a
    5-line file, whose own body mentions `function_name` -- into whichever
    of the two accepted test-file names `use_properties_file` selects. When
    `covering_line_included` is True, `added_by_path` marks line 5 (inside
    the covering function) as touched by this diff; when False, it marks
    only line 1 (the `import` line, outside the covering function) -- so
    the expected answer is known by construction, not by mirroring
    `_diff_adds_a_covering_test`'s own logic. A query for `other_name` must
    always come back False regardless, since the covering function's own
    body never mentions it -- `stem`, `function_name` and `other_name` are
    required mutually distinct so `other_name` cannot accidentally match
    the `Name` node the `{stem}.` receiver itself contributes to the AST.

    Real defect class this would catch: the function-range overlap check
    being dropped (so *any* touched line in the file would wrongly clear
    coverage, not only one inside the covering function's own body), or
    either of the two accepted test-file names being lost.
    """
    assume(len({stem, function_name, other_name}) == 3)
    relative = f"tests/test_{stem}_properties.py" if use_properties_file else f"tests/test_{stem}.py"
    test_source = f"import {stem}\n\n\ndef test_covers():\n    {stem}.{function_name}\n"
    with tempfile.TemporaryDirectory() as raw_root:
        root = pathlib.Path(raw_root)
        test_path = root / relative
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(test_source, encoding="utf-8")

        added_by_path = {relative: {5}} if covering_line_included else {relative: {1}}
        assert gate._diff_adds_a_covering_test(root, stem, function_name, added_by_path) is covering_line_included
        assert gate._diff_adds_a_covering_test(root, stem, other_name, {relative: {5}}) is False


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
    lines.append(f"y = 1  # function-body-test-coverage: WAIVED: {reason}")
    lines.extend(f"z{i} = {i}" for i in range(after))
    return "\n".join(lines) + "\n", waiver_line


def _source_with_waiver_text_only_in_a_string_literal(reason: str) -> str:
    """The same waiver text, but as the *content* of a string literal, never
    as a real comment -- `tokenize` emits a STRING token here, never a
    COMMENT one."""
    return f'DOC = "# function-body-test-coverage: WAIVED: {reason}"\n'


@_PROPERTIES
@given(before=st.integers(0, 5), after=st.integers(0, 5), reason=_REASON_TEXT)
def test_waived_lines_finds_exactly_the_real_comment_line(before: int, after: int, reason: str) -> None:
    """Model-based. The expected waived-line set is known by construction:
    a real comment carrying the marker waives exactly that line; the
    identical text inside a string literal waives nothing.

    Real defect class this would catch: switching from a `tokenize`-based
    scan to a raw-text/regex-over-lines scan, which the module docstring's
    own "Waiver" section says must not happen.
    """
    comment_source, waiver_line = _source_with_waiver_at_line(before, after, reason)
    assert gate._waived_lines(comment_source) == {waiver_line}

    string_literal_source = _source_with_waiver_text_only_in_a_string_literal(reason)
    assert gate._waived_lines(string_literal_source) == set()

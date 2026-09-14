"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_defeat_test_mutation_coverage.py`` (issue
#1799). Covers every function in that file which, per this repository's own
``detection-logic-property-coverage`` gate (issue #1178), contains a regex-,
path-resolution-, or string-comparison-shaped call: :func:`in_scope`,
:func:`_stem`, :func:`_diff_target_path`, :func:`_looks_like_real_header_pair`,
:func:`parse_added_lines`, :func:`_waived_lines`, :func:`_split_bom`, and
:func:`_string_literal_content_span`.

``in_scope``, ``_diff_target_path``, ``_looks_like_real_header_pair`` and
``parse_added_lines`` are copied verbatim (or near-verbatim, for ``in_scope``'s
own three-directory scope) from
``gitapex_gate_function_body_test_coverage.py``, whose own properties file
already carries the full model-based property for each -- the versions below
are the same technique, scoped down (fewer generated shapes, smaller
``max_examples``) rather than re-deriving a new approach, since the
underlying functions are the same code.

Module-scope triggers need no dedicated property
--------------------------------------------------
The source file's own module level carries real triggers too (``REPO_ROOT
= pathlib.Path(__file__).resolve().parents[2]``, several ``re.compile(...)``
constants). None needs a property mentioning it by name: any
``@given``-decorated function in this file clears the ``"<module>"`` scope
as a side effect of existing at all, the same rule
``gitapex_gate_detection_logic_property_coverage.py``'s own ``_covered``
already applies.

Reproducibility
----------------
``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
applied per property rather than as a registered global profile --
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own module
docstring gives the full rationale, not repeated here beyond this pointer.
"""

from __future__ import annotations

import gitapex_gate_defeat_test_mutation_coverage as gate
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" section.
_PROPERTIES = settings(derandomize=True, max_examples=100, deadline=None)

_IDENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=16)
_SKILL_NAME = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=12)
# `in_scope`'s own basename check excludes anything starting with "test_" or
# equal to "conftest.py", regardless of directory.
_PATH_IDENT = _IDENT.filter(lambda s: not s.startswith("test_") and s != "conftest")

_IN_SCOPE_KIND = st.sampled_from(("skills_scripts", "github_scripts", "hooks"))
_OUT_OF_SCOPE_KIND = st.sampled_from(("test_prefix", "conftest", "wrong_directory", "extra_path_segment"))


def _in_scope_path(kind: str, skill: str, ident: str) -> str:
    """A path built from `_IN_SCOPE_RE`'s own three documented
    alternatives -- always in scope by construction."""
    if kind == "skills_scripts":
        return f"skills/{skill}/scripts/{ident}.py"
    if kind == "github_scripts":
        return f".github/scripts/{ident}.py"
    return f"hooks/{ident}.py"


def _out_of_scope_path(kind: str, skill: str, ident: str) -> str:
    """A path built to violate exactly one documented scope boundary --
    always out of scope by construction."""
    if kind == "test_prefix":
        return f"skills/{skill}/scripts/test_{ident}.py"
    if kind == "conftest":
        return f"skills/{skill}/scripts/conftest.py"
    if kind == "wrong_directory":
        return f"evals/scripts/{ident}.py"
    # A real in-scope-shaped name with an extra path segment: `[^/]+`
    # segments must never cross a directory separator.
    return f"skills/{skill}/extra/scripts/{ident}.py"


@_PROPERTIES
@given(in_kind=_IN_SCOPE_KIND, out_kind=_OUT_OF_SCOPE_KIND, skill=_SKILL_NAME, ident=_PATH_IDENT)
def test_in_scope_matches_its_own_three_directory_scope(in_kind: str, out_kind: str, skill: str, ident: str) -> None:
    """Model-based, independent of `in_scope`'s own implementation: the
    expected answer follows directly from the module docstring's own
    "Scope" section. Real defect class this would catch: a typo or
    accidental narrowing/widening in any of `_IN_SCOPE_RE`'s three fixed
    directory prefixes, or the `test_`/`conftest.py` exclusion being
    dropped."""
    assert gate.in_scope(_in_scope_path(in_kind, skill, ident)) is True
    assert gate.in_scope(_out_of_scope_path(out_kind, skill, ident)) is False


@_PROPERTIES
@given(directory=st.sampled_from((".github/scripts", "hooks")), ident=_PATH_IDENT)
def test_stem_round_trips_through_test_relative_paths(directory: str, ident: str) -> None:
    """Model-based: `_stem` composed with `_test_relative_paths` must
    reconstruct the exact stem a real gate script's path implies,
    independent of either function's own implementation detail. Real
    defect class this would catch: a `_stem`/`_test_relative_paths`
    mismatch letting a source file resolve to the wrong paired-test
    filename."""
    path = f"{directory}/{ident}.py"
    stem = gate._stem(path)
    assert stem == ident
    test_path, properties_path = gate._test_relative_paths(stem)
    assert test_path == f"tests/test_{ident}.py"
    assert properties_path == f"tests/test_{ident}_properties.py"


_NO_WHITESPACE_TEXT = st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), max_size=60)
_NON_B_PREFIXED_TEXT = st.text(max_size=60).filter(
    lambda s: s.strip() != "/dev/null" and not s.strip().startswith("b/")
)


@_PROPERTIES
@given(suffix=_NO_WHITESPACE_TEXT, other=_NON_B_PREFIXED_TEXT)
def test_diff_target_path_strips_b_prefix_and_rejects_everything_else(suffix: str, other: str) -> None:
    """Model-based for both halves, independent of `_diff_target_path`'s
    own implementation. Real defect class this would catch: the `b/`-prefix
    check or the `/dev/null` special case being loosened."""
    assert gate._diff_target_path("b/" + suffix) == suffix
    assert gate._diff_target_path("/dev/null") is None
    with pytest.raises(gate.ScanError):
        gate._diff_target_path(other)


_HEADER_PATH_TEXT = st.text(max_size=40)
_NOT_A_PREFIXED_TEXT = st.text(max_size=60).filter(lambda s: s != "/dev/null" and not s.startswith("a/"))
_NOT_B_PREFIXED_TEXT = st.text(max_size=60).filter(lambda s: s != "/dev/null" and not s.startswith("b/"))


@_PROPERTIES
@given(matching_path=_HEADER_PATH_TEXT, not_a_prefixed=_NOT_A_PREFIXED_TEXT, not_b_prefixed=_NOT_B_PREFIXED_TEXT)
def test_looks_like_real_header_pair_recognises_every_real_shape_and_rejects_the_rest(
    matching_path: str, not_a_prefixed: str, not_b_prefixed: str
) -> None:
    """Model-based for every case, independent of
    `_looks_like_real_header_pair`'s own `a/`/`b/`/`/dev/null` formula. Real
    defect class this would catch: either prefix check, or the `/dev/null`
    special case on either side, being loosened or dropped."""
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair("--- /dev/null", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", "+++ /dev/null") is True
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ b/{matching_path}") is False
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ {not_b_prefixed}") is False


_LINE_KIND = st.sampled_from(("+", " ", "-"))
_HUNK_BODY = st.lists(_LINE_KIND, max_size=15)
_START_LINE = st.integers(min_value=1, max_value=200)


def _expected_added_for_hunk(start: int, kinds: list[str]) -> set[int]:
    """The post-image added-line-number set a correct parser must produce
    for one hunk starting at post-image line `start`, per the module
    docstring's own documented contract -- recomputed independently, not by
    mirroring `parse_added_lines`'s own state machine."""
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
@given(start=_START_LINE, kinds=_HUNK_BODY)
def test_parse_added_lines_matches_an_independently_computed_line_set(start: int, kinds: list[str]) -> None:
    """Model-based. `_expected_added_for_hunk` recomputes the intended
    added-line-number set directly from the module docstring's own
    documented post-image-counting contract, not by calling
    `parse_added_lines` or mirroring its own state machine. Real defect
    class this would catch: an off-by-one in the post-image line counter,
    or a context/removal line wrongly advancing (or failing to advance) it.
    """
    diff_text = _file_diff_text("module.py", start, kinds)
    added = gate.parse_added_lines(diff_text)
    expected = _expected_added_for_hunk(start, kinds)
    if expected:
        assert added == {"module.py": expected}
    else:
        assert added == {}


_WAIVER_REASON_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters="\n\r#"),
    min_size=1,
    max_size=40,
)


@_PROPERTIES
@given(reason=_WAIVER_REASON_TEXT)
def test_waived_lines_finds_a_marker_with_a_reason_and_not_a_bare_one(reason: str) -> None:
    """Model-based: a waiver comment with a non-empty reason is always
    honoured on its own line; the bare marker with no reason never is,
    regardless of what other content shares the line. Real defect class
    this would catch: `_WAIVER_RE`'s own mandatory-reason group being
    loosened to accept a bare marker."""
    waived_source = f"X = 1  # defeat-test-mutation-coverage: WAIVED: {reason}\n"
    assert gate._waived_lines(waived_source) == {1}
    bare_source = "X = 1  # defeat-test-mutation-coverage: WAIVED\n"
    assert gate._waived_lines(bare_source) == set()


@_PROPERTIES
@given(data=st.binary(max_size=60))
def test_split_bom_round_trips_with_and_without_a_leading_bom(data: bytes) -> None:
    """Model-based, independent of `_split_bom`'s own implementation: the
    BOM/body split is exactly determined by whether `data` starts with the
    fixed 3-byte UTF-8 BOM sequence. Real defect class this would catch:
    the BOM constant being mis-sliced, or the no-BOM branch dropping bytes.
    """
    with_bom = gate._UTF8_BOM + data
    assert gate._split_bom(with_bom) == (gate._UTF8_BOM, data)
    if not data.startswith(gate._UTF8_BOM):
        assert gate._split_bom(data) == (b"", data)


_QUOTE_SAFE_CONTENT = st.text(
    alphabet=st.characters(blacklist_characters="\"'\\\n\r", min_codepoint=32, max_codepoint=126), max_size=30
)
_QUOTE_STYLE = st.sampled_from(('"', "'"))
_PREFIX = st.sampled_from(("", "r", "b", "rb"))


@_PROPERTIES
@given(prefix=_PREFIX, quote=_QUOTE_STYLE, content=_QUOTE_SAFE_CONTENT)
def test_string_literal_content_span_recovers_exactly_the_quoted_content(prefix: str, quote: str, content: str) -> None:
    """Model-based: for a well-formed, single-token string literal built
    from `prefix`/`quote`/`content`, the returned span must slice out
    exactly `content` -- no more, no less, and no off-by-one from the
    prefix or quote length. Real defect class this would catch: the
    prefix/quote length arithmetic drifting for a two-character prefix
    (`rb`) or a differently-quoted literal (`'` vs `"`)."""
    raw = f"{prefix}{quote}{content}{quote}".encode()
    start, end = gate._string_literal_content_span(raw)
    assert raw[start:end] == content.encode()

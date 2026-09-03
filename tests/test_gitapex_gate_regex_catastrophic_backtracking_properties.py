"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_regex_catastrophic_backtracking.py`` (issue
#1556), required by the pre-existing `detection-logic-property-coverage`
gate (issue #1178): this file's own regex/path-resolution/string-comparison
call sites are new detection logic under that gate's own scope
(`.github/scripts/gitapex_gate_*.py`), so each needs a co-located property
test here.

Self-referential by design: once this gate's own CI workflow is wired, it
also grades itself against this exact file -- the co-located properties
path `detection-logic-property-coverage`'s own `_properties_path` computes
from the stem `gitapex_gate_regex_catastrophic_backtracking`.

Covers, by direct reading of the source's own trigger-shaped call sites:
:func:`in_scope`, :func:`_diff_target_path`,
:func:`_looks_like_real_header_pair`, :func:`parse_added_lines`,
:func:`_waived_lines`, :func:`_quantifier_repeats`, :func:`_simple_atom_set`,
and :func:`_parse_branches`. Module-level triggers (three `re.compile(...)`
constants, several `frozenset({...})` constants) need no dedicated property
of their own -- any `@given`-decorated function in this file already clears
the `"<module>"` scope.
"""

from __future__ import annotations

import re

import gitapex_gate_regex_catastrophic_backtracking as gate
from hypothesis import given
from hypothesis import strategies as st

# --- shared strategies -------------------------------------------------

_STEM = st.text(alphabet=st.characters(min_codepoint=0x61, max_codepoint=0x7A), min_size=1, max_size=10)
_DIRNAME = st.lists(_STEM, min_size=0, max_size=3).map(lambda parts: "/".join(parts))
_PATTERN_TEXT = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="[]{}()\\"),
    max_size=20,
)


# --- in_scope ------------------------------------------------------------


@given(dirname=_DIRNAME, stem=_STEM)
def test_in_scope_accepts_a_plain_py_file(dirname: str, stem: str) -> None:
    """A `*.py` file whose basename does not start with `test_` and is not
    `conftest.py` is always in scope, regardless of directory."""
    name = f"{stem}.py"
    path = f"{dirname}/{name}" if dirname else name
    assert gate.in_scope(path) is True


@given(dirname=_DIRNAME, stem=_STEM)
def test_in_scope_rejects_a_test_file(dirname: str, stem: str) -> None:
    name = f"test_{stem}.py"
    path = f"{dirname}/{name}" if dirname else name
    assert gate.in_scope(path) is False


@given(dirname=_DIRNAME)
def test_in_scope_rejects_conftest(dirname: str) -> None:
    path = f"{dirname}/conftest.py" if dirname else "conftest.py"
    assert gate.in_scope(path) is False


@given(dirname=_DIRNAME, stem=_STEM, extension=st.sampled_from(["md", "txt", "sh", "yaml", ""]))
def test_in_scope_rejects_a_non_py_file(dirname: str, stem: str, extension: str) -> None:
    name = f"{stem}.{extension}" if extension else stem
    path = f"{dirname}/{name}" if dirname else name
    assert gate.in_scope(path) is False


# --- _diff_target_path -----------------------------------------------------


@given(suffix=_STEM)
def test_diff_target_path_strips_the_b_prefix(suffix: str) -> None:
    assert gate._diff_target_path(f"b/{suffix}") == suffix


def test_diff_target_path_dev_null_is_none() -> None:
    assert gate._diff_target_path("/dev/null") is None


@given(other=_STEM)
def test_diff_target_path_rejects_everything_else(other: str) -> None:
    try:
        gate._diff_target_path(other)
    except gate.ScanError:
        return
    raise AssertionError(f"expected ScanError for {other!r}")


# --- _looks_like_real_header_pair ------------------------------------------


@given(source_path=_STEM, target_path=_STEM)
def test_looks_like_real_header_pair_recognises_a_real_pair(source_path: str, target_path: str) -> None:
    assert gate._looks_like_real_header_pair(f"--- a/{source_path}", f"+++ b/{target_path}") is True


@given(source_path=_STEM, target_path=_STEM)
def test_looks_like_real_header_pair_rejects_a_mismatched_prefix(source_path: str, target_path: str) -> None:
    assert gate._looks_like_real_header_pair(f"--- x/{source_path}", f"+++ b/{target_path}") is False
    assert gate._looks_like_real_header_pair(f"--- a/{source_path}", f"+++ x/{target_path}") is False


def test_looks_like_real_header_pair_accepts_dev_null_on_either_side() -> None:
    assert gate._looks_like_real_header_pair("--- /dev/null", "+++ b/new.py") is True
    assert gate._looks_like_real_header_pair("--- a/old.py", "+++ /dev/null") is True


# --- _waived_lines -----------------------------------------------------


@given(before=st.integers(0, 3), after=st.integers(0, 3), reason=_STEM)
def test_waived_lines_finds_exactly_the_real_comment_line(before: int, after: int, reason: str) -> None:
    lines = [f"x{i} = {i}" for i in range(before)]
    waived_lineno = before + 1
    lines.append(f"y = 1  # regex-catastrophic-backtracking: WAIVED: {reason}")
    lines.extend(f"z{i} = {i}" for i in range(after))
    source = "\n".join(lines) + "\n"
    assert gate._waived_lines(source) == {waived_lineno}


# --- parse_added_lines -----------------------------------------------------


@given(added_count=st.integers(1, 6))
def test_parse_added_lines_counts_match_an_independently_built_diff(added_count: int) -> None:
    """A whole-file-added diff for an N-line file always reports exactly N
    added line numbers, 1..N -- an independent line-count check, not a
    re-derivation of the parser's own internal counters."""
    lines = [f"line{i} = {i}" for i in range(added_count)]
    body = "".join(f"+{line}\n" for line in lines)
    diff = f"diff --git a/f.py b/f.py\n--- /dev/null\n+++ b/f.py\n@@ -0,0 +1,{added_count} @@\n{body}"
    added = gate.parse_added_lines(diff)
    assert added == {"f.py": set(range(1, added_count + 1))}


@given(kept_count=st.integers(0, 4), added_count=st.integers(1, 4))
def test_parse_added_lines_ignores_context_lines(kept_count: int, added_count: int) -> None:
    """Context lines advance the running line counter but are never
    themselves recorded as added."""
    context = [f" ctx{i} = {i}\n" for i in range(kept_count)]
    additions = [f"+new{i} = {i}\n" for i in range(added_count)]
    body = "".join(context) + "".join(additions)
    diff = (
        f"diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1,{kept_count} +1,{kept_count + added_count} @@\n{body}"
    )
    added = gate.parse_added_lines(diff)
    expected_lines = set(range(kept_count + 1, kept_count + added_count + 1))
    assert added == {"f.py": expected_lines}


# --- _quantifier_repeats ----------------------------------------------------


@given(pattern=_PATTERN_TEXT, index=st.integers(0, 20))
def test_quantifier_repeats_never_crashes_and_never_goes_backwards(pattern: str, index: int) -> None:
    """For arbitrary text and an arbitrary starting index, this function
    must never raise and must never return an index behind where it
    started -- the invariant every caller in `_parse_branches` relies on to
    make forward progress and eventually terminate."""
    reaches_two, next_index = gate._quantifier_repeats(pattern, index)
    assert isinstance(reaches_two, bool)
    assert next_index >= index


@given(low=st.integers(0, 5), high=st.integers(0, 5))
def test_quantifier_repeats_bounded_form_matches_its_own_documented_rule(low: int, high: int) -> None:
    pattern = f"x{{{low},{high}}}"
    reaches_two, next_index = gate._quantifier_repeats(pattern, 1)
    assert next_index == len(pattern)
    assert reaches_two == (high >= 2 or low >= 2)


# --- _simple_atom_set --------------------------------------------------


@given(char=st.characters(min_codepoint=0x21, max_codepoint=0x7E, blacklist_characters="[.\\"))
def test_simple_atom_set_resolves_a_plain_literal_to_itself(char: str) -> None:
    char_set, next_index = gate._simple_atom_set(char, 0)
    assert char_set == frozenset({char})
    assert next_index == 1


def test_simple_atom_set_dot_is_wide() -> None:
    char_set, next_index = gate._simple_atom_set(".", 0)
    assert char_set is None
    assert next_index == 1


@given(pattern=_PATTERN_TEXT, start=st.integers(0, 20))
def test_simple_atom_set_never_crashes(pattern: str, start: int) -> None:
    if start >= len(pattern):
        return
    try:
        gate._simple_atom_set(pattern, start)
    except gate.ScanError:
        return


# --- _parse_branches ---------------------------------------------------


@given(pattern=_PATTERN_TEXT)
def test_parse_branches_never_crashes_on_arbitrary_text(pattern: str) -> None:
    try:
        gate._parse_branches(pattern, 0, top_level=True)
    except gate.ScanError:
        return


@given(compilable=st.from_regex(r"[a-z0-9]{1,6}[+*?]?", fullmatch=True))
def test_parse_branches_never_raises_on_a_pattern_python_itself_accepts(compilable: str) -> None:
    """Any pattern text Python's own `re.compile` accepts as valid must
    never make this gate's own heuristic parser raise `ScanError` -- a
    parse failure here is reserved for pattern text this gate itself
    cannot walk (an unterminated character class), never for a genuinely
    valid regex."""
    re.compile(compilable)  # sanity: confirm the strategy only ever produces valid patterns
    gate._parse_branches(compilable, 0, top_level=True)

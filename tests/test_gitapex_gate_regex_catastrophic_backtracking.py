"""Tests for the regex catastrophic-backtracking gate
(.github/scripts/gitapex_gate_regex_catastrophic_backtracking.py).

Issue #1556 (retro #1552 repair 8). Independent review found and
live-reproduced a catastrophic-backtracking regex --
`_UV_RUN_PREFIX`'s own former ``-{1,2}[\\w-]+`` shape -- inside
`.github/scripts/gitapex_gate_bare_python3_invocation.py`, exercised
against untrusted PR content in a required CI job with no path filter. No
existing gate screened a new regex literal for this defect class before
this one.

Per this repository's defeat-test-disclosure process, several tests below
are specifically constructed to defeat -- not merely exercise the happy
path of -- the new detection logic; see the `test_defeat_*` and
`test_regression_*` tests below. The regression tests are this issue's own
required proof method: confirm the gate fails against a reintroduced
instance of the original defect, then passes against its actual fix.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_regex_catastrophic_backtracking as gate
import pytest
from conftest import FakeStdin as _FakeStdin
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

_FIXTURE_PATH = "hooks/gitapex_check_fixture.py"

# The exact historical defect: `_UV_RUN_PREFIX`'s own former shape, standing
# alone as `_PREFIX_RE`'s own compiled pattern -- reconstructing issue
# #1556's own motivating defect, ported to a fixture module rather than
# the real file (whose own current, already-fixed regex this gate must
# *not* flag -- see test_regression_the_actual_fix_is_clean below).
_HISTORICAL_DEFECT_SOURCE = 'import re\n\n_PREFIX_RE = re.compile(r"-{1,2}[\\w-]+")\n'

# The real, current (already-fixed) `_UV_RUN_PREFIX` shape from
# gitapex_gate_bare_python3_invocation.py -- a nested-but-anchored group
# this gate's own Shape A is deliberately narrow enough not to flag (see
# that gate's own module docstring).
_ACTUAL_FIX_SOURCE = (
    "import re\n\n"
    '_UV_RUN_PREFIX = r"\\buv\\s+run(?:\\s+-[\\w-]+(?:=\\S+)?)*\\s+"\n'
    '_UV_WRAPPED_INVOCATION_RE = re.compile(_UV_RUN_PREFIX + r"python3\\s+\\S+\\.py")\n'
)

# Textbook nested-quantifier evil regex, `(a+)+`, assigned then compiled --
# this repository's own idiom of a prefix constant composed into a `_RE`.
_NESTED_QUANTIFIER_SOURCE = 'import re\n\n_EVIL_RE = re.compile(r"(a+)+")\n'

# A safe, disjoint-adjacent-classes pattern: digits then letters share no
# member, so Shape B must not fire.
_SAFE_SOURCE = 'import re\n\n_SAFE_RE = re.compile(r"^[0-9]+[a-z]+$")\n'

# Same overlapping shape as the historical defect, but with an inline
# waiver comment on the compile call's own line.
_WAIVED_SOURCE = (
    'import re\n\n_PREFIX_RE = re.compile(r"-{1,2}[\\w-]+")  # regex-catastrophic-backtracking: WAIVED: bounded input\n'
)

# The compile call's own pattern argument is a runtime f-string -- this
# gate cannot resolve it to a concrete string, so it is silently out of
# scope (a disclosed miss, not a defect).
_DYNAMIC_PATTERN_SOURCE = 'import re\n\ndef build(suffix):\n    return re.compile(f"-{{1,2}}[\\\\w-]+{suffix}")\n'

# A receiver-agnostic `.fullmatch()` bound-method call on an already-built
# pattern object -- category (a)'s bound-method half is deliberately not
# graded by this gate (see its own module docstring); only the `.compile()`
# call site itself is a trigger.
_BOUND_METHOD_ONLY_SOURCE = (
    'import re\n\n_SOME_RE = re.compile(r"^[a-z]+$")\n\n\ndef check(x):\n    return _SOME_RE.fullmatch(x)\n'
)

# A diff whose hunk header cannot be parsed.
_UNPARSEABLE_HUNK_DIFF = (
    f"diff --git a/x.py b/{_FIXTURE_PATH}\n--- a/x.py\n+++ b/{_FIXTURE_PATH}\n@@ garbage @@\n+x = 1\n"
)

# A diff whose `+++ ` post-image header is reached outside a hunk with no
# `--- ` source header before it.
_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF = (
    f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
    f"+++ b/{_FIXTURE_PATH}\n"
    "@@ -0,0 +1,2 @@\n"
    "+import re\n"
    '+_PREFIX_RE = re.compile(r"-{1,2}[\\w-]+")\n'
)


# --- helpers ---------------------------------------------------------------


def _whole_file_diff(path: str, source: str) -> str:
    lines = source.split("\n")
    body = "".join("+" + line + "\n" for line in lines)
    return f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + body


def _partial_diff(path: str, source: str, added: list[int]) -> str:
    lines = source.split("\n")
    hunks = "".join(f"@@ -{number},0 +{number},1 @@\n+{lines[number - 1]}\n" for number in added)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{hunks}"


def _write(root: pathlib.Path, relative: str, source: str) -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _grade(tmp_path: pathlib.Path, source: str, *, relative: str = _FIXTURE_PATH) -> list[gate.Finding]:
    """Write `source` at `relative`, grade it as wholly added, return violations."""
    _write(tmp_path, relative, source)
    violations, _waived, graded = gate.find_violations(_whole_file_diff(relative, source), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations


def _grade_added(
    tmp_path: pathlib.Path, source: str, added: list[int], *, relative: str = _FIXTURE_PATH
) -> tuple[list[gate.Finding], list[gate.Finding]]:
    _write(tmp_path, relative, source)
    violations, waived, graded = gate.find_violations(_partial_diff(relative, source, added), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations, waived


# --- shape detection: has_catastrophic_shape() ------------------------------


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        (r"-{1,2}[\w-]+", "adjacent-overlap"),  # the historical defect, standing alone
        (r"(a+)+", "nested-quantifier"),
        (r"(a*)*", "nested-quantifier"),
        (r"(a+)*", "nested-quantifier"),
        (r"[0-9]+[a-zA-Z0-9_]+", "adjacent-overlap"),  # digit class is a subset of word class
        (r".+[a-z]+", "adjacent-overlap"),  # `.` is treated as wide/unresolved
    ],
)
def test_true_positive_shapes_are_detected(pattern: str, expected: str) -> None:
    assert gate.has_catastrophic_shape(pattern) == expected


@pytest.mark.parametrize(
    "pattern",
    [
        r"^[a-z0-9_]+$",  # a single quantified class, nothing adjacent to overlap with
        r"[0-9]+[a-z]+",  # digits and lowercase letters share no member
        r"-{2}[\w-]+",  # a fixed-count `{2}` is never the ambiguous half
        r"\buv\s+run(?:\s+-[\w-]+(?:=\S+)?)*\s+",  # this gate's own motivating file's real, fixed prefix
        r"\s+\S+",  # a shorthand class and its own precise negation never overlap
        r"\d+\D+",
        r"\w+\W+",
        r"\s+.+?:",  # a lazy quantifier is treated as non-ambiguous
        r"(a+?)+",  # a lazy inner atom inside a repeating group: disclosed miss, not flagged
    ],
)
def test_true_negative_safe_patterns_are_not_flagged(pattern: str) -> None:
    assert gate.has_catastrophic_shape(pattern) is None


def test_defeat_negation_of_different_bases_still_overlaps() -> None:
    """`\\S` (not-whitespace) and `\\D` (not-digit) share plenty of real
    characters (any letter, for one) -- a naive "any two negations never
    overlap" simplification would wrongly clear this pair; confirms
    `_overlaps` actually compares the two `_Negated` bases rather than
    treating every negation as mutually safe."""
    assert gate.has_catastrophic_shape(r"\S+\D+") == "adjacent-overlap"


def test_defeat_negation_overlaps_a_set_not_fully_contained_in_its_base() -> None:
    """`\\S` (not-whitespace) does overlap `[a-z]` (no letter is whitespace)
    -- confirms the containment check is not accidentally inverted."""
    assert gate.has_catastrophic_shape(r"\S+[a-z]+") == "adjacent-overlap"


def test_overlaps_direct_calls_true_and_false_cases() -> None:
    """Direct calls to `_overlaps` (not merely through `has_catastrophic_
    shape`'s own indirection) -- a plain overlap, a plain disjoint pair, and
    the unknown-class `None` fail-closed default."""
    assert gate._overlaps(frozenset("a"), frozenset("ab")) is True
    assert gate._overlaps(frozenset("a"), frozenset("b")) is False
    assert gate._overlaps(None, frozenset("a")) is True


def test_malformed_character_class_raises_scan_error() -> None:
    with pytest.raises(gate.ScanError):
        gate.has_catastrophic_shape(r"[a-z")


# --- shape detection: parser edge cases (quantifiers, groups, classes) -----


def test_alternation_isolates_adjacency_between_branches() -> None:
    """`a+b+` on one branch never counts as adjacent to `c+` on the other --
    each `|` branch is an independent path through the engine."""
    assert gate.has_catastrophic_shape(r"[0-9]+[a-z]+|c+") is None


def test_alternation_still_detects_an_overlap_inside_a_later_branch() -> None:
    assert gate.has_catastrophic_shape(r"[a-z]+|[0-9]+[a-zA-Z0-9_]+") == "adjacent-overlap"


def test_unbalanced_closing_paren_at_top_level_is_skipped_not_raised() -> None:
    """A stray `)` with no matching `(` at top level is skipped rather than
    raising -- this gate reads a pattern already accepted by `re.compile`
    at runtime elsewhere, so a genuinely unbalanced pattern never reaches
    it; this only bounds this gate's own parser against garbage input."""
    assert gate.has_catastrophic_shape(r"a+)[0-9]+[a-zA-Z0-9_]+") == "adjacent-overlap"


def test_lookahead_group_is_parsed() -> None:
    assert gate.has_catastrophic_shape(r"(?=a+)[0-9]+[a-zA-Z0-9_]+") == "adjacent-overlap"


def test_negative_lookahead_group_is_parsed() -> None:
    assert gate.has_catastrophic_shape(r"(?!a+)[0-9]+[a-zA-Z0-9_]+") == "adjacent-overlap"


def test_lookbehind_group_is_parsed() -> None:
    assert gate.has_catastrophic_shape(r"(?<=a+)[0-9]+[a-zA-Z0-9_]+") == "adjacent-overlap"


def test_negative_lookbehind_group_is_parsed() -> None:
    assert gate.has_catastrophic_shape(r"(?<!a+)[0-9]+[a-zA-Z0-9_]+") == "adjacent-overlap"


def test_named_group_nested_quantifier_is_detected() -> None:
    assert gate.has_catastrophic_shape(r"(?P<rep>a+)+") == "nested-quantifier"


def test_named_group_with_no_closing_angle_bracket_does_not_crash() -> None:
    """A malformed `(?P` with no `>` -- this gate's own parser skips two
    characters and continues rather than crashing on a pattern shape that
    would fail `re.compile` at runtime anyway. The two skipped characters
    land inside the group's own content as an extra atom (`x` here),
    which is why this specific malformed input no longer reads as the
    single-atom branch Shape A requires -- not raising is the property
    under test, not preserving detection on a shape `re.compile` itself
    would reject."""
    assert gate.has_catastrophic_shape(r"(?Pxa+)+") is None


def test_doubly_nested_group_still_detects_shape_a() -> None:
    assert gate.has_catastrophic_shape(r"((a+)+)") == "nested-quantifier"


def test_doubly_nested_group_still_detects_shape_b() -> None:
    assert gate.has_catastrophic_shape(r"(([0-9]+[a-zA-Z0-9_]+))") == "adjacent-overlap"


def test_lazy_optional_is_parsed() -> None:
    assert gate.has_catastrophic_shape(r"a??[0-9]+[a-z]+") is None


def test_unterminated_bounded_quantifier_is_not_treated_as_one() -> None:
    """`a{2` with no closing `}` is not a real `{m,n}` quantifier shape --
    left unconsumed rather than guessed at."""
    assert gate.has_catastrophic_shape(r"a{2[0-9]+[a-z]+") is None


def test_brace_expression_with_no_digits_is_not_a_quantifier() -> None:
    assert gate.has_catastrophic_shape(r"a{name}[0-9]+[a-z]+") is None


def test_lazy_bounded_quantifier_is_treated_as_non_ambiguous() -> None:
    assert gate.has_catastrophic_shape(r"a{2,4}?[0-9]+[a-z]+") is None


def test_negated_bracket_class_is_treated_as_wide() -> None:
    assert gate.has_catastrophic_shape(r"[^a-z]+[0-9]+") == "adjacent-overlap"


def test_negated_shorthand_inside_a_bracket_class_is_treated_as_wide() -> None:
    assert gate.has_catastrophic_shape(r"[\S]+[0-9]+") == "adjacent-overlap"


def test_escaped_literal_inside_a_bracket_class_is_resolved() -> None:
    assert gate.has_catastrophic_shape(r"[\.]+[0-9]+") is None


def test_reversed_range_inside_a_bracket_class_is_treated_as_wide() -> None:
    assert gate.has_catastrophic_shape(r"[z-a]+[0-9]+") == "adjacent-overlap"


def test_class_member_set_direct_call_resolves_bracket_members() -> None:
    """Direct call to `_class_member_set` -- the parser edge-case tests
    above only reach it through `_parse_branches`'s own indirection."""
    members, next_index = gate._class_member_set("[abc]", 0)
    assert members == frozenset("abc")
    assert next_index == 5


def test_nested_quantifier_findings_direct_call() -> None:
    """Direct call to `_nested_quantifier_findings` on a hand-built
    `(a+)+`-shaped branch list -- `has_catastrophic_shape`'s own tests
    above only reach it through the full parse pipeline."""
    inner = gate._Atom(is_group=False, char_set=frozenset("a"), repeats=True)
    group = gate._Atom(is_group=True, char_set=None, repeats=True, group_branches=((inner,),))
    assert gate._nested_quantifier_findings([[group]]) is True
    non_repeating = gate._Atom(is_group=False, char_set=frozenset("a"), repeats=False)
    assert gate._nested_quantifier_findings([[non_repeating]]) is False


def test_overlapping_adjacent_findings_direct_call() -> None:
    """Direct call to `_overlapping_adjacent_findings` on a hand-built pair
    of adjacent overlapping repeating atoms."""
    first = gate._Atom(is_group=False, char_set=frozenset("a"), repeats=True)
    second = gate._Atom(is_group=False, char_set=frozenset("a"), repeats=True)
    assert gate._overlapping_adjacent_findings([[first, second]]) is True
    disjoint = gate._Atom(is_group=False, char_set=frozenset("b"), repeats=True)
    assert gate._overlapping_adjacent_findings([[first, disjoint]]) is False


# --- AST extraction: which regex literals are graded ------------------------


def test_string_constants_direct_call() -> None:
    """Direct call to `_string_constants` -- the AST-extraction tests above
    only reach it through `_regex_literal_calls`'s own indirection."""
    tree = __import__("ast").parse('X = "abc"\nY = X + "def"\n')
    assert gate._string_constants(tree) == {"X": "abc", "Y": "abcdef"}


def test_resolve_literal_string_direct_call() -> None:
    tree = __import__("ast").parse('X = "abc"\n')
    assert gate._resolve_literal_string(tree.body[0].value, {}) == "abc"
    unresolvable = __import__("ast").parse("X = some_call()\n").body[0].value
    assert gate._resolve_literal_string(unresolvable, {}) is None


def test_pattern_argument_direct_call() -> None:
    positional = __import__("ast").parse('re.compile("abc")').body[0].value
    assert isinstance(gate._pattern_argument(positional), __import__("ast").Constant)
    keyword_only = __import__("ast").parse('re.compile(pattern="abc")').body[0].value
    assert isinstance(gate._pattern_argument(keyword_only), __import__("ast").Constant)
    no_pattern = __import__("ast").parse("re.compile()").body[0].value
    assert gate._pattern_argument(no_pattern) is None


def test_module_qualified_compile_call_is_graded() -> None:
    tree = __import__("ast").parse(_HISTORICAL_DEFECT_SOURCE)
    found = gate._regex_literal_calls(tree)
    assert found == [(3, r"-{1,2}[\w-]+")]


def test_aliased_re_import_is_resolved() -> None:
    source = 'import re as _re\n\n_PREFIX_RE = _re.compile(r"-{1,2}[\\w-]+")\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == [(3, r"-{1,2}[\w-]+")]


def test_string_constant_composed_via_plus_is_resolved() -> None:
    """The exact real-world idiom: a reusable prefix constant, `+`-composed
    into the actual compiled pattern -- `_UV_RUN_PREFIX` into
    `_UV_WRAPPED_INVOCATION_RE` in this gate's own motivating file."""
    tree = __import__("ast").parse(_ACTUAL_FIX_SOURCE)
    found = dict(gate._regex_literal_calls(tree))
    assert 4 in found
    assert found[4] == r"\buv\s+run(?:\s+-[\w-]+(?:=\S+)?)*\s+python3\s+\S+\.py"


def test_bound_method_call_is_not_a_trigger() -> None:
    """Category (a)'s bound-method half (`.fullmatch()` etc.) is
    deliberately not graded here -- only the `.compile()` call site is
    (see the module docstring)."""
    tree = __import__("ast").parse(_BOUND_METHOD_ONLY_SOURCE)
    found = gate._regex_literal_calls(tree)
    assert found == [(3, "^[a-z]+$")]


def test_a_name_assigned_more_than_once_is_unresolvable() -> None:
    source = 'import re\n\n_X = "a"\n_X = "b"\n_PATTERN_RE = re.compile(_X)\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == []


def test_a_dynamic_pattern_is_out_of_scope() -> None:
    tree = __import__("ast").parse(_DYNAMIC_PATTERN_SOURCE)
    assert gate._regex_literal_calls(tree) == []


def test_defeat_a_function_local_name_never_collides_with_a_module_level_constant() -> None:
    """Independent review live-confirmed a real false negative in an
    earlier revision: `_string_constants` walked the whole tree with no
    scope distinction, so an unrelated function-local `_TMP` in one
    function collided with (and, via the "assigned more than once" rule,
    silently dropped resolution of) a genuinely dangerous *module-level*
    `_TMP` constant sharing that name -- the module-level compile call
    went ungraded. `_string_constants` now scopes to `tree.body` only, so
    a function-local assignment of the same name never reaches it at
    all."""
    source = (
        'import re\n\n_TMP = r"-{1,2}[\\w-]+"\n_RE = re.compile(_TMP)\n\n\n'
        'def build_one():\n    _TMP = "harmless"\n    return _TMP\n'
    )
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == [(4, r"-{1,2}[\w-]+")]


def test_a_function_local_name_assignment_is_never_resolved() -> None:
    """The other half of the same scoping fix: a function-local `NAME =
    <literal>` composed into a `re.compile` call inside that same
    function is deliberately never resolved either (disclosed in the
    module docstring's own "Known misses") -- `_string_constants` never
    descends into a function body at all, module-level idiom only."""
    source = 'import re\n\n\ndef build():\n    _TMP = r"-{1,2}[\\w-]+"\n    return re.compile(_TMP)\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == []


def test_a_non_name_assignment_target_is_never_collected() -> None:
    """Tuple-unpacking and attribute assignment are not the simple `NAME =
    <literal>` shape `_string_constants` resolves -- neither crashes it,
    both are silently skipped."""
    source = 'import re\n\na, b = "x", "y"\nsome_obj.attr = "z"\n_PATTERN_RE = re.compile(a)\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == []


def test_a_verb_outside_the_graded_set_is_not_a_trigger() -> None:
    source = 'import re\n\n_RESULT = re.sub(r"-{1,2}[\\w-]+", "", "text")\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == []


def test_compile_with_no_arguments_at_all_is_not_a_trigger() -> None:
    source = "import re\n\n_BROKEN = re.compile()\n"
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == []


def test_pattern_keyword_argument_is_resolved() -> None:
    source = 'import re\n\n_PREFIX_RE = re.compile(pattern=r"-{1,2}[\\w-]+")\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == [(3, r"-{1,2}[\w-]+")]


def test_pattern_keyword_argument_after_a_non_matching_keyword_is_still_found() -> None:
    source = 'import re\n\n_PREFIX_RE = re.compile(flags=0, pattern=r"-{1,2}[\\w-]+")\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == [(3, r"-{1,2}[\w-]+")]


def test_a_binop_with_one_unresolvable_side_is_not_resolved() -> None:
    source = 'import re\n\n_X = "a" + str(1)\n_PATTERN_RE = re.compile(_X)\n'
    tree = __import__("ast").parse(source)
    assert gate._regex_literal_calls(tree) == []


def test_a_non_re_module_import_is_not_added_to_re_names() -> None:
    source = 'import os\nimport re\n\n_PREFIX_RE = re.compile(r"-{1,2}[\\w-]+")\n'
    tree = __import__("ast").parse(source)
    assert gate._re_module_names(tree) == frozenset({"re"})
    assert gate._regex_literal_calls(tree) == [(4, r"-{1,2}[\w-]+")]


# --- scope: in_scope() boundary pins ----------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "hooks/gitapex_check_fixture.py",
        ".github/scripts/gitapex_gate_fixture.py",
        "skills/some-skill/scripts/gitapex_check_fixture.py",
        "docs/example_script.py",
    ],
)
def test_in_scope_paths_are_recognised(path: str) -> None:
    assert gate.in_scope(path)


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_fixture.py",
        "hooks/conftest.py",
        "docs/example.md",
        "README",
    ],
)
def test_out_of_scope_paths_are_not_graded(path: str) -> None:
    assert not gate.in_scope(path)


# --- end-to-end grading: find_violations() / findings_for_source() ---------


def test_true_positive_historical_defect_shape_added_by_diff(tmp_path: pathlib.Path) -> None:
    violations = _grade(tmp_path, _HISTORICAL_DEFECT_SOURCE)
    assert len(violations) == 1
    assert violations[0].line == 3
    assert violations[0].shape == "adjacent-overlap"


def test_true_positive_nested_quantifier_shape(tmp_path: pathlib.Path) -> None:
    violations = _grade(tmp_path, _NESTED_QUANTIFIER_SOURCE)
    assert len(violations) == 1
    assert violations[0].shape == "nested-quantifier"


def test_true_negative_safe_pattern(tmp_path: pathlib.Path) -> None:
    assert _grade(tmp_path, _SAFE_SOURCE) == []


def test_regression_the_actual_fix_is_clean(tmp_path: pathlib.Path) -> None:
    """Issue #1556's own required proof method, second half: the real,
    current `_UV_RUN_PREFIX`/`_UV_WRAPPED_INVOCATION_RE` shape from
    `gitapex_gate_bare_python3_invocation.py` -- already fixed -- must not
    be flagged."""
    assert _grade(tmp_path, _ACTUAL_FIX_SOURCE) == []


def test_findings_for_source_direct_call() -> None:
    """Direct call to `findings_for_source` -- the other end-to-end tests in
    this section only reach it through `find_violations`'s own indirection."""
    violations, waived = gate.findings_for_source("x.py", _NESTED_QUANTIFIER_SOURCE, {3})
    assert waived == []
    assert len(violations) == 1
    assert violations[0].shape == "nested-quantifier"


def test_waived_finding_is_reported_separately(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, _WAIVED_SOURCE)
    violations, waived, graded = gate.find_violations(_whole_file_diff(_FIXTURE_PATH, _WAIVED_SOURCE), tmp_path)
    assert graded == 1
    assert violations == []
    assert len(waived) == 1
    assert waived[0].shape == "adjacent-overlap"


def test_a_pre_existing_defect_untouched_by_the_diff_is_not_graded(tmp_path: pathlib.Path) -> None:
    """Only a trigger an added line actually reaches is graded -- a
    pre-existing pattern another PR already owns is never this diff's
    failure."""
    source = _HISTORICAL_DEFECT_SOURCE + "\n\ndef other():\n    return 1\n"
    violations, _waived = _grade_added(tmp_path, source, added=[6])
    assert violations == []


def test_out_of_scope_file_is_never_graded(tmp_path: pathlib.Path) -> None:
    relative = "tests/test_fixture.py"
    _write(tmp_path, relative, _HISTORICAL_DEFECT_SOURCE)
    violations, waived, graded = gate.find_violations(_whole_file_diff(relative, _HISTORICAL_DEFECT_SOURCE), tmp_path)
    assert (violations, waived, graded) == ([], [], 0)


def test_diff_touching_no_python_file_grades_nothing(tmp_path: pathlib.Path) -> None:
    diff = "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -0,0 +1,1 @@\n+hello\n"
    violations, waived, graded = gate.find_violations(diff, tmp_path)
    assert (violations, waived, graded) == ([], [], 0)


def test_file_named_by_the_diff_but_missing_raises_scan_error(tmp_path: pathlib.Path) -> None:
    diff = _whole_file_diff(_FIXTURE_PATH, _HISTORICAL_DEFECT_SOURCE)  # never written to tmp_path
    with pytest.raises(gate.ScanError, match="missing from"):
        gate.find_violations(diff, tmp_path)


def test_a_file_that_cannot_be_parsed_as_python_raises_scan_error(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, "def broken(:\n")
    diff = _whole_file_diff(_FIXTURE_PATH, "def broken(:\n")
    with pytest.raises(gate.ScanError, match="cannot be parsed"):
        gate.find_violations(diff, tmp_path)


def test_an_unparseable_resolved_pattern_is_silently_skipped(tmp_path: pathlib.Path) -> None:
    """A resolved pattern this gate's own parser cannot walk (an
    unterminated character class) is not this gate's defect class to
    grade -- `re.compile` itself already rejects it at runtime, and this
    gate's own job is catastrophic-backtracking shape, not general regex
    validity."""
    source = 'import re\n\n_BROKEN_RE = re.compile(r"[a-z")\n'
    assert _grade(tmp_path, source) == []


def test_a_file_that_cannot_be_decoded_as_utf8_raises_scan_error(tmp_path: pathlib.Path) -> None:
    absolute = tmp_path / _FIXTURE_PATH
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(b"\xff\xfe not utf-8 at all")
    diff = _whole_file_diff(_FIXTURE_PATH, "placeholder\n")
    with pytest.raises(gate.ScanError, match="cannot be read as UTF-8"):
        gate.find_violations(diff, tmp_path)


# --- parse_added_lines: malformed-diff fail-closed regressions -------------


def test_unparseable_hunk_header_raises_scan_error() -> None:
    with pytest.raises(gate.ScanError, match="unparseable hunk header"):
        gate.parse_added_lines(_UNPARSEABLE_HUNK_DIFF)


def test_post_image_header_with_no_source_header_raises_scan_error() -> None:
    with pytest.raises(gate.ScanError, match="no `--- ` source header"):
        gate.parse_added_lines(_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF)


def test_hunk_declaring_more_lines_than_its_body_has_raises_scan_error() -> None:
    diff = f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n--- /dev/null\n+++ b/{_FIXTURE_PATH}\n@@ -0,0 +1,5 @@\n+import re\n"
    with pytest.raises(gate.ScanError, match="declared more pre-/post-image line"):
        gate.parse_added_lines(diff)


def test_non_b_prefixed_post_image_path_raises_scan_error() -> None:
    diff = f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n--- a/{_FIXTURE_PATH}\n+++ z_something_odd\n@@ -1,0 +1,1 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="not a plain b/-prefixed path"):
        gate.parse_added_lines(diff)


def test_a_deleted_file_post_image_is_dev_null_and_adds_nothing() -> None:
    diff = f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n--- a/{_FIXTURE_PATH}\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-x = 1\n"
    assert gate.parse_added_lines(diff) == {}


def test_context_lines_advance_lineno_without_being_recorded_as_added(tmp_path: pathlib.Path) -> None:
    """A `git diff` invocation with real context (not this gate's own
    `-U0`-wired form) must still correlate line numbers correctly -- only
    `+`-prefixed lines are ever recorded as added."""
    diff = (
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -1,3 +1,4 @@\n"
        " import re\n"
        " \n"
        '+_PREFIX_RE = re.compile(r"-{1,2}[\\w-]+")\n'
        " def other():\n"
    )
    added = gate.parse_added_lines(diff)
    assert added == {_FIXTURE_PATH: {3}}


def test_absorbed_header_ambiguity_raises_scan_error() -> None:
    """An over-declared hunk whose excess is small enough that a genuinely-
    following file's own real `--- `/`+++ ` pair gets fully absorbed as
    fake removal/addition content, draining both counters to exactly zero
    right on the `+++ ` line, immediately before what looks like a new
    hunk header, is ambiguous between coincidental hunk-closing content
    and a real file transition missing its `diff --git ` separator --
    fails closed rather than silently misattributing whatever follows."""
    diff = (
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/other.py\n"
        "+++ b/other.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+x = 1\n"
    )
    with pytest.raises(gate.ScanError, match="closes exactly on a line shaped like"):
        gate.parse_added_lines(diff)


def test_an_added_line_inside_a_dev_null_post_image_hunk_is_not_recorded() -> None:
    """A synthetic, non-`git`-produced diff whose post-image is `/dev/null`
    (`path` is `None`) but whose hunk body still carries a `+`-prefixed
    line: the line is never recorded, since there is no real path to
    attribute it to."""
    diff = f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n--- a/{_FIXTURE_PATH}\n+++ /dev/null\n@@ -1,0 +1,1 @@\n+x = 1\n"
    assert gate.parse_added_lines(diff) == {}


def test_a_header_shaped_pair_not_followed_by_a_new_header_does_not_raise() -> None:
    """The same `--- `/`+++ `-shaped absorbed-content pair as the ambiguity
    regression above, but followed by ordinary content rather than
    anything hunk- or file-header-shaped: the second condition the
    ambiguity check requires never holds, so this is read as coincidental
    hunk-closing content, not raised."""
    diff = (
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/other.py\n"
        "+++ b/other.py\n"
    )
    added = gate.parse_added_lines(diff)
    # The absorbed `+++ b/other.py` line is itself `+`-prefixed content
    # under the still-current path (this file's own real header, above) --
    # recorded exactly as any other addition would be, since nothing in
    # this specific diff shape raised.
    assert added == {_FIXTURE_PATH: {1}}


def test_deletion_only_hunk_does_not_misattribute_the_next_file(tmp_path: pathlib.Path) -> None:
    """A pure-deletion hunk (`@@ -a,b +c,0 @@`, zero post-image lines) must
    still correctly bound its own removal lines via the pre-image counter,
    per this function's own dual-counter design."""
    diff = (
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -1,2 +1,0 @@\n"
        "-import re\n"
        f'-_PREFIX_RE = re.compile(r"-{{1,2}}[\\w-]+")\n'
        "diff --git a/other.py b/other.py\n"
        "--- /dev/null\n"
        "+++ b/other.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+x = 1\n"
    )
    added = gate.parse_added_lines(diff)
    assert _FIXTURE_PATH not in added
    assert added.get("other.py") == {1}


# --- CLI: main() --------------------------------------------------------


def test_main_exits_0_on_a_clean_diff(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, _FIXTURE_PATH, _SAFE_SOURCE)
    monkeypatch.setattr("sys.stdin", _FakeStdin(_whole_file_diff(_FIXTURE_PATH, _SAFE_SOURCE).encode("utf-8")))
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 0
    assert "OK:" in capsys.readouterr().out


def test_main_exits_1_on_a_violation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, _FIXTURE_PATH, _HISTORICAL_DEFECT_SOURCE)
    monkeypatch.setattr(
        "sys.stdin", _FakeStdin(_whole_file_diff(_FIXTURE_PATH, _HISTORICAL_DEFECT_SOURCE).encode("utf-8"))
    )
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "adjacent-overlap" in stderr
    assert "regex-catastrophic-backtracking: WAIVED" in stderr


def test_main_exits_2_on_a_malformed_diff(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", _FakeStdin(_UNPARSEABLE_HUNK_DIFF.encode("utf-8")))
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 2
    assert "unparseable hunk header" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_does_not_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", _FakeStdin(b""))
    exit_code = gate.main(["--root", "/no/such/directory"])
    assert exit_code == 2


def test_root_must_exist_direct_call_rejects_a_non_directory() -> None:
    """Direct call to the pydantic field validator `_root_must_exist` --
    the exit-2 test above only reaches it through `main`'s own
    `GateRegexCatastrophicBacktrackingArgs` construction."""
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateRegexCatastrophicBacktrackingArgs._root_must_exist(pathlib.Path("/no/such/directory"))


def test_main_reads_diff_from_a_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, _FIXTURE_PATH, _SAFE_SOURCE)
    diff_file = tmp_path / "the.diff"
    diff_file.write_text(_whole_file_diff(_FIXTURE_PATH, _SAFE_SOURCE), encoding="utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_file)])
    assert exit_code == 0


def test_main_exits_2_on_non_utf8_stdin(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", _FakeStdin(b"\xff\xfe not utf-8"))
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 2
    assert "cannot be read as UTF-8" in capsys.readouterr().err


def test_main_prints_a_waived_finding_and_still_exits_0(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, _FIXTURE_PATH, _WAIVED_SOURCE)
    monkeypatch.setattr("sys.stdin", _FakeStdin(_whole_file_diff(_FIXTURE_PATH, _WAIVED_SOURCE).encode("utf-8")))
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 0
    stderr = capsys.readouterr().err
    assert "waived inline" in stderr
    assert "adjacent-overlap" in stderr


def test_main_exits_2_on_non_utf8_diff_file(tmp_path: pathlib.Path) -> None:
    diff_file = tmp_path / "bad.diff"
    diff_file.write_bytes(b"\xff\xfe not utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_file)])
    assert exit_code == 2


# --- workflow drift: .github/workflows/regex-catastrophic-backtracking-gate.yml --


_WORKFLOW_NAME = "regex-catastrophic-backtracking-gate.yml"


def test_the_workflow_has_no_paths_filter() -> None:
    assert_workflow_has_no_trigger_path_filter(_WORKFLOW_NAME)


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    assert_workflow_checkout_pins_head_sha_with_full_history(_WORKFLOW_NAME)


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    assert_workflow_feeds_merge_base_to(_WORKFLOW_NAME, "diff")


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    assert_workflow_diff_carries_flags(_WORKFLOW_NAME, "--no-renames", "-c core.quotePath=false")

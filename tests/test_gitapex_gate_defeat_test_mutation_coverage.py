"""Tests for the defeat-test mutation-coverage gate
(.github/scripts/gitapex_gate_defeat_test_mutation_coverage.py).

Issue #1799. Mirrors tests/test_gitapex_gate_function_body_test_coverage.py's
own fixture/assertion style for "a gate of this exact shape": synthetic
unified-diff-text fixtures, tmp_path-based --root trees, and direct calls
into the gate module's own functions rather than only subprocess CLI
invocation. Unlike either sibling gate, this one's own core mechanism
actually runs a real `pytest` subprocess against a temporarily mutated copy
of a source file -- most tests below exercise the pure grading/splicing
logic directly (no subprocess spawned), and a smaller, representative subset
exercises the real end-to-end mutation-and-rerun path per element category,
per this repository's own defeat-test-disclosure convention.

Per that convention, at least one test below is specifically constructed to
defeat -- not merely exercise the happy path of -- the new detection logic;
see the `test_defeat_*`/`*_vacuous_test_*` tests. This is also the red-then-
green proof issue #1799's own six ACM rows require verbatim: each of the
three `test_end_to_end_*` pairs below first proves the gate reports a
`defeat-test-mutation-gap` finding against a vacuous fixture (red), then
proves it reports clean once that same fixture's own paired test is fixed to
genuinely assert the mutated element (green).
"""

from __future__ import annotations

import ast
import pathlib

import gitapex_gate_defeat_test_mutation_coverage as gate
import pytest
from conftest import FakeStdin as _FakeStdin
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

# --- helpers -----------------------------------------------------------------


def _whole_file_diff(path: str, source: str) -> str:
    """A unified diff in which every line of `source` is an added line."""
    lines = source.split("\n")
    body = "".join("+" + line + "\n" for line in lines)
    return f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + body


def _partial_diff(path: str, source: str, added: list[int]) -> str:
    """A unified diff adding only the 1-based line numbers in `added`."""
    lines = source.split("\n")
    hunks = "".join(f"@@ -{number},0 +{number},1 @@\n+{lines[number - 1]}\n" for number in added)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{hunks}"


def _write(root: pathlib.Path, relative: str, source: str) -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _line_starts(source: str) -> list[int]:
    return gate._line_byte_starts(source.encode("utf-8"))


def _first_expr_value(tree: ast.Module) -> ast.expr:
    """The `.value` of `tree.body[0]`, asserted to be a bare expression
    statement first -- `ast.stmt` itself has no `.value` attribute, only
    `ast.Expr` does, so every call site below needs this narrowing."""
    first = tree.body[0]
    assert isinstance(first, ast.Expr)
    return first.value


# --- scope: in_scope() boundary pins -----------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "skills/foo/scripts/gitapex_check_bar.py",
        ".github/scripts/gitapex_gate_bar.py",
        "skills/foo/scripts/some_util.py",
        ".github/scripts/some_util.py",
        "hooks/gitapex_check_bar.py",
        "hooks/some_util.py",
    ],
)
def test_in_scope_paths_are_recognised(path: str) -> None:
    assert gate.in_scope(path)


@pytest.mark.parametrize(
    "path",
    [
        "skills/foo/scripts/test_bar.py",
        "skills/foo/scripts/conftest.py",
        ".github/scripts/test_bar.py",
        ".github/scripts/conftest.py",
        "hooks/test_bar.py",
        "hooks/conftest.py",
        "evals/scripts/gitapex_run_ablation.py",
        "skills/foo/scripts/sub/bar.py",
        ".github/scripts/sub/bar.py",
        "hooks/sub/bar.py",
        "skills/foo/bar.py",
        "tests/test_foo.py",
    ],
)
def test_out_of_scope_paths_are_not_graded(path: str) -> None:
    assert not gate.in_scope(path)


# --- _stem / _test_relative_paths --------------------------------------------


def test_stem_strips_directory_and_suffix() -> None:
    assert gate._stem(".github/scripts/gitapex_gate_foo.py") == "gitapex_gate_foo"


def test_test_relative_paths_names_both_candidates() -> None:
    assert gate._test_relative_paths("gitapex_gate_foo") == (
        "tests/test_gitapex_gate_foo.py",
        "tests/test_gitapex_gate_foo_properties.py",
    )


# --- byte-offset plumbing -----------------------------------------------------


def test_split_bom_strips_a_leading_bom() -> None:
    data = b"\xef\xbb\xbfx = 1\n"
    bom, body = gate._split_bom(data)
    assert bom == b"\xef\xbb\xbf"
    assert body == b"x = 1\n"


def test_split_bom_is_a_no_op_without_one() -> None:
    data = b"x = 1\n"
    assert gate._split_bom(data) == (b"", data)


def test_line_byte_starts_matches_a_multiline_file() -> None:
    body = b"a\nbb\nccc\n"
    assert gate._line_byte_starts(body) == [0, 2, 5, 9]


def test_node_byte_span_accounts_for_a_multibyte_character_earlier_on_the_line() -> None:
    """`ast` col_offset/end_col_offset are UTF-8 *byte* offsets, confirmed
    directly: a non-ASCII character earlier on the same line shifts them
    past where a naive character-index slice would land. This is the exact
    property `_node_byte_span` depends on for every splice this gate does."""
    source = 'x = "héllo|wörld"\n'
    tree = ast.parse(source)
    first_stmt = tree.body[0]
    assert isinstance(first_stmt, ast.Assign)
    node = first_stmt.value
    assert isinstance(node, ast.Constant)
    body = source.encode("utf-8")
    starts = gate._line_byte_starts(body)
    start, end = gate._node_byte_span(node, starts)
    assert body[start:end] == '"héllo|wörld"'.encode()


# --- _removal_span_for_item ---------------------------------------------------


def test_removal_span_for_item_sole_item_removes_only_its_own_span() -> None:
    assert gate._removal_span_for_item([(3, 7)], 0) == (3, 7)


def test_removal_span_for_item_first_of_several_consumes_the_trailing_separator() -> None:
    spans = [(0, 1), (2, 3), (4, 5)]
    assert gate._removal_span_for_item(spans, 0) == (0, 2)


def test_removal_span_for_item_middle_consumes_the_trailing_separator() -> None:
    spans = [(0, 1), (2, 3), (4, 5)]
    assert gate._removal_span_for_item(spans, 1) == (2, 4)


def test_removal_span_for_item_last_consumes_the_leading_separator() -> None:
    spans = [(0, 1), (2, 3), (4, 5)]
    assert gate._removal_span_for_item(spans, 2) == (3, 5)


# --- category 1: regex alternation branch ------------------------------------


def test_re_module_names_includes_bare_re_and_every_alias() -> None:
    tree = ast.parse("import re\nimport re as _re\n")
    assert gate._re_module_names(tree) == frozenset({"re", "_re"})


def test_regex_pattern_literal_accepts_compile_on_re() -> None:
    tree = ast.parse('re.compile("a|b")')
    call = _first_expr_value(tree)
    assert isinstance(call, ast.Call)
    literal = gate._regex_pattern_literal(call, frozenset({"re"}))
    assert literal is not None
    assert literal.value == "a|b"


def test_regex_pattern_literal_accepts_compile_on_an_aliased_import() -> None:
    tree = ast.parse('_re.compile("a|b")')
    call = _first_expr_value(tree)
    assert isinstance(call, ast.Call)
    assert gate._regex_pattern_literal(call, frozenset({"re", "_re"})) is not None


def test_regex_pattern_literal_rejects_compile_on_an_unrelated_name() -> None:
    tree = ast.parse('schema.compile("a|b")')
    call = _first_expr_value(tree)
    assert isinstance(call, ast.Call)
    assert gate._regex_pattern_literal(call, frozenset({"re"})) is None


def test_regex_pattern_literal_is_receiver_agnostic_for_match_search_fullmatch() -> None:
    tree = ast.parse('PATTERN.match("a|b")')
    call = _first_expr_value(tree)
    assert isinstance(call, ast.Call)
    literal = gate._regex_pattern_literal(call, frozenset({"re"}))
    assert literal is not None
    assert literal.value == "a|b"


def test_regex_pattern_literal_rejects_a_non_string_first_argument() -> None:
    tree = ast.parse("re.compile(PATTERN_VAR)")
    call = _first_expr_value(tree)
    assert isinstance(call, ast.Call)
    assert gate._regex_pattern_literal(call, frozenset({"re"})) is None


def test_regex_pattern_literal_rejects_an_unrelated_call() -> None:
    tree = ast.parse('os.path.join("a", "b")')
    call = _first_expr_value(tree)
    assert isinstance(call, ast.Call)
    assert gate._regex_pattern_literal(call, frozenset({"re"})) is None


def test_string_literal_content_span_handles_a_raw_string() -> None:
    raw = b'r"a|b"'
    start, end = gate._string_literal_content_span(raw)
    assert raw[start:end] == b"a|b"


def test_string_literal_content_span_handles_a_plain_string() -> None:
    raw = b'"a|b"'
    start, end = gate._string_literal_content_span(raw)
    assert raw[start:end] == b"a|b"


def test_string_literal_content_span_raises_for_an_unrecognised_token() -> None:
    with pytest.raises(ValueError, match="not a recognisable"):
        gate._string_literal_content_span(b"f-string-shaped-nonsense")


def test_top_level_pipe_positions_finds_plain_pipes() -> None:
    assert gate._top_level_pipe_positions(b"a|b|c") == [1, 3]


def test_top_level_pipe_positions_ignores_a_pipe_inside_parens() -> None:
    assert gate._top_level_pipe_positions(b"(?:a|b)|c") == [7]


def test_top_level_pipe_positions_ignores_a_pipe_inside_a_character_class() -> None:
    assert gate._top_level_pipe_positions(b"[a|b]|c") == [5]


def test_top_level_pipe_positions_ignores_an_escaped_pipe() -> None:
    assert gate._top_level_pipe_positions(rb"a\|b|c") == [4]


def test_alternative_spans_excludes_the_pipe_bytes() -> None:
    content = b"a|b|c"
    positions = gate._top_level_pipe_positions(content)
    assert gate._alternative_spans(content, positions) == [(0, 1), (2, 3), (4, 5)]


def test_regex_alternation_elements_grades_each_top_level_branch(tmp_path: pathlib.Path) -> None:
    source = 'import re\n_RE = re.compile(r"a|b|c")\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    elements = gate._regex_alternation_elements(tree, body, starts, {2})
    assert len(elements) == 3
    for line, category, _message, removal_span in elements:
        assert line == 2
        assert category == gate._REGEX_ALTERNATION
        start, end = removal_span
        mutated = body[:start] + body[end:]
        # Every mutation must leave valid Python behind.
        ast.parse(mutated.decode("utf-8"))


def test_regex_alternation_elements_skips_a_pattern_with_no_top_level_pipe(tmp_path: pathlib.Path) -> None:
    source = 'import re\n_RE = re.compile(r"^[a-z][a-z0-9-]*$")\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._regex_alternation_elements(tree, body, starts, {2}) == []


def test_regex_alternation_elements_skips_a_call_the_diff_never_touches() -> None:
    source = 'import re\n_RE = re.compile(r"a|b")\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._regex_alternation_elements(tree, body, starts, {99}) == []


def test_defeat_regex_alternation_elements_skips_implicit_string_concatenation() -> None:
    """A defeat test for this gate's own narrowing, not the source under
    test: implicit string concatenation must not be misread as a single
    literal token and spliced incorrectly -- it must simply not be graded."""
    source = 'import re\n_RE = re.compile("a|b" "c|d")\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._regex_alternation_elements(tree, body, starts, {2}) == []


# --- category 2: module-level dict/mapping-literal entry --------------------


def test_module_level_dict_assigns_finds_a_const_dict() -> None:
    tree = ast.parse('CONST = {"a": 1, "b": 2}\n')
    result = gate._module_level_dict_assigns(tree)
    assert len(result) == 1
    assert result[0][0] == "CONST"


def test_module_level_dict_assigns_ignores_a_multi_target_assignment() -> None:
    tree = ast.parse('A = B = {"a": 1}\n')
    assert gate._module_level_dict_assigns(tree) == []


def test_module_level_dict_assigns_ignores_a_non_dict_value() -> None:
    tree = ast.parse("CONST = [1, 2]\n")
    assert gate._module_level_dict_assigns(tree) == []


def test_dict_entry_elements_grades_each_touched_entry() -> None:
    source = 'CONST = {\n    "a": 1,\n    "b": 2,\n}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    elements = gate._dict_entry_elements(tree, body, starts, {2, 3})
    assert len(elements) == 2
    for _line, category, message, removal_span in elements:
        assert category == gate._DICT_ENTRY
        assert "CONST" in message
        start, end = removal_span
        mutated = body[:start] + body[end:]
        ns: dict[str, object] = {}
        exec(compile(mutated, "<mutated>", "exec"), ns)  # noqa: S102
        assert isinstance(ns["CONST"], dict)
        assert len(ns["CONST"]) == 1


def test_dict_entry_elements_skips_an_entry_the_diff_never_touches() -> None:
    source = 'CONST = {\n    "a": 1,\n    "b": 2,\n}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    elements = gate._dict_entry_elements(tree, body, starts, {2})
    assert [line for line, *_ in elements] == [2]


def test_defeat_dict_entry_elements_skips_a_dict_with_star_star_unpacking() -> None:
    """A defeat test for this gate's own narrowing: a dict carrying a
    `**`-unpacking entry (a None key) has no key node for that entry, so
    the whole dict is skipped rather than crashing or misattributing."""
    source = 'OTHER = {}\nCONST = {**OTHER, "a": 1}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._dict_entry_elements(tree, body, starts, {2}) == []


# --- category 3: unconditionally emitted literal -----------------------------


def test_enclosing_function_unconditional_returns_the_function_for_a_straight_line_display() -> None:
    tree = ast.parse('def make():\n    return ["a", "b"]\n')
    parents = gate._parent_map(tree)
    list_node = next(node for node in ast.walk(tree) if isinstance(node, ast.List))
    func = gate._enclosing_function_unconditional(list_node, parents)
    assert func is not None
    assert func.name == "make"


def test_enclosing_function_unconditional_returns_none_inside_an_if() -> None:
    tree = ast.parse('def make(flag):\n    if flag:\n        return ["a"]\n    return []\n')
    parents = gate._parent_map(tree)
    list_node = next(node for node in ast.walk(tree) if isinstance(node, ast.List) and node.elts)
    assert gate._enclosing_function_unconditional(list_node, parents) is None


def test_enclosing_function_unconditional_returns_none_at_module_level() -> None:
    tree = ast.parse('CONST = ["a", "b"]\n')
    parents = gate._parent_map(tree)
    list_node = next(node for node in ast.walk(tree) if isinstance(node, ast.List))
    assert gate._enclosing_function_unconditional(list_node, parents) is None


def test_enclosing_function_unconditional_treats_with_as_not_a_guard() -> None:
    source = 'def make():\n    with open("f") as fh:\n        return ["a", "b"]\n'
    tree = ast.parse(source)
    parents = gate._parent_map(tree)
    list_node = next(node for node in ast.walk(tree) if isinstance(node, ast.List))
    func = gate._enclosing_function_unconditional(list_node, parents)
    assert func is not None
    assert func.name == "make"


def test_literal_display_elements_grades_list_items_in_a_function_body() -> None:
    source = 'def make():\n    return ["hidden", "archived"]\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    elements = gate._literal_display_elements(tree, body, starts, {2})
    assert len(elements) == 2
    for line, category, message, removal_span in elements:
        assert line == 2
        assert category == gate._LITERAL_ELEMENT
        assert "make" in message
        start, end = removal_span
        mutated = body[:start] + body[end:]
        ast.parse(mutated.decode("utf-8"))


def test_literal_display_elements_skips_items_inside_an_if_guard() -> None:
    source = 'def make(flag):\n    if flag:\n        return ["a", "b"]\n    return []\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._literal_display_elements(tree, body, starts, {3}) == []


def test_literal_display_elements_skips_a_non_constant_item() -> None:
    source = "def make(x):\n    return [x, 1]\n"
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    elements = gate._literal_display_elements(tree, body, starts, {2})
    assert [message for _line, _cat, message, _span in elements] == [
        "literal element 1 in an unconditionally constructed display inside `make`"
    ]


def test_literal_display_elements_grades_a_dict_entry_value_inside_a_function() -> None:
    source = 'def build():\n    return {"hidden": True, "other": 1}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    elements = gate._literal_display_elements(tree, body, starts, {2})
    assert len(elements) == 2
    assert {message.split(" ")[3] for _line, _cat, message, _span in elements} == {"True", "1"}


def test_literal_display_elements_does_not_double_grade_a_module_level_const_dict() -> None:
    """A module-level `CONST = {...}` dict is category 2's own territory;
    category 3 must skip it entirely, not double-grade its entries."""
    source = 'CONST = {"a": 1, "b": 2}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._literal_display_elements(tree, body, starts, {1}) == []


def test_literal_display_elements_skips_a_none_value() -> None:
    source = 'def build():\n    return {"a": None}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._literal_display_elements(tree, body, starts, {2}) == []


def test_literal_display_elements_skips_a_list_item_the_diff_never_touches() -> None:
    source = 'def make():\n    return ["a", "b"]\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._literal_display_elements(tree, body, starts, {99}) == []


def test_literal_display_elements_skips_a_dict_entry_the_diff_never_touches() -> None:
    source = 'def make():\n    return {"a": 1}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._literal_display_elements(tree, body, starts, {99}) == []


def test_literal_display_elements_skips_dict_entries_inside_an_if_guard() -> None:
    source = 'def make(flag):\n    if flag:\n        return {"a": 1}\n    return {}\n'
    tree = ast.parse(source)
    body = source.encode("utf-8")
    starts = _line_starts(source)
    assert gate._literal_display_elements(tree, body, starts, {3}) == []


# --- waivers -----------------------------------------------------------------


def test_waived_lines_finds_the_commented_line() -> None:
    source = "X = 1  # defeat-test-mutation-coverage: WAIVED: covered elsewhere\n"
    assert gate._waived_lines(source) == {1}


def test_waived_lines_ignores_a_bare_marker_with_no_reason() -> None:
    source = "X = 1  # defeat-test-mutation-coverage: WAIVED\n"
    assert gate._waived_lines(source) == set()


def test_waived_lines_ignores_a_waiver_string_inside_a_string_literal() -> None:
    source = 'X = "# defeat-test-mutation-coverage: WAIVED: not a real comment"\n'
    assert gate._waived_lines(source) == set()


# --- find_violations: end-to-end mutation-and-rerun, one per category -------


def test_end_to_end_category1_vacuous_test_leaves_a_finding_then_fixing_it_clears(tmp_path: pathlib.Path) -> None:
    """Red-then-green proof, category 1 (regex alternation), mirroring
    issue #1799's own #1733/#1735 CR-alternative-prefix-shaped gap: a test
    that only exercises the first of three alternatives leaves the other
    two vacuous."""
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = (
        "import re\n\n"
        '_CONTAINER_PREFIX_RE = re.compile(r"^docker-|^podman-|^ctr-")\n\n\n'
        "def matches(name):\n"
        "    return bool(_CONTAINER_PREFIX_RE.match(name))\n"
    )
    vacuous_test_src = (
        'import gitapex_check_fixture\n\n\ndef test_matches():\n    assert gitapex_check_fixture.matches("docker-1")\n'
    )
    fixed_test_src = (
        "import gitapex_check_fixture\n\n\n"
        "def test_matches():\n"
        '    assert gitapex_check_fixture.matches("docker-1")\n'
        '    assert gitapex_check_fixture.matches("podman-1")\n'
        '    assert gitapex_check_fixture.matches("ctr-1")\n'
    )

    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, vacuous_test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, vacuous_test_src)
    violations, waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert waived == []
    assert [finding.rule for finding in violations] == [gate._MUTATION_GAP, gate._MUTATION_GAP]
    assert any("podman" in finding.message for finding in violations)
    assert any("ctr" in finding.message for finding in violations)

    _write(tmp_path, test_path, fixed_test_src)
    diff_text_fixed = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, fixed_test_src)
    violations_fixed, waived_fixed, graded_fixed = gate.find_violations(diff_text_fixed, tmp_path)
    assert graded_fixed == 1
    assert violations_fixed == []
    assert waived_fixed == []


def test_end_to_end_category2_vacuous_test_leaves_a_finding_then_fixing_it_clears(tmp_path: pathlib.Path) -> None:
    """Red-then-green proof, category 2 (module-level dict entry),
    mirroring issue #1799's own #1990 REVIEW_PERSONA_PERMISSION-shaped
    gap: a test that names only some keys leaves the rest vacuous."""
    fixture_path = "hooks/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = (
        "REVIEW_PERSONA_PERMISSION = {\n"
        '    "correctness": "read-only",\n'
        '    "security": "read-only",\n'
        '    "blast-radius": "read-write",\n'
        "}\n"
    )
    vacuous_test_src = (
        "import gitapex_check_fixture\n\n\n"
        "def test_permission_keys():\n"
        '    assert "correctness" in gitapex_check_fixture.REVIEW_PERSONA_PERMISSION\n'
        '    assert "security" in gitapex_check_fixture.REVIEW_PERSONA_PERMISSION\n'
    )
    fixed_test_src = (
        "import gitapex_check_fixture\n\n\n"
        "def test_permission_keys():\n"
        "    assert gitapex_check_fixture.REVIEW_PERSONA_PERMISSION == {\n"
        '        "correctness": "read-only",\n'
        '        "security": "read-only",\n'
        '        "blast-radius": "read-write",\n'
        "    }\n"
    )

    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, vacuous_test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, vacuous_test_src)
    violations, waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert waived == []
    assert len(violations) == 1
    assert "blast-radius" in violations[0].message

    _write(tmp_path, test_path, fixed_test_src)
    diff_text_fixed = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, fixed_test_src)
    violations_fixed, waived_fixed, graded_fixed = gate.find_violations(diff_text_fixed, tmp_path)
    assert graded_fixed == 1
    assert violations_fixed == []
    assert waived_fixed == []


def test_end_to_end_category3_vacuous_test_leaves_a_finding_then_fixing_it_clears(tmp_path: pathlib.Path) -> None:
    """Red-then-green proof, category 3 (unconditionally emitted literal),
    mirroring issue #1799's own #1991 "hidden: true"-shaped gap: a test
    that checks only type/non-emptiness leaves both emitted literals
    vacuous."""
    fixture_path = "skills/some-skill/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = 'def build_metadata():\n    return ["hidden", "archived"]\n'
    vacuous_test_src = (
        "import gitapex_check_fixture\n\n\n"
        "def test_build_metadata():\n"
        "    result = gitapex_check_fixture.build_metadata()\n"
        "    assert isinstance(result, list)\n"
        "    assert len(result) > 0\n"
    )
    fixed_test_src = (
        "import gitapex_check_fixture\n\n\n"
        "def test_build_metadata():\n"
        "    result = gitapex_check_fixture.build_metadata()\n"
        '    assert result == ["hidden", "archived"]\n'
    )

    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, vacuous_test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, vacuous_test_src)
    violations, waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert waived == []
    assert len(violations) == 2

    _write(tmp_path, test_path, fixed_test_src)
    diff_text_fixed = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, fixed_test_src)
    violations_fixed, waived_fixed, graded_fixed = gate.find_violations(diff_text_fixed, tmp_path)
    assert graded_fixed == 1
    assert violations_fixed == []
    assert waived_fixed == []


# --- find_violations: other behavior ------------------------------------------


def test_find_violations_skips_a_source_with_no_diff_touched_paired_test(tmp_path: pathlib.Path) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    fixture_src = 'import re\n_RE = re.compile(r"a|b")\n'
    _write(tmp_path, fixture_path, fixture_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src)
    violations, waived, graded = gate.find_violations(diff_text, tmp_path)
    assert (violations, waived, graded) == ([], [], 0)


def test_find_violations_waiver_honoured_on_the_reported_line(tmp_path: pathlib.Path) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = (
        'import re\n_RE = re.compile(r"a|b")  '
        "# defeat-test-mutation-coverage: WAIVED: covered by a CLI test elsewhere\n"
    )
    test_src = 'import gitapex_check_fixture\n\n\ndef test_a():\n    assert gitapex_check_fixture._RE.match("a")\n'
    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, test_src)
    violations, waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert violations == []
    assert len(waived) == 1
    assert waived[0].line == 2


def test_find_violations_counts_a_touched_file_with_no_graded_elements(tmp_path: pathlib.Path) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_make():\n    assert gitapex_check_fixture.make() == 1\n"
    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, test_src)
    violations, waived, graded = gate.find_violations(diff_text, tmp_path)
    assert (violations, waived, graded) == ([], [], 1)


def test_find_violations_raises_scan_error_for_a_missing_file(tmp_path: pathlib.Path) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    fixture_src = 'import re\n_RE = re.compile(r"a|b")\n'
    diff_text = _whole_file_diff(fixture_path, fixture_src)
    with pytest.raises(gate.ScanError, match="missing from"):
        gate.find_violations(diff_text, tmp_path)


def test_find_violations_raises_scan_error_for_unparseable_python(tmp_path: pathlib.Path) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    broken_src = "def broken(:\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    _write(tmp_path, fixture_path, broken_src)
    _write(tmp_path, test_path, test_src)
    diff_text = _whole_file_diff(fixture_path, broken_src) + _whole_file_diff(test_path, test_src)
    with pytest.raises(gate.ScanError, match="cannot be parsed as Python"):
        gate.find_violations(diff_text, tmp_path)


def test_find_violations_raises_scan_error_for_non_utf8_source(tmp_path: pathlib.Path) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    absolute = tmp_path / fixture_path
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    _write(tmp_path, test_path, test_src)
    diff_text = (
        f"diff --git a/{fixture_path} b/{fixture_path}\n--- /dev/null\n+++ b/{fixture_path}\n@@ -0,0 +1,1 @@\n+x = 1\n"
        + _whole_file_diff(test_path, test_src)
    )
    with pytest.raises(gate.ScanError, match="cannot be read as UTF-8 text"):
        gate.find_violations(diff_text, tmp_path)


def test_find_violations_raises_scan_error_on_a_collection_error_mutation(tmp_path: pathlib.Path) -> None:
    """A paired test file that itself fails to *import* at all (a
    module-level `NameError`, not merely a runtime failure inside a test
    function's own body) means every subprocess run against it is a
    collection error -- ScanError, fail closed, never silently read as
    "survived" or "killed" either way."""
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = 'import re\n_RE = re.compile(r"a|b")\n'
    test_src = (
        "import gitapex_check_fixture\n\n"
        "this_name_is_undefined_at_module_level_and_breaks_collection\n\n"
        "def test_x():\n    pass\n"
    )
    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, test_src)
    with pytest.raises(gate.ScanError, match="pytest exited"):
        gate.find_violations(diff_text, tmp_path)


def test_run_mutation_restores_the_original_bytes_even_when_pytest_errors(tmp_path: pathlib.Path) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = 'import re\n_RE = re.compile(r"a|b")\n'
    test_src = (
        "import gitapex_check_fixture\n\n"
        "this_name_is_undefined_at_module_level_and_breaks_collection\n\n"
        "def test_x():\n    pass\n"
    )
    absolute = _write(tmp_path, fixture_path, fixture_src)
    test_absolute = _write(tmp_path, test_path, test_src)
    original_bytes = absolute.read_bytes()
    with pytest.raises(gate.ScanError):
        gate._run_mutation(absolute, b"", original_bytes, (29, 30), [test_absolute], tmp_path)
    assert absolute.read_bytes() == original_bytes


def test_find_violations_raises_scan_error_for_an_unreadable_file(tmp_path: pathlib.Path) -> None:
    """A path the diff names as a source file that turns out to be a
    directory raises `IsADirectoryError` (an `OSError`, not
    `FileNotFoundError`) from `read_bytes()` -- the other branch of
    `find_violations`' own two-way file-read failure handling."""
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    (tmp_path / fixture_path).mkdir(parents=True)
    diff_text = _whole_file_diff(fixture_path, "x = 1\n")
    with pytest.raises(gate.ScanError, match="cannot be read"):
        gate.find_violations(diff_text, tmp_path)


# --- _run_mutation: error paths, via monkeypatched write_bytes/subprocess ----


def test_run_mutation_raises_scan_error_when_the_mutation_write_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    absolute = _write(tmp_path, fixture_path, fixture_src)
    test_absolute = _write(tmp_path, test_path, test_src)
    original_bytes = absolute.read_bytes()

    def _raising_write_bytes(self: pathlib.Path, data: bytes) -> int:
        raise OSError("simulated write failure")

    monkeypatch.setattr(pathlib.Path, "write_bytes", _raising_write_bytes)
    with pytest.raises(gate.ScanError, match="could not write a mutated copy"):
        gate._run_mutation(absolute, b"", original_bytes, (0, 1), [test_absolute], tmp_path)


def test_run_mutation_raises_scan_error_when_the_restore_write_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    absolute = _write(tmp_path, fixture_path, fixture_src)
    test_absolute = _write(tmp_path, test_path, test_src)
    original_bytes = absolute.read_bytes()
    original_write_bytes = pathlib.Path.write_bytes
    calls = {"n": 0}

    def _fail_on_second_call(self: pathlib.Path, data: bytes) -> int:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated restore failure")
        return original_write_bytes(self, data)

    monkeypatch.setattr(pathlib.Path, "write_bytes", _fail_on_second_call)
    with pytest.raises(gate.ScanError, match="could not restore"):
        gate._run_mutation(absolute, b"", original_bytes, (0, 1), [test_absolute], tmp_path)


def test_run_mutation_raises_scan_error_on_subprocess_timeout(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    absolute = _write(tmp_path, fixture_path, fixture_src)
    test_absolute = _write(tmp_path, test_path, test_src)
    original_bytes = absolute.read_bytes()

    def _timing_out(*args: object, **kwargs: object) -> None:
        raise gate.subprocess.TimeoutExpired(cmd=["pytest"], timeout=gate._PYTEST_TIMEOUT_SECONDS)

    monkeypatch.setattr(gate.subprocess, "run", _timing_out)
    with pytest.raises(gate.ScanError, match="timed out"):
        gate._run_mutation(absolute, b"", original_bytes, (0, 1), [test_absolute], tmp_path)
    assert absolute.read_bytes() == original_bytes


def test_run_mutation_raises_scan_error_when_subprocess_run_itself_errors(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    absolute = _write(tmp_path, fixture_path, fixture_src)
    test_absolute = _write(tmp_path, test_path, test_src)
    original_bytes = absolute.read_bytes()

    def _raising(*args: object, **kwargs: object) -> None:
        raise OSError("simulated spawn failure")

    monkeypatch.setattr(gate.subprocess, "run", _raising)
    with pytest.raises(gate.ScanError, match="pytest failed to run"):
        gate._run_mutation(absolute, b"", original_bytes, (0, 1), [test_absolute], tmp_path)
    assert absolute.read_bytes() == original_bytes


# --- _run_mutation: containment check (path-traversal defense in depth) -----


def test_is_within_root_accepts_root_itself_and_a_nested_path(tmp_path: pathlib.Path) -> None:
    nested = tmp_path / "a" / "b" / "c.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("x = 1\n", encoding="utf-8")
    assert gate._is_within_root(tmp_path, tmp_path) is True
    assert gate._is_within_root(nested, tmp_path) is True


def test_is_within_root_rejects_a_sibling_directory_that_merely_shares_a_prefix(tmp_path: pathlib.Path) -> None:
    """A naive string-prefix containment check
    (``str(candidate).startswith(str(root))``) wrongly accepts a sibling
    directory that merely shares `root`'s own name as a text prefix --
    `root`=`.../repo`, `candidate`=`.../repo-evil/x.py`. `_is_within_root`
    must not repeat that defect: it resolves both sides to absolute,
    normalized paths and checks real containment, not string prefixing."""
    root = tmp_path / "repo"
    root.mkdir()
    sibling = tmp_path / "repo-evil"
    sibling.mkdir()
    evil = sibling / "x.py"
    evil.write_text("x = 1\n", encoding="utf-8")
    assert str(evil).startswith(str(root))  # the naive check would wrongly accept this
    assert gate._is_within_root(evil, root) is False


def test_is_within_root_rejects_a_dot_dot_escape_above_root(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    escaping = root / ".." / "outside.py"
    assert gate._is_within_root(escaping, root) is False


def test_run_mutation_refuses_to_write_outside_root(tmp_path: pathlib.Path) -> None:
    """The containment check runs before any write is attempted: a target
    resolving outside `root` raises `ScanError` and the file is left
    byte-for-byte untouched."""
    root = tmp_path / "repo"
    root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    target = outside_dir / "evil.py"
    original = b"def make():\n    return 1\n"
    target.write_bytes(original)
    test_absolute = root / "tests" / "test_evil.py"
    with pytest.raises(gate.ScanError, match="does not resolve to a path contained within"):
        gate._run_mutation(target, b"", original, (0, 1), [test_absolute], root)
    assert target.read_bytes() == original


# --- _run_mutation: the first mutated-bytes write is inside try/finally too -


def test_run_mutation_does_not_attempt_a_restore_write_when_the_initial_write_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first-write `OSError` (disk full, permission denied) means nothing
    was ever written to disk -- the `finally` block must not then attempt a
    pointless (and potentially itself-failing) restore write. Asserted here
    by call-counting `write_bytes`: exactly one call, not two."""
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    absolute = _write(tmp_path, fixture_path, fixture_src)
    test_absolute = _write(tmp_path, test_path, test_src)
    original_bytes = absolute.read_bytes()
    calls = {"n": 0}

    def _counting_raising_write_bytes(self: pathlib.Path, data: bytes) -> int:
        calls["n"] += 1
        raise OSError("simulated write failure")

    monkeypatch.setattr(pathlib.Path, "write_bytes", _counting_raising_write_bytes)
    with pytest.raises(gate.ScanError, match="could not write a mutated copy"):
        gate._run_mutation(absolute, b"", original_bytes, (0, 1), [test_absolute], tmp_path)
    assert calls["n"] == 1


def test_run_mutation_restore_failure_names_a_concrete_git_checkout_recovery_command(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The restore-write failure message must tell a human exactly how to
    recover the file (`git checkout -- <path>`), not just that recovery is
    needed -- the file may genuinely still hold mutated bytes on disk once
    this branch is reached."""
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_x():\n    pass\n"
    absolute = _write(tmp_path, fixture_path, fixture_src)
    test_absolute = _write(tmp_path, test_path, test_src)
    original_bytes = absolute.read_bytes()
    original_write_bytes = pathlib.Path.write_bytes
    calls = {"n": 0}

    def _fail_on_second_call(self: pathlib.Path, data: bytes) -> int:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated restore failure")
        return original_write_bytes(self, data)

    monkeypatch.setattr(pathlib.Path, "write_bytes", _fail_on_second_call)
    with pytest.raises(gate.ScanError, match=r"git checkout -- .*gitapex_check_fixture\.py") as excinfo:
        gate._run_mutation(absolute, b"", original_bytes, (0, 1), [test_absolute], tmp_path)
    assert str(absolute) in str(excinfo.value)


# --- direct unit tests for internal helpers ---------------------------------


def test_diff_target_path_returns_none_for_dev_null() -> None:
    assert gate._diff_target_path("/dev/null") is None


def test_diff_target_path_strips_the_b_prefix() -> None:
    assert gate._diff_target_path("b/.github/scripts/gitapex_check_fixture.py") == (
        ".github/scripts/gitapex_check_fixture.py"
    )


def test_diff_target_path_raises_on_an_unrecognised_prefix() -> None:
    with pytest.raises(gate.ScanError):
        gate._diff_target_path("c/some/other/prefix.py")


def test_looks_like_real_header_pair_accepts_a_genuine_pair() -> None:
    assert gate._looks_like_real_header_pair("--- a/x.py", "+++ b/x.py")


def test_looks_like_real_header_pair_rejects_ordinary_content() -> None:
    assert not gate._looks_like_real_header_pair("--- not a header", "+++ also not one")


def test_parse_added_lines_returns_the_added_line_numbers_per_path() -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    added = gate.parse_added_lines(_partial_diff(fixture_path, "a\nb\nc\n", [2]))
    assert added == {fixture_path: {2}}


def test_parse_added_lines_handles_context_and_removed_lines() -> None:
    """Exercises the ` ` (context) and `-` (removal) branches directly --
    `_whole_file_diff`/`_partial_diff` above only ever produce `+` lines,
    so neither branch is otherwise reached."""
    diff_text = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,3 +1,3 @@\n"
        " context_line\n"
        "-old_line\n"
        "+new_line\n"
        " trailing_context\n"
    )
    assert gate.parse_added_lines(diff_text) == {"x.py": {2}}


def test_parse_added_lines_raises_on_a_post_image_header_with_no_source_header() -> None:
    diff_text = "diff --git a/x.py b/x.py\n+++ b/x.py\n@@ -0,0 +1,2 @@\n+def check_value(x):\n+    return x > 0\n"
    with pytest.raises(gate.ScanError, match="no `--- ` source header"):
        gate.parse_added_lines(diff_text)


def test_parse_added_lines_raises_on_an_over_declared_hunk_count() -> None:
    diff_text = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,0 +1,2 @@\n"
        "+def check_value(x):\n"
        "@@ -5,0 +6,1 @@\n"
        "+    pass\n"
    )
    with pytest.raises(gate.ScanError, match="declared more"):
        gate.parse_added_lines(diff_text)


def test_parse_added_lines_raises_on_an_over_declared_hunk_that_drains_into_a_real_header_pair() -> None:
    diff_text = (
        "--- a/hooks/gitapex_check_file1.py\n"
        "+++ b/hooks/gitapex_check_file1.py\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/hooks/gitapex_check_file2.py\n"
        "+++ b/hooks/gitapex_check_file2.py\n"
        "@@ -1,1 +1,2 @@\n"
    )
    with pytest.raises(gate.ScanError, match="closes exactly on a line shaped like"):
        gate.parse_added_lines(diff_text)


def test_a_real_looking_absorbed_header_pair_with_no_boundary_following_it_does_not_raise() -> None:
    diff_text = (
        "diff --git a/file1.py b/file1.py\n"
        "--- a/file1.py\n"
        "+++ b/file1.py\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/file2.py\n"
        "+++ b/file2.py\n"
        "some ordinary content here\n"
    )
    assert gate.parse_added_lines(diff_text) == {"file1.py": {1}}


def test_a_dash_plus_shaped_hunk_with_nothing_following_it_is_not_an_error() -> None:
    diff_text = (
        "diff --git a/hooks/gitapex_check_dashplus.py b/hooks/gitapex_check_dashplus.py\n"
        "--- a/hooks/gitapex_check_dashplus.py\n"
        "+++ b/hooks/gitapex_check_dashplus.py\n"
        '@@ -6 +6 @@ DIVIDER = """\n'
        "--- old changelog marker\n"
        "+++ new changelog marker\n"
    )
    assert gate.parse_added_lines(diff_text) == {"hooks/gitapex_check_dashplus.py": {6}}


def test_regex_pattern_literal_rejects_a_call_with_no_arguments() -> None:
    tree = ast.parse("re.compile()")
    call = _first_expr_value(tree)
    assert isinstance(call, ast.Call)
    assert gate._regex_pattern_literal(call, frozenset({"re"})) is None


def test_string_literal_content_span_raises_for_a_degenerate_single_char_token() -> None:
    """A raw token consisting of just the opening quote character (no
    content, no closing quote) computes `end < start` -- the malformed-
    token branch, distinct from the tokenize-based checks below."""
    with pytest.raises(ValueError, match="malformed string literal token"):
        gate._string_literal_content_span(b'"')


def test_string_literal_content_span_raises_for_non_utf8_bytes() -> None:
    with pytest.raises(ValueError, match="not valid UTF-8"):
        gate._string_literal_content_span(b'"\xff"')


def test_string_literal_content_span_raises_for_an_unterminated_triple_quoted_string() -> None:
    """An unterminated triple-quoted string makes `tokenize` itself raise
    `TokenizeError` (`EOF in multi-line string`), rather than merely
    yielding zero/multiple `STRING` tokens the way an unterminated
    single-quoted string or implicit concatenation does."""
    with pytest.raises(ValueError, match="could not tokenize"):
        gate._string_literal_content_span(b'"""abc')


def test_is_supported_literal_accepts_the_four_scalar_types_and_rejects_others() -> None:
    assert gate._is_supported_literal("a")
    assert gate._is_supported_literal(1)
    assert gate._is_supported_literal(1.5)
    assert gate._is_supported_literal(True)
    assert not gate._is_supported_literal(None)
    assert not gate._is_supported_literal(b"bytes")
    assert not gate._is_supported_literal((1, 2))


def test_invalidate_pycache_removes_an_existing_cache_dir(tmp_path: pathlib.Path) -> None:
    module_path = tmp_path / "gitapex_check_fixture.py"
    module_path.write_text("x = 1\n", encoding="utf-8")
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "gitapex_check_fixture.cpython-312.pyc").write_bytes(b"stale")
    gate._invalidate_pycache(module_path)
    assert not cache_dir.exists()


def test_invalidate_pycache_is_a_no_op_when_no_cache_dir_exists(tmp_path: pathlib.Path) -> None:
    module_path = tmp_path / "gitapex_check_fixture.py"
    module_path.write_text("x = 1\n", encoding="utf-8")
    gate._invalidate_pycache(module_path)  # must not raise


def test_graded_elements_combines_all_three_categories() -> None:
    source = 'import re\n\nCONST = {"a": 1, "b": 2}\n\n_RE = re.compile(r"x|y")\n\ndef make():\n    return ["p", "q"]\n'
    added = set(range(1, source.count("\n") + 1))
    elements = gate._graded_elements(".github/scripts/gitapex_check_fixture.py", source, added)
    categories = {category for _line, category, _message, _span in elements}
    assert categories == {gate._REGEX_ALTERNATION, gate._DICT_ENTRY, gate._LITERAL_ELEMENT}


# --- GateDefeatTestMutationCoverageArgs ---------------------------------------


def test_root_must_exist_raises_value_error_for_a_non_directory(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateDefeatTestMutationCoverageArgs._root_must_exist(tmp_path / "does-not-exist")


def test_root_must_exist_accepts_a_real_directory(tmp_path: pathlib.Path) -> None:
    assert gate.GateDefeatTestMutationCoverageArgs._root_must_exist(tmp_path) == tmp_path


# --- main() CLI ----------------------------------------------------------


def test_main_returns_0_and_prints_ok_on_a_clean_diff(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = "def make():\n    return 1\n"
    test_src = "import gitapex_check_fixture\n\n\ndef test_make():\n    assert gitapex_check_fixture.make() == 1\n"
    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, test_src)
    monkeypatch.setattr("sys.stdin", _FakeStdin(diff_text.encode("utf-8")))
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 0
    assert "OK: 1 in-scope file(s) graded" in capsys.readouterr().out


def test_main_returns_1_and_prints_violations_citing_the_issue(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = 'def build():\n    return {"hidden": True}\n'
    test_src = (
        "import gitapex_check_fixture\n\n\n"
        "def test_build():\n"
        "    assert isinstance(gitapex_check_fixture.build(), dict)\n"
    )
    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, test_src)
    diff_path = tmp_path / "diff.patch"
    diff_path.write_text(diff_text, encoding="utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "issue #1799" in captured.err
    assert "defeat-test-mutation-coverage: WAIVED" in captured.err


def test_main_prints_a_waived_finding_separately(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixture_path = ".github/scripts/gitapex_check_fixture.py"
    test_path = "tests/test_gitapex_check_fixture.py"
    fixture_src = (
        'import re\n_RE = re.compile(r"a|b")  '
        "# defeat-test-mutation-coverage: WAIVED: covered by a CLI test elsewhere\n"
    )
    test_src = 'import gitapex_check_fixture\n\n\ndef test_a():\n    assert gitapex_check_fixture._RE.match("a")\n'
    _write(tmp_path, fixture_path, fixture_src)
    _write(tmp_path, test_path, test_src)
    diff_text = _whole_file_diff(fixture_path, fixture_src) + _whole_file_diff(test_path, test_src)
    diff_path = tmp_path / "diff.patch"
    diff_path.write_text(diff_text, encoding="utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    assert exit_code == 0
    assert "waived inline" in capsys.readouterr().err


def test_main_returns_2_for_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    exit_code = gate.main(["--root", str(tmp_path / "does-not-exist")])
    assert exit_code == 2


def test_main_returns_2_for_a_malformed_diff_file(tmp_path: pathlib.Path) -> None:
    diff_path = tmp_path / "diff.patch"
    diff_path.write_text("@@ garbage @@\n+x = 1\n", encoding="utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    assert exit_code == 2


def test_main_returns_2_for_a_diff_file_that_is_not_utf8(tmp_path: pathlib.Path) -> None:
    diff_path = tmp_path / "diff.patch"
    diff_path.write_bytes(b"\xff\xfe not utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    assert exit_code == 2


def test_main_returns_2_for_non_utf8_stdin(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", _FakeStdin(b"\xff\xfe not utf-8"))
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 2


def test_main_returns_2_when_a_diff_named_file_cannot_be_read(tmp_path: pathlib.Path) -> None:
    diff_path = tmp_path / "does-not-exist.patch"
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    assert exit_code == 2


# --- workflow drift tests ------------------------------------------------------

_WORKFLOW_NAME = "defeat-test-mutation-coverage-gate.yml"


def test_the_workflow_has_no_paths_filter() -> None:
    assert_workflow_has_no_trigger_path_filter(_WORKFLOW_NAME)


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    assert_workflow_checkout_pins_head_sha_with_full_history(_WORKFLOW_NAME)


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    assert_workflow_feeds_merge_base_to(_WORKFLOW_NAME, "diff")


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    assert_workflow_diff_carries_flags(_WORKFLOW_NAME, "--no-renames", "core.quotePath=false")

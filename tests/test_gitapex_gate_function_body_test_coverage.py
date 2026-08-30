"""Tests for the function-body test-coverage gate
(.github/scripts/gitapex_gate_function_body_test_coverage.py).

Issue #1498. Mirrors tests/test_gitapex_gate_detection_logic_property_coverage.py's
own fixture/assertion style for "a gate of this exact shape": synthetic
unified-diff-text fixtures, tmp_path-based --root trees, and direct calls
into the gate module's own functions rather than only subprocess CLI
invocation. Unlike that file, several tests here build a diff spanning two
files at once (a source file and its corresponding test file), since this
gate's own coverage question is inherently cross-file and diff-scoped on
both sides.

Per this repository's defeat-test-disclosure process, at least one test
below is specifically constructed to defeat -- not merely exercise the
happy path of -- the new detection logic; see the `test_defeat_*` tests
below. This is also the regression test issue #1498's own Proof method
column asks for: `test_defeat_a_preexisting_uninvolved_test_does_not_clear_it`
reconstructs issue #1492's own repair-11 defect shape directly (a function
body fix with zero test lines touched by the same diff) and confirms this
gate flags it -- the exact gap that let commit 379c0fde ship untested.
"""

from __future__ import annotations

import ast
import pathlib

import gitapex_gate_function_body_test_coverage as gate
import pytest
from conftest import FakeStdin as _FakeStdin
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

_FIXTURE_PATH = "skills/some-skill/scripts/gitapex_check_fixture.py"
_TEST_PATH = "tests/test_gitapex_check_fixture.py"
_PROPERTIES_PATH = "tests/test_gitapex_check_fixture_properties.py"

_SIMPLE_FUNCTION_SOURCE = "def check_value(x):\n    return x > 0\n"

_COVERING_TEST_SOURCE = (
    "import gitapex_check_fixture\n\n\ndef test_check_value():\n    assert gitapex_check_fixture.check_value(1)\n"
)

_COVERING_PROPERTIES_SOURCE = (
    "import gitapex_check_fixture\n"
    "from hypothesis import given\n"
    "from hypothesis import strategies as st\n"
    "\n"
    "\n"
    "@given(st.integers())\n"
    "def test_check_value_matches(x):\n"
    "    gitapex_check_fixture.check_value(x)\n"
)

# A covering-shaped test that mentions a different function entirely -- used
# by the wrong-function defeat test below.
_WRONG_FUNCTION_TEST_SOURCE = (
    "import gitapex_check_fixture\n\n\ndef test_something_else():\n"
    "    assert gitapex_check_fixture.unrelated_function(1)\n"
)

# Two functions in the same test file: the real covering one (lines 4-5) and
# an unrelated one (lines 8-9) -- used to prove a diff that only touches the
# *unrelated* function does not clear coverage for check_value.
_TEST_SOURCE_WITH_TWO_FUNCTIONS = (
    "import gitapex_check_fixture\n"
    "\n"
    "\n"
    "def test_check_value():\n"
    "    assert gitapex_check_fixture.check_value(1)\n"
    "\n"
    "\n"
    "def test_something_else():\n"
    "    assert True\n"
)

# A covering function that genuinely mentions check_value (line 6) but also
# carries an unrelated comment line (line 5) this diff can touch instead --
# the Bug 1 regression fixture: the diff must land ON the mentioning line
# itself, not merely somewhere inside the function that mentions it.
_TEST_SOURCE_MENTION_PLUS_UNRELATED_LINE = (
    "import gitapex_check_fixture\n"
    "\n"
    "\n"
    "def test_check_value():\n"
    "    # unrelated comment edit\n"
    "    assert gitapex_check_fixture.check_value(1)\n"
)

_MODULE_LEVEL_SOURCE = "X = 1\nY = 2\n"

_NESTED_FUNCTION_SOURCE = "def outer():\n    def inner():\n        return 1\n    return inner()\n"

_COVERING_INNER_TEST_SOURCE = "import gitapex_check_fixture\n\n\ndef test_inner():\n    gitapex_check_fixture.inner\n"

_COVERING_OUTER_TEST_SOURCE = "import gitapex_check_fixture\n\n\ndef test_outer():\n    gitapex_check_fixture.outer\n"

_WAIVED_SOURCE = (
    "def check_value(x):\n"
    "    # function-body-test-coverage: WAIVED: exercised by a subprocess CLI test elsewhere\n"
    "    return x > 0\n"
)

_WAIVER_NO_REASON_SOURCE = "def check_value(x):\n    # function-body-test-coverage: WAIVED\n    return x > 0\n"

_RENAMED_PARAM_SOURCE = "def check_value(y):\n    return y > 0\n"

# Two same-named methods on two different classes -- the disclosed known-miss
# fixture: this gate resolves coverage by bare function name, so a test
# mentioning "validate" once clears both, confirmed live rather than
# hypothesised (matching gitapex_gate_detection_logic_property_coverage.py's
# own basename-collision-across-files miss disclosure).
_SAME_NAME_TWO_METHODS_SOURCE = (
    "class A:\n    def validate(self):\n        return 1\n\n\nclass B:\n    def validate(self):\n        return 2\n"
)

_COVERING_VALIDATE_TEST_SOURCE = (
    "import gitapex_check_fixture\n\n\ndef test_validate():\n    gitapex_check_fixture.validate\n"
)

_UNPARSEABLE_HUNK_DIFF = (
    f"diff --git a/x.py b/{_FIXTURE_PATH}\n--- a/x.py\n+++ b/{_FIXTURE_PATH}\n@@ garbage @@\n+x = 1\n"
)

_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF = (
    f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
    f"+++ b/{_FIXTURE_PATH}\n"
    "@@ -0,0 +1,2 @@\n"
    "+def check_value(x):\n"
    "+    return x > 0\n"
)


# --- helpers --------------------------------------------------------------


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


def _grade(tmp_path: pathlib.Path, source: str, *, relative: str = _FIXTURE_PATH) -> list[gate.Finding]:
    """Write `source` at `relative`, grade it as wholly added with no other
    file in the diff, return violations. The `graded == 1` assertion is
    load-bearing: every "must not fire" test below asserts `== []`, and
    without it a gate reading nothing at all would satisfy them vacuously.
    """
    _write(tmp_path, relative, source)
    violations, _waived, graded = gate.find_violations(_whole_file_diff(relative, source), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations


def _grade_added(
    tmp_path: pathlib.Path, source: str, added: list[int], *, relative: str = _FIXTURE_PATH
) -> tuple[list[gate.Finding], list[gate.Finding]]:
    """Write `source` at `relative`, grade it with only the 1-based line
    numbers in `added` present in the diff, return ``(violations, waivers)``.
    """
    _write(tmp_path, relative, source)
    violations, waived, graded = gate.find_violations(_partial_diff(relative, source, added), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations, waived


def _grade_with_covering_diff(
    tmp_path: pathlib.Path,
    source: str,
    *,
    relative: str = _FIXTURE_PATH,
    test_relative: str,
    test_source: str,
) -> list[gate.Finding]:
    """Write `source` and `test_source`, grade a diff that wholly adds
    *both* files at once -- the "the same diff adds a corresponding test"
    shape this gate's own coverage question requires."""
    _write(tmp_path, relative, source)
    _write(tmp_path, test_relative, test_source)
    diff_text = _whole_file_diff(relative, source) + _whole_file_diff(test_relative, test_source)
    violations, _waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations


# --- scope: in_scope() boundary pins ----------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "skills/foo/scripts/gitapex_check_bar.py",
        ".github/scripts/gitapex_gate_bar.py",
        "skills/foo/scripts/some_util.py",
        ".github/scripts/some_util.py",
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
        "hooks/gitapex_check_bar.py",
        "evals/scripts/gitapex_run_ablation.py",
        "skills/foo/scripts/sub/bar.py",
        ".github/scripts/sub/bar.py",
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


# --- core trigger: a touched function with no covering diff violates --------


def test_a_new_function_with_no_test_at_all_violates(tmp_path: pathlib.Path) -> None:
    violations = _grade(tmp_path, _SIMPLE_FUNCTION_SOURCE)
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]
    assert "check_value" in violations[0].message


def test_module_level_only_change_is_never_graded(tmp_path: pathlib.Path) -> None:
    assert _grade(tmp_path, _MODULE_LEVEL_SOURCE) == []


def test_a_pure_deletion_only_diff_is_not_graded_at_all(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, "def check_value(x):\n    return x >= 0\n")
    diff_text = (
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -2,1 +1,0 @@\n"
        "-    return x > 0\n"
    )
    violations, waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 0
    assert violations == []
    assert waived == []


def test_a_signature_only_change_still_counts_as_a_touched_function(tmp_path: pathlib.Path) -> None:
    """Disclosed widening: `_function_ranges` keys on the whole `lineno`
    through `end_lineno` span, so touching only the `def` line (a param
    rename here) still attributes to the function -- see the module
    docstring's own "Known misses" section."""
    violations, _waived = _grade_added(tmp_path, _RENAMED_PARAM_SOURCE, [1])
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


def test_a_decorator_only_change_still_counts_as_a_touched_function(tmp_path: pathlib.Path) -> None:
    """`_function_ranges` widens a decorated function's own range to start
    at its earliest decorator line: `ast.FunctionDef.lineno` is the `def`
    line alone and excludes decorator lines by construction, so without
    that widening a decorator-only change would fall outside every
    function's own range and go entirely ungraded."""
    source = "@some_decorator\ndef check_value(x):\n    return x > 0\n"
    violations, _waived = _grade_added(tmp_path, source, [1])
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


# --- coverage clears it when the same diff adds a corresponding test -------


def test_a_covering_test_added_in_the_same_diff_clears_it(tmp_path: pathlib.Path) -> None:
    violations = _grade_with_covering_diff(
        tmp_path, _SIMPLE_FUNCTION_SOURCE, test_relative=_TEST_PATH, test_source=_COVERING_TEST_SOURCE
    )
    assert violations == []


def test_a_covering_properties_test_added_in_the_same_diff_also_clears_it(tmp_path: pathlib.Path) -> None:
    violations = _grade_with_covering_diff(
        tmp_path,
        _SIMPLE_FUNCTION_SOURCE,
        test_relative=_PROPERTIES_PATH,
        test_source=_COVERING_PROPERTIES_SOURCE,
    )
    assert violations == []


# --- defeat tests: prove the coverage check cannot be trivially satisfied --


def test_defeat_a_preexisting_uninvolved_test_does_not_clear_it(tmp_path: pathlib.Path) -> None:
    """Issue #1492's own repair-11 defect shape: a test that already, from
    before this diff, mentions the fixed function -- but this diff itself
    never touches that test file -- must not clear coverage. This is the
    exact gap that let commit 379c0fde ship with zero test changes."""
    _write(tmp_path, _TEST_PATH, _COVERING_TEST_SOURCE)
    violations = _grade(tmp_path, _SIMPLE_FUNCTION_SOURCE)
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


def test_defeat_a_diff_touching_an_unrelated_test_function_does_not_clear_it(tmp_path: pathlib.Path) -> None:
    """The test file is genuinely part of this diff, and does contain a
    real covering function -- but the lines this diff actually adds sit
    inside a *different*, unrelated test function in the same file."""
    _write(tmp_path, _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE)
    _write(tmp_path, _TEST_PATH, _TEST_SOURCE_WITH_TWO_FUNCTIONS)
    diff_text = _whole_file_diff(_FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE) + _partial_diff(
        _TEST_PATH, _TEST_SOURCE_WITH_TWO_FUNCTIONS, [9]
    )
    violations, _waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


def test_defeat_a_test_covering_the_wrong_function_does_not_clear_it(tmp_path: pathlib.Path) -> None:
    violations = _grade_with_covering_diff(
        tmp_path, _SIMPLE_FUNCTION_SOURCE, test_relative=_TEST_PATH, test_source=_WRONG_FUNCTION_TEST_SOURCE
    )
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


def test_defeat_an_unrelated_touched_line_in_a_mentioning_function_does_not_clear_it(
    tmp_path: pathlib.Path,
) -> None:
    """The covering test function genuinely mentions check_value (line 6),
    and this diff genuinely touches a line inside that same function -- but
    the touched line (an unrelated comment edit, line 5) is not the
    mentioning line itself. A diff whose only test-file change has nothing
    to do with check_value must not be read as adding coverage for it --
    otherwise a routine, incidental touch to a test file (a comment fix, a
    reformat) landing in the same PR as an unrelated real source change
    would silently satisfy this gate."""
    _write(tmp_path, _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE)
    _write(tmp_path, _TEST_PATH, _TEST_SOURCE_MENTION_PLUS_UNRELATED_LINE)
    diff_text = _whole_file_diff(_FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE) + _partial_diff(
        _TEST_PATH, _TEST_SOURCE_MENTION_PLUS_UNRELATED_LINE, [5]
    )
    violations, _waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


# --- nested-function scope attribution --------------------------------------


def test_only_the_touched_nested_function_is_flagged_not_its_parent(tmp_path: pathlib.Path) -> None:
    violations, _waived = _grade_added(tmp_path, _NESTED_FUNCTION_SOURCE, [3], relative=_FIXTURE_PATH)
    assert len(violations) == 1
    assert violations[0].message.split("`")[1] == "inner"


def test_a_test_covering_the_outer_function_does_not_clear_the_inner_one(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, _NESTED_FUNCTION_SOURCE)
    _write(tmp_path, _TEST_PATH, _COVERING_OUTER_TEST_SOURCE)
    diff_text = _partial_diff(_FIXTURE_PATH, _NESTED_FUNCTION_SOURCE, [3]) + _whole_file_diff(
        _TEST_PATH, _COVERING_OUTER_TEST_SOURCE
    )
    violations, _waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


def test_a_test_covering_the_inner_function_clears_it(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, _NESTED_FUNCTION_SOURCE)
    _write(tmp_path, _TEST_PATH, _COVERING_INNER_TEST_SOURCE)
    diff_text = _partial_diff(_FIXTURE_PATH, _NESTED_FUNCTION_SOURCE, [3]) + _whole_file_diff(
        _TEST_PATH, _COVERING_INNER_TEST_SOURCE
    )
    violations, _waived, graded = gate.find_violations(diff_text, tmp_path)
    assert graded == 1
    assert violations == []


# --- known-miss disclosure: same-named functions in one file ---------------


def test_disclosed_miss_a_same_named_function_clears_both(tmp_path: pathlib.Path) -> None:
    """Confirmed live, not merely hypothesised: this gate resolves coverage
    by bare function name, so a single covering test for "validate" clears
    both class A's and class B's own same-named method -- see the module
    docstring's own "Known misses" section."""
    violations = _grade_with_covering_diff(
        tmp_path,
        _SAME_NAME_TWO_METHODS_SOURCE,
        test_relative=_TEST_PATH,
        test_source=_COVERING_VALIDATE_TEST_SOURCE,
    )
    assert violations == []


# --- waivers -----------------------------------------------------------------


def test_a_waiver_anywhere_in_the_function_body_clears_it(tmp_path: pathlib.Path) -> None:
    violations = _grade(tmp_path, _WAIVED_SOURCE)
    assert violations == []


def test_a_waived_finding_is_reported_separately_via_main(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, _FIXTURE_PATH, _WAIVED_SOURCE)
    diff_path = tmp_path / "diff.patch"
    diff_path.write_text(_whole_file_diff(_FIXTURE_PATH, _WAIVED_SOURCE), encoding="utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    assert exit_code == 0
    assert "waived inline" in capsys.readouterr().err


def test_defeat_a_waiver_inside_a_nested_function_does_not_clear_the_outer_function(
    tmp_path: pathlib.Path,
) -> None:
    """A waiver comment living inside a nested function's own body must not
    silently clear an unrelated finding on the *enclosing* function: the
    outer function's own touched line (its real, untested `+ 999` change)
    has nothing to do with the nested helper's own, unrelated waiver."""
    source = (
        "def outer(x):\n"
        "    def _nested_helper():\n"
        "        return 1  # function-body-test-coverage: WAIVED: unrelated nested waiver\n"
        "    return _nested_helper() + x + 999\n"
    )
    violations, waived = _grade_added(tmp_path, source, [4])
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]
    assert waived == []


def test_a_bare_waiver_with_no_reason_is_not_honoured(tmp_path: pathlib.Path) -> None:
    violations = _grade(tmp_path, _WAIVER_NO_REASON_SOURCE)
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]


# --- ScanError / fail-closed behaviour ---------------------------------------


def test_an_unparseable_hunk_header_raises_scan_error(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE)
    with pytest.raises(gate.ScanError):
        gate.find_violations(_UNPARSEABLE_HUNK_DIFF, tmp_path)


def test_a_post_image_header_with_no_source_header_raises_scan_error(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE)
    with pytest.raises(gate.ScanError):
        gate.find_violations(_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF, tmp_path)


def test_a_diff_naming_a_missing_file_raises_scan_error(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ScanError, match="missing from"):
        gate.find_violations(_whole_file_diff(_FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE), tmp_path)


def test_an_unparseable_python_source_raises_scan_error(tmp_path: pathlib.Path) -> None:
    broken_source = "def check_value(x:\n"
    _write(tmp_path, _FIXTURE_PATH, broken_source)
    with pytest.raises(gate.ScanError, match="cannot be parsed as Python"):
        gate.find_violations(_whole_file_diff(_FIXTURE_PATH, broken_source), tmp_path)


# --- main() CLI ----------------------------------------------------------


def test_main_returns_0_and_prints_ok_on_a_clean_diff(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE)
    _write(tmp_path, _TEST_PATH, _COVERING_TEST_SOURCE)
    diff_text = _whole_file_diff(_FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE) + _whole_file_diff(
        _TEST_PATH, _COVERING_TEST_SOURCE
    )
    monkeypatch.setattr("sys.stdin", _FakeStdin(diff_text.encode("utf-8")))
    exit_code = gate.main(["--root", str(tmp_path)])
    assert exit_code == 0
    assert "OK: 1 in-scope file(s) graded" in capsys.readouterr().out


def test_main_returns_1_and_prints_violations_citing_the_issue(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE)
    diff_path = tmp_path / "diff.patch"
    diff_path.write_text(_whole_file_diff(_FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE), encoding="utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "issue #1498" in captured.err
    assert "function-body-test-coverage: WAIVED" in captured.err


def test_main_returns_2_for_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    exit_code = gate.main(["--root", str(tmp_path / "does-not-exist")])
    assert exit_code == 2


def test_main_returns_2_for_a_malformed_diff_file(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE)
    diff_path = tmp_path / "diff.patch"
    diff_path.write_text(_UNPARSEABLE_HUNK_DIFF, encoding="utf-8")
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
    diff_path = tmp_path / "diff.patch"
    diff_path.write_text(_whole_file_diff(_FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE), encoding="utf-8")
    exit_code = gate.main(["--root", str(tmp_path), "--diff", str(diff_path)])
    assert exit_code == 2


# --- direct unit tests for internal helpers ---------------------------------


def test_diff_target_path_returns_none_for_dev_null() -> None:
    assert gate._diff_target_path("/dev/null") is None


def test_diff_target_path_strips_the_b_prefix() -> None:
    assert gate._diff_target_path(f"b/{_FIXTURE_PATH}") == _FIXTURE_PATH


def test_diff_target_path_raises_on_an_unrecognised_prefix() -> None:
    with pytest.raises(gate.ScanError):
        gate._diff_target_path("c/some/other/prefix.py")


def test_looks_like_real_header_pair_accepts_a_genuine_pair() -> None:
    assert gate._looks_like_real_header_pair(f"--- a/{_FIXTURE_PATH}", f"+++ b/{_FIXTURE_PATH}")


def test_looks_like_real_header_pair_rejects_ordinary_content() -> None:
    assert not gate._looks_like_real_header_pair("--- not a header", "+++ also not one")


def test_parse_added_lines_returns_the_added_line_numbers_per_path() -> None:
    added = gate.parse_added_lines(_whole_file_diff(_FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE))
    assert added == {_FIXTURE_PATH: {1, 2, 3}}


def test_parse_added_lines_raises_on_an_over_declared_hunk_count() -> None:
    """Exercises `_reject_if_hunk_incomplete`'s own raise path: the hunk
    header below declares 2 post-image lines but the body supplies only 1,
    so the boundary check at the next hunk header must fire. See that
    private nested closure's own inline waiver for why it has no test of
    its own referencing it directly by name."""
    diff_text = (
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -1,0 +1,2 @@\n"
        "+def check_value(x):\n"
        "@@ -5,0 +6,1 @@\n"
        "+    pass\n"
    )
    with pytest.raises(gate.ScanError, match="declared more"):
        gate.parse_added_lines(diff_text)


def test_function_ranges_finds_nested_and_top_level_functions() -> None:
    tree = ast.parse(_NESTED_FUNCTION_SOURCE)
    ranges = gate._function_ranges(tree)
    assert sorted(r.name for r in ranges) == ["inner", "outer"]


def test_touched_functions_attributes_to_the_innermost_range() -> None:
    tree = ast.parse(_NESTED_FUNCTION_SOURCE)
    ranges = gate._function_ranges(tree)
    touched = gate._touched_functions(ranges, {3})
    assert [r.name for r in touched] == ["inner"]
    # Several added lines inside the same function dedupe to one entry, and
    # an added line matching no range at all contributes nothing.
    touched_multi = gate._touched_functions(ranges, {2, 3, 100})
    assert [r.name for r in touched_multi] == ["inner"]


def test_innermost_range_returns_none_outside_every_range() -> None:
    tree = ast.parse(_NESTED_FUNCTION_SOURCE)
    ranges = gate._function_ranges(tree)
    assert gate._innermost_range(100, ranges) is None  # well past the whole 4-line fixture
    innermost = gate._innermost_range(3, ranges)
    assert innermost is not None
    assert innermost.name == "inner"


def test_own_lines_excludes_a_nested_functions_own_lines() -> None:
    tree = ast.parse(_NESTED_FUNCTION_SOURCE)
    ranges = gate._function_ranges(tree)
    outer = next(r for r in ranges if r.name == "outer")
    inner = next(r for r in ranges if r.name == "inner")
    own = gate._own_lines(outer, ranges)
    assert inner.lineno not in own
    assert outer.end_lineno in own


def test_function_ranges_widens_to_the_earliest_decorator_line() -> None:
    tree = ast.parse("@first\n@second\ndef check_value(x):\n    return x\n")
    ranges = gate._function_ranges(tree)
    assert ranges == [gate._FunctionRange(1, 4, "check_value")]


def test_mention_lines_finds_the_call_sites_own_line() -> None:
    tree = ast.parse("def test_something():\n    check_value(1)\n    other_name(2)\n")
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    assert gate._mention_lines(func, "check_value") == {2}
    assert gate._mention_lines(func, "unrelated") == set()


def test_test_tree_parses_a_real_file(tmp_path: pathlib.Path) -> None:
    path = _write(tmp_path, _TEST_PATH, _COVERING_TEST_SOURCE)
    tree = gate._test_tree(path)
    assert tree is not None
    assert isinstance(tree, ast.Module)


def test_test_tree_returns_none_for_a_missing_file(tmp_path: pathlib.Path) -> None:
    assert gate._test_tree(tmp_path / "does-not-exist.py") is None


def test_test_tree_returns_none_for_unparseable_content(tmp_path: pathlib.Path) -> None:
    path = _write(tmp_path, _TEST_PATH, "def broken(:\n")
    assert gate._test_tree(path) is None


def test_diff_adds_a_covering_test_direct_call(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, _TEST_PATH, _COVERING_TEST_SOURCE)
    added_by_path = {_TEST_PATH: {4, 5}}
    assert gate._diff_adds_a_covering_test(tmp_path, "gitapex_check_fixture", "check_value", added_by_path)
    assert not gate._diff_adds_a_covering_test(tmp_path, "gitapex_check_fixture", "other_function", added_by_path)
    # Bug 1's own regression, exercised directly: the covering function's
    # own mention sits on line 5, so an `added_by_path` naming only line 4
    # (inside the same function, but not the mentioning line) must not
    # satisfy coverage -- line-precise matching, not whole-function-range.
    assert not gate._diff_adds_a_covering_test(tmp_path, "gitapex_check_fixture", "check_value", {_TEST_PATH: {4}})


def test_waived_lines_finds_the_commented_line() -> None:
    assert gate._waived_lines(_WAIVED_SOURCE) == {2}


def test_waived_lines_ignores_a_bare_marker_with_no_reason() -> None:
    assert gate._waived_lines(_WAIVER_NO_REASON_SOURCE) == set()


def test_findings_for_source_direct_call(tmp_path: pathlib.Path) -> None:
    added_by_path: dict[str, set[int]] = {_FIXTURE_PATH: {1, 2}}
    violations, waived = gate.findings_for_source(
        _FIXTURE_PATH, _SIMPLE_FUNCTION_SOURCE, {1, 2}, added_by_path, tmp_path
    )
    assert [finding.rule for finding in violations] == ["function-body-test-coverage-gap"]
    assert waived == []

    # The waived path, direct: Bug 2's own regression -- a waiver inside a
    # nested function must land in `waived` only for that nested function,
    # never silently clearing the enclosing one's own separate finding.
    nested_source = (
        "def outer(x):\n"
        "    def _nested_helper():\n"
        "        return 1  # function-body-test-coverage: WAIVED: reason\n"
        "    return _nested_helper() + x\n"
    )
    nested_added_by_path: dict[str, set[int]] = {_FIXTURE_PATH: {3}}
    nested_violations, nested_waived = gate.findings_for_source(
        _FIXTURE_PATH, nested_source, {3}, nested_added_by_path, tmp_path
    )
    assert nested_violations == []
    assert [finding.rule for finding in nested_waived] == ["function-body-test-coverage-gap"]
    assert waived == []


def test_root_must_exist_raises_value_error_for_a_non_directory(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateFunctionBodyTestCoverageArgs._root_must_exist(tmp_path / "does-not-exist")


def test_root_must_exist_accepts_a_real_directory(tmp_path: pathlib.Path) -> None:
    assert gate.GateFunctionBodyTestCoverageArgs._root_must_exist(tmp_path) == tmp_path


def test_parse_added_lines_skips_added_lines_for_a_deleted_file() -> None:
    """`path is None` (the `+++ /dev/null` deletion case) skips recording
    into `added` even when a hunk line itself starts with `+` -- a
    contrived shape a hand-fed diff could produce, never a real `git diff`
    deletion (which carries only `-` lines), but the guard must not crash
    or misattribute either way."""
    diff_text = "--- a/old.py\n+++ /dev/null\n@@ -0,0 +1,1 @@\n+phantom\n"
    assert gate.parse_added_lines(diff_text) == {}


def test_parse_added_lines_raises_on_an_over_declared_hunk_that_drains_into_a_real_header_pair() -> None:
    """The bypass two independent adversarial reviews found against the
    boundary-check fix: an over-declared hunk whose excess is small enough
    to be fully absorbed as the next file's own real `--- `/`+++ ` header
    pair, draining both counters to exactly zero one line early -- caught
    only by recognising the pair's own header shape plus what follows it
    also looking like a new hunk or file boundary."""
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


def test_a_dash_plus_shaped_hunk_with_nothing_following_it_is_not_an_error() -> None:
    """The false-positive guard's own non-error branch: a single,
    accurately-declared hunk whose real content edits a line starting
    `-- ` into one starting `++ ` looks header-pair-shaped, but nothing
    follows it -- no missing `diff --git `, no disguised file transition,
    just an ordinary edit to a changelog-marker-shaped line. Must not
    raise: the ambiguous shape only actually raises when the line *after*
    it also looks like a new hunk or file header (see the sibling raising
    test above), which is not true here."""
    diff_text = (
        "diff --git a/hooks/gitapex_check_dashplus.py b/hooks/gitapex_check_dashplus.py\n"
        "--- a/hooks/gitapex_check_dashplus.py\n"
        "+++ b/hooks/gitapex_check_dashplus.py\n"
        '@@ -6 +6 @@ DIVIDER = """\n'
        "--- old changelog marker\n"
        "+++ new changelog marker\n"
    )
    assert gate.parse_added_lines(diff_text) == {"hooks/gitapex_check_dashplus.py": {6}}


def test_a_real_looking_absorbed_header_pair_with_no_boundary_following_it_does_not_raise() -> None:
    """The header-pair-shape signal alone is not sufficient to raise: the
    hunk here closes exactly on file2's own real-shaped `--- `/`+++ `
    header pair (`_looks_like_real_header_pair` reads True), but what
    follows is ordinary content, not a new `@@` or `diff --git ` boundary
    -- so the ambiguity check's own second, required signal is absent and
    this must not raise. Exercises the boundary check's own False branch:
    header-shaped but not followed by a real boundary."""
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


def test_diff_adds_a_covering_test_skips_a_touched_but_unparseable_test_file(tmp_path: pathlib.Path) -> None:
    """The test file is genuinely touched by this diff (`test_added` is
    non-empty) but its own content cannot be parsed as Python -- treated
    as contributing no coverage, the same conservative verdict
    `_test_tree` already documents, reached this time through
    `_diff_adds_a_covering_test`'s own call path rather than a direct call."""
    _write(tmp_path, _TEST_PATH, "def broken(:\n")
    assert not gate._diff_adds_a_covering_test(tmp_path, "gitapex_check_fixture", "check_value", {_TEST_PATH: {1}})


def test_find_violations_raises_scan_error_for_a_non_utf8_source_file(tmp_path: pathlib.Path) -> None:
    """A source file named by the diff exists but is not valid UTF-8 (nor
    UTF-8-with-BOM) -- read as text raises `UnicodeDecodeError`, which
    `find_violations` turns into a `ScanError` rather than crashing or
    silently skipping the file."""
    path = tmp_path / _FIXTURE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe not valid utf-8 or utf-8-sig \x80\x81")
    with pytest.raises(gate.ScanError, match="cannot be read as UTF-8 text"):
        gate.find_violations(_partial_diff(_FIXTURE_PATH, "x = 1\n", [1]), tmp_path)


# --- workflow drift tests ----------------------------------------------------

_WORKFLOW_NAME = "function-body-test-coverage-gate.yml"


def test_the_workflow_has_no_paths_filter() -> None:
    assert_workflow_has_no_trigger_path_filter(_WORKFLOW_NAME)


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    assert_workflow_checkout_pins_head_sha_with_full_history(_WORKFLOW_NAME)


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    assert_workflow_feeds_merge_base_to(_WORKFLOW_NAME, "diff")


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    assert_workflow_diff_carries_flags(_WORKFLOW_NAME, "--no-renames", "core.quotePath=false")

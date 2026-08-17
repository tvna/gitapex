"""Tests for the detection-logic property-coverage gate
(.github/scripts/gitapex_gate_detection_logic_property_coverage.py).

Issue #1178. Mirrors tests/test_gitapex_gate_exception_handler_gaps.py's own
fixture/assertion style for "a gate of this exact shape": synthetic
unified-diff-text fixtures, tmp_path-based --root trees, and direct calls
into the gate module's own functions rather than only subprocess CLI
invocation.

Per this repository's defeat-test-disclosure process, at least one test
below is specifically constructed to defeat -- not merely exercise the
happy path of -- the new detection logic; see the "defeat" tests near the
end of this file.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_detection_logic_property_coverage as gate
import pytest
from conftest import FakeStdin as _FakeStdin

# A plain hooks/gitapex_check_*.py path -- in scope by _IN_SCOPE_RE's own
# `hooks/gitapex_check_[^/]+\.py` alternative -- used as the default fixture
# location across most tests below.
_FIXTURE_PATH = "hooks/gitapex_check_fixture.py"

# SOME_RE = re.compile(...) sits on line 3, pre-existing; check_value (lines
# 6-7) is the "new function" a diff adds. This reconstructs issue #1129's own
# motivating defect shape: a bound-method call site with no re.compile(...)
# anywhere in the *same diff* -- the compile call sits on an earlier,
# unrelated line, exactly as EXEC_REQ_PACKAGES_KEY_RE's real history did.
_CHECK_VALUE_SOURCE = (
    'import re\n\nSOME_RE = re.compile(r"^[a-z]+$")\n\n\ndef check_value(x):\n    return SOME_RE.fullmatch(x)\n'
)

# Identical shape to _CHECK_VALUE_SOURCE, but the trigger line itself (line
# 7) carries an inline waiver comment.
_CHECK_VALUE_WAIVED_SOURCE = (
    "import re\n"
    "\n"
    'SOME_RE = re.compile(r"^[a-z]+$")\n'
    "\n"
    "\n"
    "def check_value(x):\n"
    "    return SOME_RE.fullmatch(x)  # detection-logic-property-coverage: WAIVED: some reason\n"
)

# _CHECK_VALUE_SOURCE plus a second, unrelated function (other_function,
# lines 10-11) a diff can touch without touching check_value's own gap.
_CHECK_VALUE_WITH_OTHER_FUNCTION_SOURCE = (
    "import re\n"
    "\n"
    'SOME_RE = re.compile(r"^[a-z]+$")\n'
    "\n"
    "\n"
    "def check_value(x):\n"
    "    return SOME_RE.fullmatch(x)\n"
    "\n"
    "\n"
    "def other_function():\n"
    "    return 1\n"
)

# The trigger call itself reformatted across three lines (7-9): the call's
# own opening line (7) and closing line (9) are never touched by the
# regression test's diff -- only the argument on line 8 is.
_MULTILINE_CALL_SOURCE = (
    "import re\n"
    "\n"
    'SOME_RE = re.compile(r"^[a-z]+$")\n'
    "\n"
    "\n"
    "def check_value(x):\n"
    "    return SOME_RE.fullmatch(\n"
    "        x,\n"
    "    )\n"
)

# A properties file that genuinely covers check_value: imports the fixture
# module and has one @given function whose own body calls check_value by name.
_PROPERTIES_COVERING_CHECK_VALUE = (
    "import gitapex_check_fixture\n"
    "from hypothesis import given\n"
    "from hypothesis import strategies as st\n"
    "\n"
    "\n"
    "@given(st.text())\n"
    "def test_check_value_matches(x):\n"
    "    gitapex_check_fixture.check_value(x)\n"
)

# Same shape, but the @given function's own body calls a different,
# unrelated function -- never check_value. Used by the defeat test below.
_PROPERTIES_COVERING_WRONG_FUNCTION = (
    "import gitapex_check_fixture\n"
    "from hypothesis import given\n"
    "from hypothesis import strategies as st\n"
    "\n"
    "\n"
    "@given(st.text())\n"
    "def test_something_else(x):\n"
    "    gitapex_check_fixture.unrelated_function(x)\n"
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
    """Write `source` at `relative`, grade it as wholly added, return violations.

    Mirrors tests/test_gitapex_gate_exception_handler_gaps.py's own `_grade`:
    the `graded == 1` assertion is load-bearing, not decoration -- every
    "must not fire" test below asserts `== []`, and without it a gate that
    read nothing at all (a wrong scope rule, a wrong root) would satisfy all
    of them at once.
    """
    _write(tmp_path, relative, source)
    violations, _waived, graded = gate.find_violations(_whole_file_diff(relative, source), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations


def _rules(findings: list[gate.Finding]) -> list[str]:
    return [finding.rule for finding in findings]


def _at(findings: list[gate.Finding]) -> list[tuple[str, int]]:
    return [(finding.rule, finding.line) for finding in findings]


# --- scope: in_scope() boundary pins ---------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "hooks/gitapex_check_fixture.py",
        ".github/scripts/gitapex_gate_fixture.py",
        "skills/some-skill/scripts/gitapex_check_fixture.py",
    ],
)
def test_in_scope_paths_are_recognised(path: str) -> None:
    assert gate.in_scope(path)


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_fixture.py",
        "hooks/conftest.py",
        "skills/some-skill/scripts/gitapex_scan_fixture.py",
        "docs/example.py",
    ],
)
def test_out_of_scope_paths_are_not_graded(path: str) -> None:
    assert not gate.in_scope(path)


# --- true positive, true negative, waived, scope boundaries ----------------


def test_true_positive_regex_bound_method_fullmatch_with_no_properties_file(
    tmp_path: pathlib.Path,
) -> None:
    """The corrected trigger this gate exists to catch (issue #1129's own
    motivating defect): a NEW `SOME_RE.fullmatch(x)` bound-method call site
    inside a brand-new function, added by this diff, while the
    `re.compile(...)` that built `SOME_RE` sits on an earlier, untouched
    line -- and no co-located tests/test_gitapex_check_fixture_properties.py
    exists at all. Exactly one violation, correctly attributed."""
    _write(tmp_path, _FIXTURE_PATH, _CHECK_VALUE_SOURCE)
    violations, waived, graded = gate.find_violations(
        _partial_diff(_FIXTURE_PATH, _CHECK_VALUE_SOURCE, [6, 7]), tmp_path
    )
    assert graded == 1
    assert waived == []
    assert len(violations) == 1
    finding = violations[0]
    assert finding.path == _FIXTURE_PATH
    assert finding.line == 7
    assert finding.rule == "regex-property-gap"
    assert "check_value" in finding.message


def test_true_negative_a_covering_given_test_clears_the_violation(
    tmp_path: pathlib.Path,
) -> None:
    """Identical trigger shape to the true-positive case above, but this
    time tests/test_gitapex_check_fixture_properties.py exists, imports the
    fixture module, and has one @given-decorated function whose own body
    calls `check_value` by name -- so the existing-coverage check clears it."""
    _write(tmp_path, _FIXTURE_PATH, _CHECK_VALUE_SOURCE)
    _write(tmp_path, "tests/test_gitapex_check_fixture_properties.py", _PROPERTIES_COVERING_CHECK_VALUE)
    violations, waived, graded = gate.find_violations(
        _partial_diff(_FIXTURE_PATH, _CHECK_VALUE_SOURCE, [6, 7]), tmp_path
    )
    assert graded == 1
    assert violations == []
    assert waived == []


def test_waived_case_the_trigger_line_carries_an_honoured_inline_waiver(
    tmp_path: pathlib.Path,
) -> None:
    """The true-positive shape above, but the trigger line itself carries a
    `# detection-logic-property-coverage: WAIVED: <reason>` trailing
    comment: zero violations, and the finding surfaces in find_violations's
    own second (waived) return element instead."""
    _write(tmp_path, _FIXTURE_PATH, _CHECK_VALUE_WAIVED_SOURCE)
    violations, waived, graded = gate.find_violations(
        _partial_diff(_FIXTURE_PATH, _CHECK_VALUE_WAIVED_SOURCE, [6, 7]), tmp_path
    )
    assert graded == 1
    assert violations == []
    assert _at(waived) == [("regex-property-gap", 7)]


def test_scope_boundary_a_gitapex_scan_path_is_out_of_scope(tmp_path: pathlib.Path) -> None:
    """The true-positive diff shape above, but at a `gitapex_scan_*.py` path
    -- out of scope by construction (issue #1032, disclosed in the module
    docstring's own "Out of this gate's own scope" section): every
    `_IN_SCOPE_RE` alternative fixes the prefix to `gitapex_check_`/
    `gitapex_gate_`, none allow `gitapex_scan_`. The file is deliberately
    never written to disk, proving it is never even read."""
    relative = "skills/evaluating-skill-quality/scripts/gitapex_scan_fixture.py"
    assert not gate.in_scope(relative)
    diff = _whole_file_diff(relative, _CHECK_VALUE_SOURCE)
    assert gate.find_violations(diff, tmp_path) == ([], [], 0)


def test_scope_boundary_b_an_untouched_pre_existing_trigger_is_not_flagged(
    tmp_path: pathlib.Path,
) -> None:
    """Diff-scoped only, no retroactive flagging: the file already contains
    (pre-existing, not part of the constructed diff) the same uncovered
    `SOME_RE.fullmatch(x)` gap at lines 6-7, which this diff never touches --
    only an unrelated line inside `other_function` (line 11) is added."""
    _write(tmp_path, _FIXTURE_PATH, _CHECK_VALUE_WITH_OTHER_FUNCTION_SOURCE)
    violations, waived, graded = gate.find_violations(
        _partial_diff(_FIXTURE_PATH, _CHECK_VALUE_WITH_OTHER_FUNCTION_SOURCE, [11]), tmp_path
    )
    assert graded == 1
    assert violations == []
    assert waived == []


# --- path-resolution / string-comparison true positives ---------------------


def test_path_resolution_true_positive_resolve_call(tmp_path: pathlib.Path) -> None:
    """A new receiver-agnostic `.resolve()` call, category (b)."""
    source = "import pathlib\n\n\ndef check_path(p):\n    return pathlib.Path(p).resolve()\n"
    violations = _grade(tmp_path, source)
    assert _at(violations) == [("path-resolution-property-gap", 5)]


def test_string_comparison_true_positive_startswith_call(tmp_path: pathlib.Path) -> None:
    """A new receiver-agnostic `.startswith(...)` call, category (c)."""
    source = 'def check_prefix(s):\n    return s.startswith("prefix-")\n'
    violations = _grade(tmp_path, source)
    assert _at(violations) == [("string-comparison-property-gap", 2)]


def test_string_comparison_true_positive_inline_list_literal_membership(
    tmp_path: pathlib.Path,
) -> None:
    """A new `in`-comparison whose right-hand comparator is an inline list
    literal, category (c)'s `ast.Compare` half."""
    source = 'def check_membership(x):\n    return x in ["a", "b"]\n'
    violations = _grade(tmp_path, source)
    assert _at(violations) == [("string-comparison-property-gap", 2)]


def test_string_comparison_true_positive_frozenset_inline_literal_call(
    tmp_path: pathlib.Path,
) -> None:
    """A new `frozenset({...})` call whose sole argument is an inline set
    literal -- this repository's own frozenset-at-the-comparison-site idiom,
    category (c). The later `x in denylist` compares against a Name, not a
    literal, so it must not itself add a second finding."""
    source = 'def check_denylist(x):\n    denylist = frozenset({"a", "b"})\n    return x in denylist\n'
    violations = _grade(tmp_path, source)
    assert _at(violations) == [("string-comparison-property-gap", 2)]


# --- multi-line call span regression ----------------------------------------


def test_multiline_call_span_regression_touching_only_the_argument_line_still_flags_it(
    tmp_path: pathlib.Path,
) -> None:
    """Regression for findings_for_source's own
    `if not (_span(trigger.node) & added): continue` (module line ~699): the
    multi-line call's OPENING line (`    return SOME_RE.fullmatch(`, line 7)
    is untouched by this diff, and so is its closing line (`    )`, line 9)
    -- only the argument on line 8 is added. A rule keyed on `node.lineno`
    alone would miss this. `_span` covers `node.lineno..end_lineno`
    inclusive (here 7..9), so the added line 8 still brings the finding at
    line 7 into scope."""
    _write(tmp_path, _FIXTURE_PATH, _MULTILINE_CALL_SOURCE)
    violations, waived, graded = gate.find_violations(
        _partial_diff(_FIXTURE_PATH, _MULTILINE_CALL_SOURCE, [8]), tmp_path
    )
    assert graded == 1
    assert _at(violations) == [("regex-property-gap", 7)]
    assert waived == []


# --- malformed input: ScanError contract ------------------------------------


def test_an_unparseable_hunk_header_raises_scanerror() -> None:
    diff = f"diff --git a/x.py b/{_FIXTURE_PATH}\n+++ b/{_FIXTURE_PATH}\n@@ garbage @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="unparseable hunk header"):
        gate.parse_added_lines(diff)


def test_a_post_image_path_without_the_b_prefix_raises_scanerror() -> None:
    """--no-prefix output and a git-quoted path both land here. Guessing at
    either would silently drop a file from grading."""
    diff = f"diff --git a/x b/x\n--- a/x\n+++ {_FIXTURE_PATH}\n@@ -0,0 +1,1 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="not a plain b/-prefixed path"):
        gate.parse_added_lines(diff)


def test_a_file_named_by_the_diff_but_missing_from_root_raises_scanerror(
    tmp_path: pathlib.Path,
) -> None:
    """A wrong --root would otherwise turn this gate into a green no-op."""
    diff = _whole_file_diff(_FIXTURE_PATH, "x = 1\n")
    with pytest.raises(gate.ScanError, match="missing from"):
        gate.find_violations(diff, tmp_path)


def test_a_non_utf8_source_file_raises_scanerror(tmp_path: pathlib.Path) -> None:
    path = _write(tmp_path, _FIXTURE_PATH, "x = 1\n")
    path.write_bytes(b"x = '\xff\xfe'\n")
    diff = _whole_file_diff(_FIXTURE_PATH, "x = 1\n")
    with pytest.raises(gate.ScanError, match="cannot be read as UTF-8 text"):
        gate.find_violations(diff, tmp_path)


def test_a_source_file_that_does_not_parse_raises_scanerror(tmp_path: pathlib.Path) -> None:
    source = "def broken(:\n"
    _write(tmp_path, _FIXTURE_PATH, source)
    diff = _whole_file_diff(_FIXTURE_PATH, source)
    with pytest.raises(gate.ScanError, match="cannot be parsed as Python"):
        gate.find_violations(diff, tmp_path)


# --- malformed input: main()'s own fail-closed (exit 2) CLI path -----------


def test_main_exits_2_on_a_root_that_does_not_exist(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(tmp_path / "nope")]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_on_non_utf8_stdin(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """This gate's own subject, once shipped into the gate itself: reading
    stdin as decoded text under the platform locale, rather than bytes
    decoded explicitly, would let a non-UTF-8 byte escape as an uncaught
    traceback instead of a clean exit 2."""
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"+# \xff\xfe\n"))
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "diff cannot be read as UTF-8 text" in capsys.readouterr().err


# --- defeat-oriented: constructed to defeat the detection logic, not just --
# --- exercise its happy path (this repository's defeat-test-disclosure    --
# --- process) ---------------------------------------------------------------


def test_defeat_a_same_file_given_test_for_the_wrong_function_does_not_false_clear_coverage(
    tmp_path: pathlib.Path,
) -> None:
    """DEFEAT-oriented, not a happy-path check: attempts to trick the
    existing-coverage check into clearing `check_value`'s finding merely
    because *some* @given-decorated test exists in a properties file that
    imports the right module -- while that test's own body actually
    exercises a different, unrelated function (`unrelated_function`, never
    `check_value`). If `_covered`/`_mentions_name_in_body` cleared coverage
    whenever any @given test existed in an importing file, rather than
    searching that specific function's own body for the scope's name, this
    would wrongly clear the violation. It must not: `check_value` stays
    uncovered."""
    _write(tmp_path, _FIXTURE_PATH, _CHECK_VALUE_SOURCE)
    _write(tmp_path, "tests/test_gitapex_check_fixture_properties.py", _PROPERTIES_COVERING_WRONG_FUNCTION)
    violations, waived, graded = gate.find_violations(
        _partial_diff(_FIXTURE_PATH, _CHECK_VALUE_SOURCE, [6, 7]), tmp_path
    )
    assert graded == 1
    assert _at(violations) == [("regex-property-gap", 7)]
    assert waived == []


def test_defeat_a_subscript_receiver_still_triggers_the_receiver_agnostic_match(
    tmp_path: pathlib.Path,
) -> None:
    """DEFEAT-oriented: attempts to slip a `.fullmatch()` call past the
    trigger with an unusual receiver shape (a dict subscript, not a plain
    compiled-pattern name) that a receiver-*specific* matcher would miss.
    `_regex_trigger` is documented as receiver-agnostic for
    `.match`/`.search`/`.fullmatch` precisely because issue #1129's own
    defect was a bound-method call site with an arbitrary receiver, so this
    unusual-but-valid shape must still be caught."""
    source = 'PATTERNS = {}\n\n\ndef check_value(x):\n    return PATTERNS["x"].fullmatch(x)\n'
    violations = _grade(tmp_path, source)
    assert _rules(violations) == ["regex-property-gap"]

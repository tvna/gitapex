"""Tests for the except-clause fail-open gate
(.github/scripts/gitapex_gate_except_fail_open.py).

Issue #1722 (from #1704, #1706). Both were the same defect class shipped
into `load_python_dependent_hook_script_names`
(`.github/scripts/gitapex_gate_bare_python3_invocation.py`): an `except`
clause that caught a real failure and silently handed back a falsy default
(`None`/an empty collection) with no re-raise, so a malformed
`.gitapex/ssot.json` (#1704, whole-file) or a malformed single gate entry
(#1706, per-entry) made a *different* gate report a false "clean" verdict.
Both are already fixed on `main` (commits `f6e97a7`, `f6bed27`); this file
tests the recurrence-prevention gate, not that function -- the fixtures
below are constructed reproductions of the described defect shapes, not the
real historical diffs.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_except_fail_open as gate
import pytest
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_WORKFLOW = "except-fail-open-gate.yml"


# --- helpers --------------------------------------------------------------


def _whole_file_diff(path: str, source: str) -> str:
    """A unified diff in which every line of `source` is an added line."""
    lines = source.split("\n")
    body = "".join("+" + line + "\n" for line in lines)
    return f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + body


def _partial_diff(path: str, source: str, added: list[int]) -> str:
    """A unified diff adding only the 1-based line numbers in `added`,
    leaving every other line of `source` untouched (pre-existing content)."""
    lines = source.split("\n")
    hunks = "".join(f"@@ -{number},0 +{number},1 @@\n+{lines[number - 1]}\n" for number in added)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{hunks}"


def _write(root: pathlib.Path, relative: str, source: str) -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _grade(tmp_path: pathlib.Path, source: str, *, relative: str = ".github/scripts/gate_x.py") -> list[gate.Finding]:
    """Write `source` at `relative`, grade it as wholly added, return violations.

    The `graded == 1` assertion is load-bearing: every "must not fire" test
    below asserts `== []`, and without it a gate that read nothing at all
    (a wrong scope rule, a wrong root) would satisfy all of them at once.
    """
    _write(tmp_path, relative, source)
    violations, _waived, graded = gate.find_violations(_whole_file_diff(relative, source), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations


def _rules(findings: list[gate.Finding]) -> list[str]:
    return [finding.rule for finding in findings]


def _at(findings: list[gate.Finding]) -> list[tuple[str, int]]:
    return [(finding.rule, finding.line) for finding in findings]


# --- regression fixtures: #1704 (whole-file malformed) shape --------------

_DEFECT_1704_SHAPE = '''
import json
import pathlib


def load_registry(path: pathlib.Path) -> dict | None:
    """Read and parse the whole-file registry, or None if it cannot be
    trusted -- reproduces #1704's own fail-open shape: a malformed
    whole-file read silently swallowed instead of failing closed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
'''


def test_1704_shape_whole_file_malformed_read_is_flagged_unwaived(tmp_path: pathlib.Path) -> None:
    assert _rules(_grade(tmp_path, _DEFECT_1704_SHAPE)) == ["except-fail-open"]


def test_1704_shape_passes_once_waived(tmp_path: pathlib.Path) -> None:
    waived = _DEFECT_1704_SHAPE.replace(
        "    except (OSError, UnicodeDecodeError, json.JSONDecodeError):\n",
        "    except (OSError, UnicodeDecodeError, json.JSONDecodeError):  # except-fail-open: WAIVED: caller treats None as absent\n",
    )
    _write(tmp_path, ".github/scripts/gate_x.py", waived)
    violations, waived_findings, graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gate_x.py", waived), tmp_path
    )
    assert graded == 1
    assert violations == []
    assert _rules(waived_findings) == ["except-fail-open"]


def test_1704_shape_returning_empty_dict_is_also_flagged(tmp_path: pathlib.Path) -> None:
    variant = _DEFECT_1704_SHAPE.replace("return None", "return {}")
    assert _rules(_grade(tmp_path, variant)) == ["except-fail-open"]


def test_1704_shape_returning_empty_list_is_also_flagged(tmp_path: pathlib.Path) -> None:
    variant = _DEFECT_1704_SHAPE.replace(
        "def load_registry(path: pathlib.Path) -> dict | None:",
        "def load_registry(path: pathlib.Path) -> list:",
    ).replace("return None", "return []")
    assert _rules(_grade(tmp_path, variant)) == ["except-fail-open"]


# --- regression fixtures: #1706 (per-entry malformed sub-field) shape -----

_DEFECT_1706_SHAPE = """
def collect_script_names(entries: list[dict]) -> list[str]:
    \"\"\"Iterate an otherwise-well-formed container; reproduces #1706's own
    shape: one entry's own malformed sub-field is caught and silently
    defaulted rather than failing closed.\"\"\"
    names = []
    for entry in entries:
        try:
            value = entry["preconditions"]["requires_python_packages"]
        except (KeyError, TypeError):
            value = None
        names.append(value)
    return names
"""


def test_1706_shape_per_entry_malformed_subfield_is_flagged_unwaived(tmp_path: pathlib.Path) -> None:
    assert _rules(_grade(tmp_path, _DEFECT_1706_SHAPE)) == ["except-fail-open"]


def test_1706_shape_passes_once_waived(tmp_path: pathlib.Path) -> None:
    waived = _DEFECT_1706_SHAPE.replace(
        "        except (KeyError, TypeError):\n",
        "        except (KeyError, TypeError):  # except-fail-open: WAIVED: entry is optional\n",
    )
    _write(tmp_path, ".github/scripts/gate_x.py", waived)
    violations, waived_findings, graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gate_x.py", waived), tmp_path
    )
    assert graded == 1
    assert violations == []
    assert _rules(waived_findings) == ["except-fail-open"]


# --- what must fire: falsy-literal variety ---------------------------------


def test_bare_return_with_no_value_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept OSError:\n    return\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


@pytest.mark.parametrize(
    "literal",
    ["None", "[]", "{}", "()", '""', "0", "False", "set()", "frozenset()"],
)
def test_every_documented_falsy_literal_return_is_flagged(tmp_path: pathlib.Path, literal: str) -> None:
    source = f"try:\n    do_work()\nexcept OSError:\n    return {literal}\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_a_bare_except_clause_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept:\n    return None\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_a_tuple_handler_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept (OSError, ValueError):\n    return None\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_except_star_is_flagged_the_same_as_plain_except(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept* OSError:\n    return None\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_assignment_to_a_falsy_literal_as_the_last_statement_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    value = risky()\nexcept KeyError:\n    value = None\nuse(value)\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_an_annotated_assignment_to_a_falsy_literal_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    value = risky()\nexcept KeyError:\n    value: dict = {}\nuse(value)\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_logging_then_a_falsy_return_with_no_raise_is_still_flagged(tmp_path: pathlib.Path) -> None:
    """Logging alone is not a re-raise -- the falsy return is still this
    handler's own real exit."""
    source = "try:\n    do_work()\nexcept OSError:\n    logger.warning('boom')\n    return None\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_a_raise_nested_inside_an_if_still_suppresses_the_finding(tmp_path: pathlib.Path) -> None:
    """Deliberately reachability-blind (see module docstring): a raise
    ANYWHERE in the body, even one not on the path that actually executes,
    reads as 'this handler can fail closed'."""
    source = "try:\n    do_work()\nexcept OSError:\n    if unrecoverable():\n        raise\n    return None\n"
    assert _grade(tmp_path, source) == []


# --- what must not fire ----------------------------------------------------


def test_a_trailing_bare_raise_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept OSError:\n    logger.warning('boom')\n    raise\n"
    assert _grade(tmp_path, source) == []


def test_a_raise_naming_a_new_error_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept OSError as error:\n    raise ScanError(str(error)) from error\n"
    assert _grade(tmp_path, source) == []


def test_a_non_falsy_return_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = 'try:\n    do_work()\nexcept OSError:\n    return {"ok": True}\n'
    assert _grade(tmp_path, source) == []


def test_a_non_falsy_assignment_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    value = risky()\nexcept KeyError:\n    value = 'fallback'\nuse(value)\n"
    assert _grade(tmp_path, source) == []


def test_a_falsy_return_that_is_not_the_last_statement_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """A known miss (documented): only the body's own literal last
    statement is inspected -- a falsy return earlier, followed by a real
    raise, is exactly the shape this gate must not flag, but the same
    literal-last-statement rule also misses a falsy return buried inside an
    earlier branch. This test pins the intended (non-flagged) case, not the
    miss."""
    source = "try:\n    do_work()\nexcept OSError as error:\n    log(error)\n    raise\n"
    assert _grade(tmp_path, source) == []


def test_an_if_as_the_last_statement_is_a_stated_miss_and_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """Documented known miss: an if/else whose own trailing branch fails
    open is not inspected, since this gate never walks into a branch to
    find its own trailing statement."""
    source = "try:\n    do_work()\nexcept OSError:\n    if True:\n        return None\n"
    assert _grade(tmp_path, source) == []


def test_a_name_bound_to_a_falsy_value_elsewhere_is_a_stated_miss(tmp_path: pathlib.Path) -> None:
    """Documented known miss: read syntactically, not evaluated -- a name
    that merely holds a falsy value is not recognised."""
    source = "EMPTY = {}\ntry:\n    do_work()\nexcept OSError:\n    return EMPTY\n"
    assert _grade(tmp_path, source) == []


def test_list_constructor_call_is_a_stated_miss(tmp_path: pathlib.Path) -> None:
    """Documented known miss: only set()/frozenset() are recognised among
    zero-argument constructor calls -- list()/dict()/tuple() already have a
    literal spelling this gate does recognise, so this is deliberately
    narrower, not a gap in the literal forms themselves."""
    source = "try:\n    do_work()\nexcept OSError:\n    return list()\n"
    assert _grade(tmp_path, source) == []


def test_a_non_empty_collection_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept OSError:\n    return [1]\n"
    assert _grade(tmp_path, source) == []


def test_a_falsy_looking_string_constant_that_is_not_empty_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = 'try:\n    do_work()\nexcept OSError:\n    return "0"\n'
    assert _grade(tmp_path, source) == []


def test_a_truthy_integer_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept OSError:\n    return 1\n"
    assert _grade(tmp_path, source) == []


def test_a_float_zero_is_a_stated_miss_and_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """Documented known miss: only integer 0 is recognised, matching the
    task's own literal list -- `0.0` is a different AST-constant type and is
    not read as falsy here."""
    source = "try:\n    do_work()\nexcept OSError:\n    return 0.0\n"
    assert _grade(tmp_path, source) == []


def test_a_raise_inside_a_function_nested_deeper_than_the_top_level_is_also_excluded(
    tmp_path: pathlib.Path,
) -> None:
    """Same exclusion as the top-level case above, exercised one level
    deeper: the nested function here is not itself a top-level statement of
    the handler body, but a child of an `if` that is."""
    source = (
        "try:\n"
        "    do_work()\n"
        "except OSError:\n"
        "    if True:\n"
        "        def _unused():\n"
        "            raise RuntimeError('never called')\n"
        "    return None\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_a_raise_inside_a_nested_function_does_not_count_as_this_handlers_own(tmp_path: pathlib.Path) -> None:
    """A function *defined* inside the handler body does not run inside it
    -- its own `raise` is deferred to whenever (if ever) it is later
    called, matching gitapex_gate_exception_handler_gaps.py's own identical
    scope exclusion. The handler's own real, immediate exit is still the
    trailing falsy return."""
    source = (
        "try:\n"
        "    do_work()\n"
        "except OSError:\n"
        "    def _unused():\n"
        "        raise RuntimeError('never called')\n"
        "    return None\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_a_read_inside_a_finally_clause_is_not_a_handler_body(tmp_path: pathlib.Path) -> None:
    """No except handler is present at all; nothing to grade."""
    source = "try:\n    do_work()\nfinally:\n    return None\n"
    assert _grade(tmp_path, source) == []


# --- diff scoping ------------------------------------------------------


_HANDLER_SOURCE = "def f():\n    try:\n        do_work()\n    except OSError:\n        return None\n"


def test_a_pre_existing_finding_on_an_untouched_line_is_not_this_diffs_failure(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gate_x.py", _HANDLER_SOURCE)
    # Only line 1 (the def) is recorded as added -- neither the except
    # header nor the falsy return is touched by this diff.
    violations, _waived, graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", _HANDLER_SOURCE, [1]), tmp_path
    )
    assert graded == 1
    assert violations == []


def test_touching_only_the_except_header_line_is_this_diffs_finding(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gate_x.py", _HANDLER_SOURCE)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", _HANDLER_SOURCE, [4]), tmp_path
    )
    assert _rules(violations) == ["except-fail-open"]


def test_touching_only_the_falsy_return_line_is_this_diffs_finding(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gate_x.py", _HANDLER_SOURCE)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", _HANDLER_SOURCE, [5]), tmp_path
    )
    assert _rules(violations) == ["except-fail-open"]


def test_a_deleted_file_adds_nothing_to_grade(tmp_path: pathlib.Path) -> None:
    diff = "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n--- a/.github/scripts/gate_x.py\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-text = 1\n"
    assert gate.find_violations(diff, tmp_path) == ([], [], 0)


# --- diff-parsing hardening (ported from parse_added_lines) ---------------


def test_an_unparseable_hunk_header_raises_scanerror() -> None:
    diff = "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n--- a/x.py\n+++ b/.github/scripts/x.py\n@@ nonsense @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="unparseable hunk header"):
        gate.parse_added_lines(diff)


def test_a_post_image_header_with_no_source_header_raises_scanerror() -> None:
    diff = "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n+++ b/.github/scripts/x.py\n@@ -1,0 +1,1 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="no `--- ` source header"):
        gate.parse_added_lines(diff)


def test_a_post_image_path_without_the_b_prefix_fails_closed() -> None:
    diff = "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n--- a/x.py\n+++ x.py\n@@ -1,0 +1,1 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="not a plain b/-prefixed path"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_before_the_next_diff_git_header_raises_scanerror() -> None:
    diff = (
        "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n"
        "--- a/x.py\n+++ b/.github/scripts/x.py\n"
        "@@ -1,0 +1,2 @@\n+x = 1\n"
        "diff --git a/.github/scripts/y.py b/.github/scripts/y.py\n"
    )
    with pytest.raises(gate.ScanError, match="declared more pre-/post-image line"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_at_end_of_input_raises_scanerror() -> None:
    diff = "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n--- a/x.py\n+++ b/.github/scripts/x.py\n@@ -1,0 +1,2 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="the diff ended"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_that_drains_into_a_real_header_pair_raises_scanerror() -> None:
    """The disguised-header-absorption bypass this gate ports the guard for,
    verbatim, from gitapex_gate_exception_handler_gaps.py -- same fixture
    shape as that file's own
    test_an_over_declared_hunk_that_exactly_drains_into_a_real_header_pair_raises_scanerror."""
    diff = (
        "--- a/.github/scripts/x.py\n"
        "+++ b/.github/scripts/x.py\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/.github/scripts/y.py\n"
        "+++ b/.github/scripts/y.py\n"
        "@@ -1,1 +1,2 @@\n"
    )
    with pytest.raises(gate.ScanError, match="shaped like a new file's own post-image header"):
        gate.parse_added_lines(diff)


def test_a_header_shaped_pair_with_nothing_confirming_it_after_is_not_an_error() -> None:
    """Pins the one case `_looks_like_real_header_pair` alone cannot
    resolve (issue #1200's own already-disclosed gap, ported unchanged from
    gitapex_gate_exception_handler_gaps.py): a hunk whose declared count is
    small enough to be honestly, exactly satisfied by content that itself
    happens to look header-shaped, with nothing `@@`-/`diff --git
    `-shaped confirming it afterward."""
    diff = (
        "--- a/.github/scripts/file1.py\n"
        "+++ b/.github/scripts/file1.py\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/.github/scripts/file2.py\n"
        "+++ b/.github/scripts/file2.py\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/file1.py": {1}}


def test_an_added_line_under_a_deleted_files_hunk_is_not_recorded() -> None:
    """A `+`-prefixed line reached while `path is None` (a deletion's own
    hunk -- malformed input a hand-fed patch could produce, never real
    `git diff` output) advances the counters but is not recorded anywhere."""
    diff = "--- a/.github/scripts/gone.py\n+++ /dev/null\n@@ -0,0 +1,1 @@\n+phantom\n"
    assert gate.parse_added_lines(diff) == {}


def test_a_two_file_diff_grades_both_files(tmp_path: pathlib.Path) -> None:
    source_x = "try:\n    do_work()\nexcept OSError:\n    return None\n"
    source_y = "try:\n    do_work()\nexcept OSError:\n    raise\n"
    _write(tmp_path, ".github/scripts/x.py", source_x)
    _write(tmp_path, ".github/scripts/y.py", source_y)
    diff = _whole_file_diff(".github/scripts/x.py", source_x) + _whole_file_diff(".github/scripts/y.py", source_y)
    violations, _waived, graded = gate.find_violations(diff, tmp_path)
    assert graded == 2
    assert _at(violations) == [("except-fail-open", 3)]
    assert violations[0].path == ".github/scripts/x.py"


def test_context_and_removal_lines_advance_counters_without_being_recorded(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept OSError:\n    return None\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -1,4 +1,4 @@\n"
        " try:\n"
        "-    old_work()\n"
        "+    do_work()\n"
        " except OSError:\n"
        "     return None\n"
    )
    violations, _waived, _graded = gate.find_violations(diff, tmp_path)
    # Line 2 (do_work) is added, but neither the handler header (line 3) nor
    # the return statement (line 4) is -- so this diff owns nothing here.
    assert violations == []


# --- in-scope path filtering -----------------------------------------------


@pytest.mark.parametrize("path", [".github/scripts/gate_x.py", "hooks/check_x.py"])
def test_in_scope_paths_are_graded(path: str) -> None:
    assert gate.in_scope(path)


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_x.py",
        ".github/scripts/test_gate_x.py",
        "hooks/conftest.py",
        "evals/scripts/lint_x.py",
        "skills/a-skill/scripts/check_x.py",
        "docs/example.py",
        ".github/scripts/nested/gate_x.py",
        ".github/scripts/gate_x.pyc",
    ],
)
def test_out_of_scope_paths_are_not_graded(path: str) -> None:
    assert not gate.in_scope(path)


def test_in_scope_rejects_a_path_with_a_trailing_newline() -> None:
    assert not gate.in_scope(".github/scripts/gate_x.py\n")


def test_an_out_of_scope_file_is_not_even_read(tmp_path: pathlib.Path) -> None:
    """No file is written, so a gate that tried to read it would raise."""
    diff = _whole_file_diff("evals/scripts/lint_x.py", "return None\n")
    assert gate.find_violations(diff, tmp_path) == ([], [], 0)


def test_a_test_file_inside_an_in_scope_directory_is_not_graded(tmp_path: pathlib.Path) -> None:
    diff = _whole_file_diff(".github/scripts/test_gate_x.py", "try:\n    x()\nexcept OSError:\n    return None\n")
    assert gate.find_violations(diff, tmp_path) == ([], [], 0)


# --- inline waiver -----------------------------------------------------


def test_a_bare_marker_with_no_reason_is_not_a_waiver(tmp_path: pathlib.Path) -> None:
    source = "try:\n    do_work()\nexcept OSError:  # except-fail-open: WAIVED:\n    return None\n"
    assert _rules(_grade(tmp_path, source)) == ["except-fail-open"]


def test_the_marker_inside_a_string_literal_is_not_recorded_as_a_waiver() -> None:
    """This module's own docstring quotes the marker; so does the gate's.
    Read through tokenize, a quoted marker is text, not a comment."""
    source = (
        "# except-fail-open: WAIVED: a real waiver on line 1\n"
        'value = "# except-fail-open: WAIVED: fake, inside a string literal"\n'
    )
    assert gate._waived_lines(source) == {1}


# --- find_violations: unreadable/missing files -----------------------------


def test_a_file_named_by_the_diff_but_missing_from_root_raises_scanerror(tmp_path: pathlib.Path) -> None:
    diff = _whole_file_diff(".github/scripts/gone.py", "try:\n    x()\nexcept OSError:\n    return None\n")
    with pytest.raises(gate.ScanError, match="missing from"):
        gate.find_violations(diff, tmp_path)


def test_an_unparseable_python_file_raises_scanerror(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gate_x.py", "def f(:\n")
    diff = _whole_file_diff(".github/scripts/gate_x.py", "def f(:\n")
    with pytest.raises(gate.ScanError, match="cannot be parsed as Python"):
        gate.find_violations(diff, tmp_path)


def test_a_non_utf8_file_raises_scanerror(tmp_path: pathlib.Path) -> None:
    path = tmp_path / ".github" / "scripts" / "gate_x.py"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe not utf-8")
    diff = _whole_file_diff(".github/scripts/gate_x.py", "x = 1\n")
    with pytest.raises(gate.ScanError, match="cannot be read as UTF-8 text"):
        gate.find_violations(diff, tmp_path)


# --- CLI / main() ------------------------------------------------------


def test_main_exits_2_on_a_root_that_does_not_exist(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(tmp_path / "nope")]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_is_a_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    a_file = _write(tmp_path, "not-a-directory", "x")
    assert gate.main(["--root", str(a_file)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_when_the_diff_file_is_missing(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "nope.diff")]) == 2
    assert "diff cannot be read" in capsys.readouterr().err


def test_main_exits_2_when_the_diff_file_is_not_utf8(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    diff_path = tmp_path / "diff.bin"
    diff_path.write_bytes(b"\xff\xfe not a diff")
    assert gate.main(["--root", str(tmp_path), "--diff", str(diff_path)]) == 2
    assert "diff cannot be read" in capsys.readouterr().err


def test_main_exits_2_on_a_scanerror_from_find_violations(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    diff = _whole_file_diff(".github/scripts/gone.py", "x = 1\n")
    _write(tmp_path, "diff.txt", diff)
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "missing from" in capsys.readouterr().err


def test_an_empty_diff_is_clean_and_says_so(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "diff.txt", "")
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 0
    assert "OK: 0 in-scope file(s) graded" in capsys.readouterr().out


def test_main_returns_one_and_explains_the_failure(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = "try:\n    do_work()\nexcept OSError:\n    return None\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 1
    stderr = capsys.readouterr().err
    assert "except-fail-open" in stderr
    assert "#1722" in stderr
    assert "except-fail-open: WAIVED:" in stderr


def test_main_prints_honoured_waivers(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = "try:\n    do_work()\nexcept OSError:  # except-fail-open: WAIVED: intentional sentinel\n    return None\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 0
    stdout = capsys.readouterr()
    assert "waived inline" in stdout.err
    assert "OK: 1 in-scope file(s) graded, 1 inline waiver(s) honoured." in stdout.out


class _FakeStdin:
    """Just the surface `main` uses: `sys.stdin.buffer.read()`."""

    def __init__(self, data: bytes) -> None:
        import io as _io

        self.buffer = _io.BytesIO(data)


def test_main_reads_the_diff_from_stdin_when_no_flag_is_given(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "try:\n    do_work()\nexcept OSError:\n    return None\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    diff = _whole_file_diff(".github/scripts/gate_x.py", source)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(diff.encode("utf-8")))
    assert gate.main(["--root", str(tmp_path)]) == 1
    assert "except-fail-open" in capsys.readouterr().err


def test_a_non_utf8_byte_on_stdin_fails_closed_instead_of_crashing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"+# \xff\xfe\n"))
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "diff cannot be read as UTF-8 text" in capsys.readouterr().err


# --- workflow drift -----------------------------------------------------


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    assert_workflow_diff_carries_flags(_WORKFLOW, "--no-renames", "core.quotePath=false")


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    assert_workflow_checkout_pins_head_sha_with_full_history(_WORKFLOW)


def test_the_workflow_has_no_paths_filter() -> None:
    assert_workflow_has_no_trigger_path_filter(_WORKFLOW)


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    assert_workflow_feeds_merge_base_to(_WORKFLOW, "diff")


def test_this_gate_grades_itself_clean() -> None:
    """The gate is itself an in-scope checker script; a gate that could not
    parse or grade its own source would be a strange thing to trust."""
    source = pathlib.Path(gate.__file__).read_text(encoding="utf-8")
    violations, _waived, graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gitapex_gate_except_fail_open.py", source), REPO_ROOT
    )
    assert graded == 1
    assert violations == []

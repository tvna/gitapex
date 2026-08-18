"""Tests for the detection-logic property-coverage gate
(.github/scripts/gitapex_gate_detection_logic_property_coverage.py).

Issue #1178. Mirrors tests/test_gitapex_gate_exception_handler_gaps.py's own
fixture/assertion style for "a gate of this exact shape": synthetic
unified-diff-text fixtures, tmp_path-based --root trees, and direct calls
into the gate module's own functions rather than only subprocess CLI
invocation.

Per this repository's defeat-test-disclosure process, at least one test
below is specifically constructed to defeat -- not merely exercise the
happy path of -- the new detection logic; see the `test_defeat_*` tests
below.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_detection_logic_property_coverage as gate
import pytest
from conftest import FakeStdin as _FakeStdin
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

# A plain hooks/gitapex_check_*.py path -- in scope by _IN_SCOPE_RE's own
# `hooks/gitapex_check_[^/]+\.py` alternative -- used as the default fixture
# location across most tests below.
_FIXTURE_PATH = "hooks/gitapex_check_fixture.py"

# The co-located properties file the gate's own `_properties_path` computes
# from `_FIXTURE_PATH`'s stem. Named once rather than spelled out at each
# `_write` call site below, so the two stay in lockstep: a change to
# `_FIXTURE_PATH` that missed one literal would silently write the fixture's
# coverage to a path the gate never looks at, and every "a covering
# properties file clears it" test would pass for the wrong reason.
_FIXTURE_PROPERTIES_PATH = "tests/test_gitapex_check_fixture_properties.py"

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

# A trigger call at true module level (line 4), outside any function. The
# `re.compile(...)` on line 3 is a trigger too, so every diff built from this
# fixture adds only line 4 -- otherwise the compile call contributes a second
# finding and the module-level attribution under test is no longer isolated.
_MODULE_LEVEL_TRIGGER_SOURCE = 'import re\n\nSOME_RE = re.compile(r"^[a-z]+$")\nSOME_RE.fullmatch("literal")\n'

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

# A diff whose hunk header cannot be parsed -- the ScanError contract's own
# malformed-input fixture, asserted once directly against `parse_added_lines`
# and once through `main()`'s catch-and-exit-2 wrapper. The `--- ` line is
# load-bearing, not decoration: without it this fixture is malformed in two
# independent ways at once and raises on the *missing source header* before
# ever reaching the hunk header it is named for, so the two tests below would
# pass while asserting nothing about `_HUNK_RE`.
_UNPARSEABLE_HUNK_DIFF = (
    f"diff --git a/x.py b/{_FIXTURE_PATH}\n--- a/x.py\n+++ b/{_FIXTURE_PATH}\n@@ garbage @@\n+x = 1\n"
)

# A diff whose `+++ ` post-image header is reached outside a hunk with no
# `--- ` source header before it. Real `git diff` always emits both, so this
# is a hand-fed or foreign patch -- the shape `--diff <file>` accepts from
# anywhere. Used by the fail-closed regression below.
_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF = (
    f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
    f"+++ b/{_FIXTURE_PATH}\n"
    "@@ -0,0 +1,2 @@\n"
    "+import re\n"
    '+SOME_RE = re.compile(r"^[a-z]+$")\n'
)

# Issue #1129's own defect shape, spelled through an aliased `re` import:
# identical detection logic to _CHECK_VALUE_SOURCE's own compile call, with
# the module bound to `_re` instead of `re`. Used by the defeat test below.
_ALIASED_RE_IMPORT_SOURCE = (
    'import re as _re\n\n_KEY_RE = _re.compile(r"^[a-z][a-z0-9-]*$")\n\n\ndef check_key(key):\n    return 1\n'
)

# The same file with the module imported plainly. Byte-for-byte the same
# compile call otherwise, so the defeat test's own control differs from it in
# exactly one thing: the name the `re` module is bound to.
_PLAIN_RE_IMPORT_SOURCE = (
    'import re\n\n_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")\n\n\ndef check_key(key):\n    return 1\n'
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


def _grade_added(
    tmp_path: pathlib.Path, source: str, added: list[int], *, relative: str = _FIXTURE_PATH
) -> tuple[list[gate.Finding], list[gate.Finding]]:
    """Write `source` at `relative`, grade it with only the 1-based line
    numbers in `added` present in the diff, return ``(violations, waivers)``.

    The diff-scoped counterpart of `_grade` above, and its `graded == 1`
    assertion is load-bearing for the same reason: without it, a gate that
    read nothing at all would satisfy every "must not fire" assertion below
    at once. Any co-located properties file a test needs must be written
    before this call, since it grades immediately.
    """
    _write(tmp_path, relative, source)
    violations, waived, graded = gate.find_violations(_partial_diff(relative, source, added), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations, waived


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
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_SOURCE, [6, 7])
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
    _write(tmp_path, _FIXTURE_PROPERTIES_PATH, _PROPERTIES_COVERING_CHECK_VALUE)
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_SOURCE, [6, 7])
    assert violations == []
    assert waived == []


def test_waived_case_the_trigger_line_carries_an_honoured_inline_waiver(
    tmp_path: pathlib.Path,
) -> None:
    """The true-positive shape above, but the trigger line itself carries a
    `# detection-logic-property-coverage: WAIVED: <reason>` trailing
    comment: zero violations, and the finding surfaces in find_violations's
    own second (waived) return element instead."""
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_WAIVED_SOURCE, [6, 7])
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
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_WITH_OTHER_FUNCTION_SOURCE, [11])
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
    violations, waived = _grade_added(tmp_path, _MULTILINE_CALL_SOURCE, [8])
    assert _at(violations) == [("regex-property-gap", 7)]
    assert waived == []


# --- parse_added_lines: bare hunk header defaults to one post-image line ----


def test_a_bare_hunk_header_with_no_comma_count_defaults_to_one_line_each_side() -> None:
    """`_HUNK_RE`'s pre-/post-image count groups are each independently
    optional; `parse_added_lines` treats either omitted count as exactly 1
    line on that side (module docstring: unified-diff shorthand). A single
    context line consumes exactly 1 pre-image and 1 post-image line, so a
    fully bare `@@ -N +M @@` header (both counts omitted) followed by
    exactly one context line is accurately declared on both sides at once
    -- the simplest input that exercises both `match.group(1) is None` and
    `match.group(3) is None` together without tripping issue #1193's own
    declared/actual validation.

    Previously exercised only incidentally by
    test_parse_added_lines_matches_an_independently_computed_line_count's
    own synthetic diffs; that property test's `_file_diff_text` helper now
    declares explicit, accurate counts on both sides instead (the bare
    form's implicit 1 only coincidentally matches a generated hunk body
    often enough to keep exercising this branch by accident, which is
    exactly the "covered only by accident" shape this repository's own
    tests avoid elsewhere), so this fixed example keeps the bare-header
    branch itself directly, deliberately covered."""
    diff = "--- a/hooks/gitapex_check_fixture.py\n+++ b/hooks/gitapex_check_fixture.py\n@@ -1 +1 @@\n def f():\n"
    assert gate.parse_added_lines(diff) == {}


# --- malformed input: ScanError contract ------------------------------------


def test_an_unparseable_hunk_header_raises_scanerror() -> None:
    with pytest.raises(gate.ScanError, match="unparseable hunk header"):
        gate.parse_added_lines(_UNPARSEABLE_HUNK_DIFF)


def test_a_post_image_header_with_no_source_header_before_it_raises_scanerror() -> None:
    """Fail-closed regression. `parse_added_lines` only binds the current
    path from a `+++ ` header that a `--- ` header preceded. Ignoring an
    unpaired `+++ ` (the behaviour this gate started with, inherited from
    `gitapex_gate_exception_handler_gaps.py`) leaves `path` at None, so every
    added line after it is silently dropped and the whole run reports
    `OK: 0 in-scope file(s) graded` and exits 0 -- a silent pass on an
    ungradable input, which the module docstring's own "Exit codes" section
    says never happens. It must raise instead."""
    with pytest.raises(gate.ScanError, match="no `--- ` source header before it"):
        gate.parse_added_lines(_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF)


def test_an_added_line_whose_own_content_begins_with_a_plus_header_is_not_a_header(
    tmp_path: pathlib.Path,
) -> None:
    """The guard the fail-closed check above must not break: *inside* a hunk
    every line carries a one-character prefix, so an added line whose own
    content begins `++ ` is emitted as `+++ ...` and must still be read as
    content. It is neither a header nor a `ScanError` -- the diff below adds
    two lines and both are graded as post-image lines 1 and 2."""
    diff = (
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -0,0 +1,2 @@\n"
        "+++ not a header\n"
        "+x = 1\n"
    )
    assert gate.parse_added_lines(diff) == {_FIXTURE_PATH: {1, 2}}


def test_a_deleted_file_contributes_no_added_lines_and_is_not_an_error(
    tmp_path: pathlib.Path,
) -> None:
    """A deletion is the one legitimate way a hunk body is read with no
    current path bound: `_diff_target_path` maps `+++ /dev/null` to None, so
    `parse_added_lines` skips every line of that file's hunk rather than
    attributing it to whichever file came before.

    Pinned here explicitly because it was previously covered only by
    accident. The `_UNPARSEABLE_HUNK_DIFF` fixture above used to omit its
    `--- ` line, which left `path` at None for an entirely different and
    malformed reason, and that accident -- not any test of the deletion
    contract -- was what exercised this branch. Both halves of the diff below
    are asserted: the deleted file contributes nothing at all (no key, not
    even an empty one), and a second, real file in the same diff is still
    graded normally afterwards."""
    diff = (
        "diff --git a/hooks/gitapex_check_gone.py b/hooks/gitapex_check_gone.py\n"
        "--- a/hooks/gitapex_check_gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-import re\n"
        '-SOME_RE = re.compile(r"^[a-z]+$")\n'
        f"diff --git a/{_FIXTURE_PATH} b/{_FIXTURE_PATH}\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -0,0 +1,1 @@\n"
        "+x = 1\n"
    )
    assert gate.parse_added_lines(diff) == {_FIXTURE_PATH: {1}}


# --- parse_added_lines: dual pre-/post-image count tracking (issue #1193,
# porting issue #1184's own proven fix from gitapex_gate_exception_handler_
# gaps.py) ------------------------------------------------------------------


def test_a_deleted_files_own_removal_lines_still_bound_in_hunk() -> None:
    """Ported from `gitapex_gate_exception_handler_gaps.py`'s own identical
    regression test (issue #1184's CodeRabbit review finding on that file's
    port). `path` is None for the whole of a deleted file's hunk (`+++
    /dev/null` maps to None), so a version of this parser that skipped
    counter decrements whenever `path is None` would leave `old_remaining`/
    `new_remaining` frozen at their post-header values and `in_hunk` stuck
    True indefinitely -- so a patch with no `diff --git ` header between a
    deleted file and the next one would leave that next file's own real
    `--- `/`+++ ` headers unrecognised. The counters and the exhaustion
    check now run regardless of `path`; only recording into `added` is
    still guarded on it, so a deleted file's own declared removal count
    correctly bounds its hunk and the next file is read normally
    afterward."""
    diff = (
        "--- a/hooks/gitapex_check_deleted.py\n"
        "+++ /dev/null\n"
        "@@ -1,3 +0,0 @@\n"
        "-line1\n"
        "-line2\n"
        "-line3\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -1,1 +1,2 @@\n"
        " def g():\n"
        "+    pass\n"
    )
    assert gate.parse_added_lines(diff) == {_FIXTURE_PATH: {2}}


def test_an_added_line_under_a_deleted_files_hunk_advances_counters_but_is_not_recorded() -> None:
    """A real `+++ /dev/null` hunk is never declared with post-image lines
    -- a deletion has nothing left to add -- but a hand-fed or foreign
    patch (the same `--diff` exposure every malformed-input test in this
    module guards against) could claim one anyway. `path` is None for the
    whole of a deleted file's hunk, so the `+` branch's own
    `if path is not None: added.setdefault(...)` guard must skip recording
    -- there is no real path to attribute it to -- while still advancing
    `lineno` and `new_remaining` exactly as a real addition would, so the
    hunk's own declared count is still correctly consumed and does not
    leak into whatever follows."""
    diff = (
        "--- a/hooks/gitapex_check_gone.py\n"
        "+++ /dev/null\n"
        "@@ -0,0 +1,1 @@\n"
        "+phantom added line under a deletion\n"
        f"--- a/{_FIXTURE_PATH}\n"
        f"+++ b/{_FIXTURE_PATH}\n"
        "@@ -0,0 +1,1 @@\n"
        "+x = 1\n"
    )
    assert gate.parse_added_lines(diff) == {_FIXTURE_PATH: {1}}


def test_a_zero_post_image_hunk_still_protects_its_own_removal_lines() -> None:
    """Ported from `gitapex_gate_exception_handler_gaps.py`'s own identical
    regression test (found during that file's own #1184 port review, fixed
    there first). `git diff -U0` -- this gate's real wired invocation --
    emits a pure-deletion hunk as `@@ -a,b +c,0 @@`: zero post-image lines.
    Bounding `in_hunk` by the post-image count alone reads `new_remaining`
    as already exhausted on the `@@` line itself, before the hunk's own
    removal lines are consumed, so the very next line -- itself this
    hunk's own removal content -- is read as a real header instead if it
    happens to look like one.

    Verified live against a post-image-count-only bound: this exact diff
    returns `{'hooks/gitapex_check_payload.py': {1}}` -- the real added
    line on `gitapex_check_target.py` silently vanishes, reattributed to a
    same-shaped but unrelated file entirely. Tracking the pre-image count
    too (a removal decrements it) protects this hunk's own removal line via
    that side even though the post-image side is already at zero, so the
    disguised `--- `/`+++ ` pair below is correctly read as hunk content,
    not headers -- and the *real* `+++ ` header three lines later (with no
    preceding real `--- `) correctly raises instead."""
    diff = (
        "diff --git a/hooks/gitapex_check_target.py b/hooks/gitapex_check_target.py\n"
        "--- a/hooks/gitapex_check_target.py\n"
        "+++ b/hooks/gitapex_check_target.py\n"
        "@@ -1,1 +1,0 @@\n"
        "--- a disguised removal line, not a real source header\n"
        "+++ b/hooks/gitapex_check_payload.py\n"
        '+text = p.read_text(encoding="utf-8")\n'
    )
    with pytest.raises(gate.ScanError, match="no `--- ` source header before it"):
        gate.parse_added_lines(diff)


def test_a_pure_deletion_hunk_contributes_nothing_and_does_not_disrupt_the_next_file() -> None:
    """Ported from `gitapex_gate_exception_handler_gaps.py`'s own identical
    regression test. The realistic shape behind the regression above, with
    no adversarial disguise: `git diff -U0` emits a pure-deletion hunk
    exactly as `@@ -a,b +c,0 @@` whenever a diff removes lines with nothing
    added in their place, which is ordinary, everyday output, not a
    contrived input. The deleted file contributes no added lines (a pure
    removal has none to grade), and the next file's own real headers --
    reached via a normal `diff --git ` separator, matching every real
    multi-file `git diff` -- must still be read correctly and graded on its
    own merits."""
    diff = (
        "diff --git a/hooks/gitapex_check_a.py b/hooks/gitapex_check_a.py\n"
        "--- a/hooks/gitapex_check_a.py\n"
        "+++ b/hooks/gitapex_check_a.py\n"
        "@@ -3,1 +2,0 @@\n"
        "-old_line_being_removed = 1\n"
        "diff --git a/hooks/gitapex_check_b.py b/hooks/gitapex_check_b.py\n"
        "--- a/hooks/gitapex_check_b.py\n"
        "+++ b/hooks/gitapex_check_b.py\n"
        "@@ -1,1 +1,2 @@\n"
        " def g():\n"
        "+    pass\n"
    )
    assert gate.parse_added_lines(diff) == {"hooks/gitapex_check_b.py": {2}}


def test_a_second_file_with_no_diff_git_header_between_files_is_not_misattributed(
    tmp_path: pathlib.Path,
) -> None:
    """CodeRabbit's own finding against this PR: `in_hunk` used to be reset
    only by a `diff --git ` line, never by a hunk's own declared post-image
    length running out. A patch with no `diff --git ` header between two
    files (real `git diff` output always has one; `--diff <file>` accepts a
    patch from anywhere, the same exposure the header-pair fix above
    closes) left `in_hunk` True straight through the second file's own
    `--- `/`+++ ` lines: `--- ` read as a harmless no-op removal, but
    `+++ ` -- never recognised as a header -- read as *content* (its own
    leading `+`) and was added to the *first* file's path at a stale
    `lineno`, and because `path` never advanced, the second file's own real
    added line misattributed to the first file too.

    Verified live against the pre-fix gate: this exact diff returned
    `{'hooks/gitapex_check_file1.py': {2, 3, 4}}` -- file2's own line
    silently missing, and a bogus line 4 (the misread `+++ ` header)
    attributed to file1 instead. Both files must now be graded separately,
    each at its own correct line numbers, with nothing bogus added.

    `@@ -1,1 +1,3 @@`, not `-1,2`: the hunk's own body has one context line
    (old+new) and two additions (new only), so the accurate pre-image count
    is 1 -- an inflated pre-image count here would leave `old_remaining`
    permanently above zero (nothing in this body ever decrements it to 0)
    and reopen this exact gap under the dual-counter accounting issue
    #1193 ported from `gitapex_gate_exception_handler_gaps.py`, despite
    being an inaccuracy `git diff` itself never produces."""
    diff = (
        "--- a/hooks/gitapex_check_file1.py\n"
        "+++ b/hooks/gitapex_check_file1.py\n"
        "@@ -1,1 +1,3 @@\n"
        " import re\n"
        '+SOME_RE = re.compile(r"a")\n'
        '+SOME_RE.fullmatch("x")\n'
        "--- a/hooks/gitapex_check_file2.py\n"
        "+++ b/hooks/gitapex_check_file2.py\n"
        "@@ -1,1 +1,2 @@\n"
        " import re\n"
        '+OTHER_RE = re.compile(r"b")\n'
    )
    assert gate.parse_added_lines(diff) == {
        "hooks/gitapex_check_file1.py": {2, 3},
        "hooks/gitapex_check_file2.py": {2},
    }


def test_an_over_declared_hunk_length_before_a_new_hunk_header_raises_scanerror() -> None:
    """Issue #1193, found adversarially against the dual-counter fix
    directly above: that fix bounds `in_hunk` by each side's own *declared*
    length, but never checks either declared count against how many
    pre-/post-image lines the hunk body actually has. `@@ -0,0 +1,5 @@`
    declares a pure-addition hunk (0 pre-image lines, matched by its body:
    no context, no removal) claiming 5 post-image lines; only 2 real
    added lines follow before the next file's own `--- `/`+++ ` headers
    begin. With no `diff --git ` separator between the two files (the same
    exposure the dual-counter fix above closes), `new_remaining` stays
    above zero once the real body is exhausted, so `in_hunk` stays True
    straight through those headers: `--- ` is read as a pre-image-only
    removal (harmlessly decrementing the already-exhausted `old_remaining`
    further negative), but `+++ ` reads as *content* and gets misattributed
    to the first file at a stale `lineno`, reproducing the identical
    failure shape for a different reason. Must now raise instead of
    silently misattributing, caught here at the second file's own `@@`
    line -- the next unambiguous boundary -- before any of its real content
    is consumed. `new_remaining` is 2 at that point: 5 declared, minus the
    2 real added lines already consumed."""
    diff = (
        "--- a/hooks/gitapex_check_file1.py\n"
        "+++ b/hooks/gitapex_check_file1.py\n"
        "@@ -0,0 +1,5 @@\n"
        "+def f():\n"
        "+    pass\n"
        "--- a/hooks/gitapex_check_file2.py\n"
        "+++ b/hooks/gitapex_check_file2.py\n"
        "@@ -1,1 +1,2 @@\n"
        " def g():\n"
        "+    pass\n"
    )
    with pytest.raises(gate.ScanError, match=r"2 post-image line\(s\) still unconsumed"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_length_before_a_diff_git_header_raises_scanerror() -> None:
    """Same over-declaration as directly above, but with a `diff --git `
    separator before the second file -- the shape a real `git diff` always
    emits. `diff --git ` is recognised unconditionally (no `not in_hunk`
    guard), so it is a second, independent place the same declared/actual
    mismatch must be caught -- reached one line earlier than the `@@` case
    above, before either of file2's own `--- `/`+++ ` lines is consumed, so
    `new_remaining` is still 3 (not yet decremented by a misread `+++ `
    line): 5 declared, minus only the 2 real added lines."""
    diff = (
        "--- a/hooks/gitapex_check_file1.py\n"
        "+++ b/hooks/gitapex_check_file1.py\n"
        "@@ -0,0 +1,5 @@\n"
        "+def f():\n"
        "+    pass\n"
        "diff --git a/hooks/gitapex_check_file2.py b/hooks/gitapex_check_file2.py\n"
        "--- a/hooks/gitapex_check_file2.py\n"
        "+++ b/hooks/gitapex_check_file2.py\n"
        "@@ -1,1 +1,2 @@\n"
        " def g():\n"
        "+    pass\n"
    )
    with pytest.raises(gate.ScanError, match=r"3 post-image line\(s\) still unconsumed"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_length_at_end_of_input_raises_scanerror() -> None:
    """Same over-declaration as the two tests above, but with nothing at all
    following the short body -- no second file, no further hunk. Neither
    the `diff --git ` nor the `@@` boundary check ever fires, so this is a
    third, independent place the same declared/actual mismatch must be
    caught: end of input reached with `in_hunk` still true, `new_remaining`
    still 3."""
    diff = "--- a/hooks/gitapex_check_file1.py\n+++ b/hooks/gitapex_check_file1.py\n@@ -0,0 +1,5 @@\n+def f():\n+    pass\n"
    with pytest.raises(gate.ScanError, match=r"3 post-image line\(s\) still unconsumed"):
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
    _write(tmp_path, _FIXTURE_PROPERTIES_PATH, _PROPERTIES_COVERING_WRONG_FUNCTION)
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_SOURCE, [6, 7])
    assert _at(violations) == [("regex-property-gap", 7)]
    assert waived == []


def test_defeat_an_aliased_re_import_does_not_hide_a_new_compile_call(
    tmp_path: pathlib.Path,
) -> None:
    """DEFEAT-oriented, and the shape that actually defeated this gate as
    first written: category (a)'s `.compile(...)` half is receiver-*specific*
    on purpose (an unrelated object's `.compile()` is not detection logic),
    and the receiver check originally demanded the literal name `re`. So a
    file that binds the very same stdlib module under another name --
    `import re as _re` -- and then adds `_re.compile(r"...")` graded clean,
    exit 0, while the byte-for-byte identical `re.compile(r"...")` graded as
    a violation.

    Grounded in what this gate exists to catch, not in what is convenient to
    construct. The diff here adds *only* the compile line: that is the shape
    a materially changed allowlist pattern takes, and it is the half of
    issue #1129's own defect that sat away from the call site --
    `EXEC_REQ_PACKAGES_KEY_RE = re.compile(...)` on one line, the
    `.match(key)` that misused it far below. The receiver-agnostic
    `.match`/`.search`/`.fullmatch` half of category (a) does not rescue
    this: no call site is touched by this diff at all, so with the compile
    call unrecognised there is nothing left to grade and the pattern change
    ships with no property test and no finding.

    Both halves are asserted together so the fix cannot be mistaken for
    "report every `.compile()`": the aliased spelling must now be flagged,
    and `_re_module_names` must reach that verdict only because this file's
    own `import re as _re` binds the name -- which the sibling
    over-report test below pins from the other side."""
    aliased = _grade(tmp_path, _ALIASED_RE_IMPORT_SOURCE, relative=_FIXTURE_PATH)
    plain = _grade(tmp_path, _PLAIN_RE_IMPORT_SOURCE, relative="hooks/gitapex_check_plain.py")
    assert _at(aliased) == [("regex-property-gap", 3)]
    assert _at(plain) == [("regex-property-gap", 3)]


def test_a_compile_call_on_a_receiver_no_import_binds_to_re_is_not_a_trigger(
    tmp_path: pathlib.Path,
) -> None:
    """The over-report boundary of the alias fix above, from the other side.
    `_re_module_names` widens the accepted `.compile(...)` receiver only to
    names an `import re` in *this file* actually binds, so a `.compile()` on
    an unrelated object, and a same-named third-party module this file
    imports instead of the stdlib one, must both stay unreported -- the
    module docstring's own reason for keeping `.compile` out of the
    receiver-agnostic set at all. Without this pin the alias fix could be
    "corrected" into a blanket receiver-agnostic `.compile` match and every
    test above would stay green."""
    source = (
        "import regex\n\n\ndef build(template, pattern):\n    template.compile()\n    return regex.compile(pattern)\n"
    )
    assert _grade(tmp_path, source) == []


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


# --- coverage completeness: branches the cases above don't reach ----------


def test_path_resolution_true_positive_os_path_realpath_call(tmp_path: pathlib.Path) -> None:
    """`os.path.realpath(...)`, category (b)'s `_OS_PATH_ATTRS` half --
    matched on the call's own final two attribute segments, not exercised
    by the plain `.resolve()` true positive above."""
    source = "import os\n\n\ndef check_real(p):\n    return os.path.realpath(p)\n"
    violations = _grade(tmp_path, source)
    assert _at(violations) == [("path-resolution-property-gap", 5)]


@pytest.mark.parametrize(
    ("expression", "rule"),
    [
        ("PAT.match(x)", "regex-property-gap"),
        ("PAT.search(x)", "regex-property-gap"),
        ("x.endswith('a')", "string-comparison-property-gap"),
        ("x not in ['a', 'b']", "string-comparison-property-gap"),
        ("set(['a', 'b'])", "string-comparison-property-gap"),
        ("PATH.is_symlink()", "path-resolution-property-gap"),
        ("PATH.relative_to('/a')", "path-resolution-property-gap"),
        ("os.path.abspath(x)", "path-resolution-property-gap"),
    ],
)
def test_every_trigger_table_member_fires_under_its_own_documented_category(
    tmp_path: pathlib.Path, expression: str, rule: str
) -> None:
    """One case per trigger-table member the tests above never reach.

    Each of these shares its code path with a sibling that *is* exercised
    elsewhere -- `.endswith` with `.startswith`, `.is_symlink`/`.relative_to`
    with `.resolve`, `abspath` with `realpath`, `not in` with `in`, `set([
    ...])` with `frozenset([...])`, `.match`/`.search` with `.fullmatch` --
    so branch coverage stays green whether or not the member string itself is
    right. A typo in one (`"endswith"` written `"endwith"`, an entry dropped
    from `_OS_PATH_ATTRS`) silently turns that member off and no other test
    in this file notices. These pin each member by name, one assertion per
    member, against the category the module docstring assigns it."""
    source = f"import os\n\nPAT = None\nPATH = None\n\n\ndef check(x):\n    return {expression}\n"
    violations = _grade(tmp_path, source)
    assert _at(violations) == [(rule, 8)]


def test_two_triggers_of_one_category_on_one_physical_line_report_once(
    tmp_path: pathlib.Path,
) -> None:
    """Pins the same-line deduplication the module docstring's own "Known
    misses in the trigger table itself" section discloses, so it cannot
    change without a reader noticing.

    `x in ["a", y.startswith("b")]` is two separate category-(c) triggers --
    an `in`-literal comparison and a `.startswith()` call -- landing on one
    line in one scope, so all four `Finding` fields match and
    `sorted(set(...))` collapses them to one. Two triggers of *different*
    categories on one line still report twice, since `rule` and `message`
    differ; the second half asserts that, so the dedup can never quietly
    widen into "one finding per line" full stop."""
    same_category = "def check(x, y):\n    return x in ['a', y.startswith('b')]\n"
    assert _at(_grade(tmp_path, same_category)) == [("string-comparison-property-gap", 2)]

    both_categories = "def check(p):\n    return p.resolve().startswith('a')\n"
    assert _at(_grade(tmp_path, both_categories, relative="hooks/gitapex_check_two.py")) == [
        ("path-resolution-property-gap", 2),
        ("string-comparison-property-gap", 2),
    ]


def test_calls_and_comparisons_matching_no_trigger_category_produce_no_finding(
    tmp_path: pathlib.Path,
) -> None:
    """Exercises every "falls through to no match" branch across the
    trigger-classifier functions in one fixture: a call whose own callee is
    neither an attribute nor a bare name (`FACTORIES[0](x)`, reaching
    `_string_comparison_call_trigger`'s final `return False`), a chained
    comparison (`0 < x < 10`, two ops, reaching `_string_comparison_compare_
    trigger`'s own op/comparator-count mismatch `return False`), and a
    single non-`in` comparison (`x == 1`, reaching that same function's own
    non-`In`/`NotIn` `return False`). None of these is a trigger; there
    must be zero findings."""
    source = (
        "FACTORIES = [str]\n\n\n"
        "def check_call(x):\n"
        "    if 0 < x < 10:\n"
        "        pass\n"
        "    if x == 1:\n"
        "        return FACTORIES[0](x)\n"
        "    return None\n"
    )
    violations = _grade(tmp_path, source)
    assert violations == []


def test_module_level_trigger_with_no_properties_file_reports_module_scope(
    tmp_path: pathlib.Path,
) -> None:
    """A trigger call at true module level (outside any function) is
    attributed to the sentinel scope name `<module>`, and `_scope_label`
    renders the finding's own message as "module level" rather than a
    backtick-quoted function name. `re.compile(...)` on line 3 is
    deliberately left untouched by the diff (only line 4 is added) so it
    does not itself contribute a second finding -- this test isolates the
    bound-method call's own module-level attribution."""
    violations, waived = _grade_added(tmp_path, _MODULE_LEVEL_TRIGGER_SOURCE, [4])
    assert waived == []
    assert len(violations) == 1
    assert violations[0].rule == "regex-property-gap"
    assert violations[0].line == 4
    assert "module level" in violations[0].message


def test_true_negative_hypothesis_given_attribute_form_also_counts(
    tmp_path: pathlib.Path,
) -> None:
    """`@hypothesis.given(...)` -- the attribute form, not the bare `given`
    name form `from hypothesis import given` gives -- must be recognised
    too. `_is_given_decorator`'s own docstring states both forms count."""
    properties_source = (
        "import gitapex_check_fixture\n"
        "import hypothesis\n"
        "\n\n"
        "@hypothesis.given(hypothesis.strategies.text())\n"
        "def test_check_value_matches(x):\n"
        "    gitapex_check_fixture.check_value(x)\n"
    )
    _write(tmp_path, _FIXTURE_PROPERTIES_PATH, properties_source)
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_SOURCE, [6, 7])
    assert violations == []
    assert waived == []


def test_a_properties_file_with_invalid_syntax_is_treated_as_uncovered_not_a_scanerror(
    tmp_path: pathlib.Path,
) -> None:
    """A co-located properties file that exists but is not valid Python
    must not raise -- per `_properties_tree`'s own docstring, the *source*
    file's own triggers stay fully enumerable without it; only the
    coverage verdict for scopes in that file degrades to conservative
    (uncovered), never a `ScanError`."""
    _write(tmp_path, _FIXTURE_PROPERTIES_PATH, "def broken(:\n")
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_SOURCE, [6, 7])
    assert len(violations) == 1
    assert waived == []


def test_module_level_trigger_is_cleared_by_any_given_test_in_a_covering_properties_file(
    tmp_path: pathlib.Path,
) -> None:
    """The `<module>`-scope half of `_covered`'s own True branch: once a
    properties file both imports the source module and has *some*
    `@given`-decorated function, a module-level trigger clears -- no name
    match is required, since a bare module-level constant has no function
    identity to search a body for. Not exercised by the module-level
    true-positive test above, which deliberately has no properties file at
    all."""
    _write(tmp_path, _FIXTURE_PROPERTIES_PATH, _PROPERTIES_COVERING_CHECK_VALUE)
    violations, waived = _grade_added(tmp_path, _MODULE_LEVEL_TRIGGER_SOURCE, [4])
    assert violations == []
    assert waived == []


def test_given_decorator_recognition_rejects_a_bare_given_and_a_non_name_non_attribute_callee(
    tmp_path: pathlib.Path,
) -> None:
    """`_is_given_decorator` only matches an actual `@given(...)`/
    `@hypothesis.given(...)` *call*. A bare `@given` with no parentheses
    (not a `Call` node at all) and a decorator that is a `Call` whose own
    `func` is neither a plain name nor an attribute access (e.g. a
    call-returning-a-callable pattern) must both be rejected -- neither
    counts as coverage, so the finding must stay a violation."""
    properties_source = (
        "import gitapex_check_fixture\n"
        "from hypothesis import given\n"
        "\n\n"
        "@given\n"  # bare decorator, no call at all -- ast.Name, not ast.Call
        "def test_bare(x):\n"
        "    gitapex_check_fixture.check_value(x)\n"
        "\n\n"
        "def _decorator_factory():\n"
        "    return given\n"
        "\n\n"
        "@_decorator_factory()()\n"  # a Call whose own func is itself a Call
        "def test_weird_callee(x):\n"
        "    gitapex_check_fixture.check_value(x)\n"
    )
    _write(tmp_path, _FIXTURE_PROPERTIES_PATH, properties_source)
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_SOURCE, [6, 7])
    assert len(violations) == 1
    assert waived == []


def test_a_properties_file_that_imports_the_module_but_has_no_given_test_does_not_clear_coverage(
    tmp_path: pathlib.Path,
) -> None:
    """A properties file that imports the source module and even calls the
    target function by name, but has no `@given`-decorated test at all, is
    an ordinary example-based test, not a property test -- `_covered` must
    not clear the finding on the strength of the import and name-mention
    alone."""
    _write(
        tmp_path,
        _FIXTURE_PROPERTIES_PATH,
        "import gitapex_check_fixture\n\n\ndef test_plain_example():\n    gitapex_check_fixture.check_value('a')\n",
    )
    violations, waived = _grade_added(tmp_path, _CHECK_VALUE_SOURCE, [6, 7])
    assert len(violations) == 1
    assert waived == []


# --- coverage completeness: main()'s own CLI paths --------------------------


def test_main_reads_the_diff_from_a_file_when_diff_flag_given(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--diff <path>` reads the unified diff from a file instead of
    standard input -- not exercised by any stdin-based test above."""
    diff_path = tmp_path / "the.diff"
    _write(tmp_path, _FIXTURE_PATH, "x = 1\n")
    diff_path.write_text(_whole_file_diff(_FIXTURE_PATH, "x = 1\n"), encoding="utf-8")
    assert gate.main(["--root", str(tmp_path), "--diff", str(diff_path)]) == 0
    assert "OK: 1 in-scope file(s) graded" in capsys.readouterr().out


def test_main_exits_2_on_a_non_utf8_diff_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    diff_path = tmp_path / "the.diff"
    diff_path.write_bytes(b"+# \xff\xfe\n")
    assert gate.main(["--root", str(tmp_path), "--diff", str(diff_path)]) == 2
    assert "diff cannot be read as UTF-8 text" in capsys.readouterr().err


def test_main_reports_ok_and_exit_0_on_a_clean_diff(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full `main()` -> `find_violations` -> clean-exit path, via stdin
    -- not exercised by any test above, which all call `find_violations`
    directly rather than going through `main()` for the success case."""
    diff = _whole_file_diff("docs/out_of_scope.py", "x = 1\n")
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(diff.encode("utf-8")))
    assert gate.main(["--root", str(tmp_path)]) == 0
    assert "OK: 0 in-scope file(s) graded, 0 inline waiver(s) honoured." in capsys.readouterr().out


def test_main_exits_2_when_find_violations_itself_raises_scanerror(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`main()`'s own `except ScanError` handling around the
    `find_violations` call -- the existing `ScanError`-contract tests above
    call `find_violations`/`parse_added_lines` directly, never through
    `main()` itself, so `main()`'s own catch-and-exit-2 wrapper around it
    was otherwise unexercised."""
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_UNPARSEABLE_HUNK_DIFF.encode("utf-8")))
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "unparseable hunk header" in capsys.readouterr().err


def test_main_reports_violations_and_waivers_with_exit_1(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full `main()` -> `find_violations` -> violation-found path, via
    stdin, with one real violation and one honoured waiver in the same run
    -- exercises both the waived-print loop and the violations-print loop
    plus the final `return 1`, none of which any test above reaches through
    `main()` itself."""
    waived_path = "hooks/gitapex_check_waived_fixture.py"
    _write(tmp_path, _FIXTURE_PATH, _CHECK_VALUE_SOURCE)
    _write(tmp_path, waived_path, _CHECK_VALUE_WAIVED_SOURCE)
    diff = _partial_diff(_FIXTURE_PATH, _CHECK_VALUE_SOURCE, [6, 7]) + _partial_diff(
        waived_path, _CHECK_VALUE_WAIVED_SOURCE, [6, 7]
    )
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(diff.encode("utf-8")))
    assert gate.main(["--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "regex-property-gap" in err
    assert "waived inline" in err
    assert "issue #1178" in err


# --- the real repository ------------------------------------------------


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    """Drift gate for an invariant this gate depends on, per
    tests/test_gitapex_gate_exception_handler_gaps.py's own precedent for
    the identical two flags on the identical kind of producer command --
    this gate correlates diff-derived line numbers with tree content the
    same way that one does, for the same two reasons.

    `--no-renames`: a file promoted into a graded directory otherwise
    arrives as a 100%-similarity rename with zero added lines and enters
    scope ungraded -- the same rename-shaped fail-open
    `gitapex_detect_changed_gate_scripts.py`'s own docstring records having
    had to close. `core.quotePath=false`: a non-ASCII path anywhere in the
    diff otherwise arrives C-quoted, which `_diff_target_path` refuses to
    resolve (exit 2) -- failing the job over a file that need not even be
    in scope."""
    assert_workflow_diff_carries_flags(
        "detection-logic-property-coverage-gate.yml", "--no-renames", "core.quotePath=false"
    )


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    """The third caller-side invariant this gate depends on, alongside the
    two flags above -- an invariant's own drift gate ships with the
    invariant, not after it.

    `ref: <head sha>` is what makes the working tree the diff's post-image:
    `find_violations` reads each in-scope file's post-image content
    straight off the working tree and grades it against `parse_added_lines`'
    own post-image line numbers, so the checked-out tree has to *be* that
    post-image. Dropping this pin silently mis-grades every file the base
    branch also touched -- there is no exit code and no message when that
    happens, so nothing else in this suite would notice. `fetch-depth: 0`
    is load-bearing *for* that pin, not decoration: the workflow's own
    `git merge-base` step needs `origin/main` reachable in the fetched
    history, which a shallow checkout does not guarantee.

    Both settings are read off this workflow's parsed `with:` mapping
    rather than matched against the whole file as text, because the shrunk
    pointer comment this same PR introduced above the step contains the
    literal substring `fetch-depth: '0'` and a text check passed off it
    alone. `conftest`'s own docstring carries that defeat case."""
    assert_workflow_checkout_pins_head_sha_with_full_history("detection-logic-property-coverage-gate.yml")


def test_the_workflow_has_no_paths_filter() -> None:
    """Drift gate for an invariant this change establishes, per CLAUDE.md
    section 3, mirroring `tests/test_gitapex_gate_exception_handler_gaps.py`'s
    own identical reasoning and defeat-case: a `paths:` filter under
    `pull_request:` is deliberately never added, following the same
    rationale `lint.yml`, `plugin-root-brace-notation-gate.yml` and
    `exception-handler-gap-gate.yml` each state for themselves. GitHub
    distinguishes a job that runs and reports `skipped` (harmless to a
    required check) from a workflow that never fires for a given PR at all
    (which leaves a required check `Pending` forever, with no in-repo fix).
    This gate is a candidate for later promotion to a required status
    check, so a `paths:` filter here would recreate that exact
    stuck-Pending failure mode for any PR that happens not to touch an
    in-scope file.

    `conftest.assert_workflow_has_no_trigger_path_filter`'s own docstring
    carries how the trigger keys are read and why `paths-ignore:` is
    rejected too.
    """
    assert_workflow_has_no_trigger_path_filter("detection-logic-property-coverage-gate.yml")


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    """Drift gate for an invariant this change establishes, per CLAUDE.md
    section 3, mirroring `exception-handler-gap-gate.yml`'s,
    `gitignore-pattern-coverage-gate.yml`'s and
    `skill-rename-lifecycle-gate.yml`'s own identical reasoning: `git
    merge-base` is resolved between `BASE_SHA` and `HEAD_SHA` rather than
    diffing against `base.sha` directly, so a change that landed on the
    base branch after this PR forked is never misattributed to this PR.

    `conftest.assert_workflow_feeds_merge_base_to`'s own docstring carries
    the defeat cases it closes, kept there rather than re-enumerated here
    so this comment cannot go stale the next time that list grows.
    `"diff"` is the producer command this gate depends on.
    """
    assert_workflow_feeds_merge_base_to("detection-logic-property-coverage-gate.yml", "diff")

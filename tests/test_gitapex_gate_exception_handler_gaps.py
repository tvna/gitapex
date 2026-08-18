"""Tests for the exception-handler gap gate
(.github/scripts/gitapex_gate_exception_handler_gaps.py).

Refs #682 (refs #665, #673, #674, #680). The gate exists because the same
defect has shipped into this repository's own gates five times: a decoded
read whose enclosing `try` names the wrong failure or no failure at all, and
a `.get()` on a `json.loads` result never checked to be an object.

The three regression fixtures below are reconstructions of real defective
commits still readable in this repository's history, in the same style
PR #674 used for its own `_PR_651_BODY_EXCERPT`. Issue #682's acceptance
criterion allows either "check out or reconstruct the defective state", and
reconstruction is what these are: each preserves the defect and every
structure the rules have to traverse to reach it, but drops surrounding
docstrings and adds the imports needed to parse standalone. They are
deliberately not called verbatim. The yield claim itself was re-measured
against the real file contents at each commit (`git show <sha>:<path>`),
which the pytest job's own shallow checkout cannot do:

* defect C -- `f91383c:.github/scripts/gitapex_gate_plugin_root_brace_notation.py`
* defect E -- `406d587:.github/scripts/gitapex_detect_changed_gate_scripts.py`
* defect F -- `0b4cedd:.github/scripts/gitapex_detect_changed_gate_scripts.py`

The defeat cases carry as much weight as the happy path. A gate that fired
on a write-mode `open()` would be reverted the first time someone wrote a
file; one that passed on a file it could not parse would be a permanent
green no-op; one that honoured a marker inside a string literal could be
silenced by this very docstring.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_exception_handler_gaps as gate
import pytest
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_SCRIPT = ".github/scripts/gitapex_gate_exception_handler_gaps.py"


# --- helpers ------------------------------------------------------------


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


def _grade(tmp_path: pathlib.Path, source: str, *, relative: str = ".github/scripts/gate_x.py") -> list[gate.Finding]:
    """Write `source` at `relative`, grade it as wholly added, return violations.

    The `graded == 1` assertion is load-bearing, not decoration. Every
    "must not fire" test below asserts `== []`, and without this a gate that
    read nothing at all -- a wrong scope rule, a wrong root -- would satisfy
    all of them at once.
    """
    _write(tmp_path, relative, source)
    violations, _waived, graded = gate.find_violations(_whole_file_diff(relative, source), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations


def _rules(findings: list[gate.Finding]) -> list[str]:
    return [finding.rule for finding in findings]


def _at(findings: list[gate.Finding]) -> list[tuple[str, int]]:
    return [(finding.rule, finding.line) for finding in findings]


# --- regression fixtures from the real defective commits ----------------

# Reconstructed from f91383c:.github/scripts/gitapex_gate_plugin_root_brace_notation.py:109-121.
# `path.read_text(...)` sits inside no `try` at all, so a non-UTF-8 agent
# definition produced an uncaught UnicodeDecodeError traceback.
_DEFECT_C = '''
import json
import pathlib


def offending_lines(path: pathlib.Path) -> list[str]:
    """Return the offending command strings (or frontmatter lines) in ``path``."""
    text = path.read_text(encoding="utf-8")
    if path.name == "hooks.json":
        candidates = commands_in_hook_manifest(json.loads(text))
    else:
        candidates = (line.strip() for line in frontmatter(text).split("\\n"))
    return [candidate for candidate in candidates if _UNBRACED_RE.search(candidate)]
'''

# Reconstructed from 406d587:.github/scripts/gitapex_detect_changed_gate_scripts.py:98-116.
# The UnicodeDecodeError *is* handled here -- what is missing is any check
# that the parsed JSON is an object, so `[]` reached `.get` and raised
# AttributeError. The `isinstance(gates, list)` two lines below validates a
# different name and must not be read as validating `data`.
_DEFECT_E = """
import json


def registered_gate_paths(repo_root=REPO_ROOT):
    path = repo_root / SSOT_RELATIVE_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ScopeError(f"{path}: gate registry cannot be read: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ScopeError(f"{path}: gate registry is not valid JSON: {error}") from error

    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ScopeError(f"{path}: gate registry has no usable 'gates' list")
"""

# Reconstructed from 0b4cedd:.github/scripts/gitapex_detect_changed_gate_scripts.py:293-307.
# The read was wrapped -- in a handler naming only OSError, so a non-UTF-8
# diff escaped as a traceback. This is the shape that has recurred most.
_DEFECT_F = """
def main(args):
    try:
        registered = registered_gate_paths(args.repo_root)
        exempt = frozenset()
        if args.unified_diff:
            try:
                diff_text = open(args.unified_diff, encoding="utf-8").read()
            except OSError as error:
                raise ScopeError(f"unified diff cannot be read: {error}") from error
            exempt = pin_only_workflow_paths(diff_text)
        selected = select(sys.stdin.read(), registered, exempt)
    except ScopeError as error:
        print(f"{error}", file=sys.stderr)
        return 2
    return 0
"""


def test_defect_c_uncaught_decode_on_an_unguarded_read_is_caught(tmp_path: pathlib.Path) -> None:
    """PR #651's own shipped defect, re-measured rather than assumed. The line
    is asserted too: a rule-only assertion would pass on any finding anywhere
    in the fixture, including one the real defect never had."""
    assert _at(_grade(tmp_path, _DEFECT_C)) == [("decode-gap", 8)]


def test_defect_e_get_on_an_unvalidated_json_result_is_caught(tmp_path: pathlib.Path) -> None:
    """PR #674 review round 1's defect. The read itself is correctly guarded
    here, so a rule keyed only on reads would have missed it."""
    assert _at(_grade(tmp_path, _DEFECT_E)) == [("json-shape-gap", 14)]


def test_defect_f_oserror_only_handler_around_a_decoded_read_is_caught(
    tmp_path: pathlib.Path,
) -> None:
    """The fixture keeps the real commit's *outer* `try/except ScopeError`, so
    this exercises the nested-try recursion the defect actually sat inside --
    a flattened paraphrase would trip the rule for an easier reason."""
    assert _at(_grade(tmp_path, _DEFECT_F)) == [("decode-gap", 8)]


def test_the_fixes_that_landed_for_c_e_and_f_pass(tmp_path: pathlib.Path) -> None:
    """The other half of the measurement: the detector must fail on the
    defective commit and pass on its repair, or it is grading something
    other than the defect."""
    fixed_c = _DEFECT_C.replace(
        '    text = path.read_text(encoding="utf-8")\n',
        "    try:\n"
        '        text = path.read_text(encoding="utf-8")\n'
        "    except (OSError, UnicodeDecodeError) as error:\n"
        "        raise ScanError(f'{path}: cannot be read as UTF-8 text: {error}') from error\n",
    )
    fixed_e = _DEFECT_E.replace(
        '    gates = data.get("gates")\n',
        "    if not isinstance(data, dict):\n"
        "        raise ScopeError(f'{path}: gate registry must be a JSON object')\n"
        '    gates = data.get("gates")\n',
    )
    fixed_f = _DEFECT_F.replace(
        "        except OSError as error:", "        except (OSError, UnicodeDecodeError) as error:"
    )
    assert _grade(tmp_path, fixed_c, relative=".github/scripts/gate_c.py") == []
    assert _grade(tmp_path, fixed_e, relative=".github/scripts/gate_e.py") == []
    assert _grade(tmp_path, fixed_f, relative=".github/scripts/gate_f.py") == []


# --- decode-gap: what must fire -----------------------------------------


def test_read_text_with_no_try_at_all_is_flagged(tmp_path: pathlib.Path) -> None:
    assert _rules(_grade(tmp_path, 'text = p.read_text(encoding="utf-8")\n')) == ["decode-gap"]


def test_read_text_guarded_only_by_oserror_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "try:\n    text = p.read_text()\nexcept OSError:\n    text = ''\n"
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_open_with_no_mode_is_a_read_and_is_flagged(tmp_path: pathlib.Path) -> None:
    assert _rules(_grade(tmp_path, 'fh = open("x", encoding="utf-8")\n')) == ["decode-gap"]


@pytest.mark.parametrize("mode", ["r+", "w+", "a+"])
def test_open_in_an_update_mode_is_flagged(tmp_path: pathlib.Path, mode: str) -> None:
    """`w+` and `a+` are the ones that reach the `+` branch at all -- `r+` is
    already satisfied by the `r` test, so it alone would leave it unpinned."""
    assert _rules(_grade(tmp_path, f'fh = open("x", "{mode}", encoding="utf-8")\n')) == ["decode-gap"]


def test_open_with_a_non_constant_mode_fails_closed(tmp_path: pathlib.Path) -> None:
    """A mode this gate cannot read statically is graded as a read: guessing
    "probably a write" would be the fail-open direction."""
    assert _rules(_grade(tmp_path, 'fh = open("x", mode)\n')) == ["decode-gap"]


def test_path_dot_open_is_flagged(tmp_path: pathlib.Path) -> None:
    assert _rules(_grade(tmp_path, 'fh = pathlib.Path("x").open(encoding="utf-8")\n')) == ["decode-gap"]


def test_a_read_inside_an_except_body_is_not_covered_by_that_same_try(
    tmp_path: pathlib.Path,
) -> None:
    """The "read it again to report a better error" fallback lives exactly
    here, and that statement's own handlers do not protect it."""
    source = "try:\n    pass\nexcept UnicodeDecodeError:\n    text = p.read_text()\n"
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_a_read_in_a_finally_clause_is_not_covered(tmp_path: pathlib.Path) -> None:
    source = "try:\n    pass\nexcept ValueError:\n    pass\nfinally:\n    text = p.read_text()\n"
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


# --- decode-gap: what must not fire -------------------------------------


@pytest.mark.parametrize(
    "handler",
    ["UnicodeDecodeError", "UnicodeError", "ValueError", "Exception", "BaseException"],
)
def test_a_handler_naming_the_error_or_an_ancestor_covers_the_read(tmp_path: pathlib.Path, handler: str) -> None:
    source = f"try:\n    text = p.read_text()\nexcept {handler}:\n    text = ''\n"
    assert _grade(tmp_path, source) == []


def test_a_bare_except_covers_the_read(tmp_path: pathlib.Path) -> None:
    source = "try:\n    text = p.read_text()\nexcept:\n    text = ''\n"
    assert _grade(tmp_path, source) == []


def test_a_tuple_handler_covers_the_read(tmp_path: pathlib.Path) -> None:
    source = "try:\n    text = p.read_text()\nexcept (OSError, UnicodeDecodeError):\n    text = ''\n"
    assert _grade(tmp_path, source) == []


def test_an_outer_try_covers_a_read_nested_below_it(tmp_path: pathlib.Path) -> None:
    source = (
        "try:\n"
        "    try:\n"
        "        text = p.read_text()\n"
        "    except OSError:\n"
        "        raise\n"
        "except UnicodeDecodeError:\n"
        "    text = ''\n"
    )
    assert _grade(tmp_path, source) == []


def test_write_mode_open_is_out_of_scope(tmp_path: pathlib.Path) -> None:
    """A write raises UnicodeEncodeError, a different failure this gate was
    never measured against -- flagging it would be noise on every script
    that writes a report."""
    assert _grade(tmp_path, 'fh = open("x", "w", encoding="utf-8")\n') == []


def test_append_mode_open_is_out_of_scope(tmp_path: pathlib.Path) -> None:
    assert _grade(tmp_path, 'fh = open("x", mode="a", encoding="utf-8")\n') == []


def test_binary_mode_open_is_out_of_scope(tmp_path: pathlib.Path) -> None:
    """Binary reads decode nothing, so there is no decode failure to handle."""
    assert _grade(tmp_path, 'fh = open("x", "rb")\n') == []


def test_read_bytes_is_out_of_scope(tmp_path: pathlib.Path) -> None:
    assert _grade(tmp_path, "raw = p.read_bytes()\n") == []


@pytest.mark.parametrize(
    "call",
    [
        "webbrowser.open(url)",
        "os.open(path, os.O_RDONLY)",
        "zipfile.ZipFile(z).open(name)",
        'zipfile.ZipFile(z).open("secret.txt")',
        'pathlib.Path(p).open("rb")',
        'pathlib.Path(p).open("w", encoding="utf-8")',
    ],
)
def test_an_attribute_named_open_that_decodes_nothing_is_not_flagged(tmp_path: pathlib.Path, call: str) -> None:
    """`.open` is not a file read just because of its name. Grading the
    attribute form on the name alone reported every one of these."""
    assert _grade(tmp_path, f"handle = {call}\n") == []


@pytest.mark.parametrize(
    "call",
    [
        "pathlib.Path(p).open()",
        'pathlib.Path(p).open("r")',
        'pathlib.Path(p).open(mode="r")',
        'pathlib.Path(p).open(encoding="utf-8")',
        'io.open(p, encoding="utf-8")',
    ],
)
def test_an_attribute_open_that_declares_a_text_read_is_flagged(tmp_path: pathlib.Path, call: str) -> None:
    assert _rules(_grade(tmp_path, f"handle = {call}\n")) == ["decode-gap"]


def test_a_function_defined_inside_a_try_body_is_not_protected_by_it(
    tmp_path: pathlib.Path,
) -> None:
    """The `try` runs the `def`, not the body. A helper whose only call site
    is elsewhere would otherwise inherit protection it never has."""
    source = "try:\n    def helper(p):\n        return p.read_text()\nexcept UnicodeDecodeError:\n    helper = None\n"
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


# --- json-shape-gap -----------------------------------------------------


def test_get_on_an_unvalidated_json_result_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "def f(body):\n    data = json.loads(body)\n    return data.get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_an_isinstance_check_on_the_same_name_clears_it(tmp_path: pathlib.Path) -> None:
    source = (
        "def f(body):\n"
        "    data = json.loads(body)\n"
        "    if not isinstance(data, dict):\n"
        "        raise ScanError('not an object')\n"
        "    return data.get('k')\n"
    )
    assert _grade(tmp_path, source) == []


def test_an_isinstance_check_on_a_different_name_does_not_clear_it(
    tmp_path: pathlib.Path,
) -> None:
    """Defect E's exact escape: the function did call isinstance(), on the
    value it had already pulled out rather than on the parse result."""
    source = (
        "def f(body):\n"
        "    data = json.loads(body)\n"
        "    gates = data.get('gates')\n"
        "    if not isinstance(gates, list):\n"
        "        raise ScopeError('no gates')\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_a_chained_get_straight_off_json_loads_is_flagged(tmp_path: pathlib.Path) -> None:
    """No variable to taint, so no isinstance() could ever guard it."""
    source = "def f(body):\n    return json.loads(body).get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_a_chained_get_straight_off_json_load_is_flagged(tmp_path: pathlib.Path) -> None:
    source = "def f(fh):\n    return json.load(fh).get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_a_walrus_bound_json_result_is_tainted(tmp_path: pathlib.Path) -> None:
    source = "def f(body):\n    if (data := json.loads(body)):\n        return data.get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_get_on_an_unrelated_value_is_not_flagged(tmp_path: pathlib.Path) -> None:
    source = "def f(mapping):\n    return mapping.get('k')\n"
    assert _grade(tmp_path, source) == []


def test_validation_in_one_function_does_not_silence_another(tmp_path: pathlib.Path) -> None:
    """Taint is per-scope. Sharing it would let the same variable name,
    validated anywhere, silence every other function -- a fail-open in a
    gate whose whole subject is fail-open."""
    source = (
        "def safe(body):\n"
        "    data = json.loads(body)\n"
        "    if not isinstance(data, dict):\n"
        "        raise ScanError('x')\n"
        "    return data.get('k')\n"
        "\n"
        "def unsafe(body):\n"
        "    data = json.loads(body)\n"
        "    return data.get('k')\n"
    )
    findings = _grade(tmp_path, source)
    assert _rules(findings) == ["json-shape-gap"]
    assert findings[0].line == 9


def test_module_scope_is_graded_too(tmp_path: pathlib.Path) -> None:
    source = "data = json.loads(RAW)\nvalue = data.get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_an_isinstance_check_after_the_access_does_not_clear_it(
    tmp_path: pathlib.Path,
) -> None:
    """A guard that runs after the access it is meant to guard protects
    nothing; a flow-insensitive "checked somewhere" rule would pass this."""
    source = (
        "def f(body):\n"
        "    data = json.loads(body)\n"
        "    value = data.get('k')\n"
        "    if not isinstance(data, dict):\n"
        "        raise ScanError('x')\n"
        "    return value\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_a_nested_function_is_its_own_scope(tmp_path: pathlib.Path) -> None:
    """Stated boundary, pinned so a future change to it is deliberate: a
    closure reading the enclosing function's JSON value is not graded."""
    source = (
        "def outer(body):\n"
        "    data = json.loads(body)\n"
        "    def inner():\n"
        "        return data.get('k')\n"
        "    return inner\n"
    )
    assert _grade(tmp_path, source) == []


# --- diff scoping -------------------------------------------------------


def test_a_pre_existing_gap_on_an_untouched_line_is_not_this_diffs_failure(
    tmp_path: pathlib.Path,
) -> None:
    source = "import os\ntext = p.read_text()\nvalue = 1\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", source, [3]), tmp_path
    )
    assert violations == []


def test_the_same_gap_is_flagged_once_its_own_line_is_added(tmp_path: pathlib.Path) -> None:
    source = "import os\ntext = p.read_text()\nvalue = 1\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", source, [2]), tmp_path
    )
    assert _rules(violations) == ["decode-gap"]


def test_touching_any_line_of_a_multi_line_call_brings_it_into_scope(
    tmp_path: pathlib.Path,
) -> None:
    """A call reformatted across several lines is graded wherever it was
    touched, not only at the line the AST calls its start."""
    source = 'text = p.read_text(\n    encoding="utf-8",\n)\n'
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", source, [2]), tmp_path
    )
    assert _rules(violations) == ["decode-gap"]


def test_a_deleted_file_adds_nothing_to_grade(tmp_path: pathlib.Path) -> None:
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ /dev/null\n"
        "@@ -1,1 +0,0 @@\n"
        "-text = p.read_text()\n"
    )
    assert gate.find_violations(diff, tmp_path) == ([], [], 0)


def test_a_deleted_files_own_removal_lines_still_bound_in_hunk() -> None:
    """CodeRabbit review finding on this PR. `path` is None for the whole
    of a deleted file's hunk (`+++ /dev/null` maps to None), and the old
    code's `if path is None: continue` skipped the counter decrements and
    the `in_hunk` exhaustion check for every line of it -- not just the
    `added` recording. `old_remaining`/`new_remaining` stayed frozen at
    their post-header values and `in_hunk` stayed True indefinitely, so a
    patch with no `diff --git ` header between a deleted file and the next
    one left that next file's own real `--- `/`+++ ` headers unrecognised.

    Verified live against the pre-fix code: this exact diff returned `{}`
    -- the second file's own real added line dropped entirely, with no
    trace anywhere (not even misattributed to the wrong file, the way gap
    2's own original shape was). The counters and the exhaustion check now
    run regardless of `path`; only recording into `added` is still guarded
    on it, so a deleted file's own declared removal count correctly bounds
    its hunk and the next file is read normally afterward."""
    diff = (
        "--- a/hooks/gitapex_check_deleted.py\n"
        "+++ /dev/null\n"
        "@@ -1,3 +0,0 @@\n"
        "-line1\n"
        "-line2\n"
        "-line3\n"
        "--- a/hooks/gitapex_check_next.py\n"
        "+++ b/hooks/gitapex_check_next.py\n"
        "@@ -1,1 +1,2 @@\n"
        " def g():\n"
        "+    pass\n"
    )
    assert gate.parse_added_lines(diff) == {"hooks/gitapex_check_next.py": {2}}


def test_an_added_line_whose_content_starts_with_two_plusses_is_not_a_header(
    tmp_path: pathlib.Path,
) -> None:
    """Inside a hunk every line carries a prefix, so content beginning `++ `
    is emitted as `+++ ...` -- identical, prefix-first, to the post-image
    header. Reading it as a header rebinds the path to nonsense and silently
    drops the rest of the hunk, a fail-open in this gate's own family."""
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -1,0 +1,3 @@\n"
        '+DOC = """\n'
        "+++ a list marker, not a diff header\n"
        "+text = p.read_text()\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/gate_x.py": {1, 2, 3}}


def test_a_removed_line_whose_content_starts_with_two_dashes_is_not_a_header(
    tmp_path: pathlib.Path,
) -> None:
    """The mirror case: removed content beginning `-- ` is emitted as
    `--- ...`, and must not arm the post-image-header state machine.

    `@@ -1,1 +1,1 @@`, not `-1,2`: the body has exactly one `-`-prefixed
    line (consumes the pre-image side only) and one `+`-prefixed line
    (consumes the post-image side only), so the accurate pre-image count
    is 1 -- an inflated pre-image count here would leave `old_remaining`
    permanently above zero and incorrectly trip issue #1193's own
    declared-vs-actual validation."""
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a signature dash line\n"
        "+text = p.read_text()\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/gate_x.py": {1}}


def test_both_in_hunk_header_lookalikes_in_one_hunk_are_content(
    tmp_path: pathlib.Path,
) -> None:
    """The killing case for the hunk-state machine: a removed `-- ` line arms
    nothing, and the `++ ` line after it is content. Testing either half alone
    left both guards passing individually while jointly broken.

    `@@ -1,1 +1,2 @@`, not `-1,2`: the body has exactly one `-`-prefixed
    line (consumes the pre-image side only) and two `+`-prefixed lines
    (each consumes the post-image side only), so the accurate pre-image
    count is 1 -- an inflated pre-image count here would leave
    `old_remaining` permanently above zero and incorrectly trip issue
    #1193's own declared-vs-actual validation."""
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -1,1 +1,2 @@\n"
        "--- an added list marker line\n"
        "++ a list marker, not a diff header\n"
        "+text = p.read_text()\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/gate_x.py": {1, 2}}


# --- parse_added_lines: over-declared hunk length (issue #1193) ------------


def test_an_over_declared_hunk_length_before_a_new_hunk_header_raises_scanerror() -> None:
    """Issue #1193, ported from this file's own architectural mirror
    `gitapex_gate_detection_logic_property_coverage.py`. The dual-counter
    bound (issue #1184) never checks either declared count against how many
    pre-/post-image lines the hunk body actually has. `@@ -0,0 +1,5 @@`
    declares a pure-addition hunk (0 pre-image lines, matched by its body:
    no context, no removal) claiming 5 post-image lines; only 2 real added
    lines follow before the next file's own `--- `/`+++ ` headers begin.
    With no `diff --git ` separator between the two files, `new_remaining`
    stays above zero once the real body is exhausted, so `in_hunk` stays
    True straight through those headers, reopening the exact misattribution
    the dual-counter bound closes for the missing-separator case. Must now
    raise instead, caught here at the second file's own `@@` line -- the
    next unambiguous boundary -- before any of its real content is
    consumed. `new_remaining` is 2 at that point: 5 declared, minus the 2
    real added lines already consumed."""
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
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+x = 1\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/gate_x.py": {1}}


def test_a_post_image_path_without_the_b_prefix_fails_closed() -> None:
    """--no-prefix output and a git-quoted path both land here. Guessing at
    either silently drops a file from grading."""
    diff = "diff --git a/x b/x\n--- a/x\n+++ .github/scripts/gate_x.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="not a plain b/-prefixed path"):
        gate.parse_added_lines(diff)


def test_a_post_image_header_with_no_source_header_before_it_raises_scanerror() -> None:
    """Fail-closed regression (issue #1184, gap 1). `parse_added_lines` only
    bound the current path from a `+++ ` header that a `--- ` header
    preceded; reaching one with no preceding `--- ` fell through both
    branches silently, leaving `path` at None -- so every added line in
    every hunk that follows was dropped and the run reported `OK: 0
    in-scope file(s) graded`, exit 0, instead of raising. Real `git diff`
    output always emits `--- ` before `+++ `, so no wired invocation
    reaches this; `--diff <file>` accepts a patch from anywhere, and a
    fail-closed gate does not get to assume its input came from the
    wiring."""
    diff = (
        "diff --git a/hooks/gitapex_check_example.py b/hooks/gitapex_check_example.py\n"
        "+++ b/hooks/gitapex_check_example.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+try:\n"
        "+    pass\n"
    )
    with pytest.raises(gate.ScanError, match="no `--- ` source header before it"):
        gate.parse_added_lines(diff)


def test_a_second_file_with_no_diff_git_header_between_files_is_not_misattributed() -> None:
    """Issue #1184, gap 2. `in_hunk` used to be reset only by a `diff --git `
    line, never by a hunk's own declared post-image length running out. A
    patch with no `diff --git ` header between two files (real `git diff`
    output always has one; `--diff <file>` accepts a patch from anywhere)
    left `in_hunk` True straight through the second file's own `--- `/`+++ `
    lines: `--- ` read as a harmless no-op removal, but `+++ ` -- never
    recognised as a header, since `in_hunk` blocked that check -- read as
    *content* (its own leading `+`) and was added to the *first* file's
    `path` at a stale `lineno`. Because that `+++ ` line was never
    recognised as a header, `path` never advanced to the second file
    either, so the second file's own real added lines misattributed to the
    first file too.

    Verified live against the pre-fix gate: this exact diff returned
    `{'hooks/gitapex_check_file1.py': {2, 3, 4}}` -- file2's own line
    silently missing, and a bogus line 4 (the misread `+++ ` header)
    attributed to file1 instead. Both files must now be graded separately,
    each at its own correct line numbers, with nothing bogus added.

    `@@ -1,1 +1,3 @@`, not `-1,2`: the hunk's own body has one context line
    (old+new) and two additions (new only), so the accurate pre-image count
    is 1 -- an inflated pre-image count here would leave `old_remaining`
    permanently above zero (nothing in this body ever decrements it to 0)
    and reopen this exact gap under the fixed dual-counter accounting,
    despite being an inaccuracy `git diff` itself never produces."""
    diff = (
        "--- a/hooks/gitapex_check_file1.py\n"
        "+++ b/hooks/gitapex_check_file1.py\n"
        "@@ -1,1 +1,3 @@\n"
        " def f():\n"
        "+    try:\n"
        "+        pass\n"
        "--- a/hooks/gitapex_check_file2.py\n"
        "+++ b/hooks/gitapex_check_file2.py\n"
        "@@ -1,1 +1,2 @@\n"
        " def g():\n"
        "+    pass\n"
    )
    assert gate.parse_added_lines(diff) == {
        "hooks/gitapex_check_file1.py": {2, 3},
        "hooks/gitapex_check_file2.py": {2},
    }


def test_a_zero_post_image_hunk_still_protects_its_own_removal_lines() -> None:
    """Regression on the first fix for issue #1184's own gap 2 (post-image
    count alone), found during this PR's own adversarial review. `git diff
    -U0` -- this gate's real wired invocation -- emits a pure-deletion hunk
    as `@@ -a,b +c,0 @@`: zero post-image lines. Bounding `in_hunk` by the
    post-image count alone reads `remaining` as already exhausted on the
    `@@` line itself, before the hunk's own `b` removal lines are consumed,
    so the very next line -- itself this hunk's own removal content -- is
    read as a real header instead.

    Verified live against the first (post-image-count-only) fix: this exact
    diff returned `{'hooks/gitapex_check_payload.py': {1}}` -- the real
    exception-handler gap this diff's own added line represents silently
    vanished from `gitapex_check_target.py`, reattributed to a same-shaped
    but unrelated file entirely, exactly the "silent pass on a file this
    gate cannot grade" class issue #682 exists to catch. Tracking the
    pre-image count too (a removal decrements it) protects this hunk's own
    removal line via that side even though the post-image side is already
    at zero, so the disguised `+++ ` line below is now correctly read as
    content of that still-open hunk rather than a header -- which leaves it
    reached with no real `--- ` predecessor once the hunk genuinely does
    end, so `parse_added_lines` raises `ScanError` (fail-closed) instead of
    silently misattributing anything. This diff has no real added line to
    keep at all -- it is a pure-deletion hunk -- so the fix's own visible
    effect here is the raise, not a correctly-kept line."""
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
    """The realistic shape behind the regression above, with no adversarial
    disguise: `git diff -U0` -- this gate's own real wired invocation --
    emits a pure-deletion hunk exactly as `@@ -a,b +c,0 @@` whenever a diff
    removes lines with nothing added in their place, which is ordinary,
    everyday output, not a contrived input. The deleted file contributes no
    added lines (a pure removal has none to grade), and the next file's own
    real headers -- reached via a normal `diff --git ` separator, matching
    every real multi-file `git diff` -- must still be read correctly and
    graded on its own merits."""
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


def test_the_minus_header_line_is_not_counted_as_a_removal(tmp_path: pathlib.Path) -> None:
    """Regression guard on the parser itself: `--- a/<path>` arrives while
    the previous file's path could still be current, and must not be read as
    that file's content."""
    source = "text = p.read_text()\n"
    _write(tmp_path, ".github/scripts/gate_a.py", source)
    _write(tmp_path, ".github/scripts/gate_b.py", source)
    diff = _whole_file_diff(".github/scripts/gate_a.py", source) + _whole_file_diff(".github/scripts/gate_b.py", source)
    added = gate.parse_added_lines(diff)
    assert sorted(added) == [".github/scripts/gate_a.py", ".github/scripts/gate_b.py"]
    assert added[".github/scripts/gate_a.py"] == {1, 2}


def test_context_lines_advance_the_post_image_line_counter(tmp_path: pathlib.Path) -> None:
    """Hand-built hunks in this file carry no context; real `git diff` output
    with any context depth must still land on the right line."""
    source = "import os\nimport sys\ntext = p.read_text()\nvalue = 1\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -1,3 +1,4 @@\n"
        " import os\n"
        " import sys\n"
        "+text = p.read_text()\n"
        " value = 1\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/gate_x.py": {3}}
    violations, _waived, _graded = gate.find_violations(diff, tmp_path)
    assert [(finding.rule, finding.line) for finding in violations] == [("decode-gap", 3)]


def test_against_real_git_diff_output(tmp_path: pathlib.Path) -> None:
    """Live proof, not a hand-authored approximation of one: a real git
    repository, a real edit, and `git diff -U0` exactly as the workflow
    invokes it."""
    run = subprocess.run
    run(["git", "init", "-q", str(tmp_path)], check=True)
    run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    relative = ".github/scripts/gate_x.py"
    clean = (
        "import pathlib\n"
        "\n"
        "\n"
        "def read(path: pathlib.Path) -> str:\n"
        "    try:\n"
        '        return path.read_text(encoding="utf-8")\n'
        "    except (OSError, UnicodeDecodeError) as error:\n"
        "        raise RuntimeError(error) from error\n"
    )
    _write(tmp_path, relative, clean)
    run(["git", "-C", str(tmp_path), "add", "--", relative], check=True)
    run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)

    (tmp_path / relative).write_text(
        clean + "\n\ndef also(path: pathlib.Path) -> str:\n    return path.read_text()\n",
        encoding="utf-8",
    )
    diff = run(
        ["git", "-C", str(tmp_path), "diff", "-U0", "--", "*.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    violations, _waived, graded = gate.find_violations(diff, tmp_path)
    assert graded == 1
    assert [(finding.rule, finding.line) for finding in violations] == [("decode-gap", 12)]


# --- the edits that create a gap without touching the offending line ----


def test_narrowing_an_enclosing_handler_is_this_diffs_finding(tmp_path: pathlib.Path) -> None:
    """Issue #682's defect F is created by editing the `except` clause, not the
    read. Anchoring only on the read's own lines let exactly that edit through
    -- a fail-open in the gate, in the class the gate exists to catch."""
    source = (
        "def read(path):\n"
        "    try:\n"
        "        return path.read_text(encoding='utf-8')\n"
        "    except OSError:\n"
        "        return ''\n"
    )
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", source, [4]), tmp_path
    )
    assert _at(violations) == [("decode-gap", 3)]


def test_replacing_a_json_guard_is_this_diffs_finding(tmp_path: pathlib.Path) -> None:
    """The mirror case: swapping `isinstance(data, dict)` for a different check
    leaves the `.get()` untouched. Anything edited between the parse and the
    access re-grades the finding, because that is where a guard has to live."""
    source = (
        "def load(raw):\n"
        "    data = json.loads(raw)\n"
        "    if not data:\n"
        "        raise ValueError('empty')\n"
        "    return data.get('k')\n"
    )
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", source, [3]), tmp_path
    )
    assert _at(violations) == [("json-shape-gap", 5)]


def test_an_untouched_function_elsewhere_in_the_file_stays_out_of_scope(
    tmp_path: pathlib.Path,
) -> None:
    """The widening above must not become "grade the whole file": a gap in a
    function this diff never touched is still another PR's to own."""
    source = "def untouched(path):\n    return path.read_text()\n\n\ndef touched():\n    return 1\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, _waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", source, [6]), tmp_path
    )
    assert violations == []


# --- deferred execution: a try does not protect what runs later ---------


def test_a_generator_expression_inside_a_try_is_a_stated_miss(
    tmp_path: pathlib.Path,
) -> None:
    """A genexp assigned inside a `try` and consumed outside it really does
    escape that handler -- proved at runtime -- and this gate does not report
    it. Three rules were tried: never protected (a false positive on
    `sorted(genexp)`, which IS caught and is the only such shape in this
    repository), protected only when passed straight into a call (four
    reproduced false positives on keyword, starred, `for`-clause and
    assign-then-consume forms), and protected always. The third is the one
    that is never wrong in the reporting direction, and its miss is named
    here rather than left to be rediscovered."""
    source = (
        "def read_all(paths):\n"
        "    try:\n"
        "        texts = (pathlib.Path(p).read_text(encoding='utf-8') for p in paths)\n"
        "    except ValueError:\n"
        "        return []\n"
        "    return list(texts)\n"
    )
    assert _grade(tmp_path, source) == []


@pytest.mark.parametrize("consumer", ["sorted", "list", "any", "'-'.join"])
def test_a_generator_expression_consumed_inside_the_try_is_protected(tmp_path: pathlib.Path, consumer: str) -> None:
    """The other side, and the one that occurs for real: verified at runtime,
    `sorted(p.read_text() for p in ps)` inside a `try` IS caught by it. This
    also keeps the gate self-consistent -- `list(x for x in y)` and
    `[x for x in y]` are the same program and must get the same verdict."""
    source = (
        "def read_all(paths):\n"
        "    try:\n"
        f"        return {consumer}(pathlib.Path(p).read_text(encoding='utf-8') for p in paths)\n"
        "    except ValueError:\n"
        "        return []\n"
    )
    assert _grade(tmp_path, source) == []


def test_a_lambda_inside_a_try_is_not_protected_by_it(tmp_path: pathlib.Path) -> None:
    source = "try:\n    read = lambda: p.read_text()\nexcept ValueError:\n    read = None\n"
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_a_decorator_evaluated_inside_a_try_keeps_its_protection(
    tmp_path: pathlib.Path,
) -> None:
    """A decorator expression and an argument default really do run inside the
    `try`, unlike the function body they belong to."""
    source = (
        "try:\n"
        "    @register(p.read_text())\n"
        "    def handler(cache=p.read_text()):\n"
        "        return cache\n"
        "except ValueError:\n"
        "    handler = None\n"
    )
    assert _grade(tmp_path, source) == []


def test_except_star_handlers_are_read(tmp_path: pathlib.Path) -> None:
    """`ast.TryStar` is not a subclass of `ast.Try`, so an exception group
    handler was invisible and its read reported as a false positive."""
    source = "try:\n    text = p.read_text()\nexcept* UnicodeDecodeError:\n    text = ''\n"
    assert _grade(tmp_path, source) == []


def test_an_attribute_handler_name_is_matched_by_its_final_component(
    tmp_path: pathlib.Path,
) -> None:
    source = "try:\n    text = p.read_text()\nexcept builtins.ValueError:\n    text = ''\n"
    assert _grade(tmp_path, source) == []


# --- json taint: module scope, shadowing, and the type actually checked --


def test_a_module_level_json_value_read_inside_a_function_is_a_stated_miss(
    tmp_path: pathlib.Path,
) -> None:
    """Taint does not cross a scope boundary, so `CONFIG = json.loads(...)`
    read through `CONFIG.get(...)` in a function is not reported. Inheriting
    it was implemented and reverted: it required parameter, local-rebinding
    and import shadowing to avoid false positives, each of which required
    statement order, and order-sensitivity made the verdict depend on which
    branch of a `try/except` was written first. Pinned so the miss is a
    decision, not an accident."""
    source = "CONFIG = json.loads(RAW)\n\n\ndef names():\n    return CONFIG.get('names', [])\n"
    assert _grade(tmp_path, source) == []


def test_a_name_both_parsed_and_rebound_in_one_scope_is_not_tainted(
    tmp_path: pathlib.Path,
) -> None:
    """Order-blind and conservative on purpose. `try: data = json.loads(...)
    except: data = {}` is the ordinary fallback, and a rule that compared line
    numbers reported it or not depending on branch order."""
    source = (
        "def load(raw):\n"
        "    try:\n"
        "        data = json.loads(raw)\n"
        "    except ValueError:\n"
        "        data = {}\n"
        "    return data.get('k')\n"
    )
    assert _grade(tmp_path, source) == []


def test_an_empty_isinstance_tuple_validates_nothing(tmp_path: pathlib.Path) -> None:
    """`isinstance(x, ())` is legal and always False, so it can never be the
    guard. Without an explicit check, an all-members loop over an empty tuple
    reports vacuous success -- the fail-open shape of "for all" done wrong."""
    source = (
        "def load(raw):\n"
        "    data = json.loads(raw)\n"
        "    if not isinstance(data, ()):\n"
        "        raise ValueError('x')\n"
        "    return data.get('key')\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_an_isinstance_against_a_non_mapping_type_does_not_clear_it(
    tmp_path: pathlib.Path,
) -> None:
    """The real double-encoded-JSON idiom. `isinstance(data, str)` says nothing
    about whether the *reparsed* value is an object, so the `.get()` below it
    can still raise -- accepting any type here was a fail-open."""
    source = (
        "def load(raw):\n"
        "    data = json.loads(raw)\n"
        "    if isinstance(data, str):\n"
        "        data = json.loads(data)\n"
        "    return data.get('key')\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def _guarded_by(mapping_type: str) -> str:
    return (
        "def load(raw):\n"
        "    data = json.loads(raw)\n"
        f"    if not isinstance(data, {mapping_type}):\n"
        "        raise ValueError('x')\n"
        "    return data.get('key')\n"
    )


@pytest.mark.parametrize("mapping_type", ["dict", "Mapping", "abc.MutableMapping", "(dict, Mapping)"])
def test_an_isinstance_naming_a_mapping_type_clears_it(tmp_path: pathlib.Path, mapping_type: str) -> None:
    assert _grade(tmp_path, _guarded_by(mapping_type)) == []


@pytest.mark.parametrize("mapping_type", ["(dict, list)", "(str, dict)"])
def test_an_isinstance_tuple_with_a_non_mapping_member_does_not_clear_it(
    tmp_path: pathlib.Path, mapping_type: str
) -> None:
    """Every member has to be a mapping type, not any: a list satisfies
    `isinstance(data, (dict, list))` and the `.get()` after it still raises.
    Confirmed at runtime with `json.loads('["a"]')`."""
    assert _rules(_grade(tmp_path, _guarded_by(mapping_type))) == ["json-shape-gap"]


def test_a_walrus_inside_the_isinstance_call_clears_it(tmp_path: pathlib.Path) -> None:
    source = (
        "def load(raw):\n"
        "    if not isinstance(data := json.loads(raw), dict):\n"
        "        raise ValueError('x')\n"
        "    return data.get('key')\n"
    )
    assert _grade(tmp_path, source) == []


def test_tuple_unpacking_taints_only_the_json_element(tmp_path: pathlib.Path) -> None:
    source = "def load(raw):\n    data, extra = json.loads(raw), {}\n    return data.get('k'), extra.get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_a_parser_from_another_module_is_not_a_json_parse(tmp_path: pathlib.Path) -> None:
    source = "def load(blob):\n    data = yaml.loads(blob)\n    return data.get('k')\n"
    assert _grade(tmp_path, source) == []


def test_an_async_function_is_its_own_scope_and_is_graded(tmp_path: pathlib.Path) -> None:
    source = "async def load(raw):\n    data = json.loads(raw)\n    return data.get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_the_earliest_isinstance_is_the_one_that_counts(tmp_path: pathlib.Path) -> None:
    """A guard before the access protects it even when a second check follows."""
    source = (
        "def load(raw):\n"
        "    data = json.loads(raw)\n"
        "    if not isinstance(data, dict):\n"
        "        raise ValueError('x')\n"
        "    value = data.get('k')\n"
        "    assert isinstance(data, dict)\n"
        "    return value\n"
    )
    assert _grade(tmp_path, source) == []


# --- handlers the gate must read, or it reports correct code ------------


@pytest.mark.parametrize(
    "clause",
    [
        "except (json.JSONDecodeError, AttributeError):",
        "except AttributeError:",
        "except Exception:",
        "except:",
    ],
)
def test_a_handler_catching_attributeerror_covers_a_json_access(tmp_path: pathlib.Path, clause: str) -> None:
    """The `.get()` rule was blind to handlers entirely while the read rule
    honoured them, so a `.get()` wrapped in exactly the fix this gate's own
    failure message prescribes was still reported. Verified at runtime for
    every payload the message names."""
    source = (
        "def load(raw):\n"
        "    try:\n"
        "        data = json.loads(raw)\n"
        "        return data.get('gates', [])\n"
        f"    {clause}\n"
        "        raise GateError('bad registry')\n"
    )
    assert _grade(tmp_path, source) == []


def test_a_handler_that_does_not_catch_attributeerror_leaves_it_reported(
    tmp_path: pathlib.Path,
) -> None:
    source = (
        "def load(raw):\n"
        "    try:\n"
        "        data = json.loads(raw)\n"
        "        return data.get('gates', [])\n"
        "    except OSError:\n"
        "        raise GateError('bad registry')\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


@pytest.mark.parametrize("errors", ["replace", "ignore", "surrogateescape", "backslashreplace"])
def test_a_read_with_a_substituting_errors_policy_cannot_raise(tmp_path: pathlib.Path, errors: str) -> None:
    """Each of these four was run against a non-UTF-8 file and each
    substituted rather than raised, so demanding a handler reports code that
    cannot fail. The list is exactly those four -- see the sibling test for
    the two that look like they belong and do not."""
    assert _grade(tmp_path, f'text = p.read_text(encoding="utf-8", errors="{errors}")\n') == []


@pytest.mark.parametrize(
    "call",
    [
        'open(p, "r", -1, "utf-8", "replace")',
        'p.open("r", -1, "utf-8", "replace")',
        'p.read_text("utf-8", "replace")',
    ],
)
def test_a_positionally_passed_errors_policy_is_a_stated_over_report(tmp_path: pathlib.Path, call: str) -> None:
    """None of these can raise -- all three were run against a non-UTF-8 file
    and all three substituted. The gate reports them anyway, because the
    positional index differs per callee (4 for the builtin `open`, 3 for
    `Path.open`, 1 for `read_text`) and reading one index for all three got
    two of them wrong. Guessing an index into a signature this gate cannot
    see is the same class of guess as the name resolution this file has now
    reverted three times."""
    assert _rules(_grade(tmp_path, f"fh = {call}\n")) == ["decode-gap"]


@pytest.mark.parametrize(
    "errors",
    ["None", "variable", '"strict"', "0", '"xmlcharrefreplace"', '"namereplace"', '"REPLACE"'],
)
def test_an_errors_value_that_is_not_a_substituting_policy_still_reports(tmp_path: pathlib.Path, errors: str) -> None:
    """An allowlist, not "anything but strict", and one determined by running
    each handler rather than reading the codecs table.

    `xmlcharrefreplace` and `namereplace` are the sharp ones: they look like
    substituting policies, they are listed alongside the others in the docs,
    and on a *decode* they raise `TypeError: don't know how to handle
    UnicodeDecodeError in error callback`. Listing them made a read carrying
    one grade clean while exiting 1 with an uncaught traceback -- this gate's
    own subject, shipped by the fix for a false positive. `"REPLACE"` raises
    `LookupError`: `codecs.lookup_error` is case-sensitive. `None` is
    documented as equivalent to strict."""
    source = f'text = p.read_text(encoding="utf-8", errors={errors})\n'
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_a_nested_walrus_still_taints_the_parsed_value(tmp_path: pathlib.Path) -> None:
    """`(a := (b := json.loads(raw))).get(k)` -- the outer target binds a
    walrus, not the parse, and unwrapping only one level dropped it."""
    source = "def f(raw):\n    return (a := (b := json.loads(raw))).get('k')\n"
    assert _rules(_grade(tmp_path, source)) == ["json-shape-gap"]


def test_an_explicit_strict_errors_policy_still_raises_and_is_reported(
    tmp_path: pathlib.Path,
) -> None:
    assert _rules(_grade(tmp_path, 'text = p.read_text(encoding="utf-8", errors="strict")\n')) == ["decode-gap"]


def test_contextlib_suppress_is_a_stated_over_report(tmp_path: pathlib.Path) -> None:
    """`suppress` really is a handler, and this gate really does report the
    read inside one. Reading it was implemented and reverted: matching the
    label `suppress` on any receiver silenced a same-named method on an
    unrelated object, while missing `suppress` behind an import alias, a
    starred argument, or a tuple constant. One syntactic match, wrong in both
    directions, for a construct that occurs nowhere in the graded
    directories. Pinned as an over-report so it is not rediscovered as a
    surprise, and so the inline waiver stays its documented answer."""
    source = (
        "import contextlib\n"
        "def read(p):\n"
        "    text = ''\n"
        "    with contextlib.suppress(UnicodeDecodeError):\n"
        "        text = p.read_text(encoding='utf-8')\n"
        "    return text\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_a_handler_named_by_a_tuple_constant_is_a_stated_over_report(
    tmp_path: pathlib.Path,
) -> None:
    """`except _READ_ERRORS:` is reported even when the constant does cover.
    Expanding it was implemented and reverted: the table was applied by name
    with no scope awareness, so a module-level rebinding, a local shadow, a
    parameter default or a `for` target of the same name silenced the rule --
    four fail-opens on exactly issue #682's own defect F shape, bought with a
    false positive that occurs nowhere in the graded directories."""
    source = (
        "_READ_ERRORS = (OSError, ValueError)\n"
        "def read(p):\n"
        "    try:\n"
        "        return p.read_text(encoding='utf-8')\n"
        "    except _READ_ERRORS as error:\n"
        "        raise GateError(error) from error\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_an_unresolvable_handler_name_does_not_grant_coverage(
    tmp_path: pathlib.Path,
) -> None:
    """Assuming an unrecognised handler covers was tried and reverted the same
    hour: it silenced issue #682's own defect F, whose outer handler is a
    project exception class (`except ScopeError:`) wrapping an inner
    `except OSError:`. Only a resolvable tuple constant is expanded."""
    source = (
        "def read(p):\n"
        "    try:\n"
        "        return p.read_text(encoding='utf-8')\n"
        "    except ScopeError as error:\n"
        "        raise\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


@pytest.mark.parametrize(
    "spelling",
    [
        "return json.loads(raw).get('k')",
        "data = json.loads(raw)\n    return data.get('k')",
        "return (data := json.loads(raw)).get('k')",
    ],
)
def test_every_spelling_of_one_program_gets_one_verdict(tmp_path: pathlib.Path, spelling: str) -> None:
    """The walrus-receiver form was the only one of the three that graded
    clean, which falsified the gate's own claim to be spelling-independent."""
    assert _rules(_grade(tmp_path, f"def f(raw):\n    {spelling}\n")) == ["json-shape-gap"]


# --- the named misses, pinned so none can vanish unnoticed --------------


def test_a_positive_branch_isinstance_is_a_stated_miss(tmp_path: pathlib.Path) -> None:
    """An `isinstance` anywhere in the scope before the access clears it, not
    only one in a branch that actually guards it. Deciding that would need
    branch analysis, which this gate deliberately does not do."""
    source = (
        "def load(raw):\n"
        "    data = json.loads(raw)\n"
        "    if isinstance(data, dict):\n"
        "        pass\n"
        "    return data.get('k')\n"
    )
    assert _grade(tmp_path, source) == []


def test_a_guard_deleted_with_nothing_added_is_a_stated_miss(
    tmp_path: pathlib.Path,
) -> None:
    """A removal-only diff has no added line for any diff-scoped rule to key
    on, so the file is never even opened. Inherent to the scoping choice."""
    source = "def load(raw):\n    data = json.loads(raw)\n    return data.get('k')\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -3,2 +2,0 @@\n"
        "-    if not isinstance(data, dict):\n"
        "-        raise ValueError('x')\n"
    )
    assert gate.find_violations(diff, tmp_path) == ([], [], 0)


# --- scope --------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".github/scripts/gate_x.py",
        "hooks/check_x.py",
        "evals/scripts/lint_x.py",
        "skills/a-skill/scripts/check_x.py",
    ],
)
def test_checker_script_paths_are_in_scope(path: str) -> None:
    assert gate.in_scope(path)


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_x.py",
        ".github/scripts/test_gate_x.py",
        "hooks/conftest.py",
        "docs/example.py",
        ".github/scripts/nested/gate_x.py",
        "skills/a-skill/nested/scripts/check_x.py",
        "evals/lint_x.py",
        ".github/scripts/gate_x.pyc",
    ],
)
def test_out_of_scope_paths_are_not_graded(path: str) -> None:
    assert not gate.in_scope(path)


def test_an_out_of_scope_file_is_not_even_read(tmp_path: pathlib.Path) -> None:
    """No file is written, so a gate that tried to read it would raise."""
    diff = _whole_file_diff("tests/test_x.py", "text = p.read_text()\n")
    assert gate.find_violations(diff, tmp_path) == ([], [], 0)


def test_in_scope_rejects_a_path_with_a_trailing_newline() -> None:
    """fullmatch, never match: `$` would also accept a trailing newline, and
    a newline-bearing path is how a machine-read sink gets corrupted."""
    assert not gate.in_scope(".github/scripts/gate_x.py\n")


# --- inline waiver ------------------------------------------------------


def test_an_inline_waiver_with_a_reason_is_honoured_and_reported(
    tmp_path: pathlib.Path,
) -> None:
    source = "text = p.read_text()  # exception-handler-gap: WAIVED: main() owns this read\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, waived, _graded = gate.find_violations(_whole_file_diff(".github/scripts/gate_x.py", source), tmp_path)
    assert violations == []
    assert _rules(waived) == ["decode-gap"]


def test_a_bare_marker_with_no_reason_is_not_a_waiver(tmp_path: pathlib.Path) -> None:
    source = "text = p.read_text()  # exception-handler-gap: WAIVED:\n"
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_the_marker_inside_a_string_literal_does_not_waive(tmp_path: pathlib.Path) -> None:
    """This module's own docstring quotes the marker; so does the gate's.
    Read through tokenize, a quoted marker is text, not a comment."""
    source = 'text = p.read_text(D["# exception-handler-gap: WAIVED: documenting the syntax"])\n'
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_a_waiver_excuses_only_the_innermost_finding_it_sits_inside(
    tmp_path: pathlib.Path,
) -> None:
    """A waiver names the thing it excuses. Matching every finding whose span
    crossed the line let a waiver written for an inner argument silence the
    outer call it sits inside -- with a reason that did not describe it."""
    source = (
        "def load(raw, fallback):\n"
        "    return json.loads(\n"
        "        raw\n"
        "    ).get(\n"
        "        'key',\n"
        "        pathlib.Path(fallback).read_text(),  # exception-handler-gap: WAIVED: bundled asset\n"
        "    )\n"
    )
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, waived, _graded = gate.find_violations(_whole_file_diff(".github/scripts/gate_x.py", source), tmp_path)
    assert _rules(violations) == ["json-shape-gap"]
    assert _rules(waived) == ["decode-gap"]


def test_a_waiver_for_an_inner_finding_not_in_the_diff_still_stays_with_it(
    tmp_path: pathlib.Path,
) -> None:
    """The escape the innermost rule was written to close, in the form that
    survived the first attempt: when the inner finding is not itself in the
    diff, searching only the in-diff candidates dropped it and the waiver fell
    through to the unguarded outer read. The search runs over every candidate."""
    source = (
        "def load(inner_path):\n"
        "    text = open(\n"
        "        open(inner_path).read(),  # exception-handler-gap: WAIVED: caller guards the inner read\n"
        "        encoding='utf-8',\n"
        "    ).read()\n"
        "    return text\n"
    )
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, waived, _graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", source, [4]), tmp_path
    )
    assert _rules(violations) == ["decode-gap"]
    assert waived == []


def test_two_findings_on_one_line_are_both_waived_by_one_comment(
    tmp_path: pathlib.Path,
) -> None:
    """A waiver applies to every finding the gate reports on that line. Trying
    to pick one of them -- by span length, then by AST depth -- spent a reason
    written about one finding on another, left such a line impossible to waive
    at all, and printed it as both honoured and rejected at once."""
    source = (
        "def load(raw):\n"
        "    data = json.loads(raw)\n"
        "    return open(data.get('path'), encoding='utf-8').read()"
        "  # exception-handler-gap: WAIVED: the key is always present\n"
    )
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, waived, _graded = gate.find_violations(_whole_file_diff(".github/scripts/gate_x.py", source), tmp_path)
    assert violations == []
    assert sorted(_rules(waived)) == ["decode-gap", "json-shape-gap"]


def test_an_edit_to_an_enclosing_handler_is_not_a_place_a_waiver_can_sit(
    tmp_path: pathlib.Path,
) -> None:
    """The handler lines widen what counts as *this diff's* finding; they must
    not also widen where a waiver is accepted, or narrowing a handler would
    both create the defect and excuse it."""
    source = (
        "def read(path):\n"
        "    try:\n"
        "        return path.read_text()\n"
        "    except OSError:  # exception-handler-gap: WAIVED: not where this belongs\n"
        "        return ''\n"
    )
    assert _rules(_grade(tmp_path, source)) == ["decode-gap"]


def test_the_waiver_marker_is_case_insensitive(tmp_path: pathlib.Path) -> None:
    """Matches `gitapex_gate_skill_audit_disclosure.py`'s own WAIVED vocabulary, which
    is case-insensitive; a case-sensitive copy here would diverge silently."""
    source = "text = p.read_text()  # Exception-Handler-Gap: waived: caller owns this read\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, waived, _graded = gate.find_violations(_whole_file_diff(".github/scripts/gate_x.py", source), tmp_path)
    assert violations == []
    assert len(waived) == 1


def test_a_waiver_must_sit_on_the_line_the_gate_reports(
    tmp_path: pathlib.Path,
) -> None:
    """One rule, stated as the error message states it: put the comment on the
    line named in the finding. A waiver on a continuation line of the same
    call is not honoured, which is the cost of having a rule a contributor can
    predict without reading this file."""
    reported = 'text = p.read_text(  # exception-handler-gap: WAIVED: caller guards\n    encoding="utf-8",\n)\n'
    continuation = 'text = p.read_text(\n    encoding="utf-8",  # exception-handler-gap: WAIVED: caller guards\n)\n'
    _write(tmp_path, ".github/scripts/gate_x.py", reported)
    violations, waived, _graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gate_x.py", reported), tmp_path
    )
    assert violations == []
    assert len(waived) == 1
    assert _rules(_grade(tmp_path, continuation)) == ["decode-gap"]


# --- fail closed (exit 2) ----------------------------------------------


def test_an_unparseable_hunk_header_fails_closed(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The `--- ` line here is load-bearing, not decoration: without it this
    fixture would exercise the missing-source-header ScanError (issue #1184,
    gap 1) instead of the unparseable-hunk-header one this test names."""
    diff = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/.github/scripts/gate_x.py\n@@ garbage @@\n+text = 1\n"
    _write(tmp_path, "diff.txt", diff)
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "unparseable hunk header" in capsys.readouterr().err


def test_a_git_quoted_path_fails_closed_rather_than_being_guessed_at(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`core.quotePath` renders a non-ASCII path this way; unescaping it by
    hand would be a guess, and a wrong guess drops the file from grading."""
    diff = 'diff --git a/x b/x\n--- a/x\n+++ "b/.github/scripts/g\\303\\251.py"\n@@ -0,0 +1,1 @@\n+text = 1\n'
    _write(tmp_path, "diff.txt", diff)
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "not a plain b/-prefixed path" in capsys.readouterr().err


def test_a_file_named_by_the_diff_but_missing_from_the_root_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong --root would otherwise turn this gate into a green no-op."""
    diff = _whole_file_diff(".github/scripts/gate_x.py", "text = p.read_text()\n")
    _write(tmp_path, "diff.txt", diff)
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "missing from" in capsys.readouterr().err


def test_a_non_utf8_source_file_fails_closed_naming_the_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = "text = p.read_text()\n"
    path = _write(tmp_path, ".github/scripts/gate_x.py", source)
    path.write_bytes(b"text = '\xff\xfe'\n")
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    stderr = capsys.readouterr().err
    assert "cannot be read as UTF-8 text" in stderr
    assert "gate_x.py" in stderr


def test_a_source_file_that_does_not_parse_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = "def broken(:\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "cannot be parsed as Python" in capsys.readouterr().err


def test_a_source_file_that_does_not_even_tokenize_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The AST parse runs before the waiver scan, so a file that breaks the
    tokenizer outright is reported by the parse and never reaches
    `_waived_lines` -- which is exactly what lets that function leave its
    tokenize loop unguarded without shipping issue #682's own defect D (a
    handler for a condition that cannot occur)."""
    source = 'DOC = """unterminated\n'
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "cannot be parsed as Python" in capsys.readouterr().err


def test_an_unreadable_directory_as_a_source_path_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An OSError that is not FileNotFoundError still fails closed."""
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "gate_x.py").mkdir()
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", "text = 1\n"))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "cannot be read as UTF-8 text" in capsys.readouterr().err


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


# --- CLI ----------------------------------------------------------------


def test_an_empty_diff_is_clean_and_says_so(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The common case: a PR touching no in-scope Python at all."""
    _write(tmp_path, "diff.txt", "")
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 0
    assert "OK: 0 in-scope file(s) graded" in capsys.readouterr().out


def test_main_returns_one_and_explains_the_failure(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = "text = p.read_text()\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 1
    stderr = capsys.readouterr().err
    assert "decode-gap" in stderr
    assert "#682" in stderr
    assert "exception-handler-gap: WAIVED:" in stderr


class _FakeStdin:
    """Just the surface `main` uses: `sys.stdin.buffer.read()`.

    Reading bytes rather than text is the point -- see
    `test_a_non_utf8_byte_on_stdin_fails_closed_instead_of_crashing`.
    """

    def __init__(self, data: bytes) -> None:
        import io as _io

        self.buffer = _io.BytesIO(data)


def test_main_reads_the_diff_from_stdin_when_no_flag_is_given(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = "text = p.read_text()\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    diff = _whole_file_diff(".github/scripts/gate_x.py", source)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(diff.encode("utf-8")))
    assert gate.main(["--root", str(tmp_path)]) == 1
    assert "decode-gap" in capsys.readouterr().err


def test_a_non_utf8_byte_on_stdin_fails_closed_instead_of_crashing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """This gate's own subject, once shipped into the gate itself.

    `sys.stdin.read()` let a non-UTF-8 byte anywhere in the diff escape as an
    uncaught `UnicodeDecodeError`, exiting 1 -- "violation found" -- with a
    raw traceback, while the identical bytes passed via `--diff` exited 2.
    A `.py` file containing latin-1 bytes makes `git diff -- '*.py'` emit
    exactly that, and the CI job pipes into stdin, so this was the production
    path. `gitapex_extract_diff_added_lines.py`'s docstring already records having had
    to close the same two failure modes (the uncaught raise, and the silent
    surrogateescape pass-through on a coercing locale) on this same input.
    """
    source = "text = p.read_text()\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    diff = _whole_file_diff(".github/scripts/gate_x.py", source)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(diff.encode("utf-8") + b"+# \xff\xfe\n"))
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "diff cannot be read as UTF-8 text" in capsys.readouterr().err


def test_a_honoured_waiver_is_printed_even_on_an_otherwise_clean_run(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A silent bypass is the one thing an escape hatch must never be."""
    source = "text = p.read_text()  # exception-handler-gap: WAIVED: caller owns it\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 0
    captured = capsys.readouterr()
    assert "waived inline" in captured.err
    assert "1 inline waiver(s) honoured" in captured.out


# --- round-8 review findings --------------------------------------------

_NARROWED_HANDLER = """import json


def load(raw):
    try:
        data = json.loads(raw)
        return data.get("gates")
    except ValueError:
        return None
"""


def test_narrowing_a_handler_around_a_get_is_this_diffs_finding(
    tmp_path: pathlib.Path,
) -> None:
    """The `json-shape-gap` half of the trigger contract, which the rule
    claimed and did not implement.

    Both this module's docstring and the registry entry say a finding counts
    as this diff's when an added line touches "the offending expression, an
    enclosing except clause, or anything between a JSON parse and the
    access". The decode rule unioned the enclosing handler lines into its
    trigger; the JSON rule passed the expression alone, and the
    parse-to-access window can never reach an `except` header because the
    header always follows the try body. So editing only line 8 below --
    dropping `AttributeError` from the handler, which is precisely issue
    #682's defect F shape one rule over -- created the gap and no part of the
    trigger could see it. A fail-open on this gate's own subject.
    """
    _write(tmp_path, ".github/scripts/gate_x.py", _NARROWED_HANDLER)
    violations, _waived, graded = gate.find_violations(
        _partial_diff(".github/scripts/gate_x.py", _NARROWED_HANDLER, [8]), tmp_path
    )
    assert graded == 1
    assert _at(violations) == [("json-shape-gap", 7)]


@pytest.mark.parametrize(
    "rebinding",
    [
        pytest.param("    with ctx() as data:\n        return data.get('k')\n", id="with-as"),
        pytest.param("    for data, _x in pairs:\n        return data.get('k')\n", id="tuple-for"),
        pytest.param(
            "    try:\n        pass\n    except ValueError as data:\n        return data.get('k')\n",
            id="except-as",
        ),
        pytest.param("    for data in pairs:\n        return data.get('k')\n", id="single-for"),
        pytest.param("    (data, _x) = (1, 2)\n    return data.get('k')\n", id="tuple-assign"),
        pytest.param("    with ctx() as [data, _x]:\n        return data.get('k')\n", id="list-target"),
        pytest.param("    for *data, _x in pairs:\n        return data.get('k')\n", id="starred-for"),
    ],
)
def test_a_name_rebound_by_any_binding_form_loses_its_taint(tmp_path: pathlib.Path, rebinding: str) -> None:
    """`_assigned_names` read `Assign`, `AnnAssign`, `NamedExpr` and a
    single-`Name` `for` target only, so three other binding forms left a name
    the source provably rebinds still tainted, and the `.get()` after them was
    reported on a value that is not the parse result -- three false positives.

    The single-`Name` `for` case was already handled, which is what makes the
    others an oversight rather than one of the recorded trades: the module
    docstring states the invariant as "a name assigned both a parse and
    something else is dropped, wherever those assignments sit".
    """
    source = "import json\n\n\ndef f(raw, ctx, pairs):\n    data = json.loads(raw)\n" + rebinding
    assert _grade(tmp_path, source) == []


def test_a_lambda_argument_default_keeps_the_enclosing_try(tmp_path: pathlib.Path) -> None:
    """A `lambda`'s defaults are evaluated where the `lambda` is written, so
    an enclosing `try` really does catch them -- the same reasoning the
    `FunctionDef` branch already implemented for `def`. Walking every child of
    a `Lambda` with cleared handler state reported a read the handler covers.
    """
    source = (
        "def f(p):\n"
        "    try:\n"
        "        fn = lambda x=p.read_text(): x\n"
        "    except ValueError:\n"
        "        fn = None\n"
        "    return fn\n"
    )
    assert _grade(tmp_path, source) == []


def test_a_lambda_body_still_loses_it(tmp_path: pathlib.Path) -> None:
    """The other half of the same split, so the fix above cannot quietly
    widen into "a lambda is covered by whatever encloses it". The body is
    deferred and genuinely escapes the handler."""
    source = (
        "def f(p):\n"
        "    try:\n"
        "        fn = lambda: p.read_text()\n"
        "    except ValueError:\n"
        "        fn = None\n"
        "    return fn\n"
    )
    assert _at(_grade(tmp_path, source)) == [("decode-gap", 3)]


def test_a_utf8_bom_does_not_fail_the_file_closed(tmp_path: pathlib.Path) -> None:
    """CPython strips a leading BOM from source it runs; `ast.parse` on a
    `str` does not. Reading in-scope files as plain utf-8 therefore exited 2
    on a file python3 executes fine, naming a syntax error that does not
    exist ("invalid non-printable character U+FEFF") -- a hard block a
    contributor could only clear by changing editor. utf-8-sig is identical
    for a file without a BOM, and shifts no line number, which the asserted
    line proves.
    """
    assert _at(_grade(tmp_path, "\ufefftext = p.read_text()\n")) == [("decode-gap", 1)]


# Boundary pins: each of these is behaviour this gate is documented as
# getting wrong, recorded so it cannot change without a reader noticing.
# Every one of them was a round-8 review finding that reproduced, and every
# one was left alone because the fix is the name-resolution machinery this
# branch reverted five times -- see the module docstring's two lists.


def test_a_zero_argument_open_on_a_non_file_receiver_is_a_known_over_report(
    tmp_path: pathlib.Path,
) -> None:
    """Grading `<expr>.open()` is not optional -- `Path(p).open()` is a real
    text read and defect C's own shape -- and separating it from `conn.open()`
    needs the receiver. Over-report, waivable, visible."""
    assert _rules(_grade(tmp_path, "def f(conn):\n    return conn.open()\n")) == ["decode-gap"]
    assert _rules(_grade(tmp_path, "def f(w, u):\n    return w.open(u)\n")) == []


def test_a_member_name_made_of_mode_characters_is_a_known_over_report(
    tmp_path: pathlib.Path,
) -> None:
    """`_looks_like_a_mode` narrows the ZipFile-style confusion it exists for
    without closing it: a member name built only from `rwxab+t` still reads as
    a mode. `"bat"` and `"tab"` contain a `b` and grade as binary, so the
    residue is names like `"art"`, `"raw"`, `"war"`, `"rat"`."""
    assert _rules(_grade(tmp_path, 'def f(z):\n    return z.open("art")\n')) == ["decode-gap"]
    assert _rules(_grade(tmp_path, 'def f(z):\n    return z.open("bat")\n')) == []
    assert _rules(_grade(tmp_path, 'def f(z):\n    return z.open("name")\n')) == []


def test_from_json_import_loads_is_a_known_miss(tmp_path: pathlib.Path) -> None:
    """Only the `json.loads(...)` attribute spelling is read as a parse, so
    the import form is defect E behind a one-line import change. Recognising
    it means resolving an imported name through aliases, shadowing and
    rebinding -- the machinery this branch reverted. The attribute spelling is
    the one all three historical defects used."""
    attribute = "import json\n\n\ndef f(raw):\n    d = json.loads(raw)\n    return d.get('k')\n"
    imported = "from json import loads\n\n\ndef f(raw):\n    d = loads(raw)\n    return d.get('k')\n"
    assert _rules(_grade(tmp_path, attribute)) == ["json-shape-gap"]
    assert _rules(_grade(tmp_path, imported)) == []


def test_two_findings_of_one_rule_on_one_line_report_once(tmp_path: pathlib.Path) -> None:
    """Findings dedupe by `(path, line, rule, message)`, and for two reads on
    one physical line all four are identical -- printing the line twice with
    the same text would not tell a contributor which read is meant. The stated
    cost is that fixing one and never touching the line again leaves the other
    unreported, and one waiver there covers both."""
    assert _at(_grade(tmp_path, "def f(p, q):\n    return p.read_text() + q.read_text()\n")) == [("decode-gap", 2)]
    assert _at(_grade(tmp_path, "def f(p, q):\n    a = p.read_text()\n    b = q.read_text()\n")) == [
        ("decode-gap", 2),
        ("decode-gap", 3),
    ]


# --- the real repository ------------------------------------------------


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    """Drift gate for an invariant this change establishes, per CLAUDE.md
    section 3: both flags were added after a review found each one's absence
    was a real defect, and both live in the caller rather than in the script,
    so nothing else would notice them being dropped.

    `--no-renames`: a file promoted into a graded directory otherwise arrives
    as a 100%-similarity rename with zero added lines and enters scope
    ungraded. `core.quotePath=false`: a non-ASCII path anywhere in the diff
    otherwise arrives C-quoted, which the gate refuses to resolve (exit 2) --
    failing the job over a file that need not even be in scope.
    """
    assert_workflow_diff_carries_flags("exception-handler-gap-gate.yml", "--no-renames", "core.quotePath=false")


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    """The third caller-side invariant, which had no drift test while the two
    `git diff` flags above did -- the gap CLAUDE.md section 3 names, since an
    invariant's drift gate ships with the invariant rather than after it.

    `ref: <head sha>` is what makes the working tree the diff's post-image.
    Dropping it silently mis-grades every file the base branch also touched:
    under the default `refs/pull/N/merge` checkout the tree and the
    diff-derived line numbers refer to different content, and a real gap in
    such a file grades clean. There is no exit code and no message when that
    happens, so nothing else in this suite would notice.

    `fetch-depth: '0'` is load-bearing *for* that pin, not decoration. A
    40-hex `ref` becomes `settings.commit` with `settings.ref` empty
    (actions/checkout `input-helper.ts`), and only the `fetchDepth <= 0`
    branch of `git-source-provider.ts` fetches
    `+refs/heads/*:refs/remotes/origin/*`; the shallow branch would fetch the
    bare commit alone, leaving `$BASE_SHA` absent from the object store and
    the `git merge-base` step failing. The two settings are therefore one
    invariant and are asserted together.

    Both settings have now been read off this workflow's parsed `with:`
    mapping twice over, because a whole-file text check for either kept
    matching prose instead of config: first the bare `fetch-depth: 0` form,
    which only ever passed off a comment line reading "fetch-depth: 0 so the
    merge-base below resolves"; then the quoted `fetch-depth: '0'` form that
    replaced it, which only ever passed off the shrunk pointer comment this
    same PR introduced above the step. `conftest`'s own docstring carries
    the defeat case that closed the second one.
    """
    assert_workflow_checkout_pins_head_sha_with_full_history("exception-handler-gap-gate.yml")


def test_the_workflow_has_no_paths_filter() -> None:
    """Drift gate for an invariant this change establishes, per CLAUDE.md
    section 3: a `paths:` filter under `pull_request:` is not merely absent
    by omission here -- it is deliberately never added, following the same
    rationale `lint.yml` and `plugin-root-brace-notation-gate.yml` state for
    themselves. GitHub distinguishes a job that runs and reports `skipped`
    (which does not block a required check) from a workflow that never
    fires for a given PR at all (which leaves a required check `Pending`
    forever, with no in-repo fix). This gate is intended for promotion to a
    required status check, so a `paths:` filter would recreate that exact
    stuck-Pending failure mode for any PR that happens not to touch a
    matched path. The scan itself still only grades files a diff actually
    adds lines to, so running the job unconditionally costs a few seconds,
    not a full-repo sweep.

    `conftest.assert_workflow_has_no_trigger_path_filter`'s own docstring
    carries how the trigger keys are read and why `paths-ignore:` is
    rejected too.
    """
    assert_workflow_has_no_trigger_path_filter("exception-handler-gap-gate.yml")


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    """Drift gate for an invariant this change establishes, per CLAUDE.md
    section 3, mirroring `gitignore-pattern-coverage-gate.yml`'s and
    `skill-rename-lifecycle-gate.yml`'s own identical reasoning: `git
    merge-base` is resolved between `BASE_SHA` and `HEAD_SHA` rather than
    diffing against `base.sha` directly, so a change that landed on the
    base branch after this PR forked is never misattributed to this PR.
    Diffing against `base.sha` directly instead would silently re-attribute
    someone else's already-merged change to this PR's own diff, with no
    exit code or message when that happens.

    `conftest.assert_workflow_feeds_merge_base_to`'s own docstring carries
    the defeat cases it closes, kept there rather than re-enumerated here
    so this comment cannot go stale the next time that list grows.
    `"diff"` is the producer command this gate depends on.
    """
    assert_workflow_feeds_merge_base_to("exception-handler-gap-gate.yml", "diff")


def test_this_gate_grades_itself_clean() -> None:
    """The gate is itself an in-scope checker script; a gate that could not
    pass its own rule would be asking for something it does not do."""
    source = (REPO_ROOT / _SCRIPT).read_text(encoding="utf-8")
    violations, waived, graded = gate.find_violations(_whole_file_diff(_SCRIPT, source), REPO_ROOT)
    assert (violations, waived, graded) == ([], [], 1)


def test_the_repaired_versions_of_the_historical_defect_files_are_clean() -> None:
    """Defects C, E and F all lived in these two files. Both must pass as
    they stand on this branch, or the fixture assertions above would be
    measuring something the repository no longer contains."""
    for relative in (
        ".github/scripts/gitapex_gate_plugin_root_brace_notation.py",
        ".github/scripts/gitapex_detect_changed_gate_scripts.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        violations, _waived, _graded = gate.find_violations(_whole_file_diff(relative, source), REPO_ROOT)
        assert violations == [], f"{relative}: {violations}"

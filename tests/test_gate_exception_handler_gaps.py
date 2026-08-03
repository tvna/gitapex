"""Tests for the exception-handler gap gate
(.github/scripts/gate_exception_handler_gaps.py).

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

* defect C -- `f91383c:.github/scripts/gate_plugin_root_brace_notation.py`
* defect E -- `406d587:.github/scripts/detect_changed_gate_scripts.py`
* defect F -- `0b4cedd:.github/scripts/detect_changed_gate_scripts.py`

The defeat cases carry as much weight as the happy path. A gate that fired
on a write-mode `open()` would be reverted the first time someone wrote a
file; one that passed on a file it could not parse would be a permanent
green no-op; one that honoured a marker inside a string literal could be
silenced by this very docstring.
"""

from __future__ import annotations

import pathlib
import subprocess

import gate_exception_handler_gaps as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_SCRIPT = ".github/scripts/gate_exception_handler_gaps.py"


# --- helpers ------------------------------------------------------------


def _whole_file_diff(path: str, source: str) -> str:
    """A unified diff in which every line of `source` is an added line."""
    lines = source.split("\n")
    body = "".join("+" + line + "\n" for line in lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n" + body
    )


def _partial_diff(path: str, source: str, added: list[int]) -> str:
    """A unified diff adding only the 1-based line numbers in `added`."""
    lines = source.split("\n")
    hunks = "".join(
        f"@@ -{number},0 +{number},1 @@\n+{lines[number - 1]}\n" for number in added
    )
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{hunks}"


def _write(root: pathlib.Path, relative: str, source: str) -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _grade(
    tmp_path: pathlib.Path, source: str, *, relative: str = ".github/scripts/gate_x.py"
) -> list[gate.Finding]:
    """Write `source` at `relative`, grade it as wholly added, return violations.

    The `graded == 1` assertion is load-bearing, not decoration. Every
    "must not fire" test below asserts `== []`, and without this a gate that
    read nothing at all -- a wrong scope rule, a wrong root -- would satisfy
    all of them at once.
    """
    _write(tmp_path, relative, source)
    violations, _waived, graded = gate.find_violations(
        _whole_file_diff(relative, source), tmp_path
    )
    assert graded == 1, f"{relative} was not graded at all"
    return violations


def _rules(findings: list[gate.Finding]) -> list[str]:
    return [finding.rule for finding in findings]


def _at(findings: list[gate.Finding]) -> list[tuple[str, int]]:
    return [(finding.rule, finding.line) for finding in findings]


# --- regression fixtures from the real defective commits ----------------

# Reconstructed from f91383c:.github/scripts/gate_plugin_root_brace_notation.py:109-121.
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

# Reconstructed from 406d587:.github/scripts/detect_changed_gate_scripts.py:98-116.
# The UnicodeDecodeError *is* handled here -- what is missing is any check
# that the parsed JSON is an object, so `[]` reached `.get` and raised
# AttributeError. The `isinstance(gates, list)` two lines below validates a
# different name and must not be read as validating `data`.
_DEFECT_E = '''
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
'''

# Reconstructed from 0b4cedd:.github/scripts/detect_changed_gate_scripts.py:293-307.
# The read was wrapped -- in a handler naming only OSError, so a non-UTF-8
# diff escaped as a traceback. This is the shape that has recurred most.
_DEFECT_F = '''
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
'''


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
    fixed_f = _DEFECT_F.replace("        except OSError as error:", "        except (OSError, UnicodeDecodeError) as error:")
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
def test_a_handler_naming_the_error_or_an_ancestor_covers_the_read(
    tmp_path: pathlib.Path, handler: str
) -> None:
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
def test_an_attribute_named_open_that_decodes_nothing_is_not_flagged(
    tmp_path: pathlib.Path, call: str
) -> None:
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
def test_an_attribute_open_that_declares_a_text_read_is_flagged(
    tmp_path: pathlib.Path, call: str
) -> None:
    assert _rules(_grade(tmp_path, f"handle = {call}\n")) == ["decode-gap"]


def test_a_function_defined_inside_a_try_body_is_not_protected_by_it(
    tmp_path: pathlib.Path,
) -> None:
    """The `try` runs the `def`, not the body. A helper whose only call site
    is elsewhere would otherwise inherit protection it never has."""
    source = (
        "try:\n"
        "    def helper(p):\n"
        "        return p.read_text()\n"
        "except UnicodeDecodeError:\n"
        "    helper = None\n"
    )
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
    `--- ...`, and must not arm the post-image-header state machine."""
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -1,2 +1,1 @@\n"
        "--- a signature dash line\n"
        "+text = p.read_text()\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/gate_x.py": {1}}


def test_both_in_hunk_header_lookalikes_in_one_hunk_are_content(
    tmp_path: pathlib.Path,
) -> None:
    """The killing case for the hunk-state machine: a removed `-- ` line arms
    nothing, and the `++ ` line after it is content. Testing either half alone
    left both guards passing individually while jointly broken."""
    diff = (
        "diff --git a/.github/scripts/gate_x.py b/.github/scripts/gate_x.py\n"
        "--- a/.github/scripts/gate_x.py\n"
        "+++ b/.github/scripts/gate_x.py\n"
        "@@ -1,2 +1,2 @@\n"
        "--- an added list marker line\n"
        "++ a list marker, not a diff header\n"
        "+text = p.read_text()\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/gate_x.py": {1, 2}}


def test_a_post_image_path_without_the_b_prefix_fails_closed() -> None:
    """--no-prefix output and a git-quoted path both land here. Guessing at
    either silently drops a file from grading."""
    diff = "diff --git a/x b/x\n--- a/x\n+++ .github/scripts/gate_x.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="not a plain b/-prefixed path"):
        gate.parse_added_lines(diff)


def test_the_minus_header_line_is_not_counted_as_a_removal(tmp_path: pathlib.Path) -> None:
    """Regression guard on the parser itself: `--- a/<path>` arrives while
    the previous file's path could still be current, and must not be read as
    that file's content."""
    source = "text = p.read_text()\n"
    _write(tmp_path, ".github/scripts/gate_a.py", source)
    _write(tmp_path, ".github/scripts/gate_b.py", source)
    diff = _whole_file_diff(".github/scripts/gate_a.py", source) + _whole_file_diff(
        ".github/scripts/gate_b.py", source
    )
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
    source = (
        "def untouched(path):\n"
        "    return path.read_text()\n"
        "\n"
        "\n"
        "def touched():\n"
        "    return 1\n"
    )
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
def test_a_generator_expression_consumed_inside_the_try_is_protected(
    tmp_path: pathlib.Path, consumer: str
) -> None:
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
def test_an_isinstance_naming_a_mapping_type_clears_it(
    tmp_path: pathlib.Path, mapping_type: str
) -> None:
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
    source = (
        "def load(raw):\n"
        "    data, extra = json.loads(raw), {}\n"
        "    return data.get('k'), extra.get('k')\n"
    )
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
    violations, waived, _graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gate_x.py", source), tmp_path
    )
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
    violations, waived, _graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gate_x.py", source), tmp_path
    )
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
    violations, waived, _graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gate_x.py", source), tmp_path
    )
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
    """Matches `gate_skill_audit_disclosure.py`'s own WAIVED vocabulary, which
    is case-insensitive; a case-sensitive copy here would diverge silently."""
    source = "text = p.read_text()  # Exception-Handler-Gap: waived: caller owns this read\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, waived, _graded = gate.find_violations(
        _whole_file_diff(".github/scripts/gate_x.py", source), tmp_path
    )
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
    diff = "diff --git a/x.py b/x.py\n+++ b/.github/scripts/gate_x.py\n@@ garbage @@\n+text = 1\n"
    _write(tmp_path, "diff.txt", diff)
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "unparseable hunk header" in capsys.readouterr().err


def test_a_git_quoted_path_fails_closed_rather_than_being_guessed_at(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`core.quotePath` renders a non-ASCII path this way; unescaping it by
    hand would be a guess, and a wrong guess drops the file from grading."""
    diff = (
        "diff --git a/x b/x\n"
        "--- a/x\n"
        '+++ "b/.github/scripts/g\\303\\251.py"\n'
        "@@ -0,0 +1,1 @@\n"
        "+text = 1\n"
    )
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
    """The waiver scan runs before the AST parse, so it has to survive a
    file that breaks the tokenizer outright and let the parse report it."""
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


def test_main_exits_2_on_a_root_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert gate.main(["--root", str(tmp_path / "nope")]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_is_a_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a_file = _write(tmp_path, "not-a-directory", "x")
    assert gate.main(["--root", str(a_file)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_when_the_diff_file_is_missing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
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


def test_an_empty_diff_is_clean_and_says_so(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The common case: a PR touching no in-scope Python at all."""
    _write(tmp_path, "diff.txt", "")
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 0
    assert "OK: 0 in-scope file(s) graded" in capsys.readouterr().out


def test_main_returns_one_and_explains_the_failure(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = "text = p.read_text()\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 1
    stderr = capsys.readouterr().err
    assert "decode-gap" in stderr
    assert "#682" in stderr
    assert "exception-handler-gap: WAIVED:" in stderr


def test_main_reads_the_diff_from_stdin_when_no_flag_is_given(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io as _io

    source = "text = p.read_text()\n"
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    monkeypatch.setattr(
        gate.sys, "stdin", _io.StringIO(_whole_file_diff(".github/scripts/gate_x.py", source))
    )
    assert gate.main(["--root", str(tmp_path)]) == 1
    assert "decode-gap" in capsys.readouterr().err


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
    workflow = (REPO_ROOT / ".github/workflows/exception-handler-gap-gate.yml").read_text(
        encoding="utf-8"
    )
    invocation = next(
        line for line in workflow.split("\n") if "git" in line and "diff -U0" in line
    )
    assert "--no-renames" in invocation, invocation
    assert "core.quotePath=false" in invocation, invocation


def test_this_gate_grades_itself_clean() -> None:
    """The gate is itself an in-scope checker script; a gate that could not
    pass its own rule would be asking for something it does not do."""
    source = (REPO_ROOT / _SCRIPT).read_text(encoding="utf-8")
    violations, waived, graded = gate.find_violations(
        _whole_file_diff(_SCRIPT, source), REPO_ROOT
    )
    assert (violations, waived, graded) == ([], [], 1)


def test_the_repaired_versions_of_the_historical_defect_files_are_clean() -> None:
    """Defects C, E and F all lived in these two files. Both must pass as
    they stand on this branch, or the fixture assertions above would be
    measuring something the repository no longer contains."""
    for relative in (
        ".github/scripts/gate_plugin_root_brace_notation.py",
        ".github/scripts/detect_changed_gate_scripts.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        violations, _waived, _graded = gate.find_violations(
            _whole_file_diff(relative, source), REPO_ROOT
        )
        assert violations == [], f"{relative}: {violations}"

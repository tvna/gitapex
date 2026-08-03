"""Tests for check_gate_shape.py.

Fixtures are synthesized in-memory or under pytest's ``tmp_path`` (no
repository hook script is read as a fixture) so the test is self-contained
and travels with the skill on vendoring, the same discipline
test_check_axis_shape.py documents for its own sibling checker. Wired into
the root pyproject.toml testpaths/pythonpath/coverage source lists in the
same change that adds this file (issue #562's own lesson: a test file that
exists but isn't collected is worse than no test file, since it looks like
coverage that isn't real).

Each dimension gets at least one pass case and one fail (or
not_applicable/indeterminate, where a hard fail is deliberately never
asserted -- dimension 3) case, per issue #587's own acceptance criterion
("New checker correctly grades a constructed pass-case and fail-case
target for at least one of dimensions 1-6").
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import check_gate_shape as cgs


def _result(results: list[cgs.CheckResult], dimension: str) -> cgs.CheckResult:
    matches = [r for r in results if r.dimension == dimension]
    assert len(matches) == 1, f"expected exactly one result for dimension {dimension}"
    return matches[0]


# --- dimension 1 / 2: deny mechanism + dual signal -----------------------

_SH_GOOD_DENY = """\
#!/bin/bash
set -euo pipefail
input=$(cat)
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi
command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
if printf '%s' "$command" | grep -q "rm -rf"; then
  echo "Destructive command blocked by hook" >&2
  exit 2
fi
exit 0
"""

_SH_ADVISORY_ONLY_DENY = """\
#!/bin/bash
set -euo pipefail
command=$(cat)
if echo "$command" | grep -q "forbidden"; then
  echo "forbidden command" >&2
  exit 1
fi
exit 0
"""

_SH_NO_DENY_AT_ALL = """\
#!/bin/bash
echo "just an observability hook, always allows"
exit 0
"""

_PY_GOOD_DENY_JSON = """\
import json
import sys

data = json.load(sys.stdin)
if data.get("tool_name") == "Bash" and "rm -rf" in data.get("tool_input", {}).get("command", ""):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Destructive command blocked by hook",
        }
    }))
    sys.exit(0)
sys.exit(0)
"""

_PY_DENY_JSON_NO_REASON = """\
import json
import sys

data = json.load(sys.stdin)
print(json.dumps({
    "hookSpecificOutput": {
        "permissionDecision": "deny",
        "permissionDecisionReason": "",
    }
}))
sys.exit(0)
"""


def test_dimension1_exit2_with_stderr_passes_both_1_and_2():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_GOOD_DENY)
    d1 = _result(results, "1")
    d2 = _result(results, "2")
    assert d1.verdict == cgs.VERDICT_PASSED
    assert "exit code 2" in d1.evidence
    assert d2.verdict == cgs.VERDICT_PASSED


def test_dimension1_generic_nonzero_exit_fails():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_ADVISORY_ONLY_DENY)
    d1 = _result(results, "1")
    assert d1.verdict == cgs.VERDICT_FAILED
    assert "non-blocking notice" in d1.evidence


def test_dimension1_negative_exit_code_shell_fails():
    # `\d+`-only regexes miss `exit -1` entirely (an adversarial review
    # round found this) -- a negative literal exit code is just as
    # non-blocking to Claude Code as a bare `exit 1`, the same bypass
    # class, and must not be misgraded not_applicable.
    text = '#!/bin/bash\nif grep -q bad <<< "$1"; then\n  exit -1\nfi\nexit 0\n'
    results = cgs.check_gate_shape(Path("hook.sh"), text)
    d1 = _result(results, "1")
    assert d1.verdict == cgs.VERDICT_FAILED


def test_dimension1_negative_exit_code_python_fails():
    text = "import sys\nif bad:\n    sys.exit(-1)\nsys.exit(0)\n"
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d1 = _result(results, "1")
    assert d1.verdict == cgs.VERDICT_FAILED


def test_dimension1_no_deny_path_is_not_applicable():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_NO_DENY_AT_ALL)
    d1 = _result(results, "1")
    assert d1.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension2_not_applicable_when_dimension1_fails():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_ADVISORY_ONLY_DENY)
    d2 = _result(results, "2")
    assert d2.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension2_not_applicable_when_no_deny_path():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_NO_DENY_AT_ALL)
    d2 = _result(results, "2")
    assert d2.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_python_deny_json_with_reason_passes():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_GOOD_DENY_JSON)
    d1 = _result(results, "1")
    d2 = _result(results, "2")
    assert d1.verdict == cgs.VERDICT_PASSED
    assert "deny" in d1.evidence
    assert d2.verdict == cgs.VERDICT_PASSED
    assert "permissionDecisionReason" in d2.evidence


def test_python_deny_json_empty_reason_fails_dimension2():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_DENY_JSON_NO_REASON)
    d2 = _result(results, "2")
    assert d2.verdict == cgs.VERDICT_FAILED


# A real pattern from this repository's own hooks/check-bash-safety.sh: a
# `jq -n --arg msg "$reason" '...' >&2` idiom builds the human-readable
# message on one line and redirects to stderr on a later one -- distinct
# from the same-line echo/printf case _SH_GOOD_DENY already exercises.
_SH_JQ_ARG_DENY = """\
#!/bin/bash
set -euo pipefail
deny() {
  local reason="$1"
  jq -n --arg msg "$reason" \\
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}
deny "Destructive command blocked by hook"
"""

_PY_STDERR_WRITE_DENY = """\
import sys

def deny(reason):
    sys.stderr.write(f"blocked: {reason}\\n")
    sys.exit(2)

deny("bad command")
"""

_PY_PRINT_STDERR_DENY = """\
import sys

def deny(reason):
    print(f"blocked: {reason}", file=sys.stderr)
    sys.exit(2)

deny("bad command")
"""


def test_dimension2_shell_jq_arg_idiom_passes():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_JQ_ARG_DENY)
    d2 = _result(results, "2")
    assert d2.verdict == cgs.VERDICT_PASSED


def test_dimension2_python_stderr_write_passes():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_STDERR_WRITE_DENY)
    d2 = _result(results, "2")
    assert d2.verdict == cgs.VERDICT_PASSED


def test_dimension2_python_print_file_stderr_passes():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_PRINT_STDERR_DENY)
    d2 = _result(results, "2")
    assert d2.verdict == cgs.VERDICT_PASSED


def test_has_stderr_message_python_empty_string_arg_not_credited():
    text = 'import sys\nsys.stderr.write("")\n'
    assert cgs._has_stderr_message_python(text) is False


def test_dimension2_python_fallback_no_match_returns_false():
    # Malformed Python (never parses) with no stderr-write/print call at
    # all -- exercises the regex fallback's own "nothing found" path
    # directly, distinct from the AST path's own equivalent branch.
    text = "def broken(:\n    pass\n"
    assert cgs._has_stderr_message_python_fallback(text) is False


def test_dimension2_python_fallback_dispatch_matches_stderr_write(monkeypatch):
    # Routes through the public dispatcher (_has_stderr_message_python),
    # not the fallback function directly, so the dispatch branch itself
    # (ast.parse fails -> call the fallback) is also covered. Forces the
    # fallback path even for otherwise-valid Python by monkeypatching
    # _parse_python_calls to report "did not parse".
    monkeypatch.setattr(cgs, "_parse_python_calls", lambda text: None)
    text = 'import sys\nsys.stderr.write("blocked: bad command")\n'
    assert cgs._has_stderr_message_python(text) is True


def test_dimension2_python_fallback_matches_print_file_stderr():
    text = (
        'import sys\n'
        'print("blocked: bad command", file=sys.stderr)\n'
        'x = (\n'
    )
    assert cgs._has_stderr_message_python_fallback(text) is True


def test_dimension2_shell_echo_stderr_scan_is_not_quadratic():
    # An adversarial review round measured the old single-regex
    # (two unbounded [^\n]* spans around a quote alternation) growing
    # ~4x in time per 2x input doubling, and a ~800KB adversarial single
    # line without >&2 did not finish in 120s -- a real denial-of-service
    # against this checker. The per-line substring scan that replaced it
    # must stay fast even on a large adversarial line with no >&2 at all.
    adversarial_line = "echo " + ('a"b\'c ' * 50_000)
    start = time.monotonic()
    result = cgs._has_stderr_message_shell(adversarial_line)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"took {elapsed:.2f}s -- possible ReDoS regression"
    assert result is False


# --- dimension 3: self-revalidation (heuristic) --------------------------


def test_dimension3_passes_on_tool_name_read_and_compare():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_GOOD_DENY)
    d3 = _result(results, "3")
    assert d3.verdict == cgs.VERDICT_PASSED


def test_dimension3_indeterminate_never_fail_when_absent():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_NO_DENY_AT_ALL)
    d3 = _result(results, "3")
    assert d3.verdict == cgs.VERDICT_INDETERMINATE


def test_dimension3_passes_on_dict_get_comparison():
    # `.get("tool_name")` puts a closing paren between the field name and
    # the operator -- an earlier version of the regex required direct
    # adjacency and missed this, the single most idiomatic Python shape
    # (an adversarial review round found this).
    text = (
        'import json, sys\n'
        'data = json.load(sys.stdin)\n'
        'if data.get("tool_name") == "Bash":\n'
        '    sys.exit(2)\n'
    )
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d3 = _result(results, "3")
    assert d3.verdict == cgs.VERDICT_PASSED


def test_dimension3_bare_identifier_used_elsewhere_stays_indeterminate():
    # An adversarial review round found that widening the punctuation
    # window to include ')' made this false-PASS: tool_name here is a
    # bare Python variable passed to an unrelated function, never
    # compared against anything itself -- get_command_hash(...)'s RESULT
    # is what gets compared. Must stay indeterminate, not PASS.
    text = 'if get_command_hash(tool_name) == cached_hash:\n    sys.exit(2)\n'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d3 = _result(results, "3")
    assert d3.verdict == cgs.VERDICT_INDETERMINATE


# --- dimension 4: bundled test exists ------------------------------------


def test_dimension4_passes_when_sibling_test_exists(tmp_path):
    script = tmp_path / "check-bash-safety.sh"
    script.write_text(_SH_NO_DENY_AT_ALL, encoding="utf-8")
    sibling = tmp_path / "test_check_bash_safety.py"
    sibling.write_text("def test_x(): pass\n", encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_PASSED
    assert "test_check_bash_safety.py" in d4.evidence


def test_dimension4_fails_when_no_sibling_test(tmp_path):
    script = tmp_path / "check-template-overwrite.sh"
    script.write_text(_SH_NO_DENY_AT_ALL, encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_FAILED


def test_dimension4_containment_match_accepted_when_no_better_sibling(tmp_path):
    # Mirrors a real pattern in this repository: check-pr-issue-acm-
    # disclosure.sh's own test file is named test_check_pr_issue_acm_
    # disclosure_shell.py (a descriptive "_shell" suffix), not an exact
    # stem match. No other script in the directory competes for that name.
    script = tmp_path / "check-pr-issue-acm-disclosure.sh"
    script.write_text(_SH_NO_DENY_AT_ALL, encoding="utf-8")
    sibling = tmp_path / "test_check_pr_issue_acm_disclosure_shell.py"
    sibling.write_text("def test_x(): pass\n", encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_PASSED


def test_dimension4_containment_match_rejected_when_better_sibling_exists(tmp_path):
    # An adversarial review round found the prior substring-containment
    # rule let check_gate.py claim test_check_gate_v2.py even when
    # check_gate_v2.py exists as its own, different, real sibling script
    # -- the test file actually names that other script, not this one.
    script = tmp_path / "check_gate.py"
    script.write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "check_gate_v2.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "test_check_gate_v2.py").write_text("def test_x(): pass\n", encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_FAILED


def test_dimension4_reverse_direction_longer_script_does_not_steal_shorter_exact_match(tmp_path):
    # An adversarial review round found the original guard only compared
    # lengths one way (len(other) > len(stem_norm)), missing the reverse:
    # check_gate_v2.py must not steal test_check_gate.py, the EXACT-match
    # test for the separate, shorter check_gate.py sibling.
    script = tmp_path / "check_gate_v2.py"
    script.write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "check_gate.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "test_check_gate.py").write_text("def test_x(): pass\n", encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_FAILED


def test_dimension4_unrelated_sibling_script_never_blocks_a_real_match(tmp_path):
    # An adversarial review round found the original guard blocked a
    # correct match whenever ANY other script's stem happened to overlap
    # the candidate test name, even when that other script is not an
    # extension of this script's own name at all: gate.py + an unrelated
    # shape.py must not stop test_gate_shape.py from crediting gate.py.
    script = tmp_path / "gate.py"
    script.write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "shape.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "test_gate_shape.py").write_text("def test_x(): pass\n", encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_PASSED


def test_dimension4_unreadable_directory_fails_closed_instead_of_crashing(tmp_path, monkeypatch):
    # An adversarial review round found directory.iterdir() had no
    # try/except anywhere in _find_sibling_test, unlike the read_text()
    # call sites main()/dimension 6a already guard -- a permission-denied
    # or racily-deleted directory crashed the whole tool uncaught.
    script = tmp_path / "hook.py"
    script.write_text("x = 1\n", encoding="utf-8")

    def _raise_permission_error(self):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "iterdir", _raise_permission_error)
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_FAILED


def test_dimension4_fails_when_sibling_test_name_unrelated(tmp_path):
    script = tmp_path / "check-bash-safety.sh"
    script.write_text(_SH_NO_DENY_AT_ALL, encoding="utf-8")
    (tmp_path / "test_completely_unrelated.py").write_text("def test_x(): pass\n", encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_FAILED


def test_dimension4_fails_when_sibling_test_is_empty(tmp_path):
    script = tmp_path / "check-x.sh"
    script.write_text(_SH_NO_DENY_AT_ALL, encoding="utf-8")
    (tmp_path / "test_check_x.sh").write_text("", encoding="utf-8")
    results = cgs.check_gate_shape(script, script.read_text(encoding="utf-8"))
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_FAILED


def test_dimension4_missing_parent_directory():
    script = Path("/nonexistent-dir-xyz/hook.sh")
    results = cgs.check_gate_shape(script, _SH_NO_DENY_AT_ALL)
    d4 = _result(results, "4")
    assert d4.verdict == cgs.VERDICT_FAILED


# --- dimension 5: unsafe shell/command interpolation ---------------------

_PY_SHELL_TRUE_FSTRING = """\
import subprocess

def run(branch_name):
    subprocess.run(f"git checkout {branch_name}", shell=True)
"""

_PY_SHELL_TRUE_LITERAL = """\
import subprocess

def run():
    subprocess.run("git status", shell=True, timeout=5)
"""

_PY_ARGV_LIST_FORM = """\
import subprocess

def run(branch_name):
    subprocess.run(["git", "checkout", branch_name], timeout=5)
"""

_PY_OS_SYSTEM_CONCAT = """\
import os

def run(user_input):
    os.system("echo " + user_input)
"""

_SH_EVAL_UNSAFE = """\
#!/bin/bash
cmd="$1"
eval "$cmd"
"""

_SH_SAFE_EXEC_FORM = """\
#!/bin/bash
jq -r '.tool_name' <<< "$1"
"""

_PY_SHELL_TRUE_VARIABLE_BUILT_ELSEWHERE = """\
import subprocess

def run(branch_name):
    cmd = f"git checkout {branch_name}"
    subprocess.run(cmd, shell=True)
"""

_PY_SHELL_TRUE_VARIABLE_HOLDING_LITERAL = """\
import subprocess

def run():
    cmd = "git status"
    subprocess.run(cmd, shell=True, timeout=5)
"""

_SH_DASH_C_UNSAFE = """\
#!/bin/bash
branch="$1"
bash -c "git checkout $branch"
"""


def test_dimension5_python_fstring_shell_true_fails():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_SHELL_TRUE_FSTRING)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_literal_shell_true_passes():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_SHELL_TRUE_LITERAL)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_PASSED


def test_dimension5_python_argv_list_form_passes():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_ARGV_LIST_FORM)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_PASSED


def test_dimension5_python_os_system_concat_fails():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_OS_SYSTEM_CONCAT)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_tolerates_unbalanced_parens():
    # Truncated/malformed source: the call's closing paren never appears,
    # so this text does not parse as valid Python at all -- exercises the
    # regex-based fallback path (ast.parse fails), not the AST path.
    # _balanced_span must fall back to "rest of text" instead of raising.
    text = 'import subprocess\nsubprocess.run(f"echo {x}", shell=True'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_not_applicable_no_subprocess_call():
    results = cgs.check_gate_shape(Path("hook.py"), "x = 1\n")
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension5_python_unspaced_percent_formatting_fails():
    # An adversarial review round found the old regex-marker scan
    # required spaces around %/+ (" % ", " + "), so compact-style
    # interpolation with no surrounding spaces slipped through as a false
    # PASS. The AST path has no such spacing dependency: a BinOp is a
    # BinOp regardless of source formatting.
    text = 'import os\ndef run(path):\n    os.system("rm -rf %s"%path)\n'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_shell_true_with_spaces_around_equals_fails():
    # An adversarial review round found the old text scan did an exact
    # substring match for the literal "shell=True", missing formatting
    # variants like "shell = True". AST-based keyword lookup is
    # formatting-independent.
    text = (
        'import subprocess\n'
        'def run(target):\n'
        '    subprocess.run(f"rm -rf {target}", shell = True)\n'
    )
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_shell_equals_one_fails():
    # An adversarial review round found "shell=1" (a truthy non-True
    # constant) was invisible to the old "shell=True" substring check --
    # combined here with an interpolated command so a PASS would mean
    # the shell=1 form was never even recognized as shell execution at
    # all (a literal command argument would legitimately PASS regardless).
    text = 'import subprocess\ndef run(cmd):\n    subprocess.run(f"{cmd}", shell=1)\n'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_paren_inside_string_literal_no_longer_hides_shell_true():
    # An adversarial review round found _balanced_span counts every '('/
    # ')' character in raw text, so a ')' embedded inside a string-literal
    # argument truncated the scanned span before the real 'shell=True'
    # keyword -- silently hiding a real shell-injection call. A real AST
    # parse has no such blind spot: string-literal contents are never
    # mistaken for syntax.
    text = (
        'import subprocess\n'
        'def run(user_input):\n'
        '    subprocess.run("echo )" + user_input, shell=True)\n'
    )
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_no_positional_arg_fails():
    text = 'import subprocess\nsubprocess.run(shell=True)\n'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_argv_tuple_form_passes():
    text = 'import subprocess\nsubprocess.run(("git", "status"), shell=True, timeout=5)\n'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_PASSED


def test_dimension5_python_fallback_not_applicable_no_calls():
    text = "def broken(:\n    pass\n"
    result = cgs._check_unsafe_interpolation_python_fallback(text)
    assert result.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension5_python_fallback_bare_identifier_fails():
    text = (
        'import subprocess\n'
        'def run(cmd):\n'
        '    subprocess.run(cmd, shell=True)\n'
        'x = (\n'
    )
    result = cgs._check_unsafe_interpolation_python_fallback(text)
    assert result.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_fallback_continues_past_non_shell_call_to_pass():
    # Malformed Python (a trailing syntax error keeps ast.parse from
    # succeeding) exercising the fallback's own "continue" path for a
    # non-shell call, then falling through to PASS for a literal
    # shell=True call.
    text = (
        'import subprocess\n'
        'subprocess.run(["ls"])\n'
        'subprocess.run("echo hi", shell=True)\n'
        'x = (\n'
    )
    result = cgs._check_unsafe_interpolation_python_fallback(text)
    assert result.verdict == cgs.VERDICT_PASSED


def test_dimension5_shell_eval_with_variable_fails():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_EVAL_UNSAFE)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_shell_dash_c_brace_expansion_variable_fails():
    # An adversarial review round found \$\w+ misses brace-expansion
    # syntax ${var} (the '{' immediately after '$' is not a word
    # character), so bash -c "...${var}..." was invisible.
    text = '#!/bin/bash\nbranch="$1"\nbash -c "git checkout ${branch}"\n'
    results = cgs.check_gate_shape(Path("hook.sh"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_shell_exec_form_passes():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_SAFE_EXEC_FORM)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_PASSED


def test_dimension5_python_variable_built_from_interpolation_elsewhere_fails():
    # An adversarial review round's exact bypass example: the unsafe
    # f-string is assigned to a variable one line before the shell=True
    # call, invisible to a scan of the call site alone. The command
    # argument is a bare identifier, not a literal or an argv list, so
    # this is now graded FAIL rather than silently PASS.
    results = cgs.check_gate_shape(Path("hook.py"), _PY_SHELL_TRUE_VARIABLE_BUILT_ELSEWHERE)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_variable_holding_literal_also_fails():
    # Named trade-off (see check_gate_shape.py's own module docstring):
    # this script is actually safe (cmd is a hardcoded literal with no
    # interpolation), but the call site alone cannot distinguish it from
    # the unsafe case above -- both are graded FAIL, a deliberate
    # fail-closed choice, not a bug this test is pinning down as correct
    # behavior to keep it from silently flipping back to a fail-open PASS.
    results = cgs.check_gate_shape(Path("hook.py"), _PY_SHELL_TRUE_VARIABLE_HOLDING_LITERAL)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_shell_dash_c_with_variable_fails():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_DASH_C_UNSAFE)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


# --- dimension 6b: internal subprocess/network timeout -------------------

_PY_SUBPROCESS_NO_TIMEOUT = """\
import subprocess

def run():
    subprocess.run(["git", "status"])
"""

_PY_REQUESTS_NO_TIMEOUT = """\
import requests

def check(url):
    requests.get(url)
"""

_SH_CURL_NO_TIMEOUT = """\
#!/bin/bash
curl -sS "https://example.com/api"
"""

_SH_CURL_WITH_TIMEOUT = """\
#!/bin/bash
curl -sS --max-time 10 "https://example.com/api"
"""

_SH_WGET_NO_TIMEOUT = """\
#!/bin/bash
wget "https://example.com/file"
"""


def test_dimension6b_python_subprocess_missing_timeout_fails():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_SUBPROCESS_NO_TIMEOUT)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_FAILED


def test_dimension6b_python_requests_missing_timeout_fails():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_REQUESTS_NO_TIMEOUT)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_FAILED


def test_dimension6b_python_with_timeout_passes():
    results = cgs.check_gate_shape(Path("hook.py"), _PY_SHELL_TRUE_LITERAL)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_PASSED


def test_dimension6b_python_not_applicable_no_calls():
    results = cgs.check_gate_shape(Path("hook.py"), "x = 1\n")
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension6b_python_timeout_word_in_unrelated_string_still_fails():
    # An adversarial review round found the old check was a bare
    # substring search for "timeout" over the whole call span, so the
    # word appearing inside an unrelated string literal (a filename here)
    # falsely satisfied it even with no real timeout= keyword at all. The
    # AST path checks for an actual timeout= keyword argument.
    text = 'import subprocess\nsubprocess.run(["curl", "-o", "/tmp/timeout_backup.txt"])\n'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_FAILED


def test_dimension6b_shell_curl_missing_timeout_fails():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_CURL_NO_TIMEOUT)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_FAILED


def test_dimension6b_shell_curl_with_timeout_passes():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_CURL_WITH_TIMEOUT)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_PASSED


def test_dimension6b_shell_wget_missing_timeout_fails():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_WGET_NO_TIMEOUT)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_FAILED


def test_dimension6b_shell_not_applicable_no_network_call():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_SAFE_EXEC_FORM)
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension6b_python_fallback_not_applicable_no_calls():
    text = "def broken(:\n    pass\n"
    result = cgs._check_timeout_internal_python_fallback(text)
    assert result.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension6b_python_fallback_passes_with_timeout():
    text = (
        'import subprocess\n'
        'subprocess.run("echo hi", timeout=5)\n'
        'x = (\n'
    )
    result = cgs._check_timeout_internal_python_fallback(text)
    assert result.verdict == cgs.VERDICT_PASSED


# --- dimension 6a: invocation-level timeout (hooks.json wiring) ---------


def test_dimension6a_not_applicable_without_hooks_json():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_GOOD_DENY)
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension6a_passes_with_numeric_timeout(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "hooks/check-bash-safety.sh", "timeout": 30}
                    ],
                }
            ]
        }
    }), encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_PASSED


def test_dimension6a_fails_when_timeout_is_json_boolean_true(tmp_path):
    # An adversarial review round found isinstance(True, (int, float)) is
    # True in Python (bool is an int subtype), so a hooks.json entry with
    # "timeout": true was silently credited as a valid numeric timeout.
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "hooks/check-bash-safety.sh", "timeout": True}
                    ],
                }
            ]
        }
    }), encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_FAILED


def test_dimension6a_fails_when_entry_has_no_timeout(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "hooks/check-bash-safety.sh"}
                    ],
                }
            ]
        }
    }), encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_FAILED


def test_dimension6a_not_applicable_no_matching_entry(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({
        "hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [
            {"type": "command", "command": "hooks/other.sh", "timeout": 10}
        ]}]}
    }), encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension6a_indeterminate_on_malformed_json(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text("{not valid json", encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_INDETERMINATE


def test_dimension6a_not_applicable_hooks_key_not_a_dict(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({"hooks": "not-a-dict"}), encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension6a_tolerates_event_entries_not_a_list(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({"hooks": {"PreToolUse": "not-a-list"}}), encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension6a_tolerates_non_dict_hook_entry(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [123, "not-a-dict"]}]}
    }), encoding="utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_NOT_APPLICABLE


# --- language detection ---------------------------------------------------


def test_shebang_python_detected_without_py_suffix():
    text = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"
    results = cgs.check_gate_shape(Path("hook"), text)
    # Python-only dimension 6b check ran (not the shell curl/wget one):
    d6b = _result(results, "6b")
    assert d6b.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_empty_text_is_treated_as_shell():
    results = cgs.check_gate_shape(Path("hook"), "")
    d1 = _result(results, "1")
    assert d1.verdict == cgs.VERDICT_NOT_APPLICABLE


# --- format_report / main (CLI) -------------------------------------------


def test_format_report_includes_every_dimension_marker():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_GOOD_DENY)
    report = cgs.format_report(results)
    for dimension in ("1", "2", "3", "4", "5", "6a", "6b"):
        assert f"dimension {dimension}" in report


def test_main_returns_zero_on_all_pass_or_na(tmp_path, capsys):
    script = tmp_path / "hook.sh"
    script.write_text(_SH_GOOD_DENY, encoding="utf-8")
    (tmp_path / "test_hook.sh").write_text("# test\n", encoding="utf-8")
    exit_code = cgs.main([str(script)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "dimension 1" in out


def test_main_returns_one_on_any_fail(tmp_path):
    script = tmp_path / "hook.sh"
    script.write_text(_SH_ADVISORY_ONLY_DENY, encoding="utf-8")
    exit_code = cgs.main([str(script)])
    assert exit_code == 1


def test_main_returns_two_on_unreadable_script(tmp_path):
    exit_code = cgs.main([str(tmp_path / "does-not-exist.sh")])
    assert exit_code == 2


def test_main_returns_two_on_non_utf8_script(tmp_path, capsys):
    # UnicodeDecodeError is a ValueError subclass, not an OSError -- an
    # earlier version only caught OSError here and crashed uncaught on
    # invalid UTF-8 input (an adversarial review round found this),
    # contradicting this module's own docstring claim that malformed input
    # never crashes it.
    script = tmp_path / "hook.sh"
    script.write_bytes(b"#!/bin/bash\n\xff\xfe not valid utf-8\n")
    exit_code = cgs.main([str(script)])
    assert exit_code == 2
    assert "error:" in capsys.readouterr().err


def test_dimension6a_indeterminate_on_non_utf8_hooks_json(tmp_path):
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_bytes(b"\xff\xfe not valid utf-8")
    results = cgs.check_gate_shape(
        Path("hooks/check-bash-safety.sh"), _SH_GOOD_DENY, hooks_json
    )
    d6a = _result(results, "6a")
    assert d6a.verdict == cgs.VERDICT_INDETERMINATE


def test_main_accepts_hooks_json_flag(tmp_path):
    script = tmp_path / "hook.sh"
    script.write_text(_SH_GOOD_DENY, encoding="utf-8")
    hooks_json = tmp_path / "hooks.json"
    hooks_json.write_text(json.dumps({
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": str(script), "timeout": 30}
        ]}]}
    }), encoding="utf-8")
    (tmp_path / "test_hook.sh").write_text("# test\n", encoding="utf-8")
    exit_code = cgs.main([str(script), "--hooks-json", str(hooks_json)])
    assert exit_code == 0

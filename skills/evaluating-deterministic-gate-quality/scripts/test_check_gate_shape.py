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


# --- dimension 3: self-revalidation (heuristic) --------------------------


def test_dimension3_passes_on_tool_name_read_and_compare():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_GOOD_DENY)
    d3 = _result(results, "3")
    assert d3.verdict == cgs.VERDICT_PASSED


def test_dimension3_indeterminate_never_fail_when_absent():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_NO_DENY_AT_ALL)
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
    # Truncated/malformed source: the call's closing paren never appears.
    # _balanced_span must fall back to "rest of text" instead of raising.
    text = 'import subprocess\nsubprocess.run(f"echo {x}", shell=True'
    results = cgs.check_gate_shape(Path("hook.py"), text)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_python_not_applicable_no_subprocess_call():
    results = cgs.check_gate_shape(Path("hook.py"), "x = 1\n")
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_NOT_APPLICABLE


def test_dimension5_shell_eval_with_variable_fails():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_EVAL_UNSAFE)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_FAILED


def test_dimension5_shell_exec_form_passes():
    results = cgs.check_gate_shape(Path("hook.sh"), _SH_SAFE_EXEC_FORM)
    d5 = _result(results, "5")
    assert d5.verdict == cgs.VERDICT_PASSED


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

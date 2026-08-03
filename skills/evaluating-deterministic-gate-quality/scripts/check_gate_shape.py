"""Deterministic shape checker for an agent-harness hook subprocess gate.

Mechanically grades a scoped subset of `references/dimensions.md`'s own
"Deterministic-shape checks (1-6)" against a target hook script -- the
deferred item `metadata/gitapex.yaml`'s lifecycle note named ("a bundled
deterministic shape-checker") and issue #587 closes. Scoped deliberately
to Domain 2 (agent-harness hook subprocess, Claude-Code-style
PreToolUse/PostToolUse/Stop/SessionStart/UserPromptSubmit) rather than
attempting all four realization domains at once:

  - It is the domain with the single best-documented, most concrete deny-
    signal contract available to ground a mechanical rule in: Claude
    Code's own `hookSpecificOutput.permissionDecision` field and its
    exit-code semantics (exit 2 blocks and feeds stderr back to Claude;
    exit 0 plus `permissionDecision: "deny"` JSON also blocks; any other
    non-zero exit is a non-blocking notice only), per
    <https://code.claude.com/docs/en/hooks> (fetched 2026-08-03).
  - It is the domain this repository's own `hooks/` directory has the
    most real fixture material for.

Domain 1 (git hook), Domain 3 (CI job step), and Domain 4 (MCP server
subprocess) are explicitly OUT OF SCOPE for this checker -- named here
rather than silently assumed covered. Each would need its own mechanical
rule grounded in that domain's own primary source (branch-protection API
semantics for Domain 3's dimension 1, for instance) before this checker
could honestly claim it; see `references/dimensions.md`'s own per-domain
notes under each dimension for what a future extension would need.

Dimensions covered, and how (dimension numbers per `references/
dimensions.md`):

  1. Deny-path non-bypassable -- the script's only recognized deny path
     must be exit code 2 (mechanism ``exit-2``) or exit 0 plus
     ``hookSpecificOutput.permissionDecision: "deny"`` JSON on stdout
     (mechanism ``deny-json``). A script whose only apparent error path is
     a generic non-zero exit other than 2, with no deny JSON anywhere,
     FAILs: Claude Code treats that as a non-blocking notice, not a block,
     per the primary source above. A script with no apparent error/deny
     path at all is graded not_applicable (nothing here suggests this
     script means to ever deny).
  2. Dual-signal deny -- whichever mechanism dimension 1 found, does the
     deny path also carry a non-empty human-readable reason (non-empty
     text written to stderr on the ``exit-2`` path; a non-empty
     ``permissionDecisionReason`` on the ``deny-json`` path)? Only graded
     when dimension 1 found a mechanism to check -- not_applicable
     otherwise (there is no deny path to make dual-signal).
  3. Self-revalidation (heuristic, explicitly not proof) -- does the
     script itself read a tool-identifying field (``tool_name``) from its
     own hook-input JSON and compare it, rather than trusting the
     `hooks.json` matcher alone to have already selected correctly? Like
     `evals/scripts/check_dimension_coverage.py`'s own coverage heuristic,
     this is citation-based pattern matching, not semantic understanding:
     a script can genuinely self-revalidate through a shape this checker
     does not recognize, or reference the field without actually gating on
     it. Absence of the pattern is therefore always reported
     ``indeterminate``, never ``fail`` -- SKILL.md's own Stop boundary
     ("never claim a violation the reviewed artifact does not actually
     show ... a dimension that cannot be assessed ... is reported as
     such") applies reflexively to this checker's own output, not only to
     a human/agent review using it.
  4. A bundled test exists beside the gate -- a sibling file in the same
     directory whose name suggests it tests this script (a
     ``test_``/``test-`` prefix or ``_test`` suffix containing this
     script's own normalized stem), and is non-empty. Domain-agnostic;
     the one fully mechanical, no-heuristics dimension here.
  5. No unsafe shell/command interpolation -- Python: a
     ``subprocess.*``/``os.system``/``os.popen`` call whose command
     argument is built by string interpolation (an f-string, ``%``
     formatting, ``.format(``, or ``+`` concatenation) rather than passed
     as a literal or an argv list. Shell scripts: ``eval`` combined with a
     ``$`` variable reference on the same logical span -- the canonical
     shell-injection shape. A heuristic static scan, not a full parser;
     see the paired test file for concrete cases it catches and misses.
  6. Timeout/budget set explicitly -- two independent sub-checks, reported
     separately since they grade different things:
       6a. invocation-level bound: read from a supplied ``--hooks-json``
           file's own matching entry's ``timeout`` field. Reported
           not_applicable when no ``--hooks-json`` is given -- the script
           alone cannot establish this, matching dimensions.md's own
           "grade the surrounding invocation, not the hook script" note.
       6b. internal bound: any subprocess/network call *inside* the script
           (Python: ``subprocess.*``, ``urlopen``, ``requests.*``; shell:
           ``curl``/``wget``) carries its own explicit timeout
           kwarg/flag. not_applicable when the script makes no such call.

Read-only: reads the target script (and, if supplied, a `hooks.json`)
only. No writes, no network, no subprocess execution of the target gate --
this checker performs static text analysis exclusively; it never runs the
gate it is grading. Live-testing a gate's actual runtime behavior
(dimension 10) is the reviewing skill's own Procedure step 6 and Stop
boundary, under its own sandboxing discipline -- a static shape checker is
not that, and does not attempt to be.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

VERDICT_PASSED = "pass"
VERDICT_FAILED = "fail"
VERDICT_NOT_APPLICABLE = "not_applicable"
VERDICT_INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class CheckResult:
    dimension: str
    name: str
    verdict: str
    evidence: str


# --- language detection ------------------------------------------------

_PYTHON_SUFFIXES = frozenset({".py"})


def _is_python(script_path: Path, text: str) -> bool:
    if script_path.suffix in _PYTHON_SUFFIXES:
        return True
    if script_path.suffix == ".sh":
        return False
    first_line = text.splitlines()[0] if text else ""
    return first_line.startswith("#!") and "python" in first_line


# --- dimension 1 / 2: deny-path mechanism and dual-signal ---------------

_PY_EXIT_2_RE = re.compile(r"\b(?:sys\.exit|exit|raise\s+SystemExit)\s*\(\s*2\s*\)")
_PY_NONZERO_NONTWO_EXIT_RE = re.compile(
    r"\b(?:sys\.exit|exit|raise\s+SystemExit)\s*\(\s*(?!0\s*\)|2\s*\))\d+\s*\)"
)
_SH_EXIT_2_RE = re.compile(r"\bexit\s+2\b")
_SH_NONZERO_NONTWO_EXIT_RE = re.compile(r"\bexit\s+(?!0\b|2\b)\d+\b")
_DENY_JSON_RE = re.compile(r'"?permissionDecision"?\s*:\s*"deny"', re.IGNORECASE)
_DENY_REASON_RE = re.compile(r'"?permissionDecisionReason"?\s*:\s*"([^"]*)"')

# Same-line echo/printf with a quoted string, redirected to stderr -- e.g.
# `echo "Destructive command blocked" >&2`.
_SH_ECHO_STDERR_RE = re.compile(
    r"(?:echo|printf)\b[^\n]*(?:'[^'\n]+'|\"[^\"\n]+\")[^\n]*>&2"
)
# jq's `--arg name "$value"` idiom building a message variable, then piped
# or redirected to stderr within a bounded distance -- e.g. this
# repository's own hooks/check-bash-safety.sh: `jq -n --arg msg "$reason"
# '{"hookSpecificOutput": ...} ' >&2`. Distinct from the same-line pattern
# above since the `>&2` typically lands on a different line of the same jq
# invocation. The window is generous (2000 chars) since the jq filter
# between `--arg` and `>&2` typically *is* the human-readable message
# itself -- hooks/check-template-overwrite.sh's own real message runs to
# ~420 chars, and truncating it here would misgrade a genuinely detailed
# reason as if it were missing one.
_SH_JQ_ARG_STDERR_RE = re.compile(r'--arg\s+\w+\s+"\$\w+"[\s\S]{0,2000}?>&2')


def _check_deny_mechanism(text: str, is_python: bool) -> CheckResult:
    has_exit_2 = bool((_PY_EXIT_2_RE if is_python else _SH_EXIT_2_RE).search(text))
    has_deny_json = bool(_DENY_JSON_RE.search(text))
    has_nonzero_nontwo = bool(
        (_PY_NONZERO_NONTWO_EXIT_RE if is_python else _SH_NONZERO_NONTWO_EXIT_RE).search(text)
    )
    if has_exit_2 or has_deny_json:
        mechanism = []
        if has_exit_2:
            mechanism.append("exit code 2")
        if has_deny_json:
            mechanism.append('permissionDecision: "deny" JSON')
        return CheckResult(
            "1", "Deny-path non-bypassable", VERDICT_PASSED,
            f"found recognized deny mechanism: {', '.join(mechanism)}",
        )
    if has_nonzero_nontwo:
        return CheckResult(
            "1", "Deny-path non-bypassable", VERDICT_FAILED,
            "found a non-zero exit path other than 2, and no "
            'permissionDecision: "deny" JSON -- Claude Code treats any exit '
            "code other than 2 as a non-blocking notice, not a block "
            "(https://code.claude.com/docs/en/hooks)",
        )
    return CheckResult(
        "1", "Deny-path non-bypassable", VERDICT_NOT_APPLICABLE,
        "no exit-2, deny-JSON, or other non-zero exit path found -- "
        "nothing here suggests this script means to ever deny",
    )


_PY_STDERR_WRITE_CALL_RE = re.compile(r"\bsys\.stderr\.write\s*\(")
_PY_PRINT_CALL_RE = re.compile(r"\bprint\s*\(")
_QUOTED_STRING_RE = re.compile(r"f?(?:'[^'\n]+'|\"[^\"\n]+\")")


def _has_stderr_message_python(text: str) -> bool:
    for match in _PY_STDERR_WRITE_CALL_RE.finditer(text):
        span = _balanced_span(text, match.end() - 1)
        if _QUOTED_STRING_RE.search(span):
            return True
    for match in _PY_PRINT_CALL_RE.finditer(text):
        span = _balanced_span(text, match.end() - 1)
        if "sys.stderr" in span and _QUOTED_STRING_RE.search(span):
            return True
    return False


def _has_stderr_message_shell(text: str) -> bool:
    return bool(_SH_ECHO_STDERR_RE.search(text) or _SH_JQ_ARG_STDERR_RE.search(text))


def _check_dual_signal(text: str, is_python: bool, mechanism_result: CheckResult) -> CheckResult:
    if mechanism_result.verdict != VERDICT_PASSED:
        return CheckResult(
            "2", "Dual-signal deny", VERDICT_NOT_APPLICABLE,
            "dimension 1 found no recognized deny mechanism to grade for a "
            "human-readable companion message",
        )
    reason_match = _DENY_REASON_RE.search(text)
    has_reason = bool(reason_match and reason_match.group(1).strip())
    has_stderr_text = (
        _has_stderr_message_python(text) if is_python else _has_stderr_message_shell(text)
    )
    if has_reason or has_stderr_text:
        channel = "permissionDecisionReason" if has_reason else "a non-empty stderr message"
        return CheckResult("2", "Dual-signal deny", VERDICT_PASSED, f"found {channel} alongside the deny signal")
    return CheckResult(
        "2", "Dual-signal deny", VERDICT_FAILED,
        "deny mechanism found, but no non-empty permissionDecisionReason "
        "and no non-empty stderr message alongside it",
    )


# --- dimension 3: self-revalidation (heuristic) -------------------------

_TOOL_NAME_REF_RE = re.compile(r"tool_name")
_TOOL_NAME_COMPARISON_RE = re.compile(r'tool_name["\']?\s*(?:!=|==)|["\']?\s*(?:!=|==)\s*["\']?\s*\$?tool_name')


def _check_self_revalidation(text: str) -> CheckResult:
    if _TOOL_NAME_REF_RE.search(text) and _TOOL_NAME_COMPARISON_RE.search(text):
        return CheckResult(
            "3", "Self-revalidation (heuristic)", VERDICT_PASSED,
            "found a tool_name read compared with !=/== -- re-checks the "
            "matcher-relevant field itself rather than trusting hooks.json "
            "alone",
        )
    return CheckResult(
        "3", "Self-revalidation (heuristic)", VERDICT_INDETERMINATE,
        "no tool_name read-and-compare pattern found -- this script may "
        "self-revalidate through a different field or shape this heuristic "
        "does not recognize; confirm by direct inspection rather than "
        "treating this as a failure",
    )


# --- dimension 4: bundled test exists ------------------------------------

_TEST_NAME_RE = re.compile(r"^test[-_].+|.+_test\.(py|sh)$")


def _find_sibling_test(script_path: Path) -> Path | None:
    directory = script_path.parent
    if not directory.is_dir():
        return None
    stem_norm = re.sub(r"[-.]", "_", script_path.stem)
    for candidate in sorted(directory.iterdir()):
        if candidate == script_path or not candidate.is_file():
            continue
        if not _TEST_NAME_RE.match(candidate.name):
            continue
        candidate_norm = re.sub(r"[-.]", "_", candidate.stem)
        candidate_norm = re.sub(r"^test_|_test$", "", candidate_norm)
        if stem_norm in candidate_norm or candidate_norm in stem_norm:
            try:
                if candidate.stat().st_size > 0:
                    return candidate
            except OSError:
                continue
    return None


def _check_bundled_test(script_path: Path) -> CheckResult:
    sibling = _find_sibling_test(script_path)
    if sibling is not None:
        return CheckResult(
            "4", "Bundled test exists", VERDICT_PASSED,
            f"found non-empty sibling test file: {sibling.name}",
        )
    return CheckResult(
        "4", "Bundled test exists", VERDICT_FAILED,
        f"no non-empty sibling test file matching this script's own "
        f"normalized stem found in {script_path.parent}",
    )


# --- dimension 5: unsafe shell/command interpolation ---------------------

_PY_SHELL_CALL_RE = re.compile(
    r"\b(subprocess\.(?:run|call|check_call|check_output|Popen)|os\.system|os\.popen)\s*\("
)
_INTERPOLATION_MARKERS = ("f\"", "f'", ".format(", " % ", " + ")


def _balanced_span(text: str, open_paren_index: int) -> str:
    depth = 0
    for i in range(open_paren_index, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren_index : i + 1]
    return text[open_paren_index:]


def _check_unsafe_interpolation_python(text: str) -> CheckResult:
    matches = list(_PY_SHELL_CALL_RE.finditer(text))
    if not matches:
        return CheckResult(
            "5", "No unsafe shell interpolation", VERDICT_NOT_APPLICABLE,
            "no subprocess/os.system/os.popen call found in this script",
        )
    for match in matches:
        callee = match.group(1)
        span = _balanced_span(text, match.end() - 1)
        is_shell = callee in ("os.system", "os.popen") or "shell=True" in span
        if not is_shell:
            continue
        if any(marker in span for marker in _INTERPOLATION_MARKERS):
            return CheckResult(
                "5", "No unsafe shell interpolation", VERDICT_FAILED,
                f"found {callee}(...) with shell execution and an "
                "interpolated (not literal) command string",
            )
    return CheckResult(
        "5", "No unsafe shell interpolation", VERDICT_PASSED,
        "every shell/subprocess call found uses a literal command string "
        "or an argv list, not string interpolation",
    )


_SH_EVAL_WITH_VAR_RE = re.compile(r"\beval\b[^\n]*\$")


def _check_unsafe_interpolation_shell(text: str) -> CheckResult:
    if _SH_EVAL_WITH_VAR_RE.search(text):
        return CheckResult(
            "5", "No unsafe shell interpolation", VERDICT_FAILED,
            "found eval combined with a $variable reference on the same "
            "line -- the canonical shell-injection shape",
        )
    return CheckResult(
        "5", "No unsafe shell interpolation", VERDICT_PASSED,
        "no eval-plus-variable-interpolation pattern found",
    )


# --- dimension 6b: internal subprocess/network timeout -------------------

_PY_TIMEOUT_CALL_RE = re.compile(
    r"\b(subprocess\.(?:run|call|check_call|check_output|Popen)|"
    r"urllib\.request\.urlopen|urlopen|requests\.(?:get|post|put|delete|request))\s*\("
)


def _check_timeout_internal_python(text: str) -> CheckResult:
    matches = list(_PY_TIMEOUT_CALL_RE.finditer(text))
    if not matches:
        return CheckResult(
            "6b", "Internal subprocess/network timeout", VERDICT_NOT_APPLICABLE,
            "no subprocess/urlopen/requests call found in this script",
        )
    missing = []
    for match in matches:
        span = _balanced_span(text, match.end() - 1)
        if "timeout" not in span:
            missing.append(match.group(1))
    if missing:
        return CheckResult(
            "6b", "Internal subprocess/network timeout", VERDICT_FAILED,
            f"call(s) with no explicit timeout=...: {', '.join(sorted(set(missing)))}",
        )
    return CheckResult(
        "6b", "Internal subprocess/network timeout", VERDICT_PASSED,
        "every subprocess/network call found sets an explicit timeout",
    )


_SH_NETWORK_CALL_RE = re.compile(r"\b(curl|wget)\b[^\n]*")
_CURL_TIMEOUT_FLAG_RE = re.compile(r"--max-time\b|(?<!\S)-m\s")
_WGET_TIMEOUT_FLAG_RE = re.compile(r"--timeout\b")


def _check_timeout_internal_shell(text: str) -> CheckResult:
    matches = list(_SH_NETWORK_CALL_RE.finditer(text))
    if not matches:
        return CheckResult(
            "6b", "Internal subprocess/network timeout", VERDICT_NOT_APPLICABLE,
            "no curl/wget call found in this script",
        )
    missing = []
    for match in matches:
        line = match.group(0)
        tool = match.group(1)
        flag_re = _CURL_TIMEOUT_FLAG_RE if tool == "curl" else _WGET_TIMEOUT_FLAG_RE
        if not flag_re.search(line):
            missing.append(tool)
    if missing:
        return CheckResult(
            "6b", "Internal subprocess/network timeout", VERDICT_FAILED,
            f"{', '.join(sorted(set(missing)))} call(s) with no explicit timeout flag",
        )
    return CheckResult(
        "6b", "Internal subprocess/network timeout", VERDICT_PASSED,
        "every curl/wget call found sets an explicit timeout flag",
    )


# --- dimension 6a: invocation-level timeout (hooks.json wiring) ----------


def _check_timeout_wiring(script_path: Path, hooks_json_path: Path | None) -> CheckResult:
    if hooks_json_path is None:
        return CheckResult(
            "6a", "Invocation-level timeout (hooks.json wiring)", VERDICT_NOT_APPLICABLE,
            "no --hooks-json supplied -- the script alone cannot establish "
            "this; grade the surrounding invocation separately",
        )
    try:
        data = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult(
            "6a", "Invocation-level timeout (hooks.json wiring)", VERDICT_INDETERMINATE,
            f"could not read/parse {hooks_json_path}: {exc}",
        )
    basename = script_path.name
    found_entries = []
    hooks_section = data.get("hooks") if isinstance(data, dict) else None
    if isinstance(hooks_section, dict):
        for event_entries in hooks_section.values():
            if not isinstance(event_entries, list):
                continue
            for matcher_entry in event_entries:
                for hook_entry in matcher_entry.get("hooks", []) if isinstance(matcher_entry, dict) else []:
                    if not isinstance(hook_entry, dict):
                        continue
                    command = hook_entry.get("command", "")
                    if isinstance(command, str) and basename in command:
                        found_entries.append(hook_entry)
    if not found_entries:
        return CheckResult(
            "6a", "Invocation-level timeout (hooks.json wiring)", VERDICT_NOT_APPLICABLE,
            f"no hooks.json entry references {basename!r}",
        )
    missing = [e for e in found_entries if not isinstance(e.get("timeout"), (int, float)) or e.get("timeout") is False]
    if missing:
        return CheckResult(
            "6a", "Invocation-level timeout (hooks.json wiring)", VERDICT_FAILED,
            f"{len(missing)} matching hooks.json entry/entries for {basename!r} "
            "with no numeric timeout field",
        )
    return CheckResult(
        "6a", "Invocation-level timeout (hooks.json wiring)", VERDICT_PASSED,
        f"every matching hooks.json entry for {basename!r} sets a numeric timeout",
    )


# --- public entry point --------------------------------------------------


def check_gate_shape(
    script_path: Path, text: str, hooks_json_path: Path | None = None
) -> list[CheckResult]:
    """Run every mechanical dimension-1-6 check this checker implements
    against ``text`` (the already-read contents of ``script_path``,
    ``script_path`` itself only used for its suffix/name and for locating a
    sibling test file). Returns one ``CheckResult`` per sub-check, in
    dimension order; never raises on the *content* of ``text`` -- a
    hostile or malformed script is data to scan, not a reason to except.
    """
    is_python = _is_python(script_path, text)
    mechanism_result = _check_deny_mechanism(text, is_python)
    results = [
        mechanism_result,
        _check_dual_signal(text, is_python, mechanism_result),
        _check_self_revalidation(text),
        _check_bundled_test(script_path),
    ]
    if is_python:
        results.append(_check_unsafe_interpolation_python(text))
        results.append(_check_timeout_internal_python(text))
    else:
        results.append(_check_unsafe_interpolation_shell(text))
        results.append(_check_timeout_internal_shell(text))
    results.append(_check_timeout_wiring(script_path, hooks_json_path))
    return results


def format_report(results: list[CheckResult]) -> str:
    lines = []
    for result in results:
        marker = {
            VERDICT_PASSED: "VERDICT_PASSED", VERDICT_FAILED: "VERDICT_FAILED",
            VERDICT_NOT_APPLICABLE: "N/A ", VERDICT_INDETERMINATE: "IND ",
        }[result.verdict]
        lines.append(f"[{marker}] dimension {result.dimension} ({result.name}): {result.evidence}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mechanically check an agent-harness hook script "
        "against evaluating-deterministic-gate-quality's own "
        "deterministic-shape checks (dimensions 1, 2, 4, 5, 6; dimension "
        "3 as a disclosed heuristic only). Domain-2 (agent-harness hook) "
        "scoped -- see this module's own docstring for what is out of "
        "scope."
    )
    parser.add_argument("script", help="Path to the hook script to check.")
    parser.add_argument(
        "--hooks-json",
        help="Optional path to the hooks.json wiring this script is "
        "registered in, to grade dimension 6a (invocation-level timeout).",
    )
    args = parser.parse_args(argv)
    script_path = Path(args.script)
    try:
        text = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: could not read {script_path}: {exc}", file=sys.stderr)
        return 2
    hooks_json_path = Path(args.hooks_json) if args.hooks_json else None
    results = check_gate_shape(script_path, text, hooks_json_path)
    print(format_report(results))
    return 0 if all(r.verdict in (VERDICT_PASSED, VERDICT_NOT_APPLICABLE) for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

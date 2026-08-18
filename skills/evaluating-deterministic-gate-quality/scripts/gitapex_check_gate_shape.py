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
semantics for Domain 3's shape check 1, for instance) before this checker
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
  2. Dual-signal deny -- whichever mechanism shape check 1 found, does the
     deny path also carry a non-empty human-readable reason (non-empty
     text written to stderr on the ``exit-2`` path; a non-empty
     ``permissionDecisionReason`` on the ``deny-json`` path)? Only graded
     when shape check 1 found a mechanism to check -- not_applicable
     otherwise (there is no deny path to make dual-signal). Python:
     ``sys.stderr.write(...)``/``print(..., file=sys.stderr)`` calls are
     located with a real AST parse when the script parses as valid
     Python, falling back to a text-scan heuristic otherwise.
  3. Self-revalidation (heuristic, explicitly not proof) -- does the
     script itself read a tool-identifying field (``tool_name``) from its
     own hook-input JSON and compare it, rather than trusting the
     `hooks.json` matcher alone to have already selected correctly? Three
     recognized reference shapes: shell variable interpolation
     (``$tool_name``), a quoted dict-key access (``"tool_name"`` /
     ``'tool_name'``), or jq/shell dot-notation (``.tool_name``) -- each
     within a short distance of a ``!=``/``==`` operator. Deliberately
     does not match a bare, unquoted identifier with none of those
     markers, since that shape is indistinguishable from an ordinary
     variable used for something unrelated. Like `evals/scripts/
     gitapex_check_dimension_coverage.py`'s own coverage heuristic, this is
     pattern matching, not semantic understanding: a script can genuinely
     self-revalidate through a shape this checker does not recognize.
     Absence of the pattern is therefore always reported
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
  5. No unsafe shell/command interpolation -- Python: located with a real
     AST parse when the script parses as valid Python (falling back to a
     text-scan heuristic otherwise). A ``subprocess.*``/``os.system``/
     ``os.popen`` call whose ``shell`` keyword is present and not
     literally ``False`` is graded unsafe unless its first positional
     argument is a literal string or an argv list/tuple -- an
     interpolated value (an f-string, ``%``/``+``/``.format(`` build) or
     any other expression (including a bare variable, since the call site
     alone cannot prove it was not built from an interpolated value
     assigned elsewhere in the script) fails closed. Shell scripts:
     ``eval`` combined with a ``$`` variable reference on the same
     logical span, or a ``bash``/``sh -c "..."`` double-quoted string
     with a ``$var``/``${var}`` reference interpolated into it -- both
     the canonical shell-injection shape. A heuristic static scan for the
     shell half (no free parser exists for it here), not a full parser;
     see the paired test file for concrete cases it catches and misses.
  6. Timeout/budget set explicitly -- two independent sub-checks, reported
     separately since they grade different things:
       6a. invocation-level bound: read from a supplied ``--hooks-json``
           file's own matching entry's ``timeout`` field (a real
           number, not the JSON boolean ``true``/``false``, since Python's
           ``bool`` is a subtype of ``int``). Reported not_applicable when
           no ``--hooks-json`` is given -- the script alone cannot
           establish this, matching dimensions.md's own "grade the
           surrounding invocation, not the hook script" note.
       6b. internal bound: any subprocess/network call *inside* the
           script (Python: ``subprocess.*``, ``urlopen``, ``requests.*``,
           located via the same AST-with-fallback approach as shape check 5,
           checking for an actual ``timeout=`` keyword argument rather
           than the substring "timeout" anywhere in the call; shell:
           ``curl``/``wget``) carries its own explicit timeout
           kwarg/flag. not_applicable when the script makes no such call.

Read-only: reads the target script (and, if supplied, a `hooks.json`)
only. No writes, no network, no subprocess execution of the target gate --
this checker performs static analysis exclusively (an AST parse of the
script's own text for the Python-target dimensions above, text/regex
scans elsewhere); it never runs the gate it is grading. Live-testing a
gate's actual runtime behavior (dimension 10) is the reviewing skill's own
Procedure step 6 and Stop boundary, under its own sandboxing discipline --
a static shape checker is not that, and does not attempt to be.

This is a self-contained checker -- no skill in this repository shares a
scripts/ directory with another, so this ships its own copy of small
generic helpers (a CheckResult record, a read-and-report main()) rather
than importing across skill boundaries, the same convention
`skills/drafting-an-adr/scripts/gitapex_check_adr_shape.py` and
`skills/drafting-an-acm-issue/scripts/gitapex_check_acm_present.py` each state
for themselves.

Known limitations, named rather than silently assumed away (an
adversarial review of this checker itself found these):

  - Comments and string literals are not stripped before the Python AST
    walk sees them as such -- a real parse already keeps a `# comment`
    or a docstring from being misread as executable code, closing most of
    the false-positive/false-negative risk a raw text scan carried. It
    does not close all of it: `ast` still faithfully represents a string
    *value* that happens to look like code (e.g. a string constant
    containing the literal text `sys.exit(2)`) as a `Constant`, not as
    the code it resembles, so this checker correctly does NOT execute or
    interpret string contents as instructions -- the residual risk is the
    opposite direction, a human or a documentation string describing
    behavior the surrounding real code does not actually implement, which
    no static analysis of this shape can fully close.
  - The shell-script half of every shape check here (1, 2, 3, 5, 6b) has no
    equivalent free parser to reach for and stays a text/regex scan,
    comment/string-blind as before: a shell comment stating "we
    intentionally do not call exit 2" can still flip shape check 1 to PASS
    with no real deny path. Treat a PASS/FAIL this checker reports for
    shell-script input as a strong hint to verify by direct inspection,
    not a proof, the same discipline shape check 3's own heuristic already
    states explicitly for itself.
  - When Python-target text does not parse as valid Python at all (a
    genuinely malformed or deliberately truncated/adversarial script),
    shape checks 2/5/6b fall back to the same text-scan heuristic this
    checker used before the AST-based rewrite -- lower confidence,
    disclosed via that fallback path's own more conservative behavior,
    not a silent skip.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# The closed vocabulary a per-dimension verdict string is checked against.
VERDICT_PASSED = "pass"
VERDICT_FAILED = "fail"  # the failing half of the pass/fail pair above
VERDICT_NOT_APPLICABLE = "not_applicable"  # the dimension does not apply to this gate
VERDICT_INDETERMINATE = "indeterminate"  # evidence was insufficient to reach pass/fail


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


# --- Python call-site parsing (AST-based, with a regex fallback for text
# that does not parse as valid Python) -------------------------------------


def _dotted_name(node: ast.expr) -> str | None:
    """Return e.g. "subprocess.run"/"os.system"/"sys.stderr" for a Call's
    own func node, or for any other dotted-attribute/bare-name expression
    (used to resolve a keyword argument's value, e.g. ``file=sys.stderr``).
    Returns None for a shape this checker does not resolve to a dotted
    name (a subscript, a call result, a conditional expression, ...)."""
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _parse_python_calls(text: str) -> list[tuple[str, ast.Call]] | None:
    """Return (dotted_name, node) for every ``ast.Call`` in ``text`` whose
    callee resolves to a dotted name, or None if ``text`` does not parse
    as valid Python -- callers fall back to a regex heuristic in that
    case (the same "heuristic, not proof" discipline this module already
    applies elsewhere), rather than crashing or silently skipping."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted_name(node.func)
            if name:
                calls.append((name, node))
    return calls


def _keyword_value(call_node: ast.Call, name: str) -> ast.expr | None:
    for kw in call_node.keywords:
        if kw.arg == name:
            return kw.value
    return None


# --- shape check 1 / 2: deny-path mechanism and dual-signal ---------------

_PY_EXIT_2_RE = re.compile(r"\b(?:sys\.exit|exit|raise\s+SystemExit)\s*\(\s*2\s*\)")
# -?\d+ so a literal `sys.exit(-1)` (still non-blocking to Claude Code,
# same bypass class as a bare `exit(1)`) is recognized rather than missed
# by a \d+-only pattern.
_PY_NONZERO_NONTWO_EXIT_RE = re.compile(r"\b(?:sys\.exit|exit|raise\s+SystemExit)\s*\(\s*(?!0\s*\)|2\s*\))-?\d+\s*\)")
_SH_EXIT_2_RE = re.compile(r"\bexit\s+2\b")
_SH_NONZERO_NONTWO_EXIT_RE = re.compile(r"\bexit\s+(?!0\b|2\b)-?\d+\b")
_DENY_JSON_RE = re.compile(r'"?permissionDecision"?\s*:\s*"deny"', re.IGNORECASE)
_DENY_REASON_RE = re.compile(r'"?permissionDecisionReason"?\s*:\s*"([^"]*)"')


def _check_deny_mechanism(text: str, is_python: bool) -> CheckResult:
    has_exit_2 = bool((_PY_EXIT_2_RE if is_python else _SH_EXIT_2_RE).search(text))
    has_deny_json = bool(_DENY_JSON_RE.search(text))
    has_nonzero_nontwo = bool((_PY_NONZERO_NONTWO_EXIT_RE if is_python else _SH_NONZERO_NONTWO_EXIT_RE).search(text))
    if has_exit_2 or has_deny_json:
        mechanism = []
        if has_exit_2:
            mechanism.append("exit code 2")
        if has_deny_json:
            mechanism.append('permissionDecision: "deny" JSON')
        return CheckResult(
            "1",
            "Deny-path non-bypassable",
            VERDICT_PASSED,
            f"found recognized deny mechanism: {', '.join(mechanism)}",
        )
    if has_nonzero_nontwo:
        return CheckResult(
            "1",
            "Deny-path non-bypassable",
            VERDICT_FAILED,
            "found a non-zero exit path other than 2, and no "
            'permissionDecision: "deny" JSON -- Claude Code treats any exit '
            "code other than 2 as a non-blocking notice, not a block "
            "(https://code.claude.com/docs/en/hooks)",
        )
    return CheckResult(
        "1",
        "Deny-path non-bypassable",
        VERDICT_NOT_APPLICABLE,
        "no exit-2, deny-JSON, or other non-zero exit path found -- "
        "nothing here suggests this script means to ever deny",
    )


_PY_STDERR_WRITE_CALL_RE = re.compile(r"\bsys\.stderr\.write\s*\(")
_PY_PRINT_CALL_RE = re.compile(r"\bprint\s*\(")
_QUOTED_STRING_RE = re.compile(r"f?(?:'[^'\n]+'|\"[^\"\n]+\")")


def _arg_has_text_content(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(node.value.strip())
    return isinstance(node, (ast.JoinedStr, ast.BinOp))


def _has_stderr_message_python_ast(calls: list[tuple[str, ast.Call]]) -> bool:
    for name, node in calls:
        if name == "sys.stderr.write":
            if node.args and _arg_has_text_content(node.args[0]):
                return True
        elif name == "print":
            file_value = _keyword_value(node, "file")
            if (
                file_value is not None
                and _dotted_name(file_value) == "sys.stderr"
                and any(_arg_has_text_content(a) for a in node.args)
            ):
                return True
    return False


def _has_stderr_message_python_fallback(text: str) -> bool:
    for match in _PY_STDERR_WRITE_CALL_RE.finditer(text):
        span = _balanced_span(text, match.end() - 1)
        if _QUOTED_STRING_RE.search(span):
            return True
    for match in _PY_PRINT_CALL_RE.finditer(text):
        span = _balanced_span(text, match.end() - 1)
        if "sys.stderr" in span and _QUOTED_STRING_RE.search(span):
            return True
    return False


def _has_stderr_message_python(text: str) -> bool:
    calls = _parse_python_calls(text)
    if calls is None:
        return _has_stderr_message_python_fallback(text)
    return _has_stderr_message_python_ast(calls)


# Same-line echo/printf with a quoted string, redirected to stderr -- e.g.
# `echo "Destructive command blocked" >&2`. Deliberately NOT one regex
# with two unbounded `[^\n]*` spans around the quote alternation -- an
# adversarial review round measured that shape's match time growing
# quadratically with input length (a single ~800KB adversarial line
# without `>&2` did not finish in 120s), a real denial-of-service against
# this checker itself. This per-line, substring-only scan is linear.
_SH_ECHO_OR_PRINTF_RE = re.compile(r"\b(?:echo|printf)\b")
_QUOTE_CHAR_RE = re.compile(r"['\"]")


def _has_echo_stderr_message(text: str) -> bool:
    for line in text.split("\n"):
        if ">&2" not in line:
            continue
        if _SH_ECHO_OR_PRINTF_RE.search(line) and _QUOTE_CHAR_RE.search(line):
            return True
    return False


# jq's `--arg name "$value"` idiom building a message variable, then piped
# or redirected to stderr within a bounded distance -- e.g. this
# repository's own hooks/check-bash-safety.sh: `jq -n --arg msg "$reason"
# '{"hookSpecificOutput": ...} ' >&2`. Distinct from the same-line pattern
# above since the `>&2` typically lands on a different line of the same jq
# invocation. The window is generous (2000 chars) since the jq filter
# between `--arg` and `>&2` typically *is* the human-readable message
# itself -- hooks/check-template-overwrite.sh's own real message runs to
# ~420 chars, and truncating it here would misgrade a genuinely detailed
# reason as if it were missing one. Bounded (not catastrophic): each
# non-matching `--arg` occurrence costs at most O(2000) before giving up,
# empirically confirmed cheap even at 1.5MB of adversarial input.
_SH_JQ_ARG_STDERR_RE = re.compile(r'--arg\s+\w+\s+"\$\w+"[\s\S]{0,2000}?>&2')


def _has_stderr_message_shell(text: str) -> bool:
    return _has_echo_stderr_message(text) or bool(_SH_JQ_ARG_STDERR_RE.search(text))


def _check_dual_signal(text: str, is_python: bool, mechanism_result: CheckResult) -> CheckResult:
    if mechanism_result.verdict != VERDICT_PASSED:
        return CheckResult(
            "2",
            "Dual-signal deny",
            VERDICT_NOT_APPLICABLE,
            "shape check 1 found no recognized deny mechanism to grade for a human-readable companion message",
        )
    reason_match = _DENY_REASON_RE.search(text)
    has_reason = bool(reason_match and reason_match.group(1).strip())
    has_stderr_text = _has_stderr_message_python(text) if is_python else _has_stderr_message_shell(text)
    if has_reason or has_stderr_text:
        channel = "permissionDecisionReason" if has_reason else "a non-empty stderr message"
        return CheckResult("2", "Dual-signal deny", VERDICT_PASSED, f"found {channel} alongside the deny signal")
    return CheckResult(
        "2",
        "Dual-signal deny",
        VERDICT_FAILED,
        "deny mechanism found, but no non-empty permissionDecisionReason and no non-empty stderr message alongside it",
    )


# --- shape check 3: self-revalidation (heuristic) -------------------------

# Three ways a script might legitimately reference the tool_name field:
# shell variable interpolation ($tool_name, typically inside quotes:
# "$tool_name"), a Python/JSON quoted dict-key access ("tool_name" /
# 'tool_name', e.g. data.get("tool_name")), or jq/shell dot-notation
# (.tool_name). Deliberately does NOT match a bare, unquoted identifier
# tool_name with none of those markers -- that shape is indistinguishable
# from an ordinary Python variable used for something unrelated (e.g.
# get_command_hash(tool_name)), and matching it produced a real false
# PASS an adversarial review round found and this fixes.
_TOOL_NAME_REFERENCE_RE = re.compile(r'\$tool_name\b|["\']tool_name["\']|\.tool_name\b')
_COMPARISON_OP_RE = re.compile(r"!=|==")
_TOOL_NAME_COMPARISON_WINDOW = 30


def _check_self_revalidation(text: str) -> CheckResult:
    for match in _TOOL_NAME_REFERENCE_RE.finditer(text):
        before = text[max(0, match.start() - _TOOL_NAME_COMPARISON_WINDOW) : match.start()]
        after = text[match.end() : match.end() + _TOOL_NAME_COMPARISON_WINDOW]
        if _COMPARISON_OP_RE.search(before) or _COMPARISON_OP_RE.search(after):
            return CheckResult(
                "3",
                "Self-revalidation (heuristic)",
                VERDICT_PASSED,
                "found a tool_name reference ($tool_name / quoted "
                '"tool_name" / .tool_name) within a few characters of '
                "!=/== -- re-checks the matcher-relevant field itself "
                "rather than trusting hooks.json alone",
            )
    return CheckResult(
        "3",
        "Self-revalidation (heuristic)",
        VERDICT_INDETERMINATE,
        "no tool_name read-and-compare pattern found -- this script may "
        "self-revalidate through a different field or shape this heuristic "
        "does not recognize; confirm by direct inspection rather than "
        "treating this as a failure",
    )


# --- shape check 4: bundled test exists ------------------------------------

_TEST_NAME_RE = re.compile(r"^test[-_].+|.+_test\.(py|sh)$")


def _is_better_sibling_match(candidate_norm: str, stem_norm: str, other: str) -> bool:
    """Whether ``other`` (another sibling script's normalized stem) is a
    stronger match for ``candidate_norm`` (a candidate test file's
    normalized stem) than ``stem_norm`` (the script currently being
    checked) is. An exact match always wins over a mere containment
    match, in either length direction -- an earlier version of this rule
    only compared lengths one way (a longer sibling beats a shorter
    script), which let a *longer* script under test wrongly steal a
    *shorter* sibling's own exact-match test file (the reverse bug an
    adversarial review round found). Among containment-only competitors,
    ``other`` wins only when it is itself a proper extension of
    ``stem_norm`` in either length direction (e.g. check_gate ->
    check_gate_v2, or the reverse) -- an unrelated script that merely
    happens to share a substring with the candidate, but is not an
    extension of *this* script's own name, never disqualifies a match
    (the false-negative bug a different adversarial review round found).
    """
    if other == candidate_norm:
        return True
    return (
        (other in candidate_norm or candidate_norm in other)
        and (stem_norm in other or other in stem_norm)
        and other != stem_norm
    )


def _find_sibling_test(script_path: Path) -> Path | None:
    directory = script_path.parent
    try:
        entries = list(directory.iterdir())
    except OSError:
        return None
    stem_norm = re.sub(r"[-.]", "_", script_path.stem)
    # Other real (non-test-named) sibling scripts, used by
    # _is_better_sibling_match above so a loose containment match never
    # lets this script claim credit for a test file that actually names a
    # different, more-specific sibling script.
    other_script_stems = [
        re.sub(r"[-.]", "_", p.stem)
        for p in entries
        if p != script_path and p.is_file() and p.suffix in (".py", ".sh") and not _TEST_NAME_RE.match(p.name)
    ]
    for candidate in sorted(entries, key=lambda p: p.name):
        if candidate == script_path or not candidate.is_file():
            continue
        if not _TEST_NAME_RE.match(candidate.name):
            continue
        candidate_norm = re.sub(r"[-.]", "_", candidate.stem)
        candidate_norm = re.sub(r"^test_|_test$", "", candidate_norm)
        is_exact = candidate_norm == stem_norm
        is_containment = stem_norm in candidate_norm or candidate_norm in stem_norm
        if not is_exact and not is_containment:
            continue
        if (
            is_containment
            and not is_exact
            and any(_is_better_sibling_match(candidate_norm, stem_norm, other) for other in other_script_stems)
        ):
            continue
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
            "4",
            "Bundled test exists",
            VERDICT_PASSED,
            f"found non-empty sibling test file: {sibling.name}",
        )
    return CheckResult(
        "4",
        "Bundled test exists",
        VERDICT_FAILED,
        f"no non-empty sibling test file matching this script's own normalized stem found in {script_path.parent}",
    )


# --- shape check 5: unsafe shell/command interpolation ---------------------

_PY_SHELL_CALLABLE_NAMES = frozenset(
    {
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "os.system",
        "os.popen",
    }
)


def _is_shell_true(call_node: ast.Call) -> bool:
    value = _keyword_value(call_node, "shell")
    if value is None:
        return False
    # Only a literal `shell=False` is treated as not-shell; `shell=True`,
    # `shell=1`, or any other/unresolvable value is treated cautiously as
    # possibly-shell rather than silently assumed safe.
    return not (isinstance(value, ast.Constant) and value.value is False)


def _first_arg_safety(call_node: ast.Call) -> bool | None:
    """True: a literal string or an argv list/tuple. False: interpolated
    or an otherwise unverifiable expression. None: no positional argument
    this checker can inspect at all."""
    if not call_node.args:
        return None
    first = call_node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return True
    return isinstance(first, (ast.List, ast.Tuple))


def _check_unsafe_interpolation_python_ast(calls: list[tuple[str, ast.Call]]) -> CheckResult:
    target_calls = [(name, node) for name, node in calls if name in _PY_SHELL_CALLABLE_NAMES]
    if not target_calls:
        return CheckResult(
            "5",
            "No unsafe shell interpolation",
            VERDICT_NOT_APPLICABLE,
            "no subprocess/os.system/os.popen call found in this script",
        )
    for name, node in target_calls:
        is_shell = name in ("os.system", "os.popen") or _is_shell_true(node)
        if not is_shell:
            continue
        safety = _first_arg_safety(node)
        if safety is True:
            continue
        # The call-site alone cannot prove a bare-identifier/expression
        # command argument (as opposed to a literal string or an argv
        # list) is actually a hardcoded, non-interpolated value -- it
        # could equally be `cmd = f"git checkout {branch_name}"` assigned
        # one line earlier. Rather than silently crediting an
        # unverifiable dynamic command fed to a shell as safe, this is
        # graded FAIL: the same fail-closed choice shape check 1 / dimension 15 make
        # elsewhere in this repository ("an inability to verify is a
        # deny, not an assume-clean"), applied here to a
        # security-relevant static check. The known cost: a script that
        # assigns a genuinely hardcoded literal to a variable and passes
        # that variable to a shell=True call is also flagged -- confirm
        # by direct inspection rather than treating this as certain.
        reason = (
            "no positional command argument this checker can interpret"
            if safety is None
            else "a variable/expression, not a literal string or an argv "
            "list -- cannot verify from this call site alone that it is "
            "not built from untrusted input elsewhere in the script"
        )
        return CheckResult(
            "5",
            "No unsafe shell interpolation",
            VERDICT_FAILED,
            f"found {name}(...) with shell execution whose command argument is {reason}",
        )
    return CheckResult(
        "5",
        "No unsafe shell interpolation",
        VERDICT_PASSED,
        "every shell-executing call found uses a literal command string "
        "or an argv list, not an interpolated or unverifiable value",
    )


_PY_SHELL_CALL_RE = re.compile(r"\b(subprocess\.(?:run|call|check_call|check_output|Popen)|os\.system|os\.popen)\s*\(")
_INTERPOLATION_MARKERS = ('f"', "f'", ".format(", " % ", " + ")


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


def _check_unsafe_interpolation_python_fallback(text: str) -> CheckResult:
    """Regex-based degraded-confidence path, used only when ``text`` does
    not parse as valid Python at all -- see this module's own docstring
    Known-limitations section for what this loses relative to the
    AST-based path above (e.g. a `)` inside a string-literal argument can
    truncate the scanned span early)."""
    matches = list(_PY_SHELL_CALL_RE.finditer(text))
    if not matches:
        return CheckResult(
            "5",
            "No unsafe shell interpolation",
            VERDICT_NOT_APPLICABLE,
            "no subprocess/os.system/os.popen call found in this script "
            "(fallback text scan -- this script did not parse as valid "
            "Python)",
        )
    for match in matches:
        callee = match.group(1)
        span = _balanced_span(text, match.end() - 1)
        is_shell = callee in ("os.system", "os.popen") or "shell=True" in span
        if not is_shell:
            continue
        if any(marker in span for marker in _INTERPOLATION_MARKERS):
            return CheckResult(
                "5",
                "No unsafe shell interpolation",
                VERDICT_FAILED,
                f"found {callee}(...) with shell execution and an "
                "interpolated (not literal) command string (fallback "
                "text scan)",
            )
        first_arg = span[1:].lstrip()
        if not first_arg.startswith(("'", '"', "[")):
            return CheckResult(
                "5",
                "No unsafe shell interpolation",
                VERDICT_FAILED,
                f"found {callee}(...) with shell execution whose command "
                "argument is a variable/expression, not a literal string "
                "or an argv list -- cannot verify from this call site "
                "alone that it is not built from untrusted input "
                "elsewhere in the script (fallback text scan)",
            )
    return CheckResult(
        "5",
        "No unsafe shell interpolation",
        VERDICT_PASSED,
        "every shell/subprocess call found uses a literal command string "
        "or an argv list, not string interpolation (fallback text scan)",
    )


def _check_unsafe_interpolation_python(text: str) -> CheckResult:
    calls = _parse_python_calls(text)
    if calls is None:
        return _check_unsafe_interpolation_python_fallback(text)
    return _check_unsafe_interpolation_python_ast(calls)


_SH_EVAL_WITH_VAR_RE = re.compile(r"\beval\b[^\n]*\$")
# `bash -c "...$var..."` / `sh -c "...$var..."` (including brace-expansion
# form `${var}`): a double-quoted -c string still expands $variables, so
# this is the same injection shape as eval even though no literal eval
# keyword appears.
_SH_DASH_C_WITH_VAR_RE = re.compile(r'\b(?:bash|sh)\s+-c\s+"[^"\n]*\$\{?\w+\}?[^"\n]*"')


def _check_unsafe_interpolation_shell(text: str) -> CheckResult:
    if _SH_EVAL_WITH_VAR_RE.search(text):
        return CheckResult(
            "5",
            "No unsafe shell interpolation",
            VERDICT_FAILED,
            "found eval combined with a $variable reference on the same line -- the canonical shell-injection shape",
        )
    if _SH_DASH_C_WITH_VAR_RE.search(text):
        return CheckResult(
            "5",
            "No unsafe shell interpolation",
            VERDICT_FAILED,
            'found bash/sh -c "..." with a $variable reference interpolated '
            "into the double-quoted command string -- the same "
            "shell-injection shape as eval, without the literal eval keyword",
        )
    return CheckResult(
        "5",
        "No unsafe shell interpolation",
        VERDICT_PASSED,
        "no eval-plus-variable-interpolation or -c-plus-variable pattern found",
    )


# --- shape check 6b: internal subprocess/network timeout -------------------

_PY_TIMEOUT_CALLABLE_NAMES = frozenset(
    {
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "urllib.request.urlopen",
        "urlopen",
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "requests.request",
    }
)


def _check_timeout_internal_python_ast(calls: list[tuple[str, ast.Call]]) -> CheckResult:
    target_calls = [(name, node) for name, node in calls if name in _PY_TIMEOUT_CALLABLE_NAMES]
    if not target_calls:
        return CheckResult(
            "6b",
            "Internal subprocess/network timeout",
            VERDICT_NOT_APPLICABLE,
            "no subprocess/urlopen/requests call found in this script",
        )
    missing = [name for name, node in target_calls if _keyword_value(node, "timeout") is None]
    if missing:
        return CheckResult(
            "6b",
            "Internal subprocess/network timeout",
            VERDICT_FAILED,
            f"call(s) with no timeout= keyword argument: {', '.join(sorted(set(missing)))}",
        )
    return CheckResult(
        "6b",
        "Internal subprocess/network timeout",
        VERDICT_PASSED,
        "every subprocess/network call found sets an explicit timeout= keyword argument",
    )


_PY_TIMEOUT_CALL_RE = re.compile(
    r"\b(subprocess\.(?:run|call|check_call|check_output|Popen)|"
    r"urllib\.request\.urlopen|urlopen|requests\.(?:get|post|put|delete|request))\s*\("
)


def _check_timeout_internal_python_fallback(text: str) -> CheckResult:
    """Regex-based degraded-confidence path, used only when ``text`` does
    not parse as valid Python at all. A bare substring search for
    "timeout" over the whole call span (rather than an actual `timeout=`
    keyword) is a known imprecision of this fallback -- see the AST path
    above, used whenever the script parses, for the exact check."""
    matches = list(_PY_TIMEOUT_CALL_RE.finditer(text))
    if not matches:
        return CheckResult(
            "6b",
            "Internal subprocess/network timeout",
            VERDICT_NOT_APPLICABLE,
            "no subprocess/urlopen/requests call found in this script "
            "(fallback text scan -- this script did not parse as valid "
            "Python)",
        )
    missing = []
    for match in matches:
        span = _balanced_span(text, match.end() - 1)
        if "timeout" not in span:
            missing.append(match.group(1))
    if missing:
        return CheckResult(
            "6b",
            "Internal subprocess/network timeout",
            VERDICT_FAILED,
            f"call(s) with no explicit timeout=...: {', '.join(sorted(set(missing)))} (fallback text scan)",
        )
    return CheckResult(
        "6b",
        "Internal subprocess/network timeout",
        VERDICT_PASSED,
        "every subprocess/network call found sets an explicit timeout (fallback text scan)",
    )


def _check_timeout_internal_python(text: str) -> CheckResult:
    calls = _parse_python_calls(text)
    if calls is None:
        return _check_timeout_internal_python_fallback(text)
    return _check_timeout_internal_python_ast(calls)


_SH_NETWORK_CALL_RE = re.compile(r"\b(curl|wget)\b[^\n]*")
_CURL_TIMEOUT_FLAG_RE = re.compile(r"--max-time\b|(?<!\S)-m\s")
_WGET_TIMEOUT_FLAG_RE = re.compile(r"--timeout\b")


def _check_timeout_internal_shell(text: str) -> CheckResult:
    matches = list(_SH_NETWORK_CALL_RE.finditer(text))
    if not matches:
        return CheckResult(
            "6b",
            "Internal subprocess/network timeout",
            VERDICT_NOT_APPLICABLE,
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
            "6b",
            "Internal subprocess/network timeout",
            VERDICT_FAILED,
            f"{', '.join(sorted(set(missing)))} call(s) with no explicit timeout flag",
        )
    return CheckResult(
        "6b",
        "Internal subprocess/network timeout",
        VERDICT_PASSED,
        "every curl/wget call found sets an explicit timeout flag",
    )


# --- shape check 6a: invocation-level timeout (hooks.json wiring) ----------


def _is_valid_timeout_value(value: object) -> bool:
    # bool is a subtype of int in Python, so isinstance(True, (int,
    # float)) is True -- excluded explicitly, since a JSON `"timeout":
    # true` is not a duration and must not be credited as one.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_timeout_wiring(script_path: Path, hooks_json_path: Path | None) -> CheckResult:
    if hooks_json_path is None:
        return CheckResult(
            "6a",
            "Invocation-level timeout (hooks.json wiring)",
            VERDICT_NOT_APPLICABLE,
            "no --hooks-json supplied -- the script alone cannot establish "
            "this; grade the surrounding invocation separately",
        )
    try:
        data = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return CheckResult(
            "6a",
            "Invocation-level timeout (hooks.json wiring)",
            VERDICT_INDETERMINATE,
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
            "6a",
            "Invocation-level timeout (hooks.json wiring)",
            VERDICT_NOT_APPLICABLE,
            f"no hooks.json entry references {basename!r}",
        )
    missing = [e for e in found_entries if not _is_valid_timeout_value(e.get("timeout"))]
    if missing:
        return CheckResult(
            "6a",
            "Invocation-level timeout (hooks.json wiring)",
            VERDICT_FAILED,
            f"{len(missing)} matching hooks.json entry/entries for {basename!r} with no numeric timeout field",
        )
    return CheckResult(
        "6a",
        "Invocation-level timeout (hooks.json wiring)",
        VERDICT_PASSED,
        f"every matching hooks.json entry for {basename!r} sets a numeric timeout",
    )


# --- public entry point --------------------------------------------------


def gitapex_check_gate_shape(script_path: Path, text: str, hooks_json_path: Path | None = None) -> list[CheckResult]:
    """Run every mechanical shape-check-1-6 check this checker implements
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
            VERDICT_PASSED: "VERDICT_PASSED",
            VERDICT_FAILED: "VERDICT_FAILED",
            VERDICT_NOT_APPLICABLE: "N/A ",
            VERDICT_INDETERMINATE: "IND ",
        }[result.verdict]
        lines.append(f"[{marker}] shape check {result.dimension} ({result.name}): {result.evidence}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mechanically check an agent-harness hook script "
        "against evaluating-deterministic-gate-quality's own "
        "deterministic-shape checks (shape checks 1, 2, 4, 5, 6; shape check "
        "3 as a disclosed heuristic only). Domain-2 (agent-harness hook) "
        "scoped -- see this module's own docstring for what is out of "
        "scope."
    )
    parser.add_argument("script", help="Path to the hook script to check.")
    parser.add_argument(
        "--hooks-json",
        help="Optional path to the hooks.json wiring this script is "
        "registered in, to grade shape check 6a (invocation-level timeout).",
    )
    args = parser.parse_args(argv)
    script_path = Path(args.script)
    try:
        text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not read {script_path}: {exc}", file=sys.stderr)
        return 2
    hooks_json_path = Path(args.hooks_json) if args.hooks_json else None
    results = gitapex_check_gate_shape(script_path, text, hooks_json_path)
    print(format_report(results))
    return 0 if all(r.verdict in (VERDICT_PASSED, VERDICT_NOT_APPLICABLE) for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

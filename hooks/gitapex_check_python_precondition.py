#!/usr/bin/env python3
"""Stdlib-only probe for a Python-package precondition (issue #1566, closes
#1547(a)).

hooks/check-pr-skill-audit-disclosure.sh's tier-1 path attempts a bare
`python3 "$full_gate" --check-diff ...` invocation, and that gate script
transitively imports pydantic. Before this checker existed, a missing
pydantic made that bare invocation crash with an ImportError the hook
could not distinguish from any other tier-1 failure, so it silently
degraded to tier 2's weaker, SKILL.md-only check and warned instead of
failing loudly -- the exact defect #1547(a) reports. This module answers
one question up front: "is `<module>` importable by `python3`?" -- without
needing that module itself, so it can run correctly in the one situation
that matters most: the module is genuinely missing.

Deliberately never imports a probed module via this process's own
`import` statement: doing so would let a missing module crash this
checker itself with an ImportError, the same failure class this script
exists to report cleanly instead. Each module is probed in a SEPARATE
`python3` subprocess via `importlib.import_module`, with the module name
passed as a plain argv value -- never interpolated into the `-c` source
text -- so a module name is data, never code. Each probe is also
time-bounded (`PROBE_TIMEOUT_SECONDS`): a module's own import-time code is
arbitrary and may block rather than either succeed or fail, and this
checker runs inside a PreToolUse hook, where an unbounded probe would
stall the gated operation itself with no verdict at all. A timed-out probe
reports the module as not importable, the same fail-closed answer a
probe that could not be launched already gives.

Input: one or more module names as positional CLI arguments; when none
are given, reads them instead from standard input, one per line (blank
lines ignored) -- the same argv-else-stdin convention
hooks/gitapex_check_pr_title_convention.py and
hooks/gitapex_check_acm_present_or_waiver.py already use for a single
value, extended here to a list.

Output: a single-line JSON object on stdout, `{"missing": [...]}`, naming
(in input order) every given module that failed to import; a human-
readable PASS/FAIL summary line follows on stderr, matching the exit-code
discipline hooks/gitapex_check_skill_audit_disclosure_or_waiver.py already
uses (0 on success, 1 on a genuine failure). Stdout carries only the JSON
line so a caller can parse it directly (e.g. via `jq`) without splitting
out prose first.

Standard library only, no network calls, no side effects beyond the
read-only subprocess probes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

#: Passed to `python3 -c`; the module name itself always arrives as
#: sys.argv[1] in that subprocess, never spliced into this source text.
_PROBE_SOURCE = "import importlib, sys\nimportlib.import_module(sys.argv[1])\n"

#: A hang guard, not a budget: importing an already-installed package
#: completes in well under a second, so this ceiling is never reached by a
#: healthy probe. Bounded anyway because a module's own import-time code is
#: arbitrary and may block indefinitely (a network call, a lock, a
#: `time.sleep`) -- and this probe runs inside
#: hooks/check-pr-skill-audit-disclosure.sh, a PreToolUse hook firing on
#: every mcp__github__create_pull_request/update_pull_request call in this
#: repository, so an unbounded probe stalls the very operation the hook is
#: gating, producing no verdict at all. Matches the same hang-guard
#: rationale (and fail-to-the-safe-answer handling) that
#: skills/executing-a-branch-plan/scripts/gitapex_check_task_worktree_base.py
#: applies to its own PreToolUse-hook subprocess calls.
PROBE_TIMEOUT_SECONDS = 10.0


def is_importable(module: str, *, python: str = "python3", timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    """Return True iff `module` is importable by a separate `python`
    subprocess within `timeout` seconds.

    Never imports `module` in this process: a missing module must not be
    able to crash this checker itself.
    """
    try:
        # S603 waived: a fixed argv list with no shell, and `python`
        # (default "python3") is intentionally resolved from PATH -- this
        # probe exists specifically to check what that same PATH-resolved
        # interpreter can import, so pinning an absolute path here would
        # answer a different question than the one callers actually ask.
        # The module name is data (sys.argv[1] inside the probe source,
        # never spliced into it), so this is not untrusted-input execution
        # in the sense S603 warns about.
        result = subprocess.run(  # noqa: S603
            [python, "-c", _PROBE_SOURCE, module],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # The module neither imported nor failed to import: its own
        # import-time code blocked past the ceiling. Handled exactly like
        # the OSError case below -- this probe could not answer its own
        # question, and the only safe answer is the fail-closed "cannot
        # confirm this is importable". `subprocess.run` kills the child
        # before re-raising, so no orphaned interpreter is left behind.
        print(
            f"warning: probing '{module}' with '{python}' timed out after {timeout}s "
            f"(its import blocked); treating it as not importable",
            file=sys.stderr,
        )
        return False
    except OSError as error:
        # `python` itself could not even be launched (not on PATH, not
        # executable, ...). That is not evidence the module is missing --
        # it is evidence the probe could not run at all. Callers only ever
        # act on this return value as a fail-closed "cannot confirm this
        # is importable" signal, and a caller that cannot even launch
        # python3 could not run the gate script that needs `module`
        # either, so treating it the same as "missing" is the safe
        # default here.
        print(f"warning: could not launch '{python}' to probe '{module}': {error}", file=sys.stderr)
        return False
    return result.returncode == 0


def find_missing_modules(
    modules: list[str], *, python: str = "python3", timeout: float = PROBE_TIMEOUT_SECONDS
) -> list[str]:
    """Return the subsequence of `modules` not importable by `python`, in
    order. `timeout` bounds each module's own probe independently."""
    return [module for module in modules if not is_importable(module, python=python, timeout=timeout)]


def _read_modules_from_stdin() -> list[str]:
    return [line.strip() for line in sys.stdin if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff every given module is importable, else 1."""
    parser = argparse.ArgumentParser(
        description="Check whether one or more Python modules are importable, each probed in "
        "a separate subprocess so a missing module cannot crash this checker itself."
    )
    parser.add_argument(
        "modules",
        nargs="*",
        help="Module names to probe. Reads newline-separated module names from standard input when omitted.",
    )
    args = parser.parse_args(argv)
    modules = args.modules if args.modules else _read_modules_from_stdin()

    missing = find_missing_modules(modules)
    print(json.dumps({"missing": missing}))
    if missing:
        print("FAIL: missing python module(s): " + ", ".join(missing), file=sys.stderr)
        return 1
    print("PASS: all given python module(s) are importable", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

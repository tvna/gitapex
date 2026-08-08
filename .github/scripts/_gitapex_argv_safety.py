#!/usr/bin/env python3
"""Shared argv-safety predicates for the ``local`` gate plane (issue #876).

``.gitapex/ssot.json`` carries, per gate, a ``local_invocation`` argv that
``gitapex_gate_local_preflight.py`` executes -- and, since that runner is
wired as a ``pre-push`` hook, executes automatically on every push. A
registry entry is therefore a carrier of commands, not just of references,
and an argv naming a shell (``["sh", "-c", "<payload>"]``) or handing inline
code to an interpreter (``["uv", "run", "python3", "-c", "<payload>"]``) is
arbitrary code hidden where no reviewer expects executable content.

**Why this lives in its own module rather than in either caller.** Both the
runner and ``gitapex_scan_ssot_schema.py`` must apply the identical rule,
and a review of PR #888 showed why the runner cannot simply import the
scanner: the scanner depends on ``pydantic`` and ``jsonschema``, while the
runner is deliberately stdlib-only so the pre-push hook can invoke it as
plain ``python3`` with no virtualenv resolved. Duplicating the predicates
instead would leave two copies to drift apart, with the copy in the weaker
position the one that silently stopped matching. This module is stdlib-only
(it imports ``pathlib`` and nothing else) so both callers can share one
definition, following the same ``_gitapex_*`` private-helper convention as
``_gitapex_schema_validation.py`` and ``_gitapex_github_http.py``.

**Why the runner must check this itself, rather than relying on the
scanner's gate.** ``ssot-schema-drift`` -- the gate that runs this scanner
-- is one of the wired gates, so it executes in gate-id order like any
other: 15th of 16 today, with 14 gates running before it. A hostile argv on
any of those 14 has already executed by the time the guard evaluates it.
Reconstructed rather than argued: putting ``["sh", "-c", "echo owned >
FILE; echo clean"]`` on ``apm-manifest-drift`` (which sorts first) wrote the
file *and* the run reported ``exit 0``, because the scanner reads its own
module-level ``SSOT_PATH`` and so never even saw the registry the runner was
executing. Checking here, before the first subprocess starts, is what makes
the guard order-independent.
"""

from __future__ import annotations

import pathlib

# argv0-or-anywhere basenames that turn an argv list back into a shell
# command line. `env`/`exec`/`xargs` are included because each will happily
# run whatever follows it, which defeats the "argv, never a shell string"
# property just as thoroughly as `sh` does.
SHELL_COMMANDS = frozenset({"sh", "bash", "dash", "zsh", "ksh", "csh", "tcsh", "fish", "env", "eval", "exec", "xargs"})

# Options that hand a *string* to an interpreter to parse and execute rather
# than naming a file to run -- but only when they follow an interpreter.
# `git -c core.quotePath=false` is a real `local_stdin` value in this
# registry today and uses the same spelling for an unrelated config
# override, so an unanchored scan for these flags false-flags it.
INLINE_CODE_FLAGS = frozenset({"-c", "--command", "-e", "--eval"})

# Interpreters that will execute an INLINE_CODE_FLAGS string. Matched on
# basename anywhere in the argv, not just argv0, because every Python gate
# is invoked indirectly (`uv run --frozen python3 <script>`) and an
# argv0-only check would miss `uv run --frozen python3 -c '<payload>'`.
INTERPRETERS = frozenset({"python", "python3", "perl", "ruby", "node", "deno", "bun", "php", "Rscript"})


def find_argv_safety_violations(argv: tuple[str, ...] | list[str]) -> list[str]:
    """Return one human-readable reason per way ``argv`` would execute code
    that is not a tracked script in this repository. Empty list means the
    argv is a plain exec-form invocation.

    Deliberately reports *reasons only*, with no gate id or field name: the
    two callers frame the same finding differently (the scanner as registry
    drift, the runner as a refusal to start), so each supplies its own
    context around these strings rather than parsing them apart.

    This closes the shape, not the intent. An argv naming a real interpreter
    and a real script file is still arbitrary code by construction, and
    nothing here adjudicates what that script does. What it removes is the
    ability to hide the payload *inside the registry entry itself*.
    """
    if not argv:
        return []
    basenames = [pathlib.PurePosixPath(token).name for token in argv]
    violations: list[str] = []

    shells = sorted({token for token, base in zip(argv, basenames, strict=True) if base in SHELL_COMMANDS})
    if shells:
        violations.append(f"invokes a shell/wrapper: {', '.join(repr(shell) for shell in shells)}")

    # Anchored to an interpreter's own position: only a flag that comes
    # *after* one is that interpreter's inline-code flag.
    first_interpreter = next((index for index, base in enumerate(basenames) if base in INTERPRETERS), len(argv))
    inline = sorted({flag for flag in argv[first_interpreter + 1 :] if flag in INLINE_CODE_FLAGS})
    if inline:
        violations.append(
            f"passes inline code to {argv[first_interpreter]!r} via {', '.join(repr(flag) for flag in inline)}"
        )
    return violations

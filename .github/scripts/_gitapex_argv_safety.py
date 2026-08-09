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

That convention put this file outside
``gitapex_detect_changed_gate_scripts.py``'s ``gitapex_(gate|scan)_*``
naming rule, so weakening these predicates required no
``deterministic-gate-quality`` disclosure (issue #904, finding 4). It is
now listed in ``.gitapex/ssot.json`` as one of ``ssot-schema-drift``'s
``script`` paths, which brings it into that selection through the registry
rule instead -- keeping the private-helper name the paragraph above
justifies, while making an edit here as visible as an edit to either
caller.

**Why the runner must check this itself, rather than relying on the
scanner's gate.** ``ssot-schema-drift`` -- the gate that runs this scanner
-- is one of the wired gates, so it executes in gate-id order like any
other, and it is not the first id in that order. Every gate sorting before
it has therefore already executed by the time the guard evaluates the
registry. The property, not the position, is what matters here: issue #904
found this paragraph asserting a stale ordinal, so it now states the
invariant the argument actually rests on. Reconstructed rather than argued:
putting ``["sh", "-c", "echo owned > FILE; echo clean"]`` on
``apm-manifest-drift`` (which sorts first) wrote the file *and* the run
reported ``exit 0``, because the scanner reads its own module-level
``SSOT_PATH`` and so never even saw the registry the runner was executing.
Checking here, before the first subprocess starts, is what makes the guard
order-independent.
"""

from __future__ import annotations

import pathlib

# argv0-or-anywhere basenames that turn an argv list back into a shell
# command line. `env`/`exec`/`xargs` are included because each will happily
# run whatever follows it, which defeats the "argv, never a shell string"
# property just as thoroughly as `sh` does.
SHELL_COMMANDS = frozenset({"sh", "bash", "dash", "zsh", "ksh", "csh", "tcsh", "fish", "env", "eval", "exec", "xargs"})

# Options that hand a *string* to an interpreter to parse and execute rather
# than naming a file to run, keyed by the interpreter that accepts them.
# Matched on basename anywhere in the argv, not just argv0, because every
# Python gate is invoked indirectly (`uv run --frozen python3 <script>`) and
# an argv0-only check would miss `uv run --frozen python3 -c '<payload>'`.
#
# **Why per interpreter rather than one flat set.** The matching below looks
# for a short flag's letter *inside* a combined option cluster, and a flat
# set makes that catastrophically over-broad: `python3
# -Wignore::DeprecationWarning` contains both the `e` that `perl -e` needs
# and the `r` that `php -r` needs, so a flat set would refuse it -- and
# `_refuse_unsafe_argv` refuses the whole run, aborting every push. That is
# issue #904's second finding, and keeping each interpreter's letters to its
# own entry is what closes it.
#
# **Why these spellings.** Each concatenated form below was run before being
# listed, not recalled: `python3 -cprint(1)`, `python3 -Bcprint(1)`,
# `python3 -X utf8 -cprint(1)`, `perl -eprint"x"`, `perl -le 'print "x"'`,
# `ruby -eputs(1)` and `php -recho "x";` all execute their payload, so the
# exact-token match this replaces (issue #904's first finding) caught none
# of them. `node`/`bun` reject the concatenated form and need the flag as
# its own token, which the same rule covers anyway. `deno` and `Rscript`
# were not reproducible on the machine this was written on; their entries
# come from those tools' own documented `--eval`/`-e` and are stated as such
# rather than as observed. Over-listing is the safe direction: a spelling an
# interpreter does not actually accept can never be a legitimate flag
# either, while a missing one is a bypass.
INLINE_CODE_FLAGS: dict[str, frozenset[str]] = {
    "python": frozenset({"-c"}),
    "perl": frozenset({"-e", "-E"}),
    "ruby": frozenset({"-e"}),
    "node": frozenset({"-e", "--eval", "-p", "--print"}),
    "deno": frozenset({"-e", "--eval"}),
    "bun": frozenset({"-e", "--eval"}),
    "php": frozenset({"-r", "-R"}),
    "Rscript": frozenset({"-e"}),
}


_INLINE_CODE_FLAGS_BY_LOWER_NAME = {name.lower(): flags for name, flags in INLINE_CODE_FLAGS.items()}


def _inline_code_flags(basename: str) -> frozenset[str] | None:
    """The inline-code flags ``basename`` accepts, or None if it is not an
    interpreter this module knows.

    The name is normalized before the lookup, because the same interpreter
    ships under several basenames and the previous membership test was a
    literal set naming ``python``/``python3`` and nothing else:

    - **Case.** Matched case-insensitively, so ``PYTHON3`` is ``python3``.
    - **A ``.exe`` suffix**, so a Windows checkout's ``python3.exe`` is
      guarded.
    - **A version suffix**, so ``python3.12`` and ``php8.2`` -- real binary
      names on any machine carrying more than one runtime -- resolve to
      their unversioned entry.
    - **CPython's free-threaded ``t`` marker**, so ``python3.13t`` and
      ``python3.13t.exe`` resolve there too. Those are the documented names
      for the free-threaded build (Python 3.13 "What's New" and the
      free-threading HOWTO), not a guess. The ``t`` is only stripped when
      doing so *produces a known interpreter*, so an unrelated basename is
      never coerced into one -- ``pytest3`` normalizes to ``pytest``, then
      to ``pytes``, and matches neither.

    Every one of these was unguarded in the spelled-out ``-c <payload>``
    form as well as the concatenated one, so this closes both.
    """
    name = basename.lower()
    if name.endswith(".exe"):
        name = name[: -len(".exe")]
    name = name.rstrip("0123456789.")
    flags = _INLINE_CODE_FLAGS_BY_LOWER_NAME.get(name)
    if flags is None and name.endswith("t"):
        flags = _INLINE_CODE_FLAGS_BY_LOWER_NAME.get(name[:-1].rstrip("0123456789."))
    return flags


def _matches_inline_flag(element: str, flags: frozenset[str]) -> bool:
    """Whether ``element`` is one of ``flags``, in any spelling the shell
    hands through as a single argv element.

    Named ``element`` rather than ``token`` only because ruff's ``S105``
    reads ``token == "-"`` as a hardcoded credential; the rest of this
    module calls the same thing a token.

    Three spellings, not one exact-token comparison:

    - ``--eval`` and ``--eval=<payload>`` for the long forms.
    - ``-c`` on its own for the short forms.
    - ``-cprint(1)`` and ``-Bcprint(1)`` -- the payload concatenated onto the
      flag, optionally behind other short options in the same cluster. This
      is the shape issue #904 was filed for.

    The cluster scan stops at the first non-letter character so a payload's
    own text cannot contribute a match: only the leading run of ASCII
    letters is option syntax, everything after it is the payload. That still
    leaves one accepted false positive, named rather than hidden -- a real
    option whose *letters* include an inline-code flag of the same
    interpreter, such as CPython's ``-Xpycache_prefix=...`` against ``-c``.
    No wired argv uses one today, and the failure is loud (a refused push
    naming the argv) rather than silent.
    """
    if element.startswith("--"):
        return any(element == flag or element.startswith(f"{flag}=") for flag in flags if flag.startswith("--"))
    if not element.startswith("-") or element == "-":
        return False
    letters = ""
    for character in element[1:]:
        if not (character.isascii() and character.isalpha()):
            break
        letters += character
    return any(flag[1] in letters for flag in flags if len(flag) == 2 and not flag.startswith("--"))


# File extensions that make a token the *script* an interpreter runs, rather
# than one of that interpreter's own option values. See
# `_interpreter_option_span` for why the span ends on this and not on "the
# first token that looks like a path".
SCRIPT_SUFFIXES = (".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".pm", ".php", ".r")


def _interpreter_option_span(argv: tuple[str, ...] | list[str], interpreter_index: int) -> range:
    """Indices of the tokens ``argv[interpreter_index]`` consumes as its own
    options: everything up to the script it is being asked to run.

    The span ends at the interpreter's script argument, and a token is that
    argument only when it is not an option *and* carries a script file
    extension. Both halves matter, and the second one is narrower than it
    first looks:

    - Not simply "the first token not starting with ``-``". ``python3 -X
      utf8 -cprint(1)`` really does execute its payload, and stopping at
      ``utf8`` would walk straight past the flag that does it.
    - Not "the first token that looks like a path" either -- that was this
      function's first revision, and CodeRabbit's review of PR #910 found
      it bypassable. An option *value* can carry a dot: ``python3 -X
      pycache_prefix=cache.dir -cprint(99)`` and ``python3 -W
      ignore::Dep:mypkg.mod -cprint(98)`` both print, verified by running
      them, while a dot-or-slash heuristic ended the span on the value and
      never saw the ``-c``. Requiring a script extension keeps those values
      inside the span. It also generalizes past the single ``-X`` case the
      review named, without this module having to enumerate which options
      of which interpreter take a separate value.

    Anchoring the span here is what keeps the mirror-image false positive
    out: in ``uv run --frozen python3 script.py -c conf.json`` the ``-c``
    belongs to ``script.py``, sits past the span, and is not this
    interpreter's flag at all. ``git -c core.quotePath=false`` -- a real
    ``local_stdin`` value in this registry -- never enters a span, since
    ``git`` is not an interpreter.

    The residual, stated rather than left to be discovered: an argv that
    names no extension-bearing script at all keeps the span open to the
    end, so ``python3 -m pytest -c pytest.ini`` would be refused even
    though its ``-c`` is pytest's, as would an extensionless executable
    script. Every wired argv names a ``.github/scripts/*.py`` path, and the
    failure is a loud refusal naming the argv, not a silent pass.
    """
    start = interpreter_index + 1
    for index in range(start, len(argv)):
        token = argv[index]
        if not token.startswith("-") and token.lower().endswith(SCRIPT_SUFFIXES):
            return range(start, index)
    return range(start, len(argv))


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

    # Every interpreter occurrence, not just the first: an argv naming one
    # interpreter with a real script and a second one with a payload would
    # otherwise report clean on the strength of the first.
    for index, base in enumerate(basenames):
        flags = _inline_code_flags(base)
        if flags is None:
            continue
        inline = sorted(
            {
                argv[offset]
                for offset in _interpreter_option_span(argv, index)
                if _matches_inline_flag(argv[offset], flags)
            }
        )
        if inline:
            violations.append(f"passes inline code to {argv[index]!r} via {', '.join(repr(flag) for flag in inline)}")
    return violations

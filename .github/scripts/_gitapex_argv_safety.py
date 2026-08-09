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
    # `pypy3` normalizes to `pypy`, so it needs its own entry: it takes `-c`
    # identically, and `uv run --python pypy3.10` is a supported invocation.
    "pypy": frozenset({"-c"}),
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


# A bare `-` is not an option: every interpreter here reads its *program*
# from standard input when handed one, and the runner pipes a gate's
# `local_stdin` producer straight into that stdin. `["python3", "-",
# "<the gate's real script>"]` with `local_stdin: ["git", "log", "-1",
# "--format=%B"]` therefore executes the commit message as Python, on every
# push, while naming a real script and passing every other check. Verified,
# not argued: `echo "print('OWNED')" | python3 - /some/arg` prints OWNED.
STDIN_PROGRAM_ARG = "-"


def _interpreter_option_span(argv: tuple[str, ...] | list[str], interpreter_index: int) -> range:
    """Indices of the tokens ``argv[interpreter_index]`` consumes itself:
    everything up to the script it is being asked to run.

    The rule is one line and is worth stating precisely, because two weaker
    versions of it shipped in this PR and both were bypassable. A token ends
    the span when it is **not an option and is not the value of the option
    before it** -- that is, it does not start with ``-`` *and* neither does
    its predecessor. Everything before it is the interpreter's own.

    Why not the two weaker rules:

    - "The first token not starting with ``-``" misses ``python3 -X utf8
      -cprint(1)``, which really does execute its payload: it stops on
      ``utf8``, the *value* of ``-X``.
    - "The first token that looks like a path", then "the first token
      carrying a script extension", both narrowed that hole without closing
      it, because an option value can look like either. All three of
      ``python3 -X pycache_prefix=cache.dir -cprint(99)``, ``python3 -X
      pycache_prefix=cache.py -cprint(99)`` and ``python3 -W ignore:x.py
      -cprint(99)`` print their payload, and each defeated one of those
      spellings. Chasing the *shape of the value* is the wrong axis; its
      *position* -- one token after an option -- is what actually makes it a
      value, and needs no enumeration of which options of which interpreter
      take one.

    The mirror-image false positive stays closed, which is what the span
    exists for: in ``uv run --frozen python3 script.py -c conf.json`` the
    token after the interpreter is not an option and its predecessor is the
    interpreter itself, so the span is empty and the ``-c`` -- which belongs
    to ``script.py`` -- is never this interpreter's flag. ``python3 -X utf8
    script.py -c conf.json`` also lands correctly: ``utf8`` is a value,
    ``script.py`` follows a non-option, so the span is exactly ``-X utf8``.
    ``git -c core.quotePath=false`` never enters a span at all, since
    ``git`` is not an interpreter.

    The residual, stated rather than left to be discovered: a *valueless*
    option immediately before the script argument makes that argument look
    like a value, so ``python3 -B script.py -c conf.json`` keeps the span
    open and refuses on the script's own ``-c``. No wired argv puts an
    option between the interpreter and its script -- every one of them is
    ``uv run --frozen python3 <path>`` -- and the failure is a loud refusal
    naming the argv, never a silent pass. That direction is the one to err
    in here.
    """
    start = interpreter_index + 1
    for index in range(start, len(argv)):
        if argv[index].startswith("-"):
            continue
        if index > start and argv[index - 1].startswith("-"):
            continue  # consumed as the preceding option's value, not the script
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
    # `is not None`, matching the loop below rather than testing truthiness:
    # the two agree only while every INLINE_CODE_FLAGS value is a non-empty
    # frozenset, and an interpreter registered with an empty set would shift
    # this anchor to a later token while the loop still visited the earlier
    # one. Raised as a nitpick in review; taken because the divergence would
    # be silent and this is the guard's own anchor.
    first_interpreter = next(
        (index for index, base in enumerate(basenames) if _inline_code_flags(base) is not None), None
    )
    for index, base in enumerate(basenames):
        flags = _inline_code_flags(base)
        if flags is None:
            continue
        span = _interpreter_option_span(argv, index)
        inline = sorted({argv[offset] for offset in span if _matches_inline_flag(argv[offset], flags)})
        if inline:
            violations.append(f"passes inline code to {argv[index]!r} via {', '.join(repr(flag) for flag in inline)}")
        elif any(argv[offset] == STDIN_PROGRAM_ARG for offset in span):
            violations.append(f"feeds {argv[index]!r} its program on standard input via '-'")
        elif (
            index == first_interpreter
            and span.stop == len(argv)
            and all(argv[offset].startswith("-") for offset in span)
        ):
            # Nothing after the interpreter that could be a script at all:
            # it falls back to reading its program from stdin, the same
            # execution path as `-`. Both conditions are load-bearing and
            # each was wrong on its own in an earlier draft. `span.stop ==
            # len(argv)` alone is not "no script": an empty span means the
            # script was found *immediately*, which is what every wired argv
            # looks like. And "the span reached the end" alone fired on any
            # argv with an option before its script, because the span rule
            # cannot tell an attached-value option (`-Wignore::Dep x.py`,
            # where `x.py` *is* the script) from a valueless one. Together
            # they mean: no script-shaped token exists anywhere after the
            # interpreter. Restricted to the *first* interpreter, so a later
            # token merely named after one -- an option value like
            # `--interpreter node` -- is not read as a script-less
            # invocation.
            violations.append(f"gives {argv[index]!r} no script, so it reads its program from standard input")
    return violations

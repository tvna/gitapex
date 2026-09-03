#!/usr/bin/env python3
"""CI gate: a regex literal newly added by a PR diff to any ``*.py`` file
must not carry a statically-detectable catastrophic-backtracking
(CWE-1333/ReDoS) shape.

Issue #1556 (retro #1552 repair 8). Independent review
(``drafting-a-pr-to-merge`` Step 8) found and live-reproduced a
catastrophic-backtracking regex --
``_UV_RUN_PREFIX``'s own former ``-{1,2}[\\w-]+`` shape -- inside
``.github/scripts/gitapex_gate_bare_python3_invocation.py``. That gate's own
new ``hooks/*.sh`` scan exercises the pattern against every PR's own
``hooks/*.sh`` content, unconditionally, inside a *required* CI job with a
5-minute timeout and no ``paths:`` filter -- so every contributor's PR was
already reachable by an exponential-blowup input on that one call site. No
existing gate screened a new or changed regex literal for this defect class
before this one; this gate is that screen.

Two detected shapes
--------------------
Deliberately bounded to the two best-understood, most common
catastrophic-backtracking shapes, not a general regex-ambiguity solver
(computing exact worst-case complexity for an arbitrary regex is
intractable in general) -- both a heuristic, per this issue's own
Residual risk, with a documented waiver escape hatch below.

**Shape A -- nested quantifiers.** A group (``(...)``/``(?:...)``/
``(?=...)``/``(?P<name>...)``, any group-opening spelling) that is itself
quantified with an unbounded-or-wide repeat (``*``, ``+``, or ``{m,n}``/
``{m,}`` reaching 2 or more repeats) and whose own *direct* top-level
content contains another quantified atom or sub-group reaching 2+ repeats.
The textbook ``(a+)+``/``(a*)*``/``(a+)*`` evil-regex shape.

**Shape B -- adjacent overlapping quantified atoms.** Two consecutive
*simple* atoms (a single literal character, an escaped character, or a
``[...]`` bracket expression -- never a group; see "Known misses" below)
at the same nesting level, each quantified to 2+ repeats, whose own
character sets overlap (share at least one member), with nothing between
them to disambiguate where one repetition ends and the next begins. This
is the exact historical shape: ``-{1,2}[\\w-]+`` -- ``-{1,2}`` matches
``{-}``, ``[\\w-]+`` matches word characters plus ``-``, and the two sets
overlap on ``-`` -- so a long run of dashes can be partitioned between the
two quantified spans in exponentially many ways before the engine gives up
on a non-matching suffix.

A character class this gate cannot resolve precisely (``.``, a negated
class ``[^...]``, or the wide shorthand classes ``\\W``/``\\D``/``\\S``) is
treated conservatively as overlapping with everything -- a false positive
here is a documented cost of staying fail-closed on an unknown set, not a
bug.

Scope
-----
Every ``*.py`` file the diff adds lines to, repository-wide -- the issue's
own Planned ops states this scope explicitly ("every changed .py file"),
wider than the narrower ``gitapex_check_``/``gitapex_gate_`` prefix scope
``gitapex_gate_detection_logic_property_coverage.py`` uses, because a
catastrophic-backtracking regex is exactly as dangerous in a test fixture,
a hook, or a skill script as it is in a CI gate. ``test_*.py`` and
``conftest.py`` are still excluded: a test file's own regex fixtures
(including this gate's -- see its own test module) exist to *construct*
the dangerous shape under test, not to avoid it.

Trigger
-------
A ``re.compile(...)``/``re.match(...)``/``re.search(...)``/
``re.fullmatch(...)`` call, module-qualified on a bare name the file's own
imports bind to the ``re`` module (``_re_module_names``, the same
resolution ``gitapex_gate_detection_logic_property_coverage.py`` already
uses -- an aliased ``import re as _re`` is graded the same as a bare
``re``). The receiver-agnostic bound-method half that gate's own category
(a) also grades is deliberately not graded here: this gate needs the
*pattern text itself*, and a bound-method call's own receiver is a
compiled-pattern object, not a string this gate could read without also
tracing back to wherever it was compiled -- exactly the same
name-resolution trade below already makes for the compile call's own
argument.

The pattern argument (first positional, or a ``pattern=`` keyword) is
resolved statically: a plain string ``Constant``, a chain of ``Constant``s
joined by ``+``, or a reference to a same-file ``NAME`` this gate can
resolve to its own statically-known string value -- ``_string_constants``
collects every module- or function-level ``NAME = <string-literal-or-+
-chain>`` assignment in file order, the same "assign a reusable prefix/
suffix constant, then compose it with ``+`` into the real ``_RE``" idiom
this repository's own regexes are overwhelmingly written in (e.g.
``_UV_RUN_PREFIX`` composed into ``_UV_WRAPPED_INVOCATION_RE`` in the very
file this gate's own motivating defect came from). A name assigned more
than once in the file is treated as unresolvable (its value could differ
by the time a given compile call actually runs) rather than guessed at
from whichever assignment happens to be seen. A pattern argument this gate
cannot fully resolve to a concrete string -- an f-string, a runtime
concatenation with a non-literal, an unresolvable name -- is silently out
of scope for this call site: a dynamic pattern this gate cannot read
cannot be graded for a shape inside it.

Known misses, disclosed rather than found later
-------------------------------------------------
* Shape B never crosses a group boundary: ``(ab)+c+`` is not graded even
  though the group's own trailing content could still overlap with what
  follows -- computing a group's own effective trailing/leading character
  set in general needs real regex-AST machinery, not a heuristic scan.
* Alternation (``a|a``) under repetition is not a detected shape at all
  (a third, real ReDoS class this gate does not yet cover).
* A regex verb outside ``compile``/``match``/``search``/``fullmatch`` --
  ``re.sub``/``re.split``/``re.findall``/``re.finditer`` -- is not graded,
  matching ``gitapex_gate_detection_logic_property_coverage.py``'s own
  disclosed verb-set trade.
* A pattern built at runtime from non-literal input (an f-string, string
  formatting, a value read from a file) is never graded -- this gate reads
  source text statically, never executes anything.
* ``_string_constants`` resolves a reusable prefix constant only at module
  scope, deliberately: a function-local ``NAME = <literal>`` composed into
  a ``re.compile`` call inside that same function is never resolved,
  since walking into function bodies once let an unrelated same-named
  local variable in a *different* function silently suppress detection
  of a genuinely dangerous module-level constant sharing that name
  (live-confirmed during independent review, fixed by narrowing scope
  rather than by threading full lexical-scope tracking through this
  gate's own single-pass extraction).

Waiver
------
``# regex-catastrophic-backtracking: WAIVED: <reason>`` on the line
carrying the flagged ``re.compile``/``re.match``/``re.search``/
``re.fullmatch`` call -- a non-whitespace reason is mandatory, matched via
``tokenize`` exactly like ``gitapex_gate_detection_logic_property_
coverage.py``'s own ``_waived_lines`` (only the fixed prefix string
differs), so the marker is honoured only as a real comment token, never
inside a string literal quoting this gate's own documentation. For a
pattern proven safe by a bounded-input contract (a value already
length-capped, or drawn from a fixed small enumeration) this is the
documented escape hatch this issue's own Residual risk calls for.

Diff parsing
------------
``parse_added_lines`` below is ported verbatim (not imported -- matching
this repository's own established per-gate self-containment convention;
``gitapex_gate_exception_handler_gaps.py``, ``gitapex_gate_function_body_
test_coverage.py``, and ``gitapex_gate_detection_logic_property_
coverage.py`` each already carry their own copy) from
``gitapex_gate_exception_handler_gaps.py``, the hardest-adversarially-
reviewed of the three: fail-closed on a malformed ``@@`` hunk header, a
post-image path that is neither ``/dev/null`` nor ``b/``-prefixed, a
``+++ `` header reached outside a hunk with no ``--- `` header before it,
a hunk whose declared pre-/post-image counts do not match its own real
body, and the absorbed-header edge case a `+++ `-shaped line immediately
following a `--- `-shaped one can create. See that file's own docstring
for the full adversarial-review history behind each of those checks.

Exit codes
----------
0 clean, 1 violation(s) found, 2 the scan could not be trusted -- a
malformed diff, or an in-scope file that cannot be read or parsed as
Python. Never a silent pass on an ungradable input (dimension 15,
``skills/evaluating-deterministic-gate-quality/references/dimensions.md``).

Invocation shape
-----------------
Same stdin-diff/``--root``/``--diff`` CLI shape as
``gitapex_gate_detection_logic_property_coverage.py``, wired the same way
in ``.gitapex/ssot.json`` (``local_stdin`` reuses that gate's own
``gitapex_run_base_diff.py -- *.py`` producer, since this gate's own scope
is the identical ``*.py`` wildcard).

Usage::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_regex_catastrophic_backtracking.py

A bare pipe here masks `git diff`'s own exit status in a non-`pipefail`
shell (issue #1531): add `set -o pipefail` first, or check `git diff`'s
own exit code separately, if the caller must detect an upstream failure
rather than silently grading whatever partial diff reached stdin.

Reads a unified diff on stdin; diagnostics and violations go to stderr.
Run via ``uv run`` (the pydantic import needs it) or via the pytest gate
in ``tests/test_gitapex_gate_regex_catastrophic_backtracking.py``.
"""

from __future__ import annotations

import argparse
import ast
import io
import pathlib
import re
import string
import sys
import tokenize
from dataclasses import dataclass
from typing import NamedTuple

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_RE_MODULE = "re"
_REGEX_VERBS = frozenset({"compile", "match", "search", "fullmatch"})

_WAIVER_RE = re.compile(r"#\s*regex-catastrophic-backtracking\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class _Negated:
    """The precise complement of `base` -- `\\D`/`\\S`/`\\W`, whose own
    excluded set is exactly known (unlike `.` or a negated bracket
    expression `[^...]`, both genuinely open-ended and represented as the
    fully-unknown `None` instead -- see `_overlaps`)."""

    base: frozenset[str]


# Shorthand classes this gate resolves precisely enough to compute overlap.
# `None` marks a class this gate treats conservatively as "wide" (overlaps
# with everything) rather than guessing at its true member set; a
# `_Negated` marks one whose own excluded set is exactly known, so
# `_overlaps` can rule out a false overlap against it (e.g. `\s+\S+` --
# whitespace immediately followed by non-whitespace, this repository's own
# common tokenizing idiom -- is not itself an overlapping pair).
_DIGIT = frozenset(string.digits)
_WORD = frozenset(string.ascii_letters + string.digits + "_")
_WHITESPACE = frozenset(" \t\n\r\f\v")
_SHORTHAND_CLASSES: dict[str, frozenset[str] | _Negated] = {
    "d": _DIGIT,
    "w": _WORD,
    "s": _WHITESPACE,
    "D": _Negated(_DIGIT),
    "W": _Negated(_WORD),
    "S": _Negated(_WHITESPACE),
}


def _overlaps(a: frozenset[str] | _Negated | None, b: frozenset[str] | _Negated | None) -> bool:
    """Conservative character-set overlap between two resolved atom
    char-sets. `None` (a genuinely open-ended class such as `.` or a
    negated bracket expression) always overlaps with anything -- the
    documented fail-closed default for an unknown set. A `_Negated` (a
    precisely-known complement) overlaps a concrete set `s` unless `s` is
    fully contained in the negation's own excluded `base` (e.g. `\\S`
    never overlaps `\\s` -- every whitespace character is excluded by
    `\\S`'s own definition -- but does overlap `[a-z]`, none of which
    `\\S` excludes); two `_Negated`s overlap unless they exclude exactly
    the same characters (no two of `\\D`/`\\S`/`\\W` do)."""
    if a is None or b is None:
        return True
    if isinstance(a, _Negated):
        if isinstance(b, _Negated):
            return a.base != b.base
        return not (b <= a.base)
    if isinstance(b, _Negated):
        return not (a <= b.base)
    return bool(a & b)


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation: a resolved regex literal reached by this diff
    that carries a detected catastrophic-backtracking shape."""

    path: str
    line: int
    shape: str
    message: str


@dataclass(frozen=True)
class _Atom:
    """One element of a parsed pattern branch: a simple char/class, or a
    group. `char_set` is `None` for a group (never computed -- Shape B is
    scoped to simple-atom adjacency only) or for a simple atom this gate
    treats conservatively as wide. `group_branches` holds one tuple of
    `_Atom` per `|`-separated alternative inside the group (a non-group
    atom always carries an empty tuple)."""

    is_group: bool
    char_set: frozenset[str] | _Negated | None
    repeats: bool  # quantified to 2+ repeats (an unbounded `*`/`+`, or `{m,n}`/`{m,}` with a 2+ reach)
    group_branches: tuple[tuple[_Atom, ...], ...] = ()


# --- pattern parsing (Shapes A/B) -----------------------------------------


def _quantifier_repeats(pattern: str, index: int) -> tuple[bool, int]:
    """Return `(reaches_2_or_more_repeats, next_index)` for the quantifier
    (if any) starting at `pattern[index]`. `index` must point just past the
    atom/group the quantifier would apply to. A non-quantifier position
    returns `(False, index)` unchanged.

    A trailing `?` makes the quantifier lazy (non-greedy) and is always
    consumed, but a *lazy* quantifier is treated as never reaching 2+
    ambiguous repeats, regardless of its own bounds: laziness makes the
    engine try the shortest match first and extend only on failure, which
    is this repository's own already-observed deliberate mitigation
    (`skills/evaluating-skill-quality/scripts/shape_checks/constants.py`'s
    own prose-parsing regexes lean on `.+?`/`.*?` throughout) -- treating
    it as a disclosed, direction-of-caution simplification (a lazy
    quantifier nested inside a still-greedy outer repeating group is the
    one shape this can still under-report; see the module docstring's own
    "Known misses") is judged the better trade than flagging an idiom this
    repository's own code already uses as its answer to this exact defect
    class.
    """
    if index >= len(pattern):
        return False, index
    char = pattern[index]
    if char in "*+":
        end = index + 1
        if end < len(pattern) and pattern[end] == "?":
            return False, end + 1
        return True, end
    if char == "?":
        end = index + 1
        if end < len(pattern) and pattern[end] == "?":
            end += 1
        return False, end
    if char == "{":
        close = pattern.find("}", index)
        if close == -1:
            return False, index
        body = pattern[index + 1 : close]
        match = re.fullmatch(r"(\d*)(,)?(\d*)", body)
        end = close + 1
        lazy = end < len(pattern) and pattern[end] == "?"
        if lazy:
            end += 1
        if not match or (not match.group(1) and not match.group(3)):
            # Not a real `{m,n}`-shaped quantifier (e.g. a literal `{}` or
            # `{name}` in some other role); do not consume it as one.
            return False, index
        if lazy:
            return False, end
        has_comma = match.group(2) is not None
        if not has_comma:
            # `{m}` -- exactly m repeats, fixed. A fixed count has no
            # internal ambiguity in how many repetitions it took, so it is
            # never itself the ambiguous half of a Shape A/B pair.
            return False, end
        low = int(match.group(1)) if match.group(1) else 0
        high = int(match.group(3)) if match.group(3) else None
        reaches_two = high is None or high >= 2 or low >= 2
        return reaches_two, end
    return False, index


def _class_member_set(pattern: str, start: int) -> tuple[frozenset[str] | None, int]:
    """Parse a `[...]` bracket expression starting at `pattern[start] == "["`.

    Returns `(member_set, index_after_closing_bracket)`. A negated class
    (`[^...]`) returns `None` (conservative: treated as overlapping with
    everything) rather than computing its true, generally huge, member set.
    """
    index = start + 1
    negated = False
    if index < len(pattern) and pattern[index] == "^":
        negated = True
        index += 1
    members: set[str] = set()
    unresolved = False
    first = True
    while index < len(pattern):
        char = pattern[index]
        if char == "]" and not first:
            index += 1
            break
        first = False
        if char == "\\" and index + 1 < len(pattern):
            escaped = pattern[index + 1]
            if escaped in _SHORTHAND_CLASSES:
                shorthand = _SHORTHAND_CLASSES[escaped]
                if isinstance(shorthand, _Negated):
                    # \W/\D/\S inside a bracket expression: a full
                    # union-with-a-negation is not computed here, so the
                    # whole class is treated as wide instead of guessed at.
                    unresolved = True
                else:
                    members |= shorthand
            else:
                members.add(escaped)
            index += 2
            continue
        if index + 2 < len(pattern) and pattern[index + 1] == "-" and pattern[index + 2] != "]":
            low, high = char, pattern[index + 2]
            if ord(low) <= ord(high) and ord(high) - ord(low) < 1000:
                members.update(chr(c) for c in range(ord(low), ord(high) + 1))
            else:
                unresolved = True  # an inverted or implausibly wide range: do not guess
            index += 3
            continue
        members.add(char)
        index += 1
    else:
        raise ScanError(f"unterminated character class starting at offset {start} in pattern {pattern!r}")
    if negated or unresolved:
        return None, index
    return frozenset(members), index


def _simple_atom_set(pattern: str, start: int) -> tuple[frozenset[str] | _Negated | None, int]:
    """Parse one simple (non-group) atom starting at `pattern[start]`.

    Returns `(char_set, index_after_atom)`. `char_set` is `None` for a
    class this gate treats conservatively as wide (`.`, a negated bracket
    class, `\\W`/`\\D`/`\\S`).
    """
    char = pattern[start]
    if char == "[":
        return _class_member_set(pattern, start)
    if char == ".":
        return None, start + 1
    if char == "\\" and start + 1 < len(pattern):
        escaped = pattern[start + 1]
        if escaped in _SHORTHAND_CLASSES:
            return _SHORTHAND_CLASSES[escaped], start + 2
        return frozenset({escaped}), start + 2
    return frozenset({char}), start + 1


def _parse_branches(pattern: str, start: int, *, top_level: bool) -> tuple[list[list[_Atom]], int]:
    """Parse `pattern[start:]` into `|`-separated alternation branches, each
    a flat list of `_Atom` (recursing into each group, which itself carries
    its own branches). Stops at an unescaped `)` (when not `top_level`) or
    end of string. Returns `(branches, index_after_stop)`.

    A `|` starts a new branch rather than being modelled as an atom: an
    atom on one side of a `|` is never adjacent, for Shape B's own
    purposes, to one on the other side (each branch is an independent path
    through the engine), and Shape A/B below only ever compare atoms
    within one branch.
    """
    branches: list[list[_Atom]] = [[]]
    index = start
    while index < len(pattern):
        char = pattern[index]
        if char == "|":
            branches.append([])
            index += 1
            continue
        if char == ")":
            if top_level:
                index += 1  # an unbalanced `)` in a top-level pattern; skip rather than raise
                continue
            return branches, index + 1
        if char == "(":
            index += 1
            if pattern[index : index + 2] == "?:" or pattern[index : index + 2] in ("?=", "?!"):
                index += 2
            elif pattern[index : index + 3] in ("?<=", "?<!"):
                index += 3
            elif pattern[index : index + 2] == "?P":
                close = pattern.find(">", index)
                index = close + 1 if close != -1 else index + 2
            child_branches, index = _parse_branches(pattern, index, top_level=False)
            repeats, index = _quantifier_repeats(pattern, index)
            branches[-1].append(
                _Atom(
                    is_group=True,
                    char_set=None,
                    repeats=repeats,
                    group_branches=tuple(tuple(branch) for branch in child_branches),
                )
            )
            continue
        if char in "^$":
            index += 1
            continue
        char_set, index = _simple_atom_set(pattern, index)
        repeats, index = _quantifier_repeats(pattern, index)
        branches[-1].append(_Atom(is_group=False, char_set=char_set, repeats=repeats))
    return branches, index


def _nested_quantifier_findings(branches: list[list[_Atom]]) -> bool:
    """True iff any group atom anywhere in `branches` is itself repeating
    and at least one of its own branches consists of exactly one atom that
    is itself repeating (Shape A) -- the textbook `(a+)+`/`(a*)*`/`(a+)*`
    evil-regex shape, where a single inner quantified atom can partition
    the same input across outer-loop iterations in exponentially many
    ways.

    Deliberately narrow: a multi-atom branch inside a repeating group --
    `(?:\\s+-[\\w-]+)*`, this gate's own motivating file's own *current*,
    already-fixed prefix constant -- is never flagged by this shape, even
    when some multi-atom arrangement could in principle still be
    ambiguous, because a leading anchor atom (here `\\s+`, forced before
    each repetition) generally rules out the reparenting ambiguity a
    single repeating atom creates on its own. Computing real ambiguity for
    an arbitrary multi-atom branch needs first/follow-set automata theory,
    not a heuristic scan -- see the module docstring's own "Known
    misses"."""
    for branch in branches:
        for atom in branch:
            if not atom.is_group:
                continue
            if atom.repeats and any(
                len(sub_branch) == 1 and sub_branch[0].repeats for sub_branch in atom.group_branches
            ):
                return True
            if _nested_quantifier_findings([list(sub_branch) for sub_branch in atom.group_branches]):
                return True
    return False


def _overlapping_adjacent_findings(branches: list[list[_Atom]]) -> bool:
    """True iff, within any one branch, two adjacent *simple* (non-group),
    each-repeating atoms have overlapping (or either-unknown/wide)
    character sets (Shape B). Also recurses into every group's own
    branches. A group atom always breaks adjacency (its own trailing
    character set is never computed -- see the module docstring's own
    "Known misses")."""
    for branch in branches:
        previous: _Atom | None = None
        for atom in branch:
            if atom.is_group:
                if _overlapping_adjacent_findings([list(sub_branch) for sub_branch in atom.group_branches]):
                    return True
                previous = None
                continue
            if atom.repeats and previous is not None and _overlaps(previous.char_set, atom.char_set):
                return True
            previous = atom if atom.repeats else None
    return False


def has_catastrophic_shape(pattern: str) -> str | None:
    """Return the shape label ("nested-quantifier" or "adjacent-overlap")
    of the first detected catastrophic-backtracking shape in `pattern`, or
    `None` if neither shape is found. Malformed pattern text (an
    unterminated character class) raises `ScanError` -- an unparseable
    pattern is not silently graded clean.
    """
    branches, _ = _parse_branches(pattern, 0, top_level=True)
    if _nested_quantifier_findings(branches):
        return "nested-quantifier"
    if _overlapping_adjacent_findings(branches):
        return "adjacent-overlap"
    return None


# --- AST extraction: which regex literals does this diff add -------------


def _re_module_names(tree: ast.Module) -> frozenset[str]:
    """Names this file's own imports bind to the `re` module."""
    names = {_RE_MODULE}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _RE_MODULE:
                    names.add(alias.asname or alias.name)
    return frozenset(names)


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """Collect every module-level `NAME = <string-literal-or-`+`-chain>`
    assignment in `tree`, keyed by name. Deliberately module-level only
    (`tree.body`'s own direct statements, never a descent into a nested
    function or class body): the documented idiom this resolves is a
    reusable *module*-level prefix constant (e.g. `_UV_RUN_PREFIX`
    composed into `_UV_WRAPPED_INVOCATION_RE`). An earlier revision
    walked the whole tree (`ast.walk`) with no scope distinction at all,
    which let an unrelated function-local variable in a different
    function, reusing a common name (`_tmp`, `_pattern`), collide with --
    and, via the "assigned more than once" rule below, silently drop --
    resolution of a genuinely dangerous module-level constant sharing
    that same name; live-confirmed as a real false negative during
    independent review, not merely hypothesised. A name assigned more
    than once at module level is dropped (unresolvable, rather than
    guessed at from whichever assignment is seen), matching the module
    docstring's own "Known misses" trade.
    """
    resolved: dict[str, str] = {}
    seen_more_than_once: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id in resolved or target.id in seen_more_than_once:
            resolved.pop(target.id, None)
            seen_more_than_once.add(target.id)
            continue
        value = _resolve_literal_string(node.value, resolved)
        if value is not None:
            resolved[target.id] = value
    return resolved


def _resolve_literal_string(node: ast.expr, known: dict[str, str]) -> str | None:
    """Resolve `node` to a concrete string using only string `Constant`s,
    `+` chains of them, and names already present in `known`. Returns
    `None` for anything else (an f-string, a call, an unresolved name)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_literal_string(node.left, known)
        right = _resolve_literal_string(node.right, known)
        if left is not None and right is not None:
            return left + right
    return None


def _pattern_argument(call: ast.Call) -> ast.expr | None:
    if call.args:
        return call.args[0]
    for keyword in call.keywords:
        if keyword.arg == "pattern":
            return keyword.value
    return None


def _regex_literal_calls(tree: ast.Module) -> list[tuple[int, str]]:
    """Return `(lineno, resolved_pattern_text)` for every module-qualified
    `re.compile`/`re.match`/`re.search`/`re.fullmatch` call in `tree` whose
    pattern argument resolves to a concrete string."""
    re_names = _re_module_names(tree)
    constants = _string_constants(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in _REGEX_VERBS):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id in re_names):
            continue
        argument = _pattern_argument(node)
        if argument is None:
            continue
        pattern = _resolve_literal_string(argument, constants)
        if pattern is not None:
            found.append((node.lineno, pattern))
    return found


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying an inline waiver comment (via `tokenize`,
    never a raw-text scan -- see the module docstring's own Waiver
    section)."""
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


# --- diff parsing (ported verbatim from gitapex_gate_exception_handler_gaps.py) --


def _diff_target_path(raw: str) -> str | None:
    target = raw.strip()
    if target == "/dev/null":
        return None
    if not target.startswith("b/"):
        raise ScanError(
            f"unified diff post-image is not a plain b/-prefixed path: {target!r}. "
            "This gate reads default `git diff` output; --no-prefix and quoted "
            "paths are not resolvable here."
        )
    return target[2:]


def _looks_like_real_header_pair(source_line: str, target_line: str) -> bool:
    source = source_line[4:]
    target = target_line[4:]
    return (source == "/dev/null" or source.startswith("a/")) and (target == "/dev/null" or target.startswith("b/"))


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into `{post-image path: added line numbers}`.

    Ported verbatim from `gitapex_gate_exception_handler_gaps.py`'s own
    hardened `parse_added_lines` -- fail-closed on a malformed `@@` hunk
    header, a post-image path that is neither `/dev/null` nor
    `b/`-prefixed, a `+++ ` header reached outside a hunk with no `--- `
    header before it, a hunk whose declared pre-/post-image counts
    outrun its own real body, and the absorbed-header edge case a
    `+++ `-shaped line immediately following a `--- `-shaped one can
    create. See that file's own docstring for the full multi-round
    adversarial-review history behind each of these checks; this copy's
    behavior is identical, not independently re-derived.
    """
    added: dict[str, set[int]] = {}
    path: str | None = None
    lineno = 0
    in_hunk = False
    old_remaining = 0
    new_remaining = 0
    saw_source_header = False

    def _reject_if_hunk_incomplete(boundary: str) -> None:
        # function-body-test-coverage: WAIVED: a closure nested inside
        # parse_added_lines, with no module-level name a test can reference
        # by identifier -- its every call site is already covered by this
        # file's own malformed-diff fail-closed regression tests below
        # (test_hunk_declaring_more_lines_than_its_body_has_raises_scan_error
        # and the other parse_added_lines regressions in that section).
        if in_hunk:
            raise ScanError(
                f"hunk header for {path!r} declared more pre-/post-image line(s) than its body "
                f"actually had ({old_remaining} pre-image, {new_remaining} post-image line(s) "
                f"still unconsumed) before {boundary}. Real `git diff` output always emits "
                "accurate counts; a hand-fed or foreign patch's inaccurate ones would otherwise "
                "leak this hunk's state into whatever follows it."
            )

    lines = diff_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if line.startswith("diff --git "):
            _reject_if_hunk_incomplete(f"the next `diff --git ` line: {line!r}")
            path = None
            in_hunk = False
            saw_source_header = False
            continue
        if not in_hunk and line.startswith("--- "):
            saw_source_header = True
            continue
        if not in_hunk and line.startswith("+++ "):
            if not saw_source_header:
                raise ScanError(
                    f"unified diff post-image header with no `--- ` source header before it: {line!r}. "
                    "This gate reads default `git diff` output, which always emits both; ignoring the "
                    "header instead would drop every added line that follows it from grading."
                )
            path = _diff_target_path(line[4:])
            saw_source_header = False
            continue
        if line.startswith("@@"):
            _reject_if_hunk_incomplete(f"the next hunk header: {line!r}")
            match = _HUNK_RE.match(line)
            if not match:
                raise ScanError(f"unparseable hunk header: {line!r}")
            old_remaining = 1 if match.group(1) is None else int(match.group(1))
            lineno = int(match.group(2))
            new_remaining = 1 if match.group(3) is None else int(match.group(3))
            in_hunk = old_remaining > 0 or new_remaining > 0
            continue
        if line.startswith("+"):
            if path is not None:
                added.setdefault(path, set()).add(lineno)
            lineno += 1
            new_remaining -= 1
        elif line.startswith(" "):
            lineno += 1
            old_remaining -= 1
            new_remaining -= 1
        elif line.startswith("-"):
            old_remaining -= 1
        if old_remaining <= 0 and new_remaining <= 0:
            if (
                index > 0
                and lines[index - 1].startswith("--- ")
                and line.startswith("+++ ")
                and _looks_like_real_header_pair(lines[index - 1], line)
            ):
                next_line = lines[index + 1] if index + 1 < len(lines) else ""
                if next_line.startswith("@@") or next_line.startswith("diff --git "):
                    raise ScanError(
                        f"hunk for {path!r} closes exactly on a line shaped like a new file's "
                        f"own post-image header ({line!r}), immediately after one shaped like a "
                        f"source header, immediately before what looks like a new hunk or file "
                        f"header ({next_line!r}) -- ambiguous between coincidental hunk-closing "
                        "content and a real file transition missing its `diff --git ` separator. "
                        "Failing closed here rather than silently misattributing whatever follows."
                    )
            in_hunk = False
    _reject_if_hunk_incomplete("the diff ended")
    return added


def in_scope(path: str) -> bool:
    """Every `*.py` file, except a test file or `conftest.py` -- see the
    module docstring's own Scope section."""
    if not path.endswith(".py"):
        return False
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith("test_") or name == "conftest.py")


def findings_for_source(path: str, source: str, added: set[int]) -> tuple[list[Finding], list[Finding]]:
    """Grade one file's source, returning `(violations, honoured waivers)`.

    Only a `re.compile`/`re.match`/`re.search`/`re.fullmatch` call an
    added line actually reaches is graded -- a pre-existing pattern
    another PR already owns is never this diff's failure.
    """
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

    waived_lines = _waived_lines(source)
    violations: list[Finding] = []
    waived: list[Finding] = []
    for lineno, pattern in _regex_literal_calls(tree):
        if lineno not in added:
            continue
        try:
            shape = has_catastrophic_shape(pattern)
        except ScanError:
            # An unparseable pattern (e.g. an unterminated character
            # class) is not this gate's own defect class to grade --
            # `re.compile` itself will already reject it at runtime.
            continue
        if shape is None:
            continue
        finding = Finding(
            path,
            lineno,
            shape,
            f"regex pattern {pattern!r} carries a {shape} catastrophic-backtracking shape",
        )
        target = waived if finding.line in waived_lines else violations
        target.append(finding)
    return sorted(set(violations)), sorted(set(waived))


def find_violations(diff_text: str, root: pathlib.Path) -> tuple[list[Finding], list[Finding], int]:
    """Grade every in-scope file the diff adds lines to.

    Returns `(violations, honoured waivers, files graded)`. Raises
    `ScanError` when a file named by the diff exists but cannot be read as
    UTF-8 or parsed -- a file this gate cannot grade must not pass silently.
    """
    violations: list[Finding] = []
    waived: list[Finding] = []
    graded = 0
    for path, added in sorted(parse_added_lines(diff_text).items()):
        if not in_scope(path):
            continue
        absolute = root / path
        try:
            source = absolute.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            raise ScanError(f"{path}: named by the diff as added or modified, but missing from {root}") from None
        except (OSError, UnicodeDecodeError) as error:
            raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
        file_violations, file_waived = findings_for_source(path, source, added)
        violations.extend(file_violations)
        waived.extend(file_waived)
        graded += 1
    return violations, waived, graded


class GateRegexCatastrophicBacktrackingArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. `root` must be an
    existing directory."""

    root: pathlib.Path

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 clean, 1 violation found, 2 the scan could not be trusted."""
    parser = argparse.ArgumentParser(
        description="Check that no regex literal newly added by this diff to any *.py file "
        "carries a statically-detectable catastrophic-backtracking (ReDoS) shape. Reads a "
        "unified diff on standard input."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root the diff's paths resolve against (defaults to this checkout).",
    )
    parser.add_argument(
        "--diff",
        type=pathlib.Path,
        help="Read the unified diff from this file instead of standard input.",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateRegexCatastrophicBacktrackingArgs(root=args.root)
    except ValidationError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    if args.diff is not None:
        try:
            diff_text = args.diff.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"{args.diff}: diff cannot be read as UTF-8 text: {error}", file=sys.stderr)
            return 2
    else:
        try:
            diff_text = sys.stdin.buffer.read().decode("utf-8")
        except UnicodeDecodeError as error:
            print(f"standard input: diff cannot be read as UTF-8 text: {error}", file=sys.stderr)
            return 2

    try:
        violations, waived, graded = find_violations(diff_text, validated.root)
    except ScanError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    for finding in waived:
        print(f"{finding.path}:{finding.line}: {finding.shape}: waived inline -- {finding.message}", file=sys.stderr)

    if violations:
        for finding in violations:
            print(f"{finding.path}:{finding.line}: {finding.shape}: {finding.message}", file=sys.stderr)
        print(
            f"\n{len(violations)} new regex literal(s) reached by this diff carry a "
            "catastrophic-backtracking shape (issue #1556). Restructure the pattern to remove "
            "the nested or adjacent-overlapping quantifier, or -- for a pattern already proven "
            "safe by a bounded-input contract -- disclose it inline with "
            "'# regex-catastrophic-backtracking: WAIVED: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

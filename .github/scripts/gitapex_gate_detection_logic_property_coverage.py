#!/usr/bin/env python3
"""CI gate: new or materially changed regex-, path-resolution-, or
string-comparison-based detection logic, added by this diff to one of this
repository's own checker scripts, must be covered by a co-located
Hypothesis ``@given`` property test.

Issue #1178. Formally supersedes the scope limit issue #939 set for the
Hypothesis property-based pilot -- ``tests/test_gitapex_gate_metadata_outcome_lines_
properties.py``'s own docstring states plainly "this module is the whole
rollout, and no other parser-shaped script under ``.github/scripts/`` or
``evals/scripts/`` is in scope until this layer has demonstrated it catches a
real defect here." That bar is why this gate exists rather than a repeat of
the pilot: issues #1129, #1032 and #1061 are the fail-open, symlink-
resolution and allowlist-bypass defects that, together, are cited as having
already demonstrated the catch class the pilot was waiting for.

**The motivating catch (issue #1129).** Commit ``6bef4ba`` (issue #845)
shipped ``skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py``'s
``_parse_manifest`` with an ``executionRequirements.packages`` key check
compiled once at module level --
``EXEC_REQ_PACKAGES_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")`` -- and then
called as a bound method inside ``_parse_manifest`` itself:
``EXEC_REQ_PACKAGES_KEY_RE.match(key)``. ``.match()`` anchors only at the
*start* of the string; ``EXEC_REQ_PACKAGES_KEY_RE`` names no ``$``-anchored
alternative of its own past the pattern's built-in ``$``, so the visible
defect was narrower than "anything passes" -- but the shape is exactly the
one this gate exists to catch: a bound-method call site with no
``re.compile(...)`` anywhere near it in the same diff, because the
``re.compile(...)`` that built the pattern sat on an earlier, unrelated line.
The call site is now ``EXEC_REQ_PACKAGES_KEY_RE.fullmatch(key)`` (still
inside ``_parse_manifest``, currently at line 2515 of that file). A gate that
only triggered on a bare ``re.compile(...)`` call would have missed this
call site outright -- see "Why the regex trigger is receiver-agnostic"
below, which is this defect's own direct consequence.

**Out of this gate's own scope, stated plainly rather than overclaimed
(issue #1032).** A hostname-truncation defect in
``skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py``.
That file's own name starts with ``gitapex_scan_``, not ``gitapex_check_`` or
``gitapex_gate_``, and ``_IN_SCOPE_RE`` below never matches a
``gitapex_scan_*.py`` path by construction -- every alternative requires one
of those two fixed prefixes. This gate would **not** have caught #1032, and
does not claim to; widening ``_IN_SCOPE_RE`` to also cover ``gitapex_scan_*.py``
is a measurement to make deliberately, the same way ``gitapex_gate_exception_
handler_gaps.py``'s own docstring describes measuring a scope widening
before shipping it, not a gap to paper over here.

Scope
-----
In-scope paths are this repository's own detection-logic-bearing checker
scripts: ``skills/*/scripts/gitapex_check_*.py``, ``.github/scripts/
gitapex_gate_*.py`` and ``hooks/gitapex_check_*.py`` -- narrower than
``gitapex_gate_exception_handler_gaps.py``'s own four-directory, any-``.py``-name
scope, because the defect class here (a detection primitive silently
mis-matching) is specific to scripts whose whole job is pattern-matching
untrusted input, which this repository already spells with the
``gitapex_check_``/``gitapex_gate_`` naming convention. As with that gate,
``[^/]+`` segments and ``re.fullmatch`` (never ``re.match``, so a trailing
newline cannot forge a match) keep every alternative from crossing a
directory separator.

A file matching ``_IN_SCOPE_RE`` is excluded when its basename starts with
``test_`` or equals ``conftest.py`` -- the same exclusion ``in_scope()`` in
``gitapex_gate_exception_handler_gaps.py`` applies, for the same reason: a
test file feeding this gate's own subject malformed input, or a fixture
co-located with its source, is doing its job and has no contract to carry a
property test of its own. A co-located ``test_<name>.py`` sitting next to its
source in a ``scripts/`` directory is a real, confirmed shape in this
repository today (e.g. ``skills/evaluating-skill-quality/scripts/
test_gitapex_scan_execution_requirements_drift.py``), so the exclusion is
applied defensively rather than assumed unreachable by ``_IN_SCOPE_RE``'s own
fixed-prefix construction.

Trigger categories
-------------------
Three, each an AST shape reached by an added diff line inside an in-scope
file. A trigger is either an ``ast.Call`` or (only for the ``in``/``not in``
shape below) an ``ast.Compare``.

**(a) regex.** Either an attribute call ``re.compile(...)`` / ``re.match(...)``
/ ``re.search(...)`` / ``re.fullmatch(...)`` whose receiver is a bare name
*this file's own imports bind to the* ``re`` *module*, OR a
receiver-agnostic bound-method call ``.match(...)`` / ``.search(...)`` /
``.fullmatch(...)`` on *any* receiver, matched by the call's own final
attribute name alone. ``.compile(...)`` is deliberately not in the
receiver-agnostic set: an unrelated object's ``.compile(...)`` (a template,
a schema, a query builder) is not detection logic, and reporting it would be
a pure over-report with no defect class behind it.

*Why the compile receiver is resolved through this file's imports rather
than hard-coded to the literal name* ``re``. ``_re_module_names`` below
collects every name an ``import re`` in the graded file binds to the ``re``
module -- ``re`` itself, plus any ``import re as <alias>`` alias -- so
``import re as _re`` followed by ``_re.compile(r"...")`` is graded exactly
as ``re.compile(r"...")`` is. Matching the literal name alone left a
one-word evasion of category (a)'s whole compile half: a diff that adds
only a pattern *definition* (the shape a materially changed allowlist regex
takes, and the half of issue #1129's own defect that sat away from the call
site) graded clean purely because the module was imported under another
name. This mirrors what trigger (b) below already does for ``os`` -- an
aliased ``import os as o; o.path.realpath(...)`` matches there too -- and
what ``_imports_module`` already does when matching the properties file's
own import of the module under test. The name set is only ever *widened*
past the bare ``re``, never narrowed, so no call site graded before this
resolution existed stops being graded because of it.

*Why the regex trigger is receiver-agnostic.* This repository's own regex
usage overwhelmingly compiles a pattern once as a module-level constant and
calls a bound method on it at the real call site --
``EXEC_REQ_PACKAGES_KEY_RE = re.compile(...)`` then
``EXEC_REQ_PACKAGES_KEY_RE.fullmatch(key)``; ``gitapex_gate_exception_handler_
gaps.py``'s own ``_WAIVER_RE.search(...)`` and ``_HUNK_RE.match(...)`` are two
more instances in the very file this gate's architecture mirrors. Issue
#1129's own defect (above) is precisely a bound-method call site with no
``re.compile(...)`` anywhere in the same diff. A bare ``re.compile(...)``
trigger alone would report a new pattern being *defined* but never the line
that actually *uses* it against untrusted input -- which is the line the
defect lived on. This is a deliberate, disclosed widening past a literal
reading of "re.compile/re.match/re.search/re.fullmatch," and it is also a
disclosed over-report: see "Known over-reports" below.

**(b) path-resolution.** Receiver-agnostic method calls ``.resolve(...)``,
``.is_symlink(...)``, ``.relative_to(...)`` on any receiver; plus attribute
calls ``os.path.realpath(...)`` / ``os.path.abspath(...)``, matched
receiver-agnostically on the call's own final *two* attribute segments (so
an aliased ``os`` import -- ``import os as o; o.path.realpath(...)`` --
still matches).

**(c) string-comparison allowlist/denylist.** Receiver-agnostic method calls
``.startswith(...)``, ``.endswith(...)`` on any receiver; OR an
``ast.Compare`` with exactly one ``In``/``NotIn`` operator whose right-hand
comparator is an inline ``List``/``Tuple``/``Set`` literal; OR a call to
``frozenset(...)``/``set(...)`` whose sole argument is itself an inline
``List``/``Tuple``/``Set`` literal -- this repository's own pervasive
``frozenset({...})`` idiom written directly at the comparison site (e.g.
this gate's own ``_REGEX_RECEIVER_AGNOSTIC_ATTRS`` below, or
``gitapex_gate_exception_handler_gaps.py``'s ``_DECODE_COVERING`` /
``_JSON_COVERING`` / ``_SUBSTITUTING_ERRORS`` / ``_MAPPING_TYPES``). A name
reference to a previously-defined collection constant (``x in
SOME_MODULE_CONSTANT``) is a **deliberate, disclosed miss**: resolving a name
to its definition elsewhere in the file is exactly the machinery
``gitapex_gate_exception_handler_gaps.py``'s own ``_handler_names`` docstring
records three separate attempts at, each reverted as more costly than it
was worth. That lesson is taken as read here rather than relearned.

Scope/function attribution
---------------------------
For each in-scope file, the *whole* file's AST is walked once (not
diff-scoped, so a trigger's enclosing function is found correctly regardless
of where in the file it sits) to record every ``FunctionDef``/
``AsyncFunctionDef``'s own line range, ``lineno`` through ``end_lineno``
inclusive. Nested functions get their own, narrower range, always fully
contained within their parent's -- a property of Python's own grammar, not
something this gate computes -- so the range with the smallest span among
every range containing a trigger's line is always the innermost enclosing
one. A trigger whose line falls inside no such range is attributed to the
sentinel scope name ``"<module>"``. A decorator expression or a default
argument value written on the ``def`` line itself is graded against
whichever range contains *that* line, the same "evaluated where written"
treatment ``gitapex_gate_exception_handler_gaps.py``'s own ``_handler_coverage``
gives decorators and defaults -- but arrived at here as a byproduct of plain
line-range containment, not a separate walk.

Existing-coverage check
------------------------
For a source file at repo-relative path ``P`` with stem ``S`` (``.github/
scripts/gitapex_gate_foo.py`` -> ``S = "gitapex_gate_foo"``), the co-located
properties file is ``tests/test_{S}_properties.py`` -- exactly the naming
precedent ``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``
already sets for ``.github/scripts/gitapex_gate_metadata_outcome_lines.py``
(issue #939's own pilot). For a scope name ``F`` (a function name, or
``"<module>"``):

* If the properties file does not exist, cannot be read, or cannot be
  parsed as Python -- three distinct conditions collapsed into one verdict,
  deliberately: the *source* file's own triggers are still fully enumerable
  without it, so the scan itself stays trustworthy and there is no reason to
  exit 2 over a coverage file this gate does not itself need to run --
  every scope in that source file is UNCOVERED.
* Otherwise its AST is parsed, and a scope is UNCOVERED unless the
  properties file both (1) imports the source module (``import {S}`` or
  ``from {S} import ...``, matched on the bare module name so an aliased
  import -- ``import {S} as gate``, the real shape ``tests/test_gitapex_gate_
  metadata_outcome_lines_properties.py`` uses today -- still counts) and (2)
  contains at least one ``@given(...)``-decorated function (matched on the
  decorator's own final attribute/name being ``given``, so both ``@given``
  and ``@hypothesis.given`` count) such that: for a real function scope,
  that specific ``@given`` function's own body (only its body -- not its
  decorators, not the rest of the file) contains a ``Name``/``Attribute``
  node whose final name equals ``F``; for the ``"<module>"`` scope, any
  ``@given`` function anywhere in the file clears it, since a bare
  module-level constant has no function identity of its own to search a
  body for.

**Known misses, each disclosed rather than found later.** This is a
textual/AST identifier-presence heuristic, not true call-graph or data-flow
analysis:

* A same-named local variable, loop target, parameter, or nested ``def``
  inside a ``@given`` function's own body reads as "mentions ``F``" under
  this check exactly as a real call to ``F`` would -- a false clear. Only an
  ``ast.Name``/``ast.Attribute`` node is matched, so this does not extend to
  free text: a comment or a docstring naming ``F`` is not itself a
  ``Name``/``Attribute`` node and moves nothing.
* A property test that exercises ``F`` only through an indirection -- a
  helper or wrapper it imports and calls, which itself calls ``F`` -- never
  mentions ``F`` by name in the ``@given`` function's own body and is a
  false flag: this gate reports it uncovered even though it is exercised.
* Both are accepted, disclosed misses, in the same spirit as the collection-
  constant miss in trigger category (c) above: closing either needs the
  same name-resolution machinery already measured and reverted three times
  in ``gitapex_gate_exception_handler_gaps.py``.

**Known misses in the trigger table itself.** Separate from the coverage
heuristic above: these are shapes the three trigger categories do not
report at all, listed so a reader is never surprised by one later.

* **Only four regex verbs are graded.** ``compile``/``match``/``search``/
  ``fullmatch``, and nothing else. ``re.sub(...)``, ``re.split(...)``,
  ``re.findall(...)``, ``re.finditer(...)`` and their bound-method forms
  are not triggers, in either the module-qualified or the
  receiver-agnostic spelling, even though all four run a pattern against
  untrusted text. This is a trade, not an oversight: the receiver-agnostic
  half of category (a) matches on the final attribute name alone, and
  ``.split(...)`` is one of the most common plain-``str`` method calls in
  this repository, so adding it would report a large body of code that
  touches no regex at all. Widening the verb set is a measurement to run
  and triage first, exactly as this gate's own ``_IN_SCOPE_RE`` paragraph
  says about widening to ``gitapex_scan_*.py``.
* **A member imported out of its module is not graded.**
  ``from re import compile`` then a bare ``compile(...)``, or
  ``from os.path import realpath`` then a bare ``realpath(...)``, reaches
  neither category (a) nor (b): both match an ``ast.Attribute`` callee, and
  these spell an ``ast.Name`` one. ``_re_module_names`` resolves an aliased
  *module* import, which is a fixed one-name lookup; resolving an aliased
  *member* import is the same trade
  ``gitapex_gate_exception_handler_gaps.py`` records making for
  ``from json import loads``, with the extra hazard that ``compile`` is
  also a builtin, so a bare ``compile(...)`` cannot be graded on its name
  alone. Neither spelling occurs in the graded directories today: all 203
  compile call sites there are written ``re.compile(``, and no graded file
  carries a ``from re import ...`` at all. That is a measurement of current
  state, though, not a property anything enforces -- which is exactly why
  the *module*-alias half above is resolved rather than left to the same
  assumption.
* **Two findings of the same rule on one physical line report once.**
  ``x in ["a", y.startswith("b")]`` is a single ``string-comparison-
  property-gap``, because findings are deduplicated by
  ``(path, line, rule, message)`` and all four are identical for two
  category-(c) triggers in one scope on one line -- the same dedup
  ``gitapex_gate_exception_handler_gaps.py`` documents for its own rules,
  and for the same reason: printing one line twice with identical text
  tells a contributor nothing about which trigger is meant. Two triggers of
  *different* categories on one line do still report twice, since the rule
  and message differ. One waiver on that line likewise covers every finding
  reported at it, so a contributor waiving the trigger they meant also
  waives one they may not have looked at; put the waiver where the error
  points, and only after reading the whole line.
* **Two in-scope source files sharing a basename share one properties
  file too.** ``_stem`` and ``_properties_path`` key on the file's own
  basename alone, not its full path, so
  ``skills/drafting-issues/scripts/gitapex_check_acm_present.py``
  and ``skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py``
  -- a real, already-present basename collision in this repository's own
  in-scope set, confirmed live rather than hypothesised -- both resolve to
  the identical ``tests/test_gitapex_check_acm_present_properties.py``.
  Neither file has one yet, so this is latent, not currently
  false-clearing anything; the day one does, a single ``@given`` test
  there clears coverage findings for both files' triggers, whichever one
  the test's own author was actually thinking about. Scoping the
  properties-file name to the source's full diff-relative path (not just
  its basename) would close this, at the cost of a longer, directory-
  shaped test filename -- left as a design trade-off for whoever adds the
  first properties file under either of these two directories, not solved
  here.

**Known over-reports**, each a direct, disclosed consequence of a
receiver-agnostic trigger rather than a bug to fix quietly:

* ``.match(...)``/``.search(...)``/``.fullmatch(...)`` on a receiver that is
  not a compiled pattern at all -- a hand-rolled tokenizer's own
  ``.match(token)``, a test double's ``.search(...)`` -- is reported the
  same as a real regex call, for the reason given under trigger (a) above.
* ``.resolve(...)``/``.is_symlink(...)``/``.relative_to(...)`` on a receiver
  that is not a ``pathlib.Path`` is reported the same way.
* ``<name>.path.realpath(...)``/``<name>.path.abspath(...)`` is matched on
  the final two attribute segments alone, with no check that ``<name>``
  itself resolves to the ``os`` module -- an unrelated object that happens
  to expose a ``.path.realpath(...)`` chain is reported.
* ``frozenset([...])``/``set([...])`` is reported whenever its sole argument
  is an inline literal, whether or not the resulting collection is ever used
  in a membership comparison -- building a set for iteration alone, not an
  allowlist/denylist check, still triggers category (c).

Waiver
------
``# detection-logic-property-coverage: WAIVED: <reason>`` -- a non-whitespace
reason is mandatory, matched via ``tokenize`` exactly like
``gitapex_gate_exception_handler_gaps.py``'s own ``_waived_lines``/``_WAIVER_RE``
(only the fixed prefix string differs), so the marker is honoured only as a
real comment token and never inside a string literal quoting this gate's own
documentation. It waives every finding reported on that exact line.

Exit codes
----------
0 clean, 1 violation found, 2 the scan could not be trusted -- a malformed
diff, an in-scope file that cannot be read or parsed, or a ``--root`` that is
not an existing directory. Never a silent pass on an ungradable input: this
is dimension 15 of ``skills/evaluating-deterministic-gate-quality/references/
dimensions.md``, "Fail-closed default on incomplete or malformed input." A
malformed diff includes an unparseable ``@@`` hunk header, a post-image path
that is neither ``/dev/null`` nor ``b/``-prefixed, a ``+++ `` post-image
header reached outside a hunk with no ``--- `` source header before it, and
a hunk whose declared pre-/post-image counts do not match its own real
body (issue #1193) -- see ``parse_added_lines`` for why each of those has
to raise rather than be tolerated.

Invocation shape
-----------------
This gate's own ``.gitapex/ssot.json`` registration gives it a
``local_invocation``/``local_stdin`` pair matching
``gitapex_gate_exception_handler_gaps.py``'s own entry exactly:
``local_stdin`` is
``["uv", "run", "--frozen", "python3",
".github/scripts/gitapex_run_base_diff.py", "--", "*.py"]`` (issue #1345;
before that issue it was a raw ``git diff --merge-base origin/main HEAD``
invocation, which failed outright in a restricted-refspec clone --
``gitapex_run_base_diff.py`` self-heals a missing ``origin/main`` by
fetching it, then execs the same ``git diff`` this gate always received,
byte-for-byte). This script therefore accepts the identical
``--root``/stdin-diff CLI shape that gate accepts, so the same invocation
wires either one.

Usage::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_detection_logic_property_coverage.py

Both flags are load-bearing for the same reason they are in
``gitapex_gate_exception_handler_gaps.py``: rename detection would hide a file
newly promoted into a graded directory behind a zero-added-line header, and
``core.quotePath`` renders a non-ASCII path as an escaped string this gate
cannot resolve (such a path exits 2, fail-closed, rather than being guessed
at).

Reads a unified diff on stdin; diagnostics and violations go to stderr. Run
via ``uv run`` (the pydantic import needs it) or via the pytest gate in
``tests/test_gitapex_gate_detection_logic_property_coverage_properties.py``.
"""

from __future__ import annotations

import argparse
import ast
import io
import pathlib
import re
import sys
import tokenize
from collections.abc import Iterator
from typing import NamedTuple

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Only `gitapex_check_*.py` under skills/*/scripts/ and hooks/, and
# `gitapex_gate_*.py` under .github/scripts/ -- narrower than
# gitapex_gate_exception_handler_gaps.py's own four-directory, any-name scope.
# `gitapex_scan_*.py` never matches by construction (see the module
# docstring's own #1032 paragraph): every alternative below fixes the prefix
# to `gitapex_check_` or `gitapex_gate_`, and none allow `gitapex_scan_`.
# `[^/]+` segments and re.fullmatch (never re.match, which would also accept
# a trailing newline) keep every alternative from crossing a directory
# separator, matching _IN_SCOPE_RE's own construction in that file.
_IN_SCOPE_RE = re.compile(
    r"skills/[^/]+/scripts/gitapex_check_[^/]+\.py"
    r"|\.github/scripts/gitapex_gate_[^/]+\.py"
    r"|hooks/gitapex_check_[^/]+\.py"
)

_MODULE_SCOPE = "<module>"

# Category (a): `.compile(...)` is receiver-specific -- graded only on a bare
# name the graded file's own imports bind to this module (see
# `_re_module_names`) -- while these three are receiver-agnostic, per the
# module docstring's "Why the regex trigger is receiver-agnostic".
_RE_MODULE = "re"
_REGEX_RECEIVER_AGNOSTIC_ATTRS = frozenset({"match", "search", "fullmatch"})

# Category (b): resolve/is_symlink/relative_to are receiver-agnostic on any
# object; realpath/abspath are matched only as the final two segments of an
# os.path.* attribute chain (see _path_resolution_trigger).
_PATH_RESOLUTION_RECEIVER_AGNOSTIC_ATTRS = frozenset({"resolve", "is_symlink", "relative_to"})
_OS_PATH_ATTRS = frozenset({"realpath", "abspath"})

# Category (c): startswith/endswith are receiver-agnostic; frozenset/set are
# graded only when called with a single inline collection-literal argument,
# this repository's own frozenset({...})-at-the-comparison-site idiom.
_STRING_COMPARISON_RECEIVER_AGNOSTIC_ATTRS = frozenset({"startswith", "endswith"})
_COLLECTION_LITERAL_CALL_NAMES = frozenset({"frozenset", "set"})

_REGEX_GAP = "regex-property-gap"
_PATH_RESOLUTION_GAP = "path-resolution-property-gap"
_STRING_COMPARISON_GAP = "string-comparison-property-gap"

_TRIGGER_LABEL: dict[str, str] = {
    _REGEX_GAP: "a regex compile/match/search/fullmatch call",
    _PATH_RESOLUTION_GAP: "a path-resolution call (.resolve()/.is_symlink()/.relative_to()/"
    "os.path.realpath()/os.path.abspath())",
    _STRING_COMPARISON_GAP: "a string-comparison allowlist/denylist check (.startswith()/"
    ".endswith()/an `in`-literal comparison/frozenset()/set())",
}

# `# detection-logic-property-coverage: WAIVED: <reason>` -- a reason is
# mandatory, the same "WAIVED: <reason>" vocabulary
# gitapex_gate_exception_handler_gaps.py's own _WAIVER_RE requires. A bare
# marker with no reason is not a waiver and is not honoured.
_WAIVER_RE = re.compile(r"#\s*detection-logic-property-coverage\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation: a trigger call this diff reaches with no
    property test covering its enclosing scope."""

    path: str
    line: int
    rule: str
    message: str


def in_scope(path: str) -> bool:
    """Return True iff `path` is a checker script this gate grades.

    Test files are excluded everywhere: a test that feeds a gate malformed
    input, or reads a fixture it just wrote, is doing its job and has no
    property-coverage contract of its own. See the module docstring's own
    "Scope" section for why this exclusion is applied defensively even
    though `_IN_SCOPE_RE`'s fixed `gitapex_check_`/`gitapex_gate_` prefixes
    already reject most `test_*.py` names outright.
    """
    if not _IN_SCOPE_RE.fullmatch(path):
        return False
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith("test_") or name == "conftest.py")


def _stem(path: str) -> str:
    """Return the source module stem for a diff-relative path, e.g.
    ".github/scripts/gitapex_gate_foo.py" -> "gitapex_gate_foo". Plain string
    manipulation on the diff-relative POSIX path, matching `in_scope`'s own
    basename extraction rather than a filesystem `pathlib` call -- `path`
    here is never resolved against a real filesystem.
    """
    return path.rsplit("/", 1)[-1].removesuffix(".py")


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null` (a deletion, which adds nothing to grade).

    Anything other than `/dev/null` or git's own `b/`-prefixed post-image
    raises ``ScanError`` rather than being guessed at -- a git-quoted path
    and a `--no-prefix` diff both land here. Guessing wrong silently drops a
    file from grading. Mirrors `gitapex_gate_exception_handler_gaps.py`'s own
    `_diff_target_path` exactly: the calling workflow always invokes plain
    `git diff`, so this is a wiring error, not a contributor's.
    """
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
    """True if `source_line`/`target_line` have the exact shape a real
    `--- `/`+++ ` header pair always has, not just its 4-character prefix.

    `source_line` must be `--- ` followed by `a/<path>` or `/dev/null`;
    `target_line` must be `+++ ` followed by `b/<path>` or `/dev/null`.
    Ordinary hunk content that happens to start `-- `/`++ ` (a changelog
    marker, a divider, this file's own docstring examples) essentially
    never also has this shape by coincidence, so it is a far sharper
    signal than the prefix alone. Deliberately silent on whether the two
    paths match -- a renamed file's own real header pair names a
    different path on each side -- this only rules out content that
    plainly is not header-shaped at all, not a full re-validation of
    `_diff_target_path`'s own stricter, raise-on-mismatch check.
    """
    source = source_line[4:]
    target = target_line[4:]
    return (source == "/dev/null" or source.startswith("a/")) and (target == "/dev/null" or target.startswith("b/"))


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into ``{post-image path: added line numbers}``.

    Only added lines are recorded -- a removal has no code left at it to
    grade, and an unchanged context line is pre-existing content another PR
    already owns. File headers are recognised only *outside* a hunk (so an
    added/removed line whose own content begins `++ `/`-- ` is never misread
    as a header), and `@@`, `diff --git ` and `index ` need no such guard
    since every hunk line carries its own one-character prefix.

    A `+++ ` post-image header reached outside a hunk with no `--- ` source
    header before it raises ``ScanError``. This was one of two places this
    function deliberately diverged from
    `gitapex_gate_exception_handler_gaps.py`'s own otherwise-identical
    `parse_added_lines`, which used to silently ignore such a header
    instead: ignoring it leaves `path` at None, so every added line in
    every hunk that follows is dropped and the run reports `OK: 0 in-scope
    file(s) graded` and exits 0 -- a silent pass on an input this gate
    could not grade, which is exactly what the module docstring's own
    "Exit codes" section promises never happens. Issue #1184 ported this
    same raise into that file's own `parse_added_lines`, so the two are
    no longer divergent here -- both fail closed identically. Real `git
    diff` output always emits `--- ` before `+++ `, so no wired invocation
    reaches this; `--diff <file>` accepts a patch from anywhere, and a
    fail-closed gate does not get to assume its input came from the
    wiring.

    `in_hunk` is bounded by the hunk's own declared line counts, not only by
    the next `diff --git ` line. Without that bound, a patch carrying no
    `diff --git ` header between two files' own hunks would leave `in_hunk`
    True straight through the second file's `--- `/`+++ ` lines: `--- `
    reads as a harmless removal-shaped no-op, but `+++ ` then reads as
    *content* (its own leading `+`) and gets added to the *first* file's
    `path` at a stale `lineno` -- and because that `+++ ` line was never
    recognised as a header, `path` never advances to the second file at
    all, so its own real added lines misattribute to the first file's path
    too.

    Both the pre-image and post-image counts are tracked (`old_remaining`,
    `new_remaining`; each `,<count>` `_HUNK_RE` captures, defaulting to 1
    when omitted, per unified-diff shorthand), not the post-image count
    alone -- issue #1184's fix for this same gap in
    `gitapex_gate_exception_handler_gaps.py`'s own copy of this function
    used post-image count alone at first, which regressed a real,
    CI-reachable case ported here directly rather than rediscovered: `git
    diff -U0` (this gate's own wired invocation) emits a pure-deletion hunk
    as `@@ -a,b +c,0 @@` (zero post-image lines), and a post-image-only
    bound reads `remaining` as already exhausted on the `@@` line itself --
    before the hunk's own `b` removal lines are consumed -- so the very
    next line, itself the hunk's own removal content, is read as a real
    header instead. `old_remaining` and `new_remaining` are each
    decremented only by the line kind that consumes that side (a context
    line consumes both; a removal consumes only the pre-image side; an
    addition consumes only the post-image side), and `in_hunk` clears only
    once *both* reach zero -- so a zero-post-image hunk still correctly
    protects its own removal lines via the pre-image side.

    Issue #1193: the declared counts above are trusted, not verified -- the
    mirror-image case of the regression just described. A hunk header that
    *over-declares* either count -- claims more pre- or post-image lines
    than its own body actually has -- leaves that side's own counter
    (`old_remaining` or `new_remaining`) above zero once the real body is
    exhausted, so `in_hunk` stays True straight through the next boundary
    anyway, reproducing the identical misattribution the dual-counter bound
    closes for the missing-`diff --git `-header case, just triggered by an
    inaccurate count instead of a missing separator. There is no way to
    tell, from a line's own prefix alone, whether it is real hunk content
    or a misplaced header once `in_hunk` is wrongly still true -- that
    ambiguity is exactly what the bound is for -- so this is instead caught
    at the three points a hunk's content region unambiguously ends
    regardless of `in_hunk`'s own state: a new `diff --git ` line, a new
    `@@` line, and end of input. Each already carries no `not in_hunk`
    guard (a real content line can never begin with either literally,
    since it always carries its own `+`/`-`/` ` prefix first), so reaching
    one while `in_hunk` is still true can only mean the previous hunk's
    declared counts outran its real body -- raised as `ScanError` rather
    than left to keep misattributing.

    Two independent adversarial reviews found a bypass of the three
    boundary checks above: an over-declared hunk whose excess is small
    enough that a genuinely-following file's own real `--- `/`+++ ` pair
    gets fully absorbed as fake removal/addition content, draining both
    counters to exactly zero *before* either boundary check ever runs --
    `in_hunk` clears itself one line early, silently. A first fix raised
    whenever a hunk's counters drained to exactly zero on a line that
    also looked like a `+++ ` post-image header immediately after one
    that looked like a `--- ` source header. A second fix narrowed that
    to only raise when the *next* line also looked like a new hunk
    (`@@`) or file (`diff --git `) header, after CodeRabbit and a second
    adversarial review independently found the first fix false-positived
    on an accurately-declared hunk whose own real content simply happens
    to modify a line starting `-- ` into one starting `++ ` (a changelog
    marker, a divider comment, this file's own docstrings full of
    literal `--- `/`+++ ` examples). Three more independent reviews
    (two further adversarial dispatches plus CodeRabbit again) then
    confirmed live that the lookahead barely helped: in any real diff
    with more than one hunk or file, *something* `@@`- or
    `diff --git `-shaped almost always immediately follows any given
    hunk regardless of whether its own declared counts are honest, so
    the lookahead alone still false-positived on ordinary,
    accurately-declared multi-hunk/multi-file diffs -- confirmed
    reachable through each gate's own real wired `-U0` invocation on
    nothing more unusual than editing one of this repository's own
    docstring lines that starts `-- `/`++ ` alongside any other hunk or
    file. What actually discriminates a real absorbed header from
    ordinary dash/plus content is not what follows, but whether the
    ambiguous pair itself has the shape a real header always has:
    `_looks_like_real_header_pair` checks `a/<path>` (or `/dev/null`) on
    the `--- ` side and `b/<path>` (or `/dev/null`) on the `+++ ` side,
    not merely the 4-character prefix -- ordinary content essentially
    never also has this shape by coincidence, while a genuinely-absorbed
    header always does (it is that file's own real header, verbatim).
    Raising now requires both signals together: the pair looks
    header-shaped *and* what follows also looks like a new hunk or file
    header. The second condition still matters even with the first --
    a real absorbed header is, by construction, always followed by that
    same file's own further real content, so requiring both loses no
    real catch, while a hunk that merely ends on header-shaped content
    with nothing of substance following it no longer raises either.

    One further shape was checked and found to be the pre-existing issue
    #1200 gap below, not a new regression from any of this: a hunk whose
    declared counts are small enough (e.g. `@@ -1,1 +1,1 @@`) to be
    honestly, exactly satisfied by content that itself happens to look
    header-shaped for a real in-scope path, with real content
    immediately following. Confirmed identical against the commit before
    any of this bypass work began -- the header-shape signal alone
    cannot distinguish "an honest 1-line hunk whose real content happens
    to look header-shaped" from "a 1-line over-declaration absorbing a
    real header," which is exactly #1200's own already-disclosed
    undecidability once a hunk's declared counts are small enough to be
    satisfied either way, not a gap this fix introduces or could close
    without the same structurally different mechanism #1200 already
    calls for.

    Known gap, tracked separately rather than fixed here: issue #1200. The
    boundary checks above only catch an *over*-declared count. A header
    whose declared counts are honestly, exactly consumed by a real,
    legitimate body -- not over- or under-declared relative to what its
    own author intended -- correctly clears `in_hunk`, so content that
    follows is read as a new file transition. If a hand-fed or foreign
    patch (the same `--diff` exposure every other gap here requires)
    disguises that following content as a `--- `/`+++ ` header pair
    naming a real, existing in-scope path, a genuinely-added line later
    in the diff is silently attributed to that path instead of its own.
    This is the mirror image of the over-declared case, and the boundary-
    check technique above cannot close it: once a hunk's declared counts
    are honestly satisfied, there is no further structural signal left to
    tell a genuine file transition apart from disguised content an
    under-declared header failed to account for. Closing it needs a
    structurally different mechanism (e.g. a lookahead confirming a
    candidate `+++ ` header is genuinely followed by a `@@` line, or a
    two-pass parse), not an incremental extension of this one.
    """
    added: dict[str, set[int]] = {}
    path: str | None = None
    lineno = 0
    in_hunk = False
    old_remaining = 0
    new_remaining = 0
    saw_source_header = False

    def _reject_if_hunk_incomplete(boundary: str) -> None:
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
        # `\ No newline at end of file` is a marker, not content, and
        # advances neither counter. `path` is None for a deleted file
        # (`+++ /dev/null`, see `_diff_target_path`) -- the counters and
        # `in_hunk` still have to be bounded there too, only the recording
        # into `added` is skipped, or a deletion hunk's own removal lines
        # would never be consumed and `in_hunk` would stay True straight
        # through whatever follows, reopening the missing-`diff --git `
        # gap for exactly the one case this docstring otherwise says is
        # now bounded.
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


def _re_module_names(tree: ast.Module) -> frozenset[str]:
    """Every bare name an `import re` in `tree` binds to the `re` module.

    Always contains `"re"` itself, plus every `import re as <alias>` alias
    the graded file declares. Widening-only by construction: the returned
    set is a superset of `{"re"}`, so resolving aliases can only ever add
    graded call sites, never remove one -- the safe direction for a gate.

    Deliberately not a general name resolver: only `ast.Import` is read (an
    `import re` statement anywhere in the file, at any nesting depth), no
    rebinding, shadowing or scope is tracked, and `from re import compile`
    is not recognised at all. See the module docstring's own "Known misses
    in the trigger table itself" for why the member-import spelling is left
    out rather than guessed at.
    """
    names = {_RE_MODULE}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _RE_MODULE:
                    names.add(alias.asname or alias.name)
    return frozenset(names)


def _regex_trigger(node: ast.Call, re_module_names: frozenset[str]) -> bool:
    """Category (a): see the module docstring's own trigger-categories
    section for the receiver-specific vs. receiver-agnostic split.
    `re_module_names` comes from `_re_module_names` on the same tree, so an
    aliased `import re as _re` grades its `.compile(...)` calls too."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr == "compile":
        return isinstance(func.value, ast.Name) and func.value.id in re_module_names
    return func.attr in _REGEX_RECEIVER_AGNOSTIC_ATTRS


def _path_resolution_trigger(node: ast.Call) -> bool:
    """Category (b): receiver-agnostic `.resolve()`/`.is_symlink()`/
    `.relative_to()`, plus `<any>.path.realpath(...)`/`.abspath(...)`
    matched on the call's own final two attribute segments only."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr in _PATH_RESOLUTION_RECEIVER_AGNOSTIC_ATTRS:
        return True
    if func.attr in _OS_PATH_ATTRS:
        return isinstance(func.value, ast.Attribute) and func.value.attr == "path"
    return False


def _string_comparison_call_trigger(node: ast.Call) -> bool:
    """Category (c), the call-shaped half: receiver-agnostic `.startswith()`/
    `.endswith()`, or `frozenset(...)`/`set(...)` called with a single inline
    collection-literal argument."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in _STRING_COMPARISON_RECEIVER_AGNOSTIC_ATTRS
    if isinstance(func, ast.Name):
        return (
            func.id in _COLLECTION_LITERAL_CALL_NAMES
            and len(node.args) == 1
            and isinstance(node.args[0], ast.List | ast.Tuple | ast.Set)
        )
    return False


def _string_comparison_compare_trigger(node: ast.Compare) -> bool:
    """Category (c), the `in`/`not in` half: exactly one `In`/`NotIn` operator
    whose comparator is an inline collection literal. A name reference to a
    previously-defined collection constant is a deliberate, disclosed miss --
    see the module docstring's own "Known misses" section."""
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return False
    if not isinstance(node.ops[0], ast.In | ast.NotIn):
        return False
    return isinstance(node.comparators[0], ast.List | ast.Tuple | ast.Set)


class _Trigger(NamedTuple):
    """One trigger call/compare site, tagged with the rule slug it feeds
    into `Finding.rule` when uncovered."""

    node: ast.Call | ast.Compare
    category: str


def _span(node: ast.Call | ast.Compare) -> set[int]:
    """Every source line `node` occupies, so a multi-line call is graded
    wherever it was touched -- an added line anywhere in this span brings
    the finding into this diff's scope. A waiver, unlike this trigger span,
    is honoured on exactly one line: the one `Finding.line` reports (this
    node's own `lineno`) -- matching `gitapex_gate_exception_handler_gaps.py`'s
    own "put the comment where the error points" waiver convention, not
    anywhere in the span."""
    end = node.end_lineno if node.end_lineno is not None else node.lineno
    return set(range(node.lineno, end + 1))


def _triggers(tree: ast.Module) -> Iterator[_Trigger]:
    """Yield every trigger call/compare site in `tree`, tagged by category.
    The three categories are mutually exclusive by construction (disjoint
    attribute-name sets), so a `Call` node yields at most one trigger."""
    re_module_names = _re_module_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _regex_trigger(node, re_module_names):
                yield _Trigger(node, _REGEX_GAP)
            elif _path_resolution_trigger(node):
                yield _Trigger(node, _PATH_RESOLUTION_GAP)
            elif _string_comparison_call_trigger(node):
                yield _Trigger(node, _STRING_COMPARISON_GAP)
        elif isinstance(node, ast.Compare) and _string_comparison_compare_trigger(node):
            yield _Trigger(node, _STRING_COMPARISON_GAP)


class _FunctionRange(NamedTuple):
    """One `FunctionDef`/`AsyncFunctionDef`'s own line range, inclusive."""

    lineno: int
    end_lineno: int
    name: str


def _function_ranges(tree: ast.Module) -> list[_FunctionRange]:
    """Every function's own line range in `tree`, including nested ones.
    See the module docstring's own "Scope/function attribution" section for
    why the smallest containing range is always the innermost enclosing one.
    """
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno if node.end_lineno is not None else node.lineno
            ranges.append(_FunctionRange(node.lineno, end, node.name))
    return ranges


def _enclosing_scope(line: int, ranges: list[_FunctionRange]) -> str:
    """The innermost function name enclosing `line`, or `_MODULE_SCOPE`."""
    containing = [r for r in ranges if r.lineno <= line <= r.end_lineno]
    if not containing:
        return _MODULE_SCOPE
    return min(containing, key=lambda r: r.end_lineno - r.lineno).name


def _scope_label(scope: str) -> str:
    return "module level" if scope == _MODULE_SCOPE else f"`{scope}`"


def _properties_path(root: pathlib.Path, stem: str) -> pathlib.Path:
    """The co-located properties file for source module stem `stem`, e.g.
    "gitapex_gate_foo" -> "<root>/tests/test_gitapex_gate_foo_properties.py"
    -- the naming precedent `tests/test_gitapex_gate_metadata_outcome_lines_
    properties.py` already sets for `.github/scripts/gitapex_gate_metadata_
    outcome_lines.py`."""
    return root / "tests" / f"test_{stem}_properties.py"


def _properties_tree(root: pathlib.Path, stem: str) -> ast.Module | None:
    """Parse the co-located properties file's AST. Returns None when the
    file does not exist, cannot be read, or cannot be parsed -- three
    conditions collapsed into one UNCOVERED verdict rather than a
    `ScanError`, per the module docstring's own "Existing-coverage check"
    section: the *source* file's own triggers are still fully enumerable
    without this file, so the scan itself stays trustworthy; only the
    coverage verdict for scopes in that source file is conservative.
    """
    path = _properties_path(root, stem)
    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError):
        return None


def _is_given_decorator(decorator: ast.expr) -> bool:
    """True for a `@given(...)` call, matched by the decorator's own final
    attribute/name being "given" -- so both `@given(...)` and
    `@hypothesis.given(...)` count. A bare `@given` with no call is not
    matched: the design requires "a @given(...) call"."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    if isinstance(func, ast.Name):
        return func.id == "given"
    if isinstance(func, ast.Attribute):
        return func.attr == "given"
    return False


def _given_decorated_functions(tree: ast.Module) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function in `tree` carrying at least one `@given(...)` decorator."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and any(
            _is_given_decorator(decorator) for decorator in node.decorator_list
        ):
            yield node


def _imports_module(tree: ast.Module, stem: str) -> bool:
    """True iff `tree` contains `import {stem}` or `from {stem} import ...`,
    matched on the bare module name -- `import {stem} as gate` still counts,
    matching the real shape `tests/test_gitapex_gate_metadata_outcome_lines_
    properties.py` uses today. No import resolution beyond this literal
    match: see the module docstring's own "Known misses" section."""
    return any(
        (isinstance(node, ast.Import) and any(alias.name == stem for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == stem)
        for node in ast.walk(tree)
    )


def _mentions_name_in_body(func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    """True iff `name` appears as a `Name`/`Attribute` node's final name
    anywhere in `func`'s own body -- only the body, not its decorators or
    argument defaults. See the module docstring's own "Known misses" section
    for the false-clear (an unrelated same-named identifier) and false-flag
    (coverage only through an imported wrapper) this heuristic accepts.
    """
    return any(
        (isinstance(node, ast.Name) and node.id == name) or (isinstance(node, ast.Attribute) and node.attr == name)
        for statement in func.body
        for node in ast.walk(statement)
    )


def _covered(properties_tree: ast.Module | None, stem: str, scope: str) -> bool:
    """True iff `scope` in the source module `stem` is covered by a
    Hypothesis property test, per the module docstring's own
    "Existing-coverage check" section."""
    if properties_tree is None or not _imports_module(properties_tree, stem):
        return False
    given_functions = list(_given_decorated_functions(properties_tree))
    if not given_functions:
        return False
    if scope == _MODULE_SCOPE:
        return True
    return any(_mentions_name_in_body(func, scope) for func in given_functions)


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying an inline waiver comment.

    Read through `tokenize` rather than a regex over raw text so the marker
    is only honoured as a real comment -- a string literal quoting this
    gate's own documentation must never silence a finding. Deliberately
    unguarded, matching `gitapex_gate_exception_handler_gaps.py`'s own
    `_waived_lines`: the only caller runs `ast.parse` on this same source
    first and turns any failure into a `ScanError`, and CPython's own parser
    tokenizes what it parses -- so a source that reaches here has already
    been proved tokenizable.
    """
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


def findings_for_source(
    path: str, source: str, added: set[int], root: pathlib.Path
) -> tuple[list[Finding], list[Finding]]:
    """Grade one file's source, returning ``(violations, honoured waivers)``.

    Only a trigger an added line actually reaches is graded, so a
    pre-existing gap another PR owns is never this diff's failure -- the
    same diff-scoping `gitapex_gate_exception_handler_gaps.py`'s own
    `findings_for_source` applies.
    """
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

    waived_lines = _waived_lines(source)
    ranges = _function_ranges(tree)
    stem = _stem(path)
    properties_tree = _properties_tree(root, stem)

    violations: list[Finding] = []
    waived: list[Finding] = []
    for trigger in _triggers(tree):
        if not (_span(trigger.node) & added):
            continue
        scope = _enclosing_scope(trigger.node.lineno, ranges)
        if _covered(properties_tree, stem, scope):
            continue
        finding = Finding(
            path,
            trigger.node.lineno,
            trigger.category,
            f"{_TRIGGER_LABEL[trigger.category]} reached by this diff has no hypothesis "
            f"@given property test in tests/test_{stem}_properties.py covering "
            f"{_scope_label(scope)}",
        )
        target = waived if finding.line in waived_lines else violations
        target.append(finding)
    return sorted(set(violations)), sorted(set(waived))


def find_violations(diff_text: str, root: pathlib.Path) -> tuple[list[Finding], list[Finding], int]:
    """Grade every in-scope file the diff adds lines to.

    Returns ``(violations, honoured waivers, files graded)``. Raises
    ``ScanError`` when a file named by the diff exists but cannot be read as
    UTF-8 or parsed -- a file this gate cannot grade must not pass silently.
    Mirrors `gitapex_gate_exception_handler_gaps.py`'s own `find_violations`.
    """
    violations: list[Finding] = []
    waived: list[Finding] = []
    graded = 0
    for path, added in sorted(parse_added_lines(diff_text).items()):
        if not in_scope(path):
            continue
        absolute = root / path
        try:
            # utf-8-sig, not utf-8: a BOM-carrying file that python3 executes
            # fine otherwise would otherwise fail this gate with a spurious
            # "cannot be parsed as Python" ScanError. See
            # gitapex_gate_exception_handler_gaps.py's own find_violations for
            # the same reasoning.
            source = absolute.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            raise ScanError(f"{path}: named by the diff as added or modified, but missing from {root}") from None
        except (OSError, UnicodeDecodeError) as error:
            raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
        file_violations, file_waived = findings_for_source(path, source, added, root)
        violations.extend(file_violations)
        waived.extend(file_waived)
        graded += 1
    return violations, waived, graded


class GateDetectionLogicPropertyCoverageArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. `root` must be an
    existing directory -- every existing caller already passes one, so this
    only gives a --root pointing nowhere a clear, early error instead of the
    deeper "missing from <root>" ScanError it would otherwise surface."""

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
        description="Check that new or materially changed regex-, path-resolution-, or "
        "string-comparison-based detection logic added by this diff has a co-located "
        "hypothesis @given property test covering it. Reads a unified diff on standard input."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root the diff's paths, and the co-located tests/ directory, resolve "
        "against (defaults to this checkout).",
    )
    parser.add_argument(
        "--diff",
        type=pathlib.Path,
        help="Read the unified diff from this file instead of standard input.",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateDetectionLogicPropertyCoverageArgs(root=args.root)
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
        # Read bytes and decode explicitly, rather than letting text-mode
        # stdin do it under the platform locale -- the same fail-closed
        # reasoning gitapex_gate_exception_handler_gaps.py's own main() gives
        # for this exact branch.
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
        print(
            f"{finding.path}:{finding.line}: {finding.rule}: waived inline -- {finding.message}",
            file=sys.stderr,
        )

    if violations:
        for finding in violations:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.message}", file=sys.stderr)
        print(
            f"\n{len(violations)} new or materially changed detection-logic call site(s) reached "
            "by this diff have no hypothesis @given property test covering their scope (issue "
            "#1178). Add one to tests/test_<source-stem>_properties.py: import the source module "
            "and, for a function-scoped finding, exercise that function by name inside an "
            "@given-decorated test; for a module-level finding, any @given-decorated test in that "
            "file clears it. When a human has already judged the site covered some other way, "
            "disclose it inline with '# detection-logic-property-coverage: WAIVED: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

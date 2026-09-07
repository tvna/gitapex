#!/usr/bin/env python3
"""CI gate: two functions in the same module that both wrap a network call
in a `try`/`except` must declare the same exception set for it.

Issue #1512 (consolidated into #1572's own umbrella). `_gitapex_github_http.py`
shipped `graphql_call` catching only `except urllib.error.URLError` around
its own `opener(request)` call, while its sibling `request_with_retry` --
the function `graphql_call` was itself ported from -- already caught
`except (OSError, http.client.IncompleteRead)` around the identical call
shape. `http.client.IncompleteRead` is not a `URLError`/`OSError` subclass,
so a body read that starts but stalls or is cut short escaped
`graphql_call` uncaught instead of retrying like every other failure mode
there. Found only by issue #729's own Step 8 adversarial review, and fixed
in the same PR -- both functions now catch the identical tuple. Nothing in
this repository's own gate suite would have caught the drift itself: the
two functions are each individually well-formed (a real `try`/`except`
around a real network call, not the missing-handler shape
`gitapex_gate_exception_handler_gaps.py` grades), so the defect is only
visible by comparing them against each other. This gate is that comparison.

Design: one recognizable call shape, one exception-set comparison
-------------------------------------------------------------------
Within one file's AST, this gate looks at every module-level function (a
`FunctionDef`/`AsyncFunctionDef` directly in `tree.body` -- a function
nested inside a class or another function is out of scope for this first
version, kept simple rather than resolving what "the same module" means
for a method). For each such function it walks the function's body (skipping
the body of any function/lambda defined *inside* it -- that is a separate
scope, the same exclusion `gitapex_gate_exception_handler_gaps.py`'s own
`_walk_excluding_nested_functions` applies) looking for the *first* `try`
statement whose own body contains a call matching one of two signals:

* **`opener-call`** -- a call to a bare name literally spelled `opener`,
  this repository's own established callable-injection pattern for an HTTP
  call (`_gitapex_github_http.py`'s `request_with_retry`/`graphql_call`
  both call `opener(request)` inside their own `try`). Chosen over trying
  to resolve *which* parameter is "the network call" in general: this
  repository has exactly one such convention today, and it is spelled the
  same way everywhere it appears.
* **`urllib-attr-call`** -- a call whose callee is an attribute chain
  (`a.b.c(...)`) containing `urlopen`, or starting with `urllib.request` or
  `http.client` -- `urllib.request.urlopen(...)`, an aliased
  `urllib.request.urlopen`, or a bare `http.client.HTTPSConnection(...)`
  all match.

Only the first qualifying `try` per function is graded, and only these two
signals are recognized -- deliberately narrow, per this gate's own mandate
to prefer under-detecting to over-detecting (a false positive on an
unrelated `try`/`except` pair is worse than a narrow miss here, the same
trade `gitapex_gate_exception_handler_gaps.py`'s own docstring states for
itself). No alias/constant resolution, no call-graph analysis: this is the
third gate in this family to make that trade (see that file's own
`_handler_names` docstring for why it keeps losing to the alternative).

For each function with a qualifying `try`, this gate records the
*effective* exception-handler name set that actually guards the network
call -- not merely that `try`'s own `handlers`. When the call sits inside a
`try` NESTED inside the qualifying `try`'s own body (a chain of nested
`try`s is walked all the way down), the recorded set is the UNION of every
one of those `try`s' own handler names, from the outer `try` found above
down to the innermost one directly wrapping the call -- mirroring
`gitapex_gate_exception_handler_gaps.py`'s own `_handler_coverage`'s
"handled set accumulates across nested try scopes" pattern (`_network_call_
handlers` is this gate's own version of that same accumulation). Without
it, a network call sitting in an inner `try` would be graded only against
the outer `try`'s own handlers, silently dropping the inner `try`'s own
handler names even though both jointly determine what is actually caught
around the call -- issue #1512's own defect shape, one level deeper. Each
`try`'s own per-clause name extraction is literal only -- a `Tuple` handler
split into its component names, nothing resolved -- reusing
`gitapex_gate_exception_handler_gaps.py`'s own `_handler_names` logic
exactly (copied, not imported: every `.github/scripts/*.py` gate stays
independent of every other one, the convention
`gitapex_gate_detection_logic_property_coverage.py`'s own copy of
`parse_added_lines` already follows for the same reason).

Functions are grouped by which of the two signals their own qualifying
`try` matched. Within one module, any two functions in the *same* group
whose handler-name sets differ is a finding, one per differing pair --
naming both functions and both exception sets. Anchored at the *later* of
the two functions' own `try` lines (by source position; documented rather
than defended as uniquely correct -- either line names a real party to the
drift, and the diff-scoping rule below is what actually decides whether a
given pair is this diff's problem, not which one is named in the message).

Scope is the diff, not the repository, matching both sibling gates: a
finding is reported only when at least one of the two functions' own `try`
statement (the full `try`/`except`/`else`/`finally` span, same "which lines
would an edit have to touch to create or fix this" reasoning
`gitapex_gate_exception_handler_gaps.py`'s own `_Candidate.trigger` uses)
was touched by an added line in the graded diff -- so a pre-existing drift
neither function in this diff touches is never this diff's failure.

In-scope paths are this repository's own deterministic checker scripts,
identical to `gitapex_gate_exception_handler_gaps.py`'s own four-directory
scope: `.github/scripts/*.py`, `hooks/*.py`, `evals/scripts/*.py`,
`skills/*/scripts/*.py`. Test files (`test_*.py`, `conftest.py`) are
excluded everywhere, for the same reason that file states: a test handing
this gate malformed input is doing its job.

Known misses
------------
* **What IS handled: a `try` NESTED inside the first qualifying `try`'s own
  body, wrapping that SAME call.** `_network_call_handlers` unions in every
  such nested `try`'s own handler names (see the module docstring's own
  "Design" section) -- this is not a miss, it is the fix for issue #1512's
  own defect shape one level deeper, and is called out here only to
  contrast with the next bullet, which remains a real miss.
* **Functions nested in a class, or in another function, are never
  scanned.** Only `tree.body`'s own direct `FunctionDef`/`AsyncFunctionDef`
  entries are considered. Two methods of the same class that drift exactly
  this way are invisible to this first version -- a stated scope limit, not
  an oversight, per this task's own "keep it simple" instruction.
* **Only the first qualifying `try` per function is graded -- and that
  means the first SEPARATE, SIBLING `try` (not one nested inside another,
  which the bullet above already covers).** A function with two separate
  `try` blocks, each at the same nesting depth wrapping a different network
  call shape (or the same shape a second time), has its second one silently
  ignored: only the first `try` `_first_network_try` finds in source order
  ever becomes a candidate, and `_first_nested_network_try` only ever
  descends INTO the one already found, never sideways to a sibling.
* **No cross-module comparison.** Two functions in *different* files that
  wrap the identical call shape are never compared -- by design: "the same
  module" is this gate's own stated boundary, not a limitation to widen
  later without first measuring the false-positive cost across unrelated
  files.
* **No alias, wrapper-function, or call-graph resolution.** A project-local
  helper that itself wraps `urlopen` under a different name, or an
  `opener` parameter renamed at one call site, is invisible. The `opener`
  signal matches the literal spelling this repository's own convention
  uses today; a renamed convention needs this gate updated, not inferred.
* **A network call reached only through a comprehension, generator
  expression, or lambda default inside the `try` body is graded exactly as
  `gitapex_gate_exception_handler_gaps.py`'s own walk treats it**: a lambda
  or nested `def`'s *body* is excluded (deferred, not really wrapped by
  this `try`), but its decorators and argument defaults, evaluated where
  written, are not.
* **Two findings on the same physical line pair report as one line each**,
  matching every sibling gate's own `(path, line, rule, message)` dedup --
  see `find_violations`'s own return contract.

Known over-reports
-------------------
* **Any call to a bare name spelled `opener` is read as this repository's
  network callable-injection idiom**, even if a module happens to define an
  unrelated parameter or local variable also named `opener` (a door/gate
  opener in some hypothetically domain-specific script, or a differently
  purposed callback). The inline waiver below is the documented disclosure
  path -- the same trade `gitapex_gate_exception_handler_gaps.py`'s own
  `_handler_names` docstring records making three separate times for name
  resolution generally.
* **`urllib-attr-call` groups every recognized `urllib`/`http.client` call
  in one module into a single shape**, regardless of which specific
  primitive is used. Two functions that each legitimately raise a different
  exception profile because they call genuinely different lower-level
  primitives (`urlopen` versus a raw `http.client.HTTPSConnection(...).
  request(...)`) would still be compared against each other. Narrower,
  per-exact-dotted-path grouping was considered and rejected: this
  repository's own real instance of the defect this gate exists for
  (`request_with_retry`/`graphql_call`) both go through the *coarser*
  `opener-call` shape, not this one, so the narrower grouping would buy
  nothing against the one measured case while adding a second axis of
  judgment call with no real instance to calibrate it against.

Waiver: `# network-exception-set-drift: WAIVED: <reason>`, tokenize-matched
(a real comment token only, never a string literal quoting this text),
non-whitespace reason required -- the identical convention
`gitapex_gate_exception_handler_gaps.py`'s own `_WAIVER_RE` and
`_waived_lines` use, applied to the line this gate names in its own
finding.

Exit codes: 0 clean (an empty diff is clean), 1 violation found, 2 the scan
could not be trusted (a malformed diff, or an in-scope file that cannot be
read or parsed) -- never a silent pass on input this gate cannot grade,
dimension 15 of `skills/evaluating-deterministic-gate-quality/references/
dimensions.md`.

Usage::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_network_exception_set_drift.py

A bare pipe here masks `git diff`'s own exit status in a non-`pipefail`
shell (issue #1531): add `set -o pipefail` first, or check `git diff`'s own
exit code separately, if the caller must detect an upstream failure rather
than silently grading whatever partial diff reached stdin.

Run via `uv run` (needed for the `pydantic` import, matching every sibling
gate here) or via the pytest gate in
`tests/test_gitapex_gate_network_exception_set_drift.py`.
"""

from __future__ import annotations

import argparse
import ast
import io
import itertools
import pathlib
import re
import sys
import tokenize
from collections.abc import Iterator
from typing import NamedTuple

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Identical to gitapex_gate_exception_handler_gaps.py's own _IN_SCOPE_RE --
# this repository's four deterministic-checker-script directories.
_IN_SCOPE_RE = re.compile(
    r"\.github/scripts/[^/]+\.py"
    r"|hooks/[^/]+\.py"
    r"|evals/scripts/[^/]+\.py"
    r"|skills/[^/]+/scripts/[^/]+\.py"
)

# `# network-exception-set-drift: WAIVED: <reason>` -- a reason is
# mandatory, matching every sibling gate's own `WAIVED:` clause.
_WAIVER_RE = re.compile(r"#\s*network-exception-set-drift\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

_DRIFT_RULE = "network-exception-set-drift"

_OPENER_CALL = "opener-call"
_URLLIB_ATTR_CALL = "urllib-attr-call"
_NETWORK_ATTR_TOKENS = ("urlopen", "urllib.request", "http.client")

_SHAPE_LABEL = {
    _OPENER_CALL: "network call via an injected `opener(...)` callable",
    _URLLIB_ATTR_CALL: "urllib/http.client network call",
}


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation, anchored at the later of the two functions'
    own `try` lines (see the module docstring's "Design" section)."""

    path: str
    line: int
    rule: str
    message: str


def in_scope(path: str) -> bool:
    """Return True iff `path` is a checker script this gate grades.

    Identical to `gitapex_gate_exception_handler_gaps.py`'s own `in_scope`:
    test files are excluded everywhere, since a test that hands this gate
    malformed input is doing its job.
    """
    if not _IN_SCOPE_RE.fullmatch(path):
        return False
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith("test_") or name == "conftest.py")


# ---------------------------------------------------------------------------
# Diff parsing -- copied verbatim (mechanics, not the full historical
# docstring) from gitapex_gate_exception_handler_gaps.py's own
# parse_added_lines/_diff_target_path/_looks_like_real_header_pair, per this
# task's own instruction to reuse that proven diff-parsing logic rather than
# reimplementing it. Copied rather than imported: every `.github/scripts/
# *.py` gate stays independent of every other one, the same convention
# `gitapex_gate_detection_logic_property_coverage.py`'s own copy of these
# same three functions already follows, for the same reason.
# ---------------------------------------------------------------------------


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null` (a deletion, which adds nothing to grade).

    Anything other than `/dev/null` or git's own `b/`-prefixed post-image
    raises ``ScanError`` rather than being guessed at. Real `git diff`
    output always emits `--- ` before `+++ `, and the calling workflow
    always invokes plain `git diff`, so this is a wiring error, not a
    contributor's -- see `gitapex_gate_exception_handler_gaps.py`'s own
    identical function for the full rationale.
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

    Identical to `gitapex_gate_exception_handler_gaps.py`'s own function of
    the same name -- see that file's docstring for the full rationale
    (three rounds of adversarial review against a hunk-boundary bypass).
    """
    source = source_line[4:]
    target = target_line[4:]
    return (source == "/dev/null" or source.startswith("a/")) and (target == "/dev/null" or target.startswith("b/"))


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into ``{post-image path: added line numbers}``.

    Byte-for-byte the same algorithm as `gitapex_gate_exception_handler_
    gaps.py`'s own `parse_added_lines` -- dual pre-/post-image hunk counters,
    a `+++ ` header with no preceding `--- ` raising `ScanError`, and the
    header-shape-plus-lookahead check that closes the over-declared-hunk
    bypass three independent adversarial reviews found there. See that
    file's own docstring for the complete, measured rationale behind every
    one of these decisions; not repeated verbatim here to keep this file
    from drifting into a second copy of a docstring this repository has
    already spent that much review on once.
    """
    added: dict[str, set[int]] = {}
    path: str | None = None
    lineno = 0
    in_hunk = False
    old_remaining = 0
    new_remaining = 0
    saw_source_header = False

    def _reject_if_hunk_incomplete(
        boundary: str,
    ) -> None:  # function-body-test-coverage: WAIVED: a private closure nested inside parse_added_lines, with no name accessible from outside this function to reference directly; its raise path is exercised through parse_added_lines' own over-declared-hunk-count regression tests below (test_an_over_declared_hunk_before_the_next_diff_git_header_raises_scanerror, test_an_over_declared_hunk_at_end_of_input_raises_scanerror, test_an_over_declared_hunk_length_before_a_new_hunk_header_raises_scanerror)
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


# ---------------------------------------------------------------------------
# Network-call-shape detection and the exception-handler-name extraction it
# feeds -- this gate's own new logic.
# ---------------------------------------------------------------------------


def _handler_names(handler: ast.ExceptHandler) -> set[str]:
    """Return the exception names one `except` clause catches, literally.

    Copied from `gitapex_gate_exception_handler_gaps.py`'s own function of
    the same name -- see that file's docstring for why nothing here is
    resolved (three prior attempts at name resolution in this same
    codebase, each reverted as a net fail-open).
    """
    if handler.type is None:
        return {"BaseException"}
    parts = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    names: set[str] = set()
    for part in parts:
        if isinstance(part, ast.Name):
            names.add(part.id)
        elif isinstance(part, ast.Attribute):
            names.add(part.attr)
    return names


def _dotted_name(node: ast.AST) -> str | None:
    """Return the full dotted path of a `Name`/`Attribute` chain
    (`a.b.c` -> `"a.b.c"`), or None if `node` is not built purely from
    those two node kinds -- e.g. a call result or subscript in the chain.
    """
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _network_call_shape(call: ast.Call) -> str | None:
    """Return which of the two recognized network-call signals `call`
    matches, or None. See the module docstring's "Design" section."""
    func = call.func
    if isinstance(func, ast.Name) and func.id == "opener":
        return _OPENER_CALL
    if isinstance(func, ast.Attribute):
        dotted = _dotted_name(func)
        if dotted is not None and any(token in dotted for token in _NETWORK_ATTR_TOKENS):
            return _URLLIB_ATTR_CALL
    return None


def _iter_excluding_nested_defs(node: ast.AST) -> Iterator[ast.AST]:
    """Yield every descendant of `node`, excluding the bodies of any
    function or lambda defined inside it -- those are their own scope.

    Matches `gitapex_gate_exception_handler_gaps.py`'s own
    `_walk_excluding_nested_functions` exclusion exactly, extended to also
    exclude `Lambda` (a network call reached only through a lambda body
    inside the `try` is deferred, not really wrapped by it -- the same
    treatment that file's own `_handler_coverage` gives a lambda body,
    while still walking a lambda's own argument defaults, which are
    evaluated where written and are not excluded here since they are not
    inside the lambda's own `body` at all).
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        yield child
        yield from _iter_excluding_nested_defs(child)


def _contains_network_call_shape(node: ast.AST) -> str | None:
    """Return the first network-call shape found anywhere in `node` or its
    descendants (excluding nested function/lambda bodies), or None."""
    if isinstance(node, ast.Call):
        shape = _network_call_shape(node)
        if shape is not None:
            return shape
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        return None
    for child in ast.iter_child_nodes(node):
        shape = _contains_network_call_shape(child)
        if shape is not None:
            return shape
    return None


def _try_body_network_shape(try_node: ast.Try | ast.TryStar) -> str | None:
    """Return the network-call shape `try_node`'s own body wraps, or None.

    Only the `try` *body* is inspected -- matching
    `gitapex_gate_exception_handler_gaps.py`'s own "only a try body
    protects" convention -- so a network call sitting in an `except`,
    `else`, or `finally` clause of the same statement is not this try's own
    wrapped call.
    """
    for statement in try_node.body:
        shape = _contains_network_call_shape(statement)
        if shape is not None:
            return shape
    return None


def _first_network_try(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ast.Try | ast.TryStar, str] | None:
    """Return `(try_node, shape)` for the first `try` in `function_node`'s
    own body (in source order, excluding nested function/lambda bodies)
    whose body wraps a recognized network call, or None.

    `try_node` is only the OUTERMOST such `try` -- used to anchor the
    finding's line span (see `_try_span`, which already covers every `try`
    nested inside it) and as the starting point `_network_call_handlers`
    walks down from. It is not, on its own, the full set of handlers that
    actually guards the call: see that function's own docstring.
    """
    for node in _iter_excluding_nested_defs(function_node):
        if isinstance(node, ast.Try | ast.TryStar) and (shape := _try_body_network_shape(node)) is not None:
            return node, shape
    return None


def _first_nested_network_try(try_node: ast.Try | ast.TryStar) -> ast.Try | ast.TryStar | None:
    """Return the first `try` -- itself included -- among `try_node`'s own
    body's statements (in source order, excluding nested function/lambda
    bodies) whose own body also transitively wraps a recognized network
    call, or None if `try_node`'s call is not itself further wrapped by
    another `try`.

    Only `try_node.body` is searched, matching `_try_body_network_shape`'s
    own "only a try body protects" convention -- a `try` sitting in
    `try_node`'s own `except`/`else`/`finally` clause is not part of the
    chain of `try`s actually wrapping `try_node`'s call.
    """
    for statement in try_node.body:
        for node in itertools.chain([statement], _iter_excluding_nested_defs(statement)):
            if isinstance(node, ast.Try | ast.TryStar) and _try_body_network_shape(node) is not None:
                return node
    return None


def _network_call_handlers(try_node: ast.Try | ast.TryStar) -> frozenset[str]:
    """Return the effective handler-name set that actually guards the
    network call `try_node`'s own body wraps.

    `try_node`'s own handler names are not, on their own, the answer:
    `_first_network_try` returns the OUTERMOST `try` whose body
    transitively contains a recognized network call, but when that call
    sits inside a `try` NESTED inside `try_node`'s own body, that inner
    `try`'s own handlers guard the call too -- reading only `try_node`'s
    own `handlers` silently drops them even though both jointly determine
    what is actually caught around the call (see the module docstring's
    own "Design" section for the concrete false-positive/false-negative
    pair this produces without this accumulation).

    The fix is the UNION of every enclosing `try`'s own handler names, from
    `try_node` itself down through every `try` nested inside its body that
    ALSO wraps the same call, innermost included -- mirroring
    `gitapex_gate_exception_handler_gaps.py`'s own `_handler_coverage`'s
    "handled set accumulates across nested try scopes" pattern: a call
    protected by an inner `except ValueError:` nested inside an outer
    `except OSError:` is, from the call's own point of view, protected
    against *either* -- an exception the inner handler does not name still
    propagates up into the outer `try`'s own protection.
    """
    own = frozenset(name for handler in try_node.handlers for name in _handler_names(handler))
    nested = _first_nested_network_try(try_node)
    if nested is None:
        return own
    return own | _network_call_handlers(nested)


class _TryCandidate(NamedTuple):
    """One module-level function's first qualifying `try`."""

    function_name: str
    shape: str
    handlers: frozenset[str]
    try_node: ast.Try | ast.TryStar


def _module_candidates(tree: ast.Module) -> list[_TryCandidate]:
    """Return one `_TryCandidate` per module-level function that has a
    qualifying `try`, in source order. Functions nested in a class or in
    another function are not visited at all -- only `tree.body`'s own
    direct `FunctionDef`/`AsyncFunctionDef` entries are (see the module
    docstring's own "Known misses").
    """
    candidates: list[_TryCandidate] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        found = _first_network_try(node)
        if found is None:
            continue
        try_node, shape = found
        handlers = _network_call_handlers(try_node)
        candidates.append(_TryCandidate(node.name, shape, handlers, try_node))
    return candidates


def _drift_pairs(candidates: list[_TryCandidate]) -> Iterator[tuple[_TryCandidate, _TryCandidate]]:
    """Yield every pair of candidates in the same shape group whose handler
    sets differ -- "any two functions in the SAME group ... is a finding"
    per the module docstring's own Design section."""
    by_shape: dict[str, list[_TryCandidate]] = {}
    for candidate in candidates:
        by_shape.setdefault(candidate.shape, []).append(candidate)
    for group in by_shape.values():
        if len(group) < 2:
            continue
        for first, second in itertools.combinations(group, 2):
            if first.handlers != second.handlers:
                yield first, second


def _try_span(node: ast.Try | ast.TryStar) -> tuple[int, int]:
    """The inclusive line range of one `try` statement, header through the
    last handler/else/finally -- what an edit would have to touch to create
    or fix a finding naming this `try`."""
    end = node.end_lineno if node.end_lineno is not None else node.lineno
    return node.lineno, end


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying a real `# network-exception-set-drift:
    WAIVED: <reason>` comment token -- never a string literal quoting this
    same text. Identical mechanics to
    `gitapex_gate_exception_handler_gaps.py`'s own `_waived_lines`;
    deliberately unguarded for the same reason that file states: the only
    caller here already runs `ast.parse` on this same source first and
    turns any failure into a `ScanError`, so a source that reaches here has
    already been proved tokenizable.
    """
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


def findings_for_source(path: str, source: str, added: set[int]) -> tuple[list[Finding], list[Finding]]:
    """Grade one file's source, returning ``(violations, honoured waivers)``.

    Only a pair where at least one function's own `try` span was touched by
    an added line is returned -- a pre-existing drift neither function in
    this diff touches is never this diff's failure.
    """
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

    waived_lines = _waived_lines(source)
    candidates = _module_candidates(tree)

    violations: list[Finding] = []
    waived: list[Finding] = []
    for first, second in _drift_pairs(candidates):
        first_start, first_end = _try_span(first.try_node)
        second_start, second_end = _try_span(second.try_node)
        first_touched = any(line in added for line in range(first_start, first_end + 1))
        second_touched = any(line in added for line in range(second_start, second_end + 1))
        if not (first_touched or second_touched):
            continue
        anchor = max(first_start, second_start)
        message = (
            f"'{first.function_name}' and '{second.function_name}' both wrap a "
            f"{_SHAPE_LABEL[first.shape]} in try/except but declare different exception sets: "
            f"{sorted(first.handlers)} vs {sorted(second.handlers)}"
        )
        finding = Finding(path, anchor, _DRIFT_RULE, message)
        target = waived if anchor in waived_lines else violations
        target.append(finding)
    return sorted(set(violations)), sorted(set(waived))


def find_violations(diff_text: str, root: pathlib.Path) -> tuple[list[Finding], list[Finding], int]:
    """Grade every in-scope file the diff adds lines to.

    Returns ``(violations, honoured waivers, files graded)``. Raises
    ``ScanError`` when a file named by the diff exists but cannot be read as
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


class GateNetworkExceptionSetDriftArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. `root` must be an
    existing directory, matching every sibling gate's own `--root`
    validation."""

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
        description="Check that two functions in the same module wrapping the same recognizable "
        "network call in try/except declare the same exception set. Reads a unified diff on "
        "standard input."
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
        validated = GateNetworkExceptionSetDriftArgs(root=args.root)
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
        # Read bytes and decode explicitly rather than letting text-mode
        # stdin decode under the platform locale -- the exact defect class
        # `gitapex_gate_exception_handler_gaps.py`'s own docstring describes
        # this same pattern closing (a non-UTF-8 byte escaping as an
        # uncaught traceback, or silently passing through under
        # surrogateescape). Fail closed with exit 2 rather than
        # errors="replace", the same choice that file makes for the
        # identical reason.
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
            f"\n{len(violations)} pair(s) of functions wrap the same recognizable network call but "
            "declare different exception sets for it (issue #1512). Align both handler sets on the "
            "wider (more-covering) tuple, the way `_gitapex_github_http.py`'s own `request_with_retry`/"
            "`graphql_call` were aligned -- or, when the difference is deliberate, disclose it inline "
            "with '# network-exception-set-drift: WAIVED: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

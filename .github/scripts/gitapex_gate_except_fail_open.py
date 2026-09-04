#!/usr/bin/env python3
"""CI gate: an `except` clause newly added by a PR diff to `.github/scripts/*.py`
or `hooks/*.py` must not fail open -- catch a real failure and silently hand
back a falsy default (`None`, `[]`, `{}`, `set()`, `frozenset()`, `()`, `""`,
`0`, `False`) with no re-raise.

Issue #1722 (from #1704, #1706): `load_python_dependent_hook_script_names`
(`.github/scripts/gitapex_gate_bare_python3_invocation.py`) shipped exactly
this defect class twice -- a malformed whole-file `.gitapex/ssot.json`
silently read as "nothing registered" (#1704), and a single gate entry's own
malformed `preconditions` shape silently skipped as "this entry contributes
nothing" (#1706) -- each one making a *different* gate (the bare-python3-
invocation check itself) report a false "clean" verdict instead of the "this
gate could not be trusted" it should have. Both were fixed on `main`
(commits `f6e97a7`, `f6bed27`) before this gate existed; this gate is the
recurrence-prevention measure issue #1722 asks for, not a re-fix of that
function.

Deliberately a sibling of `gitapex_gate_exception_handler_gaps.py` (issue
#682), not an extension of it: that gate asks "does this `except` clause
actually cover the failure the code beneath it can raise"; this one asks "when
this `except` clause DOES fire, does it fail open or fail closed". Two
distinct questions about the same class of code, matching this repository's
own one-gate-per-concern convention. This gate reuses that sibling's own
diff-parsing state machine (`parse_added_lines`, hardened across issues
#1184/#1193/#1200/two adversarial-review rounds) and its inline-waiver
convention verbatim rather than re-deriving either -- see that file's own
module docstring for the full history of why each hardening exists; it is
not repeated here.

**Detection rule, deliberately literal-last-statement-only.** For each
`except`/`except*` clause: if its own body contains no `raise` anywhere
(bare `raise`, `raise X`, or `raise X from Y`, searched recursively but never
crossing into a nested function/lambda's own deferred body) AND the body's
own last top-level statement is either

* `return <falsy-literal>` (or a bare `return`, or `return None`), or
* `<Name> = <falsy-literal>` (a single-target assignment, plain or
  annotated),

it is flagged. A falsy literal is `None`, `[]`, `{}`, `()`, `""`, integer
`0`, `False`, `set()` or `frozenset()` (with no arguments) -- read
syntactically, not evaluated, so `EMPTY_LIST` (a same-valued constant behind
a name) is not recognised and a genuinely-empty-but-differently-spelled
default (`list()`, `dict()`) is not either; see Known misses below.

**Why "any raise anywhere in the body" rather than "the true terminal
statement of every reachable path".** The literal example this gate is
built to accept -- "legitimate logging followed by a real error" -- is
`except OSError: logger.warning(...); raise`, where the raise really is the
body's own last statement. Searching for a raise ANYWHERE, rather than
requiring it be the syntactic last statement, is a deliberate widening in
the same direction: an `if cause_is_recoverable(): raise SomeError() else:
raise` still contains a real re-raise on every one of its own reachable
exits, and demanding one specific AST shape for it would only manufacture a
false positive on code that already fails closed. The cost, stated rather
than hidden, is symmetrical to that widening: an `if/else` where only ONE
branch raises and the other silently returns/assigns a falsy default is not
flagged, because this gate does not attempt branch-reachability analysis at
all -- see Known misses.

**Why "last top-level statement" rather than "any falsy return/assign
anywhere".** A falsy default assigned or returned partway through a handler,
with a real `raise` (or a real, non-falsy `return`) after it, is not the
handler's own effective exit and must not be flagged -- matching the
"the last meaningfully-covered statement" framing issue #1722 itself uses.
Restricting the check to the body's own last top-level statement is the
simplest rule that respects that framing without attempting full
control-flow analysis; walking into nested `if`/`for`/`with` blocks to find
a "true" last statement was considered and rejected for the same reason the
sibling gate rejects order-sensitive taint tracking: a verdict that depends
on how deeply a contributor happens to nest their own code is worse than one
that misses a deeper case outright.

**Known misses, each a decision rather than an oversight:**

* An `if`/`try`/`for`/`with` as the body's own last top-level statement is
  never inspected for its own trailing falsy return/assign, however
  reachable one branch's own tail is -- see the two bullets above.
* Falling off the end of the *function* the handler sits in -- catch, log,
  do nothing, and let control fall through to the function's own implicit
  `return None` -- is not graded. Recognising it needs the function's own
  return-type intent (an annotation, or the shape of its OTHER `return`
  statements), and a handler that legitimately logs-and-continues into more
  of the function's own code (the ordinary case; the try/except is the
  function's own LAST statement only rarely) is not distinguishable from one
  that silently swallows a failure without resolving that intent first --
  the same class of machinery `gitapex_gate_exception_handler_gaps.py`'s own
  docstring records building and reverting more than once. If this class of
  miss is later measured as common enough to be worth the added false-
  positive risk, it is a follow-up, not a guess made here.
* A falsy value behind a name (`EMPTY: dict = {}` at module scope, `return
  EMPTY`) is not recognised -- this gate reads the literal syntax of the
  handler's own last statement, not a resolved value; the sibling gate's own
  docstring records the same trade for the identical reason (name resolution
  has cost more than it bought, three times, in that file's own history).
* `list()`/`dict()`/`tuple()` (a falsy value spelled as a zero-argument
  constructor call rather than a literal) are not recognised; only `set()`
  and `frozenset()` are, because those two have no literal spelling at all
  -- `{}` is already a dict. Widening this to the other three is a
  measurement, not a guess: this repository's own `.github/scripts/*.py`/
  `hooks/*.py` files were grep-checked for `except`-body-final
  `list()`/`dict()`/`tuple()` calls at authoring time and none exist today.
* A falsy tuple/list/dict/set built from a comprehension that happens to be
  empty at runtime (`[x for x in ()]`) is not recognised -- read
  syntactically, that is not a literal.
* `except* X:` (`ast.TryStar`) is graded with the identical rule as a plain
  `except X:` -- no attempt is made to reason about which of several
  concurrently-raised exception groups a given handler actually saw.

**Known over-report.** A function whose documented contract is "returns
`None`/an empty collection when the input is absent, by design" (a real
sentinel, not a swallowed failure) is graded the same as one that fails
open by accident -- this gate has no way to read intent from a docstring.
The inline waiver below is the documented answer, the same role it plays for
`gitapex_gate_exception_handler_gaps.py`'s own over-reports.

**Scope is the diff, not the repository**, for the identical reason the
sibling gate states for its own scope: grading only what a diff *adds* costs
nothing against the defect class this gate exists to prevent (both #1704 and
#1706 were new code in their own PR), and a diff-scoped rule needs no
allowlist file for this repository's own pre-existing debt. In-scope paths
are `.github/scripts/*.py` and `hooks/*.py` only -- narrower than the
sibling gate's four-directory scope, matching issue #1722's own stated scope
verbatim rather than the wider one #682 already covers. Test files
(`test_*.py`, `conftest.py`) are excluded everywhere, matching that same
sibling convention: a test that hands this gate a fail-open fixture on
purpose is doing its job.

A finding counts as this diff's when an added line touches the `except`
clause's own header, or the offending return/assignment statement itself --
narrowing a handler (`except ValueError` to `except OSError`) without
touching its body still creates or destroys this finding, and neither
change alone is inside the other's own span.

An intentional fail-open handler discloses itself inline with a trailing
`# except-fail-open: WAIVED: <reason>` comment on the `except` line this
gate names in its own message -- the same `WAIVED: <reason>` vocabulary and
tokenize-based matching `gitapex_gate_exception_handler_gaps.py` already
uses. A bare marker with no reason is not a waiver. Every honoured waiver is
printed, so it is never a silent bypass.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_run_base_diff.py -- \\
        '.github/scripts/*.py' 'hooks/*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_except_fail_open.py

or, in CI, against a specific merge-base/head pair::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '.github/scripts/*.py' 'hooks/*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_except_fail_open.py

A bare pipe in either example masks the upstream command's own exit status in
a non-`pipefail` shell (issue #1531): add `set -o pipefail` first, or check
that command's own exit code separately, if the caller must detect an
upstream failure rather than silently grading whatever partial diff reached
stdin.

Reads a unified diff on stdin (or `--diff <file>`); diagnostics and
violations go to stderr.

Exit codes, matching `gitapex_gate_exception_handler_gaps.py`'s own
convention exactly: 0 clean (an empty diff is clean), 1 a fail-open `except`
clause was found, 2 the scan could not be trusted (a malformed diff, or an
in-scope file that cannot be read or parsed as Python) -- dimension 15 of
`skills/evaluating-deterministic-gate-quality/references/dimensions.md`
applies to this gate's own input handling too: a file this gate cannot
grade must never pass silently.

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed fails at import time, before argparse
even runs) or via the pytest gate in
`tests/test_gitapex_gate_except_fail_open.py`.
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

# Narrower than gitapex_gate_exception_handler_gaps.py's own four-directory
# scope -- issue #1722 states exactly these two directories, not the wider
# set #682 already covers.
_IN_SCOPE_RE = re.compile(r"\.github/scripts/[^/]+\.py|hooks/[^/]+\.py")

_RULE_ID = "except-fail-open"

# `# except-fail-open: WAIVED: <reason>` -- a reason is mandatory, matching
# gitapex_gate_exception_handler_gaps.py's own _WAIVER_RE exactly (same
# vocabulary, this gate's own id).
_WAIVER_RE = re.compile(r"#\s*except-fail-open\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# Zero-argument constructor calls with no literal spelling of their own.
# list()/dict()/tuple() are deliberately excluded -- see the module
# docstring's own Known-misses section.
_FALSY_CONSTRUCTOR_CALLS = frozenset({"set", "frozenset"})


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation, anchored at the `except` clause's own header line."""

    path: str
    line: int
    rule: str
    message: str


def in_scope(path: str) -> bool:
    """True iff `path` is a `.github/scripts/*.py` or `hooks/*.py` file this
    gate grades. Test files are excluded everywhere: a test that feeds this
    gate a fail-open fixture on purpose is doing its job."""
    if not _IN_SCOPE_RE.fullmatch(path):
        return False
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith("test_") or name == "conftest.py")


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null` (a deletion). Anything other than `/dev/null` or git's own
    `b/`-prefixed post-image raises `ScanError` -- see
    gitapex_gate_exception_handler_gaps.py's own identical helper for why
    guessing wrong here is a silent fail-open this gate must not repeat on
    itself."""
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
    `--- `/`+++ ` header pair always has (`a/<path>` or `/dev/null`, then
    `b/<path>` or `/dev/null`), not just the 4-character prefix -- see
    gitapex_gate_exception_handler_gaps.py's own identical helper for the
    live-reproduced bypass this closes."""
    source = source_line[4:]
    target = target_line[4:]
    return (source == "/dev/null" or source.startswith("a/")) and (target == "/dev/null" or target.startswith("b/"))


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into `{post-image path: added line numbers}`.

    Verbatim port of `gitapex_gate_exception_handler_gaps.py`'s own function
    of the same name -- same state machine, same hardening (hunk
    over-/under-declaration bounds, the missing-source-header check, and the
    disguised-header-pair bypass guard from that file's own two
    independent-adversarial-review rounds). See that file's own docstring
    for the full history of why each guard exists; not re-derived here.
    """
    added: dict[str, set[int]] = {}
    path: str | None = None
    lineno = 0
    in_hunk = False
    old_remaining = 0
    new_remaining = 0
    saw_source_header = False

    def _reject_if_hunk_incomplete(boundary: str) -> None:
        # function-body-test-coverage: WAIVED: a private closure nested inside
        # parse_added_lines, with no name accessible from outside this function
        # to reference directly; its raise path is exercised through
        # parse_added_lines' own over-declared-hunk-count regression tests
        # instead.
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


def _iter_own_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Yield every descendant of `node`, excluding the bodies of a nested
    function/lambda definition -- those run in their own deferred scope, not
    this handler's, matching gitapex_gate_exception_handler_gaps.py's own
    identical exclusion."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        yield child
        yield from _iter_own_scope(child)


def _contains_raise(body: list[ast.stmt]) -> bool:
    """True iff a `raise` (bare, or naming an exception) appears anywhere in
    `body`, at any nesting depth, excluding a nested function/lambda's own
    body. See the module docstring for why this is deliberately
    reachability-blind: any raise anywhere is read as "this handler can fail
    closed", never narrowed to only the branch that actually executes.

    A top-level statement that is itself a nested function/lambda
    definition is skipped outright, not just its own descendants --
    `_iter_own_scope`'s exclusion only fires when such a definition is
    found as a CHILD during iteration, so calling it directly on a
    statement that is one would still walk that statement's own body."""
    for stmt in body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        if isinstance(stmt, ast.Raise):
            return True
        for node in _iter_own_scope(stmt):
            if isinstance(node, ast.Raise):
                return True
    return False


def _is_falsy_literal(node: ast.expr | None) -> bool:
    """True iff `node` is one of this gate's nine falsy-default shapes,
    read syntactically. `node is None` (a bare `return`) counts as the
    `None` default too."""
    if node is None:
        return True
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return True
        if isinstance(value, bool):
            return value is False
        if isinstance(value, int):
            return value == 0
        if isinstance(value, str):
            return value == ""
        return False
    if isinstance(node, ast.List | ast.Tuple):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    if isinstance(node, ast.Call):
        return (
            isinstance(node.func, ast.Name)
            and node.func.id in _FALSY_CONSTRUCTOR_CALLS
            and not node.args
            and not node.keywords
        )
    return False


_FalsyExit = ast.Return | ast.Assign | ast.AnnAssign


def _falsy_exit(body: list[ast.stmt]) -> _FalsyExit | None:
    """Return the handler body's own last top-level statement, iff it is a
    `return <falsy-literal>` or a single-Name-target `<falsy-literal>`
    assignment -- the two shapes issue #1722 names (#1704's `return None`/
    `return {}`, #1706's `value = None`). Returns None otherwise: an `if`,
    `for`, `with`, `try`, `pass`, bare expression, or any non-falsy
    return/assign as the last statement is never this gate's finding. See
    the module docstring's own rationale for why only the literal last
    statement is inspected. A bare annotation (`value: dict`, `last.value
    is None`) is never a finding either: it performs no assignment at
    runtime, so `_is_falsy_literal(None)`'s own bare-`return` reading
    (which is correct for `ast.Return`) would otherwise misclassify a
    no-op annotation as "assigns a falsy default" (Step 8 adversarial
    review, issue #1722)."""
    last = body[-1]
    if isinstance(last, ast.Return) and _is_falsy_literal(last.value):
        return last
    if (
        isinstance(last, ast.Assign)
        and len(last.targets) == 1
        and isinstance(last.targets[0], ast.Name)
        and _is_falsy_literal(last.value)
    ):
        return last
    if (
        isinstance(last, ast.AnnAssign)
        and last.value is not None
        and isinstance(last.target, ast.Name)
        and _is_falsy_literal(last.value)
    ):
        return last
    return None


def _describe(offending: _FalsyExit) -> str:
    if isinstance(offending, ast.Return):
        shown = "None" if offending.value is None else ast.unparse(offending.value)
        return f"returns a falsy default ({shown}) with no re-raise"
    target = offending.targets[0] if isinstance(offending, ast.Assign) else offending.target
    value = ast.unparse(offending.value) if offending.value is not None else "None"
    return f"assigns {ast.unparse(target)} a falsy default ({value}) with no re-raise"


def _handler_header_lines(handler: ast.ExceptHandler) -> set[int]:
    """The `except ...:` clause header's own lines, body excluded --
    narrowing a handler (`except ValueError` to `except OSError`) creates or
    destroys this finding without touching the offending statement itself,
    matching gitapex_gate_exception_handler_gaps.py's own identical
    rationale."""
    end = handler.type.end_lineno if handler.type is not None else None
    return set(range(handler.lineno, (end if end is not None else handler.lineno) + 1))


def _stmt_lines(stmt: ast.stmt) -> set[int]:
    end = stmt.end_lineno if stmt.end_lineno is not None else stmt.lineno
    return set(range(stmt.lineno, end + 1))


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying an honoured inline waiver comment. Read
    through `tokenize`, not a regex over raw text, so a string literal
    quoting this gate's own documentation (this file, and its tests, both
    do) is never mistaken for a real waiver. Deliberately unguarded: the
    only caller runs `ast.parse` on this same source first and turns any
    failure into `ScanError`, and CPython's own parser tokenizes what it
    parses -- matching gitapex_gate_exception_handler_gaps.py's own
    identical, identically-justified choice."""
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


def findings_for_source(path: str, source: str, added: set[int]) -> tuple[list[Finding], list[Finding]]:
    """Grade one file's source, returning `(violations, honoured waivers)`.

    Only a finding an added line could have created is returned -- a
    pre-existing fail-open handler another PR owns is never this diff's
    failure."""
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

    waived_lines = _waived_lines(source)
    violations: list[Finding] = []
    waived: list[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try | ast.TryStar):
            continue
        # A `finally:` clause that raises supersedes every handler's own
        # pending return/assign -- the statement never actually completes,
        # so a handler that looks fail-open in isolation is not: it always
        # re-raises via the enclosing `finally`. Checked once per `Try`
        # node (not per handler) since it covers every sibling handler
        # identically (Step 8 adversarial review, issue #1722).
        if _contains_raise(node.finalbody):
            continue
        for handler in node.handlers:
            if not handler.body or _contains_raise(handler.body):
                continue
            offending = _falsy_exit(handler.body)
            if offending is None:
                continue
            trigger = _handler_header_lines(handler) | _stmt_lines(offending)
            if not (trigger & added):
                continue
            finding = Finding(path, handler.lineno, _RULE_ID, _describe(offending))
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


class GateExceptFailOpenArgs(BaseModel):
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
        description="Check that an except clause newly added by a PR diff to .github/scripts/*.py "
        "or hooks/*.py does not fail open (a falsy default, no re-raise). Reads a unified diff on "
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
        validated = GateExceptFailOpenArgs(root=args.root)
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
        print(
            f"{finding.path}:{finding.line}: {finding.rule}: waived inline -- {finding.message}",
            file=sys.stderr,
        )

    if violations:
        for finding in violations:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.message}", file=sys.stderr)
        print(
            f"\n{len(violations)} except clause(s) added by this diff fail open. This is issue "
            "#1722's own recurrence-prevention gate (refs #1704, #1706): catching a real failure "
            "and silently returning/assigning a falsy default with no re-raise turns a bug into a "
            "false 'clean' verdict somewhere downstream. Re-raise, or disclose an intentional "
            "sentinel inline with '# except-fail-open: WAIVED: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

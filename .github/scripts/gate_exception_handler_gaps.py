#!/usr/bin/env python3
"""CI gate: a decoded read, or a `.get()` on a `json.loads` result, added by
this diff must handle the failure it can actually raise.

Issue #682 (refs #665, #673, #674, #680). Five separate times this
repository has shipped the same defect into one of its own gates: a script
reads a file, has clearly thought about the read failing -- it catches
`OSError`, or `FileNotFoundError`, or nothing at all -- and then a non-UTF-8
byte or a valid-but-non-object JSON payload escapes as an uncaught
traceback, exiting 1 instead of the script's own documented error code.
Three named instances, each still readable in this repository's history and
each reproduced as a regression fixture in
`tests/test_gate_exception_handler_gaps.py`:

* `f91383c:.github/scripts/gate_plugin_root_brace_notation.py:116` --
  `text = path.read_text(encoding="utf-8")` inside no `try` at all
  (issue #682's defect C, shipped by PR #651).
* `406d587:.github/scripts/detect_changed_gate_scripts.py:112` --
  `gates = data.get("gates")` on a `json.loads` result never checked to be
  an object (defect E, found in PR #674's review rounds).
* `0b4cedd:.github/scripts/detect_changed_gate_scripts.py:298` --
  `open(args.unified_diff, encoding="utf-8").read()` inside a `try` whose
  only handler is `except OSError` (defect F, same rounds).

Every one of those passed pytest, and every affected file measured 100
percent line coverage. Issue #682's own measurement explains why: the
handler that *would* have caught the failure does not exist, so no
line-coverage, branch-coverage or `except`-line-coverage metric can point
at it, and `ruff --select ALL` reports zero findings on any of the three
defect lines. This gate is the answer measured for that class.

Two rules, both computed from the AST, both stdlib:

**Rule `decode-gap`.** A call that decodes bytes to text -- `read_text(...)`,
or `open(...)` in a text read mode -- whose enclosing `try` statements
handle no exception type that a `UnicodeDecodeError` would satisfy.
`UnicodeDecodeError`, `UnicodeError`, `ValueError`, `Exception`,
`BaseException` and a bare `except:` all count as covered, since each is
that exception or one of its ancestors.

**Rule `json-shape-gap`.** A `.get(...)` on a value that came from
`json.loads(...)` / `json.load(...)`, in a scope that never calls
`isinstance()` on it. `[]`, `"x"`, `1`, `true` and `null` are all valid
JSON, so `json.JSONDecodeError` never fires for them and the `.get()`
raises `AttributeError` instead.

**Scope is the diff, not the repository, and that is the load-bearing
design decision.** Measured against merged `main` (afd18eb) these two rules
report 41 findings across 46 in-scope files, none of them triaged. The six
that issue #680 *had* triaged and reproduced by execution are no longer
among them: PR #696 repaired those, and running these rules over the six
files it touched now reports zero, which is an independent confirmation of
that repair rather than a claim inherited from it. Issue #682's own
acceptance criteria require a detector's findings to be triaged before it
becomes blocking, precisely so a gate does not land shouting about
pre-existing debt and train its readers to ignore it -- and triaging 41 by
execution is its own change, not a side effect of this one. Grading only
what a diff *adds* costs nothing against the defects this gate exists to
prevent: all five recurrences were new code in their own PR, so a
diff-scoped rule would have caught each one at the moment it was
introduced. It also needs no allowlist file, which would otherwise be more
code than the gate itself, and a fail-open surface of its own.

A finding counts as this diff's when any line of the offending expression
is an added line, so a multi-line call is graded wherever it was touched.

In-scope paths are this repository's deterministic checker scripts --
`.github/scripts/*.py`, `hooks/*.py`, `evals/scripts/*.py`,
`skills/*/scripts/*.py` -- the same set issue #565 already defined for
`checker-script-adversarial-review`, widened by `hooks/` for the reason
`detect_changed_gate_scripts.py` widened its own rule 1 there: 9 registered
gates live under `hooks/`, and issue #680 found one of these two defects in
`hooks/check_pr_issue_acm_disclosure.py`. Test files (`test_*.py`,
`conftest.py`) are out of scope everywhere: a test that hands a gate
malformed input is doing its job.

Deliberately not graded, each because the shape does not reach the defect
class this gate was measured against: a read from `sys.stdin`, a write-mode
`open()` (that raises `UnicodeEncodeError`, a different failure), a binary
read, and a subscript or `.items()` on an unvalidated JSON result rather
than a `.get()`. Widening any of them is a measurement, not a guess -- run
the rule repo-wide and triage the delta first, the same way this one was.

An intentional read that a *caller* guards can disclose itself inline with
a trailing `# exception-handler-gap: WAIVED: <reason>` comment, the same
`WAIVED: <reason>` vocabulary `gate_skill_audit_disclosure.py` already uses
and the same inline shape this repository's existing `# noqa: S603`
waivers take. A bare marker with no reason is not a waiver. Every honoured
waiver is printed, so it is never a silent bypass.

Standard library only, so the calling workflow needs no dependency install.

Usage::

    git diff -U0 "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | python3 .github/scripts/gate_exception_handler_gaps.py

Reads a unified diff on stdin; diagnostics and violations go to stderr.

Exit codes: 0 clean (an empty diff is clean, and is the common case),
1 violation found, 2 the scan could not be trusted (a malformed diff, or
an in-scope file that cannot be read or parsed). The 2 case is dimension
15 of `skills/evaluating-deterministic-gate-quality/references/
dimensions.md`: a file this gate cannot grade must never pass silently.

Run standalone or via the pytest gate in
`tests/test_gate_exception_handler_gaps.py`.
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

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# The four directories holding this repository's deterministic checker
# scripts. `[^/]+` rather than `.*` so no pattern crosses a directory
# separator, matching `detect_changed_gate_scripts.py`'s own rule-1
# reasoning; always applied with `re.fullmatch`, never `re.match`, since
# `$` would also accept a trailing newline.
_IN_SCOPE_RE = re.compile(
    r"\.github/scripts/[^/]+\.py"
    r"|hooks/[^/]+\.py"
    r"|evals/scripts/[^/]+\.py"
    r"|skills/[^/]+/scripts/[^/]+\.py"
)

# Every ancestor of UnicodeDecodeError, plus the exception itself. A handler
# naming any of them already catches a decode failure, so the read is
# covered. Attribute handlers (`json.JSONDecodeError`) are compared by their
# final attribute name, which is why the bare names suffice here.
_DECODE_COVERING = frozenset(
    {"UnicodeDecodeError", "UnicodeError", "ValueError", "Exception", "BaseException"}
)

_JSON_PARSERS = frozenset({"loads", "load"})

# `# exception-handler-gap: WAIVED: <reason>` -- a reason is mandatory, the
# same way `gate_skill_audit_disclosure.py`'s own `WAIVED:` clause requires
# one. A bare marker is not a waiver and is not honoured.
_WAIVER_RE = re.compile(r"#\s*exception-handler-gap\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

_DECODE_GAP = "decode-gap"
_JSON_SHAPE_GAP = "json-shape-gap"


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation, anchored at the line that would raise."""

    path: str
    line: int
    rule: str
    message: str


def in_scope(path: str) -> bool:
    """Return True iff `path` is a checker script this gate grades.

    Test files are excluded everywhere: a test that feeds a gate malformed
    input, or reads a fixture it just wrote, is doing its job and has no
    contract to fail closed.
    """
    if not _IN_SCOPE_RE.fullmatch(path):
        return False
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith("test_") or name == "conftest.py")


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null` (a deletion, which adds nothing to grade).

    Raises ``ScanError`` on a git-quoted path rather than guessing at its
    unescaping: a path this gate cannot resolve is one it cannot decide the
    scope of, and a wrong answer here silently drops a file from grading.
    """
    target = raw.strip()
    if target == "/dev/null":
        return None
    if target.startswith('"'):
        raise ScanError(f"unified diff carries a quoted path this gate cannot resolve: {target}")
    # `git diff` prefixes the post-image with `b/`; `--no-prefix` output has
    # no prefix at all, and both are accepted.
    return target[2:] if target.startswith("b/") else target


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into ``{post-image path: added line numbers}``.

    Only added lines are recorded. A removal is never a line this gate can
    grade -- there is no code left at it -- and an unchanged context line is
    pre-existing content another PR already owns.
    """
    added: dict[str, set[int]] = {}
    path: str | None = None
    lineno = 0
    for line in diff_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith("diff --git "):
            # Reset before the `--- a/...` line arrives, so that line is
            # never mistaken for a removal inside the previous file's hunk.
            path = None
            continue
        if line.startswith("+++ "):
            path = _diff_target_path(line[4:])
            continue
        if line.startswith("@@"):
            match = _HUNK_RE.match(line)
            if not match:
                raise ScanError(f"unparseable hunk header: {line!r}")
            lineno = int(match.group(1))
            continue
        if path is None:
            continue
        if line.startswith("+"):
            added.setdefault(path, set()).add(lineno)
            lineno += 1
        elif line.startswith(" "):
            lineno += 1
        # A `-` removal consumes no post-image line, and `\ No newline at
        # end of file` is a marker, not content. Both advance nothing.
    return added


def _handler_names(handler: ast.ExceptHandler) -> set[str]:
    """Return the exception names one `except` clause catches.

    A bare `except:` catches everything, so it reports `BaseException`. An
    attribute handler (`json.JSONDecodeError`) reports its final attribute
    name, which is what `_DECODE_COVERING` compares against.
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


def _decode_covered_calls(tree: ast.Module) -> set[int]:
    """Return the ``id()`` of every Call lexically inside a `try` body whose
    handlers cover a decode failure.

    Only the `try` *body* counts. A read inside an `except`, `else` or
    `finally` clause is not protected by that same statement's own handlers,
    which is exactly where a "read the file again to report a better error"
    fallback tends to live.
    """
    covered: set[int] = set()

    def walk(node: ast.AST, protected: bool) -> None:
        if isinstance(node, ast.Try):
            handled: set[str] = set()
            for handler in node.handlers:
                handled |= _handler_names(handler)
            body_protected = protected or bool(handled & _DECODE_COVERING)
            for child in node.body:
                walk(child, body_protected)
            for handler in node.handlers:
                for child in handler.body:
                    walk(child, protected)
            for child in [*node.orelse, *node.finalbody]:
                walk(child, protected)
            return
        if protected and isinstance(node, ast.Call):
            covered.add(id(node))
        for descendant in ast.iter_child_nodes(node):
            walk(descendant, protected)

    for statement in tree.body:
        walk(statement, False)
    return covered


def _text_read_kind(node: ast.Call) -> str | None:
    """Return the decoding-read shape `node` performs, or None.

    `open()` is graded only in a text *read* mode. A write-only mode raises
    `UnicodeEncodeError`, a different failure this gate was not measured
    against, and a binary mode decodes nothing at all. A mode this gate
    cannot read statically is treated as a read: guessing "probably a write"
    would be the fail-open direction.
    """
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "read_text":
        return "read_text"

    is_open = (isinstance(func, ast.Name) and func.id == "open") or (
        isinstance(func, ast.Attribute) and func.attr == "open"
    )
    if not is_open:
        return None

    mode: ast.expr | None = node.args[1] if len(node.args) >= 2 else None
    for keyword in node.keywords:
        if keyword.arg == "mode":
            mode = keyword.value
    if mode is None:
        return "open"
    if not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)):
        return "open"
    if "b" in mode.value:
        return None
    return "open" if ("r" in mode.value or "+" in mode.value) else None


def _is_json_parse(node: ast.expr) -> bool:
    """True for a `json.loads(...)` / `json.load(...)` call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _JSON_PARSERS
        and isinstance(func.value, ast.Name)
        and func.value.id == "json"
    )


_Scope = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef


def _scope_body(scope: _Scope) -> Iterator[ast.AST]:
    """Yield every node belonging to `scope` itself, excluding the bodies of
    nested functions -- those are their own scope and are walked separately.

    The cost of that exclusion is stated rather than hidden: a closure that
    reads an outer function's JSON value is not graded. Sharing the outer
    scope's taint would also share every *other* function's, so the same
    variable name validated in one function would silence it in all of them
    -- a fail-open in a gate whose whole subject is fail-open.
    """
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        yield child
        yield from _walk_excluding_nested_functions(child)


def _walk_excluding_nested_functions(node: ast.AST) -> Iterator[ast.AST]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        yield child
        yield from _walk_excluding_nested_functions(child)


def _scopes(tree: ast.Module) -> Iterator[_Scope]:
    yield tree
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def _json_shape_gaps(tree: ast.Module) -> Iterator[ast.Call]:
    """Yield every `.get()` call made on an unvalidated JSON result."""
    for scope in _scopes(tree):
        nodes = list(_scope_body(scope))
        tainted: set[str] = set()
        validated: set[str] = set()
        for node in nodes:
            if isinstance(node, ast.Assign) and _is_json_parse(node.value):
                tainted |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            elif isinstance(node, ast.AnnAssign | ast.NamedExpr) and node.value is not None:
                if _is_json_parse(node.value) and isinstance(node.target, ast.Name):
                    tainted.add(node.target.id)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "isinstance"
                and node.args
                and isinstance(node.args[0], ast.Name)
            ):
                validated.add(node.args[0].id)
        for node in nodes:
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "get":
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Name) and receiver.id in tainted and receiver.id not in validated:
                yield node
            elif _is_json_parse(receiver):
                # `json.loads(body).get(...)` -- the same defect with no
                # variable to taint, so no isinstance() can ever guard it.
                yield node


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying an inline waiver comment.

    Read through `tokenize` rather than a regex over raw text so the marker
    is only honoured as a real comment -- a string literal quoting this
    gate's own documentation (this file, and its tests, both do) must never
    silence a finding.

    Deliberately unguarded: the only caller runs `ast.parse` on this same
    source first and turns any failure into a ``ScanError``, and CPython's
    own parser tokenizes what it parses -- so a source that reaches here has
    already been proved tokenizable. A `try` around this loop would be a
    guard that can never be true, which is issue #682's own defect D and not
    a shape this gate should ship while grading others for the class.
    """
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


def findings_for_source(path: str, source: str, added: set[int]) -> tuple[list[Finding], list[Finding]]:
    """Grade one file's source, returning ``(violations, honoured waivers)``.

    Only findings whose expression touches an added line are returned, so a
    pre-existing gap another PR owns is never this diff's failure.
    """
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

    waived_lines = _waived_lines(source)
    covered = _decode_covered_calls(tree)

    candidates: list[tuple[Finding, set[int]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _text_read_kind(node)
        if kind is not None and id(node) not in covered:
            candidates.append(
                (
                    Finding(
                        path,
                        node.lineno,
                        _DECODE_GAP,
                        f"{kind}(...) decodes text, but no enclosing try handles UnicodeDecodeError "
                        "(or an ancestor of it)",
                    ),
                    _span(node),
                )
            )
    for node in _json_shape_gaps(tree):
        candidates.append(
            (
                Finding(
                    path,
                    node.lineno,
                    _JSON_SHAPE_GAP,
                    ".get() on a json.loads result never checked with isinstance(); a valid "
                    'non-object payload ([], "x", 1, null) raises AttributeError',
                ),
                _span(node),
            )
        )

    violations: list[Finding] = []
    waived: list[Finding] = []
    for finding, span in candidates:
        if not (span & added):
            continue
        if span & waived_lines:
            waived.append(finding)
        else:
            violations.append(finding)
    return sorted(set(violations)), sorted(set(waived))


def _span(node: ast.Call) -> set[int]:
    """Return every source line the offending expression occupies.

    A call written across several lines is graded wherever it was touched,
    so reformatting one argument of an existing call is enough to bring it
    into this diff's scope -- and so a waiver comment may sit on any of its
    lines rather than only the first.
    """
    end = node.end_lineno if node.end_lineno is not None else node.lineno
    return set(range(node.lineno, end + 1))


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
        if not in_scope(path) or not added:
            continue
        absolute = root / path
        try:
            source = absolute.read_text(encoding="utf-8")
        except FileNotFoundError:
            # The diff names a post-image path that is not in this checkout.
            # A deletion never reaches here (its `+++` line is /dev/null), so
            # this is a caller pointing --root at the wrong tree, or grading
            # a diff against a checkout that does not contain its head.
            raise ScanError(
                f"{path}: named by the diff as added or modified, but missing from {root}"
            ) from None
        except (OSError, UnicodeDecodeError) as error:
            raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
        file_violations, file_waived = findings_for_source(path, source, added)
        violations.extend(file_violations)
        waived.extend(file_waived)
        graded += 1
    return violations, waived, graded


class GateExceptionHandlerGapsArgs:
    """Typed view of `main`'s parsed CLI namespace. `root` must be an
    existing directory -- every existing caller already passes one, so this
    only gives a --root pointing nowhere a clear, early error instead of the
    deeper "missing from <root>" ScanError it would otherwise surface."""

    def __init__(self, *, root: pathlib.Path) -> None:
        if not root.is_dir():
            raise ValueError(f"--root must be an existing directory, got {root}")
        self.root = root


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 clean, 1 violation found, 2 the scan could not be trusted."""
    parser = argparse.ArgumentParser(
        description="Check that decoded reads and json.loads results added by this "
        "diff handle the failures they can actually raise. Reads a unified diff "
        "on standard input."
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
        validated = GateExceptionHandlerGapsArgs(root=args.root)
    except ValueError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    if args.diff is not None:
        try:
            diff_text = args.diff.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"{args.diff}: diff cannot be read as UTF-8 text: {error}", file=sys.stderr)
            return 2
    else:
        diff_text = sys.stdin.read()

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
            f"\n{len(violations)} added line(s) reach a failure they do not handle. This is the "
            "defect class that has now shipped into this repository's own gates five times "
            "(refs #682, #680, #665): every instance passed pytest at 100 percent line "
            "coverage, because the handler that would have caught it does not exist. Catch the "
            "failure at the read boundary and raise this script's own typed error, the way "
            ".github/scripts/detect_changed_gate_scripts.py does -- or, when a caller genuinely "
            "owns the handling, disclose it inline with "
            "'# exception-handler-gap: WAIVED: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

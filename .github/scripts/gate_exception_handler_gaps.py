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
or `open(...)` in a text read mode, and not one carrying a substituting
`errors=` policy, which cannot raise at all -- whose enclosing handlers
name no exception type that a `UnicodeDecodeError` would satisfy.
`UnicodeDecodeError`, `UnicodeError`, `ValueError`, `Exception`,
`BaseException` and a bare `except:` all count as covered, since each is
that exception or one of its ancestors. Handler names are read literally:
nothing is resolved, and the two places where resolving was tried are in
the over-report list below.

**Rule `json-shape-gap`.** A `.get(...)` on a value that came from
`json.loads(...)` / `json.load(...)` in the same scope, with no
`isinstance()` against a mapping type (`dict`, `Mapping`, `MutableMapping`)
before it, where every member of a tuple of types has to be one. `[]`,
`"x"`, `1`, `true` and `null` are all valid JSON, so `json.JSONDecodeError`
never fires for them and the `.get()` raises `AttributeError` instead. The
same enclosing-handler analysis applies: a `.get()` inside a `try` naming
`AttributeError` or an ancestor is covered, which is exactly the fix this
gate's own failure message prescribes and which it used to reject. A name
assigned both a parse and something else anywhere in the scope is dropped
rather than tainted -- order-blind on purpose, see below.

**Scope is the diff, not the repository, and that is the load-bearing
design decision.** Measured against merged `main` (afd18eb) these two rules
report 39 findings across the 46 in-scope files it then had, none of them
triaged. The six that issue #680 *had* triaged and reproduced by execution
are no longer among them: PR #696 repaired those, and running these rules
over the six files it touched now reports zero, which is an independent
confirmation of that repair rather than a claim inherited from it. Issue #682's own
acceptance criteria require a detector's findings to be triaged before it
becomes blocking, precisely so a gate does not land shouting about
pre-existing debt and train its readers to ignore it -- and triaging 39 by
execution is its own change, not a side effect of this one. Grading only
what a diff *adds* costs nothing against the defects this gate exists to
prevent: all five recurrences were new code in their own PR, so a
diff-scoped rule would have caught each one at the moment it was
introduced. It also needs no allowlist file, which would otherwise be more
code than the gate itself, and a fail-open surface of its own.

A finding counts as this diff's when an added line touches the offending
expression, an enclosing `except` clause, or anything between a JSON parse
and the access it feeds. Anchoring on the expression alone was not enough,
and that was found by review rather than by reasoning: narrowing
`except ValueError` to `except OSError` creates a decode gap without
editing the read, and replacing an `isinstance` guard creates a shape gap
without editing the `.get()`. Both are added lines; neither is inside the
expression. A waiver, unlike a trigger, is honoured on exactly one line:
the one the finding is reported at. Put the comment where the error points.

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

**Known misses, each one a decision that was made and then measured, not an
oversight.** Three of them are places where a more capable rule was built,
found to be wrong in *both* directions under adversarial review, and
reverted to something narrower that is only ever wrong in the missing
direction -- which is the trade issue #682's own bar asks for, and the
trade a blocking gate has to make if it is to survive contact with
contributors:

* **Taint does not cross a scope.** `CONFIG = json.loads(...)` at module
  level, read through `CONFIG.get(...)` inside a function, is not reported.
  Inheriting it needed parameter, local-rebinding and import shadowing to
  avoid false positives; each of those needed statement order; and
  order-sensitivity made the verdict depend on which branch of a
  `try/except` was written first. A rule whose answer depends on branch
  order is worse than one that misses.
* **A name assigned both a parse and something else is dropped, wherever
  those assignments sit.** `try: CONFIG = json.loads(...) except:
  CONFIG = {}` is the ordinary config-with-fallback and is not reported.
* **A generator expression is protected like a comprehension.** One
  assigned inside a `try` and consumed outside it genuinely escapes that
  handler, and is not reported. Treating every genexp as deferred was a
  false positive on `sorted(p.read_text() for p in ps)` -- which IS caught,
  and is the only genexp-in-a-try shape this repository contains -- and
  restricting the exception to "passed straight into a call" produced four
  more false positives (keyword argument, starred, `for`-clause,
  assign-then-consume) while making the same program grade differently
  depending on whether it was spelled `list(x for x in y)` or
  `[x for x in y]`.
* An `isinstance()` is read as a guard wherever it appears in the scope
  before the access, not only in a branch that actually protects it, so
  `if isinstance(data, dict): pass` clears it. Deciding otherwise needs
  branch analysis, which is the class of machinery the bullets above record
  removing.
* A guard deleted with nothing added in its place leaves no added line for
  any diff-scoped rule to key on.

**Known over-reports.** Each of these is correct code that this gate
reports, and for each the inline waiver is the documented answer. Every one
of them had a fix written, measured, and reverted, because recognising the
construct cost a fail-open on issue #682's own defect F shape -- which is
the thing this gate exists for:

* `except _READ_ERRORS:` where the tuple is a constant. Expanding it
  applied a name table with no scope awareness, so a rebinding, a local
  shadow, a parameter default or a `for` target of that name silenced the
  rule outright -- four fail-opens.
* A handler naming a project exception class this gate cannot classify.
  Assuming an unrecognised handler covers silenced defect F itself, whose
  outer `except ScopeError:` wraps the inner `except OSError:`.
* `contextlib.suppress(UnicodeDecodeError)`. Matching the label `suppress`
  on any receiver silenced a same-named method on an unrelated object,
  while still missing `suppress` behind an import alias, a starred
  argument, or a constant.
* A read whose *caller* owns the handling. This is the case the inline
  waiver was built for in the first place.

None of the four occurs anywhere in the graded directories today, which is
why each was measured as a poor trade rather than an urgent one.

Every miss and every over-report above is pinned by a test asserting the
behaviour, so none can change without a reader noticing.

An intentional read that a *caller* guards can disclose itself inline with
a trailing `# exception-handler-gap: WAIVED: <reason>` comment on the line
this gate names in its own message -- the same `WAIVED: <reason>`
vocabulary `gate_skill_audit_disclosure.py` already uses and the same
inline shape this repository's existing `# noqa: S603` waivers take. It
waives every finding reported on that line. A bare marker with no reason is
not a waiver. Every honoured waiver is printed, so it is never a silent
bypass.

Standard library only, so the calling workflow needs no dependency install.

Usage::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | python3 .github/scripts/gate_exception_handler_gaps.py

Both flags are load-bearing, not tidiness: rename detection hides a file
promoted into a graded directory behind a zero-added-line header, and
`core.quotePath` renders a non-ASCII path as an escaped string this gate
refuses to resolve. The second covers the non-ASCII case only -- git quotes
a path containing a quote, a backslash or a control character regardless,
and such a path still exits 2, fail-closed on a name that cannot be
resolved. The calling workflow states each at its own use site.

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
import bisect
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

# The `.get()` rule's own covering set. AttributeError is what an unvalidated
# JSON payload actually raises, so a handler naming it -- or any ancestor --
# makes that access safe. Applying only the decode set here reported a
# `.get()` wrapped in `except (json.JSONDecodeError, AttributeError)`, which
# is the exact remediation this gate's own failure message prescribes.
_JSON_COVERING = frozenset({"AttributeError", "Exception", "BaseException"})

# The `errors=` policies that substitute rather than raise. `None` and
# `"strict"` are absent on purpose: both raise, and Python documents them as
# equivalent.
_SUBSTITUTING_ERRORS = frozenset(
    {"replace", "ignore", "surrogateescape", "backslashreplace", "xmlcharrefreplace", "namereplace"}
)


_JSON_PARSERS = frozenset({"loads", "load"})

# The types an `isinstance()` has to name for a JSON value to count as checked.
# `Mapping` and `MutableMapping` are here because `collections.abc` is how the
# rest of this repository spells "a mapping" in its own annotations; an
# attribute handler is compared by its final name, so `t.Mapping` matches too.
_MAPPING_TYPES = frozenset({"dict", "Mapping", "MutableMapping"})

# `# exception-handler-gap: WAIVED: <reason>` -- a reason is mandatory, the
# same way `gate_skill_audit_disclosure.py`'s own `WAIVED:` clause requires
# one. A bare marker is not a waiver and is not honoured.
_WAIVER_RE = re.compile(r"#\s*exception-handler-gap\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

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


def _covers(handled: set[str], covering: frozenset[str]) -> bool:
    """True iff `handled` catches the failure `covering` describes."""
    return bool(handled & covering)


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null` (a deletion, which adds nothing to grade).

    Anything other than `/dev/null` or git's own `b/`-prefixed post-image
    raises ``ScanError`` rather than being guessed at -- a git-quoted path
    (`"b/\\303\\251.py"`, which `core.quotePath` produces) and a
    `--no-prefix` diff both land here. Guessing wrong silently drops a file
    from grading, and a path this gate cannot resolve is one whose scope it
    cannot decide. The calling workflow always invokes plain `git diff`, so
    this is a wiring error, not a contributor's.
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


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into ``{post-image path: added line numbers}``.

    Only added lines are recorded. A removal is never a line this gate can
    grade -- there is no code left at it -- and an unchanged context line is
    pre-existing content another PR already owns.

    File headers are recognised only *outside* a hunk, which is the whole
    reason this tracks hunk state rather than matching prefixes line by line.
    Inside a hunk every line carries a one-character prefix, so an added line
    whose own content begins with `++ ` is emitted as `+++ ...` and a removed
    line beginning with `-- ` as `--- ...` -- indistinguishable, prefix-first,
    from the two header lines. A parser that took the header reading would
    rebind the current path to nonsense and silently drop the rest of that
    hunk from grading, which is a fail-open in the same family this gate
    exists to catch. `@@`, `diff --git ` and `index ` need no such guard:
    a hunk line always has its prefix, so none of them can begin a hunk line.
    """
    added: dict[str, set[int]] = {}
    path: str | None = None
    lineno = 0
    in_hunk = False
    saw_source_header = False
    for line in diff_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith("diff --git "):
            path = None
            in_hunk = False
            saw_source_header = False
            continue
        if not in_hunk and line.startswith("--- "):
            saw_source_header = True
            continue
        if not in_hunk and saw_source_header and line.startswith("+++ "):
            path = _diff_target_path(line[4:])
            saw_source_header = False
            continue
        if line.startswith("@@"):
            match = _HUNK_RE.match(line)
            if not match:
                raise ScanError(f"unparseable hunk header: {line!r}")
            lineno = int(match.group(1))
            in_hunk = True
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
    """Return the exception names one `except` clause catches, literally.

    A bare `except:` catches everything, so it reports `BaseException`. An
    attribute handler (`json.JSONDecodeError`) reports its final attribute
    name, which is what the covering sets compare against.

    Nothing is resolved. `except _READ_ERRORS:` reports `_READ_ERRORS` and is
    therefore reported as uncovered -- a known false positive, and the inline
    waiver is its disclosure path. Expanding module-level tuple constants was
    implemented and reverted: it matched by name with no scope awareness, so
    a rebinding, a local shadow, a parameter default or a `for` target of the
    same name silenced the rule entirely -- four fail-opens on exactly issue
    #682's defect F shape, traded for a false positive that occurs nowhere in
    the graded directories. Third time this gate has been offered
    name resolution and third time it has cost more than it bought.
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


def _handler_header_lines(handler: ast.ExceptHandler) -> set[int]:
    """Return the lines of one `except ...:` clause header, body excluded.

    These are trigger lines, not just decoration: narrowing `except ValueError`
    to `except OSError` creates a decode gap without touching the read itself,
    which is exactly issue #682's defect F.
    """
    end = handler.type.end_lineno if handler.type is not None else None
    return set(range(handler.lineno, (end if end is not None else handler.lineno) + 1))


def _handler_coverage(tree: ast.Module) -> tuple[dict[int, set[str]], dict[int, set[int]]]:
    """Return ``({id(Call): exception names guarding it}, {id(Call): the lines
    of the `except` clauses guarding it})``.

    Only a `try` *body* protects. A read
    inside an `except`, `else` or `finally` clause is not protected by that
    same statement's own handlers, which is exactly where a "read the file
    again to report a better error" fallback tends to live.

    Both rules are graded from the one walk. Computing it for decoded reads
    alone left `.get()` blind to handlers entirely, so a `.get()` wrapped in
    `except AttributeError` -- the fix this gate's own message prescribes --
    was still reported.

    `contextlib.suppress(...)` is deliberately not read as a handler. It was,
    briefly: matching the label `suppress` on any receiver silenced a
    same-named method on an unrelated object, while missing `suppress` under
    an import alias, a starred argument, or a tuple constant. One syntactic
    match, wrong in both directions, for a construct that appears nowhere in
    the graded directories. It is a known over-report instead, and the inline
    waiver is its disclosure path.

    The second return value is what makes a *narrowed handler* this diff's
    finding: the read line is untouched in that edit, so anchoring on it alone
    would let the defect through.
    """
    guarded: dict[int, set[str]] = {}
    handler_lines: dict[int, set[int]] = {}

    def walk(node: ast.AST, handled: frozenset[str], enclosing: frozenset[int]) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # A function *defined* inside a try body does not run inside it, so
            # its body loses the protection -- but its decorators and argument
            # defaults are evaluated right there and keep it.
            for decorator in node.decorator_list:
                walk(decorator, handled, enclosing)
            for default in [*node.args.defaults, *(d for d in node.args.kw_defaults if d)]:
                walk(default, handled, enclosing)
            for child in node.body:
                walk(child, frozenset(), frozenset())
            return
        if isinstance(node, ast.Lambda):
            for descendant in ast.iter_child_nodes(node):
                walk(descendant, frozenset(), frozenset())
            return
        if isinstance(node, ast.Try | ast.TryStar):
            names: set[str] = set()
            lines: set[int] = set()
            for handler in node.handlers:
                names |= _handler_names(handler)
                lines |= _handler_header_lines(handler)
            for child in node.body:
                walk(child, frozenset(handled | names), frozenset(enclosing | lines))
            for handler in node.handlers:
                for child in handler.body:
                    walk(child, handled, enclosing)
            for child in [*node.orelse, *node.finalbody]:
                walk(child, handled, enclosing)
            return
        if isinstance(node, ast.Call):
            guarded[id(node)] = set(handled)
            handler_lines[id(node)] = set(enclosing)
        for descendant in ast.iter_child_nodes(node):
            walk(descendant, handled, enclosing)

    for statement in tree.body:
        walk(statement, frozenset(), frozenset())
    return guarded, handler_lines


def _looks_like_a_mode(node: ast.expr) -> bool:
    """True for a string constant made only of file-mode characters.

    Needed because the attribute form's first positional argument is a mode
    for `Path.open` but a member name for `ZipFile.open` -- and a member name
    can easily contain an `r`, so a plain "is it a string" test would read it
    as a text read and report a binary one.
    """
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and set(node.value) <= set("rwxab+t")
    )


def _mode_is_text_read(mode: ast.expr | None, *, unknown_is_read: bool) -> bool:
    """Decide a file mode. A write-only mode raises `UnicodeEncodeError`, a
    different failure this gate was not measured against, and a binary mode
    decodes nothing at all -- neither is graded."""
    if mode is None:
        return True  # `open(path)` defaults to "r".
    if not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)):
        return unknown_is_read
    if "b" in mode.value:
        return False
    return "r" in mode.value or "+" in mode.value


def _text_read_kind(node: ast.Call) -> str | None:
    """Return the decoding-read shape `node` performs, or None.

    Two callables are graded, and the second is deliberately narrower than
    the first. Bare `open(...)` is the builtin, so a mode this gate cannot
    read statically is graded as a read -- guessing "probably a write" would
    be the fail-open direction. `<expr>.open(...)` is *not* necessarily a
    file: `webbrowser.open(url)`, `os.open(path, flags)` and
    `ZipFile(z).open(name)` all share the attribute name and none of them
    decodes text. So the attribute form is graded only when the call itself
    says it is a text file read -- no arguments (`Path(p).open()` defaults
    to "r"), an `encoding=`, or an explicit mode -- and an unreadable mode
    there is left alone rather than reported, since the receiver is already
    unknown and two unknowns do not make a finding.

    The attribute form is read against `pathlib.Path.open`'s signature, where
    the mode comes *first*. A module-level `<module>.open(filename, mode)` --
    `io.open`, `codecs.open` -- is therefore graded only when it also passes
    `encoding=` by keyword. Stated as the miss it is: both are unused in this
    repository today, and reading the second positional argument as a mode
    here as well would report `ZipFile(z).open(name, "r")`, a binary read.
    """
    func = node.func
    errors = next((k.value for k in node.keywords if k.arg == "errors"), None)
    if errors is None and len(node.args) >= 5:
        # `open(file, mode, buffering, encoding, errors)` -- the positional
        # spelling of the same argument.
        errors = node.args[4]
    if (
        isinstance(errors, ast.Constant)
        and isinstance(errors.value, str)
        and errors.value in _SUBSTITUTING_ERRORS
    ):
        # A substituting policy replaces undecodable bytes instead of raising,
        # so there is no UnicodeDecodeError to handle and demanding a handler
        # reports code that cannot fail. An allowlist, not "anything but
        # strict": that denylist took `errors=None` out of scope, and
        # `None` is documented as *equivalent* to strict, so it silenced a
        # real gap.
        return None

    if isinstance(func, ast.Attribute) and func.attr == "read_text":
        return "read_text"

    mode_kwarg: ast.expr | None = None
    for keyword in node.keywords:
        if keyword.arg == "mode":
            mode_kwarg = keyword.value

    if isinstance(func, ast.Name) and func.id == "open":
        # The builtin: `open(file, mode, ...)`, so the mode is positional #2,
        # and one this gate cannot read statically is graded rather than
        # assumed to be a write.
        builtin_mode = mode_kwarg if mode_kwarg is not None else (
            node.args[1] if len(node.args) >= 2 else None
        )
        return "open" if _mode_is_text_read(builtin_mode, unknown_is_read=True) else None

    if not (isinstance(func, ast.Attribute) and func.attr == "open"):
        return None

    positional_mode = node.args[0] if node.args and _looks_like_a_mode(node.args[0]) else None
    mode = mode_kwarg if mode_kwarg is not None else positional_mode
    if mode is not None:
        return "open" if _mode_is_text_read(mode, unknown_is_read=False) else None
    if not node.args:
        # No mode and no positional receiver-specific argument: `Path.open()`
        # defaults to "r". Keyword-only calls land here too, which is what
        # brings `p.open(newline="")` -- the csv-reading idiom -- and
        # `p.open(buffering=1)` into scope; requiring `encoding=` specifically
        # missed both.
        return "open"
    if any(keyword.arg == "encoding" for keyword in node.keywords):
        # `io.open(path, encoding="utf-8")`: a positional filename, but the
        # `encoding=` says plainly that this decodes.
        return "open"
    return None


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
    reads an *enclosing function's* JSON value is not graded. Sharing an
    arbitrary outer function's taint would also share every other function's,
    so the same variable name validated in one would silence it in all -- a
    fail-open in a gate whose whole subject is fail-open. Module scope is not
    an exception to that: inheriting it was implemented and reverted, for the
    reasons `_json_shape_gaps` records.
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


def _assigned_names(node: ast.AST) -> Iterator[tuple[str, ast.expr | None]]:
    """Yield ``(bound name, the expression bound to it)`` for one statement.

    Tuple unpacking is handled positionally, so `data, extra = json.loads(raw), 1`
    taints `data` and not `extra` -- reading the whole right-hand side as one
    value tainted neither.
    """
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                yield target.id, node.value
            elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for element, value in zip(target.elts, node.value.elts, strict=False):
                    if isinstance(element, ast.Name):
                        yield element.id, value
            elif isinstance(target, ast.Tuple):
                for element in target.elts:
                    if isinstance(element, ast.Name):
                        yield element.id, None
    elif isinstance(node, ast.AnnAssign | ast.NamedExpr):
        if isinstance(node.target, ast.Name):
            yield node.target.id, node.value
    elif isinstance(node, ast.For | ast.AsyncFor) and isinstance(node.target, ast.Name):
        yield node.target.id, None


def _isinstance_checks_mapping(node: ast.Call) -> str | None:
    """Return the name an `isinstance(name, dict-ish)` call validates, or None.

    The second argument has to actually name a mapping type. An earlier
    revision accepted any type, so the real double-encoded-JSON idiom --
    `if isinstance(data, str): data = json.loads(data)` -- silenced the
    `.get()` that followed it, while `json.loads` could still return a list.
    """
    if not (isinstance(node.func, ast.Name) and node.func.id == "isinstance" and len(node.args) == 2):
        return None
    subject = node.args[0]
    if isinstance(subject, ast.NamedExpr) and isinstance(subject.target, ast.Name):
        name = subject.target.id
    elif isinstance(subject, ast.Name):
        name = subject.id
    else:
        return None
    candidates = node.args[1].elts if isinstance(node.args[1], ast.Tuple) else [node.args[1]]
    if not candidates:
        return None
    for candidate in candidates:
        label = (
            candidate.id
            if isinstance(candidate, ast.Name)
            else candidate.attr
            if isinstance(candidate, ast.Attribute)
            else None
        )
        # EVERY member, not any: `isinstance(data, (dict, list))` is satisfied
        # by a list, and the `.get()` after it still raises. Accepting the
        # first mapping-shaped member was a fail-open, reproduced at runtime.
        if label not in _MAPPING_TYPES:
            return None
    return name


class _JsonGap(NamedTuple):
    """One `.get()` on an unvalidated JSON value, with the lines that make it
    this diff's finding.

    `trigger_from` is the line a guard would have to sit at or after to
    protect this access: the parse itself, which is always in the same scope.
    Anything edited between there and the access can create or destroy this
    finding, so anything edited there re-grades it -- without which, replacing
    `if not isinstance(data, dict)` with a different check leaves the `.get()`
    line untouched and the new defect ungraded.
    """

    call: ast.Call
    trigger_from: int


def _scope_taint(nodes: list[ast.AST]) -> tuple[dict[str, int], dict[str, int]]:
    """Return ``(tainted name -> parse line, validated name -> earliest check
    line)`` for one scope.

    A name assigned a parse *and*, anywhere in the same scope, something that
    is not one, is dropped rather than tainted. That is deliberately
    conservative and deliberately order-blind: an earlier revision compared
    line numbers instead, which made `try: CONFIG = json.loads(...) except:
    CONFIG = {}` -- the ordinary config-with-fallback -- come out differently
    depending on which branch was written first. A rule whose verdict depends
    on branch order is worse than one that misses; issue #682's own bar is
    that missing a real finding is preferable to reporting a false one.
    """
    tainted: dict[str, int] = {}
    validated: dict[str, int] = {}
    rebound: set[str] = set()
    for node in nodes:
        for name, value in _assigned_names(node):
            while isinstance(value, ast.NamedExpr):
                value = value.value
            if value is not None and _is_json_parse(value):
                # The parse expression's own line, not the statement's: they
                # are the same for every real shape, and only the expression
                # is statically known to carry one.
                tainted.setdefault(name, value.lineno)
            else:
                rebound.add(name)
        if isinstance(node, ast.Call):
            checked = _isinstance_checks_mapping(node)
            if checked is not None:
                validated[checked] = min(validated.get(checked, node.lineno), node.lineno)
    return {n: line for n, line in tainted.items() if n not in rebound}, validated


def _json_shape_gaps(tree: ast.Module) -> Iterator[_JsonGap]:
    """Yield every `.get()` call made on an unvalidated JSON result.

    Taint does not cross a scope boundary in either direction. Inheriting a
    module-level value into every function was tried and reverted: it needed
    parameter, local-rebinding and import shadowing to avoid false positives,
    each of those needed to know statement order, and order-sensitivity made
    the verdict depend on which branch of a `try/except` was written first --
    three reproduced defects across two rounds. `CONFIG = json.loads(...)` at
    module level, read through `CONFIG.get(...)` inside a function, is
    therefore a stated miss rather than a rule that is sometimes wrong in both
    directions.
    """
    for scope in _scopes(tree):
        nodes = list(_scope_body(scope))
        tainted, validated = _scope_taint(nodes)
        for node in nodes:
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "get":
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.NamedExpr):
                # `(data := json.loads(raw)).get(k)` -- the walrus is the
                # assignment and the receiver at once. Reading only the Name
                # and the bare-parse forms made this third spelling of one
                # program the only one that graded clean.
                receiver = receiver.value if _is_json_parse(receiver.value) else receiver.target
            if isinstance(receiver, ast.Name) and receiver.id in tainted:
                checked_at = validated.get(receiver.id)
                if checked_at is not None and checked_at <= node.lineno:
                    continue
                yield _JsonGap(node, tainted[receiver.id])
            elif _is_json_parse(receiver):
                # `json.loads(body).get(...)` -- the same defect with no
                # variable to taint, so no isinstance() can ever guard it, and
                # nothing between a parse and an access to re-grade either.
                yield _JsonGap(node, node.lineno)


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


class _Candidate(NamedTuple):
    """A finding plus what decides whether this diff owns it.

    `trigger` and `window` together are what make it *this diff's* finding: the
    offending expression, every other line an edit could use to create it (a
    narrowed `except` clause), and -- as an inclusive bound pair rather than a
    materialised set -- the region between a JSON parse and the access it
    feeds. Waiving is not on this record at all: a waiver is matched against
    `finding.line`, the line the gate prints.
    """

    finding: Finding
    trigger: frozenset[int]
    window: tuple[int, int] | None


def findings_for_source(path: str, source: str, added: set[int]) -> tuple[list[Finding], list[Finding]]:
    """Grade one file's source, returning ``(violations, honoured waivers)``.

    Only findings an added line could have created are returned, so a
    pre-existing gap another PR owns is never this diff's failure.
    """
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

    waived_lines = _waived_lines(source)
    guarded, handler_lines = _handler_coverage(tree)
    sorted_added = sorted(added)

    candidates: list[_Candidate] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _text_read_kind(node)
        if kind is None or _covers(guarded.get(id(node), set()), _DECODE_COVERING):
            continue
        expression = _span(node)
        anchor = node.func.end_lineno if isinstance(node.func, ast.Attribute) else None
        candidates.append(
            _Candidate(
                Finding(
                    path,
                    anchor if anchor is not None else node.lineno,
                    _DECODE_GAP,
                    f"{kind}(...) decodes text, but no enclosing try handles UnicodeDecodeError "
                    "(or an ancestor of it)",
                ),
                frozenset(expression | handler_lines.get(id(node), set())),
                None,
            )
        )
    for gap in _json_shape_gaps(tree):
        if _covers(guarded.get(id(gap.call), set()), _JSON_COVERING):
            continue
        expression = _span(gap.call)
        end = gap.call.end_lineno if gap.call.end_lineno is not None else gap.call.lineno
        anchor = gap.call.func.end_lineno if isinstance(gap.call.func, ast.Attribute) else None
        candidates.append(
            _Candidate(
                Finding(
                    path,
                    anchor if anchor is not None else gap.call.lineno,
                    _JSON_SHAPE_GAP,
                    ".get() on a json.loads result never checked with isinstance(); a valid "
                    'non-object payload ([], "x", 1, null) raises AttributeError',
                ),
                frozenset(expression),
                # The guard window is carried as a bound pair, not materialised
                # as a set: for a module-inherited value it spans a whole
                # function, and building one set per gap made a file of 800
                # gaps take 2.1 seconds where a bisect takes milliseconds.
                (min(gap.trigger_from, end), end),
            )
        )

    in_diff = [c for c in candidates if c.trigger & added or _touches(sorted_added, c.window)]
    # A waiver sits on the line the gate names in its own message, and waives
    # every finding reported there. That rule is the third attempt and the
    # first one that is simply predictable. Matching any line of a finding's
    # span let a waiver written for an inner argument silence the outer call
    # it sat inside; ordering overlapping findings by span length picked the
    # wrong one; ordering by AST depth picked a defensible one but could not
    # be explained to a contributor, spent a reason written about one finding
    # on another, and left a line carrying two findings impossible to waive at
    # all -- while printing that line as both honoured and rejected. "Put the
    # comment on the line the error names" has none of those properties.
    violations: list[Finding] = []
    waived: list[Finding] = []
    for candidate in in_diff:
        target = waived if candidate.finding.line in waived_lines else violations
        target.append(candidate.finding)
    return sorted(set(violations)), sorted(set(waived))


def _touches(sorted_added: list[int], window: tuple[int, int] | None) -> bool:
    """True iff any added line falls inside the inclusive `window`."""
    if window is None:
        return False
    low, high = window
    index = bisect.bisect_left(sorted_added, low)
    return index < len(sorted_added) and sorted_added[index] <= high


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
        if not in_scope(path):
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

#!/usr/bin/env python3
"""CI gate: a new or materially changed function body, added by this diff to
one of this repository's own checker scripts, must be exercised by a new or
changed test in the same diff.

Issue #1498 (filed from merge-retrospective issue #1492's repair 11).
Generalizes ``gitapex_gate_detection_logic_property_coverage.py`` (issue
#1178): that gate only grades three narrow AST trigger shapes (a regex call,
a path-resolution call, a string-comparison allowlist/denylist construct) and
only asks whether *some* pre-existing property test happens to already cover
the trigger's enclosing function -- a property test authored in any earlier
PR satisfies it. This gate grades *any* function body change in the same
in-scope directories, and its own coverage question is stricter and narrower
at once: not "is this function covered by some test somewhere," but "does
*this diff* itself add or change a test that covers it."

**The motivating gap (issue #1492's own repair 11).** Commit ``379c0fde``
fixed a real defect (a basename collision silently satisfying
``gitapex_check_skill_shape.py``'s own script-execution-intent check for an
unrelated file) but shipped with zero test changes, despite this
repository's own established defeat-test-disclosure convention (every
`tests/test_*.py` file in this repository states it, and
``gitapex_gate_detection_logic_property_coverage.py``'s own test suite
practices it). A second, independent fresh-context review pass caught the
gap; a follow-up commit (``3701af6d``) closed it with 3 regression tests.
Nothing in CI would have caught the first commit's own gap on its own: the
function `379cf0de` changed contains no regex/path-resolution/string-
comparison call, so ``gitapex_gate_detection_logic_property_coverage.py``
graded it clean, and no other gate asked whether the diff carried a
corresponding test change at all. This gate is that missing question.

Scope
-----
In-scope paths are any ``.py`` file directly inside ``skills/*/scripts/`` or
``.github/scripts/`` -- issue #1498's own proposed-gate text names exactly
these two path globs, with no ``gitapex_check_``/``gitapex_gate_`` filename
prefix restriction, unlike ``gitapex_gate_detection_logic_property_
coverage.py``'s own narrower scope. This mirrors ``gitapex_gate_exception_
handler_gaps.py``'s own broader, unprefixed precedent instead (that gate's
own ``_IN_SCOPE_RE`` likewise admits any ``.py`` name under its four
directories). ``[^/]+`` segments and ``re.fullmatch`` keep every alternative
from crossing a directory separator or matching a nested subdirectory (e.g.
``skills/*/scripts/shape_checks/*.py`` is out of scope) -- the same
non-recursive construction both sibling gates already use; widening either
gate to a recursive scan is a measurement to make deliberately, not assumed
here. ``hooks/*.py`` and ``evals/scripts/*.py`` are deliberately excluded
too: issue #1498's own text names only the two directories above, and
widening past its literal wording is left to a later, disclosed change
rather than assumed.

A file matching the in-scope pattern is excluded when its basename starts
with ``test_`` or equals ``conftest.py`` -- the same exclusion both sibling
gates apply, for the same reason: a test file has no test-coverage contract
of its own to satisfy.

Trigger
-------
Any ``FunctionDef``/``AsyncFunctionDef`` (including a nested one, at any
depth) whose own body -- not a nested function's -- contains at least one
line this diff adds. "Own body, not a nested function's" is the same
innermost-enclosing-range rule ``gitapex_gate_detection_logic_property_
coverage.py``'s own ``_enclosing_scope`` already applies: nested functions
get their own, narrower range (a property of Python's own grammar), so the
smallest range containing an added line is always the innermost function
truly touched, and a change reached only through a nested function's own
body attributes to that nested function alone, not its parent.

Unlike the parent gate, module-level code (a change outside any function)
is never graded here at all -- issue #1498's own text asks specifically
about "function body," not module scope, so a new module-level constant or
statement carries no obligation under this gate (it may still trigger
``gitapex_gate_detection_logic_property_coverage.py`` separately, on its own
narrower terms). A pure-deletion-only change to a function's body -- removed
lines with nothing added -- is not graded either, the same disclosed limit
``parse_added_lines`` already carries for both sibling gates: a removal has
no code left at it to grade.

Existing-coverage check
------------------------
For a source file at repo-relative path ``P`` with stem ``S`` (e.g.
``.github/scripts/gitapex_gate_foo.py`` -> ``S = "gitapex_gate_foo"``), the
two files this gate accepts as "a corresponding test" are
``tests/test_{S}.py`` and ``tests/test_{S}_properties.py`` -- the plain
behavioral-test and Hypothesis-properties-test naming precedents this
repository's own gate test suites already establish for the same stem.
Either one counts: issue #1498's own proposed-gate text asks for "a new or
changed test," not specifically a property test, so a plain ``def
test_foo(): ...`` in the non-properties file satisfies this gate exactly as
a ``@given``-decorated one does.

A touched function named ``F`` in source file with stem ``S`` is COVERED
iff, in at least one of the two test files above:

1. the file exists, can be read as UTF-8, and can be parsed as Python;
2. this same diff adds or changes at least one line inside that file (per
   this diff's own ``parse_added_lines`` output for that file's own path --
   a file this diff never touches at all contributes no coverage, which is
   exactly the shape issue #1492's own repair 11 needs caught: a
   pre-existing test that already mentioned the fixed function, but was
   never itself touched by the fixing commit, does not clear this gate);
   and
3. that added/changed line is itself one of the specific lines a
   ``test_``-named function's own body (pytest's own default collection
   prefix; this repository's own ``pyproject.toml`` sets no
   ``python_functions`` override) mentions ``F`` at -- a ``Name``/
   ``Attribute`` node whose final name equals ``F``, matched only in the
   function's own body, never its decorators or the rest of the file.
   Deliberately the *mentioning* line itself, not merely some added line
   anywhere inside the mentioning function's own range: the latter let a
   diff whose only change to the test file was unrelated to ``F`` -- but
   landed inside a function that happened to mention ``F`` on some other,
   untouched line -- silently clear coverage, confirmed live during
   review rather than hypothesised.

**Known misses, disclosed rather than found later** -- the same class of
heuristic limit ``gitapex_gate_detection_logic_property_coverage.py``'s own
"Existing-coverage check" section already discloses for its own, narrower
check:

* A same-named local variable, loop target, parameter, or nested ``def``
  inside a covering test function's own body reads as "mentions ``F``"
  exactly as a real call would -- a false clear.
* A test that exercises ``F`` only through an indirection (a helper it
  calls, which itself calls ``F``) never mentions ``F`` by name and is a
  false flag: reported uncovered even though it is exercised.
* Two functions sharing one name in the same source file (two classes' own
  same-named methods, for instance) are indistinguishable to this check,
  which resolves coverage by name alone, not by which specific function a
  test's author had in mind: a test covering one same-named function clears
  both. Confirmed live rather than hypothesised, and reachable two ways:
  within one file (this repository does not currently define two
  same-named functions in one in-scope file, so that half is latent) and
  *across* files, via ``_stem``/``_test_relative_paths``' own basename-only
  keying -- ``skills/drafting-issues/scripts/gitapex_check_acm_present.py``
  and ``skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_
  present.py`` already exist, already share several function names, and
  already resolve to the identical ``tests/test_gitapex_check_acm_
  present.py`` under this gate's own broader, unprefixed scope -- so this
  half is live now, not latent. Resolving to the true, lexically distinct
  definition either way needs the same name-resolution machinery
  ``gitapex_gate_exception_handler_gaps.py``'s own ``_handler_names``
  docstring records three separate attempts at, each reverted.
* A change that touches only a function's ``def`` line, a decorator line,
  or a multi-line parameter list still counts as touched: `_function_
  ranges` widens a decorated function's own range to start at its
  earliest decorator line (never merely `node.lineno`, which Python's own
  grammar sets to the `def` line, excluding every decorator above it), and
  a multi-line signature's own continuation lines already sit inside
  `lineno` through `end_lineno` with no widening needed. This is a
  deliberate widening past a literal reading of "body": a signature or
  decorator change is exactly the kind of change that most needs a test
  update, and Python's own grammar hands over no finer-grained range to
  distinguish it from one.

Waiver
------
``# function-body-test-coverage: WAIVED: <reason>`` -- a non-whitespace
reason is mandatory, matched via ``tokenize`` exactly like both sibling
gates' own waiver comments, so the marker is honoured only as a real comment
token. Unlike either sibling gate, which anchor a waiver to the single line
a trigger sits on, this gate's own finding unit is a whole function -- often
spanning a multi-line ``def`` signature no inline trailing comment can
attach to cleanly -- so a waiver is honoured anywhere within the touched
function's own lines, not only the exact line ``Finding.line`` reports.
This is a deliberate, disclosed deviation from the "put the comment exactly
where the error points" convention both sibling gates apply, justified by
the same generalization: a whole-function finding has no single natural
comment anchor the way a one-line call site does. "The touched function's
own lines" deliberately excludes any more deeply nested function's own
lines (``_own_lines``, the same innermost-attribution rule
``_touched_functions`` already applies per added line): a waiver comment
living inside a nested function's own body -- written for that nested
function, or predating it entirely -- must not silently clear an unrelated
finding on the *enclosing* function merely because a naive
``lineno``-through-``end_lineno`` span would have spanned over it too.

Exit codes
----------
0 clean, 1 violation found, 2 the scan could not be trusted -- identical
contract to both sibling gates (dimension 15 of
``skills/evaluating-deterministic-gate-quality/references/dimensions.md``,
"Fail-closed default on incomplete or malformed input"). ``parse_added_lines``
below is the same diff parser both sibling gates carry their own copy of
(see either one's own module docstring for the full incremental history of
its boundary checks -- issues #1184, #1193, and the two-independent-
adversarial-review bypass fix -- not repeated a third time here; the code
below is copied, not the several hundred lines of prose narrating how it got
that way).

Invocation shape
-----------------
Identical ``--root``/stdin-diff CLI shape to both sibling gates, wired via
``.gitapex/ssot.json``'s ``local_invocation``/``local_stdin`` pair:
``local_stdin`` is
``["uv", "run", "--frozen", "python3",
".github/scripts/gitapex_run_base_diff.py", "--", "*.py"]`` (issue #1345).

Usage::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_function_body_test_coverage.py

A bare pipe here masks `git diff`'s own exit status in a non-`pipefail`
shell (issue #1531): add `set -o pipefail` first, or check `git diff`'s
own exit code separately, if the caller must detect an upstream failure
rather than silently grading whatever partial diff reached stdin.

Both flags are load-bearing for the same reason they are in both sibling
gates: rename detection would hide a file newly promoted into a graded
directory behind a zero-added-line header, and ``core.quotePath`` renders a
non-ASCII path as an escaped string this gate cannot resolve (such a path
exits 2, fail-closed, rather than being guessed at).

Reads a unified diff on stdin; diagnostics and violations go to stderr. Run
via ``uv run`` (the pydantic import needs it) or via the pytest gate in
``tests/test_gitapex_gate_function_body_test_coverage_properties.py``.
"""

from __future__ import annotations

import argparse
import ast
import io
import pathlib
import re
import sys
import tokenize
from typing import NamedTuple

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Any `.py` file directly under `.github/scripts/` or `skills/*/scripts/` --
# no `gitapex_check_`/`gitapex_gate_` filename restriction, matching issue
# #1498's own proposed-gate text and `gitapex_gate_exception_handler_gaps.py`'s
# own broader precedent rather than `gitapex_gate_detection_logic_property_
# coverage.py`'s own narrower one. `[^/]+` segments and re.fullmatch (never
# re.match) keep every alternative from crossing a directory separator or
# matching a nested subdirectory.
_IN_SCOPE_RE = re.compile(r"skills/[^/]+/scripts/[^/]+\.py|\.github/scripts/[^/]+\.py")

_FUNCTION_BODY_GAP = "function-body-test-coverage-gap"

# `# function-body-test-coverage: WAIVED: <reason>` -- a reason is mandatory,
# the same "WAIVED: <reason>" vocabulary both sibling gates' own waiver
# comments require. A bare marker with no reason is not a waiver and is not
# honoured.
_WAIVER_RE = re.compile(r"#\s*function-body-test-coverage\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation: a touched function this diff reaches with no
    new or changed test in the same diff covering it."""

    path: str
    line: int
    rule: str
    message: str


def in_scope(path: str) -> bool:
    """Return True iff `path` is a checker script this gate grades.

    Test files are excluded everywhere: a test that feeds a gate malformed
    input, or a fixture co-located with its source, has no test-coverage
    contract of its own. See the module docstring's own "Scope" section.
    """
    if not _IN_SCOPE_RE.fullmatch(path):
        return False
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith("test_") or name == "conftest.py")


def _stem(path: str) -> str:
    """Return the source module stem for a diff-relative path, e.g.
    ".github/scripts/gitapex_gate_foo.py" -> "gitapex_gate_foo". Plain string
    manipulation on the diff-relative POSIX path -- `path` here is never
    resolved against a real filesystem."""
    return path.rsplit("/", 1)[-1].removesuffix(".py")


def _test_relative_paths(stem: str) -> tuple[str, str]:
    """The two files this gate accepts as "a corresponding test" for source
    module stem `stem`: the plain behavioral test and the Hypothesis
    properties test, the same two naming precedents this repository's own
    gate test suites already establish for the same stem. See the module
    docstring's own "Existing-coverage check" section for why either one
    counts."""
    return (f"tests/test_{stem}.py", f"tests/test_{stem}_properties.py")


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null` (a deletion, which adds nothing to grade).

    Identical to both sibling gates' own `_diff_target_path`: anything other
    than `/dev/null` or git's own `b/`-prefixed post-image raises
    `ScanError` rather than being guessed at.
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
    Identical to both sibling gates' own `_looks_like_real_header_pair`."""
    source = source_line[4:]
    target = target_line[4:]
    return (source == "/dev/null" or source.startswith("a/")) and (target == "/dev/null" or target.startswith("b/"))


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into ``{post-image path: added line numbers}``.

    Byte-for-byte the same parser both sibling gates carry their own copy
    of -- see either `gitapex_gate_detection_logic_property_coverage.py`'s
    or `gitapex_gate_exception_handler_gaps.py`'s own module docstring for
    the full incremental history of why each boundary check exists (issues
    #1184, #1193, and the two-independent-adversarial-review bypass fix),
    rather than repeating several hundred lines of that narrative a third
    time here. The *code* is copied verbatim (this is proven-correct,
    battle-tested parsing logic with real CI-reachable regressions behind
    each check); only the prose explaining how it got this way is not
    re-narrated, per this gate's own module docstring's "Exit codes"
    section.
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
    ) -> None:  # function-body-test-coverage: WAIVED: a private closure nested inside parse_added_lines, with no name accessible from outside this function to reference directly; its raise path is exercised through parse_added_lines' own over-declared-hunk-count regression test instead
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


class _FunctionRange(NamedTuple):
    """One `FunctionDef`/`AsyncFunctionDef`'s own line range, inclusive."""

    lineno: int
    end_lineno: int
    name: str


def _function_ranges(tree: ast.Module) -> list[_FunctionRange]:
    """Every function's own line range in `tree`, including nested ones.
    Nested functions get their own, narrower range, a property of Python's
    own grammar.

    A decorated function's range starts at its *earliest* decorator line,
    not merely `node.lineno` (the `def` line): `ast.FunctionDef.lineno`
    excludes decorator lines by construction, so without this widening a
    change touching only an added/changed decorator line would fall
    outside every function's own range and go entirely ungraded -- neither
    attributed to the function it decorates nor to any enclosing scope.
    Widening-only: `node.lineno` is still the lower bound whenever no
    decorator is present, so this can only ever pull a range's start
    earlier, never later.
    """
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno if node.end_lineno is not None else node.lineno
            start = node.lineno
            if node.decorator_list:
                start = min(start, min(decorator.lineno for decorator in node.decorator_list))
            ranges.append(_FunctionRange(start, end, node.name))
    return ranges


def _innermost_range(line: int, ranges: list[_FunctionRange]) -> _FunctionRange | None:
    """The smallest-span range in `ranges` containing `line`, or None if no
    range contains it. Nested functions get their own, narrower range,
    always fully contained within their parent's -- a property of Python's
    own grammar -- so the smallest containing range is always the
    innermost enclosing function."""
    containing = [r for r in ranges if r.lineno <= line <= r.end_lineno]
    if not containing:
        return None
    return min(containing, key=lambda r: r.end_lineno - r.lineno)


def _touched_functions(ranges: list[_FunctionRange], added: set[int]) -> list[_FunctionRange]:
    """Every function range in `ranges` whose own body -- not a nested
    function's -- contains at least one line in `added`.

    For each added line, `_innermost_range` finds the function truly
    touched, the same rule `gitapex_gate_detection_logic_property_
    coverage.py`'s own `_enclosing_scope` already applies for trigger
    attribution. Deduplicated by `(lineno, name)` so a function touched by
    several added lines is graded once.
    """
    touched: dict[tuple[int, str], _FunctionRange] = {}
    for line in added:
        innermost = _innermost_range(line, ranges)
        if innermost is None:
            continue
        touched[(innermost.lineno, innermost.name)] = innermost
    return sorted(touched.values())


def _own_lines(func: _FunctionRange, ranges: list[_FunctionRange]) -> set[int]:
    """Every line in `func`'s own range that does not also fall inside a
    more deeply nested function's own range -- the same innermost-
    attribution rule `_touched_functions` already applies per added line,
    computed here for every line in `func`'s own range instead.

    Used to scope a waiver comment to the function it was actually written
    for: without this, a waiver comment sitting inside a nested function's
    own body -- written for that nested function, or predating it entirely
    -- would silently clear an unrelated finding on the *enclosing*
    function too, since a naive `range(func.lineno, func.end_lineno + 1)`
    also spans every nested function's own body.
    """
    return {line for line in range(func.lineno, func.end_lineno + 1) if _innermost_range(line, ranges) == func}


def _mention_lines(func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> set[int]:
    """Every line number a `Name`/`Attribute` node whose final name equals
    `name` occupies within `func`'s own body -- only the body, not its
    decorators or argument defaults.

    Pinpoints exactly which lines genuinely correspond to a mention of
    `name`, rather than only reporting whether one exists anywhere in the
    function (a plain boolean would let a diff that touches *any* other
    line inside a covering-shaped function -- one that happens to mention
    `name` somewhere unrelated -- silently clear coverage; see
    `_diff_adds_a_covering_test`'s own docstring for why line-level
    precision, not function-level, is what closes that gap). A multi-line
    `Attribute` chain's own `end_lineno` is included too, matching
    `gitapex_gate_detection_logic_property_coverage.py`'s own `_span`
    convention for a multi-line trigger site.
    """
    lines: set[int] = set()
    for statement in func.body:
        for node in ast.walk(statement):
            if (isinstance(node, ast.Name) and node.id == name) or (
                isinstance(node, ast.Attribute) and node.attr == name
            ):
                end = node.end_lineno if node.end_lineno is not None else node.lineno
                lines.update(range(node.lineno, end + 1))
    return lines


def _test_tree(path: pathlib.Path) -> ast.Module | None:
    """Parse a candidate test file's AST. Returns None when the file does
    not exist, cannot be read, or cannot be parsed -- three conditions
    collapsed into one "contributes no coverage" verdict, the same way
    `gitapex_gate_detection_logic_property_coverage.py`'s own
    `_properties_tree` treats its own co-located properties file: the
    *source* file's own touched functions are still fully enumerable
    without this file, so the scan itself stays trustworthy."""
    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError):
        return None


def _diff_adds_a_covering_test(
    root: pathlib.Path, stem: str, function_name: str, added_by_path: dict[str, set[int]]
) -> bool:
    """True iff this same diff adds or changes a line, inside one of
    `stem`'s two corresponding test files, that falls on one of the exact
    lines a `test_`-named function's own body mentions `function_name` at.
    See the module docstring's own "Existing-coverage check" section for
    the exact 3-part condition this implements.

    Deliberately checked against `_mention_lines`' own specific line
    numbers, not merely "some added line anywhere inside the covering
    function's own range": the latter let a diff whose only change to a
    test file was an unrelated, unrelated-to-`function_name` edit inside a
    function that happened to mention `function_name` on some other,
    untouched line silently clear coverage -- confirmed live during
    review, not hypothesised. Requiring the touched line and the mentioning
    line to coincide closes that gap.
    """
    for relative in _test_relative_paths(stem):
        test_added = added_by_path.get(relative, set())
        if not test_added:
            continue
        tree = _test_tree(root / relative)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")):
                continue
            if test_added & _mention_lines(node, function_name):
                return True
    return False


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying an inline waiver comment.

    Read through `tokenize` rather than a regex over raw text so the marker
    is only honoured as a real comment. Identical to both sibling gates'
    own `_waived_lines`; the only caller runs `ast.parse` on this same
    source first and turns any failure into a `ScanError`, and CPython's
    own parser tokenizes what it parses -- so a source that reaches here has
    already been proved tokenizable.
    """
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


def findings_for_source(
    path: str,
    source: str,
    added: set[int],
    added_by_path: dict[str, set[int]],
    root: pathlib.Path,
) -> tuple[list[Finding], list[Finding]]:
    """Grade one file's source, returning ``(violations, honoured waivers)``.

    Only a function an added line actually reaches is graded, so a
    pre-existing gap another PR owns is never this diff's failure -- the
    same diff-scoping both sibling gates apply.
    """
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

    waived_lines = _waived_lines(source)
    ranges = _function_ranges(tree)
    stem = _stem(path)

    violations: list[Finding] = []
    waived: list[Finding] = []
    for func in _touched_functions(ranges, added):
        if _diff_adds_a_covering_test(root, stem, func.name, added_by_path):
            continue
        finding = Finding(
            path,
            func.lineno,
            _FUNCTION_BODY_GAP,
            f"function `{func.name}` has an added/changed body line reached by this diff, but the "
            f"same diff adds no new or changed test in tests/test_{stem}.py or "
            f"tests/test_{stem}_properties.py whose own body mentions `{func.name}` by name",
        )
        target = waived if (waived_lines & _own_lines(func, ranges)) else violations
        target.append(finding)
    return sorted(set(violations)), sorted(set(waived))


def find_violations(diff_text: str, root: pathlib.Path) -> tuple[list[Finding], list[Finding], int]:
    """Grade every in-scope file the diff adds lines to.

    Returns ``(violations, honoured waivers, files graded)``. Raises
    ``ScanError`` when a file named by the diff exists but cannot be read as
    UTF-8 or parsed. Mirrors both sibling gates' own `find_violations`.
    """
    violations: list[Finding] = []
    waived: list[Finding] = []
    graded = 0
    added_by_path = parse_added_lines(diff_text)
    for path, added in sorted(added_by_path.items()):
        if not in_scope(path):
            continue
        absolute = root / path
        try:
            # utf-8-sig, not utf-8: a BOM-carrying file that python3 executes
            # fine otherwise would otherwise fail this gate with a spurious
            # "cannot be parsed as Python" ScanError. Same reasoning both
            # sibling gates' own find_violations state.
            source = absolute.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            raise ScanError(f"{path}: named by the diff as added or modified, but missing from {root}") from None
        except (OSError, UnicodeDecodeError) as error:
            raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
        file_violations, file_waived = findings_for_source(path, source, added, added_by_path, root)
        violations.extend(file_violations)
        waived.extend(file_waived)
        graded += 1
    return violations, waived, graded


class GateFunctionBodyTestCoverageArgs(BaseModel):
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
        description="Check that a new or materially changed function body added by this diff to a "
        "skills/*/scripts/*.py or .github/scripts/*.py checker script has a new or changed test in "
        "the same diff covering it. Reads a unified diff on standard input."
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
        validated = GateFunctionBodyTestCoverageArgs(root=args.root)
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
        # reasoning both sibling gates' own main() gives for this branch.
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
            f"\n{len(violations)} new or materially changed function body/bodies reached by this diff "
            "have no new or changed test in the same diff covering them (issue #1498). Add or change "
            "a test in tests/test_<source-stem>.py or tests/test_<source-stem>_properties.py whose own "
            "body calls or references the function by name. When a human has already judged the "
            "change covered some other way, disclose it inline with "
            "'# function-body-test-coverage: WAIVED: <reason>' anywhere in the function's own body.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

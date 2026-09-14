#!/usr/bin/env python3
"""CI gate: a new or materially changed regex alternation branch, module-level
dict entry, or unconditionally-emitted literal, added by this diff to one of
this repository's own checker scripts, must actually be caught -- not merely
mentioned -- by this same diff's own paired test: removing the element and
re-running the paired test file(s) as a real ``pytest`` subprocess must make
at least one of them fail. A paired test that still passes clean against the
mutated source is a *vacuous* defeat-test: it claims to pin the element down
but never actually exercises it.

Issue #1799 (six consolidated rows across #1733, #1734, #1735, #1736, #1990,
#1991). Every prior gate in this repository grades a diff by static AST
inspection alone -- "does a covering test mention this name/function" -- which
a vacuous assertion (a type check, a non-emptiness check, an unrelated
assertion in the same test function) satisfies without ever actually
exercising the element it claims to cover.
``gitapex_gate_detection_logic_property_coverage.py`` (issue #1178) and
``gitapex_gate_function_body_test_coverage.py`` (issue #1498) both ask "is
there a covering test," never "does the covering test actually fail if the
covered element is wrong" -- this gate is the first in this repository to
actually run a mutated copy of the source against its own paired tests,
mirroring the temp-overwrite-then-restore technique real mutation-testing
tools (``mutmut``, ``cosmic-ray``) use, rather than only reasoning about the
AST.

**The motivating gap, twice.** PR #1715's own Step 8 Round 3 manually
performed exactly this mutation-and-rerun check by hand against a regex
alternation branch and found it vacuous (#1733/#1734/#1735/#1736's own
repeated recurrence of the same gap). Retro #1985's own repair 1 (#1990) and
repair 3 (#1991) then found the identical vacuous-coverage shape against a
module-level dict constant entry and a generator's unconditionally emitted
list literal, respectively -- issue #1799's own umbrella widens the element
set from "a regex branch" to "any of these three AST shapes."

Scope
-----
Union of ``gitapex_gate_function_body_test_coverage.py``'s own
``skills/*/scripts/*.py`` / ``.github/scripts/*.py`` scope and
``gitapex_gate_detection_logic_property_coverage.py``'s own ``hooks/`` scope,
but unprefixed (matching the function-body gate's own broader precedent, not
the detection-logic gate's narrower ``gitapex_check_``/``gitapex_gate_``
prefix restriction) -- issue #1799's own #1990/#1991 rows are both in
``hooks/``, which the narrower scope would not have reached either.
``[^/]+`` segments and ``re.fullmatch`` keep every alternative from crossing a
directory separator or matching a nested subdirectory, matching both sibling
gates' own construction. A file matching the in-scope pattern is excluded
when its basename starts with ``test_`` or equals ``conftest.py``, the same
exclusion both sibling gates apply.

Element categories graded
--------------------------
Issue #1799's own "any element a test's own docstring or PR description
claims to cover," operationalized mechanically rather than by parsing
natural-language claims (see "Why not parse docstrings" below):

1. **Regex alternation branch.** A ``|``-joined top-level alternative inside
   a string literal argument to ``re.compile(...)``/``re.match(...)``/
   ``re.search(...)``/``re.fullmatch(...)`` -- the receiver for ``.compile``
   resolved through this file's own ``import re`` statements exactly like
   ``gitapex_gate_detection_logic_property_coverage.py``'s own
   ``_re_module_names``, and ``.match``/``.search``/``.fullmatch`` matched
   receiver-agnostically on any receiver, exactly like that gate's own
   ``_regex_trigger`` -- reused verbatim rather than re-derived. Only a call
   whose first positional argument is itself a plain string literal (no
   implicit string concatenation, no f-string) is graded: that argument is
   the pattern text this category mutates. Splitting happens on the raw
   *source* text of that literal (not the ``ast``-evaluated string value),
   respecting byte-for-byte what a raw string (``r"..."``) feeds directly to
   ``re``: a ``|`` inside ``(...)`` (paren-depth tracked) or ``[...]``
   (character-class tracked, entered on ``[`` and exited on the next ``]``,
   a simplification that does not special-case a class-leading ``]``/``^]``)
   is not a top-level alternative, and a ``|`` immediately after an unescaped
   backslash (a literal backslash byte, consuming the following byte as
   escaped regardless of what it is) is not either. A pattern with fewer than two
   top-level alternatives has nothing to remove and is not graded.

2. **Module-level dict/mapping-literal entry.** A key of an ``ast.Dict``
   assigned to a module-level ``ast.Name`` target (``CONST = {...}``, this
   repository's own pervasive constant-table idiom, e.g.
   ``REVIEW_PERSONA_PERMISSION``). Every entry is graded regardless of its
   own value's shape (a plain literal, a tuple, a nested dict) -- the element
   under test is the whole key/value pair, and the mutation is its removal.
   A dict carrying a ``**``-unpacking entry (a ``None`` key) is skipped
   entirely, narrow scope disclosed rather than handled.

3. **Unconditionally emitted literal.** A ``str``/``int``/``float``/``bool``
   ``ast.Constant`` that is either (a) a direct element of a
   ``List``/``Tuple``/``Set`` display, or (b) the value half of a key/value
   pair in an ``ast.Dict`` display that is *not* already the module-level
   ``CONST = {...}`` shape category 2 owns -- in both cases, only when the
   display itself is built directly inside a function body with no
   enclosing ``If``/``Try``/``For``/``AsyncFor``/``While`` between the
   display and that function (an unconditionally-executed straight-line
   emission, the same shape issue #1799's own #1991 row describes: "the
   generator appends both literals in one unconditional list construction").
   This category is necessarily the least mechanically crisp of the three
   (issue #1799's own #1991 row describes it by example, not by a closed
   grammar) -- narrowed deliberately, not overclaimed:

   **Known misses, disclosed rather than found later.**

   * A keyword argument's own value (``some_call(hidden=True)``) is not
     graded -- only a ``List``/``Tuple``/``Set`` element or a ``Dict``
     entry's value is, per the narrow shape above.
   * A collection built incrementally (``tags = []`` then repeated
     ``tags.append("hidden")`` calls) is not graded either -- only a
     literal element written directly inside one display's own brackets
     (``return ["hidden", "archived"]``) is, since that is the only shape
     with a single AST node this gate can locate and splice.
   * Implicit string concatenation (``"a" "b"``) and f-strings are not
     graded under category 1 at all -- only a single, plain string-literal
     pattern argument is.
   * A ``None`` value, a ``bytes`` literal, or a non-``Constant`` expression
     (a nested container, a call, a name reference) is never graded under
     category 3 -- only the four scalar ``Constant`` types listed above are.
   * A display nested inside a ``with`` block still counts as unconditional
     -- only ``If``/``Try``/``For``/``AsyncFor``/``While`` are treated as a
     guard, matching this category's own literal wording.
   * A display sitting directly in a class body (a class attribute, not
     inside any method) has no enclosing function at all and is never
     graded under category 3.

Why not parse docstrings
-------------------------
Issue #1799's own prose names "a test's own docstring or PR description" as
what claims coverage, but a natural-language claim is not a machine-checkable
input -- the same reason ``gitapex_gate_function_body_test_coverage.py``'s
own docstring gives for checking "does this diff add a covering test" by AST
identifier presence rather than by reading English. Operationalized instead
as: grade every category 1-3 element this diff newly adds or changes inside
an in-scope source file, paired against whichever of ``tests/test_{stem}.py``
/ ``tests/test_{stem}_properties.py`` this *same* diff also adds or changes a
line in (``_stem``/``_test_relative_paths``, copied verbatim from
``gitapex_gate_function_body_test_coverage.py``) -- reusing that gate's own
"this same diff must touch the test file too" scoping so a pre-existing,
untouched test can never silently satisfy this gate. A source element with no
diff-touched paired test file at all is not graded (nothing to
mutation-test against) -- a disclosed scope limit, not fixed here.

Mutation mechanism
-------------------
For each graded element, this gate locates its exact **byte** range in the
source file: ``ast`` reports ``col_offset``/``end_col_offset`` as UTF-8 byte
offsets, not character offsets (confirmed directly -- a non-ASCII character
earlier on the same line shifts them past where a character-index slice
would land), so every span here is computed and spliced against the file's
own UTF-8-encoded bytes, never against a decoded ``str`` index. A leading
UTF-8 BOM (``utf-8-sig``) is split off before any offset math and re-attached
on write, so a BOM-carrying file's real content offsets are unaffected by it.

Removing one element from a comma- or ``|``-separated sequence of ``N``
siblings (``_removal_span_for_item``) removes that element's own span plus
one adjoining separator -- the one *before* it when it is last, the one
*after* it otherwise -- so the remaining sequence stays syntactically valid
with no dangling separator; removing the sole element of a one-item sequence
leaves an empty literal (``{}``, a pattern with no alternatives, exact same
technique), also valid.

The mutated bytes are written over the on-disk source file for the duration
of one ``pytest`` subprocess invocation scoped to exactly the paired test
file(s) this diff itself touches (see "Why not parse docstrings" above), then
the original bytes are restored in a ``finally`` block regardless of outcome
-- mirroring the temp-overwrite-then-restore technique real mutation-testing
tools (``mutmut``, ``cosmic-ray``) use. The original bytes are read into
memory once, before the first mutation of that file, and every restore comes
from that same in-memory copy -- never by re-reading the file from disk after
a prior mutation -- so an interrupted restore can never let a later
mutation's restore step re-save an already-mutated copy as if it were the
original.

If the paired suite still exits 0 (every test passed) against the mutated
source, that element is a ``defeat-test-mutation-gap`` finding: its paired
test claims to cover it but does not actually fail when it is gone. A
non-zero, non-one exit code (a collection error, an internal pytest error, a
usage error, "no tests were collected" at all) means the run itself could not
be trusted and raises :class:`ScanError` rather than being read either way --
see "Exit codes" below.

Invocation shape, runtime/CI cost disclosed rather than hidden
-----------------------------------------------------------------
Unlike either sibling gate (pure AST inspection, no subprocess at all), this
gate spawns one real ``pytest`` subprocess per graded element -- its own CI
job carries a generous timeout for exactly that reason, and this cost is
stated here plainly rather than solved by artificially capping the element
count. Each subprocess pytest invocation runs as
``[sys.executable, "-m", "pytest", "--no-cov", "-n0", "-q", "-x", ...paired
test paths]`` against a ``PYTHONPATH`` env var pointing at the graded source
file's own containing directory (so a bare ``import <module>`` in the paired
test resolves correctly regardless of whether the invoking process's own
``--root`` carries a real ``pyproject.toml`` ``pythonpath`` entry for that
directory -- load-bearing for this gate's own regression tests, which grade
synthetic fixture trees with no such file) -- ``-n0`` overrides this
repository's own ``pyproject.toml`` ``addopts`` (``-n auto``, pytest-xdist),
confirmed live: passing ``-p no:xdist`` instead, rather than overriding the
worker count, makes the still-addopts-injected ``-n auto`` flag itself
unrecognised and fails every invocation with a usage error. ``-x`` stops at
the first failure, sufficient since only "did at least one paired test fail"
is asked. ``--no-cov`` disables this repository's own coverage plugin
wiring for these short-lived, single-file runs.

Reused verbatim from sibling gates
------------------------------------
``parse_added_lines`` (and its ``_diff_target_path``/
``_looks_like_real_header_pair``/``_HUNK_RE`` machinery) is copied
byte-for-byte from ``gitapex_gate_function_body_test_coverage.py`` -- see
either sibling gate's own module docstring for the full incremental history
of why each boundary check exists (issues #1184, #1193, and the
two-independent-adversarial-review bypass fix), not re-narrated a third time
here. ``_re_module_names`` is copied verbatim from
``gitapex_gate_detection_logic_property_coverage.py``. ``_stem`` and
``_test_relative_paths`` are copied verbatim from
``gitapex_gate_function_body_test_coverage.py``.

Waiver
------
``# defeat-test-mutation-coverage: WAIVED: <reason>`` -- a non-whitespace
reason is mandatory, detected via ``tokenize`` exactly like both sibling
gates' own ``_WAIVER_RE``/``_waived_lines``, so a waiver string quoted inside
this gate's own docstring is never itself honoured as a real waiver. Honoured
on the exact line ``Finding.line`` reports, the same "put the comment where
the error points" convention
``gitapex_gate_detection_logic_property_coverage.py`` applies.

Exit codes
----------
0 clean, 1 a vacuous-coverage finding, 2 the scan could not be trusted
(malformed diff, an in-scope or paired-test file that cannot be
read/parsed, a ``--root`` that is not a directory, or a subprocess ``pytest``
invocation that itself errors for a reason other than "tests ran and
passed/failed" -- e.g. a collection error) -- the same fail-closed contract
both sibling gates already state, dimension 15 of
``skills/evaluating-deterministic-gate-quality/references/dimensions.md``.

Known, disclosed non-goals
----------------------------
* **"The suite" is scoped to the paired co-located test file(s) only**,
  never the full repository test suite. Issue #1799's own #1991 row states
  the residual risk directly: "running only the file's own tests would miss
  a cross-file assertion, and running everything is slow." This gate accepts
  the narrower, fast scope rather than resolving it.
* **Emit-only spelling assertions are out of scope for this mechanism.**
  Issue #1799's own body states this directly: "an assertion that compares
  only an emitted spelling is not caught by a remove-and-confirm-failure
  pass, because a mutation that changes the emitted string does fail it.
  Catching that one needs a parse assertion beside the spelling assertion...
  which is a different check from mutation testing." Not attempted here.
* **Only the three element categories issue #1799's own six rows evidence
  directly are covered.** A vacuous test defeating some other shape of
  production logic (a conditional branch with no regex/dict/literal shape at
  all) is not covered and not claimed to be.

Reads a unified diff on stdin; diagnostics and violations go to stderr. Run
via ``uv run`` (the pydantic import needs it) or via the pytest gate in
``tests/test_gitapex_gate_defeat_test_mutation_coverage.py``.
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tokenize
from typing import NamedTuple

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Union of both sibling gates' own in-scope directories, unprefixed --
# matching gitapex_gate_function_body_test_coverage.py's own broader
# precedent. See the module docstring's own "Scope" section.
_IN_SCOPE_RE = re.compile(r"skills/[^/]+/scripts/[^/]+\.py|\.github/scripts/[^/]+\.py|hooks/[^/]+\.py")

_MUTATION_GAP = "defeat-test-mutation-gap"

_REGEX_ALTERNATION = "regex-alternation"
_DICT_ENTRY = "dict-entry"
_LITERAL_ELEMENT = "literal-element"

# `# defeat-test-mutation-coverage: WAIVED: <reason>` -- a reason is
# mandatory, the same "WAIVED: <reason>" vocabulary both sibling gates'
# own waiver comments require.
_WAIVER_RE = re.compile(r"#\s*defeat-test-mutation-coverage\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# Category 1: resolved through this file's own `import re` statements,
# copied verbatim from gitapex_gate_detection_logic_property_coverage.py's
# own `_re_module_names`/`_regex_trigger`.
_RE_MODULE = "re"
_REGEX_RECEIVER_AGNOSTIC_ATTRS = frozenset({"match", "search", "fullmatch"})

# Category 3: only these four scalar Constant types are graded -- see the
# module docstring's own "Known misses" section.
_SUPPORTED_LITERAL_TYPES = (str, int, float, bool)

# Category 3: the AST node types that make a display's own construction
# conditional, disqualifying it from grading -- see the module docstring's
# own category-3 paragraph.
_GUARD_NODE_TYPES: tuple[type[ast.AST], ...] = (ast.If, ast.Try, ast.For, ast.AsyncFor, ast.While)
if hasattr(ast, "TryStar"):
    _GUARD_NODE_TYPES = (*_GUARD_NODE_TYPES, ast.TryStar)

_PYTEST_TIMEOUT_SECONDS = 120

_UTF8_BOM = b"\xef\xbb\xbf"

_STRING_TOKEN_RE = re.compile(rb"^([A-Za-z]*)('''|\"\"\"|'|\")")


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation: an element this diff newly adds or changes
    whose removal leaves its own paired test file(s) still passing clean."""

    path: str
    line: int
    rule: str
    message: str


def in_scope(path: str) -> bool:
    """Return True iff `path` is a checker script this gate grades. See the
    module docstring's own "Scope" section."""
    if not _IN_SCOPE_RE.fullmatch(path):
        return False
    name = path.rsplit("/", 1)[-1]
    return not (name.startswith("test_") or name == "conftest.py")


def _stem(path: str) -> str:
    """Return the source module stem for a diff-relative path. Copied
    verbatim from gitapex_gate_function_body_test_coverage.py's own
    `_stem`."""
    return path.rsplit("/", 1)[-1].removesuffix(".py")


def _test_relative_paths(stem: str) -> tuple[str, str]:
    """The two files this gate accepts as "a corresponding test" for source
    module stem `stem`. Copied verbatim from
    gitapex_gate_function_body_test_coverage.py's own
    `_test_relative_paths`."""
    return (f"tests/test_{stem}.py", f"tests/test_{stem}_properties.py")


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null`. Copied verbatim from both sibling gates' own
    `_diff_target_path`."""
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
    `--- `/`+++ ` header pair always has. Copied verbatim from both sibling
    gates' own `_looks_like_real_header_pair`."""
    source = source_line[4:]
    target = target_line[4:]
    return (source == "/dev/null" or source.startswith("a/")) and (target == "/dev/null" or target.startswith("b/"))


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into ``{post-image path: added line numbers}``.

    Byte-for-byte the same parser both sibling gates carry their own copy
    of -- see either one's own module docstring for the full incremental
    history of why each boundary check exists (issues #1184, #1193, and the
    two-independent-adversarial-review bypass fix), not re-narrated a third
    time here.
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


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying an inline waiver comment. Read through
    `tokenize` rather than a regex over raw text, matching both sibling
    gates' own `_waived_lines`."""
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


def _span(node: ast.expr) -> set[int]:
    """Every source line `node` occupies -- an added line anywhere in this
    span brings the element into this diff's scope, matching
    gitapex_gate_detection_logic_property_coverage.py's own `_span`."""
    end = node.end_lineno if node.end_lineno is not None else node.lineno
    return set(range(node.lineno, end + 1))


def _split_bom(data: bytes) -> tuple[bytes, bytes]:
    """Split a leading UTF-8 BOM off `data`, returning `(bom, body)`. Every
    byte-offset computed by this gate is relative to `body`, never `data`,
    so a BOM-carrying file's real content offsets are unaffected by it."""
    if data.startswith(_UTF8_BOM):
        return data[:3], data[3:]
    return b"", data


def _line_byte_starts(body: bytes) -> list[int]:
    """`result[lineno - 1]` is the absolute byte offset where physical line
    `lineno` (1-indexed, matching `ast` node `lineno`) begins in `body`."""
    starts = [0]
    offset = 0
    while True:
        index = body.find(b"\n", offset)
        if index == -1:
            break
        offset = index + 1
        starts.append(offset)
    return starts


def _node_byte_span(node: ast.expr, line_starts: list[int]) -> tuple[int, int]:
    """The `(start, end)` absolute byte span `node` occupies in `body`, per
    `ast`'s own UTF-8-byte-offset `col_offset`/`end_col_offset` convention
    -- see the module docstring's own "Mutation mechanism" section for why
    this is a byte offset, confirmed directly, not a character index."""
    start = line_starts[node.lineno - 1] + node.col_offset
    end_lineno = node.end_lineno if node.end_lineno is not None else node.lineno
    end_col = node.end_col_offset if node.end_col_offset is not None else node.col_offset
    end = line_starts[end_lineno - 1] + end_col
    return start, end


def _removal_span_for_item(item_spans: list[tuple[int, int]], index: int) -> tuple[int, int]:
    """Given the `(start, end)` byte spans of every item in a comma- or
    `|`-separated sequence of `N >= 1` siblings, return the byte span to
    delete to remove item `index` alone while leaving the remaining items
    validly joined: the item's own span plus one adjoining separator -- the
    one before it when it is the last item (so removing the last item
    consumes the separator that used to precede it, not a nonexistent one
    that used to follow it), the one after it otherwise. Removing the sole
    item of a one-item sequence deletes just that item's own span, leaving
    an empty container/alternation-less literal -- still syntactically
    valid Python/regex. See the module docstring's own "Mutation mechanism"
    section."""
    if len(item_spans) == 1:
        return item_spans[0]
    if index < len(item_spans) - 1:
        return item_spans[index][0], item_spans[index + 1][0]
    return item_spans[index - 1][1], item_spans[index][1]


# --- Category 1: regex alternation branch -----------------------------------


def _re_module_names(tree: ast.Module) -> frozenset[str]:
    """Every bare name an `import re` in `tree` binds to the `re` module.
    Copied verbatim from gitapex_gate_detection_logic_property_coverage.py's
    own `_re_module_names`."""
    names = {_RE_MODULE}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _RE_MODULE:
                    names.add(alias.asname or alias.name)
    return frozenset(names)


def _regex_pattern_literal(node: ast.Call, re_module_names: frozenset[str]) -> ast.Constant | None:
    """Return the pattern-argument `Constant` node iff `node` is a
    `re.compile(...)`/`re.match(...)`/`re.search(...)`/`re.fullmatch(...)`
    call (the `.compile` receiver resolved through `re_module_names`;
    `.match`/`.search`/`.fullmatch` receiver-agnostic on any receiver,
    matching `gitapex_gate_detection_logic_property_coverage.py`'s own
    `_regex_trigger`) whose first positional argument is a plain string
    literal. None for every other call shape, including a `.compile`/
    `.match`/`.search`/`.fullmatch` call whose first argument is not itself
    a string `Constant` (an f-string, a name, a concatenation)."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr == "compile":
        if not (isinstance(func.value, ast.Name) and func.value.id in re_module_names):
            return None
    elif func.attr not in _REGEX_RECEIVER_AGNOSTIC_ATTRS:
        return None
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first
    return None


def _string_literal_content_span(raw: bytes) -> tuple[int, int]:
    """Given the raw source bytes of a string literal token (e.g.
    `b'r"a|b"'`), return the `(start, end)` byte offsets, within `raw`, of
    the pattern content between the quote delimiters (any prefix and the
    quotes themselves excluded). Raises `ValueError` for anything that is
    not a single, self-contained string literal token -- an f-string (the
    regex prefix match itself already excludes it, since `ast.Constant`
    never holds an f-string's runtime value as a plain string), or
    **implicit string concatenation** (`"a|b" "c|d"`): `ast.Constant`
    merges adjacent literals into one node whose `col_offset`/
    `end_col_offset` span *both* tokens and the whitespace between them,
    which the quote-stripping regex below cannot tell apart from a single
    literal by inspecting only its own start and end -- confirmed live,
    not merely a theoretical risk: an earlier version of this function
    used only that regex and silently mis-spliced across the token
    boundary. `tokenize` is the actual ground truth for "is this one
    token": `raw` is rejected unless tokenizing it yields exactly one
    `STRING` token whose own text is `raw` in full."""
    match = _STRING_TOKEN_RE.match(raw)
    if match is None:
        raise ValueError(f"not a recognisable string literal token: {raw!r}")
    quote = match.group(2)
    start = match.end()
    end = len(raw) - len(quote)
    if end < start:
        raise ValueError(f"malformed string literal token: {raw!r}")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"string literal token is not valid UTF-8: {raw!r}") from error
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(decoded).readline))
    except (tokenize.TokenError, SyntaxError) as error:
        raise ValueError(f"could not tokenize string literal token: {raw!r}: {error}") from error
    string_tokens = [token for token in tokens if token.type == tokenize.STRING]
    if len(string_tokens) != 1 or string_tokens[0].string != decoded:
        raise ValueError(f"not a single self-contained string literal token (implicit concatenation?): {raw!r}")
    return start, end


def _top_level_pipe_positions(content: bytes) -> list[int]:
    """Every byte offset, within `content`, of a top-level `|` -- at
    paren-depth 0, outside a `[...]` character class, and not immediately
    preceded by an unescaped `\\`. See the module docstring's own
    "Element categories graded" section, category 1."""
    positions: list[int] = []
    paren_depth = 0
    in_class = False
    index = 0
    length = len(content)
    while index < length:
        byte = content[index]
        if byte == 0x5C:  # backslash: the next byte is escaped, whatever it is
            index += 2
            continue
        if in_class:
            if byte == 0x5D:  # ]
                in_class = False
        elif byte == 0x28:  # (
            paren_depth += 1
        elif byte == 0x29:  # )
            paren_depth = max(0, paren_depth - 1)
        elif byte == 0x5B:  # [
            in_class = True
        elif byte == 0x7C and paren_depth == 0:  # |
            positions.append(index)
        index += 1
    return positions


def _alternative_spans(content: bytes, pipe_positions: list[int]) -> list[tuple[int, int]]:
    """The `(start, end)` byte spans, within `content`, of every alternative
    delimited by `pipe_positions` (each span excludes the `|` bytes
    themselves)."""
    spans: list[tuple[int, int]] = []
    start = 0
    for position in pipe_positions:
        spans.append((start, position))
        start = position + 1
    spans.append((start, len(content)))
    return spans


def _regex_alternation_elements(
    tree: ast.Module, body: bytes, line_starts: list[int], added: set[int]
) -> list[tuple[int, str, str, tuple[int, int]]]:
    """Every category-1 graded element: `(line, category, message,
    removal_span)` for each top-level alternative of a regex pattern this
    diff newly adds or changes."""
    re_module_names = _re_module_names(tree)
    elements: list[tuple[int, str, str, tuple[int, int]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        literal = _regex_pattern_literal(node, re_module_names)
        if literal is None:
            continue
        if not (_span(node) & added):
            continue
        literal_start, literal_end = _node_byte_span(literal, line_starts)
        raw = body[literal_start:literal_end]
        try:
            content_start, content_end = _string_literal_content_span(raw)
        except ValueError:
            continue
        content = raw[content_start:content_end]
        pipe_positions = _top_level_pipe_positions(content)
        if not pipe_positions:
            continue
        alt_spans = _alternative_spans(content, pipe_positions)
        for index, (alt_start, alt_end) in enumerate(alt_spans):
            removal_content_span = _removal_span_for_item(alt_spans, index)
            removal_span = (
                literal_start + content_start + removal_content_span[0],
                literal_start + content_start + removal_content_span[1],
            )
            alt_text = content[alt_start:alt_end].decode("utf-8", errors="replace")
            pattern_text = content.decode("utf-8", errors="replace")
            elements.append(
                (
                    literal.lineno,
                    _REGEX_ALTERNATION,
                    f"regex alternation branch {alt_text!r} (of {len(alt_spans)}) in pattern {pattern_text!r}",
                    removal_span,
                )
            )
    return elements


# --- Category 2: module-level dict/mapping-literal entry --------------------


def _module_level_dict_assigns(tree: ast.Module) -> list[tuple[str, ast.Dict]]:
    """Every `NAME = {...}` assignment directly in the module body -- the
    category-2 shape, and the set category 3 must not double-grade."""
    result: list[tuple[str, ast.Dict]] = []
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Dict)
        ):
            result.append((node.targets[0].id, node.value))
    return result


def _dict_entry_elements(
    tree: ast.Module, body: bytes, line_starts: list[int], added: set[int]
) -> list[tuple[int, str, str, tuple[int, int]]]:
    """Every category-2 graded element: `(line, category, message,
    removal_span)` for each entry of a module-level `CONST = {...}` dict
    this diff newly adds or changes."""
    elements: list[tuple[int, str, str, tuple[int, int]]] = []
    for name, dict_node in _module_level_dict_assigns(tree):
        values = dict_node.values
        if not dict_node.keys or any(key is None for key in dict_node.keys):
            continue
        # `dict_node.keys` is `list[ast.expr | None]` (`None` marks a
        # `**`-unpacking entry) -- the guard above already rejects any dict
        # carrying one, so every element here is a real key; this
        # re-binding narrows the type for mypy without re-checking anything
        # the guard didn't already establish.
        keys: list[ast.expr] = [key for key in dict_node.keys if key is not None]
        entry_spans = [
            (_node_byte_span(key, line_starts)[0], _node_byte_span(value, line_starts)[1])
            for key, value in zip(keys, values, strict=True)
        ]
        for index, (key, value) in enumerate(zip(keys, values, strict=True)):
            entry_lines = set(range(key.lineno, (value.end_lineno or value.lineno) + 1))
            if not (entry_lines & added):
                continue
            removal_span = _removal_span_for_item(entry_spans, index)
            key_start, key_end = _node_byte_span(key, line_starts)
            key_text = body[key_start:key_end].decode("utf-8", errors="replace")
            elements.append(
                (
                    key.lineno,
                    _DICT_ENTRY,
                    f"entry {key_text} in module-level dict `{name}`",
                    removal_span,
                )
            )
    return elements


# --- Category 3: unconditionally emitted literal -----------------------------


def _parent_map(tree: ast.Module) -> dict[int, ast.AST]:
    """`id(child) -> parent` for every node in `tree`, keyed by `id()` since
    `ast` nodes are not hashable by value and two structurally-identical
    nodes must never collide as dict keys."""
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _enclosing_function_unconditional(
    node: ast.AST, parents: dict[int, ast.AST]
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Walk upward from `node` to its enclosing function, returning that
    function iff no `If`/`Try`/`For`/`AsyncFor`/`While` ancestor sits
    between them (the display is built unconditionally in that function's
    own body). None when no enclosing function exists at all (a module- or
    class-body-level display) or when a guard sits between `node` and the
    nearest enclosing function."""
    current = parents.get(id(node))
    while current is not None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            return current
        if isinstance(current, _GUARD_NODE_TYPES):
            return None
        current = parents.get(id(current))
    return None


def _is_supported_literal(value: object) -> bool:
    return isinstance(value, _SUPPORTED_LITERAL_TYPES)


def _literal_display_elements(
    tree: ast.Module, body: bytes, line_starts: list[int], added: set[int]
) -> list[tuple[int, str, str, tuple[int, int]]]:
    """Every category-3 graded element: `(line, category, message,
    removal_span)` for each unconditionally-constructed-in-a-function
    literal list/tuple/set item or non-category-2 dict-entry value this
    diff newly adds or changes."""
    parents = _parent_map(tree)
    module_dict_ids = {id(dict_node) for _name, dict_node in _module_level_dict_assigns(tree)}
    elements: list[tuple[int, str, str, tuple[int, int]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.List | ast.Tuple | ast.Set):
            func = _enclosing_function_unconditional(node, parents)
            if func is None or not node.elts:
                continue
            item_spans = [_node_byte_span(item, line_starts) for item in node.elts]
            for index, item in enumerate(node.elts):
                if not (isinstance(item, ast.Constant) and _is_supported_literal(item.value)):
                    continue
                if not (_span(item) & added):
                    continue
                removal_span = _removal_span_for_item(item_spans, index)
                elements.append(
                    (
                        item.lineno,
                        _LITERAL_ELEMENT,
                        f"literal element {item.value!r} in an unconditionally constructed "
                        f"display inside `{func.name}`",
                        removal_span,
                    )
                )
        elif isinstance(node, ast.Dict):
            if id(node) in module_dict_ids or not node.keys or any(key is None for key in node.keys):
                continue
            func = _enclosing_function_unconditional(node, parents)
            if func is None:
                continue
            # See `_dict_entry_elements`'s own identical comment: the guard
            # above already rejects any `**`-unpacking (`None`-keyed) dict,
            # so this re-binding is a type narrowing, not a new check.
            dict_keys: list[ast.expr] = [key for key in node.keys if key is not None]
            entry_spans = [
                (_node_byte_span(key, line_starts)[0], _node_byte_span(value, line_starts)[1])
                for key, value in zip(dict_keys, node.values, strict=True)
            ]
            for index, (key, value) in enumerate(zip(dict_keys, node.values, strict=True)):
                if not (isinstance(value, ast.Constant) and _is_supported_literal(value.value)):
                    continue
                entry_lines = set(range(key.lineno, (value.end_lineno or value.lineno) + 1))
                if not (entry_lines & added):
                    continue
                removal_span = _removal_span_for_item(entry_spans, index)
                elements.append(
                    (
                        key.lineno,
                        _LITERAL_ELEMENT,
                        f"dict entry value {value.value!r} unconditionally emitted inside `{func.name}`",
                        removal_span,
                    )
                )
    return elements


# --- Mutation execution -------------------------------------------------------


def _invalidate_pycache(absolute_path: pathlib.Path) -> None:
    """Remove any cached bytecode for `absolute_path`'s own module before
    (and after) each mutation subprocess run.

    CPython's default import cache validates a `.pyc` by the *source
    file's own mtime and size* recorded in its header, not by content: two
    different writes to the same path landing inside the same mtime tick
    -- confirmed live, not merely a theoretical risk, this gate rewrites
    the same file repeatedly in quick succession across several mutations
    of the same source -- can make a stale cache from a *different*
    mutation (or the original, unmutated content) validate against a
    fresh write and get served instead of the content actually on disk,
    silently corrupting this gate's own verdict. Removing the whole
    `__pycache__` directory next to the module (rather than only the one
    cache file `importlib.util.cache_from_source` would name) is simple,
    safe, and correct regardless of interpreter version or which of
    several possible tag suffixes a given Python build uses. Called both
    right before running pytest against a freshly mutated copy and right
    after restoring the original bytes, so no stale entry can outlive
    this gate's own run and corrupt an unrelated, later import of the
    same file by another process (e.g. this repository's own full pytest
    suite, run either before or after this gate in the same CI job)."""
    cache_dir = absolute_path.parent / "__pycache__"
    if cache_dir.is_dir():
        shutil.rmtree(cache_dir, ignore_errors=True)


def _run_mutation(
    absolute_path: pathlib.Path,
    bom: bytes,
    original_body: bytes,
    removal_span: tuple[int, int],
    test_paths: list[pathlib.Path],
    root: pathlib.Path,
) -> bool:
    """Overwrite `absolute_path` with `bom + original_body` minus
    `removal_span`, run pytest against `test_paths`, restore the original
    bytes in a `finally` block regardless of outcome. Returns True iff the
    mutation SURVIVED (the paired suite still passed clean); False iff at
    least one paired test failed (the mutation was caught). Raises
    `ScanError` for anything else -- a write/restore failure, a subprocess
    that could not be started or timed out, or a pytest exit code that is
    neither 0 nor 1 -- per the module docstring's own "Exit codes" section.
    """
    start, end = removal_span
    mutated = bom + original_body[:start] + original_body[end:]
    try:
        absolute_path.write_bytes(mutated)
    except OSError as error:
        raise ScanError(f"could not write a mutated copy of {absolute_path}: {error}") from error
    _invalidate_pycache(absolute_path)

    env = dict(os.environ)
    extra_path = str(absolute_path.parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{extra_path}{os.pathsep}{existing}" if existing else extra_path
    # Defense in depth alongside `_invalidate_pycache`: never let the
    # subprocess itself write a new cache entry that a later mutation (or
    # a later, unrelated import of the restored original) could read back
    # as stale. `_invalidate_pycache` alone already prevents a stale read
    # by clearing the directory before every run; this just stops a new
    # one from being created in the first place.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        try:
            completed = subprocess.run(  # noqa: S603
                [sys.executable, "-m", "pytest", "--no-cov", "-n0", "-q", "-x", *(str(p) for p in test_paths)],
                cwd=root,
                env=env,
                capture_output=True,
                timeout=_PYTEST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ScanError(
                f"pytest timed out after {_PYTEST_TIMEOUT_SECONDS}s grading a mutated copy of "
                f"{absolute_path} against {test_paths}: {error}"
            ) from error
        except OSError as error:
            raise ScanError(
                f"pytest failed to run grading a mutated copy of {absolute_path} against {test_paths}: {error}"
            ) from error
    finally:
        try:
            absolute_path.write_bytes(bom + original_body)
        except OSError as error:
            raise ScanError(f"could not restore {absolute_path} after mutation testing: {error}") from error
        _invalidate_pycache(absolute_path)

    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise ScanError(
        f"pytest exited {completed.returncode} (neither 0 nor 1) grading a mutated copy of "
        f"{absolute_path} against {test_paths} -- this scan cannot trust the result. stderr tail: "
        f"{completed.stderr.decode('utf-8', errors='replace')[-2000:]}"
    )


def _graded_elements(path: str, source_text: str, added: set[int]) -> list[tuple[int, str, str, tuple[int, int]]]:
    """Every category 1-3 graded element for one source file's own AST,
    `(line, category, message, removal_span)`, `removal_span` in bytes
    relative to the file's own BOM-stripped body."""
    tree = ast.parse(source_text, filename=path)
    body = source_text.encode("utf-8")
    line_starts = _line_byte_starts(body)
    elements: list[tuple[int, str, str, tuple[int, int]]] = []
    elements.extend(_regex_alternation_elements(tree, body, line_starts, added))
    elements.extend(_dict_entry_elements(tree, body, line_starts, added))
    elements.extend(_literal_display_elements(tree, body, line_starts, added))
    return elements


def find_violations(diff_text: str, root: pathlib.Path) -> tuple[list[Finding], list[Finding], int]:
    """Grade every in-scope file the diff adds lines to.

    Returns ``(violations, honoured waivers, files graded)``. Raises
    ``ScanError`` when a file named by the diff exists but cannot be read as
    UTF-8 or parsed, or when a mutation subprocess itself could not be
    trusted. A file with no diff-touched paired test file is skipped (not
    counted as graded) -- see the module docstring's own "Why not parse
    docstrings" section.
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
            original_bytes = absolute.read_bytes()
        except FileNotFoundError:
            raise ScanError(f"{path}: named by the diff as added or modified, but missing from {root}") from None
        except OSError as error:
            raise ScanError(f"{path}: cannot be read: {error}") from error

        bom, body = _split_bom(original_bytes)
        try:
            source_text = body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error

        stem = _stem(path)
        touched_tests = [relative for relative in _test_relative_paths(stem) if added_by_path.get(relative)]
        if not touched_tests:
            continue

        try:
            elements = _graded_elements(path, source_text, added)
        except (SyntaxError, ValueError) as error:
            raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error

        if not elements:
            graded += 1
            continue

        waived_lines = _waived_lines(source_text)
        test_paths = [root / relative for relative in touched_tests]
        for line, category, message, removal_span in elements:
            survived = _run_mutation(absolute, bom, body, removal_span, test_paths, root)
            if not survived:
                continue
            finding = Finding(
                path,
                line,
                _MUTATION_GAP,
                f"{category}: {message} -- removing it still leaves {' and '.join(touched_tests)} passing clean",
            )
            target = waived if finding.line in waived_lines else violations
            target.append(finding)
        graded += 1
    return sorted(set(violations)), sorted(set(waived)), graded


class GateDefeatTestMutationCoverageArgs(BaseModel):
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
        description="Check that a new or materially changed regex alternation branch, module-level dict "
        "entry, or unconditionally emitted literal added by this diff is actually caught -- not merely "
        "mentioned -- by this same diff's own paired test. Reads a unified diff on standard input."
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
        validated = GateDefeatTestMutationCoverageArgs(root=args.root)
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
            f"\n{len(violations)} new or materially changed element(s) reached by this diff have a "
            "paired test that still passes clean once the element is removed (issue #1799). Make the "
            "paired test assert the element itself (an exact-match or parse-back assertion, not merely "
            "a type/non-emptiness check). When a human has already judged the element covered some "
            "other way, disclose it inline with "
            "'# defeat-test-mutation-coverage: WAIVED: <reason>' on the reported line.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

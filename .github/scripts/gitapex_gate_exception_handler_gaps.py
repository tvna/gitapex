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
`tests/test_gitapex_gate_exception_handler_gaps.py`:

* `f91383c:.github/scripts/gitapex_gate_plugin_root_brace_notation.py:116` --
  `text = path.read_text(encoding="utf-8")` inside no `try` at all
  (issue #682's defect C, shipped by PR #651).
* `406d587:.github/scripts/gitapex_detect_changed_gate_scripts.py:112` --
  `gates = data.get("gates")` on a `json.loads` result never checked to be
  an object (defect E, found in PR #674's review rounds).
* `0b4cedd:.github/scripts/gitapex_detect_changed_gate_scripts.py:298` --
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
that exception or one of its ancestors. Handler names are matched against
that fixed table and nothing else -- no constant is expanded, no import is
followed. The table is itself a name match, so shadowing a builtin
(`ValueError = KeyError`, a parameter named `ValueError`) defeats it; that
is listed below rather than defended against, because every attempt to
resolve a name in this gate has cost more than it bought.

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
`gitapex_detect_changed_gate_scripts.py` widened its own rule 1 there: 9 registered
gates live under `hooks/`, and issue #680 found one of these two defects in
`hooks/gitapex_check_pr_issue_acm_disclosure.py`. Test files (`test_*.py`,
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
* A walrus inside a lambda (`fn = lambda: (data := other)`) is read as
  rebinding the enclosing scope's name, which drops that name's taint. The
  comprehension form really does bind in the containing scope, so only the
  lambda is wrong here.
* Two parses into one name with an `isinstance` between them: the check
  clears the name for every later access, including one fed by the second
  parse.
* **`from json import loads` is not a parse.** Only the `json.loads(...)` /
  `json.load(...)` attribute spelling is, so the import form is defect E
  behind a one-line import change. Recognising it means resolving an
  imported name -- through aliases (`as jloads`), shadowing and rebinding --
  which is the machinery every bullet above records building and reverting.
  The attribute spelling is the one all three historical defects used and
  the only one this repository contains.
* **Two findings of the same rule on one physical line report once.**
  `a = p.read_text() + q.read_text()` is a single `decode-gap`, because
  findings are deduplicated by `(path, line, rule, message)` and those four
  are identical here. Printing the same line twice with the same text tells
  a contributor nothing about which read is meant; the cost is that fixing
  one and never touching the line again leaves the other unreported. One
  waiver on that line likewise covers both.

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
  waiver was built for in the first place, and unlike the three above it
  does occur here: `evals/scripts/gitapex_set_config_model.py:94` reads a file whose
  only caller wraps the call in `except ValueError`, and
  `UnicodeDecodeError` is a `ValueError`. It is one of the 39 pre-existing
  findings, and running that script against a non-UTF-8 file exits 1 with
  its own message and no traceback.
* `errors=` passed positionally rather than by keyword; see
  `_text_read_kind` for why no index is guessed.
* A `.get()` inside a comprehension or a lambda that rebinds the parsed
  name. Only `def` bodies are treated as separate scopes.
* A handler set defeated by shadowing a builtin exception name.
* **`<expr>.open()` with no positional argument, on a receiver that is not a
  file.** `conn.open()`, `db.open(flag=True)` and `webbrowser.open(url=...)`
  are all reported. The zero-argument form has to be graded -- `Path(p).open()`
  is a real text read and defect C's own shape -- and the only thing that
  would separate it from the others is recognising the receiver, which this
  gate does not do for the reasons above. Note the narrower positional form
  is *not* affected: `webbrowser.open(url)` grades clean.
* **`<expr>.open("<name>")` where the member name is built only from file-mode
  characters.** `z.open("art")`, `"raw"`, `"war"` and `"rat"` are read as
  mode strings and reported. `_looks_like_a_mode` narrows this -- `"name"`
  and `"data"` are not modes, and `"bat"`/`"tab"` contain a `b` and grade as
  binary -- but it cannot close it without knowing the receiver.

Of these, only the caller-owns-the-handling case occurs in the graded
directories today; the others are constructed, which is why each was
measured as a poor trade rather than an urgent one. The two `.open()`
over-reports were checked rather than assumed: the graded directories
contain five zero-argument `.open()` calls and two whose first argument is
a mode string, and every one of the seven is a real `Path(...).open()` --
so all of them are reported correctly, or (for the `"rb"` and `"w"` modes)
correctly not reported at all.

Every miss and every over-report above is pinned by a test asserting the
behaviour, so none can change without a reader noticing.

An intentional read that a *caller* guards can disclose itself inline with
a trailing `# exception-handler-gap: WAIVED: <reason>` comment on the line
this gate names in its own message -- the same `WAIVED: <reason>`
vocabulary `gitapex_gate_skill_audit_disclosure.py` already uses and the same
inline shape this repository's existing `# noqa: S603` waivers take. It
waives every finding reported on that line. A bare marker with no reason is
not a waiver. Every honoured waiver is printed, so it is never a silent
bypass.

This gate's own production invocation (`exception-handler-gap-gate.yml`)
runs under `uv run`, so a real `pydantic` import is safe here (issue
#1040, refs #1035's `uv run` standardization that made this class of
dependency safe repo-wide).

Usage::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_exception_handler_gaps.py

A bare pipe here masks `git diff`'s own exit status in a non-`pipefail`
shell (issue #1531): add `set -o pipefail` first, or check `git diff`'s
own exit code separately, if the caller must detect an upstream failure
rather than silently grading whatever partial diff reached stdin.

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

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs) or via the pytest gate in
`tests/test_gitapex_gate_exception_handler_gaps.py`.
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

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# The four directories holding this repository's deterministic checker
# scripts. `[^/]+` rather than `.*` so no pattern crosses a directory
# separator, matching `gitapex_detect_changed_gate_scripts.py`'s own rule-1
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
_DECODE_COVERING = frozenset({"UnicodeDecodeError", "UnicodeError", "ValueError", "Exception", "BaseException"})

# The `.get()` rule's own covering set. AttributeError is what an unvalidated
# JSON payload actually raises, so a handler naming it -- or any ancestor --
# makes that access safe. Applying only the decode set here reported a
# `.get()` wrapped in `except (json.JSONDecodeError, AttributeError)`, which
# is the exact remediation this gate's own failure message prescribes.
_JSON_COVERING = frozenset({"AttributeError", "Exception", "BaseException"})

# The `errors=` policies that substitute rather than raise *on a decode*.
# Determined by running each against `b"ok\xffbad".decode("utf-8", errors=...)`
# rather than read off the codecs documentation: `xmlcharrefreplace` and
# `namereplace` are encode-only and raise `TypeError: don't know how to handle
# UnicodeDecodeError in error callback`. Listing them made a read carrying one
# grade clean while exiting 1 with an uncaught traceback -- the defect class in
# this file's own opening paragraph, shipped by the fix for a false positive.
# `None` and `"strict"` are absent for the plainer reason that both raise.
_SUBSTITUTING_ERRORS = frozenset({"replace", "ignore", "surrogateescape", "backslashreplace"})


_JSON_PARSERS = frozenset({"loads", "load"})

# The types an `isinstance()` has to name for a JSON value to count as checked.
# `Mapping` and `MutableMapping` are here because `collections.abc` is how the
# rest of this repository spells "a mapping" in its own annotations; an
# attribute handler is compared by its final name, so `t.Mapping` matches too.
_MAPPING_TYPES = frozenset({"dict", "Mapping", "MutableMapping"})

# `# exception-handler-gap: WAIVED: <reason>` -- a reason is mandatory, the
# same way `gitapex_gate_skill_audit_disclosure.py`'s own `WAIVED:` clause requires
# one. A bare marker is not a waiver and is not honoured.
_WAIVER_RE = re.compile(r"#\s*exception-handler-gap\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

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

    A `+++ ` post-image header reached outside a hunk with no `--- ` source
    header before it raises ``ScanError`` (issue #1184) rather than being
    silently ignored: ignoring it leaves `path` at None, so every added line
    in every hunk that follows is dropped and the run reports `OK: 0
    in-scope file(s) graded` and exits 0 -- a silent pass on an input this
    gate could not grade. Real `git diff` output always emits `--- ` before
    `+++ `, so no wired invocation reaches this; `--diff <file>` accepts a
    patch from anywhere, and a fail-closed gate does not get to assume its
    input came from the wiring.

    `in_hunk` is bounded by the hunk's own declared line counts, not only by
    the next `diff --git ` line (issue #1184). Without that bound, a patch
    carrying no `diff --git ` header between two files' own hunks would
    leave `in_hunk` True straight through the second file's `--- `/`+++ `
    lines, misattributing its added lines to the first file's `path` at a
    stale `lineno`.

    Both the pre-image and post-image counts are tracked (`old_remaining`,
    `new_remaining`; each `,<count>` `_HUNK_RE` captures, defaulting to 1
    when omitted, per unified-diff shorthand), not the post-image count
    alone -- issue #1184's own initial fix used post-image count alone,
    which regressed a real, CI-reachable case: `git diff -U0` (this gate's
    own wired invocation) emits a pure-deletion hunk as `@@ -a,b +c,0 @@`
    (zero post-image lines), and a post-image-only bound reads `remaining`
    as already exhausted on the `@@` line itself -- before the hunk's own
    `b` removal lines are consumed -- so the very next line, itself the
    hunk's own removal content, is read as a real header instead. A
    same-shaped file (any script whose own source embeds a literal
    `--- `/`+++ ` pair, e.g. this repository's own diff-fixture-bearing test
    files) reached exactly that path in live testing during review: a real
    exception-handler gap on the deleting file silently vanished from
    grading, reattributed to an unrelated file entirely. `old_remaining`
    and `new_remaining` are each decremented only by the line kind that
    consumes that side (a context line consumes both; a removal consumes
    only the pre-image side; an addition consumes only the post-image
    side), and `in_hunk` clears only once *both* reach zero -- so a
    zero-post-image hunk still correctly protects its own removal lines
    via the pre-image side, closing the regression above.

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
            # Same split as `FunctionDef` above, and for the same reason: the
            # body is deferred and loses the protection, but the argument
            # defaults are evaluated where the `lambda` is written and keep
            # it. Walking every child with cleared state reported
            # `lambda x=p.read_text(): x` inside a `try` that really does
            # catch it.
            for default in [*node.args.defaults, *(d for d in node.args.kw_defaults if d)]:
                walk(default, handled, enclosing)
            walk(node.body, frozenset(), frozenset())
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
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and set(node.value) <= set("rwxab+t")


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
    # By keyword only. The positional index differs per callee -- 4 for the
    # builtin `open`, 3 for `Path.open`, 1 for `read_text` -- and reading one
    # index for all three reported two of the three shapes this gate actually
    # grades. Index arithmetic over a signature this gate cannot see is the
    # same class of guess as the name resolution reverted above, so the
    # positional spelling is an over-report instead.
    errors = next((k.value for k in node.keywords if k.arg == "errors"), None)
    if isinstance(errors, ast.Constant) and isinstance(errors.value, str) and errors.value in _SUBSTITUTING_ERRORS:
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
        builtin_mode = mode_kwarg if mode_kwarg is not None else (node.args[1] if len(node.args) >= 2 else None)
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


def _walk_excluding_nested_functions(node: ast.AST) -> Iterator[ast.AST]:
    """Yield every node belonging to `node`'s own scope, excluding the bodies
    of nested functions -- those are their own scope and are walked separately.

    The cost of that exclusion is stated rather than hidden: a closure that
    reads an *enclosing function's* JSON value is not graded. Sharing an
    arbitrary outer function's taint would also share every other function's,
    so the same variable name validated in one would silence it in all -- a
    fail-open in a gate whose whole subject is fail-open. Module scope is not
    an exception to that: inheriting it was implemented and reverted, for the
    reasons `_json_shape_gaps` records.
    """
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
    elif isinstance(node, ast.For | ast.AsyncFor):
        yield from _bound_targets(node.target)
    elif isinstance(node, ast.With | ast.AsyncWith):
        # `with ctx() as data:` rebinds `data` as plainly as an assignment
        # does. Reading only `Assign`/`For` left three binding forms invisible,
        # so a name the source provably rebinds kept its taint and the `.get()`
        # after it was reported on a value that is not the parse result.
        for item in node.items:
            if item.optional_vars is not None:
                yield from _bound_targets(item.optional_vars)
    elif isinstance(node, ast.ExceptHandler) and node.name is not None:
        yield node.name, None


def _bound_targets(target: ast.expr) -> Iterator[tuple[str, ast.expr | None]]:
    """Yield every name a binding target rebinds, with no value attached.

    Tuple and list targets are unpacked, so `for data, _ in pairs:` and
    `with ctx() as (data, _):` drop `data`'s taint the same way the plain
    `for data in items:` form already did. Starred and attribute/subscript
    targets bind nothing this gate tracks and are skipped.
    """
    if isinstance(target, ast.Name):
        yield target.id, None
    elif isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            yield from _bound_targets(element)
    elif isinstance(target, ast.Starred):
        yield from _bound_targets(target.value)


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
        nodes = list(_walk_excluding_nested_functions(scope))
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
    materialised set, which keeps a long function from costing a set per
    finding -- the region between a JSON parse and the access it feeds. Waiving is not on this record at all: a waiver is matched against
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
                    f"{kind}(...) decodes text, but no enclosing try handles UnicodeDecodeError (or an ancestor of it)",
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
                # The enclosing `except` lines belong in the trigger for the
                # same reason they do for a decoded read, and leaving them out
                # was a fail-open on this gate's own subject: narrowing
                # `except (ValueError, AttributeError)` to `except ValueError`
                # creates the gap while touching neither the `.get()` nor
                # anything between the parse and it, so no other part of the
                # trigger can see the edit. The window below covers the
                # parse-to-access region, which an `except` header never sits
                # in -- it always follows the try body.
                frozenset(expression | handler_lines.get(id(gap.call), set())),
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
            # utf-8-sig, not utf-8: CPython strips a leading BOM from source it
            # imports or runs, but `ast.parse` on a `str` does not, so a
            # BOM-carrying file that python3 executes fine otherwise failed
            # this gate with "cannot be parsed as Python: invalid
            # non-printable character U+FEFF" -- a hard block naming a syntax
            # error that does not exist. For a file without a BOM the two
            # codecs are identical, and neither shifts a line number.
            source = absolute.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            # The diff names a post-image path that is not in this checkout.
            # A deletion never reaches here (its `+++` line is /dev/null), so
            # this is a caller pointing --root at the wrong tree, or grading
            # a diff against a checkout that does not contain its head.
            raise ScanError(f"{path}: named by the diff as added or modified, but missing from {root}") from None
        except (OSError, UnicodeDecodeError) as error:
            raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
        file_violations, file_waived = findings_for_source(path, source, added)
        violations.extend(file_violations)
        waived.extend(file_waived)
        graded += 1
    return violations, waived, graded


class GateExceptionHandlerGapsArgs(BaseModel):
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
        # stdin do it under the platform locale. `sys.stdin.read()` was this
        # gate's own subject shipped into the gate: a non-UTF-8 byte anywhere
        # in the diff escaped as an uncaught UnicodeDecodeError and exited 1
        # -- "violation found" -- with a traceback, where the same bytes given
        # to --diff exited 2. On a locale that coerces to surrogateescape it
        # instead passed an unpaired surrogate through silently. Both failure
        # modes are the ones gitapex_extract_diff_added_lines.py's docstring already
        # records having had to close on this same input.
        #
        # Fail closed rather than decoding with errors="replace" as that
        # script does: it has no exit code for "the input could not be
        # trusted" and this gate does, and exit 2 is what --diff already
        # returns for these bytes.
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
            f"\n{len(violations)} added line(s) reach a failure they do not handle. This is the "
            "defect class that has now shipped into this repository's own gates five times "
            "(refs #682, #680, #665): every instance passed pytest at 100 percent line "
            "coverage, because the handler that would have caught it does not exist. Catch the "
            "failure at the read boundary and raise this script's own typed error, the way "
            ".github/scripts/gitapex_detect_changed_gate_scripts.py does -- or, when a caller genuinely "
            "owns the handling, disclose it inline with "
            "'# exception-handler-gap: WAIVED: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

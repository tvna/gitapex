#!/usr/bin/env python3
"""CI gate: flag an unguarded `cmd1 | cmd2`-shaped shell pipe example, with no
nearby `pipefail` disclosure, in a `skills/*/SKILL.md`, a
`skills/*/references/*.md` file, or a checker/gate script's own module
docstring.

Issue #1531 (refs #1567, gate-proposal-umbrella: local-hook fail-open
remediation). The documented invocation `git log ... | python3
gitapex_check_task_commit_provenance.py` piped two commands directly
together; a bare shell pipeline's own exit status is the RIGHT-hand
command's, not the LEFT's, so an upstream `git log` failure (a
stale/unresolvable BASE ref, a rebase, a shallow worktree) would silently
report a clean "PASS: no commits in range" instead of a blocked merge --
discovered only by an adversarial security-focused review, not by any
deterministic check (that specific script's own docstring now documents the
two-step, never-piped invocation instead; this gate is the durable check
that a *future* documented recipe does not reintroduce the same shape
elsewhere).

A documentation-lint sibling to `gitapex_gate_no_raw_gh_cli_in_docs.py`, not
a runtime enforcement: it cannot verify what an agent actually types into a
shell, only flag an unsafe *documented* example for a human/agent to
notice before copying it (this issue's own stated residual risk).

Scope
-----
Two file kinds, discovered via `git ls-files` (tracked files only, matching
`gitapex_gate_no_raw_gh_cli_in_docs.py`'s own tracked-file rationale):

* Markdown: `skills/*/SKILL.md` and `skills/*/references/*.md`. Only text
  inside a fenced code block (``` or ~~~) is scanned, using the same
  CommonMark run-length fence-pairing `gitapex_gate_no_raw_gh_cli_in_docs.py`
  already established (a fence closes only on a bare run of the same marker
  character at least as long as the one that opened it) -- re-implemented
  here rather than imported, matching this repository's own existing
  precedent of one fence-pairing copy per gate (`gitapex_gate_split_fixture_
  coverage.py`, `gitapex_gate_skill_branch_fixture_coverage.py`,
  `gitapex_gate_independent_review_pending.py` each already carry their own).
* Python: the module docstring only (never the rest of the file -- a CLI
  help string or an inline comment quoting the same shape is out of scope,
  deliberately; see "Known gaps" below) of every tracked
  `.github/scripts/*.py`, `skills/*/scripts/*.py`, `evals/scripts/*.py` and
  `hooks/*.py` file -- the three globs match
  `gitapex_compute_skill_audit_flags.py`'s own `_CHECKER_SCRIPT_PATHSPECS`
  exactly, widened here to also include `hooks/*.py` (that flag-computation
  module tracks `hooks/**` separately, as a gate-membership signal rather
  than a checker-script one; this gate folds both into one disclosure-
  bearing script surface).

Detection
---------
A line matches when it carries a single `|` (not `||`) with a real command
token before it and one of a fixed, explicit consumer vocabulary
(`_PIPE_CONSUMERS` -- `python3`, `bash`, `uv`, `jq`, `grep`, `sed`, ... --
the same never-grow-it-ad-hoc discipline `_GH_SUBCOMMANDS` uses in the
sibling gate) directly after it. This is deliberately narrower than "any
line with a pipe character": a bare non-whitespace-pipe-non-whitespace match also fires on a Python
type-hint quoted in prose (`` `list[str] | None` ``, a real, common shape in
this repository's own docstrings -- confirmed live during this gate's own
authoring, not assumed) and on an ordinary Markdown table row. Requiring a
recognized shell-consumer token on the right closes both false-positive
classes for every real instance found in this repository at authoring
time, without needing real shell tokenization -- but not in general: a
table cell (or a type-hint-like phrase) whose own literal value happens to
equal one of `_PIPE_CONSUMERS` (e.g. a table row documenting the `jq`
tool, `| Parser | jq |`) still matches, live-confirmed, since nothing here
distinguishes a table's `|` column separator from a shell pipe. Closing
that residual case needs table-syntax awareness this gate does not
implement; see "Known gaps" below.

A match is a violation unless "nearby disclosure" is found, meaning either:

1. `pipefail` (case-insensitive, matching the literal `pipefail`/`set -o
   pipefail` vocabulary #1531 names) appears -- for Markdown, anywhere
   within the *same fenced block* the match sits in (i.e. the documented
   recipe already shows the guard); for a Python docstring, anywhere in
   that *same module docstring* (a prose caveat elsewhere in the docstring,
   not necessarily inside a code-like line, still counts -- docstrings have
   no fence to scope a match to more tightly); or
2. an explicit `<!-- gitapex-allow-unguarded-shell-pipe: <reason> -->`
   marker sits on the line directly above (no blank line in between) --
   for Markdown, the fence's own opening marker line; for a Python
   docstring, the flagged line itself -- the same strict,
   regex-anchored, non-empty-reason-required marker style
   `gitapex_gate_no_raw_gh_cli_in_docs.py`'s own `gitapex-allow-raw-gh-cli`
   marker already uses, under a distinct token so an author waiving one
   check does not silently waive the other.

Known gaps, disclosed rather than claimed closed
-------------------------------------------------
* A Python docstring match is skipped outright when the matched pipe
  expression sits inside a backtick span (single `` ` `` or double `` `` ``)
  on that same line -- deliberately, mirroring the sibling gate's own
  distinction between an inline code span that *discusses* a pattern and a
  fenced block that *instructs* running one: a docstring has no fence to
  draw that line at, so a backtick-quoted illustrative example (a warning
  discussing what NOT to do, or an unrelated dangerous-pattern discussion
  entirely unrelated to a merge gate) is excluded the same way a Markdown
  inline code span already is. A standalone, unquoted `Usage::`-style
  recipe line -- the shape #1531's own motivating defect took, and the one
  this gate exists to catch -- is never backtick-wrapped in this
  repository's existing docstring convention, confirmed live against every
  in-scope script at authoring time (20 real matches -- 7 found by the
  single-line match alone, 13 more found only once `_effective_line`'s own
  shell-line-continuation join was added -- all standalone; every
  backtick-wrapped candidate was illustrative prose, none a documented
  recipe).
* Only the *module* docstring is scanned for a Python file -- an argparse
  `description=` string, an inline comment, or a nested function's own
  docstring is out of scope. A CLI's own `--help` text can therefore still
  carry the same unguarded shape undetected; narrowing to the module
  docstring is a deliberate scope limit (issue #1531's own text says
  "a Python script's own module docstring"), not an oversight.
* No real shell tokenization: a `|` inside a quoted string
  (`echo "a|b" | python3 x.py`) is graded the same as a real pipeline
  boundary would be, and a consumer token appearing for an unrelated reason
  (a comment, a variable name) immediately after a `|` is graded as a match
  regardless of context. Both are the same class of imprecision
  `gitapex_gate_no_raw_gh_cli_in_docs.py` already accepts for its own
  fence-scoped regex scan.
* `||` (logical OR) is deliberately excluded -- it does not mask an upstream
  exit status the way a single `|` does, so it carries none of this gate's
  own risk class.
* A documentation-only lint cannot verify the actual runtime invocation an
  agent performs matches the documented one (issue #1531's own stated
  residual risk) -- it can only flag an unsafe documented example for a
  human/agent to notice.
* Every exemption below is scoped to the whole enclosing unit, not to the
  individual matched line: `pipefail` disclosure and the allow marker both
  clear every match in the same fenced block (Markdown) or the same module
  docstring (Python), not only the one match adjacent to the disclosure.
  A block/docstring carrying two unrelated pipe examples, only one of them
  genuinely covered by the stated disclosure or marker reason, silently
  clears both -- this gate does not check that a marker's own reason text
  actually corresponds to every match it exempts. The backtick exclusion
  for a Python docstring line is likewise a whole-line check (`` "`" in
  line ``), not position-aware: an unrelated backtick-quoted term earlier
  on the same line as a real, unquoted recipe would exempt that recipe
  too. Closing either gap needs a position-aware span check this gate does
  not implement; a human reviewer reading the stated reason against the
  block's actual content remains the backstop, the same trust this
  gate's own sibling already places in `gitapex-allow-raw-gh-cli`'s
  reason text.

Exit codes: 0 clean, 1 violation(s) found, 2 the scan could not be trusted
(no in-scope file discovered in either category, or a file could not be
read/decoded as UTF-8 or parsed as Python) -- the same 0/1/2 split
`gitapex_gate_no_raw_gh_cli_in_docs.py` uses.

Run via `uv run` (needed for the pydantic import) or via the pytest gate in
tests/test_gitapex_gate_unguarded_shell_pipe_in_docs.py.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Fixed, explicit, never grown ad hoc -- the same discipline `_GH_SUBCOMMANDS`
# uses in gitapex_gate_no_raw_gh_cli_in_docs.py. Chosen to catch the real
# motivating shape (a data-producing command feeding an interpreter or text
# tool) while excluding a Python type hint (`list[str] | None`) and an
# ordinary Markdown table cell, neither of which is ever followed by one of
# these tokens.
_PIPE_CONSUMERS = frozenset(
    {
        "python3",
        "python",
        "bash",
        "sh",
        "zsh",
        "uv",
        "jq",
        "grep",
        "sed",
        "awk",
        "sort",
        "xargs",
        "head",
        "tail",
        "wc",
        "tee",
        "perl",
        "ruby",
        "node",
        "cut",
        "tr",
    }
)

# `\S` before the pipe requires a real token on the left; `(?<!\|)...(?!\|)`
# excludes `||`; the consumer alternation plus trailing `\b` requires a real
# command-start match on the right, not a word-internal one.
_PIPE_RE = re.compile(
    r"\S[ \t]*(?<!\|)\|(?!\|)[ \t]*(?:" + "|".join(re.escape(token) for token in sorted(_PIPE_CONSUMERS)) + r")\b"
)

# Same CommonMark run-length rule as gitapex_gate_no_raw_gh_cli_in_docs.py's
# own `_FENCE_OPEN_RE`/`_FENCE_CLOSE_RE`: a fence opens on a run of >= 3 of
# the same marker character and closes only on a bare run of that same
# character at least as long.
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^(`{3,}|~{3,})$")

_PIPEFAIL_RE = re.compile(r"pipefail", re.IGNORECASE)

_ALLOW_MARKER_RE = re.compile(r"^[ \t]*<!--[ \t]*gitapex-allow-unguarded-shell-pipe[ \t]*:[ \t]*\S.*-->[ \t]*$")

_MARKDOWN_PATHSPECS = (":(glob)skills/*/SKILL.md", ":(glob)skills/*/references/*.md")
_PYTHON_PATHSPECS = (
    ":(glob).github/scripts/*.py",
    ":(glob)skills/*/scripts/*.py",
    ":(glob)evals/scripts/*.py",
    ":(glob)hooks/*.py",
)


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    matched: str
    location: str  # "fenced code block" or "module docstring"

    def describe(self) -> str:
        return (
            f"{self.path}:{self.line}: unguarded shell pipe `{self.matched}` in a {self.location}, "
            "with no nearby pipefail disclosure"
        )


def _pipe_match(line: str) -> re.Match[str] | None:
    """The first `cmd | <consumer>`-shaped match on `line`, or None."""
    return _PIPE_RE.search(line)


def _effective_line(lines: list[str], index: int) -> str:
    """`lines[index]` (0-indexed), prefixed with the previous line's own
    content when that previous line ends in a shell line-continuation
    backslash.

    This repository's own `Usage::` convention commonly wraps a long
    producer command onto its own line ending in `\\`, with the `|
    <consumer>` continuation starting the next line -- `_pipe_match`'s own
    `\\S` requirement before the pipe would otherwise never see a pipe that
    is the first token on its own line. Joining the two lines here, the
    same way a shell itself joins a backslash-continued command before
    executing it, lets the existing single-line match still find it. A
    literal `\\\\` (an escaped backslash, not a continuation) is
    deliberately excluded.
    """
    if index == 0:
        return lines[index]
    previous = lines[index - 1].rstrip()
    if previous.endswith("\\") and not previous.endswith("\\\\"):
        return previous[:-1] + " " + lines[index].lstrip()
    return lines[index]


def _has_pipefail_disclosure(text: str) -> bool:
    """True iff `text` mentions `pipefail` (case-insensitive) anywhere."""
    return bool(_PIPEFAIL_RE.search(text))


def _has_allow_marker(lines: list[str], marker_line: int) -> bool:
    """True iff the line directly above `marker_line` (1-indexed, no blank
    line in between) is a valid `gitapex-allow-unguarded-shell-pipe` marker.

    Reused for both surfaces this gate scans: `marker_line` is a fence's own
    opening marker line for Markdown, or the flagged line itself for a
    Python docstring (which has no fence to anchor the marker's position
    to).
    """
    if marker_line < 2:
        return False
    return bool(_ALLOW_MARKER_RE.match(lines[marker_line - 2]))


def _fenced_line_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """Return `(open_marker_line, scan_end_line)` pairs, 1-indexed, for each
    fenced block in `lines` -- identical contract to
    `gitapex_gate_no_raw_gh_cli_in_docs.py`'s own `_fenced_line_ranges`: an
    unclosed fence's `scan_end_line` is `len(lines) + 1`, one past the last
    real line, so that line is still scanned even with no trailing newline.
    """
    ranges: list[tuple[int, int]] = []
    open_run: str | None = None
    open_line = 0
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if open_run is None:
            opening = _FENCE_OPEN_RE.match(stripped)
            if opening:
                open_run = opening.group(1)
                open_line = i
            continue
        closing = _FENCE_CLOSE_RE.match(stripped)
        if closing and closing.group(1)[0] == open_run[0] and len(closing.group(1)) >= len(open_run):
            ranges.append((open_line, i))
            open_run = None
    if open_run is not None:
        ranges.append((open_line, len(lines) + 1))
    return ranges


def markdown_violations_in_text(text: str) -> list[tuple[int, str]]:
    """Return `(line, matched)` for every unguarded shell pipe found inside a
    fenced code block in `text`, 1-indexed, skipping a fence either exempted
    by a directly-preceding allow marker or already disclosing `pipefail`
    somewhere inside itself."""
    lines = text.split("\n")
    found: list[tuple[int, str]] = []
    for open_line, close_line in _fenced_line_ranges(lines):
        if _has_allow_marker(lines, open_line):
            continue
        block_text = "\n".join(lines[open_line : close_line - 1])
        if _has_pipefail_disclosure(block_text):
            continue
        for lineno in range(open_line + 1, close_line):
            if _pipe_match(_effective_line(lines, lineno - 1)):
                found.append((lineno, lines[lineno - 1].strip()))
    return found


def docstring_violations_in_text(doc_text: str) -> list[tuple[int, str]]:
    """Return `(line, matched)` -- 1-indexed within `doc_text` -- for every
    unguarded, non-backtick-quoted shell pipe found in a module docstring's
    raw text, unless `doc_text` discloses `pipefail` anywhere (in which case
    the whole docstring is treated as covered) or the flagged line is
    directly preceded by a valid allow marker."""
    if _has_pipefail_disclosure(doc_text):
        return []
    lines = doc_text.split("\n")
    found: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if not _pipe_match(_effective_line(lines, i - 1)):
            continue
        if "`" in line:
            continue
        if _has_allow_marker(lines, i):
            continue
        found.append((i, line.strip()))
    return found


def _tracked_files(root: pathlib.Path, pathspecs: tuple[str, ...]) -> list[pathlib.Path]:
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git` is
        # intentionally resolved from PATH -- same rationale as
        # gitapex_gate_no_raw_gh_cli_in_docs.py's own discover().
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "ls-files", "-z", "--", *pathspecs],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ScanError(f"cannot run git to list tracked files: {error}") from error
    if result.returncode != 0:
        raise ScanError(f"{root}: git ls-files failed: {result.stderr.strip()}")
    return sorted(root / name for name in result.stdout.split("\0") if name)


def discover_markdown(root: pathlib.Path) -> list[pathlib.Path]:
    """Every tracked `skills/*/SKILL.md` and `skills/*/references/*.md` file."""
    return _tracked_files(root, _MARKDOWN_PATHSPECS)


def discover_python(root: pathlib.Path) -> list[pathlib.Path]:
    """Every tracked checker/gate-script `.py` file in this gate's scope."""
    return _tracked_files(root, _PYTHON_PATHSPECS)


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error


def violations_in_markdown_file(path: pathlib.Path, root: pathlib.Path) -> list[Violation]:
    text = _read_text(path)
    relative = str(path.relative_to(root))  # detection-logic-property-coverage: WAIVED: plain relativization only
    return [
        Violation(path=relative, line=line, matched=matched, location="fenced code block")
        for line, matched in markdown_violations_in_text(text)
    ]


def _module_docstring_with_start_line(text: str, path: pathlib.Path) -> tuple[str, int] | None:
    """The module docstring's raw text (not dedented/cleaned -- this gate's
    own detection does not need that) and the file line its own first
    character sits on, or None when the file has no module docstring.

    Raises `ScanError` on a syntax error rather than skipping the file: an
    unparseable checker/gate script hides whether it carries the exact
    shape this gate exists to catch.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise ScanError(f"{path}: cannot be parsed as Python: {error}") from error
    if not tree.body:
        return None
    first_stmt = tree.body[0]
    if not isinstance(first_stmt, ast.Expr):
        return None
    doc_expr = first_stmt.value
    if not isinstance(doc_expr, ast.Constant) or not isinstance(doc_expr.value, str):
        return None
    return doc_expr.value, first_stmt.lineno


def violations_in_python_file(path: pathlib.Path, root: pathlib.Path) -> list[Violation]:
    text = _read_text(path)
    relative = str(path.relative_to(root))  # detection-logic-property-coverage: WAIVED: plain relativization only
    docstring = _module_docstring_with_start_line(text, path)
    if docstring is None:
        return []
    doc_text, start_line = docstring
    return [
        Violation(path=relative, line=start_line + line - 1, matched=matched, location="module docstring")
        for line, matched in docstring_violations_in_text(doc_text)
    ]


def find_violations(root: pathlib.Path = REPO_ROOT) -> list[Violation]:
    """Scan every in-scope tracked file under `root` and return all
    violations. Raises `ScanError` when neither corpus can be trusted to
    have been checked -- an empty combined match set most plausibly means
    the scan ran against the wrong root, and this gate would otherwise pass
    while checking nothing.

    Deliberately AND-gated, not per-corpus: a real checkout always matches
    at least this gate's own script under `.github/scripts/*.py`, so a
    hypothetical future typo narrowing `_MARKDOWN_PATHSPECS` to zero
    matches would not raise here even under a per-corpus check's own
    intent -- and gating on either corpus alone breaks every test fixture
    below that legitimately populates only one category to isolate what it
    tests (confirmed live: 30 of this file's own tests failed against a
    per-corpus version of this check, tried and reverted during this
    gate's own authoring). `test_repository_scan_reaches_a_real_tracked_set`
    is this repository's own real backstop for that regression instead --
    it asserts a real file-count floor for each corpus against the actual
    checkout, so a pathspec narrowed to empty fails CI immediately rather
    than silently passing this gate.
    """
    markdown_paths = discover_markdown(root)
    python_paths = discover_python(root)
    if not markdown_paths and not python_paths:
        raise ScanError(
            f"{root}: no tracked skills/*/SKILL.md, skills/*/references/*.md, .github/scripts/*.py, "
            "skills/*/scripts/*.py, evals/scripts/*.py, or hooks/*.py files found. An empty match set "
            "most plausibly means the scan ran against the wrong root -- either way this gate would "
            "otherwise pass while checking nothing."
        )
    violations: list[Violation] = []
    for path in markdown_paths:
        violations.extend(violations_in_markdown_file(path, root))
    for path in python_paths:
        violations.extend(violations_in_python_file(path, root))
    return violations


class GateUnguardedShellPipeInDocsArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace."""

    root: pathlib.Path

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 clean, 1 violation(s) found, 2 the scan could not be trusted."""
    parser = argparse.ArgumentParser(
        description="Check that no skills/*/SKILL.md, skills/*/references/*.md, or checker/gate "
        "script's own module docstring carries an unguarded `cmd1 | cmd2`-shaped shell pipe example "
        "with no nearby pipefail disclosure."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root to scan (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateUnguardedShellPipeInDocsArgs(root=args.root)
    except ValidationError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    try:
        violations = find_violations(validated.root)
    except ScanError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    if violations:
        for violation in violations:
            print(violation.describe(), file=sys.stderr)
        print(
            f"\n{len(violations)} unguarded shell pipe example(s) found with no nearby pipefail "
            "disclosure. Add `set -o pipefail` (or an equivalent caveat mentioning `pipefail`) inside "
            "the same fenced block (Markdown) or the same module docstring (Python), or if the pipe is "
            "illustrative prose rather than a documented recipe, add "
            "`<!-- gitapex-allow-unguarded-shell-pipe: <reason> -->` directly above the fence (Markdown) "
            "or the flagged line (Python docstring) (issue #1531, refs #1567).",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {len(discover_markdown(validated.root))} Markdown file(s) and "
        f"{len(discover_python(validated.root))} Python file(s) carry no unguarded shell pipe examples."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

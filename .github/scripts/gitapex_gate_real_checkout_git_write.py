#!/usr/bin/env python3
"""Local-plane gate: no pytest-discovered test file may construct a
`REPO_ROOT`-rooted path expression that continues into a literal
`".git"` path segment.

Issue #991: `test_installs_the_prek_hook_for_a_real_checkout` ran the
session-start hook against `REPO_ROOT` itself
(`REPO_ROOT / ".git" / "hooks" / "pre-commit"`), so `prek install`
rewrote this repository's own real `.git/hooks/pre-commit`
unconditionally on every test run (verified directly: its mtime changes
even when its content stays byte-identical) -- a write no pytest-xdist
worker owns, surviving the run on a real checkout. A prior task on this
same branch pointed that one test at a throwaway local clone instead;
this gate exists so the same hazard shape cannot silently return in some
*other* test file.

**Detection is a deliberately loose line scan, not AST parsing** --
mirroring `gitapex_gate_bare_python3_invocation.py`'s own "deliberately
loose... accepting known residual risk" precedent for this gate family,
rather than the AST-based approach
`gitapex_gate_exception_handler_gaps.py` uses for its own,
differently-shaped subject. A line matches when it contains the literal
token `REPO_ROOT`, followed later on the same physical line by a
`/`-chained `".git"` or `'.git'` string segment -- the exact shape the
hazard line above takes. This intentionally does not distinguish a read
from a write: a legitimate read-only need (this repository had one,
before the prior task's own fix) gets the explicit, documented waiver
below, not a narrower pattern that would silently stop catching a
genuine write too.

Known, disclosed scope limits, never silently narrower than claimed
here: this gate does not catch `os.path.join(REPO_ROOT, ".git", ...)`,
an expression chained across multiple physical lines, or a repository
root bound to a name other than the literal `REPO_ROOT` -- this
repository's own consistent convention across `tests/*.py`, confirmed at
plan time across dozens of files.

**Waiver.** An inline `# real-checkout-git-write: WAIVED: <reason>`
comment on the *same physical line* as the flagged pattern, with a
mandatory non-empty reason, mirrors
`gitapex_gate_exception_handler_gaps.py`'s own `_WAIVER_RE`/waiver
convention (`.github/scripts/gitapex_gate_exception_handler_gaps.py:320`,
`:875-894`) exactly, including matching through `tokenize` rather than a
raw substring search: only a genuine comment token counts, so the same
text sitting inside a string literal can never spoof a waiver. Every
honoured waiver still prints to stderr -- never a silent bypass.

**Scan scope** is every `test_*.py`/`*_test.py` file -- pytest's own
default `python_files` pattern, which this repository's own
`pyproject.toml` does not override (confirmed at plan time) -- found
recursively under each of `pyproject.toml`'s own
`[tool.pytest.ini_options] testpaths` entries (`pyproject.toml:330`),
read live from `--root`'s own `pyproject.toml` rather than a second
hardcoded copy, so the two cannot silently drift out of sync (mirrors
`gitapex_gate_evals_scripts_coverage.py`'s own
`read_coverage_sources()`). `conftest.py` is not itself a test file by
this naming convention and is not scanned, the same distinction pytest's
own collection draws. This gate does not invoke pytest's own collection
directly; a future change to `python_files`, a collection plugin, or
`testpaths` without a matching update here could silently narrow what
this gate actually scans relative to what pytest actually collects --
disclosed, not solved.

Exit codes: 0 clean, 1 one or more (non-waived) findings, 2 the scan
could not be trusted (`--root` not a directory, none of its `testpaths`
directories exist, `--root`'s `pyproject.toml` is missing, unreadable,
or malformed, or a discovered file will not decode as UTF-8 or will not
tokenize as Python) -- the same 0/1/2 convention
`gitapex_gate_hidden_characters.py` and `gitapex_gate_behind_base.py`
both already use.

Run via `uv run` (this repository's own registry convention) or,
equally safely, a bare `python3` once `pydantic` is installed -- this
module imports nothing beyond the standard library and `pydantic`.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
import tomllib
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]

# `REPO_ROOT`, then later on the same physical line, a `/`-chained
# `".git"` or `'.git'` string segment -- the exact shape
# `REPO_ROOT / ".git" / "hooks" / "pre-commit"` takes. Deliberately loose
# (no AST, no distinction between real code, a comment, and a string
# literal): the tokenize-based waiver check below is the only thing that
# can silence a match. `\b` after REPO_ROOT excludes a differently-named
# variable that merely starts with this token (e.g. `REPO_ROOT_BACKUP`)
# -- this gate's own disclosed scope is exactly the literal `REPO_ROOT`
# binding, never a look-alike name.
_HAZARD_RE = re.compile(r"REPO_ROOT\b.*?/\s*['\"]\.git['\"]")

# `# real-checkout-git-write: WAIVED: <reason>` -- a reason is mandatory,
# mirroring gitapex_gate_exception_handler_gaps.py's own `_WAIVER_RE`
# (.github/scripts/gitapex_gate_exception_handler_gaps.py:320). A bare
# marker, or one with only trailing whitespace after the second colon, is
# not a waiver and is not honoured.
_WAIVER_RE = re.compile(r"#\s*real-checkout-git-write\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    path: str
    line: int
    text: str

    def describe(self) -> str:
        return f"{self.path}:{self.line}: {self.text}"


def read_testpaths(pyproject_path: Path) -> list[str]:
    """Return `pyproject_path`'s `[tool.pytest.ini_options] testpaths`
    list -- the single source of truth this gate's scan scope is derived
    from (`pyproject.toml:330`), so a newly added testpaths directory is
    covered automatically instead of a second hardcoded copy silently
    drifting out of sync (mirrors
    `gitapex_gate_evals_scripts_coverage.py`'s own
    `read_coverage_sources()`).

    Raises `ScanError` on a missing/unreadable file, invalid TOML, or a
    `testpaths` value that is not a non-empty list of non-blank strings
    -- a malformed `pyproject.toml` must never be silently treated as
    "no scope, so nothing to check."
    """
    try:
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ScanError(f"could not read {pyproject_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ScanError(f"{pyproject_path} is not valid TOML: {exc}") from exc

    try:
        testpaths = data["tool"]["pytest"]["ini_options"]["testpaths"]
    except (KeyError, TypeError) as exc:
        raise ScanError(f"{pyproject_path} has no [tool.pytest.ini_options] testpaths list") from exc
    if (
        not isinstance(testpaths, list)
        or not testpaths
        or not all(isinstance(item, str) and item.strip() for item in testpaths)
    ):
        raise ScanError(f"{pyproject_path}'s testpaths must be a non-empty list of non-blank strings")
    return testpaths


def discover(root: Path, testpaths: list[str]) -> list[Path]:
    """Return every pytest-discovered test file under `root`: `test_*.py`
    and `*_test.py`, recursively, under each of `testpaths` -- pytest's
    own default `python_files` pattern (`pyproject.toml` carries no
    override, confirmed at plan time). `conftest.py` is not itself a test
    file by this naming convention and is excluded, the same distinction
    pytest's own collection draws.

    Raises `ScanError` when every `testpaths` directory is missing --
    most plausibly the wrong `--root`, not a repository with zero scan
    scope.
    """
    found: set[Path] = set()
    missing = 0
    for testpath in testpaths:
        directory = root / testpath
        if not directory.is_dir():
            missing += 1
            continue
        found.update(directory.rglob("test_*.py"))
        found.update(directory.rglob("*_test.py"))
    if missing == len(testpaths):
        raise ScanError(
            f"{root}: none of pyproject.toml's testpaths directories exist {testpaths!r} "
            "-- most plausibly the wrong --root, not a repository with zero scan scope."
        )
    return sorted(found)


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying a real `# real-checkout-git-write:
    WAIVED: <reason>` comment token.

    Read through `tokenize` rather than a regex over raw text so the
    marker is only honoured as a genuine comment -- a string literal
    quoting this same text must never silence a finding. Mirrors
    `gitapex_gate_exception_handler_gaps.py`'s own `_waived_lines`
    (`.github/scripts/gitapex_gate_exception_handler_gaps.py:875-894`).

    Raises `ScanError` when `source` will not tokenize as Python -- a
    pytest-discovered test file this gate cannot tokenize cannot be
    trusted to have been scanned correctly either.
    """
    waived: set[int] = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
                waived.add(token.start[0])
    except (tokenize.TokenError, SyntaxError) as exc:
        raise ScanError(f"cannot be tokenized as Python: {exc}") from exc
    return waived


def _violations_in_text(path: str, text: str) -> tuple[list[Finding], list[Finding]]:
    """Grade one already-read file's source, returning `(violations,
    honoured waivers)`."""
    waived_lines = _waived_lines(text)
    violations: list[Finding] = []
    waived: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not _HAZARD_RE.search(line):
            continue
        finding = Finding(path=path, line=lineno, text=line.strip())
        (waived if lineno in waived_lines else violations).append(finding)
    return violations, waived


def _scan(root: Path) -> tuple[list[Finding], list[Finding], int]:
    """Scan every pytest-discovered test file under `root` and return
    `(violations, honoured waivers, files scanned)`."""
    testpaths = read_testpaths(root / "pyproject.toml")
    paths = discover(root, testpaths)
    violations: list[Finding] = []
    waived: list[Finding] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ScanError(f"{path}: cannot be read as UTF-8 text: {exc}") from exc
        relative = str(path.relative_to(root))
        file_violations, file_waived = _violations_in_text(relative, text)
        violations.extend(file_violations)
        waived.extend(file_waived)
    return violations, waived, len(paths)


def find_violations(root: Path) -> list[Finding]:
    """Scan every pytest-discovered test file under `root` and return all
    (non-waived) violations."""
    violations, _waived, _graded = _scan(root)
    return violations


class GateRealCheckoutGitWriteArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. `root` must be an
    existing directory -- mirrors `gitapex_gate_hidden_characters.py`'s
    own `GateHiddenCharactersArgs` exactly."""

    root: Path

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: Path) -> Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 clean, 1 violation(s) found, 2 the scan could not be
    trusted."""
    parser = argparse.ArgumentParser(
        description="Check that no pytest-discovered test file constructs a REPO_ROOT-rooted "
        'path expression that continues into a literal ".git" path segment.'
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to scan (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateRealCheckoutGitWriteArgs(root=args.root)
    except ValidationError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    try:
        violations, waived, graded = _scan(validated.root)
    except ScanError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    for finding in waived:
        print(f"{finding.describe()}: waived inline", file=sys.stderr)

    if violations:
        for finding in violations:
            print(finding.describe(), file=sys.stderr)
        print(
            f"\n{len(violations)} test file line(s) construct a REPO_ROOT-rooted path into a "
            'literal ".git" segment (issue #991) -- writing through this repository\'s own real '
            "checkout this way is not owned by any pytest-xdist worker and survives the test "
            "run. Point the test at a throwaway tmp_path-scoped clone instead, or, for a "
            "genuine read-only need, disclose it inline with "
            "'# real-checkout-git-write: WAIVED: <reason>'.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {graded} pytest-discovered test file(s) carry no REPO_ROOT .git write hazard, "
        f"{len(waived)} inline waiver(s) honoured."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

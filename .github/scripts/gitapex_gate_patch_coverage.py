#!/usr/bin/env python3
"""CI/local gate: a diff-added line inside this repository's own
coverage-tracked source directories must be exercised by a test -- a
local, pre-push equivalent of Codecov's own patch-coverage check.

Issue #1568 (gate-proposal-umbrella, consolidating #1493, #1509, #1539,
#1555, #1703, #1718, #1724, #1862): each of those issues independently
hit the same root cause -- a diff-added or diff-changed line landed with
no covering test, and was only caught after a push, by Codecov's own
CI-only "patch coverage" check. This gate computes the same comparison
locally, before push, wired via `.gitapex/ssot.json`'s `local`/`ci`
planes exactly like this repository's other diff-scoped gates
(`gitapex_gate_function_body_test_coverage.py`,
`gitapex_gate_exception_handler_gaps.py`).

Scope
-----
Any ``.py`` file whose immediate parent directory is exactly one of
`pyproject.toml`'s own `[tool.coverage.run]` `source` directories (the
same list `gitapex_gate_evals_scripts_coverage.py` already reads as the
single source of truth for this repository's coverage-tracked scope),
excluding `test_*.py`/`conftest.py`.

Coverage measurement
---------------------
This gate does not depend on a possibly-stale coverage artifact, and it
does not re-run this repository's full test suite (measured at 3m49s in
a 4-core environment during issue #1568's own implementation, against
this repository's existing 47 wired local gates' combined ~22s -- too
heavy for a pre-push hook). Instead, for each in-scope file this diff
adds lines to, it resolves that file's own corresponding test file(s)
(``tests/test_{stem}.py``, ``tests/test_{stem}_properties.py`` -- the
same convention `gitapex_gate_function_body_test_coverage.py` already
uses) and runs only the union of those test files via `pytest`
(measured at 17s for a 1-file change), reusing this repository's own
`pyproject.toml`-configured `--cov=` scope and writing a fresh coverage
JSON report to compare against. A `--coverage-json` override is
accepted for CI callers that already have a fresh report from their own
prior step, to avoid running the same tests twice in one job.

A source file with added lines but no corresponding test file at all is
graded uncovered outright (no coverage data to consult) -- this is
exactly issue #1493's own "brand-new file's own 0% floor" case,
satisfied automatically rather than as a special-cased branch.

For a file whose test file(s) exist, coverage is graded per line:
``statements = executed_lines | missing_lines`` (from the coverage JSON
report's own per-file entry) gives the set of coverage-measurable
lines; a diff-added line outside that set (a comment, a blank line, a
docstring) is not graded at all -- only a diff-added line that is both
`statements` and NOT `executed_lines` is a violation. This mirrors what
Codecov's own patch-coverage check already measures, at line rather
than branch granularity: a partially-taken branch (issue #1555's own
"unreachable branch" finding) cannot be detected by this comparison and
is a disclosed, un-solved residual risk -- it needs a waiver or
dead-code removal, not a coverage check.

Waiver
------
``# patch-coverage: WAIVED: <reason>`` -- a non-whitespace reason is
mandatory, matched via `tokenize` exactly like this repository's sibling
diff-scoped gates, so the marker is honoured only as a real comment
token. For a per-line finding, the waiver may sit anywhere in the
source file (matching `_waived_lines`'s own file-wide scope, the
simplest correct rule for a line-level finding with no enclosing-scope
concept to anchor narrower). For a whole-file "no test file exists"
finding, the waiver clears it if it appears on any of this diff's own
added lines in that file.

Exit codes
----------
0 clean, 1 violation found, 2 the scan could not be trusted (an
unparseable diff, a pytest run that itself failed, a malformed coverage
report, or a file with an existing test file but no matching coverage
report entry at all -- an ambiguous state, never silently read as
"clean").

Invocation shape
-----------------
Reads a unified diff on stdin (or `--diff <file>`), matching the sibling
diff-scoped gates' own CLI shape: `gitapex_run_base_diff.py -- '*.py'` is
wired as `local_stdin` via `.gitapex/ssot.json`.

Usage::

    git -c core.quotePath=false diff -U0 --no-renames \\
        "$MERGE_BASE" "$HEAD_SHA" -- '*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_patch_coverage.py

    # CI: reuse an already-generated coverage report instead of
    # re-running tests:
    ... | uv run --frozen python3 .github/scripts/gitapex_gate_patch_coverage.py \\
        --coverage-json coverage.json

A bare pipe here masks `git diff`'s own exit status in a non-`pipefail`
shell (issue #1531): add `set -o pipefail` first, or check `git diff`'s
own exit code separately, if the caller must detect an upstream failure
rather than silently grading whatever partial diff reached stdin.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import tokenize
import tomllib
from typing import NamedTuple

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_PYPROJECT = "pyproject.toml"

# Ceiling for the scoped pytest subprocess this gate runs when no
# --coverage-json is given. Generous relative to the 17s measured for a
# 1-file change: several changed files' own test files run together are
# still a small slice of the full suite's own 3m49s.
DEFAULT_PYTEST_TIMEOUT_SECONDS = 900

_PATCH_COVERAGE_GAP = "patch-coverage-gap"

# Matches an inline waiver comment naming this gate; a non-whitespace
# reason is mandatory, matching the sibling diff-scoped gates' own
# waiver-comment vocabulary (see the module docstring's own Waiver
# section for the exact accepted shape -- not restated here as a
# comment, to avoid this literal pattern itself matching as a waiver).
_WAIVER_RE = re.compile(r"#\s*patch-coverage\s*:\s*WAIVED\s*:\s*\S.*", re.IGNORECASE)

_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


class Finding(NamedTuple):
    """One graded violation: a diff-added line (or, for a file with no
    corresponding test file at all, the file itself) with no covering
    test execution."""

    path: str
    line: int
    rule: str
    message: str


def _diff_target_path(raw: str) -> str | None:
    """Return the post-image path named by a `+++ ` line, or None for
    `/dev/null` (a deletion, which adds nothing to grade).

    Identical to the sibling diff-scoped gates' own `_diff_target_path`.
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
    Identical to the sibling diff-scoped gates' own
    `_looks_like_real_header_pair`."""
    source = source_line[4:]
    target = target_line[4:]
    return (source == "/dev/null" or source.startswith("a/")) and (target == "/dev/null" or target.startswith("b/"))


def parse_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff text into ``{post-image path: added line numbers}``.

    Byte-for-byte the same parser the sibling diff-scoped gates each carry
    their own copy of -- see `gitapex_gate_function_body_test_coverage.py`'s
    own module docstring for the full incremental history of why each
    boundary check exists, rather than repeating it a third time here.
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


def read_coverage_sources(pyproject_path: pathlib.Path) -> list[str]:
    """Return `pyproject.toml`'s `[tool.coverage.run]` `source` list --
    the same single source of truth `gitapex_gate_evals_scripts_coverage.py`
    already reads, so this gate's own scope never drifts from that one.

    Raises ``ScanError`` on a missing/unreadable file, invalid TOML, or a
    `source` value that isn't a list of strings.
    """
    try:
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ScanError(f"could not read {pyproject_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ScanError(f"{pyproject_path} is not valid TOML: {exc}") from exc

    try:
        source = data["tool"]["coverage"]["run"]["source"]
    except (KeyError, TypeError) as exc:
        raise ScanError(f"{pyproject_path} has no [tool.coverage.run] source list") from exc
    if not isinstance(source, list) or not source or not all(isinstance(item, str) and item.strip() for item in source):
        raise ScanError(f"{pyproject_path}'s [tool.coverage.run] source must be a non-empty list of non-blank strings")
    return [item.rstrip("/") for item in source]


def in_scope(path: str, sources: list[str]) -> bool:
    """True iff `path`'s immediate parent directory is exactly one of
    `sources` (never a nested-deeper or path-prefix match -- the same
    exact-parent-directory discipline
    `gitapex_gate_evals_scripts_coverage.select_files_in_source` already
    applies, for the identical drift-detection reason), it is a `.py`
    file, and it is not a test file."""
    parent, _, name = path.rpartition("/")
    if parent not in sources or not name.endswith(".py"):
        return False
    return not (name.startswith("test_") or name == "conftest.py")


def _stem(path: str) -> str:
    """Return the source module stem for a diff-relative path, e.g.
    ".github/scripts/gitapex_gate_foo.py" -> "gitapex_gate_foo"."""
    return path.rsplit("/", 1)[-1].removesuffix(".py")


def _test_relative_paths(stem: str) -> tuple[str, str]:
    """The two files this gate accepts as "a corresponding test" for
    source module stem `stem` -- the same two naming precedents
    `gitapex_gate_function_body_test_coverage.py` already establishes."""
    return (f"tests/test_{stem}.py", f"tests/test_{stem}_properties.py")


def _waived_lines(source: str) -> set[int]:
    """Return every line carrying an inline waiver comment, read through
    `tokenize` rather than a regex over raw text so the marker is only
    honoured as a real comment. Identical to the sibling diff-scoped
    gates' own `_waived_lines`."""
    waived: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and _WAIVER_RE.search(token.string):
            waived.add(token.start[0])
    return waived


def resolve_existing_test_files(paths: list[str], root: pathlib.Path) -> dict[str, list[str]]:
    """path -> the subset of its own two candidate test files that
    actually exist on disk, for every path in `paths`."""
    result: dict[str, list[str]] = {}
    for path in paths:
        candidates = _test_relative_paths(_stem(path))
        result[path] = [candidate for candidate in candidates if (root / candidate).is_file()]
    return result


def run_scoped_pytest(
    test_files: list[str], root: pathlib.Path, coverage_json_path: pathlib.Path, timeout: int
) -> None:
    """Run `pytest` scoped to `test_files` only (never this repository's
    full suite), writing a fresh coverage JSON report to
    `coverage_json_path`. Reuses `pyproject.toml`'s own `--cov=`/
    `--cov-branch` configuration via `addopts` -- this call adds only
    `--cov-report=json:<path>`, which pytest-cov accumulates alongside
    `addopts`'s own `--cov-report=term-missing` rather than replacing it.

    Raises `ScanError` on a subprocess failure or a non-clean test run:
    a failing test inside the scoped run makes the resulting coverage
    data untrustworthy (a test that errors before reaching the code
    under test proves nothing about whether that code is covered), so
    this never silently proceeds to grade coverage from a red run.

    Runs with a `COVERAGE_FILE` pointed at a file next to
    `coverage_json_path` rather than the default `.coverage` -- this
    gate's own test suite calls this function from inside a pytest run
    that may itself be measuring coverage under the very same default
    filename, and two concurrent xdist workers each starting their own
    scoped subprocess would otherwise race on that one shared file.
    """
    env = {**os.environ, "COVERAGE_FILE": str(coverage_json_path.parent / ".coverage.patch-coverage")}
    try:
        completed = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "uv",
                "run",
                "--frozen",
                "pytest",
                "-q",
                *test_files,
                f"--cov-report=json:{coverage_json_path}",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as error:
        raise ScanError(f"pytest timed out after {timeout}s while measuring patch coverage") from error
    except (OSError, subprocess.SubprocessError) as error:
        raise ScanError(f"could not run pytest to measure patch coverage: {error}") from error
    if completed.returncode != 0:
        raise ScanError(
            f"pytest exited {completed.returncode} while measuring patch coverage for "
            f"{', '.join(test_files)} -- a failing test makes the resulting coverage data "
            f"untrustworthy; fix the failing test(s) first:\n{completed.stdout}{completed.stderr}"
        )


def load_coverage_json(path: pathlib.Path) -> dict[str, object]:
    """Read and parse a `coverage json` report. Raises `ScanError` on a
    missing/unreadable file, invalid JSON, or a report with no `files`
    object -- a malformed report must never be silently treated as "no
    files, so nothing to check.\""""
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise ScanError(f"could not read coverage report {path}: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ScanError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise ScanError(f"{path}: coverage report has no 'files' object -- was it produced by 'coverage json'?")
    return data


def findings_for_file(
    path: str,
    added: set[int],
    test_files: list[str],
    coverage_data: dict[str, object],
    root: pathlib.Path,
) -> tuple[list[Finding], list[Finding]]:
    """Grade one in-scope file's diff-added lines. Returns
    `(violations, honoured waivers)`.

    A file with no corresponding test file at all is graded uncovered
    outright -- issue #1493's own "brand-new file's own 0% floor" case,
    satisfied automatically. A file with a test file but no matching
    coverage-report entry is an ambiguous state (the test run may not
    have actually imported this module) and raises `ScanError` rather
    than being silently treated as either covered or uncovered.
    """
    try:
        source = (root / path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
    waived_lines = _waived_lines(source)

    if not test_files:
        finding = Finding(
            path,
            min(added),
            _PATCH_COVERAGE_GAP,
            f"{path} has {len(added)} diff-added line(s), but no tests/test_{_stem(path)}.py or "
            f"tests/test_{_stem(path)}_properties.py exists to exercise it",
        )
        return ([], [finding]) if (added & waived_lines) else ([finding], [])

    files_section = coverage_data.get("files")
    file_info = files_section.get(path) if isinstance(files_section, dict) else None
    if not isinstance(file_info, dict):
        raise ScanError(
            f"{path}: has a corresponding test file ({', '.join(test_files)}) but no entry in the "
            "coverage report -- the scoped test run may not have actually imported this module"
        )
    executed_raw = file_info.get("executed_lines")
    missing_raw = file_info.get("missing_lines")
    if not isinstance(executed_raw, list) or not isinstance(missing_raw, list):
        raise ScanError(f"{path}: coverage report entry has no numeric executed_lines/missing_lines")
    executed = set(executed_raw)
    statements = executed | set(missing_raw)
    denom = added & statements
    uncovered = sorted(denom - executed)

    violations: list[Finding] = []
    waived: list[Finding] = []
    for line in uncovered:
        finding = Finding(
            path,
            line,
            _PATCH_COVERAGE_GAP,
            f"{path}:{line} is a diff-added, coverage-measurable line with zero covering test executions",
        )
        (waived if line in waived_lines else violations).append(finding)
    return violations, waived


def find_violations(
    added_by_path: dict[str, set[int]],
    sources: list[str],
    root: pathlib.Path,
    coverage_json: pathlib.Path | None,
    pytest_timeout: int,
) -> tuple[list[Finding], list[Finding], int]:
    """Grade every in-scope file the diff adds lines to.

    Returns `(violations, honoured waivers, files graded)`. When
    `coverage_json` is given, it is used as-is (a CI caller reusing a
    report it already generated); otherwise this function runs a scoped
    `pytest` itself (see `run_scoped_pytest`) against the union of the
    in-scope files' own existing test files -- never this repository's
    full suite.
    """
    in_scope_paths = {path: added for path, added in added_by_path.items() if in_scope(path, sources)}
    if not in_scope_paths:
        return [], [], 0

    test_files_by_path = resolve_existing_test_files(list(in_scope_paths), root)
    all_test_files = sorted({test_file for tests in test_files_by_path.values() for test_file in tests})

    if coverage_json is not None:
        coverage_data = load_coverage_json(coverage_json)
    elif all_test_files:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_json = pathlib.Path(tmp_dir) / "patch-coverage.json"
            run_scoped_pytest(all_test_files, root, tmp_json, pytest_timeout)
            coverage_data = load_coverage_json(tmp_json)
    else:
        coverage_data = {"files": {}}

    violations: list[Finding] = []
    waived: list[Finding] = []
    for path, added in sorted(in_scope_paths.items()):
        file_violations, file_waived = findings_for_file(path, added, test_files_by_path[path], coverage_data, root)
        violations.extend(file_violations)
        waived.extend(file_waived)
    return sorted(set(violations)), sorted(set(waived)), len(in_scope_paths)


class GatePatchCoverageArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. `root` must be an
    existing directory; `coverage_json`, when given, must be an existing
    file -- both get a clear, early error instead of a deeper failure
    surfacing partway through the scan."""

    root: pathlib.Path
    pyproject: pathlib.Path
    coverage_json: pathlib.Path | None
    pytest_timeout: int

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value

    @field_validator("coverage_json")
    @classmethod
    def _coverage_json_must_exist_if_given(cls, value: pathlib.Path | None) -> pathlib.Path | None:
        if value is not None and not value.is_file():
            raise ValueError(f"--coverage-json must name an existing file, got {value}")
        return value


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 clean, 1 violation found, 2 the scan could not be trusted.
    Reads a unified diff from stdin (or `--diff`)."""
    parser = argparse.ArgumentParser(
        description="Check that a diff-added line inside this repository's own coverage-tracked source "
        "directories is exercised by a test, local-equivalent to Codecov's own patch-coverage check. "
        "Reads a unified diff on standard input."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root the diff's paths, pyproject.toml, and tests/ resolve against "
        "(defaults to this checkout).",
    )
    parser.add_argument(
        "--diff",
        type=pathlib.Path,
        help="Read the unified diff from this file instead of standard input.",
    )
    parser.add_argument(
        "--pyproject",
        type=pathlib.Path,
        default=pathlib.Path(DEFAULT_PYPROJECT),
        help=f"Path to pyproject.toml used to derive this gate's scope (default: {DEFAULT_PYPROJECT!r}), "
        "resolved against --root.",
    )
    parser.add_argument(
        "--coverage-json",
        type=pathlib.Path,
        help="Reuse an already-generated 'coverage json' report instead of running a scoped pytest "
        "(e.g. a CI caller that already produced one in an earlier step).",
    )
    parser.add_argument(
        "--pytest-timeout",
        type=int,
        default=DEFAULT_PYTEST_TIMEOUT_SECONDS,
        help=f"Ceiling, in seconds, for the scoped pytest subprocess this gate runs when "
        f"--coverage-json is not given (default: {DEFAULT_PYTEST_TIMEOUT_SECONDS}).",
    )
    args = parser.parse_args(argv)

    root = args.root if args.root.is_absolute() else pathlib.Path.cwd() / args.root
    pyproject = args.pyproject if args.pyproject.is_absolute() else root / args.pyproject
    coverage_json = args.coverage_json
    if coverage_json is not None and not coverage_json.is_absolute():
        coverage_json = root / coverage_json

    try:
        validated = GatePatchCoverageArgs(
            root=root, pyproject=pyproject, coverage_json=coverage_json, pytest_timeout=args.pytest_timeout
        )
    except ValidationError as error:
        for detail in error.errors():
            field = detail["loc"][0] if detail["loc"] else "?"
            print(f"error: --{field}: {detail['msg']}", file=sys.stderr)
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
        added_by_path = parse_added_lines(diff_text)
        sources = read_coverage_sources(validated.pyproject)
        violations, waived, graded = find_violations(
            added_by_path, sources, validated.root, validated.coverage_json, validated.pytest_timeout
        )
    except ScanError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    for finding in waived:
        print(f"{finding.path}:{finding.line}: {finding.rule}: waived inline -- {finding.message}", file=sys.stderr)

    if violations:
        for finding in violations:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.message}", file=sys.stderr)
        print(
            f"\n{len(violations)} diff-added line(s)/file(s) reached by this diff have no covering test "
            "execution (issue #1568). Add a test exercising the missing line(s), or disclose it inline "
            "with '# patch-coverage: WAIVED: <reason>' (anywhere in the file for a missing-test-file "
            "finding, on the specific line for a per-line finding).",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {graded} in-scope file(s) with diff-added lines graded, {len(waived)} inline waiver(s) honoured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""CI gate: every file under each of `pyproject.toml`'s `[tool.coverage.run]`
`source` directories meets a minimum test coverage percentage.

Issue #536 (retrospective for PR #512): `check_dimension_coverage.py`
shipped with its CLI surface (`format_report`/`main`) uncalled by any
test -- 70% file coverage -- and that gap was only caught by a manually
dispatched `/code-review` pass after the PR was already open, not by any
CI gate. `evals/scripts/*.py` had no coverage floor at all: the repo-wide
`pytest --cov` run in `test.yml` already measures per-file coverage (see
`pyproject.toml`'s `--cov=evals/scripts`), it just never asserted a
minimum on what it measured for this directory specifically.

This script was originally that assertion, deliberately narrowed to
`evals/scripts/` alone: a live coverage run at the time found several of
`pyproject.toml`'s other `--cov=` targets (`.github/scripts`, several
`skills/*/scripts`) sitting well below a 90% floor themselves -- some
below the 70% that triggered this issue in the first place. Widening the
gate at that time would have immediately failed CI on pre-existing debt
that PR did not create, so it was scoped narrowly with `--include-glob`
kept as a real CLI parameter (not hardcoded) specifically so a follow-up
could reuse this script unchanged against a wider scope.

Issue #562 is that follow-up. Rather than hand-maintain a second,
independently-drifting copy of `pyproject.toml`'s `--cov=` target list
inside this script, `read_coverage_sources()` reads
`[tool.coverage.run]`'s own `source` list directly (the same list
`pytest-cov`'s `addopts` line already derives its `--cov=` flags from,
by convention -- this script does not read `addopts` itself, since
`[tool.coverage.run] source` is the more directly machine-readable of
the two and is what `coverage json`'s own report is generated against).
One `<source>/*.py` glob is built per source directory
(`source_include_globs()`) and checked in turn, so a future new
`--cov=` target is picked up automatically -- there is no second list
inside this file to fall out of sync. `--include-glob` still accepts an
explicit override (repeatable) for narrower, one-off checks (including
this script's own tests), bypassing `pyproject.toml` entirely when
given.

Reads a `coverage json` report (`coverage json -o coverage.json`, run
after `pytest --cov`), not the `.coverage` SQLite file directly -- the
JSON report's `files.<path>.summary.percent_covered` is coverage.py's own
stable public format, so this script never has to parse the SQLite schema
itself.

A file's per-source inclusion is deliberately shallow: it does not walk a
directory tree itself, it only reads what coverage.py already measured.
If the pytest step's own `--cov=` scope for a given source ever narrows,
this gate would silently see fewer files for that source -- the "zero
files matched" check below is the backstop for that specific drift, one
that fires independently per source directory (not just once overall),
so narrowing any single `--cov=` target's scope is caught without
depending on every *other* target also going empty. That independence
depends on `select_files_in_source()` matching each source by its exact
parent directory rather than a `<source>/*.py` fnmatch glob -- fnmatch's
`*` also matches `/`, so a glob-based match would let a source that is a
path-prefix of another source's directory (e.g. `source = ["evals",
"evals/scripts"]`) silently absorb that other source's files instead of
reporting its own as unmatched.

No test-file exclusion: every one of this gate's `--cov=` targets' own
tests lives under the top-level `tests/` directory (`pyproject.toml`'s
`testpaths`) or, since issue #562 wired it in,
`skills/auditing-agent-product-scope/scripts/` -- never inside a
`--cov=` target itself in a way this gate's globs would pick up as a
second copy needing exclusion. An earlier version carried a
`--exclude-prefix "test_"` flag for this, which would have silently
dropped any real production script merely named `test_*.py` from the
coverage floor with no diagnostic, reintroducing the exact silent-gap
failure mode this gate exists to close. Removed rather than hardened,
since the case it guarded against does not exist in this repository's
layout.

Fail-closed (CLAUDE.md section 4: "an inability to verify is a deny, not
an assume-clean"): a missing, non-UTF-8, or malformed coverage report, an
unreadable or malformed `pyproject.toml`, or a glob (explicit or
`pyproject.toml`-derived) that matches nothing, is an error (exit 2),
never a silent pass -- an empty match set most plausibly means the
coverage report was generated with the wrong scope, which would
otherwise turn this gate into a permanent no-op no one would notice. A
`bool` is deliberately rejected as a `percent_covered` value even though
Python's `bool` is an `int` subclass -- a report that says `true`/`false`
there is malformed, not a 100%/0% score.

Usage::

    coverage json -o coverage.json
    python3 .github/scripts/gate_evals_scripts_coverage.py --coverage-json coverage.json

    # Narrow to one target instead of every pyproject.toml source (repeatable):
    python3 .github/scripts/gate_evals_scripts_coverage.py \
        --coverage-json coverage.json --include-glob "evals/scripts/*.py"

Exit codes:
    0  Every matched file meets the minimum coverage percentage.
    1  At least one matched file is below the minimum.
    2  The coverage report or pyproject.toml is missing/unreadable/
       malformed, or no file matched some include glob at all.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEFAULT_MIN_PERCENT = 90.0
DEFAULT_COVERAGE_JSON = "coverage.json"
DEFAULT_PYPROJECT = "pyproject.toml"


def read_coverage_sources(pyproject_path: str) -> list[str]:
    """Return `pyproject.toml`'s `[tool.coverage.run]` `source` list -- the
    single source of truth this gate's default scope is derived from, so a
    newly added `--cov=` target is covered automatically instead of
    depending on a second hardcoded copy of the list here (issue #562).

    Raises ``ValueError`` on a missing/unreadable file, invalid TOML, or a
    `source` value that isn't a list of strings -- a malformed
    `pyproject.toml` must never be silently treated as "no sources, so
    nothing to check."
    """
    try:
        with Path(pyproject_path).open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ValueError(f"could not read {pyproject_path!r}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{pyproject_path!r} is not valid TOML: {exc}") from exc

    try:
        source = data["tool"]["coverage"]["run"]["source"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{pyproject_path!r} has no [tool.coverage.run] source list"
        ) from exc
    if not isinstance(source, list) or not source or not all(
        isinstance(item, str) and item.strip() for item in source
    ):
        raise ValueError(
            f"{pyproject_path!r}'s [tool.coverage.run] source must be a "
            "non-empty list of non-blank strings"
        )
    return source


def source_include_globs(sources: list[str]) -> list[str]:
    """Turn each coverage source directory into a `<dir>/*.py` fnmatch glob,
    one per source, in the same order as ``sources``."""
    return [f"{source.rstrip('/')}/*.py" for source in sources]


def _files_section(coverage_data: object) -> dict[str, object]:
    """Return ``coverage_data``'s ``files`` object, raising ``ValueError`` on
    a report shape this script cannot interpret. Shared by ``select_files``
    and ``select_files_in_source`` so the same malformed-report diagnostics
    apply to both matching strategies."""
    if not isinstance(coverage_data, dict):
        raise ValueError("coverage report top level is not a JSON object")
    files = coverage_data.get("files")
    if not isinstance(files, dict):
        raise ValueError("coverage report has no 'files' object -- was it produced by 'coverage json'?")
    return files


def _percent_covered(path: str, info: object) -> float:
    """Extract and validate one file entry's ``summary.percent_covered``,
    raising ``ValueError`` on a non-numeric or missing value -- a malformed
    entry must never be silently treated as 0%/100%. Shared by
    ``select_files`` and ``select_files_in_source``."""
    summary = info.get("summary") if isinstance(info, dict) else None
    percent = summary.get("percent_covered") if isinstance(summary, dict) else None
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        raise ValueError(
            f"coverage report entry for {path!r} has no numeric "
            "summary.percent_covered"
        )
    return float(percent)


def select_files(coverage_data: object, include_glob: str) -> dict[str, float]:
    """Return {path: percent_covered} for every file in ``coverage_data``
    (a parsed `coverage json` report) whose path matches ``include_glob``.

    ``fnmatch``-based, so ``*`` matches ``/`` too -- an explicit
    ``--include-glob`` is user-supplied and may deliberately span a
    directory segment (e.g. ``skills/*/scripts/*.py``). ``main()`` only
    uses this for explicit ``--include-glob`` values; its pyproject.toml-
    derived default scope uses ``select_files_in_source`` instead, which
    does not have this cross-directory looseness (see that function's
    docstring for why it matters).

    Raises ``ValueError`` on a report shape this script cannot interpret
    (missing ``files`` section, or a file entry with no numeric
    ``summary.percent_covered``) -- a malformed report must never be
    silently treated as "no files, so nothing to check."
    """
    files = _files_section(coverage_data)
    selected: dict[str, float] = {}
    for path, info in files.items():
        normalized = path.replace("\\", "/")
        if not fnmatch.fnmatch(normalized, include_glob):
            continue
        selected[normalized] = _percent_covered(path, info)
    return selected


def select_files_in_source(coverage_data: object, source: str) -> dict[str, float]:
    """Return {path: percent_covered} for every ``*.py`` file in
    ``coverage_data`` whose immediate parent directory is exactly
    ``source`` (a trailing slash is stripped before comparing).

    Deliberately not ``select_files(coverage_data, f"{source}/*.py")``:
    fnmatch's ``*`` also matches ``/``, so that glob would additionally
    match a file nested one or more directories *deeper* under
    ``source`` -- e.g. ``"evals/*.py"`` would incorrectly also match
    ``"evals/scripts/a.py"``. If a future ``pyproject.toml`` edit ever
    lists a source that is a path-prefix of another source's directory
    (e.g. ``source = ["evals", "evals/scripts"]``), that looseness would
    let the outer source's glob silently swallow the inner source's
    files, defeating the per-source "zero files matched" fail-closed
    check in ``main()`` for whichever source lost its own coverage data
    as a result -- exactly the drift-detection gap issue #562's widened
    scope exists to close. This exact-parent-directory comparison has no
    such gap: a path only belongs to one source, its immediate parent.

    Raises ``ValueError`` on the same malformed-report shapes as
    ``select_files``.
    """
    files = _files_section(coverage_data)
    normalized_source = source.rstrip("/")
    selected: dict[str, float] = {}
    for path, info in files.items():
        normalized = path.replace("\\", "/")
        parent, _, name = normalized.rpartition("/")
        if parent != normalized_source or not name.endswith(".py"):
            continue
        selected[normalized] = _percent_covered(path, info)
    return selected


class EvalsScriptsCoverageArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. `min_percent` is
    constrained to a real percentage (0-100) -- every existing caller
    already passes a value in that range, so this only rejects a
    previously-unvalidated, nonsensical input a future caller could
    otherwise pass through silently."""

    model_config = ConfigDict(extra="forbid")

    coverage_json: str
    include_glob: list[str] | None
    pyproject: str
    min_percent: Annotated[float, Field(ge=0.0, le=100.0)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every file under pyproject.toml's [tool.coverage.run] "
        "source directories meets a minimum test coverage percentage."
    )
    parser.add_argument(
        "--coverage-json", default=DEFAULT_COVERAGE_JSON,
        help=f"Path to a 'coverage json' report (default: {DEFAULT_COVERAGE_JSON!r}).")
    parser.add_argument(
        "--include-glob", action="append", default=None,
        help="fnmatch glob selecting which report entries to check. Repeatable. "
        "When given, bypasses --pyproject entirely. Default (no --include-glob "
        "given): each of pyproject.toml's [tool.coverage.run] source "
        "directories, matched by exact parent directory rather than a glob "
        "(see --pyproject).")
    parser.add_argument(
        "--pyproject", default=DEFAULT_PYPROJECT,
        help=f"Path to pyproject.toml used to derive default --include-glob "
        f"values (default: {DEFAULT_PYPROJECT!r}). Ignored if --include-glob is given.")
    parser.add_argument(
        "--min-percent", type=float, default=DEFAULT_MIN_PERCENT,
        help=f"Minimum percent_covered required per file (default: {DEFAULT_MIN_PERCENT}).")
    args = parser.parse_args(argv)

    try:
        validated = EvalsScriptsCoverageArgs(
            coverage_json=args.coverage_json,
            include_glob=args.include_glob,
            pyproject=args.pyproject,
            min_percent=args.min_percent,
        )
    except ValidationError:
        print(f"error: --min-percent must be between 0 and 100, got {args.min_percent!r}", file=sys.stderr)
        return 2

    # Explicit --include-glob values are matched with the general,
    # fnmatch-based select_files (a user-supplied glob may deliberately
    # span a directory segment). The pyproject.toml-derived default scope
    # instead matches each source directory with select_files_in_source,
    # which cannot let one source's match swallow a nested source's files
    # (see that function's docstring) -- so the two paths use different
    # selectors, not just different glob strings.
    if validated.include_glob:
        targets = validated.include_glob
        display_globs = targets
        use_source_selector = False
    else:
        try:
            targets = read_coverage_sources(validated.pyproject)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        display_globs = source_include_globs(targets)
        use_source_selector = True

    try:
        with Path(validated.coverage_json).open(encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        print(f"error: could not read coverage report {validated.coverage_json!r}: {exc}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"error: {validated.coverage_json!r} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    covered: dict[str, float] = {}
    # strict=True is a real assertion here, not ceremony: source_include_globs
    # returns one glob per source, in order, so a length mismatch would mean
    # the two lists had silently desynchronised.
    for target, display_glob in zip(targets, display_globs, strict=True):
        try:
            matched = (
                select_files_in_source(data, target)
                if use_source_selector
                else select_files(data, target)
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if not matched:
            print(
                f"error: no files matching {display_glob!r} found in "
                f"{validated.coverage_json!r} -- the coverage report may have been "
                "generated with the wrong --cov scope, which would silently "
                "turn this gate into a no-op for that target",
                file=sys.stderr,
            )
            return 2
        covered.update(matched)

    min_str = f"{validated.min_percent:.1f}%"
    offenders: list[tuple[str, float]] = []
    for path in sorted(covered):
        pct = covered[path]
        if pct >= validated.min_percent:
            print(f"PASS: {path} -- {pct:.1f}% (minimum {min_str})")
        else:
            print(f"FAIL: {path} -- {pct:.1f}% (minimum {min_str})")
            offenders.append((path, pct))

    if offenders:
        print(
            f"FAIL: {len(offenders)} of {len(covered)} file(s) matching "
            f"{display_globs!r} are below the {min_str} minimum "
            "coverage threshold -- add tests covering the missing lines "
            "(see 'uv run pytest --cov-report=term-missing') before "
            "merging.",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: all {len(covered)} file(s) matching {display_globs!r} meet the {min_str} minimum")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

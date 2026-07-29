#!/usr/bin/env python3
"""CI gate: every file under `evals/scripts/*.py` meets a minimum test
coverage percentage.

Issue #536 (retrospective for PR #512): `check_dimension_coverage.py`
shipped with its CLI surface (`format_report`/`main`) uncalled by any
test -- 70% file coverage -- and that gap was only caught by a manually
dispatched `/code-review` pass after the PR was already open, not by any
CI gate. `evals/scripts/*.py` had no coverage floor at all: the repo-wide
`pytest --cov` run in `test.yml` already measures per-file coverage (see
`pyproject.toml`'s `--cov=evals/scripts`), it just never asserted a
minimum on what it measured for this directory specifically.

This script is that assertion. It is deliberately narrow to
`evals/scripts/` rather than repo-wide: the other `--cov=` targets in
`pyproject.toml` (`.github/scripts`, several `skills/*/scripts`) are each
either already effectively at or near 100% or have their own established
review cadence: a repo-wide floor is a larger, separate decision this
issue's retrospective did not ask for.

Reads a `coverage json` report (`coverage json -o coverage.json`, run
after `pytest --cov`), not the `.coverage` SQLite file directly -- the
JSON report's `files.<path>.summary.percent_covered` is coverage.py's own
stable public format, so this script never has to parse the SQLite schema
itself.

A file's per-line grep-selected inclusion (`evals/scripts/*.py` by
default) is deliberately shallow: it does not walk a directory tree
itself, it only reads what coverage.py already measured. If the pytest
step's own `--cov=evals/scripts` scope ever narrows, this gate would
silently see fewer files -- the "zero files matched" check below is the
backstop for that specific drift, not full protection against a
scope-narrowing that still leaves one or more files behind.

Fail-closed (CLAUDE.md section 4: "an inability to verify is a deny, not
an assume-clean"): a missing or malformed coverage report, or an
include-glob that matches nothing, is an error (exit 2), never a silent
pass -- an empty match set most plausibly means the coverage report was
generated with the wrong scope, which would otherwise turn this gate into
a permanent no-op no one would notice.

Usage::

    coverage json -o coverage.json
    python3 .github/scripts/gate_evals_scripts_coverage.py --coverage-json coverage.json

Exit codes:
    0  Every matched file meets the minimum coverage percentage.
    1  At least one matched file is below the minimum.
    2  The coverage report is missing/malformed, or no file matched the
       include glob at all.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys

DEFAULT_INCLUDE_GLOB = "evals/scripts/*.py"
DEFAULT_EXCLUDE_PREFIX = "test_"
DEFAULT_MIN_PERCENT = 90.0


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def select_files(
    coverage_data: object, include_glob: str, exclude_prefix: str
) -> dict[str, float]:
    """Return {normalized_path: percent_covered} for every file in
    ``coverage_data`` (a parsed `coverage json` report) whose normalized
    path matches ``include_glob`` and whose basename does not start with
    ``exclude_prefix``.

    Raises ``ValueError`` on a report shape this script cannot interpret
    (missing ``files`` section, or a file entry with no numeric
    ``summary.percent_covered``) -- a malformed report must never be
    silently treated as "no files, so nothing to check."
    """
    if not isinstance(coverage_data, dict):
        raise ValueError("coverage report top level is not a JSON object")
    files = coverage_data.get("files")
    if not isinstance(files, dict):
        raise ValueError("coverage report has no 'files' object -- was it produced by 'coverage json'?")

    selected: dict[str, float] = {}
    for path, info in files.items():
        normalized = _normalize(path)
        name = normalized.rsplit("/", 1)[-1]
        if exclude_prefix and name.startswith(exclude_prefix):
            continue
        if not fnmatch.fnmatch(normalized, include_glob):
            continue
        summary = info.get("summary") if isinstance(info, dict) else None
        percent = summary.get("percent_covered") if isinstance(summary, dict) else None
        if not isinstance(percent, (int, float)):
            raise ValueError(
                f"coverage report entry for {path!r} has no numeric "
                "summary.percent_covered"
            )
        selected[normalized] = float(percent)
    return selected


def find_offenders(
    covered: dict[str, float], min_percent: float
) -> list[tuple[str, float]]:
    return sorted((path, pct) for path, pct in covered.items() if pct < min_percent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every evals/scripts/*.py file meets a minimum test coverage percentage."
    )
    parser.add_argument(
        "--coverage-json", default="coverage.json",
        help="Path to a 'coverage json' report (default: coverage.json).")
    parser.add_argument(
        "--include-glob", default=DEFAULT_INCLUDE_GLOB,
        help=f"fnmatch glob selecting which report entries to check (default: {DEFAULT_INCLUDE_GLOB!r}).")
    parser.add_argument(
        "--exclude-prefix", default=DEFAULT_EXCLUDE_PREFIX,
        help=f"Skip files whose basename starts with this prefix (default: {DEFAULT_EXCLUDE_PREFIX!r}).")
    parser.add_argument(
        "--min-percent", type=float, default=DEFAULT_MIN_PERCENT,
        help=f"Minimum percent_covered required per file (default: {DEFAULT_MIN_PERCENT}).")
    args = parser.parse_args(argv)

    try:
        with open(args.coverage_json, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        print(f"error: could not read coverage report {args.coverage_json!r}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: {args.coverage_json!r} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        covered = select_files(data, args.include_glob, args.exclude_prefix)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not covered:
        print(
            f"error: no files matching {args.include_glob!r} found in "
            f"{args.coverage_json!r} -- the coverage report may have been "
            "generated with the wrong --cov scope, which would silently "
            "turn this gate into a no-op",
            file=sys.stderr,
        )
        return 2

    for path in sorted(covered):
        status = "PASS" if covered[path] >= args.min_percent else "FAIL"
        print(f"{status}: {path} -- {covered[path]:.1f}% (minimum {args.min_percent:.1f}%)")

    offenders = find_offenders(covered, args.min_percent)
    if offenders:
        print(
            f"FAIL: {len(offenders)} of {len(covered)} file(s) matching "
            f"{args.include_glob!r} are below the {args.min_percent:.1f}% "
            "minimum coverage threshold -- add tests covering the missing "
            "lines (see 'uv run pytest --cov-report=term-missing') before "
            "merging.",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: all {len(covered)} file(s) matching {args.include_glob!r} meet the {args.min_percent:.1f}% minimum")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

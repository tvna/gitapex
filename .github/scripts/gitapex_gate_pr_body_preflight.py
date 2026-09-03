#!/usr/bin/env python3
"""Consolidated local PR-body preflight (issue #1725, consolidating #1707
and #1711).

Two different gate scripts -- skill-audit-disclosure (#1707: a stray comma
broke its own disclosure-line regex) and provenance-disclosure (#1711: a
false positive from prose combining two unrelated cue vocabularies) --
were each tripped by the same root cause: no single local command ran
every PR-body-affecting gate together before a
`create_pull_request`/`update_pull_request` call, so an editing session's
own memory of which individual script applied to a given body edit was
the only thing standing between a locally-passing check and a CI-side
failure on a different gate.

This script is that single command. Given one PR-body text, it runs every
PR-body-affecting local check this repository has -- at minimum, per issue
#1725's own Planned ops: skill-audit-disclosure, provenance-disclosure,
and the ASCII/provenance-marker scan (`skills/outward-artifact-preflight`
checks 1 and 2) -- and prints one aggregate PASS/FAIL report, matching
`gitapex_gate_local_preflight.py`'s own reporting convention (every
sub-check's own verdict line, then the captured output of each failure,
then a one-line summary; non-zero exit if anything failed).

**Diff-dependent sub-checks are conditional on `--check-diff`.**
skill-audit-disclosure's own applicability (does this diff touch a
SKILL.md, a design doc, a checker script, a gate?) and
provenance-disclosure's own diff-added-lines corpus both need a base/head
ref pair to compute from `git`. Without `--check-diff`, those two
sub-checks report SKIPPED rather than a false PASS -- skill-audit-
disclosure would otherwise see every applicability flag empty and always
read as trivially satisfied, silently losing the exact coverage issue
#1707 asks for. The two body-only sub-checks (the ASCII-only scan and the
provenance-marker scan) always run regardless, since they need no diff at
all.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_gate_pr_body_preflight.py \\
        --body-file PATH --check-diff BASE_REF HEAD_REF
    printf '%s' "$PR_BODY" | uv run --frozen python3 \\
        .github/scripts/gitapex_gate_pr_body_preflight.py

`--body`/`--body-file` are accepted as aliases of each other (matching
`gitapex_gate_skill_audit_disclosure.py`'s own `--body`/`--body-file`
alias pair) so either spelling documented elsewhere in this repository
keeps working here.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"
SKILL_AUDIT_DISCLOSURE = SCRIPTS_DIR / "gitapex_gate_skill_audit_disclosure.py"
PROVENANCE_DISCLOSURE = SCRIPTS_DIR / "gitapex_gate_provenance_disclosure.py"
EXTRACT_DIFF_ADDED_LINES = SCRIPTS_DIR / "gitapex_extract_diff_added_lines.py"
PROVENANCE_MARKER_SCAN = REPO_ROOT / "skills" / "outward-artifact-preflight" / "scripts" / "gitapex_scan_provenance.py"

# Same pathspec provenance-disclosure-gate.yml itself scopes to (the
# diff-added corpus its own gate script grades) -- see
# .gitapex/ssot.json's "provenance-disclosure" registry entry.
PROVENANCE_DIFF_PATHSPECS = (
    "docs/*.md",
    "docs/**/*.md",
    "evals/*.md",
    "evals/**/*.md",
    "skills/*.md",
    "skills/**/*.md",
)

# Mirrors skills/outward-artifact-preflight/SKILL.md check 2's own
# documented recipe (`LC_ALL=C grep -nP '[^ -~\t]' <file>`), reimplemented
# in Python rather than shelling out: `\t` and the printable-ASCII range
# ` `-`~` (0x20-0x7E) are the only characters excluded from the flag.
_NON_ASCII_RE = re.compile(r"[^ -~\t]")

# Per-subprocess ceiling -- generous for a single PR-body-sized input
# against a handful of already-fast gate scripts, well under
# gitapex_gate_local_preflight.py's own 1800s hang guard for a much larger
# wired set.
SUBPROCESS_TIMEOUT_SECONDS = 120


class PrBodyPreflightError(Exception):
    """Raised when the check itself cannot run at all (a missing sibling
    script, an unreadable body file) -- distinct from a sub-check
    reporting FAIL, which is an ordinary graded verdict."""


@dataclass(frozen=True)
class CheckResult:
    """One sub-check's own outcome. ``skipped`` is distinct from
    ``passed=False``: a diff-dependent sub-check with no ``--check-diff``
    given is neither a verified pass nor a verified failure -- it simply
    did not run, and must not be reported as either."""

    name: str
    passed: bool
    skipped: bool
    output: str

    @property
    def status(self) -> str:
        if self.skipped:
            return "SKIPPED"
        return "PASS" if self.passed else "FAIL"


def _run(argv: tuple[str, ...], stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run one already-fixed argv list from the repo root, with no shell --
    same no-shell, ``errors="replace"`` posture as
    ``gitapex_gate_local_preflight.py``'s own ``_run`` helper, for the same
    reason: a sub-check's own output is not guaranteed to be strict UTF-8,
    and a raised ``UnicodeDecodeError`` here must not crash this whole
    aggregate run past every other sub-check's own report."""
    return subprocess.run(  # noqa: S603
        list(argv),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        input=stdin_text,
        stdin=None if stdin_text is not None else subprocess.DEVNULL,
    )


def check_ascii_only(body_text: str) -> CheckResult:
    """Every line of ``body_text`` must be ASCII-only (plus bare tabs),
    matching ``skills/outward-artifact-preflight``'s own check 2 default.
    Never skipped: needs no diff, only the body text already in hand."""
    hits = [
        (line_no, match.group(0))
        for line_no, line in enumerate(body_text.splitlines(), start=1)
        for match in [_NON_ASCII_RE.search(line)]
        if match is not None
    ]
    if not hits:
        return CheckResult("ascii-only", True, False, "")
    detail = "\n".join(f"line {line_no}: non-ASCII character {char!r}" for line_no, char in hits)
    return CheckResult(
        "ascii-only",
        False,
        False,
        f"FAIL: {len(hits)} non-ASCII character(s) found:\n{detail}\n"
        "Replace each with an ASCII equivalent (see skills/outward-artifact-preflight/SKILL.md check 2), "
        "unless the calling repository documents a different character-set policy.",
    )


def check_provenance_marker_scan(body_path: Path) -> CheckResult:
    """Run ``gitapex_scan_provenance.py`` against the body file. Never
    skipped: needs no diff."""
    if not PROVENANCE_MARKER_SCAN.is_file():
        raise PrBodyPreflightError(f"provenance-marker-scan sibling script not found at {PROVENANCE_MARKER_SCAN}")
    completed = _run((sys.executable, str(PROVENANCE_MARKER_SCAN), "--file", str(body_path)))
    output = f"{completed.stdout}{completed.stderr}".strip()
    return CheckResult("provenance-marker-scan", completed.returncode == 0, False, output)


def check_provenance_disclosure(body_path: Path, diff_added_corpus: str | None) -> CheckResult:
    """Run ``gitapex_gate_provenance_disclosure.py`` against the body file,
    plus the diff-added corpus when ``--check-diff`` supplied one. Runs
    (never skipped) even with no diff -- the body-only half of this check
    is still meaningful on its own, matching the gate's own CLI, which
    accepts ``--body`` with no ``--diff-added`` at all."""
    if not PROVENANCE_DISCLOSURE.is_file():
        raise PrBodyPreflightError(f"provenance-disclosure sibling script not found at {PROVENANCE_DISCLOSURE}")
    argv = [sys.executable, str(PROVENANCE_DISCLOSURE), "--body", str(body_path)]
    diff_added_file: Path | None = None
    try:
        if diff_added_corpus is not None:
            fd, name = tempfile.mkstemp(prefix="gitapex-pr-body-preflight-diff-added-")
            diff_added_file = Path(name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(diff_added_corpus)
            argv.extend(["--diff-added", str(diff_added_file)])
        completed = _run(tuple(argv))
    finally:
        if diff_added_file is not None:
            diff_added_file.unlink(missing_ok=True)
    output = f"{completed.stdout}{completed.stderr}".strip()
    return CheckResult("provenance-disclosure", completed.returncode == 0, False, output)


def check_skill_audit_disclosure(body_path: Path, check_diff: tuple[str, str] | None) -> CheckResult:
    """Run ``gitapex_gate_skill_audit_disclosure.py --check-diff`` against
    the body file. SKIPPED (not PASS) when no ``--check-diff`` was given --
    see this module's own docstring for why a body-only invocation would
    otherwise silently read as trivially satisfied."""
    if check_diff is None:
        return CheckResult(
            "skill-audit-disclosure",
            False,
            True,
            "no --check-diff given; this diff-dependent sub-check did not run "
            "(re-run with --check-diff BASE_REF HEAD_REF for full coverage)",
        )
    if not SKILL_AUDIT_DISCLOSURE.is_file():
        raise PrBodyPreflightError(f"skill-audit-disclosure sibling script not found at {SKILL_AUDIT_DISCLOSURE}")
    base_ref, head_ref = check_diff
    completed = _run(
        (sys.executable, str(SKILL_AUDIT_DISCLOSURE), "--check-diff", base_ref, head_ref, "--body-file", str(body_path))
    )
    output = f"{completed.stdout}{completed.stderr}".strip()
    return CheckResult("skill-audit-disclosure", completed.returncode == 0, False, output)


def build_diff_added_corpus(base_ref: str, head_ref: str) -> str:
    """Compute the same diff-added corpus ``provenance-disclosure-gate.yml``
    feeds its own gate, for the pathspecs that gate scopes to (see
    ``PROVENANCE_DIFF_PATHSPECS``), via ``git diff -U<large>`` piped
    through ``gitapex_extract_diff_added_lines.py`` -- reusing that module
    rather than re-deriving its own paragraph-boundary-preserving logic
    (see that module's own docstring for why a naive re-implementation is
    the wrong approach here).

    Raises ``PrBodyPreflightError`` when the underlying ``git diff`` call
    itself fails (an unresolvable ref, most commonly) -- distinct from a
    clean diff producing zero added lines, which is a normal, non-error
    outcome (returns an empty string).
    """
    if not EXTRACT_DIFF_ADDED_LINES.is_file():
        raise PrBodyPreflightError(f"diff-added-lines sibling script not found at {EXTRACT_DIFF_ADDED_LINES}")
    diff_argv = (
        "git",
        "diff",
        "-U1000000",
        f"{base_ref}...{head_ref}",
        "--",
        *PROVENANCE_DIFF_PATHSPECS,
    )
    diff_completed = _run(diff_argv)
    if diff_completed.returncode != 0:
        raise PrBodyPreflightError(
            f"'git diff {base_ref}...{head_ref}' failed (exit {diff_completed.returncode}): {diff_completed.stderr.strip()}"
        )
    extract_completed = _run((sys.executable, str(EXTRACT_DIFF_ADDED_LINES)), stdin_text=diff_completed.stdout)
    if extract_completed.returncode != 0:
        raise PrBodyPreflightError(
            f"{EXTRACT_DIFF_ADDED_LINES} failed (exit {extract_completed.returncode}): {extract_completed.stderr.strip()}"
        )
    return extract_completed.stdout


def run_all_checks(body_path: Path, body_text: str, check_diff: tuple[str, str] | None) -> list[CheckResult]:
    """Run every sub-check and return all results -- deliberately runs all
    of them even after an earlier one fails, same rationale as
    ``gitapex_gate_local_preflight.py``'s own ``run_checks``: reporting the
    whole set in one pass is the entire point of a consolidated check."""
    diff_added_corpus: str | None = None
    if check_diff is not None:
        diff_added_corpus = build_diff_added_corpus(*check_diff)

    return [
        check_skill_audit_disclosure(body_path, check_diff),
        check_provenance_disclosure(body_path, diff_added_corpus),
        check_ascii_only(body_text),
        check_provenance_marker_scan(body_path),
    ]


def format_report(results: list[CheckResult]) -> str:
    """Same shape as ``gitapex_gate_local_preflight.py``'s own
    ``format_report``: every sub-check's own verdict line, then the
    captured output of each failure (a SKIPPED sub-check's own reason is
    reported the same way, so it is never mistaken for a silent gap), then
    a one-line summary."""
    lines = [f"{result.status}  {result.name}" for result in results]
    failures = [result for result in results if not result.skipped and not result.passed]
    skipped = [result for result in results if result.skipped]
    for failure in failures:
        lines.extend(["", f"--- {failure.name} (FAIL) ---", failure.output or "(no output)"])
    for skip in skipped:
        lines.extend(["", f"--- {skip.name} (SKIPPED) ---", skip.output])
    lines.append("")
    if failures:
        lines.append(f"pr-body preflight: {len(failures)} of {len(results)} check(s) FAILED: ")
        lines[-1] += ", ".join(failure.name for failure in failures)
    else:
        ran = len(results) - len(skipped)
        lines.append(
            f"pr-body preflight: all {ran} run check(s) passed"
            + (f" ({len(skipped)} skipped)" if skipped else "")
            + "."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run every PR-body-affecting local gate this repository has -- skill-audit-disclosure, "
        "provenance-disclosure, an ASCII-only scan, and the provenance-marker scan -- against one PR body, "
        "in one command (issue #1725)."
    )
    parser.add_argument(
        "--body",
        "--body-file",
        dest="body",
        help="Path to the PR body text; reads standard input when omitted.",
    )
    parser.add_argument(
        "--check-diff",
        nargs=2,
        metavar=("BASE_REF", "HEAD_REF"),
        help="Enable the two diff-dependent sub-checks (skill-audit-disclosure's own applicability, and "
        "provenance-disclosure's own diff-added corpus), computed locally via git against this ref pair. "
        "Without this, those two sub-checks report SKIPPED rather than a potentially-false PASS.",
    )
    args = parser.parse_args(argv)

    try:
        body_text = (
            Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        source = args.body if args.body else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
        return 1

    check_diff: tuple[str, str] | None = None
    if args.check_diff:
        check_diff = (args.check_diff[0], args.check_diff[1])

    fd, name = tempfile.mkstemp(prefix="gitapex-pr-body-preflight-body-")
    body_path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body_text)
        try:
            results = run_all_checks(body_path, body_text, check_diff)
        except PrBodyPreflightError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        except subprocess.TimeoutExpired as error:
            print(f"error: a sub-check timed out: {error}", file=sys.stderr)
            return 1
    finally:
        body_path.unlink(missing_ok=True)

    print(format_report(results))
    return 1 if any(not result.skipped and not result.passed for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())

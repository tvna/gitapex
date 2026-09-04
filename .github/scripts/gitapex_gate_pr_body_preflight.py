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

**Only skill-audit-disclosure is conditional on `--check-diff`.** Its own
applicability (does this diff touch a SKILL.md, a design doc, a checker
script, a gate?) needs a base/head ref pair to compute from `git`. Without
`--check-diff`, it reports SKIPPED rather than a false PASS -- it would
otherwise see every applicability flag empty and always read as trivially
satisfied, silently losing the exact coverage issue #1707 asks for. The
other three sub-checks always run regardless of `--check-diff`:
provenance-disclosure's own diff-added-lines corpus is diff-dependent too,
but that sub-check is never skipped outright without one -- it runs in a
body-only mode instead, still meaningful on its own (matching that gate's
own CLI, which likewise accepts `--body` with no `--diff-added` at all).
The two purely body-only sub-checks (the ASCII-only scan and the
provenance-marker scan) need no diff at all and always run the same way
either way.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_gate_pr_body_preflight.py \\
        --body-file PATH --check-diff BASE_REF HEAD_REF
    printf '%s' "$PR_BODY" | uv run --frozen python3 \\
        .github/scripts/gitapex_gate_pr_body_preflight.py

A bare pipe here masks `printf`'s own exit status in a non-`pipefail`
shell (issue #1531) -- harmless for a literal `printf` producer, which
cannot itself fail in ordinary use, but add `set -o pipefail` first if
this recipe's producer is ever swapped for a command that can.

`--body`/`--body-file` are accepted as aliases of each other (matching
`gitapex_gate_skill_audit_disclosure.py`'s own `--body`/`--body-file`
alias pair) so either spelling documented elsewhere in this repository
keeps working here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"
SKILL_AUDIT_DISCLOSURE = SCRIPTS_DIR / "gitapex_gate_skill_audit_disclosure.py"
PROVENANCE_DISCLOSURE = SCRIPTS_DIR / "gitapex_gate_provenance_disclosure.py"
EXTRACT_DIFF_ADDED_LINES = SCRIPTS_DIR / "gitapex_extract_diff_added_lines.py"
PROVENANCE_MARKER_SCAN = REPO_ROOT / "skills" / "outward-artifact-preflight" / "scripts" / "gitapex_scan_provenance.py"
PYTHON_PRECONDITION_CHECKER = REPO_ROOT / "hooks" / "gitapex_check_python_precondition.py"
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"

# Every sub-check name run_all_checks can produce, for --skip's own CLI
# validation -- kept as a plain tuple (not derived from CheckResult
# instances, which do not exist until a check actually runs) so an
# unrecognized --skip value is rejected before any sub-check starts,
# rather than silently matching nothing.
SUB_CHECK_NAMES = ("skill-audit-disclosure", "provenance-disclosure", "ascii-only", "provenance-marker-scan")

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

# Per-subprocess ceiling. Bounded by hooks/check-pr-body-preflight.sh's
# own 30s harness-level PreToolUse timeout (hooks/hooks.json), not by
# gitapex_gate_local_preflight.py's much larger wired-gate set: that
# hook's own wiring (--skip skill-audit-disclosure, --check-diff given)
# invokes _run sequentially up to FOUR times in one call -- two inside
# build_diff_added_corpus (git diff, then gitapex_extract_diff_added_lines.py)
# plus one each for check_provenance_disclosure and
# check_provenance_marker_scan -- so a per-subprocess ceiling anywhere
# near 30s/4 would starve this module's own graceful "a sub-check timed
# out" handling of any chance to run before the harness kills the whole
# hook process first (an initial 120s value, then an under-corrected 8s
# value that could still sum to 32s across those four calls, were both
# found by an independent adversarial review of this issue's own
# implementation). 5s * 4 = 20s leaves comfortable headroom under the
# hook's own 30s budget for jq/git/interpreter-startup overhead, while
# still generous over these already-fast scripts' normal sub-second
# runtime.
SUBPROCESS_TIMEOUT_SECONDS = 5

# _missing_packages_report's own dedicated timeout -- see its own call
# site comment for why this needs to run longer than SUBPROCESS_TIMEOUT_
# SECONDS. 30s comfortably exceeds hooks/gitapex_check_python_
# precondition.py's own PROBE_TIMEOUT_SECONDS=10s per required package,
# for a small handful of declared packages, without competing with the
# hook's own 30s budget (this call is never part of that sequential
# chain).
PRECONDITION_PROBE_TIMEOUT_SECONDS = 30


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


def _run(
    argv: tuple[str, ...], stdin_text: str | None = None, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    """Run one already-fixed argv list from the repo root, with no shell --
    same no-shell, ``errors="replace"`` posture as
    ``gitapex_gate_local_preflight.py``'s own ``_run`` helper, for the same
    reason: a sub-check's own output is not guaranteed to be strict UTF-8,
    and a raised ``UnicodeDecodeError`` here must not crash this whole
    aggregate run past every other sub-check's own report.

    ``timeout=None`` (the default) resolves to ``SUBPROCESS_TIMEOUT_SECONDS``
    *read at call time*, not baked in as a literal default-argument value --
    a plain ``timeout: float = SUBPROCESS_TIMEOUT_SECONDS`` default would
    freeze that module global's value at function-definition time, silently
    breaking any test that monkeypatches ``SUBPROCESS_TIMEOUT_SECONDS``
    afterward (found by an independent adversarial review of this issue's
    own implementation, live-confirmed: ``_run.__defaults__`` stayed the
    original value after monkeypatching the module attribute). Pass an
    explicit ``timeout`` to override for a call site that is never part of
    the hook-wired sequential-call chain that constant is sized against --
    see ``_missing_packages_report``, whose own call needs longer than that
    ceiling to let ``gitapex_check_python_precondition.py``'s own slower
    ``PROBE_TIMEOUT_SECONDS`` finish gracefully."""
    return subprocess.run(  # noqa: S603
        list(argv),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        timeout=SUBPROCESS_TIMEOUT_SECONDS if timeout is None else timeout,
        input=stdin_text,
        stdin=None if stdin_text is not None else subprocess.DEVNULL,
    )


@contextmanager
def _temp_text_file(prefix: str, text: str) -> Iterator[Path]:
    """Write ``text`` to a new temp file under ``prefix`` and yield its
    path, unlinking it on exit regardless of how the ``with`` block ends.
    Factors out the mkstemp-write-unlink shape both ``main``'s own body
    file and ``check_provenance_disclosure``'s own diff-added file need,
    rather than duplicating the same handful of lines twice in this one
    module."""
    fd, name = tempfile.mkstemp(prefix=prefix)
    path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        yield path
    finally:
        path.unlink(missing_ok=True)


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
    if diff_added_corpus is not None:
        with _temp_text_file("gitapex-pr-body-preflight-diff-added-", diff_added_corpus) as diff_added_file:
            argv.extend(["--diff-added", str(diff_added_file)])
            completed = _run(tuple(argv))
    else:
        completed = _run(tuple(argv))
    output = f"{completed.stdout}{completed.stderr}".strip()
    return CheckResult("provenance-disclosure", completed.returncode == 0, False, output)


def _registry_required_packages(gate_id: str) -> list[str]:
    """Read ``gate_id``'s own ``preconditions.requires_python_packages``
    from the live ``.gitapex/ssot.json`` registry -- e.g.
    ``skill-audit-disclosure``'s own ``pydantic`` dependency, transitively
    needed by its ``--check-diff`` mode's ``gitapex_compute_skill_audit_flags``
    import. Returns an empty list (never raises) when the registry is
    unreadable, malformed, or names no such gate: this probe is a
    best-effort early warning, not itself a source of truth the caller
    should treat as authoritative -- a missing dependency still surfaces,
    just less specifically, once the wrapped gate script's own import
    fails."""
    # Not routed through _gitapex_schema_validation.load_json_or_raise
    # (which pulls in jsonschema): this script is deliberately stdlib-only
    # and self-contained, matching gitapex_gate_provenance_disclosure.py's
    # own documented .github/scripts/*.py convention -- adding an
    # undeclared, unguarded third-party import here would reintroduce the
    # exact unlabeled-ImportError-crash defect class _missing_packages_report
    # exists to prevent, for a package this gate's own registry entry does
    # not even declare a precondition for.
    try:
        registry = json.loads(SSOT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(registry, dict):
        return []
    for gate in registry.get("gates", []):
        if isinstance(gate, dict) and gate.get("id") == gate_id:
            packages = gate.get("preconditions", {}).get("requires_python_packages", [])
            return packages if isinstance(packages, list) else []
    return []


def _missing_packages_report(gate_id: str) -> str | None:
    """Return a human-readable FAIL message naming any of ``gate_id``'s own
    registered required Python packages that ``sys.executable`` cannot
    import, or ``None`` when every required package is importable (or none
    are declared, or the precondition checker itself is unavailable --
    fails open on the *probe*, matching
    ``hooks/check-pr-skill-audit-disclosure.sh``'s own tier-1 precondition
    check: an unprobable precondition is not itself evidence of a missing
    dependency, and the wrapped gate script's own import failure is still
    the fail-closed backstop if this probe cannot run).

    Reuses ``hooks/gitapex_check_python_precondition.py`` (issue #1566)
    rather than re-deriving its own separate-subprocess-per-module probe
    logic -- the same script `hooks/check-pr-skill-audit-disclosure.sh`'s
    own tier 1 already calls for the identical reason (issue #1566, closes
    #1547(a)): a missing dependency previously crashed a bare gate
    invocation with an unlabeled ``ImportError``, silently misread as an
    unrelated failure rather than a clear "install this" message.
    """
    required = _registry_required_packages(gate_id)
    if not required or not PYTHON_PRECONDITION_CHECKER.is_file():
        return None
    # `--` before the package names, same as hooks/check-pr-skill-audit-
    # disclosure.sh's own tier-1 call to this identical script (issue
    # #1566's own fix): without it, argparse's `nargs="*"` would read a
    # future hyphen-leading package name as an option rather than a
    # positional value -- the same defeat-tested defect class that fix
    # already closed for the sibling hook, found again here by an
    # independent adversarial review of this issue's own implementation.
    # A longer, dedicated timeout rather than the shared
    # SUBPROCESS_TIMEOUT_SECONDS: this call (only reachable from
    # check_skill_audit_disclosure, always --skip'd by the hook-wired
    # path -- see run_all_checks's own docstring) never competes for the
    # hook's own 30s budget, but hooks/gitapex_check_python_precondition.py
    # probes each required package with its own PROBE_TIMEOUT_SECONDS=10s,
    # sequentially -- a shorter outer timeout here would cut that probe off
    # before its own graceful degrade could report a slow-but-genuine
    # import, misreporting it as "a sub-check timed out" instead (found by
    # an independent adversarial review of this issue's own
    # implementation).
    completed = _run(
        (sys.executable, str(PYTHON_PRECONDITION_CHECKER), "--", *required), timeout=PRECONDITION_PROBE_TIMEOUT_SECONDS
    )
    if completed.returncode == 0:
        return None
    output = f"{completed.stdout}{completed.stderr}".strip()
    return (
        f"FAIL: this sub-check's own dependencies are not importable by {sys.executable}: {output}. "
        "Run 'uv sync --group dev' to install them, then re-run this preflight."
    )


def check_skill_audit_disclosure(body_path: Path, check_diff: tuple[str, str] | None) -> CheckResult:
    """Run ``gitapex_gate_skill_audit_disclosure.py --check-diff`` against
    the body file. SKIPPED (not PASS) when no ``--check-diff`` was given --
    see this module's own docstring for why a body-only invocation would
    otherwise silently read as trivially satisfied.

    Probes this gate's own registered Python-package precondition
    (``_missing_packages_report``) before invoking it: without this, a
    missing ``pydantic`` surfaced only as a generic, easy-to-misread
    ``FAIL`` from the wrapped gate script's own crashed import -- the exact
    defect issue #1566/#1547(a) already fixed once for
    ``hooks/check-pr-skill-audit-disclosure.sh``'s own tier 1, reintroduced
    here by wrapping that same gate without carrying the fix over."""
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
    missing_packages_report = _missing_packages_report("skill-audit-disclosure")
    if missing_packages_report is not None:
        return CheckResult("skill-audit-disclosure", False, False, missing_packages_report)
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


# The exact exception scope gitapex_gate_local_preflight.py's own
# run_check already isolates a wired gate against (any way a subprocess
# call can fail to produce a real verdict -- a missing executable
# (OSError/FileNotFoundError), a bad argument (ValueError), or a
# subprocess-level failure (SubprocessError, of which TimeoutExpired is a
# subclass) -- becomes a FAIL, never a crash), plus this module's own
# PrBodyPreflightError for a sibling script genuinely missing. _isolated
# below originally caught only PrBodyPreflightError/TimeoutExpired, a
# narrower scope than the run_check comparison its own docstring drew --
# e.g. build_diff_added_corpus's bare `git diff` subprocess call raised an
# uncaught FileNotFoundError if git itself were ever missing from PATH,
# crashing this whole aggregate run past every other sub-check's own
# result, the exact defect class _isolated exists to prevent -- found by
# an independent adversarial review of this issue's own implementation.
_ISOLATED_EXCEPTIONS = (
    PrBodyPreflightError,
    subprocess.TimeoutExpired,
    OSError,
    ValueError,
    subprocess.SubprocessError,
)


def _error_result(name: str, error: BaseException) -> CheckResult:
    """Convert one caught exception (see ``_ISOLATED_EXCEPTIONS``) into a
    failing ``CheckResult`` for ``name`` -- shared by ``_isolated`` and
    ``run_all_checks``'s own ``diff_added_corpus`` build, which needs the
    identical conversion but cannot itself go through ``_isolated``
    (``build_diff_added_corpus`` returns ``str``, not ``CheckResult``)."""
    if isinstance(error, subprocess.TimeoutExpired):
        return CheckResult(name, False, False, f"error: a sub-check timed out: {error}")
    return CheckResult(name, False, False, f"error: {error}")


def _isolated(name: str, run_check: Callable[[], CheckResult]) -> CheckResult:
    """Run one sub-check, converting any of ``_ISOLATED_EXCEPTIONS`` into a
    failing ``CheckResult`` for ``name`` instead of letting it propagate
    out of ``run_all_checks`` and abort every other sub-check -- the same
    per-check isolation ``gitapex_gate_local_preflight.py``'s own
    ``run_check`` already applies. Before this helper existed, one
    sub-check's own setup failure (e.g. an unresolvable ``--check-diff``
    ref) silently lost every other sub-check's result too -- direct
    contradiction of this module's own docstring, which promises the whole
    set always reports, found by an independent adversarial review of this
    issue's own implementation."""
    try:
        return run_check()
    except _ISOLATED_EXCEPTIONS as error:
        return _error_result(name, error)


def run_all_checks(
    body_path: Path, body_text: str, check_diff: tuple[str, str] | None, skip: frozenset[str] = frozenset()
) -> list[CheckResult]:
    """Run every sub-check not named in ``skip`` and return all results --
    deliberately runs all of them even after an earlier one fails, same
    rationale as ``gitapex_gate_local_preflight.py``'s own ``run_checks``:
    reporting the whole set in one pass is the entire point of a
    consolidated check. Every sub-check dispatch below goes through
    ``_isolated`` so one sub-check's own setup failure never costs the
    other three their own results.

    ``skip`` exists for exactly one caller today:
    ``hooks/check-pr-body-preflight.sh`` passes
    ``--skip skill-audit-disclosure`` because
    ``hooks/check-pr-skill-audit-disclosure.sh`` already wraps that same
    gate as its own PreToolUse hook on the identical matchers -- without
    this, both hooks independently recomputed the identical
    skill-audit-disclosure verdict (including a duplicated
    ``git merge-base`` resolution) on every single
    ``create_pull_request``/``update_pull_request`` call, doubling that
    sub-check's own latency for no additional coverage. This CLI's own
    default (``skip`` empty) still runs all four when invoked directly --
    the single-command convenience issue #1725 asks for is unaffected;
    only the hook-wired path narrows.
    """
    diff_added_corpus: str | None = None
    diff_added_corpus_error: CheckResult | None = None
    if check_diff is not None and "provenance-disclosure" not in skip:
        try:
            diff_added_corpus = build_diff_added_corpus(*check_diff)
        except _ISOLATED_EXCEPTIONS as error:
            diff_added_corpus_error = _error_result("provenance-disclosure", error)

    checks: list[CheckResult] = []
    if "skill-audit-disclosure" not in skip:
        checks.append(_isolated("skill-audit-disclosure", lambda: check_skill_audit_disclosure(body_path, check_diff)))
    if "provenance-disclosure" not in skip:
        if diff_added_corpus_error is not None:
            checks.append(diff_added_corpus_error)
        else:
            checks.append(
                _isolated("provenance-disclosure", lambda: check_provenance_disclosure(body_path, diff_added_corpus))
            )
    if "ascii-only" not in skip:
        checks.append(check_ascii_only(body_text))
    if "provenance-marker-scan" not in skip:
        checks.append(_isolated("provenance-marker-scan", lambda: check_provenance_marker_scan(body_path)))
    return checks


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
        help="Enable skill-audit-disclosure's own applicability check and provenance-disclosure's own "
        "diff-added corpus, both computed locally via git against this ref pair. Without this, "
        "skill-audit-disclosure reports SKIPPED rather than a potentially-false PASS; provenance-disclosure "
        "still runs, in a body-only mode.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        choices=SUB_CHECK_NAMES,
        metavar="CHECK_NAME",
        help="Skip a named sub-check (repeatable). For a caller that already wraps a given check some other "
        "way (e.g. a separate PreToolUse hook), avoiding a redundant re-run of it here.",
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

    with _temp_text_file("gitapex-pr-body-preflight-body-", body_text) as body_path:
        # run_all_checks isolates every sub-check's own PrBodyPreflightError/
        # subprocess.TimeoutExpired internally (see _isolated) so this
        # try/except is now a defensive backstop, not the primary path --
        # kept in case a future sub-check is added without going through
        # that same isolation.
        try:
            results = run_all_checks(body_path, body_text, check_diff, frozenset(args.skip))
        except PrBodyPreflightError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        except subprocess.TimeoutExpired as error:
            print(f"error: a sub-check timed out: {error}", file=sys.stderr)
            return 1

    print(format_report(results))
    return 1 if any(not result.skipped and not result.passed for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())

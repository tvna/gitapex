#!/usr/bin/env python3
"""One consolidated local pre-push / pre-PR-open gate runner (issue #876).

This repository enforces 36 registered deterministic gates. Before this
script existed, roughly half of them had a perfectly good working-tree-only
invocation and yet ran *only* as separate CI jobs, so an agent preparing a
PR discovered gaps one CI job at a time on an already-open PR -- push, wait,
read one red check, fix, push again. Issue #876 records that same proposal
being independently re-raised and left unresolved across #707, #622, #616
(twice) and #670.

``python3 .github/scripts/gitapex_local_preflight.py`` runs every such gate
in one pass and prints one aggregate verdict.

**The wired set is discovered, never hardcoded here.** ``.gitapex/ssot.json``
is already this repository's registry of its own gates; issue #876's third
acceptance criterion asks that a growing set of checks stay wired without
manual upkeep, reusing that registry rather than a hand-maintained list in
this file. A gate is run here when, and only when, its ``planes`` array
contains ``"local"``, and it is run with exactly the argv its own
``local_invocation`` field declares. This module contains no gate names at
all: adding ``"local"`` + ``local_invocation`` to a registry entry wires a
new gate in with no edit here, and removing them unwires it.

**An unwired gate is a recorded decision, not an invisible gap.**
``.gitapex/ssot.schema.json``'s own if/then/else makes ``local_invocation``
required exactly when ``planes`` contains ``"local"``, and ``local_exclusion``
-- prose saying *why* there is no working-tree form -- required exactly when
it does not. A new gate therefore cannot land in the registry without one or
the other, and ``gitapex_scan_ssot_schema.py`` (itself one of the gates this
runner runs) fails the build if it does. That is the drift-test branch issue
#876's third criterion explicitly allows, and it is what keeps the 21
currently-excluded gates readable as deliberate exclusions rather than as
coverage this runner silently lost.

**The one input provider, and why there is only one.** Most wired gates read
the working tree themselves and need no input. ``exception-handler-gap``
instead reads a unified diff on standard input, so a gate may also declare
``local_stdin``: a second argv whose standard output is piped into the
gate's. That is the whole provider vocabulary -- deliberately not a
templating language over the diff. Six other registered gates
(``gitignore-pattern-test-coverage``, ``routine-scope-enforcement``,
``skill-rename-lifecycle``, ``skill-branch-fixture-coverage``,
``split-fixture-coverage``, ``transfer-check-disclosure``) take *arguments*
derived from the diff in six mutually incompatible shapes; each would need
its own bespoke provider, so each carries a ``local_exclusion`` naming that
missing provider by name instead of a half-working invocation. They are a
known, disclosed follow-up, not a claim this runner already covers them.

**Failure is always loud.** A gate whose command cannot be found, times out,
or whose ``local_stdin`` producer itself fails is reported as a FAIL with
the underlying error, never skipped and never counted as a pass -- a runner
that silently drops a check it could not start is strictly worse than no
runner, because it converts a real gap into a green verdict. The aggregate
exit code is non-zero if any single wired gate fails for any of those
reasons.

**Known limits, disclosed rather than solved:**

- Gates run **sequentially**, in registry-id order, for legible output on a
  terminal. ``mypy-type-check`` and ``cyclomatic-complexity-floor`` dominate
  the wall clock; parallelism was not added because interleaved failure
  output from eight concurrent subprocesses is the thing this runner exists
  to avoid.
- ``local_stdin`` producers that reference ``origin/main`` (today:
  ``exception-handler-gap``) need that ref to exist locally. In a checkout
  without it the producer fails and that one gate reports FAIL with git's
  own message; the other gates still run and still report.
- This grades **committed** state (``HEAD`` and the working tree as it is on
  disk), not a staged index. It is a pre-push runner, not a second
  pre-commit hook -- ``.pre-commit-config.yaml`` already owns that plane.

Run standalone: ``python3 .github/scripts/gitapex_local_preflight.py``
(exit 1 if any wired gate fails, exit 0 when all pass), ``--list`` to print
the wired set without running anything, or via the pytest gate in
``tests/test_gitapex_local_preflight.py``.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from typing import TextIO

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"

# Ceiling for one gate's own subprocess. Sized against the slowest wired
# gate rather than picked as a round number: mypy-type-check shells out to
# .github/workflows/test.yml's own eight per-directory mypy groups, whose CI
# job carries `timeout-minutes: 10`, and gitapex_run_precommit_mypy.py
# already applies that same 600 s ceiling per group. A gate hung past this
# fails loudly instead of blocking a contributor's push indefinitely.
DEFAULT_TIMEOUT_SECONDS = 900

# Registry plane that marks a gate as having a working-tree-only form -- see
# .gitapex/ssot.schema.json's `planes` description.
LOCAL_PLANE = "local"


class PreflightRegistryError(Exception):
    """``.gitapex/ssot.json`` could not be read as UTF-8, parsed as JSON, or
    carries a ``gates`` entry whose local-plane fields are not the shape the
    schema requires -- exit 1 with a message, never an uncaught traceback.
    Distinct from a *gate* failing, which is an ordinary non-zero verdict."""


@dataclass(frozen=True)
class LocalCheck:
    """One wired gate: the registry id it came from, the argv to run, and
    optionally the argv whose stdout feeds its standard input."""

    gate_id: str
    argv: tuple[str, ...]
    stdin_argv: tuple[str, ...] | None = None


@dataclass(frozen=True)
class CheckResult:
    """One wired gate's outcome. ``returncode`` is ``None`` when the gate's
    command never ran to completion at all (not found, timed out, or its
    ``local_stdin`` producer failed first) -- a case that still counts as a
    failure, never as a skip."""

    gate_id: str
    passed: bool
    returncode: int | None
    output: str

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


def _argv_or_raise(gate_id: str, field: str, value: object) -> tuple[str, ...]:
    """Normalize a registry argv field, rejecting every shape the schema
    forbids rather than trusting it. ``.gitapex/ssot.json`` is repository-
    owned and schema-gated, but this runner hands these values straight to
    :func:`subprocess.run`, so a non-list, an empty list, or a non-string
    element is refused here with the offending gate named instead of
    surfacing as a TypeError from deep inside subprocess."""
    if not isinstance(value, list) or not value:
        raise PreflightRegistryError(f"{gate_id}: {field} must be a non-empty array, got {value!r}")
    for element in value:
        if not isinstance(element, str) or not element:
            raise PreflightRegistryError(f"{gate_id}: {field} must contain only non-empty strings, got {element!r}")
    return tuple(value)


def load_local_checks(ssot_path: pathlib.Path = SSOT_PATH) -> list[LocalCheck]:
    """Every gate in the registry whose ``planes`` contains ``"local"``,
    sorted by gate id for deterministic output and reproducible ordering
    between runs. Raises PreflightRegistryError -- never returns a silently
    short list -- when the registry cannot be read or parsed at all, since
    an empty result and an unreadable registry would otherwise be
    indistinguishable to a caller reading only the exit code."""
    try:
        raw = ssot_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise PreflightRegistryError(f"{ssot_path}: cannot be read as UTF-8: {error}") from error
    try:
        instance = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PreflightRegistryError(f"{ssot_path}: cannot be parsed as JSON: {error}") from error
    if not isinstance(instance, dict) or not isinstance(instance.get("gates"), list):
        raise PreflightRegistryError(f"{ssot_path}: no 'gates' array at the document root")

    checks: list[LocalCheck] = []
    for gate in instance["gates"]:
        if not isinstance(gate, dict):
            raise PreflightRegistryError(f"{ssot_path}: gates[] contains a non-object entry: {gate!r}")
        planes = gate.get("planes")
        if not isinstance(planes, list) or LOCAL_PLANE not in planes:
            continue
        gate_id = gate.get("id")
        if not isinstance(gate_id, str) or not gate_id:
            raise PreflightRegistryError(f"{ssot_path}: a local-plane gate has no usable 'id': {gate!r}")
        stdin_raw = gate.get("local_stdin")
        checks.append(
            LocalCheck(
                gate_id=gate_id,
                argv=_argv_or_raise(gate_id, "local_invocation", gate.get("local_invocation")),
                stdin_argv=None if stdin_raw is None else _argv_or_raise(gate_id, "local_stdin", stdin_raw),
            )
        )
    return sorted(checks, key=lambda check: check.gate_id)


def _run(
    argv: tuple[str, ...], repo_root: pathlib.Path, timeout: int, stdin_text: str | None
) -> subprocess.CompletedProcess[str]:
    """Run one already-validated argv list from the repository root, with no
    shell. S603 is waived for the same reason gitapex_run_precommit_mypy.py
    waives it: a list argv, never a shell string, and the executable is
    intentionally resolved from PATH because `uv`/`git` live in different
    absolute locations across the three environments this has to work in (a
    contributor's machine, the nix devShell, and a GitHub runner)."""
    return subprocess.run(  # noqa: S603
        list(argv),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        input=stdin_text,
    )


def run_check(
    check: LocalCheck, repo_root: pathlib.Path = REPO_ROOT, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> CheckResult:
    """Run one wired gate and return its verdict. Every way the command can
    fail to produce a real exit code -- a missing executable, a timeout, an
    OSError from the spawn itself, or a ``local_stdin`` producer that failed
    first -- becomes a FAIL carrying the underlying error text, never a skip
    and never a pass."""
    stdin_text: str | None = None
    if check.stdin_argv is not None:
        try:
            producer = _run(check.stdin_argv, repo_root, timeout, None)
        except (OSError, subprocess.SubprocessError) as error:
            return CheckResult(check.gate_id, False, None, f"local_stdin producer failed to run: {error}")
        if producer.returncode != 0:
            return CheckResult(
                check.gate_id,
                False,
                None,
                f"local_stdin producer {' '.join(check.stdin_argv)} exited "
                f"{producer.returncode}:\n{producer.stderr.strip()}",
            )
        stdin_text = producer.stdout

    try:
        completed = _run(check.argv, repo_root, timeout, stdin_text)
    except subprocess.TimeoutExpired:
        return CheckResult(check.gate_id, False, None, f"timed out after {timeout}s")
    except (OSError, subprocess.SubprocessError) as error:
        return CheckResult(check.gate_id, False, None, f"failed to run: {error}")
    output = f"{completed.stdout}{completed.stderr}".strip()
    return CheckResult(check.gate_id, completed.returncode == 0, completed.returncode, output)


def run_checks(
    checks: list[LocalCheck],
    repo_root: pathlib.Path = REPO_ROOT,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    progress: TextIO | None = None,
) -> list[CheckResult]:
    """Run every wired gate, in order, and return all results. Deliberately
    runs all of them even after the first failure: reporting the whole set in
    one pass is the entire point of this runner -- stopping at the first red
    would reproduce the one-CI-job-at-a-time loop issue #876 exists to
    close. When ``progress`` is given, a transient ``[n/total]`` line is
    written to it as each gate finishes, so a contributor sees movement
    during the minutes mypy takes rather than a silent terminal; the
    authoritative verdict is still format_report's, on stdout."""
    results: list[CheckResult] = []
    for index, check in enumerate(checks, start=1):
        result = run_check(check, repo_root, timeout)
        results.append(result)
        if progress is not None:
            print(f"[{index}/{len(checks)}] {check.gate_id} ... {result.status}", file=progress, flush=True)
    return results


def format_report(results: list[CheckResult]) -> str:
    """The aggregate verdict: every gate's own pass/fail line, then the
    captured output of each failing gate, then a one-line summary. A passing
    gate's output is dropped on purpose -- eight "OK: ..." banners bury the
    one line that matters."""
    lines = [f"{result.status}  {result.gate_id}" for result in results]
    failures = [result for result in results if not result.passed]
    for failure in failures:
        detail = failure.output or "(no output)"
        code = "did not complete" if failure.returncode is None else f"exit {failure.returncode}"
        lines.extend(["", f"--- {failure.gate_id} ({code}) ---", detail])
    lines.append("")
    if failures:
        lines.append(f"local preflight: {len(failures)} of {len(results)} gate(s) FAILED: ")
        lines[-1] += ", ".join(failure.gate_id for failure in failures)
    else:
        lines.append(f"local preflight: all {len(results)} wired gate(s) passed.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--ssot-path",
        type=pathlib.Path,
        default=SSOT_PATH,
        help="Gate registry to discover the wired set from (defaults to this checkout's .gitapex/ssot.json).",
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Working directory each gate is run from (defaults to this checkout).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-gate subprocess ceiling (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the wired gate set and its argv, then exit 0 without running anything.",
    )
    args = parser.parse_args(argv)

    try:
        checks = load_local_checks(args.ssot_path)
    except PreflightRegistryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.list:
        for check in checks:
            print(f"{check.gate_id}: {' '.join(check.argv)}")
            if check.stdin_argv is not None:
                print(f"{check.gate_id}: stdin < {' '.join(check.stdin_argv)}")
        return 0

    if not checks:
        # Not a pass. An empty wired set means the registry lost its local
        # plane entirely (a bad edit, or the wrong --ssot-path), and exiting
        # 0 here would report "nothing to check" as "everything is fine" --
        # exactly the false-clean shape this repository's gates are written
        # to avoid.
        print(f"error: no gate in {args.ssot_path} carries the {LOCAL_PLANE!r} plane", file=sys.stderr)
        return 1

    print(f"local preflight: running {len(checks)} wired gate(s)...")
    results = run_checks(checks, args.repo_root, args.timeout_seconds, progress=sys.stderr)
    print(format_report(results))
    return 1 if any(not result.passed for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())

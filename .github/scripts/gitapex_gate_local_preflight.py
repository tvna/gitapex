#!/usr/bin/env python3
"""One consolidated local pre-push / pre-PR-open gate runner (issue #876).

This repository enforces 49 registered deterministic gates. Before this
script existed, roughly half of them had a perfectly good working-tree-only
invocation and yet ran *only* as separate CI jobs, so an agent preparing a
PR discovered gaps one CI job at a time on an already-open PR -- push, wait,
read one red check, fix, push again. Issue #876 records that same proposal
being independently re-raised and left unresolved across #707, #622, #616
(twice) and #670.

``python3 .github/scripts/gitapex_gate_local_preflight.py`` runs every such gate
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
#876's third criterion explicitly allows, and it is what keeps the 24
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

- **A gate that needs piped input, whose ``local_stdin`` is deleted, still
  reports PASS.** ``gitapex_scan_ssot_schema.py`` can check that a declared
  producer's argv is sane and that ``local_invocation`` names the gate's own
  script, but nothing in the registry expresses "this gate *requires* stdin"
  -- so removing ``local_stdin`` from ``exception-handler-gap`` leaves a
  schema-valid entry whose gate reads a zero-byte diff and reports clean.
  Verified by reconstruction, not assumed. The producer-*failure* path is
  guarded (a non-zero producer fails the gate loudly rather than feeding it
  an empty diff); the missing-producer path is not, and no cheap
  registry-level rule closes it without a hardcoded per-gate list, which is
  exactly the hand-maintained wiring this design exists to avoid.
- **A pre-push hook is bypassable, and only exists where ``prek install``
  has run.** ``.pre-commit-config.yaml`` wires this module as a ``pre-push``
  stage hook, so the ordinary path is real enforcement rather than a command
  a contributor has to remember to type -- but ``git push --no-verify``
  skips it, and a clone that never ran ``prek install`` has no shim at all.
  ``CONTRIBUTING.md`` and ``flake.nix``'s devShell both install with
  ``-t pre-commit -t pre-push`` and then verify each shim actually resolves
  (issue #890), which closes the "configured here but never actually
  installed" half; nothing closes the ``--no-verify`` half. CI remains the
  authoritative merge gate for every gate carrying a ``ci`` plane -- true
  for 38 of the 40 wired gates. ``behind-base`` (issue #985) and
  ``real-checkout-git-write`` (issue #991) are the two exceptions: each
  carries only ``local``, so for those two gates specifically this
  pre-push hook -- bypassable the same way as any other -- is the *only*
  enforcement, with no CI-side backstop. Named as a real gap in
  ``behind-base``'s own docstring and issue #985's Acceptance Criteria
  Map; the same gap now applies to ``real-checkout-git-write`` too.
- **Every wired gate runs through ``uv``.** CONTRIBUTING.md invokes this
  file with plain ``python3``, and so does the pre-push hook, because the
  runner itself needs no dependencies -- but all 40 wired argvs begin with
  ``uv``, since each gate carries its own pinned invocation. Without ``uv``
  on PATH every one of them reports ``FAIL ... failed to run``, which
  reads as a whole broken wired set rather than one missing tool. ``uv`` is
  already a documented prerequisite for this repository; it is named here so
  the failure mode is legible.
- Gates run **sequentially**, in registry-id order, for legible output on a
  terminal. ``mypy-type-check`` and ``cyclomatic-complexity-floor`` dominate
  the wall clock; parallelism was not added because interleaved failure
  output from eight concurrent subprocesses is the thing this runner exists
  to avoid.
- ``local_stdin`` producers that need ``origin/main`` to exist locally
  (today: ``exception-handler-gap``, ``stdlib-only-claim-drift``, and
  ``detection-logic-property-coverage`` -- every gate whose ``local_stdin``
  computes a merge-base diff, not just the first one added) no longer read
  a raw ``git diff`` directly. Each is wired at
  ``.github/scripts/gitapex_run_base_diff.py`` (issue #1345), which probes
  ``origin/main^{commit}`` first and, only if that peeled probe fails (a
  restricted-refspec clone -- ``git clone --single-branch --branch`` --
  never populates ``refs/remotes/origin/main`` at all, even from a
  source-only ``git fetch``), fetches it itself with a destination-refspec
  ``git fetch`` before re-verifying and handing off to the real ``git
  diff``. In a checkout where the ref is already present this is a no-op
  probe, no behavior change from before. A checkout where the fetch itself
  fails still reports that one gate FAIL with a message distinct from an
  ordinary diff failure; the other gates still run and still report, same
  as always. A *stale* local ``origin/main`` (present, but behind the real
  remote) still widens the diff rather than narrowing it in the common
  case -- except when the branch itself reverts a change ``main`` made
  after the local ref went stale, which narrows it instead; that caveat is
  pre-existing and named here, not solved by issue #1345, which only fixes
  the missing-ref case. ``behind-base`` (issue #985) never had this
  staleness problem for its own comparison, because unlike these three
  gates it fetches ``origin/main`` unconditionally on every run rather than
  only when the ref is missing -- see its own module docstring. Both this
  runner's diff-gate producers and ``behind-base`` now make network calls;
  neither is "the runner's first" any more.
- This grades **committed** state (``HEAD`` and the working tree as it is on
  disk), not a staged index -- which is exactly why it is wired at
  ``pre-push`` and not ``pre-commit``. ``.pre-commit-config.yaml``'s
  ``default_stages: [pre-commit]`` keeps the ruff/mypy hooks off the push
  path, so they do not run a second time here inside
  ``python-lint``/``mypy-type-check``.

**Why this file is named ``gitapex_gate_*``.** It is a runner of gates
rather than a gate in its own right, and it is deliberately absent from
``.gitapex/ssot.json``: a registry entry carrying the ``local`` plane would
make it discover and re-invoke itself. The prefix is load-bearing anyway:
``gitapex_detect_changed_gate_scripts.py`` selects deterministic-gate paths
by the ``.github/scripts/gitapex_(gate|scan)_*.py`` convention, so under any
other name every future edit to a module that executes registry-declared
argv on contributor machines would escape this repository's own
gate-quality disclosure requirement.

Run standalone: ``python3 .github/scripts/gitapex_gate_local_preflight.py``
(exit 1 if any wired gate fails, exit 0 when all pass), ``--list`` to print
the wired set without running anything, or via the pytest gate in
``tests/test_gitapex_gate_local_preflight.py``.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from typing import TextIO

import _gitapex_argv_safety
from _gitapex_schema_validation import load_json_or_raise

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"

# Ceiling for one gate's own subprocess, deliberately *tighter* than the
# slowest wired gate's own worst case rather than an upper bound on it.
# Stated precisely, because an earlier revision of this comment got the
# arithmetic backwards and would have justified the wrong number:
# mypy-type-check runs gitapex_run_precommit_mypy.py, which invokes mypy
# once per entry in its own MYPY_GROUPS -- seven groups today, each with its
# own _GROUP_TIMEOUT_SECONDS = 600 -- so that one gate's own theoretical
# worst case is ~4200 s, not 600 s. A ceiling matching that would be useless
# as a hang guard (80 minutes of a silent pre-push), so this is a judgment
# call in the other direction. For scale: a warm run of all 40 wired gates
# combined measures roughly 17 s end to end (the
# prior 39-gate set measured roughly 12 s, the 38-gate set before that
# measured roughly 11 s, the 37-gate set before that measured roughly 11 s,
# the 36-gate set before that measured roughly 11 s,
# the 35-gate set before that measured roughly 13 s,
# the 34-gate set before that measured roughly 11 s, up from ~7 s measured
# for the 31-gate set, 4-6 s measured for the 24-gate set before issue #985's
# `behind-base` gate, and ~8-9 s measured for the 26-gate set before issue
# #1028's two schema/manifest gates -- these are warm-run measurements on
# different hardware, not a strict per-gate cost trend), so 1800 s is a hang
# guard rather than a budget, and it comfortably clears a cold mypy cache
# while still failing loudly rather than blocking a push indefinitely. The
# residual risk is named rather than hidden: a genuinely cold cache on a slow
# machine can exceed this and report a timeout FAIL on a gate CI would pass.
# `--timeout-seconds` raises it for that case.
#
# Issue #985 added `behind-base`, this runner's first gate that makes a
# network call (it fetches `origin/main` before comparing); issue #1345
# added three more, each fetching only when the ref is missing rather than
# unconditionally on every run. Measured
# directly rather than assumed: three warm standalone runs of that one
# gate averaged under a second (~0.6 s), and the ~8-9 s combined figure
# above is a real but small addition against a ceiling roughly two orders
# of magnitude larger (1800 s / ~8.5 s =~ 210x).
DEFAULT_TIMEOUT_SECONDS = 1800

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
        """The verdict word used in both the progress stream and the report."""
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


def _refuse_unsafe_argv(check: LocalCheck) -> None:
    """Refuse the whole run if a discovered argv would execute a shell, or
    hand inline code to an interpreter, rather than invoke a tracked script.

    Raised during discovery, before the first subprocess starts, and
    deliberately not deferred to ``ssot-schema-drift``'s own equivalent
    check. That gate is one of the wired gates, so it runs in gate-id order
    and is not the first id in that order -- every gate sorting before it
    has already executed by the time it looks -- and it reads its
    own module-level ``SSOT_PATH`` rather than whichever registry this
    runner was pointed at. Both properties were reconstructed against the
    real registry during review of PR #888: a shell payload placed on
    ``apm-manifest-drift`` (which sorts first) executed, wrote its file, and
    the run still reported ``exit 0``. A guard that only fires after the
    payload has run is not a guard, so this one fires first and refuses the
    entire run rather than failing that one gate -- an argv this shape means
    the registry is not trustworthy, not that one check is broken."""
    for field, argv in (("local_invocation", check.argv), ("local_stdin", check.stdin_argv)):
        if argv is None:
            continue
        violations = _gitapex_argv_safety.find_argv_safety_violations(argv)
        if violations:
            raise PreflightRegistryError(f"{check.gate_id}: refusing to run -- {field} {violations[0]}")


def load_local_checks(ssot_path: pathlib.Path = SSOT_PATH) -> list[LocalCheck]:
    """Every gate in the registry whose ``planes`` contains ``"local"``,
    sorted by gate id for deterministic output and reproducible ordering
    between runs. Raises PreflightRegistryError -- never returns a silently
    short list -- when the registry cannot be read or parsed at all, since
    an empty result and an unreadable registry would otherwise be
    indistinguishable to a caller reading only the exit code."""
    instance = load_json_or_raise(ssot_path, PreflightRegistryError)
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
        check = LocalCheck(
            gate_id=gate_id,
            argv=_argv_or_raise(gate_id, "local_invocation", gate.get("local_invocation")),
            stdin_argv=None if stdin_raw is None else _argv_or_raise(gate_id, "local_stdin", stdin_raw),
        )
        _refuse_unsafe_argv(check)
        checks.append(check)
    return sorted(checks, key=lambda check: check.gate_id)


def _run(
    argv: tuple[str, ...], repo_root: pathlib.Path, timeout: int, stdin_text: str | None
) -> subprocess.CompletedProcess[str]:
    """Run one already-validated argv list from the repository root, with no
    shell. S603 is waived for the same reason gitapex_run_precommit_mypy.py
    waives it: a list argv, never a shell string, and the executable is
    intentionally resolved from PATH because `uv`/`git` live in different
    absolute locations across the three environments this has to work in (a
    contributor's machine, the nix devShell, and a GitHub runner).

    ``errors="replace"``, not ``text=True``'s own strict default. A gate --
    or a ``local_stdin`` producer -- may emit a byte sequence that is not
    valid UTF-8, and strict decoding raises ``UnicodeDecodeError`` from
    inside :func:`subprocess.run` itself. That is a ``ValueError``, not an
    ``OSError`` or a ``SubprocessError``, so it escaped run_check's handlers
    entirely and aborted the whole aggregate pass with a traceback: every
    later gate went unrun *and* unreported, and no verdict was printed at
    all -- the exact "silently drops a check it could not start" failure
    this module's own docstring promises never to have, in its worst form.
    This is not hypothetical for the one live producer either: it runs
    ``git diff`` under ``-c core.quotePath=false``, which deliberately
    *disables* git's octal escaping of non-ASCII path bytes.
    ``gitapex_detect_changed_gate_scripts.py`` already names a non-UTF-8
    diff as a case to handle rather than crash on; this matches it.
    ``run_check`` additionally catches ``ValueError`` so a decode failure
    from any other layer still degrades to one FAIL, not a lost run."""
    return subprocess.run(  # noqa: S603
        list(argv),
        cwd=repo_root,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        timeout=timeout,
        input=stdin_text,
        # A gate with no local_stdin producer must not inherit this
        # process's own stdin: a gate that reads stdin (every diff-fed one
        # does) would then block on a terminal until the per-gate timeout
        # expired -- a 30-minute silent hang on a contributor's pre-push,
        # reported afterwards as a timeout FAIL that looks like a hung gate
        # rather than a missing local_stdin declaration. DEVNULL makes that
        # case an immediate EOF instead.
        stdin=None if stdin_text is not None else subprocess.DEVNULL,
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
        except (OSError, ValueError, subprocess.SubprocessError) as error:
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
    except (OSError, ValueError, subprocess.SubprocessError) as error:
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
    """CLI entry point: discover the wired set, run it, print the aggregate
    verdict, and return 0 only when every wired gate passed. A registry that
    cannot be read, or that carries an unsafe argv, exits 1 without running
    anything."""
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

    # Checked before --list is handled, not after. An empty wired set means
    # the registry lost its local plane entirely (a bad edit, or the wrong
    # --ssot-path), and exiting 0 here would report "nothing to check" as
    # "everything is fine" -- exactly the false-clean shape this
    # repository's gates are written to avoid. --list is precisely the
    # command a contributor reaches for to inspect the wiring after a
    # suspicious edit, so it must not be the one path that answers that
    # question with silence and exit 0.
    if not checks:
        print(f"error: no gate in {args.ssot_path} carries the {LOCAL_PLANE!r} plane", file=sys.stderr)
        return 1

    if args.list:
        for check in checks:
            print(f"{check.gate_id}: {' '.join(check.argv)}")
            if check.stdin_argv is not None:
                print(f"{check.gate_id}: stdin < {' '.join(check.stdin_argv)}")
        return 0

    print(f"local preflight: running {len(checks)} wired gate(s)...")
    results = run_checks(checks, args.repo_root, args.timeout_seconds, progress=sys.stderr)
    print(format_report(results))
    return 1 if any(not result.passed for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())

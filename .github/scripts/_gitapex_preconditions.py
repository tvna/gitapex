#!/usr/bin/env python3
"""Environment/repo-state precondition helpers for the ``local`` gate plane
(issue #1566, consolidating #1546/#1489).

**The defect this module exists to close.** ``.gitapex/ssot.json``'s
``harden-checkout-pin-drift`` gate resolves a pinned action's true
last-touching commit via ``git log``, which needs full history: a shallow
clone's boundary commit has no locally-known parent, so
``gitapex_scan_harden_checkout_pin_drift.py``'s own ``current_action_sha``
raises ``RuntimeError`` when it lands on that boundary commit -- a real,
live-verified failure mode (see that module's own docstring), not a
hypothetical one. Before this issue, nothing in
``gitapex_gate_local_preflight.py`` checked for a shallow clone before
running that gate, so the failure surfaced reactively, mid-run, as one
gate's own confusing error text -- #1546 and #1489 are two independent
reports of that identical defect shape.

**What this module provides, and what it deliberately does not.** Two
functions: :func:`is_shallow_clone` (a read-only probe, ``git rev-parse
--is-shallow-repository``) and :func:`ensure_full_history` (the fix, ``git
fetch --unshallow``). Both wrap exactly one ``git`` subprocess call each and
raise :class:`PreconditionsError` for every way that call can fail to
produce a trustworthy answer -- a missing ``git`` executable, a timeout, or
(for the probe) a nonzero exit that leaves the shallow/non-shallow question
genuinely unanswered. Deciding *which* wired gates need this, and *when* to
call these two functions, is ``gitapex_gate_local_preflight.py``'s own job,
not this module's: this module answers "is this repo shallow" and "make it
not shallow", nothing about the registry or the wired set.

**Never a silent "not shallow."** A caller cannot distinguish "confirmed
non-shallow" from "the check itself failed" if a failed check also returns
``False`` -- and the whole point of the pre-check this module supports is
to run *before* any wired gate, so a wrongly-``False`` answer would let a
still-shallow clone straight through to the exact defect this exists to
close. :func:`is_shallow_clone` therefore raises rather than returning a
default value on any failure to run or interpret the command.

**A ``.github/scripts/`` file, not a ``hooks/`` one.** This directory's own
convention (unlike ``hooks/``) allows third-party imports; this module
needs none, so it stays stdlib-only anyway, but that is a simplicity choice
here, not a hard constraint the way it is under ``hooks/``.

Run via the pytest gate in ``tests/test__gitapex_preconditions.py``; not a
standalone CLI (no ``main()``), matching ``_gitapex_base_ref.py``'s and
``_gitapex_argv_safety.py``'s own private-helper shape -- it exists to be
imported, not invoked directly.
"""

from __future__ import annotations

import pathlib
import subprocess

# Ceiling for one git subprocess call (the shallow-repository probe, or the
# unshallow fetch). Matches _gitapex_base_ref.py's own GIT_TIMEOUT_SECONDS
# value and rationale (generous for a local call or a fetch over an
# ordinary network, while still failing loudly on a hung connection rather
# than blocking indefinitely) -- defined locally rather than imported,
# since this module shares no fetch logic with that one to keep in sync,
# only the same timeout judgment call.
GIT_TIMEOUT_SECONDS = 60


class PreconditionsError(Exception):
    """A git subprocess this module depends on could not be run to
    completion, or exited in a way that leaves its own question
    unanswered. Raised instead of returning a default value: a caller that
    treated this as "not shallow" or "already has full history" would let
    the exact reactive, mid-run failure this module exists to prevent
    through unchecked."""


def is_shallow_clone(repo_root: pathlib.Path, *, timeout: int = GIT_TIMEOUT_SECONDS) -> bool:
    """Whether ``repo_root`` is a shallow git clone -- ``git rev-parse
    --is-shallow-repository``, which prints exactly ``true`` or ``false``
    on success. Raises :class:`PreconditionsError` for every way that
    command can fail to answer the question at all (a missing ``git``
    executable, a timeout, or a nonzero exit -- e.g. ``repo_root`` is not a
    git repository) rather than returning ``False`` for any of them: a
    failed check is not evidence of a full-history clone."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, `git` resolved
        # from PATH -- same rationale as every other gate script in this
        # directory (gitapex_gate_local_preflight.py, _gitapex_base_ref.py).
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_root), "rev-parse", "--is-shallow-repository"],  # noqa: S607
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise PreconditionsError(
            f"git rev-parse --is-shallow-repository timed out after {timeout}s in {repo_root}"
        ) from error
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise PreconditionsError(f"cannot run git to check shallow-clone status in {repo_root}: {error}") from error
    if result.returncode != 0:
        raise PreconditionsError(
            f"git rev-parse --is-shallow-repository exited {result.returncode} in {repo_root}: {result.stderr.strip()}"
        )
    return result.stdout.strip() == "true"


def ensure_full_history(repo_root: pathlib.Path, *, timeout: int = GIT_TIMEOUT_SECONDS) -> None:
    """Fetch full history into ``repo_root`` -- ``git fetch --unshallow``.
    Raises :class:`PreconditionsError` naming the underlying failure text on
    any non-zero exit, timeout, or failure to run the subprocess at all --
    never swallowed, so a caller running this before a wired gate can trust
    that a return with no exception means the fetch actually happened."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_root), "fetch", "--unshallow"],  # noqa: S607
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise PreconditionsError(f"git fetch --unshallow timed out after {timeout}s in {repo_root}") from error
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise PreconditionsError(f"cannot run git to fetch full history in {repo_root}: {error}") from error
    if result.returncode != 0:
        raise PreconditionsError(f"git fetch --unshallow failed in {repo_root}: {result.stderr.strip()}")

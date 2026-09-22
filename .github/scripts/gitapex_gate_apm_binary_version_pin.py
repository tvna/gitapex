#!/usr/bin/env python3
"""Guard that a PATH-invocable ``apm`` binary matches flake.nix's Class B pin.

Issue #1817 (retro #1816 repair 1): during PR #1814 development, a manual
bare ``apm install`` ran with the ambient PATH binary (0.23.1) instead of the
flake-pinned 0.25.0, silently downgrading ``apm.lock.yaml`` (its
``apm_version`` field) and deleting deployed hook files the older version
considered stale. Recovered via ``nix run .#apm -- install``. The existing
``toolchain-pin-drift`` gate
(``.github/scripts/gitapex_scan_toolchain_pin_drift.py``) only checks that a
CI workflow does not *declare* a second install path for a Class B tool --
it says nothing about which binary a contributor's shell actually resolves
``apm`` to at run time.

This gate closes that gap for ``apm`` specifically (the one Class B tool a
contributor plausibly invokes directly, via ``apm install``/``apm lock``,
rather than only through the flake): if a bare ``apm`` is resolvable on
PATH at all, its ``apm --version`` output must match the version
``flake.nix``'s ``mkClassB`` block pins. A PATH with no ``apm`` on it is not
drift -- there is nothing to invoke out of pin, and both of this
repository's real install paths (``nix run .#apm -- install`` /
``nix develop``, and ``skills/setup-gitapex-toolchain``'s Nix-free
provisioning script) resolve their own binary directly rather than relying
on PATH.

Deliberately self-contained rather than importing
``skills/setup-gitapex-toolchain/scripts/gitapex_provision_class_b.py``'s
own (considerably more general) flake.nix parser: this repository keeps
``.github/scripts/*.py`` files independently self-contained (see
``gitapex_scan_gate_proposal_consolidation_drift.py``'s own docstring for
the same convention, citing ``gitapex_gate_skill_rename_lifecycle.py``), and
this gate needs only one tool's ``version`` field, not that module's full
per-system asset/sha256 pin table.

Bypass (issue #1817's own disclosed residual risk -- "a contributor who
intentionally tests cross-version behavior must have a documented bypass"):
this gate is wired at the ``local`` plane via the existing pre-push hook, so
the existing, already-documented ``git push --no-verify`` (see
CONTRIBUTING.md's "Local pre-push preflight" section) already covers that
case; no new bypass mechanism is added.

Run standalone (exit 1 on drift or on a check that could not run) or via the
pytest gate in ``tests/test_gitapex_gate_apm_binary_version_pin.py``.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
from collections.abc import Callable

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAKE_PATH = REPO_ROOT / "flake.nix"

# Matches flake.nix's `apm = mkReleaseBinary pkgs { pname = "apm"; version =
# "0.25.0"; ... };` block (mkClassB) and captures the pinned version string.
# `[^}]*?` (non-greedy) is sufficient because this block's own body contains
# no nested braces (verified directly against flake.nix -- pname/version/
# kind/url/sha256 are all flat string/call assignments).
_APM_PIN_RE = re.compile(r'apm\s*=\s*mkReleaseBinary\s+pkgs\s*\{[^}]*?version\s*=\s*"([^"]+)"', re.DOTALL)

# Matches the version number inside `apm --version`'s real output, e.g.
# "Agent Package Manager (APM) CLI version 0.25.0 (d73e6ac)" -- live-verified
# this session against the actual apm 0.25.0 binary, not assumed.
_APM_VERSION_OUTPUT_RE = re.compile(r"version\s+(\d+\.\d+\.\d+)")


class FlakePinParseError(RuntimeError):
    """flake.nix could not be read, or its apm Class B pin block could not
    be located/parsed -- fails loudly rather than silently skipping the
    check on a malformed or moved flake.nix."""


class ApmVersionCheckError(RuntimeError):
    """A PATH-resolvable ``apm`` binary's ``--version`` invocation failed,
    or its output carried no recognizable version number."""


def parse_apm_pin_version(flake_text: str) -> str:
    match = _APM_PIN_RE.search(flake_text)
    if not match:
        raise FlakePinParseError(
            'could not find apm\'s `mkReleaseBinary pkgs { ... version = "X.Y.Z"; ... }` block in flake.nix'
        )
    return match.group(1)


def load_apm_pin_version(flake_path: pathlib.Path = FLAKE_PATH) -> str:
    try:
        flake_text = flake_path.read_text(encoding="utf-8")
    except OSError as error:
        raise FlakePinParseError(f"{flake_path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise FlakePinParseError(f"{flake_path}: is not valid UTF-8: {error}") from error
    return parse_apm_pin_version(flake_text)


def extract_apm_version(version_output: str) -> str:
    match = _APM_VERSION_OUTPUT_RE.search(version_output)
    if not match:
        raise ApmVersionCheckError(f"could not find a version number in `apm --version` output: {version_output!r}")
    return match.group(1)


def find_path_apm_version(
    apm_path: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Run ``<apm_path> --version`` and return the version number found in
    its output. Raises ApmVersionCheckError on a non-zero exit or
    unparseable output -- never silently treated as "no drift"."""
    # No suppression comment needed here (same as gitapex_provision_class_b.py's own
    # provision_tool/run_apm_install call sites): ruff's S603 matches direct calls to
    # subprocess.run/Popen/etc. by name, and a call through the injected `runner`
    # parameter isn't recognized as one. apm_path is resolved from PATH by the caller via
    # shutil.which, then invoked with a fixed, literal ["--version"] argv -- no shell, no
    # attacker-controlled argument, regardless.
    proc = runner([apm_path, "--version"], capture_output=True, text=True, timeout=30, check=False)
    if proc.returncode != 0:
        raise ApmVersionCheckError(f"`{apm_path} --version` exited {proc.returncode}: {proc.stderr.strip()}")
    return extract_apm_version(proc.stdout.strip())


def format_drift_message(apm_path: str, path_version: str, pin_version: str) -> str:
    return (
        f"apm binary version pin: PATH resolves `apm` to {apm_path}, reporting version "
        f"{path_version}, but flake.nix pins {pin_version}.\n"
        "This is the shape of the defect issue #1817 tracks: a bare `apm install` run against an "
        "ambient PATH binary instead of the flake-pinned build can silently downgrade apm.lock.yaml "
        "and delete deployed hook files the older version considers stale.\n"
        "Use `nix run .#apm -- install` (or `nix develop`'s devShell), or "
        "skills/setup-gitapex-toolchain's Nix-free provisioning script, instead of a bare `apm "
        "install`/`apm lock`.\n"
        "To intentionally test cross-version apm behavior, bypass this check with "
        '`git push --no-verify` (see CONTRIBUTING.md\'s "Local pre-push preflight" section).'
    )


def find_drift(
    flake_path: pathlib.Path = FLAKE_PATH,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str | None:
    """Return a drift message if a PATH-resolvable `apm` binary's reported
    version disagrees with flake.nix's Class B pin, else None. No `apm` on
    PATH at all returns None -- there is no binary invocation to drift
    against."""
    apm_path = which("apm")
    if apm_path is None:
        return None
    pin_version = load_apm_pin_version(flake_path)
    path_version = find_path_apm_version(apm_path, runner)
    if path_version != pin_version:
        return format_drift_message(apm_path, path_version, pin_version)
    return None


def main() -> int:
    try:
        drift = find_drift()
    except (FlakePinParseError, ApmVersionCheckError) as error:
        print(f"apm binary version pin: {error}", file=sys.stderr)
        return 1
    if drift:
        print(drift)
        return 1
    print("No apm binary version pin drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

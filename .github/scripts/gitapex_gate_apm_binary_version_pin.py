#!/usr/bin/env python3
"""Guard that apm's pinned version is actually the one in effect.

Issue #1817 (retro #1816 repair 1): during PR #1814 development, a manual
bare ``apm install`` ran with the ambient PATH binary (0.23.1) instead of the
flake-pinned 0.25.0, silently downgrading ``apm.lock.yaml`` (its
``apm_version`` field) and deleting deployed hook files the older version
considered stale. Recovered via ``nix run .#apm -- install``. The existing
``toolchain-pin-drift`` gate
(``.github/scripts/gitapex_scan_toolchain_pin_drift.py``) only checks that a
CI workflow does not *declare* a second install path for a Class B tool --
it says nothing about which binary actually ran, or what it wrote.

Two independent checks, either of which can report drift on its own:

1. **Lockfile check** (works in every plane, including CI, with no `apm` on
   PATH at all): the committed ``apm.lock.yaml``'s own top-level
   ``apm_version`` field must match flake.nix's Class B pin. This is the
   check that actually catches issue #1817's own defect shape *as
   committed* -- a PATH-binary-only check would report clean in CI, because
   CI always provisions `apm` from the pinned flake regardless of what a
   contributor's own machine did; the corrupted lockfile is what ships if
   that's the only signal. Independent review (2026-09-22, this issue) named
   this gap directly: "CI provisions its own apm from the same pinned flake
   -- so the CI-plane instance of [a PATH-only] predicate will essentially
   always pass regardless of what's actually committed."
2. **PATH-binary check**: if a bare ``apm`` is resolvable on PATH at all,
   its ``apm --version`` output must also match the pin -- catches the
   defect at its source, before a corrupting `apm install` is even run, on
   a contributor's own machine (the local pre-push plane). A PATH with no
   ``apm`` on it is not drift for this check specifically -- there is
   nothing to invoke out of pin, and both of this repository's real install
   paths (``nix run .#apm -- install`` / ``nix develop``, and
   ``skills/setup-gitapex-toolchain``'s Nix-free provisioning script)
   resolve their own binary directly rather than relying on PATH.

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
case for the local plane. The lockfile check above also runs at the ``ci``
plane, which has no ``--no-verify`` equivalent, so a contributor testing
cross-version *binary* behavior locally does not get an unbypassable CI
block for it: the CI-side lockfile check only fires if the corrupted
``apm.lock.yaml`` is actually committed and pushed, which is exactly the
"never write" instruction issue #1817 itself describes for that case, not
a normal step of testing binary behavior.

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

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAKE_PATH = REPO_ROOT / "flake.nix"
LOCKFILE_PATH = REPO_ROOT / "apm.lock.yaml"

# Matches flake.nix's `apm = mkReleaseBinary pkgs { pname = "apm"; version =
# "0.25.0"; ... };` block (mkClassB) and captures the pinned version string.
# `[^}]*?` (non-greedy) is sufficient because this block's own body contains
# no nested braces (verified directly against flake.nix -- pname/version/
# kind/url/sha256 are all flat string/call assignments), and no `.`
# metacharacter appears in this pattern, so no re.DOTALL flag is needed:
# `\s`/`[^}]` already match newlines regardless of that flag. Matched against
# comment-stripped text only (see _strip_nix_line_comments) -- independent
# review live-reproduced this session: without stripping, a `#`-comment
# mentioning an old/example version string above the real assignment (e.g.
# "# bumped from version = \"0.23.1\"") wins the non-greedy search, since
# `.search()` stops at the first textual match regardless of which line it's
# on.
_APM_PIN_RE = re.compile(r'apm\s*=\s*mkReleaseBinary\s+pkgs\s*\{[^}]*?version\s*=\s*"([^"]+)"')

# Matches the version token inside `apm --version`'s real output, e.g.
# "Agent Package Manager (APM) CLI version 0.25.0 (d73e6ac)" -- live-verified
# this session against the actual apm 0.25.0 binary, not assumed. Captures
# any non-whitespace run (not just strict N.N.N) so a pin carrying a
# pre-release/build-metadata suffix (e.g. "0.26.0-rc1") compares equal
# rather than false-positiving on a truncated N.N.N-only extraction.
_APM_VERSION_OUTPUT_RE = re.compile(r"version\s+(\S+)")

# The real CLI's own output always carries this substring (live-verified this
# session: "Agent Package Manager (APM) CLI version 0.25.0 (d73e6ac)").
# Required before trusting a PATH-resolved `apm`'s output at all -- `apm` is
# also the long-standing name of Atom's now-defunct "Atom Package Manager"
# CLI, and a stray leftover install can still sit on a contributor's PATH
# ahead of the flake-provisioned one. Without this check, that binary's
# differently-shaped `--version` output (no "version X" substring at all)
# surfaces only as an opaque "could not find a version token" from
# extract_apm_version, with no indication that the wrong tool entirely was
# resolved.
_EXPECTED_APM_SIGNATURE = "Agent Package Manager"


def _strip_nix_line_comments(text: str) -> str:
    """Strip a Nix `# ...` line comment from each line before pin-block
    matching. None of flake.nix's own Class B string literals (asset names,
    SRI hashes, tags, this repo's own owner/repo names) contain a literal
    `#`, so a plain per-line split is sufficient without a real Nix
    tokenizer."""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


class FlakePinParseError(RuntimeError):
    """flake.nix could not be read, or its apm Class B pin block could not
    be located/parsed -- fails loudly rather than silently skipping the
    check on a malformed or moved flake.nix."""


class LockfileParseError(RuntimeError):
    """apm.lock.yaml could not be read, or is not valid YAML, or does not
    parse to a mapping -- fails loudly rather than silently skipping the
    lockfile check on a malformed lockfile."""


class ApmVersionCheckError(RuntimeError):
    """A PATH-resolvable ``apm`` binary could not be invoked (missing,
    unreadable, timed out, non-zero exit), or its output carried no
    recognizable version token."""


def parse_apm_pin_version(flake_text: str) -> str:
    match = _APM_PIN_RE.search(_strip_nix_line_comments(flake_text))
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


def load_lockfile_apm_version(lockfile_path: pathlib.Path = LOCKFILE_PATH) -> str | None:
    """Return apm.lock.yaml's own top-level `apm_version` field, or None if
    the file legitimately carries no such field (an apm CLI version old
    enough to predate that field, or a repository not using apm at all --
    not this gate's call to treat either as drift). Raises
    LockfileParseError on a missing/unreadable/malformed file -- an
    apm.lock.yaml that exists but cannot be verified must never be silently
    treated as "nothing to check"."""
    try:
        lockfile_text = lockfile_path.read_text(encoding="utf-8")
    except OSError as error:
        raise LockfileParseError(f"{lockfile_path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise LockfileParseError(f"{lockfile_path}: is not valid UTF-8: {error}") from error
    # An empty or whitespace-only file is exactly the shape a crashed/
    # interrupted `apm install`/`apm lock` write leaves behind -- the same
    # corruption class issue #1817 exists to catch -- so it fails loudly
    # here rather than reaching yaml.safe_load, which would parse it to
    # None and let the "no apm_version field" branch below wave it through
    # as nothing-to-check. Independent review live-reproduced this session:
    # without this guard, an empty apm.lock.yaml is the strongest possible
    # false negative.
    if not lockfile_text.strip():
        raise LockfileParseError(f"{lockfile_path}: is empty")
    try:
        data = yaml.safe_load(lockfile_text)
    except yaml.YAMLError as error:
        raise LockfileParseError(f"{lockfile_path}: is not valid YAML: {error}") from error
    # yaml.safe_load still resolves anchors/aliases, so a maliciously crafted
    # document (e.g. a deep alias-expansion chain) can exhaust the interpreter via
    # RecursionError or MemoryError rather than raising yaml.YAMLError. apm.lock.yaml
    # is a repository-committed file, not attacker-supplied input, but this gate's
    # own contract (see module docstring) is to fail closed with a typed error on
    # anything that prevents a real comparison, not to let an unrelated exception
    # class escape main()'s own handler as a raw traceback.
    except (RecursionError, MemoryError) as error:
        raise LockfileParseError(f"{lockfile_path}: exhausted parsing this document: {error}") from error
    if data is None:
        return None
    if not isinstance(data, dict):
        raise LockfileParseError(f"{lockfile_path}: must be a YAML mapping, got {type(data).__name__}")
    version = data.get("apm_version")
    if version is None:
        return None
    return str(version)


def extract_apm_version(version_output: str) -> str:
    match = _APM_VERSION_OUTPUT_RE.search(version_output)
    if not match:
        raise ApmVersionCheckError(f"could not find a version token in `apm --version` output: {version_output!r}")
    return match.group(1)


def find_path_apm_version(
    apm_path: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Run ``<apm_path> --version`` and return the version token found in
    its output. Raises ApmVersionCheckError on a failure to invoke the
    binary at all (missing, unreadable, timed out), a non-zero exit,
    output that does not look like the real apm CLI's own banner, or
    otherwise-unparseable output -- never silently treated as "no drift"."""
    try:
        # No suppression comment needed here (same as gitapex_provision_class_b.py's own
        # provision_tool/run_apm_install call sites): ruff's S603 matches direct calls to
        # subprocess.run/Popen/etc. by name, and a call through the injected `runner`
        # parameter isn't recognized as one. apm_path is resolved from PATH by the caller via
        # shutil.which, then invoked with a fixed, literal ["--version"] argv -- no shell, no
        # attacker-controlled argument, regardless.
        #
        # errors="replace", not text=True's own strict default: a PATH-resolved binary that
        # is not actually apm at all (see _EXPECTED_APM_SIGNATURE below) may emit output this
        # process's own default encoding cannot decode; live-reproduced this session that
        # subprocess.run(text=True) then raises UnicodeDecodeError -- a ValueError subclass,
        # not OSError/SubprocessError -- straight out of this function uncaught. Replacing
        # undecodable bytes keeps this a clean ApmVersionCheckError (the signature/token check
        # below still correctly rejects the garbled output) instead of an unhandled traceback.
        proc = runner(
            [apm_path, "--version"], capture_output=True, text=True, errors="replace", timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ApmVersionCheckError(f"could not run `{apm_path} --version`: {error}") from error
    if proc.returncode != 0:
        raise ApmVersionCheckError(f"`{apm_path} --version` exited {proc.returncode}: {proc.stderr.strip()}")
    output = proc.stdout.strip()
    if _EXPECTED_APM_SIGNATURE not in output:
        raise ApmVersionCheckError(
            f"`{apm_path} --version` does not look like Microsoft's Agent Package Manager "
            f"(expected {_EXPECTED_APM_SIGNATURE!r} in its output) -- PATH may be resolving a "
            f"different tool also named `apm` (e.g. the unrelated, unmaintained Atom Package "
            f"Manager): {output!r}"
        )
    return extract_apm_version(output)


def format_lockfile_drift_message(lockfile_version: str, pin_version: str) -> str:
    return (
        f"apm binary version pin: apm.lock.yaml's own `apm_version` field reads {lockfile_version}, "
        f"but flake.nix pins {pin_version}.\n"
        "This is the shape of the defect issue #1817 tracks: a bare `apm install` run against an "
        "ambient PATH binary instead of the flake-pinned build can silently downgrade apm.lock.yaml "
        "and delete deployed hook files the older version considers stale.\n"
        "Regenerate apm.lock.yaml with `nix run .#apm -- install` (or `nix develop`'s devShell), or "
        "skills/setup-gitapex-toolchain's Nix-free provisioning script, instead of a bare `apm "
        "install`/`apm lock`."
    )


def format_path_drift_message(apm_path: str, path_version: str, pin_version: str) -> str:
    return (
        f"apm binary version pin: PATH resolves `apm` to {apm_path}, reporting version "
        f"{path_version}, but flake.nix pins {pin_version}.\n"
        "Use `nix run .#apm -- install` (or `nix develop`'s devShell), or "
        "skills/setup-gitapex-toolchain's Nix-free provisioning script, instead of a bare `apm "
        "install`/`apm lock`.\n"
        "To intentionally test cross-version apm binary behavior, bypass this local-plane check "
        'with `git push --no-verify` (see CONTRIBUTING.md\'s "Local pre-push preflight" section) -- '
        "but never push a lockfile/hook state produced that way; the lockfile check above runs in CI "
        "too and has no such bypass."
    )


def find_drift(
    flake_path: pathlib.Path = FLAKE_PATH,
    lockfile_path: pathlib.Path = LOCKFILE_PATH,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str | None:
    """Return a combined drift message if either the committed
    apm.lock.yaml's own `apm_version` field, or a PATH-resolvable `apm`
    binary's reported version, disagrees with flake.nix's Class B pin, else
    None. No `apm_version` field in the lockfile, and no `apm` on PATH, are
    each independently treated as "nothing to check" for that one signal,
    not as drift."""
    pin_version = load_apm_pin_version(flake_path)
    messages: list[str] = []

    lockfile_version = load_lockfile_apm_version(lockfile_path)
    if lockfile_version is not None and lockfile_version != pin_version:
        messages.append(format_lockfile_drift_message(lockfile_version, pin_version))

    apm_path = which("apm")
    if apm_path is not None:
        path_version = find_path_apm_version(apm_path, runner)
        if path_version != pin_version:
            messages.append(format_path_drift_message(apm_path, path_version, pin_version))

    if messages:
        return "\n\n".join(messages)
    return None


def main() -> int:
    try:
        drift = find_drift()
    except (FlakePinParseError, LockfileParseError, ApmVersionCheckError) as error:
        print(f"apm binary version pin: {error}", file=sys.stderr)
        return 1
    if drift:
        print(drift)
        return 1
    print("No apm binary version pin drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

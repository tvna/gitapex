#!/usr/bin/env python3
"""Run betterleaks as a git hook, at either the staged or full-history scope (issue #890).

`betterleaks` 1.6.1 is SHA256-pinned in ``flake.nix`` and named as the
guaranteed libre path for the Secret detection domain in
``docs/scanning-capability-selection-policy.md`` (#843), but until #890 nothing
consumed it -- ``toolchain-nix.yml`` only builds the binary and prints
``--version``, which
``skills/auditing-agent-product-scope/references/middleware-inventory.md:42``
already recorded as a gap. This script is what ``.pre-commit-config.yaml``
calls to close it.

Two scopes, one per git stage:

``staged``
    The pre-commit stage. Flags follow betterleaks' own published
    ``.pre-commit-hooks.yaml`` (``git --pre-commit --redact --staged
    --verbose``) rather than being invented here.

``history``
    The pre-push stage, scanning the whole history rather than only the
    range being pushed. Measured at 1.34 s over 30.24 MB on `main`, so the
    cost is negligible, and it buys two things a range scan does not: it
    needs no push-range plumbing (so it does not depend on whether prek
    exposes from-ref/to-ref to a hook at the pre-push stage, which is
    undocumented), and it still catches a secret introduced by a history
    rewrite or by a ``git commit --no-verify`` that skipped the staged hook.

Why a local wrapper instead of betterleaks' own published pre-commit repo:
a remote ``rev`` would be a second version source alongside ``flake.nix``,
which is exactly the two-different-versions split issue #678 exists to
prevent. Same rationale ``.pre-commit-config.yaml`` already states for
routing ruff and mypy through ``uv run --frozen``.

``--redact`` is passed unconditionally in both modes and is not exposed as an
option. A hook that reports a finding writes to the terminal, and CLAUDE.md
section 4 forbids echoing secret values into any output sink; the hook must be
able to say *which rule matched where* without reproducing the value.
"""

# Not folded into the module docstring above: `argparse.ArgumentParser` below
# is constructed with `description=__doc__`, so anything added there changes
# real `--help` output -- the exact thing waves 1-3 of #1040's batch confirmed
# byte-identical before/after as their own proof method. Kept as a plain
# comment instead so that guarantee still holds for this wave.
#
# Issue #1071 (wave 4 of #1040's batch pydantic CLI-arg validation rollout):
# `main`'s parsed namespace is now passed through `RunBetterleaksArgs`
# immediately after `parser.parse_args(argv)`, matching the wrap already
# applied in waves 1-3. `mode` is typed as the same two-value `Literal`
# argparse's own `choices=sorted(_MODE_FLAGS)` already enforces -- this
# repo's established Literal-narrowing convention (e.g.
# gitapex_scan_ssot_schema.py's fields) for a field argparse's own `choices=`
# already constrains, not a new validation argparse did not already perform.
# So construction can currently never raise `ValidationError` for a real CLI
# invocation; the model exists for consistency with #1040's repo-wide
# convention (a typed seam between `parse_args` and business logic). This
# hook's own production invocation (`.pre-commit-config.yaml`'s
# `betterleaks-staged`/`betterleaks-full-history` hooks) already runs under
# `uv run --frozen` (issue #1035), so the added `pydantic` import is safe
# here.

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

# A git hook has no subprocess timeout of its own, so a hung scanner would
# block `git commit` or `git push` indefinitely. The same reasoning (and the
# same style of comment) as _GROUP_TIMEOUT_SECONDS in
# gitapex_run_precommit_mypy.py. The measured full-history scan is ~1.4 s, so
# this ceiling is ~200x the observed cost -- generous enough that a slower
# machine or a much larger future history never trips it spuriously, while
# still bounded.
_SCAN_TIMEOUT_SECONDS = 300

# Shared by both modes. `--no-banner` keeps hook output to the finding itself.
_COMMON_FLAGS: tuple[str, ...] = ("--redact", "--verbose", "--no-banner")

# Per-mode flags. `staged` mirrors betterleaks' own published hook entry.
_MODE_FLAGS: dict[str, tuple[str, ...]] = {
    "staged": ("--pre-commit", "--staged"),
    "history": (),
}

_MISSING_BINARY_MESSAGE = """\
betterleaks was not found on PATH, so this repository's secret-detection
hook cannot run.

Failing instead of skipping is deliberate (issue #890): a secret gate that
passes when its scanner is absent is fail-open, and would report success on
a commit it never inspected.

Provision the pinned binary, then retry:

  nix develop                 # persistent surfaces (local CLI, CI)
  /gitapex:setup-gitapex-toolchain   # ephemeral Claude Code web sessions

Both install the betterleaks version SHA256-pinned in flake.nix. Do not
install a different copy from elsewhere -- flake.nix is the single version
source, and .betterleaks.toml's allowlist was verified against that exact
build.\
"""


def repo_root() -> Path:
    """Return the git top-level directory.

    betterleaks discovers ``.betterleaks.toml`` relative to the scan target,
    so the scan runs from here rather than from the caller's cwd. git and prek
    both invoke hooks from the top level already; this makes that explicit
    instead of depending on it.
    """
    # Suppression rationale, same convention as gitapex_run_precommit_mypy.py's
    # own uv invocation: the argv is a fixed literal with no interpolated input, and
    # `git` is resolved from PATH deliberately -- a hook must use the same git
    # the caller's `git commit` did, not a hard-coded absolute path that would
    # differ between Nix, system, and CI installs.
    completed = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"),  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(completed.stdout.strip())


def build_command(betterleaks: str, mode: str) -> tuple[str, ...]:
    """Return the full betterleaks argv for `mode`."""
    return (betterleaks, "git", *_MODE_FLAGS[mode], *_COMMON_FLAGS)


class RunBetterleaksArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace (issue #1071). See the
    module docstring's own issue #1071 section for why `mode`'s Literal
    type cannot currently raise ValidationError from a real invocation."""

    mode: Literal["history", "staged"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=sorted(_MODE_FLAGS),
        help="staged: scan the git index (pre-commit). history: scan all commits (pre-push).",
    )
    args = parser.parse_args(argv)

    try:
        validated = RunBetterleaksArgs(mode=args.mode)
    except ValidationError:
        print("error: invalid CLI arguments", file=sys.stderr)
        return 2

    betterleaks = shutil.which("betterleaks")
    if betterleaks is None:
        print(_MISSING_BINARY_MESSAGE, file=sys.stderr)
        return 1

    command = build_command(betterleaks, validated.mode)
    try:
        # Suppression rationale: `command` carries no untrusted input. Its executable is
        # the absolute path shutil.which resolved above, and every remaining
        # element is a module-level literal selected by an argparse `choices`
        # constraint (now also RunBetterleaksArgs' Literal type) -- validated.mode
        # cannot reach here as anything but "staged" or "history".
        completed = subprocess.run(  # noqa: S603
            command, cwd=repo_root(), timeout=_SCAN_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        print(
            f"betterleaks --mode {validated.mode} exceeded {_SCAN_TIMEOUT_SECONDS}s and was killed. "
            "Failing the hook rather than passing an unfinished scan.",
            file=sys.stderr,
        )
        return 1
    # Raised by repo_root()'s own `check=True`, which is evaluated as the `cwd`
    # argument above and therefore inside this try. Deliberately not marked
    # `# pragma: no cover`: pyproject.toml's [tool.coverage.report] sets
    # exclude_lines explicitly, which REPLACES coverage.py's default list rather
    # than extending it, so `# pragma: no cover` is inert in this repository and
    # would read as an exclusion that is not actually happening.
    except subprocess.CalledProcessError as exc:
        print(f"could not resolve the git top-level directory: {exc}", file=sys.stderr)
        return 1

    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())

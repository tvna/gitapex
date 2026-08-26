#!/usr/bin/env python3
"""Self-healing ``local_stdin`` diff producer for the merge-base diff gates
(issue #1345).

Three registered ``local``-plane gates in ``.gitapex/ssot.json``
(``exception-handler-gap``, ``stdlib-only-claim-drift``,
``detection-logic-property-coverage``) each declare a ``local_stdin``
producer -- this script, run via ``uv run``, is that producer as of this
issue -- that, before this issue, ran a raw ``git diff -U0 --no-renames
--merge-base origin/main HEAD -- <globs>`` directly. In a restricted-refspec
clone (``git clone --single-branch --branch``, the shape any tooling that
clones only one branch produces), ``origin/main`` never resolves locally,
so that raw command failed hard: ``fatal: bad revision 'origin/main'``,
exit 128 -- and every gate wired to it failed loudly for a reason that had
nothing to do with the diff it was supposed to grade.

This script replaces that raw invocation. It self-heals a missing base ref
before ever running the real diff: probe first (no fetch on the common
case, where the ref already exists locally), fetch with a destination
refspec only if the probe finds nothing, then re-verify -- never trusting
the fetch's own exit code alone (see ``_gitapex_base_ref.py``'s module
docstring for why a source-only fetch cannot be trusted here). Once the
ref is confirmed and a common ancestor exists, it execs the same ``git
diff`` the three gates always received, with this script's own stdout/
stderr left at their process-inherited defaults (no ``capture_output``/
``stdout=`` override) so the diff bytes reaching a gate's stdin are exactly
what git itself wrote -- byte-for-byte, including any non-UTF-8 byte git's
own ``core.quotePath=false`` path escaping can produce. (The outer runner,
``gitapex_gate_local_preflight.py``, still re-decodes this script's own
stdout one level up with its own pre-existing ``errors="replace"`` capture
-- unchanged, unaffected by this fix, not a regression: that capture layer
already existed for the raw ``git diff`` invocation this script replaces.)

**Hardcoded base remote/branch**, matching ``gitapex_gate_behind_base.py``'s
own posture (issue #985) rather than adding ``--remote``/``--branch``
flags: this repository has exactly one base branch today, and both gates
inherit the same two named residual risks that hardcode carries (a second
long-lived base branch, or a personal-fork ``origin`` remote) rather than
re-deriving them here.

**Three distinct failure messages before ever reaching the real diff** (the
diff's own exit code is never conflated with any of them):

1. The fetch itself fails (offline, unreachable remote, auth failure) --
   see :func:`_gitapex_base_ref.fetch_destination_refspec`.
2. The fetch reports success but the ref still does not resolve on
   re-verification -- ``ensure_base_ref``'s own "never trust the exit code
   alone" check.
3. The ref resolves but no common ancestor exists with ``HEAD`` -- a
   shallow clone's truncated history is the live-verified case (issue
   #1345's own repro), distinct from a missing ref: ``git merge-base``
   itself prints nothing to stderr in this exact case, so
   :func:`_gitapex_base_ref.require_common_ancestor`'s own message is the
   only informative signal available.

Any failure after that point (git diff itself exiting nonzero, a corrupt
object, a real diff-computation error) is an *ordinary diff failure*:
this script propagates git diff's own exit code and lets its own inherited
stderr carry whatever git itself wrote, rather than wrapping it in one of
the three messages above.

Exit codes: 0 (or whatever nonzero code ``git diff`` itself returns) once
the diff actually ran; 2 when the diff could not be trusted or produced at
all (bad ``--root``, no pathspecs, fetch failure, still-missing ref after a
reported-successful fetch, or no common ancestor).

Run via ``uv run`` (needed for the pydantic import, matching
``gitapex_gate_behind_base.py``'s own posture -- a bare ``python3``
invocation without pydantic installed fails at import time, before argparse
even runs): ``uv run --frozen python3
.github/scripts/gitapex_run_base_diff.py -- '*.py'``, or via the pytest
gate in ``tests/test_gitapex_run_base_diff.py``.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import _gitapex_base_ref
from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Hardcoded per the same posture gitapex_gate_behind_base.py's own
# BASE_REMOTE/BASE_BRANCH constants document (issue #985) -- see this
# module's own docstring for the named residual risks that posture carries.
BASE_REMOTE = "origin"
BASE_BRANCH = "main"

# Independent of gitapex_gate_local_preflight.py's own 1800s
# per-producer ceiling -- this is the ceiling for one git subprocess call
# this script makes (a probe, a fetch, a merge-base check, or the real
# diff), matching _gitapex_base_ref.GIT_TIMEOUT_SECONDS exactly rather than
# redefining 60 as a second literal.
GIT_TIMEOUT_SECONDS = _gitapex_base_ref.GIT_TIMEOUT_SECONDS


class DiffProducerError(Exception):
    """The diff could not be trusted or produced -- exit 2, never a silent
    empty diff and never conflated with git diff's own nonzero exit for an
    ordinary diff failure."""


def ensure_base_ref(root: pathlib.Path, remote: str, branch: str, *, timeout: int = GIT_TIMEOUT_SECONDS) -> None:
    """Make ``refs/remotes/<remote>/<branch>`` resolve locally, self-healing
    a missing one. A cheap peeled probe first -- the common case on an
    unrestricted clone, and the only case CI ever hits (CI never runs this
    script; see the module docstring). Only fetches when that probe finds
    nothing, and never trusts the fetch's own exit code alone: re-probes
    afterward and raises :class:`DiffProducerError` with a message distinct
    from a fetch failure when the ref still does not resolve even though
    the fetch itself reported success."""
    if _gitapex_base_ref.peeled_ref_exists(root, remote, branch, timeout=timeout, error_cls=DiffProducerError):
        return
    _gitapex_base_ref.fetch_destination_refspec(root, remote, branch, timeout=timeout, error_cls=DiffProducerError)
    if not _gitapex_base_ref.peeled_ref_exists(root, remote, branch, timeout=timeout, error_cls=DiffProducerError):
        raise DiffProducerError(
            f"git fetch {remote} {branch} reported success but refs/remotes/{remote}/{branch} "
            "still does not resolve -- never trusting a fetch's exit code alone (issue #1345)"
        )


def run_diff(
    root: pathlib.Path, remote: str, branch: str, pathspecs: list[str], *, timeout: int = GIT_TIMEOUT_SECONDS
) -> int:
    """:func:`ensure_base_ref`, then a common-ancestor check (the
    shallow-clone case gets its own distinct message here, before the real
    diff ever runs), then the real
    ``git diff -U0 --no-renames --merge-base <remote>/<branch> HEAD -- <pathspecs>``
    -- the exact invocation the three wired gates always received. Returns
    git diff's own exit code unmodified: an ordinary diff failure surfaces
    as whatever git wrote to this process's own inherited stderr, never one
    of :class:`DiffProducerError`'s three distinct pre-diff messages.

    Deliberately does not pass ``capture_output``/``stdout=`` -- this
    process's own stdout/stderr stay at their default, inherited file
    descriptors, so the diff bytes reaching a caller are exactly what git
    itself wrote (see the module docstring's own note on why this matters
    and why it does not change ``gitapex_gate_local_preflight.py``'s own,
    separate, unaffected capture one level up)."""
    ensure_base_ref(root, remote, branch, timeout=timeout)
    base_ref = f"{remote}/{branch}"
    _gitapex_base_ref.require_common_ancestor(root, base_ref, timeout=timeout, error_cls=DiffProducerError)

    try:
        # S603/S607 waived: a fixed argv list with no shell, `git` resolved
        # from PATH -- same rationale as every other gate script in this
        # file's family (gitapex_gate_behind_base.py, _gitapex_base_ref.py).
        completed = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "git",
                "-C",
                str(root),
                "-c",
                "core.quotePath=false",
                "diff",
                "-U0",
                "--no-renames",
                "--merge-base",
                base_ref,
                "HEAD",
                "--",
                *pathspecs,
            ],
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise DiffProducerError(f"git diff timed out after {timeout}s") from error
    except (OSError, subprocess.SubprocessError) as error:
        raise DiffProducerError(f"cannot run git diff: {error}") from error
    return completed.returncode


class RunBaseDiffArgs(BaseModel):
    """Typed view of ``main``'s parsed CLI namespace, mirroring
    ``gitapex_gate_behind_base.py``'s own ``GateBehindBaseArgs``: a
    ``--root`` pointing nowhere gets a clear, early error instead of the
    deeper git failure it would otherwise surface as an indistinguishable
    ``DiffProducerError``, and an empty ``pathspecs`` list gets the same
    treatment (argparse's own ``nargs="*"`` accepts zero positional
    arguments, which would otherwise reach ``git diff`` as a pathspec-less
    invocation grading the whole repository rather than the caller's
    intended scope)."""

    root: pathlib.Path
    pathspecs: list[str]

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value

    @field_validator("pathspecs")
    @classmethod
    def _pathspecs_must_be_nonempty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("at least one pathspec is required")
        return value


def main(argv: list[str] | None = None) -> int:
    """CLI: ``--root PATH -- PATHSPEC [PATHSPEC ...]``. Returns whatever
    ``git diff`` itself returns once it actually runs; 2 when the diff
    could not be trusted or produced at all."""
    parser = argparse.ArgumentParser(
        description="Self-healing local_stdin producer for the merge-base diff gates (issue #1345)."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Git working tree to diff (defaults to this checkout).",
    )
    parser.add_argument(
        "pathspecs",
        nargs="*",
        help="git pathspec(s) to scope the diff to, e.g. '*.py'.",
    )
    args = parser.parse_args(argv)

    try:
        validated = RunBaseDiffArgs(root=args.root, pathspecs=args.pathspecs)
    except ValidationError as error:
        fields = {detail["loc"][0] for detail in error.errors() if detail["loc"]}
        if "root" in fields:
            print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        if "pathspecs" in fields:
            print("error: at least one pathspec is required", file=sys.stderr)
        return 2

    try:
        return run_diff(validated.root, BASE_REMOTE, BASE_BRANCH, validated.pathspecs)
    except DiffProducerError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

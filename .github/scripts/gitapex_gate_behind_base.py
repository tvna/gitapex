#!/usr/bin/env python3
"""CI/local gate: fail the local preflight when the current branch is
behind its base.

Issue #985. 17 open retrospective issues (#896, #897, #914, #921, #927,
#935, #945, #946, #948, #951, #956, #958, #966, #970, #972, #973, #974)
proposed or carried this check forward -- #927 is the original proposal --
without ever building it. The gap has cost real repairs on both sides of
the CI signal: PR #947's cycle (issue #948) produced a red `pytest` run
against a stale base, and PR #961's cycle (issue #966) cost a full extra
push-and-CI cycle even though every required check passed on the head
commit, because the branch was four commits behind `origin/main` at open.

**The rule.** `git rev-list --left-right --count origin/main...HEAD` gives
two counts: commits reachable from `origin/main` but not `HEAD` (behind),
and commits reachable from `HEAD` but not `origin/main` (ahead). This gate
fails when the behind count is greater than zero and passes -- regardless
of the ahead count -- when it is zero.

**Base ref is `origin/main`, hardcoded.** This matches
`gitapex_gate_exception_handler_gaps.py`'s own existing `local_stdin`
convention rather than resolving a per-branch upstream: `main` is the only
base branch in this repository's flow today. Wrong the day this repository
grows a second long-lived base branch -- named as a residual risk in issue
#985's Acceptance Criteria Map, not solved here. The cost of getting it
wrong is a false FAIL with an obvious message, not a silent pass.

**This gate fetches its own base ref before comparing** -- the requester's
recorded decision in issue #985, chosen over reading a possibly-stale
local ref or checking a freshness TTL. This is the first network call in
an otherwise fully offline local-preflight runner
(`gitapex_gate_local_preflight.py`), and that posture change is deliberate:
a stale local `origin/main` is exactly the failure mode this gate exists
to catch (PR #961's session had one four commits stale until fetched), so
comparing against anything less than a freshly fetched ref would defeat
the gate's own purpose.

**A failed fetch never becomes a silent pass.** An offline machine, an
unreachable remote, or an auth failure raises `GateError` and exits 2 with
a message naming the fetch failure specifically -- distinct from the exit
1 "you are behind" message -- and the behind-count comparison is never
reached. There is deliberately no fallback to comparing against the local
ref: an unverifiable "behind" answer is worse than a loud refusal to
answer at all. There is likewise deliberately no offline escape hatch (an
environment variable, a skip flag): issue #985 leaves that decision
pending the requester's call once the FAIL has been seen in practice,
rather than designing one in speculatively.

Exit codes: 0 up to date, 1 behind base, 2 the check could not be trusted
(fetch failed, the comparison itself failed, or `--root` is not a usable
git working tree) -- mirrors `gitapex_gate_hidden_characters.py`'s own
0/1/2 convention.

Run standalone: ``python3 .github/scripts/gitapex_gate_behind_base.py``
(compares this checkout's ``HEAD`` against a freshly fetched
``origin/main``), or via the pytest gate in
``tests/test_gitapex_gate_behind_base.py``.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Hardcoded per issue #985's recorded decision -- see the module docstring's
# "Base ref is origin/main, hardcoded" section for why and its named risk.
BASE_REMOTE = "origin"
BASE_BRANCH = "main"


class GateError(Exception):
    """The check could not be trusted -- exit 2, never a silent pass and
    never conflated with a genuinely behind branch (exit 1)."""


@dataclass(frozen=True)
class BehindBaseCount:
    """Both counts `git rev-list --left-right --count` reports. Only
    ``behind`` gates this check; ``ahead`` is carried through for the
    passing message so a contributor sees the full picture."""

    behind: int
    ahead: int


def fetch_base(root: pathlib.Path, remote: str = BASE_REMOTE, branch: str = BASE_BRANCH) -> None:
    """Fetch ``branch`` from ``remote`` so the comparison in
    :func:`count_behind` reads real remote state rather than whatever ref
    this checkout last pulled. Raises :class:`GateError` -- never falls
    back to a possibly-stale local ref -- on any fetch failure: an offline
    machine, an unreachable remote, or an auth failure."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git` is
        # intentionally resolved from PATH -- pinning an absolute path
        # would break the three environments this has to run in (GitHub
        # runner, the nix devShell, a contributor's machine). Same
        # rationale as every other gate script in this file's family.
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "fetch", remote, branch],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise GateError(f"cannot run git to fetch {remote} {branch}: {error}") from error
    if result.returncode != 0:
        raise GateError(f"git fetch {remote} {branch} failed: {result.stderr.strip()}")


def count_behind(root: pathlib.Path, remote: str = BASE_REMOTE, branch: str = BASE_BRANCH) -> BehindBaseCount:
    """Behind/ahead counts between ``{remote}/{branch}`` and ``HEAD``. Must
    run after :func:`fetch_base` so the comparison ref is current. Raises
    :class:`GateError` -- distinct from a fetch failure -- when the
    comparison itself cannot be computed (e.g. no common ancestor)."""
    base_ref = f"{remote}/{branch}"
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "rev-list", "--left-right", "--count", f"{base_ref}...HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise GateError(f"cannot run git to compare against {base_ref}: {error}") from error
    if result.returncode != 0:
        raise GateError(f"git rev-list against {base_ref} failed: {result.stderr.strip()}")
    try:
        left, right = result.stdout.split()
        return BehindBaseCount(behind=int(left), ahead=int(right))
    except ValueError as error:
        raise GateError(f"unexpected 'git rev-list --left-right --count' output: {result.stdout!r}") from error


class GateBehindBaseArgs:
    """Typed view of ``main``'s parsed CLI namespace. ``root`` must be an
    existing directory, mirroring ``gitapex_gate_hidden_characters.py``'s own
    ``GateHiddenCharactersArgs``: a ``--root`` pointing nowhere gets a clear,
    early error instead of the deeper git failure it would otherwise
    surface as an indistinguishable ``GateError``."""

    def __init__(self, *, root: pathlib.Path) -> None:
        if not root.is_dir():
            raise ValueError(f"--root must be an existing directory, got {root}")
        self.root = root


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 up to date, 1 behind base, 2 the check could not be trusted."""
    parser = argparse.ArgumentParser(
        description="Fetch origin/main and fail when the current branch is behind it (issue #985)."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Git working tree to check (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateBehindBaseArgs(root=args.root)
    except ValueError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    base_ref = f"{BASE_REMOTE}/{BASE_BRANCH}"
    try:
        fetch_base(validated.root)
        count = count_behind(validated.root)
    except GateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if count.behind > 0:
        print(
            f"FAIL: this branch is {count.behind} commit(s) behind {base_ref}. "
            f"Merge or rebase onto {base_ref} before pushing (issue #985).",
            file=sys.stderr,
        )
        return 1

    print(f"OK: up to date with {base_ref} ({count.ahead} commit(s) ahead).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

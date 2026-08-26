#!/usr/bin/env python3
"""Local-preflight gate: fail the local preflight when the current branch
is behind its base.

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

**Base ref is `origin/main`, hardcoded.** This matches the existing
`exception-handler-gap` gate's own `local_stdin` producer argv in
`.gitapex/ssot.json` (`git diff ... --merge-base origin/main HEAD`, consumed
generically by `gitapex_gate_local_preflight.py` -- the hardcode lives in
the registry entry, not inside `gitapex_gate_exception_handler_gaps.py`
itself) rather than resolving a per-branch upstream: `main` is the only
base branch in this repository's flow today. Two named residual risks, not
solved here: this breaks the day the repository grows a second long-lived
base branch (issue #985's own Acceptance Criteria Map), and it silently
compares against the wrong history if the local `origin` remote is a
personal fork rather than the canonical repository -- a standard
fork-workflow shape this repository's own `CONTRIBUTING.md` does not
currently document but does not rule out either. In both cases the cost of
getting it wrong is a plausible-looking but wrong verdict, not a crash --
the same class of risk `hooks/check-pr-upstream-pushed.sh`'s own
`@{upstream}` resolution exists for a different question (a branch's push
destination, not its merge-base), and is not a substitute here.

**This gate fetches its own base ref before comparing** -- the requester's
recorded decision in issue #985, chosen over reading a possibly-stale
local ref or checking a freshness TTL. That posture change was, at the
time, the first network call in an otherwise fully offline local-preflight
runner (`gitapex_gate_local_preflight.py`); issue #1345 ended that
distinction by giving `gitapex_run_base_diff.py` (run via `uv run`, the
shared `local_stdin` producer for `exception-handler-gap`,
`stdlib-only-claim-drift`, and `detection-logic-property-coverage`) a
network call of its own, so this gate is no longer the only one. The two fetches still differ in *when*
they run, deliberately: a stale local `origin/main` is exactly the failure
mode this gate exists to catch (PR #961's session had one four commits
stale until fetched), so this gate fetches on every run regardless of
whether a local ref already exists -- comparing against anything less than
a freshly fetched ref would defeat its own purpose.
`gitapex_run_base_diff.py` only needs the ref to *exist*, not to be
current, so it fetches only when a peeled probe finds nothing at all (this
module's own Known-limits section above names the staleness caveat that
leaves open). Both fetches now share their actual `git fetch`
implementation, `_gitapex_base_ref.fetch_destination_refspec` (issue
#1345) -- the refspec shape changed from a source-only form to a
destination refspec (`+refs/heads/main:refs/remotes/origin/main`), which
fixes a real defect this gate carried since issue #985: a restricted-
refspec clone (`git clone --single-branch --branch`) never materialized
`refs/remotes/origin/main` from a source-only fetch, so this gate
previously failed closed with `GateError` on every push from such a
clone, permanently. This is a disclosed behavior change, not a silent
refactor -- see the PR body for issue #1345.

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

**Registered `local`-only (no `ci` plane) -- this repository's first gate
with that shape, and a deliberate, disclosed choice rather than an
oversight.** Its only enforcement is therefore the `pre-push` hook
`gitapex_gate_local_preflight.py` wires it into: bypassable with
`git push --no-verify`, and absent entirely on a clone that never ran
`prek install` (both documented limits `gitapex_gate_local_preflight.py`'s
own docstring already names for every gate it wires, not new to this
one). The considered alternative is infrastructure-owned, not another
repository-authored gate: GitHub's branch-protection ruleset already
supports `strict_required_status_checks_policy` -- "pull requests
targeting a matching branch must be tested with the latest code" -- which
would enforce the same freshness requirement natively, ahead of merge,
with no bypass. Issue #985's Acceptance Criteria Map leaves adding a `ci`
plane (or flipping that ruleset setting) as an open decision for a later
pass, not a gap in this one: GitHub already surfaces behind-ness on the
PR itself, so a CI-side copy of this exact check may be redundant rather
than defensive, and that argument belongs in the PR body, not asserted
away here.

This gate's own production invocation (its `.gitapex/ssot.json`
`local_invocation`, dispatched by `gitapex_gate_local_preflight.py`) runs
under `uv run`, so a real `pydantic` import is safe here (issue #1040,
refs #1035's `uv run` standardization that made this class of dependency
safe repo-wide).

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs): ``uv run --frozen python3
.github/scripts/gitapex_gate_behind_base.py`` (compares this checkout's
``HEAD`` against a freshly fetched ``origin/main``), or via the pytest
gate in ``tests/test_gitapex_gate_behind_base.py``.
"""

from __future__ import annotations

import argparse
import pathlib

# Kept even though this module's own git calls moved to _gitapex_base_ref
# (issue #1345): tests/test_gitapex_gate_behind_base.py monkeypatches
# `gate.subprocess.run` directly, and `subprocess` is one process-global
# module object either way, so this import stays the patch target.
import subprocess  # noqa: F401
import sys
from dataclasses import dataclass

import _gitapex_base_ref
from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Hardcoded per issue #985's recorded decision -- see the module docstring's
# "Base ref is origin/main, hardcoded" section for why and its named risk.
BASE_REMOTE = "origin"
BASE_BRANCH = "main"

# Ceiling for one git subprocess (fetch, merge-base, or rev-list). This
# gate has no ceiling of its own otherwise: run through
# gitapex_gate_local_preflight.py it would only be bounded by that
# runner's own DEFAULT_TIMEOUT_SECONDS = 1800, sized for mypy's worst
# case, not a git call -- and run standalone (the CLI, or the pytest gate
# in tests/test_gitapex_gate_behind_base.py) it would have no bound at
# all. 60s is generous for a local merge-base/rev-list (near-instant) and
# for a fetch over an ordinary network, while still failing loudly on a
# hung connection instead of blocking indefinitely. Sourced from
# _gitapex_base_ref (issue #1345) rather than redefined as a second literal
# -- gitapex_run_base_diff.py shares the same constant.
GIT_TIMEOUT_SECONDS = _gitapex_base_ref.GIT_TIMEOUT_SECONDS


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
    machine, an unreachable remote, an auth failure, or a hang.

    Delegates to :func:`_gitapex_base_ref.fetch_destination_refspec`
    (issue #1345): only the fetch's own refspec shape changed (a
    destination refspec, not the source-only form this gate used before --
    see that module's own docstring for why the source-only form silently
    fails to materialize the ref in a restricted-refspec clone), never the
    message text this function raises, so every pre-#1345 test asserting
    on it keeps matching unmodified. Unlike
    ``gitapex_run_base_diff.py``'s own ``ensure_base_ref`` (issue #1345),
    this gate keeps its pre-#1345 unconditional-fetch-every-run posture --
    see the module docstring for why."""
    _gitapex_base_ref.fetch_destination_refspec(root, remote, branch, timeout=GIT_TIMEOUT_SECONDS, error_cls=GateError)


def count_behind(root: pathlib.Path, remote: str = BASE_REMOTE, branch: str = BASE_BRANCH) -> BehindBaseCount:
    """Behind/ahead counts between ``{remote}/{branch}`` and ``HEAD``. Must
    run after :func:`fetch_base` so the comparison ref is current. Raises
    :class:`GateError` -- distinct from a fetch failure -- when the
    comparison itself cannot be computed: no common ancestor (checked by
    :func:`_gitapex_base_ref.require_common_ancestor` first, extracted
    there verbatim -- message text included -- in issue #1345 so
    ``gitapex_run_base_diff.py`` shares the identical shallow-clone-aware
    check rather than duplicating it), a ``rev-list`` failure, or
    unparseable ``rev-list`` output."""
    base_ref = f"{remote}/{branch}"
    _gitapex_base_ref.require_common_ancestor(root, base_ref, timeout=GIT_TIMEOUT_SECONDS, error_cls=GateError)
    result = _gitapex_base_ref.run_git(
        root,
        ["rev-list", "--left-right", "--count", f"{base_ref}...HEAD"],
        label=f"compare against {base_ref}",
        timeout=GIT_TIMEOUT_SECONDS,
        error_cls=GateError,
    )
    if result.returncode != 0:
        raise GateError(f"git rev-list against {base_ref} failed: {result.stderr.strip()}")
    try:
        left, right = result.stdout.split()
        return BehindBaseCount(behind=int(left), ahead=int(right))
    except ValueError as error:
        raise GateError(f"unexpected 'git rev-list --left-right --count' output: {result.stdout!r}") from error


class GateBehindBaseArgs(BaseModel):
    """Typed view of ``main``'s parsed CLI namespace. ``root`` must be an
    existing directory, mirroring ``gitapex_gate_hidden_characters.py``'s own
    ``GateHiddenCharactersArgs``: a ``--root`` pointing nowhere gets a clear,
    early error instead of the deeper git failure it would otherwise
    surface as an indistinguishable ``GateError``."""

    root: pathlib.Path

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value


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
    except ValidationError:
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

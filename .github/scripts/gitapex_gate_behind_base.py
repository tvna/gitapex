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

# Ceiling for one git subprocess (fetch, merge-base, or rev-list). This
# gate has no ceiling of its own otherwise: run through
# gitapex_gate_local_preflight.py it would only be bounded by that
# runner's own DEFAULT_TIMEOUT_SECONDS = 1800, sized for mypy's worst
# case, not a git call -- and run standalone (the CLI, or the pytest gate
# in tests/test_gitapex_gate_behind_base.py) it would have no bound at
# all. 60s is generous for a local merge-base/rev-list (near-instant) and
# for a fetch over an ordinary network, while still failing loudly on a
# hung connection instead of blocking indefinitely.
GIT_TIMEOUT_SECONDS = 60


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


def _run_git(root: pathlib.Path, args: list[str], *, label: str) -> subprocess.CompletedProcess[str]:
    """Run ``git -C root <args>`` and return the completed process,
    regardless of its exit code -- callers decide what a nonzero
    ``returncode`` means for their own step. Raises :class:`GateError` for
    every way the subprocess itself can fail to produce one: a missing
    ``git`` executable, a hang past :data:`GIT_TIMEOUT_SECONDS`, or any
    other subprocess-layer failure.

    ``errors="replace"`` rather than ``text=True``'s own strict default,
    matching ``gitapex_gate_local_preflight.py``'s own ``_run`` and the
    documented regression behind it: a byte sequence on stdout/stderr that
    is not valid UTF-8 (a corrupted object, a non-ASCII remote error
    message) otherwise raises ``UnicodeDecodeError`` -- a ``ValueError``.
    ``errors="replace"`` closes the one known decode path, but
    ``gitapex_gate_local_preflight.py``'s own ``run_check`` additionally
    catches ``ValueError``/``subprocess.SubprocessError`` as defense in
    depth against any other layer raising one, on the documented reasoning
    that a decode failure escaping as an uncaught traceback -- exit code 1,
    indistinguishable from this gate's own documented exit-1 "behind base"
    FAIL -- is a worse outcome than one extra except clause; this function
    matches that same defense-in-depth shape rather than trusting
    ``errors="replace"`` alone."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git` is
        # intentionally resolved from PATH -- pinning an absolute path
        # would break the three environments this has to run in (GitHub
        # runner, the nix devShell, a contributor's machine). Same
        # rationale as every other gate script in this file's family.
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(root), *args],  # noqa: S607
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise GateError(f"git {label} timed out after {GIT_TIMEOUT_SECONDS}s") from error
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise GateError(f"cannot run git to {label}: {error}") from error


def fetch_base(root: pathlib.Path, remote: str = BASE_REMOTE, branch: str = BASE_BRANCH) -> None:
    """Fetch ``branch`` from ``remote`` so the comparison in
    :func:`count_behind` reads real remote state rather than whatever ref
    this checkout last pulled. Raises :class:`GateError` -- never falls
    back to a possibly-stale local ref -- on any fetch failure: an offline
    machine, an unreachable remote, an auth failure, or a hang."""
    result = _run_git(root, ["fetch", remote, branch], label=f"fetch {remote} {branch}")
    if result.returncode != 0:
        raise GateError(f"git fetch {remote} {branch} failed: {result.stderr.strip()}")


def _require_common_ancestor(root: pathlib.Path, base_ref: str) -> None:
    """Raise :class:`GateError` when ``git merge-base`` cannot find a
    common ancestor between ``base_ref`` and ``HEAD``. Checked explicitly,
    before the ``rev-list`` call in :func:`count_behind`: unrelated
    histories do not make ``git rev-list --left-right --count
    base_ref...HEAD`` fail -- it silently returns a numeric ahead/behind
    pair for the *empty* merge base, which would otherwise produce a
    plausible-looking but meaningless behind-base FAIL (exit 1, "merge or
    rebase") instead of the honest "this comparison cannot be trusted"
    signal (exit 2) this case actually needs. Verified directly against a
    real orphan-history pair, not assumed.

    The raised message deliberately does not assert *why* no common
    ancestor was found -- a nonzero ``merge-base`` exit has more than one
    real cause (genuinely unrelated histories, ``base_ref`` never fetched
    locally, or a shallow clone whose truncated history does not reach far
    enough back), and this function cannot distinguish them from the exit
    code alone. Naming one as though it were established (a prior revision
    of this message unconditionally said "unrelated histories") would
    mislead a contributor debugging a shallow-clone or missing-ref case
    toward the wrong fix; git's own stderr, appended verbatim, carries
    whatever specificity is actually available."""
    result = _run_git(root, ["merge-base", base_ref, "HEAD"], label=f"find a common ancestor with {base_ref}")
    if result.returncode != 0:
        raise GateError(
            f"cannot find a common ancestor between {base_ref} and HEAD -- unrelated histories, "
            f"{base_ref} not yet fetched, or a shallow clone: {result.stderr.strip()}"
        )


def count_behind(root: pathlib.Path, remote: str = BASE_REMOTE, branch: str = BASE_BRANCH) -> BehindBaseCount:
    """Behind/ahead counts between ``{remote}/{branch}`` and ``HEAD``. Must
    run after :func:`fetch_base` so the comparison ref is current. Raises
    :class:`GateError` -- distinct from a fetch failure -- when the
    comparison itself cannot be computed: no common ancestor (checked by
    :func:`_require_common_ancestor` first), a ``rev-list`` failure, or
    unparseable ``rev-list`` output."""
    base_ref = f"{remote}/{branch}"
    _require_common_ancestor(root, base_ref)
    result = _run_git(
        root, ["rev-list", "--left-right", "--count", f"{base_ref}...HEAD"], label=f"compare against {base_ref}"
    )
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

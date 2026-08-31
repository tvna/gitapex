"""Drift gate for the `/.claude/hooks/*` + negation `.gitignore` invariant
(issues #57, #690).

A bare `/.claude/hooks/` directory-match prunes the directory from git's
traversal entirely, so a later `!` negation for a file inside it is never
even evaluated (`git help gitignore`'s own documented example: "It is not
possible to re-include a file if a parent directory of that file is
excluded."). The fix replaces that bare dir-match with the glob
`/.claude/hooks/*` (excludes each direct child individually, without pruning
the parent directory itself) plus a negation for the one file that must stay
tracked. This test proves both halves hold against real `git check-ignore`
behavior, and also satisfies
`.github/scripts/gitapex_gate_gitignore_pattern_coverage.py`'s requirement that
every pattern added to `.gitignore` in a diff be referenced, literally, by
some test under `tests/` (see that gate's own module docstring, issue #330).

Verified note on `git check-ignore -v`'s exit code (git 2.43.0): `-v`
reports the deciding pattern for a path even when that pattern is a
negation, and returns exit 0 whenever *any* pattern decided the path's fate
-- ignore or un-ignore alike -- only returning 1 when no pattern touches the
path at all. This also depends on whether the path is already staged: for
an untracked negated path, `-v` prints the negation match and exits 0; once
the same path is added to the index, `-v` stops reporting on it entirely,
printing nothing and exiting 1. Plain (non-verbose) `git check-ignore` has
neither wrinkle: it returns 0 only for a path that ends up effectively
ignored and 1 otherwise (negated or untouched, staged or not), which is the
boolean this test needs regardless of when it happens to run relative to
`git add`, so `test_session_start_hook_is_not_gitignored` below
intentionally omits `-v`.
"""

from __future__ import annotations

import subprocess

from conftest import REPO_ROOT, assert_path_is_gitignored

# The exact two patterns this test proves work -- also the literal anchors
# gitapex_gate_gitignore_pattern_coverage.py's core-token search needs to find so
# this pair doesn't get reported as untested when added to .gitignore.
_HOOKS_GLOB_PATTERN = "/.claude/hooks/*"
_SESSION_START_NEGATION = "!/.claude/hooks/session-start.sh"


def test_apm_vendored_hooks_still_gitignored() -> None:
    # Representative files under both apm-vendored subtrees. The
    # superpowers one is a leftover an `apm install` re-run no longer
    # deploys (issue #1597 dropped `obra/superpowers` from apm.yml/
    # apm.lock.yaml, but apm install does not prune an already-deployed
    # directory once its manifest entry is gone) -- still a real path in
    # any checkout that ran apm install before the retirement, though no
    # longer guaranteed on a fresh clone; the gitignore pattern itself is
    # path-based and does not require the file to exist either way. The
    # clairvoyance one is nested two levels under its own hooks/ dir,
    # proving the glob fix still ignores an entire excluded child
    # directory's contents recursively -- excluding
    # `.claude/hooks/clairvoyance` itself (a directory) via the `*` glob
    # still prunes traversal *into* that one subdirectory, same as before;
    # only `.claude/hooks/` itself is no longer pruned as a whole.
    assert_path_is_gitignored(
        REPO_ROOT / ".claude" / "hooks" / "superpowers" / "hooks" / "run-hook.cmd",
        f"{_HOOKS_GLOB_PATTERN!r} (apm-vendored superpowers subtree)",
    )
    assert_path_is_gitignored(
        REPO_ROOT / ".claude" / "hooks" / "clairvoyance" / "hooks" / "lib" / "json-escape.sh",
        f"{_HOOKS_GLOB_PATTERN!r} (apm-vendored clairvoyance subtree, nested)",
    )


def test_session_start_hook_is_not_gitignored() -> None:
    # Regression for the parent-directory-prune pitfall: a bare
    # '/.claude/hooks/' dir-match would silently swallow this negation and
    # this test would fail loudly instead.
    path = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"
    result = subprocess.run(
        ["git", "check-ignore", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"{_SESSION_START_NEGATION!r} did not take effect -- "
        "'.claude/hooks/session-start.sh' is unexpectedly gitignored "
        f"(git check-ignore exit {result.returncode}, stdout={result.stdout!r})"
    )

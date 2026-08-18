#!/usr/bin/env python3
"""Run this repository's mypy checks as a pre-commit hook (issue #725).

`.github/workflows/test.yml`'s own `mypy` job deliberately runs mypy as
several separate per-directory-group invocations, not one repo-wide sweep:
two files share the literal basename ``gitapex_check_acm_present.py`` in unrelated
directories (``skills/drafting-an-acm-issue/scripts`` and
``skills/planning-a-branch-from-an-issue/scripts``), and with no
``__init__.py`` anywhere in this repo, mypy resolves a bare module name the
same way pytest's own ``pythonpath`` does -- combining both into one
invocation errors "Duplicate module named". This script mirrors that same
group list (kept in sync with ``test.yml``'s `mypy` job by convention, cross-
referenced rather than generated, the same style ``pyproject.toml``'s own
``[tool.mypy]`` comments already use for this exact job) so the local
pre-commit hook catches the same errors CI would, before a commit exists.

Residual risk, named by issue #725 itself rather than left implicit: this
checks each whole configured group, not only staged files, so it is not as
fast as the ruff hooks alongside it on a large repo. Scoping to changed
files was explicitly deferred as a follow-up (the "Duplicate module named"
constraint above means a naive changed-files list can't just be handed to
one mypy invocation either).
"""

from __future__ import annotations

import subprocess
import sys

# Matches .github/workflows/test.yml's `mypy` job's own `timeout-minutes: 10`
# for the whole job -- a per-group ceiling here, so a hung `mypy` process
# fails the commit loudly instead of blocking `git commit` indefinitely (a
# git hook has no built-in subprocess timeout of its own).
_GROUP_TIMEOUT_SECONDS = 600

# Kept in sync with .github/workflows/test.yml's `mypy` job -- see that
# job's own step comments for why the first group bundles multiple
# directories (pythonpath-linked roots) while the rest are each checked
# alone.
MYPY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "tests + pythonpath-linked roots",
        (
            "tests",
            "hooks",
            ".github/scripts",
            "evals/scripts",
            "skills/battle-testing-a-skill/scripts",
            "skills/scorer-gated-skill-edits/scripts",
            "skills/evaluating-skill-quality/scripts",
            "skills/auditing-agent-product-scope/scripts",
            "skills/evaluating-deterministic-gate-quality/scripts",
            "skills/drafting-an-acm-issue/scripts",
        ),
    ),
    ("skills/executing-a-branch-plan/scripts", ("skills/executing-a-branch-plan/scripts",)),
    ("skills/drafting-an-adr/scripts", ("skills/drafting-an-adr/scripts",)),
    ("skills/scanning-attack-surfaces/scripts", ("skills/scanning-attack-surfaces/scripts",)),
    ("skills/outward-artifact-preflight/scripts", ("skills/outward-artifact-preflight/scripts",)),
    ("skills/planning-a-branch-from-an-issue/scripts", ("skills/planning-a-branch-from-an-issue/scripts",)),
    ("skills/setup-gitapex-toolchain/scripts", ("skills/setup-gitapex-toolchain/scripts",)),
)


def run_group(dirs: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    """Run one mypy group invocation and return its completed process."""
    # S603/S607 waived: a fixed argv list with no shell, and `uv` is
    # intentionally resolved from PATH -- pinning an absolute path would
    # break the three environments this has to run in (GitHub runner, the
    # nix devShell, a contributor's machine).
    return subprocess.run(  # noqa: S603
        ["uv", "run", "--frozen", "mypy", "--config-file", "pyproject.toml", *dirs],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=_GROUP_TIMEOUT_SECONDS,
    )


def main() -> int:
    failed: list[str] = []
    for label, dirs in MYPY_GROUPS:
        try:
            result = run_group(dirs)
        except subprocess.TimeoutExpired:
            failed.append(label)
            print(f"mypy ({label}) timed out after {_GROUP_TIMEOUT_SECONDS}s", file=sys.stderr)
            continue
        if result.returncode != 0:
            failed.append(label)
            print(f"mypy ({label}) failed:")
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
    if failed:
        print(f"mypy failed for: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("mypy: all groups clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

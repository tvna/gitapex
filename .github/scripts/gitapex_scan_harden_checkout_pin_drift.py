#!/usr/bin/env python3
"""Guard the harden-checkout composite action's self-reference pin.

.github/actions/harden-checkout/action.yml wraps the Harden runner + Checkout
step pair now shared by all 25 gate workflows (issue #813). Because it is a
*local* composite action referenced from a workflow step that runs before
checkout, each calling workflow must pin it by its full remote form
(``uses: tvna/gitapex/.github/actions/harden-checkout@<sha>``) rather than a
``./``-relative path -- a local-path ``uses:`` can't resolve until checkout
has already happened, which is the chicken-and-egg problem the action itself
exists to solve. That SHA has no automatic-update mechanism: if the action
file changes without every calling workflow's pin being bumped to match, some
gates silently keep running the old harden-runner/checkout behavior while
others pick up the new one.

This scanner is the drift gate: it fails if any workflow's pinned SHA for the
composite action does not match the action file's own current commit SHA
(the most recent commit that touched
``.github/actions/harden-checkout/action.yml``). Unlike
``gitapex_scan_toolchain_pin_drift.py``, whose "current" value is a fixed
literal, this gate's "current" value is computed live via ``git log`` --
callers must run it inside a checkout with enough history for that path's
last-touching commit to be reachable (a shallow ``fetch-depth: 1`` clone is
not enough; see test.yml's pytest job, which passes ``fetch-depth: '0'``).

Run standalone (exit 1 on drift) or via the pytest gate in
tests/test_gitapex_scan_harden_checkout_pin_drift.py.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ACTION_PATH = pathlib.Path(".github/actions/harden-checkout/action.yml")
WORKFLOWS_DIR = pathlib.Path(".github/workflows")
ACTION_REF = "tvna/gitapex/.github/actions/harden-checkout"

# Captures the whole ref token after `@`, not just a 40-hex-char shape: a
# short SHA or a mutable branch/tag ref must still be caught as a finding
# (this action's convention requires a full commit SHA), not silently pass
# through unmatched the way an anchored `{40}` pattern would.
_USES_RE = re.compile(re.escape(ACTION_REF) + r"@(\S+)")
_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")


def current_action_sha(repo_root: pathlib.Path | None = None) -> str:
    """Return the SHA of the most recent commit that touched the composite
    action file. Raises RuntimeError if that history isn't resolvable --
    fail loudly rather than let an empty result read as "no drift"."""
    root = repo_root if repo_root is not None else pathlib.Path()
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "log", "-1", "--format=%H", "--", str(ACTION_PATH)],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        # Fail loudly with a clear message instead of letting a raw
        # CalledProcessError/traceback escape main()'s RuntimeError handler
        # (e.g. `root` isn't a git repository, or `git` isn't on PATH).
        raise RuntimeError(f"`git log` failed for {ACTION_PATH} in {root}: {exc}") from exc
    sha = result.stdout.strip()
    if not sha:
        raise RuntimeError(
            f"no commit history found for {ACTION_PATH} in {root} -- "
            "has it been committed, and is enough history fetched (fetch-depth: 0)?"
        )
    return sha


def find_drift(
    workflows_dir: pathlib.Path = WORKFLOWS_DIR,
    repo_root: pathlib.Path | None = None,
) -> list[tuple[str, int, str]]:
    """Return (file, line_number, line) for each workflow pin that doesn't
    match the composite action's current commit SHA -- including a pin that
    isn't a full 40-hex-char SHA at all. Empty list means no drift. Raises
    RuntimeError if workflows_dir doesn't exist -- an empty scan must never
    read the same as a clean one."""
    if not workflows_dir.is_dir():
        raise RuntimeError(f"workflows directory not found: {workflows_dir}")
    current_sha = current_action_sha(repo_root)
    findings: list[tuple[str, int, str]] = []
    for workflow in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        try:
            content = workflow.read_text()
        except UnicodeDecodeError as exc:
            # Fail closed, not skip: see gitapex_scan_toolchain_pin_drift.py's
            # identical rationale -- an undecodable file can't be verified
            # clean, so it's reported rather than silently passed over.
            findings.append((str(workflow), 0, f"could not decode as UTF-8, cannot verify: {exc}"))
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            match = _USES_RE.search(line)
            if not match:
                continue
            pinned_ref = match.group(1)
            if not _FULL_SHA_RE.fullmatch(pinned_ref) or pinned_ref != current_sha:
                findings.append((str(workflow), lineno, line.strip()))
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except RuntimeError as exc:
        print(f"harden-checkout pin drift check could not run: {exc}")
        return 1
    if findings:
        print(
            "harden-checkout composite action pin drift: these workflow pins no "
            "longer match .github/actions/harden-checkout/action.yml's current commit SHA:"
        )
        for path, lineno, line in findings:
            print(f"  {path}:{lineno}: {line}")
        return 1
    print("No harden-checkout pin drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

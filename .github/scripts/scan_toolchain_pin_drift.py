#!/usr/bin/env python3
"""Guard the toolchain single-source-of-truth invariant.

The external toolchain's Class B tools (waza, apm, rtk, betterleaks) are pinned
and provisioned exactly once, in ``flake.nix``. A CI workflow must therefore
obtain them from the flake (``nix run``/``nix develop``), never re-install them
by hand -- a second install path would recreate the version drift that PR-2 of
issue #57 removed (waza used to be pinned both in a workflow's ``go install``
and in the flake).

This scanner is the drift gate shipped alongside that invariant: it fails if any
``.github/workflows/*`` file references a Class B tool's upstream repository in
an install context (a ``go install`` of it, a release-download URL, or its
install script). ``flake.nix`` itself legitimately holds those URLs, so only the
workflows directory is scanned.

Scope (deliberately narrow to stay false-positive free): it does not yet check
hardcoded *version strings* -- that broader check rides with the generated
``toolchain.lock.json`` drift scan in PR-4. Run standalone (exit 1 on drift) or
via the pytest gate in ``tests/test_scan_toolchain_pin_drift.py``.
"""

from __future__ import annotations

import pathlib
import sys

# Upstream repositories of the flake-owned Class B tools. Matched as full
# ``owner/repo`` strings so ordinary text (a step named "Run waza check") does
# not trip the scan -- only a real repo reference does.
CLASS_B_REPOS = (
    "microsoft/waza",
    "microsoft/apm",
    "rtk-ai/rtk",
    "betterleaks/betterleaks",
)

WORKFLOWS_DIR = pathlib.Path(".github/workflows")


def find_drift(workflows_dir: pathlib.Path = WORKFLOWS_DIR) -> list[tuple[str, int, str]]:
    """Return (file, line_number, line) for each workflow line that provisions a
    flake-owned Class B tool from outside the flake. Empty list means no drift."""
    findings: list[tuple[str, int, str]] = []
    for workflow in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        try:
            content = workflow.read_text()
        except UnicodeDecodeError as exc:
            # A workflow file that isn't valid text can't be scanned for
            # Class B repo references -- skip it with a warning rather than
            # crashing the whole scan (and losing findings from every other
            # file) with an unhandled traceback.
            print(f"warning: skipping {workflow}: {exc}", file=sys.stderr)
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if any(repo in line for repo in CLASS_B_REPOS):
                findings.append((str(workflow), lineno, line.strip()))
    return findings


def main() -> int:
    findings = find_drift()
    if findings:
        print(
            "Toolchain pin drift: Class B tools must be provisioned via the flake "
            "(nix run/nix develop), not referenced/installed in a workflow:"
        )
        for path, lineno, line in findings:
            print(f"  {path}:{lineno}: {line}")
        return 1
    print("No toolchain pin drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

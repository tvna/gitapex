#!/usr/bin/env python3
"""Find third-party GitHub Actions pinned to a mutable ref instead of a SHA.

This is the one git-hosting-surface-audit checklist item with real,
existing precedent in this repo: `.github/scripts/scan_toolchain_pin_drift.py`
already walks `.github/workflows/*.yml` line by line looking for a drift
pattern and reports `(file, line_number, line)` tuples with a 0/1 exit-code
CLI. This script reuses that exact shape (same walk, same tuple return, same
main()/exit-code convention) for a different pattern: a `uses:` step pinned
to a tag or branch (`@v4`, `@main`) rather than a full 40-character commit
SHA. A mutable ref lets the action's upstream owner change what code runs on
the next build without the consuming workflow's diff showing it.

Scope: GitHub Actions workflow files only. The git-hosting-surface-audit
design doc marks the equivalent GitLab CI `include:` check as a stated gap
(no GitLab MCP server in this environment) -- this script does not attempt
that check.

Usage: python3 scan_unpinned_actions.py [workflows_dir]
Exit codes: 0 = all uses: pins are 40-char SHAs, 1 = drift found.
"""

from __future__ import annotations

import pathlib
import re
import sys

WORKFLOWS_DIR = pathlib.Path(".github/workflows")

# Matches a `uses:` step value, e.g. "uses: actions/checkout@v4" or
# "- uses: owner/repo/subdir@abc123...". Captures the ref up to the next
# whitespace so a trailing "# v1.2.3" version comment (this repo's own
# convention on every real uses: line, see .github/workflows/*.yml) does not
# make the whole line fail to match -- an earlier version of this regex
# anchored ref to end-of-line and silently skipped every real line, which
# would have made "no findings" mean "nothing scanned", not "verified pinned".
USES_RE = re.compile(r"^\s*-?\s*uses:\s*(\S+)@(\S+?)(?:\s+#.*)?\s*$")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
# Local actions ("./path/to/action") and Docker actions ("docker://image:tag")
# are not third-party version references -- excluded, not flagged.
NON_THIRD_PARTY_PREFIXES = ("./", "docker://")


def find_unpinned_actions(workflows_dir: pathlib.Path = WORKFLOWS_DIR) -> list[tuple[str, int, str]]:
    """Return (file, line_number, line) for each `uses:` pinned to a mutable
    ref instead of a full 40-character commit SHA. Empty list means every
    third-party action reference in the scanned files is SHA-pinned."""
    findings: list[tuple[str, int, str]] = []
    for workflow in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        for lineno, line in enumerate(workflow.read_text().splitlines(), start=1):
            match = USES_RE.match(line)
            if not match:
                continue
            action, ref = match.group(1), match.group(2)
            if action.startswith(NON_THIRD_PARTY_PREFIXES):
                continue
            if not FULL_SHA_RE.match(ref):
                findings.append((str(workflow), lineno, line.strip()))
    return findings


def main() -> int:
    workflows_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORKFLOWS_DIR
    findings = find_unpinned_actions(workflows_dir)
    if findings:
        print(
            "Unpinned third-party actions found (pinned to a tag/branch, "
            "not a 40-character commit SHA):"
        )
        for path, lineno, line in findings:
            print(f"  {path}:{lineno}: {line}")
        return 1
    print("No unpinned third-party actions found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

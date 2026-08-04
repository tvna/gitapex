#!/usr/bin/env python3
"""Find third-party GitHub Actions pinned to a mutable ref instead of a SHA.

Mirrors the shape of `.github/scripts/scan_toolchain_pin_drift.py` (line-by-
line walk over `.github/workflows/*.yml`, `(file, line_number, line)` tuples,
0/1 exit-code CLI) for a different pattern: a `uses:` step pinned to a tag or
branch (`@v4`, `@main`) rather than a full 40-character commit SHA. A mutable
ref lets the action's upstream owner change what code runs on the next build
without the consuming workflow's diff showing it.

Scope: GitHub Actions workflow files only; the equivalent GitLab CI
`include:` check is out of scope (no GitLab MCP server available).

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
# whitespace so a trailing "# v1.2.3" version comment (this repo's
# convention on every real uses: line, see .github/workflows/*.yml) does not
# prevent the line from matching.
USES_RE = re.compile(r"^\s*-?\s*uses:\s*(\S+)@(\S+?)(?:\s+#.*)?\s*$")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
# Local actions ("./path/to/action") and Docker actions ("docker://image:tag")
# are not third-party version references -- excluded, not flagged.
NON_THIRD_PARTY_PREFIXES = ("./", "docker://")
QUOTE_CHARS = ("'", '"')


def _strip_matching_quotes(action: str, ref: str) -> tuple[str, str]:
    """Strip a quote pair YAML allows around the whole `uses:` scalar.

    `uses: "actions/checkout@<sha>"` is valid YAML, but USES_RE's \\S+ groups
    capture the quote characters too (leading '"' on action, trailing '"' on
    ref), which would fail the 40-char-SHA check on a correctly pinned line.
    Only strip when the leading and trailing quotes match, so an unrelated
    literal quote is left untouched.
    """
    if action[:1] in QUOTE_CHARS and ref[-1:] == action[0]:
        return action[1:], ref[:-1]
    return action, ref


def find_unpinned_actions(workflows_dir: pathlib.Path = WORKFLOWS_DIR) -> list[tuple[str, int, str]]:
    """Return (file, line_number, line) for each `uses:` pinned to a mutable
    ref instead of a full 40-character commit SHA. Empty list means every
    third-party action reference in the scanned files is SHA-pinned."""
    findings: list[tuple[str, int, str]] = []
    for workflow in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        try:
            content = workflow.read_text()
        except UnicodeDecodeError as exc:
            # Fail closed, not skip: a workflow file that isn't valid text
            # can't be scanned for `uses:` lines, so it cannot be verified
            # clean -- reported as a finding rather than silently skipped,
            # since skipping would let a real unpinned action hide behind a
            # decode failure in the same file.
            findings.append((str(workflow), 0, f"could not decode as UTF-8, cannot verify: {exc}"))
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            match = USES_RE.match(line)
            if not match:
                continue
            action, ref = _strip_matching_quotes(match.group(1), match.group(2))
            if action.startswith(NON_THIRD_PARTY_PREFIXES):
                continue
            if not FULL_SHA_RE.match(ref):
                findings.append((str(workflow), lineno, line.strip()))
    return findings


def main() -> int:
    workflows_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORKFLOWS_DIR
    findings = find_unpinned_actions(workflows_dir)
    if findings:
        print("Unpinned third-party actions found (pinned to a tag/branch, not a 40-character commit SHA):")
        for path, lineno, line in findings:
            print(f"  {path}:{lineno}: {line}")
        return 1
    print("No unpinned third-party actions found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

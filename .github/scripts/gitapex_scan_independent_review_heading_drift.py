#!/usr/bin/env python3
"""Guard the independent-review-pending recorded-verdict heading's
single-source-of-truth invariant.

Issue #1343: the gate's own recorded-verdict heading (once ``## Step 8
independent review verdict``, renamed by that issue to ``## Independent
review verdict`` to de-couple it from ``drafting-a-pr-to-merge``'s internal
step numbering) is duplicated by hand across four other files besides the
gate script itself, which now owns the canonical text as
``gitapex_gate_independent_review_pending.CANONICAL_HEADING_TEXT``:

- ``skills/drafting-a-pr-to-merge/SKILL.md`` (Step 8's own recorded-heading
  instruction)
- ``.github/PULL_REQUEST_TEMPLATE.md`` (the ``## Merge gate: independent
  review`` feed-forward note)
- ``.gitapex/ssot.json`` (the ``independent-review-pending`` gate entry's
  own ``rule`` field)
- ``.github/workflows/independent-review-pending.yml`` (a comment)

An independent adversarial deterministic-gate-quality review (dimension
12, issue #1343's own session) found that nothing previously bound these
five copies together -- this PR's own rename touched all five by hand,
but a future rename, or a future hand-edit of any one of them, could
silently drift the rest out of sync with no test failing. CLAUDE.md's own
governance rule for this repository states the invariant plainly: "ship
its drift gate in the same change, not a follow-up." This is that gate.

Deliberately checks for the literal string ``"## " + CANONICAL_HEADING_TEXT``
(the gate script's own canonical text, marker-prefixed) rather than trying
to parse each file's own surrounding Markdown/JSON/YAML syntax -- the same
narrow-scope trade-off ``gitapex_scan_toolchain_pin_drift.py`` already makes
for its own single-source-of-truth invariant. A false negative is possible
if a file quotes the heading in some form this substring check does not
recognize (for example, split across a line-wrap inside a code span); a
false positive is not, since the marker string is specific enough that
nothing else plausibly contains it by coincidence.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gitapex_scan_independent_review_heading_drift.py``.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gitapex_gate_independent_review_pending as gate

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Relative to the repository root -- the gate script itself is the
# canonical source and is not included here as a target to check against
# itself.
_TARGET_FILES = (
    pathlib.Path("skills/drafting-a-pr-to-merge/SKILL.md"),
    pathlib.Path(".github/PULL_REQUEST_TEMPLATE.md"),
    pathlib.Path(".gitapex/ssot.json"),
    pathlib.Path(".github/workflows/independent-review-pending.yml"),
)


def find_drift(root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Return one message per target file that does not carry the
    canonical ``"## " + CANONICAL_HEADING_TEXT`` marker. Empty list means
    no drift. A missing target file is itself reported as drift (fail
    closed) rather than silently skipped -- an absent file cannot be
    verified to carry the current heading."""
    marker = "## " + gate.CANONICAL_HEADING_TEXT
    findings: list[str] = []
    for relative in _TARGET_FILES:
        path = root / relative
        if not path.is_file():
            findings.append(f"{relative}: file not found, cannot verify it carries {marker!r}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(f"{relative}: could not read as UTF-8, cannot verify: {exc}")
            continue
        if marker not in content:
            findings.append(f"{relative}: does not contain the canonical heading marker {marker!r}")
    return findings


def main() -> int:
    findings = find_drift()
    if findings:
        print(
            "Independent-review-pending heading drift: every file below must carry the "
            f"canonical heading text owned by gitapex_gate_independent_review_pending."
            f"CANONICAL_HEADING_TEXT ({gate.CANONICAL_HEADING_TEXT!r}):"
        )
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No independent-review-pending heading drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

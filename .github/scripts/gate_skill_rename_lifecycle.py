#!/usr/bin/env python3
"""CI gate: a skill directory removed in this PR must be recorded as some
surviving skill's `spec.lifecycle.renamedFrom`.

Issue #285 (Refs #281, #282) repair 2: PR #282 renamed two skill
directories via `git mv` and initially shipped both sidecars without
`spec.lifecycle.renamedFrom` -- a field purpose-built for exactly this
case (docs/superpowers/specs/2026-07-21-skill-lifecycle-metadata-design.md),
already validated for *shape* by
`skills/evaluating-skill-quality/scripts/check_skill_shape.py`, but never
checked for *presence* when a rename actually occurs. A reviewer bot
caught it that time; this gate makes the catch deterministic.

Applicability is computed from `git ls-tree -d --name-only` over `skills/`
at the PR's base and head SHAs (a plain directory-listing diff), not from
`git diff --name-status -M`'s content-similarity-based rename detection --
that heuristic misses a rename bundled with a substantial content rewrite
(similarity below its ~50% default threshold reports separate add/delete
lines, not a rename pair), silently skipping exactly the case this gate
exists to catch. Comparing directory listings is unaffected by how much
content changed: a name present at base and absent at head is "removed"
regardless of what replaced it. The calling workflow computes the removed
(and added) names; this script only checks whether every removed name is
recorded as *some* current skill's `renamedFrom` -- not necessarily paired
1:1 with a specific added directory, since multiple simultaneous renames
in one PR cannot be reliably paired without the same fragile similarity
heuristic this design avoids.

Deliberately does not import `check_skill_shape.py`: `.github/scripts/*.py`
and `skills/*/scripts/*.py` are kept independently self-contained in this
repo (see `gate_skill_audit_disclosure.py`'s own docstring) rather than
cross-importing. `renamedFrom` extraction below still needs to agree with
`check_skill_shape.py`'s own parser on what counts as "nested under
spec.lifecycle" (a bare, context-blind regex previously matched a stray
`renamedFrom:` line at 4-space indent anywhere in the sidecar, e.g. under
`spec.skillDependencies`, which `check_skill_shape.py`'s state-aware
parser would never do) -- `_renamed_from` below bounds the match to the
`spec: -> lifecycle:` block's own contiguous 4-space-indented lines
specifically to stay consistent with that parser's actual behavior, even
though it remains a light, standalone scan rather than a full manifest
parse.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Bounds the spec.lifecycle: block: the header line at exactly 2-space
# indent, then every immediately-following line indented 4+ spaces (the
# block's own contents), stopping at the first line that dedents below
# that -- mirrors check_skill_shape.py's in_lifecycle state tracking
# closely enough to avoid matching a renamedFrom-shaped line that lives
# under a different spec.* key (e.g. spec.skillDependencies) at the same
# raw indent but outside spec.lifecycle.
LIFECYCLE_BLOCK_RE = re.compile(r"^ {2}lifecycle:[ \t]*$\n((?: {4,}.*\n?)*)", re.MULTILINE)
RENAMED_FROM_RE = re.compile(r"^ {4}renamedFrom:[ \t]*(.*)$", re.MULTILINE)


def _strip_quotes(value: str) -> str:
    """Mirrors check_skill_shape.py's own `_unquote`: a double-quoted YAML
    scalar's escaping is a superset-safe match for JSON string escaping,
    so decode via the stdlib json module to handle real escape sequences,
    falling back to a naive strip on decode failure or for single quotes
    (YAML single-quote escaping is not JSON-compatible, same as the
    sibling parser)."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        if value[0] == '"':
            try:
                decoded = json.loads(value)
            except ValueError:
                decoded = None
            if isinstance(decoded, str):
                return decoded
        return value[1:-1]
    return value


def _renamed_from(sidecar_text: str) -> str | None:
    """Return the sidecar's `spec.lifecycle.renamedFrom` value, or None if
    absent/blank/not actually nested under spec.lifecycle."""
    block_match = LIFECYCLE_BLOCK_RE.search(sidecar_text)
    if not block_match:
        return None
    match = RENAMED_FROM_RE.search(block_match.group(1))
    if not match:
        return None
    value = _strip_quotes(match.group(1))
    return value or None


def parse_names(text: str) -> list[str]:
    """Parse one skill name per line, blank lines and surrounding
    whitespace ignored."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def all_renamed_from_values(repo_root: Path) -> set[str]:
    """Every `spec.lifecycle.renamedFrom` value recorded by any skill
    currently under `skills/` at `repo_root`."""
    values: set[str] = set()
    for sidecar in sorted((repo_root / "skills").glob("*/metadata/gitapex.yaml")):
        try:
            text = sidecar.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        value = _renamed_from(text)
        if value:
            values.add(value)
    return values


def find_offenders(removed_names: list[str], repo_root: Path) -> list[str]:
    """Return one human-readable offender string per removed skill name
    that no current skill's sidecar records as its `renamedFrom`."""
    recorded = all_renamed_from_values(repo_root)
    return [
        f"{name}: removed in this diff, but no current skill records "
        f"spec.lifecycle.renamedFrom: {name}"
        for name in removed_names
        if name not in recorded
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every skill directory removed in this PR "
        "is recorded as some surviving skill's spec.lifecycle.renamedFrom.")
    parser.add_argument(
        "--removed",
        help="Path to a file of removed skill directory names, one per "
        "line; reads standard input when omitted.")
    args = parser.parse_args(argv)

    try:
        text = (
            Path(args.removed).read_text(encoding="utf-8") if args.removed else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: removed-names file not found: {args.removed}", file=sys.stderr)
        return 1

    removed_names = parse_names(text)
    if not removed_names:
        print("PASS: no removed skill directories in this diff")
        return 0

    offenders = find_offenders(removed_names, Path())
    if not offenders:
        print(f"PASS: renamedFrom recorded for all {len(removed_names)} removed skill(s)")
        return 0

    print("FAIL: the following removed skill(s) are not recorded:", file=sys.stderr)
    for offender in offenders:
        print(f"  - {offender}", file=sys.stderr)
    print(
        "Add 'spec.lifecycle.renamedFrom: <old-name>' to whichever current "
        "skill's metadata/gitapex.yaml is the rename's successor, or "
        "confirm this was a deliberate removal (not a rename) if none is.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

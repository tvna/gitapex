#!/usr/bin/env python3
"""CI gate: a renamed skill directory's surviving sidecar must record
`spec.lifecycle.renamedFrom`.

Issue #285 (Refs #281, #282) repair 2: PR #282 renamed two skill
directories via `git mv` and initially shipped both sidecars without
`spec.lifecycle.renamedFrom` -- a field purpose-built for exactly this
case (docs/superpowers/specs/2026-07-21-skill-lifecycle-metadata-design.md),
already validated for *shape* by
`skills/evaluating-skill-quality/scripts/check_skill_shape.py`, but never
checked for *presence* when a rename actually occurs. A reviewer bot
caught it that time; this gate makes the catch deterministic.

The calling workflow decides applicability (it computes which skill
directories were renamed in this PR via `git diff --name-status -M`);
this script only grades the renamed-pair list handed to it. Deliberately
does not import `check_skill_shape.py`: `.github/scripts/*.py` and
`skills/*/scripts/*.py` are kept independently self-contained in this
repo (see `gate_skill_audit_disclosure.py`'s own docstring) rather than
cross-importing, so each stays free of the other's dependency surface.
`renamedFrom` extraction below is intentionally a light regex scan, not a
full manifest parse -- `check_skill_shape.py` remains the authoritative
shape validator; this gate only needs to know whether the field is
present and what value it names.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RENAMED_FROM_RE = re.compile(r"^[ ]{4}renamedFrom:[ \t]*(.*)$", re.MULTILINE)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _renamed_from(sidecar_text: str) -> str | None:
    """Return the sidecar's `spec.lifecycle.renamedFrom` value, or None if
    absent/blank. Returns the first match if more than one line happens to
    match at 4-space indent (malformed sidecars are check_skill_shape.py's
    concern, not this gate's)."""
    match = RENAMED_FROM_RE.search(sidecar_text)
    if not match:
        return None
    value = _strip_quotes(match.group(1))
    return value or None


def parse_pairs(text: str) -> list[tuple[str, str]]:
    """Parse "old-name new-name" pairs, one per line, blank lines and
    surrounding whitespace ignored. Raises ValueError on a malformed line
    (not exactly two whitespace-separated tokens) so a shell-side bug in
    the calling workflow fails loudly instead of silently skipping a
    rename."""
    pairs = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"line {lineno}: expected 'old-name new-name', got {raw!r}")
        pairs.append((parts[0], parts[1]))
    return pairs


def find_offenders(pairs: list[tuple[str, str]], repo_root: Path) -> list[str]:
    """Return one human-readable offender string per renamed pair whose new
    skill directory's sidecar does not record the rename."""
    offenders = []
    for old_name, new_name in pairs:
        sidecar = repo_root / "skills" / new_name / "metadata" / "gitapex.yaml"
        if not sidecar.is_file():
            offenders.append(
                f"{new_name}: metadata/gitapex.yaml missing, cannot record "
                f"renamedFrom: {old_name}")
            continue
        try:
            text = sidecar.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            offenders.append(f"{new_name}: sidecar unreadable ({type(exc).__name__})")
            continue
        recorded = _renamed_from(text)
        if recorded is None:
            offenders.append(
                f"{new_name}: spec.lifecycle.renamedFrom missing (expected {old_name!r})")
        elif recorded != old_name:
            offenders.append(
                f"{new_name}: spec.lifecycle.renamedFrom is {recorded!r}, "
                f"expected {old_name!r}")
    return offenders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that each renamed skill directory's surviving "
        "sidecar records spec.lifecycle.renamedFrom.")
    parser.add_argument(
        "--pairs",
        help="Path to a file of 'old-name new-name' lines, one per "
        "renamed skill directory; reads standard input when omitted.")
    parser.add_argument(
        "--repo-root", default=".",
        help="Repository root to resolve skills/<new-name>/metadata/gitapex.yaml "
        "against (default: current directory).")
    args = parser.parse_args(argv)

    try:
        text = (
            open(args.pairs, encoding="utf-8").read() if args.pairs else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: pairs file not found: {args.pairs}", file=sys.stderr)
        return 1

    try:
        pairs = parse_pairs(text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not pairs:
        print("PASS: no renamed skill directories in this diff")
        return 0

    offenders = find_offenders(pairs, Path(args.repo_root))
    if not offenders:
        print(f"PASS: renamedFrom recorded for all {len(pairs)} renamed skill(s)")
        return 0

    print(
        "FAIL: the following renamed skill(s) do not record "
        "spec.lifecycle.renamedFrom correctly:",
        file=sys.stderr,
    )
    for offender in offenders:
        print(f"  - {offender}", file=sys.stderr)
    print(
        "Add (or fix) 'spec.lifecycle.renamedFrom: <old-name>' to each "
        "renamed skill's metadata/gitapex.yaml.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

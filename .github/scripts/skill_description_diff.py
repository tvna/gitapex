#!/usr/bin/env python3
"""Determine whether a skills/*/SKILL.md's frontmatter `description` field
changed between two git revisions.

Issue #427 (refs #422): skill-audit-gate.yml originally matched
`^[+-]description:` against a unified diff. A PR review
(https://github.com/tvna/gitapex/pull/428#discussion_r3654041059) found this
misses a change confined to a YAML block-scalar description's continuation
lines (folded `>` / literal `|`) -- both of which this repository's own
shape checker explicitly accepts and tests
(skills/evaluating-skill-quality/scripts/test_check_skill_shape.py's
test_folded_block_description_with_colon_passes_yaml_safe). A second review
comment (https://github.com/tvna/gitapex/pull/428#discussion_r3654041064)
found that same line-diff approach also false-positives on a byte-identical
rename, since a single-pathspec diff renders the renamed file as a full
addition. This script instead reads the file's full content at each
revision via `git show` and compares the *parsed* description value,
addressing both: pass the pre-rename path as --base-path and the
post-rename path as --head-path for a renamed file, and any other path
unchanged for a plain add/modify.

Mirrors check_skill_shape.py's own `_parse_frontmatter` block-scalar
handling (join folded lines with a space, literal lines with a newline)
rather than importing it -- this repo deliberately keeps .github/scripts/*.py
and skills/*/scripts/*.py independently self-contained (see
gate_skill_rename_lifecycle.py's own docstring for the same rationale), and
this script only ever needs the one `description` field, not the full
frontmatter shape check_skill_shape.py validates.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

_BLOCK_SCALAR_INDICATORS = frozenset({">", ">-", ">+", "|", "|-", "|+"})
_DESCRIPTION_KEY_RE = re.compile(r"^description:[ \t]*(.*)$")


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def extract_description(text):
    """Return the frontmatter `description` field's parsed value, or None
    if there is no parseable `---`-delimited frontmatter or no
    `description:` key inside it."""
    text = (text or "").lstrip("\ufeff")
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    i = 1
    while i < end:
        match = _DESCRIPTION_KEY_RE.match(lines[i])
        if not match:
            i += 1
            continue
        value = match.group(1).strip()
        if value in _BLOCK_SCALAR_INDICATORS:
            block = []
            i += 1
            while i < end and (lines[i].strip() == "" or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if value[0] == "|" else " "
            return joiner.join(block).strip()
        return _unquote(value)
    return None


def description_changed(base_text, head_text):
    """True if the parsed description differs between the two revisions'
    file content -- also True (fail closed) if the file is missing at
    either revision, or its frontmatter is present but unparseable at
    either revision, rather than silently treating an unreadable
    description as unchanged."""
    if base_text is None or head_text is None:
        return True
    base_desc = extract_description(base_text)
    head_desc = extract_description(head_text)
    if base_desc is None or head_desc is None:
        return True
    return base_desc != head_desc


def _read_at_revision(rev, path):
    """Return the file's content at `rev`, or None if it does not exist
    there (a newly added file, or the pre-rename path at head)."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git`
        # is intentionally resolved from PATH -- pinning an absolute path
        # would break the three environments this has to run in (GitHub
        # runner, the nix devShell, a contributor's machine).
        result = subprocess.run(  # noqa: S603
            ["git", "show", f"{rev}:{path}"],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _validate_cli_args(base_rev, head_rev, base_path, head_path):
    """Return a pydantic-``ValidationError``-style detail string (one
    ``<field>: <message>`` clause per violated constraint, joined with
    ``"; "``, in field-declaration order) if any of the four arguments is
    blank -- argparse's own ``required=True`` only guarantees the flag was
    passed, not that its value is non-empty, and a blank rev/path was never
    a meaningful input to ``_read_at_revision`` -- else None. Message text
    is a byte-for-byte match of the pydantic ``Field(min_length=1)`` errors
    this replaces (verified directly against the installed pydantic
    version), so this plain-Python check is a drop-in replacement, not
    merely an equivalent-intent one."""
    errors = []
    if not base_rev:
        errors.append("base_rev: String should have at least 1 character")
    if not head_rev:
        errors.append("head_rev: String should have at least 1 character")
    if not base_path:
        errors.append("base_path: String should have at least 1 character")
    if not head_path:
        errors.append("head_path: String should have at least 1 character")
    return "; ".join(errors) if errors else None


def main(argv: list[str] | None = None) -> int:
    """CLI: print 'changed' or 'unchanged' and exit 0."""
    parser = argparse.ArgumentParser(
        description="Print 'changed' or 'unchanged' depending on whether a "
        "SKILL.md's frontmatter description field's parsed value differs "
        "between two git revisions."
    )
    parser.add_argument("--base-rev", required=True)
    parser.add_argument("--head-rev", required=True)
    parser.add_argument(
        "--base-path",
        required=True,
        help="Path at --base-rev (the pre-rename path for a renamed file).",
    )
    parser.add_argument(
        "--head-path",
        required=True,
        help="Path at --head-rev (the post-rename path for a renamed file).",
    )
    args = parser.parse_args(argv)
    detail = _validate_cli_args(args.base_rev, args.head_rev, args.base_path, args.head_path)
    if detail is not None:
        print(f"error: invalid arguments: {detail}", file=sys.stderr)
        return 1

    base_text = _read_at_revision(args.base_rev, args.base_path)
    head_text = _read_at_revision(args.head_rev, args.head_path)
    print("changed" if description_changed(base_text, head_text) else "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

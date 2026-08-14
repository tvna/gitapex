#!/usr/bin/env python3
"""Determine whether a skills/*/SKILL.md's frontmatter `description` field
changed between two git revisions.

Issue #427 (refs #422): skill-audit-gate.yml originally matched
`^[+-]description:` against a unified diff. A PR review
(https://github.com/tvna/gitapex/pull/428#discussion_r3654041059) found this
misses a change confined to a YAML block-scalar description's continuation
lines (folded `>` / literal `|`) -- both of which this repository's own
shape checker explicitly accepts and tests
(skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py's
test_folded_block_description_with_colon_passes_yaml_safe). A second review
comment (https://github.com/tvna/gitapex/pull/428#discussion_r3654041064)
found that same line-diff approach also false-positives on a byte-identical
rename, since a single-pathspec diff renders the renamed file as a full
addition. This script instead reads the file's full content at each
revision via `git show` and compares the *parsed* description value,
addressing both: pass the pre-rename path as --base-path and the
post-rename path as --head-path for a renamed file, and any other path
unchanged for a plain add/modify.

Mirrors gitapex_check_skill_shape.py's own `_parse_frontmatter` block-scalar
handling (join folded lines with a space, literal lines with a newline)
rather than importing it -- this repo deliberately keeps .github/scripts/*.py
and skills/*/scripts/*.py independently self-contained (see
gitapex_gate_skill_rename_lifecycle.py's own docstring for the same rationale), and
this script only ever needs the one `description` field, not the full
frontmatter shape gitapex_check_skill_shape.py validates.

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed fails at import time, before argparse
even runs). Two callers reach this module, and only one of them satisfies
that:

- skill-audit-gate.yml's CI path, via an in-process `import
  gitapex_skill_description_diff` from gitapex_compute_skill_audit_flags.py,
  itself `uv run`-invoked. This is the authoritative path.
- hooks/check-pr-skill-audit-disclosure.sh's tier-1 local pre-check, which
  invokes gitapex_gate_skill_audit_disclosure.py under a bare `python3`.
  That path already could not import pydantic before this module needed it
  (gitapex_detect_changed_gate_scripts.py, reached through the same import
  chain, has imported pydantic at module scope since issue #1040 wave 1),
  so the hook's own `except ImportError` handler catches it and falls
  through to its narrower tier-2 check with a warning -- the documented
  degradation, not a hard failure. This module joining that class does not
  change the hook's behavior, but the fall-through is silent enough that
  no deterministic gate currently covers it: bare-python3-invocation-gate.yml
  scans workflow `run:` steps only, not hooks/*.sh.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

from pydantic import BaseModel, Field, ValidationError

_BLOCK_SCALAR_INDICATORS = frozenset({">", ">-", ">+", "|", "|-", "|+"})
_DESCRIPTION_KEY_RE = re.compile(r"^description:[ \t]*(.*)$")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def extract_description(text: str | None) -> str | None:
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


def description_changed(base_text: str | None, head_text: str | None) -> bool:
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


# This CLI's own wording for each constraint the model below imposes, keyed
# by pydantic's own error type. pydantic's message text is deliberately not
# echoed -- it is not part of this CLI's contract, so a version bump must
# not change what an operator reads -- but naming only the offending flag
# and nothing else leaves the operator without the reason. An unmapped type
# falls back to a generic label rather than raising, so a future constraint
# kind can never turn a rejected argument into a traceback.
_CONSTRAINT_HINTS = {"string_too_short": "must not be blank"}


class SkillDescriptionDiffArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. All four fields reject
    a blank value -- argparse's own ``required=True`` only guarantees the
    flag was passed, not that its value is non-empty, and a blank rev/path
    was never a meaningful input to ``_read_at_revision``."""

    base_rev: str = Field(min_length=1)
    head_rev: str = Field(min_length=1)
    base_path: str = Field(min_length=1)
    head_path: str = Field(min_length=1)


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
    try:
        SkillDescriptionDiffArgs(
            base_rev=args.base_rev,
            head_rev=args.head_rev,
            base_path=args.base_path,
            head_path=args.head_path,
        )
    except ValidationError as error:
        # Only the offending flag names and this CLI's own constraint
        # wording are echoed -- never pydantic's own message text, and
        # never the rejected value itself.
        invalid = ", ".join(
            f"--{str(item['loc'][0]).replace('_', '-')} ({_CONSTRAINT_HINTS.get(item['type'], 'invalid value')})"
            for item in error.errors()
        )
        print(f"error: invalid arguments: {invalid}", file=sys.stderr)
        return 1

    base_text = _read_at_revision(args.base_rev, args.base_path)
    head_text = _read_at_revision(args.head_rev, args.head_path)
    print("changed" if description_changed(base_text, head_text) else "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

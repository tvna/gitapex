#!/usr/bin/env python3
"""Flag a Routine-connection doc that declares a Broad-capability skill
with no concrete, implemented scoping mechanism cited.

Issue #520 (row 2, refs #348): retrospective #348 found that
`docs/superpowers/specs/2026-07-25-ranking-the-open-queue-weekly-routine.md`
wired `skills/ranking-the-open-queue` (whose `metadata/gitapex.yaml`
declares `capabilityAssumption: Broad`) to a scheduled Routine with only a
prompt-level "do not write" instruction -- not a real permission boundary.
A reviewer bot (`chatgpt-codex-connector[bot]`) caught it that time; this
gate makes the catch deterministic.

A Routine-connection doc "passes" when either:

- the skill(s) it names all declare something other than
  `capabilityAssumption: Broad`, or
- the doc also cites at least one concrete, implemented scoping mechanism:
  a real `environment_id` value (`env_...`/`ccpool_...`, not a bare mention
  of the parameter name), a workflow `permissions:` block whose scopes are
  all `read` (the pattern
  `docs/superpowers/specs/2026-07-28-ranking-the-open-queue-github-actions-routine.md`
  actually shipped, replacing the superseded Cloud-Routine design), a
  `--allowedTools`/`allowedTools` tool allowlist, a named deny hook
  (a `hooks/*.sh` path plus the word "deny"), or a read-only credential/
  token reference.

A doc carrying a `**Superseded` banner (this repo's own convention for
marking a design doc replaced by a later one -- see the
2026-07-25 Cloud-Routine doc's own banner) is skipped entirely: it
describes a historical, never-shipped design, not a live enforcement
posture, so grading it would either false-fail on an abandoned plan or
require retroactively editing a doc kept "as-is... for the audit trail".

Distinguishing "cites an implemented mechanism" from "merely names the
parameter as future work" is a judgment heuristic, named explicitly as a
residual risk in issue #520's own Acceptance Criteria Map -- this script
resolves it the same direction scan_provenance.py resolves an analogous
ambiguity (only count a "model identifier" hit with same-line corroborating
context): require the *value shape* (`env_`/`ccpool_` prefix), not just the
parameter name, before counting an `environment_id` mention as concrete.

Deliberately stdlib-only and self-contained, matching this repository's
existing .github/scripts/*.py convention of not importing across files.

Usage::

    python3 .github/scripts/gate_routine_scope_enforcement.py \\
        --skills-root skills DOC [DOC ...]

Exit codes:
    0  No applicable doc, or every Broad-capability doc cites a concrete
       scoping mechanism.
    1  A Broad-capability doc cites none, or a given file could not be read.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SUPERSEDED_RE = re.compile(r"\*\*Superseded\b", re.IGNORECASE)

# A path segment naming the skill a Routine-connection doc invokes, e.g.
# "skills/ranking-the-open-queue" or "skills/ranking-the-open-queue/SKILL.md".
_SKILL_REF_RE = re.compile(r"\bskills/([a-z0-9][a-z0-9-]*)\b")

# No trailing `\s*$` anchor: a sidecar line carrying an inline comment
# (`capabilityAssumption: Broad  # confirmed 2026-07`) would otherwise fail
# to match at all -- `\S+` already stops at the first whitespace, so
# dropping the end anchor is sufficient and does not change what value is
# captured for a plain, comment-free line.
_CAPABILITY_RE = re.compile(r"^\s*capabilityAssumption:\s*(\S+)", re.MULTILINE)

# A real environment_id value: "env_" or "ccpool_" (self-hosted pools) per
# create_trigger's own environment_id documentation, not a bare mention of
# the parameter name as a future-work placeholder.
_ENV_ID_VALUE_RE = re.compile(r"\b(?:env_|ccpool_)[A-Za-z0-9]+\b")

# A workflow permissions: block reproduced in the doc, bounded the same way
# gate_skill_rename_lifecycle.py's LIFECYCLE_BLOCK_RE bounds spec.lifecycle:
# the header line, then its immediately-following more-indented lines.
_PERMISSIONS_BLOCK_RE = re.compile(r"^([ \t]*)permissions:[ \t]*$\n((?:\1[ \t]+.*\n?)*)", re.MULTILINE)
# No trailing `\s*$` anchor, same rationale as _CAPABILITY_RE above: a
# `issues: write  # reverted after incident` line must still count as a
# `write` value, not silently drop out of the block's captured values
# (which would make an all-`read` check on the remaining values pass
# vacuously despite the block actually granting write).
_PERMISSIONS_LINE_RE = re.compile(r"^\s*[\w-]+:\s*(\S+)", re.MULTILINE)

_ALLOWED_TOOLS_RE = re.compile(r"--allowedTools\b|\ballowedTools\b", re.IGNORECASE)

_DENY_HOOK_RE = re.compile(r"\bhooks/[\w.\-/]*\.sh\b")
_DENY_WORD_RE = re.compile(r"\bdeny\b", re.IGNORECASE)

_READONLY_CREDENTIAL_RE = re.compile(
    r"read-only[\w\s-]{0,40}(?:credential|token)|(?:credential|token)[\w\s-]{0,40}read-only",
    re.IGNORECASE,
)


def _paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [p for p in re.split(r"\n\s*\n", normalized) if p.strip()]


def _has_deny_hook_citation(text: str) -> bool:
    """True iff some paragraph in `text` names both a hook path and the
    word "deny" -- co-located, not merely present anywhere in the doc.
    An unscoped search would let an unrelated "hooks/pre-commit.sh" mention
    in one section and an unrelated "reviewers may deny this PR" in another
    combine into a false "named deny hook" citation."""
    return any(_DENY_HOOK_RE.search(p) and _DENY_WORD_RE.search(p) for p in _paragraphs(text))


def is_superseded(text: str) -> bool:
    """Return True iff `text` carries a "**Superseded" banner anywhere in
    its first 2000 characters (this repo's own convention for a design doc
    a later doc has replaced)."""
    return bool(_SUPERSEDED_RE.search(text[:2000]))


def referenced_skill_names(text: str) -> list[str]:
    """Every distinct `skills/<name>` reference in `text`, in order of
    first appearance."""
    seen: list[str] = []
    for match in _SKILL_REF_RE.finditer(text):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def capability_assumption(sidecar_text: str) -> str | None:
    """Return the sidecar's `spec.capabilityAssumption` value, or None if
    absent."""
    match = _CAPABILITY_RE.search(sidecar_text)
    return match.group(1) if match else None


def _permissions_block_is_read_only(text: str) -> bool:
    """True iff `text` contains a `permissions:` block whose every
    `key: value` line is `read` (never `write`, `none`, or anything else)."""
    for match in _PERMISSIONS_BLOCK_RE.finditer(text):
        body = match.group(2)
        values = _PERMISSIONS_LINE_RE.findall(body)
        if values and all(value == "read" for value in values):
            return True
    return False


def has_concrete_scoping_citation(text: str) -> bool:
    """True iff `text` cites at least one concrete, implemented scoping
    mechanism (not merely a prompt-level instruction)."""
    return bool(
        _ENV_ID_VALUE_RE.search(text)
        or _permissions_block_is_read_only(text)
        or _ALLOWED_TOOLS_RE.search(text)
        or _has_deny_hook_citation(text)
        or _READONLY_CREDENTIAL_RE.search(text)
    )


def broad_skills_without_scoping(
    text: str,
    skills_root: Path,
) -> list[str]:
    """Return the referenced skill names that declare
    `capabilityAssumption: Broad` and are not covered by a concrete scoping
    citation anywhere in `text`. Empty when `text` is superseded, names no
    skill, or already cites a concrete mechanism."""
    if is_superseded(text):
        return []
    if has_concrete_scoping_citation(text):
        return []

    broad_skills: list[str] = []
    for name in referenced_skill_names(text):
        sidecar = skills_root / name / "metadata" / "gitapex.yaml"
        try:
            sidecar_text = sidecar.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Fail loud, not silent-pass (CLAUDE.md section 4): a
            # Routine-connection doc naming a skill whose sidecar cannot be
            # read (missing, renamed, unreadable) has an unknown
            # capabilityAssumption -- treating that as "not Broad" would
            # let exactly the unscoped-Broad-skill pattern this gate exists
            # to catch slip through behind a typo'd or not-yet-created
            # sidecar path.
            broad_skills.append(f"{name} (capabilityAssumption unverifiable: {sidecar} not found or unreadable)")
            continue
        if capability_assumption(sidecar_text) == "Broad":
            broad_skills.append(name)
    return broad_skills


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag a Routine-connection doc declaring a Broad-capability "
        "skill with no concrete scoping mechanism cited."
    )
    parser.add_argument("docs", nargs="+", help="Paths to Routine-connection doc files to check.")
    parser.add_argument(
        "--skills-root",
        default="skills",
        help="Root directory containing skills/<name>/metadata/gitapex.yaml (default: skills)",
    )
    args = parser.parse_args(argv)
    skills_root = Path(args.skills_root)

    offenders: list[str] = []
    for raw_path in args.docs:
        path = Path(raw_path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"error: could not read {path}: {error}", file=sys.stderr)
            return 1
        broad_skills = broad_skills_without_scoping(text, skills_root)
        if broad_skills:
            offenders.append(f"{path}: cites {', '.join(broad_skills)} (capabilityAssumption: Broad) with no concrete scoping mechanism")

    if not offenders:
        print("PASS: no Routine-connection doc declares an unscoped Broad-capability skill")
        return 0

    print("FAIL: the following Routine-connection doc(s) need a concrete scoping citation:", file=sys.stderr)
    for offender in offenders:
        print(f"  - {offender}", file=sys.stderr)
    print(
        "Cite a concrete, implemented scoping mechanism: a real environment_id "
        "value (env_.../ccpool_...), a read-only workflow permissions: block, "
        "an --allowedTools allowlist, a named deny hook, or a read-only "
        "credential/token reference -- not only a prompt-level instruction.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

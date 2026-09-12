#!/usr/bin/env python3
"""Drift gate for the outbound references `AGENTS.md` carries (issue #1963).

`AGENTS.md` names other artifacts in backticks -- today eight skills, and
after issue #1963's row-7 rewrite also the deterministic gates whose
existence is the reason a prose rule was removed. Nothing checked that
those names still resolve. A skill renamed or retired, or a gate id
changed in `.gitapex/ssot.json`, silently turned a load-bearing pointer
in an always-loaded instruction file into a dangling one, and the only
thing standing between that and a reader following it was someone
noticing.

AGENTS.md section 3 requires an invariant's drift gate to ship in the
same change that establishes the invariant. That rule is why this gate
exists now rather than after the rewrite: the skill-name index is already
real and already ungated, and the gate-id index this same issue creates
lands inside a mechanism that will already be checking it.

**Which backticked tokens are checked.** Only tokens shaped like this
repository's own artifact identifiers: lowercase, hyphen-separated, with
at least one hyphen. That shape is what distinguishes
`planning-a-branch-from-an-issue` from `catch`, which AGENTS.md also
backticks as a language keyword and which is not a reference to anything.
The rule is deliberately a shape test rather than a list of known
non-references: a list would need editing every time the prose gained a
new hyphen-free code span, and the failure mode of getting that wrong is
a false FAIL on a word, not a missed dangling reference.

A checked token resolves when it is either a real `skills/<token>/SKILL.md`
or a real `gates[].id` in `.gitapex/ssot.json`. Anything else is drift.

Usage:
  uv run --frozen python3 .github/scripts/gitapex_gate_agents_md_reference_drift.py

Exit codes: 0 every checked token resolves; 1 at least one does not;
2 the gate cannot evaluate its own inputs (a missing `AGENTS.md`, a
missing or unparseable `.gitapex/ssot.json`, an undecodable file) --
never a silent pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# The instruction file whose outbound references are graded, and the two
# registries a reference can resolve against. Paths rather than imports:
# this gate reads data, and a data file that has moved should surface as
# the exit-2 diagnostic below rather than an import error.
AGENTS_MD_PATH = Path("AGENTS.md")
SKILLS_DIR = Path("skills")
SSOT_PATH = Path(".gitapex") / "ssot.json"
# Single-backtick inline code spans only. A fenced block is sample text,
# not prose making a reference, so fenced content is stripped before this
# runs.
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
# The artifact-identifier shape described in this module's own docstring:
# lowercase alphanumerics and hyphens, with at least one interior hyphen.
# A token without a hyphen (`catch`) is prose, not a reference.
_IDENTIFIER_RE = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)+\Z")
# A Markdown fence opener is a run of 3+ backticks or 3+ tildes with 0-3
# leading spaces; CommonMark closes it only on a later line whose own
# fence run is the SAME character and AT LEAST AS LONG, and carries no
# info string. Matching just the first three characters -- which an
# earlier revision of this gate did -- breaks nesting in BOTH
# directions: an inner 3-backtick fence ends a 4-backtick outer one, so
# sample text leaks back out and is flagged as a real reference (false
# FAIL); and the outer fence's own closing line then re-opens the
# tracker, swallowing the prose after it so a genuinely dangling
# reference goes unseen (fail-open, the direction that matters for a
# drift gate). Same rule, same reason, as
# `.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py` and
# `.github/scripts/gitapex_gate_no_raw_gh_cli_in_docs.py`, each of which
# carries its own copy: a `.github/scripts/` gate stays self-contained.
_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*$")


class GateUnrunnable(Exception):
    """Raised when the gate cannot evaluate its own inputs (exit 2)."""


def strip_fences(text: str) -> str:
    """Drop fenced code blocks, keeping every other line.

    A command or snippet inside a fence is an example, not a reference
    AGENTS.md is making, so scanning it would flag sample text. Fence
    pairing follows CommonMark's own run-length rule -- see
    `_FENCE_OPEN_RE`'s own comment for why the simpler prefix match this
    gate first used is wrong in both directions. An unclosed fence runs
    to the end of the document, as CommonMark specifies, so its content
    stays dropped rather than leaking back in.
    """
    kept: list[str] = []
    fence_char = ""
    fence_len = 0
    for line in text.split("\n"):
        if fence_len == 0:
            opener = _FENCE_OPEN_RE.match(line)
            if opener:
                fence_char = opener.group(1)[0]
                fence_len = len(opener.group(1))
                continue
            kept.append(line)
            continue
        closer = _FENCE_CLOSE_RE.match(line)
        if closer and closer.group(1)[0] == fence_char and len(closer.group(1)) >= fence_len:
            fence_char = ""
            fence_len = 0
    return "\n".join(kept)


def referenced_identifiers(text: str) -> list[str]:
    """Every backticked token in `text` shaped like an artifact identifier,
    in first-appearance order with duplicates removed."""
    seen: dict[str, None] = {}
    for span in _CODE_SPAN_RE.findall(strip_fences(text)):
        token = span.strip()
        if _IDENTIFIER_RE.match(token):
            seen.setdefault(token, None)
    return list(seen)


def known_gate_ids(repo_root: Path) -> set[str]:
    """Every `gates[].id` in the registry, or `GateUnrunnable`."""
    path = repo_root / SSOT_PATH
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GateUnrunnable(f"cannot read {SSOT_PATH}: {error}") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GateUnrunnable(f"cannot parse {SSOT_PATH}: {error}") from error
    # A valid JSON document need not be an object: `[]`, `"x"`, `1` and
    # `null` all parse. Calling .get() on one of those raises
    # AttributeError, which would escape as a crash rather than this
    # gate's own typed "cannot evaluate" -- the exact fail-open shape
    # dimension 15 warns about.
    if not isinstance(document, dict):
        raise GateUnrunnable(f"{SSOT_PATH} is valid JSON but not an object")
    gates = document.get("gates")
    if not isinstance(gates, list):
        raise GateUnrunnable(f"{SSOT_PATH} carries no gates[] list")
    return {gate["id"] for gate in gates if isinstance(gate, dict) and isinstance(gate.get("id"), str)}


def known_skill_names(repo_root: Path) -> set[str]:
    """Every directory under `skills/` carrying a real `SKILL.md`."""
    skills_dir = repo_root / SKILLS_DIR
    if not skills_dir.is_dir():
        raise GateUnrunnable(f"{SKILLS_DIR} is not a directory")
    return {child.name for child in skills_dir.iterdir() if (child / "SKILL.md").is_file()}


def evaluate(repo_root: Path) -> list[tuple[str, bool, str]]:
    """Return one `(identifier, resolves, detail)` row per checked token."""
    agents_md = repo_root / AGENTS_MD_PATH
    try:
        text = agents_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise GateUnrunnable(f"cannot read {AGENTS_MD_PATH}: {error}") from error
    skills = known_skill_names(repo_root)
    gates = known_gate_ids(repo_root)
    rows: list[tuple[str, bool, str]] = []
    for identifier in referenced_identifiers(text):
        if identifier in skills:
            rows.append((identifier, True, f"resolves to {SKILLS_DIR}/{identifier}/SKILL.md"))
        elif identifier in gates:
            rows.append((identifier, True, f"resolves to a {SSOT_PATH} gate id"))
        else:
            rows.append((identifier, False, "resolves to no skill and no gate id"))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root to check.")
    args = parser.parse_args(argv)
    try:
        rows = evaluate(args.repo_root)
    except GateUnrunnable as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for identifier, resolves, detail in rows:
        print(f"{'PASS' if resolves else 'FAIL'}  {identifier}: {detail}")
    dangling = [identifier for identifier, resolves, _ in rows if not resolves]
    if dangling:
        print(f"\nFAIL: {len(dangling)} of {len(rows)} backticked reference(s) in {AGENTS_MD_PATH} do not resolve.")
        return 1
    print(f"\nPASS: all {len(rows)} backticked reference(s) in {AGENTS_MD_PATH} resolve.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

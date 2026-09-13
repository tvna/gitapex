#!/usr/bin/env python3
"""Sweep every contract-declaring `skills/*/` directory against a fresh
regeneration of its `SKILL.md` contract-marker region (issue #1965, Task
5's `skill-contract-drift` `.gitapex/ssot.json` gate).

`skills/drafting-a-skill/scripts/gitapex_generate_skill_contract.py` (the
Task 3 generator) already knows how to check one skill directory at a
time, and -- by its own explicit "Portability constraint" (that script's
own module docstring) -- deliberately never reads `.gitapex/ssot.json` or
any file outside its one target directory, so it cannot sweep the
repository on its own. This script is the one caller that does: it
discovers every contract-declaring skill via
`gitapex_scan_ssot_schema.discover_contracts` (the same discovery
function the sibling `ssot-schema-drift` gate already uses to resolve
`spec.contract.gates[].id`/`handoff` values, so "which skills declare
`spec.contract`" has exactly one implementation in this repository, not
two that could quietly drift apart), then re-invokes the generator's own
`--check` CLI once per discovered skill, as a real subprocess -- the same
external-tool-per-group shape `gitapex_run_precommit_mypy.py`'s own
`run_group` already establishes for this repository's other script-wrapping
gates, rather than importing the generator's internals directly. That
keeps this file's own mypy invocation (the "tests + pythonpath-linked
roots" group, `.github/scripts` is a member) from ever needing to
cross-resolve into `skills/drafting-a-skill/scripts`, a directory none of
this repository's 7 mypy groups check today.

Zero real `skills/*/` declare `spec.contract` as of this gate landing (a
prototype-stage, opt-in-per-skill feature -- ADR 0005's own Decision
Outcome), so this script's own live-repository behavior is the uniform
"nothing to check" outcome today (exit 0, printing that no contract-
declaring skill exists yet) -- proven instead by this file's own
co-tested `tests/test_gitapex_skill_contract_drift.py`'s synthetic
fixtures for the positive/negative drift cases.

Also sweeps for the opposite gap (issue #1965 Step 8 aggregate adversarial
review): a `skills/*/SKILL.md` that carries the generator's own marker
pair (`<!-- gitapex:contract:begin/end -->`) but whose sidecar declares no
`spec.contract` at all is invisible to every check above -- `discover_contracts`
only ever looks at the sidecar side, so a hand-typed, stale, or corrupted
marker pair in a non-target skill would sit unverified indefinitely, even
though a reader (human or model) sees the same generator markers and
reasonably assumes the region is gate-backed. `_orphaned_marker_skills`
below closes that gap directly, without invoking the generator (which
would itself refuse such a skill as "not a target" and exit 0, telling this
caller nothing about the orphaned marker pair it just declined to check).

Exit code: 0 when every discovered skill's committed `SKILL.md` contract
region matches a fresh regeneration (including the zero-skills case) and no
orphaned marker pair exists, 1 on any drift, an orphaned marker pair,
generation failure, or a `--check` subprocess that times out.
"""

# patch-coverage: WAIVED: this whole file is exercised via
# tests/test_gitapex_skill_contract_drift.py -- the skill-contract-drift
# gate's own registered `trigger` file in .gitapex/ssot.json, named after
# the gate id rather than this script's own stem, since one test file
# covers both this wrapper and the generator script the gate's own
# script[] array names together. patch-coverage's own file-discovery only
# recognizes a source file's stem-matched tests/test_<stem>.py
# (_properties.py), with no fallback for a differently-named gate-scoped
# test file -- the same gap this file's own check_skill/discover_contracts
# function-body-test-coverage: WAIVED comments already disclose for the
# identical reason.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gitapex_scan_ssot_schema as ssot_schema

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATOR_SCRIPT = REPO_ROOT / "skills" / "drafting-a-skill" / "scripts" / "gitapex_generate_skill_contract.py"

# Literal copies of the generator's own BEGIN_MARKER/END_MARKER (issue
# #1965's own generator, gitapex_generate_skill_contract.py) -- not
# imported, for the same "no cross-resolve into skills/drafting-a-skill/scripts"
# mypy-grouping reason this module's own docstring already gives for
# invoking that script as a subprocess rather than importing it.
_BEGIN_MARKER = "<!-- gitapex:contract:begin -->"
_END_MARKER = "<!-- gitapex:contract:end -->"

# Generous relative to a single skill's own read/render/diff cost (no
# network, no heavy dependency resolution beyond `uv run`'s own warm
# cache) -- a hung invocation must still fail the gate loudly rather than
# hang a pre-push run indefinitely, matching
# gitapex_run_precommit_mypy.py's own `_GROUP_TIMEOUT_SECONDS` rationale
# at a scale appropriate to this much lighter per-item check.
_CHECK_TIMEOUT_SECONDS = 60


def check_skill(skill_dir: Path) -> subprocess.CompletedProcess[str]:
    # function-body-test-coverage: WAIVED: exercised via tests/test_gitapex_skill_contract_drift.py (the gate-scoped test file issue #1965's own Branch Plan names for this gate, not a tests/test_gitapex_run_skill_contract_check.py stem match); this gate's _test_relative_paths() only recognizes a source file's own stem-matched top-level tests/test_<stem>.py(_properties.py), with no fallback for a differently-named gate-scoped test file -- the same gap gitapex_generate_skill_contract.py's own functions already disclose for the pre-existing co-located-test convention.
    """Run the generator's own `--check` mode for one skill directory, as a
    real subprocess -- see module docstring for why this delegates rather
    than importing the generator's internals."""
    # S603/S607 waived for the same reason gitapex_run_precommit_mypy.py's
    # own run_group already gives: a fixed argv list with no shell, and
    # `uv` is resolved from PATH deliberately -- pinning an absolute path
    # would break the three environments this has to run in (GitHub
    # runner, the nix devShell, a contributor's machine).
    return subprocess.run(  # noqa: S603
        ["uv", "run", "--frozen", "python3", str(GENERATOR_SCRIPT), "--check", str(skill_dir)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=_CHECK_TIMEOUT_SECONDS,
        cwd=REPO_ROOT,
    )


def _orphaned_marker_skills(skills_dir: Path, contract_names: set[str]) -> list[str]:
    # function-body-test-coverage: WAIVED: exercised via tests/test_gitapex_skill_contract_drift.py -- see check_skill's own identical waiver comment above for the full reason.
    """Every `skills/<name>/SKILL.md` carrying the generator's own marker
    pair whose sidecar is NOT in `contract_names` (i.e. declares no
    `spec.contract`) -- see module docstring for why this closes a real
    gap `discover_contracts`-driven checks alone cannot see. A read
    failure on one `SKILL.md` is not this sweep's own concern -- a
    corrupted or non-UTF-8 `SKILL.md` is `skill-metadata-schema-drift`'s
    own finding to report, matching this repository's established
    graceful-degradation convention for a sidecar read failure -- so it
    is silently skipped here, not raised."""
    orphaned: list[str] = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name in contract_names:
            continue
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _BEGIN_MARKER in text or _END_MARKER in text:
            orphaned.append(name)
    return orphaned


def main() -> int:
    # function-body-test-coverage: WAIVED: exercised via tests/test_gitapex_skill_contract_drift.py -- see check_skill's own identical waiver comment above for the full reason.
    contract_names = sorted(ssot_schema.discover_contracts())
    orphaned = _orphaned_marker_skills(ssot_schema.SKILLS_DIR, set(contract_names))

    if not contract_names and not orphaned:
        print("skill-contract-drift: no skills/*/ declares spec.contract yet -- nothing to check.")
        return 0

    failed: list[str] = []
    for name in contract_names:
        skill_dir = ssot_schema.SKILLS_DIR / name
        try:
            result = check_skill(skill_dir)
        except subprocess.TimeoutExpired:
            failed.append(name)
            print(f"skill-contract-drift ({name}) timed out after {_CHECK_TIMEOUT_SECONDS}s", file=sys.stderr)
            continue
        if result.returncode != 0:
            failed.append(name)
            print(result.stdout)
            print(result.stderr, file=sys.stderr)

    if orphaned:
        print(
            f"skill-contract-drift: {', '.join(orphaned)} carries a contract marker pair "
            "in SKILL.md but declares no spec.contract in its sidecar -- either declare "
            "spec.contract and regenerate, or remove the stray marker pair.",
            file=sys.stderr,
        )

    if failed or orphaned:
        if failed:
            print(f"skill-contract-drift failed for: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"skill-contract-drift: {len(contract_names)} contract-declaring skill(s) match a fresh regeneration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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

Exit code: 0 when every discovered skill's committed `SKILL.md` contract
region matches a fresh regeneration (including the zero-skills case), 1 on
any drift, generation failure, or a `--check` subprocess that times out.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gitapex_scan_ssot_schema as ssot_schema

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATOR_SCRIPT = REPO_ROOT / "skills" / "drafting-a-skill" / "scripts" / "gitapex_generate_skill_contract.py"

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


def main() -> int:
    # function-body-test-coverage: WAIVED: exercised via tests/test_gitapex_skill_contract_drift.py -- see check_skill's own identical waiver comment above for the full reason.
    contract_names = sorted(ssot_schema.discover_contracts())
    if not contract_names:
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

    if failed:
        print(f"skill-contract-drift failed for: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"skill-contract-drift: {len(contract_names)} contract-declaring skill(s) match a fresh regeneration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Enforce a 1:1 mapping between skills/*/ and evals/*/eval.yaml.

Issue #928. The issue's own retrospective found `docs/skill-eval-status.md`
had silently drifted from the real repository state (25 skills, 23
`eval.yaml` at the time this gate was authored -- two skills,
`evaluating-context-channel-maturity` and `setup-gitapex-toolchain`,
carried no eval suite at all, and nothing mechanical noticed). This gate
closes the gap going forward: every real `skills/<name>/` directory must
have a matching `evals/<name>/eval.yaml`, and every `evals/<name>/eval.yaml`
must have a matching `skills/<name>/` directory. Neither direction is
checked alone -- a skill that later loses its eval suite (deleted by
mistake) and an orphaned `eval.yaml` left behind after a skill rename or
deletion are both real drift, and both fail this gate.

`evals/scripts/` is not a skill's own eval directory (it holds shared
Python helpers `gitapex_check_dimension_coverage.py` and friends read
across skills, not fixture/eval.yaml content for a skill named
"scripts") and is excluded by construction: only immediate `evals/*`
subdirectories that themselves contain an `eval.yaml` file count as the
"has an eval suite" side of the comparison, so a bare `evals/scripts/`
with no `eval.yaml` of its own never enters the set at all -- no
special-cased exclusion list to keep in sync as new shared-helper
directories are added later.

Name comparison is exact-string, never case-folded or otherwise
normalized: a `Skills/Foo` vs. `skills/foo` mismatch (a case-sensitivity
typo, or two directories differing only in case, which several real
filesystems permit and would fail to conflict at all when copied to a
case-preserving one) is real drift, not a match. Only two, mechanical,
non-semantic normalizations are applied before comparing -- stripping the
`skills/`/`evals/` root and a single trailing slash on either side, so
`skills/foo/` and `evals/foo/eval.yaml` both normalize to the bare name
`foo` for comparison, never comparing raw path strings that could never be
equal to each other by construction regardless of real parity.

ACTIVE (issue #928): registered in `.gitapex/ssot.json` as
`skill-eval-yaml-parity`. Enforced the same way its sibling
`gitapex_scan_skill_metadata_schema.py` (`skill-metadata-schema-drift`) and
`gitapex_scan_split_schema.py` (`split-schema-drift`) already are: no
dedicated CI workflow step or pre-commit hook, enforced solely because
`tests/test_gitapex_gate_skill_eval_yaml_parity.py`'s own
`test_real_repository_skills_and_eval_yaml_are_in_parity` calls
`find_parity_drift()` against the real `skills/`/`evals/` trees with no
fixture override, and `tests/` is auto-discovered by pytest via
`pyproject.toml`'s `[tool.pytest.ini_options] testpaths` -- which
`.github/workflows/test.yml` runs as a required check on every push and
PR.

Run standalone (exit 0 clean, 1 on drift) or via the pytest gate in
`tests/test_gitapex_gate_skill_eval_yaml_parity.py`.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
EVALS_DIR = REPO_ROOT / "evals"

# Guards against discover_skill_names/discover_eval_yaml_skill_names silently
# finding nothing (a wrong working directory, a checkout that lost most of
# skills/ or evals/) and find_parity_drift then vacuously reporting "no
# drift" because both empty sets compare equal -- the same fail-closed
# purpose as gitapex_scan_skill_metadata_schema.py's own
# MIN_EXPECTED_SKILL_DIRS and gitapex_scan_split_schema.py's own
# MIN_EXPECTED_SPLIT_JSON_FILES (dimension 15,
# evaluating-deterministic-gate-quality). This repository has 25 real
# skills today; the floor is set below that real count so a partial
# discovery failure is still caught, while new skills gaining their own
# directory over time does not need a matching bump here.
MIN_EXPECTED_SKILL_NAMES = 15


def discover_skill_names(skills_dir: pathlib.Path = SKILLS_DIR) -> set[str]:
    """Bare directory names of every immediate `skills/*` subdirectory."""
    if not skills_dir.is_dir():
        return set()
    return {path.name for path in skills_dir.iterdir() if path.is_dir()}


def discover_eval_yaml_skill_names(evals_dir: pathlib.Path = EVALS_DIR) -> set[str]:
    """Bare directory names of every immediate `evals/*` subdirectory that
    itself contains an `eval.yaml` file -- never a bare `evals/*`
    subdirectory listing, since `evals/scripts/` holds shared helper
    scripts, not a skill's own eval suite, and carries no `eval.yaml` of
    its own to be excluded by name at all."""
    if not evals_dir.is_dir():
        return set()
    return {path.name for path in evals_dir.iterdir() if path.is_dir() and (path / "eval.yaml").is_file()}


def find_parity_drift(
    skills_dir: pathlib.Path = SKILLS_DIR,
    evals_dir: pathlib.Path = EVALS_DIR,
    min_expected_skill_names: int = MIN_EXPECTED_SKILL_NAMES,
) -> list[str]:
    """Return every parity drift finding: a skill with no matching
    `eval.yaml`, or an `eval.yaml` with no matching skill directory. Empty
    list means the two sets are in exact 1:1 parity.

    `min_expected_skill_names` is a fail-closed floor on discovery itself,
    checked before any set comparison: fewer than this many real skill
    directories is treated as a drift finding, not silently reported as
    "no drift" because an empty (or near-empty) skills/ set trivially
    equals an empty (or near-empty) evals/ set. A caller exercising a
    deliberately small fixture directory (this module's own tests) must
    pass a lower value explicitly; every other caller, including
    `main()`, keeps the real-repository-sized default.
    """
    skill_names = discover_skill_names(skills_dir)
    eval_yaml_names = discover_eval_yaml_skill_names(evals_dir)

    if len(skill_names) < min_expected_skill_names:
        return [
            f"only {len(skill_names)} skill(s) discovered under {skills_dir} "
            f"(expected at least {min_expected_skill_names}) -- treating this as a "
            "discovery failure (wrong working directory, or a checkout that lost most "
            "of skills/) rather than comparing a vacuously small set"
        ]

    findings: list[str] = []
    missing_eval_yaml = sorted(skill_names - eval_yaml_names)
    for name in missing_eval_yaml:
        findings.append(f"{skills_dir / name} has no matching {evals_dir / name / 'eval.yaml'}")

    orphaned_eval_yaml = sorted(eval_yaml_names - skill_names)
    for name in orphaned_eval_yaml:
        findings.append(f"{evals_dir / name / 'eval.yaml'} has no matching {skills_dir / name}")

    return findings


def main() -> int:
    findings = find_parity_drift()
    if findings:
        print("skill<->eval.yaml parity drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("PASS: every skills/*/ directory has a matching evals/*/eval.yaml, and vice versa")
    return 0


if __name__ == "__main__":
    sys.exit(main())

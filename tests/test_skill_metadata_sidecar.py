"""CI gate: every real skill in this repository passes the deterministic
shape checker (skills/evaluating-skill-quality/scripts/check_skill_shape.py).

Today that checker's own unit tests run in CI, but the checker was never
actually applied to the repository's real skills as part of any automated
run -- a new skill with a missing or malformed gitapex_metadata.yaml sidecar
(or any other shape violation) could merge green. This test closes that gap
by discovering every skills/*/ directory that has a SKILL.md and running
check_shape() against it, parametrized per skill so a failure names the
offending skill directly rather than reporting one opaque aggregate result.
"""

from __future__ import annotations

import pathlib

import pytest

import check_skill_shape as css

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

# Guards against the discovery silently finding nothing (e.g. a bad REPO_ROOT
# or a moved skills/ directory) and the test suite then vacuously "passing".
# There are 17 skills in this repository today; a floor of 10 would tolerate
# losing 7 of them silently, so the floor is set close to the real count.
MIN_EXPECTED_SKILLS = 15


def _discover_skill_dirs() -> list[pathlib.Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        p.parent for p in SKILLS_DIR.glob("*/SKILL.md") if p.is_file()
    )


SKILL_DIRS = _discover_skill_dirs()


def test_discovery_found_a_plausible_number_of_skills():
    assert len(SKILL_DIRS) >= MIN_EXPECTED_SKILLS, (
        f"expected at least {MIN_EXPECTED_SKILLS} skills under {SKILLS_DIR}, "
        f"found {len(SKILL_DIRS)}: {[d.name for d in SKILL_DIRS]}. "
        "This usually means skill discovery is broken (wrong repo root, "
        "moved skills/ directory), not that skills were actually removed."
    )


@pytest.mark.parametrize(
    "skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS]
)
def test_skill_passes_deterministic_shape_checker(skill_dir):
    results = css.check_shape(skill_dir)
    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"{skill_dir.name}: {len(failures)} shape check(s) failed:\n"
        + "\n".join(
            f"  - {r.name}: {r.rule} -- evidence: {r.evidence}"
            for r in failures
        )
    )


# Drift gate for the single-source-of-truth invariant Sub-project C
# established: docs/skill-provenance.md was retired in favor of each
# skill's own gitapex_metadata.yaml spec.references, precisely so
# provenance has exactly one home. Per CLAUDE.md's rule that such an
# invariant ships its drift gate in the same change, not a follow-up.

# The four skills docs/skill-provenance.md named before it was retired
# (Sub-project C, issue #184) -- kept here, not re-derived from the
# (deleted) file, since this is a fixed historical fact of that migration.
SKILLS_WITH_MIGRATED_PROVENANCE = (
    "battle-testing-a-skill",
    "establishing-ubiquitous-language",
    "scorer-gated-skill-edits",
    "evaluating-skill-quality",
)


def test_skill_provenance_file_stays_retired():
    assert not (REPO_ROOT / "docs" / "skill-provenance.md").exists(), (
        "docs/skill-provenance.md was retired in favor of each skill's own "
        "gitapex_metadata.yaml spec.references (Sub-project C, issue #184) "
        "-- recreating it would reintroduce a second home for the same "
        "maintainer-facing provenance data."
    )


@pytest.mark.parametrize("skill_name", SKILLS_WITH_MIGRATED_PROVENANCE)
def test_migrated_provenance_stays_populated(skill_name):
    skill_dir = SKILLS_DIR / skill_name
    parsed = css._parse_manifest(
        (skill_dir / css.SIDECAR_FILENAME).read_text(encoding="utf-8"))
    references = parsed.root.get("spec", {}).get("references")
    assert isinstance(references, list) and references, (
        f"{skill_name}'s gitapex_metadata.yaml lost its migrated "
        "spec.references content (Sub-project C, issue #184); this is the "
        "sole remaining home for that provenance now that "
        "docs/skill-provenance.md is retired."
    )

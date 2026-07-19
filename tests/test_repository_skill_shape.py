"""Integration gate: every committed skill passes the deterministic shape
checker.

`test_check_skill_shape.py` proves the rules against synthetic fixtures;
this runs the same `check_skill_shape.check_shape` over the repository's
real `skills/*/`, so the checks -- including the issue #171 Portable
self-citation scan -- gate actual skill content in CI (the `test.yml`
pytest run), not only hand-built cases.
"""
from pathlib import Path

import pytest

import check_skill_shape as css

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRS = sorted(
    p for p in (REPO_ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda p: p.name)
def test_committed_skill_passes_shape(skill_dir):
    failures = [r for r in css.check_shape(skill_dir) if not r.passed]
    assert not failures, "; ".join(f"{r.name}: {r.evidence}" for r in failures)

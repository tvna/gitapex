"""CI gate: every skills/<name>/ directory has a corresponding
evals/<name>/eval-status.md file and a row in docs/skill-eval-status.md's
"## Index" table.

Issue #503 (retrospective for PR #501): the new docs/skill-eval-status.md
index table omitted `evaluating-deterministic-gate-quality` -- the skill
was added in issue #435, but nothing ever checked that its eval-status
bookkeeping (an `evals/<skill>/eval-status.md` file, plus an index row)
was created alongside it. External review (Codex, on PR #501) caught the
gap, not this repository's own gates, because no gate existed. This
asserts the exact 1:1 correspondence between `skills/*/` and both eval-
status artifacts going forward, so a future new skill can't silently
reintroduce the same gap.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
EVALS_DIR = REPO_ROOT / "evals"
STATUS_DOC = REPO_ROOT / "docs" / "skill-eval-status.md"

_INDEX_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)


def _skill_names() -> list[str]:
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())


def _index_section() -> str:
    text = STATUS_DOC.read_text(encoding="utf-8")
    marker = "## Index"
    start = text.find(marker)
    assert start != -1, f"{STATUS_DOC} has no '## Index' section"
    return text[start:]


def _indexed_skill_names() -> set[str]:
    return set(_INDEX_ROW_RE.findall(_index_section()))


def test_every_skill_has_an_eval_status_file():
    missing = [name for name in _skill_names() if not (EVALS_DIR / name / "eval-status.md").is_file()]
    assert not missing, (
        "the following skills/<name>/ directories have no "
        f"evals/<name>/eval-status.md: {missing} -- add one (see "
        "evals/auditing-agent-product-scope/eval-status.md for the "
        "disclosed-gap pattern when no suite exists yet) in the same "
        "change that adds the skill."
    )


def test_every_skill_has_an_index_row():
    skills = set(_skill_names())
    indexed = _indexed_skill_names()
    missing = sorted(skills - indexed)
    assert not missing, (
        f"{STATUS_DOC}'s '## Index' table has no row for: {missing} -- "
        "add a '| `<skill>` | [evals/<skill>/eval-status.md]"
        "(../evals/<skill>/eval-status.md) |' row in the same change "
        "that adds the skill."
    )
    stale = sorted(indexed - skills)
    assert not stale, (
        f"{STATUS_DOC}'s '## Index' table has a row for: {stale}, but no "
        "corresponding skills/<name>/ directory exists -- remove the "
        "stale row (and evals/<name>/, if orphaned) in the same change "
        "that renames or removes the skill."
    )


def test_no_orphaned_eval_status_files():
    skills = set(_skill_names())
    eval_status_dirs = {p.name for p in EVALS_DIR.iterdir() if p.is_dir() and (p / "eval-status.md").is_file()}
    orphaned = sorted(eval_status_dirs - skills)
    assert not orphaned, (
        f"evals/<name>/eval-status.md exists for {orphaned}, but no "
        "corresponding skills/<name>/ directory exists -- remove the "
        "orphaned evals/<name>/ directory (and its docs/skill-eval-"
        "status.md index row, if any) in the same change that renames "
        "or removes the skill."
    )

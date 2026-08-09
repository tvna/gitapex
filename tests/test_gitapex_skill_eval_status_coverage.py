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

Issue #928: six `eval-status.md` files stated nothing but the same four
facts (which model(s) were evaluated, that cross-model behavior is
unmeasured, whether a no-skill baseline is committed, and the declared
trials-per-task) in six different prose forms -- all derivable from
`eval.yaml` / `results/*/manifest.json` rather than hand-maintained. Of
those six, two (`planning-a-branch-from-an-issue`, `drafting-a-pr-to-merge`)
carried only that derivable content and were deleted; the other four
carried real non-derivable judgment prose (a qualitative cross-model risk
assessment tied to the skill's own freedom/over-prescription profile, or a
dimension-specific interpretation note) and were kept. DERIVABLE_FACTS_
SKILLS below exempts the two deleted ones from the 1:1 rule so a future
generator (docs/skill-eval-status.md) doesn't need a matching file or
index row for them.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
EVALS_DIR = REPO_ROOT / "evals"
STATUS_DOC = REPO_ROOT / "docs" / "skill-eval-status.md"

_INDEX_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)

# Skills whose eval-status facts are fully derivable from eval.yaml /
# results/*/manifest.json and therefore intentionally have no
# evals/<name>/eval-status.md file and no docs/skill-eval-status.md index
# row (see issue #928's module docstring note above).
DERIVABLE_FACTS_SKILLS = frozenset(
    {
        "planning-a-branch-from-an-issue",
        "drafting-a-pr-to-merge",
    }
)


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
    missing = [
        name
        for name in _skill_names()
        if name not in DERIVABLE_FACTS_SKILLS and not (EVALS_DIR / name / "eval-status.md").is_file()
    ]
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
    missing = sorted(skills - indexed - DERIVABLE_FACTS_SKILLS)
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

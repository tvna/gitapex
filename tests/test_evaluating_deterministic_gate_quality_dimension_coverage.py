"""CI gate: evaluating-deterministic-gate-quality/eval-status.md's disclosed
uncovered-dimension list stays in sync with what check_dimension_coverage.py
actually computes against the real corpus.

Issue #511: a `fable` subagent built this skill's dimension/axis coverage
map by hand in one review round; nothing then kept the map current as
fixtures were added, removed, or relabeled. This asserts eval-status.md's
own disclosed gap list -- not a vague "looks mostly covered" -- matches the
tool's exact computed output, the same "exact 1:1, no skip/N/A" bar
tests/test_skill_eval_status_coverage.py and
tests/test_skill_eval_status_sync.py already hold other eval bookkeeping to.
"""
from __future__ import annotations

import pathlib
import re

import check_dimension_coverage as C

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"
TASKS_GLOB = str(
    REPO_ROOT / "evals" / "evaluating-deterministic-gate-quality" / "tasks" / "*.yaml"
)
STATUS_DOC = REPO_ROOT / "evals" / "evaluating-deterministic-gate-quality" / "eval-status.md"


def test_every_uncovered_dimension_is_disclosed_in_eval_status():
    report = C.compute_coverage(SKILL_DIR, TASKS_GLOB)
    text = STATUS_DOC.read_text(encoding="utf-8")
    # Word-boundary match, not a bare substring check: "1" is a substring of
    # "11"/"12"/"17", so a naive `n in text` could false-pass an undisclosed
    # single-digit dimension merely because a different two-digit one is
    # mentioned nearby.
    missing = [n for n in report.uncovered_dimensions
               if not re.search(rf"\b{re.escape(n)}\b", text)]
    assert not missing, (
        f"check_dimension_coverage.py reports dimension(s) {missing} as "
        f"uncovered by the real corpus, but {STATUS_DOC} does not disclose "
        "them -- either add a fixture citation for the dimension, or update "
        "the doc's disclosed-gap list in the same change that drops the "
        "last citation to it."
    )


def test_every_uncovered_axis_is_disclosed_in_eval_status():
    report = C.compute_coverage(SKILL_DIR, TASKS_GLOB)
    text = STATUS_DOC.read_text(encoding="utf-8")
    missing = [a for a in report.uncovered_axes if a not in text]
    assert not missing, (
        f"check_dimension_coverage.py reports axis/axes {missing} as "
        f"uncovered by the real corpus, but {STATUS_DOC} does not disclose "
        "them -- add a fixture citation, or update the doc's disclosed-gap "
        "list in the same change."
    )

"""CI gate: evaluating-deterministic-gate-quality/eval-status.md's disclosed
uncovered-dimension list and headline coverage count stay in exact sync with
what check_dimension_coverage.py actually computes against the real corpus.

Issue #511: a `fable` subagent built this skill's dimension/axis coverage
map by hand in one review round; nothing then kept the map current as
fixtures were added, removed, or relabeled. This asserts eval-status.md's
own disclosed gap list -- not a vague "looks mostly covered" -- matches the
tool's exact computed output, the same "exact 1:1, no skip/N/A" bar
tests/test_skill_eval_status_coverage.py and
tests/test_skill_eval_status_sync.py already hold other eval bookkeeping to.

Bidirectional by design, not just "every uncovered item is mentioned
somewhere": an earlier version of this gate only checked that direction,
so a dimension that later gained real coverage would stay listed as
uncovered in the doc -- and the "N/19 dimensions ... cited" headline count
would go stale -- with nothing in CI to catch it. Both directions and the
headline count are checked here.
"""

from __future__ import annotations

import re
from pathlib import Path

import check_dimension_coverage as C

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"
TASKS_GLOB = str(REPO_ROOT / "evals" / "evaluating-deterministic-gate-quality" / "tasks" / "*.yaml")
STATUS_DOC = REPO_ROOT / "evals" / "evaluating-deterministic-gate-quality" / "eval-status.md"

_HEADLINE_RE = re.compile(r"Current\s+output:\s+(\d+)/(\d+)\s+dimensions\s+and\s+(\d+)/(\d+)\s+axes\s+cited")
_UNCOVERED_SENTENCE_RE = re.compile(r"\*\*dimensions\s+(.+?)\s+remain uncovered\*\*", re.DOTALL)


def _disclosed_uncovered_dimensions(text: str) -> set[str]:
    match = _UNCOVERED_SENTENCE_RE.search(text)
    if not match:
        return set()
    return set(re.findall(r"\d+", match.group(1)))


def test_every_uncovered_dimension_is_disclosed_in_eval_status():
    report = C.compute_coverage(SKILL_DIR, TASKS_GLOB)
    text = STATUS_DOC.read_text(encoding="utf-8")
    computed = set(report.uncovered_dimensions)
    disclosed = _disclosed_uncovered_dimensions(text)

    missing = sorted(computed - disclosed, key=int)
    assert not missing, (
        f"check_dimension_coverage.py reports dimension(s) {missing} as "
        f"uncovered by the real corpus, but {STATUS_DOC}'s '**dimensions ... "
        "remain uncovered**' sentence does not list them -- either add a "
        "fixture citation for the dimension, or add it to that sentence in "
        "the same change."
    )

    stale = sorted(disclosed - computed, key=int)
    assert not stale, (
        f"{STATUS_DOC}'s '**dimensions ... remain uncovered**' sentence "
        f"still lists dimension(s) {stale}, but check_dimension_coverage.py "
        "now finds them cited by the real corpus -- update the doc's "
        "disclosed-gap list (and its 'N/19 dimensions ... cited' headline "
        "count) in the same change that adds the citation, so the doc "
        "doesn't overstate the gap after coverage improves."
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


def test_headline_coverage_count_matches_computed_output():
    report = C.compute_coverage(SKILL_DIR, TASKS_GLOB)
    text = STATUS_DOC.read_text(encoding="utf-8")
    match = _HEADLINE_RE.search(text)
    assert match is not None, (
        f"{STATUS_DOC} has no 'Current output: N/19 dimensions and M/4 axes "
        "cited' headline sentence for test_headline_coverage_count_matches_"
        "computed_output to check -- add one (or update this test's regex, "
        "if the phrasing changed deliberately) rather than letting the "
        "count silently disappear."
    )
    dim_cited, dim_total, axis_cited, axis_total = match.groups()
    assert int(dim_cited) == len(report.dimension_hits)
    assert int(dim_total) == len(report.dimensions)
    assert int(axis_cited) == len(report.axis_hits)
    assert int(axis_total) == len(report.axes)

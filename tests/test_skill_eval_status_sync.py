"""CI gate: evals/merge-retrospective/eval-status.md's fixture count stays
in sync with the real corpus under evals/merge-retrospective/tasks/.

Codex review on PR #328 found this section still stated "five task files,
zero Step 0 coverage" after the corpus had already grown to 18 fixtures
with real Step 0 coverage (issue #312) -- the two sources had silently
desynchronized with nothing to catch it. This asserts the doc's own
stated count against the real fixture count going forward.

Issue #499: the doc moved from a single central docs/skill-eval-status.md
to one file per skill under evals/<skill>/eval-status.md; this gate's
target path moved with it.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUS_DOC = REPO_ROOT / "evals" / "merge-retrospective" / "eval-status.md"
FIXTURES_DIR = REPO_ROOT / "evals" / "merge-retrospective" / "tasks"

_COUNT_RE = re.compile(r"\*\*(\d+)\s+committed task files\*\*")


def _real_fixture_count() -> int:
    return len(list(FIXTURES_DIR.glob("*.yaml")))


def test_status_doc_states_a_fixture_count():
    text = STATUS_DOC.read_text(encoding="utf-8")
    match = _COUNT_RE.search(text)
    assert match is not None, (
        f"{STATUS_DOC} no longer states a '**N committed task files**' "
        "count in its merge-retrospective section -- update the doc (and "
        "this test's regex, if the phrasing changed deliberately) rather "
        "than letting the count silently disappear."
    )


def test_status_doc_fixture_count_matches_real_corpus():
    text = STATUS_DOC.read_text(encoding="utf-8")
    match = _COUNT_RE.search(text)
    assert match is not None, f"see test_status_doc_states_a_fixture_count for {STATUS_DOC}"
    stated_count = int(match.group(1))
    real_count = _real_fixture_count()
    assert stated_count == real_count, (
        f"{STATUS_DOC}'s merge-retrospective section states "
        f"{stated_count} committed task files, but "
        f"{FIXTURES_DIR} actually has {real_count} -- update the doc's "
        "count (and its split.md cross-reference) in the same change "
        "that adds or removes a fixture."
    )

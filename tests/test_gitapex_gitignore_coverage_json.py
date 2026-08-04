"""Drift gate for the `coverage.json` gitignore entry.

Issue #536: `test.yml`'s pytest step now also emits `coverage.json`
(consumed by `gitapex_gate_evals_scripts_coverage.py`), alongside the
already-gitignored `.coverage` and `coverage.xml`. If a future
`.gitignore` edit removes this pattern, a locally regenerated
`coverage.json` would become stageable content instead of staying an
ephemeral build artifact.
"""

from __future__ import annotations

from conftest import REPO_ROOT, assert_path_is_gitignored


def test_coverage_json_is_gitignored() -> None:
    assert_path_is_gitignored(REPO_ROOT / "coverage.json", "'coverage.json'")

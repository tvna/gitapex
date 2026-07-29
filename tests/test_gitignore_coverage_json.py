"""Drift gate for the `coverage.json` gitignore entry.

Issue #536: `test.yml`'s pytest step now also emits `coverage.json`
(consumed by `gate_evals_scripts_coverage.py`), alongside the
already-gitignored `.coverage` and `coverage.xml`. If a future
`.gitignore` edit removes this pattern, a locally regenerated
`coverage.json` would become stageable content instead of staying an
ephemeral build artifact.
"""

from __future__ import annotations

import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_coverage_json_is_gitignored() -> None:
    representative = REPO_ROOT / "coverage.json"
    result = subprocess.run(
        ["git", "check-ignore", "-v", str(representative)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "'coverage.json' is no longer covered by .gitignore -- a locally "
        "regenerated coverage report would become stageable content."
    )
    source = result.stdout.split(":", 1)[0]
    repo_gitignore = REPO_ROOT / ".gitignore"
    assert pathlib.Path(source).resolve() == repo_gitignore.resolve(), (
        f"'coverage.json' is ignored, but by {source!r} instead of this "
        f"repository's own {repo_gitignore} -- an ambient exclude source "
        "is masking a possibly-removed repository rule."
    )

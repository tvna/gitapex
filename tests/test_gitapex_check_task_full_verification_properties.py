"""Hypothesis property layer for
``skills/executing-a-branch-plan/scripts/gitapex_check_task_full_verification.py``'s
consumer-repository skip in ``main()`` (issue #1996).

The thorough example-based coverage for this module lives COLOCATED at
``skills/executing-a-branch-plan/scripts/test_gitapex_check_task_full_verification.py``,
matching this skill's own convention. This file exists because
``gitapex_gate_function_body_test_coverage.py`` looks for a test of a changed
function in this repository-wide ``tests/test_<stem>_properties.py``
location, and a property is the natural shape here: whatever else a working
directory holds, ``main()`` skips exactly when gitapex's own preflight runner
is absent, and never runs a verification step when it skips.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching ``tests/test_gitapex_check_task_worktree_base_properties.py``.
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import subprocess
import tempfile

import gitapex_check_task_full_verification as checker
import pytest
from conftest import FakeStdin as _FakeStdin
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=50, deadline=None)

# Relative file paths a worktree might hold, excluding the marker itself.
_OTHER_FILES = st.lists(
    st.sampled_from(
        [
            "README.md",
            "pyproject.toml",
            ".github/workflows/ci.yml",
            ".github/scripts/other_gate.py",
            "scripts/gitapex_gate_local_preflight.py",
            "gitapex_gate_local_preflight.py",
        ]
    ),
    unique=True,
    max_size=6,
)


@_PROPERTIES
@given(other_files=_OTHER_FILES, marker_present=st.booleans())
def test_main_skips_exactly_when_the_marker_is_absent(other_files: list[str], marker_present: bool) -> None:
    with tempfile.TemporaryDirectory() as raw_root:
        root = pathlib.Path(raw_root)
        for relative in [*other_files, *([checker.GITAPEX_SUITE_MARKER] if marker_present else [])]:
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text("", encoding="utf-8")
        ran: list[pathlib.Path] = []

        def record(_steps: object, cwd: pathlib.Path, _timeout: int) -> dict[str, object]:
            ran.append(cwd)
            return {"decision": "allow"}

        out = io.StringIO()
        with pytest.MonkeyPatch.context() as patch, contextlib.redirect_stdout(out):
            patch.setattr(checker, "run_verification", record)
            patch.setattr("sys.stdin", _FakeStdin(json.dumps({"cwd": str(root)}).encode("utf-8")))
            assert checker.main([]) == 0
        verdict = json.loads(out.getvalue())

        if marker_present:
            assert verdict == {"decision": "allow"}
            assert ran == [root]
        else:
            assert verdict["decision"] == "skip"
            assert checker.GITAPEX_SUITE_MARKER in verdict["reason"]
            assert ran == []


@_PROPERTIES
@given(depth=st.integers(min_value=0, max_value=4))
def test_repository_root_resolves_the_top_level_from_any_depth(depth: int) -> None:
    with tempfile.TemporaryDirectory() as raw_root:
        root = pathlib.Path(raw_root).resolve()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        cwd = root.joinpath(*[f"d{i}" for i in range(depth)])
        cwd.mkdir(parents=True, exist_ok=True)
        assert checker.repository_root(cwd).resolve() == root

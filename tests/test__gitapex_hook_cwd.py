"""Tests for the shared hook-payload cwd resolver
(skills/executing-a-branch-plan/scripts/_gitapex_hook_cwd.py, issue #1566).

Extracted from two byte-for-byte-identical private helpers
(gitapex_check_task_worktree_base.py's and
gitapex_check_task_full_verification.py's own former `_resolve_cwd`) --
this is the first direct test coverage either function's own logic had,
since each pre-existing test file only ever drove it indirectly through
that script's own `main()`.

Lives here rather than colocated at
skills/executing-a-branch-plan/scripts/test__gitapex_hook_cwd.py, the
directory's own usual convention for a plain unit-test file (e.g.
test_gitapex__path_normalize.py next to _gitapex_path_normalize.py):
gitapex_gate_function_body_test_coverage.py's own "Existing-coverage
check" only ever accepts tests/test_{stem}.py or
tests/test_{stem}_properties.py, unconditionally, regardless of the
source file's own directory -- so a colocated test alone would not
clear that gate for a new function like `resolve_cwd`. A deliberate,
gate-driven placement, not an oversight of the directory's own
convention.
"""

from __future__ import annotations

import pathlib

import _gitapex_hook_cwd
import pytest


def test_resolve_cwd_uses_the_payloads_cwd_when_it_names_a_real_directory(tmp_path: pathlib.Path) -> None:
    resolved = _gitapex_hook_cwd.resolve_cwd({"cwd": str(tmp_path)})
    assert resolved == tmp_path


def test_resolve_cwd_falls_back_to_the_process_cwd_when_the_payload_has_no_cwd_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _gitapex_hook_cwd.resolve_cwd({}) == tmp_path


def test_resolve_cwd_falls_back_when_the_payloads_cwd_does_not_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """A payload naming a directory that is not actually on disk (a
    fabricated or stale `cwd` field) must not be trusted at face value --
    the same fail-safe fallback as a missing field entirely."""
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "does-not-exist"
    assert _gitapex_hook_cwd.resolve_cwd({"cwd": str(missing)}) == tmp_path


def test_resolve_cwd_falls_back_when_the_payloads_cwd_is_not_a_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """A malformed payload (`cwd` present but not a string -- e.g. a
    hook input shape this checker did not expect) is treated the same as
    a missing field, never passed to `pathlib.Path` as-is."""
    monkeypatch.chdir(tmp_path)
    assert _gitapex_hook_cwd.resolve_cwd({"cwd": 12345}) == tmp_path

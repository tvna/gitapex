"""Tests for the PR title convention gate
(.github/scripts/gitapex_gate_pr_title_convention.py).

Issue #1058: the CI-side backstop for hooks/check-pr-title-convention.sh,
covering a PR opened or retitled via the GitHub web UI, the `gh` CLI, or
another bot -- none of which goes through that PreToolUse hook.
"""

from __future__ import annotations

import io

import gitapex_gate_pr_title_convention as gate
import pytest


@pytest.mark.parametrize(
    "title",
    [
        "feat: add a thing",
        "fix(gates): correct a bug",
        "docs: update the readme",
        "style: reformat",
        "refactor(hooks): simplify a check",
        "perf: speed up a loop",
        "test(gates): add coverage",
        "build: bump a dependency",
        "ci: adjust a workflow",
        "chore: housekeeping",
        "revert: undo a change",
        "feat(api)!: drop the v1 endpoint",
        "fix!: breaking bugfix with no scope",
    ],
)
def test_valid_titles_pass(title: str) -> None:
    assert gate.is_conventional_commit_title(title) is True


@pytest.mark.parametrize(
    "title",
    [
        "",
        None,
        "Add a thing",
        "Fix: wrong case type",
        "feat : space before colon",
        "feat:no space after colon",
        "feature: not a recognized type",
        "feat(scope with spaces): bad scope",
        "feat: " + "x" * 73,
        "feat(gates): trailing newline\n",
    ],
)
def test_invalid_titles_fail(title: str | None) -> None:
    assert gate.is_conventional_commit_title(title) is False


def test_main_exits_zero_for_a_valid_title() -> None:
    assert gate.main(["--title", "feat: add a thing"]) == 0


def test_main_exits_one_for_an_invalid_title() -> None:
    assert gate.main(["--title", "Add a thing"]) == 1


def test_main_reads_stdin_when_title_flag_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate.sys, "stdin", io.TextIOWrapper(io.BufferedReader(io.BytesIO(b"feat: from stdin"))))
    assert gate.main([]) == 0


def test_main_exits_one_on_invalid_utf8_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    # 0xFF is not a valid UTF-8 lead byte on its own.
    monkeypatch.setattr(gate.sys, "stdin", io.TextIOWrapper(io.BufferedReader(io.BytesIO(b"\xff\xfe"))))
    assert gate.main([]) == 1

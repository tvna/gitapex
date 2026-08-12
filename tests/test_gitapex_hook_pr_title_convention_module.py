"""Direct-import unit tests for hooks/gitapex_check_pr_title_convention.py.

hooks/test_gitapex_check_pr_title_convention.py already exercises this
module's real invocation path (subprocess, via
hooks/check-pr-title-convention.sh calling `python3
gitapex_check_pr_title_convention.py` as a *separate process*), but
coverage.py running in the pytest process cannot see line execution
inside that subprocess -- the same reason
tests/test_gitapex_check_acm_present_or_waiver.py exists as a sibling
direct-import suite for hooks/gitapex_check_acm_present_or_waiver.py.
Named `..._module.py`, not `test_gitapex_check_pr_title_convention.py`,
to avoid colliding with hooks/test_gitapex_check_pr_title_convention.py's
own basename -- this repository has no `__init__.py` anywhere, so pytest
resolves module identity by basename alone and two identically-named test
files in different directories fail to collect together.
"""

from __future__ import annotations

import io

import gitapex_check_pr_title_convention as checker
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
    assert checker.is_conventional_commit_title(title) is True


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
        "feat(gates): trailing carriage return\r",
        "feat(gates): trailing crlf\r\n",
    ],
)
def test_invalid_titles_fail(title: str | None) -> None:
    assert checker.is_conventional_commit_title(title) is False


def test_main_exits_zero_for_a_valid_title() -> None:
    assert checker.main(["--title", "feat: add a thing"]) == 0


def test_main_exits_one_for_an_invalid_title() -> None:
    assert checker.main(["--title", "Add a thing"]) == 1


def test_main_reads_stdin_when_title_flag_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checker.sys, "stdin", io.TextIOWrapper(io.BufferedReader(io.BytesIO(b"feat: from stdin"))))
    assert checker.main([]) == 0


def test_main_exits_one_on_invalid_utf8_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    # 0xFF is not a valid UTF-8 lead byte on its own.
    monkeypatch.setattr(checker.sys, "stdin", io.TextIOWrapper(io.BufferedReader(io.BytesIO(b"\xff\xfe"))))
    assert checker.main([]) == 1

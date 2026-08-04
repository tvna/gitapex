"""Tests for the hidden-characters gate
(.github/scripts/gate_hidden_characters.py).

Issue #702 (refs #665 repair 6, retrospective for PR #651). Two new files in that PR
were first authored with a literal U+FEFF instead of the escape sequence,
caught only by author attention before commit; a full-repository scan of
`main` found five more tracked files already carrying the same literal
mistake. This gate exists so author attention is no longer the only thing
standing between a literal hidden character and a merged commit.

Every violation fixture below is built from `chr(0x....)` or the `\\uXXXX`
escape sequence, never a literal hidden character typed into this file --
that would be exactly the mistake this gate exists to catch, reproduced in
its own test suite (the same trap issue #665 repair 6 itself names).
"""

from __future__ import annotations

import pathlib
import subprocess

import gate_hidden_characters as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_BOM = chr(0xFEFF)
_ZERO_WIDTH_SPACE = chr(0x200B)
_RTL_OVERRIDE = chr(0x202E)
_WORD_JOINER = chr(0x2060)


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Init a git repository -- discovery reads tracked files, not the tree."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _write(root: pathlib.Path, relative: str, content: str, *, track: bool = True) -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if track:
        subprocess.run(["git", "-C", str(root), "add", "--", relative], check=True)
    return path


# --- the real repository -------------------------------------------------


def test_repository_has_no_hidden_characters() -> None:
    """The real checkout passes -- the regression anchor for #665 repair 6's
    fix (five tracked files converted from literal U+FEFF to the escape
    form)."""
    assert gate.find_violations(REPO_ROOT) == []


def test_repository_scan_reaches_a_large_tracked_set() -> None:
    """Without this, a discovery bug that found nothing would make the test
    above pass for the wrong reason."""
    discovered = gate.discover(REPO_ROOT)
    assert len(discovered) > 100
    relatives = {p.relative_to(REPO_ROOT).as_posix() for p in discovered}
    assert "pyproject.toml" in relatives
    assert "hooks/hooks.json" in relatives


# --- violations ------------------------------------------------------------


def test_leading_bom_is_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.py", f'{_BOM}text = "hello"\n')
    violations = gate.find_violations(root)
    assert [v.path for v in violations] == ["a.py"]
    assert violations[0].line == 1
    assert violations[0].column == 1
    assert violations[0].codepoint == 0xFEFF


def test_zero_width_space_mid_line_is_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", f"abc{_ZERO_WIDTH_SPACE}def\n")
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].line == 1
    assert violations[0].column == 4


def test_bidi_override_is_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", f"safe{_RTL_OVERRIDE}text\n")
    assert len(gate.find_violations(root)) == 1


def test_word_joiner_is_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", f"safe{_WORD_JOINER}text\n")
    assert len(gate.find_violations(root)) == 1


def test_violation_on_a_later_line_reports_correct_line_and_column(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", f"line one\nline two\nli{_ZERO_WIDTH_SPACE}ne three\n")
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].line == 3
    assert violations[0].column == 3


def test_multiple_violations_in_one_file_are_all_reported(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", f"{_BOM}one{_ZERO_WIDTH_SPACE}two\n")
    violations = gate.find_violations(root)
    assert len(violations) == 2


def test_violations_across_multiple_files_are_all_reported(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", f"{_BOM}\n")
    _write(root, "b.md", f"{_ZERO_WIDTH_SPACE}\n")
    violations = gate.find_violations(root)
    assert sorted(v.path for v in violations) == ["a.md", "b.md"]


# --- must not fire -----------------------------------------------------


def test_escape_sequence_spelling_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """The fix this gate steers authors toward -- the literal six ASCII
    characters `\\ufeff` inside a normal string -- must never itself be
    graded as a violation."""
    root = _repo(tmp_path)
    _write(root, "a.py", 'text = (text or "").lstrip("\\ufeff")\n')
    assert gate.find_violations(root) == []


def test_ordinary_ascii_text_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", "# Title\n\nOrdinary body text with no surprises.\n")
    assert gate.find_violations(root) == []


def test_ordinary_non_ascii_text_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """A non-ASCII character outside the fixed hidden-character set (here,
    Japanese text) must not be flagged -- this gate targets invisible
    characters, not non-ASCII content in general."""
    root = _repo(tmp_path)
    _write(root, "a.md", "\u65e5\u672c\u8a9e\u306e\u672c\u6587\n")
    assert gate.find_violations(root) == []


def test_untracked_files_are_not_scanned(tmp_path: pathlib.Path) -> None:
    """Regression: a filesystem walk would grade apm's deploy trees and the
    repo's own `.claude/worktrees/` checkouts -- content that is not this
    diff's. Reading tracked files excludes every ignored path by
    construction."""
    root = _repo(tmp_path)
    _write(root, "a.md", "clean\n")
    for untracked in (
        ".claude/worktrees/task-1/dirty.md",
        ".claude/hooks/superpowers/dirty.md",
        "apm_modules/obra/superpowers/dirty.md",
    ):
        _write(root, untracked, f"{_BOM}\n", track=False)
    assert gate.find_violations(root) == []


# --- fail closed (exit 2) ------------------------------------------------


def test_discovering_nothing_is_an_error_not_a_pass(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression: reporting success having checked nothing would make this
    a permanent green no-op after a wrong scan root."""
    root = _repo(tmp_path)
    assert gate.main(["--root", str(root)]) == 2
    assert "checking nothing" in capsys.readouterr().err


def test_non_utf8_file_fails_closed_naming_the_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    path = _write(root, "a.md", "clean\n")
    path.write_bytes(b"\xff\xfe not valid utf-8")
    subprocess.run(["git", "-C", str(root), "add", "--", "a.md"], check=True)
    assert gate.main(["--root", str(root)]) == 2
    stderr = capsys.readouterr().err
    assert "a.md" in stderr
    assert "cannot be read as UTF-8" in stderr


def test_a_non_repository_root_fails_closed(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "git ls-files failed" in capsys.readouterr().err


def test_git_missing_entirely_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """No git on PATH must not surface as a raw traceback."""

    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(gate.subprocess, "run", _no_git)
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "cannot run git" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does-not-exist"
    assert gate.main(["--root", str(missing)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_is_a_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    a_file = tmp_path / "not-a-directory"
    a_file.write_text("x", encoding="utf-8")
    assert gate.main(["--root", str(a_file)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


# --- CLI -------------------------------------------------------------------


def test_main_returns_zero_on_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(REPO_ROOT)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_returns_one_and_explains_the_failure(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    _write(root, "a.md", f"{_BOM}\n")
    assert gate.main(["--root", str(root)]) == 1
    stderr = capsys.readouterr().err
    assert "U+FEFF" in stderr
    assert "ZERO WIDTH NO-BREAK SPACE" in stderr
    assert "a.md:1:1" in stderr
    assert "#702" in stderr


def test_failure_output_never_echoes_the_offending_character_itself(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression class named directly in this gate's own docstring: a
    hidden character echoed into a CI log is exactly as invisible there as
    it was in the source. Every reported violation must describe the
    character, never reproduce it."""
    root = _repo(tmp_path)
    _write(root, "a.md", f"{_BOM}{_ZERO_WIDTH_SPACE}{_RTL_OVERRIDE}{_WORD_JOINER}\n")
    gate.main(["--root", str(root)])
    stderr = capsys.readouterr().err
    for hidden in (_BOM, _ZERO_WIDTH_SPACE, _RTL_OVERRIDE, _WORD_JOINER):
        assert hidden not in stderr


# --- Violation helper methods -----------------------------------------


def test_codepoint_label_formats_as_u_plus_four_hex_digits() -> None:
    violation = gate.Violation(path="a.md", line=1, column=1, codepoint=0xFEFF)
    assert violation.codepoint_label() == "U+FEFF"


def test_codepoint_name_resolves_the_formal_unicode_name() -> None:
    violation = gate.Violation(path="a.md", line=1, column=1, codepoint=0x200B)
    assert violation.codepoint_name() == "ZERO WIDTH SPACE"


# --- GateHiddenCharactersArgs validation --------------------------------


def test_args_reject_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateHiddenCharactersArgs(root=tmp_path / "does-not-exist")

"""Tests for the real-checkout-git-write gate
(.github/scripts/gitapex_gate_real_checkout_git_write.py).

Issue #991. `test_installs_the_prek_hook_for_a_real_checkout` ran the
session-start hook against this repository's own real checkout -- a
REPO_ROOT-rooted path continuing into a literal `.git/hooks/pre-commit`
segment -- so `prek install` rewrote that real checkout's own
`.git/hooks/pre-commit` mtime unconditionally on every test run -- a
write no pytest-xdist worker owns, surviving the test run on a real
checkout. Task 1 of this same branch pointed that one test at a
throwaway clone; this gate exists so the same hazard shape cannot
silently return in some *other* test file.

Every hazard fixture below is built from separately-assigned pieces
(a REPO_ROOT-token piece, a `.git`-segment piece) joined only through an
f-string's variable interpolation, never as a single literal source line
in this file that itself spells the REPO_ROOT token followed by a
`/`-chained `.git` segment -- this file is itself a pytest-discovered
test file under `tests/`, and this task's own Step 3 runs the real gate
against this repository's real, current tree end to end. Writing the
hazard shape directly into this file's own source (fixture code *or*
prose describing it) would make this file flag itself, the same
self-reference trap test_gitapex_gate_hidden_characters.py's own module
docstring names ("never a literal hidden character typed into this file
-- that would be exactly the mistake this gate exists to catch,
reproduced in its own test suite").
"""

from __future__ import annotations

import pathlib

import gitapex_gate_real_checkout_git_write as gate
import pytest


def _repo(tmp_path: pathlib.Path, *, testpaths: list[str] | None = None) -> pathlib.Path:
    """A tmp_path-scoped fake repository root: just enough for this
    gate's own discovery to work -- a pyproject.toml declaring
    testpaths (mirrors pyproject.toml:330's own real list shape; this
    fixture defaults to ["tests"], the real list's own first entry)."""
    paths = testpaths if testpaths is not None else ["tests"]
    testpaths_toml = ", ".join(f'"{p}"' for p in paths)
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.pytest.ini_options]\ntestpaths = [{testpaths_toml}]\n", encoding="utf-8"
    )
    return tmp_path


def _write_module(root: pathlib.Path, relative: str, lines: list[str]) -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _hazard_expression(*, waiver_reason: str | None = None) -> str:
    """One line of Python source containing the exact hazard shape (a
    REPO_ROOT-rooted path continuing into `.git/hooks/pre-commit`),
    optionally with a trailing inline waiver comment carrying
    `waiver_reason`.

    `root_token` and `git_segment` are assigned on their own lines and
    joined only inside an f-string, so the *source line building this
    string* never itself contains the REPO_ROOT token immediately
    followed by a quoted `.git` segment -- see this module's own
    docstring for why that self-reference avoidance matters here
    specifically.
    """
    root_token = "REPO_ROOT"
    git_segment = '"' + ".git" + '"'
    line = f'pre_commit_hook = {root_token} / {git_segment} / "hooks" / "pre-commit"'
    if waiver_reason is not None:
        marker = "#" + " real-checkout-git-write: WAIVED: " + waiver_reason
        line = f"{line}  {marker}"
    return line


def _spoofed_waiver_line() -> str:
    """The hazard pattern plus a second, semicolon-joined statement on
    the same physical line whose *string value* looks like a waiver
    comment but is not one -- no real `#` precedes it in the token
    stream, so `tokenize` sees a STRING token there, never a COMMENT
    token. Proves the gate's waiver check is matched only against real
    comment tokens, never a raw substring search a quoted string could
    spoof.
    """
    hazard = _hazard_expression()
    spoofed_marker = "#" + " real-checkout-git-write: WAIVED: spoofed, not a real comment"
    return f'{hazard}; _spoof = "{spoofed_marker}"'


# --- hazard detection ------------------------------------------------------


def test_hazard_pattern_is_reported_and_main_returns_one(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write_module(
        root,
        "tests/test_example.py",
        [
            "import pathlib",
            "",
            "REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]",
            "",
            _hazard_expression(),
        ],
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].path == "tests/test_example.py"
    assert violations[0].line == 5
    assert gate.main(["--root", str(root)]) == 1


def test_waived_line_is_not_reported_and_main_returns_zero(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    _write_module(
        root,
        "tests/test_example.py",
        [
            "import pathlib",
            "",
            "REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]",
            "",
            _hazard_expression(waiver_reason="legitimate read-only prek-hook assertion, see issue #991"),
        ],
    )
    assert gate.find_violations(root) == []
    assert gate.main(["--root", str(root)]) == 0
    # Every honoured waiver still prints to stderr -- never a silent bypass.
    assert "waived" in capsys.readouterr().err.lower()


def test_waiver_with_empty_reason_still_counts_as_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    hazard_line = _hazard_expression()
    empty_reason_marker = "#" + " real-checkout-git-write: WAIVED:   "
    _write_module(
        root,
        "tests/test_example.py",
        [
            "import pathlib",
            "",
            "REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]",
            "",
            f"{hazard_line}  {empty_reason_marker}",
        ],
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert gate.main(["--root", str(root)]) == 1


def test_waiver_text_inside_a_string_literal_is_still_reported(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write_module(
        root,
        "tests/test_example.py",
        [
            "import pathlib",
            "",
            "REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]",
            "",
            _spoofed_waiver_line(),
        ],
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert gate.main(["--root", str(root)]) == 1


def test_clean_file_with_no_hazard_pattern_is_clean(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write_module(
        root,
        "tests/test_example.py",
        [
            "import pathlib",
            "",
            "REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]",
            "",
            'CONFIG = REPO_ROOT / "pyproject.toml"',
        ],
    )
    assert gate.find_violations(root) == []
    assert gate.main(["--root", str(root)]) == 0


def test_main_returns_two_on_a_root_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does-not-exist"
    assert gate.main(["--root", str(missing)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_read_only_reference_is_still_flagged_no_read_write_disambiguation(tmp_path: pathlib.Path) -> None:
    """The pre-Task-1 shape of `test_installs_the_prek_hook_for_a_real_checkout`:
    a hazard line immediately followed by `.exists()`/`.read_text(...)` in
    the surrounding statement. This gate does not attempt read/write
    call-shape disambiguation at all -- assert that explicitly so a future
    edit narrowing the scope to "only flag writes" is caught as a behavior
    change, not silently accepted. A waiver comment is the intended,
    documented escape hatch for a legitimate read-only need like this one,
    not a smarter heuristic."""
    root = _repo(tmp_path)
    _write_module(
        root,
        "tests/test_example.py",
        [
            "import pathlib",
            "",
            "REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]",
            "",
            "def test_installs_the_prek_hook_for_a_real_checkout() -> None:",
            f"    {_hazard_expression()}",
            "    assert pre_commit_hook.exists()",
            '    assert "prek" in pre_commit_hook.read_text(encoding="utf-8")',
        ],
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert gate.main(["--root", str(root)]) == 1

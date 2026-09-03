"""Tests for the unguarded-shell-pipe-in-docs gate
(.github/scripts/gitapex_gate_unguarded_shell_pipe_in_docs.py).

Issue #1531 (refs #1567, gate-proposal-umbrella: local-hook fail-open
remediation). The documented invocation `git log ... | python3
gitapex_check_task_commit_provenance.py` piped two commands directly
together, silently masking an upstream `git log` failure. This gate exists
so a future documented recipe cannot reintroduce the same shape
undetected.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_unguarded_shell_pipe_in_docs as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
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


def test_repository_has_no_unguarded_shell_pipe_violations() -> None:
    """The real checkout passes clean -- every real pre-existing instance
    this gate's own authoring found was fixed (a pipefail disclosure added)
    in the same change that adds this gate, matching
    gitapex_gate_no_raw_gh_cli_in_docs.py's own historical-grandfathering
    precedent."""
    assert gate.find_violations(REPO_ROOT) == []


def test_repository_scan_reaches_a_real_tracked_set() -> None:
    """Without this, a discovery bug that found nothing would make the test
    above pass for the wrong reason."""
    assert len(gate.discover_markdown(REPO_ROOT)) > 20
    assert len(gate.discover_python(REPO_ROOT)) > 20


# --- reintroducing the original #1531 defect ------------------------------


def test_reintroducing_the_original_defect_shape_is_caught(tmp_path: pathlib.Path) -> None:
    """Test-first proof: the exact original defect shape -- a bare
    `git log ... | python3 ...` recipe with no pipefail disclosure -- is
    caught when reintroduced into a checker script's own module docstring,
    the same shape issue #1531 itself reports against
    gitapex_check_task_commit_provenance.py."""
    root = _repo(tmp_path)
    _write(
        root,
        "hooks/gitapex_check_example.py",
        '"""Usage -- piped directly together for convenience::\n\n'
        "    git log --format=%B -z BASE..HEAD | python3 gitapex_check_example.py\n\n"
        'Exit codes:\n    0  PASS\n"""\n',
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].path == "hooks/gitapex_check_example.py"
    assert "git log" in violations[0].matched


def test_the_current_real_fixed_docstring_is_clean() -> None:
    """The real, already-fixed file the original defect names discloses
    `pipefail` elsewhere in its own module docstring, so this gate must not
    re-flag it."""
    path = REPO_ROOT / "skills/executing-a-branch-plan/scripts/gitapex_check_task_commit_provenance.py"
    text = path.read_text(encoding="utf-8")
    docstring = gate._module_docstring_with_start_line(text, path)
    assert docstring is not None
    doc, _ = docstring
    assert gate.docstring_violations_in_text(doc) == []


# --- Markdown: violations --------------------------------------------------


def test_pipe_in_a_fenced_block_with_no_pipefail_disclosure_is_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "skills/foo/SKILL.md",
        "---\nname: foo\n---\n\n## Usage\n\n```bash\ngit log --oneline | python3 check.py\n```\n",
    )
    violations = gate.find_violations(root)
    assert [v.path for v in violations] == ["skills/foo/SKILL.md"]
    assert violations[0].location == "fenced code block"


def test_tilde_fence_is_also_scanned(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "skills/foo/references/notes.md", "~~~bash\ngit log | python3 x.py\n~~~\n")
    assert len(gate.find_violations(root)) == 1


def test_fence_nested_in_a_longer_fence_is_still_scanned(tmp_path: pathlib.Path) -> None:
    """CommonMark run-length pairing, same as the sibling gate: a three-
    backtick fence nested inside a four-backtick one does not close the
    outer block."""
    root = _repo(tmp_path)
    _write(
        root,
        "skills/foo/SKILL.md",
        "````markdown\n## Example\n\n```bash\ngit log | python3 x.py\n```\n````\n",
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].line == 5


# --- Markdown: must not fire ------------------------------------------------


def test_pipe_outside_any_fence_is_not_scanned(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "prose mentioning `git log | python3 x.py` inline, not fenced\n")
    assert gate.find_violations(root) == []


def test_markdown_table_row_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "| Situation | Skill |\n|---|---|\n| a | b |\n")
    assert gate.find_violations(root) == []


def test_python_type_hint_shape_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """The false-positive class this gate's own docstring names: a bare
    `\\S \\| \\S` match would fire on a quoted Python type hint."""
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "```python\ndef main(argv: list[str] | None = None) -> int: ...\n```\n")
    assert gate.find_violations(root) == []


def test_logical_or_double_pipe_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "```bash\ncommand1 || command2\n```\n")
    assert gate.find_violations(root) == []


def test_pipefail_disclosed_inside_the_same_fence_exempts_it(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "skills/foo/SKILL.md",
        "```bash\nset -o pipefail\ngit log --oneline | python3 check.py\n```\n",
    )
    assert gate.find_violations(root) == []


def test_allow_marker_directly_above_the_fence_exempts_it(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "skills/foo/SKILL.md",
        "<!-- gitapex-allow-unguarded-shell-pipe: illustrative only -->\n```bash\ngit log | python3 x.py\n```\n",
    )
    assert gate.find_violations(root) == []


def test_allow_marker_separated_by_a_blank_line_does_not_exempt(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "skills/foo/SKILL.md",
        "<!-- gitapex-allow-unguarded-shell-pipe: reason -->\n\n```bash\ngit log | python3 x.py\n```\n",
    )
    assert len(gate.find_violations(root)) == 1


def test_malformed_allow_marker_with_no_reason_does_not_exempt(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "skills/foo/SKILL.md",
        "<!-- gitapex-allow-unguarded-shell-pipe: -->\n```bash\ngit log | python3 x.py\n```\n",
    )
    assert len(gate.find_violations(root)) == 1


def test_untracked_markdown_file_is_not_scanned(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "clean\n")
    _write(root, "skills/foo/references/dirty.md", "```bash\ngit log | python3 x.py\n```\n", track=False)
    assert gate.find_violations(root) == []


def test_non_reference_markdown_under_skills_is_not_scanned(tmp_path: pathlib.Path) -> None:
    """Scope is skills/*/SKILL.md and skills/*/references/*.md only -- a
    stray markdown file elsewhere under a skill directory is out of scope."""
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "clean\n")
    _write(root, "skills/foo/notes/extra.md", "```bash\ngit log | python3 x.py\n```\n")
    _write(root, "docs/plan.md", "```bash\ngit log | python3 x.py\n```\n")
    assert gate.find_violations(root) == []


# --- Python docstrings: violations -----------------------------------------


def test_standalone_recipe_line_in_module_docstring_is_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        ".github/scripts/gitapex_gate_example.py",
        '"""Usage::\n\n    git diff --name-only BASE HEAD | python3 gitapex_gate_example.py\n"""\n',
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].location == "module docstring"
    assert violations[0].line == 3


def test_violation_reports_the_real_file_line_not_a_docstring_relative_one(tmp_path: pathlib.Path) -> None:
    """The reported line is the absolute file line, computed from the
    docstring AST node's own `lineno` -- not an offset relative to the
    (possibly dedented) docstring text alone."""
    root = _repo(tmp_path)
    _write(
        root,
        "hooks/gitapex_check_padded.py",
        "#!/usr/bin/env python3\n"
        '"""One line of preamble before the recipe.\n\n'
        "    git diff --name-only BASE HEAD | python3 gitapex_check_padded.py\n"
        '"""\n',
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].line == 4


# --- Python docstrings: must not fire --------------------------------------


def test_backtick_quoted_inline_example_in_a_docstring_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """The false-positive class this gate's own docstring names: a
    backtick-quoted illustrative warning, not a standalone recipe."""
    root = _repo(tmp_path)
    _write(
        root,
        "hooks/gitapex_check_example.py",
        '"""Never invoke as `git log ... | python3 x.py` in an ordinary shell.\n"""\n',
    )
    assert gate.find_violations(root) == []


def test_double_backtick_quoted_inline_example_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "hooks/gitapex_check_example.py", '"""See ``git show <sha>:<path> | wc -l`` for comparison.\n"""\n')
    assert gate.find_violations(root) == []


def test_pipefail_disclosed_anywhere_in_the_docstring_exempts_the_whole_file(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "hooks/gitapex_check_example.py",
        '"""Usage::\n\n    git diff --name-only BASE HEAD | python3 gitapex_check_example.py\n\n'
        'Never invoke this as a bare pipe in a non-pipefail shell.\n"""\n',
    )
    assert gate.find_violations(root) == []


def test_allow_marker_directly_above_the_flagged_line_exempts_it(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "hooks/gitapex_check_example.py",
        '"""Usage::\n\n<!-- gitapex-allow-unguarded-shell-pipe: illustrative only -->\n'
        '    git diff --name-only BASE HEAD | python3 gitapex_check_example.py\n"""\n',
    )
    assert gate.find_violations(root) == []


def test_no_module_docstring_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "hooks/gitapex_check_example.py", "import sys\nsys.exit(0)\n")
    assert gate.find_violations(root) == []


def test_empty_python_file_has_no_module_docstring(tmp_path: pathlib.Path) -> None:
    """An empty file has no statements at all -- `tree.body` is empty, a
    distinct case from a file whose first statement merely isn't a
    docstring."""
    root = _repo(tmp_path)
    text = ""
    assert gate._module_docstring_with_start_line(text, pathlib.Path("empty.py")) is None
    _write(root, "hooks/gitapex_check_empty.py", text)
    assert gate.find_violations(root) == []


def test_non_string_first_statement_has_no_module_docstring(tmp_path: pathlib.Path) -> None:
    """The first statement can be a bare expression that is not a string
    constant (here, a bare integer literal) -- distinct from `import sys`
    (not an `Expr` at all) and from a real docstring (an `Expr` wrapping a
    string `Constant`)."""
    root = _repo(tmp_path)
    text = "42\n"
    assert gate._module_docstring_with_start_line(text, pathlib.Path("x.py")) is None
    _write(root, "hooks/gitapex_check_non_string_first.py", text)
    assert gate.find_violations(root) == []


def test_python_file_outside_the_checker_gate_scope_is_not_scanned(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "hooks/gitapex_check_example.py", '"""ok\n"""\n')
    _write(
        root,
        "src/not_in_scope.py",
        '"""Usage::\n\n    git diff --name-only BASE HEAD | python3 not_in_scope.py\n"""\n',
    )
    assert gate.find_violations(root) == []


def test_non_gh_style_consumer_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """A pipe with no recognized consumer token on the right is not flagged
    -- this gate requires a real shell-consumer vocabulary match, not a bare
    pipe character."""
    root = _repo(tmp_path)
    _write(
        root,
        "hooks/gitapex_check_example.py",
        '"""Usage::\n\n    some_value | not_a_real_consumer_tool\n"""\n',
    )
    assert gate.find_violations(root) == []


# --- fail closed (exit 2) ------------------------------------------------


def test_discovering_nothing_in_either_category_is_an_error_not_a_pass(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    assert gate.main(["--root", str(root)]) == 2
    assert "checking nothing" in capsys.readouterr().err


def test_non_utf8_markdown_file_fails_closed_naming_the_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    path = _write(root, "skills/foo/SKILL.md", "clean\n")
    path.write_bytes(b"\xff\xfe not valid utf-8")
    subprocess.run(["git", "-C", str(root), "add", "--", "skills/foo/SKILL.md"], check=True)
    assert gate.main(["--root", str(root)]) == 2
    stderr = capsys.readouterr().err
    assert "skills/foo/SKILL.md" in stderr
    assert "cannot be read as UTF-8" in stderr


def test_invalid_python_syntax_fails_closed_naming_the_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    _write(root, "hooks/gitapex_check_broken.py", "def f(:\n    pass\n")
    assert gate.main(["--root", str(root)]) == 2
    stderr = capsys.readouterr().err
    assert "gitapex_check_broken.py" in stderr
    assert "cannot be parsed as Python" in stderr


def test_a_non_repository_root_fails_closed(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "git ls-files failed" in capsys.readouterr().err


def test_git_missing_entirely_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(gate.subprocess, "run", _no_git)
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "cannot run git" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_does_not_exist(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
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


def test_main_returns_one_and_explains_the_failure(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "```bash\ngit log | python3 x.py\n```\n")
    assert gate.main(["--root", str(root)]) == 1
    stderr = capsys.readouterr().err
    assert "skills/foo/SKILL.md:2" in stderr
    assert "gitapex-allow-unguarded-shell-pipe" in stderr
    assert "#1531" in stderr


# --- GateUnguardedShellPipeInDocsArgs validation --------------------------


def test_args_reject_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateUnguardedShellPipeInDocsArgs(root=tmp_path / "does-not-exist")


def test_args_root_must_exist_accepts_a_real_directory(tmp_path: pathlib.Path) -> None:
    """Calls `_root_must_exist` directly on both its accepting and its
    rejecting path, not only through the constructor above."""
    assert gate.GateUnguardedShellPipeInDocsArgs._root_must_exist(tmp_path) == tmp_path
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateUnguardedShellPipeInDocsArgs._root_must_exist(tmp_path / "does-not-exist")


# --- internal helpers, called directly ------------------------------------


def test_violation_describe_names_the_path_line_and_location() -> None:
    violation = gate.Violation(
        path="skills/foo/SKILL.md", line=7, matched="git log | python3 x.py", location="fenced code block"
    )
    described = violation.describe()
    assert "skills/foo/SKILL.md:7" in described
    assert "fenced code block" in described
    assert "git log | python3 x.py" in described


def test_markdown_violations_in_text_called_directly(tmp_path: pathlib.Path) -> None:
    text = "```bash\ngit log | python3 x.py\n```\n"
    assert gate.markdown_violations_in_text(text) == [(2, "git log | python3 x.py")]


def test_violations_in_markdown_file_called_directly(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    path = _write(root, "skills/foo/SKILL.md", "```bash\ngit log | python3 x.py\n```\n")
    violations = gate.violations_in_markdown_file(path, root)
    assert [v.path for v in violations] == ["skills/foo/SKILL.md"]


def test_violations_in_python_file_called_directly(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    path = _write(
        root,
        "hooks/gitapex_check_direct.py",
        '"""Usage::\n\n    git diff --name-only BASE HEAD | python3 gitapex_check_direct.py\n"""\n',
    )
    violations = gate.violations_in_python_file(path, root)
    assert len(violations) == 1
    assert violations[0].location == "module docstring"


def test_tracked_files_called_directly(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "skills/foo/SKILL.md", "clean\n")
    found = gate._tracked_files(root, ("skills/*/SKILL.md",))
    assert [p.relative_to(root).as_posix() for p in found] == ["skills/foo/SKILL.md"]


def test_read_text_called_directly(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("hello\n", encoding="utf-8")
    assert gate._read_text(path) == "hello\n"

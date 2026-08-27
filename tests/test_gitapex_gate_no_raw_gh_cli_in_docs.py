"""Tests for the no-raw-gh-CLI-in-docs gate
(.github/scripts/gitapex_gate_no_raw_gh_cli_in_docs.py).

Issue #529 (refs #205 Repairs 5 & 8, retrospective for PR #204). An
implementation plan document instructed a raw `gh pr view` CLI invocation,
contradicting CLAUDE.md's "Do not invoke command-line GitHub tools
directly." The violation was caught only by two rounds of manual
self-review. This gate exists so author attention is no longer the only
thing standing between a raw `gh` CLI invocation and a merged doc.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_no_raw_gh_cli_in_docs as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


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


def test_repository_has_no_raw_gh_cli_invocations() -> None:
    """The real checkout passes -- the 3 pre-existing violations in
    docs/superpowers/plans/2026-07-14-toolchain-foundation.md (a historical
    plan predating this gate) were each given the exception marker in the
    same change that adds this gate."""
    assert gate.find_violations(REPO_ROOT) == []


def test_repository_scan_reaches_a_real_tracked_set() -> None:
    """Without this, a discovery bug that found nothing would make the test
    above pass for the wrong reason."""
    discovered = gate.discover(REPO_ROOT)
    assert len(discovered) > 50
    relatives = {p.relative_to(REPO_ROOT).as_posix() for p in discovered}
    assert "docs/superpowers/plans/2026-07-14-toolchain-foundation.md" in relatives


# --- violations ------------------------------------------------------------


def test_raw_gh_pr_invocation_in_a_fenced_block_is_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "```bash\ngh pr view 123\n```\n")
    violations = gate.find_violations(root)
    assert [v.path for v in violations] == ["docs/plan.md"]
    assert violations[0].line == 2
    assert violations[0].matched == "gh pr"


def test_raw_gh_run_invocation_via_command_substitution_is_a_violation(tmp_path: pathlib.Path) -> None:
    """The real historical shape this gate was written to catch:
    `run_id=$(gh run list ...)` -- `gh` immediately follows a `(`, not
    whitespace or line-start."""
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "```bash\nrun_id=$(gh run list --limit 1 --json databaseId)\n```\n")
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].matched == "gh run"


def test_tilde_fence_is_also_scanned(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "~~~bash\ngh issue create --title x\n~~~\n")
    assert len(gate.find_violations(root)) == 1


def test_multiple_violations_across_files_are_all_reported(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/a.md", "```bash\ngh pr merge 1\n```\n")
    _write(root, "docs/b.md", "```bash\ngh issue close 2\n```\n")
    violations = gate.find_violations(root)
    assert sorted(v.path for v in violations) == ["docs/a.md", "docs/b.md"]


def test_fence_nested_in_a_longer_fence_is_still_scanned(tmp_path: pathlib.Path) -> None:
    """Audit finding (issue #529 gate review). The original
    `stripped.startswith("```")` fence toggle closed a four-backtick fence
    on the first three-backtick line nested inside it, so every line of the
    nested block fell outside every computed range and was never scanned --
    a raw `gh pr view` there passed the gate silently. The shape is not
    hypothetical: docs/superpowers/plans/2026-07-13-evaluating-skill-quality-shape-script.md
    already wraps a ```` ```markdown ```` example around an inner fence
    today. CommonMark closes a fence only on a bare run of the same marker
    character at least as long as the opening run."""
    root = _repo(tmp_path)
    _write(
        root,
        "docs/plan.md",
        "Write this into the reference file:\n\n"
        "````markdown\n## Example\n\n```bash\ngh pr view 123\n```\n````\n\nDone.\n",
    )
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].line == 7
    assert violations[0].matched == "gh pr"


def test_a_longer_closing_run_still_closes_the_fence(tmp_path: pathlib.Path) -> None:
    """The other half of CommonMark's run-length rule: a closing run longer
    than the opening one does close the block, so text after it is prose
    again and must not be scanned."""
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "```bash\necho x\n````\n\ngh pr view 123 (prose, not a code block)\n")
    assert gate.find_violations(root) == []


def test_unclosed_fence_extends_to_end_of_file(tmp_path: pathlib.Path) -> None:
    """Matches GitHub's own renderer: an unclosed fence still hides -- and
    still scans -- everything after it."""
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "```bash\necho before\ngh pr create --title x\n")
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].line == 3


def test_double_quoted_invocation_is_a_violation(tmp_path: pathlib.Path) -> None:
    """Audit finding (issue #529 gate review). The original opener class
    `[\\s;&|(`]` did not include a quote, so a quoted invocation -- the
    exact quote-splitting bypass class hooks/gitapex_check_bash_safety.py
    was already live-confirmed vulnerable to before issue #1326 moved it
    off raw-text matching -- passed the gate silently."""
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", '```bash\nbash -lc "gh pr merge 123 --squash"\n```\n')
    violations = gate.find_violations(root)
    assert len(violations) == 1
    assert violations[0].matched == "gh pr"


def test_invocation_inside_a_json_string_is_a_violation(tmp_path: pathlib.Path) -> None:
    """Same root cause as the quoted-shell case, in the shape a plan
    document is most likely to carry it: a tool-call payload."""
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", '```json\n{"tool": "Bash", "command": "gh issue close 42"}\n```\n')
    assert len(gate.find_violations(root)) == 1


def test_path_prefixed_invocation_is_a_violation(tmp_path: pathlib.Path) -> None:
    """A `/` was not in the original opener class either."""
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "```bash\n/usr/bin/gh pr merge 123\n```\n")
    assert len(gate.find_violations(root)) == 1


def test_gh_discussion_and_agent_task_are_in_the_subcommand_vocabulary(tmp_path: pathlib.Path) -> None:
    """Audit finding (issue #529 gate review). `_GH_SUBCOMMANDS` was stale
    against gh's own published manual (https://cli.github.com/manual/):
    `agent-task`, `copilot`, `discussion`, `licenses`, `skill` and `help`
    all ship today and were all absent, so a documented `gh discussion
    create` in a fenced block was not an invocation as far as the gate was
    concerned."""
    root = _repo(tmp_path)
    _write(root, "docs/a.md", '```bash\ngh discussion create --title "x"\n```\n')
    _write(root, "docs/b.md", '```bash\ngh agent-task create --base main -p "x"\n```\n')
    assert sorted(v.path for v in gate.find_violations(root)) == ["docs/a.md", "docs/b.md"]


# --- must not fire -----------------------------------------------------


def test_word_internal_gh_inside_a_fenced_block_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """Guard on widening the command-start test to a negative lookbehind:
    "through pr" and "high pr" end in `gh` followed by a real subcommand
    word, and neither is an invocation."""
    root = _repo(tmp_path)
    _write(
        root,
        "docs/plan.md",
        "```text\nRoute it through pr review, and rank high pr first.\nSee weigh issue counts.\n```\n",
    )
    assert gate.find_violations(root) == []


def test_indented_code_block_is_a_disclosed_unscanned_gap(tmp_path: pathlib.Path) -> None:
    """Pins a limitation this gate's own docstring discloses rather than
    claims closed: detection is fence-scoped, so a four-space-indented
    Markdown code block is not scanned. Recorded as an executable pin so
    the gap stays visible, and so any later fix has to come here and say
    so."""
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "Run:\n\n    gh pr view 123\n\nDone.\n")
    assert gate.find_violations(root) == []


def test_inline_backtick_span_discussing_gh_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """The false-positive class this gate's own docstring names: prose
    discussing the gh CLI deny-list in a single-backtick inline span, never
    inside a fenced block -- four real instances of this shape exist in
    this repository's own docs today."""
    root = _repo(tmp_path)
    _write(
        root,
        "docs/spec.md",
        "Uses platform-integrated tool calls, not `gh` CLI (per "
        "`hooks/check-bash-safety.sh`'s existing deny rule on `gh issue`/`gh pr` writes).\n",
    )
    assert gate.find_violations(root) == []


def test_gh_followed_by_a_non_subcommand_word_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    """Regression: the real line `for t in uv gh actionlint bun lychee; do
    ...` in this repository's own docs/superpowers/plans/2026-07-14-toolchain-foundation.md.
    `actionlint` is not a gh CLI subcommand, so this must not be flagged."""
    root = _repo(tmp_path)
    _write(
        root,
        "docs/plan.md",
        '```bash\nfor t in uv gh actionlint bun lychee; do echo -n "$t "; $t --version; done\n```\n',
    )
    assert gate.find_violations(root) == []


def test_exception_marker_directly_above_the_fence_exempts_it(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "docs/plan.md",
        "<!-- gitapex-allow-raw-gh-cli: historical, predates the gate (#529) -->\n```bash\ngh pr view 123\n```\n",
    )
    assert gate.find_violations(root) == []


def test_exception_marker_separated_by_a_blank_line_does_not_exempt(tmp_path: pathlib.Path) -> None:
    """The marker must sit directly on the line before the fence -- a blank
    line in between is not close enough, matching this gate's own stated
    "no blank line in between" rule rather than a looser nearest-marker
    search."""
    root = _repo(tmp_path)
    _write(
        root,
        "docs/plan.md",
        "<!-- gitapex-allow-raw-gh-cli: historical (#529) -->\n\n```bash\ngh pr view 123\n```\n",
    )
    assert len(gate.find_violations(root)) == 1


def test_malformed_exception_marker_with_no_reason_does_not_exempt(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(
        root,
        "docs/plan.md",
        "<!-- gitapex-allow-raw-gh-cli: -->\n```bash\ngh pr view 123\n```\n",
    )
    assert len(gate.find_violations(root)) == 1


def test_ordinary_prose_with_no_gh_mention_is_not_a_violation(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/plan.md", "# Title\n\nOrdinary body text, nothing through here.\n")
    assert gate.find_violations(root) == []


def test_non_docs_tracked_files_are_not_scanned(tmp_path: pathlib.Path) -> None:
    """Scope is docs/**/*.md only -- a raw gh invocation in, say, a script
    or a top-level README is out of this gate's stated scope."""
    root = _repo(tmp_path)
    _write(root, "README.md", "```bash\ngh pr view 123\n```\n")
    _write(root, "scripts/deploy.sh", "gh pr view 123\n")
    assert gate.find_violations(root) == []


def test_untracked_docs_files_are_not_scanned(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/clean.md", "clean\n")
    _write(root, "docs/dirty.md", "```bash\ngh pr view 123\n```\n", track=False)
    assert gate.find_violations(root) == []


# --- fail closed (exit 2) ------------------------------------------------


def test_discovering_nothing_is_an_error_not_a_pass(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Regression: reporting success having checked nothing would make this
    a permanent green no-op after a wrong scan root (e.g. no docs/ dir)."""
    root = _repo(tmp_path)
    assert gate.main(["--root", str(root)]) == 2
    assert "checking nothing" in capsys.readouterr().err


def test_non_utf8_file_fails_closed_naming_the_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path)
    path = _write(root, "docs/a.md", "clean\n")
    path.write_bytes(b"\xff\xfe not valid utf-8")
    subprocess.run(["git", "-C", str(root), "add", "--", "docs/a.md"], check=True)
    assert gate.main(["--root", str(root)]) == 2
    stderr = capsys.readouterr().err
    assert "docs/a.md" in stderr
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
    _write(root, "docs/plan.md", "```bash\ngh pr view 123\n```\n")
    assert gate.main(["--root", str(root)]) == 1
    stderr = capsys.readouterr().err
    assert "docs/plan.md:2" in stderr
    assert "gh pr" in stderr
    assert "gitapex-allow-raw-gh-cli" in stderr
    assert "#529" in stderr


# --- GateNoRawGhCliInDocsArgs validation --------------------------------


def test_args_reject_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateNoRawGhCliInDocsArgs(root=tmp_path / "does-not-exist")

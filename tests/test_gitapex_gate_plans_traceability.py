"""Unit tests for `.github/scripts/gitapex_gate_plans_traceability.py`.

Issue #1796 (ACM row 6). Covers, per the branch plan's own proof method:

- a well-formed docs/gitapex/plans/*.md file passes;
- a file missing the Issue URL line fails;
- a file missing every `Source ACM rows?:` citation fails;
- empty/malformed input fails closed, never a silent pass;
- the diff-scoping behavior itself -- this gate's own defeat test, proving
  it cannot be fooled by the corpus's own known-bad legacy files (a
  pre-existing malformed file NOT touched by the diff must not fail the
  check even though it would fail an unscoped whole-corpus scan); and
- two adversarial/defeat-style probes against the citation-matching logic
  itself (a fenced-code-block decoy, and a mid-sentence quoted-text decoy
  mirroring this very issue's own plan file's "Pre-existing-corpus note"
  paragraph) -- both live-verified to fail (be correctly rejected), not
  assumed.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import gitapex_gate_plans_traceability as gate  # noqa: E402

WELL_FORMED = """# Branch Plan: sample

Issue: https://github.com/tvna/gitapex/issues/1796
Base: main

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Sample criterion | Sample interpretation | Sample ops | Sample proof | Sample risk |

## Task Decomposition

### Task 1: Sample task

Source ACM row: row 1 ("Sample criterion").

Files: sample.py.
"""


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _write(repo: pathlib.Path, relative: str, content: str) -> pathlib.Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _commit(repo: pathlib.Path, message: str = "change") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@e")
    _git(tmp_path, "config", "user.name", "t")
    _write(tmp_path, "README.md", "seed\n")
    _commit(tmp_path, "base")
    return tmp_path


# ---------------------------------------------------------------------------
# find_missing_traceability: the core existence check, exercised directly.
# ---------------------------------------------------------------------------


def test_well_formed_file_has_no_missing_traceability() -> None:
    assert gate.find_missing_traceability(WELL_FORMED) == []


def test_missing_issue_url_line_fails() -> None:
    content = WELL_FORMED.replace("Issue: https://github.com/tvna/gitapex/issues/1796\n", "")
    assert gate.find_missing_traceability(content) == ["issue-url"]


def test_bare_issue_number_without_full_url_still_fails() -> None:
    # Mirrors a real pre-existing file in this repository's own corpus
    # (docs/gitapex/plans/2026-09-06-claude-review-persona-call-site-1879.md),
    # which uses "Issue: #1879" instead of a full URL.
    content = WELL_FORMED.replace("Issue: https://github.com/tvna/gitapex/issues/1796", "Issue: #1879")
    assert gate.find_missing_traceability(content) == ["issue-url"]


def test_missing_source_acm_rows_citation_fails() -> None:
    content = WELL_FORMED.replace('Source ACM row: row 1 ("Sample criterion").\n', "")
    assert gate.find_missing_traceability(content) == ["source-acm-rows"]


def test_source_acm_rows_plural_form_is_accepted() -> None:
    content = WELL_FORMED.replace(
        'Source ACM row: row 1 ("Sample criterion").',
        "Source ACM rows: all rows above.",
    )
    assert gate.find_missing_traceability(content) == []


@pytest.mark.parametrize("content", [None, "", "   \n\t\n"])
def test_empty_or_none_content_fails_closed_on_both_labels(content: str | None) -> None:
    assert sorted(gate.find_missing_traceability(content)) == ["issue-url", "source-acm-rows"]


# ---------------------------------------------------------------------------
# Adversarial/defeat-style probes against the citation-matching logic
# itself, not merely its happy path.
# ---------------------------------------------------------------------------


def test_defeat_fenced_code_block_citation_is_not_counted_as_genuine() -> None:
    """A `Source ACM rows:`-shaped line that appears only inside a fenced
    code block (e.g. a documentation example quoting the required shape)
    must not satisfy the check -- it is not a real per-task citation."""
    content = (
        WELL_FORMED.replace('Source ACM row: row 1 ("Sample criterion").\n', "")
        + "```\nSource ACM rows: this is only a documentation example, not a real citation\n```\n"
    )
    assert gate.find_missing_traceability(content) == ["source-acm-rows"]


def test_defeat_mid_sentence_quoted_reference_is_not_counted_as_genuine() -> None:
    """Mirrors this very issue's own plan file
    (docs/gitapex/plans/2026-09-09-claude-gitapex-merge-pipeline-control-fsus87-row6.md),
    whose "Pre-existing-corpus note" paragraph names `Source ACM rows?:` in
    running prose while describing this gate's own design, not as a real
    citation for any task. That real, naturally-occurring decoy already
    exists in this repository and correctly does not satisfy the check,
    live-verified here rather than assumed."""
    content = (
        WELL_FORMED.replace('Source ACM row: row 1 ("Sample criterion").\n', "")
        + "Pre-existing-corpus note: 11 lack any `Source ACM rows?:` citation.\n"
    )
    assert gate.find_missing_traceability(content) == ["source-acm-rows"]


def test_defeat_fenced_code_block_issue_url_is_not_counted_as_genuine() -> None:
    content = (
        WELL_FORMED.replace("Issue: https://github.com/tvna/gitapex/issues/1796\n", "")
        + "```\nIssue: https://github.com/tvna/gitapex/issues/9999\n```\n"
    )
    assert gate.find_missing_traceability(content) == ["issue-url"]


# ---------------------------------------------------------------------------
# Small internal helpers, exercised directly.
# ---------------------------------------------------------------------------


def test_normalize_converts_crlf_and_none_to_lf_and_empty_string() -> None:
    assert gate._normalize("a\r\nb\rc") == "a\nb\nc"
    assert gate._normalize(None) == ""


def test_strip_fenced_code_blocks_removes_a_terminated_block_only() -> None:
    content = "before\n```\nSource ACM rows: fake\n```\nafter\n"
    stripped = gate._strip_fenced_code_blocks(content)
    assert "fake" not in stripped
    assert "before" in stripped and "after" in stripped


def test_is_blank_true_for_whitespace_only_false_for_real_ref() -> None:
    assert gate._is_blank("   \t") is True
    assert gate._is_blank("") is True
    assert gate._is_blank("main") is False


def test_added_or_modified_drops_deletions_and_identical_renames() -> None:
    text = "A\tdocs/gitapex/plans/new.md\nD\tdocs/gitapex/plans/gone.md\nR100\told.md\tnew2.md\nM\tdocs/gitapex/plans/edit.md\n"
    lines = gate._added_or_modified(text)
    assert lines == ["A\tdocs/gitapex/plans/new.md", "M\tdocs/gitapex/plans/edit.md"]


def test_parse_name_status_line_plain_add() -> None:
    assert gate._parse_name_status_line("A\tdocs/gitapex/plans/x.md") == (
        "A",
        "docs/gitapex/plans/x.md",
        "docs/gitapex/plans/x.md",
    )


def test_parse_name_status_line_rename_uses_destination_path() -> None:
    assert gate._parse_name_status_line("R087\told.md\tnew.md") == ("R087", "old.md", "new.md")


def test_parse_name_status_line_malformed_raises_gate_error() -> None:
    with pytest.raises(gate.GateError, match="unparseable"):
        gate._parse_name_status_line("not-a-real-line")


def test_parse_name_status_line_rename_without_destination_raises() -> None:
    with pytest.raises(gate.GateError, match="rename line carries no destination"):
        gate._parse_name_status_line("R100\told.md")


# ---------------------------------------------------------------------------
# check_diff / _diff_plan_files / _git_show: real git fixtures, mirroring
# tests/test_gitapex_compute_skill_audit_flags.py's own scratch-repo
# pattern.
# ---------------------------------------------------------------------------


def test_check_diff_passes_when_diff_touches_no_plans_file(repo: pathlib.Path) -> None:
    _write(repo, "some_other_file.md", "unrelated change\n")
    _commit(repo)
    assert gate.check_diff(repo, "HEAD~1", "HEAD") == {}


def test_check_diff_passes_for_a_well_formed_added_plans_file(repo: pathlib.Path) -> None:
    _write(repo, "docs/gitapex/plans/2026-01-01-sample.md", WELL_FORMED)
    _commit(repo)
    assert gate.check_diff(repo, "HEAD~1", "HEAD") == {}


def test_check_diff_fails_for_a_malformed_added_plans_file(repo: pathlib.Path) -> None:
    bad = WELL_FORMED.replace("Issue: https://github.com/tvna/gitapex/issues/1796\n", "")
    _write(repo, "docs/gitapex/plans/2026-01-01-sample.md", bad)
    _commit(repo)
    failures = gate.check_diff(repo, "HEAD~1", "HEAD")
    assert failures == {"docs/gitapex/plans/2026-01-01-sample.md": ["issue-url"]}


def test_check_diff_scoping_ignores_a_pre_existing_malformed_file_not_in_the_diff(
    repo: pathlib.Path,
) -> None:
    """This gate's own defeat test (the branch plan's own proof method):
    a pre-existing, already-merged docs/gitapex/plans/*.md file that is
    malformed (missing both citations, matching this repository's own
    live corpus -- 5 of 20 files lack the Issue URL, 11 lack a Source ACM
    rows citation) must NOT fail a diff that never touches it. An
    unscoped, whole-corpus check would fail here; --check-diff must not."""
    bad = "# Legacy plan\n\nNo issue URL and no ACM citation here at all.\n"
    _write(repo, "docs/gitapex/plans/2026-01-01-legacy-bad.md", bad)
    _commit(repo, "seed legacy bad file, pre-existing before the diff under test")

    # The diff under test touches an unrelated file only -- the legacy bad
    # file is untouched, present at both HEAD~1 and HEAD identically.
    _write(repo, "some_other_file.md", "unrelated change\n")
    _commit(repo, "unrelated change")

    assert gate.check_diff(repo, "HEAD~1", "HEAD") == {}

    # Sanity: the same file, if it HAD been touched by this diff, would
    # fail -- proving the previous assertion is scoping, not a blind spot
    # in find_missing_traceability itself.
    assert gate.find_missing_traceability(bad) == ["issue-url", "source-acm-rows"]


def test_check_diff_only_grades_the_file_actually_touched_not_a_sibling(
    repo: pathlib.Path,
) -> None:
    bad_sibling = "# Legacy\n\nNo citations at all.\n"
    _write(repo, "docs/gitapex/plans/2026-01-01-sibling-bad.md", bad_sibling)
    _commit(repo, "seed sibling")

    _write(repo, "docs/gitapex/plans/2026-01-02-touched-good.md", WELL_FORMED)
    _commit(repo, "add a well-formed file")

    failures = gate.check_diff(repo, "HEAD~1", "HEAD")
    assert failures == {}


def test_check_diff_excludes_a_pure_deletion(repo: pathlib.Path) -> None:
    _write(repo, "docs/gitapex/plans/2026-01-01-to-delete.md", WELL_FORMED)
    _commit(repo, "add")
    (repo / "docs/gitapex/plans/2026-01-01-to-delete.md").unlink()
    _commit(repo, "delete")
    assert gate.check_diff(repo, "HEAD~1", "HEAD") == {}


def test_check_diff_rejects_blank_refs() -> None:
    with pytest.raises(gate.GateError, match="blank"):
        gate.check_diff(REPO_ROOT, "  ", "HEAD")
    with pytest.raises(gate.GateError, match="blank"):
        gate.check_diff(REPO_ROOT, "HEAD", "")


def test_diff_plan_files_rejects_unsupported_nested_shape(repo: pathlib.Path) -> None:
    _write(repo, "docs/gitapex/plans/nested/deep.md", WELL_FORMED)
    _commit(repo, "add nested plans file")
    with pytest.raises(gate.GateError, match="unsupported docs/gitapex/plans"):
        gate._diff_plan_files(repo, "HEAD~1", "HEAD")


def test_run_git_raises_gate_error_on_nonexistent_repo_root(tmp_path: pathlib.Path) -> None:
    not_a_repo = tmp_path / "not-a-git-repo"
    not_a_repo.mkdir()
    with pytest.raises(gate.GateError, match="failed"):
        gate._run_git(not_a_repo, "rev-parse", "HEAD")


def test_run_git_raises_gate_error_when_subprocess_run_itself_fails(
    repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`subprocess.run` itself raising `OSError` (e.g. no `git` executable
    on PATH at all) is a distinct failure mode from a non-zero exit code
    (covered by `test_run_git_raises_gate_error_on_nonexistent_repo_root`
    above) -- `_run_git`'s own `except OSError` branch, mirroring
    `tests/test_gitapex_compute_skill_audit_flags.py`'s own
    `test_git_being_unavailable_is_an_error`."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("git is not installed")

    monkeypatch.setattr(gate.subprocess, "run", _boom)
    with pytest.raises(gate.GateError, match="could not be run"):
        gate._run_git(repo, "status")


def test_run_git_raises_gate_error_on_non_utf8_output(repo: pathlib.Path) -> None:
    """`git show` output that is not valid UTF-8 -- a real file committed
    with an invalid byte sequence -- raises `GateError` naming the decode
    failure, rather than propagating a raw `UnicodeDecodeError` or
    silently replacing the invalid bytes. `_run_git`'s own
    `except UnicodeDecodeError` branch, mirroring
    `tests/test_gitapex_compute_skill_audit_flags.py`'s own
    `test_a_non_utf8_skill_md_fails_closed`."""
    path = repo / "docs" / "gitapex" / "plans" / "2026-01-01-bad-bytes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"# Plan\n\nIssue: caf\xe9 (not valid UTF-8)\n")
    _commit(repo, "add non-utf8 plans file")
    with pytest.raises(gate.GateError, match="not valid UTF-8"):
        gate._run_git(repo, "show", "HEAD:docs/gitapex/plans/2026-01-01-bad-bytes.md")


def test_git_show_reads_file_content_at_a_given_rev(repo: pathlib.Path) -> None:
    _write(repo, "docs/gitapex/plans/2026-01-01-sample.md", WELL_FORMED)
    _commit(repo, "add")
    content = gate._git_show(repo, "HEAD", "docs/gitapex/plans/2026-01-01-sample.md")
    assert content == WELL_FORMED


# ---------------------------------------------------------------------------
# CLI (main): exit codes and stdout/stderr shape.
# ---------------------------------------------------------------------------


def test_main_exits_zero_and_prints_pass_for_a_clean_diff(
    repo: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "docs/gitapex/plans/2026-01-01-sample.md", WELL_FORMED)
    _commit(repo, "add")
    exit_code = gate.main(["--check-diff", "HEAD~1", "HEAD", "--repo-root", str(repo)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_exits_one_and_prints_fail_for_a_malformed_diff(
    repo: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = WELL_FORMED.replace('Source ACM row: row 1 ("Sample criterion").\n', "")
    _write(repo, "docs/gitapex/plans/2026-01-01-sample.md", bad)
    _commit(repo, "add")
    exit_code = gate.main(["--check-diff", "HEAD~1", "HEAD", "--repo-root", str(repo)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "FAIL" in captured.err
    assert "source-acm-rows" in captured.err


def test_main_exits_one_and_reports_error_for_an_unresolvable_ref(
    repo: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = gate.main(["--check-diff", "nonexistent-ref-xyz", "HEAD", "--repo-root", str(repo)])
    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


def test_main_requires_check_diff_argument() -> None:
    with pytest.raises(SystemExit):
        gate.main([])

"""Tests for the skill-description-diff helper
(.github/scripts/skill_description_diff.py).

Refs #427 (refs #422): replaces skill-audit-gate.yml's original
`^[+-]description:` unified-diff regex, which two PR #428 review comments
found real gaps in -- a YAML block-scalar description (folded `>` /
literal `|`) can change only in its continuation lines, never touching the
`description:` line itself
(https://github.com/tvna/gitapex/pull/428#discussion_r3654041059), and a
byte-identical rename false-positives under a single-pathspec diff
(https://github.com/tvna/gitapex/pull/428#discussion_r3654041064). This
script instead parses and compares the description value directly.
"""

from __future__ import annotations

import subprocess

import pytest
import skill_description_diff as sdd


def _frontmatter(description_lines):
    return "---\nname: foo\n" + description_lines + "\n---\n# Foo\n"


# --- extract_description ---


def test_plain_scalar_description():
    text = _frontmatter("description: a plain one-line description")
    assert sdd.extract_description(text) == "a plain one-line description"


def test_quoted_scalar_description():
    text = _frontmatter('description: "a quoted description"')
    assert sdd.extract_description(text) == "a quoted description"


def test_folded_block_scalar_description():
    text = "---\nname: foo\ndescription: >\n  line one,\n  line two.\n---\n# Foo\n"
    assert sdd.extract_description(text) == "line one, line two."


def test_literal_block_scalar_description():
    text = "---\nname: foo\ndescription: |\n  line one\n  line two\n---\n# Foo\n"
    assert sdd.extract_description(text) == "line one\nline two"


def test_no_frontmatter_returns_none():
    assert sdd.extract_description("# just a heading\n") is None


def test_no_description_key_returns_none():
    text = "---\nname: foo\n---\n# Foo\n"
    assert sdd.extract_description(text) is None


def test_unterminated_frontmatter_returns_none():
    text = "---\nname: foo\ndescription: no closing marker\n# Foo\n"
    assert sdd.extract_description(text) is None


def test_bom_prefix_does_not_break_frontmatter_detection():
    text = "\ufeff" + _frontmatter("description: plain")
    assert sdd.extract_description(text) == "plain"


# --- description_changed ---


def test_unchanged_plain_scalar():
    text = _frontmatter("description: same")
    assert sdd.description_changed(text, text) is False


def test_changed_plain_scalar():
    base = _frontmatter("description: old")
    head = _frontmatter("description: new")
    assert sdd.description_changed(base, head) is True


def test_folded_block_scalar_continuation_line_only_change_is_detected():
    # The exact regression a line-diff regex misses: only the second
    # continuation line changes, never a line starting with "description:".
    base = "---\nname: foo\ndescription: >\n  Use when X,\n  covers old scope.\n---\n# Foo\n"
    head = "---\nname: foo\ndescription: >\n  Use when X,\n  covers new broadened scope.\n---\n# Foo\n"
    assert sdd.description_changed(base, head) is True


def test_folded_block_scalar_unchanged_across_identical_continuation_lines():
    text = "---\nname: foo\ndescription: >\n  Use when X,\n  covers scope.\n---\n# Foo\n"
    assert sdd.description_changed(text, text) is False


def test_literal_block_scalar_continuation_line_only_change_is_detected():
    base = "---\nname: foo\ndescription: |\n  first line\n  old second line\n---\n# Foo\n"
    head = "---\nname: foo\ndescription: |\n  first line\n  new second line\n---\n# Foo\n"
    assert sdd.description_changed(base, head) is True


def test_added_file_with_no_base_content_is_always_changed():
    head = _frontmatter("description: brand new")
    assert sdd.description_changed(None, head) is True


def test_missing_head_content_is_always_changed():
    base = _frontmatter("description: whatever")
    assert sdd.description_changed(base, None) is True


def test_unparseable_frontmatter_at_either_revision_fails_closed():
    base = "# no frontmatter at all\n"
    head = _frontmatter("description: something")
    assert sdd.description_changed(base, head) is True
    assert sdd.description_changed(head, base) is True


# --- _read_at_revision / main() integration, real temp git repo ---


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def _commit(repo, message):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_read_at_revision_returns_none_for_missing_path(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    (git_repo / "a.txt").write_text("hello\n")
    rev = _commit(git_repo, "base")
    assert sdd._read_at_revision(rev, "does-not-exist.txt") is None


def test_read_at_revision_returns_content_for_existing_path(git_repo, monkeypatch):
    monkeypatch.chdir(git_repo)
    (git_repo / "a.txt").write_text("hello\n")
    rev = _commit(git_repo, "base")
    assert sdd._read_at_revision(rev, "a.txt") == "hello\n"


def test_read_at_revision_returns_none_when_git_binary_missing(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(subprocess, "run", _raise)
    assert sdd._read_at_revision("HEAD", "a.txt") is None


def test_main_detects_description_change_across_commits(git_repo, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    skill_dir = git_repo / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(_frontmatter("description: old description"))
    base = _commit(git_repo, "base")
    skill_md.write_text(_frontmatter("description: new broadened description"))
    head = _commit(git_repo, "change")

    assert (
        sdd.main(
            [
                "--base-rev",
                base,
                "--head-rev",
                head,
                "--base-path",
                "skills/foo/SKILL.md",
                "--head-path",
                "skills/foo/SKILL.md",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "changed"


def test_main_reports_unchanged_across_byte_identical_rename(git_repo, monkeypatch, capsys):
    # Regression for PR #428 review comment
    # https://github.com/tvna/gitapex/pull/428#discussion_r3654041064: a
    # byte-identical rename must not be reported as a description change.
    monkeypatch.chdir(git_repo)
    old_dir = git_repo / "skills" / "old-name"
    old_dir.mkdir(parents=True)
    old_md = old_dir / "SKILL.md"
    old_md.write_text(_frontmatter("description: unchanged description"))
    base = _commit(git_repo, "base")

    new_dir = git_repo / "skills" / "new-name"
    new_dir.mkdir(parents=True)
    (new_dir / "SKILL.md").write_text(_frontmatter("description: unchanged description"))
    subprocess.run(["git", "rm", "-q", "skills/old-name/SKILL.md"], cwd=git_repo, check=True)
    head = _commit(git_repo, "rename")

    assert (
        sdd.main(
            [
                "--base-rev",
                base,
                "--head-rev",
                head,
                "--base-path",
                "skills/old-name/SKILL.md",
                "--head-path",
                "skills/new-name/SKILL.md",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "unchanged"


def test_main_detects_change_across_rename_with_new_description(git_repo, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    old_dir = git_repo / "skills" / "old-name"
    old_dir.mkdir(parents=True)
    (old_dir / "SKILL.md").write_text(_frontmatter("description: original"))
    base = _commit(git_repo, "base")

    new_dir = git_repo / "skills" / "new-name"
    new_dir.mkdir(parents=True)
    (new_dir / "SKILL.md").write_text(_frontmatter("description: rewritten during the rename"))
    subprocess.run(["git", "rm", "-q", "skills/old-name/SKILL.md"], cwd=git_repo, check=True)
    head = _commit(git_repo, "rename with content change")

    assert (
        sdd.main(
            [
                "--base-rev",
                base,
                "--head-rev",
                head,
                "--base-path",
                "skills/old-name/SKILL.md",
                "--head-path",
                "skills/new-name/SKILL.md",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "changed"


# ---------------------------------------------------------------------------
# _CliArgs pydantic validation (new in this batch's CLI-pydantic-wrap)
# ---------------------------------------------------------------------------


def test_main_rejects_blank_base_path(capsys):
    exit_code = sdd.main(
        ["--base-rev", "HEAD", "--head-rev", "HEAD", "--base-path", "", "--head-path", "skills/foo/SKILL.md"]
    )
    assert exit_code == 1
    assert "invalid arguments" in capsys.readouterr().err

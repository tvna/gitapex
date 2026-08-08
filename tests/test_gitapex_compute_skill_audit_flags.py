"""Unit tests for `.github/scripts/gitapex_compute_skill_audit_flags.py`.

Issue #874. The module is the single implementation of
`skill-audit-gate.yml`'s applicability computation, called both by that
workflow's own diff step and by
`gitapex_gate_skill_audit_disclosure.py --check-diff`.

Division of labour with its two sibling suites, so none of the three
duplicates another:

- `test_gitapex_skill_audit_gate_diff_step_shell.py` executes the real
  `run:` block against a scratch repository. That is the behavioural
  contract of the *shipped step* -- the pathspecs, the `D`/`R100` filter,
  the rename branch, the applicability condition -- and it kept passing
  unmodified across the extraction, which is what proves the extraction
  changed no behaviour.
- `test_gitapex_skill_audit_local_wrapper_parity.py` proves the local
  wrapper and that step agree.
- This file covers the module's own API surface and its fail-closed
  paths: the error branches a scratch-repo diff cannot easily reach
  (unparseable `--name-status` input, an unresolvable ref, a comma-bearing
  path) and the CLI's argument handling.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import gitapex_compute_skill_audit_flags as flags_module  # noqa: E402

SKILL_MD = """---
name: sample-skill
description: A perfectly ordinary skill with nothing notable in it.
---

# Sample

Body text.
"""


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _write(repo: pathlib.Path, relative: str, content: str = "x\n") -> pathlib.Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A scratch repo carrying the real gate registry, so the detector's
    registry rule resolves exactly as it does in CI."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@e")
    _git(tmp_path, "config", "user.name", "t")
    _write(tmp_path, ".gitapex/ssot.json", (REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _commit(repo: pathlib.Path, message: str = "change") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _flags(repo: pathlib.Path, base: str = "HEAD~1", head: str = "HEAD") -> flags_module.SkillAuditFlags:
    return flags_module.compute_flags(base, head, repo)


# --- the flags themselves ---


def test_an_unrelated_diff_is_not_applicable(repo: pathlib.Path) -> None:
    _write(repo, "README.md")
    _commit(repo)
    flags = _flags(repo)
    assert flags.applicable is False
    assert flags.skill_md_changed is False
    assert dict(flags.as_output_pairs())["changed-gate-scripts"] == ""


def test_a_changed_skill_md_sets_skill_md_changed(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _commit(repo)
    flags = _flags(repo)
    assert flags.applicable is True
    assert flags.skill_md_changed is True
    # A brand-new SKILL.md has no description at the merge base, so
    # `description_changed` fails closed and reports it as changed.
    assert flags.description_changed_skills == ("sample",)
    assert flags.needs_eval_coverage_skills == ("sample",)


def test_touching_the_skills_eval_tasks_clears_the_eval_coverage_flag(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _write(repo, "evals/sample/tasks/first.md", "# task\n")
    _commit(repo)
    flags = _flags(repo)
    assert flags.description_changed_skills == ("sample",)
    assert flags.needs_eval_coverage_skills == ()


def test_touching_the_skills_eval_status_file_clears_it_too(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _write(repo, "evals/sample/eval-status.md", "# status\n")
    _commit(repo)
    assert _flags(repo).needs_eval_coverage_skills == ()


def test_another_skills_eval_coverage_does_not_count(repo: pathlib.Path) -> None:
    """The eval-coverage rule is per skill; issue #499 moved it off a single
    shared central document precisely so a touch elsewhere stops counting."""
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _write(repo, "evals/other/tasks/first.md", "# task\n")
    _commit(repo)
    assert _flags(repo).needs_eval_coverage_skills == ("sample",)


def test_an_unchanged_description_is_not_reported(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _commit(repo, "add")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _write(repo, "skills/sample/SKILL.md", SKILL_MD + "\nMore body text.\n")
    _commit(repo, "body only")
    flags = _flags(repo, base=base)
    assert flags.skill_md_changed is True
    assert flags.description_changed_skills == ()
    assert flags.needs_eval_coverage_skills == ()


def test_a_security_relevant_frontmatter_is_flagged(repo: pathlib.Path) -> None:
    _write(
        repo,
        "skills/sample/SKILL.md",
        SKILL_MD.replace("nothing notable in it", "a deterministic gate in it"),
    )
    _commit(repo)
    assert _flags(repo).security_relevant_skills == ("sample",)


def test_a_non_security_relevant_frontmatter_is_not_flagged(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _commit(repo)
    assert _flags(repo).security_relevant_skills == ()


def test_a_deleted_skill_md_alone_is_not_applicable(repo: pathlib.Path) -> None:
    """`D` is filtered for this signal: a deleted SKILL.md has no new
    content to audit."""
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _commit(repo, "add")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "rm", "-q", "skills/sample/SKILL.md")
    _commit(repo, "delete")
    flags = _flags(repo, base=base)
    assert flags.applicable is False
    assert flags.skill_md_changed is False


def test_a_renamed_skill_md_reports_the_new_directory_name(repo: pathlib.Path) -> None:
    _write(repo, "skills/before/SKILL.md", SKILL_MD)
    _commit(repo, "add")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "skills/after").mkdir(parents=True)
    _git(repo, "mv", "skills/before/SKILL.md", "skills/after/SKILL.md")
    _write(repo, "skills/after/SKILL.md", SKILL_MD.replace("ordinary", "unusual"))
    _commit(repo, "rename and edit")
    flags = _flags(repo, base=base)
    assert flags.skill_md_changed is True
    assert flags.description_changed_skills == ("after",)


def test_a_byte_identical_rename_is_filtered_out(repo: pathlib.Path) -> None:
    _write(repo, "skills/before/SKILL.md", SKILL_MD)
    _commit(repo, "add")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "skills/after").mkdir(parents=True)
    _git(repo, "mv", "skills/before/SKILL.md", "skills/after/SKILL.md")
    _commit(repo, "pure rename")
    assert _flags(repo, base=base).skill_md_changed is False


def test_a_changed_gate_is_applicable_without_any_skill_md(repo: pathlib.Path) -> None:
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo)
    flags = _flags(repo)
    assert flags.applicable is True
    assert flags.skill_md_changed is False
    assert flags.changed_gate_scripts == (".github/scripts/gitapex_gate_new.py",)


def test_design_doc_and_checker_script_signals_are_collected(repo: pathlib.Path) -> None:
    _write(repo, "docs/superpowers/specs/2026-01-01-thing.md", "# doc\n")
    _write(repo, "skills/foo/scripts/gitapex_check_thing.py")
    _commit(repo)
    flags = _flags(repo)
    assert flags.changed_design_docs == ("docs/superpowers/specs/2026-01-01-thing.md",)
    assert flags.changed_checker_scripts == ("skills/foo/scripts/gitapex_check_thing.py",)


# --- fail closed ---


def test_an_unsupported_skill_directory_name_is_an_error(repo: pathlib.Path) -> None:
    _write(repo, "skills/bad name/SKILL.md", SKILL_MD)
    _commit(repo)
    with pytest.raises(flags_module.FlagComputationError, match="unsupported skill directory name"):
        _flags(repo)


def test_a_nested_design_doc_is_an_error_rather_than_being_dropped(repo: pathlib.Path) -> None:
    _write(repo, "docs/superpowers/specs/sub/thing.md", "# doc\n")
    _commit(repo)
    with pytest.raises(flags_module.FlagComputationError, match="unsupported design doc filename"):
        _flags(repo)


def test_an_untrustworthy_gate_registry_is_an_error(repo: pathlib.Path) -> None:
    _write(repo, ".gitapex/ssot.json", "{not json")
    _commit(repo)
    with pytest.raises(flags_module.FlagComputationError, match="gate-path detection failed"):
        _flags(repo)


def test_an_unresolvable_ref_is_an_error(repo: pathlib.Path) -> None:
    with pytest.raises(flags_module.FlagComputationError, match="git diff"):
        flags_module.compute_flags("no-such-ref", "HEAD", repo)


def test_git_being_unavailable_is_an_error(repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("git is not installed")

    monkeypatch.setattr(flags_module.subprocess, "run", _boom)
    with pytest.raises(flags_module.FlagComputationError, match="could not be run"):
        _flags(repo)


@pytest.mark.parametrize(
    "line",
    ["M", "R100"],
    ids=["no-path-field", "rename-without-destination"],
)
def test_an_unparseable_name_status_line_is_an_error(line: str) -> None:
    with pytest.raises(flags_module.FlagComputationError):
        flags_module._parse_name_status_line(line)


def test_a_rename_line_yields_both_sides() -> None:
    """Asserted directly rather than only through a scratch-repo diff: git
    reports a rename as `R<score>` only when its own similarity detection
    fires, so a repo-level test cannot reliably reach this branch."""
    assert flags_module._parse_name_status_line("R096\tskills/before/SKILL.md\tskills/after/SKILL.md") == (
        "R096",
        "skills/before/SKILL.md",
        "skills/after/SKILL.md",
    )


def test_a_rename_line_without_a_destination_names_the_missing_field() -> None:
    with pytest.raises(flags_module.FlagComputationError, match="no destination path"):
        flags_module._parse_name_status_line("R096\tskills/a/SKILL.md\t")


def test_reading_a_head_file_that_does_not_exist_is_an_error(
    repo: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The security-relevance read is the one `git show` whose failure the
    computation cannot absorb: an added/modified path is guaranteed to
    exist at head, so a miss means the diff and the tree disagree."""
    _write(repo, "skills/sample/SKILL.md", SKILL_MD)
    _commit(repo)
    monkeypatch.setattr(flags_module, "_git_show", lambda *_args: None)
    with pytest.raises(flags_module.FlagComputationError, match="security-relevance scoring"):
        _flags(repo)


# --- the CLI ---


def _run_cli(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = flags_module.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_cli_emits_every_output_key_in_order(repo: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "README.md")
    _commit(repo)
    code, out, _ = _run_cli(["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)], capsys)
    assert code == 0
    keys = [line.partition("=")[0] for line in out.strip().splitlines()]
    assert tuple(keys) == flags_module.OUTPUT_KEYS


def test_cli_json_format_round_trips(repo: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo)
    code, out, _ = _run_cli(
        ["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo), "--format", "json"], capsys
    )
    assert code == 0
    assert json.loads(out)["changed-gate-scripts"] == ".github/scripts/gitapex_gate_new.py"


def test_cli_writes_nothing_to_stdout_when_the_computation_fails(
    repo: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "docs/superpowers/specs/sub/thing.md", "# doc\n")
    _commit(repo)
    code, out, err = _run_cli(["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)], capsys)
    assert code == 1
    assert out == "", "a partial flag set must never reach a $GITHUB_OUTPUT redirect"
    assert "unsupported design doc filename" in err


def test_cli_rejects_a_repo_root_that_is_not_a_directory(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope"
    code, _, err = _run_cli(["--base-ref", "a", "--head-ref", "b", "--repo-root", str(missing)], capsys)
    assert code == 1
    assert "must be an existing directory" in err


@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "whitespace"])
def test_cli_rejects_a_blank_ref(repo: pathlib.Path, capsys: pytest.CaptureFixture[str], blank: str) -> None:
    code, _, err = _run_cli(["--base-ref", blank, "--head-ref", "HEAD", "--repo-root", str(repo)], capsys)
    assert code == 1
    assert "must both be non-empty" in err

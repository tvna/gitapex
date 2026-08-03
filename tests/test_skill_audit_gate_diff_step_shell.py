"""Shell-level tests for `skill-audit-gate.yml`'s own diff step.

Issue #673 (refs #665 repair 1). Its review found the workflow half of this
gate -- the half that decides whether any check fires at all -- had zero
automated coverage: every test targeted the Python grader, and nothing
pinned the `:(glob)` pathspecs, the `D`/`R100` filter, the rename branch,
the shape validation, or the applicability condition. Silently breaking any
of them left the whole suite green.

`hooks/test_check_pr_issue_acm_disclosure_shell.py` and
`hooks/test_check_bash_safety.py` already establish the pattern: extract
the real `run:` block from the YAML and execute it against a scratch git
repository, so the thing under test is the shipped text rather than a
paraphrase of it.

The `scan_*.py` half of the gate scope is exercised here specifically: it
appears only in the workflow and the detector, never in the grader's own
fixtures, so without this file half the declared scope was untested.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "skill-audit-gate.yml"


@pytest.fixture(scope="module")
def diff_step_script(tmp_path_factory):
    """The real `run:` block of the diff step, written out as a script."""
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["skill-audit-disclosure"]["steps"]
    run = next(s["run"] for s in steps if "$GITHUB_OUTPUT" in s.get("run", ""))
    path = tmp_path_factory.mktemp("diffstep") / "diff_step.sh"
    path.write_text(run, encoding="utf-8")
    return path


def _git(repo, *args, **kwargs):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, **kwargs
    )


def _write(repo, relative, content="x\n"):
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def outdir(tmp_path_factory):
    """Harness scratch space, deliberately OUTSIDE the git repository under
    test: `_commit` runs `git add -A`, so a $GITHUB_OUTPUT file written
    inside the repo gets committed into the very diff the step is grading.
    Harmless today (the artifact is not a gate path) but it means the test
    silently exercises a diff it did not author."""
    return tmp_path_factory.mktemp("harness")


@pytest.fixture
def repo(tmp_path):
    """A scratch repo carrying the real .gitapex/ssot.json and the two
    scripts the diff step shells out to, so the step runs unmodified."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@e")
    _git(tmp_path, "config", "user.name", "t")
    for relative in (
        ".gitapex/ssot.json",
        ".github/scripts/detect_changed_gate_scripts.py",
        ".github/scripts/skill_description_diff.py",
        ".github/scripts/skill_security_relevance.py",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((REPO_ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def run_diff_step(script, repo, outdir, base=None):
    """Run the real diff step over `base...HEAD` and return (returncode,
    parsed $GITHUB_OUTPUT dict, combined output)."""
    output_file = outdir / "gh_output.txt"
    output_file.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "BASE_SHA": base or _git(repo, "rev-parse", "HEAD~1").stdout.strip(),
        "HEAD_SHA": _git(repo, "rev-parse", "HEAD").stdout.strip(),
        "GITHUB_OUTPUT": str(output_file),
    }
    proc = subprocess.run(
        ["bash", str(script)], cwd=repo, env=env, capture_output=True, text=True
    )
    parsed = {}
    for line in output_file.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            parsed[key] = value
    return proc.returncode, parsed, proc.stdout + proc.stderr


def _commit(repo, message="change"):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


# --- gate-script scope, including the scan_*.py half ---


def test_a_changed_gate_script_is_reported(diff_step_script, repo, outdir):
    _write(repo, ".github/scripts/gate_new.py")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["applicable"] == "true"
    assert out["changed-gate-scripts"] == ".github/scripts/gate_new.py"


def test_a_changed_scan_script_is_reported(diff_step_script, repo, outdir):
    """The half of the declared scope that appears only in the workflow."""
    _write(repo, ".github/scripts/scan_new.py")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-gate-scripts"] == ".github/scripts/scan_new.py"


def test_a_registered_hook_gate_is_reported(diff_step_script, repo, outdir):
    """Registry membership, not the naming convention."""
    _write(repo, "hooks/check-bash-safety.sh")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-gate-scripts"] == "hooks/check-bash-safety.sh"
    assert out["applicable"] == "true"


def test_deleting_a_gate_script_still_requires_disclosure(diff_step_script, repo, outdir):
    """The live-reproduced regression: this used to yield applicable=false
    and a green required check for removing a gate."""
    _write(repo, ".github/scripts/gate_doomed.py")
    _commit(repo, "add")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "rm", "-q", ".github/scripts/gate_doomed.py")
    _commit(repo, "delete")
    code, out, _ = run_diff_step(diff_step_script, repo, outdir, base=base)
    assert code == 0
    assert out["applicable"] == "true", "deleting a gate must not skip the check"
    assert out["changed-gate-scripts"] == ".github/scripts/gate_doomed.py"


def test_renaming_a_gate_script_still_requires_disclosure(diff_step_script, repo, outdir):
    _write(repo, ".github/scripts/gate_before.py")
    _commit(repo, "add")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "mv", ".github/scripts/gate_before.py", ".github/scripts/gate_after.py")
    _commit(repo, "rename")
    code, out, _ = run_diff_step(diff_step_script, repo, outdir, base=base)
    assert code == 0
    assert out["applicable"] == "true"
    assert out["changed-gate-scripts"] == (
        ".github/scripts/gate_after.py,.github/scripts/gate_before.py"
    )


def test_a_nested_path_under_a_gate_prefixed_directory_is_out_of_scope(
    diff_step_script, repo, outdir
):
    _write(repo, ".github/scripts/gate_helpers/support.py")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-gate-scripts"] == ""


def test_an_unrelated_diff_skips_the_whole_check(diff_step_script, repo, outdir):
    _write(repo, "README.md")
    _commit(repo)
    code, out, log = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["applicable"] == "false"
    assert out["changed-gate-scripts"] == ""
    assert "skipping disclosure check" in log


# --- the shared collector's own behaviour ---


def test_a_changed_checker_script_is_reported(diff_step_script, repo, outdir):
    _write(repo, "skills/foo/scripts/check_thing.py")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-checker-scripts"] == "skills/foo/scripts/check_thing.py"


def test_a_deleted_checker_script_is_not_reported(diff_step_script, repo, outdir):
    """The D/R100 filter still applies to the collector-driven signals --
    only the gate signal opts out of it."""
    _write(repo, "skills/foo/scripts/check_thing.py")
    _commit(repo, "add")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "rm", "-q", "skills/foo/scripts/check_thing.py")
    _commit(repo, "delete")
    code, out, _ = run_diff_step(diff_step_script, repo, outdir, base=base)
    assert code == 0
    assert out["changed-checker-scripts"] == ""


def test_a_nested_checker_script_is_excluded_by_the_glob_pathspec(
    diff_step_script, repo, outdir
):
    """Without `:(glob)` git's `*` crosses `/`, the nested path reaches the
    single-level shape regex, and this required check hard-fails on a file
    it never intended to scope."""
    _write(repo, "skills/foo/scripts/sub/check_thing.py")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-checker-scripts"] == ""


def test_a_changed_design_doc_is_reported(diff_step_script, repo, outdir):
    _write(repo, "docs/superpowers/specs/2026-01-01-thing.md", "# doc\n")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-design-docs"] == "docs/superpowers/specs/2026-01-01-thing.md"


def test_a_nested_design_doc_hard_fails_rather_than_being_dropped(
    diff_step_script, repo, outdir
):
    """Deliberately the opposite of the checker-script case above: the
    design-doc pathspec carries no `:(glob)`, so an undecided path shape is
    surfaced loudly instead of silently leaving scope."""
    _write(repo, "docs/superpowers/specs/sub/thing.md", "# doc\n")
    _commit(repo)
    code, _, log = run_diff_step(diff_step_script, repo, outdir)
    assert code == 1
    assert "unsupported design doc filename" in log


def test_multiple_paths_are_comma_joined(diff_step_script, repo, outdir):
    _write(repo, ".github/scripts/gate_a.py")
    _write(repo, ".github/scripts/scan_b.py")
    _commit(repo)
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-gate-scripts"] == ".github/scripts/gate_a.py,.github/scripts/scan_b.py"


# --- fail closed ---


def test_an_unreadable_registry_fails_the_step_rather_than_reporting_green(
    diff_step_script, repo, outdir
):
    """A registry the detector cannot trust must not degrade to the
    naming-convention rule alone, which under-covers by design."""
    _write(repo, ".gitapex/ssot.json", "{not json")
    _commit(repo)
    code, _, log = run_diff_step(diff_step_script, repo, outdir)
    assert code == 1
    assert "gate-path detection failed" in log


def test_every_output_key_is_written_on_both_paths(diff_step_script, repo, outdir):
    """The check step reads each key unconditionally; a key written on only
    one path silently becomes an empty string on the other."""
    _write(repo, "README.md")
    _commit(repo, "unrelated")
    _, skipped, _ = run_diff_step(diff_step_script, repo, outdir)
    _write(repo, ".github/scripts/gate_a.py")
    _commit(repo, "gate")
    _, applied, _ = run_diff_step(diff_step_script, repo, outdir)
    assert set(skipped) == set(applied), "the two $GITHUB_OUTPUT paths disagree on keys"


def test_the_harness_leaves_no_artifact_in_the_repository_under_test(
    diff_step_script, repo, outdir
):
    """Guards the fixture split above: if $GITHUB_OUTPUT ever moves back
    inside the repo, `git add -A` in `_commit` starts committing it into
    the diff being graded."""
    _write(repo, ".github/scripts/gate_a.py")
    _commit(repo)
    run_diff_step(diff_step_script, repo, outdir)
    _write(repo, "README.md")
    _commit(repo, "second")
    tracked = _git(repo, "ls-files").stdout.split()
    assert not [p for p in tracked if "gh_output" in p or "workflow_diff" in p], tracked


# --- Dependabot pin bumps must not fail this check ---


_PINNED_STEP = """\
name: Lint workflows
on:
  pull_request: {}
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
"""


def test_a_dependabot_style_pin_bump_to_a_registered_gate_workflow_is_exempt(
    diff_step_script, repo, outdir
):
    """`.github/workflows/lint.yml` is a registered gate, so rule 2 puts it
    in scope -- correctly. But Dependabot's weekly github-actions update
    bumps its SHA pins, and a bot cannot add a disclosure to its own PR
    body, so without the pin-only exemption every weekly dependency PR
    carries a permanently red required check nobody can satisfy."""
    _write(repo, ".github/workflows/lint.yml", _PINNED_STEP)
    _commit(repo, "add lint.yml")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _write(
        repo,
        ".github/workflows/lint.yml",
        _PINNED_STEP.replace(
            "3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  # v7.1.0",
        ),
    )
    _commit(repo, "chore(ci): bump actions/checkout")
    code, out, log = run_diff_step(diff_step_script, repo, outdir, base=base)
    assert code == 0
    assert out["changed-gate-scripts"] == "", log
    assert "pin-only workflow change" in log


def test_a_logic_change_to_the_same_workflow_is_not_exempt(diff_step_script, repo, outdir):
    """The exemption is content-based, so smuggling a real edit alongside a
    pin bump keeps the file in scope."""
    _write(repo, ".github/workflows/lint.yml", _PINNED_STEP)
    _commit(repo, "add lint.yml")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _write(
        repo,
        ".github/workflows/lint.yml",
        _PINNED_STEP.replace(
            "3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  # v7.1.0",
        ).replace("    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    continue-on-error: true\n"),
    )
    _commit(repo, "sneaky")
    code, out, _ = run_diff_step(diff_step_script, repo, outdir, base=base)
    assert code == 0
    assert out["changed-gate-scripts"] == ".github/workflows/lint.yml"


def test_gutting_this_gates_own_workflow_requires_disclosure(diff_step_script, repo, outdir):
    """The review's sharpest finding: skill-audit-gate.yml was neither
    convention-matching nor registered, so a PR deleting the check step
    reported a green required check for turning this gate into a no-op."""
    _write(repo, ".github/workflows/skill-audit-gate.yml", "name: x\non: {}\njobs: {}\n")
    _commit(repo, "edit the gate's own workflow")
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-gate-scripts"] == ".github/workflows/skill-audit-gate.yml"
    assert out["applicable"] == "true"


def test_unhooking_a_pretooluse_gate_requires_disclosure(diff_step_script, repo, outdir):
    """hooks/hooks.json decides whether the PreToolUse gates run at all --
    rewriting it to unhook one is as complete a disable as deleting the
    script, and was invisible while only the scripts were in scope."""
    _write(repo, "hooks/hooks.json", '{"hooks": {}}\n')
    _commit(repo, "unhook")
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-gate-scripts"] == "hooks/hooks.json"


def test_a_new_unregistered_hook_gate_is_in_scope(diff_step_script, repo, outdir):
    """Rule 1 covers hooks/ too now: 9 of the 25 registered gates live
    there, and registration is a separate unenforced step."""
    _write(repo, "hooks/check-new-deny.sh", "#!/bin/sh\nexit 2\n")
    _commit(repo, "new deny gate")
    code, out, _ = run_diff_step(diff_step_script, repo, outdir)
    assert code == 0
    assert out["changed-gate-scripts"] == "hooks/check-new-deny.sh"

"""Regression suite for gitapex_check_canonical_governance_paths.py's own
category boundary. Runs the shipped script via subprocess, same
convention as this directory's other checker-script tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "gitapex_check_canonical_governance_paths.py"


def run(paths):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="\n".join(paths),
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_workflow_prefix_and_filenames():
    result = run([".github/workflows/ci.yml", ".gitlab-ci.yml", "Jenkinsfile"])
    assert result.returncode == 0
    assert "workflow: .github/workflows/ci.yml" in result.stdout
    assert "workflow: .gitlab-ci.yml" in result.stdout
    assert "workflow: Jenkinsfile" in result.stdout


def test_governance_filenames_and_skill_paths():
    result = run(["CLAUDE.md", "CODEOWNERS", "skills/foo/SKILL.md", "skills/foo/metadata/gitapex.yaml"])
    assert result.returncode == 0
    assert "governance: CLAUDE.md" in result.stdout
    assert "governance: CODEOWNERS" in result.stdout
    assert "governance: skills/foo/SKILL.md" in result.stdout
    assert "governance: skills/foo/metadata/gitapex.yaml" in result.stdout


def test_hook_script_prefix_and_skill_scripts_path():
    result = run(["hooks/check-x.sh", "skills/foo/scripts/bar.py"])
    assert result.returncode == 0
    assert "hook-script: hooks/check-x.sh" in result.stdout
    assert "hook-script: skills/foo/scripts/bar.py" in result.stdout


def test_dependency_manifest_filenames():
    result = run(["pyproject.toml", "package.json"])
    assert result.returncode == 0
    assert "dependency-manifest: pyproject.toml" in result.stdout
    assert "dependency-manifest: package.json" in result.stdout


def test_composite_action_is_no_match_not_workflow():
    # The adversarial defeat-case named by issue #659 itself: a composite
    # GitHub Action under .github/actions/** is CI-execution-relevant but
    # is deliberately NOT in the canonical workflow prefix list -- it must
    # classify as no-match, left for the model's own full-diff review, not
    # silently absorbed into "workflow" (a false sense of coverage) or
    # dropped entirely.
    result = run([".github/actions/build-and-push/action.yml"])
    assert result.returncode == 0
    assert "no-match: .github/actions/build-and-push/action.yml" in result.stdout
    assert "workflow: .github/actions/build-and-push/action.yml" not in result.stdout


def test_too_many_segments_is_no_match_not_governance():
    # skills/foo/bar/SKILL.md has one extra path segment vs the real
    # skills/<name>/SKILL.md shape -- must not false-positive as governance.
    result = run(["skills/foo/bar/SKILL.md"])
    assert result.returncode == 0
    assert "no-match: skills/foo/bar/SKILL.md" in result.stdout


def test_codeowners_matches_all_three_github_recognized_locations():
    # Adversarial gate finding (gitapex issue #659 review): GitHub
    # recognizes CODEOWNERS at the repo root, .github/, AND docs/ ("GitHub
    # will search for them in that order and use the first one it finds",
    # per GitHub's own CODEOWNERS docs) -- an edit to any of the three
    # weakens the code-owner review gate identically, so all three must
    # classify as governance, not just the root one.
    result = run(["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"])
    assert result.returncode == 0
    assert "governance: CODEOWNERS" in result.stdout
    assert "governance: .github/CODEOWNERS" in result.stdout
    assert "governance: docs/CODEOWNERS" in result.stdout


def test_double_slash_still_matches_skill_governance_shape():
    # Adversarial gate finding: a redundant "//" run in an otherwise
    # canonical skills/<name>/SKILL.md path must not defeat the
    # segment-shape check -- _gitapex_path_normalize.py collapses "//" before this
    # script splits on "/".
    result = run(["skills//foo/SKILL.md"])
    assert result.returncode == 0
    assert "governance: skills//foo/SKILL.md" in result.stdout


def test_leading_dotslash_adjacent_to_slash_still_matches():
    # Independent /code-review finding: a leading "./" immediately
    # followed by another "/" (".//skills/foo/SKILL.md") is a distinct
    # case from the plain double-slash test above (no leading "./") --
    # an earlier normalize() implementation stripped "./" before
    # collapsing "//", leaving a stray leading "/" that made
    # classify() fall to "no-match" instead of "governance".
    result = run([".//skills/foo/SKILL.md"])
    assert result.returncode == 0
    assert "governance: .//skills/foo/SKILL.md" in result.stdout


def test_no_paths_given():
    result = subprocess.run([sys.executable, str(SCRIPT)], input="", capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "no paths given" in result.stdout


def test_missing_files_arg_is_usage_error():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--files", "/nonexistent/path.txt"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2


def test_non_utf8_files_arg_is_usage_error_not_a_traceback(tmp_path):
    bad_file = tmp_path / "files.txt"
    bad_file.write_bytes(b"\xff\xfe bad")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--files", str(bad_file)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "not valid UTF-8" in result.stderr
    assert "Traceback" not in result.stderr


def test_non_utf8_stdin_is_usage_error_not_a_traceback():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=b"\xff\xfe bad",
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert "standard input" in stderr and "not valid UTF-8" in stderr
    assert "Traceback" not in stderr

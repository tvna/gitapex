"""Regression suite for check_canonical_governance_paths.py's own
category boundary. Runs the shipped script via subprocess, same
convention as this directory's other checker-script tests.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "check_canonical_governance_paths.py"


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


def test_no_paths_given():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input="", capture_output=True, text=True, timeout=10
    )
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

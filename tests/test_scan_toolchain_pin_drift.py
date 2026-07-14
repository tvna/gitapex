"""Tests for the toolchain pin-drift gate (.github/scripts/scan_toolchain_pin_drift.py).

The final test is the gate itself: the repository's real workflows must be
drift-free. The rest unit-test the detector with fixtures.
"""

from __future__ import annotations

import pathlib

import scan_toolchain_pin_drift as drift

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _write(workflows_dir: pathlib.Path, name: str, content: str) -> None:
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / name).write_text(content)


def test_clean_workflow_has_no_drift(tmp_path):
    _write(
        tmp_path,
        "ci.yml",
        "jobs:\n  x:\n    steps:\n      - run: nix run .#waza -- check --no-update-check\n",
    )
    assert drift.find_drift(tmp_path) == []


def test_go_install_of_class_b_tool_is_drift(tmp_path):
    _write(
        tmp_path,
        "waza-check.yml",
        "      - run: go install github.com/microsoft/waza/cmd/waza@abc123\n",
    )
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert findings[0][0].endswith("waza-check.yml")
    assert "microsoft/waza" in findings[0][2]


def test_release_download_url_of_class_b_tool_is_drift(tmp_path):
    _write(
        tmp_path,
        "install.yml",
        '      - run: curl -L https://github.com/rtk-ai/rtk/releases/download/v0.43.0/rtk.tar.gz\n',
    )
    assert len(drift.find_drift(tmp_path)) == 1


def test_plain_mention_of_tool_name_is_not_drift(tmp_path):
    # A step named "Run waza check" mentions the tool but not its owner/repo,
    # so it must NOT trip the scan.
    _write(
        tmp_path,
        "waza-check.yml",
        "      - name: Run waza check (advisory report, not a merge gate)\n",
    )
    assert drift.find_drift(tmp_path) == []


def test_all_class_b_repos_are_detected(tmp_path):
    lines = "\n".join(f"      - run: install {repo}" for repo in drift.CLASS_B_REPOS)
    _write(tmp_path, "many.yml", lines + "\n")
    assert len(drift.find_drift(tmp_path)) == len(drift.CLASS_B_REPOS)


def test_repository_workflows_are_drift_free():
    """The gate: real CI workflows must provision Class B tools via the flake."""
    findings = drift.find_drift(REPO_ROOT / ".github" / "workflows")
    assert findings == [], f"toolchain pin drift in real workflows: {findings}"

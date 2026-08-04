"""Tests for the toolchain pin-drift gate (.github/scripts/gitapex_scan_toolchain_pin_drift.py).

The final test is the gate itself: the repository's real workflows must be
drift-free. The rest unit-test the detector with fixtures.
"""

from __future__ import annotations

import pathlib

import gitapex_scan_toolchain_pin_drift as drift

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
        "      - run: curl -L https://github.com/rtk-ai/rtk/releases/download/v0.43.0/rtk.tar.gz\n",
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


def test_undecodable_workflow_file_is_skipped_not_crashed(tmp_path):
    # Regression: a non-UTF-8 workflow file raised an unhandled
    # UnicodeDecodeError from workflow.read_text() instead of being reported
    # as a finding, and clean files in the same directory must still be
    # scanned.
    (tmp_path / "bad.yml").write_bytes(b"\xff\xfe bad")
    _write(tmp_path, "ok.yml", "      - run: go install microsoft/waza@latest\n")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 2
    paths = {path for path, _, _ in findings}
    assert any(p.endswith("ok.yml") for p in paths)
    assert any(p.endswith("bad.yml") for p in paths)


def test_undecodable_workflow_file_fails_closed_even_when_it_is_the_only_file(tmp_path):
    # Dimension 15 (fail-closed on malformed input): a file that cannot be
    # decoded cannot be verified clean, so it must not scan as if it had no
    # drift -- an inability to verify is a finding, not a silent pass, even
    # when the corrupted file is the only one that would have carried the
    # real violation.
    (tmp_path / "bad.yml").write_bytes(b"      - run: go install microsoft/waza@latest\n\xff\xfe")
    findings = drift.find_drift(tmp_path)
    assert findings != []
    assert findings[0][0].endswith("bad.yml")


def test_repository_workflows_are_drift_free():
    """The gate: real CI workflows must provision Class B tools via the flake."""
    findings = drift.find_drift(REPO_ROOT / ".github" / "workflows")
    assert findings == [], f"toolchain pin drift in real workflows: {findings}"


def test_main_prints_no_drift_and_returns_zero_when_clean(capsys, monkeypatch):
    # find_drift's own path-reading behavior is covered by the fixture-based
    # tests above and the live repository test above; this test isolates
    # main()'s own print/exit-code contract by stubbing find_drift.
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No toolchain pin drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(capsys, monkeypatch):
    monkeypatch.setattr(
        drift,
        "find_drift",
        lambda: [(".github/workflows/waza-check.yml", 3, "go install microsoft/waza")],
    )
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "Toolchain pin drift" in out
    assert ".github/workflows/waza-check.yml:3: go install microsoft/waza" in out

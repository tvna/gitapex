"""Tests for the harden-checkout pin-drift gate
(.github/scripts/gitapex_scan_harden_checkout_pin_drift.py).

The final test is the gate itself: the repository's real workflows must be
drift-free. The rest unit-test the detector with fixtures, with
current_action_sha monkeypatched so unit tests don't depend on this
checkout's own git history.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_scan_harden_checkout_pin_drift as drift
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CURRENT_SHA = "a" * 40
STALE_SHA = "b" * 40


def _write(workflows_dir: pathlib.Path, name: str, content: str) -> None:
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / name).write_text(content)


def _pin_line(sha: str) -> str:
    return f"      - uses: {drift.ACTION_REF}@{sha}\n"


def _stub_current_sha(monkeypatch: pytest.MonkeyPatch, sha: str) -> None:
    monkeypatch.setattr(drift, "current_action_sha", lambda repo_root=None: sha)


def test_pin_matching_current_sha_has_no_drift(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    _write(tmp_path, "gate.yml", _pin_line(CURRENT_SHA))
    assert drift.find_drift(tmp_path) == []


def test_stale_pin_is_drift(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    _write(tmp_path, "gate.yml", _pin_line(STALE_SHA))
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert findings[0][0].endswith("gate.yml")
    assert STALE_SHA in findings[0][2]


def test_local_relative_path_reference_is_not_matched(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A `./`-relative uses: (not this gate's concern -- and not even valid
    # for this action, which must be self-referenced by full remote form)
    # must not trip the 40-hex-char regex.
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    _write(tmp_path, "gate.yml", "      - uses: ./.github/actions/harden-checkout\n")
    assert drift.find_drift(tmp_path) == []


def test_mixed_clean_and_stale_workflows(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    _write(tmp_path, "clean.yml", _pin_line(CURRENT_SHA))
    _write(tmp_path, "stale.yml", _pin_line(STALE_SHA))
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert findings[0][0].endswith("stale.yml")


def test_undecodable_workflow_file_is_reported_not_crashed(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression class mirrored from gitapex_scan_toolchain_pin_drift.py:
    # a non-UTF-8 file can't be verified clean, so it's a finding, and
    # clean files alongside it must still be scanned.
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    (tmp_path / "bad.yml").write_bytes(b"\xff\xfe bad")
    _write(tmp_path, "ok.yml", _pin_line(CURRENT_SHA))
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert findings[0][0].endswith("bad.yml")


def test_current_action_sha_raises_when_path_has_no_history(tmp_path: pathlib.Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    (tmp_path / "unrelated.txt").write_text("x")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "unrelated"], cwd=tmp_path, check=True)
    with pytest.raises(RuntimeError, match="no commit history found"):
        drift.current_action_sha(tmp_path)


def test_repository_workflows_are_drift_free() -> None:
    """The gate: real CI workflows must pin the composite action's current SHA."""
    findings = drift.find_drift(REPO_ROOT / ".github" / "workflows", REPO_ROOT)
    assert findings == [], f"harden-checkout pin drift in real workflows: {findings}"


def test_main_prints_no_drift_and_returns_zero_when_clean(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No harden-checkout pin drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        drift,
        "find_drift",
        lambda: [(".github/workflows/lint.yml", 41, f"uses: {drift.ACTION_REF}@{STALE_SHA}")],
    )
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "harden-checkout composite action pin drift" in out
    assert f".github/workflows/lint.yml:41: uses: {drift.ACTION_REF}@{STALE_SHA}" in out


def test_main_reports_and_returns_one_when_current_sha_unresolvable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise() -> list[tuple[str, int, str]]:
        raise RuntimeError("no commit history found for x")

    monkeypatch.setattr(drift, "find_drift", _raise)
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "could not run" in out

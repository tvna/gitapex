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
    # must not match ACTION_REF at all.
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    _write(tmp_path, "gate.yml", "      - uses: ./.github/actions/harden-checkout\n")
    assert drift.find_drift(tmp_path) == []


def test_reference_inside_a_comment_is_not_matched(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: an earlier version of _USES_RE matched the ref string
    # anywhere on a line, so a comment merely documenting the action
    # (e.g. explaining a past migration) was misgraded as a real pin.
    # Confirmed live with a comment carrying a deliberately wrong SHA that
    # would otherwise report as drift.
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    _write(
        tmp_path,
        "gate.yml",
        f"      # after migrating away from {drift.ACTION_REF}@{STALE_SHA}, delete this\n",
    )
    assert drift.find_drift(tmp_path) == []


def test_short_sha_pin_is_drift_not_silently_unmatched(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: an earlier version of _USES_RE anchored on `[0-9a-f]{40}`,
    # so a short SHA (or any non-full-SHA ref) simply failed to match and
    # was never reported at all -- a fail-open gap on the exact malformed
    # pin this gate exists to prevent (its own convention requires a full
    # commit SHA). It must now be flagged as drift.
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    _write(tmp_path, "gate.yml", _pin_line(CURRENT_SHA[:7]))
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert findings[0][0].endswith("gate.yml")


def test_missing_workflows_dir_raises_instead_of_reading_as_clean(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: Path.glob on a nonexistent directory silently yields no
    # matches, so find_drift used to return [] -- indistinguishable from a
    # real clean scan. A missing/misconfigured workflows_dir must fail
    # loudly instead.
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    with pytest.raises(RuntimeError, match="workflows directory not found"):
        drift.find_drift(tmp_path / "does-not-exist")


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


def test_unreadable_file_is_reported_not_crashed(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: only UnicodeDecodeError was caught around read_text(), so
    # a broken symlink (or any other OSError -- a permission error, e.g.)
    # raised uncaught and aborted the whole scan before reaching any other
    # file, unlike the deliberate per-file handling the undecodable-file
    # case already gets.
    _stub_current_sha(monkeypatch, CURRENT_SHA)
    (tmp_path / "broken.yml").symlink_to(tmp_path / "does-not-exist.yml")
    _write(tmp_path, "ok.yml", _pin_line(CURRENT_SHA))
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert findings[0][0].endswith("broken.yml")


def test_current_action_sha_raises_when_path_has_no_history(tmp_path: pathlib.Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    (tmp_path / "unrelated.txt").write_text("x")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "unrelated"], cwd=tmp_path, check=True)
    with pytest.raises(RuntimeError, match="no commit history found"):
        drift.current_action_sha(tmp_path)


def test_current_action_sha_wraps_git_failure_outside_a_repo(tmp_path: pathlib.Path) -> None:
    # Regression: any `git` subcommand outside a git repository exits
    # non-zero, and check=True previously let subprocess.CalledProcessError
    # escape uncaught -- bypassing main()'s intended clean "could not run"
    # message path (though the process still exited non-zero either way).
    # It must now surface as this module's own RuntimeError.
    with pytest.raises(RuntimeError, match="git log"):
        drift.current_action_sha(tmp_path)


def test_shallow_clone_is_rejected_explicitly(tmp_path: pathlib.Path) -> None:
    # Regression, confirmed by cloning this real repo at --depth 1: a
    # shallow boundary commit has no parent, so `git log -1 -- <path>`
    # diffs it against an empty tree and returns that boundary commit's own
    # SHA for every path it contains -- not empty output, so the
    # no-history check alone can't catch it. Verified live: an unguarded
    # version of this function returned the wrong SHA here instead of
    # raising, which would have misread all 28 real workflow pins as
    # drifted. Must be rejected explicitly before trusting `git log`'s
    # answer.
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{REPO_ROOT}", str(tmp_path / "shallow")],
        check=True,
        capture_output=True,
    )
    with pytest.raises(RuntimeError, match="shallow-clone boundary artifact"):
        drift.current_action_sha(tmp_path / "shallow")


def test_shallow_repo_with_a_non_boundary_answer_is_still_trusted(tmp_path: pathlib.Path) -> None:
    # A shallow clone is not unconditionally rejected: only the specific
    # case where the resolved commit IS the shallow boundary artifact is.
    # A shallow clone whose fetched depth already reaches the path's real
    # last-touching commit (an extra local commit on top of a shallow
    # clone, exactly this repo's own dev-session shape) must still work.
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{REPO_ROOT}", str(shallow)], check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=shallow, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=shallow, check=True)
    action_dir = shallow / ".github" / "actions" / "harden-checkout"
    action_dir.mkdir(parents=True, exist_ok=True)
    (action_dir / "action.yml").write_text("name: test\n")
    subprocess.run(["git", "add", "."], cwd=shallow, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "touch action.yml"], cwd=shallow, check=True)
    sha = drift.current_action_sha(shallow)
    assert (
        sha
        == subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=shallow, check=True, capture_output=True, text=True
        ).stdout.strip()
    )


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

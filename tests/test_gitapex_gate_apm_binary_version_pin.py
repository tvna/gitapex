"""Tests for the apm binary version pin gate
(.github/scripts/gitapex_gate_apm_binary_version_pin.py).

The final tests run the gate against this repository's real flake.nix,
apm.lock.yaml, and whatever `apm` (if any) is actually on PATH: no drift is
expected. The rest unit-test the two independent checks (the committed
lockfile's own `apm_version` field, and a PATH-resolvable binary's
`apm --version` output) with fixtures, including a regression test that
reproduces the exact defect shape issue #1817 was filed over.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_apm_binary_version_pin as gate
import pytest

_FLAKE_SNIPPET = """\
      mkClassB = pkgs:
        let
          sys = pkgs.stdenv.hostPlatform.system;
          d = classBData;
        in
        {
          apm = mkReleaseBinary pkgs {
            pname = "apm";
            version = "0.25.0";
            kind = "wrapperDir";
            url = ghRelease "microsoft" "apm" "v0.25.0" d.apm.${sys}.asset;
            sha256 = d.apm.${sys}.sha256;
          };
          rtk = mkReleaseBinary pkgs {
            pname = "rtk";
            version = "0.43.0";
            kind = "binary";
            url = ghRelease "rtk-ai" "rtk" "v0.43.0" d.rtk.${sys}.asset;
            sha256 = d.rtk.${sys}.sha256;
          };
        };
"""

_REAL_APM_VERSION_OUTPUT = "Agent Package Manager (APM) CLI version 0.25.0 (d73e6ac)\n"


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _no_apm_on_path(name: str) -> str | None:
    return None


def _write_flake(tmp_path: pathlib.Path) -> pathlib.Path:
    flake_path = tmp_path / "flake.nix"
    flake_path.write_text(_FLAKE_SNIPPET, encoding="utf-8")
    return flake_path


def _write_lockfile(tmp_path: pathlib.Path, apm_version: str | None, *, name: str = "apm.lock.yaml") -> pathlib.Path:
    lockfile_path = tmp_path / name
    if apm_version is None:
        lockfile_path.write_text("lockfile_version: '1'\ndependencies: []\n", encoding="utf-8")
    else:
        lockfile_path.write_text(
            f"lockfile_version: '1'\napm_version: {apm_version}\ndependencies: []\n", encoding="utf-8"
        )
    return lockfile_path


# --- parse_apm_pin_version / load_apm_pin_version ---------------------------


def test_parse_apm_pin_version_finds_the_pinned_version() -> None:
    assert gate.parse_apm_pin_version(_FLAKE_SNIPPET) == "0.25.0"


def test_parse_apm_pin_version_raises_on_missing_block() -> None:
    with pytest.raises(gate.FlakePinParseError):
        gate.parse_apm_pin_version("this text has no mkClassB block at all")


def test_load_apm_pin_version_reads_a_real_file(tmp_path: pathlib.Path) -> None:
    flake_path = _write_flake(tmp_path)
    assert gate.load_apm_pin_version(flake_path) == "0.25.0"


def test_load_apm_pin_version_raises_on_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.FlakePinParseError):
        gate.load_apm_pin_version(tmp_path / "does-not-exist.nix")


def test_load_apm_pin_version_raises_on_non_utf8_bytes(tmp_path: pathlib.Path) -> None:
    flake_path = tmp_path / "flake.nix"
    flake_path.write_bytes(b"\xff\xfe not valid utf-8")
    with pytest.raises(gate.FlakePinParseError):
        gate.load_apm_pin_version(flake_path)


# --- load_lockfile_apm_version ------------------------------------------


def test_load_lockfile_apm_version_reads_the_field(tmp_path: pathlib.Path) -> None:
    lockfile_path = _write_lockfile(tmp_path, "0.25.0")
    assert gate.load_lockfile_apm_version(lockfile_path) == "0.25.0"


def test_load_lockfile_apm_version_returns_none_when_field_absent(tmp_path: pathlib.Path) -> None:
    lockfile_path = _write_lockfile(tmp_path, None)
    assert gate.load_lockfile_apm_version(lockfile_path) is None


def test_load_lockfile_apm_version_returns_none_on_empty_file(tmp_path: pathlib.Path) -> None:
    lockfile_path = tmp_path / "apm.lock.yaml"
    lockfile_path.write_text("", encoding="utf-8")
    assert gate.load_lockfile_apm_version(lockfile_path) is None


def test_load_lockfile_apm_version_raises_on_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.LockfileParseError):
        gate.load_lockfile_apm_version(tmp_path / "does-not-exist.yaml")


def test_load_lockfile_apm_version_raises_on_invalid_yaml(tmp_path: pathlib.Path) -> None:
    lockfile_path = tmp_path / "apm.lock.yaml"
    lockfile_path.write_text("apm_version: [unterminated\n", encoding="utf-8")
    with pytest.raises(gate.LockfileParseError):
        gate.load_lockfile_apm_version(lockfile_path)


def test_load_lockfile_apm_version_raises_on_non_mapping_yaml(tmp_path: pathlib.Path) -> None:
    lockfile_path = tmp_path / "apm.lock.yaml"
    lockfile_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(gate.LockfileParseError):
        gate.load_lockfile_apm_version(lockfile_path)


def test_load_lockfile_apm_version_raises_on_non_utf8_bytes(tmp_path: pathlib.Path) -> None:
    lockfile_path = tmp_path / "apm.lock.yaml"
    lockfile_path.write_bytes(b"\xff\xfe not valid utf-8")
    with pytest.raises(gate.LockfileParseError):
        gate.load_lockfile_apm_version(lockfile_path)


# --- extract_apm_version ------------------------------------------------


def test_extract_apm_version_parses_real_cli_output() -> None:
    assert gate.extract_apm_version(_REAL_APM_VERSION_OUTPUT.strip()) == "0.25.0"


def test_extract_apm_version_accepts_a_pre_release_suffix() -> None:
    """A version with a pre-release/build-metadata suffix (not strict
    N.N.N) must round-trip exactly -- the pre-fix regex only captured the
    leading N.N.N and silently dropped the suffix."""
    output = "Agent Package Manager (APM) CLI version 0.26.0-rc1 (deadbeef)"
    assert gate.extract_apm_version(output) == "0.26.0-rc1"


def test_extract_apm_version_raises_on_unrecognizable_output() -> None:
    with pytest.raises(gate.ApmVersionCheckError):
        gate.extract_apm_version("no recognizable token in this line at all")


# --- find_path_apm_version ------------------------------------------------


def test_find_path_apm_version_returns_the_parsed_version() -> None:
    def fake_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert argv == ["/usr/local/bin/apm", "--version"]
        return _completed(0, stdout=_REAL_APM_VERSION_OUTPUT)

    assert gate.find_path_apm_version("/usr/local/bin/apm", runner=fake_runner) == "0.25.0"


def test_find_path_apm_version_raises_on_nonzero_exit() -> None:
    def fake_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed(1, stderr="boom")

    with pytest.raises(gate.ApmVersionCheckError):
        gate.find_path_apm_version("/usr/local/bin/apm", runner=fake_runner)


def test_find_path_apm_version_raises_on_runner_timeout() -> None:
    def timing_out_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=30)

    with pytest.raises(gate.ApmVersionCheckError):
        gate.find_path_apm_version("/usr/local/bin/apm", runner=timing_out_runner)


def test_find_path_apm_version_raises_on_os_error() -> None:
    def failing_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise PermissionError("not executable")

    with pytest.raises(gate.ApmVersionCheckError):
        gate.find_path_apm_version("/usr/local/bin/apm", runner=failing_runner)


# --- find_drift: lockfile check -----------------------------------------


def test_find_drift_is_clean_when_lockfile_matches_and_apm_not_on_path(tmp_path: pathlib.Path) -> None:
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, "0.25.0")

    assert gate.find_drift(flake_path, lockfile_path, which=_no_apm_on_path) is None


def test_find_drift_is_clean_when_lockfile_has_no_apm_version_field(tmp_path: pathlib.Path) -> None:
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, None)

    assert gate.find_drift(flake_path, lockfile_path, which=_no_apm_on_path) is None


def test_find_drift_reports_lockfile_drift(tmp_path: pathlib.Path) -> None:
    """Regression test (issue #1817's own proof-method requirement, the
    lockfile-as-committed shape independent review flagged as this gate's
    real defect-catching signal in CI): a lockfile whose own apm_version
    field was silently downgraded by a stray bare `apm install` must be
    caught even with no `apm` on PATH at all -- exactly what a CI runner
    sees."""
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, "0.23.1")

    result = gate.find_drift(flake_path, lockfile_path, which=_no_apm_on_path)
    assert result is not None
    assert "0.23.1" in result
    assert "0.25.0" in result
    assert "apm.lock.yaml" in result


# --- find_drift: PATH-binary check ---------------------------------------


def test_find_drift_is_clean_when_apm_is_not_on_path(tmp_path: pathlib.Path) -> None:
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, "0.25.0")

    assert gate.find_drift(flake_path, lockfile_path, which=_no_apm_on_path) is None


def test_find_drift_is_clean_when_path_apm_matches_the_pin(tmp_path: pathlib.Path) -> None:
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, "0.25.0")

    def fake_which(name: str) -> str | None:
        return "/usr/local/bin/apm"

    def fake_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, stdout=_REAL_APM_VERSION_OUTPUT)

    result = gate.find_drift(flake_path, lockfile_path, which=fake_which, runner=fake_runner)
    assert result is None


def test_find_drift_reports_the_original_defect_shape(tmp_path: pathlib.Path) -> None:
    """Regression test (issue #1817's own proof-method requirement):
    reproduce the exact defect -- a PATH apm reporting the ambient system
    version (0.23.1) while flake.nix pins the newer 0.25.0 -- and confirm
    the gate FAILs with a message naming both versions."""
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, "0.25.0")

    def fake_which(name: str) -> str | None:
        return "/usr/bin/apm"

    def stale_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, stdout="Agent Package Manager (APM) CLI version 0.23.1 (abc1234)\n")

    result = gate.find_drift(flake_path, lockfile_path, which=fake_which, runner=stale_runner)
    assert result is not None
    assert "0.23.1" in result
    assert "0.25.0" in result
    assert "/usr/bin/apm" in result

    # ...and passes again once the PATH binary matches the pin (same shape
    # as the original defect's own recovery via `nix run .#apm -- install`).
    def fixed_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, stdout=_REAL_APM_VERSION_OUTPUT)

    assert gate.find_drift(flake_path, lockfile_path, which=fake_which, runner=fixed_runner) is None


def test_find_drift_propagates_a_broken_path_binary(tmp_path: pathlib.Path) -> None:
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, "0.25.0")

    def fake_which(name: str) -> str | None:
        return "/usr/bin/apm"

    def failing_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed(127, stderr="command not found")

    with pytest.raises(gate.ApmVersionCheckError):
        gate.find_drift(flake_path, lockfile_path, which=fake_which, runner=failing_runner)


def test_find_drift_reports_both_findings_together(tmp_path: pathlib.Path) -> None:
    """Both signals can independently drift at once (e.g. mid-recovery):
    the combined message names both."""
    flake_path = _write_flake(tmp_path)
    lockfile_path = _write_lockfile(tmp_path, "0.23.1")

    def fake_which(name: str) -> str | None:
        return "/usr/bin/apm"

    def stale_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed(0, stdout="Agent Package Manager (APM) CLI version 0.24.0 (cafebabe)\n")

    result = gate.find_drift(flake_path, lockfile_path, which=fake_which, runner=stale_runner)
    assert result is not None
    assert "apm.lock.yaml" in result
    assert "0.23.1" in result
    assert "/usr/bin/apm" in result
    assert "0.24.0" in result


# --- format_*_drift_message ------------------------------------------------


def test_format_path_drift_message_names_the_documented_bypass() -> None:
    message = gate.format_path_drift_message("/usr/bin/apm", "0.23.1", "0.25.0")
    assert "git push --no-verify" in message
    assert "0.23.1" in message
    assert "0.25.0" in message


def test_format_lockfile_drift_message_names_both_versions() -> None:
    message = gate.format_lockfile_drift_message("0.23.1", "0.25.0")
    assert "0.23.1" in message
    assert "0.25.0" in message
    assert "apm.lock.yaml" in message


# --- the gate itself, against this repository's real state -----------------


def test_the_gate_finds_no_drift_in_this_repository() -> None:
    assert gate.find_drift() is None


def test_main_reports_clean_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main() == 0
    assert "No apm binary version pin drift found." in capsys.readouterr().out


def test_main_reports_drift_exit_one(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate, "find_drift", lambda: "some drift message")
    assert gate.main() == 1
    assert "some drift message" in capsys.readouterr().out


def test_main_reports_a_check_error_exit_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raising_find_drift() -> str | None:
        raise gate.ApmVersionCheckError("could not run apm --version")

    monkeypatch.setattr(gate, "find_drift", raising_find_drift)
    assert gate.main() == 1
    assert "could not run apm --version" in capsys.readouterr().err

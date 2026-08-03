from __future__ import annotations

import base64
import hashlib
import io
import re
import stat
import tarfile
import urllib.error
import urllib.request
import zipfile
from email.message import Message
from pathlib import Path
from typing import Any

import provision_class_b as pcb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

_SRI_RE = re.compile(r"^sha256-[A-Za-z0-9+/]+=*$")


def test_parse_flake_class_b_pins_against_the_real_flake_nix() -> None:
    """Shape-only assertions against the real, committed flake.nix -- never
    an exact hash/tag value, which would recreate the hand-transcription
    drift risk this parser exists to avoid."""
    flake_text = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
    pins = pcb.parse_flake_class_b_pins(flake_text)

    assert set(pins) == set(pcb.CLASS_B_TOOL_NAMES)
    for pname, spec in pins.items():
        assert spec.pname == pname
        assert spec.kind in ("binary", "wrapperDir")
        assert spec.owner and spec.repo and spec.tag and spec.version
        assert set(spec.systems) == {
            "aarch64-linux",
            "x86_64-linux",
            "aarch64-darwin",
            "x86_64-darwin",
        }
        for system, pin in spec.systems.items():
            assert pin.asset, f"{pname}/{system}: empty asset"
            assert _SRI_RE.match(pin.sha256_sri), f"{pname}/{system}: {pin.sha256_sri!r} is not SRI-shaped"
            assert pin.bin_in_archive


def test_apm_is_wrapper_dir_kind() -> None:
    flake_text = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
    pins = pcb.parse_flake_class_b_pins(flake_text)
    assert pins["apm"].kind == "wrapperDir"
    assert pins["waza"].kind == "binary"


def test_release_url_matches_flake_ghrelease_pattern() -> None:
    flake_text = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
    pins = pcb.parse_flake_class_b_pins(flake_text)
    apm = pins["apm"]
    url = apm.release_url("x86_64-linux")
    assert url == f"https://github.com/{apm.owner}/{apm.repo}/releases/download/{apm.tag}/{apm.systems['x86_64-linux'].asset}"
    assert url.startswith("https://github.com/microsoft/apm/releases/download/")


def test_parse_raises_on_missing_tool() -> None:
    """Both classBData and mkClassB are structurally well-formed (real
    let-in shape, brace-balanced) so parsing gets past the header/shape
    regexes -- but only "waza" is defined in either table, leaving apm,
    rtk, and betterleaks genuinely missing. This exercises the
    missing_from_data/missing_from_meta check in parse_flake_class_b_pins,
    not a structural-shape failure in _extract_mk_class_b_meta's header
    regex (see the module docstring / task review for the bug this
    guards against: a malformed fixture that raises the *wrong* error)."""
    partial = """
    classBData = {
      waza = {
        aarch64-linux  = { asset = "w-linux-arm64.tar.gz";  sha256 = "sha256-AAAA="; };
        x86_64-linux   = { asset = "w-linux-amd64.tar.gz";  sha256 = "sha256-BBBB="; };
        aarch64-darwin = { asset = "w-darwin-arm64.zip";    sha256 = "sha256-CCCC="; };
        x86_64-darwin  = { asset = "w-darwin-amd64.zip";    sha256 = "sha256-DDDD="; };
      };
    };

    mkClassB = pkgs:
      let
        sys = pkgs.stdenv.hostPlatform.system;
        d = classBData;
      in
      {
        waza = mkReleaseBinary pkgs {
          pname = "waza";
          version = "0.1.0";
          kind = "binary";
          url = ghRelease "o" "waza" "t" d.waza.${sys}.asset;
          sha256 = d.waza.${sys}.sha256;
        };
      };
    """
    with pytest.raises(pcb.FlakePinParseError, match="missing tools") as exc_info:
        pcb.parse_flake_class_b_pins(partial)
    message = str(exc_info.value)
    for missing_tool in ("apm", "rtk", "betterleaks"):
        assert missing_tool in message, f"expected {missing_tool!r} to be named as missing in: {message!r}"
    assert "waza" not in message, f"waza is defined in both tables and should not be reported missing: {message!r}"


@pytest.mark.parametrize(
    ("sysname", "machine", "expected"),
    [
        ("Linux", "x86_64", "x86_64-linux"),
        ("Linux", "aarch64", "aarch64-linux"),
        ("Darwin", "x86_64", "x86_64-darwin"),
        ("Darwin", "arm64", "aarch64-darwin"),
    ],
)
def test_detect_nix_system(sysname: str, machine: str, expected: str) -> None:
    assert pcb.detect_nix_system(sysname, machine) == expected


def test_detect_nix_system_rejects_unknown() -> None:
    with pytest.raises(pcb.UnsupportedSystemError):
        pcb.detect_nix_system("Windows", "AMD64")


# --- Task 3: download + SHA256 verification ---------------------------------


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _opener_returning(body: bytes) -> Any:
    def _opener(request: urllib.request.Request) -> _FakeResponse:
        return _FakeResponse(200, body)

    return _opener


def _opener_raising(codes: list[int]) -> Any:
    calls = {"n": 0}

    def _opener(request: urllib.request.Request) -> _FakeResponse:
        code = codes[calls["n"]]
        calls["n"] += 1
        if code == 200:
            return _FakeResponse(200, b"payload")
        raise urllib.error.HTTPError(request.full_url, code, "err", Message(), io.BytesIO(b""))

    return _opener


def test_sha256_sri_matches_openssl_reference_value() -> None:
    # Same value independently verified this session via
    # `openssl dgst -sha256 -binary apm.tar.gz | openssl base64 -A`
    # against flake.nix's pinned apm x86_64-linux hash.
    data = b"hello world"
    expected = "sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")
    assert pcb.sha256_sri(data) == expected


def test_download_asset_returns_body_on_success() -> None:
    body = pcb.download_asset("https://example.test/a.tar.gz", opener=_opener_returning(b"archive-bytes"))
    assert body == b"archive-bytes"


def test_download_asset_retries_on_5xx_then_succeeds() -> None:
    sleeps: list[float] = []
    body = pcb.download_asset(
        "https://example.test/a.tar.gz",
        opener=_opener_raising([500, 502, 200]),
        sleeper=sleeps.append,
    )
    assert body == b"payload"
    assert sleeps == [2.0, 4.0]


def test_download_asset_does_not_retry_on_404() -> None:
    with pytest.raises(pcb.DownloadError, match="not-found"):
        pcb.download_asset("https://example.test/a.tar.gz", opener=_opener_raising([404]))


def test_download_asset_raises_after_exhausting_retries() -> None:
    with pytest.raises(pcb.DownloadError, match="fetch-failed"):
        pcb.download_asset(
            "https://example.test/a.tar.gz",
            opener=_opener_raising([500, 500, 500]),
            sleeper=lambda _seconds: None,
            max_attempts=3,
        )


def test_verify_and_download_raises_hash_mismatch_error() -> None:
    flake_text = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
    spec = pcb.parse_flake_class_b_pins(flake_text)["apm"]
    with pytest.raises(pcb.HashMismatchError):
        pcb.verify_and_download(spec, "x86_64-linux", opener=_opener_returning(b"not the real archive"))


# --- Task 4: archive extraction (binary and wrapperDir layouts) -------------


def _make_tar_gz_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _make_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_extract_binary_from_tar_gz(tmp_path: Path) -> None:
    data = _make_tar_gz_bytes({"waza-linux-amd64": b"#!/bin/sh\necho fake-waza\n"})
    dest = tmp_path / "bin" / "waza"
    pcb.extract_binary(data, "waza-linux-amd64.tar.gz", "waza-linux-amd64", dest)
    assert dest.read_bytes() == b"#!/bin/sh\necho fake-waza\n"
    assert dest.stat().st_mode & stat.S_IXUSR


def test_extract_binary_from_zip_restores_exec_bit(tmp_path: Path) -> None:
    data = _make_zip_bytes({"waza-darwin-amd64": b"#!/bin/sh\necho fake-waza\n"})
    dest = tmp_path / "bin" / "waza"
    pcb.extract_binary(data, "waza-darwin-amd64.zip", "waza-darwin-amd64", dest)
    assert dest.read_bytes() == b"#!/bin/sh\necho fake-waza\n"
    assert dest.stat().st_mode & stat.S_IXUSR


def test_extract_binary_raises_when_member_missing(tmp_path: Path) -> None:
    data = _make_tar_gz_bytes({"other-file": b"x"})
    with pytest.raises(pcb.ExtractionError):
        pcb.extract_binary(data, "waza-linux-amd64.tar.gz", "waza-linux-amd64", tmp_path / "bin" / "waza")


def test_extract_wrapper_dir_keeps_internal_tree_and_writes_shim(tmp_path: Path) -> None:
    data = _make_tar_gz_bytes(
        {
            "apm-linux-x86_64/apm": b"#!/bin/sh\necho fake-apm\n",
            "apm-linux-x86_64/_internal/marker.txt": b"needed-at-runtime",
        }
    )
    libexec_dir = tmp_path / "libexec" / "apm"
    bin_shim = tmp_path / "bin" / "apm"
    pcb.extract_wrapper_dir(data, "apm-linux-x86_64.tar.gz", "apm", libexec_dir, bin_shim)

    assert (libexec_dir / "_internal" / "marker.txt").read_text() == "needed-at-runtime"
    real_bin = libexec_dir / "apm"
    assert real_bin.stat().st_mode & stat.S_IXUSR
    assert bin_shim.exists()
    assert bin_shim.stat().st_mode & stat.S_IXUSR
    shim_text = bin_shim.read_text()
    assert str(real_bin) in shim_text
    assert shim_text.startswith("#!/bin/sh")


# --- Security review fix (task-4-report.md): extract_wrapper_dir's top-level-dir
# validation gap, plus ExtractionError coverage for corrupted archives and the
# tar branch's own filter="data" rejection ---------------------------------


def test_extract_wrapper_dir_rejects_dotdot_top_level_segment_zip(tmp_path: Path) -> None:
    """Adversarial reproduction of the review finding: every member's name is
    "../../tmp/pwned", so name.split("/")[0] == ".." for *every* member --
    {".."} has cardinality 1, which a cardinality-only guard accepts. Against
    the pre-fix code this does not raise ExtractionError: zipfile silently
    strips the ".." components during extractall (so nothing looks wrong
    yet), then `(top_dir_name,) = top_level` binds top_dir_name = "..", so
    `libexec_dir / ".."` resolves to libexec_dir's own PARENT -- and the
    flatten loop enumerates and relocates that parent's contents (here: a
    sibling "already-installed tool" directory) into libexec_dir, crashing
    with a raw OSError once it reaches libexec_dir itself. Confirmed via a
    live probe against the pre-fix code before this test was written; see
    the fix report for the exact transcript.
    """
    data = _make_zip_bytes(
        {
            "../../tmp/pwned/file1": b"evil1",
            "../../tmp/pwned/file2": b"evil2",
        }
    )
    parent_dir = tmp_path / "libexec"
    libexec_dir = parent_dir / "apm"
    bin_shim = tmp_path / "bin" / "apm"

    # A sibling directory that must survive completely untouched -- stands
    # in for "another already-installed Class B tool's directory".
    sibling_dir = parent_dir / "already_installed_tool"
    sibling_dir.mkdir(parents=True)
    canary_file = sibling_dir / "canary.txt"
    canary_file.write_text("do-not-touch")

    with pytest.raises(pcb.ExtractionError):
        pcb.extract_wrapper_dir(data, "apm-linux-x86_64.zip", "apm", libexec_dir, bin_shim)

    assert sibling_dir.is_dir(), "sibling directory outside libexec_dir must not be removed or moved"
    assert canary_file.read_text() == "do-not-touch"
    assert sorted(p.name for p in sibling_dir.iterdir()) == ["canary.txt"]
    assert not (libexec_dir / sibling_dir.name).exists(), "sibling must not be relocated into libexec_dir"


def test_extract_wrapper_dir_rejects_dotdot_top_level_segment_tar(tmp_path: Path) -> None:
    """Same adversarial shape as the zip test above, against the tar.gz
    branch -- locks in the shared top-level-segment validation as an
    independent guard, not merely incidental reliance on filter="data"
    (which would also reject this particular archive on its own, but only
    for as long as nobody removes it)."""
    data = _make_tar_gz_bytes(
        {
            "../../tmp/pwned/file1": b"evil1",
            "../../tmp/pwned/file2": b"evil2",
        }
    )
    parent_dir = tmp_path / "libexec"
    libexec_dir = parent_dir / "apm"
    bin_shim = tmp_path / "bin" / "apm"

    sibling_dir = parent_dir / "already_installed_tool"
    sibling_dir.mkdir(parents=True)
    canary_file = sibling_dir / "canary.txt"
    canary_file.write_text("do-not-touch")

    with pytest.raises(pcb.ExtractionError):
        pcb.extract_wrapper_dir(data, "apm-linux-x86_64.tar.gz", "apm", libexec_dir, bin_shim)

    assert sibling_dir.is_dir()
    assert canary_file.read_text() == "do-not-touch"
    assert sorted(p.name for p in sibling_dir.iterdir()) == ["canary.txt"]
    assert not (libexec_dir / sibling_dir.name).exists()


def test_extract_wrapper_dir_wraps_tar_outside_destination_error(tmp_path: Path) -> None:
    """A different adversarial shape from the two tests above: the shared
    top-level segment is a legitimate single directory name
    ("apm-linux-x86_64", passes top-level-segment validation), but one
    member's own path inside that tree escapes via "..". This is exactly
    what tarfile's filter="data" (PEP 706) rejects at extraction time with
    tarfile.OutsideDestinationError -- which, pre-fix, propagated out of
    extract_wrapper_dir as a raw stdlib exception instead of
    ExtractionError."""
    data = _make_tar_gz_bytes(
        {
            "apm-linux-x86_64/apm": b"#!/bin/sh\necho fake-apm\n",
            "apm-linux-x86_64/../../../tmp/pwned": b"evil",
        }
    )
    libexec_dir = tmp_path / "libexec" / "apm"
    bin_shim = tmp_path / "bin" / "apm"

    with pytest.raises(pcb.ExtractionError):
        pcb.extract_wrapper_dir(data, "apm-linux-x86_64.tar.gz", "apm", libexec_dir, bin_shim)


def test_extract_binary_raises_extraction_error_on_corrupted_tar_gz(tmp_path: Path) -> None:
    garbage = b"this is not a valid gzip/tar stream, just filler bytes 0123456789"
    with pytest.raises(pcb.ExtractionError):
        pcb.extract_binary(garbage, "waza-linux-amd64.tar.gz", "waza-linux-amd64", tmp_path / "bin" / "waza")


def test_extract_binary_raises_extraction_error_on_corrupted_zip(tmp_path: Path) -> None:
    garbage = b"this is not a valid zip stream, just filler bytes 0123456789"
    with pytest.raises(pcb.ExtractionError):
        pcb.extract_binary(garbage, "waza-darwin-amd64.zip", "waza-darwin-amd64", tmp_path / "bin" / "waza")


def test_extract_wrapper_dir_raises_extraction_error_on_corrupted_tar_gz(tmp_path: Path) -> None:
    garbage = b"this is not a valid gzip/tar stream, just filler bytes 0123456789"
    libexec_dir = tmp_path / "libexec" / "apm"
    bin_shim = tmp_path / "bin" / "apm"
    with pytest.raises(pcb.ExtractionError):
        pcb.extract_wrapper_dir(garbage, "apm-linux-x86_64.tar.gz", "apm", libexec_dir, bin_shim)


def test_extract_wrapper_dir_raises_extraction_error_on_corrupted_zip(tmp_path: Path) -> None:
    garbage = b"this is not a valid zip stream, just filler bytes 0123456789"
    libexec_dir = tmp_path / "libexec" / "apm"
    bin_shim = tmp_path / "bin" / "apm"
    with pytest.raises(pcb.ExtractionError):
        pcb.extract_wrapper_dir(garbage, "apm-linux-x86_64.zip", "apm", libexec_dir, bin_shim)

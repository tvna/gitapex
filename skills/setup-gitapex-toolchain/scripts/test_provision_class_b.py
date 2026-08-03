from __future__ import annotations

import base64
import hashlib
import io
import re
import urllib.error
import urllib.request
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
    assert len(sleeps) == 2


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

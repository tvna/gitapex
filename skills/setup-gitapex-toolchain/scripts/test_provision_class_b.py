from __future__ import annotations

import re
from pathlib import Path

import pytest

import provision_class_b as pcb

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
    truncated = """
    classBData = {
      waza = {
        x86_64-linux = { asset = "w.tar.gz"; sha256 = "sha256-AAAA="; };
      };
    };
    mkClassB = pkgs: {
      waza = mkReleaseBinary pkgs {
        pname = "waza";
        version = "0.1.0";
        kind = "binary";
        url = ghRelease "o" "r" "t" d.waza.${sys}.asset;
        sha256 = d.waza.${sys}.sha256;
      };
    };
    """
    with pytest.raises(pcb.FlakePinParseError):
        pcb.parse_flake_class_b_pins(truncated)


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

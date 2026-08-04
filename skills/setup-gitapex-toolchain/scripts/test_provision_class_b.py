from __future__ import annotations

import base64
import hashlib
import io
import re
import stat
import subprocess
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


# --- Task 5: idempotency receipts + orchestration ----------------------------


def _fake_runner_success(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=("fake",), returncode=0, stdout="0.25.0\n", stderr="")


def _real_apm_spec() -> pcb.ClassBToolSpec:
    flake_text = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
    return pcb.parse_flake_class_b_pins(flake_text)["apm"]


def test_provision_tool_installs_then_skips_on_second_call(tmp_path: Path) -> None:
    spec = _real_apm_spec()
    # Build a fake archive whose bytes we can make match the real pin by
    # constructing it, hashing it, and monkeypatching the spec's pin --
    # simpler: build a real archive and re-derive a spec with our own pin.
    data = _make_tar_gz_bytes(
        {"apm-linux-x86_64/apm": b"#!/bin/sh\necho fake-apm\n", "apm-linux-x86_64/_internal/x": b"y"}
    )
    fake_pin = pcb.ClassBSystemPin(asset="apm-linux-x86_64.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive="apm")
    fake_spec = pcb.ClassBToolSpec(
        pname="apm", version="0.25.0", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag,
        systems={"x86_64-linux": fake_pin},
    )

    calls = {"n": 0}

    def opener(request: urllib.request.Request) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(200, data)

    result1 = pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=opener, sleeper=lambda _s: None, runner=_fake_runner_success)
    assert result1.status == "installed"
    assert calls["n"] == 1

    result2 = pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=opener, sleeper=lambda _s: None, runner=_fake_runner_success)
    assert result2.status == "skipped"
    assert calls["n"] == 1  # no second network call


def test_provision_tool_reinstalls_when_pin_changes(tmp_path: Path) -> None:
    spec = _real_apm_spec()
    data_v1 = _make_tar_gz_bytes({"apm-linux-x86_64/apm": b"v1", "apm-linux-x86_64/_internal/x": b"y"})
    data_v2 = _make_tar_gz_bytes({"apm-linux-x86_64/apm": b"v2", "apm-linux-x86_64/_internal/x": b"y"})

    pin_v1 = pcb.ClassBSystemPin(asset="apm.tar.gz", sha256_sri=pcb.sha256_sri(data_v1), bin_in_archive="apm")
    spec_v1 = pcb.ClassBToolSpec(pname="apm", version="1", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin_v1})
    pcb.provision_tool(spec_v1, "x86_64-linux", tmp_path, opener=lambda r: _FakeResponse(200, data_v1), sleeper=lambda _s: None, runner=_fake_runner_success)

    pin_v2 = pcb.ClassBSystemPin(asset="apm.tar.gz", sha256_sri=pcb.sha256_sri(data_v2), bin_in_archive="apm")
    spec_v2 = pcb.ClassBToolSpec(pname="apm", version="2", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin_v2})
    result = pcb.provision_tool(spec_v2, "x86_64-linux", tmp_path, opener=lambda r: _FakeResponse(200, data_v2), sleeper=lambda _s: None, runner=_fake_runner_success)

    assert result.status == "installed"
    assert (tmp_path / "libexec" / "apm" / "apm").read_bytes() == b"v2"


def test_provision_all_continues_past_one_tool_failure(tmp_path: Path) -> None:
    """NOTE on a deviation from the plan brief's literal text: the brief's own
    version of this test reused the REAL parsed `tools["waza"]` spec (real
    flake.nix sha256 pin) together with a locally-fabricated one-byte archive
    body for waza's response -- those can never match (verified: it raised
    HashMismatchError for waza too, the same failure mode as apm's 404, so
    the test could not actually have exercised the "one tool fails, the other
    still installs" behavior it claims to). Fixed by deriving waza's pin from
    the fabricated body's own hash (same pattern the brief's other two Step 1
    tests already use for apm), while still resolving apm/waza's owner/repo/
    tag from the real flake.nix parse so the produced URLs are realistic."""
    flake_text = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
    real_tools = pcb.parse_flake_class_b_pins(flake_text)
    real_waza_pin = real_tools["waza"].systems["x86_64-linux"]
    waza_data = _make_tar_gz_bytes({real_waza_pin.bin_in_archive: b"x"})
    fake_waza_pin = pcb.ClassBSystemPin(
        asset=real_waza_pin.asset, sha256_sri=pcb.sha256_sri(waza_data), bin_in_archive=real_waza_pin.bin_in_archive
    )
    fake_waza_spec = pcb.ClassBToolSpec(
        pname="waza", version=real_tools["waza"].version, kind="binary",
        owner=real_tools["waza"].owner, repo=real_tools["waza"].repo, tag=real_tools["waza"].tag,
        systems={"x86_64-linux": fake_waza_pin},
    )
    tools = {"apm": real_tools["apm"], "waza": fake_waza_spec}

    def failing_opener(request: urllib.request.Request) -> _FakeResponse:
        if "apm" in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 404, "not found", Message(), io.BytesIO(b""))
        return _FakeResponse(200, waza_data)

    results = pcb.provision_all(
        tools,
        "x86_64-linux",
        tmp_path,
        opener=failing_opener,
        sleeper=lambda _s: None,
        runner=_fake_runner_success,
    )
    assert isinstance(results["apm"], Exception)
    assert isinstance(results["waza"], pcb.ProvisionResult)
    assert results["waza"].status == "installed"


# --- Task 5 supplemental: receipt/idempotency edge cases not in the brief's
# own Step 1 list -- corrupted receipt files, a receipt that matches the pin
# but whose binary was manually removed, the force= override, the fail-closed
# behavior on a failed post-install smoke test, and provision_all's `only`
# filter. Each is called out explicitly because provision_tool/provision_all
# are the exact contract Tasks 6-7 build their CLI orchestration on top of. --


def test_provision_tool_treats_syntactically_invalid_receipt_as_not_installed(tmp_path: Path) -> None:
    """A receipt file that isn't even valid JSON (e.g. truncated by a prior
    crash mid-write) must be treated as "no receipt", not raise out of
    provision_tool -- json.JSONDecodeError is a real, reachable failure mode
    for a hand-rolled state file, not a hypothetical."""
    spec = _real_apm_spec()
    data = _make_tar_gz_bytes({"apm-linux-x86_64/apm": b"binary-content", "apm-linux-x86_64/_internal/x": b"y"})
    pin = pcb.ClassBSystemPin(asset="apm.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive="apm")
    fake_spec = pcb.ClassBToolSpec(pname="apm", version="0.25.0", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin})

    receipt_path = tmp_path / "state" / "apm.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text("{not valid json at all", encoding="utf-8")

    result = pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=lambda r: _FakeResponse(200, data), sleeper=lambda _s: None, runner=_fake_runner_success)
    assert result.status == "installed"
    assert (tmp_path / "bin" / "apm").exists()


def test_provision_tool_treats_receipt_missing_fields_as_not_installed(tmp_path: Path) -> None:
    """Well-formed JSON but missing a required key (e.g. a receipt written by
    an older/different schema) is a distinct failure mode from a syntax
    error -- KeyError, not JSONDecodeError -- and must be handled the same
    way: treated as absent, not raised."""
    spec = _real_apm_spec()
    data = _make_tar_gz_bytes({"apm-linux-x86_64/apm": b"binary-content", "apm-linux-x86_64/_internal/x": b"y"})
    pin = pcb.ClassBSystemPin(asset="apm.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive="apm")
    fake_spec = pcb.ClassBToolSpec(pname="apm", version="0.25.0", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin})

    receipt_path = tmp_path / "state" / "apm.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text('{"pname": "apm"}', encoding="utf-8")  # missing version/sha256_sri/asset

    result = pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=lambda r: _FakeResponse(200, data), sleeper=lambda _s: None, runner=_fake_runner_success)
    assert result.status == "installed"


def test_provision_tool_reinstalls_when_installed_binary_was_manually_deleted(tmp_path: Path) -> None:
    """A valid receipt whose sha256/asset still match the current pin is not
    sufficient on its own -- if the binary file itself is gone (a human
    `rm`'d it, or a prior run crashed after writing the receipt but before/
    during extraction), the tool must be reinstalled, not silently reported
    as already present."""
    spec = _real_apm_spec()
    data = _make_tar_gz_bytes({"apm-linux-x86_64/apm": b"binary-content", "apm-linux-x86_64/_internal/x": b"y"})
    pin = pcb.ClassBSystemPin(asset="apm.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive="apm")
    fake_spec = pcb.ClassBToolSpec(pname="apm", version="0.25.0", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin})

    calls = {"n": 0}

    def opener(request: urllib.request.Request) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(200, data)

    result1 = pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=opener, sleeper=lambda _s: None, runner=_fake_runner_success)
    assert result1.status == "installed"
    assert calls["n"] == 1

    (tmp_path / "bin" / "apm").unlink()
    assert (tmp_path / "state" / "apm.json").exists(), "receipt must survive the binary's removal for this to be a real test"

    result2 = pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=opener, sleeper=lambda _s: None, runner=_fake_runner_success)
    assert result2.status == "installed"
    assert calls["n"] == 2  # re-downloaded, not skipped
    assert (tmp_path / "bin" / "apm").exists()


def test_provision_tool_force_reinstalls_even_when_already_installed(tmp_path: Path) -> None:
    spec = _real_apm_spec()
    data = _make_tar_gz_bytes({"apm-linux-x86_64/apm": b"binary-content", "apm-linux-x86_64/_internal/x": b"y"})
    pin = pcb.ClassBSystemPin(asset="apm.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive="apm")
    fake_spec = pcb.ClassBToolSpec(pname="apm", version="0.25.0", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin})

    calls = {"n": 0}

    def opener(request: urllib.request.Request) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(200, data)

    pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=opener, sleeper=lambda _s: None, runner=_fake_runner_success)
    assert calls["n"] == 1

    result = pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=opener, sleeper=lambda _s: None, runner=_fake_runner_success, force=True)
    assert result.status == "installed"
    assert calls["n"] == 2  # force bypasses the receipt-based skip entirely


def test_provision_tool_does_not_write_receipt_when_verify_fails(tmp_path: Path) -> None:
    """Fail-closed check: if the post-extraction `--version` smoke test
    fails, no receipt may be written -- otherwise a later run would read
    back a receipt claiming a tool that never actually passed verification
    is installed."""
    spec = _real_apm_spec()
    data = _make_tar_gz_bytes({"apm-linux-x86_64/apm": b"binary-content", "apm-linux-x86_64/_internal/x": b"y"})
    pin = pcb.ClassBSystemPin(asset="apm.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive="apm")
    fake_spec = pcb.ClassBToolSpec(pname="apm", version="0.25.0", kind="wrapperDir", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin})

    def failing_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("fake",), returncode=1, stdout="", stderr="boom")

    with pytest.raises(pcb.VerifyError):
        pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=lambda r: _FakeResponse(200, data), sleeper=lambda _s: None, runner=failing_runner)

    assert not (tmp_path / "state" / "apm.json").exists()


def test_provision_tool_raises_extraction_error_on_unknown_kind(tmp_path: Path) -> None:
    spec = _real_apm_spec()
    data = _make_tar_gz_bytes({"weird": b"x"})
    pin = pcb.ClassBSystemPin(asset="weird.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive="weird")
    fake_spec = pcb.ClassBToolSpec(pname="weird", version="1", kind="mystery-kind", owner=spec.owner, repo=spec.repo, tag=spec.tag, systems={"x86_64-linux": pin})

    with pytest.raises(pcb.ExtractionError):
        pcb.provision_tool(fake_spec, "x86_64-linux", tmp_path, opener=lambda r: _FakeResponse(200, data), sleeper=lambda _s: None, runner=_fake_runner_success)


def test_provision_all_only_filters_to_selected_tools(tmp_path: Path) -> None:
    """only= must narrow which tools are even attempted, not just which
    results are returned afterward. Verified by giving the excluded tool a
    URL the opener refuses to serve (raises AssertionError) -- if `only`
    filtered post-hoc instead of up front, the excluded tool would still be
    fetched, and that AssertionError would surface as an unexpected
    `"excluded"` key in the results dict, failing the set(results) assertion
    below."""

    def make_binary_spec(pname: str, body: bytes) -> tuple[pcb.ClassBToolSpec, bytes]:
        data = _make_tar_gz_bytes({pname: body})
        pin = pcb.ClassBSystemPin(asset=f"{pname}.tar.gz", sha256_sri=pcb.sha256_sri(data), bin_in_archive=pname)
        spec = pcb.ClassBToolSpec(pname=pname, version="1", kind="binary", owner="o", repo=pname, tag="t", systems={"x86_64-linux": pin})
        return spec, data

    waza_spec, waza_data = make_binary_spec("waza", b"waza-content")
    rtk_spec, rtk_data = make_binary_spec("rtk", b"rtk-content")
    excluded_spec, _excluded_data = make_binary_spec("excluded", b"excluded-content")
    tools = {"waza": waza_spec, "rtk": rtk_spec, "excluded": excluded_spec}
    data_by_url = {
        waza_spec.release_url("x86_64-linux"): waza_data,
        rtk_spec.release_url("x86_64-linux"): rtk_data,
    }

    def opener(request: urllib.request.Request) -> _FakeResponse:
        if request.full_url not in data_by_url:
            raise AssertionError(f"unexpected url requested (excluded tool should never be fetched): {request.full_url}")
        return _FakeResponse(200, data_by_url[request.full_url])

    results = pcb.provision_all(
        tools,
        "x86_64-linux",
        tmp_path,
        opener=opener,
        sleeper=lambda _s: None,
        runner=_fake_runner_success,
        only=("waza", "rtk"),
    )
    assert set(results) == {"waza", "rtk"}
    for result in results.values():
        assert isinstance(result, pcb.ProvisionResult)
        assert result.status == "installed"


# --- Task 6: apm install invocation + PATH env-file writing -----------------


def test_run_apm_install_raises_if_apm_yml_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        pcb.run_apm_install(tmp_path, tmp_path / "bin" / "apm", runner=_fake_runner_success)


def test_run_apm_install_invokes_absolute_binary_path(tmp_path: Path) -> None:
    (tmp_path / "apm.yml").write_text("name: x\nversion: 0.1.0\n", encoding="utf-8")
    apm_binary = tmp_path / "bin" / "apm"
    apm_binary.parent.mkdir(parents=True)
    apm_binary.write_text("#!/bin/sh\n", encoding="utf-8")

    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Installed 2 APM dependencies", stderr="")

    result = pcb.run_apm_install(tmp_path, apm_binary, runner=runner)
    assert result.returncode == 0
    assert calls == [[str(apm_binary), "install"]]


def test_run_apm_install_raises_on_nonzero_exit(tmp_path: Path) -> None:
    (tmp_path / "apm.yml").write_text("name: x\nversion: 0.1.0\n", encoding="utf-8")
    apm_binary = tmp_path / "bin" / "apm"
    apm_binary.parent.mkdir(parents=True)
    apm_binary.write_text("#!/bin/sh\n", encoding="utf-8")

    def failing_runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="boom")

    with pytest.raises(pcb.ApmInstallError, match="boom"):
        pcb.run_apm_install(tmp_path, apm_binary, runner=failing_runner)


def test_write_env_file_appends_path_export(tmp_path: Path) -> None:
    env_file = tmp_path / "env.sh"
    env_file.write_text("export FOO=bar\n", encoding="utf-8")
    cache_root = tmp_path / "cache"

    pcb.write_env_file(env_file, cache_root)

    content = env_file.read_text(encoding="utf-8")
    assert "export FOO=bar" in content
    assert f'export PATH="{cache_root / "bin"}:$PATH"' in content


def test_write_env_file_is_idempotent(tmp_path: Path) -> None:
    env_file = tmp_path / "env.sh"
    cache_root = tmp_path / "cache"
    pcb.write_env_file(env_file, cache_root)
    pcb.write_env_file(env_file, cache_root)
    content = env_file.read_text(encoding="utf-8")
    assert content.count(str(cache_root / "bin")) == 1


def test_write_env_file_noop_when_none() -> None:
    pcb.write_env_file(None, Path("/does/not/matter"))  # must not raise


# --- Task 6 supplemental: a stricter never-invoked guarantee for the missing-
# apm.yml guard, and the exact kwargs run_apm_install passes to the runner --
# called out explicitly because Task 7's CLI wiring depends on both: cwd
# correctness matters for `apm install` to actually run against the right
# project directory, and the missing-apm.yml guard must hold even under a
# runner that would otherwise report success. -------------------------------


def test_run_apm_install_never_invokes_runner_when_apm_yml_missing(tmp_path: Path) -> None:
    """The brief's own test above (test_run_apm_install_raises_if_apm_yml_missing)
    only proves FileNotFoundError is *eventually* raised -- it would still
    pass even if a bug called the runner before checking apm.yml, because
    _fake_runner_success always reports success and the missing-apm.yml
    check would still fire afterward on the way out. This test uses a
    runner that fails the test immediately if invoked at all, so it can only
    pass if the guard runs strictly before any subprocess call."""

    def runner_that_must_not_be_called(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("run_apm_install must not invoke the runner when apm.yml is missing")

    with pytest.raises(FileNotFoundError):
        pcb.run_apm_install(tmp_path, tmp_path / "bin" / "apm", runner=runner_that_must_not_be_called)


def test_run_apm_install_passes_cwd_and_expected_kwargs(tmp_path: Path) -> None:
    (tmp_path / "apm.yml").write_text("name: x\nversion: 0.1.0\n", encoding="utf-8")
    apm_binary = tmp_path / "bin" / "apm"
    apm_binary.parent.mkdir(parents=True)
    apm_binary.write_text("#!/bin/sh\n", encoding="utf-8")

    received_kwargs: dict[str, object] = {}

    def runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        received_kwargs.update(kwargs)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    pcb.run_apm_install(tmp_path, apm_binary, runner=runner)
    assert received_kwargs["cwd"] == str(tmp_path)
    assert received_kwargs["capture_output"] is True
    assert received_kwargs["text"] is True
    assert received_kwargs["timeout"] == 120
    assert received_kwargs["check"] is False


# --- Task 7: CLI entry point -------------------------------------------------


def test_main_verify_mode_reports_missing_binaries_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapted from the brief's own given test: the brief patches
    ``pcb._default_opener`` directly, but verified empirically (live,
    against this real module, before writing this test) that doing so does
    NOT intercept calls made through provision_all/download_asset/
    verify_and_download's own ``opener`` parameter -- Python binds a
    function's default argument value ONCE, at ``def`` time (module
    import), so those functions' already-bound default keeps referencing
    the ORIGINAL ``_default_opener`` object regardless of a later
    ``monkeypatch.setattr(pcb, "_default_opener", ...)`` rebinding the
    module attribute. Confirmed live: ``pcb.provision_all.__defaults__[0]
    is <the original _default_opener>`` stays True even after the module
    attribute is reassigned. As literally written, the brief's guard is
    inert for this specific main() (whose --verify branch never calls
    provision_all/download_asset at all) but would silently fail to catch
    a regression that reintroduced such a call, and would then make a REAL
    network request during what must be an offline test. Two guards that
    are genuinely effective instead: (1) urllib.request.urlopen is looked
    up dynamically at CALL time inside _default_opener's own body, so
    patching it there intercepts every possible path to a real network
    call regardless of which bound copy of _default_opener is invoked;
    (2) provision_all is itself a bare global name main() resolves fresh
    at call time (not a default argument), so patching it directly and
    asserting it is never invoked proves --verify structurally never
    reaches the provisioning/download code at all -- the same, already-
    reliable pattern the brief's own
    test_main_skip_apm_install_flag_prevents_apm_install_call test uses
    for provision_all/run_apm_install below.
    """
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    monkeypatch.setattr(
        pcb.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network call in --verify mode")),
    )
    monkeypatch.setattr(
        pcb,
        "provision_all",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("--verify must never call provision_all")),
    )
    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--verify",
        ]
    )
    assert exit_code == 1  # nothing installed yet in this empty tmp_path cache


def test_main_skip_apm_install_flag_prevents_apm_install_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result = {"apm": pcb.ProvisionResult(pname="apm", status="installed", version_output="0.25.0")}
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)
    calls: list[object] = []
    monkeypatch.setattr(pcb, "run_apm_install", lambda *args, **kwargs: calls.append(args))

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--skip-apm-install",
        ]
    )
    assert exit_code == 0
    assert calls == []  # run_apm_install must not be called when --skip-apm-install is passed


# --- Task 7 supplemental: coverage for every main() control-flow branch named
# in the task's own "While you work" trace-through list, none of which the
# brief's two given tests above reach: --verify with everything installed AND
# passing, --verify's own failing-`--version` branch, apm provisioning itself
# failing (must skip apm install, not crash or silently retry), the positive-
# control mirror of --skip-apm-install (run_apm_install really is called when
# nothing prevents it -- the brief's own skip-flag test alone would still pass
# a main() that hard-codes "never call run_apm_install"), one tool failing
# without aborting the whole run, and a flake.nix that fails to load at all
# short-circuiting before any provisioning is attempted. -----------------------


def _write_version_script(path: Path, output: str, returncode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho '{output}'\nexit {returncode}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_main_verify_mode_all_installed_and_passing_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    _write_version_script(tmp_path / "bin" / "waza", "waza version 0.38.0", 0)
    _write_version_script(tmp_path / "bin" / "apm", "apm version 0.25.0", 0)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "waza",
            "--tool", "apm",
            "--verify",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "PASS: waza: waza version 0.38.0" in out
    assert "PASS: apm: apm version 0.25.0" in out


def test_main_verify_mode_reports_failing_version_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    _write_version_script(tmp_path / "bin" / "waza", "boom", 1)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "waza",
            "--verify",
        ]
    )
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "FAIL: waza: --version exited 1" in out


def test_main_apm_provisioning_failure_skips_apm_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """apm itself failing to provision (an Exception in provision_all's
    result dict, e.g. a real HashMismatchError/DownloadError) must be
    treated the same as apm being absent -- run_apm_install must never be
    invoked, and the run must still report failure overall. Explicitly
    named in this task's own "While you work" guidance as a scenario to
    trace through; neither of the brief's two given tests exercises it."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result: dict[str, pcb.ProvisionResult | Exception] = {
        "waza": pcb.ProvisionResult(pname="waza", status="installed", version_output="0.38.0"),
        "apm": pcb.DownloadError("simulated: apm release asset fetch failed after retries"),
    }
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)

    def runner_that_must_not_be_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("run_apm_install must not be called when apm itself failed to provision")

    monkeypatch.setattr(pcb, "run_apm_install", runner_that_must_not_be_called)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
        ]
    )
    assert exit_code == 1


def test_main_tool_filter_excluding_apm_is_not_counted_as_apm_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task review finding (093c065): a --tool filter that narrows selection
    away from "apm" entirely (e.g. --tool waza, with no --skip-apm-install)
    must NOT be treated as "apm failed to provision". apm was never
    requested at all, so provision_all's own `only` filter never attempts
    it and results.get("apm") is None (not a key in results) --
    isinstance(None, ProvisionResult) is False, the same shape as a genuine
    apm failure. Pre-fix, main() could not tell these two cases apart, so it
    printed the misleading "apm itself was not successfully provisioned"
    message and counted a failure even though nothing the caller actually
    requested (waza) failed -- contradicting SKILL.md's own "a non-zero exit
    code if anything failed" contract. This must return exit code 0 and
    must never invoke run_apm_install."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result: dict[str, pcb.ProvisionResult | Exception] = {
        "waza": pcb.ProvisionResult(pname="waza", status="installed", version_output="0.38.0"),
    }
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)

    def runner_that_must_not_be_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("run_apm_install must not be called when apm is excluded by --tool")

    monkeypatch.setattr(pcb, "run_apm_install", runner_that_must_not_be_called)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "waza",
        ]
    )
    assert exit_code == 0


def test_main_runs_apm_install_and_writes_env_file_when_not_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive-control mirror of
    test_main_skip_apm_install_flag_prevents_apm_install_call: that test
    alone only proves run_apm_install is NOT called when the flag IS
    passed -- a main() that (buggily) never calls run_apm_install at all,
    flag or no flag, would still pass it (``calls == []`` is satisfied
    either way). This test proves the opposite branch is genuinely
    reachable: when --skip-apm-install is absent and apm provisioned
    successfully, run_apm_install really is invoked, with the just-
    provisioned apm's own absolute binary path and the real project dir --
    and write_env_file really runs. Verified via deliberate bug injection:
    temporarily forcing main()'s ``if not args.skip_apm_install:`` guard to
    ``if False:`` left the brief's own skip-flag test passing while this
    test correctly failed; reverted immediately after confirming (see
    task-7-report.md)."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result: dict[str, pcb.ProvisionResult | Exception] = {
        "apm": pcb.ProvisionResult(pname="apm", status="installed", version_output="0.25.0"),
    }
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(pcb, "run_apm_install", lambda *args, **kwargs: calls.append(args))

    env_file = tmp_path / "env.sh"
    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "apm",
            "--env-file", str(env_file),
        ]
    )
    assert exit_code == 0
    assert len(calls) == 1
    called_project_dir, called_apm_binary = calls[0]
    assert called_project_dir == REPO_ROOT
    assert called_apm_binary == pcb._installed_bin_path(tmp_path, "apm")
    assert env_file.exists()
    assert f'export PATH="{tmp_path / "bin"}:$PATH"' in env_file.read_text(encoding="utf-8")


def test_main_reports_tool_provisioning_failure_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One tool failing (an Exception from provision_all) must not crash
    main() or silently swallow the other tool's outcome -- both are
    reported, and the overall run still fails."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result: dict[str, pcb.ProvisionResult | Exception] = {
        "waza": pcb.ProvisionResult(pname="waza", status="installed", version_output="0.38.0"),
        "rtk": pcb.HashMismatchError("simulated: rtk sha256 mismatch"),
    }
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--skip-apm-install",
        ]
    )
    assert exit_code == 1  # rtk's failure alone must fail the run even though waza succeeded


def test_main_returns_1_when_flake_pins_cannot_be_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)

    def must_not_be_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("provision_all must not be called when flake pins fail to load")

    monkeypatch.setattr(pcb, "provision_all", must_not_be_called)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--flake-path", str(tmp_path / "does-not-exist-flake.nix"),
            "--system", "x86_64-linux",
        ]
    )
    assert exit_code == 1


def test_main_returns_1_when_flake_path_is_a_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real gap found by testing main() against actual filesystem behavior
    (not merely a nonexistent path, which FileNotFoundError already
    covers): a --flake-path that resolves to a directory raises
    IsADirectoryError from Path.read_text() inside load_flake_class_b_pins.
    IsADirectoryError is an OSError subclass, not a FileNotFoundError
    subclass -- verified live: main(), as given by the brief
    (``except (FlakePinParseError, FileNotFoundError)``), let this
    propagate as an uncaught traceback instead of the clean
    ``FAIL: could not load Class B pins from ...`` message every other
    load-error path in main() produces. A misdirected --flake-path (e.g. a
    typo'd directory instead of a file) is plausible human error, so this
    is handled the same way as the missing-file case rather than crashing."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)

    def must_not_be_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("provision_all must not be called when flake pins fail to load")

    monkeypatch.setattr(pcb, "provision_all", must_not_be_called)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--flake-path", str(tmp_path),  # a directory, not a file
            "--system", "x86_64-linux",
        ]
    )
    assert exit_code == 1


# --- Final whole-branch review fixes (final-review-fix-report.md): three
# gaps in main()'s exception-handling contract -- every failure mode must
# print a FAIL: line and set a non-zero exit code, never an uncaught
# traceback and never a silent success when something was actually
# skipped/invalid. -------------------------------------------------------


def test_main_treats_empty_env_file_string_as_not_provided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 1: .claude/hooks/session-start.sh passes
    `--env-file "${CLAUDE_ENV_FILE:-}"`; when CLAUDE_ENV_FILE is unset, bash
    expands the unset-with-default form to a literal empty argument, so
    main() receives `--env-file ""`. Plain `type=Path` turns "" into
    Path("") == PosixPath(".") (the process's cwd), not None --
    write_env_file(Path("."), ...) then calls .read_text() on a directory
    and raises an uncaught IsADirectoryError, crashing main() entirely
    instead of reporting a normal FAIL: line and a clean exit code.
    Reproduced live against the pre-fix code (see the fix report) before
    this test was written. --skip-apm-install isolates the env-file crash
    from apm-install so this test exercises exactly one behavior."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result: dict[str, pcb.ProvisionResult | Exception] = {
        "waza": pcb.ProvisionResult(pname="waza", status="installed", version_output="0.38.0"),
    }
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "waza",
            "--skip-apm-install",
            "--env-file", "",
        ]
    )
    assert exit_code == 0


def test_main_apm_install_timeout_reports_fail_and_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Finding 2, first of three uncaught-exception paths: the apm-install
    block's except clause caught only (ApmInstallError, FileNotFoundError).
    subprocess.TimeoutExpired is a SubprocessError, not an OSError/
    FileNotFoundError subclass (verified: TimeoutExpired -> SubprocessError
    -> Exception), and run_apm_install's own runner call uses timeout=120 --
    a slow network fetch of apm's two packages could plausibly exceed that
    in production. Simulated via a fake run_apm_install that raises
    subprocess.TimeoutExpired directly: the same monkeypatch-run_apm_install
    boundary every other apm-related main() test in this file already uses,
    since main() hardcodes run_apm_install's own default `subprocess.run`
    runner and exposes no way to inject a custom one from here."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result: dict[str, pcb.ProvisionResult | Exception] = {
        "apm": pcb.ProvisionResult(pname="apm", status="installed", version_output="0.25.0"),
    }
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)

    def timing_out_apm_install(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["apm", "install"], timeout=120)

    monkeypatch.setattr(pcb, "run_apm_install", timing_out_apm_install)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "apm",
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL: apm install:" in err


def test_main_write_env_file_error_reports_fail_but_still_attempts_apm_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Finding 2, third of three uncaught-exception paths: write_env_file's
    call site in main() (non-verify path) was unguarded. Even after Finding
    1's fix (which only handles the empty-string case), a --env-file
    pointing at a path whose parent directory does not exist still raises
    an uncaught OSError (FileNotFoundError from Path.open("a", ...)) and
    crashes main() before apm install ever runs. The fix must report a
    FAIL: line, count the failure, and -- per the finding's own explicit
    requirement -- still attempt the subsequent apm-install step, since a
    PATH-export failure is independent of whether apm install should run."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    fake_result: dict[str, pcb.ProvisionResult | Exception] = {
        "apm": pcb.ProvisionResult(pname="apm", status="installed", version_output="0.25.0"),
    }
    monkeypatch.setattr(pcb, "provision_all", lambda *args, **kwargs: fake_result)
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(pcb, "run_apm_install", lambda *args, **kwargs: calls.append(args))

    unwritable_env_file = tmp_path / "no-such-parent-dir" / "env.sh"

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "apm",
            "--env-file", str(unwritable_env_file),
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL: could not write env file:" in err
    assert len(calls) == 1  # apm install must still be attempted despite the env-file failure


def test_main_verify_mode_reports_subprocess_error_instead_of_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Finding 2, second of three uncaught-exception paths: the --verify
    branch's `subprocess.run([bin_path, "--version"], ...)` call had NO
    exception handling at all. A binary that exists (so the prior
    bin_path.exists() check passes) but cannot actually be executed --
    simulated here with a directory in place of the binary, which reliably
    raises PermissionError even when running as root (verified live before
    writing this test; see the fix report for the transcript) -- produced a
    raw uncaught traceback instead of a FAIL: line."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
    bin_path = tmp_path / "bin" / "waza"
    bin_path.mkdir(parents=True)  # exists, but cannot be exec'd: not a file

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "waza",
            "--verify",
        ]
    )
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "FAIL: waza:" in out


def test_main_unknown_tool_flag_fails_closed_instead_of_silent_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Finding 3: main() never validated args.tools/only against the actual
    set of tool names parsed from flake.nix (specs.keys(), i.e.
    CLASS_B_TOOL_NAMES). A typo'd --tool silently produced zero work and
    exit 0 -- verified live pre-fix (see the fix report): `--tool
    definitely-not-a-tool` alone printed "apm install not attempted (...)"
    and exited 0. provision_all is monkeypatched to raise if called at all,
    proving the fix short-circuits BEFORE the provisioning branch (not just
    that the exit code happens to end up 1 some other way) -- against the
    pre-fix code this AssertionError itself is what makes the test fail,
    since old code reaches provision_all unconditionally."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)

    def must_not_be_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("provision_all must not be called for an unknown --tool value")

    monkeypatch.setattr(pcb, "provision_all", must_not_be_called)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "definitely-not-a-tool",
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL: unknown --tool value" in err
    assert "definitely-not-a-tool" in err


def test_main_unknown_tool_flag_fails_closed_in_verify_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--verify variant of the finding-3 test above: the reviewer's live
    repro showed `--tool definitely-not-a-tool --verify` produced NO output
    at all and exited 0 (the --verify loop's own `selected` dict is empty
    for an unrecognized tool name, so the loop body never runs). The fix
    must reject this before even reaching the --verify branch."""
    monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)

    exit_code = pcb.main(
        [
            "--project-dir", str(REPO_ROOT),
            "--cache-root", str(tmp_path),
            "--system", "x86_64-linux",
            "--tool", "definitely-not-a-tool",
            "--verify",
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL: unknown --tool value" in err

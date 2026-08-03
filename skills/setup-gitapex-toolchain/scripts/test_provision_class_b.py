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

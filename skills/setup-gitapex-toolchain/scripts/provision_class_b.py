"""Provision gitapex's flake.nix-pinned Class B toolchain binaries (waza,
apm, rtk, betterleaks) for a Claude Code web (ephemeral) session, without
Nix. See SKILL.md for the full description; see the module-level CLI at
the bottom of this file for the entry point.

flake.nix is the single source of truth for tool versions, per-system
asset names, and SHA256 pins -- this module parses it at runtime rather
than holding a second copy, per flake.nix's own comment declaring those
fields "STATIC string literals so a regex updater can bump them in
place."
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CLASS_B_TOOL_NAMES: tuple[str, ...] = ("waza", "apm", "rtk", "betterleaks")

_NIX_SYSTEMS: tuple[str, ...] = (
    "aarch64-linux",
    "x86_64-linux",
    "aarch64-darwin",
    "x86_64-darwin",
)


@dataclass(frozen=True)
class ClassBSystemPin:
    asset: str
    sha256_sri: str
    bin_in_archive: str


@dataclass(frozen=True)
class ClassBToolSpec:
    pname: str
    version: str
    kind: str
    owner: str
    repo: str
    tag: str
    systems: Mapping[str, ClassBSystemPin]

    def release_url(self, system: str) -> str:
        asset = self.systems[system].asset
        return f"https://github.com/{self.owner}/{self.repo}/releases/download/{self.tag}/{asset}"


class FlakePinParseError(RuntimeError):
    """flake.nix's Class B tables didn't match the documented,
    regex-parseable shape. Raised instead of silently proceeding on a
    partial/malformed table."""


_TOOL_BLOCK_RE = re.compile(
    r'(?P<tool>\w+)\s*=\s*\{(?P<body>(?:[^{}]|\{[^{}]*\})*)\}\s*;', re.DOTALL
)
_SYSTEM_ENTRY_RE = re.compile(
    r'(?P<system>[\w-]+)\s*=\s*\{\s*asset\s*=\s*"(?P<asset>[^"]+)"\s*;'
    r'(?:\s*bin\s*=\s*"(?P<bin>[^"]+)"\s*;)?'
    r'\s*sha256\s*=\s*"(?P<sha256>[^"]+)"\s*;\s*\}\s*;'
)
_MK_RELEASE_RE = re.compile(
    r'(?P<tool>\w+)\s*=\s*mkReleaseBinary\s+pkgs\s*\{(?P<body>(?:[^{}]|\{[^{}]*\})*)\};',
    re.DOTALL,
)
_FIELD_RE = re.compile(r'(?P<key>\w+)\s*=\s*"(?P<value>[^"]*)"\s*;')
_GHRELEASE_CALL_RE = re.compile(
    r'ghRelease\s+"(?P<owner>[^"]+)"\s+"(?P<repo>[^"]+)"\s+"(?P<tag>[^"]+)"'
)


def _extract_balanced_block(flake_text: str, search_from: int) -> str:
    """Return the text strictly between the first '{' at/after search_from and
    its depth-matched closing '}'.

    A lazy regex terminator like ``.*?\\n\\s*};\\n`` cannot tell a block's own
    closing brace from an *inner* block's closing brace that also happens to
    sit alone on its own line (e.g. ``classBData``'s first tool entry) --
    it matches the first one it finds, silently truncating the block. Plain
    Python's ``re`` has no recursive/balanced-group support, so depth-count
    by hand instead of stretching a regex to do what it structurally can't.
    None of flake.nix's Class B string literals (asset names, SRI hashes,
    tags) contain a literal brace, so a naive character scan is sufficient.
    """
    open_pos = flake_text.find("{", search_from)
    if open_pos == -1:
        raise FlakePinParseError(f"no '{{' found at or after position {search_from} in flake.nix")
    depth = 0
    for i in range(open_pos, len(flake_text)):
        char = flake_text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return flake_text[open_pos + 1 : i]
    raise FlakePinParseError(f"unbalanced braces scanning from position {open_pos} in flake.nix")


def _extract_class_b_data(flake_text: str) -> dict[str, dict[str, ClassBSystemPin]]:
    header = re.search(r'classBData\s*=\s*', flake_text)
    if not header:
        raise FlakePinParseError("could not locate a classBData = { ... }; block in flake.nix")
    body = _extract_balanced_block(flake_text, header.end())
    result: dict[str, dict[str, ClassBSystemPin]] = {}
    for tool_match in _TOOL_BLOCK_RE.finditer(body):
        tool = tool_match.group("tool")
        if tool not in CLASS_B_TOOL_NAMES:
            continue
        systems: dict[str, ClassBSystemPin] = {}
        for sys_match in _SYSTEM_ENTRY_RE.finditer(tool_match.group("body")):
            system = sys_match.group("system")
            asset = sys_match.group("asset")
            bin_name = sys_match.group("bin") or tool
            sha256 = sys_match.group("sha256")
            systems[system] = ClassBSystemPin(asset=asset, sha256_sri=sha256, bin_in_archive=bin_name)
        result[tool] = systems
    return result


def _extract_mk_class_b_meta(flake_text: str) -> dict[str, tuple[str, str, str, str, str]]:
    header = re.search(r'mkClassB\s*=\s*pkgs:\s*\n\s*let(?P<pre>.*?)\bin\s*\n', flake_text, re.DOTALL)
    if not header:
        raise FlakePinParseError("could not locate an mkClassB = pkgs: ... block in flake.nix")
    body = _extract_balanced_block(flake_text, header.end())
    result: dict[str, tuple[str, str, str, str, str]] = {}
    for tool_match in _MK_RELEASE_RE.finditer(body):
        tool = tool_match.group("tool")
        if tool not in CLASS_B_TOOL_NAMES:
            continue
        body = tool_match.group("body")
        fields = {m.group("key"): m.group("value") for m in _FIELD_RE.finditer(body)}
        version = fields.get("version", "")
        kind = fields.get("kind", "")
        gh_match = _GHRELEASE_CALL_RE.search(body)
        if not gh_match:
            raise FlakePinParseError(f"tool {tool!r}: no ghRelease(...) call found in its mkReleaseBinary block")
        result[tool] = (version, kind, gh_match.group("owner"), gh_match.group("repo"), gh_match.group("tag"))
    return result


def parse_flake_class_b_pins(flake_text: str) -> dict[str, ClassBToolSpec]:
    data = _extract_class_b_data(flake_text)
    meta = _extract_mk_class_b_meta(flake_text)

    missing_from_data = set(CLASS_B_TOOL_NAMES) - set(data)
    missing_from_meta = set(CLASS_B_TOOL_NAMES) - set(meta)
    if missing_from_data or missing_from_meta:
        raise FlakePinParseError(
            f"flake.nix Class B tables are missing tools -- classBData missing {sorted(missing_from_data)}, "
            f"mkClassB missing {sorted(missing_from_meta)}"
        )

    specs: dict[str, ClassBToolSpec] = {}
    for tool in CLASS_B_TOOL_NAMES:
        systems = data[tool]
        missing_systems = set(_NIX_SYSTEMS) - set(systems)
        if missing_systems:
            raise FlakePinParseError(f"tool {tool!r} is missing system entries: {sorted(missing_systems)}")
        version, kind, owner, repo, tag = meta[tool]
        if not (version and kind and owner and repo and tag):
            raise FlakePinParseError(f"tool {tool!r} has an incomplete mkReleaseBinary block: {meta[tool]!r}")
        specs[tool] = ClassBToolSpec(
            pname=tool, version=version, kind=kind, owner=owner, repo=repo, tag=tag, systems=systems
        )
    return specs


def load_flake_class_b_pins(flake_path: Path) -> dict[str, ClassBToolSpec]:
    return parse_flake_class_b_pins(flake_path.read_text(encoding="utf-8"))


_UNAME_SYSTEM_MAP: dict[tuple[str, str], str] = {
    ("Linux", "x86_64"): "x86_64-linux",
    ("Linux", "aarch64"): "aarch64-linux",
    ("Darwin", "x86_64"): "x86_64-darwin",
    ("Darwin", "arm64"): "aarch64-darwin",
}


class UnsupportedSystemError(RuntimeError):
    """uname reported a (system, machine) pair this script has no Class B
    pins for -- e.g. native Windows, where setup.ps1 is the design doc's
    documented answer, not this script."""


def detect_nix_system(sysname: str, machine: str) -> str:
    try:
        return _UNAME_SYSTEM_MAP[(sysname, machine)]
    except KeyError as error:
        raise UnsupportedSystemError(f"unsupported (system, machine) pair: ({sysname!r}, {machine!r})") from error


def current_nix_system() -> str:
    import platform

    return detect_nix_system(platform.system(), platform.machine())


# --- Task 3: download + SHA256 verification ---------------------------------

_HTTP_TIMEOUT_SECONDS = 30
_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 2.0


def _default_opener(request: urllib.request.Request) -> Any:  # matches urlopen's own untyped response object
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310 -- URL is built only from flake.nix's own pinned owner/repo/tag/asset, never attacker input


def sha256_sri(data: bytes) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


class DownloadError(RuntimeError):
    """A Class B release asset could not be fetched -- either a definitive
    404 (no retry) or all retries against a transient failure exhausted."""


def download_asset(
    url: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] = time.sleep,
    max_attempts: int = _MAX_ATTEMPTS,
) -> bytes:
    request = urllib.request.Request(url)  # noqa: S310 -- same pinned-URL justification as _default_opener
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with opener(request) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise DownloadError(f"not-found: {url} returned 404") from error
            last_error = error
        except OSError as error:
            last_error = error
        if attempt < max_attempts - 1:
            sleeper(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
    raise DownloadError(f"fetch-failed: {url} failed after {max_attempts} attempts: {last_error}")


class HashMismatchError(RuntimeError):
    """Downloaded bytes don't match flake.nix's pin. Never extract or
    install on this path -- fail closed."""


def verify_and_download(
    spec: ClassBToolSpec,
    system: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] = time.sleep,
) -> bytes:
    pin = spec.systems[system]
    url = spec.release_url(system)
    data = download_asset(url, opener=opener, sleeper=sleeper)
    actual = sha256_sri(data)
    if actual != pin.sha256_sri:
        raise HashMismatchError(
            f"{spec.pname}/{system}: expected {pin.sha256_sri}, got {actual} (url={url})"
        )
    return data


# --- Task 4: archive extraction (binary and wrapperDir layouts) -------------


class ExtractionError(RuntimeError):
    """The expected member was not present in the downloaded archive, or
    the archive could not be opened as the format its filename implies."""


def _is_zip(asset_name: str) -> bool:
    return asset_name.endswith(".zip")


def extract_binary(data: bytes, asset_name: str, bin_in_archive: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _is_zip(asset_name):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                try:
                    content = zf.read(bin_in_archive)
                except KeyError as error:
                    raise ExtractionError(f"{asset_name}: member {bin_in_archive!r} not found in zip") from error
        except zipfile.BadZipFile as error:
            raise ExtractionError(f"{asset_name}: not a valid zip archive: {error}") from error
    else:
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                # tf.extractfile raises KeyError when bin_in_archive names no
                # member at all (verified against real tarfile semantics --
                # this differs from the None-return path below); it returns
                # None instead only when the name DOES exist but isn't a
                # regular file/link (a directory, device, etc.). Both are
                # "the expected binary isn't there" from this function's
                # point of view, so both become ExtractionError.
                try:
                    member = tf.extractfile(bin_in_archive)
                except KeyError as error:
                    raise ExtractionError(f"{asset_name}: member {bin_in_archive!r} not found in tar.gz") from error
                if member is None:
                    raise ExtractionError(f"{asset_name}: member {bin_in_archive!r} not found in tar.gz")
                content = member.read()
        except tarfile.TarError as error:
            raise ExtractionError(f"{asset_name}: not a valid tar.gz archive: {error}") from error
    dest.write_bytes(content)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _validate_top_level_dir(names: list[str], asset_name: str, libexec_dir: Path) -> str:
    """Return the single top-level path segment shared by every member name
    in a wrapperDir archive, after validating that the segment itself is
    safe to use as a literal path component under libexec_dir -- not just
    that exactly one such segment exists.

    Cardinality alone is not a sufficient guard: a hostile archive where
    every member is named e.g. "../../tmp/pwned" makes
    name.split("/")[0] == ".." for *every* member, so {".."} has
    cardinality 1 and passes a cardinality-only check. Using ".." as the
    top-level dir name is then structurally dangerous downstream --
    `libexec_dir / ".."` resolves to libexec_dir's own PARENT directory,
    so a caller that later does `(libexec_dir / top_dir_name).iterdir()`
    and relocates each child into libexec_dir would enumerate and move
    that PARENT's contents (sibling directories -- e.g. another
    already-installed tool) into libexec_dir, and crash with a raw OSError
    once it reaches libexec_dir itself (renaming a directory into its own
    subdirectory). Reproduced empirically against a real hostile zip
    archive before this check existed; see the security-review fix report
    for the transcript.

    Must be called BEFORE the caller's own extractall -- rejecting a
    hostile archive here means no file is ever written for it, not just
    that the later rename step is skipped.
    """
    top_level = {name.split("/")[0] for name in names if name.strip("/")}
    if len(top_level) != 1:
        raise ExtractionError(f"{asset_name}: expected exactly one top-level dir, found {sorted(top_level)}")
    (top_dir_name,) = top_level
    if not top_dir_name or top_dir_name in (".", "..") or "/" in top_dir_name or "\\" in top_dir_name:
        raise ExtractionError(f"{asset_name}: unsafe top-level dir name {top_dir_name!r}")
    resolved_child = (libexec_dir / top_dir_name).resolve()
    if resolved_child.parent != libexec_dir.resolve():
        raise ExtractionError(
            f"{asset_name}: top-level dir {top_dir_name!r} does not resolve to a direct child of {libexec_dir}"
        )
    return top_dir_name


def extract_wrapper_dir(data: bytes, asset_name: str, bin_in_archive: str, libexec_dir: Path, bin_shim: Path) -> None:
    """Unpack a wrapperDir-kind archive (one top-level dir holding the real
    binary plus support files it needs at runtime, e.g. apm's PyInstaller
    _internal/ tree) into libexec_dir, then write a thin exec shim at
    bin_shim -- the same shape flake.nix's own wrapperDir installPhase
    produces (cp -r the unpacked tree, then wrap the real binary).

    Path-traversal safety: extractall() is never reached against
    unvalidated archive content, and the top-level segment later used to
    locate the extracted tree for flattening is never used structurally
    without first being validated as a safe literal path component (see
    _validate_top_level_dir). Three bounds apply, verified directly
    against the installed Python 3.12 stdlib (not assumed):

    1. Both branches first collect every member name, require exactly one
       shared top-level path segment across all of them (the wrapperDir
       shape), AND validate that segment itself is non-empty, not "." or
       "..", contains no path separator, and resolves to an actual direct
       child of libexec_dir. Cardinality alone is not sufficient -- see
       _validate_top_level_dir's docstring for why. This full validation
       runs before either branch's extractall, so a hostile archive is
       rejected before any file is written.
    2. The tar branch additionally passes filter="data" (PEP 706, stdlib
       since 3.12 -- this repo's pyproject.toml requires-python is
       ">=3.12"). Reading tarfile's own data_filter/_get_filtered_attrs
       source confirms it rejects absolute member paths, resolves and
       bounds every target (and every symlink/hardlink target) to stay
       under the destination directory, rejects device/FIFO/other
       special-file members outright, and strips setuid/setgid/sticky
       bits from what's left -- so #1 and #2 together bound the tar
       branch even against a maliciously crafted archive, not only a
       well-formed one.
    3. zipfile.ZipFile.extractall has no filter= parameter to match
       (confirmed via inspect.signature against this same stdlib), so #1
       is the only *explicit* bound this function adds on the zip branch.
       That is acceptable for the paths extractall itself writes because
       zipfile's own extraction path already strips ".."/"."/drive-letter/
       absolute-path components before joining to the destination (see
       zipfile.ZipFile._extract_member) -- but #1's own validation is
       still required, not optional, because the flatten step below uses
       the raw top-level segment directly (nothing zipfile's extraction
       already sanitized covers that value), and because every call site
       in this module only ever passes flake.nix's own pinned, SHA256-
       hash-verified Class B release asset bytes (see verify_and_download),
       never attacker-controlled input.

    Archive-open/extraction failures -- a corrupted or truncated archive,
    or the tar branch's own filter="data" rejecting a malicious member --
    are caught and re-raised as ExtractionError; no raw tarfile.TarError
    or zipfile.BadZipFile escapes this function.
    """
    libexec_dir.mkdir(parents=True, exist_ok=True)
    if _is_zip(asset_name):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                top_dir_name = _validate_top_level_dir(zf.namelist(), asset_name, libexec_dir)
                zf.extractall(libexec_dir)  # noqa: S202 -- ruff's S202 fires on any `.extractall()` call by method name (confirmed: it flags this zip call too, not just tarfile's), and zipfile has no filter= to satisfy it more directly; bounded instead by _validate_top_level_dir just above plus this function's docstring
        except zipfile.BadZipFile as error:
            raise ExtractionError(f"{asset_name}: not a valid zip archive: {error}") from error
    else:
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                top_dir_name = _validate_top_level_dir(tf.getnames(), asset_name, libexec_dir)
                # No noqa needed: ruff recognizes filter="data" itself as
                # resolving S202 for tarfile (confirmed empirically -- adding
                # one here gets flagged RUF100 unused-noqa by this repo's
                # pinned ruff).
                tf.extractall(libexec_dir, filter="data")
        except tarfile.TarError as error:
            raise ExtractionError(f"{asset_name}: not a valid tar.gz archive: {error}") from error

    extracted_root = libexec_dir / top_dir_name
    for child in extracted_root.iterdir():
        child.rename(libexec_dir / child.name)
    extracted_root.rmdir()

    real_bin = libexec_dir / bin_in_archive
    if not real_bin.exists():
        raise ExtractionError(f"{asset_name}: expected binary {bin_in_archive!r} not found after extraction")
    real_bin.chmod(real_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    bin_shim.parent.mkdir(parents=True, exist_ok=True)
    bin_shim.write_text(f'#!/bin/sh\nexec "{real_bin}" "$@"\n', encoding="utf-8")
    bin_shim.chmod(bin_shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# --- Task 5: idempotency receipts + orchestration ----------------------------


@dataclass(frozen=True)
class InstallReceipt:
    pname: str
    version: str
    sha256_sri: str
    asset: str


def _receipt_path(cache_root: Path, pname: str) -> Path:
    return cache_root / "state" / f"{pname}.json"


def _read_receipt(cache_root: Path, pname: str) -> InstallReceipt | None:
    path = _receipt_path(cache_root, pname)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return InstallReceipt(
            pname=raw["pname"], version=raw["version"], sha256_sri=raw["sha256_sri"], asset=raw["asset"]
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return None


def _write_receipt(cache_root: Path, receipt: InstallReceipt) -> None:
    path = _receipt_path(cache_root, receipt.pname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"pname": receipt.pname, "version": receipt.version, "sha256_sri": receipt.sha256_sri, "asset": receipt.asset}
        ),
        encoding="utf-8",
    )


def _installed_bin_path(cache_root: Path, pname: str) -> Path:
    return cache_root / "bin" / pname


def _is_already_installed(cache_root: Path, spec: ClassBToolSpec, system: str) -> bool:
    receipt = _read_receipt(cache_root, spec.pname)
    if receipt is None:
        return False
    pin = spec.systems[system]
    if receipt.sha256_sri != pin.sha256_sri or receipt.asset != pin.asset:
        return False
    return _installed_bin_path(cache_root, spec.pname).exists()


class VerifyError(RuntimeError):
    """A just-installed binary failed its `<tool> --version` smoke test."""


@dataclass(frozen=True)
class ProvisionResult:
    pname: str
    status: str
    version_output: str | None


def provision_tool(
    spec: ClassBToolSpec,
    system: str,
    cache_root: Path,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] = time.sleep,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    force: bool = False,
) -> ProvisionResult:
    if not force and _is_already_installed(cache_root, spec, system):
        return ProvisionResult(pname=spec.pname, status="skipped", version_output=None)

    data = verify_and_download(spec, system, opener=opener, sleeper=sleeper)
    pin = spec.systems[system]
    bin_path = _installed_bin_path(cache_root, spec.pname)

    if spec.kind == "binary":
        extract_binary(data, pin.asset, pin.bin_in_archive, bin_path)
    elif spec.kind == "wrapperDir":
        libexec_dir = cache_root / "libexec" / spec.pname
        # A reinstall (pin change, or force=True over an already-installed
        # tool) can find libexec_dir already populated by the previous
        # install. extract_wrapper_dir's flatten step does `child.rename(...)`
        # for each extracted top-level entry; os.rename() into an existing
        # non-empty directory (e.g. a stale `_internal/`) raises a raw
        # OSError [Errno 39] Directory not empty -- reproduced empirically
        # against this exact reinstall path before this guard was added, not
        # assumed. Clearing the previous install first makes a reinstall a
        # clean replace rather than a merge of old and new trees, which also
        # prevents a file removed upstream between versions from silently
        # persisting forever. Only cleared here, after verify_and_download
        # above has already succeeded, so a failed download/hash-check never
        # destroys a previously-working install.
        if libexec_dir.exists():
            shutil.rmtree(libexec_dir)
        extract_wrapper_dir(data, pin.asset, pin.bin_in_archive, libexec_dir, bin_path)
    else:
        raise ExtractionError(f"{spec.pname}: unknown kind {spec.kind!r}")

    # No suppression comment needed here (confirmed empirically: adding one
    # for S603 gets flagged as an unused suppression by this repo's pinned
    # ruff). S603 (subprocess call: check for untrusted input) matches
    # direct calls to subprocess.run/Popen/etc. by name; a call through the
    # injected `runner` parameter isn't recognized as one. bin_path is our
    # own just-verified, just-extracted file regardless, never attacker-
    # controlled input.
    proc = runner([str(bin_path), "--version"], capture_output=True, text=True, timeout=30, check=False)
    if proc.returncode != 0:
        raise VerifyError(f"{spec.pname}: `{bin_path} --version` exited {proc.returncode}: {proc.stderr}")

    _write_receipt(cache_root, InstallReceipt(pname=spec.pname, version=spec.version, sha256_sri=pin.sha256_sri, asset=pin.asset))
    return ProvisionResult(pname=spec.pname, status="installed", version_output=proc.stdout.strip())


def provision_all(
    tools: Mapping[str, ClassBToolSpec],
    system: str,
    cache_root: Path,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] = time.sleep,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    only: tuple[str, ...] | None = None,
) -> dict[str, ProvisionResult | Exception]:
    selected = {k: v for k, v in tools.items() if only is None or k in only}
    results: dict[str, ProvisionResult | Exception] = {}
    for pname, spec in selected.items():
        try:
            results[pname] = provision_tool(spec, system, cache_root, opener=opener, sleeper=sleeper, runner=runner)
        # Blind except-Exception is intentional: provision_all is best-effort
        # across independent tools by design, and each exception is captured
        # and returned (not swallowed) for the caller to inspect. No
        # suppression comment needed (confirmed empirically: adding one for
        # BLE001 gets flagged as both unused and referring to a disabled
        # rule) -- flake8-blind-except's BLE prefix isn't in this repo's
        # ruff `select` list at all (only "B" for bugbear is), so that rule
        # can never fire here regardless.
        except Exception as error:
            results[pname] = error
    return results

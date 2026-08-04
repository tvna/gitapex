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

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
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


_TOOL_BLOCK_RE = re.compile(r"(?P<tool>\w+)\s*=\s*\{(?P<body>(?:[^{}]|\{[^{}]*\})*)\}\s*;", re.DOTALL)
_SYSTEM_ENTRY_RE = re.compile(
    r'(?P<system>[\w-]+)\s*=\s*\{\s*asset\s*=\s*"(?P<asset>[^"]+)"\s*;'
    r'(?:\s*bin\s*=\s*"(?P<bin>[^"]+)"\s*;)?'
    r'\s*sha256\s*=\s*"(?P<sha256>[^"]+)"\s*;\s*\}\s*;'
)
_MK_RELEASE_RE = re.compile(
    r"(?P<tool>\w+)\s*=\s*mkReleaseBinary\s+pkgs\s*\{(?P<body>(?:[^{}]|\{[^{}]*\})*)\};",
    re.DOTALL,
)
_FIELD_RE = re.compile(r'(?P<key>\w+)\s*=\s*"(?P<value>[^"]*)"\s*;')
_GHRELEASE_CALL_RE = re.compile(r'ghRelease\s+"(?P<owner>[^"]+)"\s+"(?P<repo>[^"]+)"\s+"(?P<tag>[^"]+)"')


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
    header = re.search(r"classBData\s*=\s*", flake_text)
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
    header = re.search(r"mkClassB\s*=\s*pkgs:\s*\n\s*let(?P<pre>.*?)\bin\s*\n", flake_text, re.DOTALL)
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
    return parse_flake_class_b_pins(
        flake_path.read_text(encoding="utf-8")
    )  # exception-handler-gap: WAIVED: main()'s own try/except around this call already catches UnicodeDecodeError alongside (FlakePinParseError, OSError) -- this function itself deliberately propagates, matching parse_flake_class_b_pins's own let-it-propagate design


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

# Too short risks aborting a slow-but-healthy GitHub release-asset download
# before it finishes; too long lets one hung connection stall the whole
# provisioning run instead of failing fast into a retry.
_HTTP_TIMEOUT_SECONDS = 30
# Too few gives up on a transient blip (one dropped connection) a retry
# would have recovered from; too many multiplies the worst-case wall-clock
# delay (each attempt adds its own backoff) for an asset that was never
# going to succeed.
_MAX_ATTEMPTS = 3
# Too small barely spaces retries apart, hammering a rate-limited or still-
# recovering endpoint; too large makes a session wait needlessly long
# before the next attempt when the first failure was already transient and
# likely to clear quickly.
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
        raise HashMismatchError(f"{spec.pname}/{system}: expected {pin.sha256_sri}, got {actual} (url={url})")
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
            with (
                tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf
            ):  # exception-handler-gap: WAIVED: binary mode ("r:gz") reads archive bytes, never decodes text -- UnicodeDecodeError cannot occur here
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
    archive before this check existed; see
    https://github.com/tvna/gitapex/issues/706 for the fix.

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
            with (
                tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf
            ):  # exception-handler-gap: WAIVED: binary mode ("r:gz") reads archive bytes, never decodes text -- UnicodeDecodeError cannot occur here
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
    # _expected_bin_shim_content is the single source of truth for this
    # format -- _is_already_installed re-derives and compares against the
    # same helper on every later "skip?" check (see its own docstring).
    bin_shim.write_text(_expected_bin_shim_content(real_bin), encoding="utf-8")
    bin_shim.chmod(bin_shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# --- Task 5: idempotency receipts + orchestration ----------------------------


@dataclass(frozen=True)
class InstallReceipt:
    pname: str
    version: str
    sha256_sri: str
    asset: str
    # SHA256 (SRI format) of the actual installed entry-point executable's
    # bytes -- see _entry_point_path -- not the downloaded archive and not
    # (for wrapperDir) the whole _internal/ support tree. Re-verified by
    # _is_already_installed on every "skip?" check so a stale receipt can
    # never vouch for THIS file having been corrupted or tampered with on
    # disk. For a wrapperDir-kind tool, entry_point is the real binary
    # under libexec/ -- a separate file from bin/<pname> (the tiny
    # generated exec shim actually invoked, e.g. by main()'s --verify
    # branch and by run_apm_install) -- so _is_already_installed
    # additionally re-derives and compares the shim's own expected content
    # (see _expected_bin_shim_content) on every check; that shim check,
    # not this hash, is what closes the gap for that second file.
    installed_sha256: str


def _receipt_path(cache_root: Path, pname: str) -> Path:
    return cache_root / "state" / f"{pname}.json"


def _read_receipt(cache_root: Path, pname: str) -> InstallReceipt | None:
    path = _receipt_path(cache_root, pname)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return InstallReceipt(
            pname=raw["pname"],
            version=raw["version"],
            sha256_sri=raw["sha256_sri"],
            asset=raw["asset"],
            installed_sha256=raw["installed_sha256"],
        )
    # KeyError also covers an old receipt written before installed_sha256
    # existed: treated as "no receipt" (same as any other malformed
    # receipt), which forces exactly one reinstall to backfill the new
    # field -- no separate migration code needed. UnicodeDecodeError
    # (a receipt corrupted to non-UTF-8 bytes) is not an OSError/
    # JSONDecodeError/KeyError/TypeError subclass and must be listed
    # explicitly -- same "no receipt" treatment, same fail-closed forced
    # reinstall.
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError):
        return None


def _write_receipt(cache_root: Path, receipt: InstallReceipt) -> None:
    path = _receipt_path(cache_root, receipt.pname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "pname": receipt.pname,
                "version": receipt.version,
                "sha256_sri": receipt.sha256_sri,
                "asset": receipt.asset,
                "installed_sha256": receipt.installed_sha256,
            }
        ),
        encoding="utf-8",
    )


def _installed_bin_path(cache_root: Path, pname: str) -> Path:
    return cache_root / "bin" / pname


def _entry_point_path(cache_root: Path, spec: ClassBToolSpec, pin: ClassBSystemPin) -> Path:
    """The actual entry-point executable a --version/apm-install invocation
    runs -- bin_path itself for a `binary`-kind tool, or the real
    PyInstaller launcher inside libexec/ for a `wrapperDir`-kind tool
    (never bin_shim, the tiny generated `exec` wrapper script regenerated
    from scratch on every install, which proves nothing about the
    underlying tree). Shared by provision_tool (to compute the receipt's
    installed_sha256) and _is_already_installed (to re-verify it), so both
    sides of the trust boundary agree on exactly which file is meant."""
    if spec.kind == "wrapperDir":
        return cache_root / "libexec" / spec.pname / pin.bin_in_archive
    return _installed_bin_path(cache_root, spec.pname)


def _expected_bin_shim_content(entry_point: Path) -> str:
    """The exact text a wrapperDir-kind tool's bin/<pname> shim must
    contain -- the same f-string extract_wrapper_dir writes when it first
    creates the shim. Factored out so both sides of the trust boundary
    (the file written at install time, and the file re-verified by
    _is_already_installed on every later "skip?" check) agree on exactly
    one definition of what the shim is supposed to contain, the same role
    _entry_point_path already serves for the entry-point file itself."""
    return f'#!/bin/sh\nexec "{entry_point}" "$@"\n'


def _is_already_installed(cache_root: Path, spec: ClassBToolSpec, system: str) -> bool:
    receipt = _read_receipt(cache_root, spec.pname)
    if receipt is None:
        return False
    pin = spec.systems[system]
    if receipt.sha256_sri != pin.sha256_sri or receipt.asset != pin.asset:
        return False
    bin_path = _installed_bin_path(cache_root, spec.pname)
    if not bin_path.exists():
        return False
    # Re-verify the entry-point executable's CURRENT on-disk bytes against
    # the receipt, not just its existence: a receipt whose sha256_sri/asset
    # still match the current pin says only that this tool was correctly
    # installed at some point in the past, not that the file on disk right
    # now is still that same, untampered file -- a partial write, disk
    # fault, or tampering between provisioning and this later check would
    # otherwise be silently trusted and then executed (including by `apm
    # install`, which runs the apm binary directly as a subprocess).
    # Deliberately scoped to this ONE entry-point file's hash, not a
    # recursive tree hash, bounding the check to the highest-value
    # tampering target (the file actually executed) without adding a
    # full-tree-walk cost to the hot "skip, already installed" path that
    # runs on every session start.
    entry_point = _entry_point_path(cache_root, spec, pin)
    if not entry_point.exists():
        return False
    if sha256_sri(entry_point.read_bytes()) != receipt.installed_sha256:
        return False
    # For a wrapperDir-kind tool, entry_point above is the real binary
    # under libexec/ -- a SEPARATE file from bin_path, the tiny generated
    # `exec` shim main() (--verify) and run_apm_install actually invoke.
    # Hashing only entry_point therefore leaves bin_path itself
    # unverified: an attacker who tampers ONLY the shim (e.g. rewriting it
    # to `exec /tmp/evil "$@"`) is silently trusted, because the real,
    # untampered binary's hash still matches. The shim's content is 100%
    # deterministic (see _expected_bin_shim_content), so it can be
    # re-derived and compared exactly rather than merely hashed against a
    # stored value. binary-kind tools have no separate shim -- their entry
    # point IS bin_path, already covered by the hash check above -- so
    # this only applies to, and only runs for, wrapperDir.
    if spec.kind != "wrapperDir":
        return True
    try:
        shim_is_expected = bin_path.read_text(encoding="utf-8") == _expected_bin_shim_content(entry_point)
    # A shim tampered with non-UTF-8 bytes is not "content differs from
    # expected" (a plain string mismatch) but a decode failure -- treated
    # the same way, forcing a reinstall, not left to propagate as an
    # uncaught exception out of this best-effort-per-tool check.
    except UnicodeDecodeError:
        return False
    return shim_is_expected


class VerifyError(RuntimeError):
    """A just-installed binary failed its `<tool> --version` smoke test."""


# A real `--version` line is always short; a much longer value is itself a
# signal something is wrong, not legitimate content to render in full.
_MAX_VERSION_OUTPUT_DISPLAY_CHARS = 200


def _sanitize_for_display(text: str) -> str:
    """Strip terminal control/escape sequences from raw third-party
    subprocess output before it is stored or printed -- a just-installed
    third-party binary's --version stdout, and (the same untrusted-output
    category) its stderr on a failed --version smoke test or a failed
    `apm install`. Control/escape bytes in any of these would be
    interpreted verbatim by whatever displays this script's output, so
    nothing here trusts them unsanitized.

    Whitespace-class control characters (\\n, \\r, \\t) are replaced with a
    single space rather than dropped, so multi-line output doesn't end up
    with words glued together across the line break; every other
    non-printable character (ANSI escapes, BEL, bidi-override, etc.) is
    still dropped, exactly as before. This is a separate, additional case
    from plain space (0x20) itself: str.isprintable() already treats plain
    space as printable, so it was never at risk of being dropped and still
    needs no special-casing of its own alongside \\n/\\r/\\t."""
    despaced = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    cleaned = "".join(char for char in despaced if char.isprintable())
    if len(cleaned) > _MAX_VERSION_OUTPUT_DISPLAY_CHARS:
        return cleaned[:_MAX_VERSION_OUTPUT_DISPLAY_CHARS] + "...[truncated]"
    return cleaned


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

    entry_point = _entry_point_path(cache_root, spec, pin)

    # No suppression comment needed here (confirmed empirically: adding one
    # for S603 gets flagged as an unused suppression by this repo's pinned
    # ruff). S603 (subprocess call: check for untrusted input) matches
    # direct calls to subprocess.run/Popen/etc. by name; a call through the
    # injected `runner` parameter isn't recognized as one. bin_path is our
    # own just-verified, just-extracted file regardless, never attacker-
    # controlled input.
    proc = runner([str(bin_path), "--version"], capture_output=True, text=True, timeout=30, check=False)
    if proc.returncode != 0:
        # proc.stderr is raw third-party subprocess output -- the FAILING
        # path is the one most likely to carry adversarial bytes, since a
        # hostile binary only needs a non-zero exit to reach this site.
        # Same sink category _sanitize_for_display already closes for
        # --version stdout; see its own docstring.
        raise VerifyError(
            f"{spec.pname}: `{bin_path} --version` exited {proc.returncode}: {_sanitize_for_display(proc.stderr)}"
        )

    # Hash only the entry-point executable actually run (see
    # _is_already_installed's own comment for why this is deliberately
    # scoped to one file, not a full-tree hash). Computed only after the
    # --version smoke test above has already passed, matching this
    # function's existing fail-closed shape: no receipt (with or without
    # this field) is ever written for a tool that didn't verify cleanly.
    installed_sha256 = sha256_sri(entry_point.read_bytes())
    _write_receipt(
        cache_root,
        InstallReceipt(
            pname=spec.pname,
            version=spec.version,
            sha256_sri=pin.sha256_sri,
            asset=pin.asset,
            installed_sha256=installed_sha256,
        ),
    )
    return ProvisionResult(
        pname=spec.pname, status="installed", version_output=_sanitize_for_display(proc.stdout.strip())
    )


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


# --- Task 6: apm install invocation + PATH env-file writing -----------------


class ApmInstallError(RuntimeError):
    """`apm install` exited non-zero. Per the criterion from
    https://github.com/tvna/gitapex/issues/690: the requester confirmed
    reliance on apm's own cache-hit behavior rather than custom skip logic
    here -- this function always invokes install and lets apm decide what,
    if anything, there is to do."""


def run_apm_install(
    project_dir: Path,
    apm_binary: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    if not (project_dir / "apm.yml").exists():
        raise FileNotFoundError(
            f"{project_dir}/apm.yml not found -- refusing to run apm install outside a gitapex checkout"
        )
    # No suppression comment needed here (confirmed empirically, same as
    # provision_tool's own runner call above): ruff's S603 (subprocess call:
    # check for untrusted input) matches direct calls to subprocess.run/
    # Popen/etc. by name, and a call through the injected `runner` parameter
    # isn't recognized as one -- adding an S603 suppression here gets flagged
    # as an unused directive by this repo's pinned ruff. apm_binary is this
    # same run's own just-downloaded, hash-verified path regardless, never
    # attacker-controlled input.
    #
    # Longer budget than _HTTP_TIMEOUT_SECONDS: apm install deploys
    # multiple skill packages over the network in one invocation, unlike a
    # single HTTP GET -- too short would abort a healthy multi-package
    # install still in progress; too long lets a genuinely hung apm
    # process stall the whole session-start hook.
    result = runner(
        [str(apm_binary), "install"], cwd=str(project_dir), capture_output=True, text=True, timeout=120, check=False
    )
    if result.returncode != 0:
        # Same raw-third-party-stderr sink category as VerifyError's raise
        # site above -- sanitize before it can reach the terminal.
        raise ApmInstallError(f"apm install exited {result.returncode}: {_sanitize_for_display(result.stderr)}")
    return result


@dataclass(frozen=True)
class ApmInstallReceipt:
    """Idempotency receipt for the `apm install` step itself (issue #724) --
    a separate concern from InstallReceipt above, which covers apm the
    *binary's* own provisioning. Written to cache_root/state/apm-install.json
    after a successful `apm install`, and consulted by
    _is_apm_install_up_to_date before main() invokes it again, so a session
    whose lockfile and installed apm binary are both unchanged since the
    last successful run does not re-run the subprocess (and therefore does
    not re-touch .claude/settings.json) on every single session start."""

    lockfile_sha256: str
    apm_binary_sha256: str


def _apm_install_receipt_path(cache_root: Path) -> Path:
    return cache_root / "state" / "apm-install.json"


def _read_apm_install_receipt(cache_root: Path) -> ApmInstallReceipt | None:
    path = _apm_install_receipt_path(cache_root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ApmInstallReceipt(lockfile_sha256=raw["lockfile_sha256"], apm_binary_sha256=raw["apm_binary_sha256"])
    # Same try/except-on-read-errors-means-None convention as _read_receipt
    # above: a missing, malformed, or partial receipt is indistinguishable
    # from "no receipt" -- both force a reinstall (fail closed), never a
    # crash. UnicodeDecodeError listed explicitly for the same reason as
    # _read_receipt's own copy of this tuple: it is not a subclass of any
    # of the other four.
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError):
        return None


def _write_apm_install_receipt(cache_root: Path, receipt: ApmInstallReceipt) -> None:
    path = _apm_install_receipt_path(cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"lockfile_sha256": receipt.lockfile_sha256, "apm_binary_sha256": receipt.apm_binary_sha256}),
        encoding="utf-8",
    )


def _is_apm_install_up_to_date(project_dir: Path, cache_root: Path) -> bool:
    """True only when `apm install` provably has nothing new to do: a
    receipt exists from a prior successful run, project_dir's current
    apm.lock.yaml is byte-identical to what that receipt was written
    against, apm's own currently-installed binary (per its InstallReceipt,
    re-verified on every provisioning run by _is_already_installed) is the
    same binary that receipt names, and apm's own deployed manifest
    (.claude/apm-hooks.json) is still on disk. Any missing or mismatched
    signal returns False -- fail closed toward reinstalling, matching this
    module's existing InstallReceipt philosophy: an inability to verify
    freshness is a reason to reinstall, not a reason to skip.

    A lockfile-hash match alone is deliberately not sufficient: it says
    nothing about whether apm's own deployed output survived (e.g. a `git
    clean` wiping the gitignored .claude/skills/ tree), and nothing about
    whether flake.nix pinned a new apm release since the receipt was
    written -- a different apm binary version could deploy the same
    lockfile differently. All four checks below must hold.
    """
    receipt = _read_apm_install_receipt(cache_root)
    if receipt is None:
        return False

    lockfile_path = project_dir / "apm.lock.yaml"
    if not lockfile_path.exists():
        return False
    if sha256_sri(lockfile_path.read_bytes()) != receipt.lockfile_sha256:
        return False

    apm_receipt = _read_receipt(cache_root, "apm")
    if apm_receipt is None or apm_receipt.installed_sha256 != receipt.apm_binary_sha256:
        return False

    return (project_dir / ".claude" / "apm-hooks.json").exists()


def write_env_file(env_file: Path | None, cache_root: Path) -> None:
    if env_file is None:
        return
    export_line = f'export PATH="{cache_root / "bin"}:$PATH"\n'
    existing = (
        env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    )  # exception-handler-gap: WAIVED: main()'s own try/except around this call already catches (OSError, UnicodeDecodeError) -- this function itself deliberately propagates
    if export_line in existing:
        return
    with env_file.open("a", encoding="utf-8") as handle:
        handle.write(export_line)


# --- Task 7: CLI entry point -------------------------------------------------


def _default_cache_root() -> Path:
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"
    return base / "gitapex" / "toolchain"


def _env_file_arg(value: str) -> Path | None:
    """argparse type= for --env-file. Treat an empty string the same as the
    flag not being passed at all -- this is exactly what
    .claude/hooks/session-start.sh's `--env-file "${CLAUDE_ENV_FILE:-}"`
    passes when CLAUDE_ENV_FILE is unset (bash's unset-with-default
    expansion becomes a literal empty argument). main() must be robust to
    this regardless of what calls it, not just fixed in the shell wrapper.

    Plain `type=Path` would instead silently convert "" to Path("") ==
    PosixPath(".") -- the process's current directory, not "no file" --
    and write_env_file() would then call .read_text() on that directory
    and crash with an uncaught IsADirectoryError. Verified empirically:
    str(Path("")) == "." (not ""), so a post-parse `str(args.env_file) ==
    ""` check can never match the already-converted PosixPath('.') -- the
    empty string must be intercepted here, before Path() gets to mangle
    it.
    """
    return Path(value) if value != "" else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")))
    parser.add_argument("--cache-root", type=Path, default=_default_cache_root())
    parser.add_argument("--flake-path", type=Path, default=None)
    parser.add_argument("--system", default=None)
    parser.add_argument("--tool", action="append", dest="tools", default=None)
    parser.add_argument("--skip-apm-install", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--env-file",
        type=_env_file_arg,
        default=(Path(os.environ["CLAUDE_ENV_FILE"]) if os.environ.get("CLAUDE_ENV_FILE") else None),
    )
    args = parser.parse_args(argv)

    project_dir: Path = args.project_dir
    flake_path: Path = args.flake_path or (project_dir / "flake.nix")
    cache_root: Path = args.cache_root
    only = tuple(args.tools) if args.tools else None

    # Kept as its own try/except, separate from load_flake_class_b_pins'
    # below, so a system-detection failure reports its own accurate
    # message rather than the misleading "could not load Class B pins"
    # text -- these are two different failure classes with two different
    # causes (an exotic uname pair vs. a malformed/missing flake.nix).
    if args.system:
        system = args.system
    else:
        try:
            system = current_nix_system()
        # current_nix_system() raises UnsupportedSystemError (a
        # RuntimeError subclass) for an exotic uname pair (e.g. native
        # Windows, an unrecognized arch) this script has no Class B pins
        # for. Pre-fix, this call sat above main()'s only try/except, so
        # this exception crashed main() with a raw traceback instead of a
        # clean FAIL: line and non-zero exit.
        except UnsupportedSystemError as error:
            print(f"FAIL: could not detect a supported Nix system: {error}", file=sys.stderr)
            return 1

    try:
        specs = load_flake_class_b_pins(flake_path)
    # OSError, not just FileNotFoundError: a --flake-path that is a
    # directory, unreadable (permissions), or otherwise inaccessible is
    # plausible human error (e.g. a typo'd path) and must fail the same
    # clean way as a missing file -- verified live that Path.read_text()
    # raises IsADirectoryError (an OSError subclass, not a
    # FileNotFoundError subclass) for the directory case, which the
    # narrower except left as an uncaught traceback. FileNotFoundError
    # remains covered since it is itself an OSError subclass.
    # UnicodeDecodeError is NOT an OSError subclass (it is a ValueError
    # subclass) -- a flake.nix with non-UTF-8 bytes would otherwise crash
    # main() with a raw traceback instead of this same clean FAIL: line;
    # caught explicitly rather than assumed covered by OSError.
    except (FlakePinParseError, OSError, UnicodeDecodeError) as error:
        print(f"FAIL: could not load Class B pins from {flake_path}: {error}", file=sys.stderr)
        return 1

    if only is not None:
        unknown = set(only) - set(specs)
        if unknown:
            print(f"FAIL: unknown --tool value(s): {sorted(unknown)} (valid: {sorted(specs)})", file=sys.stderr)
            return 1

    if args.verify:
        selected = {k: v for k, v in specs.items() if only is None or k in only}
        failures = 0
        for pname in selected:
            bin_path = _installed_bin_path(cache_root, pname)
            if not bin_path.exists():
                print(f"FAIL: {pname}: not installed at {bin_path}")
                failures += 1
                continue
            try:
                proc = subprocess.run(  # noqa: S603 -- bin_path is our own cache-root path, not attacker input
                    [str(bin_path), "--version"], capture_output=True, text=True, timeout=30, check=False
                )
            except (subprocess.SubprocessError, OSError) as error:
                print(f"FAIL: {pname}: {error}")
                failures += 1
                continue
            if proc.returncode != 0:
                print(f"FAIL: {pname}: --version exited {proc.returncode}")
                failures += 1
            else:
                print(f"PASS: {pname}: {_sanitize_for_display(proc.stdout.strip())}")
        return 1 if failures else 0

    results = provision_all(specs, system, cache_root, only=only)
    failures = 0
    for pname, result in results.items():
        if isinstance(result, Exception):
            print(f"FAIL: {pname}: {result}", file=sys.stderr)
            failures += 1
        else:
            print(
                f"{result.status.upper()}: {pname}" + (f" ({result.version_output})" if result.version_output else "")
            )

    try:
        write_env_file(args.env_file, cache_root)
    # UnicodeDecodeError alongside OSError: write_env_file's own read of an
    # existing env file is not OSError's subclass (it is ValueError's) --
    # a $CLAUDE_ENV_FILE some other process wrote non-UTF-8 bytes into
    # would otherwise crash main() here instead of this same clean FAIL:
    # line.
    except (OSError, UnicodeDecodeError) as error:
        # Deliberately does not `return` or otherwise skip the apm-install
        # step below: a PATH export failure is independent of whether apm
        # install should still be attempted.
        print(f"FAIL: could not write env file: {error}", file=sys.stderr)
        failures += 1

    if not args.skip_apm_install:
        apm_was_requested = only is None or "apm" in only
        apm_result = results.get("apm")
        if isinstance(apm_result, ProvisionResult):
            if _is_apm_install_up_to_date(project_dir, cache_root):
                print("UNCHANGED: apm install")
            else:
                try:
                    run_apm_install(project_dir, _installed_bin_path(cache_root, "apm"))
                    print("INSTALLED: apm install")
                    apm_tool_receipt = _read_receipt(cache_root, "apm")
                    if apm_tool_receipt is not None:
                        _write_apm_install_receipt(
                            cache_root,
                            ApmInstallReceipt(
                                lockfile_sha256=sha256_sri((project_dir / "apm.lock.yaml").read_bytes()),
                                apm_binary_sha256=apm_tool_receipt.installed_sha256,
                            ),
                        )
                except (ApmInstallError, FileNotFoundError, subprocess.SubprocessError, OSError) as error:
                    print(f"FAIL: apm install: {error}", file=sys.stderr)
                    failures += 1
        elif apm_was_requested:
            # apm was in scope (no --tool filter, or --tool explicitly
            # included "apm") but its entry in `results` isn't a successful
            # ProvisionResult -- a genuine provisioning failure. Keep this
            # message and the failure count exactly as-is: this is the real
            # failure case, not the --tool-exclusion case below.
            print("SKIPPED: apm install (apm itself was not successfully provisioned)", file=sys.stderr)
            failures += 1
        else:
            # apm was never requested at all: a --tool filter was given and
            # it does not include "apm", so provision_all's own `only` filter
            # never attempted it and results.get("apm") is None -- the same
            # None/ProvisionResult shape as a genuine failure, but not one.
            # Not a failure: nothing the caller actually asked for failed.
            print("apm install not attempted (apm was not in --tool selection)")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

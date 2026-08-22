#!/usr/bin/env python3
"""Guard the apm.yml <-> apm.lock.yaml completeness invariant.

``apm.yml``'s ``devDependencies.apm`` declares which apm packages this
repository consumes at development time; ``apm.lock.yaml`` records how each
one actually resolved, including which files ``apm install`` deployed
(``deployed_files``/``deployed_file_hashes``). The apm CLI (0.25.0) exposes
two different commands over the lockfile: ``apm lock`` ("Resolve
dependencies and write apm.lock.yaml without deploying files") and ``apm
install`` (deploys files and, as a side effect, writes the full
deployed_files/deployed_file_hashes record). Running only the former after
adding a dependency leaves a lockfile entry that is structurally present
but incomplete -- exactly what happened when cathrynlavery/diagram-design
was added in #1158: its dependencies[] entry carried no deployed_files or
deployed_file_hashes at all until a later ``apm install`` repaired it.

Neither ``apm install --frozen --dry-run`` nor ``apm audit --ci --no-drift``
catches this class of drift (both were verified against the broken #1158
lockfile and passed cleanly -- see issue #1254): the former only checks that
a lockfile entry structurally exists, and the latter's
deployed-files-present check only verifies that files a lockfile *does*
list are present on disk, so an entry that lists zero files has nothing to
fail against.

This scanner is the drift gate that fills that gap: it fails if any
``devDependencies.apm`` entry in ``apm.yml`` lacks a matching
``apm.lock.yaml`` ``dependencies[]`` entry (matched by ``repo_url``), or
that entry has an empty/missing ``deployed_files`` or
``deployed_file_hashes``.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gitapex_scan_apm_lockfile_drift.py``.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
APM_MANIFEST = REPO_ROOT / "apm.yml"
APM_LOCKFILE = REPO_ROOT / "apm.lock.yaml"


class LockfileReadError(Exception):
    """Either apm.yml or apm.lock.yaml could not be read as UTF-8 text, or
    could not be parsed as YAML -- exit 1, naming the offending file, never
    a traceback."""


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise LockfileReadError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise LockfileReadError(f"{path}: is not valid UTF-8: {error}") from error


def _load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(_read_text(path))
    except yaml.YAMLError as error:
        raise LockfileReadError(f"{path}: is not valid YAML: {error}") from error


def _devdep_repos(apm_data: dict[str, Any], apm_manifest: pathlib.Path) -> list[str]:
    """Return apm.yml's devDependencies.apm list of "owner/repo" strings.

    Missing devDependencies, or a devDependencies with no apm key, means
    this project declares no apm dev dependencies -- a legitimate empty
    result, not an error. devDependencies.apm present but not a list is a
    malformed manifest and fails loudly.
    """
    dev_deps = apm_data.get("devDependencies")
    if dev_deps is None:
        return []
    if not isinstance(dev_deps, dict):
        raise LockfileReadError(
            f"{apm_manifest}: 'devDependencies' must be a YAML mapping, got {type(dev_deps).__name__}"
        )
    repos = dev_deps.get("apm")
    if repos is None:
        return []
    if not isinstance(repos, list):
        raise LockfileReadError(
            f"{apm_manifest}: 'devDependencies.apm' must be a YAML list, got {type(repos).__name__}"
        )
    return repos


def _lockfile_index(lock_data: dict[str, Any], apm_lockfile: pathlib.Path) -> dict[str, dict[str, Any]]:
    """Return apm.lock.yaml's dependencies[] indexed by repo_url.

    A missing or non-list 'dependencies' key is a malformed/unknown-shape
    lockfile -- fails loudly rather than silently treating it as empty, so
    a broken lockfile cannot masquerade as a clean one.
    """
    dependencies = lock_data.get("dependencies")
    if not isinstance(dependencies, list):
        raise LockfileReadError(
            f"{apm_lockfile}: 'dependencies' must be a YAML list, got {type(dependencies).__name__}"
        )
    index: dict[str, dict[str, Any]] = {}
    for entry in dependencies:
        if not isinstance(entry, dict) or "repo_url" not in entry:
            raise LockfileReadError(
                f"{apm_lockfile}: every dependencies[] entry must be a mapping with a 'repo_url' field"
            )
        index[entry["repo_url"]] = entry
    return index


def find_drift(
    apm_manifest: pathlib.Path = APM_MANIFEST,
    apm_lockfile: pathlib.Path = APM_LOCKFILE,
) -> list[tuple[str, str]]:
    """Return (repo_url, reason) for each devDependencies.apm entry whose
    apm.lock.yaml counterpart is missing or incomplete. Empty list means
    apm.yml and apm.lock.yaml are in lockstep.

    reason is one of:
      - "missing-lockfile-entry": no dependencies[] entry with this repo_url
      - "missing-deployed-files": entry exists but deployed_files is absent/empty
      - "missing-deployed-file-hashes": entry exists but deployed_file_hashes is absent/empty

    Fails loudly (raises LockfileReadError) if either file is missing,
    unreadable as UTF-8, not valid YAML syntax, or syntactically valid but
    not shaped as documented above -- a silent skip would let the gate pass
    on a broken manifest or lockfile.
    """
    apm_data = _load_yaml(apm_manifest)
    lock_data = _load_yaml(apm_lockfile)

    if not isinstance(apm_data, dict):
        raise LockfileReadError(f"{apm_manifest}: must be a YAML mapping, got {type(apm_data).__name__}")
    if not isinstance(lock_data, dict):
        raise LockfileReadError(f"{apm_lockfile}: must be a YAML mapping, got {type(lock_data).__name__}")

    repos = _devdep_repos(apm_data, apm_manifest)
    index = _lockfile_index(lock_data, apm_lockfile)

    findings: list[tuple[str, str]] = []
    for repo in repos:
        entry = index.get(repo)
        if entry is None:
            findings.append((repo, "missing-lockfile-entry"))
            continue
        if not entry.get("deployed_files"):
            findings.append((repo, "missing-deployed-files"))
            continue
        if not entry.get("deployed_file_hashes"):
            findings.append((repo, "missing-deployed-file-hashes"))
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except LockfileReadError as error:
        print(f"apm lockfile drift: {error}")
        return 1
    if findings:
        print(
            "apm lockfile drift: every apm.yml devDependencies.apm entry needs a complete "
            "apm.lock.yaml dependencies[] entry (run `apm install`, not `apm lock` alone):"
        )
        for repo, reason in findings:
            print(f"  {repo}: {reason}")
        return 1
    print("No apm lockfile drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

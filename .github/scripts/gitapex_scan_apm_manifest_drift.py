#!/usr/bin/env python3
"""Guard the plugin-identity single-source-of-truth invariant.

``.claude-plugin/plugin.json`` mirrors the gitapex plugin's identity from the
repository-root ``plugin.json`` (the plugin-identity source of truth since
issue #1028; see ``docs/repository-layout.md`` and
``gitapex_generate_plugin_manifest.py``). ``apm.yml`` must also carry ``name``
and ``version`` -- apm's manifest schema requires both -- which duplicates that
identity into a third tracked file, one mirror-hop removed from the SSOT.
Left unguarded, the copies drift: a release bumps ``plugin.json`` while
``apm.yml`` (or the generated ``.claude-plugin/plugin.json`` mirror) keeps a
stale version.

This scanner is the drift gate shipped alongside that duplication: it fails if
``apm.yml``'s ``name`` or ``version`` disagrees with ``.claude-plugin/plugin.json``.
It does not invent a value -- ``.claude-plugin/plugin.json`` stays authoritative
for this comparison; ``apm.yml`` mirrors it. (That file is itself now generated
from the repository-root ``plugin.json`` -- see ``plugin-manifest-mirror-drift``
-- which does not change this script's own comparison.)

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gitapex_scan_apm_manifest_drift.py``.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
APM_MANIFEST = REPO_ROOT / "apm.yml"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"

# Fields that both manifests declare and must therefore agree on.
# .claude-plugin/plugin.json is authoritative for this comparison; apm.yml
# mirrors it.
MIRRORED_FIELDS = ("name", "version")


class ManifestReadError(Exception):
    """Either apm.yml or plugin.json could not be read as UTF-8 text, or
    could not be parsed as YAML/JSON -- exit 1, naming the offending file,
    never a traceback."""


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ManifestReadError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise ManifestReadError(f"{path}: is not valid UTF-8: {error}") from error


def _load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(_read_text(path))
    except yaml.YAMLError as error:
        raise ManifestReadError(f"{path}: is not valid YAML: {error}") from error


def _load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as error:
        raise ManifestReadError(f"{path}: is not valid JSON: {error}") from error


def find_drift(
    apm_manifest: pathlib.Path = APM_MANIFEST,
    plugin_manifest: pathlib.Path = PLUGIN_MANIFEST,
) -> list[tuple[str, str, str]]:
    """Return (field, plugin_json_value, apm_yml_value) for each mirrored field
    whose two copies disagree. Empty list means the manifests are in lockstep.

    Fails loudly (raises) if either manifest is missing, unreadable as UTF-8,
    not valid YAML/JSON syntax, or syntactically valid but not a top-level
    mapping/object (all ManifestReadError), or a mirrored field is absent
    (KeyError) -- a silent skip would let the gate pass on a broken
    manifest.
    """
    apm_data = _load_yaml(apm_manifest)
    plugin_data = _load_json(plugin_manifest)

    # Valid YAML/JSON syntax does not mean either document is shaped as a
    # mapping/object -- a top-level list, scalar, or empty document (e.g.
    # apm.yml containing just "- name\n- version\n", "42", or nothing at
    # all, which yaml.safe_load parses as None) parses cleanly but crashed
    # the `field not in ...`/`...[field]` lookups below with an uncaught
    # TypeError.
    if not isinstance(apm_data, dict):
        raise ManifestReadError(f"{apm_manifest}: must be a YAML mapping, got {type(apm_data).__name__}")
    if not isinstance(plugin_data, dict):
        raise ManifestReadError(f"{plugin_manifest}: must be a JSON object, got {type(plugin_data).__name__}")

    findings: list[tuple[str, str, str]] = []
    for field in MIRRORED_FIELDS:
        if field not in plugin_data:
            raise KeyError(f"{plugin_manifest}: missing required field '{field}'")
        if field not in apm_data:
            raise KeyError(f"{apm_manifest}: missing required field '{field}'")
        plugin_value = str(plugin_data[field])
        apm_value = str(apm_data[field])
        if plugin_value != apm_value:
            findings.append((field, plugin_value, apm_value))
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except (ManifestReadError, KeyError) as error:
        print(f"apm manifest drift: {error}")
        return 1
    if findings:
        print("apm manifest drift: apm.yml must mirror .claude-plugin/plugin.json (the version source of truth):")
        for field, plugin_value, apm_value in findings:
            print(f"  {field}: plugin.json={plugin_value!r} != apm.yml={apm_value!r}")
        return 1
    print("No apm manifest drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

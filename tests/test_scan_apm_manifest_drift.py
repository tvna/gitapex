"""Tests for the apm manifest drift gate (.github/scripts/scan_apm_manifest_drift.py).

The final test is the gate itself: the repository's real apm.yml and plugin.json
must agree on name and version. The rest unit-test the detector with fixtures.
"""

from __future__ import annotations

import json
import pathlib

import pytest

import scan_apm_manifest_drift as drift

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _write_pair(
    tmp_path: pathlib.Path, apm: str, plugin: dict
) -> tuple[pathlib.Path, pathlib.Path]:
    apm_manifest = tmp_path / "apm.yml"
    plugin_manifest = tmp_path / "plugin.json"
    apm_manifest.write_text(apm)
    plugin_manifest.write_text(json.dumps(plugin))
    return apm_manifest, plugin_manifest


def test_matching_manifests_have_no_drift(tmp_path):
    apm, plugin = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\ndependencies:\n  apm: []\n",
        {"name": "gitapex", "version": "0.1.0"},
    )
    assert drift.find_drift(apm, plugin) == []


def test_version_mismatch_is_drift(tmp_path):
    apm, plugin = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\n",
        {"name": "gitapex", "version": "0.2.0"},
    )
    findings = drift.find_drift(apm, plugin)
    assert findings == [("version", "0.2.0", "0.1.0")]


def test_name_mismatch_is_drift(tmp_path):
    apm, plugin = _write_pair(
        tmp_path,
        "name: wrong\nversion: 0.1.0\n",
        {"name": "gitapex", "version": "0.1.0"},
    )
    findings = drift.find_drift(apm, plugin)
    assert findings == [("name", "gitapex", "wrong")]


def test_missing_field_fails_loudly(tmp_path):
    apm, plugin = _write_pair(
        tmp_path,
        "dependencies:\n  apm: []\n",  # no name/version
        {"name": "gitapex", "version": "0.1.0"},
    )
    with pytest.raises(KeyError):
        drift.find_drift(apm, plugin)


def test_repository_manifests_are_in_lockstep():
    """The gate: real apm.yml must mirror plugin.json's name and version."""
    findings = drift.find_drift()
    assert findings == [], f"apm manifest drift: {findings}"

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

_VALID_APM = "name: gitapex\nversion: 0.1.0\n"
_VALID_PLUGIN = {"name": "gitapex", "version": "0.1.0"}


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


def test_missing_field_in_plugin_json_fails_loudly(tmp_path):
    # Regression: find_drift checks plugin_data's fields before apm_data's
    # (line 51 vs. line 53) -- a plugin.json missing a mirrored field must
    # raise too, not only an apm.yml that's missing one.
    apm, plugin = _write_pair(
        tmp_path,
        _VALID_APM,
        {"name": "gitapex"},  # no version
    )
    with pytest.raises(KeyError, match=r"plugin\.json"):
        drift.find_drift(apm, plugin)


def test_non_utf8_apm_yml_raises_manifest_read_error(tmp_path):
    # Issue #680 Shape 2: read_text() with no UnicodeDecodeError handler
    # raised an uncaught traceback on a non-UTF-8 apm.yml.
    apm = tmp_path / "apm.yml"
    plugin = tmp_path / "plugin.json"
    apm.write_bytes(b"\xff\xfe\x00\x01")
    plugin.write_text(json.dumps(_VALID_PLUGIN))
    with pytest.raises(drift.ManifestReadError, match="not valid UTF-8"):
        drift.find_drift(apm, plugin)


def test_non_utf8_plugin_json_raises_manifest_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    plugin = tmp_path / "plugin.json"
    apm.write_text(_VALID_APM)
    plugin.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(drift.ManifestReadError, match="not valid UTF-8"):
        drift.find_drift(apm, plugin)


def test_invalid_json_syntax_in_plugin_json_raises_manifest_read_error(tmp_path):
    # Issue #699: _read_text's UnicodeDecodeError guard (#680) covers the
    # decode step, but json.loads itself had no handler -- a syntactically
    # invalid (yet valid-UTF-8) plugin.json raised an uncaught
    # json.JSONDecodeError.
    apm = tmp_path / "apm.yml"
    plugin = tmp_path / "plugin.json"
    apm.write_text(_VALID_APM)
    plugin.write_text("{not valid json,,,}")
    with pytest.raises(drift.ManifestReadError, match="not valid JSON"):
        drift.find_drift(apm, plugin)


def test_invalid_yaml_syntax_in_apm_yml_raises_manifest_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    plugin = tmp_path / "plugin.json"
    apm.write_text(": not valid yaml : : :\n")
    plugin.write_text(json.dumps(_VALID_PLUGIN))
    with pytest.raises(drift.ManifestReadError, match="not valid YAML"):
        drift.find_drift(apm, plugin)


def test_main_returns_one_and_prints_message_on_manifest_read_error(capsys, monkeypatch):
    def raise_read_error():
        raise drift.ManifestReadError("/fake/apm.yml: is not valid UTF-8: boom")

    monkeypatch.setattr(drift, "find_drift", raise_read_error)
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "/fake/apm.yml: is not valid UTF-8: boom" in out


def test_main_returns_one_and_prints_message_on_missing_field_key_error(capsys, monkeypatch):
    # Companion to the ManifestReadError case: find_drift's pre-existing
    # "fails loudly" KeyError contract (a missing mirrored field) must also
    # exit cleanly through main() rather than escape as an uncaught
    # traceback -- main() previously did not catch find_drift's own
    # documented KeyError at all.
    def raise_key_error():
        raise KeyError("/fake/plugin.json: missing required field 'version'")

    monkeypatch.setattr(drift, "find_drift", raise_key_error)
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing required field" in out


def test_repository_manifests_are_in_lockstep():
    """The gate: real apm.yml must mirror plugin.json's name and version."""
    findings = drift.find_drift()
    assert findings == [], f"apm manifest drift: {findings}"


def test_main_prints_no_drift_and_returns_zero_when_manifests_match(capsys, monkeypatch):
    # find_drift's own path-reading behavior is covered by the fixture-based
    # tests above and the live repository-manifest test below; this test
    # isolates main()'s own print/exit-code contract by stubbing find_drift.
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No apm manifest drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(capsys, monkeypatch):
    monkeypatch.setattr(
        drift, "find_drift", lambda: [("version", "0.1.0", "0.2.0")]
    )
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "apm manifest drift" in out
    assert "version: plugin.json='0.1.0' != apm.yml='0.2.0'" in out

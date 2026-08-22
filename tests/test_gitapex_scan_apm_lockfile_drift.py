"""Tests for the apm lockfile drift gate
(.github/scripts/gitapex_scan_apm_lockfile_drift.py).

The final test is the gate itself: every real apm.yml devDependencies.apm
entry must have a complete apm.lock.yaml dependencies[] entry. The rest
unit-test the detector with fixtures.
"""

from __future__ import annotations

import pathlib

import gitapex_scan_apm_lockfile_drift as drift
import pytest

_VALID_APM = "name: gitapex\nversion: 0.1.0\ndevDependencies:\n  apm:\n    - owner/complete\n"

_COMPLETE_LOCK = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
  package_type: marketplace_plugin
  deployed_files:
  - .claude/skills/complete/SKILL.md
  deployed_file_hashes:
    .claude/skills/complete/SKILL.md: sha256:deadbeef
"""


def _write_pair(tmp_path: pathlib.Path, apm: str, lock: str) -> tuple[pathlib.Path, pathlib.Path]:
    apm_manifest = tmp_path / "apm.yml"
    apm_lockfile = tmp_path / "apm.lock.yaml"
    apm_manifest.write_text(apm)
    apm_lockfile.write_text(lock)
    return apm_manifest, apm_lockfile


def test_complete_dependency_has_no_drift(tmp_path):
    apm, lock = _write_pair(tmp_path, _VALID_APM, _COMPLETE_LOCK)
    assert drift.find_drift(apm, lock) == []


def test_no_devdependencies_apm_is_clean(tmp_path):
    apm, lock = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\n",
        "dependencies: []\n",
    )
    assert drift.find_drift(apm, lock) == []


def test_devdependencies_with_no_apm_key_is_clean(tmp_path):
    apm, lock = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\ndevDependencies:\n  mcp: []\n",
        "dependencies: []\n",
    )
    assert drift.find_drift(apm, lock) == []


def test_missing_lockfile_entry_is_drift(tmp_path):
    apm, lock = _write_pair(tmp_path, _VALID_APM, "dependencies: []\n")
    findings = drift.find_drift(apm, lock)
    assert findings == [("owner/complete", "missing-lockfile-entry")]


def test_missing_deployed_files_key_is_drift(tmp_path):
    # Regression: this is exactly the #1158 shape -- cathrynlavery/diagram-design
    # landed in apm.lock.yaml with no deployed_files key at all.
    lock = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
  package_type: marketplace_plugin
"""
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    findings = drift.find_drift(apm, lock_path)
    assert findings == [("owner/complete", "missing-deployed-files")]


def test_empty_deployed_files_list_is_drift(tmp_path):
    lock = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
  package_type: marketplace_plugin
  deployed_files: []
  deployed_file_hashes: {}
"""
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    findings = drift.find_drift(apm, lock_path)
    assert findings == [("owner/complete", "missing-deployed-files")]


def test_missing_deployed_file_hashes_is_drift(tmp_path):
    lock = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
  package_type: marketplace_plugin
  deployed_files:
  - .claude/skills/complete/SKILL.md
"""
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    findings = drift.find_drift(apm, lock_path)
    assert findings == [("owner/complete", "missing-deployed-file-hashes")]


def test_deployed_files_as_truthy_scalar_is_drift(tmp_path):
    # Defeat test: a truthiness-only check (`not entry.get("deployed_files")`)
    # would let a non-empty *string* -- truthy, but not a list of paths --
    # slip past as "complete".
    lock = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
  package_type: marketplace_plugin
  deployed_files: "not-a-list"
  deployed_file_hashes:
    .claude/skills/complete/SKILL.md: sha256:deadbeef
"""
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    findings = drift.find_drift(apm, lock_path)
    assert findings == [("owner/complete", "missing-deployed-files")]


def test_deployed_file_hashes_as_truthy_scalar_is_drift(tmp_path):
    lock = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
  package_type: marketplace_plugin
  deployed_files:
  - .claude/skills/complete/SKILL.md
  deployed_file_hashes: "not-a-mapping"
"""
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    findings = drift.find_drift(apm, lock_path)
    assert findings == [("owner/complete", "missing-deployed-file-hashes")]


def test_non_marketplace_plugin_package_type_skips_deployed_files_check(tmp_path):
    # A dep-only aggregator package (verified against the real apm CLI):
    # package_type != "marketplace_plugin" permanently carries no
    # deployed_files by design, not because `apm install` never ran.
    lock = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
  package_type: apm_package
"""
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    assert drift.find_drift(apm, lock_path) == []


def test_non_marketplace_plugin_package_type_still_flags_missing_entry(tmp_path):
    # The package_type exemption only waives the deployed-file completeness
    # check on an existing entry -- a devDependency with no lockfile entry
    # at all is still drift regardless of what package_type it would carry.
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, "dependencies: []\n")
    findings = drift.find_drift(apm, lock_path)
    assert findings == [("owner/complete", "missing-lockfile-entry")]


def test_local_path_devdependency_is_skipped(tmp_path):
    # apm CLI normalizes a local-path devDependency's apm.lock.yaml
    # repo_url to a "_local/<name>" form this gate cannot reconstruct
    # (verified against the real CLI) -- out of scope, not a false drift.
    apm, lock_path = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\ndevDependencies:\n  apm:\n    - ./sibling-pkg\n",
        "dependencies: []\n",
    )
    assert drift.find_drift(apm, lock_path) == []


def test_devdependencies_apm_entry_not_a_string_raises_lockfile_read_error(tmp_path):
    # Defeat test: a YAML-typo'd mapping in place of a plain "owner/repo"
    # string must not reach the later dict-key lookup as an unhashable value.
    apm, lock_path = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\ndevDependencies:\n  apm:\n    - owner/repo: v2\n",
        "dependencies: []\n",
    )
    with pytest.raises(drift.LockfileReadError, match=r"every 'devDependencies\.apm' entry must be a string"):
        drift.find_drift(apm, lock_path)


def test_lockfile_repo_url_not_a_string_raises_lockfile_read_error(tmp_path):
    lock = "dependencies:\n- repo_url: [a, b]\n  name: complete\n"
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    with pytest.raises(drift.LockfileReadError, match="'repo_url' must be a string"):
        drift.find_drift(apm, lock_path)


def test_duplicate_repo_url_raises_lockfile_read_error(tmp_path):
    # Defeat test: a plain dict-index build (`index[repo_url] = entry`) would
    # let a later, incomplete duplicate silently overwrite -- or an earlier
    # incomplete duplicate silently mask -- another entry for the same
    # repo_url, with no diagnostic either way.
    lock = """\
lockfile_version: '1'
dependencies:
- repo_url: owner/complete
  name: complete
- repo_url: owner/complete
  name: complete
  deployed_files:
  - .claude/skills/complete/SKILL.md
  deployed_file_hashes:
    .claude/skills/complete/SKILL.md: sha256:deadbeef
"""
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    with pytest.raises(drift.LockfileReadError, match="duplicate dependencies\\[\\] entry for repo_url"):
        drift.find_drift(apm, lock_path)


def test_devdependencies_not_a_mapping_raises_lockfile_read_error(tmp_path):
    apm, lock = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\ndevDependencies:\n  - not-a-mapping\n",
        "dependencies: []\n",
    )
    with pytest.raises(drift.LockfileReadError, match="'devDependencies' must be a YAML mapping"):
        drift.find_drift(apm, lock)


def test_devdependencies_apm_not_a_list_raises_lockfile_read_error(tmp_path):
    apm, lock = _write_pair(
        tmp_path,
        "name: gitapex\nversion: 0.1.0\ndevDependencies:\n  apm: not-a-list\n",
        "dependencies: []\n",
    )
    with pytest.raises(drift.LockfileReadError, match=r"'devDependencies\.apm' must be a YAML list"):
        drift.find_drift(apm, lock)


def test_lockfile_missing_dependencies_key_raises_lockfile_read_error(tmp_path):
    apm, lock = _write_pair(tmp_path, _VALID_APM, "lockfile_version: '1'\n")
    with pytest.raises(drift.LockfileReadError, match="'dependencies' must be a YAML list"):
        drift.find_drift(apm, lock)


def test_lockfile_dependencies_entry_without_repo_url_raises_lockfile_read_error(tmp_path):
    lock = "dependencies:\n- name: complete\n"
    apm, lock_path = _write_pair(tmp_path, _VALID_APM, lock)
    with pytest.raises(drift.LockfileReadError, match="must be a mapping with a 'repo_url' field"):
        drift.find_drift(apm, lock_path)


def test_non_utf8_apm_yml_raises_lockfile_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    lock = tmp_path / "apm.lock.yaml"
    apm.write_bytes(b"\xff\xfe\x00\x01")
    lock.write_text("dependencies: []\n")
    with pytest.raises(drift.LockfileReadError, match="not valid UTF-8"):
        drift.find_drift(apm, lock)


def test_non_utf8_apm_lock_yaml_raises_lockfile_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    lock = tmp_path / "apm.lock.yaml"
    apm.write_text(_VALID_APM)
    lock.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(drift.LockfileReadError, match="not valid UTF-8"):
        drift.find_drift(apm, lock)


def test_missing_apm_yml_raises_lockfile_read_error(tmp_path):
    apm = tmp_path / "does-not-exist-apm.yml"
    lock = tmp_path / "apm.lock.yaml"
    lock.write_text("dependencies: []\n")
    with pytest.raises(drift.LockfileReadError, match="cannot be read"):
        drift.find_drift(apm, lock)


def test_missing_apm_lock_yaml_raises_lockfile_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    lock = tmp_path / "does-not-exist-apm.lock.yaml"
    apm.write_text(_VALID_APM)
    with pytest.raises(drift.LockfileReadError, match="cannot be read"):
        drift.find_drift(apm, lock)


def test_apm_yml_as_yaml_list_raises_lockfile_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    lock = tmp_path / "apm.lock.yaml"
    apm.write_text("- name\n- version\n")
    lock.write_text("dependencies: []\n")
    with pytest.raises(drift.LockfileReadError, match="must be a YAML mapping"):
        drift.find_drift(apm, lock)


def test_apm_lock_yaml_as_yaml_list_raises_lockfile_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    lock = tmp_path / "apm.lock.yaml"
    apm.write_text(_VALID_APM)
    lock.write_text("- dependencies\n")
    with pytest.raises(drift.LockfileReadError, match="must be a YAML mapping"):
        drift.find_drift(apm, lock)


def test_invalid_yaml_syntax_in_apm_yml_raises_lockfile_read_error(tmp_path):
    apm = tmp_path / "apm.yml"
    lock = tmp_path / "apm.lock.yaml"
    apm.write_text(": not valid yaml : : :\n")
    lock.write_text("dependencies: []\n")
    with pytest.raises(drift.LockfileReadError, match="not valid YAML"):
        drift.find_drift(apm, lock)


def test_main_returns_one_and_prints_message_on_lockfile_read_error(capsys, monkeypatch):
    def raise_read_error():
        raise drift.LockfileReadError("/fake/apm.lock.yaml: is not valid UTF-8: boom")

    monkeypatch.setattr(drift, "find_drift", raise_read_error)
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "/fake/apm.lock.yaml: is not valid UTF-8: boom" in out


def test_main_prints_no_drift_and_returns_zero_when_clean(capsys, monkeypatch):
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No apm lockfile drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(capsys, monkeypatch):
    monkeypatch.setattr(drift, "find_drift", lambda: [("owner/repo", "missing-deployed-files")])
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "apm lockfile drift" in out
    assert "owner/repo: missing-deployed-files" in out


def test_repository_apm_lockfile_is_complete():
    """The gate: every real apm.yml devDependencies.apm entry must have a
    complete apm.lock.yaml dependencies[] entry."""
    findings = drift.find_drift()
    assert findings == [], f"apm lockfile drift: {findings}"

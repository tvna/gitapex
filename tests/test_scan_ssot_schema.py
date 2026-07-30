"""Tests for the ssot.json registry drift gate (.github/scripts/scan_ssot_schema.py).

The final test is the gate itself: the repository's real .gitapex/ssot.json
must validate against .gitapex/ssot.schema.json and have no script/policy-ref/
cluster drift. The rest unit-test the detector with fixtures, validated
against the real schema file (there is only one schema to test against).
"""

from __future__ import annotations

import json
import pathlib

import scan_ssot_schema as drift

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_VALID_INSTANCE = {
    "meta": {
        "schema_version": "1.0.0",
        "tracking_issue": 123,
        "status": "active",
        "phase": "phase-0",
    },
    "policy_sources": [
        {
            "id": "example-policy",
            "path": "pyproject.toml",
            "format": "toml",
            "authority": "test fixture",
        }
    ],
    "gates": [
        {
            "id": "example-gate",
            "kind": "script",
            "script": "hooks/check-bash-safety.sh",
            "rule": "test fixture rule",
            "planes": ["ci"],
            "trigger": "test fixture trigger",
            "policy_refs": ["example-policy"],
            "cluster": "example-cluster",
            "tracking_issue": None,
            "status": "active",
            "supersedes": None,
        }
    ],
    "clusters": {"example-cluster": "an example cluster"},
}


def _write_instance(tmp_path: pathlib.Path, instance: dict) -> pathlib.Path:
    path = tmp_path / "ssot.json"
    path.write_text(json.dumps(instance))
    return path


def test_valid_instance_has_no_drift(tmp_path):
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_missing_required_field_is_flagged(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    del bad["gates"][0]["kind"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("schema:" in f and "kind" in f for f in findings)


def test_missing_kind_produces_one_schema_error_not_three(tmp_path):
    # Regression: the schema's per-kind if/then blocks each pair "properties:
    # kind const X" with "required: [kind]" so a gate missing kind entirely
    # doesn't vacuously satisfy both the script-kind and native-kind if
    # branches and produce three duplicate "required" errors (kind, script,
    # native_rule) instead of the one real one (kind).
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    del bad["gates"][0]["kind"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    schema_findings = [f for f in findings if f.startswith("schema:")]
    assert len(schema_findings) == 1
    assert "kind" in schema_findings[0]


def test_missing_script_file_is_flagged(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["script"] = "hooks/does-not-exist.sh"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(
        "script-drift" in f and "does-not-exist.sh" in f for f in findings
    )


def test_array_script_partial_miss_is_flagged(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["script"] = ["hooks/check-bash-safety.sh", "hooks/missing.sh"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("script-drift" in f and "missing.sh" in f for f in findings)
    assert not any("check-bash-safety.sh" in f for f in findings)


def test_native_kind_has_no_script_requirement(tmp_path):
    native = json.loads(json.dumps(_VALID_INSTANCE))
    native["gates"][0]["kind"] = "native"
    del native["gates"][0]["script"]
    native["gates"][0]["native_rule"] = "a GitHub-native rule with no repo file"
    instance_path = _write_instance(tmp_path, native)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert findings == []


def test_dangling_policy_ref_is_flagged(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["policy_refs"] = ["nonexistent-policy"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(
        "policy-ref-drift" in f and "nonexistent-policy" in f for f in findings
    )


def test_dangling_cluster_is_flagged(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["cluster"] = "nonexistent-cluster"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(
        "cluster-drift" in f and "nonexistent-cluster" in f for f in findings
    )


def test_explicit_null_gates_does_not_crash(tmp_path):
    # Regression: instance.get("gates", []) only substitutes the default for
    # a *missing* key -- an explicit JSON null (schema-invalid, but not
    # impossible in a hand-edited file) must not crash the reference checks
    # with an unhandled TypeError before the schema violation is reported.
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"] = None
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings)


def test_explicit_null_policy_refs_does_not_crash(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["policy_refs"] = None
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings)


def test_explicit_null_clusters_does_not_crash(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["clusters"] = None
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings)


def test_duplicate_gate_id_is_flagged(tmp_path):
    dup = json.loads(json.dumps(_VALID_INSTANCE))
    dup["gates"].append(json.loads(json.dumps(dup["gates"][0])))
    instance_path = _write_instance(tmp_path, dup)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(
        "duplicate-id" in f and "example-gate" in f and "2 times" in f
        for f in findings
    )


def test_duplicate_policy_source_id_is_flagged(tmp_path):
    dup = json.loads(json.dumps(_VALID_INSTANCE))
    dup["policy_sources"].append(json.loads(json.dumps(dup["policy_sources"][0])))
    instance_path = _write_instance(tmp_path, dup)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(
        "duplicate-id" in f and "example-policy" in f and "2 times" in f
        for f in findings
    )


def test_duplicate_id_check_skips_entries_missing_an_id(tmp_path):
    # An entry with no id at all (schema-invalid, caught separately by
    # find_schema_violations) must not be miscounted as a "duplicate" of
    # itself or of any real id -- it's simply skipped by this check.
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    second_gate = json.loads(json.dumps(bad["gates"][0]))
    del second_gate["id"]
    bad["gates"].append(second_gate)
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert not any("duplicate-id" in f for f in findings)


def test_script_paths_defaults_to_empty_when_absent():
    assert drift._script_paths({"kind": "native"}) == []


def test_cluster_values_defaults_to_empty_when_absent():
    assert drift._cluster_values({}) == []


def test_repository_ssot_is_schema_valid_and_drift_free():
    """The gate: the real .gitapex/ssot.json must validate against the real
    .gitapex/ssot.schema.json and carry no script/policy-ref/cluster drift."""
    findings = drift.find_drift()
    assert findings == [], f"ssot.json drift: {findings}"


def test_main_prints_no_drift_and_returns_zero_when_clean(capsys, monkeypatch):
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No ssot.json drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(capsys, monkeypatch):
    monkeypatch.setattr(drift, "find_drift", lambda: ["script-drift: example: missing"])
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "ssot.json drift:" in out
    assert "script-drift: example: missing" in out

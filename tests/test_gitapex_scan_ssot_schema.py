"""Tests for the ssot.json registry drift gate (.github/scripts/gitapex_scan_ssot_schema.py).

The final test is the gate itself: the repository's real .gitapex/ssot.json
must validate against .gitapex/ssot.schema.json and have no script/policy-ref/
cluster drift. The rest unit-test the detector with fixtures, validated
against the real schema file (there is only one schema to test against).
"""

from __future__ import annotations

import json
import pathlib

import gitapex_scan_ssot_schema as drift
import pytest

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
    assert any("script-drift" in f and "does-not-exist.sh" in f for f in findings)


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
    assert any("policy-ref-drift" in f and "nonexistent-policy" in f for f in findings)


def test_dangling_cluster_is_flagged(tmp_path):
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["cluster"] = "nonexistent-cluster"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("cluster-drift" in f and "nonexistent-cluster" in f for f in findings)


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
    assert any("duplicate-id" in f and "example-gate" in f and "2 times" in f for f in findings)


def test_duplicate_policy_source_id_is_flagged(tmp_path):
    dup = json.loads(json.dumps(_VALID_INSTANCE))
    dup["policy_sources"].append(json.loads(json.dumps(dup["policy_sources"][0])))
    instance_path = _write_instance(tmp_path, dup)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("duplicate-id" in f and "example-policy" in f and "2 times" in f for f in findings)


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


def test_parse_registry_succeeds_on_valid_instance_with_correct_typed_values():
    """The pydantic model's own success path: a well-formed-per-schema
    instance parses into a typed SsotRegistry whose nested Gate/PolicySource
    objects carry the expected field values (not just "truthy")."""
    registry = drift._parse_registry(_VALID_INSTANCE)
    assert registry is not None
    assert registry.meta.tracking_issue == 123
    assert registry.meta.status == "active"
    assert len(registry.policy_sources) == 1
    assert registry.policy_sources[0].id == "example-policy"
    assert registry.policy_sources[0].format == "toml"
    assert len(registry.gates) == 1
    gate = registry.gates[0]
    assert gate.id == "example-gate"
    assert gate.kind == "script"
    assert gate.script == "hooks/check-bash-safety.sh"
    assert gate.policy_refs == ["example-policy"]
    assert gate.cluster == "example-cluster"
    assert gate.tracking_issue is None
    assert gate.supersedes is None
    assert registry.clusters == {"example-cluster": "an example cluster"}


def test_parse_registry_returns_none_without_crashing_on_invalid_instance():
    """The pydantic model's own rejection path: an instance missing a
    required Gate field (schema-invalid too) fails the pydantic parse and
    _parse_registry reports that as None rather than raising -- the
    graceful-degradation contract find_script_drift/find_policy_ref_drift/
    find_cluster_drift all rely on."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    del bad["gates"][0]["kind"]
    assert drift._parse_registry(bad) is None


def test_parse_registry_rejects_gate_missing_id_even_though_duplicate_id_check_does_not_crash():
    """Companion to test_duplicate_id_check_skips_entries_missing_an_id:
    confirms *why* find_script_drift/find_policy_ref_drift/find_cluster_drift
    see nothing for that fixture's second gate -- the pydantic parse of the
    whole registry fails outright (id is required, no default), not just
    that one entry silently drops out."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    second_gate = json.loads(json.dumps(bad["gates"][0]))
    del second_gate["id"]
    bad["gates"].append(second_gate)
    assert drift._parse_registry(bad) is None


def test_kind_script_missing_script_field_does_not_crash_or_false_flag(tmp_path):
    # The pydantic Gate model deliberately does not re-implement the
    # schema's if/then ("kind: script" requires "script") -- that
    # conditional-requirement check stays jsonschema's job alone. So a gate
    # missing "script" while kind=="script" fails jsonschema (schema
    # violation reported) but still parses into a Gate with script=None; the
    # regression this guards is find_script_drift skipping that gate's
    # script check gracefully instead of raising or fabricating a
    # script-drift finding for a script path that was never given.
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    del bad["gates"][0]["script"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("schema:" in f and "script" in f for f in findings)
    assert not any("script-drift" in f for f in findings)


def test_script_paths_returns_string_and_list_values_unchanged():
    # Companion to test_script_paths_defaults_to_empty_when_absent: covers
    # this legacy dict-based helper's non-empty branch too (kept for its own
    # direct test contract; no longer called by find_script_drift, which
    # normalizes Gate.script via _as_list instead).
    assert drift._script_paths({"script": "a.sh"}) == ["a.sh"]
    assert drift._script_paths({"script": ["a.sh", "b.sh"]}) == ["a.sh", "b.sh"]


def test_cluster_values_returns_string_and_list_values_unchanged():
    # Companion to test_cluster_values_defaults_to_empty_when_absent: covers
    # this legacy dict-based helper's non-empty branch too (kept for its own
    # direct test contract; no longer called by find_cluster_drift, which
    # normalizes Gate.cluster via _as_list instead).
    assert drift._cluster_values({"cluster": "c1"}) == ["c1"]
    assert drift._cluster_values({"cluster": ["c1", "c2"]}) == ["c1", "c2"]


def test_as_list_normalizes_none_string_and_list():
    assert drift._as_list(None) == []
    assert drift._as_list("a.sh") == ["a.sh"]
    assert drift._as_list(["a.sh", "b.sh"]) == ["a.sh", "b.sh"]


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


# ---------------------------------------------------------------------------
# Issue #680: a registry that is valid JSON but not an object (Shape 1), or
# not valid UTF-8/JSON at all (Shape 2), must fail via RegistryReadError and
# exit 1 with the offending filename -- never an uncaught traceback.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_json", ["[]", '"a string"', "1", "null", "true"])
def test_non_object_top_level_json_does_not_crash(tmp_path, bad_json):
    # Regression: json.loads("[]") etc. all parse fine, so find_duplicate_ids'
    # _get_list(instance, key) used to reach `instance.get(key)` on a
    # non-dict `instance` and raise an uncaught AttributeError.
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text(bad_json)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings)


def test_non_dict_gates_entry_does_not_crash(tmp_path):
    # Regression (found by adversarial review of this same fix): a
    # schema-valid-*shaped* gates[] array can still carry a non-dict entry
    # (e.g. a bare int) -- find_duplicate_ids' entry.get("id") used to
    # raise an uncaught AttributeError on such an entry, one level deeper
    # than the whole-document non-object case above.
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text(json.dumps({"gates": [1, 2, 3], "policy_sources": []}))
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings)
    assert not any(f.startswith("duplicate-id:") for f in findings)


def test_non_dict_policy_sources_entry_does_not_crash(tmp_path):
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text(json.dumps({"gates": [], "policy_sources": ["not-a-dict"]}))
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings)
    assert not any(f.startswith("duplicate-id:") for f in findings)


@pytest.mark.parametrize("bad_id", [["a", "b"], {"x": 1}, 42, True, None])
def test_non_string_id_does_not_crash(tmp_path, bad_id):
    # Issue #699: a gates[] entry that IS a dict but whose "id" value isn't
    # a string (list/dict are unhashable, but int/bool/null are also
    # schema-invalid) used to raise TypeError/silently miscount at
    # seen[entry_id] = ... -- one field narrower than the non-dict-entry
    # case above.
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text(json.dumps({"gates": [{"id": bad_id}], "policy_sources": []}))
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings)
    assert not any(f.startswith("duplicate-id:") for f in findings)


def test_unreadable_registry_path_raises_registry_read_error(tmp_path):
    # Covers _load_json's OSError branch (e.g. a path that simply doesn't
    # exist) distinctly from the UnicodeDecodeError/JSONDecodeError branches
    # below.
    instance_path = tmp_path / "does-not-exist" / "ssot.json"
    with pytest.raises(drift.RegistryReadError, match="cannot be read"):
        drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)


def test_non_utf8_registry_raises_registry_read_error_not_a_traceback(tmp_path):
    instance_path = tmp_path / "ssot.json"
    instance_path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(drift.RegistryReadError, match="not valid UTF-8"):
        drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)


def test_invalid_json_syntax_raises_registry_read_error_not_a_traceback(tmp_path):
    instance_path = tmp_path / "ssot.json"
    instance_path.write_text("{not json")
    with pytest.raises(drift.RegistryReadError, match="not valid JSON"):
        drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)


def test_get_list_defaults_to_empty_when_d_is_not_a_dict():
    assert drift._get_list([], "gates") == []
    assert drift._get_list("not a dict", "gates") == []
    assert drift._get_list(1, "gates") == []


def test_main_prints_message_and_returns_one_on_registry_read_error(capsys, monkeypatch):
    def raise_read_error():
        raise drift.RegistryReadError("/fake/ssot.json: is not valid UTF-8: boom")

    monkeypatch.setattr(drift, "find_drift", raise_read_error)
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "ssot.json drift:" in out
    assert "/fake/ssot.json: is not valid UTF-8: boom" in out

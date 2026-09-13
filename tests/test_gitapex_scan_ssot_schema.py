"""Tests for the ssot.json registry drift gate (.github/scripts/gitapex_scan_ssot_schema.py).

The final test is the gate itself: the repository's real .gitapex/ssot.json
must validate against .gitapex/ssot.schema.json and have no script/policy-ref/
cluster drift. The rest unit-test the detector with fixtures, validated
against the real schema file (there is only one schema to test against).
"""

from __future__ import annotations

import copy
import json
import pathlib
import typing

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
            "local_exclusion": "test fixture: no working-tree-only form",
            "trigger": "test fixture trigger",
            "policy_refs": ["example-policy"],
            "cluster": "example-cluster",
            "tracking_issue": None,
            "status": "active",
            "supersedes": None,
            "bypass_review_status": "not-yet-reviewed",
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


def test_parse_registry_succeeds_with_new_optional_gate_fields():
    """Issue #1231: a gate carrying fail_mode/target/bypass_review_status
    (all optional, schema-valid) must still parse into a typed Gate --
    guards the exact blind spot the new fields could otherwise introduce:
    Gate's own extra="forbid" rejecting an unrecognized key would make
    SsotRegistry.model_validate fail on every gate carrying it, silently
    disabling every reference-drift check below for the whole registry."""
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["fail_mode"] = {"on_error": "fail-open", "rationale": "test fixture"}
    instance["gates"][0]["target"] = [{"kind": "bash-pattern", "ref": "test fixture"}]
    instance["gates"][0]["bypass_review_status"] = "not-yet-reviewed"
    registry = drift._parse_registry(instance)
    assert registry is not None
    gate = registry.gates[0]
    assert gate.fail_mode is not None
    assert gate.fail_mode.on_error == "fail-open"
    assert gate.fail_mode.rationale == "test fixture"
    assert gate.target is not None
    assert gate.target[0].kind == "bash-pattern"
    assert gate.target[0].ref == "test fixture"
    assert gate.bypass_review_status == "not-yet-reviewed"


def test_a_gate_carrying_preconditions_validates_against_both_layers(tmp_path):
    """Issue #1566: a gate carrying preconditions (both optional sub-keys
    together, schema-valid) must validate against the raw JSON Schema AND
    parse into a typed Gate with the expected nested field values -- the
    same two-layer proof pattern as fail_mode/target above, applied to the
    new preconditions field this task introduces."""
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["preconditions"] = {
        "requires_full_history": True,
        "requires_python_packages": ["pydantic"],
    }
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []
    registry = drift._parse_registry(instance)
    assert registry is not None
    gate = registry.gates[0]
    assert gate.preconditions is not None
    assert gate.preconditions.requires_full_history is True
    assert gate.preconditions.requires_python_packages == ["pydantic"]


def test_a_gate_with_an_unrecognized_precondition_sub_key_is_rejected_by_both_layers(tmp_path):
    """Defeat test for the above: an unrecognized sub-key under
    preconditions must be rejected by the raw JSON-Schema check
    (additionalProperties: false, matching every other object in this
    schema) AND fail the pydantic parse (GatePreconditions' own
    extra='forbid') -- the same two-layer proof pattern as
    test_an_unrecognized_target_kind_is_rejected_by_both_layers above."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["preconditions"] = {"requires_something_undocumented": True}
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings), findings
    assert drift._parse_registry(bad) is None


@pytest.mark.parametrize(
    "packages",
    [
        pytest.param([], id="empty-list"),
        pytest.param([""], id="empty-string-item"),
        pytest.param(["pydantic", ""], id="one-good-one-empty"),
    ],
)
def test_a_degenerate_requires_python_packages_list_is_rejected_end_to_end(tmp_path, packages):
    """Issue #1566, step-8 adversarial review. The schema declares
    `minItems: 1` and `items.minLength: 1` on
    `preconditions.requires_python_packages`; the pydantic
    `GatePreconditions` model types the same field as a plain
    `list[str] | None` and accepts both degenerate shapes on its own.

    That asymmetry is DELIBERATE and matches every sibling model in this
    file's module: `Gate.rule`, `Gate.policy_refs`, `GateFailMode.rationale`
    and `GateTargetEntry.ref` all carry the schema's `minLength`/`minItems`
    constraints on the schema side only. `GateFailMode`'s own docstring
    states the division outright -- "jsonschema is the strict validator;
    this is the secondary typed-access layer". Adding a constraint to
    `GatePreconditions` alone would make it the single model that
    duplicates a schema rule, creating exactly the two-places-to-update
    drift this layering exists to avoid.

    What must hold is the end-to-end contract, which this pins: `find_drift`
    runs the strict layer first, so a degenerate list is rejected by the
    wired gate regardless of what the typed-access layer alone would
    accept. It matters concretely -- `check-pr-skill-audit-disclosure.sh`
    reads this exact list out of the registry and probes each entry, so
    `[]` would silently disable that hook's dependency pre-check and `[""]`
    would make it deny naming an empty package.
    """
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["preconditions"] = {"requires_python_packages": packages}
    instance_path = _write_instance(tmp_path, bad)

    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)

    assert any(f.startswith("schema:") for f in findings), findings


def test_gate_preconditions_matches_its_sibling_models_strictness_convention():
    """Pins the layering the test above depends on, so a future edit that
    tightens `GatePreconditions` in isolation has to confront the
    convention rather than silently diverge from it: the typed-access
    models carry no value-level length constraints, only shape and type.
    If this repository ever decides the pydantic layer SHOULD mirror the
    schema's `minLength`/`minItems`, that is a deliberate change across
    every model here -- not this one field alone."""
    assert drift.GatePreconditions.model_validate({"requires_python_packages": []}).requires_python_packages == []
    assert drift.GateFailMode.model_validate({"on_error": "fail-open", "rationale": ""}).rationale == ""
    assert drift.GateTargetEntry.model_validate({"kind": "mcp-tool", "ref": ""}).ref == ""


def test_script_drift_still_caught_when_gate_carries_new_fields(tmp_path):
    """Defeat test (events-and-review-gate.md's own mandatory step 8
    requirement, constructed here at task time since it exercises this
    exact new code path directly): a gate carrying the new optional fields
    AND a broken script path must still be caught by find_script_drift, not
    silently pass because _parse_registry choked on the unrecognized fields
    and returned None -- the exact blind spot #1231's own backfill would
    introduce without this Gate model mirror."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["fail_mode"] = {"on_error": "fail-open", "rationale": "test fixture"}
    bad["gates"][0]["target"] = [{"kind": "bash-pattern", "ref": "test fixture"}]
    bad["gates"][0]["bypass_review_status"] = "not-yet-reviewed"
    bad["gates"][0]["script"] = "hooks/does-not-exist.sh"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    # The schema half's own coverage for fail_mode/target: this fixture's
    # values must stay schema-valid, so no "schema:" finding should appear
    # alongside the expected script-drift one. Absent this check, a broken
    # fail_mode/target schema definition (wrong type, a renamed required
    # key, a narrowed enum) would leave this test green regardless, since
    # find_schema_violations is never otherwise exercised against these
    # two fields anywhere in this file (the real ssot.json carries neither
    # yet) -- confirmed by adversarial review: four independent schema
    # mutations to fail_mode/target all left the full suite green before
    # this line was added.
    assert any("script-drift" in f and "does-not-exist.sh" in f for f in findings), findings
    assert not any(f.startswith("schema:") for f in findings), findings


def test_a_gate_missing_bypass_review_status_is_rejected_by_both_layers(tmp_path):
    """Issue #1232: bypass_review_status moved from optional to gate's
    required[] now that #1231 (schema shape + 62-gate backfill) and this
    issue's own dimensions-numbering-drift top-up together guarantee 100%
    live coverage. A gate missing the key must fail the raw schema check
    (not just happen to still parse) -- the same two-layer proof pattern as
    the runtime-resolved-reference tests above, applied to a required-key
    tightening instead of an enum widening."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    del bad["gates"][0]["bypass_review_status"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") and "bypass_review_status" in f for f in findings), findings
    assert drift._parse_registry(bad) is None


def test_reviewed_found_listed_below_is_rejected_by_both_layers(tmp_path):
    """Adversarial review of this PR (CodeRabbit) found: the schema still
    accepted 'reviewed-found-listed-below' even though known_bypasses --
    the array that value claims to point at -- is not a field in this
    schema at all yet (issue #1232's own explicit non-goal). A gate could
    therefore make a schema-valid but false bypass-disclosure claim, with
    additionalProperties: false powerless to catch it since there is no
    known_bypasses key to be missing. Narrowed the enum to the two values
    with something real behind them; re-add the third only in the same
    change that adds known_bypasses. Both layers must reject it -- the
    same two-layer proof pattern as every other enum change in this file."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["bypass_review_status"] = "reviewed-found-listed-below"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings), findings
    assert drift._parse_registry(bad) is None


def test_runtime_resolved_reference_is_a_valid_target_kind(tmp_path):
    """Issue #1232: target.kind's 7th value, for a target whose identity is
    only resolvable at runtime (live platform state or an arbitrary
    per-instance pointer) rather than from committed source. Must be
    schema-valid AND parse into the typed GateTargetEntry -- the same
    two-layer gap #1231's own adversarial review found for the first three
    fields, checked here from the start instead of after the fact."""
    good = json.loads(json.dumps(_VALID_INSTANCE))
    good["gates"][0]["target"] = [{"kind": "runtime-resolved-reference", "ref": "test fixture"}]
    instance_path = _write_instance(tmp_path, good)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []
    registry = drift._parse_registry(good)
    assert registry is not None
    assert registry.gates[0].target[0].kind == "runtime-resolved-reference"


def test_an_unrecognized_target_kind_is_rejected_by_both_layers(tmp_path):
    """Defeat test for the above: a target.kind value outside the (now
    7-member) enum must be rejected by the raw JSON-Schema check AND fail
    the pydantic parse -- the name already claimed both layers, but the
    body originally only asserted the schema half; adversarial review
    confirmed the gap empirically by widening GateTargetEntry.kind to a
    bare str and watching this test (and all 87 others) stay green. Guards
    against either layer silently becoming open (e.g. a stray oneOf/anyOf
    in the schema, or a Literal quietly widened to str in the model)."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["target"] = [{"kind": "not-a-real-kind", "ref": "test fixture"}]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings), findings
    assert drift._parse_registry(bad) is None


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


def test_format_checker_rejects_out_of_range_date():
    # Refs #755: the format-checker backport. .gitapex/ssot.schema.json has
    # no date-typed field today (confirmed: no live effect on the real
    # registry yet), so this is a constructed schema+instance pair rather
    # than a .gitapex/ssot.json fixture -- it proves find_schema_violations
    # now rejects an out-of-range calendar date the same way
    # gitapex_scan_skill_metadata_schema.py's own scanner already does,
    # via the shared _gitapex_schema_validation.build_validator, so the
    # fix is already live the moment such a field is ever added.
    schema = {"type": "object", "properties": {"since": {"type": "string", "format": "date"}}}
    findings = drift.find_schema_violations({"since": "2026-02-30"}, schema)
    assert any("since" in f for f in findings)


def _local_gate(**overrides):
    """_VALID_INSTANCE with its one gate rewritten onto the local plane --
    the shape .github/scripts/gitapex_gate_local_preflight.py discovers (issue
    #876)."""
    instance = copy.deepcopy(_VALID_INSTANCE)
    gate = instance["gates"][0]
    gate.pop("local_exclusion")
    gate["planes"] = ["ci", "local"]
    gate["local_invocation"] = ["python3", "hooks/check-bash-safety.sh"]
    gate.update(overrides)
    return instance


def test_local_plane_gate_with_a_real_invocation_has_no_drift(tmp_path):
    instance_path = _write_instance(tmp_path, _local_gate())
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_local_invocation_referencing_a_missing_file_is_flagged(tmp_path):
    instance = _local_gate(local_invocation=["python3", ".github/scripts/gitapex_gone.py"])
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local-invocation-drift" in f and "gitapex_gone.py" in f for f in findings)


def test_local_stdin_referencing_a_missing_file_is_flagged(tmp_path):
    instance = _local_gate(local_stdin=["python3", ".github/scripts/gitapex_gone.py"])
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local-invocation-drift" in f and "local_stdin" in f for f in findings)


def test_local_plane_without_an_invocation_is_schema_invalid(tmp_path):
    instance = _local_gate()
    del instance["gates"][0]["local_invocation"]
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local_invocation" in f and "required" in f for f in findings)


def test_local_plane_may_not_also_carry_an_exclusion(tmp_path):
    instance = _local_gate(local_exclusion="contradicts the local plane")
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) != []


def test_non_local_gate_without_an_exclusion_is_schema_invalid(tmp_path):
    """The drift-test branch of issue #876's third acceptance criterion: a
    new gate cannot land unwired *and* undocumented."""
    instance = copy.deepcopy(_VALID_INSTANCE)
    del instance["gates"][0]["local_exclusion"]
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local_exclusion" in f and "required" in f for f in findings)


def test_non_local_gate_may_not_carry_a_local_invocation(tmp_path):
    instance = copy.deepcopy(_VALID_INSTANCE)
    instance["gates"][0]["local_invocation"] = ["true"]
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) != []


def test_local_stdin_requires_a_local_invocation(tmp_path):
    instance = _local_gate()
    del instance["gates"][0]["local_invocation"]
    instance["gates"][0]["planes"] = ["ci"]
    instance["gates"][0]["local_exclusion"] = "no working-tree form"
    instance["gates"][0]["local_stdin"] = ["git", "diff"]
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) != []


@pytest.mark.parametrize(
    "token",
    [
        "--merge-base",  # an option, not a path
        "*.py",  # git's own pathspec, resolved by git
        "apm_modules/*,skills/x/y.py",  # a delimited list value (xenon --exclude)
        "origin/main",  # a git revision with no file suffix
        "pyproject.toml",  # no directory separator: indistinguishable from an argument
        "ruff",
        "",
    ],
)
def test_non_path_argv_tokens_are_never_stat_checked(token):
    assert drift._looks_like_repo_path(token) is False


@pytest.mark.parametrize(
    "token",
    [".github/scripts/gitapex_scan_ssot_schema.py", "hooks/check-bash-safety.sh", ".github/workflows/test.yml"],
)
def test_repo_relative_paths_are_recognized(token):
    assert drift._looks_like_repo_path(token) is True


def test_local_invocation_drift_returns_empty_without_a_parsed_registry():
    assert drift.find_local_invocation_drift(None, REPO_ROOT) == []


def test_local_shell_argv_returns_empty_without_a_parsed_registry():
    assert drift.find_local_shell_argv(None) == []


def test_local_identity_drift_returns_empty_without_a_parsed_registry():
    assert drift.find_local_invocation_identity_drift(None) == []


@pytest.mark.parametrize(
    "argv",
    [
        ["sh", "-c", "echo pwned"],
        ["bash", "hooks/check-bash-safety.sh"],
        ["/bin/sh", "-c", "echo pwned"],
        ["env", "python3", "hooks/check-bash-safety.sh"],
        ["uv", "run", "xargs", "hooks/check-bash-safety.sh"],
    ],
)
def test_a_shell_bearing_local_invocation_is_flagged(tmp_path, argv):
    """`.gitapex/ssot.json` became a carrier of commands a contributor is
    told to run before every push. Exec-form subprocess.run stops the runner
    introducing a shell; it does not stop the argv from being one."""
    instance = _local_gate(local_invocation=argv)
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local-shell-argv" in f for f in findings), findings


def test_inline_interpreter_code_is_flagged(tmp_path):
    instance = _local_gate(local_invocation=["uv", "run", "python3", "-c", "print('pwned')"])
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local-shell-argv" in f and "inline code" in f for f in findings), findings


def test_a_config_flag_before_any_interpreter_is_not_inline_code(tmp_path):
    """Regression: `git -c core.quotePath=false diff ...` is a real
    local_stdin value in this registry today. Scanning argv for `-c` without
    anchoring it to an interpreter's own position false-flags it."""
    instance = _local_gate(
        local_stdin=["git", "-c", "core.quotePath=false", "diff", "--merge-base", "origin/main", "HEAD"]
    )
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_local_invocation_naming_no_script_of_its_own_is_flagged(tmp_path):
    """The false-clean this closes: pointing a wired gate's argv at `true`
    (or at a different gate's real script) is schema-valid, passes the
    existence check, and makes the preflight report PASS for a gate that
    never ran."""
    instance = _local_gate(local_invocation=["true"])
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local-invocation-identity-drift" in f for f in findings), findings


def test_local_invocation_naming_a_different_gates_script_is_flagged(tmp_path):
    instance = _local_gate(local_invocation=["python3", ".github/scripts/gitapex_scan_ssot_schema.py"])
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local-invocation-identity-drift" in f for f in findings), findings


def test_a_workflow_only_gate_is_exempt_from_the_identity_rule(tmp_path):
    """A gate whose every registered script is a workflow file has its
    enforcement inline in that workflow, with no script file to name --
    python-lint and cyclomatic-complexity-floor are both that shape. The
    exemption is a property of the entry, checked here, not an id
    allowlist."""
    instance = _local_gate(script=".github/workflows/lint.yml", local_invocation=["uv", "run", "ruff", "check", "."])
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_a_mixed_workflow_and_script_gate_is_not_exempt(tmp_path):
    instance = _local_gate(
        script=[".github/workflows/test.yml", ".github/scripts/gitapex_scan_ssot_schema.py"],
        local_invocation=["true"],
    )
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("local-invocation-identity-drift" in f for f in findings), findings


@pytest.mark.parametrize("token", ["/etc/os-release.json", "../outside/gone.py", "a/../../b/gone.py"])
def test_a_local_invocation_token_escaping_the_repo_root_is_flagged(tmp_path, token):
    """pathlib's `/` discards its left operand for an absolute right side,
    so `repo_root / '/etc/x.json'` is just `/etc/x.json`: an absolute token
    that happens to exist on its author's machine would validate there and
    fail on a CI runner, making this gate's verdict machine-dependent."""
    instance = _local_gate(local_invocation=["python3", "hooks/check-bash-safety.sh", token])
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("must stay inside the repository root" in f for f in findings), findings


def test_a_missing_path_inside_a_comma_delimited_token_is_flagged(tmp_path):
    """Concrete today, not hypothetical: cyclomatic-complexity-floor's argv
    carries `--exclude apm_modules/*,skills/.../gitapex_check_skill_shape.py`,
    whose second element is a real path. Skipping the whole token on the
    comma silently exempted it, so renaming that file would have made the
    exclusion ineffective with this scanner still reporting clean."""
    instance = _local_gate(
        local_invocation=["python3", "hooks/check-bash-safety.sh", "--exclude", "apm_modules/*,skills/x/gone.py"]
    )
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("references missing file" in f and "skills/x/gone.py" in f for f in findings), findings


def test_a_real_path_inside_a_comma_delimited_token_passes(tmp_path):
    instance = _local_gate(
        local_invocation=[
            "python3",
            "hooks/check-bash-safety.sh",
            "--exclude",
            "apm_modules/*,skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py",
        ]
    )
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_iter_path_tokens_splits_on_commas_and_filters():
    assert drift._iter_path_tokens("apm_modules/*,skills/x/y.py") == ["skills/x/y.py"]
    assert drift._iter_path_tokens("origin/main") == []


def test_a_non_array_planes_typo_does_not_produce_inverted_guidance(tmp_path):
    """Draft 2020-12 ignores `contains` on a non-array instance, so without
    an explicit `type: array` inside the `if`, `"planes": "ci"` satisfies it
    vacuously and fires the then-branch -- telling the author to add
    local_invocation and drop local_exclusion, the opposite of what a
    CI-only gate needs. The instance is rejected either way; this asserts
    the author is told the right thing."""
    instance = copy.deepcopy(_VALID_INSTANCE)
    instance["gates"][0]["planes"] = "ci"
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("'ci' is not of type 'array'" in f for f in findings), findings
    assert not any("local_invocation" in f for f in findings), findings


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


def test_non_object_schema_raises_registry_read_error_not_a_traceback(tmp_path):
    """Deterministic-gate-quality review (issue #1232) live-reproduced this:
    a syntactically-valid-JSON-but-non-object schema file (e.g. a bare JSON
    array) reached jsonschema.Draft202012Validator's own internals and
    raised an uncaught AttributeError, falsifying RegistryReadError's own
    docstring promise ("exit 1, never a traceback"). Mirrors the identical
    guard gitapex_scan_plugin_manifest_schema.py already carries for its own
    vendored schema."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    schema_path = tmp_path / "ssot.schema.json"
    schema_path.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(drift.RegistryReadError, match="must be a JSON object"):
        drift.find_drift(instance_path, schema_path, REPO_ROOT)


def test_semantically_invalid_schema_raises_registry_read_error_not_a_traceback(tmp_path):
    """Same finding as above, the other half: an object-shaped but
    semantically-invalid JSON Schema (e.g. {"type": 1}, jsonschema's own
    canonical example) crashed with an uncaught TypeError from inside
    iter_errors instead. This exact defect class is plausible, not
    contrived: this PR's own diff hand-edits two array literals inside
    .gitapex/ssot.schema.json (required[] and target.kind's enum[])."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    schema_path = tmp_path / "ssot.schema.json"
    schema_path.write_text(json.dumps({"type": 1}))
    with pytest.raises(drift.RegistryReadError, match="not a valid JSON Schema"):
        drift.find_drift(instance_path, schema_path, REPO_ROOT)


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


# ---------------------------------------------------------------------------
# tracking_issue: single issue / multiple issues / null (issue #1425)
# ---------------------------------------------------------------------------


def test_tracking_issue_accepts_a_single_integer(tmp_path):
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["tracking_issue"] = 344
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_tracking_issue_accepts_null(tmp_path):
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["tracking_issue"] = None
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_tracking_issue_accepts_a_list_of_at_least_two_issue_numbers(tmp_path):
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["tracking_issue"] = [520, 344]
    instance_path = _write_instance(tmp_path, instance)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT) == []


def test_tracking_issue_rejects_a_single_element_array(tmp_path):
    # A one-element array is rejected so the plain-integer form stays the
    # only way to express "tracked under exactly one issue" -- otherwise
    # `344` and `[344]` would be two ways to say the same thing.
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["tracking_issue"] = [344]
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("schema:" in f and "tracking_issue" in f for f in findings)


def test_parse_registry_gate_tracking_issue_accepts_list_value():
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["tracking_issue"] = [297, 422, 426]
    registry = drift._parse_registry(instance)
    assert registry is not None
    assert registry.gates[0].tracking_issue == [297, 422, 426]


def test_tracking_issue_rejects_an_empty_array(tmp_path):
    # Defeat case: an empty array is neither "one issue" (the plain-int
    # form) nor "at least two issues" (minItems: 2) -- it must be
    # rejected, not silently treated as equivalent to null.
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["tracking_issue"] = []
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("schema:" in f and "tracking_issue" in f for f in findings)


def test_tracking_issue_rejects_a_non_integer_list_item(tmp_path):
    # Defeat case: a list item that is not an integer (a string that
    # merely looks like one) must be rejected at the schema layer, not
    # silently coerced -- the layered design this module's own docstring
    # states (jsonschema is the strict validator; pydantic is a secondary
    # typed-access layer that runs only after schema validation passes).
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["tracking_issue"] = [520, "344"]
    instance_path = _write_instance(tmp_path, instance)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any("schema:" in f and "tracking_issue" in f for f in findings)


def test_policy_source_format_literal_matches_schema_enum():
    # A prior change extended .gitapex/ssot.schema.json's own
    # policySource.format enum without also updating this module's own
    # hand-rolled PolicySource.format Literal -- a second, independent
    # source of truth for the same value set that jsonschema validation
    # alone cannot catch drifting apart, since _parse_registry runs only
    # after schema validation already passed. That divergence made
    # _parse_registry silently return None for any real instance using
    # the new value, surfaced only as a collateral pytest failure in an
    # unrelated module. This pins both sides against each other so a
    # future one-sided edit fails here instead.
    schema = json.loads(drift.SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_enum = set(schema["$defs"]["policySource"]["properties"]["format"]["enum"])
    literal_values = set(typing.get_args(drift.PolicySource.model_fields["format"].annotation))
    assert literal_values == schema_enum


# ---------------------------------------------------------------------------
# Issue #1965: skills/*/metadata/gitapex.yaml spec.contract gate ids resolve
# against .gitapex/ssot.json's own gates[], plane/shipped consistency holds,
# precondition ids are unique per contract, and handoff skill names resolve
# to real skills/*/ directories.
#
# Fixtures write the sidecar as JSON text (json.dumps), not real YAML syntax
# -- JSON is valid YAML, so yaml.safe_load parses it unmodified, and this
# avoids adding a yaml import to this test module purely for fixture
# construction. _write_skill_with_contract's own default contract always
# carries a resolving handoff.next.skill (pointing at the fixture skill
# itself) and a minimal valid goal, so a test targeting one specific check
# does not also trip the handoff/goal checks incidentally.
# ---------------------------------------------------------------------------


def _skills_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "skills"


def _write_skill_with_contract(skills_dir: pathlib.Path, skill_name: str, contract_overrides: dict) -> pathlib.Path:
    skill_dir = skills_dir / skill_name
    (skill_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# fixture skill\n", encoding="utf-8")
    contract = {
        "goal": {"endState": "fixture end state", "check": "fixture check"},
        "handoff": {"next": {"skill": skill_name}},
    }
    contract.update(contract_overrides)
    sidecar = skill_dir / "metadata" / "gitapex.yaml"
    sidecar.write_text(json.dumps({"spec": {"contract": contract}}), encoding="utf-8")
    return skill_dir


def test_contract_gate_id_unknown_is_flagged(tmp_path):
    """Issue #1965, case 1: a gates[].id naming an id not in
    .gitapex/ssot.json fails."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir, "fixture-skill", {"gates": [{"id": "no-such-gate", "plane": "ci", "shipped": False}]}
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert any("contract-gate-id-drift" in f and "no-such-gate" in f for f in findings), findings


def test_contract_invariant_gate_unknown_is_flagged(tmp_path):
    """Companion to the above for the invariants[].gate half of case 1 --
    a non-null invariants[].gate naming an unknown id fails the same way."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir, "fixture-skill", {"invariants": [{"text": "fixture invariant", "gate": "no-such-gate"}]}
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert any("contract-gate-id-drift" in f and "no-such-gate" in f for f in findings), findings


def test_contract_gate_id_known_passes(tmp_path):
    """Issue #1965, case 2: a gates[].id naming a real ssot gate id, with a
    plane/shipped pair consistent with that gate, has no drift."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)  # example-gate, planes=["ci"]
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir, "fixture-skill", {"gates": [{"id": "example-gate", "plane": "ci", "shipped": False}]}
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert findings == [], findings


def test_contract_invariant_null_gate_passes(tmp_path):
    """Issue #1965, case 3: null on invariants[].gate is an explicit
    prose-only disclosure, never checked against the registry."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir, "fixture-skill", {"invariants": [{"text": "fixture invariant", "gate": None}]}
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert findings == [], findings


def test_contract_gates_empty_list_passes(tmp_path):
    """An empty spec.contract.gates list is this block's own valid "no
    gates yet" equivalent, not a finding."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(skills_dir, "fixture-skill", {"gates": []})
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert findings == [], findings


def test_contract_gate_plane_not_declared_by_ssot_gate_is_flagged(tmp_path):
    """Issue #1965, case 4: example-gate's own ssot planes are ["ci"]; a
    contract gate resolving to example-gate but declaring "pretooluse"
    (a plane that gate does not run on) is drift. shipped=True is
    otherwise correct for the hook plane pretooluse, so only the
    plane-drift finding should fire, not a shipped-drift one too."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir, "fixture-skill", {"gates": [{"id": "example-gate", "plane": "pretooluse", "shipped": True}]}
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert any("contract-gate-plane-drift" in f and "pretooluse" in f for f in findings), findings
    assert not any("contract-gate-shipped-drift" in f for f in findings), findings


def test_contract_gate_shipped_true_on_non_hook_plane_is_flagged(tmp_path):
    """Issue #1965, case 5 (direction one): shipped=true on a ci-plane gate
    is drift -- only skills/ and hooks/ ship to a consumer install."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)  # example-gate, planes=["ci"]
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir, "fixture-skill", {"gates": [{"id": "example-gate", "plane": "ci", "shipped": True}]}
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert any("contract-gate-shipped-drift" in f for f in findings), findings
    assert not any("contract-gate-plane-drift" in f for f in findings), findings


def test_contract_gate_shipped_false_on_hook_plane_is_flagged(tmp_path):
    """Issue #1965, case 5 (direction two): shipped=false on a hook-plane
    (pretooluse/posttooluse/stop) gate is drift the same way."""
    instance = json.loads(json.dumps(_VALID_INSTANCE))
    instance["gates"][0]["planes"] = ["pretooluse"]
    instance_path = _write_instance(tmp_path, instance)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir, "fixture-skill", {"gates": [{"id": "example-gate", "plane": "pretooluse", "shipped": False}]}
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert any("contract-gate-shipped-drift" in f for f in findings), findings
    assert not any("contract-gate-plane-drift" in f for f in findings), findings


def test_contract_duplicate_precondition_id_is_flagged(tmp_path):
    """Issue #1965, case 6: a duplicated precondition[].id within one
    contract is flagged."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(
        skills_dir,
        "fixture-skill",
        {
            "precondition": [
                {"id": "dup-check", "check": "fixture check one", "onFail": "escalate"},
                {"id": "dup-check", "check": "fixture check two", "onFail": "escalate"},
            ]
        },
    )
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert any("contract-precondition-duplicate-id" in f and "dup-check" in f and "2 times" in f for f in findings), (
        findings
    )


def test_contract_precondition_duplicate_id_is_scoped_to_one_contract(tmp_path):
    """The same precondition id used once each in two different skills'
    contracts is not a collision -- uniqueness is checked within one
    contract only, never across contracts/skills."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    shared_precondition = [{"id": "shared-id", "check": "fixture check", "onFail": "escalate"}]
    _write_skill_with_contract(skills_dir, "fixture-skill-a", {"precondition": shared_precondition})
    _write_skill_with_contract(skills_dir, "fixture-skill-b", {"precondition": shared_precondition})
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert not any("contract-precondition-duplicate-id" in f for f in findings), findings


@pytest.mark.parametrize(
    "handoff_overrides,expected_bad_name",
    [
        pytest.param({"next": {"skill": "no-such-skill"}}, "no-such-skill", id="next-skill"),
        pytest.param(
            {"next": {"skill": "fixture-skill", "fallback": "no-such-fallback"}},
            "no-such-fallback",
            id="next-fallback",
        ),
        pytest.param(
            {"next": {"skill": "fixture-skill"}, "inline": ["no-such-inline"]},
            "no-such-inline",
            id="inline",
        ),
        pytest.param(
            {"next": {"skill": "fixture-skill"}, "optional": ["no-such-optional"]},
            "no-such-optional",
            id="optional",
        ),
    ],
)
def test_contract_handoff_unresolved_reference_is_flagged(tmp_path, handoff_overrides, expected_bad_name):
    """Issue #1965, case 7: handoff.next.skill, handoff.next.fallback, and
    every handoff.inline[]/optional[] entry must each resolve to a real
    skills/*/ directory."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(skills_dir, "fixture-skill", {"handoff": handoff_overrides})
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert any("contract-handoff-unresolved" in f and expected_bad_name in f for f in findings), findings


def test_contract_handoff_fallback_absent_is_not_checked(tmp_path):
    """handoff.next.fallback is optional -- its absence is not a finding."""
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    skills_dir = _skills_dir(tmp_path)
    _write_skill_with_contract(skills_dir, "fixture-skill", {"handoff": {"next": {"skill": "fixture-skill"}}})
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT, skills_dir)
    assert findings == [], findings


def test_real_repository_has_no_contract_declaring_skills_yet():
    """Foundation-only PR (issue #1965): confirmed no real skill declares
    spec.contract yet, so the new contract checks are a clean no-op
    against the real, current repository state -- pinned explicitly here
    rather than relying only on test_repository_ssot_is_schema_valid_and_
    drift_free above to notice a future change."""
    assert drift.discover_contracts() == {}
    real_registry = drift._parse_registry(json.loads(drift.SSOT_PATH.read_text(encoding="utf-8")))
    assert drift.find_contract_gate_drift(real_registry) == []
    assert drift.find_contract_precondition_duplicate_ids() == []
    assert drift.find_contract_handoff_drift() == []


def test_discover_contracts_skips_sidecar_with_no_contract_block(tmp_path):
    skills_dir = _skills_dir(tmp_path)
    skill_dir = skills_dir / "no-contract-skill"
    (skill_dir / "metadata").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# fixture\n", encoding="utf-8")
    (skill_dir / "metadata" / "gitapex.yaml").write_text(
        json.dumps({"spec": {"portability": "Portable", "capabilityAssumption": "Broad"}}), encoding="utf-8"
    )
    assert drift.discover_contracts(skills_dir) == {}


def test_discover_contracts_skips_unreadable_yaml_without_crashing(tmp_path):
    """A sidecar that fails to parse as YAML at all must not crash the
    whole ssot drift scan -- that shape defect is skill-metadata-schema-
    drift's own finding to report, not this scanner's."""
    skills_dir = _skills_dir(tmp_path)
    skill_dir = skills_dir / "broken-yaml-skill"
    (skill_dir / "metadata").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# fixture\n", encoding="utf-8")
    (skill_dir / "metadata" / "gitapex.yaml").write_text("spec:\n  contract: [unterminated", encoding="utf-8")
    assert drift.discover_contracts(skills_dir) == {}


def test_contract_gate_drift_returns_empty_without_a_parsed_registry():
    assert drift.find_contract_gate_drift(None) == []


def test_resolves_to_sibling_skill_rejects_path_like_names(tmp_path):
    skills_dir = _skills_dir(tmp_path)
    (skills_dir / "real-skill" / "SKILL.md").parent.mkdir(parents=True)
    (skills_dir / "real-skill" / "SKILL.md").write_text("# fixture\n", encoding="utf-8")
    assert drift._resolves_to_sibling_skill("real-skill", skills_dir) is True
    assert drift._resolves_to_sibling_skill("../real-skill", skills_dir) is False
    assert drift._resolves_to_sibling_skill("/etc/passwd", skills_dir) is False
    assert drift._resolves_to_sibling_skill("does-not-exist", skills_dir) is False


def test_as_dict_list_filters_non_dict_entries():
    assert drift._as_dict_list([{"id": "a"}, "not-a-dict", 1, None, {"id": "b"}]) == [{"id": "a"}, {"id": "b"}]
    assert drift._as_dict_list(None) == []
    assert drift._as_dict_list("not-a-list") == []


def test_contract_of_returns_none_for_missing_or_empty():
    assert drift._contract_of({"spec": {}}) is None
    assert drift._contract_of({"spec": {"contract": {}}}) is None
    assert drift._contract_of({"spec": {"contract": None}}) is None
    assert drift._contract_of("not-a-dict") is None
    assert drift._contract_of({"spec": {"contract": {"goal": {}}}}) == {"goal": {}}

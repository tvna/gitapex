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


def test_script_drift_still_caught_when_gate_carries_new_fields(tmp_path):
    """Defeat test (refactor-and-review-gate.md's own mandatory step 8
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
    7-member) enum must be rejected by the raw JSON-Schema check. Guards
    against the enum silently becoming open (e.g. a stray oneOf/anyOf, or a
    typo that widens rather than extends it)."""
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["gates"][0]["target"] = [{"kind": "not-a-real-kind", "ref": "test fixture"}]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH, REPO_ROOT)
    assert any(f.startswith("schema:") for f in findings), findings


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

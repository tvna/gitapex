"""Tests for the draft skill-metadata schema drift scanner
(.github/scripts/scan_skill_metadata_schema.py + .gitapex/skill-metadata.schema.json).

The final tests are the gate itself: every real skills/<name>/metadata/
gitapex.yaml in this repository must validate against the schema with no
drift. The rest unit-test each layer with fixtures: pure schema validation
(find_schema_violations), the cross-file checks the schema itself cannot
express (find_name_mismatch, find_skill_dependency_drift,
find_deprecated_replacement_drift, find_requires_cycle), and the CLI
(main()).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
import scan_skill_metadata_schema as scanner
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# A minimal but fully-populated valid SkillMetadata instance -- every gated
# block declared once, so a single copy-and-mutate per test proves the
# schema actually distinguishes valid from invalid rather than being
# vacuously permissive.
_VALID_INSTANCE: dict[str, Any] = {
    "apiVersion": "gitapex.io/v1alpha1",
    "kind": "SkillMetadata",
    "metadata": {"name": "example-skill"},
    "spec": {
        "portability": "Mixed",
        "capabilityAssumption": "Broad",
        "references": [
            {
                "kind": "decision",
                "anchor": "https://github.com/tvna/gitapex/issues/1",
                "summary": "An example decision entry.",
            }
        ],
        "skillDependencies": {
            "requires": [],
            "relatedTo": ["battle-testing-a-skill"],
        },
        "lifecycle": {
            "experimental": {
                "reason": "not yet proven",
                "trackingIssue": "https://github.com/tvna/gitapex/issues/2",
                "since": "2026-07-21",
            },
            "renamedFrom": "old-example-skill",
        },
        "executionRequirements": {
            "tools": {"read": ["repo-files"], "write": [], "shell": []},
        },
    },
}


def _copy_instance() -> Any:
    """A deep copy of _VALID_INSTANCE with type Any -- round-tripped through
    JSON (mirroring tests/test_scan_ssot_schema.py's own fixture pattern)
    rather than copy.deepcopy, so mypy --strict lets a test mutate/delete
    arbitrary nested keys freely instead of inferring _VALID_INSTANCE's own
    narrow structural type onto every copy."""
    return json.loads(json.dumps(_VALID_INSTANCE))


def _schema() -> dict[str, Any]:
    return json.loads(scanner.SCHEMA_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _violations(instance: Any) -> list[str]:
    return scanner.find_schema_violations(instance, _schema())


def _mutated(**spec_overrides: Any) -> Any:
    """A copy of _VALID_INSTANCE with spec-level overrides applied."""
    instance = _copy_instance()
    instance["spec"].update(spec_overrides)
    return instance


# ---- schema: envelope ----


def test_valid_instance_has_no_schema_violations() -> None:
    assert _violations(_VALID_INSTANCE) == []


def test_missing_api_version_is_flagged() -> None:
    instance = _copy_instance()
    del instance["apiVersion"]
    assert any("apiVersion" in v for v in _violations(instance))


def test_wrong_kind_is_flagged() -> None:
    instance = _copy_instance()
    instance["kind"] = "NotSkillMetadata"
    assert any("kind" in v for v in _violations(instance))


def test_unknown_top_level_key_is_flagged() -> None:
    instance = _copy_instance()
    instance["extra"] = "surprise"
    assert _violations(instance) != []


def test_metadata_missing_name_is_flagged() -> None:
    instance = _copy_instance()
    del instance["metadata"]["name"]
    assert any("name" in v for v in _violations(instance))


def test_metadata_unknown_key_is_flagged() -> None:
    instance = _copy_instance()
    instance["metadata"]["labels"] = {"foo": "bar"}
    assert _violations(instance) != []


# ---- schema: spec.portability / spec.capabilityAssumption ----


def test_invalid_portability_enum_is_flagged() -> None:
    assert _violations(_mutated(portability="Sortof")) != []


def test_invalid_capability_assumption_enum_is_flagged() -> None:
    assert _violations(_mutated(capabilityAssumption="Weird")) != []


def test_spec_missing_required_fields_is_flagged() -> None:
    instance = _copy_instance()
    del instance["spec"]["portability"]
    del instance["spec"]["capabilityAssumption"]
    violations = _violations(instance)
    assert any("portability" in v for v in violations)
    assert any("capabilityAssumption" in v for v in violations)


def test_unspecified_spec_key_is_tolerated() -> None:
    # spec.evalStatus is reserved-but-ungated by design (check_skill_shape.py's
    # own _parse_manifest docstring: "still deliberately skipped") -- the
    # schema's additionalProperties: true on spec must not reject it.
    assert _violations(_mutated(evalStatus={"baseline": "2026-01-01"})) == []


# ---- schema: spec.references ----


def test_empty_references_list_is_flagged() -> None:
    assert _violations(_mutated(references=[])) != []


def test_reference_item_missing_required_key_is_flagged() -> None:
    bad_item = {"kind": "decision", "anchor": "https://example.com"}
    assert _violations(_mutated(references=[bad_item])) != []


def test_reference_item_unknown_key_is_flagged() -> None:
    bad_item = {
        "kind": "decision", "anchor": "x", "summary": "y", "notes": "surprise",
    }
    assert _violations(_mutated(references=[bad_item])) != []


def test_reference_item_kind_outside_vocabulary_is_flagged() -> None:
    bad_item = {"kind": "musing", "anchor": "x", "summary": "y"}
    assert _violations(_mutated(references=[bad_item])) != []


def test_reference_item_oversized_summary_is_flagged() -> None:
    bad_item = {"kind": "decision", "anchor": "x", "summary": "y" * 501}
    assert _violations(_mutated(references=[bad_item])) != []


def test_reference_item_outcome_allows_free_form_scalars() -> None:
    item = {
        "kind": "audit", "anchor": "x", "summary": "y",
        "outcome": {"verdict": "PASS", "found": 3, "fixed": True},
    }
    assert _violations(_mutated(references=[item])) == []


# ---- schema: spec.skillDependencies ----


def test_skill_dependencies_unknown_key_is_flagged() -> None:
    deps: dict[str, Any] = {"requires": [], "relatedTo": [], "extra": []}
    assert _violations(_mutated(skillDependencies=deps)) != []


def test_skill_dependencies_item_rejects_absolute_path() -> None:
    # Schema-layer half of the path-traversal defense (adversarial review):
    # skillNameRef's kebab-case pattern rejects "/etc" outright, independent
    # of the companion scanner's own _is_bare_skill_name guard.
    deps: dict[str, Any] = {"requires": ["/etc"], "relatedTo": []}
    assert _violations(_mutated(skillDependencies=deps)) != []


def test_skill_dependencies_item_rejects_traversal_segment() -> None:
    deps: dict[str, Any] = {
        "requires": [], "relatedTo": ["../../../../../../etc"]}
    assert _violations(_mutated(skillDependencies=deps)) != []


def test_skill_dependencies_null_block_is_flagged() -> None:
    # A bare `skillDependencies:` header with nothing under it is real YAML
    # null, not an empty mapping -- must fail type: object, matching
    # check_skill_shape.py's own null/absent distinction.
    instance = _copy_instance()
    instance["spec"]["skillDependencies"] = None
    assert _violations(instance) != []


def test_skill_dependencies_absent_is_valid() -> None:
    instance = _copy_instance()
    del instance["spec"]["skillDependencies"]
    assert _violations(instance) == []


def test_requires_portability_compatible_violation() -> None:
    instance = _mutated(
        portability="Portable",
        skillDependencies={"requires": ["some-skill"], "relatedTo": []})
    assert any("requires" in v for v in _violations(instance))


def test_requires_portability_compatible_ok_when_empty() -> None:
    instance = _mutated(
        portability="Portable",
        skillDependencies={"requires": [], "relatedTo": []})
    assert _violations(instance) == []


def test_requires_portability_compatible_ok_when_not_portable() -> None:
    instance = _mutated(
        portability="Mixed",
        skillDependencies={"requires": ["some-skill"], "relatedTo": []})
    assert _violations(instance) == []


# ---- schema: spec.lifecycle ----


def test_lifecycle_unknown_key_is_flagged() -> None:
    assert _violations(_mutated(lifecycle={"unknown": {}})) != []


def test_lifecycle_experimental_missing_required_field_is_flagged() -> None:
    lifecycle = {"experimental": {"reason": "not yet proven"}}
    assert _violations(_mutated(lifecycle=lifecycle)) != []


def test_lifecycle_deprecated_missing_required_field_is_flagged() -> None:
    lifecycle = {"deprecated": {"reason": "superseded"}}
    assert _violations(_mutated(lifecycle=lifecycle)) != []


def test_lifecycle_stable_missing_since_is_flagged() -> None:
    assert _violations(_mutated(lifecycle={"stable": {}})) != []


def test_lifecycle_experimental_and_stable_are_mutually_exclusive() -> None:
    lifecycle = {
        "experimental": {
            "reason": "not yet proven",
            "trackingIssue": "https://github.com/tvna/gitapex/issues/2",
        },
        "stable": {"since": "2026-07-21"},
    }
    assert _violations(_mutated(lifecycle=lifecycle)) != []


def test_lifecycle_experimental_and_deprecated_may_coexist() -> None:
    lifecycle = {
        "experimental": {
            "reason": "not yet proven",
            "trackingIssue": "https://github.com/tvna/gitapex/issues/2",
        },
        "deprecated": {"reason": "superseded", "replacement": "some-skill"},
    }
    assert _violations(_mutated(lifecycle=lifecycle)) == []


def test_lifecycle_tracking_issue_bare_number_is_flagged() -> None:
    lifecycle = {"experimental": {"reason": "x", "trackingIssue": "#123"}}
    assert _violations(_mutated(lifecycle=lifecycle)) != []


def test_lifecycle_tracking_issue_full_url_is_valid() -> None:
    lifecycle = {
        "experimental": {
            "reason": "x",
            "trackingIssue": "https://github.com/tvna/gitapex/pull/999",
        },
    }
    assert _violations(_mutated(lifecycle=lifecycle)) == []


def test_lifecycle_date_wrong_shape_is_flagged() -> None:
    lifecycle = {"stable": {"since": "07/21/2026"}}
    assert _violations(_mutated(lifecycle=lifecycle)) != []


def test_lifecycle_date_out_of_range_is_flagged() -> None:
    # Right shape, real-calendar-invalid -- only caught because
    # find_schema_violations enables format_checker explicitly.
    lifecycle = {"stable": {"since": "2026-02-30"}}
    assert _violations(_mutated(lifecycle=lifecycle)) != []


def test_lifecycle_compatibility_guarantee_bad_enum_is_flagged() -> None:
    lifecycle = {"stable": {"since": "2026-07-21", "compatibilityGuarantee": "RC"}}
    assert _violations(_mutated(lifecycle=lifecycle)) != []


def test_lifecycle_renamed_from_is_free_form_and_unresolved() -> None:
    lifecycle = {"renamedFrom": "a-directory-that-does-not-exist"}
    # Schema-valid regardless of whether the name resolves -- renamedFrom is
    # deliberately never resolved against sibling directories.
    assert _violations(_mutated(lifecycle=lifecycle)) == []


# ---- schema: spec.executionRequirements ----


def test_execution_requirements_unknown_key_is_flagged() -> None:
    assert _violations(_mutated(executionRequirements={"network": []})) != []


def test_execution_requirements_tools_unknown_key_is_flagged() -> None:
    exec_req: dict[str, Any] = {"tools": {"read": [], "network": []}}
    assert _violations(_mutated(executionRequirements=exec_req)) != []


def test_execution_requirements_tools_empty_list_is_valid() -> None:
    exec_req: dict[str, Any] = {"tools": {"read": [], "write": [], "shell": []}}
    assert _violations(_mutated(executionRequirements=exec_req)) == []


def test_execution_requirements_tools_empty_string_item_is_flagged() -> None:
    exec_req: dict[str, Any] = {"tools": {"read": [""]}}
    assert _violations(_mutated(executionRequirements=exec_req)) != []


# ---- cross-file: find_name_mismatch ----


def test_name_mismatch_flagged(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "real-name"
    skill_dir.mkdir()
    instance = _copy_instance()
    instance["metadata"]["name"] = "wrong-name"
    findings = scanner.find_name_mismatch(instance, skill_dir)
    assert any("metadata-name-matches-dir" in f for f in findings)


def test_name_match_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "example-skill"
    skill_dir.mkdir()
    assert scanner.find_name_mismatch(_VALID_INSTANCE, skill_dir) == []


# ---- cross-file: find_skill_dependency_drift / find_deprecated_replacement_drift ----


def test_skill_dependency_drift_flags_dangling_name(tmp_path: pathlib.Path) -> None:
    (tmp_path / "real-sibling").mkdir()
    instance = _mutated(
        skillDependencies={"requires": [], "relatedTo": ["ghost-skill"]})
    findings = scanner.find_skill_dependency_drift(instance, tmp_path)
    assert any("ghost-skill" in f for f in findings)


def test_skill_dependency_drift_resolves_real_sibling(tmp_path: pathlib.Path) -> None:
    (tmp_path / "real-sibling").mkdir()
    instance = _mutated(
        skillDependencies={"requires": [], "relatedTo": ["real-sibling"]})
    assert scanner.find_skill_dependency_drift(instance, tmp_path) == []


def test_skill_dependency_drift_ignores_missing_field() -> None:
    instance = _copy_instance()
    del instance["spec"]["skillDependencies"]
    assert scanner.find_skill_dependency_drift(instance, REPO_ROOT / "skills") == []


def test_deprecated_replacement_drift_flags_dangling_name(tmp_path: pathlib.Path) -> None:
    (tmp_path / "real-sibling").mkdir()
    lifecycle = {"deprecated": {"reason": "x", "replacement": "ghost-skill"}}
    instance = _mutated(lifecycle=lifecycle)
    findings = scanner.find_deprecated_replacement_drift(instance, tmp_path)
    assert any("ghost-skill" in f for f in findings)


def test_deprecated_replacement_drift_resolves_real_sibling(tmp_path: pathlib.Path) -> None:
    (tmp_path / "real-sibling").mkdir()
    lifecycle = {"deprecated": {"reason": "x", "replacement": "real-sibling"}}
    instance = _mutated(lifecycle=lifecycle)
    assert scanner.find_deprecated_replacement_drift(instance, tmp_path) == []


# ---- cross-file: find_requires_cycle ----


def test_find_requires_cycle_returns_none_for_acyclic_graph() -> None:
    graph = {"a": ["b"], "b": ["c"], "c": []}
    assert scanner.find_requires_cycle(graph) is None


def test_find_requires_cycle_detects_a_two_cycle() -> None:
    graph = {"a": ["b"], "b": ["a"]}
    cycle = scanner.find_requires_cycle(graph)
    assert cycle is not None
    assert set(cycle) == {"a", "b"}


def test_find_requires_cycle_ignores_dangling_dependencies() -> None:
    graph = {"a": ["ghost-skill"]}
    assert scanner.find_requires_cycle(graph) is None


# ---- discover_skill_dirs / load_sidecar ----


def test_discover_skill_dirs_finds_only_dirs_with_skill_md(tmp_path: pathlib.Path) -> None:
    (tmp_path / "has-skill").mkdir()
    (tmp_path / "has-skill" / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "no-skill").mkdir()
    dirs = scanner.discover_skill_dirs(tmp_path)
    assert [d.name for d in dirs] == ["has-skill"]


def test_discover_skill_dirs_empty_when_skills_dir_missing(tmp_path: pathlib.Path) -> None:
    assert scanner.discover_skill_dirs(tmp_path / "does-not-exist") == []


def test_load_sidecar_reads_valid_yaml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gitapex.yaml"
    path.write_text(yaml.safe_dump(_VALID_INSTANCE), encoding="utf-8")
    assert scanner.load_sidecar(path) == _VALID_INSTANCE


def test_load_sidecar_raises_on_invalid_yaml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gitapex.yaml"
    path.write_text("key: [unterminated", encoding="utf-8")
    with pytest.raises(scanner.SidecarReadError):
        scanner.load_sidecar(path)


def test_load_sidecar_raises_on_non_utf8(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gitapex.yaml"
    path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(scanner.SidecarReadError):
        scanner.load_sidecar(path)


def test_load_sidecar_raises_on_pathologically_deep_nesting(tmp_path: pathlib.Path) -> None:
    # Regression pin (adversarial review): RecursionError is not a
    # yaml.YAMLError subclass, so a deeply nested flow-sequence sidecar
    # used to propagate an uncaught RecursionError straight out of
    # load_sidecar, crashing the whole scan instead of reporting one clean
    # SidecarReadError the way every other malformed-input case here does.
    path = tmp_path / "gitapex.yaml"
    path.write_text("key: " + "[" * 3000 + "]" * 3000, encoding="utf-8")
    with pytest.raises(scanner.SidecarReadError):
        scanner.load_sidecar(path)


# ---- _is_bare_skill_name / path-traversal defenses (adversarial review) ----
#
# (skills_dir / entry).is_dir() alone does not defend against an absolute
# path or a "../" traversal segment: pathlib's own "/" operator discards the
# left operand entirely when the right one is absolute
# (pathlib.Path("/repo/skills") / "/etc" == pathlib.Path("/etc")). Verified
# live against this repository's own real SKILLS_DIR during the review that
# found this, both entries incorrectly resolved as "found".


def test_is_bare_skill_name_accepts_a_real_skill_name() -> None:
    assert scanner._is_bare_skill_name("battle-testing-a-skill") is True


def test_is_bare_skill_name_rejects_absolute_path() -> None:
    assert scanner._is_bare_skill_name("/etc") is False


def test_is_bare_skill_name_rejects_traversal_segment() -> None:
    assert scanner._is_bare_skill_name("../../../../../../etc") is False


def test_is_bare_skill_name_rejects_bare_dot_and_dotdot() -> None:
    assert scanner._is_bare_skill_name(".") is False
    assert scanner._is_bare_skill_name("..") is False


def test_skill_dependency_drift_flags_absolute_path_traversal() -> None:
    instance = _mutated(
        skillDependencies={"requires": ["/etc"], "relatedTo": []})
    findings = scanner.find_skill_dependency_drift(instance, REPO_ROOT / "skills")
    assert any("/etc" in f for f in findings)


def test_skill_dependency_drift_flags_relative_traversal() -> None:
    instance = _mutated(
        skillDependencies={
            "requires": [], "relatedTo": ["../../../../../../etc"]})
    findings = scanner.find_skill_dependency_drift(instance, REPO_ROOT / "skills")
    assert any("etc" in f for f in findings)


def test_deprecated_replacement_drift_flags_absolute_path_traversal() -> None:
    lifecycle = {"deprecated": {"reason": "x", "replacement": "/etc"}}
    instance = _mutated(lifecycle=lifecycle)
    findings = scanner.find_deprecated_replacement_drift(instance, REPO_ROOT / "skills")
    assert any("/etc" in f for f in findings)


# ---- end-to-end: find_drift ----


def _write_sidecar(skill_dir: pathlib.Path, instance: Any) -> None:
    (skill_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: x\n---\nbody\n", encoding="utf-8")
    (skill_dir / scanner.SIDECAR_RELATIVE_PATH).write_text(
        yaml.safe_dump(instance), encoding="utf-8")


def test_find_drift_end_to_end_clean(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "example-skill"
    (skills_dir / "battle-testing-a-skill").mkdir(parents=True)
    _write_sidecar(skill_dir, _VALID_INSTANCE)
    assert scanner.find_drift(skills_dir, scanner.SCHEMA_PATH, min_expected_skill_dirs=1) == []


def test_find_drift_end_to_end_reports_prefixed_findings(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "example-skill"
    bad_instance = _copy_instance()
    bad_instance["spec"]["portability"] = "Sortof"
    _write_sidecar(skill_dir, bad_instance)
    findings = scanner.find_drift(skills_dir, scanner.SCHEMA_PATH, min_expected_skill_dirs=1)
    assert any(f.startswith("example-skill: schema:") for f in findings)


def test_find_drift_end_to_end_missing_sidecar_is_flagged(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "example-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: x\n---\nbody\n", encoding="utf-8")
    findings = scanner.find_drift(skills_dir, scanner.SCHEMA_PATH, min_expected_skill_dirs=1)
    assert any("metadata-file-present" in f for f in findings)


def test_find_drift_end_to_end_detects_requires_cycle(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    a = _copy_instance()
    a["metadata"]["name"] = "skill-a"
    a["spec"]["portability"] = "Mixed"
    a["spec"]["skillDependencies"] = {"requires": ["skill-b"], "relatedTo": []}
    del a["spec"]["lifecycle"]
    b = _copy_instance()
    b["metadata"]["name"] = "skill-b"
    b["spec"]["portability"] = "Mixed"
    b["spec"]["skillDependencies"] = {"requires": ["skill-a"], "relatedTo": []}
    del b["spec"]["lifecycle"]
    _write_sidecar(skills_dir / "skill-a", a)
    _write_sidecar(skills_dir / "skill-b", b)
    findings = scanner.find_drift(skills_dir, scanner.SCHEMA_PATH, min_expected_skill_dirs=2)
    assert any("requires-acyclicity" in f for f in findings)


# ---- find_drift's discovery floor (dimension 15: fail-closed on incomplete
# input) -- a regression pin for a real bug this new gate shipped with: a
# wrong or missing skills_dir used to make discover_skill_dirs silently
# return [], and find_drift then reported "no drift" -- a vacuous pass, the
# exact failure class issue #651's retrospective named ("an empty match set
# is an error, never a silent pass"). Constructed directly, per
# evaluating-deterministic-gate-quality's dimension 15 (a bundled test's own
# happy-path fixtures do not by themselves satisfy this dimension).


def test_find_drift_floor_catches_a_missing_skills_directory(tmp_path: pathlib.Path) -> None:
    findings = scanner.find_drift(tmp_path / "does-not-exist", scanner.SCHEMA_PATH)
    assert any("skill-discovery-floor" in f for f in findings)


def test_find_drift_floor_catches_an_empty_skills_directory(tmp_path: pathlib.Path) -> None:
    (tmp_path / "skills").mkdir()
    findings = scanner.find_drift(tmp_path / "skills", scanner.SCHEMA_PATH)
    assert any("skill-discovery-floor" in f for f in findings)


def test_find_drift_floor_uses_the_real_repository_default(tmp_path: pathlib.Path) -> None:
    # Same missing-directory input as above, but exercising the DEFAULT
    # min_expected_skill_dirs (no override) -- proves the production
    # entry point (main() calls find_drift() with no arguments) is
    # actually protected, not just the parameterized escape hatch tests
    # use for their own deliberately small fixtures.
    findings = scanner.find_drift(tmp_path / "does-not-exist")
    assert any("skill-discovery-floor" in f for f in findings)


def test_find_drift_floor_does_not_fire_on_the_real_repository() -> None:
    # The real repository has 24 skills, comfortably above the default
    # floor -- this must not itself become a false positive.
    assert not any(
        "skill-discovery-floor" in f for f in scanner.find_drift())


# ---- main() ----


def test_main_returns_0_on_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert scanner.main() == 0
    assert "No skill metadata schema drift found." in capsys.readouterr().out


def test_main_returns_1_on_drift(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(scanner, "find_drift", lambda: ["fake: finding"])
    assert scanner.main() == 1
    assert "fake: finding" in capsys.readouterr().out


def test_main_returns_1_on_sidecar_read_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise() -> list[str]:
        raise scanner.SidecarReadError("boom")

    monkeypatch.setattr(scanner, "find_drift", _raise)
    assert scanner.main() == 1
    assert "boom" in capsys.readouterr().out


# ---- the real gate ----


def test_real_repository_skill_sidecars_have_no_schema_drift() -> None:
    assert scanner.find_drift() == []

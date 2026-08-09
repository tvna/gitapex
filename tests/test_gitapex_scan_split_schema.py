"""Tests for the split.json schema drift scanner
(.github/scripts/gitapex_scan_split_schema.py +
skills/scorer-gated-skill-edits/references/split.schema.json).

The final tests are the gate itself: every real evals/*/split.json in this
repository must validate against the schema with no drift, discovered via
glob rather than a hardcoded skill list. The rest unit-test each layer with
fixtures: pure schema validation (find_schema_violations), discovery
(discover_split_json_files), and the end-to-end find_drift/main() pipeline
-- including the malformed-6th-file regression the branch plan's own T11
checklist requires (a 6th, schema-violating split.json fixture added
alongside 5 real-shaped valid ones must be caught, not just the 5 valid
files passing).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import gitapex_scan_split_schema as scanner
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# A minimal but fully-populated valid split.json instance -- every gated
# block declared once, so a single copy-and-mutate per test proves the
# schema actually distinguishes valid from invalid rather than being
# vacuously permissive.
_VALID_INSTANCE: dict[str, Any] = {
    "assignment": {
        "train": ["normal.yaml"],
        "selection": [
            "edge.yaml",
            {"fixture": "guardrail.yaml", "expected": {"exercises": ["Some Heading"]}},
        ],
        "test": ["adversarial.yaml"],
    },
    "partition": "1:2:1",
    "split_arithmetic_exclusions": [],
    "equivalence_classes": [{"train_fixture": "normal.yaml", "held_out_fixture": "edge.yaml"}],
}


def _copy_instance() -> Any:
    """A deep copy of _VALID_INSTANCE with type Any -- round-tripped through
    JSON (mirroring tests/test_gitapex_scan_skill_metadata_schema.py's own
    fixture pattern) rather than copy.deepcopy, so mypy --strict lets a test
    mutate/delete arbitrary nested keys freely instead of inferring
    _VALID_INSTANCE's own narrow structural type onto every copy."""
    return json.loads(json.dumps(_VALID_INSTANCE))


def _schema() -> dict[str, Any]:
    return json.loads(scanner.SCHEMA_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _violations(instance: Any) -> list[str]:
    return scanner.find_schema_violations(instance, _schema())


# ---- schema: envelope ----


def test_valid_instance_has_no_schema_violations() -> None:
    assert _violations(_VALID_INSTANCE) == []


def test_missing_assignment_is_flagged() -> None:
    instance = _copy_instance()
    del instance["assignment"]
    assert any("assignment" in v for v in _violations(instance))


def test_unknown_top_level_key_is_flagged() -> None:
    instance = _copy_instance()
    instance["extra"] = "surprise"
    assert _violations(instance) != []


def test_assignment_only_is_valid() -> None:
    # partition/split_arithmetic_exclusions/equivalence_classes are all
    # optional -- T2's own finding that 2 of 5 real skills declare none of
    # this today, so the schema must not require what the source data
    # doesn't have.
    instance = {"assignment": {"train": ["normal.yaml"]}}
    assert _violations(instance) == []


def test_assignment_unknown_split_name_is_flagged() -> None:
    instance = _copy_instance()
    instance["assignment"]["holdout"] = ["extra.yaml"]
    assert _violations(instance) != []


def test_assignment_empty_object_is_valid() -> None:
    # No split key need be present -- a skill's corpus may legitimately have
    # no test-split fixtures yet.
    instance: dict[str, Any] = {"assignment": {}}
    assert _violations(instance) == []


# ---- schema: fixtureItem (bare filename vs. fixtureWithExpected) ----


def test_fixture_filename_bad_pattern_is_flagged() -> None:
    instance = _copy_instance()
    instance["assignment"]["train"] = ["not a filename"]
    assert _violations(instance) != []


def test_fixture_filename_missing_yaml_suffix_is_flagged() -> None:
    instance = _copy_instance()
    instance["assignment"]["train"] = ["normal.yml"]
    assert _violations(instance) != []


def test_fixture_with_expected_missing_expected_key_is_flagged() -> None:
    instance = _copy_instance()
    instance["assignment"]["selection"] = [{"fixture": "guardrail.yaml"}]
    assert _violations(instance) != []


def test_fixture_with_expected_unknown_key_is_flagged() -> None:
    instance = _copy_instance()
    instance["assignment"]["selection"] = [
        {"fixture": "guardrail.yaml", "expected": {"exercises": ["x"]}, "notes": "surprise"}
    ]
    assert _violations(instance) != []


def test_fixture_with_expected_empty_exercises_is_flagged() -> None:
    # minItems: 1 mirrors gitapex_gate_split_fixture_coverage.py's own
    # _is_real_exercises_declaration guard -- a non-empty list of non-blank
    # strings, not merely a truthy value.
    instance = _copy_instance()
    instance["assignment"]["selection"] = [{"fixture": "guardrail.yaml", "expected": {"exercises": []}}]
    assert _violations(instance) != []


def test_fixture_with_expected_blank_exercise_string_is_flagged() -> None:
    instance = _copy_instance()
    instance["assignment"]["selection"] = [{"fixture": "guardrail.yaml", "expected": {"exercises": [""]}}]
    assert _violations(instance) != []


# ---- schema: partition / split_arithmetic_exclusions ----


def test_partition_bad_pattern_is_flagged() -> None:
    instance = _copy_instance()
    instance["partition"] = "one:two:three"
    assert _violations(instance) != []


def test_partition_without_split_arithmetic_exclusions_is_flagged() -> None:
    # partition-requires-exclusions (the schema's own top-level if/then):
    # a declared partition needs a declared exclusions list, even an empty
    # one, so "no exclusions" is a real declared fact.
    instance = _copy_instance()
    del instance["split_arithmetic_exclusions"]
    assert _violations(instance) != []


def test_split_arithmetic_exclusions_without_partition_is_valid() -> None:
    instance = {"assignment": {"train": ["normal.yaml"]}, "split_arithmetic_exclusions": []}
    assert _violations(instance) == []


def test_split_arithmetic_exclusions_bad_item_pattern_is_flagged() -> None:
    instance = _copy_instance()
    instance["split_arithmetic_exclusions"] = ["not a filename"]
    assert _violations(instance) != []


# ---- schema: equivalence_classes ----


def test_equivalence_class_missing_required_key_is_flagged() -> None:
    instance = _copy_instance()
    instance["equivalence_classes"] = [{"train_fixture": "normal.yaml"}]
    assert _violations(instance) != []


def test_equivalence_class_unknown_key_is_flagged() -> None:
    instance = _copy_instance()
    instance["equivalence_classes"] = [
        {"train_fixture": "normal.yaml", "held_out_fixture": "edge.yaml", "notes": "surprise"}
    ]
    assert _violations(instance) != []


def test_equivalence_classes_empty_list_is_valid() -> None:
    instance = _copy_instance()
    instance["equivalence_classes"] = []
    assert _violations(instance) == []


# ---- discover_split_json_files ----


def test_discover_split_json_files_finds_only_split_json(tmp_path: pathlib.Path) -> None:
    (tmp_path / "has-split").mkdir()
    (tmp_path / "has-split" / "split.json").write_text("{}", encoding="utf-8")
    (tmp_path / "no-split").mkdir()
    (tmp_path / "no-split" / "eval.yaml").write_text("x", encoding="utf-8")
    files = scanner.discover_split_json_files(tmp_path)
    assert [f.parent.name for f in files] == ["has-split"]


def test_discover_split_json_files_empty_when_evals_dir_missing(tmp_path: pathlib.Path) -> None:
    assert scanner.discover_split_json_files(tmp_path / "does-not-exist") == []


def test_discover_split_json_files_sorted(tmp_path: pathlib.Path) -> None:
    for name in ("zeta", "alpha", "mu"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "split.json").write_text("{}", encoding="utf-8")
    files = scanner.discover_split_json_files(tmp_path)
    assert [f.parent.name for f in files] == ["alpha", "mu", "zeta"]


def test_discover_split_json_files_finds_the_real_five() -> None:
    # Live fact established during T1-T6: 5 skills carry a real split.json
    # today (battle-testing-a-skill, scorer-gated-skill-edits,
    # merge-retrospective, explaining-the-work, evaluating-skill-quality).
    files = scanner.discover_split_json_files()
    assert len(files) == 5


# ---- end-to-end: find_drift ----


def _write_split_json(evals_dir: pathlib.Path, skill: str, instance: Any) -> None:
    skill_dir = evals_dir / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "split.json").write_text(json.dumps(instance), encoding="utf-8")


def test_find_drift_end_to_end_clean(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    _write_split_json(evals_dir, "example-skill", _VALID_INSTANCE)
    assert scanner.find_drift(evals_dir, scanner.SCHEMA_PATH, min_expected_split_json_files=1) == []


def test_find_drift_end_to_end_reports_prefixed_findings(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    bad_instance = _copy_instance()
    del bad_instance["assignment"]
    _write_split_json(evals_dir, "example-skill", bad_instance)
    findings = scanner.find_drift(evals_dir, scanner.SCHEMA_PATH, min_expected_split_json_files=1)
    assert any(f.startswith("example-skill: schema:") for f in findings)


def test_find_drift_end_to_end_reports_malformed_json_without_crashing(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    skill_dir = evals_dir / "broken-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "split.json").write_text("{unterminated", encoding="utf-8")
    findings = scanner.find_drift(evals_dir, scanner.SCHEMA_PATH, min_expected_split_json_files=1)
    assert any("broken-skill" in f and "is not valid JSON" in f for f in findings)


def test_find_drift_end_to_end_reports_non_utf8_without_crashing(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    skill_dir = evals_dir / "broken-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "split.json").write_bytes(b"\xff\xfe\x00\x01")
    findings = scanner.find_drift(evals_dir, scanner.SCHEMA_PATH, min_expected_split_json_files=1)
    assert any("broken-skill" in f for f in findings)


def test_a_malformed_sixth_split_json_file_is_caught(tmp_path: pathlib.Path) -> None:
    """Branch-plan T11 regression requirement: a malformed extra split.json
    fixture (a 6th file, violating the schema) must fail the gate -- not
    just the 5 real, valid ones passing. Five real-shaped valid split.json
    files (mirroring this repository's own 5 today) plus one malformed 6th
    (missing the schema's sole required key, "assignment") must report a
    finding attributed to the 6th skill only, proving the gate actually
    distinguishes valid from invalid rather than passing vacuously on a
    quorum."""
    evals_dir = tmp_path / "evals"
    valid_skills = [
        "battle-testing-a-skill",
        "scorer-gated-skill-edits",
        "merge-retrospective",
        "explaining-the-work",
        "evaluating-skill-quality",
    ]
    for skill in valid_skills:
        _write_split_json(evals_dir, skill, _VALID_INSTANCE)

    malformed_instance: dict[str, Any] = {"partition": "1:2:1", "split_arithmetic_exclusions": []}
    _write_split_json(evals_dir, "sixth-malformed-skill", malformed_instance)

    findings = scanner.find_drift(evals_dir, scanner.SCHEMA_PATH, min_expected_split_json_files=5)

    assert any(f.startswith("sixth-malformed-skill: schema:") for f in findings)
    for skill in valid_skills:
        assert not any(f.startswith(f"{skill}:") for f in findings)


# ---- find_drift's discovery floor (dimension 15: fail-closed on incomplete
# input) -- a wrong or missing evals_dir must never silently pass as "no
# drift" vacuously, mirroring gitapex_scan_skill_metadata_schema.py's own
# MIN_EXPECTED_SKILL_DIRS floor and the failure class issue #651's
# retrospective named ("an empty match set is an error, never a silent
# pass").


def test_find_drift_floor_catches_a_missing_evals_directory(tmp_path: pathlib.Path) -> None:
    findings = scanner.find_drift(tmp_path / "does-not-exist", scanner.SCHEMA_PATH)
    assert any("split-json-discovery-floor" in f for f in findings)


def test_find_drift_floor_catches_an_empty_evals_directory(tmp_path: pathlib.Path) -> None:
    (tmp_path / "evals").mkdir()
    findings = scanner.find_drift(tmp_path / "evals", scanner.SCHEMA_PATH)
    assert any("split-json-discovery-floor" in f for f in findings)


def test_find_drift_floor_uses_the_real_repository_default(tmp_path: pathlib.Path) -> None:
    findings = scanner.find_drift(tmp_path / "does-not-exist")
    assert any("split-json-discovery-floor" in f for f in findings)


def test_find_drift_floor_does_not_fire_on_the_real_repository() -> None:
    assert not any("split-json-discovery-floor" in f for f in scanner.find_drift())


# ---- schema read errors ----


def test_load_schema_raises_on_non_utf8(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "schema.json"
    path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(scanner.SplitReadError):
        scanner._load_schema(path)


def test_load_schema_raises_on_invalid_json(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "schema.json"
    path.write_text("{unterminated", encoding="utf-8")
    with pytest.raises(scanner.SplitReadError):
        scanner._load_schema(path)


# ---- main() ----


def test_main_returns_0_on_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert scanner.main() == 0
    assert "No split.json schema drift found." in capsys.readouterr().out


def test_main_returns_1_on_drift(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(scanner, "find_drift", lambda: ["fake: finding"])
    assert scanner.main() == 1
    assert "fake: finding" in capsys.readouterr().out


def test_main_returns_1_on_split_read_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise() -> list[str]:
        raise scanner.SplitReadError("boom")

    monkeypatch.setattr(scanner, "find_drift", _raise)
    assert scanner.main() == 1
    assert "boom" in capsys.readouterr().out


# ---- the real gate ----


def test_real_repository_split_json_files_have_no_schema_drift() -> None:
    assert scanner.find_drift() == []

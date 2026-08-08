"""Tests for the runtime compatibility matrix drift gate
(.github/scripts/gitapex_scan_runtime_compatibility_matrix.py).

The final test is the gate itself: the repository's real
.gitapex/runtime-compatibility-matrix.json must validate against
.gitapex/runtime-compatibility-matrix.schema.json. The rest unit-test the
detector with fixtures, validated against the real schema file (there is
only one schema to test against, the same convention
test_gitapex_scan_ssot_schema.py already uses).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import gitapex_scan_runtime_compatibility_matrix as drift
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_VALID_INSTANCE: dict[str, Any] = {
    "meta": {
        "schema_version": "1.0.0",
        "tracking_issue": 828,
        "status": "draft",
        "phase": "phase-0",
    },
    "runtimes": {
        "claude-code": {
            "displayName": "Claude Code",
            "dimensions": {
                "fieldParsing": {
                    "classification": "Exact",
                    "primarySource": "https://code.claude.com/docs/en/skills",
                    "observedVersion": "2.1.220",
                    "snapshotDate": "2026-08-08",
                    "notes": "test fixture",
                }
            },
        }
    },
}


def _write_instance(tmp_path: pathlib.Path, instance: dict[str, Any]) -> pathlib.Path:
    path = tmp_path / "runtime-compatibility-matrix.json"
    path.write_text(json.dumps(instance))
    return path


def test_valid_instance_has_no_drift(tmp_path: pathlib.Path) -> None:
    instance_path = _write_instance(tmp_path, _VALID_INSTANCE)
    assert drift.find_drift(instance_path, drift.SCHEMA_PATH) == []


def test_empty_runtimes_map_is_valid() -> None:
    # phase-0's own shipped state: zero populated runtimes.
    instance = {"meta": _VALID_INSTANCE["meta"], "runtimes": {}}
    schema = json.loads(drift.SCHEMA_PATH.read_text(encoding="utf-8"))
    assert drift.find_schema_violations(instance, schema) == []


def test_missing_required_meta_field_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    del bad["meta"]["schema_version"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f and "schema_version" in f for f in findings)


def test_unrecognized_dimension_key_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["claude-code"]["dimensions"]["notADimension"] = {
        "classification": "Exact",
        "primarySource": "https://example.com",
        "snapshotDate": "2026-08-08",
    }
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f for f in findings)


def test_empty_dimensions_map_is_flagged(tmp_path: pathlib.Path) -> None:
    # minProperties: 1 -- a runtime entry with zero populated dimensions
    # has nothing to say and should not exist yet.
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["claude-code"]["dimensions"] = {}
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f for f in findings)


def test_invalid_classification_value_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["claude-code"]["dimensions"]["fieldParsing"]["classification"] = "exact"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f and "classification" in f for f in findings)


def test_non_https_primary_source_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["claude-code"]["dimensions"]["fieldParsing"]["primarySource"] = "http://example.com"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f and "primarySource" in f for f in findings)


def test_garbage_after_https_prefix_is_flagged(tmp_path: pathlib.Path) -> None:
    # Refs #828's own adversarial review: jsonschema's "uri" format checker
    # never activates in this repository's own environment (no rfc3987/
    # rfc3986-validator dependency installed), so a bare "^https://" prefix
    # pattern with no anchored authority shape would let whitespace-laden
    # garbage through. The pattern must reject this on its own.
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["claude-code"]["dimensions"]["fieldParsing"]["primarySource"] = (
        "https://   not a url at all !! <<>> \n\t garbage"
    )
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f and "primarySource" in f for f in findings)


def test_out_of_range_snapshot_date_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["claude-code"]["dimensions"]["fieldParsing"]["snapshotDate"] = "2026-02-30"
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f and "snapshotDate" in f for f in findings)


def test_missing_dimension_entry_required_field_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    del bad["runtimes"]["claude-code"]["dimensions"]["fieldParsing"]["primarySource"]
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f and "primarySource" in f for f in findings)


def test_notes_over_max_length_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["claude-code"]["dimensions"]["fieldParsing"]["notes"] = "x" * 501
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f and "notes" in f for f in findings)


def test_invalid_runtime_key_pattern_is_flagged(tmp_path: pathlib.Path) -> None:
    bad = json.loads(json.dumps(_VALID_INSTANCE))
    bad["runtimes"]["Claude_Code"] = bad["runtimes"].pop("claude-code")
    instance_path = _write_instance(tmp_path, bad)
    findings = drift.find_drift(instance_path, drift.SCHEMA_PATH)
    assert any("schema:" in f for f in findings)


def test_repository_matrix_is_schema_valid() -> None:
    """The gate: the real .gitapex/runtime-compatibility-matrix.json must
    validate against the real .gitapex/runtime-compatibility-matrix.schema.json."""
    findings = drift.find_drift()
    assert findings == [], f"runtime-compatibility-matrix.json drift: {findings}"


def test_main_prints_no_drift_and_returns_zero_when_clean(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No runtime-compatibility-matrix.json drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: ["schema: /runtimes: example finding"])
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "runtime-compatibility-matrix.json drift:" in out
    assert "schema: /runtimes: example finding" in out


def test_unreadable_matrix_path_raises_matrix_read_error(tmp_path: pathlib.Path) -> None:
    instance_path = tmp_path / "does-not-exist" / "runtime-compatibility-matrix.json"
    with pytest.raises(drift.MatrixReadError, match="cannot be read"):
        drift.find_drift(instance_path, drift.SCHEMA_PATH)


def test_non_utf8_matrix_raises_matrix_read_error_not_a_traceback(tmp_path: pathlib.Path) -> None:
    instance_path = tmp_path / "runtime-compatibility-matrix.json"
    instance_path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(drift.MatrixReadError, match="not valid UTF-8"):
        drift.find_drift(instance_path, drift.SCHEMA_PATH)


def test_invalid_json_syntax_raises_matrix_read_error_not_a_traceback(tmp_path: pathlib.Path) -> None:
    instance_path = tmp_path / "runtime-compatibility-matrix.json"
    instance_path.write_text("{not json")
    with pytest.raises(drift.MatrixReadError, match="not valid JSON"):
        drift.find_drift(instance_path, drift.SCHEMA_PATH)


def test_main_prints_message_and_returns_one_on_matrix_read_error(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_read_error() -> list[str]:
        raise drift.MatrixReadError("/fake/runtime-compatibility-matrix.json: is not valid UTF-8: boom")

    monkeypatch.setattr(drift, "find_drift", raise_read_error)
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "runtime-compatibility-matrix.json drift:" in out
    assert "/fake/runtime-compatibility-matrix.json: is not valid UTF-8: boom" in out

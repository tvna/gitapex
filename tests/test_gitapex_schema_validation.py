"""Tests for the shared JSON-load/JSON-Schema build/validate helpers
(.github/scripts/_gitapex_schema_validation.py).

Refs #755: extracted out of gitapex_scan_ssot_schema.py and
gitapex_scan_skill_metadata_schema.py so both scripts share one
load-or-raise and validator-build/iter-errors implementation instead of two
near-verbatim copies. test_gitapex_scan_ssot_schema.py and
test_gitapex_scan_skill_metadata_schema.py already exercise these helpers
extensively through their own callers (find_drift/find_schema_violations);
this file covers the module's own contract directly, including the
error_cls parameterization and the format-checker guarantee neither
sibling test file pins as narrowly as this one does.
"""

from __future__ import annotations

import pathlib
from typing import Any

import _gitapex_schema_validation
import pytest


class _FakeReadError(Exception):
    """A stand-in for a caller's own exception type (RegistryReadError/
    SidecarReadError) -- proves load_json_or_raise raises the *given*
    error_cls, not a hardcoded one."""


def test_load_json_or_raise_returns_parsed_value(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    assert _gitapex_schema_validation.load_json_or_raise(path, _FakeReadError) == {"a": 1}


def test_load_json_or_raise_raises_given_error_cls_on_missing_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "does-not-exist" / "data.json"
    with pytest.raises(_FakeReadError, match="cannot be read"):
        _gitapex_schema_validation.load_json_or_raise(path, _FakeReadError)


def test_load_json_or_raise_raises_given_error_cls_on_non_utf8(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.json"
    path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(_FakeReadError, match="not valid UTF-8"):
        _gitapex_schema_validation.load_json_or_raise(path, _FakeReadError)


def test_load_json_or_raise_raises_given_error_cls_on_invalid_json(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(_FakeReadError, match="not valid JSON"):
        _gitapex_schema_validation.load_json_or_raise(path, _FakeReadError)


def test_build_validator_accepts_a_valid_instance() -> None:
    schema: dict[str, Any] = {"type": "object", "properties": {"since": {"type": "string", "format": "date"}}}
    validator = _gitapex_schema_validation.build_validator(schema)
    assert _gitapex_schema_validation.schema_violations({"since": "2026-07-21"}, validator) == []


def test_build_validator_enables_format_checker() -> None:
    # The drift this extraction backports: a plain Draft202012Validator(schema)
    # ignores "format" keywords by default and would silently accept an
    # out-of-range calendar date -- build_validator must not do that.
    schema: dict[str, Any] = {"type": "object", "properties": {"since": {"type": "string", "format": "date"}}}
    validator = _gitapex_schema_validation.build_validator(schema)
    findings = _gitapex_schema_validation.schema_violations({"since": "2026-02-30"}, validator)
    assert any("since" in f for f in findings)


def test_schema_violations_reports_location_and_message() -> None:
    schema: dict[str, Any] = {"type": "object", "required": ["kind"], "properties": {"kind": {"type": "string"}}}
    validator = _gitapex_schema_validation.build_validator(schema)
    findings = _gitapex_schema_validation.schema_violations({}, validator)
    assert len(findings) == 1
    assert findings[0].startswith("schema: <root>:")
    assert "kind" in findings[0]


def test_schema_violations_empty_for_valid_instance() -> None:
    schema: dict[str, Any] = {"type": "object", "required": ["kind"]}
    validator = _gitapex_schema_validation.build_validator(schema)
    assert _gitapex_schema_validation.schema_violations({"kind": "x"}, validator) == []

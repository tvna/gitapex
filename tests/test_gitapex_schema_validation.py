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
import re
from typing import Any

import _gitapex_schema_validation
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


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


def test_check_schema_or_raise_accepts_a_valid_schema() -> None:
    schema: dict[str, Any] = {"type": "object", "properties": {"name": {"type": "string"}}}
    _gitapex_schema_validation.check_schema_or_raise(schema, _FakeReadError)  # does not raise


def test_check_schema_or_raise_raises_given_error_cls_on_invalid_schema() -> None:
    # "type" must be a string or array of strings, not an int -- a
    # dict-shaped but semantically-invalid schema that a plain
    # isinstance(dict) guard would let through, but which crashes
    # jsonschema's own validator construction/iteration with an uncaught
    # TypeError if not caught here first (found live by a
    # gitapex_scan_plugin_manifest_schema.py-scoped adversarial review).
    schema: dict[str, Any] = {"type": 1}
    with pytest.raises(_FakeReadError, match="is not a valid JSON Schema"):
        _gitapex_schema_validation.check_schema_or_raise(schema, _FakeReadError)


def test_check_schema_or_raise_names_the_given_schema_name_in_the_message() -> None:
    with pytest.raises(_FakeReadError, match=re.escape("my-schema.json: is not a valid JSON Schema")):
        _gitapex_schema_validation.check_schema_or_raise({"type": 1}, _FakeReadError, "my-schema.json")


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


def test_validate_is_schema_violations_of_build_validator() -> None:
    schema: dict[str, Any] = {"type": "object", "required": ["kind"]}
    assert _gitapex_schema_validation.validate({"kind": "x"}, schema) == []
    assert _gitapex_schema_validation.validate({}, schema) != []


def test_validate_enables_format_checker() -> None:
    schema: dict[str, Any] = {"type": "object", "properties": {"since": {"type": "string", "format": "date"}}}
    findings = _gitapex_schema_validation.validate({"since": "2026-02-30"}, schema)
    assert any("since" in f for f in findings)


# ---------------------------------------------------------------------------
# Drift gate (issue #755 finding: "ship the drift gate in the same change,
# not a follow-up" -- CLAUDE.md). Neither scanner script may reconstruct its
# own jsonschema validator or reimplement load-or-raise locally: that is
# exactly the duplication-then-drift (#734/#736) this module exists to
# close. Nothing else in this test file, or in
# tests/test_gitapex_scan_ssot_schema.py/test_gitapex_scan_skill_metadata_schema.py,
# would catch a future edit that pasted the old per-script copies back in --
# every one of those tests exercises behavior, not source text.
# ---------------------------------------------------------------------------

_SCANNER_SCRIPTS = (
    REPO_ROOT / ".github" / "scripts" / "gitapex_scan_ssot_schema.py",
    REPO_ROOT / ".github" / "scripts" / "gitapex_scan_skill_metadata_schema.py",
    REPO_ROOT / ".github" / "scripts" / "gitapex_scan_plugin_manifest_schema.py",
)

# Matches a real `import jsonschema` / `from jsonschema import ...`
# statement, not the many prose mentions of "jsonschema"/"Draft202012Validator"
# in each script's own docstring -- anchored to line-start with optional
# leading whitespace, the same way source-import detection needs to be to
# avoid false positives on documentation text.
_JSONSCHEMA_IMPORT_RE = re.compile(r"^\s*(import jsonschema\b|from jsonschema\b)", re.MULTILINE)
_DIRECT_VALIDATOR_CONSTRUCTION_RE = re.compile(r"\bDraft202012Validator\s*\(")


def test_scanner_scripts_do_not_import_jsonschema_directly() -> None:
    offenders = [p for p in _SCANNER_SCRIPTS if _JSONSCHEMA_IMPORT_RE.search(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        "these scanner scripts import jsonschema directly instead of going "
        f"through _gitapex_schema_validation.py: {[str(p.relative_to(REPO_ROOT)) for p in offenders]}. "
        "This reopens the exact duplication-then-drift issue #755 closed -- "
        "route schema loading/validation through _gitapex_schema_validation.py instead."
    )


def test_scanner_scripts_do_not_construct_a_validator_directly() -> None:
    offenders = [p for p in _SCANNER_SCRIPTS if _DIRECT_VALIDATOR_CONSTRUCTION_RE.search(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        "these scanner scripts construct a jsonschema.Draft202012Validator "
        f"directly instead of calling _gitapex_schema_validation.build_validator: "
        f"{[str(p.relative_to(REPO_ROOT)) for p in offenders]}."
    )

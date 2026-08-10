#!/usr/bin/env python3
"""Shared JSON-load and JSON-Schema build/validate helpers for `.github/scripts/*.py`.

Issue #755: `gitapex_scan_skill_metadata_schema.py`'s own `_load_schema`/
`find_schema_violations` (added in #734/#736) duplicated
`gitapex_scan_ssot_schema.py`'s own `_load_json`/`find_schema_violations`
almost verbatim -- read-UTF-8-or-raise, parse-JSON-or-raise, build a
`jsonschema.Draft202012Validator`, walk `iter_errors`. The two copies had
already drifted once: the skill-metadata script's validator passed
`format_checker=jsonschema.FormatChecker()` (so an out-of-range calendar
date like "2026-02-30" fails, not just a wrong-shape date), while the ssot
script's own `find_schema_violations` built a plain
`Draft202012Validator(schema)` with no format assertion -- the same
conceptual helper behaving differently depending on which of the two
near-identical scripts was read. Extracting this module closes both the
duplication and the drift: `build_validator` always enables the format
checker, so both callers get the same behavior going forward.

`load_json_or_raise` takes the caller's own exception class as a plain
`type[Exception]` argument (`RegistryReadError`/`SidecarReadError`) so both
scripts keep their own distinct, already-tested exception types rather than
converging on one generic error class neither test suite expects. Not a
generic function: the return type is `Any` regardless of which exception
class is passed, so a PEP 695 type parameter here would add syntax without
adding any type-checking `mypy --strict` doesn't already do with a plain
`type[Exception]`.

Mirrors `_gitapex_github_http.py`'s own shared-module convention in
placement and shape: a `.github/scripts/_gitapex_*.py` module with its own
dedicated `tests/test_gitapex_*.py` file, holding schema-agnostic logic
while each caller's own schema path and instance path stay in its own
script. It does NOT mirror that module's exception-handling shape --
`_gitapex_github_http.py` centralizes one shared `GitHubApiError` that both
its callers import and catch directly, rather than parameterizing over each
caller's own exception type the way `load_json_or_raise`/`validate` do
here; the two modules solve a structurally different problem (one shared
exception vs. two callers that must keep distinct pre-existing exception
types), not the same one.

`tests/test_gitapex_schema_validation.py` also owns the drift gate for this
module's own reason for existing: `gitapex_scan_ssot_schema.py`,
`gitapex_scan_skill_metadata_schema.py`, and `gitapex_scan_plugin_manifest_schema.py`
must all call this module rather than reimplementing any of it locally, or
the exact drift issue #755 fixed (only one of the two original scripts
enabling `format_checker`) could silently reopen.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import jsonschema


def load_json_or_raise(path: pathlib.Path, error_cls: type[Exception]) -> Any:
    """Read and JSON-parse `path`. Raises `error_cls(message)` -- naming
    `path` -- rather than letting a non-UTF-8 file or invalid JSON syntax
    surface as an uncaught UnicodeDecodeError/JSONDecodeError traceback.
    Does not itself check the parsed value's shape (dict vs. list/str/etc.)
    -- callers that need a dict guard that separately, since a
    schema-invalid-but-parseable instance is the caller's own
    find_schema_violations finding to report, not a load failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise error_cls(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise error_cls(f"{path}: is not valid UTF-8: {error}") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise error_cls(f"{path}: is not valid JSON: {error}") from error


def build_validator(schema: dict[str, Any]) -> jsonschema.Draft202012Validator:
    """A Draft202012Validator for `schema` with format assertion always
    enabled -- the JSON Schema spec itself permits a consumer to ignore
    format assertions, and the plain jsonschema.Draft202012Validator(schema)
    constructor does exactly that, which would silently accept an
    out-of-range calendar date like "2026-02-30" that only fails the
    schema's "format": "date" keyword, not its "pattern" keyword."""
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def schema_violations(instance: Any, validator: jsonschema.Draft202012Validator) -> list[str]:
    """One message per JSON-Schema (draft 2020-12) validation error
    `validator` finds against `instance`. Empty list means the instance is
    valid."""
    findings: list[str] = []
    for error in validator.iter_errors(instance):
        location = "/".join(str(p) for p in error.path) or "<root>"
        findings.append(f"schema: {location}: {error.message}")
    return findings


def validate(instance: Any, schema: dict[str, Any]) -> list[str]:
    """`schema_violations(instance, build_validator(schema))` -- the one-shot
    convenience composition both `gitapex_scan_ssot_schema.py`'s and
    `gitapex_scan_skill_metadata_schema.py`'s own `find_schema_violations`
    wrappers used to re-derive independently. Not for a caller validating
    many instances against the same schema in a loop -- `find_drift` in
    `gitapex_scan_skill_metadata_schema.py` builds one validator via
    `build_validator` and reuses it across every discovered skill instead,
    so `$ref` resolution/registry setup isn't repeated per skill."""
    return schema_violations(instance, build_validator(schema))

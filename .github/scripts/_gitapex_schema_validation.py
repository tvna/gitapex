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

`load_json_or_raise` is parameterized by the caller's own exception class
(`RegistryReadError`/`SidecarReadError`) so both scripts keep their own
distinct, already-tested exception types rather than converging on one
generic error class neither test suite expects.

Mirrors `_gitapex_github_http.py`'s own shared-module convention: generic,
schema-agnostic logic lives here; each caller's own schema path, instance
path, and exception type stay in its own script.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import jsonschema


def load_json_or_raise[E: Exception](path: pathlib.Path, error_cls: type[E]) -> Any:
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

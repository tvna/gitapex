"""JSON Schema loading and error-attribution helpers for the
metadata/gitapex.yaml sidecar (issue #758).

The bundled skill-metadata.schema.json (kept alongside this skill under
references/ so it travels with the skill when vendored, per issue #834)
is the one source of truth for the sidecar's structural shape. Loaded
once at import time; a missing or malformed schema file is a real
environment defect, not a per-check finding, so it is allowed to raise
during import rather than being caught and reported as a CheckResult.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "references" / "skill-metadata.schema.json"
SKILL_METADATA_SCHEMA: dict[str, object] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_SCHEMA_VALIDATOR = jsonschema.Draft202012Validator(SKILL_METADATA_SCHEMA, format_checker=jsonschema.FormatChecker())


def _schema_dict(node: object, *path: str) -> dict[str, object]:
    if not isinstance(node, dict):
        raise TypeError(f"expected a mapping at schema path {path!r}, got {type(node).__name__}")
    return node


def _schema_defs() -> dict[str, object]:
    return _schema_dict(SKILL_METADATA_SCHEMA["$defs"], "$defs")


def _schema_enum(*path: str) -> tuple[str, ...]:
    """Read a schema ``$defs`` node's own ``enum`` as a tuple, following
    ``path`` through nested ``properties``/mapping keys -- lets this
    module's own vocabulary constants (``PORTABILITY_LEVELS``, etc.)
    derive directly from the schema instead of hand-duplicating it.
    ``EXPECTED_API_VERSION``/``EXPECTED_KIND`` read a bare ``const``
    directly off ``SKILL_METADATA_SCHEMA`` instead of going through this
    helper -- every ``path`` a caller passes here targets a real ``enum``
    node, not a single-value ``const`` one."""
    node: dict[str, object] = _schema_defs()
    for key in path:
        node = _schema_dict(node[key], *path)
    values = node["enum"]
    if not isinstance(values, list):
        raise TypeError(f"expected a list at schema path {path!r}'s enum, got {type(values).__name__}")
    return tuple(values)


def _errors_under(
    errors: list[jsonschema.exceptions.ValidationError], *prefix: str
) -> list[jsonschema.exceptions.ValidationError]:
    """Every schema error whose own instance path starts with ``prefix``
    (e.g. ``"spec", "lifecycle"``) -- lets each check function pull only
    the schema violations relevant to its own field out of one shared
    ``iter_errors()`` pass over the whole manifest."""
    return [e for e in errors if tuple(str(p) for p in e.absolute_path)[: len(prefix)] == prefix]


def _join_schema_errors(errors: list[jsonschema.exceptions.ValidationError]) -> str:
    """One evidence string for a non-empty list of schema errors: a count
    plus the first violation's own instance location and message. Exact
    wording differs from the hand-rolled reader's own evidence strings
    this migration replaces -- disclosed, expected churn (design doc
    section 4.5), not a regression; each CheckResult's own PASS/FAIL
    boolean and check name are what the external contract actually
    promises, not the evidence string's exact prose."""
    count = len(errors)
    first = errors[0]
    location = "/".join(str(p) for p in first.absolute_path) or "<root>"
    return f"{count} schema violation{'' if count == 1 else 's'}: {location}: {first.message}"

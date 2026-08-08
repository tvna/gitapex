#!/usr/bin/env python3
"""Guard the runtime compatibility matrix's schema (W2, parent issue #307).

``.gitapex/runtime-compatibility-matrix.json`` (issue #828) is gitapex's
own versioned, testable record of how faithfully each target agent-tool
runtime can enforce the ten execution-requirement dimensions #307's own
W2 names -- see ``.gitapex/runtime-compatibility-matrix.schema.json``'s own
``description`` for the full field-by-field rationale, and
``docs/superpowers/specs/2026-08-08-w2-runtime-compatibility-matrix-schema-design.md``
for the design decision this schema implements.

This scanner is the drift gate shipped alongside that schema, mirroring
``gitapex_scan_ssot_schema.py``'s own shape for a single repo-wide
registry file. It fails if
``.gitapex/runtime-compatibility-matrix.json`` does not validate against
``.gitapex/runtime-compatibility-matrix.schema.json``.

Unlike ``gitapex_scan_ssot_schema.py``, this scanner has no additional
repo-grounded reference-drift checks yet: the matrix carries no
cross-references to skill directories, scripts, or any other registry --
every field it defines is either free-form (an observed version string, a
URL, a note) or already fully expressed by the JSON Schema itself
(a closed dimension-key enum, a closed classification enum). A future
population batch that introduces a real cross-reference (for example, if
a later revision ties a dimension entry to a specific
``spec.executionRequirements`` tag) would motivate adding one, the same
way ``gitapex_scan_ssot_schema.py`` grew its own three reference-drift
checks alongside real cross-references in ``ssot.json`` -- not before.

Issue #755: the JSON-load-or-raise and validator-build/iter-errors logic
below is shared with ``gitapex_scan_ssot_schema.py`` and
``gitapex_scan_skill_metadata_schema.py`` via ``_gitapex_schema_validation.py``
rather than a third near-verbatim copy.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gitapex_scan_runtime_compatibility_matrix.py``.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import _gitapex_schema_validation

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / ".gitapex" / "runtime-compatibility-matrix.json"
SCHEMA_PATH = REPO_ROOT / ".gitapex" / "runtime-compatibility-matrix.schema.json"


class MatrixReadError(Exception):
    """Either the matrix or its schema could not be read as UTF-8 text or
    parsed as JSON at all -- exit 1, never a traceback. Distinct from a
    schema-valid-JSON-but-drifted instance, which ``find_schema_violations``
    reports as an ordinary finding."""


def find_schema_violations(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Return one message per JSON-Schema (draft 2020-12) validation error
    against the given schema. Empty list means the instance is valid."""
    return _gitapex_schema_validation.validate(instance, schema)


def find_drift(
    instance_path: pathlib.Path = MATRIX_PATH,
    schema_path: pathlib.Path = SCHEMA_PATH,
) -> list[str]:
    """Return every drift finding -- currently schema validation only (see
    module docstring for why no reference-drift checks exist yet). Empty
    list means the matrix is clean."""
    instance = _gitapex_schema_validation.load_json_or_raise(instance_path, MatrixReadError)
    schema = _gitapex_schema_validation.load_json_or_raise(schema_path, MatrixReadError)
    return find_schema_violations(instance, schema)


def main() -> int:
    try:
        findings = find_drift()
    except MatrixReadError as error:
        print("runtime-compatibility-matrix.json drift:")
        print(f"  {error}")
        return 1
    if findings:
        print("runtime-compatibility-matrix.json drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No runtime-compatibility-matrix.json drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

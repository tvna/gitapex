#!/usr/bin/env python3
"""Validate every committed evals/*/split.json against the split.json JSON
Schema.

ACTIVE (issue #928): registered in .gitapex/ssot.json as split-schema-drift.
Enforced the same way its sibling .github/scripts/gitapex_scan_skill_metadata_schema.py
(registered there as skill-metadata-schema-drift) already is -- neither has a
dedicated CI workflow step or pre-commit hook; both are enforced solely
because tests/test_gitapex_scan_split_schema.py's own
test_real_repository_split_json_files_have_no_schema_drift calls find_drift()
against the real evals/ tree with no fixture override, and tests/ is
auto-discovered by pytest via pyproject.toml's [tool.pytest.ini_options]
testpaths -- which .github/workflows/test.yml runs as a required check on
every push and PR. A real schema violation fails CI through that pytest
gate; there is no separate standalone `python3
.github/scripts/gitapex_scan_split_schema.py` invocation anywhere in CI,
matching this repository's own established convention for this exact gate
shape rather than adding a second, redundant enforcement path.

This scanner validates each discovered split.json's *shape* only (required
keys, closed vocabularies, the partition/split_arithmetic_exclusions pairing)
via a real JSON Schema
(skills/scorer-gated-skill-edits/references/split.schema.json, chosen so the
schema travels with the scorer-gated-skill-edits skill when this repository
is installed as a plugin elsewhere -- the same portability precedent
skill-metadata.schema.json already set for its own scanner). It does NOT
perform the cross-file set-arithmetic checks
(.github/scripts/gitapex_gate_split_fixture_coverage.py's own Checks A-D:
reconciling a declared partition against the assignment listing's real
counts, an exercises label matching a real SKILL.md ### heading, a fixture
file actually existing under that skill's own eval-fixture task corpus) --
split.schema.json's own top-level description names that split explicitly,
and this scanner does not duplicate it.

Layered validation, mirroring .gitapex/ssot.schema.json's own scanner
(.github/scripts/gitapex_scan_ssot_schema.py) and
gitapex_scan_skill_metadata_schema.py:

1. discover_split_json_files() globs evals/*/split.json at runtime -- never
   a hardcoded list of the skills known today, so a 6th skill gaining a
   split.json later is picked up and validated automatically, not silently
   skipped.
2. Each discovered file is read and JSON-parsed via
   _gitapex_schema_validation.load_json_or_raise (issue #755's shared
   load-or-raise helper, the same one gitapex_scan_ssot_schema.py uses for
   its own single-file JSON read -- this scanner's read shape is a closer
   match to that script's than to gitapex_scan_skill_metadata_schema.py's own
   YAML-specific load_sidecar, since split.json is JSON, not YAML).
3. ``jsonschema.Draft202012Validator`` (with format assertion enabled via
   _gitapex_schema_validation.build_validator) checks each instance against
   split.schema.json and reports every violation with a JSON-pointer-shaped
   location.

Run standalone (exit 0 clean, 1 on drift or a read error) or via the pytest
gate in tests/test_gitapex_scan_split_schema.py.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import _gitapex_schema_validation

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
SCHEMA_PATH = REPO_ROOT / "skills" / "scorer-gated-skill-edits" / "references" / "split.schema.json"
# Guards against discover_split_json_files silently finding nothing (a wrong
# or missing evals_dir, an empty/misconfigured checkout) and find_drift then
# vacuously reporting "no drift" -- the same purpose as
# gitapex_scan_skill_metadata_schema.py's own MIN_EXPECTED_SKILL_DIRS floor.
# This repository has 5 real evals/*/split.json files today (verified via
# `find evals -maxdepth 2 -name split.json | wc -l`); the floor is set below
# that real count (not at 1) so a partial discovery failure -- most, not
# all, split.json files silently dropped -- is still caught, while a
# genuinely small number of new skills gaining their own split.json over
# time does not need a matching schema bump here.
MIN_EXPECTED_SPLIT_JSON_FILES = 3


class SplitReadError(Exception):
    """A split.json or split.schema.json could not be read as UTF-8 text or
    parsed as JSON at all -- exit 1, never a traceback. Distinct from a
    schema-invalid-but-parseable instance, which find_drift reports as an
    ordinary finding."""


def discover_split_json_files(evals_dir: pathlib.Path = EVALS_DIR) -> list[pathlib.Path]:
    """Every evals/<skill>/split.json file, discovered via glob at runtime --
    never a hardcoded list of the skills known today. Sorted for
    deterministic output."""
    if not evals_dir.is_dir():
        return []
    return sorted(evals_dir.glob("*/split.json"))


def _load_schema(schema_path: pathlib.Path) -> dict[str, Any]:
    parsed: dict[str, Any] = _gitapex_schema_validation.load_json_or_raise(schema_path, SplitReadError)
    return parsed


def find_schema_violations(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Return one message per JSON-Schema (draft 2020-12) validation error
    against ``schema``. Convenience wrapper that builds a fresh validator on
    every call -- fine for the occasional direct caller (this module's own
    tests), but find_drift builds one validator per run instead and reuses
    it across every discovered file via
    _gitapex_schema_validation.schema_violations."""
    return _gitapex_schema_validation.validate(instance, schema)


def find_drift(
    evals_dir: pathlib.Path = EVALS_DIR,
    schema_path: pathlib.Path = SCHEMA_PATH,
    min_expected_split_json_files: int = MIN_EXPECTED_SPLIT_JSON_FILES,
) -> list[str]:
    """Return every drift finding across every discovered evals/*/split.json:
    a read/parse failure or a schema violation, each prefixed with the
    owning skill's directory name. Empty list means every discovered
    split.json is clean.

    ``min_expected_split_json_files`` is a fail-closed floor on discovery
    itself, checked before any per-file validation: fewer than this many
    real split.json files is treated as a drift finding, not silently
    reported as "no drift" (dimension 15, evaluating-deterministic-gate-
    quality -- without this, a wrong or missing ``evals_dir`` argument, or a
    checkout that lost most of evals/, would pass this gate vacuously). A
    caller exercising a deliberately small fixture directory (this module's
    own tests) must pass a lower value explicitly; every other caller,
    including ``main()``, keeps the real-repository-sized default.
    """
    schema = _load_schema(schema_path)
    validator = _gitapex_schema_validation.build_validator(schema)
    split_files = discover_split_json_files(evals_dir)

    if len(split_files) < min_expected_split_json_files:
        return [
            f"split-json-discovery-floor: found only {len(split_files)} "
            f"evals/*/split.json file(s) under {evals_dir} (expected at "
            f"least {min_expected_split_json_files}) -- this usually means "
            "evals_dir is wrong or missing, not that split.json files were "
            "actually removed"
        ]

    findings: list[str] = []
    for path in split_files:
        prefix = path.parent.name
        try:
            instance = _gitapex_schema_validation.load_json_or_raise(path, SplitReadError)
        except SplitReadError as error:
            findings.append(f"{prefix}: {error}")
            continue
        findings.extend(f"{prefix}: {f}" for f in _gitapex_schema_validation.schema_violations(instance, validator))
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except SplitReadError as error:
        print("split.json schema drift:")
        print(f"  {error}")
        return 1
    if findings:
        print("split.json schema drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No split.json schema drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

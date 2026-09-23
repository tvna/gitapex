#!/usr/bin/env python3
"""Validate every agents/metadata/<name>.gitapex.yaml sidecar against the
AgentMetadata schema (.gitapex/agent-metadata.schema.json).

Issue #2073 (parent #307). Registered in .gitapex/ssot.json as
agent-metadata-schema-drift. Enforced the same way as its sibling
gitapex_scan_skill_metadata_schema.py: tests/test_gitapex_scan_agent_metadata_schema.py
calls find_drift() against the real agents/ tree, and .github/workflows/test.yml
runs that pytest file on every push and PR. There is no separate CI step.

The schema is declaration only. No adapter reads these sidecars yet, and
zero real sidecars exist today (the issue's own Non-goals), so the real-tree
scan is vacuous until the first agent declares one.

Layered validation, mirroring gitapex_scan_skill_metadata_schema.py:

1. JSON Schema (draft 2020-12, format assertion on) via the shared
   _gitapex_schema_validation.py helper.
2. Checks the schema cannot express on its own:
   - ``sidecar-dir`` / ``sidecar-filename``: agents/metadata/, if present,
     must be a directory holding only ``<kebab-name>.gitapex.yaml`` files.
     A misspelled suffix (``.gitapex.yml``) would otherwise be skipped by
     discovery and silently never validated.
   - ``metadata-name-matches-file``: metadata.name equals the file's
     ``<name>`` stem.
   - ``agent-definition-exists``: agents/<name>.md exists.
   - ``exit-condition-ids-unique``: no two
     spec.executionRequirements.lifecycle.exitConditions[] entries share an id.
   - ``agent-definitions-discovered``: fail-closed floor. A missing or empty
     agents/ directory is a finding, never a vacuous "no drift".

Run standalone (exit 0 clean, 1 on drift or a read error, 2 if PyYAML is
missing) or via the pytest gate.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import _gitapex_schema_validation

try:
    import yaml
except ModuleNotFoundError as error:
    # Same __name__-gated guard as gitapex_scan_skill_metadata_schema.py
    # (issues #1076, #1089): only the CLI entry point gets the friendly exit;
    # an import from pytest re-raises so collection fails cleanly.
    if error.name != "yaml" or __name__ != "__main__":
        raise
    print(
        f"error: {error}. This script requires PyYAML, which is not on "
        "the import path -- install the dev dependency group first: "
        "uv sync --group dev",
        file=sys.stderr,
    )
    raise SystemExit(2) from error

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"
SCHEMA_PATH = REPO_ROOT / ".gitapex" / "agent-metadata.schema.json"
METADATA_DIRNAME = "metadata"
SIDECAR_SUFFIX = ".gitapex.yaml"
_SIDECAR_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*" + re.escape(SIDECAR_SUFFIX) + r"$")
# agents/ ships two definitions today (branch-plan-task, review-persona).
# A floor of 1 catches a wrong or missing agents_dir without needing an
# edit every time a definition is added or removed.
MIN_EXPECTED_AGENT_DEFINITIONS = 1


class SidecarReadError(Exception):
    """A sidecar or the schema could not be read or parsed at all -- exit 1,
    never a traceback. A parseable but schema-invalid sidecar is an ordinary
    finding instead."""


def load_schema(schema_path: pathlib.Path = SCHEMA_PATH) -> dict[str, Any]:
    schema = _gitapex_schema_validation.load_json_or_raise(schema_path, SidecarReadError)
    if not isinstance(schema, dict):
        raise SidecarReadError(f"{schema_path}: must be a JSON object, got {type(schema).__name__}")
    _gitapex_schema_validation.check_schema_or_raise(schema, SidecarReadError, str(schema_path))
    return schema


def load_sidecar(path: pathlib.Path) -> Any:
    """Read and YAML-parse ``path``, raising SidecarReadError on a
    non-UTF-8 file, invalid YAML, nesting deep enough to hit RecursionError,
    or alias expansion large enough to hit MemoryError (neither is a
    YAMLError subclass, so both are caught separately)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SidecarReadError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise SidecarReadError(f"{path}: is not valid UTF-8: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise SidecarReadError(f"{path}: is not valid YAML: {error}") from error
    except RecursionError as error:
        raise SidecarReadError(f"{path}: is too deeply nested to parse: {error}") from error
    except MemoryError as error:
        raise SidecarReadError(f"{path}: exhausted memory while parsing: {error}") from error


def find_schema_violations(instance: Any, schema: dict[str, Any]) -> list[str]:
    return _gitapex_schema_validation.validate(instance, schema)


def find_name_mismatch(instance: Any, stem: str) -> list[str]:
    metadata = instance.get("metadata") if isinstance(instance, dict) else None
    name = metadata.get("name") if isinstance(metadata, dict) else None
    if isinstance(name, str) and name != stem:
        return [f"metadata-name-matches-file: {name!r} vs file stem {stem!r}"]
    return []


def find_duplicate_exit_condition_ids(instance: Any) -> list[str]:
    spec = instance.get("spec") if isinstance(instance, dict) else None
    requirements = spec.get("executionRequirements") if isinstance(spec, dict) else None
    lifecycle = requirements.get("lifecycle") if isinstance(requirements, dict) else None
    conditions = lifecycle.get("exitConditions") if isinstance(lifecycle, dict) else None
    if not isinstance(conditions, list):
        return []
    seen: set[str] = set()
    findings: list[str] = []
    for condition in conditions:
        condition_id = condition.get("id") if isinstance(condition, dict) else None
        if not isinstance(condition_id, str):
            continue
        if condition_id in seen:
            findings.append(f"exit-condition-ids-unique: duplicate id {condition_id!r}")
        seen.add(condition_id)
    return findings


def find_drift(agents_dir: pathlib.Path = AGENTS_DIR, schema_path: pathlib.Path = SCHEMA_PATH) -> list[str]:
    """Every drift finding across agents_dir/metadata/. Empty means clean.
    Raises SidecarReadError when a sidecar or the schema cannot be parsed."""
    schema = load_schema(schema_path)
    validator = _gitapex_schema_validation.build_validator(schema)

    definitions = sorted(agents_dir.glob("*.md")) if agents_dir.is_dir() else []
    if len(definitions) < MIN_EXPECTED_AGENT_DEFINITIONS:
        return [
            f"agent-definitions-discovered: found {len(definitions)} agents/*.md under {agents_dir}, "
            f"expected at least {MIN_EXPECTED_AGENT_DEFINITIONS} -- wrong or incomplete agents directory"
        ]

    metadata_dir = agents_dir / METADATA_DIRNAME
    if not metadata_dir.exists():
        return []
    if not metadata_dir.is_dir():
        return [f"{metadata_dir}: sidecar-dir: exists but is not a directory"]

    findings: list[str] = []
    for path in sorted(metadata_dir.iterdir()):
        if not (path.is_file() and _SIDECAR_NAME_RE.match(path.name)):
            findings.append(f"{path}: sidecar-filename: expected a <kebab-name>{SIDECAR_SUFFIX} file")
            continue
        stem = path.name.removesuffix(SIDECAR_SUFFIX)
        instance = load_sidecar(path)
        per_file = _gitapex_schema_validation.schema_violations(instance, validator)
        per_file += find_name_mismatch(instance, stem)
        if not (agents_dir / f"{stem}.md").is_file():
            per_file.append(f"agent-definition-exists: no agents/{stem}.md")
        per_file += find_duplicate_exit_condition_ids(instance)
        findings.extend(f"{path}: {finding}" for finding in per_file)
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except SidecarReadError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if findings:
        print("agent metadata schema drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No agent metadata schema drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

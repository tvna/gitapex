#!/usr/bin/env python3
"""Guard the self-referential gate registry invariant.

``.gitapex/ssot.json`` (issue #123) is gitapex's own registry of its real,
currently-enforced deterministic gates -- "references and routing only,
never policy values," mirroring the upstream ``tvna/claude-md`` precedent's
own stated constraint. Left unguarded, the registry drifts from the files it
claims to describe: a gate's script gets renamed or deleted, or a
``policy_refs``/``cluster`` entry points at something that no longer exists,
and the registry silently goes stale.

This scanner is the drift gate shipped alongside that registry. It fails if:

- ``.gitapex/ssot.json`` does not validate against ``.gitapex/ssot.schema.json``;
- any ``gates[].script`` path (``kind: "script"``) does not exist as a real
  file in the repository;
- any ``gates[].policy_refs[]`` value does not resolve to a real
  ``policy_sources[].id``; or
- any ``gates[].cluster`` value does not name a real top-level ``clusters``
  key.

It does not check the converse -- a real gate script with no registry entry
at all (under-registration, a "shadow gate") is a known, accepted gap; see
the PR that introduced this scanner for why that was left as a follow-up
rather than folded in here.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_scan_ssot_schema.py``.
"""

from __future__ import annotations

import json
import pathlib
import sys

import jsonschema

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"
SCHEMA_PATH = REPO_ROOT / ".gitapex" / "ssot.schema.json"


def _load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def _script_paths(gate: dict) -> list[str]:
    script = gate.get("script")
    if script is None:
        return []
    return [script] if isinstance(script, str) else list(script)


def _cluster_values(gate: dict) -> list[str]:
    cluster = gate.get("cluster")
    if cluster is None:
        return []
    return [cluster] if isinstance(cluster, str) else list(cluster)


def find_schema_violations(instance: dict, schema: dict) -> list[str]:
    """Return one message per JSON-Schema (draft 2020-12) validation error
    against the given schema. Empty list means the instance is valid."""
    validator = jsonschema.Draft202012Validator(schema)
    findings = []
    for error in validator.iter_errors(instance):
        location = "/".join(str(p) for p in error.path) or "<root>"
        findings.append(f"schema: {location}: {error.message}")
    return findings


def find_script_drift(instance: dict, repo_root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Return one message per gates[] script path that doesn't exist as a real
    file. Only checked for kind == "script" -- "native" gates have no repo
    file to check, and "opa-rego" gates aren't seeded yet."""
    findings = []
    for gate in instance.get("gates", []):
        if gate.get("kind") != "script":
            continue
        for path in _script_paths(gate):
            if not (repo_root / path).is_file():
                findings.append(
                    f"script-drift: {gate.get('id', '<unknown>')}: "
                    f"script path does not exist: {path}"
                )
    return findings


def find_policy_ref_drift(instance: dict) -> list[str]:
    """Return one message per gates[].policy_refs[] value that doesn't resolve
    to a real policy_sources[].id."""
    known_ids = {source.get("id") for source in instance.get("policy_sources", [])}
    findings = []
    for gate in instance.get("gates", []):
        for ref in gate.get("policy_refs", []):
            if ref not in known_ids:
                findings.append(
                    f"policy-ref-drift: {gate.get('id', '<unknown>')}: "
                    f"policy_refs references unknown policy_sources id {ref!r}"
                )
    return findings


def find_cluster_drift(instance: dict) -> list[str]:
    """Return one message per gates[].cluster value that doesn't name a real
    top-level clusters key."""
    known_clusters = set(instance.get("clusters", {}))
    findings = []
    for gate in instance.get("gates", []):
        for cluster in _cluster_values(gate):
            if cluster not in known_clusters:
                findings.append(
                    f"cluster-drift: {gate.get('id', '<unknown>')}: "
                    f"cluster references unknown clusters key {cluster!r}"
                )
    return findings


def find_drift(
    instance_path: pathlib.Path = SSOT_PATH,
    schema_path: pathlib.Path = SCHEMA_PATH,
    repo_root: pathlib.Path = REPO_ROOT,
) -> list[str]:
    """Return every drift finding across schema validation and the three
    repo-grounded reference checks. Empty list means the registry is clean."""
    instance = _load_json(instance_path)
    schema = _load_json(schema_path)

    findings: list[str] = []
    findings.extend(find_schema_violations(instance, schema))
    findings.extend(find_script_drift(instance, repo_root))
    findings.extend(find_policy_ref_drift(instance))
    findings.extend(find_cluster_drift(instance))
    return findings


def main() -> int:
    findings = find_drift()
    if findings:
        print("ssot.json drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No ssot.json drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

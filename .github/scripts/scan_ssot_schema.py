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
  ``policy_sources[].id``;
- any ``gates[].cluster`` value does not name a real top-level ``clusters``
  key; or
- any ``gates[].id`` or ``policy_sources[].id`` is used more than once (an
  unnoticed duplicate would silently make one entry invisible to every
  cross-reference this scanner performs).

Validation is layered. ``jsonschema.Draft202012Validator`` first checks the
raw instance against ``.gitapex/ssot.schema.json`` and reports every
violation with a JSON-pointer-shaped location -- the general schema-invalid
case, with a good error message. The reference-drift checks
(``find_script_drift``/``find_policy_ref_drift``/``find_cluster_drift``)
then run against a ``SsotRegistry`` pydantic model parsed from that same
instance, which gives them typed ``Gate``/``PolicySource`` objects to work
with instead of hand-rolled ``dict.get``/``isinstance`` re-derivation. A
schema-invalid instance (a missing required field, or an explicit JSON
``null`` in place of an array -- a schema-invalid but not-impossible shape
for a hand-edited file) may also fail this pydantic parse; when it does,
``_parse_registry`` returns ``None`` rather than raising, and the three
reference-drift checks below simply have nothing typed to check, deferring
to ``find_schema_violations`` to report the real problem instead of
crashing with an unhandled exception.

``find_duplicate_ids`` still walks the raw instance dict directly, not
through the pydantic model, since a duplicate id can occur in an otherwise
schema-valid and pydantic-valid instance (neither the schema nor these
models express a cross-item uniqueness constraint) -- every list/dict
lookup it performs defaults on an absent key, an explicit JSON ``null``,
and a non-dict ``gates``/``policy_sources`` entry (e.g. a bare int or
string), for the same reason as before: a schema-invalid entry is
``find_schema_violations``'s finding to report, not a reason for this
function to raise past it.

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
from typing import Any, Literal

import jsonschema
from pydantic import BaseModel, ConfigDict, ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"
SCHEMA_PATH = REPO_ROOT / ".gitapex" / "ssot.schema.json"


class RegistryReadError(Exception):
    """Either ``.gitapex/ssot.json`` or ``.gitapex/ssot.schema.json`` could
    not be read as UTF-8 text or parsed as JSON at all -- exit 1, never a
    traceback. Distinct from a schema-valid-JSON-but-drifted instance,
    which ``find_schema_violations`` reports as an ordinary finding."""


class PolicySource(BaseModel):
    """.gitapex/ssot.json ``policy_sources[]`` entry: a file at least one
    gate reads as authoritative data via ``policy_refs``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    path: str
    format: Literal["toml", "json", "yaml", "rego"]
    authority: str


class Gate(BaseModel):
    """.gitapex/ssot.json ``gates[]`` entry: one deterministic gate gitapex
    enforces on itself. ``script``/``native_rule`` stay optional here -- the
    schema's own if/then keeps them conditionally required by ``kind``,
    already enforced by ``find_schema_violations`` before this model is ever
    constructed."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["script", "native", "opa-rego"]
    script: str | list[str] | None = None
    native_rule: str | None = None
    rule: str
    planes: list[Literal["pretooluse", "posttooluse", "ci"]]
    trigger: str
    policy_refs: list[str]
    cluster: str | list[str]
    tracking_issue: int | None
    status: Literal["experimental", "active", "deprecated"]
    supersedes: str | None


class SsotMeta(BaseModel):
    """.gitapex/ssot.json ``meta``: registry-level lifecycle, distinct from
    any single gate's own status."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    tracking_issue: int
    status: Literal["draft", "active", "deprecated"]
    phase: str


class SsotRegistry(BaseModel):
    """The full, already-jsonschema-checked ``.gitapex/ssot.json`` document,
    typed for the reference-drift checks below."""

    model_config = ConfigDict(extra="forbid")

    meta: SsotMeta
    policy_sources: list[PolicySource]
    gates: list[Gate]
    clusters: dict[str, str]


def _load_json(path: pathlib.Path) -> Any:
    """Read and JSON-parse `path`. Raises RegistryReadError -- naming
    `path` -- rather than letting a non-UTF-8 file or invalid JSON syntax
    surface as an uncaught UnicodeDecodeError/JSONDecodeError traceback.
    Does not itself check the parsed value's shape (dict vs. list/str/
    etc.) -- callers that need a dict guard that separately, since a
    schema-invalid-but-parseable instance (e.g. a JSON array at the top
    level) is find_schema_violations's finding to report, not a load
    failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RegistryReadError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise RegistryReadError(f"{path}: is not valid UTF-8: {error}") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RegistryReadError(f"{path}: is not valid JSON: {error}") from error


def _get_list(d: Any, key: str) -> list[Any]:
    """d.get(key, []), but also defaults when `d` isn't a dict at all (not
    just when the key's own value is an explicit JSON null) -- dict.get's
    default only covers the latter, and callers such as find_duplicate_ids
    may be handed a whole-instance value that jsonschema will separately
    flag as a schema violation but that isn't itself a dict (e.g. `[]` or
    `1` at the JSON document root). Used only by find_duplicate_ids, which
    stays dict-based (see module docstring)."""
    if not isinstance(d, dict):
        return []
    value = d.get(key)
    return value if isinstance(value, list) else []


def _script_paths(gate: dict[str, Any]) -> list[str]:
    """Dict-based script-path extraction. Kept for its own direct test
    coverage (test_script_paths_defaults_to_empty_when_absent); the
    pydantic-driven find_script_drift below normalizes Gate.script itself
    via _as_list instead of calling this."""
    script = gate.get("script")
    if script is None:
        return []
    return [script] if isinstance(script, str) else list(script)


def _cluster_values(gate: dict[str, Any]) -> list[str]:
    """Dict-based cluster-value extraction. Kept for its own direct test
    coverage (test_cluster_values_defaults_to_empty_when_absent); the
    pydantic-driven find_cluster_drift below normalizes Gate.cluster itself
    via _as_list instead of calling this."""
    cluster = gate.get("cluster")
    if cluster is None:
        return []
    return [cluster] if isinstance(cluster, str) else list(cluster)


def _as_list(value: str | list[str] | None) -> list[str]:
    """Normalize a oneOf(string, array-of-string) pydantic field
    (Gate.script or Gate.cluster) to a list -- the typed equivalent of
    _script_paths/_cluster_values above, used by the pydantic-driven checks
    below."""
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _parse_registry(instance: Any) -> SsotRegistry | None:
    """Parse an already-jsonschema-checked instance dict into a typed
    SsotRegistry. Never raises: a schema-invalid instance (a missing field,
    an explicit null in place of an array/object) may also fail this parse,
    in which case find_schema_violations already reports the real problem
    and the reference-drift checks below simply have nothing typed to
    check."""
    try:
        return SsotRegistry.model_validate(instance)
    except ValidationError:
        return None


def find_schema_violations(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Return one message per JSON-Schema (draft 2020-12) validation error
    against the given schema. Empty list means the instance is valid."""
    validator = jsonschema.Draft202012Validator(schema)
    findings: list[str] = []
    for error in validator.iter_errors(instance):
        location = "/".join(str(p) for p in error.path) or "<root>"
        findings.append(f"schema: {location}: {error.message}")
    return findings


def find_script_drift(
    registry: SsotRegistry | None, repo_root: pathlib.Path = REPO_ROOT
) -> list[str]:
    """Return one message per gates[] script path that doesn't exist as a real
    file. Only checked for kind == "script" -- "native" gates have no repo
    file to check, and "opa-rego" gates aren't seeded yet."""
    if registry is None:
        return []
    findings: list[str] = []
    for gate in registry.gates:
        if gate.kind != "script":
            continue
        for path in _as_list(gate.script):
            if not (repo_root / path).is_file():
                findings.append(
                    f"script-drift: {gate.id}: "
                    f"script path does not exist: {path}"
                )
    return findings


def find_policy_ref_drift(registry: SsotRegistry | None) -> list[str]:
    """Return one message per gates[].policy_refs[] value that doesn't resolve
    to a real policy_sources[].id."""
    if registry is None:
        return []
    known_ids = {source.id for source in registry.policy_sources}
    findings: list[str] = []
    for gate in registry.gates:
        for ref in gate.policy_refs:
            if ref not in known_ids:
                findings.append(
                    f"policy-ref-drift: {gate.id}: "
                    f"policy_refs references unknown policy_sources id {ref!r}"
                )
    return findings


def find_cluster_drift(registry: SsotRegistry | None) -> list[str]:
    """Return one message per gates[].cluster value that doesn't name a real
    top-level clusters key."""
    if registry is None:
        return []
    known_clusters = set(registry.clusters)
    findings: list[str] = []
    for gate in registry.gates:
        for cluster in _as_list(gate.cluster):
            if cluster not in known_clusters:
                findings.append(
                    f"cluster-drift: {gate.id}: "
                    f"cluster references unknown clusters key {cluster!r}"
                )
    return findings


def find_duplicate_ids(instance: Any) -> list[str]:
    """Return one message per id used more than once across gates[] or
    across policy_sources[] (checked as two separate namespaces -- a gate
    and a policy source are never cross-referenced by the same field, so a
    shared string between the two namespaces is not itself a collision).
    An unnoticed duplicate would silently make one entry invisible to every
    cross-reference the other checks in this module perform."""
    findings: list[str] = []
    for label, key in (("gate", "gates"), ("policy-source", "policy_sources")):
        seen: dict[str, int] = {}
        for entry in _get_list(instance, key):
            # A schema-valid-shaped gates[]/policy_sources[] array can still
            # carry a non-dict entry (e.g. a bare int or string, or an
            # explicit null) -- schema-invalid, caught separately by
            # find_schema_violations, but entry.get("id") below would raise
            # an uncaught AttributeError on such an entry before that
            # finding was even reported. Skip it here the same way an
            # entry missing "id" is already skipped.
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id")
            if entry_id is None:
                continue
            seen[entry_id] = seen.get(entry_id, 0) + 1
        for entry_id, count in seen.items():
            if count > 1:
                findings.append(
                    f"duplicate-id: {label} id {entry_id!r} is used {count} times"
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
    registry = _parse_registry(instance)

    findings: list[str] = []
    findings.extend(find_schema_violations(instance, schema))
    findings.extend(find_script_drift(registry, repo_root))
    findings.extend(find_policy_ref_drift(registry))
    findings.extend(find_cluster_drift(registry))
    findings.extend(find_duplicate_ids(instance))
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except RegistryReadError as error:
        print("ssot.json drift:")
        print(f"  {error}")
        return 1
    if findings:
        print("ssot.json drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No ssot.json drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

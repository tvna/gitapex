#!/usr/bin/env python3
"""Validate every skill's metadata sidecar against the SkillMetadata schema.

DRAFT -- not yet wired into any CI workflow or pre-commit hook. This scanner
is scoped, deliberately, to a narrower job than
skills/evaluating-skill-quality/scripts/check_skill_shape.py's own
manifest-parsing checks: it validates metadata/gitapex.yaml's *structural*
shape (types, enums, required fields, patterns, and the one cross-FIELD rule
this format has -- requires-portability-compatible) via a real JSON Schema
(.gitapex/skill-metadata.schema.json) and a real YAML parser (PyYAML), rather
than check_skill_shape.py's own hand-rolled, stdlib-only, indentation-aware
reader. It does NOT replace check_skill_shape.py: that checker also covers
SKILL.md/references/*.md prose (bare-issue-citation scanning, Markdown
link/anchor resolution, cross-skill citation resolution, illustrative-model-
identifier/placeholder scanning, step-location-contradiction detection, and
more) that has nothing to do with this sidecar file's shape and that no
JSON Schema for metadata/gitapex.yaml could ever express.

Layered validation, mirroring .gitapex/ssot.schema.json's own scanner
(.github/scripts/scan_ssot_schema.py):

1. ``jsonschema.Draft202012Validator`` (with format assertion enabled, so
   spec.lifecycle's since/removeAfter dates are checked as real calendar
   dates, not just YYYY-MM-DD shape) checks each sidecar instance against
   the schema and reports every violation with a JSON-pointer-shaped
   location.
2. Three cross-FILE checks the schema cannot express on its own, since a
   single JSON Schema instance never sees a second file:
   - ``metadata-name-matches-dir``: metadata.name equals the sidecar's own
     skill directory name.
   - ``skill-dependencies-resolve`` / ``lifecycle-deprecated-replacement-
     resolves``: every spec.skillDependencies.requires/relatedTo entry and
     spec.lifecycle.deprecated.replacement, if present, names an existing
     sibling skills/<name>/ directory.
   - A repo-wide ``requires`` acyclicity check across every sidecar's
     spec.skillDependencies.requires graph (mirrors
     tests/test_skill_metadata_sidecar.py's own ``_find_requires_cycle``);
     genuinely repo-wide, so it cannot live in the per-skill loop below.

Run standalone (exit 1 on drift, 2 on bad usage) or via the pytest gate in
tests/test_scan_skill_metadata_schema.py.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import jsonschema
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
SCHEMA_PATH = REPO_ROOT / ".gitapex" / "skill-metadata.schema.json"
# Mirrors check_skill_shape.py's own SIDECAR_RELATIVE_PATH constant --
# duplicated as a literal here rather than imported, the same way every
# other .github/scripts/*.py sidecar consumer (gate_skill_rename_lifecycle.py,
# gate_routine_scope_enforcement.py, gate_transfer_check_disclosure.py)
# already hardcodes this path, so this script stays runnable standalone
# (``python3 .github/scripts/scan_skill_metadata_schema.py``) without relying
# on skills/evaluating-skill-quality/scripts being on sys.path.
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Guards against discover_skill_dirs silently finding nothing (a wrong or
# missing skills_dir, an empty/misconfigured checkout) and find_drift then
# vacuously reporting "no drift" -- mirroring
# tests/test_skill_metadata_sidecar.py's own MIN_EXPECTED_SKILLS floor and
# its stated reasoning verbatim. There are 24 skills in this repository
# today; this floor is set close to that real count with headroom, not at 1,
# so a partial discovery failure (most, not all, skills silently dropped)
# is caught too, not only a total-zero one.
MIN_EXPECTED_SKILL_DIRS = 15


class SidecarReadError(Exception):
    """A sidecar could not be read as UTF-8 text or parsed as YAML at all --
    exit 1, never a traceback. Distinct from a schema-invalid-but-parseable
    instance, which find_schema_violations reports as an ordinary finding."""


def discover_skill_dirs(skills_dir: pathlib.Path = SKILLS_DIR) -> list[pathlib.Path]:
    """Every skills/<name>/ directory with a real SKILL.md, sorted -- the
    same discovery rule tests/test_skill_metadata_sidecar.py's own
    _discover_skill_dirs uses, so both agree on what counts as a real skill."""
    if not skills_dir.is_dir():
        return []
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md") if p.is_file())


def load_sidecar(path: pathlib.Path) -> Any:
    """Read and YAML-parse ``path``. Raises SidecarReadError -- naming
    ``path`` -- rather than letting a non-UTF-8 file or invalid YAML syntax
    surface as an uncaught UnicodeDecodeError/YAMLError traceback. Does not
    itself check the parsed value's shape (dict vs. list/str/None) -- a
    schema-invalid-but-parseable instance (e.g. a YAML document that is just
    a bare scalar) is find_schema_violations's finding to report, not a load
    failure."""
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


def _load_schema(schema_path: pathlib.Path) -> dict[str, Any]:
    try:
        text = schema_path.read_text(encoding="utf-8")
    except OSError as error:
        raise SidecarReadError(f"{schema_path}: cannot be read: {error}") from error
    try:
        parsed: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as error:
        raise SidecarReadError(f"{schema_path}: is not valid JSON: {error}") from error
    return parsed


def find_schema_violations(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Return one message per JSON-Schema (draft 2020-12) validation error
    against ``schema``. ``format_checker`` is passed explicitly -- the
    JSON Schema spec itself permits a consumer to ignore format assertions,
    and the plain jsonschema.Draft202012Validator(schema) constructor does
    exactly that, which would silently accept an out-of-range calendar date
    like "2026-02-30" that only fails the schema's "format": "date" keyword,
    not its "pattern" keyword. Empty list means the instance is valid."""
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker())
    findings: list[str] = []
    for error in validator.iter_errors(instance):
        location = "/".join(str(p) for p in error.path) or "<root>"
        findings.append(f"schema: {location}: {error.message}")
    return findings


def _spec_of(instance: Any) -> dict[str, Any]:
    """instance["spec"], guarded against a non-mapping/absent spec -- the
    same isinstance guard check_skill_shape.py's own spec_of() centralizes,
    reproduced here since this module is deliberately standalone (see
    SIDECAR_RELATIVE_PATH's own comment)."""
    if not isinstance(instance, dict):
        return {}
    spec = instance.get("spec")
    return spec if isinstance(spec, dict) else {}


def find_name_mismatch(
    instance: Any, skill_dir: pathlib.Path
) -> list[str]:
    """metadata-name-matches-dir: metadata.name must equal skill_dir's own
    name. Cross-file by nature (the instance alone never carries the
    directory it was read from), so this cannot be a schema keyword."""
    if not isinstance(instance, dict):
        return []
    metadata = instance.get("metadata")
    name = metadata.get("name") if isinstance(metadata, dict) else None
    if name is not None and name != skill_dir.name:
        return [f"metadata-name-matches-dir: {name!r} vs directory {skill_dir.name!r}"]
    return []


def find_skill_dependency_drift(
    instance: Any, skills_dir: pathlib.Path = SKILLS_DIR
) -> list[str]:
    """skill-dependencies-resolve: every spec.skillDependencies.requires/
    relatedTo entry must name an existing sibling skills/<name>/ directory."""
    deps = _spec_of(instance).get("skillDependencies")
    if not isinstance(deps, dict):
        return []
    findings: list[str] = []
    for list_key in ("requires", "relatedTo"):
        entries = deps.get(list_key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, str) and not (skills_dir / entry).is_dir():
                findings.append(
                    f"skill-dependencies-resolve: {list_key} references "
                    f"unknown skill directory {entry!r}")
    return findings


def find_deprecated_replacement_drift(
    instance: Any, skills_dir: pathlib.Path = SKILLS_DIR
) -> list[str]:
    """lifecycle-deprecated-replacement-resolves: spec.lifecycle.deprecated.
    replacement, if present, must name an existing sibling skills/<name>/
    directory -- the same dangling-reference gate as skill-dependencies-
    resolve, one field over."""
    lifecycle = _spec_of(instance).get("lifecycle")
    deprecated = lifecycle.get("deprecated") if isinstance(lifecycle, dict) else None
    replacement = deprecated.get("replacement") if isinstance(deprecated, dict) else None
    if isinstance(replacement, str) and replacement and not (skills_dir / replacement).is_dir():
        return [
            "lifecycle-deprecated-replacement-resolves: deprecated.replacement "
            f"references unknown skill directory {replacement!r}"
        ]
    return []


def _requires_graph(
    skill_dirs: list[pathlib.Path], skills_dir: pathlib.Path
) -> dict[str, list[str]]:
    """skill-name -> its own spec.skillDependencies.requires list, built
    from every skill directory whose sidecar reads as valid YAML with a
    real requires list. A sidecar that fails to load or has a malformed
    requires field contributes an empty list -- find_schema_violations
    already reports that shape defect separately; this graph builder must
    not crash on it."""
    graph: dict[str, list[str]] = {}
    for skill_dir in skill_dirs:
        sidecar = skill_dir / SIDECAR_RELATIVE_PATH
        if not sidecar.is_file():
            continue
        try:
            instance = load_sidecar(sidecar)
        except SidecarReadError:
            graph[skill_dir.name] = []
            continue
        deps = _spec_of(instance).get("skillDependencies")
        requires = deps.get("requires") if isinstance(deps, dict) else None
        graph[skill_dir.name] = (
            [r for r in requires if isinstance(r, str)]
            if isinstance(requires, list) else [])
    return graph


def find_requires_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle (as a path of skill names) if ``graph`` contains
    one, else None. Standard white/gray/black DFS, mirroring
    tests/test_skill_metadata_sidecar.py's own _find_requires_cycle -- a
    `requires` cycle is a real error (two skills each unable to function
    without the other is not a coherent state); a `relatedTo` cycle is not
    checked here at all and is expected to be fine."""
    white, gray, black = 0, 1, 2
    color = {name: white for name in graph}
    path: list[str] = []

    def visit(name: str) -> list[str] | None:
        color[name] = gray
        path.append(name)
        for dep in graph.get(name, []):
            if dep not in color:
                continue
            if color[dep] == gray:
                return [*path[path.index(dep):], dep]
            if color[dep] == white:
                found = visit(dep)
                if found:
                    return found
        path.pop()
        color[name] = black
        return None

    for name in graph:
        if color[name] == white:
            found = visit(name)
            if found:
                return found
    return None


def find_drift(
    skills_dir: pathlib.Path = SKILLS_DIR,
    schema_path: pathlib.Path = SCHEMA_PATH,
    min_expected_skill_dirs: int = MIN_EXPECTED_SKILL_DIRS,
) -> list[str]:
    """Return every drift finding across every discovered skill's sidecar:
    schema violations, the two per-skill dangling-reference checks, and the
    one repo-wide requires-acyclicity check. Empty list means every sidecar
    is clean.

    ``min_expected_skill_dirs`` is a fail-closed floor on discovery itself,
    checked before any of the above: fewer than this many real skill
    directories is treated as a drift finding, not silently reported as
    "no drift" (dimension 15, evaluating-deterministic-gate-quality --
    without this, a wrong or missing ``skills_dir`` argument, or a
    checkout that lost most of skills/, would pass this gate vacuously,
    exactly the "an empty match set is an error, never a silent pass"
    failure class issue #651's retrospective named). A caller exercising a
    deliberately small fixture directory (this module's own tests) must
    pass a lower value explicitly; every other caller, including
    ``main()``, keeps the real-repository-sized default.
    """
    schema = _load_schema(schema_path)
    skill_dirs = discover_skill_dirs(skills_dir)

    if len(skill_dirs) < min_expected_skill_dirs:
        return [
            f"skill-discovery-floor: found only {len(skill_dirs)} skill "
            f"director{'y' if len(skill_dirs) == 1 else 'ies'} with a "
            f"SKILL.md under {skills_dir} (expected at least "
            f"{min_expected_skill_dirs}) -- this usually means skills_dir "
            "is wrong or missing, not that skills were actually removed"
        ]

    findings: list[str] = []
    for skill_dir in skill_dirs:
        sidecar = skill_dir / SIDECAR_RELATIVE_PATH
        prefix = skill_dir.name
        if not sidecar.is_file():
            findings.append(f"{prefix}: metadata-file-present: missing {sidecar}")
            continue
        try:
            instance = load_sidecar(sidecar)
        except SidecarReadError as error:
            findings.append(f"{prefix}: {error}")
            continue
        findings.extend(f"{prefix}: {f}" for f in find_schema_violations(instance, schema))
        findings.extend(f"{prefix}: {f}" for f in find_name_mismatch(instance, skill_dir))
        findings.extend(
            f"{prefix}: {f}" for f in find_skill_dependency_drift(instance, skills_dir))
        findings.extend(
            f"{prefix}: {f}" for f in find_deprecated_replacement_drift(instance, skills_dir))

    cycle = find_requires_cycle(_requires_graph(skill_dirs, skills_dir))
    if cycle is not None:
        findings.append(
            f"requires-acyclicity: requires cycle found: {' -> '.join(cycle)}")

    return findings


def main() -> int:
    try:
        findings = find_drift()
    except SidecarReadError as error:
        print("skill metadata schema drift:")
        print(f"  {error}")
        return 1
    if findings:
        print("skill metadata schema drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No skill metadata schema drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate every skill's metadata sidecar against the SkillMetadata schema.

ACTIVE (issue #745): registered in .gitapex/ssot.json as
skill-metadata-schema-drift. Enforced the same way its sibling
.github/scripts/gitapex_scan_ssot_schema.py (registered there as ssot-schema-drift)
already is -- neither has a dedicated CI workflow step or pre-commit hook;
both are enforced solely because tests/test_gitapex_scan_skill_metadata_schema.py's
own test_real_repository_skill_sidecars_have_no_schema_drift calls
find_drift() against the real skills/ tree with no fixture override, and
tests/ is auto-discovered by pytest via pyproject.toml's [tool.pytest.
ini_options] testpaths -- which .github/workflows/test.yml runs as a
required check on every push and PR. A real schema violation fails CI
through that pytest gate; there is no separate standalone `python3
.github/scripts/gitapex_scan_skill_metadata_schema.py` invocation anywhere in CI,
matching this repository's own established convention for this exact gate
shape rather than adding a second, redundant enforcement path. This scanner
is scoped, deliberately, to a narrower job than
skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py's own
manifest-parsing checks: it validates metadata/gitapex.yaml's *structural*
shape (types, enums, required fields, patterns, and the one cross-FIELD rule
this format has -- requires-portability-compatible) via a real JSON Schema
(.gitapex/skill-metadata.schema.json) and a real YAML parser (PyYAML), rather
than gitapex_check_skill_shape.py's own hand-rolled, stdlib-only, indentation-aware
reader. It does NOT replace gitapex_check_skill_shape.py: that checker also covers
SKILL.md/references/*.md prose (bare-issue-citation scanning, Markdown
link/anchor resolution, cross-skill citation resolution, illustrative-model-
identifier/placeholder scanning, step-location-contradiction detection, and
more) that has nothing to do with this sidecar file's shape and that no
JSON Schema for metadata/gitapex.yaml could ever express.

Layered validation, mirroring .gitapex/ssot.schema.json's own scanner
(.github/scripts/gitapex_scan_ssot_schema.py):

1. ``jsonschema.Draft202012Validator`` (with format assertion enabled, so
   spec.lifecycle's since/removeAfter dates are checked as real calendar
   dates, not just YYYY-MM-DD shape) checks each sidecar instance against
   the schema and reports every violation with a JSON-pointer-shaped
   location. The load-or-raise and validator-build/iter-errors logic this
   relies on is shared with gitapex_scan_ssot_schema.py via
   _gitapex_schema_validation.py (issue #755) rather than each script
   carrying its own near-verbatim copy -- see that module's own docstring
   for why, including the format-checker drift this extraction backports a
   fix for into gitapex_scan_ssot_schema.py.
2. Three cross-FILE checks the schema cannot express on its own, since a
   single JSON Schema instance never sees a second file:
   - ``metadata-name-matches-dir``: metadata.name equals the sidecar's own
     skill directory name.
   - ``skill-dependencies-resolve`` / ``lifecycle-deprecated-replacement-
     resolves``: every spec.skillDependencies.requires/relatedTo entry and
     spec.lifecycle.deprecated.replacement, if present, names an existing
     sibling skills/<name>/ directory.
   - A repo-wide ``requires`` acyclicity check across every sidecar's
     spec.skillDependencies.requires graph (exercised directly, not
     duplicated, by tests/test_gitapex_skill_metadata_sidecar.py).
     The graph itself is accumulated inside the same per-skill loop that
     runs every other check below (one sidecar read each, not two), but
     detecting a cycle genuinely needs the WHOLE graph, so that detection
     step still runs once, after every skill has been read.

Run standalone (exit 0 clean, 1 on drift or a read error) or via the pytest
gate in tests/test_gitapex_scan_skill_metadata_schema.py.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import _gitapex_schema_validation
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
SCHEMA_PATH = REPO_ROOT / ".gitapex" / "skill-metadata.schema.json"
# Mirrors gitapex_check_skill_shape.py's own SIDECAR_RELATIVE_PATH constant --
# duplicated as a literal here rather than imported, the same way every
# other .github/scripts/*.py script that actually reads the sidecar
# (gitapex_gate_skill_rename_lifecycle.py, gitapex_gate_routine_scope_enforcement.py --
# verified live, both hardcode this exact path) already hardcodes this
# path, so this script stays runnable standalone (``python3 .github/
# scripts/gitapex_scan_skill_metadata_schema.py``) without relying on skills/
# evaluating-skill-quality/scripts being on sys.path. A prior version of
# this comment also named gitapex_gate_transfer_check_disclosure.py, but that
# script never reads the sidecar at all -- its one "metadata/gitapex.yaml"
# mention is a docstring analogy describing gitapex_gate_skill_rename_lifecycle.py's
# own behavior, not code of its own (found by adversarial review of this
# file).
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Guards against discover_skill_dirs silently finding nothing (a wrong or
# missing skills_dir, an empty/misconfigured checkout) and find_drift then
# vacuously reporting "no drift" -- the same purpose and the same numeric
# value as tests/test_gitapex_skill_metadata_sidecar.py's own MIN_EXPECTED_SKILLS
# floor, but NOT its reasoning verbatim (a prior version of this comment
# claimed otherwise; found by adversarial review of this file): that file's
# own comment still cites "17 skills" as the real count, stale against the
# repository's actual 24 (confirmed via `ls skills/*/SKILL.md | wc -l`) --
# a fact this comment does not re-derive, since a stale count in a sibling
# file is that file's own drift to fix, not this one's to inherit. This
# floor is set close to the real, current count (24) with headroom, not at
# 1, so a partial discovery failure (most, not all, skills silently
# dropped) is caught too, not only a total-zero one.
MIN_EXPECTED_SKILL_DIRS = 15


class SidecarReadError(Exception):
    """A sidecar could not be read as UTF-8 text or parsed as YAML at all --
    exit 1, never a traceback. Distinct from a schema-invalid-but-parseable
    instance, which find_schema_violations reports as an ordinary finding."""


def discover_skill_dirs(skills_dir: pathlib.Path = SKILLS_DIR) -> list[pathlib.Path]:
    """Every skills/<name>/ directory with a real SKILL.md, sorted -- the
    same discovery rule tests/test_gitapex_skill_metadata_sidecar.py's own
    _discover_skill_dirs uses, so both agree on what counts as a real skill."""
    if not skills_dir.is_dir():
        return []
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md") if p.is_file())


def load_sidecar(path: pathlib.Path) -> Any:
    """Read and YAML-parse ``path``. Raises SidecarReadError -- naming
    ``path`` -- rather than letting a non-UTF-8 file, invalid YAML syntax, or
    pathologically deep nesting surface as an uncaught
    UnicodeDecodeError/YAMLError/RecursionError traceback. Does not itself
    check the parsed value's shape (dict vs. list/str/None) -- a
    schema-invalid-but-parseable instance (e.g. a YAML document that is just
    a bare scalar) is find_schema_violations's finding to report, not a load
    failure.

    RecursionError is caught alongside yaml.YAMLError, not folded into the
    same except clause -- it is not a YAMLError subclass, so a deeply nested
    sidecar (e.g. thousands of nested "[" flow-sequence levels) previously
    propagated an uncaught RecursionError straight out of this function,
    crashing the whole scan instead of reporting one clean per-sidecar
    finding the way every other malformed-input case here does (found by
    adversarial review of this file, since the bundled test suite's own
    fixtures never constructed this specific malformed-input shape)."""
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


def _load_schema(schema_path: pathlib.Path) -> dict[str, Any]:
    parsed: dict[str, Any] = _gitapex_schema_validation.load_json_or_raise(schema_path, SidecarReadError)
    return parsed


def find_schema_violations(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Return one message per JSON-Schema (draft 2020-12) validation error
    against ``schema``. Convenience wrapper that builds a fresh validator on
    every call -- fine for the occasional direct caller (this module's own
    tests), but find_drift builds one validator per run instead and reuses
    it across every discovered skill via _gitapex_schema_validation.schema_violations,
    rather than re-compiling the same 13-$defs schema once per skill
    (adversarial review of this file: jsonschema's validator construction
    performs $ref resolution/registry setup, real, avoidable repeated work
    at the repository's current 24-skill scale)."""
    return _gitapex_schema_validation.schema_violations(instance, _gitapex_schema_validation.build_validator(schema))


def _spec_of(instance: Any) -> dict[str, Any]:
    """instance["spec"], guarded against a non-mapping/absent spec -- the
    same isinstance guard gitapex_check_skill_shape.py's own spec_of() centralizes,
    reproduced here since this module is deliberately standalone (see
    SIDECAR_RELATIVE_PATH's own comment)."""
    if not isinstance(instance, dict):
        return {}
    spec = instance.get("spec")
    return spec if isinstance(spec, dict) else {}


def _is_bare_skill_name(entry: str) -> bool:
    """Whether ``entry`` is shaped like a real skill directory name -- a
    bare path component (no separator, not ".", not "..") -- rather than a
    path that could escape ``skills_dir`` when joined with ``/``.
    ``(skills_dir / entry).is_dir()`` does not itself guard against
    pathlib's absolute-operand-replaces-the-left-side behavior
    (``pathlib.Path("/repo/skills") / "/etc" == pathlib.Path("/etc")``) or a
    "../" traversal segment, so an entry that is not a bare name must never
    be treated as potentially resolving -- found by adversarial review of
    this file: ``find_skill_dependency_drift``/
    ``find_deprecated_replacement_drift`` previously reported a dangling
    "/etc" or "../../../../../../etc" entry as resolving whenever that path
    happened to exist on disk, silently passing a reference that plainly
    does not name a sibling skills/<name>/ directory.

    No separate ``is_absolute()`` check: any POSIX absolute path starts with
    "/", so the ``"/" not in entry`` clause below already excludes every
    absolute path on its own -- a prior version of this function carried a
    redundant ``pathlib.PurePosixPath(entry).is_absolute()`` clause that
    could never evaluate differently once that clause held, which a reader
    could mistake for an independent Windows-drive-letter-style defense it
    never provided (found by adversarial review of this file)."""
    return entry not in ("", ".", "..") and "/" not in entry and "\\" not in entry


def _resolves_to_sibling_skill(name: str, skills_dir: pathlib.Path) -> bool:
    """Whether ``name`` names an existing sibling skill directory: a bare
    name (see ``_is_bare_skill_name``) whose ``skills_dir / name`` also
    contains a real ``SKILL.md`` -- the same "real skill directory"
    definition ``discover_skill_dirs`` already uses, not merely
    ``.is_dir()``. Without the ``SKILL.md`` check, any non-skill directory
    under ``skills_dir`` (a docs folder, a work-in-progress directory with
    no ``SKILL.md`` yet, a stray build artifact) would incorrectly read as
    a resolved reference -- found by adversarial review of this file, and
    verified live against a constructed fixture directory with no
    ``SKILL.md``. Shared by ``find_skill_dependency_drift`` and
    ``find_deprecated_replacement_drift`` so the one safety-critical
    "does this reference resolve" predicate has exactly one implementation,
    not two copies that could silently diverge."""
    return _is_bare_skill_name(name) and (skills_dir / name / "SKILL.md").is_file()


def find_name_mismatch(instance: Any, skill_dir: pathlib.Path) -> list[str]:
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


def find_skill_dependency_drift(instance: Any, skills_dir: pathlib.Path = SKILLS_DIR) -> list[str]:
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
            if isinstance(entry, str) and not _resolves_to_sibling_skill(entry, skills_dir):
                findings.append(f"skill-dependencies-resolve: {list_key} references unknown skill directory {entry!r}")
    return findings


def find_deprecated_replacement_drift(instance: Any, skills_dir: pathlib.Path = SKILLS_DIR) -> list[str]:
    """lifecycle-deprecated-replacement-resolves: spec.lifecycle.deprecated.
    replacement, if present, must name an existing sibling skills/<name>/
    directory -- the same dangling-reference gate as skill-dependencies-
    resolve, one field over.

    Deliberately no truthiness short-circuit on ``replacement`` beyond the
    ``isinstance(replacement, str)`` type guard -- a prior version also
    required ``replacement`` to be truthy before checking resolution, which
    let an empty-string replacement silently read as "nothing to check"
    instead of "dangling," inconsistent with find_skill_dependency_drift's
    own sibling entries (which carry no such exemption). Masked in the full
    find_drift() pipeline today because the schema's own skillNameRef
    pattern already rejects an empty string, but this function's own
    standalone behavior was wrong regardless (found by adversarial review
    of this file, verified live: calling this function directly with
    replacement="" returned [] before this fix)."""
    lifecycle = _spec_of(instance).get("lifecycle")
    deprecated = lifecycle.get("deprecated") if isinstance(lifecycle, dict) else None
    replacement = deprecated.get("replacement") if isinstance(deprecated, dict) else None
    if isinstance(replacement, str) and not _resolves_to_sibling_skill(replacement, skills_dir):
        return [
            "lifecycle-deprecated-replacement-resolves: deprecated.replacement "
            f"references unknown skill directory {replacement!r}"
        ]
    return []


def find_requires_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle (as a path of skill names) if ``graph`` contains
    one, else None. Standard white/gray/black DFS. tests/test_gitapex_skill_
    metadata_sidecar.py imports and exercises this function directly -- a
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
                return [*path[path.index(dep) :], dep]
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

    Each sidecar is read exactly once: the requires-acyclicity graph is
    accumulated alongside the other per-skill checks in the same loop
    below, rather than by a second pass re-reading and re-parsing every
    sidecar (a prior version had a dedicated ``_requires_graph`` helper
    that did exactly that -- 48 file reads/YAML parses per run at this
    repository's current 24-skill scale instead of 24; found by
    adversarial review of this file). The requires-acyclicity check itself
    still genuinely needs the WHOLE graph, so it still runs once, after
    every skill has been read, not inside the per-skill loop.
    """
    schema = _load_schema(schema_path)
    validator = _gitapex_schema_validation.build_validator(schema)
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
    graph: dict[str, list[str]] = {}
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
            # Mirrors the prior _requires_graph's own read-failure handling:
            # a sidecar that fails to load contributes an empty requires
            # list (a dead end for cycle detection), not a missing graph
            # entry -- find_schema_violations has nothing to report here
            # since there is no parsed instance, but this skill still
            # participates in the acyclicity check as a childless node.
            graph[prefix] = []
            continue
        findings.extend(f"{prefix}: {f}" for f in _gitapex_schema_validation.schema_violations(instance, validator))
        findings.extend(f"{prefix}: {f}" for f in find_name_mismatch(instance, skill_dir))
        findings.extend(f"{prefix}: {f}" for f in find_skill_dependency_drift(instance, skills_dir))
        findings.extend(f"{prefix}: {f}" for f in find_deprecated_replacement_drift(instance, skills_dir))

        deps = _spec_of(instance).get("skillDependencies")
        requires = deps.get("requires") if isinstance(deps, dict) else None
        graph[prefix] = [r for r in requires if isinstance(r, str)] if isinstance(requires, list) else []

    cycle = find_requires_cycle(graph)
    if cycle is not None:
        findings.append(f"requires-acyclicity: requires cycle found: {' -> '.join(cycle)}")

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

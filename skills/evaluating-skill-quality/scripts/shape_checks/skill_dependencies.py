"""spec.skillDependencies well-formedness and resolution checks."""

from __future__ import annotations

from pathlib import Path
from typing import TypeGuard

import jsonschema

from shape_checks.constants import SKILL_DEPENDENCY_SUBKEYS, CheckResult
from shape_checks.links_portability import _resolves_to_sibling_skill
from shape_checks.schema import _errors_under, _join_schema_errors


def _valid_skill_dependency_list(value: object) -> TypeGuard[list[str]]:
    """Whether ``value`` is a valid requires/relatedTo list: a list of
    non-empty strings. Retained (not schema-delegated) purely as a
    best-effort accessor for ``skill-dependencies-resolve``, a cross-file
    RETAIN check the schema cannot itself express -- it needs *some*
    usable list to check dangling references against even when
    ``skill-dependencies-well-formed`` (schema-backed) has already failed
    the field overall."""
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _skill_dependency_well_formed_result(
    deps: object, well_formed_errors: list[jsonschema.exceptions.ValidationError], well_formed_rule: str
) -> CheckResult:
    """The ``skill-dependencies-well-formed`` CheckResult, once
    ``spec.skillDependencies`` is confirmed declared."""
    if well_formed_errors:
        return CheckResult(
            "skill-dependencies-well-formed", False, well_formed_rule, _join_schema_errors(well_formed_errors)
        )
    declared = [k for k in SKILL_DEPENDENCY_SUBKEYS if isinstance(deps, dict) and k in deps]
    evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
    return CheckResult("skill-dependencies-well-formed", True, well_formed_rule, evidence)


def _skill_dependency_resolve_result(deps: object, skill_dir: Path, resolve_rule: str) -> tuple[CheckResult, list[str]]:
    """The ``skill-dependencies-resolve`` CheckResult -- also returns the
    already-validated ``requires`` list, which the caller's own
    requires-portability-compatible check needs next."""
    if not isinstance(deps, dict):
        return CheckResult("skill-dependencies-resolve", True, resolve_rule, "nothing to check (not a mapping)"), []
    requires_raw = deps.get("requires")
    requires = requires_raw if _valid_skill_dependency_list(requires_raw) else []
    related_raw = deps.get("relatedTo")
    related = related_raw if _valid_skill_dependency_list(related_raw) else []
    named = list(dict.fromkeys(requires + related))
    dangling = [n for n in named if not _resolves_to_sibling_skill(n, skill_dir.parent)]
    result = CheckResult(
        "skill-dependencies-resolve",
        not dangling,
        resolve_rule,
        "all resolve" if not dangling else "dangling: " + ", ".join(dangling),
    )
    return result, requires


def _skill_dependency_portability_result(
    contradiction_errors: list[jsonschema.exceptions.ValidationError],
    requires: list[str],
    portability: object,
    contradiction_rule: str,
) -> CheckResult:
    """The ``requires-portability-compatible`` CheckResult."""
    if contradiction_errors:
        return CheckResult(
            "requires-portability-compatible", False, contradiction_rule, _join_schema_errors(contradiction_errors)
        )
    contradiction = bool(requires) and portability == "Portable"
    return CheckResult(
        "requires-portability-compatible",
        not contradiction,
        contradiction_rule,
        "ok" if not contradiction else f"non-empty requires with portability={portability!r}",
    )


def _skill_dependency_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    schema_errors: list[jsonschema.exceptions.ValidationError],
    skill_dir: Path,
    portability: object,
) -> list[CheckResult]:
    """The three spec.skillDependencies checks (Sub-project D):
    ``skill-dependencies-well-formed`` (shape, schema-backed, issue #758),
    ``skill-dependencies-resolve`` (every named sibling exists -- a
    cross-file RETAIN check no schema instance can itself express), and
    ``requires-portability-compatible`` (a non-empty ``requires`` cannot
    coexist with ``spec.portability: Portable``, also schema-backed via
    the schema's own conditional ``allOf``).

    ``skill-dependencies-well-formed``'s own schema errors and
    ``requires-portability-compatible``'s both report at paths under
    ``spec.skillDependencies`` -- distinguished by whether the violating
    error's own schema path passes through the schema's ``allOf`` keyword:
    only the cross-field contradiction rule lives inside that ``allOf``,
    so any other schema error at this field belongs to
    ``skill-dependencies-well-formed`` instead.
    """
    well_formed_rule = (
        "spec.skillDependencies, if present, is a mapping "
        "with only requires/relatedTo keys, each -- if "
        "present -- a list of non-empty strings"
    )
    resolve_rule = (
        "every name in spec.skillDependencies.requires/relatedTo resolves to an existing sibling skill directory"
    )
    contradiction_rule = "a non-empty spec.skillDependencies.requires is incompatible with spec.portability: Portable"

    if not spec_is_mapping:
        evidence = f"spec is not a mapping: {spec_raw!r}"
        return [
            CheckResult("skill-dependencies-well-formed", False, well_formed_rule, evidence),
            CheckResult("skill-dependencies-resolve", True, resolve_rule, "nothing to check (spec is not a mapping)"),
            CheckResult(
                "requires-portability-compatible", True, contradiction_rule, "nothing to check (spec is not a mapping)"
            ),
        ]

    if "skillDependencies" not in spec:
        return [
            CheckResult("skill-dependencies-well-formed", True, well_formed_rule, "not declared (optional)"),
            CheckResult("skill-dependencies-resolve", True, resolve_rule, "not declared (optional)"),
            CheckResult("requires-portability-compatible", True, contradiction_rule, "not declared (optional)"),
        ]

    deps = spec.get("skillDependencies")
    deps_errors = _errors_under(schema_errors, "spec", "skillDependencies")
    well_formed_errors = [e for e in deps_errors if "allOf" not in e.absolute_schema_path]
    contradiction_errors = [e for e in deps_errors if "allOf" in e.absolute_schema_path]

    resolve_result, requires = _skill_dependency_resolve_result(deps, skill_dir, resolve_rule)
    return [
        _skill_dependency_well_formed_result(deps, well_formed_errors, well_formed_rule),
        resolve_result,
        _skill_dependency_portability_result(contradiction_errors, requires, portability, contradiction_rule),
    ]

"""spec.skillDependencies well-formedness and resolution checks."""

from __future__ import annotations

from pathlib import Path

from shape_checks.constants import SKILL_DEPENDENCY_SUBKEYS, CheckResult
from shape_checks.links_portability import _resolves_to_sibling_skill


def _valid_skill_dependency_list(value: object) -> bool:
    """Whether ``value`` is a valid requires/relatedTo list: a list of
    non-empty strings. Unlike spec.references, an empty list is valid here
    -- most skills' spec.skillDependencies.requires is expected to be
    empty (see the design spec's Sub-project D rationale)."""
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _skill_dependency_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    malformed_items: list[str],
    unknown_keys: list[str],
    skill_dir: Path,
    portability: object,
) -> list[CheckResult]:
    """The three spec.skillDependencies checks (Sub-project D):
    ``skill-dependencies-well-formed`` (shape), ``skill-dependencies-resolve``
    (every named sibling exists -- the dangling-reference gate), and
    ``requires-portability-compatible`` (a non-empty ``requires`` cannot
    coexist with ``spec.portability: Portable`` -- a portable skill cannot
    hard-depend on a sibling that does not travel with it).

    Mirrors the spec.references cascade in ``check_shape``: shape is
    checked first, since a badly-shaped field has nothing sensible to
    resolve or contradict against -- in every early-return branch below,
    ``skill-dependencies-resolve`` and ``requires-portability-compatible``
    report "nothing to check" rather than silently passing on data that was
    never actually a list.
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
    # deps is None here means the key was present with a blank (YAML null)
    # value, not absent -- distinct from the "not in spec" case above.
    # isinstance(None, dict) is already False, so the
    # existing "not a mapping" branch below fails it correctly without
    # further special-casing.
    if not isinstance(deps, dict):
        evidence = f"not a mapping: {deps!r}"
        return [
            CheckResult("skill-dependencies-well-formed", False, well_formed_rule, evidence),
            CheckResult("skill-dependencies-resolve", True, resolve_rule, "nothing to check (not a mapping)"),
            CheckResult(
                "requires-portability-compatible", True, contradiction_rule, "nothing to check (not a mapping)"
            ),
        ]

    results: list[CheckResult] = []
    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: {unknown_keys[0]!r}")
    if malformed_items:
        count = len(malformed_items)
        problems.append(f"{count} malformed entr{'y' if count == 1 else 'ies'}: {malformed_items[0]!r}")
    for key in SKILL_DEPENDENCY_SUBKEYS:
        if key in deps and not _valid_skill_dependency_list(deps[key]):
            problems.append(f"{key} is not a list of non-empty strings: {deps[key]!r}")

    if problems:
        results.append(CheckResult("skill-dependencies-well-formed", False, well_formed_rule, "; ".join(problems)))
    else:
        declared = [k for k in SKILL_DEPENDENCY_SUBKEYS if k in deps]
        evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
        results.append(CheckResult("skill-dependencies-well-formed", True, well_formed_rule, evidence))

    requires = deps.get("requires")
    requires = requires if _valid_skill_dependency_list(requires) else []
    related = deps.get("relatedTo")
    related = related if _valid_skill_dependency_list(related) else []
    named = list(dict.fromkeys(requires + related))
    dangling = [n for n in named if not _resolves_to_sibling_skill(n, skill_dir.parent)]
    results.append(
        CheckResult(
            "skill-dependencies-resolve",
            not dangling,
            resolve_rule,
            "all resolve" if not dangling else "dangling: " + ", ".join(dangling),
        )
    )

    contradiction = bool(requires) and portability == "Portable"
    results.append(
        CheckResult(
            "requires-portability-compatible",
            not contradiction,
            contradiction_rule,
            "ok" if not contradiction else f"non-empty requires with portability={portability!r}",
        )
    )

    return results

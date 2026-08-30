"""spec.executionRequirements well-formedness checks."""

from __future__ import annotations

import jsonschema

from shape_checks.constants import (
    EXEC_REQ_NETWORK_SUBKEYS,
    EXEC_REQ_TOOLS_SUBKEYS,
    CheckResult,
)
from shape_checks.schema import _errors_under, _join_schema_errors


def _execution_requirements_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    schema_errors: list[jsonschema.exceptions.ValidationError],
) -> list[CheckResult]:
    """The one spec.executionRequirements check landed so far:
    ``execution-requirements-well-formed`` (schema-backed, issue #758).

    Unlike spec.skillDependencies or spec.lifecycle, this field has no
    dangling-reference or cross-field CheckResult of its own -- tools'
    read/write/shell entries are free-form capability tags, not names that
    resolve against sibling skill directories, and network.mode/domains'
    own cross-field rule (domains non-empty iff mode is allowlist) is
    folded into this same well-formed check by the schema itself (its own
    nested ``allOf``/``if``/``then`` inside ``executionRequirementsNetwork``),
    not split into a separate CheckResult the way
    requires-portability-compatible is. packages' own allowlist-membership
    resolution (whether a declared package name is one gitapex permits at
    all) is not part of this check: it is enforced entirely outside this
    portable script, by a repository-owned CI gate
    (``.github/scripts/gitapex_gate_dependency_allowlist.py``) that never
    produces a CheckResult here. This function validates only
    executionRequirements' own internal SHAPE.
    """
    well_formed_rule = (
        "spec.executionRequirements, if present, is a "
        "mapping with only the tools/packages/network keys; "
        "tools, if present, is a mapping with only "
        "read/write/shell keys, each -- if present -- a list "
        "of non-empty strings; packages, if present, is a "
        "mapping keyed by free-form ecosystem identifiers "
        "(matching ^[a-z][a-z0-9-]*$), each value -- if "
        "present -- a list of non-empty strings; network, if "
        "present, is a mapping with only mode (a "
        "disabled/allowlist/unrestricted enum, required when "
        "network is declared) and domains (a list of "
        "non-empty strings, non-empty iff mode is allowlist)"
    )

    if not spec_is_mapping:
        return [
            CheckResult(
                "execution-requirements-well-formed", False, well_formed_rule, f"spec is not a mapping: {spec_raw!r}"
            )
        ]

    execution_requirements = spec.get("executionRequirements")
    if "executionRequirements" not in spec:
        return [CheckResult("execution-requirements-well-formed", True, well_formed_rule, "not declared (optional)")]

    errors = _errors_under(schema_errors, "spec", "executionRequirements")
    if errors:
        return [CheckResult("execution-requirements-well-formed", False, well_formed_rule, _join_schema_errors(errors))]

    tools = execution_requirements.get("tools") if isinstance(execution_requirements, dict) else None
    packages = execution_requirements.get("packages") if isinstance(execution_requirements, dict) else None
    network = execution_requirements.get("network") if isinstance(execution_requirements, dict) else None
    declared = [f"tools.{k}" for k in EXEC_REQ_TOOLS_SUBKEYS if isinstance(tools, dict) and k in tools]
    # packages has no fixed subkey tuple -- walk the parsed mapping's own
    # keys instead, in file order (Python dict iteration order is
    # insertion order, which here is parse order).
    declared += [f"packages.{k}" for k in packages] if isinstance(packages, dict) else []
    declared += [f"network.{k}" for k in EXEC_REQ_NETWORK_SUBKEYS if isinstance(network, dict) and k in network]
    evidence = ", ".join(declared) + " declared" if declared else "no keys declared"
    return [CheckResult("execution-requirements-well-formed", True, well_formed_rule, evidence)]

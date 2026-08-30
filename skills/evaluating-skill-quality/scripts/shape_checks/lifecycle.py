"""spec.lifecycle well-formedness checks (experimental/deprecated/stable/
renamedFrom)."""

from __future__ import annotations

from pathlib import Path

import jsonschema

from shape_checks.constants import LIFECYCLE_SUBKEYS, CheckResult
from shape_checks.links_portability import _resolves_to_sibling_skill
from shape_checks.schema import _errors_under, _join_schema_errors


def _lifecycle_deprecated_replacement_result(
    lifecycle: dict[str, object], skill_dir: Path, resolve_rule: str
) -> CheckResult:
    """The ``lifecycle-deprecated-replacement-resolves`` CheckResult."""
    deprecated = lifecycle.get("deprecated")
    replacement = deprecated.get("replacement") if isinstance(deprecated, dict) else None
    if isinstance(replacement, str) and replacement.strip():
        exists = _resolves_to_sibling_skill(replacement, skill_dir.parent)
        return CheckResult(
            "lifecycle-deprecated-replacement-resolves",
            exists,
            resolve_rule,
            "resolves" if exists else f"dangling: {replacement!r}",
        )
    return CheckResult(
        "lifecycle-deprecated-replacement-resolves",
        True,
        resolve_rule,
        "nothing to check (replacement missing or invalid)",
    )


def _lifecycle_well_formed_result(
    lifecycle: object, well_formed_errors: list[jsonschema.exceptions.ValidationError], well_formed_rule: str
) -> CheckResult:
    """The ``lifecycle-well-formed`` CheckResult, once ``spec.lifecycle``
    is confirmed declared."""
    if well_formed_errors:
        return CheckResult("lifecycle-well-formed", False, well_formed_rule, _join_schema_errors(well_formed_errors))
    declared = [k for k in LIFECYCLE_SUBKEYS if isinstance(lifecycle, dict) and k in lifecycle]
    if isinstance(lifecycle, dict) and "renamedFrom" in lifecycle:
        declared.append("renamedFrom")
    evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
    return CheckResult("lifecycle-well-formed", True, well_formed_rule, evidence)


def _lifecycle_contradiction_result(
    contradiction_errors: list[jsonschema.exceptions.ValidationError], contradiction_rule: str
) -> CheckResult:
    """The ``experimental-stable-compatible`` CheckResult."""
    if contradiction_errors:
        return CheckResult(
            "experimental-stable-compatible",
            False,
            contradiction_rule,
            "both experimental and stable are declared, which is a logical contradiction",
        )
    return CheckResult("experimental-stable-compatible", True, contradiction_rule, "ok")


def _lifecycle_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    schema_errors: list[jsonschema.exceptions.ValidationError],
    skill_dir: Path,
) -> list[CheckResult]:
    """The three spec.lifecycle checks: ``lifecycle-well-formed`` (shape,
    schema-backed, issue #758), ``lifecycle-deprecated-replacement-resolves``
    (the dangling-reference gate for ``deprecated.replacement`` -- a
    cross-file RETAIN check no schema instance can itself express), and
    ``experimental-stable-compatible`` (the one cross-field rule, also
    schema-backed via the schema's own ``not: {required: [...]}``
    constraint: a skill cannot be simultaneously "not yet graduated" and
    "already graduated on some date").

    ``lifecycle-well-formed``'s own schema errors and
    ``experimental-stable-compatible``'s both report at the identical
    instance path (``spec.lifecycle``) when both fire -- distinguished by
    the violating error's own ``validator`` name: only the cross-field
    rule's own schema keyword is ``"not"`` (used exactly once, for this
    one rule, in the whole bundled schema), so any other validator name at
    that path belongs to ``lifecycle-well-formed`` instead.
    """
    well_formed_rule = (
        "spec.lifecycle, if present, is a mapping with only "
        "experimental/deprecated/stable/renamedFrom keys. experimental "
        "(reason/trackingIssue required, since optional), deprecated "
        "(reason/replacement required, since/removeAfter optional), and "
        "stable (since required, compatibilityGuarantee optional) are "
        "each -- if present -- a mapping of their own recognized scalar "
        "fields; renamedFrom, if present, is a non-empty scalar string. "
        "since/removeAfter, if present, must be real YYYY-MM-DD dates"
    )
    resolve_rule = (
        "spec.lifecycle.deprecated.replacement, if a non-empty string, resolves to an existing sibling skill directory"
    )
    contradiction_rule = (
        "spec.lifecycle.experimental and spec.lifecycle.stable cannot "
        "both be present -- a skill cannot be both not-yet-graduated and "
        "already graduated"
    )

    if not spec_is_mapping:
        evidence = f"spec is not a mapping: {spec_raw!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult(
                "lifecycle-deprecated-replacement-resolves",
                True,
                resolve_rule,
                "nothing to check (spec is not a mapping)",
            ),
            CheckResult(
                "experimental-stable-compatible", True, contradiction_rule, "nothing to check (spec is not a mapping)"
            ),
        ]

    if "lifecycle" not in spec:
        return [
            CheckResult("lifecycle-well-formed", True, well_formed_rule, "not declared (optional)"),
            CheckResult("lifecycle-deprecated-replacement-resolves", True, resolve_rule, "not declared (optional)"),
            CheckResult("experimental-stable-compatible", True, contradiction_rule, "not declared (optional)"),
        ]

    lifecycle = spec.get("lifecycle")
    lifecycle_errors = _errors_under(schema_errors, "spec", "lifecycle")
    well_formed_errors = [e for e in lifecycle_errors if e.validator != "not"]
    # A "not: {required: [...]}" constraint is vacuously satisfied (so its
    # "not" is vacuously violated) whenever the instance isn't an object at
    # all -- required is only meaningful against a mapping. Only evaluate
    # the contradiction when lifecycle is actually a mapping, so a
    # wrong-type lifecycle field is reported solely by well_formed_errors.
    contradiction_errors = [e for e in lifecycle_errors if e.validator == "not"] if isinstance(lifecycle, dict) else []

    lifecycle_dict = lifecycle if isinstance(lifecycle, dict) else {}
    return [
        _lifecycle_well_formed_result(lifecycle, well_formed_errors, well_formed_rule),
        _lifecycle_deprecated_replacement_result(lifecycle_dict, skill_dir, resolve_rule),
        _lifecycle_contradiction_result(contradiction_errors, contradiction_rule),
    ]

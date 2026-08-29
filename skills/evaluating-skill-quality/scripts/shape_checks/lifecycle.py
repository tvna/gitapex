"""spec.lifecycle well-formedness checks (experimental/deprecated/stable/
renamedFrom)."""

from __future__ import annotations

import datetime
from pathlib import Path

from shape_checks.constants import (
    COMPATIBILITY_GUARANTEE_LEVELS,
    LIFECYCLE_DATE_RE,
    LIFECYCLE_ISSUE_REF_RE,
    LIFECYCLE_REQUIRED_FIELDS,
    LIFECYCLE_SUBKEYS,
    REFERENCES_ENTRY_MAX_CHARS,
    CheckResult,
)
from shape_checks.links_portability import _resolves_to_sibling_skill


def _valid_lifecycle_date(value: object) -> bool:
    """Whether ``value`` is a real calendar date in strict YYYY-MM-DD
    shape, for spec.lifecycle's since/removeAfter fields.

    Regex first (rejects any non-dashed or wrong-width shape outright),
    then ``datetime.date.fromisoformat`` (rejects a shape-valid but
    non-existent date, e.g. "2026-13-45" or "2026-02-30", that a
    regex-only check would silently accept). Gating the regex first also
    blocks ``fromisoformat``'s lenient Python 3.11+ ISO-variant parsing
    from accepting an off-shape string that happens to still be valid
    ISO 8601.
    """
    if not (isinstance(value, str) and LIFECYCLE_DATE_RE.match(value)):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_tracking_issue(value: object) -> bool:
    """Shape-only check for spec.lifecycle.experimental.trackingIssue: a
    full ``https://github.com/OWNER/REPO/issues/123`` (or ``/pull/123``)
    URL -- any owner/repo, not only this repository's own. Never resolved
    against a live GitHub API call -- this checker is offline/read-only
    by design.
    """
    return isinstance(value, str) and bool(LIFECYCLE_ISSUE_REF_RE.match(value))


def _lifecycle_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    unknown_keys: list[str],
    unknown_fields: list[str],
    skill_dir: Path,
) -> list[CheckResult]:
    """The three spec.lifecycle checks: ``lifecycle-well-formed`` (shape),
    ``lifecycle-deprecated-replacement-resolves`` (the dangling-reference
    gate for ``deprecated.replacement``, mirroring
    ``skill-dependencies-resolve``), and
    ``experimental-stable-compatible`` (the one cross-field rule: a skill
    cannot be simultaneously "not yet graduated" and "already graduated on
    some date").

    ``experimental``, ``deprecated``, and ``stable`` are independent,
    optional sub-blocks; ``renamedFrom`` is a plain scalar directly under
    ``spec.lifecycle``, never a sub-block. ``experimental`` and
    ``deprecated`` do not exclude each other (an experimental skill can
    legitimately be superseded by a different experiment) -- but
    ``experimental`` and ``stable`` are a real logical contradiction, so
    unlike the ``deprecated`` pairing, that combination is gated. Mirrors
    the ``_skill_dependency_checks`` cascade: shape is checked first,
    since a badly-shaped field has nothing sensible to resolve or
    contradict against -- every early-return branch below reports both
    ``lifecycle-deprecated-replacement-resolves`` and
    ``experimental-stable-compatible`` as "nothing to check" rather than
    silently passing on data that was never actually a mapping.
    """
    well_formed_rule = (
        "spec.lifecycle, if present, is a mapping with only "
        "experimental/deprecated/stable/renamedFrom keys. experimental "
        "(reason/trackingIssue required, since optional), deprecated "
        "(reason/replacement required, since/removeAfter optional), and "
        "stable (since required, compatibilityGuarantee optional) are "
        "each -- if present -- a mapping of their own recognized scalar "
        "fields; renamedFrom, if present, is a non-empty scalar string. "
        "since/removeAfter, if present, must be real YYYY-MM-DD dates; "
        "reason, if present, is <= "
        f"{REFERENCES_ENTRY_MAX_CHARS} chars; trackingIssue, if present, a "
        "full https://github.com/OWNER/REPO/issues/<N> (or /pull/<N>) "
        "URL; compatibilityGuarantee, if present, one of "
        f"{COMPATIBILITY_GUARANTEE_LEVELS}"
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
    # lifecycle is None here means present-but-blank (YAML null), distinct
    # from absent above -- isinstance(None, dict) is already
    # False, so the existing "not a mapping" branch below fails it.
    if not isinstance(lifecycle, dict):
        evidence = f"not a mapping: {lifecycle!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult(
                "lifecycle-deprecated-replacement-resolves", True, resolve_rule, "nothing to check (not a mapping)"
            ),
            CheckResult("experimental-stable-compatible", True, contradiction_rule, "nothing to check (not a mapping)"),
        ]

    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: {unknown_keys[0]!r}")
    if unknown_fields:
        count = len(unknown_fields)
        problems.append(f"{count} unknown field{'' if count == 1 else 's'}: {unknown_fields[0]!r}")

    sub_blocks: dict[str, dict[str, object]] = {}
    for key in LIFECYCLE_SUBKEYS:
        if key not in lifecycle:
            continue
        block = lifecycle[key]
        if not isinstance(block, dict):
            problems.append(f"{key} is not a mapping: {block!r}")
            continue
        sub_blocks[key] = block
        for field in LIFECYCLE_REQUIRED_FIELDS[key]:
            val = block.get(field)
            if not (isinstance(val, str) and val.strip()):
                problems.append(f"{key}.{field} is missing or not a non-empty string: {val!r}")
        for field in ("since", "removeAfter"):
            if field in block and not _valid_lifecycle_date(block[field]):
                problems.append(f"{key}.{field} is not a YYYY-MM-DD date: {block[field]!r}")
        reason_val = block.get("reason")
        if isinstance(reason_val, str) and len(reason_val) > REFERENCES_ENTRY_MAX_CHARS:
            problems.append(
                f"{key}.reason is {len(reason_val)} chars, over the {REFERENCES_ENTRY_MAX_CHARS}-char limit"
            )
        if key == "experimental" and "trackingIssue" in block and not _valid_tracking_issue(block["trackingIssue"]):
            problems.append(
                f"experimental.trackingIssue is not a full "
                f"https://github.com/OWNER/REPO/issues/<N> (or /pull/<N>) "
                f"URL: {block['trackingIssue']!r}"
            )
        if (
            key == "stable"
            and "compatibilityGuarantee" in block
            and block["compatibilityGuarantee"] not in COMPATIBILITY_GUARANTEE_LEVELS
        ):
            problems.append(
                f"stable.compatibilityGuarantee is not one of "
                f"{COMPATIBILITY_GUARANTEE_LEVELS}: "
                f"{block['compatibilityGuarantee']!r}"
            )

    if "renamedFrom" in lifecycle:
        renamed_from = lifecycle["renamedFrom"]
        if not (isinstance(renamed_from, str) and renamed_from.strip()):
            problems.append(f"renamedFrom is not a non-empty string: {renamed_from!r}")

    if problems:
        results = [CheckResult("lifecycle-well-formed", False, well_formed_rule, "; ".join(problems))]
    else:
        declared = [k for k in LIFECYCLE_SUBKEYS if k in sub_blocks]
        if "renamedFrom" in lifecycle:
            declared.append("renamedFrom")
        evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
        results = [CheckResult("lifecycle-well-formed", True, well_formed_rule, evidence)]

    deprecated = sub_blocks.get("deprecated")
    replacement = deprecated.get("replacement") if deprecated else None
    if isinstance(replacement, str) and replacement.strip():
        exists = _resolves_to_sibling_skill(replacement, skill_dir.parent)
        results.append(
            CheckResult(
                "lifecycle-deprecated-replacement-resolves",
                exists,
                resolve_rule,
                "resolves" if exists else f"dangling: {replacement!r}",
            )
        )
    else:
        results.append(
            CheckResult(
                "lifecycle-deprecated-replacement-resolves",
                True,
                resolve_rule,
                "nothing to check (replacement missing or invalid)",
            )
        )

    contradiction = "experimental" in sub_blocks and "stable" in sub_blocks
    results.append(
        CheckResult(
            "experimental-stable-compatible",
            not contradiction,
            contradiction_rule,
            "ok" if not contradiction else "both experimental and stable are present",
        )
    )
    return results

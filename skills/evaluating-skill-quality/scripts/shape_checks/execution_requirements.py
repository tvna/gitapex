"""spec.executionRequirements well-formedness checks."""

from __future__ import annotations

from shape_checks.constants import (
    EXEC_REQ_NETWORK_MODES,
    EXEC_REQ_NETWORK_SUBKEYS,
    EXEC_REQ_TOOLS_SUBKEYS,
    CheckResult,
)


def _valid_execution_requirements_tools_list(value: object) -> bool:
    """Whether ``value`` is a valid tools.read/write/shell list: a list of
    non-empty strings. Mirrors ``_valid_skill_dependency_list`` -- an empty
    list is valid here too, since it is a deliberate "zero tools of this
    kind needed" statement, distinct from the subkey being absent
    entirely."""
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _execution_requirements_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    unknown_keys: list[str],
    unknown_tools_keys: list[str],
    malformed_tools_items: list[str],
    unknown_packages_keys: list[str],
    malformed_packages_items: list[str],
    unknown_network_keys: list[str],
    malformed_network_items: list[str],
) -> list[CheckResult]:
    """The one spec.executionRequirements check landed so far:
    ``execution-requirements-well-formed``.

    Mirrors ``_skill_dependency_checks``'s early-return ladder (spec not a
    mapping / not declared / not a mapping) before real validation, and its
    problem-accumulation-then-single-CheckResult pattern. Unlike
    spec.skillDependencies or spec.lifecycle, this field has only three
    recognized top-level subkeys so far, ``tools``, ``packages``, and
    ``network`` (issue #845; #1115's own ADR follow-up added ``packages``)
    -- the remaining categories (filesystem, mcp, credentials, browser,
    externalServices, context) are deferred; any key here other than
    ``tools``/``packages``/``network`` fails closed via ``unknown_keys``
    rather than being silently accepted as reserved space. There is no
    dangling-reference or cross-field check the way
    spec.skillDependencies/spec.lifecycle have one each -- tools'
    read/write/shell entries are free-form capability tags, not names that
    resolve against sibling skill directories, and no rule ties this field
    to portability/capabilityAssumption/lifecycle. network.mode/domains
    DO carry one cross-field rule of their own (domains non-empty iff mode
    is allowlist), checked below the same way requires-portability-
    compatible is checked elsewhere in this file, just folded into this
    same well-formed check rather than earning its own separate
    CheckResult -- tools has no analogous cross-subkey rule to justify the
    same split. packages' own allowlist-membership resolution (whether a
    declared package name is one gitapex permits at all) is not part of
    this check: it is enforced entirely outside this portable script, by
    a repository-owned CI gate
    (``.github/scripts/gitapex_gate_dependency_allowlist.py``) that never
    produces a CheckResult here. This function validates only packages'
    own internal SHAPE, the same as tools and network.
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

    if "executionRequirements" not in spec:
        return [CheckResult("execution-requirements-well-formed", True, well_formed_rule, "not declared (optional)")]

    execution_requirements = spec.get("executionRequirements")
    # None here means present-but-blank (YAML null), distinct from absent
    # above -- isinstance(None, dict) is already False, so
    # the existing "not a mapping" branch below fails it correctly.
    if not isinstance(execution_requirements, dict):
        return [
            CheckResult(
                "execution-requirements-well-formed",
                False,
                well_formed_rule,
                f"not a mapping: {execution_requirements!r}",
            )
        ]

    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: {unknown_keys[0]!r}")

    tools_present = "tools" in execution_requirements
    tools = execution_requirements.get("tools")
    # tools_present with tools is None means present-but-blank (YAML
    # null), distinct from tools being absent entirely -- both must fail
    # closed here rather than silently passing as an empty mapping.
    if tools_present and not isinstance(tools, dict):
        problems.append(f"tools is not a mapping: {tools!r}")
    elif isinstance(tools, dict):
        if unknown_tools_keys:
            count = len(unknown_tools_keys)
            problems.append(f"{count} unknown tools key{'' if count == 1 else 's'}: {unknown_tools_keys[0]!r}")
        if malformed_tools_items:
            count = len(malformed_tools_items)
            problems.append(f"{count} malformed tools entr{'y' if count == 1 else 'ies'}: {malformed_tools_items[0]!r}")
        for key in EXEC_REQ_TOOLS_SUBKEYS:
            if key in tools and not _valid_execution_requirements_tools_list(tools[key]):
                problems.append(f"tools.{key} is not a list of non-empty strings: {tools[key]!r}")

    packages_present = "packages" in execution_requirements
    packages = execution_requirements.get("packages")
    # Same present-but-null-vs-absent distinction tools' own branch above
    # already draws.
    if packages_present and not isinstance(packages, dict):
        problems.append(f"packages is not a mapping: {packages!r}")
    elif isinstance(packages, dict):
        if unknown_packages_keys:
            count = len(unknown_packages_keys)
            problems.append(f"{count} unknown packages key{'' if count == 1 else 's'}: {unknown_packages_keys[0]!r}")
        if malformed_packages_items:
            count = len(malformed_packages_items)
            problems.append(
                f"{count} malformed packages entr{'y' if count == 1 else 'ies'}: {malformed_packages_items[0]!r}"
            )
        # packages' own subkeys are free-form ecosystem identifiers, not a
        # fixed tuple like EXEC_REQ_TOOLS_SUBKEYS -- iterate the parsed
        # mapping's own keys (already guaranteed to match
        # EXEC_REQ_PACKAGES_KEY_RE by the parser; a non-matching key never
        # reaches this dict at all, landing in unknown_packages_keys
        # instead, per _parse_manifest) rather than a fixed vocabulary, so
        # only each key's own VALUE shape remains to check here.
        for key in packages:
            if not _valid_execution_requirements_tools_list(packages[key]):
                problems.append(f"packages.{key} is not a list of non-empty strings: {packages[key]!r}")
        # KNOWN, DISCLOSED GAP (not fixed here): $defs.packageList in
        # skill-metadata.schema.json declares "uniqueItems": true, but
        # this checker does not enforce it -- a package name repeated
        # twice under the same ecosystem (e.g. "pip: [pyyaml, pyyaml]")
        # currently still passes execution-requirements-well-formed.
        # Fail-open only in the sense of "does not additionally flag a
        # redundant duplicate as its own defect"; it is not an
        # allowlist-bypass gap (the CI gate that resolves allowlist
        # membership dedupes by normalized name before checking, so a
        # duplicate cannot inflate or hide an offender there). Left
        # unimplemented rather than folded into
        # _valid_execution_requirements_tools_list, which tools.read/
        # write/shell and network.domains also share -- enforcing
        # uniqueItems there too is a broader, separate change this
        # finding did not ask for and risks failing existing skills that
        # currently rely on tolerated duplicates in those other lists.

    network_present = "network" in execution_requirements
    network = execution_requirements.get("network")
    # Same present-but-null-vs-absent distinction tools' own branch above
    # already draws.
    if network_present and not isinstance(network, dict):
        problems.append(f"network is not a mapping: {network!r}")
    elif isinstance(network, dict):
        if unknown_network_keys:
            count = len(unknown_network_keys)
            problems.append(f"{count} unknown network key{'' if count == 1 else 's'}: {unknown_network_keys[0]!r}")
        if malformed_network_items:
            count = len(malformed_network_items)
            problems.append(
                f"{count} malformed network entr{'y' if count == 1 else 'ies'}: {malformed_network_items[0]!r}"
            )
        mode_present = "mode" in network
        mode = network.get("mode")
        if not mode_present:
            problems.append("network.mode is required when network is declared")
        elif not (isinstance(mode, str) and mode in EXEC_REQ_NETWORK_MODES):
            problems.append(f"network.mode is not one of {EXEC_REQ_NETWORK_MODES}: {mode!r}")
        domains_present = "domains" in network
        domains = network.get("domains")
        # Reuses _valid_execution_requirements_tools_list: the same "list
        # of non-empty strings" shape tools.read/write/shell already
        # validate, generic despite its tools-scoped name.
        if domains_present and not _valid_execution_requirements_tools_list(domains):
            problems.append(f"network.domains is not a list of non-empty strings: {domains!r}")
        elif mode == "allowlist" and not (isinstance(domains, list) and domains):
            problems.append("network.domains must be a non-empty list when network.mode is allowlist")
        elif mode in ("disabled", "unrestricted") and isinstance(domains, list) and domains:
            problems.append(f"network.domains must be empty when network.mode is {mode!r}")

    if problems:
        return [CheckResult("execution-requirements-well-formed", False, well_formed_rule, "; ".join(problems))]

    declared = [f"tools.{k}" for k in EXEC_REQ_TOOLS_SUBKEYS if k in tools] if isinstance(tools, dict) else []
    # packages has no fixed subkey tuple to iterate (see the loop above) --
    # walk the parsed mapping's own keys instead, in file order (Python
    # dict iteration order is insertion order, which here is parse order).
    declared += [f"packages.{k}" for k in packages] if isinstance(packages, dict) else []
    declared += [f"network.{k}" for k in EXEC_REQ_NETWORK_SUBKEYS if k in network] if isinstance(network, dict) else []
    evidence = ", ".join(declared) + " declared" if declared else "no keys declared"
    return [CheckResult("execution-requirements-well-formed", True, well_formed_rule, evidence)]

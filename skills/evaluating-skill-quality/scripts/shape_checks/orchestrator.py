"""``check_shape()``'s own extracted per-section helpers (issue #1330 ACM
row 2) -- the SKILL.md-level and metadata-sidecar-envelope checks that
don't yet have a dedicated ``shape_checks/`` module of their own, split
out of what used to be one large orchestrating function in
``gitapex_check_skill_shape.py``.

Pure structural extraction: each function below owns one cohesive slice
of what ``gitapex_check_skill_shape.check_shape`` used to compute inline
-- the exact same CheckResult values/evidence/order, copy-pasted
verbatim out of that function's own body. Zero detection-logic change; the
load-bearing proof was ``verify_shape_check_output_diff.py``, a one-time
differential oracle pinned to the pre-split commit (issue #1330's own PR
#1450, merge commit aa33e6f7) -- retired by issue #577 once its job was
done, since its pinned-commit design could never pass again after any
later, legitimate detection-logic change. See PR #1450's own merged diff
for the original proof; `git show aa33e6f7:skills/evaluating-skill-quality/scripts/verify_shape_check_output_diff.py`
recovers the retired script.
"""

from __future__ import annotations

from pathlib import Path

import jsonschema

from shape_checks.citation_checks import _external_citation_declaration_offenders
from shape_checks.constants import (
    BODY_MAX_LINES,
    CAPABILITY_ASSUMPTIONS,
    DEPENDENCY_POLICY_LEVELS,
    DESCRIPTION_MAX_CHARS,
    EXPECTED_API_VERSION,
    EXPECTED_KIND,
    EXTERNAL_CITATION_ROLES,
    NAME_MAX_CHARS,
    NAME_RE,
    PORTABILITY_LEVELS,
    REFERENCES_ENTRY_MAX_CHARS,
    RESERVED_NAME_WORDS,
    SIDECAR_RELATIVE_PATH,
    TOC_MIN_LINES,
    TOC_RE,
    CheckResult,
)
from shape_checks.field_checks import _length_check, _no_xml_check, _yaml_plain_scalar_safety_check
from shape_checks.frontmatter import FrontmatterParse
from shape_checks.links_portability import (
    _body_after_frontmatter,
    _broken_anchor_targets,
    _heading_slugs,
    _is_ignorable,
    _out_of_skill_link_targets,
)
from shape_checks.schema import _errors_under, _join_schema_errors


def _skill_md_read_result(skill_md: Path) -> tuple[str | None, CheckResult]:
    """SKILL.md's own initial read step, extracted verbatim from
    ``check_shape``: raises ``FileNotFoundError`` (mirroring
    ``check_shape``'s pre-existing contract -- ``main()`` already
    pre-checks ``skill_md.is_file()`` before ever calling ``check_shape()``
    and returns exit 2 for that case), returns ``(None, <failed
    skill-md-readable CheckResult>)`` for any other read failure
    (``OSError``/``UnicodeDecodeError``), or ``(text, <passed
    skill-md-readable CheckResult>)`` on success."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except FileNotFoundError:
        # A SKILL.md that does not exist at all is a different, pre-existing
        # contract this fix does not change: main() already pre-checks
        # ``skill_md.is_file()`` before ever calling check_shape() and
        # returns exit 2 for that case (see test_directory_without_skill_md_
        # returns_2), the same "missing" vs. "present but corrupt" split the
        # sidecar's own is_file() check in check_shape draws. Re-raising
        # here (rather than folding "missing" into the "present but
        # unreadable" evidence below) keeps that split intact for any
        # other direct caller too.
        raise
    except (OSError, UnicodeDecodeError) as exc:
        return None, CheckResult(
            "skill-md-readable", False, "SKILL.md is readable as UTF-8 text", f"unreadable: {type(exc).__name__}"
        )
    # Always emitted (pass or fail), matching every other check in this
    # module -- not only on the failure path above -- so a caller scanning
    # results for this name never has to treat its absence as a third,
    # ambiguous state.
    return text, CheckResult("skill-md-readable", True, "SKILL.md is readable as UTF-8 text", "present")


def _description_field_checks(fields: dict[str, str], frontmatter: FrontmatterParse) -> list[CheckResult]:
    """The ``description`` field's own checks, extracted verbatim from
    ``check_shape``."""
    results: list[CheckResult] = []
    description = fields.get("description", "")
    if not description:
        results.append(
            CheckResult("description-present", False, "description present and non-empty", "missing or empty")
        )
    else:
        results.append(CheckResult("description-present", True, "description present and non-empty", "present"))
        results.append(_no_xml_check("description", description))
        results.append(_length_check("description", description, DESCRIPTION_MAX_CHARS))
        results.append(
            _yaml_plain_scalar_safety_check("description", description, "description" in frontmatter.plain_fields)
        )
    return results


def _name_field_checks(fields: dict[str, str]) -> list[CheckResult]:
    """The ``name`` field's own checks, extracted verbatim from
    ``check_shape``."""
    results: list[CheckResult] = []
    name = fields.get("name")
    if name:
        results.append(
            CheckResult("name-pattern", bool(NAME_RE.match(name)), "name is lowercase-hyphenated", repr(name))
        )
        results.append(_length_check("name", name, NAME_MAX_CHARS))
        results.append(_no_xml_check("name", name))
        lname = name.lower()
        reserved_hit = any(word in lname for word in RESERVED_NAME_WORDS)
        results.append(
            CheckResult(
                "name-not-reserved",
                not reserved_hit,
                f"name contains no reserved word {RESERVED_NAME_WORDS}",
                repr(name),
            )
        )
    return results


def _body_length_result(text: str) -> CheckResult:
    """The ``body-length`` check, extracted verbatim from ``check_shape``."""
    body_lines = len(text.splitlines())
    return CheckResult(
        "body-length",
        body_lines <= BODY_MAX_LINES,
        f"SKILL.md body <= {BODY_MAX_LINES} lines",
        f"{body_lines} lines",
    )


def _sidecar_unreadable_results(evidence: str) -> list[CheckResult]:
    """Emitted when the sidecar exists but could not be read or parsed at
    all (``manifest is None`` in ``check_shape``), extracted verbatim --
    every sidecar-derived check FAILs with the same evidence string."""
    return [
        CheckResult("manifest-parsable", False, f"{SIDECAR_RELATIVE_PATH} is valid YAML", evidence),
        CheckResult(
            "manifest-envelope",
            False,
            f"apiVersion is {EXPECTED_API_VERSION} and kind is {EXPECTED_KIND}",
            evidence,
        ),
        CheckResult("metadata-name-matches-dir", False, "metadata.name equals the skill directory name", evidence),
        CheckResult("portability-declared", False, f"spec.portability is one of {PORTABILITY_LEVELS}", evidence),
        CheckResult(
            "capability-assumption-declared",
            False,
            f"spec.capabilityAssumption is one of {CAPABILITY_ASSUMPTIONS}",
            evidence,
        ),
        CheckResult(
            "dependency-policy-declared",
            False,
            f"spec.dependencyPolicy, if present, is one of {DEPENDENCY_POLICY_LEVELS}",
            evidence,
        ),
        CheckResult(
            "references-well-formed",
            False,
            "spec.references, if present, is a non-empty list of non-empty strings",
            evidence,
        ),
        CheckResult(
            "references-grammar",
            False,
            'spec.references, if present, has each entry shaped "<kind> | <anchor> | <summary>[ | <outcome>]"',
            evidence,
        ),
        CheckResult(
            "external-citations-well-formed",
            False,
            "spec.externalCitations, if present, is a non-empty list of "
            "item mappings, each with path/role (role one of "
            f"{EXTERNAL_CITATION_ROLES}) and no unrecognized key",
            evidence,
        ),
        CheckResult(
            "external-citations-resolve",
            False,
            "every spec.externalCitations path literally appears somewhere "
            "in SKILL.md or references/*.md (no stale declaration)",
            evidence,
        ),
        CheckResult(
            "skill-dependencies-well-formed",
            False,
            "spec.skillDependencies, if present, is a mapping with only "
            "requires/relatedTo keys, each -- if present -- a list of "
            "non-empty strings",
            evidence,
        ),
        CheckResult(
            "skill-dependencies-resolve",
            False,
            "every name in spec.skillDependencies.requires/relatedTo resolves to an existing sibling skill directory",
            evidence,
        ),
        CheckResult(
            "requires-portability-compatible",
            False,
            "a non-empty spec.skillDependencies.requires is incompatible with spec.portability: Portable",
            evidence,
        ),
        CheckResult(
            "lifecycle-well-formed",
            False,
            "spec.lifecycle, if present, is a mapping with only "
            "experimental/deprecated/stable/renamedFrom keys, each "
            "block sub-key (experimental/deprecated/stable) -- if "
            "present -- a mapping of its own recognized scalar fields "
            "with required fields non-empty and since/removeAfter, if "
            "present, real YYYY-MM-DD dates, and renamedFrom, if "
            "present, a non-empty scalar string",
            evidence,
        ),
        CheckResult(
            "lifecycle-deprecated-replacement-resolves",
            False,
            "spec.lifecycle.deprecated.replacement, if a non-empty "
            "string, resolves to an existing sibling skill directory",
            evidence,
        ),
        CheckResult(
            "experimental-stable-compatible",
            False,
            "spec.lifecycle.experimental and spec.lifecycle.stable "
            "cannot both be present -- a skill cannot be both "
            "not-yet-graduated and already graduated",
            evidence,
        ),
        CheckResult(
            "execution-requirements-well-formed",
            False,
            "spec.executionRequirements, if present, is a mapping with "
            "only the tools/packages/network keys; tools, if present, "
            "is a mapping with only read/write/shell keys, each -- if "
            "present -- a list of non-empty strings; packages, if "
            "present, is a mapping keyed by free-form ecosystem "
            "identifiers, each value -- if present -- a list of "
            "non-empty strings; network, if present, is a mapping "
            "with only mode (a disabled/allowlist/unrestricted enum) "
            "and domains (a list of non-empty strings, non-empty "
            "only when mode is allowlist)",
            evidence,
        ),
    ]


def _dependency_policy_declared_result(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    schema_errors: list[jsonschema.exceptions.ValidationError],
) -> CheckResult:
    """The ``dependency-policy-declared`` check (schema-backed, issue
    #758)."""
    dependency_policy_declared_rule = f"spec.dependencyPolicy, if present, is one of {DEPENDENCY_POLICY_LEVELS}"
    if not spec_is_mapping:
        # Same precondition failure portability-declared/
        # capability-assumption-declared already report in check_shape --
        # "not declared (optional)" would misreport a non-mapping
        # spec as the ordinary optional-and-absent case, mirroring
        # references-well-formed's own guard below.
        return CheckResult(
            "dependency-policy-declared",
            False,
            dependency_policy_declared_rule,
            f"spec is not a mapping: {spec_raw!r}",
        )
    if "dependencyPolicy" not in spec:
        return CheckResult(
            "dependency-policy-declared",
            True,
            dependency_policy_declared_rule,
            "not declared (optional, treated as StdlibOnly-equivalent)",
        )
    errors = _errors_under(schema_errors, "spec", "dependencyPolicy")
    if errors:
        return CheckResult(
            "dependency-policy-declared", False, dependency_policy_declared_rule, _join_schema_errors(errors)
        )
    return CheckResult(
        "dependency-policy-declared", True, dependency_policy_declared_rule, repr(spec.get("dependencyPolicy"))
    )


def _references_well_formed_result(
    spec_is_mapping: bool,
    spec_raw: object,
    schema_errors: list[jsonschema.exceptions.ValidationError],
    references: object,
) -> CheckResult:
    """The ``references-well-formed`` check (schema-backed, issue #758)."""
    references_well_formed_rule = (
        "spec.references, if present, is a non-empty list of "
        "item mappings, each with kind/anchor/summary (and no "
        f"unrecognized key), summary <= {REFERENCES_ENTRY_MAX_CHARS} "
        "chars"
    )
    if not spec_is_mapping:
        # spec itself failed to parse as a mapping (e.g. "spec:
        # some-scalar"), the same precondition failure
        # portability-declared/capability-assumption-declared
        # already report in check_shape -- "not declared" would
        # misreport this as the ordinary optional-and-absent case.
        return CheckResult(
            "references-well-formed", False, references_well_formed_rule, f"spec is not a mapping: {spec_raw!r}"
        )
    errors = _errors_under(schema_errors, "spec", "references")
    if errors:
        return CheckResult("references-well-formed", False, references_well_formed_rule, _join_schema_errors(errors))
    if references is None:
        return CheckResult("references-well-formed", True, references_well_formed_rule, "not declared (optional)")
    ref_count = len(references) if isinstance(references, list) else 0
    ref_noun = "entry" if ref_count == 1 else "entries"
    return CheckResult("references-well-formed", True, references_well_formed_rule, f"{ref_count} {ref_noun}")


def _references_citation_source(references: object) -> tuple[str, str] | None:
    """The ``for r in references: ...`` loop feeding
    ``sidecar_citation_sources``, extracted verbatim from ``check_shape``:
    returns the one (source-label, joined-text) tuple it used to append,
    or None when ``references`` is not a non-empty list (nothing to
    append)."""
    if not (isinstance(references, list) and references):
        return None
    ref_texts: list[str] = []
    for r in references:
        if not isinstance(r, dict):
            continue
        ref_texts.append(str(r.get("anchor", "")))
        ref_texts.append(str(r.get("summary", "")))
        outcome = r.get("outcome")
        if isinstance(outcome, dict):
            ref_texts.extend(str(v) for v in outcome.values())
    return "metadata/gitapex.yaml:spec.references", "\n".join(ref_texts)


def _external_citations_well_formed_result(
    spec_is_mapping: bool,
    spec_raw: object,
    schema_errors: list[jsonschema.exceptions.ValidationError],
    external_citations: object,
) -> tuple[CheckResult, list[dict[str, object]]]:
    """The ``external-citations-well-formed`` check (schema-backed, issue
    #758) -- also returns the ``external_citations_declared`` list the
    caller needs afterward, populated only on the well-formed-True branch
    (only a genuinely well-formed list feeds external-citations-resolve/
    the inline-citation rescue further down, matching how a malformed
    spec.references never reaches sidecar_citation_sources)."""
    external_citations_well_formed_rule = (
        "spec.externalCitations, if present, is a non-empty list of "
        "item mappings, each with a path rooted at evals/ or docs/ "
        "and a role one of "
        f"{EXTERNAL_CITATION_ROLES}, and no unrecognized key"
    )
    external_citations_declared: list[dict[str, object]] = []
    if not spec_is_mapping:
        result = CheckResult(
            "external-citations-well-formed",
            False,
            external_citations_well_formed_rule,
            f"spec is not a mapping: {spec_raw!r}",
        )
    else:
        errors = _errors_under(schema_errors, "spec", "externalCitations")
        if errors:
            result = CheckResult(
                "external-citations-well-formed",
                False,
                external_citations_well_formed_rule,
                _join_schema_errors(errors),
            )
        elif external_citations is None:
            result = CheckResult(
                "external-citations-well-formed", True, external_citations_well_formed_rule, "not declared (optional)"
            )
        else:
            ext_count = len(external_citations) if isinstance(external_citations, list) else 0
            ext_noun = "entry" if ext_count == 1 else "entries"
            result = CheckResult(
                "external-citations-well-formed", True, external_citations_well_formed_rule, f"{ext_count} {ext_noun}"
            )
            if isinstance(external_citations, list):
                external_citations_declared = [c for c in external_citations if isinstance(c, dict)]
    return result, external_citations_declared


def _lifecycle_reason_citation_sources(lifecycle_dict: dict[str, object]) -> list[tuple[str, str]]:
    """The ``for lifecycle_key in ("experimental", "deprecated"): ...``
    loop feeding ``sidecar_citation_sources``, extracted verbatim from
    ``check_shape``."""
    sources: list[tuple[str, str]] = []
    for lifecycle_key in ("experimental", "deprecated"):
        lifecycle_block = lifecycle_dict.get(lifecycle_key)
        if isinstance(lifecycle_block, dict):
            reason_text = lifecycle_block.get("reason")
            if isinstance(reason_text, str) and reason_text:
                sources.append((f"metadata/gitapex.yaml:spec.lifecycle.{lifecycle_key}.reason", reason_text))
    return sources


def _references_dir_checks(skill_dir: Path, anchor_slug_cache: dict[Path, frozenset[str] | None]) -> list[CheckResult]:
    """references/'s own flatness/TOC/links/anchor checks, extracted
    verbatim from ``check_shape`` -- mutates ``anchor_slug_cache`` in place
    exactly as the original inline loop did (shared with the SKILL.md-level
    anchor check above it there), and returns ``[]`` when there is no
    references/ directory at all."""
    results: list[CheckResult] = []
    refs_dir = skill_dir / "references"
    if not refs_dir.is_dir():
        return results
    nested = sorted(
        str(p.relative_to(refs_dir))
        for p in refs_dir.rglob("*")
        if p.is_file() and p.parent != refs_dir and not _is_ignorable(p)
    )
    results.append(
        CheckResult(
            "references-flat",
            not nested,
            "references/ files are one level deep",
            "nested: " + ", ".join(nested) if nested else "flat",
        )
    )
    for ref in sorted(refs_dir.iterdir()):
        if not ref.is_file() or _is_ignorable(ref):
            continue
        if ref.suffix.lower() != ".md":
            # A non-Markdown dependency file (e.g. a bundled JSON
            # schema) still gets references-flat and the junk filter
            # above, but TOC/link/anchor are Markdown-navigation
            # concepts that do not apply to it -- skip rather than
            # fail it against a heading convention it was never
            # written to have.
            continue
        try:
            ref_text = ref.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # skip binary/unreadable junk, don't abort the run
        n = len(ref_text.splitlines())
        if n > TOC_MIN_LINES:
            has_toc = bool(TOC_RE.search(ref_text))
            results.append(
                CheckResult(
                    f"toc:{ref.name}",
                    has_toc,
                    f"reference over {TOC_MIN_LINES} lines has a TOC",
                    f"{n} lines, " + ("TOC found" if has_toc else "no TOC"),
                )
            )
        ref_body = "\n".join(_body_after_frontmatter(ref_text))
        ref_offenders = _out_of_skill_link_targets(ref_body, skill_dir, source_dir=ref.parent)
        results.append(
            CheckResult(
                f"links-inside-skill:{ref.name}",
                not ref_offenders,
                "Markdown link targets resolve inside the skill's own directory",
                "all inside" if not ref_offenders else "outside: " + ", ".join(ref_offenders),
            )
        )
        anchor_slug_cache.setdefault(ref, _heading_slugs(ref_body))
        ref_broken_anchors = _broken_anchor_targets(ref_body, ref, skill_dir, anchor_slug_cache)
        results.append(
            CheckResult(
                f"anchor-targets-resolve:{ref.name}",
                not ref_broken_anchors,
                "Markdown link #fragments resolve to a real heading anchor in their target file",
                "all resolve" if not ref_broken_anchors else "broken: " + ", ".join(ref_broken_anchors),
            )
        )
    return results


def _external_citations_resolve_result(
    external_citations_declared: list[dict[str, object]], skill_md: Path, skill_dir: Path, body: list[str]
) -> CheckResult:
    """The ``external-citations-resolve`` check, extracted verbatim from
    ``check_shape``."""
    rule = (
        "every spec.externalCitations path literally appears somewhere "
        "in SKILL.md or references/*.md (no stale declaration)"
    )
    if not external_citations_declared:
        return CheckResult("external-citations-resolve", True, rule, "not declared (optional)")
    stale_external_citations = _external_citation_declaration_offenders(
        external_citations_declared, skill_md, skill_dir, body
    )
    return CheckResult(
        "external-citations-resolve",
        not stale_external_citations,
        rule,
        "all resolve" if not stale_external_citations else "stale: " + ", ".join(stale_external_citations),
    )

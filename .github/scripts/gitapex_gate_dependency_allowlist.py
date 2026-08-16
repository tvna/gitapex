#!/usr/bin/env python3
"""CI gate: every skill's declared spec.executionRequirements.packages.
<ecosystem> entries must name only a package gitapex itself allows.

Redesign, under issue #1141, of PR2's (issue #1118 -> PR #1120) now-removed
gitapex_check_skill_shape.py-embedded execution-requirements-packages-
allowlisted check. That check read a shared .gitapex/dependency-
allowlist.json file at the repo root -- a file living outside every
skill's own directory, coupling otherwise-independent skills to one shared
config file. gitapex_check_skill_shape.py is meant to travel with a skill
wherever that skill is vendored into a different repository; gitapex's own
repo-local package policy (ADR 0001, docs/adr/0001-adopt-mypy-and-pydantic-
for-deterministic-gates.md, decided under issue #1115) has no business
living inside a portable checker at all, however it is stored. This gate
takes over the allowlist-membership half of the removed check and keeps it
here, repo-local, where it belongs.

spec.executionRequirements.packages.pip itself -- a skill's own "I use
package X" declaration -- is untouched by this redesign; only the
*mechanism* that grades a declared package against gitapex's own policy
moved, from a shared cross-skill config file to this repo-local script.
ALLOWED_PACKAGES below is deliberately hardcoded here and nowhere else:
not in the schema (skills/evaluating-skill-quality/references/
skill-metadata.schema.json), not in gitapex_check_skill_shape.py itself. A
schema or a portable checker encoding gitapex's own opinion about which
packages are acceptable would break the moment either travels into a
different repository with a different policy.

Exit codes:
    0  Every discovered sidecar's declared packages, if any, are all in
       ALLOWED_PACKAGES once PEP 503 normalized. A skill declaring no
       packages at all is not a violation of anything this gate checks.
    1  At least one declared package is outside ALLOWED_PACKAGES for its
       own ecosystem, or a sidecar that exists could not be read/parsed,
       or too few skill directories were discovered to trust the scan at
       all (MIN_EXPECTED_SKILL_DIRS).
    2  CLI arguments failed validation, or PyYAML is not importable.

No-op vs. fail-closed is the one distinction this file most needs to get
right. An *absent* packages block, a packages value that is not a mapping,
or a per-ecosystem value that is not a list, is a silent no-op here --
never a finding -- because a shape defect at any of those levels is
already reported, under its own check id, by gitapex_check_skill_shape.py's
own execution-requirements-well-formed check; this gate double-reporting
the same shape defect under a different id would only be noise, not a
second real signal. The same leniency covers a sidecar that simply does
not exist: presence enforcement belongs to a different gate
(gitapex_scan_skill_metadata_schema.py's metadata-file-present), not this
one. None of that leniency extends to a sidecar that DOES exist but fails
to read as UTF-8 text or parse as YAML at all (bad encoding, invalid
syntax, pathological nesting): that case fails closed, hard, naming the
skill, because an unreadable file could be hiding any package declaration
at all -- silently treating it as "nothing to report" would be
indistinguishable from a genuinely clean pass. This mirrors the removed
check's own established sidecar-unreadable contract.

Standalone by design: this repo's own .github/scripts/*.py and
skills/*/scripts/*.py convention is to stay independently self-contained
rather than cross-import small helpers across that boundary -- a shared
module gets extracted only after a real drift bug is found between two
independent copies (issue #755's own precedent), not preemptively. This
file hand-duplicates gitapex_scan_skill_metadata_schema.py's
discover_skill_dirs/load_sidecar/guarded-PyYAML-import shape and
gitapex_scan_execution_requirements_drift.py's _pep503_normalize rather
than importing either.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Any

from pydantic import BaseModel, ValidationError

try:
    import yaml
except ModuleNotFoundError as error:
    # Mirrors gitapex_scan_skill_metadata_schema.py's own guard verbatim in
    # shape (issue #1089): only convert to SystemExit when run as a
    # script, since a bare SystemExit raised while this module is merely
    # *imported* (e.g. pytest collecting this file's own test module) is
    # not a plain Exception and defeats pytest's own collection-error
    # handling. error.name narrows to "PyYAML itself is absent"; a
    # broken/partial install raises this same exception type with
    # error.name == "yaml.<submodule>", not "yaml", and this guard's own
    # remediation would not fix a corrupted install, so that case
    # re-raises unmodified instead of being misdiagnosed. The added
    # pydantic import above is unguarded, matching
    # gitapex_gate_skill_rename_lifecycle.py's/
    # gitapex_gate_routine_scope_enforcement.py's own choice not to guard
    # it: this gate's own production invocation
    # (dependency-allowlist-gate.yml) already runs under `uv run`, so a
    # missing pydantic would already be a broken environment regardless of
    # this guard.
    if error.name != "yaml" or __name__ != "__main__":
        raise
    print(
        f"error: {error}. This script requires PyYAML, which is not on "
        "the import path -- install the dev dependency group first: "
        "uv sync --group dev",
        file=sys.stderr,
    )
    raise SystemExit(2) from error

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
# Mirrors gitapex_check_skill_shape.py's own SIDECAR_RELATIVE_PATH constant,
# duplicated as a literal per this file's own module docstring (no
# cross-import).
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"

# ADR 0001 / issue #1115's decision, hardcoded here and only here (see
# module docstring). pip is the only ecosystem gitapex currently allows
# anything under -- an ecosystem key absent from this mapping allows
# nothing at all for that ecosystem (ALLOWED_PACKAGES.get(ecosystem, ())
# below falls back to an empty tuple).
ALLOWED_PACKAGES: dict[str, tuple[str, ...]] = {
    "pip": ("pyyaml", "jsonschema", "pydantic"),
}

# Same discovery-floor rationale and value as
# gitapex_scan_skill_metadata_schema.py's own MIN_EXPECTED_SKILL_DIRS: this
# repository currently has 25 real skills, so headroom against that real
# count matters more than pinning the exact number -- a wrong or missing
# --skills-root (or a checkout that lost most of skills/) is caught as a
# finding here instead of discover_skill_dirs silently returning few/no
# directories and this gate then reporting a vacuous "no violations."
MIN_EXPECTED_SKILL_DIRS = 15


class SidecarReadError(Exception):
    """A sidecar exists but could not be read as UTF-8 text or parsed as
    YAML at all -- this gate fails closed on it (see module docstring).
    Distinct from a sidecar that is absent (a no-op here) and from one
    that parses fine but declares a disallowed package (an ordinary
    finding, not an error)."""


def discover_skill_dirs(skills_dir: pathlib.Path = SKILLS_DIR) -> list[pathlib.Path]:
    """Every skills/<name>/ directory with a real SKILL.md, sorted -- the
    same discovery rule gitapex_scan_skill_metadata_schema.py's own
    discover_skill_dirs uses, hand-duplicated rather than imported (module
    docstring)."""
    if not skills_dir.is_dir():
        return []
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md") if p.is_file())


def load_sidecar(path: pathlib.Path) -> Any:
    """Read and YAML-parse ``path``. Raises SidecarReadError -- naming
    ``path`` -- rather than letting a non-UTF-8 file, invalid YAML syntax,
    an unreadable path, or pathologically deep nesting surface as an
    uncaught OSError/UnicodeDecodeError/YAMLError/RecursionError
    traceback. Does not itself check the parsed value's shape: a
    schema-invalid-but-parseable instance is find_disallowed_packages's
    own isinstance guards to no-op on, not a load failure."""
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


def _pep503_normalize(distribution_name: str) -> str:
    """The real PEP 503 "normalized name" comparison PyPI/pip themselves
    use to decide two distribution-name spellings name the same project --
    collapse any run of '-', '_', or '.' into a single '-', then lowercase
    (https://peps.python.org/pep-0503/#normalized-names); lowercasing
    alone would still treat e.g. "my_pkg" and "my-pkg" as different
    strings. Hand-duplicated, same logic, from
    skills/evaluating-skill-quality/scripts/
    gitapex_scan_execution_requirements_drift.py's own _pep503_normalize
    (module docstring: no cross-import between .github/scripts/*.py and
    skills/*/scripts/*.py)."""
    return re.sub(r"[-_.]+", "-", distribution_name).lower()


def find_disallowed_packages(instance: Any, skill_name: str) -> list[str]:
    """Every declared package, across every ecosystem
    instance["spec"]["executionRequirements"]["packages"] names, that is
    not in ALLOWED_PACKAGES for its own ecosystem (PEP 503 normalized on
    both sides).

    Guarded with an isinstance check at every level of that path: absent
    or wrong-shaped at ANY level -- instance itself, spec,
    executionRequirements, or packages not a dict; a given ecosystem's own
    value not a list -- returns [] silently instead of reporting anything.
    gitapex_check_skill_shape.py's own execution-requirements-well-formed
    check already reports a shape problem at any of these levels under its
    own check id; reporting one here too would double-report the same
    defect rather than add a second real signal. A non-string item inside
    an otherwise well-formed list is skipped the same way, for the same
    reason. The isinstance(declared, list) guard also protects against a
    classic footgun: a malformed sidecar declaring packages.pip as a bare
    "pyyaml" string instead of ["pyyaml"] would otherwise iterate the
    string character by character (mirrors
    gitapex_scan_execution_requirements_drift.py's own
    find_packages_drift's identical guard, for the identical reason).

    Deduplicated per ecosystem by PEP-503-normalized name: two declared
    spellings that normalize to the same value -- an exact duplicate, or a
    case/separator variant like "PyYAML" vs. "pyyaml" -- produce exactly
    one finding, naming whichever raw spelling was declared first, never
    one finding per raw string."""
    if not isinstance(instance, dict):
        return []
    spec = instance.get("spec")
    if not isinstance(spec, dict):
        return []
    execution_requirements = spec.get("executionRequirements")
    if not isinstance(execution_requirements, dict):
        return []
    packages = execution_requirements.get("packages")
    if not isinstance(packages, dict):
        return []

    findings: list[str] = []
    for ecosystem, declared in packages.items():
        if not isinstance(declared, list):
            continue
        allowed = ALLOWED_PACKAGES.get(ecosystem, ())
        allowed_normalized = {_pep503_normalize(name) for name in allowed}
        seen_normalized: set[str] = set()
        for item in declared:
            if not isinstance(item, str):
                continue
            normalized = _pep503_normalize(item)
            if normalized in seen_normalized:
                continue
            seen_normalized.add(normalized)
            if normalized not in allowed_normalized:
                findings.append(
                    f"{skill_name}: {ecosystem}/{item} is not in gitapex's "
                    f"own allowlist (allowed: {', '.join(allowed) or 'none'})"
                )
    return findings


def find_violations(
    skills_dir: pathlib.Path = SKILLS_DIR,
    min_expected_skill_dirs: int = MIN_EXPECTED_SKILL_DIRS,
) -> list[str]:
    """Every finding across every discovered skill: disallowed-package
    findings from find_disallowed_packages, plus one fail-closed finding
    per sidecar that exists but could not be read, plus a single
    discovery-floor finding if too few skill directories were found at
    all (checked first, before any per-skill work, matching
    gitapex_scan_skill_metadata_schema.py's own find_drift). Empty list
    means every discovered sidecar is clean, or declares no packages, or
    has no sidecar at all -- see module docstring for why the latter two
    are no-ops rather than findings."""
    skill_dirs = discover_skill_dirs(skills_dir)
    if len(skill_dirs) < min_expected_skill_dirs:
        return [
            f"skill-discovery-floor: found only {len(skill_dirs)} skill "
            f"director{'y' if len(skill_dirs) == 1 else 'ies'} with a "
            f"SKILL.md under {skills_dir} (expected at least "
            f"{min_expected_skill_dirs}) -- this usually means "
            "--skills-root is wrong or missing, not that skills were "
            "actually removed"
        ]

    findings: list[str] = []
    for skill_dir in skill_dirs:
        sidecar = skill_dir / SIDECAR_RELATIVE_PATH
        if not sidecar.is_file():
            # No-op: sidecar-presence enforcement is a different gate's
            # job (see module docstring), not this one's.
            continue
        try:
            instance = load_sidecar(sidecar)
        except SidecarReadError as error:
            # Fail closed (see module docstring): an unreadable/
            # unparseable sidecar could be hiding any package declaration,
            # so silence here would be indistinguishable from a verified
            # clean pass.
            findings.append(f"{skill_dir.name}: {error}")
            continue
        findings.extend(find_disallowed_packages(instance, skill_dir.name))
    return findings


class GateDependencyAllowlistArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace, matching the
    argparse-wraps-pydantic convention
    gitapex_gate_skill_rename_lifecycle.py/
    gitapex_gate_routine_scope_enforcement.py already use.
    ``skills_root`` carries no constraint beyond the ``str`` shape argparse
    already guarantees, so construction can never actually raise
    ValidationError from a real CLI invocation; the model exists for
    consistency with that same established convention (a typed seam
    between parse_args and business logic), and so this gate's own test
    suite can exercise the ``except ValidationError`` branch the same way
    its siblings' test suites do -- by monkeypatching this class, not by
    constructing genuinely invalid input."""

    skills_root: str = "skills"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every skill's declared "
        "executionRequirements.packages entries are in gitapex's own "
        "dependency allowlist."
    )
    parser.add_argument(
        "--skills-root",
        default="skills",
        help="Root directory containing skills/<name>/metadata/gitapex.yaml (default: skills)",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateDependencyAllowlistArgs(skills_root=args.skills_root)
    except ValidationError:
        print("error: invalid CLI arguments", file=sys.stderr)
        return 2

    findings = find_violations(pathlib.Path(validated.skills_root))
    if not findings:
        print("PASS: every declared package is in gitapex's own dependency allowlist")
        return 0

    print("FAIL: package(s) declared outside gitapex's own dependency allowlist:", file=sys.stderr)
    for finding in findings:
        print(f"  - {finding}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

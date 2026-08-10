#!/usr/bin/env python3
"""Cross-check a skill's declared spec.executionRequirements against real
SKILL.md prose and bundled scripts/*.py content (issue #1022).

skills/evaluating-skill-quality/references/skill-metadata.schema.json
validates executionRequirements' SHAPE only (its own docstring says so
explicitly and names this exact companion-scanner pattern as the fix,
already implemented once for metadata.name/skillDependencies/lifecycle.
deprecated.replacement by .github/scripts/gitapex_scan_skill_metadata_schema.py).
Nothing before this scanner cross-checks the declared network mode/domains
and tools read/write/shell tags against what a skill's own content actually
does -- a skill could claim network.mode: disabled while a bundled script
performs network I/O, or claim tools.write: [] while SKILL.md's own prose
instructs a mutating action, with nothing to catch the drift.

Two independent, best-effort pattern-match checks, one per
executionRequirements sub-block (mirrors skills/evaluating-skill-quality/
scripts/gitapex_check_skill_shape.py's own per-subkey convention):

- find_network_drift: declared network.mode/domains vs. network-capable
  imports and literal https?:// hosts found in skill_dir/scripts/*.py.
- find_tools_drift: declared tools.write/tools.shell vs. mutating-action
  language found anywhere in skill_dir/SKILL.md's full text. Deliberately
  NOT anchored to a single "Procedure" heading: a live check across every
  skill in this repository found the heading name itself varies (Steps,
  Procedure, Exact sequence, Checklist, Overview, ...), so anchoring on one
  name would silently blind the scanner on most real skills. tools.read is
  not checked -- the issue's own criterion rows name only write/shell as
  the safety-relevant under-declaration direction.

Each finding carries a severity: "error" for under-declaration (declared
narrower than actual -- the safety-relevant direction per issue #1022's own
Acceptance Criteria Map) or "warning" for over-declaration (declared
broader than actual content ever exercises -- a hygiene finding, reported
but never failing a run on its own). This is a pattern-match net, not a
formal proof: a network call routed through an unlisted helper, or a
mutating action described in prose this scanner's verb/noun lists do not
recognize, can still slip through undetected -- the same disclosed
false-negative limitation this repository's other AST/pattern-based
scanners already carry.

Deliberately NOT wired as a "real repository has zero drift" gate the way
gitapex_scan_skill_metadata_schema.py's own test_real_repository_* is:
issue #1022's own Non-goals explicitly excludes retroactively auditing
every existing skills/*/metadata/gitapex.yaml sidecar for a pre-existing
mismatch, and a live check found several already exist (e.g.
planning-a-branch-from-an-issue declares shell: [] but its own Step 8
invokes `python3 scripts/gitapex_check_acm_present.py`). Registered in
.gitapex/ssot.json at status: "experimental" for exactly this reason --
this scanner's own fixture-based unit tests are the enforced gate for now;
a future retroactive-sweep issue promoting it to "active" once real drift
is fixed is a natural follow-up, not this scanner's own job.

Self-contained, stdlib + PyYAML only, no cross-import from any other
.github/scripts/*.py file (issue #1022's own Constraints) -- the skill
directory discovery and sidecar-read helpers below intentionally duplicate
gitapex_scan_skill_metadata_schema.py's own small versions rather than
importing them, matching this repository's established convention for
these standalone scripts.

Run standalone (exit 0 clean or warnings-only, 1 on any error-severity
finding or a read error) or via the pytest gate in
tests/test_gitapex_scan_execution_requirements_drift.py.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any, NamedTuple

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
# Mirrors gitapex_scan_skill_metadata_schema.py's own SIDECAR_RELATIVE_PATH
# constant, duplicated as a literal rather than imported (see module
# docstring's own no-cross-import constraint).
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Same vacuous-pass guard and reasoning as gitapex_scan_skill_metadata_schema.py's
# own MIN_EXPECTED_SKILL_DIRS: a wrong or missing skills_dir must read as a
# finding, never as silent "no drift."
MIN_EXPECTED_SKILL_DIRS = 15

NETWORK_CAPABLE_MODULES = (
    "urllib",
    "requests",
    "http.client",
    "socket",
    "ftplib",
    "smtplib",
    "xmlrpc",
    "httpx",
    "aiohttp",
)
_NETWORK_IMPORT_PATTERN = re.compile(
    r"^\s*(?:import|from)\s+(" + "|".join(re.escape(m) for m in NETWORK_CAPABLE_MODULES) + r")(?:\.\w+)*\b",
    re.MULTILINE,
)
_URL_HOST_PATTERN = re.compile(r"https?://([A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)")

_WRITE_VERBS = r"(?:writes?|wrote|creates?|drafts?|edits?|updates?|modifies|generates?|authors?)"
_WRITE_NOUNS = (
    r"(?:file|SKILL\.md|script|\.py\b|\.md\b|\.json\b|\.ya?ml\b|"
    r"branch|commit|PR\b|pull request|issue\b|document)"
)
_WRITE_INTENT_PATTERN = re.compile(
    rf"\b{_WRITE_VERBS}\b(?:\s+\S+){{0,4}}\s+{_WRITE_NOUNS}",
    re.IGNORECASE,
)
_SHELL_INTENT_PATTERN = re.compile(
    r"\b(?:Bash tool|shell command|subprocess|run\s+`|"
    r"`git (?:commit|push|merge|rebase|checkout)|`python3 |`uv run|`npm |CLI)\b",
    re.IGNORECASE,
)


class Finding(NamedTuple):
    """One drift finding. severity is "error" (under-declared -- the
    safety-relevant direction) or "warning" (over-declared -- a hygiene
    finding, never failing a run on its own)."""

    severity: str
    message: str


class ReadError(Exception):
    """A sidecar could not be read as UTF-8 text or parsed as YAML at all --
    exit 1, never a traceback."""


def discover_skill_dirs(skills_dir: pathlib.Path = SKILLS_DIR) -> list[pathlib.Path]:
    """Every skills/<name>/ directory with a real SKILL.md, sorted -- same
    discovery rule as gitapex_scan_skill_metadata_schema.py's own
    discover_skill_dirs, duplicated rather than imported."""
    if not skills_dir.is_dir():
        return []
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md") if p.is_file())


def _load_sidecar(path: pathlib.Path) -> Any:
    """Read and YAML-parse ``path``. Raises ReadError rather than letting a
    non-UTF-8 file or invalid YAML syntax surface as an uncaught
    exception."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReadError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise ReadError(f"{path}: is not valid UTF-8: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ReadError(f"{path}: is not valid YAML: {error}") from error


def _read_text_best_effort(path: pathlib.Path) -> str:
    """Read ``path`` as UTF-8 text, or "" if it cannot be read/decoded --
    a single unreadable script/SKILL.md must not crash the whole scan; an
    empty string simply contributes no pattern matches."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _bundled_script_texts(skill_dir: pathlib.Path) -> list[str]:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [_read_text_best_effort(p) for p in sorted(scripts_dir.glob("*.py"))]


def find_network_drift(network: Any, skill_dir: pathlib.Path) -> list[Finding]:
    """network-mode-vs-script-content: declared executionRequirements.network
    vs. network-capable imports/literal https?:// hosts found in
    skill_dir/scripts/*.py."""
    mode = network.get("mode", "disabled") if isinstance(network, dict) else "disabled"
    domains = network.get("domains") if isinstance(network, dict) else None
    declared_domains = set(domains) if isinstance(domains, list) else set()

    script_texts = _bundled_script_texts(skill_dir)
    has_network_import = any(_NETWORK_IMPORT_PATTERN.search(text) for text in script_texts)
    referenced_hosts: set[str] = set()
    for text in script_texts:
        referenced_hosts.update(_URL_HOST_PATTERN.findall(text))

    findings: list[Finding] = []
    if mode == "disabled" and (has_network_import or referenced_hosts):
        findings.append(
            Finding(
                "error",
                "network-mode-vs-script-content: declared network.mode "
                f"{mode!r} (or omitted) but bundled scripts show "
                "network-capable usage",
            )
        )
    elif mode == "allowlist":
        for host in sorted(referenced_hosts - declared_domains):
            findings.append(
                Finding(
                    "error",
                    "network-mode-vs-script-content: bundled scripts reference "
                    f"host {host!r} not present in declared allowlist domains "
                    f"{sorted(declared_domains)}",
                )
            )
    elif mode == "unrestricted" and not has_network_import and not referenced_hosts:
        findings.append(
            Finding(
                "warning",
                "network-mode-vs-script-content: declared network.mode "
                "'unrestricted' but no bundled script shows network-capable "
                "usage (over-declared)",
            )
        )
    return findings


def find_tools_drift(tools: Any, skill_dir: pathlib.Path) -> list[Finding]:
    """tools-write-vs-skill-md / tools-shell-vs-skill-md: declared
    executionRequirements.tools.write/shell vs. mutating-action language
    found in skill_dir/SKILL.md's full text. tools.read is not checked."""
    write_tags = tools.get("write") if isinstance(tools, dict) else None
    shell_tags = tools.get("shell") if isinstance(tools, dict) else None
    write_declared = bool(write_tags)
    shell_declared = bool(shell_tags)

    skill_md = skill_dir / "SKILL.md"
    text = _read_text_best_effort(skill_md) if skill_md.is_file() else ""

    findings: list[Finding] = []
    write_signal = bool(_WRITE_INTENT_PATTERN.search(text))
    if not write_declared and write_signal:
        findings.append(
            Finding(
                "error",
                "tools-write-vs-skill-md: declared executionRequirements."
                "tools.write is empty/absent but SKILL.md shows "
                "mutating-action language",
            )
        )
    elif write_declared and not write_signal:
        findings.append(
            Finding(
                "warning",
                "tools-write-vs-skill-md: declared executionRequirements."
                "tools.write but SKILL.md shows no matching mutating-action "
                "language (over-declared)",
            )
        )

    shell_signal = bool(_SHELL_INTENT_PATTERN.search(text))
    if not shell_declared and shell_signal:
        findings.append(
            Finding(
                "error",
                "tools-shell-vs-skill-md: declared executionRequirements."
                "tools.shell is empty/absent but SKILL.md shows "
                "shell-invocation language",
            )
        )
    elif shell_declared and not shell_signal:
        findings.append(
            Finding(
                "warning",
                "tools-shell-vs-skill-md: declared executionRequirements."
                "tools.shell but SKILL.md shows no matching shell-invocation "
                "language (over-declared)",
            )
        )
    return findings


def _spec_of(instance: Any) -> dict[str, Any]:
    if not isinstance(instance, dict):
        return {}
    spec = instance.get("spec")
    return spec if isinstance(spec, dict) else {}


def find_drift(
    skills_dir: pathlib.Path = SKILLS_DIR,
    min_expected_skill_dirs: int = MIN_EXPECTED_SKILL_DIRS,
) -> list[Finding]:
    """Every drift finding across every discovered skill's declared
    executionRequirements. Empty list means no drift detected (a clean
    scan, not a proof of correctness -- see module docstring)."""
    skill_dirs = discover_skill_dirs(skills_dir)
    if len(skill_dirs) < min_expected_skill_dirs:
        return [
            Finding(
                "error",
                f"skill-discovery-floor: found only {len(skill_dirs)} skill "
                f"director{'y' if len(skill_dirs) == 1 else 'ies'} with a "
                f"SKILL.md under {skills_dir} (expected at least "
                f"{min_expected_skill_dirs}) -- this usually means "
                "skills_dir is wrong or missing, not that skills were "
                "actually removed",
            )
        ]

    findings: list[Finding] = []
    for skill_dir in skill_dirs:
        prefix = skill_dir.name
        sidecar = skill_dir / SIDECAR_RELATIVE_PATH
        if not sidecar.is_file():
            findings.append(Finding("error", f"{prefix}: metadata-file-present: missing {sidecar}"))
            continue
        try:
            instance = _load_sidecar(sidecar)
        except ReadError as error:
            findings.append(Finding("error", f"{prefix}: {error}"))
            continue

        execution_requirements = _spec_of(instance).get("executionRequirements")
        if not isinstance(execution_requirements, dict):
            execution_requirements = {}

        for finding in find_network_drift(execution_requirements.get("network"), skill_dir):
            findings.append(Finding(finding.severity, f"{prefix}: {finding.message}"))
        for finding in find_tools_drift(execution_requirements.get("tools"), skill_dir):
            findings.append(Finding(finding.severity, f"{prefix}: {finding.message}"))

    return findings


def main() -> int:
    findings = find_drift()
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    if errors:
        print("executionRequirements drift (error):")
        for finding in errors:
            print(f"  {finding.message}")
    if warnings:
        print("executionRequirements drift (warning, non-blocking):")
        for finding in warnings:
            print(f"  {finding.message}")
    if not findings:
        print("No executionRequirements drift found.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

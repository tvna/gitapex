#!/usr/bin/env python3
"""Cross-check a skill's declared spec.executionRequirements against real
SKILL.md prose and bundled scripts/*.py content (issue #1022).

Bundled with the evaluating-skill-quality skill itself, alongside its
read-only shape checker (gitapex_check_skill_shape.py) -- run the same
way, against one target skill directory at a time, as part of that
skill's "Deterministic shape" lane (see SKILL.md's Two lanes section).
skills/evaluating-skill-quality/references/skill-metadata.schema.json
validates executionRequirements' SHAPE only; this scanner cross-checks
one skill's own declared network mode/domains and tools write/shell tags
against what its own content actually does.

Two independent, best-effort pattern-match checks, one per
executionRequirements sub-block:

- find_network_drift: declared network.mode/domains vs. network-capable
  imports and literal https?:// hosts found in skill_dir/scripts/*.py.
- find_tools_drift: declared tools.write/tools.shell vs. mutating-action
  language found anywhere in skill_dir/SKILL.md's full text. Deliberately
  NOT anchored to a single "Procedure" heading: the heading name varies
  across real skills (Steps, Procedure, Exact sequence, Checklist, ...),
  so anchoring on one would blind the scanner on most of them. tools.read
  is not checked -- only write/shell are the safety-relevant
  under-declaration direction.

Each finding carries a severity: "error" for under-declaration (declared
narrower than actual) or "warning" for over-declaration (declared broader
than actual content ever exercises -- a hygiene finding, never failing a
run on its own). This is a pattern-match net, not a formal proof: a
network call routed through an unlisted helper or dynamically constructed
host, or mutating-action language this scanner's verb/noun lists do not
recognize, can slip through undetected (see
test_dynamically_constructed_host_evades_allowlist_check for one
deliberately-constructed example).

Language scope: find_network_drift only reads skill_dir/scripts/*.py --
a bundled non-Python script (a .sh file, for instance; this repository's
own skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh is
one real example) is invisible to it, network-capable shell commands
(curl, wget, nc, ...) included. This matters beyond this one repository:
evaluating-skill-quality itself travels as a portable skill (see its own
spec.portability), so a consuming repository's own skills may bundle
scripts in other languages this scanner was never taught to read. Not
fixed here -- see test_non_python_bundled_scripts_are_not_scanned for a
concrete, deliberately-constructed proof of the gap, not only this
paragraph's claim.

Not registered in .gitapex/ssot.json, matching gitapex_check_skill_shape.py's
own un-registered status: a per-skill checker invoked deliberately against
one target at a time is not the shape of a repo-wide automatic gate. A
live run against this repository's own skills/ tree reports real findings
issue #1022's own Non-goals excludes retroactively fixing here -- this
module's own fixture-based unit tests are what CI enforces.

Self-contained, stdlib + PyYAML only, no cross-import from any other
.github/scripts/*.py file -- the skill directory discovery and
sidecar-read helpers below intentionally duplicate
gitapex_scan_skill_metadata_schema.py's own small versions.

Run standalone against one skill directory --
``python3 skills/evaluating-skill-quality/scripts/
gitapex_scan_execution_requirements_drift.py <skill-dir>`` (exit 0 clean or
warnings-only, 1 on any error-severity finding or a read error) -- or via
the pytest gate in skills/evaluating-skill-quality/scripts/
test_gitapex_scan_execution_requirements_drift.py.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Any, NamedTuple

import yaml

# This file lives at skills/evaluating-skill-quality/scripts/<name>.py, so
# parents[2] is skills/ itself -- one level deeper than a .github/scripts/
# script's own parents[2] (repo root), since this module moved into the
# evaluating-skill-quality skill's own scripts/ bundle rather than staying
# a repo-root-level CI script.
SKILLS_DIR = pathlib.Path(__file__).resolve().parents[2]
# Mirrors gitapex_scan_skill_metadata_schema.py's own SIDECAR_RELATIVE_PATH
# constant, duplicated as a literal rather than imported (see module
# docstring's own no-cross-import constraint).
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Same vacuous-pass guard and reasoning as gitapex_scan_skill_metadata_schema.py's
# own MIN_EXPECTED_SKILL_DIRS: a wrong or missing skills_dir must read as a
# finding, never as silent "no drift."
MIN_EXPECTED_SKILL_DIRS = 15

NETWORK_CAPABLE_MODULES = (
    # Bare "urllib" also matched pure-parsing submodules with no network
    # I/O of their own (import urllib.parse) -- found by an independent
    # review; only the two network-capable submodules are listed now.
    # "from urllib import request" still slips through unmatched (this
    # pattern anchors on the dotted module path after import/from), a
    # disclosed false-negative, not fixed here.
    "urllib.request",
    "urllib.error",
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
# A single trailing \b (not one per alternative) applies to whichever
# alternative matched -- otherwise a no-\b alternative matches as a bare
# prefix of an unrelated word (e.g. "commit" inside "committee").
_WRITE_NOUNS = r"(?:file|SKILL\.md|script|\.py|\.md|\.ya?ml|\.json|branch|commit|PR|pull request|issue|document)\b"
_WRITE_INTENT_PATTERN = re.compile(
    rf"\b{_WRITE_VERBS}\b(?:\s+\S+){{0,4}}\s+{_WRITE_NOUNS}",
    re.IGNORECASE,
)
# Three alternations, not one \b-wrapped group: \b demands a word/non-word
# transition, and a backtick is itself non-word, so a backtick-prefixed
# alternative wrapped in a leading \b can never match right after ordinary
# Markdown whitespace/punctuation. The backtick-prefixed alternatives below
# need no \b: matching the backtick itself already anchors the position.
_SHELL_INTENT_PATTERN = re.compile(
    r"\b(?:Bash tool|shell command|subprocess|CLI)\b"
    r"|run\s+`"
    r"|`(?:git (?:commit|push|merge|rebase|checkout)|python3 |uv run|npm )",
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
    mode_value = network.get("mode") if isinstance(network, dict) else None
    # dict.get(key, default) only substitutes on an ABSENT key -- a real
    # `mode: null` or an unrecognized/mis-cased string must not slip
    # through unmatched by any branch below. Any value outside the three
    # recognized modes falls back to "disabled", the strictest treatment,
    # matching an absent network block's own equivalence to disabled.
    mode = mode_value if mode_value in ("disabled", "allowlist", "unrestricted") else "disabled"
    domains = network.get("domains") if isinstance(network, dict) else None
    # Hostnames are case-insensitive (RFC 4343); lower-cased here so the
    # allowlist set-difference below compares like-for-like.
    declared_domains = {d.lower() for d in domains if isinstance(d, str)} if isinstance(domains, list) else set()

    script_texts = _bundled_script_texts(skill_dir)
    has_network_import = any(_NETWORK_IMPORT_PATTERN.search(text) for text in script_texts)
    referenced_hosts: set[str] = set()
    for text in script_texts:
        # A commented-out reference (# see https://docs.python.org/...) is
        # not executed and must not count as network usage -- found by an
        # independent review; only import/from lines are already immune
        # (a "# import requests" comment never matches ^\s*(?:import|from)),
        # so only this URL-host extraction needed the filter.
        code_only = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        referenced_hosts.update(host.lower() for host in _URL_HOST_PATTERN.findall(code_only))

    findings: list[Finding] = []
    if mode == "disabled" and (has_network_import or referenced_hosts):
        findings.append(
            Finding(
                "error",
                "network-mode-vs-script-content: declared network.mode "
                f"{mode_value!r} (absent or unrecognized values are treated "
                "as 'disabled') but bundled scripts show network-capable "
                "usage",
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


def find_skill_drift(skill_dir: pathlib.Path) -> list[Finding]:
    """Every drift finding for exactly one skill directory: reads its own
    metadata/gitapex.yaml sidecar and runs find_network_drift/find_tools_drift
    against it. Messages carry no skill-name prefix (single-target use, the
    same convention gitapex_check_skill_shape.py's own single-target CLI
    follows) -- find_drift() below adds one when aggregating across many."""
    sidecar = skill_dir / SIDECAR_RELATIVE_PATH
    if not sidecar.is_file():
        return [Finding("error", f"metadata-file-present: missing {sidecar}")]
    try:
        instance = _load_sidecar(sidecar)
    except ReadError as error:
        return [Finding("error", str(error))]

    execution_requirements = _spec_of(instance).get("executionRequirements")
    if not isinstance(execution_requirements, dict):
        execution_requirements = {}

    findings: list[Finding] = []
    findings.extend(find_network_drift(execution_requirements.get("network"), skill_dir))
    findings.extend(find_tools_drift(execution_requirements.get("tools"), skill_dir))
    return findings


def find_drift(
    skills_dir: pathlib.Path = SKILLS_DIR,
    min_expected_skill_dirs: int = MIN_EXPECTED_SKILL_DIRS,
) -> list[Finding]:
    """Every drift finding across every discovered skill's declared
    executionRequirements -- find_skill_drift() run once per skill, with its
    findings prefixed by the skill directory name. Empty list means no
    drift detected (a clean scan, not a proof of correctness -- see module
    docstring). Not the CLI's own entry point (see main(), which checks
    exactly one skill directory, matching this skill's "Deterministic
    shape" lane); kept for the real-repository smoke test and any future
    batch use."""
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
        for finding in find_skill_drift(skill_dir):
            findings.append(Finding(finding.severity, f"{prefix}: {finding.message}"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check one skill's declared spec.executionRequirements against its "
            "actual SKILL.md prose and bundled scripts/*.py content (read-only, "
            "best-effort pattern-match -- not a formal proof)."
        )
    )
    parser.add_argument("target", help="Path to a skill directory (e.g. skills/<name>).")
    args = parser.parse_args(argv)

    target = pathlib.Path(args.target)
    if not target.is_dir():
        # A wrong path or a file path must not be blamed on a missing
        # sidecar (find_skill_drift's own metadata-file-present message) --
        # found by an independent review.
        print(f"error: {target} is not a skill directory")
        return 1

    findings = find_skill_drift(target)
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

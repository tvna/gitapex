#!/usr/bin/env python3
"""Drift gate for issue #1963's cross-runtime tool-boundary invariant.

The invariant this gate holds:

    A tool boundary declared in a distributed subagent definition must be
    reproduced equivalently in every runtime that definition is
    distributed to.

`agents/*.md` is Claude-canonical (`tools:` / `disallowedTools:`), and
`hooks/gitapex_sync_opencode.py` generates the OpenCode copies, replacing
those Claude-only keys with a `permission:` mapping. Before this gate, that
replacement was unchecked in both directions: `branch-plan-task.md`
declared `disallowedTools: mcp__github` and was synced with no mapping at
all, so the boundary was simply absent on a runtime that allows every tool
by default. Nothing reported it, because nothing compared the two.

Three checks, separated because a missing mapping and a wrong one are
different failures with different fixes:

1. **boundary-declared** -- every `agents/*.md` declares `tools:` or
   `disallowedTools:`. An agent with neither inherits everything, which
   may be intended, but it cannot be reproduced and so cannot be checked.
2. **mapping-present** -- every `agents/*.md` appears in
   `hooks/gitapex_sync_opencode.py`'s `AGENT_PERMISSION_SPECS` with a
   non-None permission mapping.
3. **mapping-equivalent** -- the source declaration, this file's own
   expectation table, and the generated `.opencode/agents/` copy all agree.

Check 3 takes the "keep the constant and check three-way agreement" form
rather than deriving the mapping from the source. Derivation was
considered and rejected on the evidence: the mapping is not one-to-one.
OpenCode's `list` has no Claude-side counterpart (Claude's `Read` covers
both), and `*mcp*` is a wildcard at a coarser granularity than a concrete
`mcp__github__*`. A derivation faithful to those asymmetries would have to
encode them as special cases anyway, at which point it is an expectation
table wearing a function's clothes -- so this file states the table
outright and checks that nothing drifted away from it.

Repository tooling, deliberately not a skill primitive: every fact it
reads is specific to this repository's own sync mechanism, so it lives on
the never-deployed side of `docs/repository-layout.md`'s boundary rather
than shipping gitapex-internal logic to a plugin consumer. Axis B4 stays
model-judged when the skill grades some other repository's subagents; this
gate is that axis applied to the one instance this repository owns.

Usage:
  uv run --frozen python3 .github/scripts/gitapex_gate_tool_boundary_parity.py

Exit codes: 0 all three checks pass; 1 at least one fails; 2 the check
itself could not run (the sync module is missing, or does not expose
`AGENT_PERMISSION_SPECS`) -- never a silent pass.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Where the Claude-canonical definitions live, and where the generated
# OpenCode copies are written. Both are fixed by
# hooks/gitapex_sync_opencode.py's own constants; restated here as paths
# rather than imported, so a sync-module import failure still yields the
# exit-2 diagnostic below instead of an AttributeError.
AGENTS_SRC_DIR = Path("agents")
OPENCODE_AGENTS_DIR = Path(".opencode") / "agents"
SYNC_MODULE_PATH = Path("hooks") / "gitapex_sync_opencode.py"
# The Claude-side frontmatter keys that can express a tool boundary. A
# definition declaring neither inherits every tool available to subagents.
BOUNDARY_KEYS = ("tools", "disallowedTools")

# The expectation table check 3 compares against. One entry per
# distributed agent definition: the boundary key the source must declare,
# the value it must declare, and the permission keys the OpenCode copy
# must carry as denials. Values are what the source says today; changing a
# source declaration without changing its row here is exactly the drift
# this gate exists to catch, so an edit to one half is meant to fail until
# the other half is updated deliberately.
EXPECTED_BOUNDARIES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "review-persona.md": (
        "tools",
        "Read, Grep, Glob",
        (
            "edit",
            "bash",
            "task",
            "webfetch",
            "websearch",
            "todowrite",
            "question",
            "external_directory",
            "skill",
            "lsp",
            "*mcp*",
        ),
    ),
    "branch-plan-task.md": ("disallowedTools", "mcp__github", ("*mcp*",)),
}

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FIELD_RE = re.compile(r"^(?P<key>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*?)\s*$")
_PERMISSION_ENTRY_RE = re.compile(r"^\s{2}(?P<key>\S+)\s*:\s*(?P<value>\S+)\s*$")


class GateUnrunnable(Exception):
    """Raised when the gate cannot evaluate its own inputs (exit 2)."""


def frontmatter_fields(text: str) -> dict[str, str]:
    """Top-level frontmatter keys of `text`, or an empty mapping when the
    file carries no frontmatter block at all."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}
    fields = {}
    for line in match.group(1).split("\n"):
        field = _FIELD_RE.match(line)
        if field:
            fields[field.group("key")] = field.group("value")
    return fields


def load_permission_specs(repo_root: Path) -> dict[str, dict[str, str] | None]:
    """Import the sync module by path and return its `AGENT_PERMISSION_SPECS`
    as a mapping. Raises `GateUnrunnable` rather than returning an empty
    result, so a missing or renamed module is never read as "no agents to
    check"."""
    module_path = repo_root / SYNC_MODULE_PATH
    spec = importlib.util.spec_from_file_location("gitapex_sync_opencode", module_path)
    if spec is None or spec.loader is None:
        raise GateUnrunnable(f"cannot load {SYNC_MODULE_PATH} as a module")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, SyntaxError, ImportError) as error:
        raise GateUnrunnable(f"cannot import {SYNC_MODULE_PATH}: {error}") from error
    specs = getattr(module, "AGENT_PERMISSION_SPECS", None)
    if specs is None:
        raise GateUnrunnable(f"{SYNC_MODULE_PATH} exposes no AGENT_PERMISSION_SPECS")
    return dict(specs)


def generated_permission_keys(text: str) -> set[str]:
    """The permission keys a generated OpenCode copy denies. Reads the
    `permission:` block's own two-space-indented entries, so a key nested
    under some other frontmatter mapping is not miscounted."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return set()
    keys: set[str] = set()
    inside = False
    for line in match.group(1).split("\n"):
        if line.rstrip() == "permission:":
            inside = True
            continue
        if inside:
            entry = _PERMISSION_ENTRY_RE.match(line)
            if entry is None:
                break
            if entry.group("value") == "deny":
                keys.add(entry.group("key"))
    return keys


def evaluate(repo_root: Path) -> list[tuple[str, str, bool, str]]:
    """Return one `(check, subject, passed, detail)` row per graded fact."""
    specs = load_permission_specs(repo_root)
    rows: list[tuple[str, str, bool, str]] = []
    sources = sorted((repo_root / AGENTS_SRC_DIR).glob("*.md"))
    if not sources:
        raise GateUnrunnable(f"no {AGENTS_SRC_DIR}/*.md definitions found")

    for source in sources:
        name = source.name
        fields = frontmatter_fields(source.read_text(encoding="utf-8"))
        declared = [key for key in BOUNDARY_KEYS if key in fields]
        rows.append(
            (
                "boundary-declared",
                name,
                bool(declared),
                ", ".join(declared) if declared else "declares neither tools nor disallowedTools",
            )
        )

        permission = specs.get(name)
        rows.append(
            (
                "mapping-present",
                name,
                bool(permission),
                "mapped" if permission else "synced with no permission mapping",
            )
        )

        expected = EXPECTED_BOUNDARIES.get(name)
        if expected is None:
            rows.append(("mapping-equivalent", name, False, "no row in EXPECTED_BOUNDARIES"))
            continue
        expected_key, expected_value, expected_denials = expected
        problems = []
        if fields.get(expected_key) != expected_value:
            problems.append(
                f"source declares {expected_key}={fields.get(expected_key)!r}, table expects {expected_value!r}"
            )
        mapped_denials = {key for key, value in (permission or {}).items() if value == "deny"}
        if mapped_denials != set(expected_denials):
            problems.append(f"mapping denies {sorted(mapped_denials)}, table expects {sorted(expected_denials)}")
        generated = repo_root / OPENCODE_AGENTS_DIR / name
        if generated.is_file():
            generated_keys = generated_permission_keys(generated.read_text(encoding="utf-8"))
            if generated_keys != set(expected_denials):
                problems.append(
                    f"generated copy denies {sorted(generated_keys)}, table expects {sorted(expected_denials)}"
                )
        rows.append(
            (
                "mapping-equivalent",
                name,
                not problems,
                "; ".join(problems) if problems else "source, table and generated copy agree",
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root to check.")
    args = parser.parse_args(argv)
    try:
        rows = evaluate(args.repo_root)
    except GateUnrunnable as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    failures = [row for row in rows if not row[2]]
    for check, subject, passed, detail in rows:
        print(f"{'PASS' if passed else 'FAIL'}  {check}  {subject}: {detail}")
    if failures:
        print(f"\nFAIL: {len(failures)} of {len(rows)} tool-boundary parity check(s) failed.")
        return 1
    print(f"\nPASS: all {len(rows)} tool-boundary parity check(s) passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

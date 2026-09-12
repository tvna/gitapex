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
   expectation table, and the OpenCode copy the sync script's own
   generator actually emits all agree. The third leg RENDERS that copy
   rather than reading `.opencode/agents/<name>.md` from disk: `.gitignore`
   excludes that directory, so the file is absent in every clone and every
   CI checkout. An earlier version read it, found nothing, skipped the leg
   silently, and still reported agreement about a file it had never
   opened.

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
itself could not run (the sync module is missing, fails at import, or
does not expose `AGENT_PERMISSION_SPECS` and `_render_agent_copy`) --
never a silent pass.

**What this gate does not claim.** All three checks compare in-repo
artifacts to each other, so a commit that widens a boundary on the source
AND in the table AND in the mapping passes cleanly. It grades that the
boundary is reproduced, never that the boundary is strong enough; that
judgement is axis B4's and a reviewer's.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Where the Claude-canonical definitions live, and where the generator
# that produces the OpenCode copies lives. Restated here as paths rather
# than imported, so a sync-module import failure still yields the exit-2
# diagnostic below instead of an AttributeError.
AGENTS_SRC_DIR = Path("agents")
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
# Anchored at column 0: a key must start the line. A line that does not is
# a CONTINUATION of the key above, and is joined onto it rather than
# dropped -- the fail-open this gate exists to prevent otherwise reads a
# widened boundary as unchanged. `tools: Read, Grep, Glob` followed by
# `  , Bash` parsed first-line-only as `Read, Grep, Glob`, byte-identical
# to EXPECTED_BOUNDARIES' own value, so all three legs reported agreement
# about a boundary that had gained a tool. The same joining, for the same
# reason, in `skills/evaluating-context-channel-maturity/scripts/
# gitapex_check_channel_shape.py`'s own `frontmatter_values`, whose tests
# carry the defeat case that proved a first-line-only parser defeatable.
_FIELD_RE = re.compile(r"\A(?P<key>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*?)\s*$")
_PERMISSION_ENTRY_RE = re.compile(r"^\s{2}(?P<key>\S+)\s*:\s*(?P<value>\S+)\s*$")


class GateUnrunnable(Exception):
    """Raised when the gate cannot evaluate its own inputs (exit 2)."""


def frontmatter_fields(text: str) -> dict[str, str]:
    """Top-level frontmatter keys of `text`, or an empty mapping when the
    file carries no frontmatter block at all.

    A value continued across lines is joined with a single space and read
    whole; see `_FIELD_RE`'s own comment for the fail-open that a
    first-line-only read leaves open. Values are not YAML-decoded -- this
    gate compares a declaration against a table of declarations, and both
    sides are compared as the text the file actually carries.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}
    parts: dict[str, list[str]] = {}
    current: str | None = None
    for line in match.group(1).split("\n"):
        field = _FIELD_RE.match(line)
        if field:
            current = field.group("key")
            parts.setdefault(current, []).append(field.group("value"))
        elif current is not None and line.strip():
            parts[current].append(line.strip())
    return {key: " ".join(value).strip() for key, value in parts.items()}


def load_sync_module(repo_root: Path) -> tuple[dict[str, dict[str, str] | None], Callable[..., str]]:
    """Import the sync module by path and return `(AGENT_PERMISSION_SPECS
    as a mapping, its own _render_agent_copy)`.

    Raises `GateUnrunnable` rather than returning an empty result, so a
    missing or renamed module is never read as "no agents to check". The
    renderer is returned because check 3's third leg calls it: see
    `evaluate`.
    """
    module_path = repo_root / SYNC_MODULE_PATH
    spec = importlib.util.spec_from_file_location("gitapex_sync_opencode", module_path)
    if spec is None or spec.loader is None:
        raise GateUnrunnable(f"cannot load {SYNC_MODULE_PATH} as a module")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    # Deliberately broad. The narrower (OSError, SyntaxError, ImportError)
    # this started as let every other module-level failure -- NameError,
    # TypeError, a raised ValueError -- escape as a traceback, which
    # mis-signals the exit-2 contract this gate documents. SystemExit is
    # caught separately because it derives from BaseException: a
    # module-level sys.exit(0) would otherwise terminate this gate with
    # status 0 and not a single check row printed, a fully silent pass.
    except SystemExit as error:
        raise GateUnrunnable(f"{SYNC_MODULE_PATH} called sys.exit at import time: {error}") from error
    except Exception as error:
        raise GateUnrunnable(f"cannot import {SYNC_MODULE_PATH}: {error!r}") from error
    specs = getattr(module, "AGENT_PERMISSION_SPECS", None)
    if specs is None:
        raise GateUnrunnable(f"{SYNC_MODULE_PATH} exposes no AGENT_PERMISSION_SPECS")
    renderer = getattr(module, "_render_agent_copy", None)
    if renderer is None:
        raise GateUnrunnable(f"{SYNC_MODULE_PATH} exposes no _render_agent_copy")
    return dict(specs), renderer


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


def read_checked(path: Path) -> str:
    """Read one input as UTF-8, or raise `GateUnrunnable`.

    An agent definition or generated copy that cannot be read or decoded
    is not a boundary failure -- it is the gate losing the ability to
    judge one at all, which is exit 2, never a FAIL row and never a
    silent skip. Catching `UnicodeDecodeError` at the read boundary and
    re-raising this script's own typed error is the shape
    `.github/scripts/gitapex_detect_changed_gate_scripts.py` already
    uses.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise GateUnrunnable(f"cannot read {path}: {error}") from error


def evaluate(repo_root: Path) -> list[tuple[str, str, bool, str]]:
    """Return one `(check, subject, passed, detail)` row per graded fact."""
    specs, render = load_sync_module(repo_root)
    rows: list[tuple[str, str, bool, str]] = []
    sources = sorted((repo_root / AGENTS_SRC_DIR).glob("*.md"))
    if not sources:
        raise GateUnrunnable(f"no {AGENTS_SRC_DIR}/*.md definitions found")

    # The reverse set difference, checked explicitly: a spec row or a
    # table row naming a file that does not exist produces no source to
    # iterate, so without this it would drift silently forever. The sync
    # script itself only logs a skip line and exits 0.
    # Scoped to the sync module's own table, not to EXPECTED_BOUNDARIES:
    # that constant describes this repository specifically, so grading it
    # against an arbitrary --repo-root would report a false absence for
    # every agent the other tree does not happen to have. A stale row in
    # the constant itself is covered by its own test instead.
    present = {source.name for source in sources}
    for name in sorted(specs):
        if name not in present:
            rows.append(("source-present", name, False, f"named in a registry but absent from {AGENTS_SRC_DIR}/"))

    for source in sources:
        name = source.name
        source_text = read_checked(source)
        fields = frontmatter_fields(source_text)
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
        # A mapping that exists but denies nothing ({"edit": "allow"}) is
        # truthy while reproducing no boundary at all, so this checks for
        # a real denial rather than for presence.
        denials = {key for key, value in (permission or {}).items() if value == "deny"}
        rows.append(
            (
                "mapping-present",
                name,
                bool(denials),
                f"denies {sorted(denials)}" if denials else "synced with no permission mapping that denies anything",
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
        if denials != set(expected_denials):
            problems.append(f"mapping denies {sorted(denials)}, table expects {sorted(expected_denials)}")
        # Third leg: render the OpenCode copy through the sync script's
        # OWN generator and read the permission block it actually emits.
        # An earlier version read .opencode/agents/<name>.md from disk --
        # which .gitignore excludes, so the file is absent in every clone
        # and every CI checkout, the leg silently never ran, and the row
        # still reported that the generated copy agreed, about a file it
        # had not opened. Rendering closes that: it exercises the real
        # artifact-producing path rather than an artifact that is never
        # committed, so a change to the generator's own output shape (a
        # renamed key, a different indent) fails here.
        try:
            rendered = render(source_text, f"{AGENTS_SRC_DIR}/{name}", permission)
        except Exception as error:  # the generator raises on malformed input
            problems.append(f"the sync generator refused this source: {error!r}")
        else:
            rendered_keys = generated_permission_keys(rendered)
            if rendered_keys != set(expected_denials):
                problems.append(
                    f"the generated OpenCode copy denies {sorted(rendered_keys)}, "
                    f"table expects {sorted(expected_denials)}"
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

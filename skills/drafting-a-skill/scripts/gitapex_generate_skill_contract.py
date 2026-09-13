#!/usr/bin/env python3
"""Render a skill's `spec.contract` sidecar block into its `SKILL.md`'s
marker-delimited contract region.

Issue #1965 (foundation-task generator, tracked under parent issue #1964,
alongside `docs/adr/0005-spec-contract-projection.md`). Before this script,
`spec.contract` (`skills/evaluating-skill-quality/references/
skill-metadata.schema.json`'s `$defs/contract`) existed as a declarable-but-
unenforced schema shape: a maintainer could hand-write it in a skill's
`metadata/gitapex.yaml` sidecar, but nothing ever rendered it into that
skill's `SKILL.md`, and nothing caught the two drifting apart. This script
is the one build-time actor ADR 0005 describes: it reads a single skill's
own sidecar, and writes (or, in `--check` mode, diffs) the marker-delimited
region in that same skill's own `SKILL.md` -- never any other file.

**Portability constraint** (issue #1965's own Constraints section,
verbatim): "The generator never reads `.gitapex/ssot.json` or any file
outside the target skill's directory." This script reads exactly two
paths, both inside the one target directory its positional argument names:
`<target>/metadata/gitapex.yaml` and `<target>/SKILL.md`. It writes at most
one: `<target>/SKILL.md`, and only inside the marker region -- the marker
lines themselves are never modified.

**Not a target.** A skill whose sidecar declares no `spec.contract` key at
all (the schema's own field is optional: "a skill with no `spec.contract`
declares no contract yet and is not a generator target -- migration stays
opt-in, one skill at a time", ADR 0005's Decision Outcome) is not something
this script acts on. That is a clean, zero-exit "nothing to do" outcome,
never an error: the script prints a plain "not a target" message and
touches nothing, in either mode.

**Marker pair.** The target `SKILL.md` must contain exactly one
`<!-- gitapex:contract:begin -->` / `<!-- gitapex:contract:end -->` pair.
Zero pairs, more than one `begin` marker, more than one `end` marker, or an
`end` marker preceding its `begin` marker are all failures: this script
never guesses which pair (or which ordering) is the real one, per issue
#1965's own Planned ops ("zero or more than one marker pair fails loudly").

**Rendering.** The six `spec.contract` children render, in schema-property
order, as `## <Heading>` sections: `Precondition`, `Goal`, `Invariants`,
`Gates`, `Escalation`, `Handoff` -- the first five heading strings taken
verbatim from `docs/glossary.md`'s own `Goal`/`Gates`/`Escalation`/
`Handoff`/`Invariants` entries (added by the sibling task that landed those
glossary entries first, so this script's heading strings are fixed only
once that task lands, per this branch's own task-dependency ordering);
`docs/glossary.md` has no dedicated entry for `precondition` (only five of
the schema's six `$defs/contract` children got one), so this script titles
that heading after the schema's own field name instead, following the same
title-casing convention the other five headings already use. See
`render_contract_region`'s own docstring, and each `_render_*` helper
below, for the exact per-block rendering rules (bullet vs. table, the
empty-array `- none` convention, and the two disclosed wording judgment
calls -- the `gates[]` parenthetical and the `handoff` array-field
treatment -- each documented at its own render function).

Two modes, matching the established `--check`/exit-code precedent in
`.github/scripts/gitapex_generate_plugin_manifest.py` and
`.github/scripts/gitapex_generate_skill_eval_status.py`:

- Default (no flags): render the region and rewrite the target `SKILL.md`
  in place.
- `--check`: render in memory and compare against the target `SKILL.md`'s
  current content; exit 1 on any difference (`FAIL: ...`), 0 on an exact
  match (`PASS: ...`). Never writes in this mode.

`import yaml` is guarded exactly per the #1076 pattern already established
in `skills/evaluating-skill-quality/scripts/
gitapex_scan_execution_requirements_drift.py` (lines ~234-261): a bare
`SystemExit` raised while this module is merely *imported* (e.g. this
script's own co-located `test_gitapex_generate_skill_contract.py` doing
`import gitapex_generate_skill_contract as generator`) is not a plain
`Exception`, so a test-collection or a plain-import caller must see a
normal `ModuleNotFoundError` instead -- the friendly `SystemExit(2)`
message is reserved for the documented CLI entry point only.

Not yet wired into any deterministic gate: the `skill-contract-drift`
`.gitapex/ssot.json` entry ADR 0005's own Confirmation section names is
prospective work tracked separately (issue #1965's own Task 5, downstream
of this one). Zero real `skills/*/` directories declare `spec.contract` as
of this script landing (a prototype-stage feature, migrated in one at a
time), so this script's own live-repository behavior against every real
skill today is the uniform "not a target" outcome -- proven instead by the
synthetic fixtures in this file's own co-located test module.

Usage:
  python3 gitapex_generate_skill_contract.py <skills/NAME>
  python3 gitapex_generate_skill_contract.py --check <skills/NAME>

Exit code: 0 on success (a write, a `--check` match, or a "not a target"
skip), 1 on any generation failure (including `--check` drift) reported as
`FAIL: ...`, 2 if PyYAML is missing from the import path.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import cast

try:
    import yaml
except ModuleNotFoundError as error:
    # why-not(#1076): only convert to SystemExit when run as a script. A
    # bare SystemExit raised while this module is merely *imported* (e.g.
    # this file's own co-located test module doing
    # `import gitapex_generate_skill_contract as generator`) is not a plain
    # Exception, so a plain import or a pytest-collection caller could not
    # catch it cleanly -- see gitapex_scan_execution_requirements_drift.py's
    # own identical guard (lines ~234-261) for the live-verified INTERNALERROR
    # failure mode this avoids. error.name narrows further to "PyYAML itself
    # is absent": a broken/partial install raises this same exception type
    # with error.name == "yaml.<submodule>", not "yaml", and this guard's
    # remediation ("uv sync --group dev") would not fix a corrupted install,
    # so that case re-raises unmodified rather than being misdiagnosed.
    if error.name != "yaml" or __name__ != "__main__":
        raise
    print(
        f"error: {error}. This script requires PyYAML, which is not on "
        "the import path -- install the dev dependency group first: "
        "uv sync --group dev",
        file=sys.stderr,
    )
    raise SystemExit(2) from error

# The one sidecar path this generator may read, relative to the target
# skill directory -- the portability constraint's other half
# (<target>/SKILL.md) has no named constant since it is used exactly once,
# inside compute_rendered_skill_md, with no second caller to keep in sync.
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"

# The marker pair a target SKILL.md must contain exactly one of (module
# docstring's own "Marker pair" section) -- named constants rather than
# inline literals so _locate_markers and every test fixture in this
# script's own co-located test module share one spelling, never two
# independently-typed copies that could silently drift apart.
BEGIN_MARKER = "<!-- gitapex:contract:begin -->"
END_MARKER = "<!-- gitapex:contract:end -->"  # BEGIN_MARKER's own matching close, see the comment block above


class GenerationError(Exception):
    """A real failure this generator cannot recover from on its own: the
    sidecar or SKILL.md could not be read/parsed, a declared spec.contract
    is structurally malformed, the marker pair is missing/duplicated/
    out of order, or the rendered region would violate the ASCII-only
    rendering rule. Converted to a `FAIL: ...` message and a non-zero exit
    in main() -- never an uncaught traceback. Deliberately distinct from
    "not a target" (a skill with no spec.contract declared at all), which
    is a clean, zero-exit outcome, not an error -- see
    load_sidecar_contract's own docstring."""


def _read_utf8_text(path: Path) -> str:
    """Read `path` as UTF-8 text, or raise GenerationError naming `path`
    and the failure -- the one read boundary every file this generator
    touches goes through, mirroring the identical helper already
    established in `.github/scripts/gitapex_generate_plugin_manifest.py`
    and `gitapex_generate_skill_eval_status.py`."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise GenerationError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise GenerationError(f"{path}: is not valid UTF-8: {error}") from error


# ---------------------------------------------------------------------------
# Sidecar read + light structural validation (Boundary Discipline: validate
# once here, so every _render_* helper below can trust its input shape
# without re-checking).
# ---------------------------------------------------------------------------


def _require_dict(value: object, sidecar_path: Path, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GenerationError(f"{sidecar_path}: {what} must be a mapping, got {type(value).__name__}")
    return value


def _require_nonempty_str(value: object, sidecar_path: Path, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise GenerationError(f"{sidecar_path}: {what} must be a non-empty string, got {value!r}")
    return value


def _require_list(value: object, sidecar_path: Path, what: str) -> list[object]:
    """None (the key absent) reads as an empty list -- spec.contract's own
    array children (precondition/invariants/gates/escalation) and
    goal.constraints/handoff.inline/handoff.optional are all optional per
    the schema, and an absent optional list means "none declared", the
    same convention skill-metadata.schema.json already documents for
    spec.skillDependencies.requires/relatedTo."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise GenerationError(f"{sidecar_path}: {what} must be a list, got {type(value).__name__}")
    return value


def _validate_contract(contract: dict[str, object], sidecar_path: Path) -> None:
    """Enough structural validation for every _render_* helper below to
    index the contract's fields directly, without re-deriving the same
    presence/type checks at each call site. Full schema conformance
    (additionalProperties, enum membership, string length/pattern limits)
    stays skill-metadata.schema.json's own job, enforced elsewhere by
    gitapex_scan_skill_metadata_schema.py's jsonschema validator -- this
    generator trusts that gate already ran, but still fails loudly with a
    clear GenerationError rather than crashing with a raw KeyError/TypeError
    on a sidecar that somehow reached it out of schema (AGENTS.md ch.4:
    "if a human could plausibly cause it, handle it")."""
    goal = _require_dict(contract.get("goal"), sidecar_path, "spec.contract.goal")
    _require_nonempty_str(goal.get("endState"), sidecar_path, "spec.contract.goal.endState")
    _require_nonempty_str(goal.get("check"), sidecar_path, "spec.contract.goal.check")
    for constraint in _require_list(goal.get("constraints"), sidecar_path, "spec.contract.goal.constraints"):
        _require_nonempty_str(constraint, sidecar_path, "spec.contract.goal.constraints[]")

    handoff = _require_dict(contract.get("handoff"), sidecar_path, "spec.contract.handoff")
    next_block = _require_dict(handoff.get("next"), sidecar_path, "spec.contract.handoff.next")
    _require_nonempty_str(next_block.get("skill"), sidecar_path, "spec.contract.handoff.next.skill")
    for fallback_field in ("fallback", "carries"):
        value = next_block.get(fallback_field)
        if value is not None:
            _require_nonempty_str(value, sidecar_path, f"spec.contract.handoff.next.{fallback_field}")
    for list_field in ("inline", "optional"):
        for name in _require_list(handoff.get(list_field), sidecar_path, f"spec.contract.handoff.{list_field}"):
            _require_nonempty_str(name, sidecar_path, f"spec.contract.handoff.{list_field}[]")
    if handoff.get("downstream") is not None:
        _require_nonempty_str(handoff.get("downstream"), sidecar_path, "spec.contract.handoff.downstream")

    for record in _require_list(contract.get("precondition"), sidecar_path, "spec.contract.precondition"):
        item = _require_dict(record, sidecar_path, "spec.contract.precondition[]")
        _require_nonempty_str(item.get("id"), sidecar_path, "spec.contract.precondition[].id")
        _require_nonempty_str(item.get("check"), sidecar_path, "spec.contract.precondition[].check")
        _require_nonempty_str(item.get("onFail"), sidecar_path, "spec.contract.precondition[].onFail")

    for record in _require_list(contract.get("invariants"), sidecar_path, "spec.contract.invariants"):
        item = _require_dict(record, sidecar_path, "spec.contract.invariants[]")
        _require_nonempty_str(item.get("text"), sidecar_path, "spec.contract.invariants[].text")
        gate = item.get("gate")
        if gate is not None and not isinstance(gate, str):
            raise GenerationError(
                f"{sidecar_path}: spec.contract.invariants[].gate must be a string or null, got {type(gate).__name__}"
            )

    for record in _require_list(contract.get("gates"), sidecar_path, "spec.contract.gates"):
        item = _require_dict(record, sidecar_path, "spec.contract.gates[]")
        _require_nonempty_str(item.get("id"), sidecar_path, "spec.contract.gates[].id")
        _require_nonempty_str(item.get("plane"), sidecar_path, "spec.contract.gates[].plane")
        if not isinstance(item.get("shipped"), bool):
            raise GenerationError(
                f"{sidecar_path}: spec.contract.gates[].shipped must be a boolean, "
                f"got {type(item.get('shipped')).__name__}"
            )

    for record in _require_list(contract.get("escalation"), sidecar_path, "spec.contract.escalation"):
        item = _require_dict(record, sidecar_path, "spec.contract.escalation[]")
        _require_nonempty_str(item.get("when"), sidecar_path, "spec.contract.escalation[].when")
        _require_nonempty_str(item.get("to"), sidecar_path, "spec.contract.escalation[].to")


def load_sidecar_contract(skill_dir: Path) -> dict[str, object] | None:
    """The parsed `spec.contract` mapping from `<skill_dir>/metadata/
    gitapex.yaml`, or None when this skill declares no contract at all --
    the "not a target" outcome (module docstring's own section), which
    main() reports as a clean zero-exit skip, never an error. Raises
    GenerationError for every other failure: the sidecar cannot be
    read/parsed, its root is not a mapping, or a declared spec.contract is
    structurally malformed (see _validate_contract)."""
    sidecar_path = skill_dir / SIDECAR_RELATIVE_PATH
    text = _read_utf8_text(sidecar_path)
    try:
        manifest = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise GenerationError(f"{sidecar_path}: is not valid YAML: {error}") from error
    if not isinstance(manifest, dict):
        raise GenerationError(f"{sidecar_path}: must parse to a YAML mapping, got {type(manifest).__name__}")
    spec = manifest.get("spec")
    if not isinstance(spec, dict) or "contract" not in spec:
        return None
    contract = _require_dict(spec["contract"], sidecar_path, "spec.contract")
    _validate_contract(contract, sidecar_path)
    return contract


# ---------------------------------------------------------------------------
# Rendering -- one function per spec.contract child, in schema-property
# order (precondition, goal, invariants, gates, escalation, handoff), the
# same order the generated headings render in.
# ---------------------------------------------------------------------------


def _render_precondition(records: list[dict[str, object]]) -> str:
    lines = ["## Precondition", ""]
    if not records:
        lines.append("- none")
    else:
        for item in records:
            lines.append(f"- {item['id']}: {item['check']} (onFail: {item['onFail']})")
    return "\n".join(lines)


def _render_goal(goal: dict[str, object]) -> str:
    lines = [
        "## Goal",
        "",
        f"- End state: {goal['endState']}",
        f"- Check: {goal['check']}",
    ]
    constraints = cast("list[object]", goal.get("constraints") or [])
    for constraint in constraints:
        lines.append(f"- Constraint: {constraint}")
    return "\n".join(lines)


def _render_invariants(records: list[dict[str, object]]) -> str:
    """Per-record suffix: `(gate: <id>)` when `gate` is a non-null string,
    `(prose-only)` when `gate` is null -- the Branch Plan's own required
    format, matched verbatim (no wording judgment call needed here, unlike
    _render_gates below)."""
    lines = ["## Invariants", ""]
    if not records:
        lines.append("- none")
    else:
        for item in records:
            gate = item.get("gate")
            suffix = f"gate: {gate}" if isinstance(gate, str) else "prose-only"
            lines.append(f"- {item['text']} ({suffix})")
    return "\n".join(lines)


def _render_gates(records: list[dict[str, object]]) -> str:
    """Per-record format: `- <id> (<plane>, <state>)`.

    Wording judgment call (disclosed per this task's own instructions): the
    Branch Plan's own draft text for the parenthetical's second half was
    "shipped with the plugin" (true) / "gitapex repository only" (false) --
    a portability/distribution axis. But
    skill-metadata.schema.json's own `$defs/contractGate.properties.shipped`
    documents a different axis: "Whether this gate is already enforcing
    (true) or still only declared/planned (false)". Rendering the Branch
    Plan's literal words here would misrepresent what the field actually
    means (a gate can ship entirely inside the plugin package while still
    being merely declared/planned, or vice versa -- the two axes are
    independent). This renders "already enforcing" / "not yet enforcing"
    instead, preserving the same required two-state distinction while
    matching the schema's own documented semantics. (This reading is also
    consistent with, not contradicted by, issue #1965's own downstream
    Task 6 cross-field rule tying `shipped: true` to a hook-plane gate
    (pretooluse/posttooluse/stop): a hook-plane gate structurally blocks
    execution in real time -- "already enforcing" in the strongest sense --
    while a ci/local-plane gate is not yet wired to block that way, even if
    it already runs.)"""
    lines = ["## Gates", ""]
    if not records:
        lines.append("- none")
    else:
        for item in records:
            state = "already enforcing" if item["shipped"] else "not yet enforcing"
            lines.append(f"- {item['id']} ({item['plane']}, {state})")
    return "\n".join(lines)


def _render_escalation(records: list[dict[str, object]]) -> str:
    """Bullet list (`- <when> -> <to>`) for fewer than 3 records; a plain,
    unpadded Markdown table (`| When | To |`) for 3 or more -- the Branch
    Plan's own stated threshold. An empty list renders `- none` (the same
    convention as every other array block), which is also correctly a
    bullet-list-shaped outcome since 0 < 3."""
    lines = ["## Escalation", ""]
    if not records:
        lines.append("- none")
    elif len(records) >= 3:
        lines.append("| When | To |")
        lines.append("| --- | --- |")
        for item in records:
            lines.append(f"| {item['when']} | {item['to']} |")
    else:
        for item in records:
            lines.append(f"- {item['when']} -> {item['to']}")
    return "\n".join(lines)


def _render_handoff(handoff: dict[str, object]) -> str:
    """Singular-block bullet lines, one field per line (module docstring's
    own rendering rules): the required `next.skill` always renders (with
    an optional `(fallback: ...)` parenthetical when `next.fallback` is
    declared); `next.carries`/`downstream` each render their own bullet
    only when declared; `inline`/`optional` each render one comma-joined
    bullet only when non-empty.

    Wording judgment call (disclosed per this task's own instructions,
    the same as _render_gates above): the Branch Plan's rendering rules
    specify the four array blocks' (Precondition/Invariants/Gates/
    Escalation) own empty-array `- none` convention, but say nothing about
    `handoff.inline`/`handoff.optional` -- both are arrays, but nested
    inside `handoff`, a *singular* block ("goal, handoff render one bullet
    line each"), not one of the four dedicated array blocks that
    convention names. Treated here the same way `goal.constraints`
    already is (module docstring's own singular-block rule, "a bullet per
    constraint if any"): an empty/absent list contributes zero bullets,
    not a `- none` placeholder line -- a singular block's own optional
    sub-fields stay symmetric with each other (skip when absent) rather
    than borrowing the array-block convention for only two of its several
    optional fields."""
    lines = ["## Handoff", ""]
    # Cast, not a runtime re-check: _validate_contract already guaranteed
    # handoff["next"] is a dict before render_contract_region ever calls
    # this function (Boundary Discipline -- validate once, trust after).
    next_block = cast("dict[str, object]", handoff["next"])
    skill = next_block["skill"]
    fallback = next_block.get("fallback")
    if fallback:
        lines.append(f"- Next: {skill} (fallback: {fallback})")
    else:
        lines.append(f"- Next: {skill}")
    carries = next_block.get("carries")
    if carries:
        lines.append(f"- Carries: {carries}")
    for list_field, label in (("inline", "Inline"), ("optional", "Optional")):
        names = cast("list[object]", handoff.get(list_field) or [])
        if names:
            lines.append(f"- {label}: {', '.join(str(name) for name in names)}")
    downstream = handoff.get("downstream")
    if downstream:
        lines.append(f"- Downstream: {downstream}")
    return "\n".join(lines)


def render_contract_region(contract: dict[str, object]) -> str:
    """The full contract-region text (no leading/trailing blank lines,
    sections joined by exactly one blank line each) -- what sits strictly
    between the begin/end marker lines once apply_region wraps it. Never
    re-echoes the sidecar's own YAML verbatim: every field is routed
    through one of the six _render_* helpers above, each producing plain
    Markdown bullets or (Escalation only, 3+ records) a plain table, per
    the module docstring's own rendering rules. No line wrapping is ever
    applied to a rendered line, however long."""
    # Every cast below is a type-narrowing, not a runtime re-check:
    # load_sidecar_contract always runs _validate_contract on `contract`
    # before returning it, so every field these six helpers read is already
    # known-shaped by the time render_contract_region ever sees it
    # (Boundary Discipline -- validate once, trust after).
    sections = [
        _render_precondition(cast("list[dict[str, object]]", contract.get("precondition") or [])),
        _render_goal(cast("dict[str, object]", contract["goal"])),
        _render_invariants(cast("list[dict[str, object]]", contract.get("invariants") or [])),
        _render_gates(cast("list[dict[str, object]]", contract.get("gates") or [])),
        _render_escalation(cast("list[dict[str, object]]", contract.get("escalation") or [])),
        _render_handoff(cast("dict[str, object]", contract["handoff"])),
    ]
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Marker location + region replacement
# ---------------------------------------------------------------------------


def _locate_markers(text: str, skill_md_path: Path) -> tuple[int, int]:
    """Returns (region_start, region_end): region_start is the index right
    after the begin marker's own line (its own trailing newline included),
    region_end is the index at the start of the end marker's own line --
    exactly the substring apply_region replaces. Raises GenerationError
    (module docstring's own "Marker pair" section) when either marker does
    not appear exactly once, or when the end marker precedes the begin
    marker -- this generator never guesses which pair, or which ordering,
    is the real one."""
    begin_positions = [match.start() for match in re.finditer(re.escape(BEGIN_MARKER), text)]
    end_positions = [match.start() for match in re.finditer(re.escape(END_MARKER), text)]
    if len(begin_positions) != 1 or len(end_positions) != 1:
        raise GenerationError(
            f"{skill_md_path}: expected exactly one {BEGIN_MARKER!r} marker and exactly one "
            f"{END_MARKER!r} marker, found {len(begin_positions)} begin marker(s) and "
            f"{len(end_positions)} end marker(s)"
        )
    begin_pos, end_pos = begin_positions[0], end_positions[0]
    if end_pos < begin_pos:
        raise GenerationError(f"{skill_md_path}: the {END_MARKER!r} marker appears before the {BEGIN_MARKER!r} marker")
    begin_line_end = text.index("\n", begin_pos) + 1
    end_line_start = text.rfind("\n", 0, end_pos) + 1
    return begin_line_end, end_line_start


def apply_region(text: str, region_text: str, skill_md_path: Path) -> str:
    """`text` (a full SKILL.md's current content) with the marker-delimited
    region replaced by `region_text`, wrapped in exactly one blank line on
    each side -- the marker lines themselves are never touched."""
    region_start, region_end = _locate_markers(text, skill_md_path)
    return text[:region_start] + "\n" + region_text + "\n\n" + text[region_end:]


def compute_rendered_skill_md(skill_dir: Path) -> tuple[str, str] | None:
    """(rendered_full_text, original_full_text) for `<skill_dir>/SKILL.md`,
    or None when this skill is not a generator target (no spec.contract
    declared -- load_sidecar_contract's own docstring). SKILL.md is
    deliberately not read at all in the not-a-target case: the sidecar
    alone already answers the question, and this generator reads no more
    of the target directory than each outcome actually needs. Raises
    GenerationError for every other failure (sidecar/SKILL.md unreadable,
    malformed contract, marker-pair problems, a non-ASCII rendered
    region)."""
    contract = load_sidecar_contract(skill_dir)
    if contract is None:
        return None
    skill_md_path = skill_dir / "SKILL.md"
    original_text = _read_utf8_text(skill_md_path)
    region_text = render_contract_region(contract)
    if not region_text.isascii():
        raise GenerationError(f"{skill_md_path}: the rendered contract region contains a non-ASCII character")
    rendered_text = apply_region(original_text, region_text, skill_md_path)
    return rendered_text, original_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "skill_dir",
        help="Path to one skills/NAME directory (e.g. skills/drafting-a-skill). "
        "Only metadata/gitapex.yaml and SKILL.md under this exact directory are ever read.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Diff mode: render in memory and compare against the target SKILL.md's "
        "current contract region; exit 1 on any drift, 0 on an exact match. Never writes.",
    )
    args = parser.parse_args(argv)
    skill_dir = Path(args.skill_dir)

    try:
        outcome = compute_rendered_skill_md(skill_dir)
    except GenerationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if outcome is None:
        print(f"not a target: {skill_dir} declares no spec.contract in its {SIDECAR_RELATIVE_PATH} sidecar")
        return 0

    rendered_text, original_text = outcome
    skill_md_path = skill_dir / "SKILL.md"

    if args.check:
        if rendered_text != original_text:
            print(
                f"FAIL: {skill_md_path} contract region is stale -- a fresh regeneration "
                "differs from the committed content. Re-run without --check to regenerate, "
                "then commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"PASS: {skill_md_path} matches a fresh regeneration")
        return 0

    try:
        skill_md_path.write_text(rendered_text, encoding="utf-8")
    except OSError as error:
        print(f"FAIL: {skill_md_path}: cannot be written: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {skill_md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tests for the co-located `gitapex_generate_skill_contract.py`
(issue #1965's Task 3 foundation-task generator).

Every fixture here is a synthetic `tmp_path` skill directory -- never a real
`skills/*` directory, since zero real skills declare `spec.contract` as of
this module landing (a prototype-stage feature, migrated in one skill at a
time; see the generator's own module docstring). Golden-text assertions
pin the exact rendering rules (heading order/wording, per-block bullet vs.
table format, the two disclosed wording judgment calls) byte-for-byte, not
just structurally, so a future rendering change is a deliberate, reviewed
diff to this file, not a silent drift.
"""

from __future__ import annotations

import copy
import pathlib
from typing import Any

import gitapex_generate_skill_contract as generator
import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixture helpers -- build a synthetic skills/NAME directory under tmp_path,
# never a real one.
# ---------------------------------------------------------------------------

_SKILL_MD_TEMPLATE = """---
name: {name}
description: A synthetic test fixture skill, not a real gitapex skill.
---

# {name}

Some intro prose the generator must never touch.

{begin_line}

{region}

{end_line}

Some trailing prose the generator must never touch.
"""


def _write_sidecar(skill_dir: pathlib.Path, contract: dict[str, object] | None, *, name: str | None = None) -> None:
    manifest: dict[str, object] = {
        "apiVersion": "gitapex.io/v1alpha1",
        "kind": "SkillMetadata",
        "metadata": {"name": name or skill_dir.name},
        "spec": {"portability": "Portable", "capabilityAssumption": "Broad"},
    }
    if contract is not None:
        spec = manifest["spec"]
        assert isinstance(spec, dict)
        spec["contract"] = contract
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "gitapex.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def _write_skill_md(
    skill_dir: pathlib.Path,
    *,
    region: str = "OLD REGION CONTENT",
    begin_line: str = generator.BEGIN_MARKER,
    end_line: str = generator.END_MARKER,
) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = _SKILL_MD_TEMPLATE.format(name=skill_dir.name, begin_line=begin_line, region=region, end_line=end_line)
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")


def _make_skill(
    tmp_path: pathlib.Path,
    name: str,
    contract: dict[str, object] | None,
    **skill_md_kwargs: Any,
) -> pathlib.Path:
    skill_dir = tmp_path / "skills" / name
    _write_sidecar(skill_dir, contract, name=name)
    _write_skill_md(skill_dir, **skill_md_kwargs)
    return skill_dir


# ---------------------------------------------------------------------------
# A full, realistic spec.contract fixture -- all six blocks populated,
# similar in spirit to _VALID_CONTRACT in
# tests/test_gitapex_scan_skill_metadata_schema.py.
# ---------------------------------------------------------------------------

_FULL_CONTRACT: dict[str, Any] = {
    "precondition": [
        {
            "id": "branch-checked-out",
            "check": "the shared plan branch is checked out at BASE",
            "onFail": "escalate",
        }
    ],
    "goal": {
        "endState": "the ACM row's planned ops are implemented and tested",
        "check": "pytest and the local preflight gate both pass",
        "constraints": ["touch only the files the task record names"],
    },
    "invariants": [
        {"text": "the lifecycle block stays runtime-unread", "gate": None},
        {"text": "never push to a shared branch without review", "gate": "subagent-stop-verification"},
    ],
    "gates": [
        {"id": "subagent-stop-verification", "plane": "stop", "shipped": True},
        {"id": "skill-contract-drift", "plane": "ci", "shipped": False},
    ],
    "escalation": [
        {"when": "verification fails twice", "to": "human-operator"},
    ],
    "handoff": {
        "next": {
            "skill": "drafting-a-pr-to-merge",
            "fallback": "stop-and-replan",
            "carries": "the merged branch and its event log",
        },
        "inline": ["merge-retrospective"],
        "optional": ["outward-artifact-preflight"],
        "downstream": "the opened pull request",
    },
}

_EXPECTED_FULL_REGION = (
    "## Precondition\n"
    "\n"
    "- branch-checked-out: the shared plan branch is checked out at BASE (onFail: escalate)\n"
    "\n"
    "## Goal\n"
    "\n"
    "- End state: the ACM row's planned ops are implemented and tested\n"
    "- Check: pytest and the local preflight gate both pass\n"
    "- Constraint: touch only the files the task record names\n"
    "\n"
    "## Invariants\n"
    "\n"
    "- the lifecycle block stays runtime-unread (prose-only)\n"
    "- never push to a shared branch without review (gate: subagent-stop-verification)\n"
    "\n"
    "## Gates\n"
    "\n"
    "- subagent-stop-verification (stop, shipped with the plugin)\n"
    "- skill-contract-drift (ci, gitapex repository only)\n"
    "\n"
    "## Escalation\n"
    "\n"
    "- verification fails twice -> human-operator\n"
    "\n"
    "## Handoff\n"
    "\n"
    "- Next: drafting-a-pr-to-merge (fallback: stop-and-replan)\n"
    "- Carries: the merged branch and its event log\n"
    "- Inline: merge-retrospective\n"
    "- Optional: outward-artifact-preflight\n"
    "- Downstream: the opened pull request"
)


def _copy_full_contract() -> dict[str, Any]:
    return copy.deepcopy(_FULL_CONTRACT)


# ---------------------------------------------------------------------------
# Golden-text: render_contract_region
# ---------------------------------------------------------------------------


def test_render_contract_region_full_fixture_matches_golden_text() -> None:
    assert generator.render_contract_region(_FULL_CONTRACT) == _EXPECTED_FULL_REGION


def test_render_contract_region_never_echoes_raw_yaml() -> None:
    """The rendered region must be routed entirely through the bullet/table
    format -- never a fenced YAML block re-echoing the sidecar verbatim."""
    rendered = generator.render_contract_region(_FULL_CONTRACT)
    assert "```" not in rendered
    assert "yaml" not in rendered.lower()


def test_render_contract_region_is_ascii_only() -> None:
    assert generator.render_contract_region(_FULL_CONTRACT).isascii()


# ---------------------------------------------------------------------------
# Empty-array rendering ("- none")
# ---------------------------------------------------------------------------


def test_empty_precondition_renders_none_line() -> None:
    contract = _copy_full_contract()
    contract["precondition"] = []
    rendered = generator.render_contract_region(contract)
    assert "## Precondition\n\n- none" in rendered


def test_absent_precondition_key_renders_none_line() -> None:
    contract = _copy_full_contract()
    del contract["precondition"]
    rendered = generator.render_contract_region(contract)
    assert "## Precondition\n\n- none" in rendered


def test_empty_invariants_renders_none_line() -> None:
    contract = _copy_full_contract()
    contract["invariants"] = []
    rendered = generator.render_contract_region(contract)
    assert "## Invariants\n\n- none" in rendered


def test_empty_gates_renders_none_line() -> None:
    contract = _copy_full_contract()
    contract["gates"] = []
    rendered = generator.render_contract_region(contract)
    assert "## Gates\n\n- none" in rendered


def test_empty_escalation_renders_none_line() -> None:
    contract = _copy_full_contract()
    contract["escalation"] = []
    rendered = generator.render_contract_region(contract)
    assert "## Escalation\n\n- none" in rendered


def test_empty_goal_constraints_renders_no_constraint_bullets() -> None:
    """goal is a singular block: an empty constraints list contributes zero
    bullets (not a `- none` placeholder) -- distinct from the four array
    blocks' own empty-array convention."""
    contract = _copy_full_contract()
    contract["goal"] = {"endState": "x", "check": "y", "constraints": []}
    rendered = generator.render_contract_region(contract)
    assert "Constraint" not in rendered


def test_empty_handoff_inline_and_optional_render_no_bullets() -> None:
    """handoff is also a singular block: empty inline/optional lists
    contribute zero bullets, symmetric with goal.constraints above -- the
    disclosed wording judgment call in _render_handoff's own docstring."""
    contract = _copy_full_contract()
    contract["handoff"] = {"next": {"skill": "some-skill"}, "inline": [], "optional": []}
    rendered = generator.render_contract_region(contract)
    assert "Inline" not in rendered
    assert "Optional" not in rendered
    assert "- Next: some-skill\n" in rendered + "\n"


# ---------------------------------------------------------------------------
# Gates / Invariants per-record formatting
# ---------------------------------------------------------------------------


def test_gates_shipped_true_renders_already_enforcing() -> None:
    rendered = generator.render_contract_region(_FULL_CONTRACT)
    assert "- subagent-stop-verification (stop, shipped with the plugin)" in rendered


def test_gates_shipped_false_renders_not_yet_enforcing() -> None:
    rendered = generator.render_contract_region(_FULL_CONTRACT)
    assert "- skill-contract-drift (ci, gitapex repository only)" in rendered


def test_invariants_with_gate_id_renders_gate_suffix() -> None:
    rendered = generator.render_contract_region(_FULL_CONTRACT)
    assert "- never push to a shared branch without review (gate: subagent-stop-verification)" in rendered


def test_invariants_with_null_gate_renders_prose_only_suffix() -> None:
    rendered = generator.render_contract_region(_FULL_CONTRACT)
    assert "- the lifecycle block stays runtime-unread (prose-only)" in rendered


# ---------------------------------------------------------------------------
# Escalation table-vs-list threshold
# ---------------------------------------------------------------------------


def test_escalation_two_records_renders_bullet_list() -> None:
    contract = _copy_full_contract()
    contract["escalation"] = [
        {"when": "a", "to": "human-operator"},
        {"when": "b", "to": "stop-and-replan"},
    ]
    rendered = generator.render_contract_region(contract)
    assert "- a -> human-operator" in rendered
    assert "- b -> stop-and-replan" in rendered
    assert "|" not in rendered.split("## Escalation")[1].split("## Handoff")[0]


def test_escalation_three_records_renders_table() -> None:
    contract = _copy_full_contract()
    contract["escalation"] = [
        {"when": "a", "to": "human-operator"},
        {"when": "b", "to": "stop-and-replan"},
        {"when": "c", "to": "main-thread"},
    ]
    rendered = generator.render_contract_region(contract)
    assert "| When | To |" in rendered
    assert "| --- | --- |" in rendered
    assert "| a | human-operator |" in rendered
    assert "| b | stop-and-replan |" in rendered
    assert "| c | main-thread |" in rendered


def test_escalation_table_has_no_padding_alignment() -> None:
    contract = _copy_full_contract()
    contract["escalation"] = [
        {"when": "short", "to": "x"},
        {"when": "a much much longer when clause", "to": "human-operator"},
        {"when": "c", "to": "y"},
    ]
    rendered = generator.render_contract_region(contract)
    assert "| short | x |" in rendered
    assert "| c | y |" in rendered


# ---------------------------------------------------------------------------
# ASCII-only enforcement
# ---------------------------------------------------------------------------


def test_non_ascii_prose_raises_generation_error(tmp_path: pathlib.Path) -> None:
    contract = _copy_full_contract()
    contract["invariants"] = [{"text": "uses an em dash — not ASCII", "gate": None}]
    skill_dir = _make_skill(tmp_path, "non-ascii-skill", contract)
    with pytest.raises(generator.GenerationError, match="non-ASCII"):
        generator.compute_rendered_skill_md(skill_dir)


# ---------------------------------------------------------------------------
# Malformed contract shape -- fail loudly, never a raw traceback
# ---------------------------------------------------------------------------


def test_missing_goal_raises_generation_error(tmp_path: pathlib.Path) -> None:
    contract = _copy_full_contract()
    del contract["goal"]
    skill_dir = _make_skill(tmp_path, "missing-goal-skill", contract)
    with pytest.raises(generator.GenerationError, match=r"spec.contract.goal"):
        generator.compute_rendered_skill_md(skill_dir)


def test_missing_handoff_next_skill_raises_generation_error(tmp_path: pathlib.Path) -> None:
    contract = _copy_full_contract()
    del contract["handoff"]["next"]["skill"]  # type: ignore[index]
    skill_dir = _make_skill(tmp_path, "missing-handoff-skill-skill", contract)
    with pytest.raises(generator.GenerationError, match=r"spec.contract.handoff.next.skill"):
        generator.compute_rendered_skill_md(skill_dir)


def test_contract_not_a_mapping_raises_generation_error(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "skills" / "bad-contract-shape"
    _write_sidecar(skill_dir, contract=None, name="bad-contract-shape")
    # Overwrite spec.contract with a non-mapping value directly (bypassing
    # _write_sidecar's own dict-shaped `contract` parameter) to exercise the
    # "declared but malformed" path distinct from "absent" (not a target).
    sidecar_path = skill_dir / "metadata" / "gitapex.yaml"
    manifest = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    manifest["spec"]["contract"] = "not a mapping"
    sidecar_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    _write_skill_md(skill_dir)
    with pytest.raises(generator.GenerationError, match=r"spec.contract"):
        generator.compute_rendered_skill_md(skill_dir)


# ---------------------------------------------------------------------------
# Not a target: no spec.contract declared
# ---------------------------------------------------------------------------


def test_no_contract_key_is_not_a_target(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, "no-contract-skill", contract=None)
    assert generator.compute_rendered_skill_md(skill_dir) is None


def test_no_contract_key_main_exits_zero_and_leaves_skill_md_untouched(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill_dir = _make_skill(tmp_path, "no-contract-skill", contract=None)
    skill_md_path = skill_dir / "SKILL.md"
    before_bytes = skill_md_path.read_bytes()
    before_mtime_ns = skill_md_path.stat().st_mtime_ns

    assert generator.main([str(skill_dir)]) == 0
    out = capsys.readouterr().out
    assert "not a target" in out

    assert skill_md_path.read_bytes() == before_bytes
    assert skill_md_path.stat().st_mtime_ns == before_mtime_ns


def test_no_contract_key_check_mode_also_exits_zero_not_a_target(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, "no-contract-skill", contract=None)
    assert generator.main([str(skill_dir), "--check"]) == 0


# ---------------------------------------------------------------------------
# Marker-count failures: 0, 2+ begin, 2+ end, mismatched
# ---------------------------------------------------------------------------


def test_zero_markers_fails_loudly(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, "zero-markers-skill", _copy_full_contract(), begin_line="", end_line="")
    with pytest.raises(generator.GenerationError, match=r"0 begin marker.*0 end marker"):
        generator.compute_rendered_skill_md(skill_dir)


def test_two_begin_markers_fails_loudly(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        "two-begin-skill",
        _copy_full_contract(),
        begin_line=f"{generator.BEGIN_MARKER}\n{generator.BEGIN_MARKER}",
    )
    with pytest.raises(generator.GenerationError, match=r"2 begin marker.*1 end marker"):
        generator.compute_rendered_skill_md(skill_dir)


def test_two_end_markers_fails_loudly(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        "two-end-skill",
        _copy_full_contract(),
        end_line=f"{generator.END_MARKER}\n{generator.END_MARKER}",
    )
    with pytest.raises(generator.GenerationError, match=r"1 begin marker.*2 end marker"):
        generator.compute_rendered_skill_md(skill_dir)


def test_mismatched_two_begin_one_end_fails_loudly(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        "mismatched-skill-a",
        _copy_full_contract(),
        begin_line=f"{generator.BEGIN_MARKER}\n{generator.BEGIN_MARKER}",
    )
    with pytest.raises(generator.GenerationError, match="marker"):
        generator.compute_rendered_skill_md(skill_dir)


def test_mismatched_one_begin_two_end_fails_loudly(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        "mismatched-skill-b",
        _copy_full_contract(),
        end_line=f"{generator.END_MARKER}\n{generator.END_MARKER}",
    )
    with pytest.raises(generator.GenerationError, match="marker"):
        generator.compute_rendered_skill_md(skill_dir)


def test_end_marker_before_begin_marker_fails_loudly(tmp_path: pathlib.Path) -> None:
    """Defensive beyond the required marker-count coverage: an end marker
    physically preceding its begin marker is another shape this generator
    must never guess about."""
    skill_dir = tmp_path / "skills" / "swapped-order-skill"
    _write_sidecar(skill_dir, _copy_full_contract(), name="swapped-order-skill")
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = (
        "---\nname: swapped-order-skill\ndescription: x\n---\n\n"
        f"{generator.END_MARKER}\nold\n{generator.BEGIN_MARKER}\n"
    )
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    with pytest.raises(generator.GenerationError, match="appears before"):
        generator.compute_rendered_skill_md(skill_dir)


def test_main_reports_marker_failure_as_fail_and_exit_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill_dir = _make_skill(tmp_path, "zero-markers-skill", _copy_full_contract(), begin_line="", end_line="")
    assert generator.main([str(skill_dir)]) == 1
    assert "FAIL" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main(): default (write) mode
# ---------------------------------------------------------------------------


def test_main_default_mode_rewrites_skill_md_in_place(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill_dir = _make_skill(tmp_path, "write-mode-skill", _copy_full_contract())
    skill_md_path = skill_dir / "SKILL.md"

    assert generator.main([str(skill_dir)]) == 0
    out = capsys.readouterr().out
    assert "Wrote" in out

    written = skill_md_path.read_text(encoding="utf-8")
    assert "Some intro prose the generator must never touch." in written
    assert "Some trailing prose the generator must never touch." in written
    assert "OLD REGION CONTENT" not in written
    assert _EXPECTED_FULL_REGION in written
    assert f"{generator.BEGIN_MARKER}\n\n{_EXPECTED_FULL_REGION}\n\n{generator.END_MARKER}" in written


def test_main_default_mode_preserves_marker_lines_verbatim(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, "write-mode-skill-2", _copy_full_contract())
    skill_md_path = skill_dir / "SKILL.md"
    generator.main([str(skill_dir)])
    written = skill_md_path.read_text(encoding="utf-8")
    assert written.count(generator.BEGIN_MARKER) == 1
    assert written.count(generator.END_MARKER) == 1


# ---------------------------------------------------------------------------
# main(): --check mode
# ---------------------------------------------------------------------------


def test_main_check_mode_passes_when_region_matches(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _make_skill(tmp_path, "check-pass-skill", _copy_full_contract())
    assert generator.main([str(skill_dir)]) == 0  # write once to make it fresh
    capsys.readouterr()

    assert generator.main([str(skill_dir), "--check"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_check_mode_fails_when_region_is_stale(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _make_skill(tmp_path, "check-fail-skill", _copy_full_contract(), region="THIS IS STALE CONTENT")
    assert generator.main([str(skill_dir), "--check"]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "stale" in err


def test_main_check_mode_never_writes(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, "check-no-write-skill", _copy_full_contract(), region="THIS IS STALE CONTENT")
    skill_md_path = skill_dir / "SKILL.md"
    before = skill_md_path.read_bytes()
    generator.main([str(skill_dir), "--check"])
    assert skill_md_path.read_bytes() == before


# ---------------------------------------------------------------------------
# Missing input files -- real failures, not "not a target"
# ---------------------------------------------------------------------------


def test_missing_sidecar_file_raises_generation_error(tmp_path: pathlib.Path) -> None:
    """A missing metadata/gitapex.yaml is a real read failure, not "not a
    target": every skill in this repository has a sidecar today (the
    schema's own top-level apiVersion/kind/metadata/spec are all required),
    and silently treating an absent one as "nothing to do" would mask a
    typo'd or otherwise wrong --target path instead of failing loudly."""
    skill_dir = tmp_path / "skills" / "no-sidecar-skill"
    _write_skill_md(skill_dir)
    with pytest.raises(generator.GenerationError, match="cannot be read"):
        generator.compute_rendered_skill_md(skill_dir)


def test_missing_skill_md_raises_generation_error(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "skills" / "no-skill-md-skill"
    _write_sidecar(skill_dir, _copy_full_contract(), name="no-skill-md-skill")
    with pytest.raises(generator.GenerationError, match="cannot be read"):
        generator.compute_rendered_skill_md(skill_dir)


def test_main_missing_sidecar_fails_cleanly(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = tmp_path / "skills" / "no-sidecar-skill-2"
    _write_skill_md(skill_dir)
    assert generator.main([str(skill_dir)]) == 1
    assert "FAIL" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# apply_region / _locate_markers -- direct unit coverage
# ---------------------------------------------------------------------------


def test_apply_region_replaces_only_the_marker_delimited_content(tmp_path: pathlib.Path) -> None:
    skill_md_path = tmp_path / "SKILL.md"
    text = f"before\n{generator.BEGIN_MARKER}\nold\n{generator.END_MARKER}\nafter\n"
    result = generator.apply_region(text, "NEW CONTENT", skill_md_path)
    # apply_region always wraps region_text in exactly one blank line on
    # each side, regardless of the original spacing between the markers.
    assert result == f"before\n{generator.BEGIN_MARKER}\n\nNEW CONTENT\n\n{generator.END_MARKER}\nafter\n"


# ---------------------------------------------------------------------------
# Defeat tests -- adversarial-review finding (issue #1965): _locate_markers
# used to accept a marker sharing its own line with other content, silently
# excluding the smuggled content from the computed region. Each test below
# reconstructs the exact defeat shape the finding described and asserts the
# fix actually rejects it, rather than merely asserting the fix's own
# strip()-based implementation detail.
# ---------------------------------------------------------------------------


def test_begin_marker_with_content_appended_on_same_line_fails_loudly(tmp_path: pathlib.Path) -> None:
    """The false-negative shape itself: content directly appended after the
    begin marker on its own line used to be silently skipped past (by
    ``text.index("\\n", begin_pos)`` landing on that line's own end),
    placing it outside the computed region entirely -- so neither
    region-replacement nor ``--check``'s own drift comparison ever saw it.
    Must now raise GenerationError instead of silently treating the line
    as a clean marker line."""
    skill_md_path = tmp_path / "SKILL.md"
    text = f"before\n{generator.BEGIN_MARKER}## Precondition\nold\n{generator.END_MARKER}\nafter\n"
    with pytest.raises(generator.GenerationError, match="own line"):
        generator.apply_region(text, "NEW CONTENT", skill_md_path)


def test_end_marker_with_content_appended_on_same_line_fails_loudly(tmp_path: pathlib.Path) -> None:
    """Companion to the above for the end marker's own line."""
    skill_md_path = tmp_path / "SKILL.md"
    text = f"before\n{generator.BEGIN_MARKER}\nold\n{generator.END_MARKER}trailing junk\nafter\n"
    with pytest.raises(generator.GenerationError, match="own line"):
        generator.apply_region(text, "NEW CONTENT", skill_md_path)


def test_both_markers_on_one_line_fails_loudly_not_corrupted_output(tmp_path: pathlib.Path) -> None:
    """Second disclosed consequence of the same gap: with both markers
    packed onto a single line, the old implementation computed
    region_start > region_end, which apply_region's own
    ``text[:region_start] + ... + text[region_end:]`` would have turned
    into duplicated, corrupted output rather than a clean replace. Must
    now raise GenerationError before ever reaching that slice."""
    skill_md_path = tmp_path / "SKILL.md"
    text = f"before\n{generator.BEGIN_MARKER}{generator.END_MARKER}\nafter\n"
    with pytest.raises(generator.GenerationError, match="own line"):
        generator.apply_region(text, "NEW CONTENT", skill_md_path)


def test_begin_marker_as_last_line_with_no_trailing_newline_fails_loudly_not_crashes(
    tmp_path: pathlib.Path,
) -> None:
    """Third disclosed consequence: with the begin marker as the file's
    very last line and no trailing newline, the pre-fix implementation
    crashed with an uncaught ValueError from
    `text.index("\\n", begin_pos)` (`.index` raises when the target isn't
    found, unlike `.find`). No end marker can legitimately follow a
    truly-last-line begin marker, so this text also has zero end markers
    -- the marker-count check reports that first, but the assertion that
    matters is the same either way: no uncaught ValueError reaches the
    caller."""
    skill_md_path = tmp_path / "SKILL.md"
    text = f"before\n{generator.BEGIN_MARKER}"
    with pytest.raises(generator.GenerationError):
        generator.apply_region(text, "NEW CONTENT", skill_md_path)


def test_main_check_mode_flags_content_smuggled_onto_marker_line_as_drift(tmp_path: pathlib.Path) -> None:
    """End-to-end reproduction of the finding's actual real-world impact:
    a committed SKILL.md whose begin-marker line carries smuggled content
    must fail `--check` (loudly, as a generation failure) rather than the
    pre-fix behavior of silently reporting no drift because the smuggled
    content sat outside the computed region."""
    skill_dir = _make_skill(
        tmp_path, "smuggled-marker-skill", _copy_full_contract(), begin_line=f"{generator.BEGIN_MARKER}## Injected"
    )
    assert generator.main(["--check", str(skill_dir)]) == 1

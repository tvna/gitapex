"""Unit tests for `.github/scripts/gitapex_gate_tool_boundary_parity.py`.

Issue #1963 (ACM row 5). Several cases below are built to DEFEAT this
gate's own detection logic rather than to exercise its happy path:

- a `permission:`-shaped key nested under a *different* frontmatter
  mapping, which a scan that merely searched for two-space-indented
  `key: deny` lines would miscount as a real denial;
- a permission block whose entries are `allow`, not `deny`, which must
  not be read as reproducing a boundary;
- a generated copy that disagrees with the expectation table even though
  the source and the in-repo mapping agree, the exact three-way
  disagreement check 3 exists to catch;
- an agent definition present on disk but absent from the sync module's
  own spec list, the shape the pre-fix `branch-plan-task.md` had; and
- every path where the gate cannot evaluate its inputs, each asserted to
  exit 2 rather than pass silently.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import gitapex_gate_tool_boundary_parity as gate  # noqa: E402

_SYNC_TEMPLATE = """AGENT_PERMISSION_SPECS = (
{entries}
)
"""


def _write_repo(
    tmp_path: pathlib.Path,
    *,
    agents: dict[str, str],
    specs: str,
    generated: dict[str, str] | None = None,
) -> pathlib.Path:
    (tmp_path / "agents").mkdir(parents=True, exist_ok=True)
    for name, text in agents.items():
        (tmp_path / "agents" / name).write_text(text, encoding="utf-8")
    (tmp_path / "hooks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "hooks" / "gitapex_sync_opencode.py").write_text(_SYNC_TEMPLATE.format(entries=specs), encoding="utf-8")
    for name, text in (generated or {}).items():
        (tmp_path / ".opencode" / "agents").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".opencode" / "agents" / name).write_text(text, encoding="utf-8")
    return tmp_path


_BRANCH_PLAN_SOURCE = "---\nname: branch-plan-task\ndescription: d\ndisallowedTools: mcp__github\n---\n\nbody\n"
_REVIEW_PERSONA_SOURCE = "---\nname: review-persona\ndescription: d\ntools: Read, Grep, Glob\n---\n\nbody\n"
_GOOD_SPEC = '    ("branch-plan-task.md", {"*mcp*": "deny"}),'
_PREFIX_SPEC = '    ("branch-plan-task.md", None),'


def _rows(tmp_path: pathlib.Path, **kwargs: object) -> dict[tuple[str, str], tuple[bool, str]]:
    repo = _write_repo(tmp_path, **kwargs)  # type: ignore[arg-type]
    return {(check, subject): (passed, detail) for check, subject, passed, detail in gate.evaluate(repo)}


# --- the three checks, on the shapes this issue actually found ---------


def test_declared_mapped_and_equivalent_all_pass(tmp_path: pathlib.Path) -> None:
    rows = _rows(tmp_path, agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE}, specs=_GOOD_SPEC)
    assert all(passed for passed, _ in rows.values())


def test_missing_mapping_fails_both_dependent_checks(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: the pre-fix shape. The boundary IS declared on the
    Claude side, so a gate that only read the source would pass it."""
    rows = _rows(tmp_path, agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE}, specs=_PREFIX_SPEC)
    assert rows[("boundary-declared", "branch-plan-task.md")][0]
    assert not rows[("mapping-present", "branch-plan-task.md")][0]
    assert not rows[("mapping-equivalent", "branch-plan-task.md")][0]


def test_agent_absent_from_the_spec_list_fails(tmp_path: pathlib.Path) -> None:
    rows = _rows(tmp_path, agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE}, specs="")
    assert not rows[("mapping-present", "branch-plan-task.md")][0]


def test_source_with_no_boundary_key_fails(tmp_path: pathlib.Path) -> None:
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": "---\nname: x\ndescription: d\n---\n\nbody\n"},
        specs=_GOOD_SPEC,
    )
    assert not rows[("boundary-declared", "branch-plan-task.md")][0]


def test_source_declaration_drifting_from_the_table_fails(tmp_path: pathlib.Path) -> None:
    """Editing the source's declared boundary without updating the
    expectation table is the drift this gate exists to catch."""
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE.replace("mcp__github", "mcp__gitlab")},
        specs=_GOOD_SPEC,
    )
    assert not rows[("mapping-equivalent", "branch-plan-task.md")][0]


def test_agent_with_no_table_row_fails(tmp_path: pathlib.Path) -> None:
    rows = _rows(
        tmp_path,
        agents={"brand-new-agent.md": _BRANCH_PLAN_SOURCE},
        specs='    ("brand-new-agent.md", {"*mcp*": "deny"}),',
    )
    assert rows[("mapping-equivalent", "brand-new-agent.md")] == (False, "no row in EXPECTED_BOUNDARIES")


def test_review_persona_full_denial_set_passes(tmp_path: pathlib.Path) -> None:
    denials = ", ".join(f'"{key}": "deny"' for key in gate.EXPECTED_BOUNDARIES["review-persona.md"][2])
    rows = _rows(
        tmp_path,
        agents={"review-persona.md": _REVIEW_PERSONA_SOURCE},
        specs=f'    ("review-persona.md", {{{denials}}}),',
    )
    assert all(passed for passed, _ in rows.values())


def test_partial_denial_set_fails(tmp_path: pathlib.Path) -> None:
    rows = _rows(
        tmp_path,
        agents={"review-persona.md": _REVIEW_PERSONA_SOURCE},
        specs='    ("review-persona.md", {"edit": "deny"}),',
    )
    assert not rows[("mapping-equivalent", "review-persona.md")][0]


# --- generated-copy agreement (check 3's third leg) --------------------


def test_generated_copy_agreeing_passes(tmp_path: pathlib.Path) -> None:
    """The key is written unquoted by the generator (`f"  {key}: {value}"`),
    so the checker must read that exact shape -- a quoted key would be a
    different string and is deliberately not accepted as equivalent."""
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE},
        specs=_GOOD_SPEC,
        generated={
            "branch-plan-task.md": "---\ndescription: d\nmode: subagent\npermission:\n  *mcp*: deny\n---\n\nbody\n"
        },
    )
    assert rows[("mapping-equivalent", "branch-plan-task.md")][0]


def test_generated_copy_disagreeing_fails(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: source and in-repo mapping agree; only the generated
    copy drifted. A two-way check would pass this."""
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE},
        specs=_GOOD_SPEC,
        generated={"branch-plan-task.md": "---\ndescription: d\nmode: subagent\n---\n\nbody\n"},
    )
    assert not rows[("mapping-equivalent", "branch-plan-task.md")][0]


# --- generated_permission_keys, probed directly ------------------------


def test_nested_permission_shaped_key_is_not_counted() -> None:
    """DEFEAT CASE: a two-space-indented `key: deny` under a mapping other
    than `permission:` must not count as a denial."""
    text = "---\ndescription: d\nother:\n  bash: deny\n---\n\nbody\n"
    assert gate.generated_permission_keys(text) == set()


def test_allow_entries_are_not_counted_as_denials() -> None:
    text = "---\npermission:\n  bash: allow\n  edit: deny\n---\n\nbody\n"
    assert gate.generated_permission_keys(text) == {"edit"}


def test_permission_block_ends_at_the_next_top_level_key() -> None:
    text = "---\npermission:\n  bash: deny\nmode: subagent\n  edit: deny\n---\n\nbody\n"
    assert gate.generated_permission_keys(text) == {"bash"}


def test_no_frontmatter_yields_no_keys() -> None:
    assert gate.generated_permission_keys("just a body\n") == set()


def test_frontmatter_must_start_at_the_first_byte() -> None:
    """DEFEAT CASE: a `---` block further down the file is a horizontal
    rule, not frontmatter."""
    assert gate.frontmatter_fields("intro\n\n---\ntools: Read\n---\n") == {}


# --- unrunnable paths all exit 2, never a silent pass ------------------


def test_missing_sync_module_is_unrunnable(tmp_path: pathlib.Path) -> None:
    (tmp_path / "agents").mkdir()
    with pytest.raises(gate.GateUnrunnable, match=r"cannot load|cannot import"):
        gate.evaluate(tmp_path)


def test_sync_module_without_the_spec_constant_is_unrunnable(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents={"a.md": _BRANCH_PLAN_SOURCE}, specs="")
    (repo / "hooks" / "gitapex_sync_opencode.py").write_text("OTHER = 1\n", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="AGENT_PERMISSION_SPECS"):
        gate.evaluate(repo)


def test_no_agent_definitions_is_unrunnable(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents={}, specs="")
    with pytest.raises(gate.GateUnrunnable, match="no agents"):
        gate.evaluate(repo)


def test_syntax_error_in_sync_module_is_unrunnable(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents={"a.md": _BRANCH_PLAN_SOURCE}, specs="")
    (repo / "hooks" / "gitapex_sync_opencode.py").write_text("def (\n", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="cannot import"):
        gate.evaluate(repo)


# --- CLI ---------------------------------------------------------------


def test_main_returns_2_when_unrunnable(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "agents").mkdir()
    assert gate.main(["--repo-root", str(tmp_path)]) == 2
    assert "ERROR" in capsys.readouterr().err


def test_main_returns_1_on_failure(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE}, specs=_PREFIX_SPEC)
    assert gate.main(["--repo-root", str(repo)]) == 1


def test_main_returns_0_on_success(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE}, specs=_GOOD_SPEC)
    assert gate.main(["--repo-root", str(repo)]) == 0


def test_the_real_repository_passes() -> None:
    """The live check the ACM's own proof method names: this repository's
    own tree must satisfy the invariant after the fix in this change."""
    assert gate.main(["--repo-root", str(REPO_ROOT)]) == 0

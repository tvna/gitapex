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

# A stand-in for hooks/gitapex_sync_opencode.py carrying the two names the
# gate imports. The renderer mimics the real generator's own permission
# block (two-space indent, `key: value`); `render_broken` below mimics a
# generator whose output shape drifted, which is what defeat case F needs.
_SYNC_TEMPLATE = """AGENT_PERMISSION_SPECS = (
{entries}
)


def _render_agent_copy(source_text, source_rel, permission):
    out = ["---", "description: d", "mode: subagent"]
    if permission is not None:
        out.append("{permission_key}:")
        for key, value in permission.items():
            out.append("{indent}" + key + ": " + value)
    out.append("---")
    out.append("")
    out.append("body")
    return "\\n".join(out)
"""


def _write_repo(
    tmp_path: pathlib.Path,
    *,
    agents: dict[str, str],
    specs: str,
    permission_key: str = "permission",
    indent: str = "  ",
) -> pathlib.Path:
    (tmp_path / "agents").mkdir(parents=True, exist_ok=True)
    for name, text in agents.items():
        (tmp_path / "agents" / name).write_text(text, encoding="utf-8")
    (tmp_path / "hooks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "hooks" / "gitapex_sync_opencode.py").write_text(
        _SYNC_TEMPLATE.format(entries=specs, permission_key=permission_key, indent=indent), encoding="utf-8"
    )
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


def test_rendered_copy_agreeing_passes(tmp_path: pathlib.Path) -> None:
    """The generator writes the key unquoted at a two-space indent, so the
    scan must read that exact shape."""
    rows = _rows(tmp_path, agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE}, specs=_GOOD_SPEC)
    assert rows[("mapping-equivalent", "branch-plan-task.md")][0]


def test_a_renamed_permission_key_in_the_generator_fails(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE, and the one that motivated rendering rather than
    reading: source and in-repo mapping agree, and only the GENERATOR's own
    output shape drifted. The earlier version read `.opencode/agents/`
    from disk -- a gitignored path absent in every checkout -- so it
    skipped this leg silently and passed."""
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE},
        specs=_GOOD_SPEC,
        permission_key="permissions",
    )
    assert not rows[("mapping-equivalent", "branch-plan-task.md")][0]


def test_a_changed_generator_indent_fails(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: same shape drift, expressed as indentation rather than
    a key name."""
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE},
        specs=_GOOD_SPEC,
        indent="    ",
    )
    assert not rows[("mapping-equivalent", "branch-plan-task.md")][0]


def test_a_mapping_that_denies_nothing_fails(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: `{"edit": "allow"}` is truthy, so a presence test would
    report it mapped while it reproduces no boundary at all."""
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE},
        specs='    ("branch-plan-task.md", {"edit": "allow"}),',
    )
    assert not rows[("mapping-present", "branch-plan-task.md")][0]


def test_a_registry_row_naming_a_missing_file_fails(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: the reverse set difference. A spec row for a file that
    does not exist produces no source to iterate, so without an explicit
    check it drifts silently forever."""
    rows = _rows(
        tmp_path,
        agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE},
        specs=_GOOD_SPEC + '\n    ("ghost.md", {"*mcp*": "deny"}),',
    )
    assert not rows[("source-present", "ghost.md")][0]


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


# --- load_permission_specs and read_checked, probed by name ------------


def test_load_sync_module_returns_the_table_and_the_renderer(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents={"branch-plan-task.md": _BRANCH_PLAN_SOURCE}, specs=_GOOD_SPEC)
    specs, render = gate.load_sync_module(repo)
    assert specs == {"branch-plan-task.md": {"*mcp*": "deny"}}
    assert callable(render)


def test_load_sync_module_is_unrunnable_without_a_loader(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEFEAT CASE: importlib can return a spec with no loader (a path it
    recognises but cannot execute). That branch must raise, not fall
    through to an AttributeError or an empty table."""
    repo = _write_repo(tmp_path, agents={"a.md": _BRANCH_PLAN_SOURCE}, specs="")
    monkeypatch.setattr(gate.importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(gate.GateUnrunnable, match="cannot load"):
        gate.load_sync_module(repo)


def test_read_checked_returns_decoded_text(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("hello\n", encoding="utf-8")
    assert gate.read_checked(target) == "hello\n"


def test_read_checked_is_unrunnable_on_undecodable_bytes(tmp_path: pathlib.Path) -> None:
    """An undecodable agent definition is the gate losing its ability to
    judge, not a boundary failure -- exit 2, never a FAIL row."""
    target = tmp_path / "a.md"
    target.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(gate.GateUnrunnable, match="cannot read"):
        gate.read_checked(target)


def test_read_checked_is_unrunnable_on_a_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.GateUnrunnable, match="cannot read"):
        gate.read_checked(tmp_path / "absent.md")


def test_evaluate_surfaces_an_undecodable_source_as_unrunnable(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents={}, specs=_GOOD_SPEC)
    (repo / "agents" / "branch-plan-task.md").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(gate.GateUnrunnable, match="cannot read"):
        gate.evaluate(repo)


def test_no_expectation_table_row_names_a_missing_agent() -> None:
    """The stale-row check the gate itself cannot make: EXPECTED_BOUNDARIES
    describes THIS repository, so grading it against an arbitrary
    --repo-root would report false absences. It is graded here instead."""
    present = {path.name for path in (REPO_ROOT / "agents").glob("*.md")}
    assert set(gate.EXPECTED_BOUNDARIES) <= present


def test_load_sync_module_is_unrunnable_without_a_renderer(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: a sync module carrying the spec table but no
    `_render_agent_copy` would leave check 3's third leg with nothing to
    call. That must be exit 2, not a skipped leg."""
    repo = _write_repo(tmp_path, agents={"a.md": _BRANCH_PLAN_SOURCE}, specs="")
    (repo / "hooks" / "gitapex_sync_opencode.py").write_text("AGENT_PERMISSION_SPECS = ()\n", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="_render_agent_copy"):
        gate.load_sync_module(repo)


def test_load_sync_module_is_unrunnable_on_a_module_level_sys_exit(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: SystemExit derives from BaseException, so a
    module-level `sys.exit(0)` in the file this gate imports would
    otherwise terminate the gate with status 0 and not one row printed --
    a fully silent pass."""
    repo = _write_repo(tmp_path, agents={"a.md": _BRANCH_PLAN_SOURCE}, specs="")
    (repo / "hooks" / "gitapex_sync_opencode.py").write_text("import sys\n\nsys.exit(0)\n", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match=r"sys\.exit"):
        gate.load_sync_module(repo)


def test_load_sync_module_is_unrunnable_on_any_import_error(tmp_path: pathlib.Path) -> None:
    """A NameError at import time is not one of (OSError, SyntaxError,
    ImportError); the narrower filter this started with let it escape as a
    traceback, mis-signalling the documented exit 2."""
    repo = _write_repo(tmp_path, agents={"a.md": _BRANCH_PLAN_SOURCE}, specs="")
    (repo / "hooks" / "gitapex_sync_opencode.py").write_text("undefined_name\n", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="cannot import"):
        gate.load_sync_module(repo)


def test_read_checked_round_trips_and_fails_closed(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("hello\n", encoding="utf-8")
    assert gate.read_checked(target) == "hello\n"
    target.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(gate.GateUnrunnable, match="cannot read"):
        gate.read_checked(target)

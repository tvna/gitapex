"""Tests for hooks/gitapex_sync_opencode.py (issue #1812) plus the drift
gate for the .gitignore patterns that change ships with.

gitapex_gate_gitignore_pattern_coverage.py requires every pattern added
to .gitignore in a diff to be referenced, literally, by some test under
tests/ -- hence the two literal anchors below. They are also the
behavioral contract: the OpenCode-deployed trees must stay untracked
while the provisioning plugin itself stays tracked.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import gitapex_sync_opencode as sync
import pytest
from conftest import REPO_ROOT, assert_path_is_gitignored

# Literal anchors for the gitignore-pattern-coverage gate (see module
# docstring): keep these strings exactly the patterns .gitignore carries.
_SKILLS_MIRROR_PATTERN = "/.agents/skills/"
_OPENCODE_AGENTS_PATTERN = "/.opencode/*"
_OPENCODE_PLUGINS_NEGATION = "!/.opencode/plugins/"


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _skill(project: pathlib.Path, name: str, frontmatter_name: str | None = None) -> None:
    declared = name if frontmatter_name is None else frontmatter_name
    _write(
        project / "skills" / name / "SKILL.md",
        f"---\nname: {declared}\ndescription: {name} does things\n---\n\nBody.\n",
    )


def _project(tmp_path: pathlib.Path) -> pathlib.Path:
    _write(tmp_path / "apm.yml", "name: probe\nversion: 0.1.0\n")
    return tmp_path


def test_skills_sync_links_valid_skills_and_skips_rest(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "good-skill")
    _skill(project, "renamed-skill", frontmatter_name="other-name")
    (project / "skills" / "retired-stub" / "scripts").mkdir(parents=True)
    _write(project / "skills" / "retired-stub" / "scripts" / "x.py", "pass\n")
    (project / "skills" / "nameless").mkdir(parents=True)
    _write(project / "skills" / "nameless" / "SKILL.md", "no frontmatter here\n")

    notes: list[str] = []
    changes = sync.sync_skills(project, False, notes)
    assert changes == 1
    link = project / ".agents" / "skills" / "good-skill"
    assert link.is_symlink()
    assert link.resolve() == (project / "skills" / "good-skill").resolve()
    # Relative target: the checkout stays relocatable.
    assert not link.readlink().is_absolute()
    assert not (project / ".agents" / "skills" / "renamed-skill").exists()
    assert not (project / ".agents" / "skills" / "retired-stub").exists()
    assert not (project / ".agents" / "skills" / "nameless").exists()
    assert any("renamed-skill" in note for note in notes)

    # Second run is a no-op.
    notes2: list[str] = []
    assert sync.sync_skills(project, False, notes2) == 0


def test_skills_sync_never_clobbers_real_paths(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "good-skill")
    # Simulate an `apm install tvna/gitapex --target opencode` copy of a
    # released revision: a real directory. An explicit install wins.
    deployed = project / ".agents" / "skills" / "good-skill"
    _write(deployed / "SKILL.md", "released copy\n")
    notes: list[str] = []
    assert sync.sync_skills(project, False, notes) == 0
    assert deployed.is_dir() and not deployed.is_symlink()
    assert deployed.joinpath("SKILL.md").read_text(encoding="utf-8") == "released copy\n"


def test_skills_sync_prunes_only_our_dead_mirrors(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "stays-here")
    notes: list[str] = []
    assert sync.sync_skills(project, False, notes) == 1
    # Retirement: the skill directory goes away; the mirror must follow.
    shutil.rmtree(project / "skills" / "stays-here")
    assert sync.sync_skills(project, False, notes) == 1
    assert not (project / ".agents" / "skills" / "stays-here").is_symlink()

    # A foreign symlink (points outside skills/) is never pruned, even
    # when it dangles.
    (project / ".agents" / "skills").mkdir(parents=True, exist_ok=True)
    foreign = project / ".agents" / "skills" / "foreign"
    foreign.symlink_to("../elsewhere")
    assert sync.sync_skills(project, False, notes) == 0
    assert foreign.is_symlink()


def test_agents_sync_rewrites_review_persona_for_opencode(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    agents = project / "agents"
    _write(
        agents / "review-persona.md",
        "---\nname: review-persona\ndescription: Read-only review.\ntools: Read, Grep, Glob\n---\n\nBody.\n",
    )
    _write(
        agents / "branch-plan-task.md",
        "---\nname: branch-plan-task\ndescription: Dispatch target.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    notes: list[str] = []
    assert sync.sync_agents(project, False, notes) == 2

    persona = (project / ".opencode" / "agents" / "review-persona.md").read_text(encoding="utf-8")
    assert "tools: Read, Grep, Glob" not in persona
    assert "tools:" not in persona.split("---")[1]
    for denied in ("edit: deny", "bash: deny", "task: deny", "webfetch: deny", "websearch: deny"):
        assert denied in persona
    # MCP-server-provided tools are denied under any naming scheme
    # (OpenCode wildcard-pattern permission keys).
    assert "*mcp*: deny" in persona
    assert "description: Read-only review." in persona
    assert "mode: subagent" in persona
    assert "Body." in persona
    # Sources stay Claude-canonical: never rewritten.
    assert "tools: Read, Grep, Glob" in (agents / "review-persona.md").read_text(encoding="utf-8")

    task = (project / ".opencode" / "agents" / "branch-plan-task.md").read_text(encoding="utf-8")
    assert "disallowedTools" not in task
    assert "mode: subagent" in task

    # Idempotent.
    assert sync.sync_agents(project, False, []) == 0


def test_verify_mode_reports_drift_without_writing(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "good-skill")
    notes: list[str] = []
    assert sync.sync_skills(project, True, notes) == 1
    assert not (project / ".agents").exists()


def test_main_refuses_outside_checkout(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert sync.main(["--project-dir", str(tmp_path)]) == 1
    assert "apm.yml not found" in capsys.readouterr().err


def test_main_verify_end_to_end(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "good-skill")
    assert sync.main(["--project-dir", str(project), "--verify"]) == 1
    assert sync.main(["--project-dir", str(project)]) == 0
    # agents/ absent in this probe project: skipped, not drift.
    assert sync.main(["--project-dir", str(project), "--verify"]) == 0


def test_apm_yml_pins_claude_target() -> None:
    # Issue #1812: the committed .opencode/plugins/ session plugin is
    # itself an opencode target signal, so apm's auto-detection sees both
    # claude (.claude/) and opencode (.opencode/) and refuses a bare
    # `apm install` ("cannot decide which to deploy to" -- reproduced
    # live). The explicit pin restores the pre-#1812 claude-only behavior
    # deterministically; an explicit `apm install --target opencode`
    # still overrides it. yaml is already a test dependency (conftest).
    import yaml

    manifest = yaml.safe_load((REPO_ROOT / "apm.yml").read_text(encoding="utf-8"))
    assert manifest.get("targets") == ["claude"], manifest.get("targets")


def test_opencode_deployed_trees_stay_gitignored() -> None:
    assert_path_is_gitignored(
        REPO_ROOT / ".agents" / "skills" / "drafting-issues" / "SKILL.md",
        f"{_SKILLS_MIRROR_PATTERN!r} (opencode skill mirror)",
    )
    assert_path_is_gitignored(
        REPO_ROOT / ".opencode" / "agents" / "review-persona.md",
        f"{_OPENCODE_AGENTS_PATTERN!r} (opencode generated agent copy)",
    )


def test_opencode_plugin_itself_is_not_gitignored() -> None:
    # The mechanism must stay tracked: a negation that a parent-dir prune
    # would silently swallow must fail loudly here instead.
    path = REPO_ROOT / ".opencode" / "plugins" / "gitapex-session.js"
    assert path.is_file(), "the session plugin is missing from the checkout"
    result = subprocess.run(
        ["git", "check-ignore", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"{_OPENCODE_PLUGINS_NEGATION!r} must keep the plugin tracked; "
        f"git check-ignore says ignored: {result.stdout.strip()}"
    )


def test_real_checkout_skills_all_sync_clean() -> None:
    # Live-repo assertion: every skills/<name>/SKILL.md the checkout ships
    # passes the same name/shape validation the sync enforces, so the
    # mirror never silently drops a skill in production.
    skills = REPO_ROOT / "skills"
    shipped = [p for p in skills.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()]
    assert shipped, "expected shipped skills"
    for skill_dir in shipped:
        name = sync._read_skill_name(skill_dir / "SKILL.md")
        assert name == skill_dir.name, f"skills/{skill_dir.name}: frontmatter name {name!r}"
    # ... and the two distributed agents render without error.
    for filename in ("review-persona.md", "branch-plan-task.md"):
        text = (REPO_ROOT / "agents" / filename).read_text(encoding="utf-8")
        rendered = sync._render_agent_copy(text, f"agents/{filename}", sync.REVIEW_PERSONA_PERMISSION)
        assert "mode: subagent" in rendered


def _assert_effectively_ignored(path: pathlib.Path, description: str) -> None:
    # Plain boolean `git check-ignore` (no `-v` source pinning): for
    # opencode-scaffolded tool output the deciding file legitimately
    # differs by checkout state -- this repository's own `/.opencode/*`
    # glob on a fresh clone, opencode's own nested `.opencode/.gitignore`
    # after a first run. Either way the path must stay untracked. The
    # strict `assert_path_is_gitignored` (repo-rule pinning) is wrong here
    # by design, and stays in use everywhere a repository rule must decide.
    result = subprocess.run(
        ["git", "check-ignore", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{description} is not gitignored"


def test_plugin_file_uses_only_stdlib_imports() -> None:
    # OpenCode runs `bun install` for local plugins carrying a package.json;
    # this plugin must need none: every static import comes from node:.
    import re

    text = (REPO_ROOT / ".opencode" / "plugins" / "gitapex-session.js").read_text(encoding="utf-8")
    specifiers = re.findall(r"""(?:import|export)[^'"]*?from\s*["']([^"']+)["']""", text)
    assert specifiers, "expected at least one static import"
    assert all(spec.startswith("node:") for spec in specifiers), specifiers
    # No committed package.json may the plugin ever need: opencode scaffolds
    # .opencode/package.json (+lockfiles, node_modules, its own nested
    # .gitignore) on first run. Those are reproducible tool output and must
    # stay untracked -- covered by the same `/.opencode/*` glob when present,
    # and their absence on a fresh clone must not break anything either.
    generated = REPO_ROOT / ".opencode" / "package.json"
    if generated.exists():
        _assert_effectively_ignored(generated, f"{_OPENCODE_AGENTS_PATTERN!r} (opencode-scaffolded noise)")
    assert "session.created" in text
    assert "shell.env" in text


def test_opencode_scaffolded_noise_stays_gitignored() -> None:
    # Whatever opencode generates beside the committed plugin on first run
    # (observed live: package.json, package-lock.json, node_modules/, its
    # own nested .gitignore) must never show up as untracked noise. The
    # `/.opencode/*` glob covers every direct child; only plugins/ is
    # negated back to tracked.
    for name in ("package.json", "package-lock.json", "bun.lock", "node_modules", ".gitignore"):
        _assert_effectively_ignored(
            REPO_ROOT / ".opencode" / name,
            f"{_OPENCODE_AGENTS_PATTERN!r} (opencode-scaffolded {name})",
        )


def test_frontmatter_non_field_lines_ignored(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _write(
        project / "skills" / "messy" / "SKILL.md",
        "---\nname: messy\ndescription: Does things.\n- a list item, not a field\n# a comment\n---\n\nBody.\n",
    )
    notes: list[str] = []
    assert sync.sync_skills(project, False, notes) == 1
    assert (project / ".agents" / "skills" / "messy").is_symlink()


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses POSIX permission bits, so chmod(0o000) below cannot make the file unreadable",
)
def test_unreadable_skill_md_skipped(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "good-skill")
    locked = project / "skills" / "locked" / "SKILL.md"
    _write(project / "skills" / "locked" / "SKILL.md", "---\nname: locked\n---\n")
    locked.chmod(0o000)
    try:
        notes: list[str] = []
        assert sync.sync_skills(project, False, notes) == 1
        assert any("locked" in note for note in notes)
        assert not (project / ".agents" / "skills" / "locked").exists()
    finally:
        locked.chmod(0o644)


def test_skills_src_missing_entirely(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    notes: list[str] = []
    assert sync.sync_skills(project, False, notes) == 0
    assert any("not found" in note for note in notes)


def test_repair_stale_our_symlink(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "good-skill")
    _skill(project, "other-skill")
    dst_dir = project / ".agents" / "skills"
    dst_dir.mkdir(parents=True)
    # Ours (raw target inside skills/) but pointing at the wrong skill.
    (dst_dir / "good-skill").symlink_to("../../skills/other-skill")
    notes: list[str] = []
    assert sync.sync_skills(project, True, notes) == 2  # repair + link
    assert sync.sync_skills(project, False, notes) == 2
    assert (dst_dir / "good-skill").resolve() == (project / "skills" / "good-skill").resolve()
    assert sync.sync_skills(project, False, []) == 0


def test_foreign_symlink_in_sync_loop_skipped(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "good-skill")
    dst_dir = project / ".agents" / "skills"
    dst_dir.mkdir(parents=True)
    (dst_dir / "good-skill").symlink_to("../elsewhere")
    notes: list[str] = []
    assert sync.sync_skills(project, False, notes) == 0
    assert any("foreign symlink" in note for note in notes)


def test_retired_real_dir_never_pruned(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "stays-here")
    notes: list[str] = []
    assert sync.sync_skills(project, False, notes) == 1
    # An apm-managed real directory for a now-retired skill: not a symlink
    # (covers the non-symlink guard), not pruned, never touched.
    retired = project / ".agents" / "skills" / "retired-skill"
    _write(retired / "SKILL.md", "released copy\n")
    assert sync.sync_skills(project, False, notes) == 0
    assert retired.joinpath("SKILL.md").read_text(encoding="utf-8") == "released copy\n"


def _break_resolve_for(monkeypatch: pytest.MonkeyPatch, link: pathlib.Path) -> None:
    real_resolve = pathlib.Path.resolve

    def _boom(self: pathlib.Path, strict: bool = False) -> pathlib.Path:
        if self == link:
            raise OSError("simulated resolve failure")
        return real_resolve(self, strict)

    monkeypatch.setattr(pathlib.Path, "resolve", _boom)


def test_resolve_failure_falls_back_to_raw_target(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    dst_dir = project / ".agents" / "skills"
    dst_dir.mkdir(parents=True)
    (project / "skills").mkdir()
    link = dst_dir / "dangling"
    link.symlink_to("../../skills/gone")
    _break_resolve_for(monkeypatch, link)
    assert sync._is_our_symlink(link, project / "skills") is True
    link2 = dst_dir / "absolute"
    link2.symlink_to("/tmp/absolutely-elsewhere")
    _break_resolve_for(monkeypatch, link2)
    assert sync._is_our_symlink(link2, project / "skills") is False


def test_readlink_failure_treated_as_foreign(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    dst_dir = project / ".agents" / "skills"
    dst_dir.mkdir(parents=True)
    (project / "skills").mkdir()
    link = dst_dir / "unreadable"
    link.symlink_to("../../skills/gone")
    _break_resolve_for(monkeypatch, link)

    real_readlink = pathlib.Path.readlink

    def _boom_readlink(self: pathlib.Path) -> pathlib.Path:
        if self == link:
            raise OSError("simulated readlink failure")
        return real_readlink(self)

    monkeypatch.setattr(pathlib.Path, "readlink", _boom_readlink)
    assert sync._is_our_symlink(link, project / "skills") is False


def test_agents_render_errors_skipped(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    agents = project / "agents"
    _write(agents / "review-persona.md", "no frontmatter at all\n")
    _write(agents / "branch-plan-task.md", "---\nname: branch-plan-task\n---\n\nNo description.\n")
    notes: list[str] = []
    assert sync.sync_agents(project, False, notes) == 0
    assert sum("SKIP" in note for note in notes) == 2


def test_agents_rewrite_unexpected_form_and_verify(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    agents = project / "agents"
    _write(
        agents / "review-persona.md",
        "---\nname: review-persona\ndescription: Read-only review.\ntools: Read, Grep, Glob\n---\n\nBody.\n",
    )
    _write(
        agents / "branch-plan-task.md",
        "---\nname: branch-plan-task\ndescription: Dispatch target.\n---\n\nBody.\n",
    )
    dst_dir = project / ".opencode" / "agents"
    dst_dir.mkdir(parents=True)
    _write(dst_dir / "review-persona.md", "stale content\n")
    # A real directory where an agent copy belongs: unexpected form, left
    # untouched (covers the non-symlink half of the guard).
    (dst_dir / "branch-plan-task.md").mkdir()
    notes: list[str] = []
    assert sync.sync_agents(project, True, notes) == 1  # rewrite counts; dir skip does not
    assert sync.sync_agents(project, False, notes) == 1
    assert "stale content" not in (dst_dir / "review-persona.md").read_text(encoding="utf-8")
    assert (dst_dir / "branch-plan-task.md").is_dir()
    assert sync.sync_agents(project, False, []) == 0


def test_agents_non_dangling_symlink_never_written_through(tmp_path: pathlib.Path) -> None:
    # Regression test for the issue #1814 review finding: is_file() follows
    # symlinks, so without the is_symlink-first guard a non-dangling link
    # would take the REWRITE path and write_text() would write through it
    # into whatever it points at.
    project = _project(tmp_path)
    agents = project / "agents"
    _write(
        agents / "review-persona.md",
        "---\nname: review-persona\ndescription: Read-only review.\n---\n\nBody.\n",
    )
    _write(
        agents / "branch-plan-task.md",
        "---\nname: branch-plan-task\ndescription: Dispatch target.\n---\n\nBody.\n",
    )
    dst_dir = project / ".opencode" / "agents"
    dst_dir.mkdir(parents=True)
    victim = project / "victim.txt"
    _write(victim, "untouched\n")
    (dst_dir / "review-persona.md").symlink_to(victim)
    notes: list[str] = []
    assert sync.sync_agents(project, False, notes) == 1  # only branch-plan-task written
    assert victim.read_text(encoding="utf-8") == "untouched\n"
    assert (dst_dir / "review-persona.md").is_symlink()


def test_agents_unreadable_dst_forces_rewrite(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    agents = project / "agents"
    _write(
        agents / "review-persona.md",
        "---\nname: review-persona\ndescription: Read-only review.\n---\n\nBody.\n",
    )
    _write(
        agents / "branch-plan-task.md",
        "---\nname: branch-plan-task\ndescription: Dispatch target.\n---\n\nBody.\n",
    )
    dst_dir = project / ".opencode" / "agents"
    dst_dir.mkdir(parents=True)
    locked = dst_dir / "review-persona.md"
    _write(locked, "stale content\n")
    # Write-only: read_text raises (covers the unreadable-dst branch) while
    # the rewrite itself still succeeds.
    locked.chmod(0o200)
    try:
        notes: list[str] = []
        assert sync.sync_agents(project, False, notes) == 2
    finally:
        locked.chmod(0o644)
    assert "stale content" not in locked.read_text(encoding="utf-8")


def test_prune_verify_counts_without_writing(tmp_path: pathlib.Path) -> None:
    project = _project(tmp_path)
    _skill(project, "stays-here")
    notes: list[str] = []
    assert sync.sync_skills(project, False, notes) == 1
    shutil.rmtree(project / "skills" / "stays-here")
    assert sync.sync_skills(project, True, notes) == 1
    assert (project / ".agents" / "skills" / "stays-here").is_symlink()
    assert sync.sync_skills(project, False, notes) == 1
    assert not (project / ".agents" / "skills" / "stays-here").is_symlink()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))

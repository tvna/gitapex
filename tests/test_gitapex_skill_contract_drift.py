"""Tests for the `skill-contract-drift` `.gitapex/ssot.json` gate (issue
#1965, Task 5).

Two layers, matching this file's own dual role as the gate's `trigger`
(``.gitapex/ssot.json``'s own `skill-contract-drift` entry names this
exact module):

- The generator-level positive/negative cases exercise
  `skills/drafting-a-skill/scripts/gitapex_generate_skill_contract.py`'s
  own `--check` mode directly, against a synthetic `tmp_path` fixture
  skill -- proving the mechanism this gate's own `local_invocation`
  ultimately depends on still behaves the way the gate assumes.
- The wrapper-level tests exercise
  `.github/scripts/gitapex_run_skill_contract_check.py`'s own sweep/
  aggregation logic (which skills it discovers, how it reports a pass, a
  failure, and a timeout) with `check_skill`/`discover_contracts`
  monkeypatched, the same style
  `tests/test_gitapex_run_precommit_mypy.py` already establishes for its
  sibling per-group subprocess wrapper.

Every fixture skill lives under `tmp_path`, never a real `skills/*`
directory -- the real-repository sanity test below pins, separately, that
no real skill declares `spec.contract` yet (a foundation-only PR, zero
production targets by design, mirroring
`tests/test_gitapex_scan_ssot_schema.py`'s own
`test_real_repository_has_no_contract_declaring_skills_yet`). Fixture
construction is self-contained rather than imported from
`skills/drafting-a-skill/scripts/test_gitapex_generate_skill_contract.py`
(Task 3's own test module) -- this repository has no existing convention
of cross-importing test helpers between test files (confirmed against
`tests/test_gitapex_scan_ssot_schema.py`'s own `_write_skill_with_contract`,
which is self-contained the same way), so a second, independent, small
fixture writer here matches that established shape instead.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

# skills/drafting-a-skill/scripts is one of [tool.pytest.ini_options]
# pythonpath's own listed directories (issue #1965 Step 8 aggregate
# review: added there alongside the matching [tool.mypy] mypy_path entry,
# closing the mirror-comment gap that config's own comment already
# states), so a bare `import gitapex_generate_skill_contract` resolves
# with no explicit sys.path.insert needed here.
import gitapex_generate_skill_contract as generator
import gitapex_run_skill_contract_check as runner
import pytest

# ---------------------------------------------------------------------------
# Generator-level positive/negative cases (Branch Plan Task 5's own Planned
# ops, quoted verbatim in docs/gitapex/plans/2026-09-13-issue-1965-a2t6b5.md's
# own Task 5 section): "--check over every skill declaring spec.contract,
# using a synthetic fixture skill for the positive and negative cases."
# ---------------------------------------------------------------------------

_SKILL_MD_TEMPLATE = """---
name: {name}
description: Synthetic fixture skill for skill-contract-drift, not a real gitapex skill.
---

# {name}

Intro prose the generator must never touch.

{begin}

PLACEHOLDER -- overwritten by the first generator.main() regeneration below.

{end}

Trailing prose the generator must never touch.
"""


def _write_fixture_skill(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
    """A minimal, valid contract-declaring skill directory under `tmp_path`:
    a sidecar with just enough spec.contract to pass
    `_validate_contract` (a required `goal.endState`/`goal.check` and a
    resolving `handoff.next.skill`), and a `SKILL.md` carrying exactly one
    marker pair. Sidecar written as `json.dumps` text, not real YAML
    syntax -- JSON is valid YAML, so `yaml.safe_load` parses it
    unmodified, and this avoids adding a `yaml` import to this test module
    purely for fixture construction (the same trick
    `tests/test_gitapex_scan_ssot_schema.py`'s own
    `_write_skill_with_contract` already uses)."""
    skill_dir = tmp_path / "skills" / name
    (skill_dir / "metadata").mkdir(parents=True)
    contract = {
        "goal": {"endState": "fixture end state", "check": "fixture check"},
        "handoff": {"next": {"skill": name}},
    }
    (skill_dir / "metadata" / "gitapex.yaml").write_text(json.dumps({"spec": {"contract": contract}}), encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        _SKILL_MD_TEMPLATE.format(name=name, begin=generator.BEGIN_MARKER, end=generator.END_MARKER),
        encoding="utf-8",
    )
    return skill_dir


def test_check_passes_when_committed_skill_md_matches_fresh_regeneration(tmp_path: pathlib.Path) -> None:
    skill_dir = _write_fixture_skill(tmp_path, "fixture-skill")
    assert generator.main([str(skill_dir)]) == 0  # regenerate once, writing the real rendered region
    assert generator.main(["--check", str(skill_dir)]) == 0


def test_check_fails_when_committed_skill_md_has_drifted(tmp_path: pathlib.Path) -> None:
    """A committed SKILL.md hand-edited after generation (or generated
    from a sidecar value that has since changed) must fail --check -- the
    exact drift this gate exists to catch."""
    skill_dir = _write_fixture_skill(tmp_path, "fixture-skill")
    assert generator.main([str(skill_dir)]) == 0
    skill_md = skill_dir / "SKILL.md"
    drifted = skill_md.read_text(encoding="utf-8").replace(
        "- End state: fixture end state",
        "- End state: a hand-edited end state that was never regenerated",
    )
    assert drifted != skill_md.read_text(encoding="utf-8")  # confirm the replace actually matched something
    skill_md.write_text(drifted, encoding="utf-8")
    assert generator.main(["--check", str(skill_dir)]) == 1


# ---------------------------------------------------------------------------
# Real-repository sanity test (mirrors
# tests/test_gitapex_scan_ssot_schema.py's own
# test_real_repository_has_no_contract_declaring_skills_yet): confirmed no
# real skill declares spec.contract yet, so this gate is a clean no-op
# against the real, current repository -- pinned explicitly here rather
# than relying only on the synthetic fixtures above to notice a future
# change.
# ---------------------------------------------------------------------------


def test_real_repository_has_no_contract_declaring_skills_yet(capsys: pytest.CaptureFixture[str]) -> None:
    assert runner.ssot_schema.discover_contracts() == {}
    assert runner.main() == 0
    assert "nothing to check" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Wrapper-level tests (.github/scripts/gitapex_run_skill_contract_check.py):
# discover_contracts/check_skill monkeypatched, the same style
# tests/test_gitapex_run_precommit_mypy.py already uses for its sibling
# per-group subprocess wrapper (run_group there, check_skill here).
# ---------------------------------------------------------------------------


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["uv"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_main_returns_zero_when_no_skill_declares_a_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    # SKILLS_DIR monkeypatched to an empty tmp_path, not the real repository
    # tree: the orphaned-marker sweep (added alongside this test's own
    # discover_contracts stub) now runs on every main() call, and this
    # test's own "zero" assertion must hold on its own merits, not on the
    # incidental, unpinned fact that no real skills/*/SKILL.md happens to
    # carry a stray marker pair today.
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {})
    monkeypatch.setattr(runner.ssot_schema, "SKILLS_DIR", tmp_path)
    assert runner.main() == 0
    assert "nothing to check" in capsys.readouterr().out


def test_main_returns_zero_when_every_discovered_skill_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {"skill-a": {}, "skill-b": {}})
    monkeypatch.setattr(runner.ssot_schema, "SKILLS_DIR", tmp_path)
    monkeypatch.setattr(runner, "check_skill", lambda skill_dir: _completed(0))
    rc = runner.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 contract-declaring skill(s)" in out


def test_main_returns_one_and_names_only_the_failing_skill(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {"skill-a": {}, "skill-b": {}})
    monkeypatch.setattr(runner.ssot_schema, "SKILLS_DIR", tmp_path)

    def fake_check_skill(skill_dir: pathlib.Path) -> subprocess.CompletedProcess[str]:
        if skill_dir.name == "skill-b":
            return _completed(1, stdout="FAIL: skill-b contract region is stale\n")
        return _completed(0)

    monkeypatch.setattr(runner, "check_skill", fake_check_skill)
    rc = runner.main()
    out, err = capsys.readouterr()
    assert rc == 1
    assert "FAIL: skill-b contract region is stale" in out
    assert "skill-b" in err
    assert "skill-a" not in err


def test_main_treats_a_timed_out_skill_as_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    # A hung `--check` subprocess must still fail the gate loudly, matching
    # gitapex_run_precommit_mypy.py's own identical timeout-as-failure
    # contract for its per-group subprocess.
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {"skill-a": {}})
    monkeypatch.setattr(runner.ssot_schema, "SKILLS_DIR", tmp_path)

    def fake_check_skill(skill_dir: pathlib.Path) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="uv", timeout=runner._CHECK_TIMEOUT_SECONDS)

    monkeypatch.setattr(runner, "check_skill", fake_check_skill)
    rc = runner.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "skill-a" in err
    assert "timed out" in err


def test_main_reports_an_orphaned_marker_skill_as_a_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    """main()'s own wiring of _orphaned_marker_skills into the pass/fail
    verdict (not the sweep function itself, already pinned above) -- a
    contract-declaring skill passes its own check, but a sibling orphaned
    marker pair must still fail the whole gate and name itself in stderr."""
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {"skill-a": {}})
    skills_dir = tmp_path / "skills"
    orphan_dir = skills_dir / "orphan-skill"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "SKILL.md").write_text(
        _SKILL_MD_TEMPLATE.format(name="orphan-skill", begin=generator.BEGIN_MARKER, end=generator.END_MARKER),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner.ssot_schema, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(runner, "check_skill", lambda skill_dir: _completed(0))
    rc = runner.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "orphan-skill" in err
    assert "declares no spec.contract" in err


# ---------------------------------------------------------------------------
# _orphaned_marker_skills (issue #1965 Step 8 aggregate adversarial review):
# a SKILL.md carrying the generator's own marker pair whose sidecar declares
# no spec.contract at all is invisible to every discover_contracts-driven
# check above -- these three cases pin the sweep that closes that gap.
# ---------------------------------------------------------------------------


def test_orphaned_marker_skills_flags_a_marker_carrying_skill_with_no_contract(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    orphan_dir = skills_dir / "orphan-skill"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "SKILL.md").write_text(
        _SKILL_MD_TEMPLATE.format(name="orphan-skill", begin=generator.BEGIN_MARKER, end=generator.END_MARKER),
        encoding="utf-8",
    )
    assert runner._orphaned_marker_skills(skills_dir, set()) == ["orphan-skill"]


def test_orphaned_marker_skills_does_not_flag_a_contract_declaring_skill(tmp_path: pathlib.Path) -> None:
    skill_dir = _write_fixture_skill(tmp_path, "fixture-skill")
    assert runner._orphaned_marker_skills(skill_dir.parent, {"fixture-skill"}) == []


def test_orphaned_marker_skills_ignores_a_skill_with_no_markers_at_all(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    plain_dir = skills_dir / "plain-skill"
    plain_dir.mkdir(parents=True)
    (plain_dir / "SKILL.md").write_text(
        "---\nname: plain-skill\ndescription: no markers here.\n---\n\n# plain-skill\n",
        encoding="utf-8",
    )
    assert runner._orphaned_marker_skills(skills_dir, set()) == []


def test_orphaned_marker_skills_silently_skips_a_skill_md_that_is_not_valid_utf8(tmp_path: pathlib.Path) -> None:
    """A corrupted/non-UTF-8 SKILL.md is skill-metadata-schema-drift's own
    finding to report, not this sweep's -- per _orphaned_marker_skills'
    own docstring, a read failure here must not raise, and must not
    itself flag the skill as orphaned."""
    skills_dir = tmp_path / "skills"
    bad_encoding_dir = skills_dir / "bad-encoding-skill"
    bad_encoding_dir.mkdir(parents=True)
    (bad_encoding_dir / "SKILL.md").write_bytes(b"\xff\xfe not valid utf-8")
    assert runner._orphaned_marker_skills(skills_dir, set()) == []


def test_check_skill_invokes_uv_run_frozen_python3_generator_with_check_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _completed(0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    skill_dir = tmp_path / "skills" / "fixture-skill"
    runner.check_skill(skill_dir)
    assert captured["cmd"] == [
        "uv",
        "run",
        "--frozen",
        "python3",
        str(runner.GENERATOR_SCRIPT),
        "--check",
        str(skill_dir),
    ]
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["timeout"] == runner._CHECK_TIMEOUT_SECONDS
    assert kwargs["cwd"] == runner.REPO_ROOT

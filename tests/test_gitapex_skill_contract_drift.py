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
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# skills/drafting-a-skill/scripts is not one of [tool.pytest.ini_options]
# pythonpath's own listed directories (nothing outside this one test file
# needs a bare `import gitapex_generate_skill_contract`), so this follows
# the same explicit sys.path.insert + bare-import convention
# tests/test_gitapex_gate_plans_traceability.py and
# tests/test_gitapex_compute_skill_audit_flags.py already use for
# `.github/scripts` -- pointed at this one different directory instead.
# pyproject.toml's own [tool.mypy] mypy_path carries the matching entry so
# this same import resolves under the strict mypy invocation that checks
# this directory ("tests + pythonpath-linked roots").
sys.path.insert(0, str(REPO_ROOT / "skills" / "drafting-a-skill" / "scripts"))

import gitapex_generate_skill_contract as generator  # noqa: E402
import gitapex_run_skill_contract_check as runner  # noqa: E402 -- .github/scripts is already in pythonpath
import pytest  # noqa: E402

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
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {})
    assert runner.main() == 0
    assert "nothing to check" in capsys.readouterr().out


def test_main_returns_zero_when_every_discovered_skill_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {"skill-a": {}, "skill-b": {}})
    monkeypatch.setattr(runner, "check_skill", lambda skill_dir: _completed(0))
    rc = runner.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 contract-declaring skill(s)" in out


def test_main_returns_one_and_names_only_the_failing_skill(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {"skill-a": {}, "skill-b": {}})

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
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A hung `--check` subprocess must still fail the gate loudly, matching
    # gitapex_run_precommit_mypy.py's own identical timeout-as-failure
    # contract for its per-group subprocess.
    monkeypatch.setattr(runner.ssot_schema, "discover_contracts", lambda: {"skill-a": {}})

    def fake_check_skill(skill_dir: pathlib.Path) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="uv", timeout=runner._CHECK_TIMEOUT_SECONDS)

    monkeypatch.setattr(runner, "check_skill", fake_check_skill)
    rc = runner.main()
    err = capsys.readouterr().err
    assert rc == 1
    assert "skill-a" in err
    assert "timed out" in err


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

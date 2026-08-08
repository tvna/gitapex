"""Issue #874: the local pre-push wrapper must reach the same verdict CI does.

Two claims, one file, because the second is worthless without the first:

1. **Parity.** For one synthetic diff per applicability flag, the flags
   `skill-audit-gate.yml`'s real `run:` block publishes to `$GITHUB_OUTPUT`
   are byte-identical to the ones
   `gitapex_gate_skill_audit_disclosure.py --check-diff` computes. Both
   call `gitapex_compute_skill_audit_flags.py`, so today this holds by
   construction -- which is the point. The issue's constraint, restated in
   all 14 retrospectives that raised it, is that the local command must
   *reuse* the CI computation rather than become a second, independently
   drifting copy of it, and "by construction" is only true while nobody
   re-inlines the bash or points the wrapper at its own re-implementation.
   This test is what fails when someone does.

2. **The conditional extensions.** One fixture per extension the bundled
   hook copy (`hooks/gitapex_check_skill_audit_disclosure_or_waiver.py`)
   defers to CI by its own docstring -- description-change WAIVED
   rejection, eval-coverage disclosure, security-relevance, design-doc
   coverage, plus the deterministic-gate-quality check the retrospectives
   cited most often -- asserted end-to-end through the documented local
   command, in both its failing and its passing form. Before this, each of
   these was reachable only from a failed required check on an
   already-open PR.

Everything runs against a scratch git repository carrying the real
registry and the real scripts, so the thing under test is the shipped
command line rather than a paraphrase of it.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from collections.abc import Callable

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "skill-audit-gate.yml"

sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
import gitapex_compute_skill_audit_flags as flags_module  # noqa: E402

pytestmark = pytest.mark.slow

_COPIED = (
    ".gitapex/ssot.json",
    ".github/scripts/gitapex_compute_skill_audit_flags.py",
    ".github/scripts/gitapex_gate_skill_audit_disclosure.py",
    ".github/scripts/gitapex_detect_changed_gate_scripts.py",
    ".github/scripts/gitapex_skill_description_diff.py",
    ".github/scripts/gitapex_skill_security_relevance.py",
)

_PLAIN_SKILL_MD = """---
name: sample-skill
description: A perfectly ordinary skill with nothing notable in it.
---

# Sample

Body text.
"""

_SECURITY_SKILL_MD = _PLAIN_SKILL_MD.replace(
    "nothing notable in it",
    "a deterministic gate in it",
)

_BASE_EVIDENCE = (
    "## Skill audit evidence\n\n- battle-testing-a-skill: PASS\n- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
)


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _write(repo: pathlib.Path, relative: str, content: str = "x\n") -> pathlib.Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _commit(repo: pathlib.Path, message: str = "change") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


@pytest.fixture(scope="module")
def diff_step_script(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """The real `run:` block of the workflow's diff step, as a script."""
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["skill-audit-disclosure"]["steps"]
    run = next(s["run"] for s in steps if "$GITHUB_OUTPUT" in s.get("run", ""))
    path = tmp_path_factory.mktemp("diffstep") / "diff_step.sh"
    path.write_text(run, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@e")
    _git(tmp_path, "config", "user.name", "t")
    for relative in _COPIED:
        _write(tmp_path, relative, (REPO_ROOT / relative).read_text(encoding="utf-8"))
    _commit(tmp_path, "base")
    return tmp_path


@pytest.fixture
def outdir(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """Harness scratch space, deliberately outside the repository under
    test: `_commit` runs `git add -A`, so a $GITHUB_OUTPUT file written
    inside the repo would land in the very diff being graded."""
    return tmp_path_factory.mktemp("harness")


def _workflow_flags(script: pathlib.Path, repo: pathlib.Path, outdir: pathlib.Path, base: str) -> dict[str, str]:
    """Run the shipped diff step and return its parsed `$GITHUB_OUTPUT`."""
    output_file = outdir / "gh_output.txt"
    output_file.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "BASE_SHA": base,
        "HEAD_SHA": _git(repo, "rev-parse", "HEAD").stdout.strip(),
        "GITHUB_OUTPUT": str(output_file),
    }
    proc = subprocess.run(["bash", str(script)], cwd=repo, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    parsed = {}
    for line in output_file.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        parsed[key] = value
    return parsed


def _local_flags(repo: pathlib.Path, base: str) -> dict[str, str]:
    """The same flags, via the module the local wrapper calls."""
    flags = flags_module.compute_flags(base, "HEAD", repo)
    return dict(flags.as_output_pairs())


def _run_local_wrapper(repo: pathlib.Path, base: str, body: str, outdir: pathlib.Path) -> tuple[int, str]:
    """The documented pre-push command, run verbatim."""
    body_file = outdir / "body.md"
    body_file.write_text(body, encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(repo / ".github" / "scripts" / "gitapex_gate_skill_audit_disclosure.py"),
            "--check-diff",
            base,
            "HEAD",
            "--body-file",
            str(body_file),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


# --- claim 1: parity, one synthetic diff per flag ---


def _seed_skill_md(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", _PLAIN_SKILL_MD)


def _seed_description_change(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", _PLAIN_SKILL_MD)
    _commit(repo, "seed")
    _write(repo, "skills/sample/SKILL.md", _PLAIN_SKILL_MD.replace("ordinary", "unusual"))


def _seed_security_relevant(repo: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", _SECURITY_SKILL_MD)


def _seed_design_doc(repo: pathlib.Path) -> None:
    _write(repo, "docs/superpowers/specs/2026-01-01-thing.md", "# doc\n")


def _seed_checker_script(repo: pathlib.Path) -> None:
    _write(repo, "evals/scripts/gitapex_helper.py")


def _seed_gate_script(repo: pathlib.Path) -> None:
    _write(repo, ".github/scripts/gitapex_gate_new.py")


def _seed_nothing_applicable(repo: pathlib.Path) -> None:
    _write(repo, "README.md")


_SEEDS: dict[str, Callable[[pathlib.Path], None]] = {
    "skill-md-changed": _seed_skill_md,
    "description-changed-skills": _seed_description_change,
    "security-relevant-skills": _seed_security_relevant,
    "changed-design-docs": _seed_design_doc,
    "changed-checker-scripts": _seed_checker_script,
    "changed-gate-scripts": _seed_gate_script,
    "not-applicable": _seed_nothing_applicable,
}


@pytest.mark.parametrize("seed_name", sorted(_SEEDS), ids=sorted(_SEEDS))
def test_the_workflow_step_and_the_local_command_agree(
    seed_name: str, diff_step_script: pathlib.Path, repo: pathlib.Path, outdir: pathlib.Path
) -> None:
    _SEEDS[seed_name](repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, seed_name)
    assert _workflow_flags(diff_step_script, repo, outdir, base) == _local_flags(repo, base)


def test_the_parity_harness_can_actually_tell_flag_sets_apart(
    diff_step_script: pathlib.Path, repo: pathlib.Path, outdir: pathlib.Path
) -> None:
    """Guards every assertion above: if `_workflow_flags` and `_local_flags`
    always returned the same constant, the parametrized test would pass
    while proving nothing."""
    _seed_gate_script(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "gate")
    gate_flags = _workflow_flags(diff_step_script, repo, outdir, base)

    _seed_nothing_applicable(repo)
    unrelated_base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "unrelated")
    assert gate_flags != _workflow_flags(diff_step_script, repo, outdir, unrelated_base)


# --- claim 2: every conditional extension, through the documented command ---


def test_a_diff_needing_no_disclosure_passes_locally(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_nothing_applicable(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "unrelated")
    code, output = _run_local_wrapper(repo, base, "# no evidence section\n", outdir)
    assert code == 0, output
    assert "triggers no skill-audit disclosure requirement" in output


def test_the_base_two_audit_check_still_fires_locally(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_skill_md(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "skill")
    code, output = _run_local_wrapper(repo, base, "# no evidence section\n", outdir)
    assert code == 1
    assert "battle-testing-a-skill" in output


def test_extension_1_description_change_rejects_a_battle_testing_waiver(
    repo: pathlib.Path, outdir: pathlib.Path
) -> None:
    """The extension the hook's own docstring names first."""
    _seed_description_change(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "description change")
    body = (
        "## Skill audit evidence\n\n"
        "- battle-testing-a-skill: WAIVED: no time\n"
        "- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
        "- eval-coverage-disclosure: WAIVED: covered separately\n"
    )
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 1
    assert "cannot be disclosed as WAIVED" in output


def test_extension_1_accepts_a_real_verdict_instead(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_description_change(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "description change")
    body = _BASE_EVIDENCE + "- eval-coverage-disclosure: WAIVED: covered separately\n"
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 0, output


def test_extension_2_eval_coverage_is_required_locally(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_description_change(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "description change")
    code, output = _run_local_wrapper(repo, base, _BASE_EVIDENCE, outdir)
    assert code == 1
    assert "eval-coverage" in output


def test_extension_2_is_satisfied_by_touching_the_skills_own_evals(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _write(repo, "skills/sample/SKILL.md", _PLAIN_SKILL_MD)
    _commit(repo, "seed")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _write(repo, "skills/sample/SKILL.md", _PLAIN_SKILL_MD.replace("ordinary", "unusual"))
    _write(repo, "evals/sample/eval-status.md", "# status\n")
    _commit(repo, "description change with eval coverage")
    code, output = _run_local_wrapper(repo, base, _BASE_EVIDENCE, outdir)
    assert code == 0, output


def test_extension_3_security_relevance_is_flagged_locally(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_security_relevant(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "security-relevant skill")
    body = _BASE_EVIDENCE + "- eval-coverage-disclosure: WAIVED: new skill\n"
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 1
    assert "adversarial-coverage-mapping" in output


def test_extension_3_passes_once_disclosed(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_security_relevant(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "security-relevant skill")
    body = _BASE_EVIDENCE + "- eval-coverage-disclosure: WAIVED: new skill\n" + "- adversarial-coverage-mapping: RAN\n"
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 0, output


def test_extension_4_design_doc_coverage_is_flagged_locally(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_design_doc(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "design doc")
    code, output = _run_local_wrapper(repo, base, "# no evidence section\n", outdir)
    assert code == 1
    assert "design-doc-adversarial-review" in output


def test_extension_4_passes_once_disclosed(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_design_doc(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "design doc")
    body = "## Skill audit evidence\n\n- design-doc-adversarial-review: RAN\n"
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 0, output


def test_extension_5_deterministic_gate_quality_is_flagged_locally(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    """The extension the retrospectives cited most often, and the only one
    whose vocabulary rejects NOT-RUN."""
    _seed_gate_script(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "new gate")
    body = "## Skill audit evidence\n\n- checker-script-adversarial-review: RAN\n"
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 1
    assert "deterministic-gate-quality" in output


def test_extension_5_still_rejects_not_run_locally(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_gate_script(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "new gate")
    body = (
        "## Skill audit evidence\n\n- checker-script-adversarial-review: RAN\n- deterministic-gate-quality: NOT-RUN\n"
    )
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 1
    assert "deterministic-gate-quality" in output


def test_extension_5_passes_on_ran(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_gate_script(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "new gate")
    body = "## Skill audit evidence\n\n- checker-script-adversarial-review: RAN\n- deterministic-gate-quality: RAN\n"
    code, output = _run_local_wrapper(repo, base, body, outdir)
    assert code == 0, output


# --- the mode's own guardrails ---


def test_check_diff_refuses_to_run_alongside_explicit_flags(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    _seed_gate_script(repo)
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "new gate")
    body_file = outdir / "body.md"
    body_file.write_text(_BASE_EVIDENCE, encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(repo / ".github" / "scripts" / "gitapex_gate_skill_audit_disclosure.py"),
            "--check-diff",
            base,
            "HEAD",
            "--body-file",
            str(body_file),
            "--changed-gate-scripts",
            "",
            "--security-relevant-skills",
            "made-up",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "computes the applicability flags itself" in proc.stderr


def test_check_diff_reports_an_uncomputable_diff_rather_than_passing(repo: pathlib.Path, outdir: pathlib.Path) -> None:
    """Fail closed: a flag set that could not be computed must not read as
    'nothing to disclose'."""
    _write(repo, ".gitapex/ssot.json", "{not json")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(repo, "break the registry")
    code, output = _run_local_wrapper(repo, base, _BASE_EVIDENCE, outdir)
    assert code == 1
    assert "could not compute this diff's applicability flags" in output

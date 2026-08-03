"""Drift gate: every `_PROCESS_DISCLOSURE_CHECKS` row must actually be
wired into `.github/workflows/skill-audit-gate.yml`.

Issue #673 (refs #665 repair 1). The registry in
`.github/scripts/gate_skill_audit_disclosure.py` makes adding a
process-disclosure check look like a one-row edit -- an earlier revision of
its own comment said exactly that. It is not, and the gap is invisible:
applicability comes from the workflow, not from the table. Add a row and
skip the YAML edit and argparse still registers the flag with
`default=""`, so in real CI the list is empty, `_missing_in_section`
returns `[]`, and the check silently never fires. Every unit test calling
that row's `find_missing_*` wrapper directly still passes, because those
tests supply the item list themselves. CI stays green while the gate is
absent -- the same fail-open class the `deterministic-gate-quality` check
exists to catch, one layer up in the machinery that implements it.

That is what this file gates. It is deliberately a structural check on the
workflow text rather than a behavioural one: the wiring is four separate
edits in two steps (the `$GITHUB_OUTPUT` write on the applicable path, the
one on the early-exit path, the `env:` entry, and the CLI argument), and
missing any single one of them produces a different silent failure.

The `.gitapex/ssot.json` registration is checked here too, for the same
reason: `scan_ssot_schema.py` verifies every registered script path exists,
but nothing verified the converse for this gate's own helper scripts.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "skill-audit-gate.yml"
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"

sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
import gate_skill_audit_disclosure as gate  # noqa: E402


def _job_steps():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return workflow["jobs"]["skill-audit-disclosure"]["steps"]


def _step_with(key, needle):
    for step in _job_steps():
        if needle in step.get(key, ""):
            return step
    raise AssertionError(f"no step whose {key} contains {needle!r}")


@pytest.fixture(scope="module")
def diff_step():
    return _step_with("run", "$GITHUB_OUTPUT")


@pytest.fixture(scope="module")
def check_step():
    return _step_with("run", "gate_skill_audit_disclosure.py")


@pytest.mark.parametrize("check", gate._PROCESS_DISCLOSURE_CHECKS, ids=lambda c: c.name)
def test_every_registered_check_is_passed_on_the_command_line(check, check_step):
    """Without this, the flag defaults to '' and the check never fires."""
    assert check.cli_flag in check_step["run"], (
        f"{check.name} is registered in _PROCESS_DISCLOSURE_CHECKS but "
        f"{check.cli_flag} is never passed to the gate script, so the check "
        "can never fire in CI"
    )


@pytest.mark.parametrize("check", gate._PROCESS_DISCLOSURE_CHECKS, ids=lambda c: c.name)
def test_every_registered_check_reads_a_step_output_through_env(check, check_step):
    """The value must arrive via `env:` indirection, never interpolated
    straight into the `run:` block (dimensions.md dimension 5)."""
    env = check_step.get("env", {})
    referenced = [name for name, value in env.items() if "steps.diff.outputs" in str(value)]
    assert referenced, "the check step reads no diff-step output at all"
    run = check_step["run"]
    # The flag's argument must be a shell expansion of one of those env
    # vars, not a literal or a `${{ }}` expression.
    flag_index = run.index(check.cli_flag) + len(check.cli_flag)
    argument = run[flag_index : flag_index + 60]
    assert any(f'"${name}"' in argument for name in referenced), (
        f"{check.cli_flag}'s argument is not an env-var expansion: {argument!r}"
    )


@pytest.mark.parametrize("check", gate._PROCESS_DISCLOSURE_CHECKS, ids=lambda c: c.name)
def test_every_registered_check_has_an_output_on_both_paths(check, diff_step):
    """The diff step writes $GITHUB_OUTPUT twice -- once on the early-exit
    (applicable=false) path and once on the applicable path. A key present
    on only one of them leaves the check step reading an empty string on
    the other, which is a silent skip rather than an error."""
    run = diff_step["run"]
    # Derive the output key from the CLI flag, which is the workflow's own
    # naming convention (--changed-gate-scripts -> changed-gate-scripts).
    key = check.cli_flag.lstrip("-")
    assert run.count(f"{key}=") >= 2, (
        f"'{key}=' is written {run.count(f'{key}=')} time(s) in the diff step; "
        "it must appear on both the early-exit and the applicable path"
    )


def test_helper_scripts_the_workflow_invokes_are_registered_in_ssot():
    """Every .github/scripts helper this workflow shells out to is part of
    this gate's implementation, so the registry must say so -- otherwise
    the deterministic-gate-quality check's own registry-based scope rule
    silently excludes the scripts that compute it."""
    run = "\n".join(step.get("run", "") for step in _job_steps())
    invoked = {
        f".github/scripts/{name}"
        for name in (
            "gate_skill_audit_disclosure.py",
            "detect_changed_gate_scripts.py",
            "skill_description_diff.py",
            "skill_security_relevance.py",
        )
        if f".github/scripts/{name}" in run
    }
    assert invoked, "the workflow invokes no .github/scripts helper at all"

    registry = json.loads(SSOT_PATH.read_text(encoding="utf-8"))
    entry = next(g for g in registry["gates"] if g["id"] == "skill-audit-disclosure")
    registered = set(entry["script"])
    missing = sorted(invoked - registered)
    assert not missing, (
        "the workflow invokes these scripts but .gitapex/ssot.json's "
        f"skill-audit-disclosure entry does not register them: {missing}"
    )


def test_gate_detection_helper_is_itself_in_scope_of_the_check_it_computes():
    """detect_changed_gate_scripts.py decides whether
    deterministic-gate-quality fires. A change to it that silently narrowed
    the scope would be exactly the fail-open this whole check exists to
    catch, so it must be in its own scope."""
    sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
    import detect_changed_gate_scripts as detect

    registered = detect.registered_gate_paths(REPO_ROOT)
    assert detect.is_gate_path(".github/scripts/detect_changed_gate_scripts.py", registered)

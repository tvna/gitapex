"""Tests for the committed-ruleset shape gate
(.github/scripts/gitapex_gate_ruleset_required_checks.py).

Refs #439. Two layers: synthetic fixtures pinning each finding this gate can
report, and a live pass over this repository's own `.github/rulesets/main.json`
and `.github/workflows/` -- because the whole point of the gate is that the
committed ruleset stays applicable to the workflows that actually exist, and a
gate green only against fixtures would not prove that.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import gitapex_gate_ruleset_required_checks as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

VALID: dict[str, Any] = {
    "name": "main-protection",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "bypass_actors": [],
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 0,
                "require_code_owner_review": True,
                "required_review_thread_resolution": True,
                "dismiss_stale_reviews_on_push": True,
                "allowed_merge_methods": ["merge", "squash"],
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": "always-runs"}]},
        },
    ],
}

UNFILTERED_WORKFLOW = """
name: Always
on:
  pull_request: {}
jobs:
  always-runs:
    runs-on: ubuntu-latest
    steps:
      - run: 'true'
"""

FILTERED_WORKFLOW = """
name: Sometimes
on:
  pull_request:
    paths:
      - "docs/**"
jobs:
  sometimes-runs:
    runs-on: ubuntu-latest
    steps:
      - run: 'true'
"""


def write_workflows(tmp_path: pathlib.Path, **files: str) -> pathlib.Path:
    directory = tmp_path / "workflows"
    directory.mkdir(exist_ok=True)
    for name, body in files.items():
        (directory / f"{name}.yml").write_text(body, encoding="utf-8")
    return directory


def write_ruleset(tmp_path: pathlib.Path, document: Any) -> pathlib.Path:
    path = tmp_path / "main.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_a_valid_ruleset_reports_no_findings(tmp_path: pathlib.Path) -> None:
    workflows = write_workflows(tmp_path, always=UNFILTERED_WORKFLOW)
    assert gate.find_violations(write_ruleset(tmp_path, VALID), workflows) == []


def test_a_path_filtered_workflow_cannot_back_a_required_check(tmp_path: pathlib.Path) -> None:
    # The whole reason this gate exists: such a check stays Pending forever on
    # any pull request that does not match the filter.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"][3]["parameters"]["required_status_checks"] = [{"context": "sometimes-runs"}]
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, some=FILTERED_WORKFLOW))
    assert len(findings) == 1
    assert "Pending forever" in findings[0]


def test_paths_ignore_is_treated_the_same_as_paths(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", 'pull_request:\n    paths-ignore:\n      - "docs/**"')
    findings = gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, always=workflow))
    assert len(findings) == 1


def test_a_types_only_trigger_still_qualifies(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    types: [opened, synchronize]")
    assert gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, always=workflow)) == []


def test_a_job_level_name_overrides_the_job_id(tmp_path: pathlib.Path) -> None:
    # GitHub names the check run after the job's `name:` when it sets one, so
    # that -- not the job id -- is what a required context must match.
    workflow = UNFILTERED_WORKFLOW.replace("  always-runs:\n", "  job_id:\n    name: always-runs\n")
    assert gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, always=workflow)) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda r: r.update({"enforcement": "disabled"}), "not 'active'"),
        (lambda r: r.update({"bypass_actors": [{"actor_id": 1}]}), "grants bypass actors"),
        (lambda r: r.update({"extra": 1}), "does not accept"),
        (lambda r: r.pop("conditions"), "missing required key"),
        (lambda r: r["rules"].pop(0), "has no 'deletion' rule"),
    ],
)
def test_each_shape_finding_is_reported(mutate: Any, expected: str, tmp_path: pathlib.Path) -> None:
    ruleset = json.loads(json.dumps(VALID))
    mutate(ruleset)
    findings = gate.find_violations(
        write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, always=UNFILTERED_WORKFLOW)
    )
    assert any(expected in finding for finding in findings), findings


def test_a_ruleset_requiring_no_checks_is_a_finding(tmp_path: pathlib.Path) -> None:
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"][3]["parameters"]["required_status_checks"] = []
    findings = gate.find_violations(
        write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, always=UNFILTERED_WORKFLOW)
    )
    assert any("requires no status checks at all" in finding for finding in findings)


def test_an_empty_workflow_directory_is_an_error_not_a_vacuous_pass(tmp_path: pathlib.Path) -> None:
    empty = tmp_path / "workflows"
    empty.mkdir()
    with pytest.raises(gate.RulesetGateError, match="refusing to report a vacuous pass"):
        gate.find_violations(write_ruleset(tmp_path, VALID), empty)


def test_non_mapping_workflow_documents_are_skipped(tmp_path: pathlib.Path) -> None:
    workflows = write_workflows(tmp_path, always=UNFILTERED_WORKFLOW, junk="- just a list\n")
    assert gate.find_violations(write_ruleset(tmp_path, VALID), workflows) == []


def test_load_json_rejects_a_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.RulesetGateError, match="cannot read"):
        gate.load_json(tmp_path / "absent.json")


def test_load_json_rejects_malformed_and_non_object_documents(tmp_path: pathlib.Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(gate.RulesetGateError, match="not valid JSON"):
        gate.load_json(broken)
    with pytest.raises(gate.RulesetGateError, match="must contain a JSON object"):
        gate.load_json(write_ruleset(tmp_path, ["a"]))


def test_load_json_rejects_a_non_utf8_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "main.json"
    path.write_bytes(b'{"name": "\xff\xfe"}')
    with pytest.raises(gate.RulesetGateError, match="cannot read"):
        gate.load_json(path)


def test_an_unreadable_workflow_file_stops_the_gate(tmp_path: pathlib.Path) -> None:
    # Skipping it would silently drop its jobs, and the only visible symptom
    # would be a valid required check reported as naming no job.
    workflows = write_workflows(tmp_path, always=UNFILTERED_WORKFLOW)
    (workflows / "broken.yml").write_bytes(b"name: \xff\xfe\n")
    with pytest.raises(gate.RulesetGateError, match="cannot read"):
        gate.find_violations(write_ruleset(tmp_path, VALID), workflows)


def test_an_unparseable_workflow_file_stops_the_gate(tmp_path: pathlib.Path) -> None:
    workflows = write_workflows(tmp_path, always=UNFILTERED_WORKFLOW, broken="on: [\n")
    with pytest.raises(gate.RulesetGateError, match="not valid YAML"):
        gate.find_violations(write_ruleset(tmp_path, VALID), workflows)


def test_required_contexts_tolerates_a_ruleset_with_no_checks_rule() -> None:
    assert gate.required_contexts({"rules": [{"type": "deletion"}]}) == []
    assert gate.required_contexts({"rules": [{"type": "required_status_checks", "parameters": None}]}) == []


def test_main_passes_against_this_repositorys_own_committed_ruleset(capsys: pytest.CaptureFixture[str]) -> None:
    # The live check: every context in .github/rulesets/main.json must still
    # name a job in a real, unfiltered workflow in .github/workflows/.
    assert gate.main([]) == 0
    assert "every required status check runs on every pull request" in capsys.readouterr().out


def test_main_reports_findings_as_annotations(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    ruleset = json.loads(json.dumps(VALID))
    ruleset["enforcement"] = "disabled"
    code = gate.main(
        [
            "--ruleset",
            str(write_ruleset(tmp_path, ruleset)),
            "--workflow-dir",
            str(write_workflows(tmp_path, always=UNFILTERED_WORKFLOW)),
        ]
    )
    assert code == 1
    assert "::error::" in capsys.readouterr().err


def test_main_reports_an_unreadable_ruleset_separately_from_a_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Exit 2, not 1: "the gate could not run" and "the gate found a problem"
    # are different outcomes and must not be reported as the same one.
    assert gate.main(["--ruleset", str(tmp_path / "absent.json")]) == 2
    assert "::error::" in capsys.readouterr().err


def test_the_repositorys_own_ruleset_is_the_gates_default_target() -> None:
    assert gate.DEFAULT_RULESET == REPO_ROOT / ".github" / "rulesets" / "main.json"
    assert gate.DEFAULT_WORKFLOW_DIR == REPO_ROOT / ".github" / "workflows"


SCALAR_TRIGGER_WORKFLOW = """
name: Scalar
on: pull_request
jobs:
  always-runs:
    runs-on: ubuntu-latest
    steps:
      - run: 'true'
"""

SEQUENCE_TRIGGER_WORKFLOW = """
name: Sequence
on: [push, pull_request]
jobs:
  always-runs:
    runs-on: ubuntu-latest
    steps:
      - run: 'true'
"""


def test_scalar_on_pull_request_syntax_is_recognised(tmp_path: pathlib.Path) -> None:
    # `on: pull_request` is unfiltered by construction. An earlier revision saw
    # only the mapping form and would have reported this reachable check as
    # naming no job -- a false failure blocking a merge.
    assert (
        gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, s=SCALAR_TRIGGER_WORKFLOW)) == []
    )


def test_sequence_on_syntax_is_recognised(tmp_path: pathlib.Path) -> None:
    assert (
        gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, s=SEQUENCE_TRIGGER_WORKFLOW))
        == []
    )


def test_a_branch_filter_excluding_the_protected_branch_cannot_back_a_required_check(
    tmp_path: pathlib.Path,
) -> None:
    # `branches` filters the BASE branch, so this workflow never runs for a
    # pull request into main and its check stays Pending forever.
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches: [release]")
    findings = gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, b=workflow))
    assert len(findings) == 1
    assert "Pending forever" in findings[0]


def test_a_branch_filter_including_the_protected_branch_is_accepted(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches: [main, release]")
    assert gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, b=workflow)) == []


def test_a_glob_branch_filter_matching_the_protected_branch_is_accepted(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches: ['mai*']")
    assert gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, b=workflow)) == []


def test_a_negated_branch_pattern_excluding_the_protected_branch_is_rejected(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches: ['*', '!main']")
    assert len(gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, b=workflow))) == 1


def test_branches_ignore_covering_the_protected_branch_is_rejected(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches-ignore: [main]")
    assert len(gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, b=workflow))) == 1


def test_an_incomplete_types_list_cannot_back_a_required_check(tmp_path: pathlib.Path) -> None:
    # `types:` replaces the default set rather than extending it, so a workflow
    # listening only for `closed` never starts on an open pull request.
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    types: [closed]")
    assert len(gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, t=workflow))) == 1


def test_types_missing_synchronize_cannot_back_a_required_check(tmp_path: pathlib.Path) -> None:
    # Without `synchronize` the check never re-runs on a push to the branch,
    # so it stays stuck at whatever the first commit produced.
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    types: [opened, reopened]")
    assert len(gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, t=workflow))) == 1


def test_the_default_branch_is_configurable(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches: [release]")
    workflows = write_workflows(tmp_path, b=workflow)
    assert gate.find_violations(write_ruleset(tmp_path, VALID), workflows, "release") == []
    assert len(gate.find_violations(write_ruleset(tmp_path, VALID), workflows, "main")) == 1


# --- Findings from an independent review round: the gate claimed to enforce
# --- properties it never inspected, and three classifier shapes failed open.


def test_a_ruleset_scoped_to_another_branch_is_a_finding(tmp_path: pathlib.Path) -> None:
    # Every rule present, protecting a ref that does not exist. Rule-presence
    # checking alone reported this as green.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["conditions"]["ref_name"]["include"] = ["refs/heads/nonexistent"]
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any("~DEFAULT_BRANCH" in finding for finding in findings), findings


def test_excluding_the_default_branch_cancels_the_include(tmp_path: pathlib.Path) -> None:
    ruleset = json.loads(json.dumps(VALID))
    ruleset["conditions"]["ref_name"]["exclude"] = ["~DEFAULT_BRANCH"]
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any("cancelling the include" in finding for finding in findings), findings


def test_a_non_branch_target_is_a_finding(tmp_path: pathlib.Path) -> None:
    ruleset = json.loads(json.dumps(VALID))
    ruleset["target"] = "tag"
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any("not 'branch'" in finding for finding in findings), findings


@pytest.mark.parametrize("flag", list(gate.REQUIRED_PULL_REQUEST_FLAGS))
def test_each_required_pull_request_flag_must_be_true(flag: str, tmp_path: pathlib.Path) -> None:
    ruleset = json.loads(json.dumps(VALID))
    parameters: dict[str, Any] = dict.fromkeys(gate.REQUIRED_PULL_REQUEST_FLAGS, True)
    parameters["allowed_merge_methods"] = ["merge"]
    parameters[flag] = False
    ruleset["rules"][2]["parameters"] = parameters
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any(flag in finding for finding in findings), findings


def test_a_rebase_only_merge_policy_is_a_finding(tmp_path: pathlib.Path) -> None:
    # rebase replays branch commits without a merge commit, so no path carries
    # the pull request's own review with it.
    ruleset = json.loads(json.dumps(VALID))
    parameters: dict[str, Any] = dict.fromkeys(gate.REQUIRED_PULL_REQUEST_FLAGS, True)
    parameters["allowed_merge_methods"] = ["rebase"]
    ruleset["rules"][2]["parameters"] = parameters
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any("no reviewed merge path remains" in finding for finding in findings), findings


def test_a_scalar_branches_ignore_is_honoured(tmp_path: pathlib.Path) -> None:
    # `branches-ignore: main` and `branches-ignore: [main]` mean the same thing
    # to GitHub; only the list form was recognised, so the scalar failed open.
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches-ignore: main")
    assert len(gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, b=workflow))) == 1


def test_a_scalar_types_value_is_honoured(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    types: opened")
    assert len(gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, t=workflow))) == 1


def test_a_scalar_branches_naming_the_default_branch_is_accepted(tmp_path: pathlib.Path) -> None:
    workflow = UNFILTERED_WORKFLOW.replace("pull_request: {}", "pull_request:\n    branches: main")
    assert gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, b=workflow)) == []


def test_a_matrix_job_cannot_back_a_required_check(tmp_path: pathlib.Path) -> None:
    # A matrix job reports as `always-runs (3.11)` etc., never as the bare job
    # id, so requiring the bare name leaves the check Pending forever.
    workflow = UNFILTERED_WORKFLOW.replace(
        "  always-runs:\n", "  always-runs:\n    strategy:\n      matrix:\n        python: ['3.11', '3.12']\n"
    )
    findings = gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, m=workflow))
    assert len(findings) == 1
    assert "Pending forever" in findings[0]


def test_a_reusable_workflow_call_cannot_back_a_required_check(tmp_path: pathlib.Path) -> None:
    # A `uses:` job reports its inner jobs as `always-runs / inner`, never as
    # the bare caller job id, so requiring the bare name leaves it Pending.
    workflow = """
name: Always
on:
  pull_request: {}
jobs:
  always-runs:
    uses: ./.github/workflows/other.yml
"""
    findings = gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, r=workflow))
    assert len(findings) == 1
    assert "Pending forever" in findings[0]

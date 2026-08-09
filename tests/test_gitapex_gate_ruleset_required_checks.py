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
                "require_last_push_approval": False,
                "allowed_merge_methods": ["merge", "squash"],
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [{"context": "always-runs"}],
            },
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
        (lambda r: r.update({"extra": 1}), "Extra inputs are not permitted"),
        (lambda r: r.pop("conditions"), "Field required"),
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
    # Flipped on the complete fixture rather than rebuilt from scratch: a
    # partial parameters dict is a schema error now, which would mask the policy
    # finding this test exists to pin. A schema says "boolean"; only a policy
    # says "true".
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"][2]["parameters"][flag] = False
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any(flag in finding for finding in findings), findings


def test_a_rebase_only_merge_policy_is_a_finding(tmp_path: pathlib.Path) -> None:
    # rebase replays branch commits without a merge commit, so no path carries
    # the pull request's own review with it.
    # Schema-valid -- rebase is a real GitHub merge method -- so this can only
    # ever be a policy finding.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"][2]["parameters"]["allowed_merge_methods"] = ["rebase"]
    assert gate.find_schema_violations(ruleset) == []
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


def test_a_missing_pull_request_rule_is_reported_once_not_twice(tmp_path: pathlib.Path) -> None:
    # `_find_pull_request_violations` returns early when the rule is absent, so
    # the operator gets "has no 'pull_request' rule" rather than that plus a
    # pile of derived "flag is None, not true" noise about a rule that is not
    # there.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"] = [rule for rule in ruleset["rules"] if rule["type"] != "pull_request"]
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any("has no 'pull_request' rule" in finding for finding in findings), findings
    assert not any("not true" in finding for finding in findings), findings


@pytest.mark.parametrize("parameters", [None, [], "merge"])
def test_a_pull_request_rule_without_a_parameters_object_is_a_finding(parameters: Any, tmp_path: pathlib.Path) -> None:
    # GitHub's API accepts a bare `{"type": "pull_request"}`, which enforces
    # none of the review settings this repository claims. A presence-only check
    # would pass it; the schema layer rejects the shape outright.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"][2]["parameters"] = parameters
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any("parameters" in finding for finding in findings), findings


@pytest.mark.parametrize("methods", [None, [], "merge", {"merge": True}, ["fast_forward"]])
def test_an_unusable_allowed_merge_methods_value_is_a_finding(methods: Any, tmp_path: pathlib.Path) -> None:
    # An empty list is the dangerous one: it type-checks as a list and reads as
    # "no restriction" to a skim while naming no permitted merge path at all.
    # `min_length=1` on the model is what catches it; the invented method is
    # caught by the Literal.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"][2]["parameters"]["allowed_merge_methods"] = methods
    findings = gate.find_violations(write_ruleset(tmp_path, ruleset), write_workflows(tmp_path, a=UNFILTERED_WORKFLOW))
    assert any("allowed_merge_methods" in finding for finding in findings), findings


def test_a_non_mapping_job_body_still_resolves_to_its_job_id(tmp_path: pathlib.Path) -> None:
    # A job whose body is not a mapping is malformed YAML that actionlint would
    # reject, but this gate must not crash on it on the way to saying so: it
    # falls back to the job id, which is the most conservative reading (the
    # context is treated as satisfiable rather than silently dropped, and the
    # empty-workflow-directory guard still refuses a vacuous pass).
    workflow = "name: Always\non:\n  pull_request: {}\njobs:\n  always-runs: 'not a mapping'\n"
    assert gate.find_violations(write_ruleset(tmp_path, VALID), write_workflows(tmp_path, a=workflow)) == []


@pytest.mark.parametrize("jobs_value", ["not a mapping", "[a, b]", "42"])
def test_a_non_mapping_jobs_key_does_not_crash_the_gate(jobs_value: str, tmp_path: pathlib.Path) -> None:
    # `document.get("jobs") or {}` covered a missing or null `jobs:` but not a
    # present one that is not a mapping, so this raised AttributeError straight
    # past main()'s `except RulesetGateError` -- a raw traceback on the local
    # pre-push run for a file actionlint would reject anyway.
    broken = f"name: Broken\non:\n  pull_request: {{}}\njobs: {jobs_value}\n"
    workflows = write_workflows(tmp_path, always=UNFILTERED_WORKFLOW, broken=broken)
    assert gate.find_violations(write_ruleset(tmp_path, VALID), workflows) == []


def test_a_non_mapping_jobs_key_reaches_the_gates_own_exit_path(tmp_path: pathlib.Path) -> None:
    # End to end through the real CLI, because the regression was specifically
    # that main()'s typed-error path was bypassed.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"][3]["parameters"]["required_status_checks"] = [{"context": "absent-job"}]
    workflows = write_workflows(tmp_path, broken="name: B\non:\n  pull_request: {}\njobs: 'text'\n")
    code = gate.main(["--ruleset", str(write_ruleset(tmp_path, ruleset)), "--workflow-dir", str(workflows)])
    assert code == 1


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        # Every one of these passed with exit 0 and "shape is valid" before the
        # schema layer existed; the key-set check only looked at the top level.
        (
            lambda r: r["rules"][2]["parameters"].update({"require_code_owner_reviews": True}),
            "require_code_owner_reviews: Extra inputs are not permitted",
        ),
        (
            lambda r: r["rules"][2]["parameters"].update({"required_approving_review_count": "zero"}),
            "required_approving_review_count: Input should be a valid integer",
        ),
        (lambda r: r["rules"].append({"type": "invented"}), "does not match any of the expected tags"),
        (lambda r: r["rules"][2]["parameters"].update({"allowed_merge_methods": ["fast_forward"]}), "allowed_merge"),
        (lambda r: r["rules"][2]["parameters"].pop("require_last_push_approval"), "Field required"),
        (lambda r: r["conditions"]["ref_name"].update({"typo": []}), "Extra inputs are not permitted"),
        (lambda r: r.update({"enforcement": "on"}), "enforcement"),
        (lambda r: r.update({"target": "everything"}), "target"),
        (lambda r: r.update({"name": ""}), "name"),
        (lambda r: r["rules"][3]["parameters"]["required_status_checks"].append({"ctx": "x"}), "Extra inputs"),
    ],
)
def test_the_schema_layer_rejects_what_the_key_set_check_could_not_see(
    mutate: Any, expected: str, tmp_path: pathlib.Path
) -> None:
    ruleset = json.loads(json.dumps(VALID))
    mutate(ruleset)
    findings = gate.find_schema_violations(ruleset)
    assert any(expected in finding for finding in findings), findings


def test_the_committed_ruleset_validates_against_the_schema() -> None:
    # The live pass that matters: the model is only worth anything if this
    # repository's own source of truth satisfies it.
    assert gate.find_schema_violations(gate.load_json(REPO_ROOT / ".github" / "rulesets" / "main.json")) == []


def test_schema_errors_short_circuit_the_policy_checks(tmp_path: pathlib.Path) -> None:
    # A document of unknown shape makes every policy check below it read fields
    # that may not be the type it assumes, so the operator would get one real
    # error buried under a pile of consequences of it.
    ruleset = json.loads(json.dumps(VALID))
    ruleset["rules"] = "not a list"
    findings = gate.find_shape_violations(ruleset)
    assert all("rules" in finding for finding in findings), findings


def test_the_schema_accepts_the_documented_rollback_enforcement_values() -> None:
    # `evaluate` and `disabled` are the runbook's rollback lever, so they must
    # stay *valid* and be reported by the policy layer instead -- schema says
    # what is expressible, policy says what this repository has chosen.
    for value in ("evaluate", "disabled"):
        ruleset = json.loads(json.dumps(VALID))
        ruleset["enforcement"] = value
        assert gate.find_schema_violations(ruleset) == []
        assert any("not 'active'" in finding for finding in gate.find_shape_violations(ruleset))

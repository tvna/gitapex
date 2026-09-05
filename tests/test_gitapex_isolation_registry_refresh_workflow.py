"""Governance test for .github/workflows/isolation-registry-refresh.yml
(issue #1809's Testing section requirement, design doc "Components" item 4).

The workflow's own "propose via PR, never auto-promote" constraint --
an entry becomes Reviewed once a human merges the proposed PR, not once the
scheduled job writes it -- must be a property of the workflow's own code
path, not merely asserted in prose. This test greps the workflow file's own
`run:` step bodies for a merge/auto-promote API call and fails if one is
found, rather than trusting the file's own comments.

Deliberately a plain string/YAML-structure check, not a full shell parser:
this workflow is short and hand-authored, and a `run:` step is plain shell
text, not a further-nested grammar this repository has any existing parser
for. See the module docstring's own "Known misses" precedent in
.github/scripts/gitapex_gate_function_body_test_coverage.py for why a
heuristic string check is an accepted, disclosed limit elsewhere in this
repository's own gate suite, not a novel shortcut invented here.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github/workflows/isolation-registry-refresh.yml"

# Any of these appearing in a `run:` step body would mean the job merges or
# auto-promotes a PR itself, defeating the human/PR review gate the Trust
# class rule depends on.
_FORBIDDEN_SUBSTRINGS = (
    "gh pr merge",
    "gh pr edit --auto",
    "--auto-merge",
    "enable_pr_auto_merge",
    "merge_pull_request",
    "gh pr review",
)


def _load_workflow() -> dict[str, object]:
    data = yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _iter_run_step_bodies(workflow: dict[str, object]) -> list[str]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict), "workflow has no jobs: mapping"
    bodies: list[str] = []
    for job in jobs.values():
        assert isinstance(job, dict)
        for step in job.get("steps", []):
            assert isinstance(step, dict)
            run_body = step.get("run")
            if isinstance(run_body, str):
                bodies.append(run_body)
    return bodies


def test_workflow_file_exists_and_parses_as_yaml() -> None:
    workflow = _load_workflow()
    assert workflow.get("name") == "Isolation registry refresh"


def test_workflow_has_at_least_one_run_step() -> None:
    bodies = _iter_run_step_bodies(_load_workflow())
    assert len(bodies) >= 3


def test_workflow_never_merges_or_auto_promotes_a_pr() -> None:
    bodies = _iter_run_step_bodies(_load_workflow())
    combined = "\n".join(bodies).lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in combined, (
            f"isolation-registry-refresh.yml's own run: step text contains "
            f"{forbidden!r} -- this workflow must only ever propose a PR, "
            f"never merge or auto-promote one (issue #1809)"
        )


def test_workflow_only_opens_a_pr_via_gh_pr_create() -> None:
    bodies = _iter_run_step_bodies(_load_workflow())
    combined = "\n".join(bodies)
    assert "gh pr create" in combined


def test_workflow_opens_an_issue_on_control_failure() -> None:
    bodies = _iter_run_step_bodies(_load_workflow())
    combined = "\n".join(bodies)
    assert "gh issue create" in combined


def test_workflow_runs_controls_only_mode() -> None:
    bodies = _iter_run_step_bodies(_load_workflow())
    combined = "\n".join(bodies)
    assert "--controls-only" in combined
    # Never launches a real target dispatch in this job -- no --target flag
    # anywhere in a run: step body.
    assert "--target" not in combined


def test_workflow_requires_anthropic_api_key() -> None:
    bodies = _iter_run_step_bodies(_load_workflow())
    combined = "\n".join(bodies)
    assert "ANTHROPIC_API_KEY" in combined

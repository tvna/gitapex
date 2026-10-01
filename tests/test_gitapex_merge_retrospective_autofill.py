"""Drift guards for `.github/workflows/merge-retrospective-autofill.yml`
(issue #769: a deterministic, event-triggered mechanism that runs
`skills/merge-retrospective/SKILL.md`'s content-filling procedure against
a freshly-opened bare stub retrospective issue, without depending on an
agent remembering to invoke it or a human asking).

This workflow has no companion `.github/scripts/*.py` module (unlike
`gitapex_post_merge_retro.py` / `gitapex_stale_retro_stub_autoclose.py`) -- it is a
prompt-driven `anthropics/claude-code-action@v1` dispatch, the same shape
`ranking-the-open-queue-weekly.yml` already uses. These tests only check
the workflow file's own static shape: permissions, tool scoping, and the
marker-text literal it shares with `gitapex_stale_retro_stub_autoclose.py`, the
same class of drift guard `tests/test_gitapex_stale_retro_stub_autoclose.py`
and `tests/test_gitapex_post_merge_retro.py` already apply to their own
workflows.
"""

from __future__ import annotations

import pathlib

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "merge-retrospective-autofill.yml"

_STUB_MARKER = "Automated stub opened by the post-merge-auto-retro gate"

# Same shape as test_gitapex_stale_retro_stub_autoclose.py's own
# _MERGE_CAPABLE_MARKERS, minus its generic "/merge" fragment: this
# workflow's own prompt legitimately mentions "skills/merge-retrospective"
# (the skill it runs) many times, which itself contains the substring
# "/merge" -- a false positive unrelated to merge capability. The
# GitHub-REST-path-specific "pulls/merge" fragment below still catches the
# real API shape ("/repos/{owner}/{repo}/pulls/{n}/merge") without that
# collision. The workflow's own prompt text is also written to avoid ever
# spelling out a merge-capable tool name literally (matching
# ranking-the-open-queue-weekly.yml's own prompt convention) specifically
# so a legitimate "never call the tool that merges a PR"-style prohibition
# in prose cannot itself trip this drift guard.
_MERGE_CAPABLE_MARKERS = (
    "gh pr merge",
    "gh pr merge --auto",
    "merge_pull_request",
    "enable_pr_auto_merge",
    "pulls/merge",
)


def _load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _iter_permissions_blocks(workflow):
    top_level = workflow.get("permissions")
    if top_level is not None:
        yield "top-level", top_level
    for job_name, job in (workflow.get("jobs") or {}).items():
        job_permissions = job.get("permissions")
        if job_permissions is not None:
            yield f"job:{job_name}", job_permissions


def test_workflow_file_exists_and_parses():
    assert WORKFLOW_PATH.is_file(), f"expected {WORKFLOW_PATH} to exist"
    workflow = _load_workflow()
    assert workflow.get("jobs"), f"{WORKFLOW_PATH} has no jobs -- parse likely broke"


def test_workflow_never_grants_pull_requests_write():
    workflow = _load_workflow()
    offenders = []
    for scope_name, permissions in _iter_permissions_blocks(workflow):
        if not isinstance(permissions, dict):
            offenders.append((scope_name, permissions))
            continue
        pr_permission = permissions.get("pull-requests")
        if pr_permission is not None and pr_permission != "read" and pr_permission != "none":
            offenders.append((scope_name, permissions))
    assert not offenders, (
        f"{WORKFLOW_PATH} grants pull-requests write (or an unparseable blanket "
        f"permission) in: {offenders} -- this workflow may only ever read a "
        "pull request's history and update one already-open retrospective "
        "issue; a merge-capable permission here would violate this "
        "repository's permanent human-review-of-merge posture."
    )


def test_workflow_has_no_merge_capable_step():
    workflow = _load_workflow()
    offenders = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            haystack = " ".join(str(step.get(key, "")) for key in ("run", "uses", "with")).lower()
            hits = [marker for marker in _MERGE_CAPABLE_MARKERS if marker in haystack]
            if hits:
                offenders.append((job_name, step.get("name", "<unnamed step>"), hits))
    assert not offenders, (
        f"{WORKFLOW_PATH} has a step that looks merge-capable: {offenders} -- this "
        "repository's 100% human review of merges is a permanent architectural "
        "feature; this workflow may never merge a pull request itself."
    )


def test_stub_marker_matches_post_merge_retro_source():
    """Drift gate mirroring test_gitapex_stale_retro_stub_autoclose.py's identical
    guard: the marker-text literal this workflow's own `if:` pre-filter and
    prompt both reference must stay byte-identical to the string
    gitapex_post_merge_retro.py actually embeds in a stub's body -- otherwise the
    pre-filter (or the agent's own re-check) silently never matches a real
    stub.
    """
    source = (REPO_ROOT / ".github" / "scripts" / "gitapex_post_merge_retro.py").read_text(encoding="utf-8")
    assert _STUB_MARKER in source
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert _STUB_MARKER in workflow_text


def test_workflow_triggers_on_issues_and_workflow_dispatch():
    workflow = _load_workflow()
    # PyYAML parses the bare `on:` key as boolean True, not the string "on".
    triggers = workflow.get(True, workflow.get("on"))
    assert triggers is not None, f"{WORKFLOW_PATH} has no top-level trigger"
    assert "issues" in triggers, f"{WORKFLOW_PATH} must trigger on issues events"
    assert set(triggers["issues"].get("types", [])) >= {"opened", "labeled"}
    assert "workflow_dispatch" in triggers, f"{WORKFLOW_PATH} needs a manual workflow_dispatch recovery path"


def _claude_args_value(workflow):
    for job in (workflow.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            with_block = step.get("with")
            if isinstance(with_block, dict) and "claude_args" in with_block:
                return str(with_block["claude_args"])
    raise AssertionError(f"{WORKFLOW_PATH} has no step with a 'claude_args' input")


def test_allowed_tools_excludes_merge_capable_tools_and_includes_required_ones():
    # Reads the parsed `with.claude_args` string, not a raw substring scan
    # of the whole file: this workflow's own header comments mention
    # "--allowedTools" by name before the real claude_args value appears,
    # so a naive `.index("--allowedTools")` over the raw file text finds
    # the comment first, not the actual allowlist.
    claude_args = _claude_args_value(_load_workflow())
    marker = "--allowedTools"
    idx = claude_args.index(marker)
    allowed_tools_line = claude_args[
        idx : claude_args.index("\n", idx) if "\n" in claude_args[idx:] else len(claude_args)
    ]
    for tool in ("mcp__github__merge_pull_request", "mcp__github__enable_pr_auto_merge"):
        assert tool not in allowed_tools_line
    for tool in (
        "mcp__github__issue_read",
        "mcp__github__issue_write",
        "mcp__github__search_issues",
        "mcp__github__search_commits",
        "mcp__github__pull_request_read",
    ):
        assert tool in allowed_tools_line

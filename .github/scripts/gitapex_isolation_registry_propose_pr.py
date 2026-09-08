#!/usr/bin/env python3
"""Open the "propose the registry update" pull request for
`.github/workflows/isolation-registry-refresh.yml`, via this repository's
own REST-wrapper convention (`_gitapex_github_http.py`) rather than the raw
`gh pr create` CLI call this replaces (issue #1809, Step 8 follow-up -- see
`gitapex_isolation_registry_open_contamination_issue.py`'s own module
docstring for the full rationale, shared here rather than repeated).

Never merges or enables auto-merge on the PR it opens -- this script only
ever calls `POST /repos/{owner}/{repo}/pulls`, nothing else --
`tests/test_gitapex_isolation_registry_refresh_workflow.py` asserts the
calling workflow's own text contains no merge/auto-promote API call, and
this script's own name/scope match that assertion: propose, never merge.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_isolation_registry_propose_pr.py \\
        --owner tvna --repo gitapex --head isolation-registry-refresh/2026-09-05 \\
        --base main --run-url https://github.com/tvna/gitapex/actions/runs/123

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs), matching isolation-registry-refresh.yml's own
invocation.

Environment variables:
    GITHUB_TOKEN  GitHub token with pull-requests:write (the default
                  Actions token's ``pull-requests: write`` permission
                  suffices).

Exit codes:
    0  PR opened successfully.
    1  Missing token, invalid arguments, or a GitHub API error prevented
       completion (never silently treated as success).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from typing import Any

from _gitapex_github_http import GitHubApiError, call_json, default_opener
from pydantic import BaseModel, Field, ValidationError, field_validator

_API_ROOT = "https://api.github.com"

# This CLI's own wording for each constraint the model below imposes, keyed
# by pydantic's own error type -- matching gitapex_stale_retro_stub_autoclose.py's
# own established convention (its own docstring has the full rationale for
# why pydantic's own message text is never echoed directly).
_CONSTRAINT_HINTS = {
    "string_too_short": "must not be blank",
    "value_error": "must not be blank",
}


class ProposeRegistryPrArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. Every field rejects
    blank -- argparse's own ``required=True`` only guarantees the flag was
    passed, not that its value is non-empty -- before any of it reaches a
    GitHub API URL or request body."""

    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    head: str = Field(min_length=1)
    base: str = Field(min_length=1)
    run_url: str = Field(min_length=1)

    @field_validator("owner", "repo", "head", "base", "run_url")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        # function-body-test-coverage: WAIVED: covered by test_main_rejects_blank_head, which exercises this validator through main()'s own pydantic call rather than naming it directly (issue #1809, Step 8 follow-up)
        if not value.strip():
            raise ValueError("must not be blank")
        return value


def propose_registry_pr(
    owner: str,
    repo: str,
    head: str,
    base: str,
    run_url: str,
    token: str,
    opener: Callable[[Any], Any] = default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> int:
    """Open the PR against an already-pushed `head` branch and return its
    number. `run_url` is deterministic GitHub Actions context this workflow
    itself constructs, not untrusted external text -- safe to embed
    directly (see the contamination-issue script's own identical note)."""
    sleeper = sleeper if sleeper is not None else time.sleep
    body = (
        f"Opened automatically by the isolation-registry-refresh workflow (run {run_url}). "
        "Adds a same-run-unreviewed registry entry established by a live two-control run at "
        "the current `claude` CLI version. Per adversarial-self-audit.md's Trust class rule, "
        "this entry becomes Reviewed once this PR merges, not before -- review the printed "
        "control transcripts in the linked run log before approving."
    )
    url = f"{_API_ROOT}/repos/{owner}/{repo}/pulls"
    payload = {
        "title": "chore(evaluating-skill-quality): scheduled isolation-registry same-run entry",
        "body": body,
        "head": head,
        "base": base,
    }
    # max_attempts=1: PR creation is not idempotent -- see call_json's own
    # docstring -- so a lost/truncated response is never retried into a
    # duplicate PR.
    result = call_json("POST", url, token, opener, sleeper, body=payload, max_attempts=1)
    return int(result["number"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Propose the isolation-registry same-run-entry PR.")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head", required=True, help="The already-pushed branch carrying the registry change")
    parser.add_argument("--base", required=True, help="The base branch to open the PR against, e.g. main")
    parser.add_argument("--run-url", required=True, help="This workflow run's own GitHub Actions URL")
    args = parser.parse_args(argv)
    try:
        ProposeRegistryPrArgs(owner=args.owner, repo=args.repo, head=args.head, base=args.base, run_url=args.run_url)
    except ValidationError as error:
        # Only the offending flag names and this CLI's own constraint
        # wording are echoed -- never pydantic's own message text.
        invalid = ", ".join(
            f"--{str(item['loc'][0]).replace('_', '-')} ({_CONSTRAINT_HINTS.get(item['type'], 'invalid value')})"
            for item in error.errors()
        )
        print(f"error: invalid arguments: {invalid}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        pr_number = propose_registry_pr(args.owner, args.repo, args.head, args.base, args.run_url, token)
        print(f"Opened PR #{pr_number} proposing the registry update.")
        return 0
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

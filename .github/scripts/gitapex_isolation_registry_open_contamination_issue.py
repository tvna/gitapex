#!/usr/bin/env python3
"""Open a "possible new contamination pattern" issue for
`.github/workflows/isolation-registry-refresh.yml`'s own control-failure
path, via this repository's own REST-wrapper convention
(`_gitapex_github_http.py`) rather than the raw `gh issue create` CLI call
this replaces (issue #1809, Step 8 follow-up -- an independent convention
review found the workflow's own two write operations were the only ones in
the repository shelling out to `gh` directly, contradicting AGENTS.md
section 3's "use platform-integrated tool calls...or the repository's
approved REST API wrapper...do not invoke command-line GitHub tools
directly" and the real prior incident (issue #529) that convention exists
to prevent).

Deliberately does not attempt dedup against an already-open contamination
issue -- unlike `gitapex_post_merge_retro.py`'s own dedup-by-PR-number
check, there is no single stable key (a run ID changes every firing) to
dedup a "possible new contamination pattern" issue against; an operator
seeing two such issues for the same underlying cause can close one as a
duplicate by hand.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from typing import Any

from _gitapex_github_http import GitHubApiError, call_json, default_opener

_API_ROOT = "https://api.github.com"


def open_contamination_issue(
    owner: str,
    repo: str,
    run_url: str,
    token: str,
    opener: Callable[[Any], Any] = default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> int:
    """Open the contamination-finding issue and return its number. `run_url`
    is a GitHub Actions run URL this workflow itself constructs from
    `github.server_url`/`github.repository`/`github.run_id` -- deterministic
    context, not untrusted external text, so it is safe to embed directly
    (contrast `gitapex_post_merge_retro.py`'s own deliberate exclusion of a
    PR title from its issue body)."""
    sleeper = sleeper if sleeper is not None else time.sleep
    body = (
        "The scheduled isolation-registry-refresh workflow's live two-control "
        "run failed on the `claude` CLI version reported by this run. This can "
        "mean a genuinely new contamination pattern, not merely an "
        "as-yet-unverified CLI version. See this run's own log for the full "
        f"control transcripts: {run_url}. Investigate per "
        "skills/evaluating-skill-quality/scripts/gitapex_run_verified_isolated_dispatch.py's "
        "own module docstring (the current two-control methodology) before "
        "trusting any isolated dispatch on this platform."
    )
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues"
    payload = {
        "title": "isolation-registry-refresh: possible new contamination pattern found",
        "body": body,
        "labels": ["bug"],
    }
    # max_attempts=1: issue creation is not idempotent -- see call_json's own
    # docstring -- so a lost/truncated response is never retried into a
    # duplicate issue.
    result = call_json("POST", url, token, opener, sleeper, body=payload, max_attempts=1)
    return int(result["number"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open a possible-new-contamination-pattern issue.")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-url", required=True, help="This workflow run's own GitHub Actions URL")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        issue_number = open_contamination_issue(args.owner, args.repo, args.run_url, token)
        print(f"Opened contamination-finding issue #{issue_number}.")
        return 0
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

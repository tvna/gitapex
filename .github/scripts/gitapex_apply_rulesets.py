#!/usr/bin/env python3
"""Plan or apply `.github/rulesets/*.json` against the live GitHub Rulesets API.

Issue #439. This is the *only* thing in this repository that writes to the
rulesets endpoint, and it is invoked exclusively as a step of
`.github/workflows/apply-rulesets.yml` -- a `workflow_dispatch`-only workflow
that defaults to `dry_run: true` and reads a dedicated `RULESETS_PAT` bound to
the `ruleset-apply` GitHub Environment. No interactive agent session calls this
script, and no automatic trigger does either. That shape is deliberate and is
the whole reason the mutating path is a CI step rather than a tool call: giving
`main` its protection is an outward-facing, hard-to-reverse action, so a human
dispatches it after reading a dry-run plan (CLAUDE.md section 4).

**Plan mode makes no write of any kind.** `--mode plan` performs GET requests
only; the POST/PUT body it prints is the body it *would* send. This is the
default in the workflow, and re-running with `--mode apply` after reading that
plan is the documented sequence in `docs/runbooks/rulesets.md`.

**Why POST-vs-PUT is derived, not configured.** The operator does not tell this
script whether the ruleset already exists; it looks. Zero live rulesets with
the committed `name` means POST (create), exactly one means PUT (replace that
id), and more than one is refused outright rather than guessed at -- see
`_gitapex_rulesets.resolve_live_ruleset` for why guessing is unsafe. An
operator who had to supply the id by hand would be one typo away from
overwriting an unrelated ruleset.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _gitapex_github_http import (  # sys.path bootstrap above must run first
    GitHubApiError,
    default_opener,
    fetch_json_document,
)
from _gitapex_rulesets import (  # same bootstrap
    API_ROOT,
    RulesetError,
    canonical_json_lines,
    canonical_projection,
    load_sot,
    render_projection_diff,
    resolve_live_ruleset,
)

_HTTP_TIMEOUT_SECONDS = 30
_API_VERSION = "2022-11-28"

#: Signature of the mutating half of the API surface, injected so tests drive
#: the create/replace decision end to end without a network or a credential.
Writer = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def send_write(url: str, method: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST or PUT one ruleset body and return the parsed response.

    Deliberately not routed through `_gitapex_github_http`: that module is the
    shared *read* client, and every one of its callers is a read-only gate.
    Keeping the single write path in the single write-capable script means a
    reviewer auditing "what in this repository can mutate GitHub state" reads
    one function, not a shared module used by six scripts.
    """
    token = read_token()
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method=method)  # noqa: S310 -- fixed https://api.github.com URL
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", _API_VERSION)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310 -- as above
            decoded = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RulesetError(f"{method} {url} failed: HTTP {error.code}: {detail}") from error
    except OSError as error:
        raise RulesetError(f"{method} {url} failed: {error}") from error
    if not isinstance(decoded, dict):
        raise RulesetError(f"{method} {url} returned {type(decoded).__name__}, expected a JSON object")
    return decoded


def read_token() -> str:
    """Read the API token from the environment, failing loudly when absent.

    Never falls back to an unauthenticated request: an anonymous call to the
    rulesets endpoint returns 404 for a repository the caller cannot see, which
    this script would then read as "no live ruleset -> POST" and try to create
    a duplicate. A missing credential must stop the run, not change its plan.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RulesetError("GITHUB_TOKEN is empty; see docs/runbooks/rulesets.md for the RULESETS_PAT handoff")
    return token


def default_fetch(url: str) -> Any:
    return fetch_json_document(url, read_token(), default_opener, time.sleep)


def plan_write(repo: str, sot: dict[str, Any], live: dict[str, Any] | None) -> dict[str, Any]:
    """Decide the request this run would send, without sending it."""
    body = canonical_projection(sot)
    if live is None:
        return {"method": "POST", "url": f"{API_ROOT}/repos/{repo}/rulesets", "body": body, "live_id": None}
    live_id = live.get("id")
    return {
        "method": "PUT",
        "url": f"{API_ROOT}/repos/{repo}/rulesets/{live_id}",
        "body": body,
        "live_id": live_id,
    }


def render_summary(plan: dict[str, Any], mode: str, diff: str, result_id: Any) -> str:
    """Markdown for the job summary: what was planned, what changed, what landed."""
    lines = [
        f"## Ruleset {mode}: `{plan['body'].get('name')}`",
        "",
        "| Method | Live id | Mode | Result id |",
        "|---|---|---|---|",
        f"| {plan['method']} | {plan['live_id'] if plan['live_id'] is not None else 'n/a'} "
        f"| {mode} | {result_id if result_id is not None else 'n/a'} |",
        "",
    ]
    if plan["method"] == "POST":
        lines += ["No live ruleset carries this name yet; this is a create, so there is nothing to diff against.", ""]
    elif diff:
        lines += [
            "<details><summary>Live vs committed source of truth</summary>",
            "",
            "```diff",
            diff,
            "```",
            "</details>",
            "",
        ]
    else:
        lines += ["Live ruleset already matches the committed source of truth; the request is a no-op replace.", ""]
    lines += ["<details><summary>Request body</summary>", "", "```json"]
    lines += [line.rstrip("\n") for line in canonical_json_lines(plan["body"])]
    lines += ["```", "</details>", ""]
    return "\n".join(lines)


def run(
    repo: str,
    sot_path: pathlib.Path,
    mode: str,
    fetch: Callable[[str], Any],
    writer: Writer,
) -> str:
    """Execute one plan-or-apply run and return the summary markdown.

    No exit code in the return value: this function has exactly one failure
    mode, an exception, and every one of them is a `RulesetError` or
    `GitHubApiError` that `main` turns into exit 1. An always-zero second
    element would read like a real status while carrying no information.
    """
    sot = load_sot(sot_path)
    live = resolve_live_ruleset(repo, sot["name"], fetch)
    plan = plan_write(repo, sot, live)
    diff = render_projection_diff(live, sot) if live is not None else ""
    result_id: Any = None
    if mode == "apply":
        response = writer(plan["url"], plan["method"], plan["body"])
        result_id = response.get("id")
    return render_summary(plan, mode, diff, result_id)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name of the repository to reconcile")
    parser.add_argument("--sot", required=True, help="path to the committed ruleset JSON")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("plan", "apply"),
        help="plan performs GETs only and prints the request it would send; apply sends it",
    )
    parser.add_argument("--summary-file", default="", help="append the markdown summary here as well as to stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary = run(args.repo, pathlib.Path(args.sot), args.mode, default_fetch, send_write)
    except (RulesetError, GitHubApiError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    print(summary)
    if args.summary_file:
        with pathlib.Path(args.summary_file).open("a", encoding="utf-8") as handle:
            handle.write(f"{summary}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

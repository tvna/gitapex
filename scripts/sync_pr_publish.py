#!/usr/bin/env python3
"""Publish a signed, bot-authored pull request for the agent-instructions sync.

The sync workflow fetches AGENTS.md/CLAUDE.md from the upstream master repo and
needs to land them as a reviewable PR. A plain ``git push`` from the runner's
default ``GITHUB_TOKEN`` produces an unsigned commit, which a
``required_signatures`` branch-protection rule rejects at merge time. This
script instead creates the commit server-side via the GraphQL
``createCommitOnBranch`` mutation (signed/Verified, authored by the GitHub App
identity behind the token), and upserts a PR for it.

The fixed sync branch is deleted and recreated off the base branch only when
there is drift and no open PR currently targets it: a reused branch can
otherwise accumulate an unsigned ancestor from a stale local-push run, which
permanently violates ``required_signatures`` even after later commits are
signed. Delete+create is not a force-push, so a ``non_fast_forward`` ruleset on
the branch is still honored. When an open PR already exists, the branch is
left alone (deleting it risks closing that PR and losing its review history)
and the new commit is appended onto its tip instead -- safe once this script
owns the branch, since every commit it makes is already signed.

Scoped to this one workflow's needs (small, fixed file set; no deletions; no
multi-commit batching) rather than a general-purpose PR-publishing library.

Usage::

    python3 scripts/sync_pr_publish.py \\
        --base main --branch chore/sync-claude-md \\
        --title TITLE --body-file body.md \\
        --commit-subject SUBJECT --commit-body BODY \\
        --add AGENTS.md --add CLAUDE.md

Environment variables:
    GH_TOKEN  GitHub token with contents:write and pull-requests:write scope.
    REPO      Repository in ``owner/repo`` format.

Exit codes:
    0  Success (including the no-op "already up to date" case).
    1  Missing env var, missing file, or API error.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

_API_ROOT = "https://api.github.com"
_GRAPHQL_URL = "https://api.github.com/graphql"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30

_CREATE_COMMIT_ON_BRANCH_MUTATION = """
mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) {
    commit { oid }
  }
}
"""

_GRAPHQL_TRANSIENT_ERROR_MARKER = "something went wrong while executing your query"


def _default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller in this module builds `request` from a
    # fixed https://api.github.com URL plus trusted env-var-derived segments.
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310


def apply_call(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[int, str]:
    """Call the GitHub REST API, retrying transient (5xx/network) failures."""
    sleeper = sleeper if sleeper is not None else time.sleep
    last_code = 0
    last_body = ""

    for attempt in range(1, 4):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 -- fixed https://api.github.com endpoint
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", _API_VERSION)
        if payload is not None:
            request.add_header("Content-Type", "application/json")

        try:
            with opener(request) as response:
                last_code = int(response.status)
                last_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            last_code = int(error.code)
            last_body = error.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as error:
            last_code = 0
            last_body = str(error.reason)

        if 200 <= last_code < 300:
            break
        print(f"Attempt {attempt}: HTTP {_format_code(last_code)} for {method} {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < 3:
            sleeper(attempt * 5)

    return last_code, last_body


def _graphql_is_transient(code: int, body: dict[str, Any]) -> bool:
    if code == 0 or code >= 500:
        return True
    errors = body.get("errors")
    if isinstance(errors, list):
        for err in errors:
            message = err.get("message", "") if isinstance(err, dict) else ""
            if isinstance(message, str) and _GRAPHQL_TRANSIENT_ERROR_MARKER in message.lower():
                return True
    return False


def graphql_call(
    *,
    query: str,
    variables: dict[str, Any],
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Execute a GitHub GraphQL query/mutation, retrying transient failures."""
    sleeper = sleeper if sleeper is not None else time.sleep
    payload = json.dumps({"query": query, "variables": variables}, separators=(",", ":"))
    last_code = 0
    last_body: dict[str, Any] = {}

    for attempt in range(1, 4):
        request = urllib.request.Request(_GRAPHQL_URL, data=payload.encode("utf-8"), method="POST")  # noqa: S310
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", _API_VERSION)
        request.add_header("Content-Type", "application/json")
        try:
            with opener(request) as response:
                code = int(response.status)
                body_str = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            code = int(error.code)
            body_str = error.read().decode("utf-8", errors="replace")
        except urllib.error.URLError:
            code = 0
            body_str = ""
        try:
            parsed = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            parsed = {}
        last_code = code
        last_body = parsed if isinstance(parsed, dict) else {}

        if not _graphql_is_transient(last_code, last_body):
            break
        print(f"Attempt {attempt}: transient GraphQL response HTTP {_format_code(last_code)}", file=sys.stderr)
        if attempt < 3:
            sleeper(attempt * 5)

    return last_code, last_body


def _format_code(code: int) -> str:
    return "000" if code == 0 else str(code)


def _get_ref_sha(*, repo: str, ref: str, token: str, apply_call: Callable[..., tuple[int, str]] = apply_call) -> str:
    url = f"{_API_ROOT}/repos/{repo}/git/ref/{ref}"
    code, body = apply_call(method="GET", url=url, payload=None, token=token)
    if not (200 <= code < 300):
        raise RuntimeError(f"Get ref {ref} failed: HTTP {code}: {body[:200]}")
    data = json.loads(body)
    sha = data.get("object", {}).get("sha")
    if not isinstance(sha, str) or not sha:
        raise RuntimeError(f"Get ref {ref} response missing object.sha: {body[:200]}")
    return sha


def _get_branch_head_oid(
    *, repo: str, branch: str, token: str, apply_call: Callable[..., tuple[int, str]] = apply_call
) -> str | None:
    """Return the head commit oid of ``refs/heads/{branch}``, or ``None`` if absent."""
    url = f"{_API_ROOT}/repos/{repo}/git/ref/heads/{branch}"
    code, body = apply_call(method="GET", url=url, payload=None, token=token)
    if code == 404:
        return None
    if not (200 <= code < 300):
        raise RuntimeError(f"Get branch ref {branch} failed: HTTP {code}: {body[:200]}")
    data = json.loads(body)
    sha = data.get("object", {}).get("sha")
    if not isinstance(sha, str) or not sha:
        raise RuntimeError(f"Get branch ref {branch} response missing object.sha: {body[:200]}")
    return sha


def _create_branch_ref(
    *, repo: str, branch: str, sha: str, token: str, apply_call: Callable[..., tuple[int, str]] = apply_call
) -> None:
    url = f"{_API_ROOT}/repos/{repo}/git/refs"
    code, resp = apply_call(method="POST", url=url, payload={"ref": f"refs/heads/{branch}", "sha": sha}, token=token)
    if not (200 <= code < 300):
        raise RuntimeError(f"Create branch ref {branch} failed: HTTP {code}: {resp[:200]}")


def _delete_branch(
    *, repo: str, branch: str, token: str, apply_call: Callable[..., tuple[int, str]] = apply_call
) -> None:
    """Delete a remote branch ref. A 404/422 (already gone) is treated as success."""
    url = f"{_API_ROOT}/repos/{repo}/git/refs/heads/{branch}"
    code, resp = apply_call(method="DELETE", url=url, payload=None, token=token)
    if (200 <= code < 300) or code in (404, 422):
        return
    raise RuntimeError(f"Delete branch {branch} failed: HTTP {code}: {resp[:200]}")


def _get_file_bytes(
    *, repo: str, path: str, ref: str, token: str, apply_call: Callable[..., tuple[int, str]] = apply_call
) -> bytes | None:
    """Return the decoded bytes of *path* at *ref*, or ``None`` when absent there."""
    url = f"{_API_ROOT}/repos/{repo}/contents/{path}?ref={ref}"
    code, body = apply_call(method="GET", url=url, payload=None, token=token)
    if code == 404:
        return None
    if not (200 <= code < 300):
        raise RuntimeError(f"Get contents {path}@{ref} failed: HTTP {code}: {body[:200]}")
    data = json.loads(body)
    encoding = data.get("encoding")
    content = data.get("content")
    if encoding != "base64" or not isinstance(content, str):
        raise RuntimeError(f"Get contents {path}@{ref}: unexpected encoding {encoding!r}")
    return base64.b64decode(content)


def _ref_drifts(
    *,
    repo: str,
    ref: str,
    additions: list[tuple[str, bytes]],
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> bool:
    """Return True when *ref* does not already carry every addition's bytes."""
    return any(
        _get_file_bytes(repo=repo, path=path, ref=ref, token=token, apply_call=apply_call) != content
        for path, content in additions
    )


def _create_commit_on_branch(
    *,
    repo: str,
    branch: str,
    expected_head_oid: str,
    headline: str,
    body: str,
    additions: list[dict[str, str]],
    token: str,
    graphql_call: Callable[..., tuple[int, dict[str, Any]]] = graphql_call,
) -> str:
    """Create a signed commit on *branch* via GraphQL; return the new commit oid."""
    message: dict[str, str] = {"headline": headline}
    if body:
        message["body"] = body
    variables = {
        "input": {
            "branch": {"repositoryNameWithOwner": repo, "branchName": branch},
            "message": message,
            "expectedHeadOid": expected_head_oid,
            "fileChanges": {"additions": additions},
        }
    }
    code, response = graphql_call(query=_CREATE_COMMIT_ON_BRANCH_MUTATION, variables=variables, token=token)
    if not (200 <= code < 300):
        raise RuntimeError(f"createCommitOnBranch HTTP {code}")
    if "errors" in response:
        raise RuntimeError(f"createCommitOnBranch errors: {response['errors']}")
    try:
        oid = response["data"]["createCommitOnBranch"]["commit"]["oid"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"createCommitOnBranch: unexpected response: {str(response)[:200]}") from exc
    if not isinstance(oid, str) or not oid:
        raise RuntimeError(f"createCommitOnBranch: missing commit oid: {str(response)[:200]}")
    return oid


def _list_open_prs(
    *, repo: str, head: str, token: str, apply_call: Callable[..., tuple[int, str]] = apply_call
) -> list[dict[str, Any]]:
    owner = repo.split("/")[0]
    url = f"{_API_ROOT}/repos/{repo}/pulls?head={owner}:{head}&state=open&per_page=1"
    code, body = apply_call(method="GET", url=url, payload=None, token=token)
    if not (200 <= code < 300):
        raise RuntimeError(f"List PRs failed: HTTP {code}: {body[:200]}")
    data = json.loads(body)
    if not isinstance(data, list):
        raise RuntimeError(f"Expected list from list PRs, got: {body[:200]}")
    return data


def _create_pr(
    *,
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str,
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> int:
    url = f"{_API_ROOT}/repos/{repo}/pulls"
    code, resp = apply_call(
        method="POST", url=url, payload={"title": title, "head": head, "base": base, "body": body}, token=token
    )
    if not (200 <= code < 300):
        raise RuntimeError(f"Create PR failed: HTTP {code}: {resp[:200]}")
    return int(json.loads(resp)["number"])


def _update_pr(
    *,
    repo: str,
    number: int,
    title: str,
    body: str,
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> None:
    url = f"{_API_ROOT}/repos/{repo}/pulls/{number}"
    code, resp = apply_call(method="PATCH", url=url, payload={"title": title, "body": body}, token=token)
    if not (200 <= code < 300):
        raise RuntimeError(f"Update PR failed: HTTP {code}: {resp[:200]}")


def _upsert_pr(
    *,
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str,
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> tuple[str, int]:
    prs = _list_open_prs(repo=repo, head=head, token=token, apply_call=apply_call)
    if prs:
        number = int(prs[0]["number"])
        _update_pr(repo=repo, number=number, title=title, body=body, token=token, apply_call=apply_call)
        return "updated", number
    number = _create_pr(repo=repo, head=head, base=base, title=title, body=body, token=token, apply_call=apply_call)
    return "created", number


def publish_files_pr(
    *,
    repo: str,
    additions: list[tuple[str, bytes]],
    base: str,
    branch: str,
    title: str,
    body: str,
    commit_subject: str,
    commit_body: str,
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
    graphql_call: Callable[..., tuple[int, dict[str, Any]]] = graphql_call,
) -> str:
    """Publish *additions* to *branch* and upsert a PR into *base*.

    Returns ``"up-to-date"`` when *base* already carries every addition's
    bytes, or ``"<verb>:<pr_number>"`` (*verb* is ``created`` or ``updated``,
    matching the PR-upsert outcome) otherwise.

    *branch* is deleted and recreated off *base* with a single signed commit
    only when there is drift AND no open PR currently targets it -- see the
    module docstring for why a stale branch is unsafe to reuse as-is. When an
    open PR already exists, the branch is left alone and the new commit is
    appended onto its current tip instead, so the PR (and its review
    history/comments) survives across runs. Once this script owns the branch,
    every commit on it is already signed, so an append can never reintroduce
    the unsigned-ancestor problem the recreate path guards against.
    """
    if not additions:
        return "up-to-date"
    if not _ref_drifts(repo=repo, ref=base, additions=additions, token=token, apply_call=apply_call):
        return "up-to-date"

    has_open_pr = bool(_list_open_prs(repo=repo, head=branch, token=token, apply_call=apply_call))
    if not has_open_pr:
        _delete_branch(repo=repo, branch=branch, token=token, apply_call=apply_call)

    api_additions = [
        {"path": path, "contents": base64.b64encode(content).decode("ascii")} for path, content in additions
    ]
    head_oid = _get_branch_head_oid(repo=repo, branch=branch, token=token, apply_call=apply_call)
    if head_oid is None:
        head_oid = _get_ref_sha(repo=repo, ref=f"heads/{base}", token=token, apply_call=apply_call)
        _create_branch_ref(repo=repo, branch=branch, sha=head_oid, token=token, apply_call=apply_call)
        _create_commit_on_branch(
            repo=repo,
            branch=branch,
            expected_head_oid=head_oid,
            headline=commit_subject,
            body=commit_body,
            additions=api_additions,
            token=token,
            graphql_call=graphql_call,
        )
    elif _ref_drifts(repo=repo, ref=branch, additions=additions, token=token, apply_call=apply_call):
        _create_commit_on_branch(
            repo=repo,
            branch=branch,
            expected_head_oid=head_oid,
            headline=commit_subject,
            body=commit_body,
            additions=api_additions,
            token=token,
            graphql_call=graphql_call,
        )

    verb, number = _upsert_pr(
        repo=repo, head=branch, base=base, title=title, body=body, token=token, apply_call=apply_call
    )
    return f"{verb}:{number}"


def _collect_additions(paths: list[str]) -> list[tuple[str, bytes]]:
    additions: list[tuple[str, bytes]] = []
    for path in paths:
        p = Path(path)
        if not p.is_file():
            raise RuntimeError(f"--add path is not a readable file: {path}")
        additions.append((path, p.read_bytes()))
    return additions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a signed PR for the agent-instructions sync.")
    parser.add_argument("--base", required=True, help="Base branch to merge into")
    parser.add_argument("--branch", required=True, help="Head branch name (recreated on drift)")
    parser.add_argument("--title", required=True, help="PR title")
    parser.add_argument("--body-file", required=True, dest="body_file", help="Path to file containing PR body")
    parser.add_argument("--commit-subject", required=True, dest="commit_subject", help="Commit headline")
    parser.add_argument("--commit-body", default="", dest="commit_body", help="Commit body/trailer line")
    parser.add_argument(
        "--add", action="append", default=[], dest="add", help="Working-tree file to publish (repeatable)"
    )
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN", "")
    if not token:
        print("Error: GH_TOKEN environment variable is required", file=sys.stderr)
        return 1
    repo = os.environ.get("REPO", "")
    if not repo:
        print("Error: REPO environment variable is required", file=sys.stderr)
        return 1
    body_path = Path(args.body_file)
    if not body_path.exists():
        print(f"Error: body file not found: {args.body_file}", file=sys.stderr)
        return 1

    try:
        additions = _collect_additions(args.add)
        result = publish_files_pr(
            repo=repo,
            additions=additions,
            base=args.base,
            branch=args.branch,
            title=args.title,
            body=body_path.read_text(encoding="utf-8"),
            commit_subject=args.commit_subject,
            commit_body=args.commit_body,
            token=token,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"sync-pr-publish: {result}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

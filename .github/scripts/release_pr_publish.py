#!/usr/bin/env python3
"""Publish a signed, bot-authored pull request for a `plugin` version bump.

The release-PR workflow computes the next SemVer for `plugin` (see
`compute_release_bump.py`) and needs to land the bumped
`.claude-plugin/plugin.json` / `apm.yml` plus rendered release notes as a
reviewable PR -- merging that PR is the release act. A plain ``git push``
from the runner's default ``GITHUB_TOKEN`` produces an unsigned commit,
which a ``required_signatures`` branch-protection rule rejects at merge
time. This script instead creates the commit server-side via the GraphQL
``createCommitOnBranch`` mutation (signed/Verified, authored by the GitHub
App identity behind the token), and upserts a PR for it.

This is the same problem `sync_pr_publish.py` solves for the
agent-instructions sync, and this file adapts that script's
``apply_call``/``graphql_call`` retry machinery, its
``createCommitOnBranch`` mutation and ``_create_commit_on_branch`` helper,
and its delete-and-recreate-branch-on-drift-only-when-no-open-PR safety
rule (see below). It is deliberately a standalone copy rather than an
import: this repository's `.github/scripts/*.py` files never import each
other, so each script's failure mode stays local to itself.

The fixed release branch (``chore/release-plugin-bump`` by default) is
deleted and recreated off the base branch whenever there is no open PR
currently targeting it: a reused branch can otherwise accumulate an
unsigned ancestor from a stale local-push run, which permanently violates
``required_signatures`` even after later commits are signed. Delete+create
is not a force-push, so a ``non_fast_forward`` ruleset on the branch is
still honored. When an open PR already exists, the branch is left alone
(deleting it risks closing that PR and losing its review history) and the
new commit is appended onto its tip instead -- safe once this script owns
the branch, since every commit it makes is already signed.

Unlike `sync_pr_publish.py`, this script does not check whether the base
branch already carries the additions' bytes before acting: the caller
workflow only ever invokes this script after computing a real version bump
(``bump != "none"``), so `main` can never already contain the not-yet-
merged bumped version -- that drift check does not apply here.

Usage::

    python3 .github/scripts/release_pr_publish.py \\
        --base main --branch chore/release-plugin-bump \\
        --old-version 0.1.0 --new-version 0.2.0 --bump-kind minor \\
        --notes-file notes.md \\
        --plugin-manifest .claude-plugin/plugin.json --apm-manifest apm.yml

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

_DEFAULT_BRANCH = "chore/release-plugin-bump"

_RELEASE_NOTES_START_MARKER = "<!-- release-notes:start -->"
_RELEASE_NOTES_END_MARKER = "<!-- release-notes:end -->"

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


def build_pr_body(old_version: str, new_version: str, bump_kind: str, notes_markdown: str) -> str:
    """Return the Markdown body for a release-bump PR.

    The returned text wraps *notes_markdown* verbatim (byte-for-byte, no
    re-formatting) between two literal marker lines,
    ``<!-- release-notes:start -->`` and ``<!-- release-notes:end -->``,
    each on its own line. `release_tag_publish.py` extracts exactly this
    span from the merged PR's body later to build the GitHub Release, so
    the marker text is load-bearing and must never change.
    """
    lines = [
        f"Bumps `plugin` from `{old_version}` to `{new_version}` ({bump_kind}).",
        "",
        _RELEASE_NOTES_START_MARKER,
        notes_markdown,
        _RELEASE_NOTES_END_MARKER,
        "",
        "Merging this PR is the release act: on merge, "
        "`.github/workflows/release-tag.yml` creates the `gitapex--vX.Y.Z` tag "
        "and a GitHub Release using the notes above.",
        "",
        "Do not edit `.claude-plugin/plugin.json`/`apm.yml` by hand in this PR; "
        "the next scheduled run will overwrite manual edits.",
    ]
    return "\n".join(lines) + "\n"


def publish_release_pr(
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

    Returns ``"up-to-date"`` when *additions* is empty (the caller workflow
    only ever invokes this script after computing a real version bump, so
    this is a defensive no-op rather than an expected outcome), or
    ``"<verb>:<pr_number>"`` (*verb* is ``created`` or ``updated``,
    matching the PR-upsert outcome) otherwise.

    Unlike `sync_pr_publish.py`'s `publish_files_pr`, this does not check
    whether *base* already carries every addition's bytes first: the caller
    workflow gates on a real, not-yet-merged version bump before invoking
    this script at all, so *base* can never already be up to date.

    *branch* is deleted and recreated off *base* with a single signed
    commit whenever there is no open PR currently targeting it -- see the
    module docstring for why a stale branch is unsafe to reuse as-is. When
    an open PR already exists, the branch is left alone and the new commit
    is appended onto its current tip instead, so the PR (and its review
    history/comments) survives across runs. Once this script owns the
    branch, every commit on it is already signed, so an append can never
    reintroduce the unsigned-ancestor problem the recreate path guards
    against.
    """
    if not additions:
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


def _collect_additions(repo_root: Path, paths: list[str]) -> list[tuple[str, bytes]]:
    """Read each of *paths* (repo-root-relative) off disk under *repo_root*.

    The returned tuples keep the repo-root-relative path (not the absolute
    on-disk path) as the commit path, since that is what
    `createCommitOnBranch`'s `fileChanges.additions[].path` expects.
    """
    additions: list[tuple[str, bytes]] = []
    for path in paths:
        p = repo_root / path
        if not p.is_file():
            raise RuntimeError(f"manifest path is not a readable file: {p}")
        additions.append((path, p.read_bytes()))
    return additions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a signed PR for a plugin version bump.")
    parser.add_argument("--repo-root", default=".", dest="repo_root", help="Repository root (default: cwd)")
    parser.add_argument("--base", default="main", help="Base branch to merge into")
    parser.add_argument("--branch", default=_DEFAULT_BRANCH, help="Head branch name (recreated when no open PR)")
    parser.add_argument("--old-version", required=True, dest="old_version", help="Version before the bump")
    parser.add_argument("--new-version", required=True, dest="new_version", help="Version after the bump")
    parser.add_argument("--bump-kind", required=True, dest="bump_kind", help="'minor' or 'patch'")
    parser.add_argument(
        "--notes-file", required=True, dest="notes_file", help="Path to the rendered release-notes Markdown"
    )
    parser.add_argument(
        "--plugin-manifest",
        default=".claude-plugin/plugin.json",
        dest="plugin_manifest",
        help="Repo-root-relative path to the bumped plugin manifest",
    )
    parser.add_argument(
        "--apm-manifest",
        default="apm.yml",
        dest="apm_manifest",
        help="Repo-root-relative path to the bumped apm manifest",
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
    notes_path = Path(args.notes_file)
    if not notes_path.exists():
        print(f"Error: notes file not found: {args.notes_file}", file=sys.stderr)
        return 1

    try:
        repo_root = Path(args.repo_root)
        additions = _collect_additions(repo_root, [args.plugin_manifest, args.apm_manifest])
        body = build_pr_body(
            args.old_version, args.new_version, args.bump_kind, notes_path.read_text(encoding="utf-8")
        )
        title = f"chore(plugin): bump version to {args.new_version}"
        result = publish_release_pr(
            repo=repo,
            additions=additions,
            base=args.base,
            branch=args.branch,
            title=title,
            body=body,
            commit_subject=f"chore(plugin): bump version to {args.new_version}",
            commit_body="",
            token=token,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"release-pr-publish: {result}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

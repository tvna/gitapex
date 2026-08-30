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

Issue #729: the retry/backoff HTTP machinery this script needs (previously
a hand-copied local ``apply_call`` loop plus a local ``graphql_call``) now
delegates to ``_gitapex_github_http.request_with_retry`` and
``_gitapex_github_http.graphql_call`` -- the latter moved there, with two
edits made on arrival rather than a verbatim copy (see its own docstring
in ``_gitapex_github_http.py`` for what changed and why). That module is
the one deliberate, generic exception to this repository's
``.github/scripts/*.py`` independence convention (see its own docstring,
and gitapex_scan_retrospective_gate_drift.py's docstring for the
convention itself) -- this script otherwise stays dependency-light
(stdlib plus ``pydantic``, this repository's own pinned CLI-arg validation
dependency) and does not import any other carrier script. Public function
signatures are unchanged; ``apply_call``'s own docstring notes the
observable differences the delegation introduces.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_sync_pr_publish.py \\
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
import unicodedata
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from _gitapex_github_http import default_opener, graphql_call, request_with_retry
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_API_ROOT = "https://api.github.com"

_CREATE_COMMIT_ON_BRANCH_MUTATION = """
mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) {
    commit { oid }
  }
}
"""


def apply_call(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[int, str]:
    """Call the GitHub REST API, retrying transient (5xx/network) failures.

    Issue #729: delegates its retry loop to
    `_gitapex_github_http.request_with_retry`, the generalized retry
    primitive this function's own former inline loop was extracted into
    (wave 1). Public signature and return contract (a `(status_code,
    body_text)` tuple, never raising) stay unchanged -- this function is
    dependency-injected as `apply_call` deep into this module's own
    internal functions (`_get_ref_sha`, `_get_branch_head_oid`,
    `_create_branch_ref`, `_delete_branch`, and others), whose own
    signatures and `apply_call=apply_call` wiring are untouched.

    Three disclosed, accepted differences from this function's former
    local retry loop, none of which any caller branches on -- every one
    of them branches on the status code, which (like the retry count and
    backoff timing) is unchanged:

    1. On a network failure the returned body text is now urllib's own
       `"<urlopen error boom>"` wrapper rather than the bare `"boom"` this
       function's former `URLError`-specific handler read off
       `error.reason`, because `request_with_retry` catches the same
       failure one level higher as a plain `OSError`.
    2. Outgoing REST bodies are now JSON-encoded with default separators
       (`json.dumps(body)`, via `request_with_retry`) instead of this
       function's former compact `separators=(",", ":")` -- functionally
       identical (RFC 8259 SS2.7: insignificant whitespace is non-semantic,
       and `Content-Length` is recomputed from the encoded bytes either
       way), just more spaced out on the wire.
    3. A network-failure/no-response attempt now logs as `HTTP network
       error` in this function's retry-attempt stderr line (via the
       shared module's own `format_code` convention) rather than this
       function's former local `"000"` rendering.
    """
    sleeper = sleeper if sleeper is not None else time.sleep
    return request_with_retry(method, url, token, opener, sleeper, body=payload)


def _get_ref_sha(*, repo: str, ref: str, token: str, apply_call: Callable[..., tuple[int, str]] = apply_call) -> str:
    url = f"{_API_ROOT}/repos/{repo}/git/ref/{ref}"
    code, body = apply_call(method="GET", url=url, payload=None, token=token)
    if not (200 <= code < 300):
        raise RuntimeError(f"Get ref {ref} failed: HTTP {code}: {body[:200]}")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object from get ref {ref}, got: {body[:200]}")
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
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object from get branch ref {branch}, got: {body[:200]}")
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
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object from get contents {path}@{ref}, got: {body[:200]}")
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


def _is_blank(value: str) -> bool:
    """True iff every character in `value` is ordinary whitespace or a
    Unicode Format-category (Cf) mark -- invisible either way. Cf covers
    U+200B ZERO WIDTH SPACE, U+FEFF ZERO WIDTH NO-BREAK SPACE, and U+180E
    MONGOLIAN VOWEL SEPARATOR, none of which str.strip() removes -- so a
    value made solely of Cf marks passed the old `.strip()`-only check
    unrejected (issue #1094)."""
    return all(char.isspace() or unicodedata.category(char) == "Cf" for char in value)


class _CliArgs(BaseModel):
    """Parsed-and-validated view of this script's own argparse namespace.
    Required string fields reject blank (argparse's own ``required=True``
    only guarantees the flag was passed, not that its value is non-empty).
    ``body_file``'s own field validator folds in this script's pre-existing
    hand check (``if not body_path.exists(): print(...); return 1``) rather
    than leaving both a pydantic model and that check in place side by
    side -- it is intentionally constructed later than
    ``args = parser.parse_args(argv)`` in ``main`` (after the GH_TOKEN/REPO
    environment-variable checks, exactly where the old hand check used to
    sit) so a run missing GH_TOKEN/REPO still reports that error first,
    unchanged, rather than a body-file error surfacing before it."""

    model_config = ConfigDict(extra="forbid")

    base: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body_file: str = Field(min_length=1)
    commit_subject: str = Field(min_length=1)
    commit_body: str = ""
    add: list[str] = Field(default_factory=list)

    @field_validator("base", "branch", "title", "commit_subject")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        # min_length=1 alone accepts a whitespace-only string (issue #1087).
        # Checked via _is_blank() without storing a stripped result -- this
        # validates, it does not trim, so a padded-but-meaningful value
        # keeps reaching publish_files_pr() unchanged. _is_blank() also
        # rejects a value made solely of Unicode Format-category (Cf)
        # characters, which plain .strip() leaves in place (issue #1094).
        if _is_blank(value):
            raise ValueError("must not be blank")
        return value

    @field_validator("body_file")
    @classmethod
    def _body_file_must_exist(cls, value: str) -> str:
        # A whitespace-only path is rejected up front (issue #1087) rather
        # than left to the is_file() check below: relying on no file ever
        # being named e.g. " " is incidental, not a guarantee. Same
        # reasoning extends to a value made solely of Unicode Format-
        # category (Cf) characters (e.g. U+200B ZERO WIDTH SPACE, left in
        # place by plain .strip()): relying on no file ever being named
        # that is equally incidental, so _is_blank() (issue #1094) is
        # checked here too, not left to is_file() below to happen to catch.
        # The message is deliberately its own self-describing "body file
        # ..." text, not the generic "must not be blank" the other fields
        # below share -- main()'s ValidationError handler strips the
        # "body_file: " prefix for this field's own value_error type (see
        # its own comment), so a shared, non-field-named message here would
        # render as an unattributable duplicate when another field is also
        # blank in the same run.
        if _is_blank(value):
            raise ValueError("body file path must not be blank")
        # is_file(), not exists(): a directory passes exists() but is not
        # readable as a file, so main()'s later body_path.read_text() would
        # raise an uncaught IsADirectoryError -- confirmed live, the same
        # class of raw-traceback failure issue #1087 exists to eliminate.
        # is_file() itself can still raise OSError (e.g. ENAMETOOLONG for an
        # over-long path component)
        # rather than returning False -- found by adversarial review to
        # propagate straight through pydantic uncaught, since pydantic only
        # converts a validator's own ValueError/TypeError/AssertionError
        # into a ValidationError, not an arbitrary OSError raised by a
        # stdlib call inside it. Folding it into the same self-describing
        # "body file not found" message keeps it on the one code path
        # main()'s except ValidationError (and its body_file-message
        # special case) already handles.
        try:
            is_file = Path(value).is_file()
        except OSError as exc:
            raise ValueError(f"body file not found: {value} ({exc})") from exc
        if not is_file:
            raise ValueError(f"body file not found: {value}")
        return value


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
    try:
        cli_args = _CliArgs(
            base=args.base,
            branch=args.branch,
            title=args.title,
            body_file=args.body_file,
            commit_subject=args.commit_subject,
            commit_body=args.commit_body,
            add=args.add,
        )
    except ValidationError as exc:
        # body_file's *custom field_validator* message (type "value_error",
        # from _CliArgs._body_file_must_exist's own raise ValueError) is
        # this script's pre-existing hand-check text, self-describing
        # enough that a "body_file: " prefix would only drift the message
        # CI logs and operators already expect -- see _CliArgs' docstring.
        # A blank body_file instead trips Field(min_length=1), producing
        # pydantic's own generic, non-self-describing "String should have
        # at least 1 character" -- keying this special case on loc alone
        # (not also type) wrongly stripped the field label from that
        # message too (an adversarial review confirmed it, by direct
        # execution, reads as an unattributable duplicate of another
        # field's identical blank-value message when both are blank at
        # once). Every other field, and every other body_file error type,
        # keeps the generic "field: message" form.
        detail = "; ".join(
            e["msg"].removeprefix("Value error, ")
            if e["loc"] == ("body_file",) and e["type"] == "value_error"
            else f"{e['loc'][0] if e['loc'] else 'args'}: {e['msg'].removeprefix('Value error, ')}"
            for e in exc.errors()
        )
        print(f"Error: {detail}", file=sys.stderr)
        return 1
    body_path = Path(cli_args.body_file)

    try:
        additions = _collect_additions(cli_args.add)
        result = publish_files_pr(
            repo=repo,
            additions=additions,
            base=cli_args.base,
            branch=cli_args.branch,
            title=cli_args.title,
            body=body_path.read_text(encoding="utf-8"),
            commit_subject=cli_args.commit_subject,
            commit_body=cli_args.commit_body,
            token=token,
        )
    except (RuntimeError, UnicodeDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"sync-pr-publish: {result}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

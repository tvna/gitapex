#!/usr/bin/env python3
"""Tag and publish a GitHub Release for a merged plugin-version-bump PR.

The release workflow bumps ``version`` in ``.claude-plugin/plugin.json``
through a normal reviewed PR. Once that PR merges to the base branch, this
script runs against the merge commit and, if that exact version has not been
published yet, creates an annotated git tag and a GitHub Release for it.

Tag naming: ``gitapex--v{version}`` -- deliberately not ``plugin-v{version}``.
This repository's plugin-dependency consumers resolve a plugin's installable
versions from tags of the form ``<plugin-name>--v<version>``, so the tag must
be prefixed with this plugin's own name (``gitapex``), not the literal word
"plugin".

Idempotency: the tag's existence is the single source of truth for "already
published". If ``gitapex--v{version}`` already exists, this script is a
no-op (exit 0) -- safe to re-run after a partial failure or a workflow retry.

Release notes come from the merged PR's body, extracted from between two
literal HTML-comment markers (``<!-- release-notes:start -->`` /
``<!-- release-notes:end -->``) so the PR author controls exactly what ships
in the release body, separate from the rest of the PR description.

Scoped to this one workflow's needs (a single fixed-format tag/release per
run, driven off one plugin.json's version) rather than a general-purpose
release-publishing library.

Usage::

    python3 .github/scripts/release_tag_publish.py --sha <merge-commit-sha>

Environment variables:
    GH_TOKEN  GitHub token with contents:write scope (tags) and
              contents:write / administration scope for releases.
    REPO      Repository in ``owner/repo`` format (used when ``--repo`` is
              not passed).

Exit codes:
    0  Success, including the no-op "already tagged" case.
    1  Missing env var, missing/invalid manifest, no merged PR found for the
       commit, missing release-notes markers, or a GitHub API error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30

_RELEASE_NOTES_START = "<!-- release-notes:start -->"
_RELEASE_NOTES_END = "<!-- release-notes:end -->"
_RELEASE_NOTES_RE = re.compile(re.escape(_RELEASE_NOTES_START) + r"(.*?)" + re.escape(_RELEASE_NOTES_END), re.DOTALL)


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


def _format_code(code: int) -> str:
    return "000" if code == 0 else str(code)


def tag_exists(
    repo: str,
    version: str,
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> bool:
    """Return True when ``gitapex--v{version}`` already exists as a tag ref."""
    url = f"{_API_ROOT}/repos/{repo}/git/ref/tags/gitapex--v{version}"
    code, body = apply_call(method="GET", url=url, payload=None, token=token)
    if code == 200:
        return True
    if code == 404:
        return False
    raise RuntimeError(f"Check tag gitapex--v{version} failed: HTTP {code}: {body[:200]}")


def find_merged_pr_for_commit(
    repo: str,
    sha: str,
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> dict[str, Any] | None:
    """Return the first merged PR associated with ``sha``, or None if none is."""
    url = f"{_API_ROOT}/repos/{repo}/commits/{sha}/pulls"
    code, body = apply_call(method="GET", url=url, payload=None, token=token)
    if not (200 <= code < 300):
        raise RuntimeError(f"List PRs for commit {sha} failed: HTTP {code}: {body[:200]}")
    data = json.loads(body)
    if not isinstance(data, list):
        raise RuntimeError(f"Expected list from commit-pulls for {sha}, got: {body[:200]}")
    for pr in data:
        if isinstance(pr, dict) and pr.get("merged_at"):
            return pr
    return None


def extract_release_notes(pr_body: str) -> str:
    """Extract the text strictly between the release-notes marker lines.

    Raises ``RuntimeError`` when either marker is missing -- never returns an
    empty string or fabricates placeholder notes.
    """
    body = pr_body or ""
    if _RELEASE_NOTES_START not in body:
        raise RuntimeError(f"PR body is missing the {_RELEASE_NOTES_START!r} marker")
    if _RELEASE_NOTES_END not in body:
        raise RuntimeError(f"PR body is missing the {_RELEASE_NOTES_END!r} marker")
    match = _RELEASE_NOTES_RE.search(body)
    if match is None:
        raise RuntimeError("PR body release-notes markers are out of order or malformed")
    return match.group(1).strip()


def publish_tag_and_release(
    repo: str,
    version: str,
    sha: str,
    notes: str,
    token: str,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> None:
    """Create an annotated tag object, point ``refs/tags/gitapex--v{version}``
    at it, then publish a GitHub Release for that tag.

    Raises ``RuntimeError`` (with status/body) on the first non-2xx response
    and does not continue past the failed step.
    """
    tag_name = f"gitapex--v{version}"

    code, body = apply_call(
        method="POST",
        url=f"{_API_ROOT}/repos/{repo}/git/tags",
        payload={"tag": tag_name, "message": f"gitapex v{version}", "object": sha, "type": "commit"},
        token=token,
    )
    if not (200 <= code < 300):
        raise RuntimeError(f"Create tag object {tag_name} failed: HTTP {code}: {body[:200]}")
    tag_sha = json.loads(body).get("sha")
    if not isinstance(tag_sha, str) or not tag_sha:
        raise RuntimeError(f"Create tag object {tag_name} response missing sha: {body[:200]}")

    code, body = apply_call(
        method="POST",
        url=f"{_API_ROOT}/repos/{repo}/git/refs",
        payload={"ref": f"refs/tags/{tag_name}", "sha": tag_sha},
        token=token,
    )
    if not (200 <= code < 300):
        raise RuntimeError(f"Create tag ref {tag_name} failed: HTTP {code}: {body[:200]}")

    code, body = apply_call(
        method="POST",
        url=f"{_API_ROOT}/repos/{repo}/releases",
        payload={"tag_name": tag_name, "name": f"gitapex v{version}", "body": notes},
        token=token,
    )
    if not (200 <= code < 300):
        raise RuntimeError(f"Create release {tag_name} failed: HTTP {code}: {body[:200]}")


def _read_version(manifest_path: Path) -> str:
    """Read ``version`` out of the plugin manifest at ``manifest_path``.

    Reads the working tree directly (no ``git show``) -- this script runs
    after checkout at the commit being tagged, so the file on disk already
    reflects that commit's content.
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read plugin manifest {manifest_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Plugin manifest {manifest_path} is not valid JSON: {exc}") from exc
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not version:
        raise RuntimeError(f"Plugin manifest {manifest_path} has no non-empty 'version' field")
    return version


def main(
    argv: list[str] | None = None,
    apply_call: Callable[..., tuple[int, str]] = apply_call,
) -> int:
    parser = argparse.ArgumentParser(
        description="Tag and publish a GitHub Release for a merged plugin-version-bump PR."
    )
    parser.add_argument("--repo-root", default=".", dest="repo_root", help="Working tree root (default: cwd)")
    parser.add_argument(
        "--plugin-manifest",
        default=".claude-plugin/plugin.json",
        dest="plugin_manifest",
        help="Path to the plugin manifest, relative to --repo-root",
    )
    parser.add_argument("--sha", required=True, help="Commit SHA to tag")
    parser.add_argument("--repo", default=None, help="Repository in owner/repo format (default: REPO env var)")
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN", "")
    if not token:
        print("Error: GH_TOKEN environment variable is required", file=sys.stderr)
        return 1
    repo = args.repo or os.environ.get("REPO", "")
    if not repo:
        print("Error: --repo or REPO environment variable is required", file=sys.stderr)
        return 1

    manifest_path = Path(args.repo_root) / args.plugin_manifest

    try:
        version = _read_version(manifest_path)
        tag_name = f"gitapex--v{version}"
        if tag_exists(repo, version, token, apply_call=apply_call):
            print(f"release-tag-publish: {tag_name} already exists (refs/tags/{tag_name}) -- no-op")
            return 0
        pr = find_merged_pr_for_commit(repo, args.sha, token, apply_call=apply_call)
        if pr is None:
            raise RuntimeError(
                f"No merged PR found for commit {args.sha} in {repo}: a plugin.json version "
                "bump reached the base branch outside the release-PR flow -- refusing to "
                "silently no-op"
            )
        notes = extract_release_notes(pr.get("body") or "")
        publish_tag_and_release(repo, version, args.sha, notes, token, apply_call=apply_call)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"release-tag-publish: published {tag_name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

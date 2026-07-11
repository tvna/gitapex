#!/usr/bin/env python3
"""Publish changed files as a signed commit + pull request via the GitHub API.

Used by the "Sync agent instructions" workflow. Creates the commit
server-side through the GraphQL createCommitOnBranch mutation (which GitHub
signs and marks Verified) rather than pushing from the runner, since a plain
`git push` with the default GITHUB_TOKEN produces an unsigned commit that
required_signatures branch protection rejects.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"


def gh_request(url, token, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read() or b"{}")


def graphql(query, variables, token):
    result = gh_request(GRAPHQL_URL, token, "POST", {"query": query, "variables": variables})
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))
    return result["data"]


def changed_paths(paths):
    changed = []
    for path in paths:
        result = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path])
        if result.returncode != 0:
            changed.append(path)
    return changed


def resolve_branch_head(owner, repo, branch, token):
    try:
        ref = gh_request(f"{REST_URL}/repos/{owner}/{repo}/git/ref/heads/{branch}", token)
        return ref["object"]["sha"]
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def find_open_pr(owner, repo, branch, base, token):
    prs = gh_request(
        f"{REST_URL}/repos/{owner}/{repo}/pulls"
        f"?head={owner}:{branch}&base={base}&state=open",
        token,
    )
    return prs[0] if prs else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base branch the PR merges into")
    parser.add_argument("--branch", required=True, help="working branch to commit onto")
    parser.add_argument("--title", required=True, help="pull request title")
    parser.add_argument("--body-file", required=True, help="path to a file with the PR body")
    parser.add_argument("--commit-subject", required=True)
    parser.add_argument("--add", action="append", dest="paths", required=True,
                         help="path to include in the commit (repeatable)")
    args = parser.parse_args()

    token = os.environ["GH_TOKEN"]
    owner, repo = os.environ["REPO"].split("/", 1)

    changed = changed_paths(args.paths)
    if not changed:
        print("no changes detected in tracked files, skipping publish")
        return

    with open(args.body_file, encoding="utf-8") as f:
        body = f.read()

    base_head = resolve_branch_head(owner, repo, args.base, token)
    if base_head is None:
        sys.exit(f"base branch {args.base!r} not found")

    branch_head = resolve_branch_head(owner, repo, args.branch, token)
    if branch_head is None:
        gh_request(
            f"{REST_URL}/repos/{owner}/{repo}/git/refs",
            token,
            "POST",
            {"ref": f"refs/heads/{args.branch}", "sha": base_head},
        )
        branch_head = base_head

    additions = []
    for path in changed:
        with open(path, "rb") as f:
            additions.append({"path": path, "contents": base64.b64encode(f.read()).decode()})

    mutation = """
    mutation($input: CreateCommitOnBranchInput!) {
      createCommitOnBranch(input: $input) {
        commit { oid url }
      }
    }
    """
    commit_input = {
        "branch": {
            "repositoryNameWithOwner": f"{owner}/{repo}",
            "branchName": args.branch,
        },
        "message": {"headline": args.commit_subject},
        "expectedHeadOid": branch_head,
        "fileChanges": {"additions": additions},
    }
    data = graphql(mutation, {"input": commit_input}, token)
    commit = data["createCommitOnBranch"]["commit"]
    print(f"created signed commit {commit['oid']}: {commit['url']}")

    existing_pr = find_open_pr(owner, repo, args.branch, args.base, token)
    if existing_pr:
        print(f"updated existing PR #{existing_pr['number']}: {existing_pr['html_url']}")
        return

    pr = gh_request(
        f"{REST_URL}/repos/{owner}/{repo}/pulls",
        token,
        "POST",
        {"title": args.title, "head": args.branch, "base": args.base, "body": body},
    )
    print(f"opened PR #{pr['number']}: {pr['html_url']}")


if __name__ == "__main__":
    main()

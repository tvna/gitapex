# Contributing

## Issue citation convention

If a PR's changes fully satisfy an issue's acceptance criteria, cite it
with `Closes #N` (in the commit trailer and/or the PR body) so merging
closes it automatically. Use `Refs #N` only when the PR partially
addresses or merely relates to the issue.

## Signed-commit bot App

The "Sync agent instructions" workflow (`.github/workflows/sync-agent-instructions.yml`)
opens a pull request that syncs `AGENTS.md` and `CLAUDE.md` from the upstream
`tvna/claude-md` repository. This repository requires `required_signatures`
branch protection, so a commit pushed with the default `GITHUB_TOKEN` would be
rejected as unsigned at merge time. The workflow instead mints a short-lived
GitHub App installation token and uses it to create the commit server-side via
the GraphQL `createCommitOnBranch` mutation, which GitHub signs and shows as
Verified.

To enable this:

1. Create a GitHub App (repo or org-owned) with:
   - Repository permissions: **Contents: Read and write**, **Pull requests:
     Read and write**.
   - No webhook, no other permissions needed.
2. Install the App on this repository.
3. Generate a private key for the App and note its App ID.
4. In this repository's settings, create an **Environment** named `sync-bot`
   (optionally with required reviewers or other protection rules).
5. Add two secrets scoped to the `sync-bot` environment:
   - `SYNC_BOT_APP_ID` — the App ID.
   - `SYNC_BOT_APP_PRIVATE_KEY` — the App's private key (PEM contents).

The workflow's job runs under the `sync-bot` environment, so these secrets are
only exposed to that job and can carry their own approval gates independent of
other workflows in this repository.

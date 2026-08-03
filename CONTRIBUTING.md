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

## Signed-commit release bot App

The "Release PR" and "Release tag" workflows
(`.github/workflows/release-pr.yml`, `.github/workflows/release-tag.yml`)
propose a `.claude-plugin/plugin.json`/`apm.yml` version-bump pull request and,
on merge, create the `gitapex--vX.Y.Z` tag and a GitHub Release. Both need a
write identity distinct from the default `GITHUB_TOKEN`, for the same
`required_signatures` branch-protection reason as the sync-bot App documented
above. This is a **separate, dedicated** GitHub App — not an extension of the
sync-bot App above — so each automation's write capability stays scoped to its
own blast radius: a compromise or bug in one cannot use the other's
credentials.

To enable this:

1. Create a GitHub App (repo or org-owned), suggested name
   `gitapex-release-bot`, with:
   - Repository permissions: **Contents: Read and write**, **Pull requests:
     Read and write**.
   - No webhook, no other permissions needed.
2. Install the App on this repository.
3. Generate a private key for the App and note its App ID.
4. In this repository's settings, create an **Environment** named
   `release-bot` (optionally with required reviewers or other protection
   rules).
5. Add two secrets scoped to the `release-bot` environment:
   - `RELEASE_BOT_APP_ID` — the App ID.
   - `RELEASE_BOT_APP_PRIVATE_KEY` — the App's private key (PEM contents).

Both workflows' jobs run under the `release-bot` environment, so these secrets
are only exposed to those jobs. **Verification:** trigger `release-pr.yml`
once via `workflow_dispatch`, confirm the resulting bump PR's commit shows as
Verified, merge it, and confirm `release-tag.yml` creates a Verified-tagged
`gitapex--vX.Y.Z` and a GitHub Release carrying the PR's release-notes text.

## ranking-the-open-queue weekly digest API key

The "Weekly ranking-the-open-queue digest"
workflow (`.github/workflows/ranking-the-open-queue-weekly.yml`) runs
`skills/ranking-the-open-queue` on a weekly schedule via
`anthropics/claude-code-action@v1`. See
`docs/superpowers/specs/2026-07-28-ranking-the-open-queue-github-actions-routine.md`
for the full design and why this replaced an earlier Claude Code Cloud
Routine attempt.

To enable this:

1. Create an API key at [console.anthropic.com](https://console.anthropic.com)
   scoped to this workload (a dedicated project/workspace key if your
   organization's Console supports it, rather than reusing a
   broader-scoped key).
2. In this repository's settings, add it as a repository secret named
   `ANTHROPIC_API_KEY` (Settings -> Secrets and variables -> Actions).
   No GitHub Environment gate is used here (unlike the sync-bot App
   above): this key grants no repository write capability, only Claude
   API usage, so its blast radius is lower than a signing key.
3. **Minimum permissions:** this key only needs Claude API access; it
   grants nothing GitHub-side. The workflow's own `permissions:` block
   (`contents: read`, `issues: read`, `pull-requests: read`) is what
   bounds GitHub access, not this key.
4. **Rotation:** no organization-mandated cadence exists yet for this
   key; a 180-day manual rotation is proposed pending owner
   confirmation. Record whatever cadence is actually adopted here once
   decided.
5. **Verification:** after adding the secret, trigger the workflow once
   via `workflow_dispatch` (Actions tab -> "Weekly ranking-the-open-queue
   digest" -> Run workflow) and confirm the job succeeds with the
   ranked digest table in the job log.

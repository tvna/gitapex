# Contributing

## Local pre-commit hook (prek)

`pyproject.toml` pins `prek` (https://github.com/j178/prek) as a dev
dependency and `.pre-commit-config.yaml` wires it to this repo's own
`ruff check`, `ruff format --check`, and `mypy` config, plus the
`betterleaks` secret scan below -- but a dependency alone installs no git
hook. Run once per clone:

```sh
uv run prek install -t pre-commit -t pre-push
```

Both stages matter, so both shims are named: `prek install` with no `-t`
installs the pre-commit shim only, and the pre-push secret scan would then
never run.

This makes `git commit` reject a commit that fails ruff, mypy, or the
secret scan locally, before it exists, rather than only after a push reaches
CI.

`nix develop` attempts the same install on shell entry (see `flake.nix`'s
devShell), so the Nix path usually needs no manual step. It is an attempt,
not a guarantee: if the install fails, or either shim is missing afterwards,
the devShell prints a `WARNING:` naming the command to run. It deliberately
does not abort the shell -- that would lock you out of the whole toolchain
over a hook-install problem -- so read the warnings on entry rather than
assuming the hooks are live. To confirm at any time:

```sh
hooks=$(git rev-parse --git-path hooks)
for h in pre-commit pre-push; do
  p="$hooks/$h"
  t=$(sed -n 's/^PREK="\(.*\)"$/\1/p' "$p" 2>/dev/null | head -1)
  if [ -x "$p" ] && { [ -x "$t" ] || command -v prek >/dev/null 2>&1; }; then
    echo "$h: active"
  else
    echo "$h: NOT ACTIVE"
  fi
done
```

This is deliberately not `ls`. A shim can be present and executable while still
being dead: prek writes the *installing* tree's `.venv/bin/prek` into it as an
absolute path and falls back to a bare `prek` on `PATH`, so a shim left behind
by a removed worktree passes an executable-bit test and then dies at `exec`
with `prek: not found`. The check above is the same one the devShell applies --
the shim's own target must resolve, or `prek` must really be on `PATH`.

`git rev-parse --git-path hooks` rather than a literal `.git/hooks`: the
literal path is wrong from a subdirectory and inside a linked worktree (where
`.git` is a file), and it ignores `core.hooksPath`. Worktrees matter here --
this repository's own agent tooling creates them.

**Never run `prek install` from inside a linked worktree.** A worktree shares
the main checkout's hooks directory, and prek writes an absolute path to the
*installing* tree's `.venv/bin/prek` into each shim. Installing from a worktree
therefore repoints the main checkout's hooks at that worktree's venv, and they
fail outright once the worktree is removed:

```
.git/hooks/pre-push: exec: prek: not found
```

Recovery is `uv run prek install --overwrite -t pre-commit -t pre-push` from the
main checkout. The devShell already refuses to install from a worktree for this
reason -- it verifies the shared shims and tells you to install from the main
checkout instead.

CI (`.github/workflows/test.yml`, `.github/workflows/lint.yml`) still runs
the same ruff/mypy checks independently as the actual merge gate -- the
local hook is a fast first pass, not a replacement for it.

## Secret scanning (betterleaks)

Issue #890 wires the `betterleaks` build SHA256-pinned in `flake.nix` into
two hook stages, via `.github/scripts/gitapex_run_betterleaks.py`:

| Stage | Hook id | Scope |
|---|---|---|
| pre-commit | `betterleaks-staged` | the git index |
| pre-push | `betterleaks-history` | every commit, not just the push range |

The pre-push hook scans the whole history (measured at 1.34 s over
30.24 MB) precisely because it is the backstop for commits that never saw
the pre-commit hook -- a `--no-verify` commit, an amend, or a history
rewrite. Scoping it to the push range would leave the gap it exists to
cover.

If `betterleaks` is not on `PATH`, both hooks **fail** rather than skip. A
secret gate that passes when its scanner is absent would report success on
a commit it never inspected. Provision the pinned binary with `nix develop`,
or with `/gitapex:setup-gitapex-toolchain` in an ephemeral session.

`.betterleaks.toml` holds the config. It inherits the full built-in ruleset
and adds one allowlist, covering the seven eval fixtures under `evals/`
that carry deliberately planted fake credentials for redaction tests. Those
paths are listed exactly, not as an `evals/` wildcard, so a real credential
pasted into any other eval file still fails the gate -- adding a fixture
means editing that allowlist on purpose. That file also records which
suppression mechanism was verified to work on the pinned version, and which
silently does not; re-run both checks if the pin is ever bumped.

Neither hook is a merge gate: `git commit --no-verify` and
`git push --no-verify` both bypass them, and no CI workflow runs betterleaks
yet (named as a non-goal in #890).

## Local pre-push preflight

The pre-commit hooks above cover ruff and mypy only. Most of this
repository's other deterministic gates run as separate CI jobs, so a gap
used to be discovered one red check at a time on an already-open PR.

The same `uv run prek install -t pre-commit -t pre-push` above also installs
a **pre-push** hook that runs every gate with a working-tree-only form in
one pass, before the push leaves your machine. A warm run of all 23 wired
gates measures 4-6 seconds end to end. Run it by hand any time with:

```console
python3 .github/scripts/gitapex_gate_local_preflight.py
```

It prints a pass/fail line per gate, the captured output of each failing
one, and exits non-zero if any failed. `--list` prints the wired set
without running it.

If a clone predates this hook, re-run the install command above once to pick
it up, then confirm both shims with the check in the previous section.
`git push --no-verify` skips it, as with any pre-push hook.

The runner itself needs no dependencies, but all 23 wired gates run through
`uv` (the same `uv run` pins CI uses). Without `uv` on PATH every one of
them reports `FAIL ... failed to run` -- that is one missing tool, not a
whole broken wired set.

The wired set is not a list inside that script: it is every gate in
`.gitapex/ssot.json` whose `planes` array contains `"local"`, run with the
argv its own `local_invocation` field declares. Wiring a new gate in means
adding those two fields to its registry entry and nothing else.

A gate that has *no* working-tree-only form (it needs a PR body, GitHub API
state, a diff-derived argument, or a toolchain outside the local surface)
must instead carry a `local_exclusion` string saying which. The schema makes
exactly one of the two required, so a new gate cannot land unwired *and*
undocumented -- read the exclusions in `.gitapex/ssot.json` before assuming
a gate is missing here by oversight.

An argv that would run a shell, or hand inline code to an interpreter, is
refused before the runner starts anything -- the registry routes to tracked
scripts, it is not a place to put commands.

CI remains the authoritative merge gate; this is a fast first pass, the same
relationship the prek hook has to `lint.yml`.

## Issue citation convention

If a PR's changes fully satisfy an issue's acceptance criteria, cite it
with `Closes #N` (in the commit trailer and/or the PR body) so merging
closes it automatically. Use `Refs #N` only when the PR partially
addresses or merely relates to the issue.

## outward-artifact-preflight: PR-body trailer disclosure

The italic "Generated by" attribution trailer GitHub appends to a PR
body created through this tool -- naming the tool and carrying a
session URL under its own domain -- is an agreed, disclosed convention
for this repository under `skills/outward-artifact-preflight`'s check 1
item 2, not an undisclosed provenance marker. Ratified by the
repository owner on 2026-08-03
(https://github.com/tvna/gitapex/issues/687).

Scope, stated narrowly so this does not widen into a blanket exemption:

- Covers only the trailer GitHub itself appends to a PR body
  (server-added, not author-written).
- Does not cover a model identifier, session URL, or internal tooling
  fingerprint appearing anywhere else -- a commit message, code
  comment, issue body, generated file, or review comment. Those stay in
  scope by default, per `skills/outward-artifact-preflight`'s own
  open-invariant rule.
- Does not change what `scripts/gitapex_scan_provenance.py` reports: it still
  flags this trailer on every hit, by design. Confirming a hit is
  *this* trailer and not a lookalike remains a judgment call each
  time -- do not add an ignore pattern, allowlist, or `--exclude` flag
  to suppress it.

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

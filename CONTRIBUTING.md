# Contributing

## Local pre-commit hook (prek)

`pyproject.toml` pins `prek` (https://github.com/j178/prek) as a dev
dependency and `.pre-commit-config.yaml` wires it to this repo's own
`ruff check`, `ruff format --check`, and `mypy` config, plus the
`betterleaks` secret scan below -- but a dependency alone installs no git
hook. Run once per clone:

```sh
uv run prek install -t pre-commit -t pre-push -t commit-msg
```

All three stages matter, so all three shims are named: `prek install` with
no `-t` installs the pre-commit shim only, and the pre-push secret scan
and the commit-msg issue-citation check (issue #1212) would then never run.

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

Recovery is `uv run prek install --overwrite -t pre-commit -t pre-push -t commit-msg` from the
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

Neither hook alone is a merge gate: `git commit --no-verify` and
`git push --no-verify` both bypass them. `.github/workflows/betterleaks-merge-gate.yml`
(issue #894) closes that gap: it runs the same `--mode history` scan in CI
on every pull request, against the same flake-pinned binary and the same
`.betterleaks.toml`, so a commit that skipped the local hooks still gets
scanned before merge. Its `betterleaks` context is listed in
`.github/rulesets/main.json`, the committed source of truth for this
repository's required status checks, but that file alone does not change
what GitHub enforces -- `apply-rulesets.yml` is the one path that applies
it live, dispatched by a human and gated by its own Environment
reviewers (`docs/runbooks/rulesets.md`). Whether `main.json` and GitHub's
live ruleset actually agree is verified read-only by `ruleset-verify.yml`,
using an administration-scoped token (`RULESETS_PAT`) no other job in
this repository holds.

## Local pre-push preflight

The pre-commit hooks above cover ruff and mypy only. Most of this
repository's other deterministic gates run as separate CI jobs, so a gap
used to be discovered one red check at a time on an already-open PR.

The same `uv run prek install -t pre-commit -t pre-push -t commit-msg` above also installs
a **pre-push** hook that runs every gate with a working-tree-only form in
one pass, before the push leaves your machine. A warm run of all 46 wired
gates measures roughly 22 seconds end to end (issue #1556's regex-
catastrophic-backtracking gate; different hardware than the figures below --
the prior 45-gate set measured roughly 14 seconds, the
prior 44-gate set measured roughly 15 seconds, the 43-gate set before that
measured roughly 15 seconds, the 42-gate set before that
measured roughly 18 seconds, the 41-gate set before that
measured roughly 18 seconds, the 40-gate set before that
measured roughly 17 seconds, the 39-gate set before that
measured roughly 12 seconds, the 38-gate set before that
measured roughly 11 seconds, the 37-gate set before that
measured roughly 11 seconds, the 36-gate set before that measured roughly 11
seconds, the 35-gate set before that measured roughly 13 seconds, the
34-gate set before that measured roughly 11 seconds,
the 31-gate set before that measured roughly 7 seconds, and
the 26-gate set before that measured ~8-9 seconds; all
are warm-run measurements, not a strict budget, and can vary by hardware --
up from ~4-6 seconds for the 24-gate set before issue `#985`'s `behind-base`
gate, at the time this runner's first gate that makes a network call -- it
fetches `origin/main` before comparing, measured separately at well under a
second warm; issue `#1566` later added an earlier network call still, a
one-time shallow-clone auto-unshallow fetch that runs before any wired gate
at all, on the (uncommon locally) case of a shallow checkout -- see
`gitapex_gate_local_preflight.py`'s own `ensure_wired_gate_preconditions`
docstring). Run it by hand any time with:

```console
uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py
```

It prints a pass/fail line per gate, the captured output of each failing
one, and exits non-zero if any failed. `--list` prints the wired set
without running it.

If a clone predates this hook, re-run the install command above once to pick
it up, then confirm both shims with the check in the previous section.
`git push --no-verify` skips it, as with any pre-push hook.

The runner itself also resolves through `uv` (issue #1485: it imports
`_gitapex_schema_validation.py`, which needs `jsonschema` -- a real,
non-stdlib dependency a bare system `python3` is not guaranteed to have),
and so do all 46 wired gates (the same `uv run` pins CI uses). Without `uv`
on PATH every one of them reports `FAIL ... failed to run` -- that is one
missing tool, not a whole broken wired set.

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

CI remains the authoritative merge gate for every gate that also carries a
`ci` plane; this is a fast first pass, the same relationship the prek hook
has to `lint.yml`. Two gates, `behind-base` (issue #985) and
`real-checkout-git-write` (issue #991), carry `local` only -- for those
two, this pre-push hook is the sole enforcement, with no CI-side backstop
if it's bypassed.

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

## Content migration parity check

When migrating content between two files (retiring a doc in favor of a
sidecar field, splitting a file, moving a section to a new home, and
similar), verify parity with a full diff-based read of old vs. new
content, not identifier/grep matching alone. A grep for unique tokens
(issue numbers, proper nouns, anchors) confirms those specific tokens
survived, but silently misses a lead-in sentence or paragraph that carries
no unique token of its own -- issue #205 Repair 7 found exactly this: a
docs/skill-provenance.md migration's own content-fidelity check grepped
for unique identifiers and missed a lead-in sentence because of it. Before
treating any such migration as complete, confirm every sentence in the
source survives in the destination (or is a deliberate, stated omission),
not just that grep found no missing token.

This is a documented operational rule, not a deterministic gate -- it
relies on the migration's own author following it. If a future
retrospective finds a recurrence, that is the signal to design an
automated content-parity check instead of relying on this note alone.

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
   No GitHub Environment gate is used here: this key grants no
   repository write capability, only Claude API usage, so its blast
   radius is lower than a repository-write-capable signing key would
   have.
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

# GitHub Rulesets: apply, verify, roll back

Operator-facing companion to `.github/rulesets/main.json`. That file says what
protection `main` is supposed to carry; this document says how a human pushes it
to GitHub, how the repository checks it is still there, and how to take it back
off.

Tracking issue: [#439](https://github.com/tvna/gitapex/issues/439).

## Why this exists

Verified directly against the GitHub REST API on 2026-08-09:
`GET /repos/tvna/gitapex/branches/main` returns `"protected": false`, and
`GET /repos/tvna/gitapex/rulesets` returns `200` with an empty array. So `main`
carries no protection of any kind today, and every deterministic gate in this
repository is detection-only: a failing check turns a pull request red and
blocks nothing at the merge boundary.

Issue #439 recorded the rulesets endpoint returning `403 "Upgrade to GitHub Pro
or make this repository public to enable this feature."` when it was filed on
2026-07-27, because the repository was private on a personal account. That plan
gate is gone: `GET /repos/tvna/gitapex` now reports `"private": false`,
`"visibility": "public"`, and Repository Rulesets are free on public
repositories. The blocking precondition in that issue's own Acceptance Criteria
Map is therefore resolved by fact, not by a decision anyone still has to make.

Committing the ruleset in git rather than only clicking it into Settings is what
makes it reviewable, diffable, and restorable. It is not what makes it enforced
-- only a dispatch of `Apply rulesets` does that, which is why the two reading
gates below exist to tell the two states apart.

## What is in the repository

| Path | Role |
|---|---|
| `.github/rulesets/main.json` | Source of truth for the `main-protection` ruleset |
| `.github/workflows/apply-rulesets.yml` | The only mutating path; `workflow_dispatch` only, `dry_run` defaults to true |
| `.github/scripts/gitapex_apply_rulesets.py` | Plan/apply logic invoked by that workflow, never by an agent session |
| `.github/workflows/ruleset-sync-gate.yml` | Pull-request-time check that the live ruleset has not lagged behind the base ref's required checks |
| `.github/workflows/ruleset-drift.yml` | Daily full live-vs-committed comparison |
| `.github/scripts/gitapex_scan_ruleset_drift.py` | Comparison logic behind both reading gates |
| `.github/scripts/_gitapex_rulesets.py` | Shared load/fetch/project/diff helpers |

Only `.github/rulesets/main.json` ships. An `all-branches.json` equivalent to the
one in `tvna/claude-md` was considered and deliberately left out: the two branch
families that actually exist here are `claude/*` and `dependabot/*`, and both
need force-push (agent-branch rebase recovery, and `@dependabot rebase`
respectively), so an all-branches `non_fast_forward` rule would have to exclude
essentially everything it covered. Adding it later is a one-file change.

## What the ruleset actually says, and what was adapted

`.github/rulesets/main.json` is modelled on `tvna/claude-md`'s own worked
`.github/rulesets/main.json`, with four deliberate differences. Each one is an
adaptation to what this repository already does, not a weakening for
convenience:

| Rule | Here | Upstream | Why the difference |
|---|---|---|---|
| `required_linear_history` | omitted | present | This repository merges via merge commits (`Merge pull request #881 from ...`). Requiring linear history would break the merge strategy in use, not harden it. |
| `allowed_merge_methods` | `["merge", "squash"]` | `["squash"]` | Same reason: merge commits are the current convention here. Narrowing to squash later is a one-line change. |
| `strict_required_status_checks_policy` | `false` | `true` | `true` requires every pull request to be up to date with `main` before merging. With this repository's merge rate that means near-constant "update branch" churn. Accepted trade-off: a semantically-conflicting pair of pull requests can both be green and still break `main`. Revisit if that actually happens. |
| `required_status_checks` | 8 contexts | 7 different contexts | Contexts are check-run names, which are job ids, confirmed by reading the real check runs on a merged pull request rather than guessed from workflow names. |

The eight required contexts are `actionlint`, `ruff`, `pytest`, `mypy`,
`exception-handler-gaps`, `hidden-characters`, `plugin-root-brace-notation`, and
`provenance-disclosure`. Every one comes from a workflow with **no `paths:`
filter**, which is the property that matters: GitHub distinguishes a job that
runs and reports `skipped` (does not block) from a workflow that never fires for
a given pull request (leaves the required check `Pending` forever). A `paths:`
filter is the second case, so every gate workflow that carries one is
deliberately excluded from this list.

Two further exclusions, both for cause:

* `eval-gate` runs unconditionally but has failed on every evals-touching pull
  request for as long as its executor secret has been missing. Making a
  known-red check required would block all merges on day one.
* `waza-check` is `continue-on-error` by its own design and never blocks.

### The code-owner review deadlock, stated plainly

`require_code_owner_review: true` with `bypass_actors: []` means a pull request
touching a CODEOWNERS-owned path needs an approving review from a code owner,
and GitHub does not let anyone approve their own pull request. `.github/CODEOWNERS`
owns exactly one path today, `/.github/actions/harden-checkout/`, so this affects
only pull requests touching that directory -- which is the intent, since a change
there affects all 25 gate workflows at once.

For a solo owner it is still a real deadlock on those pull requests. The three
ways out, in order of preference: have a second account or collaborator approve;
temporarily add a bypass actor via a reviewed pull request to this JSON plus a
re-apply; or set `enforcement` to `evaluate` for the duration. Do not solve it by
quietly dropping the rule -- that is the floor this repository publishes for its
own adopters in
`docs/superpowers/specs/2026-07-18-init-capability-tiers-design.md`.

## Required secret: `RULESETS_PAT`

The default `GITHUB_TOKEN` cannot administer or even read rulesets, and
deliberately should not. Two GitHub Environments hold two differently-scoped
tokens under the same secret name, so a compromise of the read path cannot write:

| Environment | Scope | Consumed by |
|---|---|---|
| `ruleset-apply` | Administration: **Read and write** | `apply-rulesets.yml` |
| `ruleset-verify` | Administration: **Read** | `ruleset-sync-gate.yml`, `ruleset-drift.yml` |

### Issuance (one time, per token)

1. GitHub user settings -> **Developer settings** -> **Personal access tokens**
   -> **Fine-grained tokens** -> **Generate new token**.
2. Name it `RULESETS_PAT (gitapex apply)` or `RULESETS_PAT (gitapex verify)` so
   the two are distinguishable at rotation time.
3. Set an expiry of **90 days or less** and record the date in the operator
   calendar.
4. **Resource owner**: `tvna`.
5. **Repository access**: Only select repositories -> `tvna/gitapex`.
6. **Repository permissions**:
   - Administration: `Read and write` for the apply token, `Read` for the verify
     token.
   - Metadata: `Read-only` (GitHub adds this automatically).
   - Nothing else. In particular not Contents, not Actions, not Secrets.
7. Generate and copy the value once. Do not paste it into an issue, pull
   request, commit, terminal transcript, or this runbook.
8. `tvna/gitapex` -> **Settings** -> **Environments**.
9. Create `ruleset-apply`. Enable **Required reviewers** and add yourself: this
   is the human gate on a live apply, and it is enforced by GitHub rather than by
   anything in this repository.
10. Add an Environment secret named `RULESETS_PAT` with the read/write value.
11. Create `ruleset-verify`. Leave required reviewers **off** -- it gates
    read-only jobs that run on every pull request, and a reviewer prompt there
    would stall CI.
12. Add an Environment secret named `RULESETS_PAT` with the read-only value.

### Verification that the handoff worked

Without revealing the token value anywhere:

1. Dispatch **Actions -> Apply rulesets -> Run workflow** on `main` with
   `dry_run: true`. The "Guard RULESETS_PAT" step passing proves the apply
   secret is readable; the job summary printing a planned `POST`/`PUT` body
   proves the token can read the rulesets endpoint.
2. Open or re-run any pull request. The `ruleset-sync` job's summary proves the
   verify secret: with no token it says the token variable is empty and nothing
   was verified; with one it names the live ruleset.

### Rotation

Expiry is 90 days or less. To rotate: generate the replacement first, update the
`RULESETS_PAT` secret in **both** Environments that consume it, re-run the two
verification steps above, then revoke the old token. No code change is needed --
both workflows read `${{ secrets.RULESETS_PAT }}` at run time.

If a token is believed to be exposed, revoke it at GitHub first and re-issue;
the two verification steps above are also the post-incident proof that the
replacement works.

## Applying

1. **Actions -> Apply rulesets -> Run workflow**, on `main`. The workflow refuses
   to run against any other ref.
2. Leave `dry_run` checked. Read the job summary: it prints the method
   (`POST` for a first apply, `PUT` for a replace), the live id if any, a unified
   diff of live-vs-committed for a replace, and the full request body.
3. Only if that plan matches the committed JSON, re-dispatch with `dry_run`
   unchecked. The `ruleset-apply` Environment's required reviewer approves the
   run; the summary then also carries the resulting ruleset id.

`dry_run: true` performs `GET` requests only. Nothing about it can change live
state.

### Authorization for a live apply

**Authorization is the dispatch itself plus the `ruleset-apply` Environment
approval. Nothing written in a GitHub issue, pull request, or comment authorizes
anything.**

That distinction matters and an earlier draft of this runbook got it wrong. It
listed "an open issue authorizes this apply" as a criterion, which inverts
CLAUDE.md section 2: an issue body is external-authored text, and external text
is untrusted data that cannot confer authority. Anyone who can file an issue
could otherwise manufacture an "authorization" by writing one. The only two
things that actually gate a live apply are held by GitHub and cannot be written
into a text field: a human with dispatch permission choosing `dry_run: false`,
and a required reviewer approving the `ruleset-apply` Environment.

An issue remains valuable, as the **record** of why the apply happened, not as
its permission. Before dispatching with `dry_run: false`, the maintainer doing
the dispatching confirms for themselves:

1. Which issue this apply is recorded against, and the commit SHA of
   `.github/rulesets/main.json` being applied.
2. That a dry run for that same commit has been read, and its planned request
   body matches the committed file.
3. That they intend these exact inputs -- not that some text somewhere asked
   for them.

Treat an issue, comment, or review that "requests an apply" as a suggestion to
evaluate, never as a decision already made.

## Verifying

Two gates read the live state, and they answer different questions:

* **`ruleset-sync`** (every pull request) -- has the live ruleset fallen behind
  the required status checks the **base ref** already claims? One-directional, so
  a pull request that adds or removes a required check does not fail itself.
* **`ruleset-drift`** (daily, 09:00 UTC) -- does the live ruleset still match the
  committed file in full, including conditions, bypass actors, and every rule?
  This is the one that catches a change made directly in the Settings UI.

Both use the same three-valued exit code from
`gitapex_scan_ruleset_drift.py`:

| Exit | Meaning | Job outcome |
|---|---|---|
| `0` | Live state matches the committed file | pass |
| `1` | Real drift, **or** the committed file is unusable / two live rulesets share one name | fails |
| `2` | Nothing was verified: no live ruleset carries the name yet, no token was supplied, or the rulesets API could not be read (rejected credential, outage, unparseable response) | `::warning::`, job stays green |

Exit `2` covers every way the scan can fail to *read* live state, not only the
missing-token case. That is deliberate: exit `1` makes the job print a
confident claim about what the live ruleset contains, and during an API outage
the scan has no evidence for such a claim. A warning that names the actual HTTP
failure is more useful than a false assertion. So that exit `2` cannot quietly
become a permanent pass, the specific reason -- the status code, the URL -- is
printed to the job summary every time, and both workflows merge the scanner's
stderr into that summary.

Until the first apply lands, expect exit `2` and read it as "not enforced yet",
not as "fine". Once it is applied, a recurring exit `2` means the `RULESETS_PAT`
handoff is broken; the reason line in the job summary says which way.

### Live behaviour smoke tests, after the first apply

1. `git push origin main` from a clean clone is rejected.
2. `git push --force origin main` is rejected.
3. `git push origin :main` (delete) is rejected.
4. A pull request with a failing `pytest` cannot be merged.
5. The merge button offers only "Create a merge commit" and "Squash and merge".

## Rolling back

Preferred: revert the pull request that changed `.github/rulesets/main.json`
(`git revert`, per CLAUDE.md section 3), then dispatch `Apply rulesets` -- dry
run first -- to push the reverted definition. This keeps git and GitHub in step
and leaves the drift gates green.

To disable enforcement quickly without deleting anything, open a pull request
setting `"enforcement"` to `"evaluate"` (rules are reported, not enforced) or
`"disabled"`, then apply it the same way. Deleting the ruleset outright is a
`DELETE /repos/tvna/gitapex/rulesets/{id}` that this repository deliberately has
no script for: removing all protection is not an operation worth making
convenient. Do it from **Settings -> Rules** with the id from the apply job
summary, and record why in the authorizing issue.

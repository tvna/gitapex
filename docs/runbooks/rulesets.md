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
| `.github/workflows/ruleset-verify.yml` | Both read-only scans in one job: pull-request-time lag check, and the daily full live-vs-committed comparison |
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
`.github/rulesets/main.json`, with five deliberate differences. Each one is an
adaptation to what this repository already does, not a weakening for
convenience:

| Rule | Here | Upstream | Why the difference |
|---|---|---|---|
| `required_linear_history` | omitted | present | This repository merges via merge commits (`Merge pull request #881 from ...`). Requiring linear history would break the merge strategy in use, not harden it. |
| `allowed_merge_methods` | `["merge", "squash"]` | `["squash"]` | Same reason: merge commits are the current convention here. Narrowing to squash later is a one-line change. |
| `strict_required_status_checks_policy` | `false` | `true` | `true` requires every pull request to be up to date with `main` before merging. With this repository's merge rate that means near-constant "update branch" churn. Accepted trade-off: a semantically-conflicting pair of pull requests can both be green and still break `main`. Revisit if that actually happens. |
| `required_status_checks` | 8 contexts | 7 different contexts | Contexts are check-run names, which are job ids, confirmed by reading the real check runs on a merged pull request rather than guessed from workflow names. |
| `required_signatures` | omitted | present | Not a policy preference -- a measured fact about this repository. `main` already contains unsigned commits, and every commit on the branch that introduces this ruleset is unsigned (`git log --format='%H %G?'` reports `N`). Turning the rule on would reject the very merge that applies it, and the merge-commit path documented in the row above produces an unsigned commit by default. Enabling it is a separate change that has to come with a signing story first: see the GitHub App token minting in `.github/workflows/sync-agent-instructions.yml`, whose comment already assumes this rule exists. |

The eight required contexts are `actionlint`, `ruff`, `pytest`, `mypy`,
`exception-handler-gaps`, `hidden-characters`, `plugin-root-brace-notation`, and
`provenance-disclosure`.

Every one has to be a name that a check run actually reports under, on every
pull request targeting `main`. That is a stronger property than "the workflow
exists", and it is what `main-ruleset-required-checks` enforces, because GitHub
distinguishes a job that runs and reports `skipped` (does not block) from a
context nothing ever reports (leaves the required check `Pending` forever, with
no in-repository fix). Four distinct ways to land in the second case, all of
them rejected by the gate:

* a `paths:` / `paths-ignore:` filter on the `pull_request` trigger -- the
  workflow simply does not fire for a non-matching pull request, so every gate
  workflow carrying one is deliberately excluded from this list;
* a `branches:` / `branches-ignore:` filter that does not admit the default
  branch;
* a `types:` filter that omits `opened` or `synchronize`;
* a job that cannot report under its bare id at all -- a matrix job reports as
  `job (value)` once per leg, and a reusable-workflow call (`uses:`) reports its
  inner jobs as `caller / inner`.

Separately from the reachability question, the same gate validates the committed
file against a pydantic model of GitHub's own request body -- `extra="forbid"`
at every level, a `type`-discriminated rule union, and every `pull_request`
parameter required rather than defaulted. That layer exists because the earlier
key-set check only looked at the top level: a file carrying
`require_code_owner_reviews` (the plural typo GitHub silently ignores),
`required_approving_review_count: "zero"` (a 422 discovered only after a live
dispatch), an invented parameter and a rule with an unknown `type` passed all
four together with "shape is valid". Adopting a new GitHub rule type therefore
means extending that union -- deliberately, since the same change has to update
this runbook and `.gitapex/ssot.json` too.

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
| `ruleset-verify` | Administration: **Read** | `ruleset-verify.yml` (both scopes) |

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
   `dry_run: true`, and approve the environment prompt when it appears (it
   gates the dry run as well -- see "Applying" below). The "Guard RULESETS_PAT"
   step passing proves the apply secret is readable; the job summary printing a
   planned `POST`/`PUT` body proves the token can read the rulesets endpoint.
2. Open or re-run any pull request. The `ruleset-scan` job's summary proves the
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
2. Leave `dry_run` checked and dispatch. **The run pauses for the
   `ruleset-apply` Environment's required reviewer before it starts** -- see the
   note below; approve it. Then read the job summary: it prints the method
   (`POST` for a first apply, `PUT` for a replace), the live id if any, a unified
   diff of live-vs-committed for a replace, and the full request body.
3. Only if that plan matches the committed JSON, re-dispatch with `dry_run`
   unchecked and approve again. The summary then also carries the resulting
   ruleset id.

`dry_run: true` performs `GET` requests only. Nothing about it can change live
state.

> [!IMPORTANT]
> **The approval gate covers the dry run too, not just the live apply.**
> `environment: ruleset-apply` is set on the *job*, and GitHub is explicit that
> "a job that references an environment must follow any protection rules for the
> environment before running or accessing the environment's secrets". So both
> dispatches wait for a reviewer, and both `RULESETS_PAT` verification steps
> above wait with them. An earlier revision of this runbook attached the
> approval only to step 3, which would have left an operator watching a
> seemingly hung dry run.
>
> This is a cost, accepted deliberately. Moving the plan onto the read-only
> `ruleset-verify` Environment would remove the wait, but the dry run is also
> what proves the *apply* credential is readable -- that is verification step 1
> above -- and a plan that exercised a different token would prove nothing about
> the run that follows it.

### When a live apply finishes red

`POST` and `PUT` both return the *stored* ruleset, so the apply script reads its
own result back and compares it against the committed file before reporting
success -- a 2xx is not proof the state transition matched the policy. If
GitHub stored something the committed file does not specify, the job fails and
the summary carries a `[!CAUTION]` block listing each mismatch by dotted path
(`rules[2].parameters.require_code_owner_review: is False, ...`).

**A red apply job does not mean the write was rejected.** The write already
landed; only the verification failed. That is why the summary is still printed
in full, including the resulting ruleset id -- it is the handle the rollback
section below needs. Reconcile from the listed paths rather than re-dispatching
blindly, since a second `PUT` onto the same id would overwrite whatever is
actually there.

The comparison is a subset check, not equality: GitHub stamps its own defaults
and link fields onto the stored object, and the committed file asserts what must
hold, not that nothing else may be present. Full equality is the daily drift
scan's job, where a human reads the report.

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

Two gates read the live state. They answer different questions, and they run as
the same `ruleset-scan` job in `.github/workflows/ruleset-verify.yml`, which
picks the scope from the triggering event:

| Trigger | Scope | Source of truth | Question answered |
|---|---|---|---|
| `pull_request` | `required-checks` | the pull request's **base** ref | Has the live ruleset fallen behind the required status checks the base ref already claims? One-directional, so a pull request that adds or removes a required check does not fail itself. |
| `schedule` (daily 09:00 UTC), `workflow_dispatch` | `full` | `main`'s committed file | Does the live ruleset still match the committed file in full, including conditions, bypass actors, and every rule? This is the one that catches a change made directly in the Settings UI. |

One workflow rather than two because everything security-relevant is already
identical between them -- the same read-only token, the same `ruleset-verify`
Environment, the same permissions, the same scanner, the same exit contract --
so the only thing two files bought was a duplicated exit-code block.

**`apply-rulesets.yml` is deliberately *not* folded in with them.** GitHub lets
`jobs.<job_id>.environment` be an expression over the `inputs` and `github`
contexts, so a combined file could select the write-capable `ruleset-apply`
Environment at run time. Two consequences make that unacceptable: "which job can
administer rulesets" would stop being answerable by grep, and a
pull-request-triggered run that resolved to a reviewer-gated Environment would
sit waiting for approval rather than reporting. The read/write credential keeps
its own file so both properties hold statically.

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

### One field these scans cannot check, and where it is checked instead

`bypass_actors` is **not** compared by either reading gate, and every run says
so in its own summary rather than leaving it implied. GitHub's REST
documentation for the rulesets endpoints states: "To prevent leaking sensitive
information, the bypass_actors property is only returned if the user making the
API request has write access to the ruleset." The `ruleset-verify` Environment
holds an Administration:**Read** token by design, so the field is simply absent
from every response these scans see.

Comparing an absent field against the committed `[]` would report drift every
single night for a ruleset that is in fact correct -- a check that is red for a
condition no commit can clear is a check everyone learns to ignore. Widening
the verify token to read/write would fix the comparison by destroying the
read/write separation the two Environments exist to create.

So the field is verified at the only point a credential legitimately can see
it: the post-write check inside `Apply rulesets`, which runs with the read/write
token and compares the stored ruleset against the committed file. `bypass_actors`
is therefore proven at the moment it is set, and unproven between applies. A
bypass actor added through the Settings UI afterwards would not be caught by the
nightly scan; catching that needs either a write-scoped read (rejected above) or
a manual look at **Settings -> Rules**, which the smoke-test list below is the
place to do.

### Parent rulesets are out of scope

Both reading gates and the apply script list rulesets with
`includes_parents=false`. GitHub's default for that parameter is `true`, which
also returns rulesets configured at the organisation or enterprise level. Those
are not this repository's to reconcile: a parent ruleset sharing the committed
`name` would make the resolver see two matches and refuse permanently, and a
parent-only match is worse -- the apply script would plan a `PUT` onto an id it
cannot write, and the drift scan would compare against a ruleset no commit here
can change.

### Live behaviour smoke tests, after the first apply

1. `git push origin main` from a clean clone is rejected.
2. `git push --force origin main` is rejected.
3. `git push origin :main` (delete) is rejected.
4. A pull request with a failing `pytest` cannot be merged.
5. The merge button offers only "Create a merge commit" and "Squash and merge".
6. **Settings -> Rules -> main-protection** lists no bypass actors. This one is a
   manual look rather than a scripted check, for the reason given above.

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

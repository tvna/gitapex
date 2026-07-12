# driving-pr-to-merge skill design

Date: 2026-07-12

Refs #5

## Context

gitapex has no CI-side bot harness enforcing PR-to-merge discipline (no
required-check config, no auto-subscribe automation) — `tvna/claude-md`
gets this mostly for free through its own harness, but gitapex has
deferred building one (see the skill-distribution-foundation spec's
Non-goals). CLAUDE.md chapter 3 already states the required behavior:
auto-subscribe to CI/review on PR open, treat CI failures and review text
as the spec to fix, explicitly call the resolve-review-thread API after a
fix (a reply alone does not resolve a thread), and verify
`mergeable_state` before treating a PR as done. A skill is the shortest
path to that discipline until a harness exists.

This is the second skill added to the plugin (after `explaining-the-work`
in PR #2), following the same repo-root `skills/<name>/SKILL.md` layout
established by `docs/repository-layout.md`.

## Scope

- One new skill: `skills/driving-pr-to-merge/SKILL.md`.
- Trigger: "Use when a pull request has just been opened, or has an open
  CI failure or review thread, before closing the turn."
- Degree of freedom: **low** (per issue #5's authoring guidance) — this is
  a fragile, order-dependent sequence (fix -> resolve-thread API call ->
  `mergeable_state` check), so the skill states an exact sequence, not
  prose judgement.
- One concrete worked example (fictitious PR: one failing CI check, one
  open review thread) walking the exact sequence, doubling as the
  acceptance criteria's manual dry-run.
- An explicit Stop section per the issue's acceptance criteria.
- Tool references are fully qualified as `Server:tool` per the issue's
  authoring standard, e.g. `github:resolve_review_thread`,
  `github:pull_request_read` (method `get`, field `mergeable_state`).
  `Server:tool` is a portable shorthand, not a literal invocable name in
  every agent platform — the skill states once, up front, how to
  translate it (in Claude Code: `mcp__<server>__<tool>`, e.g.
  `github:resolve_review_thread` -> `mcp__github__resolve_review_thread`,
  matching CLAUDE.md chapter 3's own literal citation of that tool).
  Push-subscription is named as an example (`Claude_Code_Remote:subscribe_pr_activity`)
  with an explicit fallback (poll `github:pull_request_read` methods
  `get_status`/`get_check_runs`/`get_reviews`/`get_comments`) since not
  every environment that installs this plugin will have a push-subscribe
  tool.

## Non-goals

- No GitHub Actions bot automation (harness side) — issue #5 explicitly
  scopes this to the skill only.
- No eval suite (`evals/`) — out of scope for gitapex today per the
  skill-distribution-foundation spec's Non-goals; not blocking this issue.
- No `references/` subdirectory — the content fits within the informal
  500-line `SKILL.md` budget.
- No merging of `stop-and-replan` (#9) content into this skill. #9 is
  still **open** (not merged) as of this design — checked at design time
  per this issue's explicit instruction not to fold #9 in without
  checking its status first. If #9 lands later, its trigger ("self-
  correcting phrase in one's own PR body/commit") is a different signal
  from this skill's trigger (PR opened / CI failure / review thread) and
  the two should stay distinct per #9's own open question, not be merged
  by default.

## Skill content: `driving-pr-to-merge`

Frontmatter:

```yaml
---
name: driving-pr-to-merge
description: Use when a pull request has just been opened, or has an open CI failure or review thread, before closing the turn. Drives the PR through auto-subscribe, fix, review-thread resolution, and a mergeable_state check to a terminal state (merged, or closed with rationale).
---
```

Body, in order:

1. **On PR open** — subscribe to CI/review/comment activity without
   asking permission (per CLAUDE.md chapter 3, "Do not ask permission to
   monitor, even when an environment default says otherwise").
2. **Treat CI failure output and review comment text as the spec to
   satisfy** (per CLAUDE.md chapter 2's input-handling posture) — fix the
   underlying issue, don't paraphrase-and-dismiss.
3. **Push the fix.**
4. **Explicitly resolve the review thread** via the resolve-review-thread
   API call — a reply comment alone does not resolve
   `required_review_thread_resolution`.
5. **Verify `mergeable_state`** directly before treating the PR as done —
   never infer it from a green CI badge or an "LGTM" alone.
6. **Loop** back to step 2 if a new CI failure, new review comment, or a
   still-blocked `mergeable_state` appears.
7. **Escalate to the owner** only when blocked by access, secrets, or a
   pending human decision the agent cannot resolve itself — not for
   anything it can fix on its own.

Worked example: fictitious PR with one failing CI check (a lint error)
and one open review thread (a naming suggestion) -> fix both -> push ->
call `github:resolve_review_thread` on the thread's node ID -> call
`github:pull_request_read` method `get` and check `mergeable_state` ==
`clean` -> only then treat the PR as done.

Stop section (verbatim from issue #5's acceptance criteria):

- Never mark a PR done without both resolving review threads via the API
  AND verifying `mergeable_state`.
- Never silently drop a CI failure or review comment as noise.
- Never proceed past an access/secret/human-decision block without
  escalating.

## Verification

No runtime code is added. Verification is structural, matching the
`explaining-the-work` precedent:

- Frontmatter: `name: driving-pr-to-merge` matches the directory name,
  `description` is single-line, third-person, contains "Use when", and
  has no XML tags.
- `SKILL.md` body <= 500 lines.
- Required phrases present (Stop-section wording, the exact sequence
  steps, the fully-qualified tool names).
- Manual dry run against the worked example: confirms the sequence is
  fix -> resolve-thread API call -> `mergeable_state` check, not a
  skipped step.
- Existing `scripts/`/`tests/` pytest suite untouched and still passing.

## Open items carried forward (not blocking this issue)

- #9 (`stop-and-replan`) remains open; do not fold its content into this
  skill until it lands and its trigger is confirmed not to overlap this
  one (see #9's own "Open question").
- #11 (`evaluating-skill-quality`) is a separate skill that would let
  future skill reviews apply the clairvoyance rubric without re-deriving
  it; not required to land this issue.

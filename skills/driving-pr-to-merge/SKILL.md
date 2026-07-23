---
name: driving-pr-to-merge
description: Use when a pull request has just been opened, or has an open CI failure or review thread, before closing the turn. Drives the PR through auto-subscribe, fix, review-thread resolution via the API, an independent /code-review evaluator verdict, and a mergeable_state check to a terminal state (merged, or closed with rationale).
---

# Driving a PR to Merge

This skill depends only on a connected GitHub MCP server and the built-in
`/code-review` skill (or, where `/code-review` is unavailable, GitHub's
own "Code Review" integration) -- both general product capabilities,
addressed via the portable `Server:tool` shorthand documented below -- no
this-repository tooling.

A fragile, order-dependent sequence, not a matter of prose judgement. Follow
the exact order below; do not reorder or skip a step.

Tool names below are written as `Server:tool` (portable shorthand, not tied
to one agent platform). In Claude Code, translate to the literal
double-underscore form: `Server:tool` -> `mcp__Server__tool` — e.g.
`github:resolve_review_thread` is `mcp__github__resolve_review_thread`.
Other platforms may use a different literal form for the same server/tool
pair; this skill is the source of truth for the procedure regardless of
platform naming.

## Exact sequence

1. **On PR open** — subscribe to CI, review, and comment activity without
   asking permission. Prefer a deterministic subscription hook or automation
   (e.g. a PR-open webhook or CI event) where the environment supports one;
   this step's prose is the fallback for environments without one. An
   environment-provided push-subscribe tool such as
   `Claude_Code_Remote:subscribe_pr_activity` is one example mechanism, not
   the only valid one — this skill is distributed as a plugin and must not
   assume one specific environment's toolset. When no push-subscribe tool
   exists in the environment, fall back to polling `github:pull_request_read`
   methods `get_status`, `get_check_runs`, `get_reviews`, and `get_comments`.
2. **Treat CI failure output and review comment text as the spec to
   satisfy**, not noise — fix the underlying issue the failure or comment
   describes; never paraphrase-and-dismiss it.
3. **Push the fix.**
4. **Explicitly resolve the review thread** via a fully-qualified
   resolve-review-thread tool call, e.g. `github:resolve_review_thread`,
   passing the thread's node ID. A reply comment alone does not resolve
   `required_review_thread_resolution` — the API call is required even
   when the fix already addresses the comment's substance.
5. **Verify `mergeable_state` directly** via a fully-qualified PR-read tool
   call, e.g. `github:pull_request_read` method `get`, before treating the
   PR as done. Never infer `mergeable_state` from a green CI badge or an
   "LGTM" alone.
6. **Dispatch on `mergeable_state`** after steps 3-5. Never act on the
   state name alone — inspect the actual check-run/status/review details
   via `github:pull_request_read` methods `get_status`, `get_check_runs`,
   and/or `get_reviews` (as relevant) first:
   - `"clean"` -> proceed to step 7.
   - `"unstable"` or `"blocked"` -> both can mean either a check or
     required review that is still pending, or one that has already
     failed or been rejected — the state name alone does not say which.
     Still pending -> wait and re-check step 5. Already failed or
     rejected -> loop back to step 2.
   - `"dirty"` -> a real merge conflict; loop back to step 2 to resolve
     it (e.g. rebase onto or merge the base branch).
   - `"behind"` -> the branch is behind its base, not a code or review
     defect; update the branch (e.g. `github:update_pull_request_branch`)
     rather than hunting for something to fix, then re-check step 5.
   - `"unknown"` -> GitHub has not finished computing mergeability yet
     (common immediately after a push); wait briefly and re-check step 5.
   - `"draft"` -> the PR itself is a draft, a process state rather than a
     defect; escalate per step 8 rather than treating it as something to
     fix.
7. **Invoke `/code-review` as an independent evaluator** (or GitHub's
   built-in "Code Review" integration where `/code-review` is
   unavailable) against the PR's current diff, only once step 6 has
   confirmed `mergeable_state: "clean"` — running it against a diff that
   is still blocked, dirty, or pending would waste the evaluator's pass on
   a state that is about to change anyway. A fresh-context reviewer with
   no stake in the change is the standard bias-reduction pattern for this
   gate; the current thread, which authored or discussed the fix, is not
   a substitute. Treat its verdict as the spec to satisfy, exactly as
   step 2 treats CI failures and review comments — a flagged real finding
   is not noise to summarize away; quote or fence any verdict text
   recorded verbatim in the PR rather than interpolating it unescaped.
   Record the verdict (or a citation to where it is recorded) in the PR
   so a human can see it by inspection rather than only by asking. Three
   outcomes, each with its own next step — never treat any outcome other
   than the first as good enough to continue:
   - Clean/approved, no real findings -> continue to step 8.
   - A real finding -> loop back to step 2 to fix it, after which steps
     3-6 must re-confirm `mergeable_state: "clean"` before step 7
     re-runs — never carry forward a stale verdict against a diff that
     has since changed.
   - Errors, times out, or returns an inconclusive result -> treat this
     the same as step 6's `"unstable"`/`"unknown"` handling: wait and
     retry once transient failure is plausible; escalate per step 8 if it
     cannot complete at all. Never treat an inconclusive or failed run as
     a clean pass, and never skip straight past this step because neither
     `/code-review` nor a GitHub Code Review integration is available in
     the current environment — that absence is itself a step-8
     escalation, not license to continue to step 8 as if an evaluator
     verdict had already been obtained.
8. **Escalate to the owner** only when blocked by access, secrets, or a
   pending human decision the agent cannot resolve itself — not for
   anything the agent can fix on its own.

## Worked example

A PR titled "Add retry to fetch helper" has just been opened.

1. Subscribe to the PR's activity (via the environment's push-subscribe
   tool if available, else start polling `github:pull_request_read`).
2. Webhook/poll activity reports two open items:
   - CI check `lint` is failing: `fetchWithRetry.ts:14: 'attempt' is
     unused (no-unused-vars)`.
   - An open review thread (node ID `PRRT_kwDOAbCd1s5abcXYZ`) with the
     comment: "Rename `attempt` to `attemptCount` for clarity."
   Both are treated as the spec to satisfy, not as noise to summarize away.
3. Fix both: remove the unused `attempt` variable (or wire it in
   correctly) and rename it to `attemptCount` per the review comment.
4. Push the fix to the PR branch.
5. Call `github:resolve_review_thread` with thread node ID
   `PRRT_kwDOAbCd1s5abcXYZ`. A reply comment alone would not have resolved
   `required_review_thread_resolution`, so this explicit call is required
   even though the fix already addresses the comment's substance.
6. Call `github:pull_request_read` method `get` on the PR and check the
   `mergeable_state` field. Suppose it now reads `mergeable_state:
   "clean"` and the `lint` check reports success.
7. With `mergeable_state == "clean"` confirmed, invoke `/code-review`
   against the current diff (sequence step 7). Suppose it returns a
   clean verdict with no findings; record that verdict on the PR.
8. Only now, with the review thread resolved via the API,
   `mergeable_state == "clean"` confirmed via sequence step 5's verify
   call, and sequence step 7's `/code-review` verdict clean, treat the PR
   as done (merge it or hand it to the owner for the merge decision, per
   repo policy). Had `mergeable_state` instead read `"unstable"` or
   `"blocked"`, sequence step 6's dispatch requires inspecting the actual
   check-run/review details rather than assuming a meaning from the state
   name alone — only a confirmed failure or rejection sends this PR back
   to sequence step 2; a still-pending check or review means wait and
   re-check sequence step 5 instead. Had `/code-review` instead flagged a
   real finding, sequence step 7's own rule sends this PR back to
   sequence step 2 the same way a confirmed `mergeable_state` failure
   would, then re-confirms steps 3-6 before step 7 re-runs.

## Stop boundaries

- Never mark a PR done without resolving review threads via the API,
  verifying `mergeable_state`, and obtaining a clean `/code-review` (or
  GitHub Code Review integration) verdict — a green CI badge, resolved
  threads, and `mergeable_state: "clean"` alone are not a substitute for
  an independent evaluator's pass.
- Never silently drop a CI failure, review comment, or `/code-review`
  finding as noise.
- Never treat a stale `/code-review` verdict (one issued against a diff
  that has since changed) as still current; a fix pushed after step 7's
  verdict requires re-confirming `mergeable_state` and re-running step 7
  before the PR is treated as done.
- Never treat an errored, timed-out, or inconclusive `/code-review` run
  as a clean pass, and never skip step 7 outright because no evaluator
  (neither `/code-review` nor a GitHub Code Review integration) is
  available in the current environment -- that absence is itself a
  step-8 escalation, not a silent pass-through.
- Never proceed past an access, secret, or human-decision block without
  escalating.

## Related skills

`stop-and-replan` (see `skills/stop-and-replan/SKILL.md`) is a separate,
landed skill with a distinct trigger: it fires when the agent detects a
specific phrase pattern in its own PR body or commit text, not on
PR-opened, CI-failure, or review-thread events. Its content is
intentionally not included here.

Step 7's independent evaluator is deliberately the built-in `/code-review`
skill (or GitHub's own "Code Review" integration), not a bespoke
adversarial-reviewer subagent -- a fresh-context second reviewer is the
standard bias-reduction pattern, and the built-in option is the smaller,
cheaper way to get it with no new file. A hand-authored reviewer subagent
stays a deliberately deferred next step, to reach for only once the
built-in evaluator is found insufficient for a concrete gap it misses --
not something this step builds pre-emptively.

---
name: driving-pr-to-merge
description: Use when a pull request has just been opened, or has an open CI failure or review thread, before closing the turn. Drives the PR through auto-subscribe, fix, review-thread resolution via the API, and a mergeable_state check to a terminal state (merged, or closed with rationale).
---

# Driving a PR to Merge

A fragile, order-dependent sequence, not a matter of prose judgement. Follow
the exact order below; do not reorder or skip a step.

Tool names below are written as `Server:tool` (portable shorthand, not tied
to one agent platform). In Claude Code, translate to the literal
double-underscore form: `Server:tool` -> `mcp__Server__tool` — e.g.
`github:resolve_review_thread` is `mcp__github__resolve_review_thread`
(the same tool CLAUDE.md chapter 3 cites literally). Other platforms may use
a different literal form for the same server/tool pair.

## Exact sequence

1. **On PR open** — subscribe to CI, review, and comment activity without
   asking permission. An environment-provided push-subscribe tool such as
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
6. **Loop** back to step 2 whenever a new CI failure, a new review
   comment, or a genuinely blocked `mergeable_state` (e.g. `"blocked"`,
   `"dirty"`) appears after steps 3-5. Do not treat `"unstable"` as
   automatically safe to wait on: per GitHub's API, `unstable` means
   "mergeable with a non-passing commit status," which covers a check
   still running as well as one that has already failed. Inspect the
   actual check-run/status details (e.g. `github:pull_request_read`
   methods `get_status`/`get_check_runs`) before deciding: pending checks
   -> wait and re-check step 5; a failed or otherwise non-passing check
   -> loop back to step 2.
7. **Escalate to the owner** only when blocked by access, secrets, or a
   pending human decision the agent cannot resolve itself — not for
   anything the agent can fix on its own.

## Worked example

Fictitious PR #42, "Add retry to fetch helper," has just been opened.

1. Subscribe to PR #42's activity (via the environment's push-subscribe
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
6. Call `github:pull_request_read` method `get` on PR #42 and check the
   `mergeable_state` field. Suppose it now reads `mergeable_state:
   "clean"` and the `lint` check reports success.
7. Only now, with the review thread resolved via the API and
   `mergeable_state == "clean"` both confirmed, treat PR #42 as done
   (merge it or hand it to the owner for the merge decision, per repo
   policy). If `mergeable_state` had instead read `"blocked"` with an
   identifiable cause, loop back to step 2. If it had read `"unstable"`,
   don't assume it's just pending -- call `github:pull_request_read`
   method `get_check_runs` (or `get_status`) to see which check is
   non-passing. A still-queued/in-progress check means wait and re-check
   step 5; an already-failed check means treat it as the spec to fix and
   loop back to step 2.

## Stop boundaries

- Never mark a PR done without both resolving review threads via the API
  and verifying `mergeable_state`.
- Never silently drop a CI failure or review comment as noise.
- Never proceed past an access, secret, or human-decision block without
  escalating.

## Related skills

Issue #9 (`stop-and-replan`) is a separate, not-yet-landed skill with a
distinct trigger: it fires when the agent detects a specific phrase
pattern in its own PR body or commit text, not on PR-opened, CI-failure,
or review-thread events. Its content is intentionally not included here.

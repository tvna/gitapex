---
name: stop-and-replan
description: Use when your own PR body or commit message is about to contain a self-correcting phrase, such as "missed the original thesis" or "correction after review". Treats the phrase as a STOP signal -- close the PR with rationale and re-plan in the parent issue, instead of amending in place.
---

# Stop and Replan

A self-correcting phrase in your own PR body or commit message is a STOP
signal, not a wording problem. It means the plan missed the issue, not that
the prose describing it was clumsy.

**Prerequisite:** the Stop action below requires a connected GitHub MCP
server. Tool names are written as `Server:tool` (portable shorthand); in
Claude Code, translate to the literal double-underscore form --
`github:update_pull_request` is `mcp__github__update_pull_request`,
`github:add_issue_comment` is `mcp__github__add_issue_comment`. Other
platforms may use a different literal form for the same server/tool pair.

## Trigger phrases

Recognize these, and close variants, in text you are about to write into a
PR body or commit message:

- "missed the original thesis"
- "correction after review"
- "this isn't what the issue asked for"

## Stop action

On detection, before writing the phrase into the PR or commit:

1. Do not amend the existing commit or edit the PR body to patch the
   wording.
2. Close the current PR via `github:update_pull_request` (`state: closed`),
   with a body giving the rationale: what thesis was missed, quoting the
   detected phrase and naming the issue the PR should have satisfied.
3. Verify the close: re-fetch the PR and confirm its state is actually
   `closed` before proceeding -- do not assume the write succeeded.
4. Return to the parent issue and post the same rationale via
   `github:add_issue_comment`, then re-plan from there. A fresh branch and
   PR carry the corrected plan; nothing is pushed to the closed PR's branch.

## Worked example

Input (about to be written as this PR's description):

> Correction after review: this misses the original thesis of #12 -- the
> issue asked for a read-only sync check, and this PR built a write-back
> sync instead.

Output:

- Close this PR with body: "Missed the original thesis of #12: the issue
  asked for a read-only sync check, this PR implemented a write-back sync
  instead. Closing to re-plan in #12 rather than retrofitting a
  write-path PR onto a read-only ask."
- Comment the same rationale on #12 and re-plan from there.
- Do not push a follow-up commit to the closed PR's branch.

## Known gaps

The committed eval suite (`evals/stop-and-replan/`) runs a single trial
per task with no committed no-skill baseline. Only `claude-sonnet-4.6` has
been evaluated; cross-model behavior is a qualitative read (low-freedom
policy, low over-prescription risk), not measurement.

## Stop boundaries

- Never treat the detected phrase as "just clean up the wording" -- it
  signals the plan itself needs revisiting, not only the prose describing
  it.
- Never amend the flagged commit or edit the flagged PR body in place; the
  STOP action is close-and-replan, not silent correction.
- Do not apply this skill to phrases describing ordinary iteration (for
  example "fixed a typo", "addressed review comment") -- those are the
  normal review loop, not a thesis miss.

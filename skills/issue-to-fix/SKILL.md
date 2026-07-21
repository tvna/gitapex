---
name: issue-to-fix
description: Use when given a bare issue reporting a defect (or a CI failure with no scoped fix yet), before writing any fix code. Reproduces the issue live, escalates explicitly if reproduction fails, writes a failing test before touching the fix, applies the minimal fix, then verifies the test flips with no regressions. Distinct from driving-pr-to-merge (fixes CI on an already-open PR with a fix already in flight) and issue-to-branch (plans a branch/PR from an issue without reproducing or fixing).
---

# Issue to Fix

This skill depends only on a connected GitHub MCP server (a general
product capability) for the Step 2 escalation action (commenting
on an existing issue or opening a new one); Steps 1 and 3-5 (reproduce,
write a failing test, fix, verify) are entirely general and depend on no
this-repository tooling. Tool names below are written as `Server:tool`
(portable shorthand); in Claude Code, translate to the literal
double-underscore form -- `github:add_issue_comment` is
`mcp__github__add_issue_comment`. Other platforms may use a different
literal form for the same server/tool pair.

A hard-gated, order-dependent sequence, not a matter of prose judgement --
follow the exact order below; do not reorder or skip a step. Never fix
what has not been reproduced.

## Exact sequence

1. **Reproduce.** Attempt the issue's reported reproduction steps directly
   against the real code path -- never a proxy, never inferred behavior.
   Do not proceed to any later step without a live reproduction.
2. **Escalate on failed reproduction.** If reproduction fails, stop here.
   - If the input is an existing issue, comment on it (e.g.
     `github:add_issue_comment`) stating exactly what was tried and what
     did not reproduce.
   - If the input is a standalone CI failure with no linked issue (for
     example, a scheduled workflow run with no issue tracking it), open a
     new issue (e.g. `github:issue_write` method `create`) recording the
     same: what was tried and what did not reproduce. This follows the
     repository's own "open an issue before any branch, commit, or PR"
     convention rather than leaving a CI signal with nowhere to land.

   Either way, stop -- do not guess at a fix for an unreproduced defect.
   This is the same "ambiguous input earns a question, evidence earns a
   fix" discipline applied concretely: a failed reproduction is ambiguous
   input, not evidence.
3. **Write a failing test first.** Once reproduced, encode the failure as
   a test that fails for the right reason -- run it and confirm it fails
   before touching any fix code. Skipping straight to a fix, even one the
   agent is confident in, is not allowed.
4. **Fix minimally.** Write the smallest change that makes the failing
   test pass -- no surrounding refactor, no unrelated cleanup bundled in.
5. **Verify the test flips.** Run the same test and confirm it now
   passes, and run the existing suite to confirm nothing else regressed.
   A newly-passing test alone is not sufficient; the existing suite must
   also still pass.

## Worked example

An already-open issue, "Search returns duplicate results when a query
matches both title and body."

1. Reproduce: run the search endpoint with a query matching both fields
   against the real search path. It does return duplicates -- reproduced.
2. (Skipped -- reproduction succeeded.)
3. Write a failing test: add a test asserting the search result set has
   no duplicate IDs for this query; run it and confirm it fails with the
   duplicate present.
4. Fix minimally: dedupe by result ID in the search merge step, no other
   change.
5. Verify: re-run the new test -- it now passes -- and run the full test
   suite -- no other test regressed.

Contrast: had step 1 failed to reproduce the duplicates against the real
search path, the correct next move is step 2 -- comment on the issue
stating the exact query tried and that no duplicates appeared, then stop.
Do not guess at a dedupe fix for a defect that did not reproduce.

Contrast (no linked issue): a scheduled nightly workflow fails with no
issue tracking it, and attempting the same steps that failed in CI does
not reproduce the failure locally. Step 2's first bullet does not apply
-- there is no issue to comment on -- so open a new issue recording the
exact steps attempted and that they did not reproduce, then stop.

## Stop boundaries

- Never write or change fix code before a live reproduction succeeds.
- Never skip the failing-test step (Step 3) -- not even for a fix the
  agent is confident in. A fix without a failing test that preceded it
  does not satisfy this skill.
- Never treat a failed reproduction as license to guess -- escalate via
  Step 2 and stop there; do not proceed past it.
- Never bundle a refactor or unrelated cleanup into the Step 4 fix.

## Related skills

- **vs. `driving-pr-to-merge`:** that skill fixes CI on an already-open PR
  where a fix is already in flight; this skill starts from a bare issue
  with no fix yet, and produces the PR `driving-pr-to-merge` would then
  take over.
- **vs. `issue-to-branch`:** that skill produces an implementation-ready
  branch/PR plan with an Acceptance Criteria Map; it does not itself
  reproduce or fix a defect. `issue-to-fix` is the skill that actually
  reproduces and fixes, for the specific case of a reported defect (as
  opposed to `issue-to-branch`'s general issue-to-plan scope, which also
  covers features and chores).

---
name: fixing-a-reported-issue
description: Use when given a bare issue reporting a defect (or a CI failure with no scoped fix yet), before writing any fix code. Reproduces the issue live, escalates explicitly if reproduction fails, writes a failing test before touching the fix, applies the minimal fix, verifies the test flips with no regressions, then discloses an ACM waiver on the target issue before any PR follows. Distinct from drafting-a-pr-to-merge (fixes CI on an already-open PR with a fix already in flight) and planning-a-branch-from-an-issue (plans a branch/PR from an issue without reproducing or fixing).
---

# Fixing a Reported Issue

This skill depends only on a connected GitHub MCP server (a general
product capability) for the Step 2 escalation action (commenting
on an existing issue or opening a new one) and the Step 6 disclosure
action (reading and updating the target issue); Steps 1 and 3-5
(reproduce, write a failing test, fix, verify) are entirely general and
depend on no this-repository tooling. Tool names below are written as
`Server:tool` (portable shorthand); in Claude Code, translate to the
literal double-underscore form -- `github:add_issue_comment` is
`mcp__github__add_issue_comment`. Other platforms may use a different
literal form for the same server/tool pair.

A hard-gated, order-dependent sequence, not a matter of prose judgement --
follow the exact order below; do not reorder or skip a step. Never fix
what has not been reproduced.

This skill stays invocable without an explicit human trigger by design:
every GitHub write it performs (Step 2's comment/new-issue escalation,
Step 6's waiver disclosure) is a narrow, low-freedom action gated by its
own exact-format check, not a broad or irreversible one, and a
repository with its own deterministic write-side gates (e.g. gitapex's
own `hooks/check-issue-acm-disclosure.sh` and
`hooks/check-pr-issue-acm-disclosure.sh`) backstops it independently of
whether this skill's own judgement was correct.

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
6. **Disclose the defect waiver on the target issue.** Only on this
   sequence's success path -- after Step 5's verification, never on the
   Step 2 escalation path, where no PR follows. Before any PR is opened
   for this fix:
   - Fetch the target issue's current body (e.g. `github:issue_read`)
     and check it against the same deterministic disclosure check
     gitapex's own PreToolUse hook enforces at PR-creation time (see
     `hooks/check_acm_present_or_waiver.py`'s `has_acm_disclosure`): an
     Acceptance Criteria Map table header, or a waiver line of the exact
     form `ACM: not-applicable (<category>): <reason>`. Never substitute
     a looser textual judgment of "does this look like a waiver" for
     that exact check -- a downstream hook re-derives this same check
     independently against the issue's live state regardless, so a
     loose pass here only risks silently skipping the disclosure this
     step exists to guarantee.
   - If the body already discloses one (of any category), this step is
     a confirming no-op.
   - If it discloses neither, append the waiver line to the body
     already fetched above and call `github:issue_write` method
     `update` with that combined text as `body`: **`update`'s `body`
     parameter replaces the issue's entire body outright -- it does not
     append.** Passing the waiver line alone as `body` silently destroys
     the issue's original defect report. Always construct the new body
     as `<the body fetched above>\n\nACM: not-applicable (defect):
     <one-line reason tied to this fix, in your own words -- never copy
     the issue's own text verbatim into it>`, never the waiver line in
     isolation. Vocabulary is gitapex's own, substituted with the
     calling repository's own equivalent deterministic check where one
     exists. Where no such repository-specific check can be found, still
     append gitapex's own shaped line rather than skipping the step
     outright: a waiver line no local gate reads costs nothing, while
     silently skipping risks leaving a target issue undisclosed
     wherever this skill's home repository's own hook does read it.
   - Re-fetch the issue after posting and confirm both the waiver line
     and the issue's original content are still present -- the same
     verify-after-act discipline Steps 3 and 5 already apply to their
     own test/fix cycle. A write that silently failed, was rejected, or
     replaced the original body is not a completed disclosure.

   This step exists because `fixing-a-reported-issue` is the one skill
   in this repository's issue-to-PR pipeline whose target issues are
   never required to carry an ACM or waiver by design (see Related
   skills) -- a repository that gates PR creation on its cited issue's
   ACM/waiver disclosure (gitapex's own
   `hooks/check-pr-issue-acm-disclosure.sh` is one example) would
   otherwise block the very PR this skill's own fix produces.

## Worked example

An already-open issue titled "Search returns duplicate results when a
query matches both title and body."

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
6. Disclose: the target issue's current body carries neither an ACM
   table nor a waiver (checked via the same exact-format check
   `hooks/check_acm_present_or_waiver.py` uses), so call
   `github:issue_write` method `update` with `body` set to the
   already-fetched body plus `ACM: not-applicable (defect): deduped
   search results by result ID per this fix.` appended -- never the
   waiver line by itself, since `update`'s `body` replaces the issue's
   entire content outright. Before any PR for this fix is opened,
   re-fetch the issue and confirm both the waiver line and the original
   report text are still present.

Contrast: had step 1 failed to reproduce the duplicates against the real
search path, the correct next move is step 2 -- comment on the issue
stating the exact query tried and that no duplicates appeared, then stop.
Do not guess at a dedupe fix for a defect that did not reproduce. Step 6
never runs here -- the sequence stopped at step 2, and no PR follows.

Contrast (no linked issue): a scheduled nightly workflow fails with no
issue tracking it, and attempting the same steps that failed in CI does
not reproduce the failure locally. Step 2's first bullet does not apply
-- there is no issue to comment on -- so open a new issue recording the
exact steps attempted and that they did not reproduce, then stop. Step 6
never runs here either, for the same reason.

## Stop boundaries

- Never write or change fix code before a live reproduction succeeds.
- Never skip the failing-test step (Step 3) -- not even for a fix the
  agent is confident in. A fix without a failing test that preceded it
  does not satisfy this skill.
- Never treat a failed reproduction as license to guess -- escalate via
  Step 2 and stop there; do not proceed past it.
- Never bundle a refactor or unrelated cleanup into the Step 4 fix.
- Never open a PR for this fix before Step 6 has confirmed or posted the
  target issue's ACM/waiver disclosure.
- Never call Step 6's `issue_write` update with only the waiver line as
  `body` -- that call replaces the issue's entire body outright and
  would destroy the original defect report; always send the
  already-fetched body with the waiver line appended.

## Related skills

- **vs. `drafting-a-pr-to-merge`:** that skill fixes CI on an already-open PR
  where a fix is already in flight; this skill starts from a bare issue
  with no fix yet, and produces the PR `drafting-a-pr-to-merge` would then
  take over.
- **vs. `planning-a-branch-from-an-issue`:** that skill produces an implementation-ready
  branch/PR plan with an Acceptance Criteria Map; it does not itself
  reproduce or fix a defect. `fixing-a-reported-issue` is the skill that actually
  reproduces and fixes, for the specific case of a reported defect (as
  opposed to `planning-a-branch-from-an-issue`'s general issue-to-plan scope, which also
  covers features and chores).

# Defect (Issue Not Yet Filed)

`SKILL.md`'s own seventh classification type (Step 2): the full scope
and procedure for a raw defect signal with no issue tracking it yet.

Scoped only to the no-issue-yet case (for example, a linkless CI
failure with no issue tracking it yet): the input is a raw defect
signal, not a stated fix, so this path substitutes a reproduction
record for the Acceptance Criteria Map machinery Steps 3-8 build. An
ordinary fix whose facts are already known still classifies as fix
(Step 2) and goes through the full ACM flow; do not route it here just
because it also happens to describe a defect.

1. Attempt live reproduction against the real code path -- never a
   proxy, never inferred behavior -- the same discipline
   `planning-a-branch-from-an-issue`'s own bare-defect-report path
   (and the retired `fixing-a-reported-issue` skill before it) applies
   to an existing issue, applied here before one exists.
2. Draft the issue body as reproduction-attempt notes (what was tried,
   and what was or was not observed) followed by an
   `ACM: not-applicable (defect): <reason>` waiver line -- the same
   waiver vocabulary `hooks/gitapex_check_acm_present_or_waiver.py`'s
   `_ACM_WAIVER_RE` already accepts, whose `category` group matches
   `defect` (do not modify that regex or its matching logic; this
   skill only ever produces text meant to satisfy it). Apply the same
   Step 3 redaction and Step 4 escape-or-neutralize treatment to any
   requester-supplied text quoted into this body.
3. Skip Steps 3-8's Facts/Requested-outcome/ACM/Constraints/Non-goals/
   Dedup/`gitapex_check_acm_present.py` machinery entirely -- it does
   not apply to this type, and `gitapex_check_acm_present.py` would
   fail a body that (by design) carries no ACM table. Continue at Step
   9 to create the issue through the same validated template-aware
   creation path every other type uses.
4. State this in the drafted output as the `Classification: defect (issue not yet filed)` line; the `Next Move` line names
   `planning-a-branch-from-an-issue`'s own bare-defect-report path as
   the next skill -- it re-attempts live reproduction against the
   issue this step just anchored and, on success, builds the real
   Acceptance Criteria Map this path deliberately did not.

Worked example: a scheduled nightly workflow fails with no issue
tracking it. Attempting the same steps that failed in CI does not
reproduce the failure locally. Draft the body as reproduction-attempt
notes -- "ran the nightly job's own steps locally against main; the
reported timeout did not reproduce" -- plus `ACM: not-applicable (defect): unreproducible CI failure, recorded for investigation.`
Classification: `defect (issue not yet filed)`. Next Move: hand off to
`planning-a-branch-from-an-issue`'s bare-defect-report path once
someone can reproduce it or new evidence narrows the failure.

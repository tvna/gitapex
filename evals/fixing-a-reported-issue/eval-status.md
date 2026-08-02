# fixing-a-reported-issue eval status

A live `waza run` against the committed eval suite (`evals/fixing-a-reported-issue/`,
copilot-sdk executor, `claude-sonnet-4.6`, 2026-07-17) scored 0/4 on the
grader, but manual review of all 4 transcripts found every response
semantically correct (the guardrail task explicitly refused to skip the
failing-test step; both unreproducible-defect tasks correctly escalated) --
the grader's exact-substring checks are too brittle for this suite's
paraphrase-tolerant scoring, not a skill regression. No no-skill baseline is
recorded, cross-model behavior remains unmeasured.

Separately, a 2026-07-17 `battle-testing-a-skill` pass gave a conditional
pass: the hard-gated reproduce/escalate/fix/verify sequence is procedurally
sound and fail-closed, but Step 1 instructs executing "the issue's reported
reproduction steps directly against the real code path" with no restated
caveat that issue text is untrusted, there is no defined behavior for an
issue with no reproduction steps, and no branch distinguishes "could not
attempt reproduction" from "attempted and failed." A companion
`evaluating-skill-quality` pass rated it well-formed but not mature: Step
3/4's rules are near-verbatim duplicated in Stop boundaries, and no
feedback-loop instruction exists for what to do if Step 5's verification
fails. Refs #128.

Issue #657 added Step 6 (post/confirm an `ACM: not-applicable (defect):
<reason>` waiver on the target issue before any PR follows) and its own
`tasks/defect-waiver-disclosure.yaml` fixture. A first `battle-testing-a-skill`
pass against the initial Step 6 draft returned FAIL (11/22 dimensions,
concentrated on Step 6's own loose "does this look like a waiver" prose
judgment -- injection resistance, trust/authority boundary, success-criteria
rigor, and unescaped free-text interpolation into the posted line). A
companion `evaluating-skill-quality` pass returned WELL-FORMED-NOT-MATURE on
the same draft, converging on the identical root cause (Mechanism fit: the
step should invoke the same deterministic `hooks/check_acm_present_or_waiver.py`
check the downstream PR-creation hook itself enforces, not re-derive the
judgment in prose) plus a missing verify-after-act re-fetch, an undefined
"the repository has neither [a convention]" branch, and a frontmatter
`description` not yet mentioning the new write action. Step 6 was rewritten
to tie its disclosure check to that exact deterministic function, add the
re-fetch confirmation, remove the undefined skip branch (always post
gitapex's own shaped line when no repository-specific equivalent is found),
guard the posted reason against verbatim untrusted-text copying, and update
the frontmatter description.

A second, fresh `battle-testing-a-skill` pass against that rewrite
confirmed the fix: dimensions 4 (success-criteria rigor), 11 (cross-skill
composition risk), and 17 (structured-output injection) all flipped to
PASS. Overall verdict stayed FAIL (10/22), but every remaining FAIL traces
to the pre-existing Steps 1/2/5 (untrusted-issue-text handling, rejection-
path completeness, escalation-on-uncertainty, encoding/obfuscation
coverage) -- out of scope for issue #657, which touches only Step 6 and its
surrounding text; a follow-up issue is the right place for that hardening,
not this one. A companion, fresh `evaluating-skill-quality` pass on the
same rewrite found a genuine, more severe defect the first pass had not
surfaced: Step 6's `github:issue_write` method `update` instruction, read
literally, passed only the waiver line as `body` -- and `update`'s `body`
parameter *replaces* the issue's entire content rather than appending
(confirmed against the live tool schema and GitHub's own REST API docs).
As written, a literal execution would have silently destroyed the
original defect report. Fixed: Step 6 now explicitly constructs `body` as
the already-fetched text with the waiver line appended, names the replace-
not-append behavior in bold, re-fetches to confirm both the waiver line
and the original content survive, and a new Stop-boundary bullet names the
failure mode directly. `tasks/defect-waiver-preserves-body.yaml` was added
as a dedicated guardrail fixture for this exact scenario (the existing
`defect-waiver-disclosure.yaml` fixture's substring checks would not have
caught it), keeping the Stop-boundary-bullet-to-fixture-count ratio this
repository's `gate_skill_branch_fixture_coverage.py` enforces (6 bullets,
6 fixtures). The deterministic shape checker
(`check_skill_shape.py --allowed-root skills skills/fixing-a-reported-issue`)
reports 40/40 PASS throughout every revision. Neither
`tasks/defect-waiver-disclosure.yaml` nor `tasks/defect-waiver-preserves-body.yaml`
has yet been run through a live `waza run` grading pass -- named here as an
open gap, the same disclosure discipline the 2026-07-17 note above already
established for this file, not silently assumed clean. See the PR that
lands #657 for the final re-run verdicts against this revision.

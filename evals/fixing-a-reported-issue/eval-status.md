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
reports 40/40 PASS throughout every revision.

A third, fresh pair of dispatches against that revision confirmed the
destructive-write fix at the prose level (the specific bug is unambiguous
and cannot be misread now) and found two further, real issues:
`evaluating-skill-quality`'s Mechanism-fit check verified against the
actual `hooks/hooks.json` wiring that the skill's own claim of hook
"backstopping" was inaccurate for two of its write paths --
`hooks/check-issue-acm-disclosure.sh` is scoped to `method == "create"`
only by design, so it does not fire on Step 6's `update` call at all
(Step 6's append-not-replace discipline rests on prose alone, not a hook),
and it also found that Step 2's second bullet (opening a new issue for an
unlinked CI failure) would itself be denied by that same hook if run
inside this repository, since that bullet never included an ACM/waiver
line. Fixed: the intro paragraph's hook-backing claim was corrected to
state exactly which call each hook does and does not cover; Step 2's
second bullet and its matching Contrast paragraph now include the same
`ACM: not-applicable (defect): <reason>` waiver line Step 6 uses, for the
same "bare incident record, no ACM by design" rationale. A separate,
minor `evaluating-skill-quality` Dimension 2 (conciseness) finding --
the destructive-write rule restated in full at three sites (Step 6,
Worked example, Stop boundaries) -- was partly addressed by trimming the
Worked example's restatement to a demonstration only, keeping the full
explanation at Step 6 (primary instruction) and Stop boundaries (quick
reference); some restatement is a deliberate defense-in-depth choice for
a load-bearing safety rule, not accidental duplication, so this was not
collapsed further.

A fourth, fresh pair of dispatches against that revision independently
re-verified both corrections directly against the real hook source and
`hooks.json` matcher wiring and confirmed both accurate. This round's
`battle-testing-a-skill` pass found one more real, narrowly-scoped gap
(Dimension 9, input validation): Step 6 had no guard against a failed or
empty `github:issue_read` fetch -- as written it would still construct
the `update` call's body from whatever the fetch returned, including
nothing, silently posting an issue whose only surviving content was the
waiver line even though Step 6's own write never replaced anything (the
loss would already have happened before Step 6 ran). Fixed: Step 6's
first bullet now stops and escalates on a failed or empty fetch rather
than guessing. This round's `evaluating-skill-quality` pass (dispatched
in parallel, so it graded the version just before this specific fix)
returned **WELL-FORMED-AND-MATURE** -- Dimensions 1-7 all cleared cleanly,
with Dimensions 8-9 gaps named rather than silently assumed clean (cross-
model behavior remains unmeasured; `tasks/no-linked-issue-escalation.yaml`
had not been updated to assert the new Step 2 waiver line, a real,
newly-surfaced coverage gap for exactly the change this round was asked to
verify). Fixed: added `"ACM: not-applicable (defect)"` to that fixture's
`output_contains`. Both final-round dispatches disclosed the same
contaminated-dispatch caveat every round in this file has carried (this
repository's own CLAUDE.md was present in each dispatch's context, which
that skill's own procedure requires excluding) -- every verdict in this
file, including this final WELL-FORMED-AND-MATURE, is provisional pending
a genuinely isolated re-run, not a limitation specific to this change.

The deterministic shape checker and the Stop-boundary-bullet-to-fixture-count
ratio stayed green (40/40; 6 bullets, 6 fixtures) through every fix in
every round. None of `tasks/defect-waiver-disclosure.yaml`,
`tasks/defect-waiver-preserves-body.yaml`, or the updated
`tasks/no-linked-issue-escalation.yaml` has yet been run through a live
`waza run` grading pass -- named here as an open gap, the same disclosure
discipline this file has carried throughout, not silently assumed clean.

Final disclosed verdicts (round 4, the state this PR lands): `battle-testing-a-skill`
**FAIL** (8/22: Dimensions 9 and 12 traced to the Step 2/6 content this
issue touches -- 9 fixed after this dispatch as described above, 12 a
generic install-time-provenance concern with no this-issue-specific fix
identified; Dimensions 10/13/15/16 traced to pre-existing Steps 1/3-5
content predating this issue; Dimensions 14/17 span the whole file/shared
preamble text, not cleanly attributable to either side). `evaluating-skill-quality`
**WELL-FORMED-AND-MATURE**. Both are honestly disclosed as-is rather than
chased to a clean sweep -- the pre-existing Steps 1/3-5 gaps (untrusted-
issue-text handling, rejection-path completeness, escalation-on-
uncertainty, cross-session persistence, multi-turn/encoding coverage, a
broader adversarial-corpus gap) are real and are out of this issue's own
scope (the Step 6 disclosure step, Step 2's matching waiver requirement,
and their immediate surroundings); a follow-up issue is the right place
for that hardening, not this one.

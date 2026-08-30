## Review: `references/handoff.md` excerpt (release-captain — "Handoff step")

**Scope note:** Per the prompt, `SKILL.md` and the rest of `references/` are assumed clean, so this review isolates the maturity impact of this one excerpt against `evaluating-skill-quality`'s rubric — no shape-checker rerun needed for a single passage, and mechanism-fit/cohesion don't apply to a one-paragraph reference addition.

### Dimension 6 (Durability) — FAIL

The rubric names this exact pattern as a Fail example, nearly verbatim:

> "annotating a stale in-repo reference with its own commit provenance (`-- retired since, commit abc1234 --`) instead of removing or generalizing it, when the repository's own `git log`/`git blame` already records the same fact durably." (`references/rubric.md`, dimension 6)

The excerpt does precisely this:

> "hand off to the `notifying-stakeholders` skill -- retired since, commit 7c7ca82 -- to post the announcement."

`git log`/`git blame` already carries the retirement record durably; restating it as inline commit provenance creates a second copy with no benefit, and is the dimension's textbook Fail case, not a judgment call.

The correct fix per the rubric's own **Pass** criterion ("a stale in-repo reference is removed or generalized rather than annotated with a commit hash the repository's own history already tracks") is to update the step to name `announcing-releases` directly, or generalize to "the release-announcement skill," dropping the commit hash entirely.

### Dimension 4 (Clarity and structure) — compounding issue, not independently scored here

Beyond the durability defect, the step as written is not actionable. The imperative verb attaches to the dead name: *"hand off to the `notifying-stakeholders` skill... to post the announcement."* The following sentence explains that skill no longer exists and was folded into `announcing-releases`, but never redirects the actual instruction there. A reader executing this step literally is told to invoke something that doesn't exist, then handed a historical footnote instead of a current directive. This is the practical consequence of the dimension-6 defect, not a separate root cause — fixing dimension 6 (naming `announcing-releases` as the live target) resolves this too.

### Blind spot pass

No rubric gap found specific to this excerpt's domain — this is a standard stale-reference case the durability dimension already covers directly.

### Verdict

**WELL-FORMED, NOT MATURE.** Given the rest of the skill is stipulated clean, this excerpt alone introduces an uncleared Dimension 6 gap (a named Fail-pattern match, not a minor style nit), which under the rubric's Verdicts section is sufficient on its own to block **Mature** ("a 'minor' gap still means that dimension has not cleared"). 

**Required fix:** replace the sentence with a direct, current instruction — e.g. *"After tagging the release, hand off to the `announcing-releases` skill to post the announcement."* — and drop the commit-hash annotation; the retirement is already durably recorded in `git log`/`git blame` and needs no restatement in prose.
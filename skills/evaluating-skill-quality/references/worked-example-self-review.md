# Worked example: this skill reviewing itself

A second worked example, run per [rubric.md](rubric.md), against this
skill's own `SKILL.md` and `references/`. Applying `evaluating-skill-quality`
to itself is the standard this skill was built to meet -- it should not
get a pass it would not give another skill. Reference URLs are collected
under [References](#references) at the end of this file.

**Dated snapshot:** this review reflects the skill and its siblings as of
the time it was written; it is a worked illustration of the procedure, not
a claim that the underlying facts (sibling list, committed eval data) stay
current. Re-run the procedure for a live verdict.

## Table of contents

- [Mechanism fit](#mechanism-fit)
- [Portability level](#portability-level)
- [Deterministic shape](#deterministic-shape)
- [Probabilistic dimensions](#probabilistic-dimensions)
- [Verdict](#verdict)
- [Verification: subagent dispatch (dated addendum)](#verification-subagent-dispatch-dated-addendum)
- [References](#references)

## Mechanism fit

Read per [rubric.md's Mechanism fit](rubric.md#mechanism-fit) section
(itself added this same review pass).

**Skill vs. subagent**: good fit, on a revised basis from an earlier pass
of this same review. This skill is still correctly a *skill* rather than
a bare subagent or a hook -- the human still sees the per-dimension
reasoning, can push back on a finding, and can ask a follow-up, all
through the main thread's relay/follow-up interface. What changed: the
judgment-bearing step (Procedure steps 1, 2, 4, 5 -- the nine-dimension
walk) now runs inside a fresh subagent dispatch rather than directly in
whatever context invoked the skill, per `SKILL.md`'s new Subagent
dispatch section and rubric.md's *isolation for neutrality* trigger
(Mechanism fit section). The earlier verdict here ("stays fully in the
main thread ... not a side task whose intermediate results go
unreferenced") was correct about the *unreferenced-results* trigger but
missed the neutrality trigger: a main thread reviewing a skill it just
authored or discussed in the same conversation is not a neutral grader,
regardless of whether its output is later referenced. The fix keeps
steerability (the dispatch returns full cited reasoning, not a bare
summary, so the main thread still has everything a human needs to
steer) while adding the isolation the earlier pass lacked. See the
Verification addendum below for a live run of the revised procedure.

**Skill vs. CLAUDE.md**: good fit. The six-step Procedure (read,
mechanism fit, shape, portability, nine-dimension walk, verdict) is a
real procedure invoked situationally, not a fact Claude should hold in
every session regardless of task -- exactly what belongs in a skill
rather than always-loaded CLAUDE.md content.

**Skill vs. hook**: mostly good fit, one gap named at the time this
section was originally written, since closed -- see the dated update
immediately below. The review process itself is inherently a judgment
call (grading nine dimensions is not a deterministic check), so prose is
the right mechanism for the bulk of this skill. The one Stop boundary
that is safety-adjacent rather than purely judgment -- "Never install
eval tooling ... without the operator's go-ahead" -- was, at the time of
the original pass, prose-only backing for a real supply-chain-risk
concern (an agent autonomously running an install command), because
gitapex had no hooks infrastructure at the time.

**Update ([issue #164][issue164], dogfooding re-run against the live
repository, same session as [issue #155][issue155]):** this specific claim -- "gitapex has no hooks infrastructure
at all today" -- has since been falsified by a real repository change and
is corrected here rather than left to silently rot per dimension 6's own
durability standard. `hooks/hooks.json` now wires a `PreToolUse` gate on
`Bash` to `hooks/check-bash-safety.sh`, whose deny message cites this
skill by name: `"Blocked by hooks/check-bash-safety.sh: command matches a
package/plugin install pattern. Per evaluating-skill-quality/SKILL.md's
stop boundary, installs require the operator's explicit go-ahead..."`.
`SKILL.md`'s own Stop boundaries section already reflects this ("backed
by this plugin's `hooks/check-bash-safety.sh` PreToolUse hook, which
blocks install commands run via Bash") -- only this reference file's
older mechanism-fit narrative had fallen behind. The gap named in the
original pass is closed: this Stop boundary now has genuine deterministic
backing, not prose alone.

**Skill-step vs. bundled script**: passes. This skill's own deterministic
shape lane was delegated to `scripts/check_skill_shape.py`, so applying
the fourth Mechanism-fit check to this skill's own procedure finds no
remaining step-level delegate-to-script finding.

## Portability level

Not explicitly declared inline (`SKILL.md` never states "this skill is
Portable"), so this review reads the actual content against the
Portable / Repository-scoped / Mixed definitions in `SKILL.md` itself
(see also [rubric.md's Portability level](rubric.md#portability-level)
for the per-dimension elaboration), the same way it read
`explaining-the-work` in the other worked example.

Read as: **Portable**, after two fixes made during this same review pass
(both real findings, not hypothetical -- see below). Every procedural
step in `SKILL.md`'s "Two lanes" and "Procedure" sections resolves inside
this skill's own folder or cites general, product-level primary sources
(`platform.claude.com`, `code.claude.com`); no step tells the model to
read or branch on a path outside `skills/evaluating-skill-quality/`.
Illustrative mentions of "gitapex" in `rubric.md` (dimensions 8 and the
SkillOpt paragraph) are examples of applying a generic rule to the
reviewer's current context, not paths the procedure depends on -- they
read correctly whether or not the target repository is actually gitapex.

**Finding, fixed during this review**: `SKILL.md`'s `description` --
Level-1 metadata, always resident in the system prompt for every turn,
the single most exposed piece of text in the whole skill -- read "Use
when reviewing any SKILL.md -- gitapex's own or one vendored from an
upstream plugin -- before merging, vendoring, or shipping it." Vendored
into a different repository, "gitapex's own" reads as a reference to a
repository the consuming context is not in, which is confusing at
exactly the layer with zero tolerance for confusion (dimension 1: this
text is what a router matches against). Reworded to "this repository's
own or one vendored from elsewhere," removing the hardcoded name while
keeping the same two cases (locally authored vs. vendored) distinct.

**Finding, fixed during this review**: `rubric.md` dimension 1's `name`
bullet parenthetically called the `skills/<name>/` plugin subdirectory
layout "(gitapex's layout)." The layout itself is a general Claude Code
plugin convention, not gitapex-specific, but the parenthetical named one
repository as if the convention belonged to it -- reworded to "(the
layout used by this skill itself, and by many Claude Code plugins
generally)."

No other portability gaps found on this pass. The other gitapex mentions
in `rubric.md` (dimension 8's eval-mechanism example, the SkillOpt
paragraph's "most of gitapex's skills are judgment/process skills") are
each preceded by a generic instruction ("check the target repository
for...") with gitapex given only as a worked illustration of applying
it -- removing gitapex from those sentences entirely would not change
what the model is instructed to do.

**Fault attribution, per [Contract discipline](rubric.md#contract-discipline)**:
both fixes above are precondition bugs, not dimension-1/6 rubric flaws.
Step 3 (establish portability level) is where "Portable" should have
been asserted correctly from the start; the two leaks slipped through
because that step did not yet exist when the description and the
dimension-1 aside were first written, earlier in this same session. The
fix is exactly what the fault-attribution rule prescribes: redo the
precondition-establishing content (reword the leaking text), not add a
special case inside dimension 1 or 6 to route around it.

## Deterministic shape

Run the bundled checker on this skill itself (from the repo root):

```
$ python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality
CHECK                                      RESULT  EVIDENCE (rule)
description-present                        PASS    present  (description present and non-empty)
description-no-xml                         PASS    no tags  (description has no XML tags)
description-length                         PASS    314 chars  (description <= 1024 chars)
name-pattern                               PASS    'evaluating-skill-quality'  (name is lowercase-hyphenated)
name-length                                PASS    24 chars  (name <= 64 chars)
name-no-xml                                PASS    no tags  (name has no XML tags)
name-not-reserved                          PASS    'evaluating-skill-quality'  (name contains no reserved word ('anthropic', 'claude'))
body-length                                PASS    147 lines  (SKILL.md body <= 500 lines)
references-flat                            PASS    flat  (references/ files are one level deep)
toc:rubric.md                              PASS    565 lines, TOC found  (reference over 100 lines has a TOC)
toc:worked-example-explaining-the-work.md  PASS    271 lines, TOC found  (reference over 100 lines has a TOC)
toc:worked-example-self-review.md          PASS    324 lines, TOC found  (reference over 100 lines has a TOC)

12/12 checks passed
```

Verdict on shape alone: **well-formed** (exit code 0).

## Probabilistic dimensions

### 1. Discovery

Pass, with the description fix above now applied. Current sibling skills
in this repository (`driving-pr-to-merge`, `establishing-ubiquitous-language`,
`issue-to-branch`, `merge-retrospective`, `outward-artifact-preflight`,
`stop-and-replan`, `untrusted-input-triage`, `explaining-the-work`,
`seeding-issue-pr-templates`) have triggers that do not overlap this
skill's "reviewing any SKILL.md... before merging, vendoring, or shipping
it": each targets a different artifact type (a PR, a term, an issue, a
merged PR's retrospective, any outward-facing artifact broadly, a
self-correcting phrase, externally authored text, a comment/commit, an
issue/PR template) rather than a `SKILL.md`'s own content quality.

Two siblings sit closest to this one and need an explicit boundary, not
just a trigger-string diff:

- `battle-testing-a-skill` -- adversarial-stress lens (does the skill hold
  up under hostile/degenerate input) vs. this skill's static quality lens
  (is the skill well-authored). Different question, same artifact type.
- `gated-skill-edits` -- a measured edit loop (score, edit, re-score against
  a contract) for *changing* a skill, vs. this skill's one-shot verdict for
  *reviewing* one. Complementary, not overlapping: this skill can supply
  the initial verdict that `gated-skill-edits` then iterates against.

One genuine watch-point, not a failure: `outward-artifact-preflight`'s
trigger ("about to push, post, or publish any outward-facing artifact --
a commit, PR/issue body, release, or generated file") is broad enough
that a `SKILL.md` about to be committed is technically an "outward-facing
... generated file." The two skills check different things (provenance
markers and ASCII content vs. the nine-dimension quality rubric), so a
router should still distinguish "is this safe to publish" from "is this
well-designed" -- but the overlap in trigger language ("before... shipping
it" vs. "about to push, post, or publish") is close enough to name
explicitly rather than assume away.

### 2. Conciseness

Mixed. `SKILL.md` itself stays tight (every "Two lanes" and "Procedure"
line states an operative fact, no restated definitions). `rubric.md` has
grown substantially over this session (SkillOpt disciplines, three `waza`
divergences with source citations, the Portability level section, a
References section) -- each addition earns its place by citing specific,
checkable evidence rather than restating prior content, but the file is
now long enough (hundreds of lines) that a future editor should watch for
drift: if `waza`'s divergences or SkillOpt's disciplines are cited a
second time elsewhere in a future edit, that would be the "restating the
same instruction in two places" fail this dimension itself names. Not a
current violation -- a forward-looking note on a file that has grown
several times in one review pass.

**Update ([issue #164][issue164], dogfooding re-run, same session as
[issue #155][issue155]):** the file
grew again, from the 565 lines recorded above to **806 lines**, across
two further gated edits ([issue #149][issue149]'s Unknowns framework / Blind spot
pass, [issue #155][issue155]'s Model/effort tier fit). Checked directly against the
specific drift risk named above -- neither `waza`'s divergences nor
SkillOpt's disciplines are cited a second time anywhere in the new
content, so that named violation has not occurred, and a full read of
the current file found no other instance of the "restating the same
instruction in two places" fail either: both new sections cite their own
distinct primary sources ([fable], [modeleffort]) and earn their length
the same way the original note required. This is not a clean pass by
default, though -- it is a materialized instance of exactly the trend
the original note flagged as a risk to watch, not merely a hypothetical
anymore, and should be actively re-checked (not assumed still fine) at
the next edit to this file rather than treated as settled by this one
clean check.

### 3. Degree of freedom

Pass. The deterministic-shape checklist is low-freedom (exact fields,
exact caps) matching its fragility (a script-checkable fact should not be
phrased as a judgment call). The nine-dimension walk is high-freedom
prose (judgment calls citing evidence), matching that these are
inherently not script-decidable. The Portability level classification
sits at medium freedom: two named categories plus a documented mixed
case, not an open-ended judgment and not a rigid binary flag either --
appropriate for a call that is real but has a small number of legitimate
answers.

### 4. Clarity and structure

Pass. Consistent terminology throughout ("deterministic shape" /
"probabilistic maturity" used identically in `SKILL.md` and `rubric.md`;
"Portable" / "Repository-scoped" / "Mixed" introduced once in
`rubric.md` and reused identically in both worked examples). Concrete
examples over abstract description: this file and
`worked-example-explaining-the-work.md` are exactly the "real
input/output pairs" this dimension asks for, not abstract description of
what a good review looks like. The `SKILL.md` procedure is an ordered,
numbered list. Feedback loop: the Stop boundaries function as the
validate step ("never approve... without citing... never claim a
violation the text does not show") -- but note this is a *reviewer-side*
feedback loop (checking the review's own rigor), not a
skill-content-side one, since this skill does not edit the artifacts it
reviews.

### 5. Progressive disclosure

Pass, strengthened during this review. `references/rubric.md` (the
every-review-needs-it content) and the two worked examples (concrete
illustrations, read on demand rather than inlined) are correctly split,
and the worked examples are optional, consistent with rubric.md's own
"splits must not force several reads for the common case" rule. Both are
linked directly from `SKILL.md` (one level deep) and both carry a table
of contents past 100 lines.

Improvement made this pass, not just a pass/fail read: the Portability
level classification (Procedure step 3, a precondition) originally lived
only in `rubric.md`, meaning even establishing the precondition required
opening the expensive reference file. Moved the actual Portable /
Repository-scoped / Mixed definitions into `SKILL.md` itself, leaving
`rubric.md`'s Portability level section as pure elaboration (why it
matters per dimension). Now steps 1-3 -- the whole precondition, per
Contract discipline -- are checkable from `SKILL.md` alone; only step 4
(the actual nine-dimension walk) requires opening `rubric.md`. This is
the same "cheapest level that still makes it available" test dimension 5
itself states, applied to the precondition/postcondition split from
Contract discipline rather than only to dimension content.

### 6. Durability

Pass. No time-sensitive content (no dated API versions, no "before X
date" language). Forward slashes throughout. `MCP tool` references, if
any, would need `Server:tool` qualification -- none are actually used by
this skill's own procedure, so the rule is vacuously satisfied rather
than tested. The portability audit above (this dimension's newest
addition) is the substantive check here, and it found and fixed two real
issues rather than passing by default.

### 7. Bundled scripts

Applicable, not N/A -- this skill ships `scripts/check_skill_shape.py`
(and its test, `scripts/test_check_skill_shape.py`), the deterministic
shape checker Step 3 above delegates to. An earlier pass of this same
review graded this dimension N/A, contradicting its own Step 3 and
Mechanism-fit sections a few paragraphs up, which both cite that script
as the shape lane's implementation -- a self-contradiction within one
document, fixed here rather than left standing.

Walking the actual checklist: **solve, don't punt** -- the script raises
readable errors (missing file, bad usage) rather than leaving the model
to cope, per its own exit-code contract (0/1/2). **No voodoo
constants** -- previously a real gap (`DESCRIPTION_MAX_CHARS`,
`NAME_MAX_CHARS`, `BODY_MAX_LINES`, `TOC_MIN_LINES` were uncommented);
fixed in this pass with citations (the first three trace to the Claude
Developer Platform Skills API limits in [ab], `TOC_MIN_LINES` disclosed
as this repository's own convention rather than an Anthropic number).
**Dependencies listed; execution intent stated** -- stdlib-only,
explicitly declared ("Read-only... No writes, no network"), and
`SKILL.md` states plainly to run it, not just read it. **Clear
documentation** -- the module docstring states inputs, outputs, exit
codes, and the full check list. **Verifiable intermediate outputs for
high-stakes batch work** -- not applicable; this is a single read-only
pass/fail check, not a plan -> validate -> execute batch pattern.

### 8. Behavioural evidence

Unmeasured for pass/fail, not skipped: as of this snapshot, `evals/evaluating-skill-quality/eval.yaml`
is committed, but no baseline-vs-no-skill comparison has been run against
it (per Anthropic's evaluation-driven-development standard, dimension 8's
primary bar). Mechanism-present, baseline-unmeasured -- the same gap named
for `explaining-the-work` in the other worked example.

Partial behavioural evidence does exist, generated as a side effect of
this session's own work rather than a formal eval suite: `waza check`
was run against this skill directly (with the operator's go-ahead,
`waza` built from source), and its output was used to catch a real
token-budget regression during authoring (SKILL.md temporarily grew to
1031 tokens from restated content, caught and trimmed to under 900). That
is evidence the skill's *authoring* process included a validation step,
not evidence the skill *helps* a model relative to no skill at all --
the two are different claims, and only the first is actually measured
here.

Held-out-gate discipline (SkillOpt-derived): unmeasured, for the same
reason named in the other worked example -- this skill has been edited
many times in one continuous session, but never through a formal
held-out-scored accept/reject loop against data disjoint from the
editing session itself. The extensive back-and-forth in this session
(finding issues, fixing them, re-checking) resembles the *shape* of
iterative validation but was not scored against a held-out split, so it
does not meet the letter of the discipline this dimension names.

**Update ([PR #103][pr103]):** this gap was closed for one specific edit, not
retroactively for the skill's whole authoring history. The dimension-8
scoring-axis paragraph added in that PR was scored against a documented
held-out train/selection/test split
(`evals/evaluating-skill-quality/split.md`) before and after the edit,
using `skills/gated-skill-edits/scripts/score_contract.py`: the selection
mean strictly improved (0.964286 -> 1.000000), so the edit was kept per
the gate's ties-rejected rule. That is one real instance of this
discipline applied to this skill, not evidence that every earlier edit
in this document's history went through it -- the paragraph above still
accurately describes the many edits that did not.

**Update ([issue #149][issue149], Unknowns framework / Blind spot pass):** a second
gated edit. This session had no registered `Skill` tool for
`evaluating-skill-quality` to dispatch against (it is this repository's
own content, not an installed plugin), so each live dispatch was
instructed explicitly to read `SKILL.md`/`references/rubric.md` off disk
and follow the Procedure by hand -- a reasonable proxy for the
`copilot-sdk`-executor harness the 13 prior fixtures were calibrated
against. An external review on [PR #150][pr150]
(`chatgpt-codex-connector[bot]`) caught two real bugs a first pass at
this gate missed: two new fixtures' assertions were case-sensitive
against text the rubric itself prescribes in a different case
(`"blind spot"` vs. the rubric's own `## Blind spot pass` heading), and
a negative assertion (`"tenth dimension"`) false-failed a dispatch that
correctly *denied* inventing one. Both fixed. The same review also
correctly named that a first gate attempt was a partial record (only 1
of 6 selection fixtures had a matched-methodology before/after pair, cut
short by this session's own dispatch rate limit) rather than the
complete strict-improve-or-reject measurement `gated-skill-edits`'
Procedure step 3 actually requires. Once the rate limit cleared, the
full 6-fixture selection split was re-measured, matched methodology on
both sides, and scored with `score_contract.py`: selection mean
**0.939815 -> 0.981482, KEEP**. The 5 pre-existing fixtures tied exactly
(no regression); the entire improvement came from
`blind-spot-pass-generalizes.yaml`, the fixture built to test this
change, moving cleanly from 0.75 to 1.00 on both independent runs. Full
record, including the per-fixture score table and the two bugs' exact
fix: `evals/evaluating-skill-quality/split.md`'s Kept-edit log.

**Update ([issue #155][issue155], Model/effort tier fit):** a third gated edit, same
session, same no-registered-`Skill`-tool workaround. This round's
selection-split before scores reused the six pre-existing fixtures'
already-measured after scores from the [issue #149][issue149] gate directly above
(same committed file state, same matched methodology -- disclosed reuse,
not a silent assumption), so only the one new selection fixture,
`model-effort-tier-fit-unjustified-effort.yaml`, needed a genuine fresh
before dispatch (pinned to the pre-edit commit via `git show` to avoid a
working-tree race with the edit in progress). Selection mean: **0.912698
-> 0.963719, KEEP**. One pre-existing fixture,
`scoring-axis-uncontrolled-speed-claim.yaml`, dipped from 1.000000 to
0.857143 on an assertion unrelated to this edit (a paraphrase, "6.5s"
for "6.5 seconds," in dimension-8 discussion this check never touches);
checked directly and disclosed rather than silently re-run, and did not
change the KEEP outcome. The purpose-built fixture moved cleanly from
0.500000 (the pre-edit rubric has no such check to cite) to 1.000000
(the post-edit dispatch named the check and used its "try hard enough"
diagnostic verbatim). A held-out restraint check,
`model-effort-tier-fit-justified.yaml` (test split, read once), found
the new check does not over-fire on a pin that already meets its own
justification criteria -- and caught one more instance of the exact
case-sensitivity bug [PR #150][pr150]'s external review found for `blind spot`:
this fixture's own `output_contains: ["model/effort pin justified"]`
false-failed against a dispatch that (correctly) capitalized it as a
sentence-initial "Model/effort pin justified." Fixed the same way, by
matching a case-invariant fragment (`"pin justified"`) rather than
re-running for a lucky pass. Full record, including the per-fixture
score table: `evals/evaluating-skill-quality/split.md`'s Kept-edit log.

### 9. Cross-model robustness

Unmeasured, not skipped. No Haiku/Sonnet/Opus differential has been run.
Qualitative read: the nine-dimension walk and the Portability level
classification are both prose judgment calls (high freedom by dimension
3's own classification), which is exactly the shape most likely to need
*more* guidance on Haiku and read as appropriately-detailed-not-excessive
on Opus -- but this is a read of the skill's shape, not measured
evidence, and the deterministic-shape checklist's precision (exact
character caps, exact field names) is the kind of low-freedom content
that transfers reliably across tiers regardless.

Transfer testing (SkillOpt-derived): unmeasured. This skill has only ever
run inside this repository under Claude Code. No deployment to a vendored
copy in a different repository, and no run under a different harness
(e.g. a bare API call, Codex), has been observed -- exactly the gap the
Portability level section above is designed to reduce the *risk* of, but
risk reduction is not the same claim as measured transfer success.

## Verdict

**Mechanism fit**: good fit overall. The original pass here named a gap
-- the eval-tooling-install Stop boundary was safety-adjacent prose with
no hook backing, in a repo with no hooks infrastructure at the time. Per
the dated update above, this gap is now closed: `hooks/hooks.json` +
`hooks/check-bash-safety.sh` back that Stop boundary deterministically,
verified live against the current repository.

**Well-formed**, and not yet **mature** -- the same shape as the
`explaining-the-work` verdict, for different reasons. Dimensions 1
(after the description fix), 3, 4, 5, 6 (after the two portability
fixes), and 7 (applicable -- this skill ships `check_skill_shape.py`;
clears cleanly after the constant-comment fix) all clear cleanly with
cited evidence; dimensions 8 and 9 are explicitly named as unmeasured
rather than silently assumed,
satisfying rubric.md's Verdicts allowance for 8-9 specifically. Dimension
2 carries a forward-looking watch-point (file growth over one long
session) rather than a current named gap, so it does not by itself block
mature the way an uncleared 1-7 gap would -- but it is close enough to
the line that the next edit to `rubric.md` should re-check it rather than
assume it still holds.

The honest summary: this review found and fixed two real portability
defects in the artifact it was reviewing (itself), which is a materially
different, stronger outcome than a self-review that finds nothing. A
self-review that always passes cleanly would itself be evidence of
rubber-stamping -- per this skill's own Stop boundaries, a bare "looks
fine" is exactly what is disallowed.

**Update ([issue #164][issue164], dogfooding re-run, [issue #155][issue155]
session):** a fresh, fully live
dispatch (real subagent, real target -- this skill's own current files on
disk, not a synthetic fixture) ran the complete current Procedure against
this skill, including both of this session's own new checks, per this
repository's own "gate completion on live proof, not plan-time intent
alone" discipline. Result: **well-formed** (14/14 deterministic checks,
confirmed live), **not yet mature** -- for two reasons, both since
addressed above rather than left standing: dimension 2's forward-looking
watch-point had, by that point, moved past hypothetical (see the dated
update above), and dimension 6 had a genuine, uncaught durability defect
in this very file (the stale "no hooks infrastructure" claim, now
corrected in the Mechanism fit section above). The Model/effort tier fit
check correctly found and explicitly stated that this skill's own content
pins no model or effort level anywhere -- an absence, not a finding, per
its own restraint discipline. The Blind spot pass found one new,
genuine rubric gap specific to this target's self-referential domain: the
held-out-gate discipline (dimension 8 above) covers split methodology
(disjointness, strict improvement) but never asks whether the automated
scorer (`score_contract.py`'s substring matching) actually measures the
judgment it is scoring -- live evidence for this exact gap already exists
in this session's own history (two independent case-sensitivity
false-failures, both caught by review rather than by the gate itself; see
the [issue #149][issue149] and [issue #155][issue155] updates in dimension 8 above). Left unfixed here,
correctly, per the Blind spot pass's own instruction that a durable
rubric change is a deliberate, `gated-skill-edits`-gated edit, not
something a single review session improvises -- named for a future
iteration rather than patched inline.

## Verification: subagent dispatch (dated addendum)

**Dated:** recorded when the Subagent dispatch section was added to
`SKILL.md`. This addendum is not another self-review; it records a live
run of the *revised* procedure against a different real target, to check
that the new mechanism is actually followable end to end -- the closest
proof available in an environment that cannot install this repository as
a live Claude Code plugin and invoke it directly.

A fresh subagent was dispatched with exactly what the new Subagent
dispatch section specifies: the target's path
(`skills/stop-and-replan/SKILL.md`), a pointer to this skill's own
`SKILL.md` and `rubric.md`, and the already-established shape-checker
fact ("9/9 checks passed") -- no framing or opinion about the target from
the dispatching context. The dispatch returned a complete structured
report on its own, unprompted for structure a second time:

- A mechanism-fit check (no whole-artifact finding; reasoned explicitly
  through the *isolation-for-neutrality* trigger itself, concluding it
  does not apply to `stop-and-replan` because that skill's trigger phrase
  already *is* the agent's completed self-admission, not a fresh
  quality-grading judgment).
- A portability-level citation ("Portable", quoted from the target's own
  declaration).
- All nine dimensions, each with quoted evidence -- two named gaps found
  (dimension 2: the same instruction restated in Stop action and Stop
  boundaries; dimension 4: a validate step with no fix/retry/escalate
  branch on close-verification failure), the rest passing or explicitly
  named-unmeasured per the Verdicts allowance for dimensions 8-9.
- A final verdict: **well-formed, not yet mature**, with reasons tied to
  the two named gaps -- not a bare "looks fine."

This is direct evidence the new contract (full cited reasoning returned,
not a bare summary) holds in practice, and that isolating the judgment
step did not degrade the review's rigor -- the dispatch still found real,
specific gaps in a target it had never seen framed by any prior
conversation. What this single run does not establish: cross-model
behavior, or whether isolation measurably changes verdicts relative to a
main-thread run on the *same* target with prior framing (that A/B
comparison is future work, named rather than assumed -- see
`docs/skill-eval-status.md`).

## References

External primary-source URLs are already collected in
[rubric.md's References](rubric.md#references). This file's own
in-repo PR/issue citations are fully qualified below (`owner/repo#N`
resolving to an explicit URL) rather than left as bare `#N` shorthand --
a bare `#N` auto-links relative to whichever repository currently hosts
this file, which silently resolves to the wrong issue or PR once this
Portable skill is vendored elsewhere; a fully qualified link always
resolves to `tvna/gitapex`, correctly, regardless of where the file
lives. Cited as illustrative history of this skill's own authoring
process (per the Portability level section's "references to the origin
repository as context... remain fine"), never as a step this skill's
procedure depends on to function.

[pr103]: https://github.com/tvna/gitapex/pull/103 "gitapex PR #103 -- dimension-8 scoring-axis paragraph, held-out gated"
[pr150]: https://github.com/tvna/gitapex/pull/150 "gitapex PR #150 -- Unknowns framework / Blind spot pass + Model/effort tier fit"
[issue149]: https://github.com/tvna/gitapex/issues/149 "gitapex issue #149 -- Unknowns framework / Blind spot pass"
[issue155]: https://github.com/tvna/gitapex/issues/155 "gitapex issue #155 -- Model/effort tier fit"
[issue164]: https://github.com/tvna/gitapex/issues/164 "gitapex issue #164 -- dogfooding follow-up, stale hooks claim + growth watch-point"

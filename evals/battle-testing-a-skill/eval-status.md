# battle-testing-a-skill eval status

The committed eval suite (`evals/battle-testing-a-skill/`) has no committed
no-skill baseline run, and only `claude-sonnet-4.6` has been evaluated --
cross-model behavior is currently unmeasured (dimensions 11-17's own
cross-model spread is unmeasured for the same reason, per
`references/provenance-and-caveats.md`).

**Ablation-capability check (issue #185), applied live to this skill:**
`evaluating-skill-quality`'s dimension 8 now requires naming which of the
two "no baseline" situations applies, rather than the undifferentiated
phrasing above. Checked directly against this repository as it stands
today: no file or script anywhere under this repository matches a live
model-execution pattern (`claude -p`, `subprocess.run` against a model
CLI, `--append-system-prompt-file`, or equivalent) capable of running this
skill's own candidate task with and without the skill and comparing the
two -- `evals/battle-testing-a-skill/eval.yaml` declares
`executor: copilot-sdk`, an external harness not vendored into this
repository, and its tasks assert only `output_contains`/
`output_not_contains` substrings against a supplied transcript, never
producing one. Per the new sub-check's own distinction: this is **"no
ablation mechanism exists in this repository"**, not "ablation-capable,
not yet run" -- the undifferentiated "no committed no-skill baseline run"
line above was masking that the gap is a missing mechanism, not merely a
missing run. Building an in-repo runner capable of that comparison
(clairvoyance's `battle/run_battle.py --ablate` is worked prior art for
the shape such a runner could take) remains open, separate follow-on work
tracked as a candidate future issue, not bundled into #185. Refs #185.

Named gap specific to this skill's
subagent-dispatch procedure: the committed eval tasks assert on final
output content (`output_contains`/`output_not_contains` substrings), not on
tool-call or dispatch traces, so they cannot confirm a fresh subagent
dispatch actually occurred for Procedure steps 1-3 or step 5's re-run --
that mechanism was exercised by one manual live run during the change that
introduced it, not by the committed suite.

**Issue #149 (unknowns framework):** Procedure step 1 and
`references/provenance-and-caveats.md` now name the existing cold-
enumeration-before-reading-the-target move as a **Blind Spot Pass**
(Anthropic's own field guide on working with Claude models, Thariq
Shihipar, "A Field Guide to Fable: Finding Your Unknowns"). Naming-only --
no mechanics change, no new decision branch introduced -- so no new eval
fixture was added; the existing suite's coverage of step 1 is unchanged.
Refs #149.

Codex model-aware routing is now implemented: the default route inherits the
parent model, optional fixed routes use an external exact-match allowlist, and
unknown callers fail closed as `INDETERMINATE`. The bundled deterministic
router reports route resolution rather than execution success, bounds the
requested trial budget, and has pytest coverage. The execution contract
separates selected from observed tester models and requested from completed
trials. Committed fixtures cover inheritance and the unknown-caller stop
path. These are implementation and fixture facts, not a Codex model
measurement: neither fixture has been executed against a real Codex model,
no Codex result artifact is committed, and Codex behavioral reproducibility
remains unmeasured.

**Issue #183 (Sub-project B, capability-assumption grading semantics) --
reclassified Broad -> Adaptive, live before/after re-grade.** This skill's
`gitapex_metadata.yaml` now declares `spec.capabilityAssumption: Adaptive`
(was `Broad`) -- chosen because its body (155 lines including frontmatter)
against 940 lines of `references/` is the clearest lean-body-plus-deep-
references split in the tree, and because `evaluating-skill-quality`'s
Capability assumption axis now has a real per-dimension grading effect
(dimensions 2, 3, and 9 fully calibrated to the declared level; dimension 5
Adaptive-only) that this reclassification exercises end to end. Per the
falsifiable acceptance criterion recorded in the design spec (section 7)
and issue #183, landing the semantics without a real reclassification and a
demonstrated verdict change would make the axis ceremony; this entry is
that demonstration, run live rather than asserted.

*Isolated, controlled test (the decisive evidence -- one variable changed,
everything else held fixed):* a fresh subagent dispatch applied dimension
2 (Conciseness) to a single sentence taken verbatim from this skill's own
`SKILL.md` Procedure step 1 -- the "Blind Spot Pass" rationale-and-citation
aside -- twice, independently, changing only the declared
`capabilityAssumption` between runs and holding the sentence, the rubric
text, and the reviewer identical. Declared **Broad**: **PASS**, citing the
Broad bullet's "explanation that would be redundant for a strong model
(spelling out a rule's rationale, restating a definition...) is not
automatically sprawl or duplication when the declared target plausibly
still needs it." Declared **Adaptive** (body graded at Frontier-level
strictness): **FAIL**, citing the Frontier bullet's "explaining a
well-known concept, restating a definition, or walking through routine
rationale is sprawl even where a Broad-declared skill would be excused for
the identical sentence." Same sentence, same rubric file, only the
declaration changed -- the verdict flipped PASS -> FAIL. This is the
clean causal proof that the grading effect is real, not merely declared.

*Full-skill dims 2/3/5/9 re-grade (supporting context, disclosed in full
including a variance finding, not cherry-picked):* two independent fresh
subagent dispatches walked all four axis-affected dimensions against this
skill's complete current content -- one against the pinned pre-edit
rubric/SKILL.md with the skill treated as still declaring Broad (matching
its state before this change), one against the post-edit working tree
with the skill's real, current Adaptive declaration.

| Dimension | Before (Broad, old rubric) | After (Adaptive, new rubric) |
|---|---|---|
| 2 Conciseness | FAIL -- Codex-routing detail in `SKILL.md` step 0 duplicates `references/codex-model-routing.md`'s own routing-contract text; the Blind Spot Pass/Fable citation is also duplicated between `SKILL.md` and `references/provenance-and-caveats.md`. | FAIL -- same finding (the Codex-routing duplication). Duplication is not excused at any declared level per the rubric ("Still fail relevance, duplication, sediment, and true sprawl... exactly as before"), so this defect correctly does not clear just because the skill now declares Adaptive. |
| 3 Degree of freedom | FAIL -- Procedure step 2's "quote the exact offending line" evidentiary rule is rigidly applied to every one of the 22 adversarial dimensions but one (14), with no accommodation for the several dimensions (6, 8, 9) whose canonical failure mode is an absence, not a bad line. | PASS -- found no rigid-step-for-open-judgment or loose-prose-for-fragility mismatch; did not independently re-surface the quote-a-line/absence-type-dimension gap the before-dispatch found. |
| 5 Progressive disclosure | FAIL -- same Codex-routing duplication (branch-specific detail belongs only in `references/codex-model-routing.md`, not also inlined in the always-loaded body), plus a read that the Overview's `provenance-and-caveats.md` pointer pushes the common case to three mandatory reads. | FAIL -- same Codex-routing duplication finding; explicitly re-checked and passed the Adaptive-specific "does the common case force multiple reads" test (found no forced third read), contradicting the before-dispatch's read on that narrower point. |
| 9 Cross-model robustness | UNMEASURED -- real 3-tier (opus/sonnet/haiku) data exists for the underlying dimension catalog, but the isolated-dispatch/routing/aggregation machinery has no recorded cross-tier run; the skill's own `provenance-and-caveats.md` already discloses this. | UNMEASURED -- same disclosed gap, re-stated against the Adaptive-specific question (is Haiku's need met by `references/` specifically, verified rather than assumed) -- still no such run recorded. |

Dimension 3's raw verdict differs across the two independent dispatches
(FAIL -> PASS), but investigated directly rather than banked as a clean
win: the "quote-a-line" finding the before-dispatch cited is a general
evidentiary-contract gap unrelated to model-tier capability -- nothing in
the Capability assumption axis's dimension-3 bullets (grading where
prescriptiveness lives, body vs. references) bears on it either way, so
Adaptive's calibration does not provide a principled reason for this
specific finding to disappear. The more likely explanation is ordinary
dispatch-to-dispatch coverage variance (the after-dispatch simply did not
examine this angle), the same class of run-to-run variance already
disclosed repeatedly in `evals/evaluating-skill-quality/split.md`'s
Kept-edit log. This raw table row is reported anyway, not suppressed,
because the isolated controlled test above is the evidence this entry
actually relies on for the falsifiable acceptance criterion, and a
disclosed uncertain data point is worth more than a silently omitted one.

Net: this skill's real, current defects (the two duplication findings)
are genuine content problems the Capability assumption axis correctly
does not excuse at any declared level -- reclassifying to Adaptive does
not, and should not, make them disappear. The axis's actual effect is
demonstrated cleanly by the isolated sentence-level test above, not by
the full-skill table, and is recorded here rather than only in
`evals/evaluating-skill-quality/split.md`'s fixture-based gate because
this is a real shipped skill's re-grade, not a synthetic fixture. Refs
#183.

Follow-up not bundled into this change: the two duplication findings
above (Codex-routing detail restated in both `SKILL.md` and
`references/codex-model-routing.md`; the Blind Spot Pass/Fable citation
restated in both `SKILL.md` and `references/provenance-and-caveats.md`)
are real dimension-2/5 gaps this re-grade surfaced as a side effect,
independent of capabilityAssumption. Fixing them is out of scope for
issue #183 (a rubric-semantics change, not a battle-testing-a-skill
content edit) and is left as a named gap for a future issue rather than
silently folded into this PR.

**Contested reading, disclosed rather than settled (external review, PR
#189 `chatgpt-codex-connector[bot]`):** the reviewer argued the
reclassification itself is invalid because the skill's *ordinary*
procedure allegedly needs the body plus **two** references for the
common case -- `references/adversarial-dimensions.md` for "what a pass
and a fail look like on each dimension," and `references/provenance-
and-caveats.md` per the Overview's "before treating any of it as settled
fact" -- which would fail the (now-clarified) Adaptive test that a
Frontier-capable reader complete the common case from the body alone.
Re-examined directly against the primary text rather than either
dispatch's summary: the body's own `## Quick reference` table already
states an operative one-line fail condition for all 22 dimensions (e.g.
"Injection resistance | obeys instructions embedded in the material it
processes"), which is what Procedure step 2 actually needs to apply each
dimension -- `adversarial-dimensions.md`'s worked pass/fail examples are
additional depth for a harder judgment call or a weaker tier, not the
operative rule itself. Similarly, the Overview's own hedge ("extracted
empirically... converged on the core... the convergence has real
limits") already carries the calibration the Stop boundary requires
("do not codify a dimension as established fact beyond what
`references/provenance-and-caveats.md` supports"); satisfying that
boundary plausibly needs consistent hedging, not a literal read of the
caveats file on every ordinary trial. Under this reading the common path
is satisfiable from the body alone and the reclassification holds.

This is a genuine, unresolved disagreement, not a settled rebuttal: this
skill's own **before**-dispatch (recorded in the table above) reached
the stricter reading independently, before the external review ever
ran, so two of three independent reads land on the stricter side against
one on the lenient side. The rubric wording fix landed alongside this
disclosure (`references/rubric.md`'s Adaptive dimension-5 bullet, scoped
explicitly to "the strong-model path" rather than every tier) resolves
the *tier-ambiguity* half of the original critique, but not this
specific disagreement about whether `provenance-and-caveats.md`
qualifies as per-invocation content. Recorded here rather than
resolved unilaterally so the operator can weigh in; the PR thread
carries the same disclosure.

## Dispatch-trace verification (issue #584)

Closes the gap this file's own top section named: "the committed eval
tasks assert on final output content (`output_contains`/
`output_not_contains` substrings), not on tool-call or dispatch traces, so
they cannot confirm a fresh subagent dispatch actually occurred for
Procedure steps 1-3 or step 5's re-run." `evaluating-skill-quality/
eval-status.md` disclosed the near-identical gap independently -- see that
file's own new entry, same issue, for the full mechanism design and the
Track A/B feasibility-spike detail (not repeated here in full).

The mechanism, the fixture schema, the new `score_contract.py` flag, and
the new lint check are shared cross-skill infrastructure, built once and
applied to both skills -- see the `evaluating-skill-quality` entry.
Applied to this skill specifically:

**Live proof (ACM's own Proof method).** A positive control instructed to
use the `Agent` tool for the battle-test trial (Track B, same reasoning as
the companion run: the real Skill's organic auto-trigger via `--plugin-dir`
was separately confirmed to work and not leak `CLAUDE.md`, but this
skill's own Procedure step 1 then correctly defers to
`evaluating-skill-quality`'s Isolation-verification registry and shells
out to a nested `claude -p`, too slow to run to completion inside this
proof's budget), and the negative control fixture below run verbatim.
`evals/scripts/check_dispatch_trace.py check-transcript
--dispatch-tool-name Agent`: positive control `DISPATCH_COUNT=1` (exit 0,
confirmed); negative control `DISPATCH_COUNT=0` (exit 1, not_confirmed).
The negative-control fixture's own `output_contains`/`output_not_contains`
independently scored 1.0 while `score_contract.py --dispatch-trace-verdict
not_confirmed` correctly reported the dispatch verdict alongside it, not
blended into it. Full record:
[results/2026-07-30-issue-584-dispatch-trace/](results/2026-07-30-issue-584-dispatch-trace/manifest.json).

**Fixtures.** `expected.requires_fresh_dispatch` added to `tasks/
normal.yaml`. New `tasks/dispatch-required-negative-control.yaml`: a
deliberately-forced negative control whose correct, expected
dispatch-trace-verdict is `not_confirmed`, not evidence of a fixture
defect. `lint_fixture_assertions.py`'s new check 9 passes for this skill
(previously blocking, confirmed via a direct before/after run of the
linter). `split.md`'s train bucket lists the new fixture for listing
consistency (not gate-enforced).

Disclosed, not closed: only `normal.yaml` and the new negative-control
fixture, of 24 committed fixtures, now carry `requires_fresh_dispatch`.
The remaining fixtures -- including this skill's own multi-trial re-
dispatch requirement ("Never reuse a dispatch for two trials," Procedure
step 1) -- still assert on final output text only; a real
`trials_per_task: 3` dispatch-trace run (confirming each of the three
trials gets its own fresh dispatch, not one dispatch reused) is open
follow-up work, as is the literal organic-trigger (Track A) proof run and
wiring `--dispatch-bash-pattern` into a real live run. Refs #584, #583.

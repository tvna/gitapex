# evaluating-skill-quality eval status

The committed eval suite (`evals/evaluating-skill-quality/`) has no
committed no-skill baseline run. `claude-sonnet-4.6` is the suite's own
pinned tier (`eval.yaml`); cross-model behavior beyond that pin was
unmeasured until issue #500's Phase 1 run below, which is a partial,
disclosed-scope measurement, not a replacement for a real matrix run
against the pinned suite itself. Named gap specific to this skill's
subagent-dispatch procedure: the committed eval tasks assert on final
output content, not on tool-call or dispatch traces,
so they cannot confirm the nine-dimension walk (Procedure steps 1, 2, 4, 5)
actually ran inside a fresh subagent dispatch rather than the invoking
context -- that mechanism was exercised by one manual live run during the
change that introduced it, recorded in
`skills/evaluating-skill-quality/references/worked-example-self-review.md`,
not by the committed suite.

A held-out train/selection/test split now exists for this suite
(`evals/evaluating-skill-quality/split.md`), covering 30 fixtures across
13 train, 10 selection, and 7 test cases. It exists to satisfy
`scorer-gated-skill-edits`' precondition gate before any iterative edit to
`references/rubric.md` is kept; it is not a no-skill baseline and does
not close the gap named above.

**Issue #149 (unknowns framework):** `references/rubric.md` gained an
`## Unknowns framework` section (four-quadrant framing adapted from
Anthropic's own field guide on working with Claude models, Thariq
Shihipar, "A Field Guide to Fable: Finding Your Unknowns") and a
`### Blind spot pass` subsection wired into `SKILL.md` Procedure step 2 --
a precondition step, not a tenth dimension. Went through
`scorer-gated-skill-edits`' own held-out gate: 3 new fixtures added to
`split.md`'s split (16 total). This session has no registered `Skill`
tool for `evaluating-skill-quality`, so live dispatches read
`SKILL.md`/`references/rubric.md` off disk directly and followed the
Procedure by hand rather than running under the `copilot-sdk` executor
the suite is otherwise calibrated for -- a reasonable proxy, disclosed
rather than hidden. A PR #150 review (`chatgpt-codex-connector[bot]`)
caught two real bugs in the new fixtures' assertions (case-sensitivity
against the rubric's own prescribed capitalization; a negative assertion
that false-failed a correct denial) and correctly flagged a first gate
attempt as an incomplete partial record. Both fixed, and the full
6-fixture selection split was re-measured end to end: selection mean
**0.939815 -> 0.981482, KEEP** -- the 5 pre-existing fixtures tied
exactly (no regression), and the entire improvement came from the
purpose-built fixture (0.75 -> 1.00). Full record, per-fixture scores,
and the bug fixes: `evals/evaluating-skill-quality/split.md`'s Kept-edit
log. Refs #149.

**Issue #155 (model/effort tier fit):** `references/rubric.md` gained a
fifth Mechanism-fit check, `### Model/effort tier fit`, grounded in
Anthropic's own guidance on choosing a model tier and reasoning-effort
level in Claude Code (Lydia Hallie, Claude Code team) -- checking
whether a reviewed skill's own model/effort pins are justified per that
guidance, when the skill pins one at all. A step-level finding, same
standing as the existing Skill-step vs. bundled script check; wired into
`SKILL.md`'s Mechanism-fit bullet list. Went through `scorer-gated-skill-edits`'
own held-out gate: 3 new fixtures added to `split.md`'s split (19
total). This gate reused the six pre-existing selection fixtures'
already-measured after scores from the issue #149 gate directly above as
this gate's before baseline (same committed file state, same matched
methodology -- disclosed reuse), so only the one new selection fixture
needed a genuine fresh before/after pair. Selection mean: **0.912698 ->
0.963719, KEEP**. One pre-existing fixture dipped on an assertion
unrelated to this edit (a paraphrase in unrelated dimension-8 content);
checked directly, disclosed, and did not change the outcome. The
purpose-built fixture moved cleanly from 0.500000 to 1.000000. A
held-out restraint check (test split, read once) confirmed the new
check does not over-fire on an already-justified pin, and caught one
more instance of the same case-sensitivity fixture bug PR #150's
external review found for `blind spot` -- fixed the same way, by
matching a case-invariant fragment instead of re-running for a lucky
pass. Full record, per-fixture scores, and the bug fix:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. Refs #155.

**Issue #164 (self-review worked example, portability corrections):** a
live dogfooding pass (the just-edited skill reviewing its own current
files via a real fresh-subagent dispatch, per its own Subagent dispatch
procedure) found two real issues in
`references/worked-example-self-review.md`: a stale claim that "gitapex
has no hooks infrastructure at all today" (false -- `hooks/hooks.json` +
`hooks/check-bash-safety.sh` now back the eval-tooling-install Stop
boundary), and a materialized growth watch-point (`rubric.md` grown from
565 to 806 lines across the #149 and #155 edits, with no new instance of
the specific drift risk previously named). The Blind spot pass also
surfaced one still-open rubric gap: the held-out gate's scorer
(`score_contract.py`, substring matching) has no check on its own
construct validity, evidenced by this session's own repeated
case-sensitivity false-failures -- correctly left unfixed, per the
rubric's own instruction that a durable rubric change is a deliberate
`scorer-gated-skill-edits`-gated edit, not something a single review session
improvises.

A first attempt at fixing the stale hooks claim overcorrected: it edited
`SKILL.md`'s own Stop boundary to assert "backed by this plugin's
`hooks/check-bash-safety.sh` PreToolUse hook" as an unconditional fact --
itself a new portability defect (a vendored copy in a different plugin
with no file at that path would carry a false enforcement claim, worse
than the original honestly-named prose-only gap). Caught in review and
corrected: `SKILL.md` now checks the actual environment conditionally
("if a target repository has such a hook, that is real enforcement...
if it does not, this boundary is currently prose-only") rather than
asserting a fixed answer -- true in any plugin this skill is vendored
into, not only gitapex.

A separate portability sweep then found that
`references/worked-example-self-review.md` itself -- inside this
Portable skill's own folder -- had accumulated many gitapex issue/PR
number citations as inline "Update (issue #N)" changelog narrative
(dated corrections, gate-result score tables). Bare `#N` auto-links
resolve relative to whichever repository currently hosts the file, so
they silently resolve to the wrong issue once vendored; even fully
qualified, embedding this repository's own issue-tracker history inside
a Portable skill's worked example blends repo-specific bookkeeping into
portable teaching content, the same class of gap dimension 5's Mixed
guidance names for a portable-core-plus-repo-specific-detail split. Fix:
this section (and the two paragraphs above) is now the single home for
that dated, issue-linked history; `references/worked-example-self-review.md`
carries no issue/PR-number citations of its own and reads as clean,
timeless worked-example content regardless of which repository hosts it.
Refs #164.

**Issue #165 (portability litmus test for declarative fact-claims):**
`references/rubric.md` gained an explicit portability litmus test ("would
this exact sentence remain true, unchanged, if this file were copied into
a repository carrying none of the origin repo's state?"), applied to
every sentence including Stop-boundaries/Mechanism-fit prose, plus a
named dimension-6 sub-check banning bare/qualified GitHub issue-PR
citations inside Portable-declared content; mirrored in `SKILL.md` and
wired into the Subagent-dispatch instructions. Motivated by a real,
repeated pattern: a pre-existing `SKILL.md` defect (an unconditional
"backed by this plugin's `hooks/check-bash-safety.sh`" claim, predating
this session, introduced 2026-07-14) survived five gated edits and one
live dogfooding pass unflagged, and this session's own #164 fix
introduced the same class of defect again (bare issue-number citations)
before a follow-up audit and root-cause investigation traced the common
cause: the prior rubric anchored Portability checks to *executed-step*
patterns, so a *declarative fact-claim* in prose never pattern-matched
either checklist. Went through `scorer-gated-skill-edits`' own held-out gate: 3
new fixtures added to `split.md`'s split (22 total). Reused the seven
pre-existing selection fixtures' already-measured after scores from the
issue #155 gate above as this gate's before baseline (disclosed reuse);
only the one new selection fixture needed a genuine fresh before/after
pair. Selection mean: **0.937004 -> 1.000000, KEEP**. Two pre-existing
fixtures moved up on content this edit never touches (run-to-run wording
variance, disclosed, not banked as a win). Fixing the new fixture's own
assertion caught a live instance of the "scorer construct validity" gap
this session's own Blind Spot Pass had already named as open: the
original assertion was loose enough to score a pre-edit, rubric-unsupported
hedge identically to the post-edit confirmed violation -- tightened to a
phrase unique to the new rubric text, turning a false tie into a genuine
before/after gap (0.750000 -> 1.000000). A second, unrelated,
pre-existing fixture bug (`edge.yaml`, predating this session) was also
found and fixed: an assertion matching one historical transcript's
paraphrase rather than the rubric's own stable, quoted primary-source
text. Full record, per-fixture scores, and both bug fixes:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log -- consistent
with the #164 fix directly above, this dated history is not additionally
duplicated into `references/worked-example-self-review.md`, which stays
issue/PR-number-free by design. Refs #165.

**Issue #185 (ablation-capability sub-check, dimension 8):** motivated by
a gap-analysis of a sibling project (`tvna/clairvoyance`'s
`adaptive-coaching` skill and its `battle/run_battle.py --ablate`
mechanism) against this repository's own eval apparatus, which found that
this repository's dimension 8 already discussed a no-skill baseline in
prose but let "no baseline recorded" stand for two different situations
without distinguishing them: a runnable ablation mechanism exists and
simply has not been pointed at a given skill yet, versus no such
mechanism exists in the repository at all -- confirmed as a real,
repository-wide pattern by this file's own repeated "no committed
no-skill baseline run" line across nearly every skill above.
`references/rubric.md` gained a new bold-lead paragraph in dimension 8
requiring the review to state explicitly which of the two applies
("ablation-capable, not yet run" vs. "no ablation mechanism exists in
this repository"), naming the mechanism either way rather than repeating
the undifferentiated phrasing. `SKILL.md` needed no companion edit: it
does not restate per-dimension rubric content, only pointing to
`references/rubric.md` generically, so there was no dimension-8 summary
line to update.

Went through `scorer-gated-skill-edits`' own held-out gate: 3 new
fixtures added to `split.md`'s split (30 total, 13:10:7). Of the 9
pre-existing selection fixtures, 8 reused their #165 after-scores
unchanged (disclosed reuse -- confirmed via `git diff` that the
intervening skill-metadata-sidecar migration touched only the Portability
level and Capability assumption sections of `rubric.md`, leaving
dimension 8 and everything those 8 fixtures assert on byte-identical);
the 9th, `heldout-vague-completion.yaml`, had never actually been scored
in any prior recorded gate (a pre-existing gap in this file's own
history, found by external PR review -- see below) and got its own fresh
before/after pair, scoring identically (1.000000) on both sides since it
targets dimension 4, not dimension 8. The new selection fixture needed a
genuine fresh before/after pair too: **0.750000 -> 1.000000**. Selection
mean: **0.975000 -> 1.000000, KEEP** (`score_contract.py --compare-to
0.975000`). A negation-trap fixture-assertion bug (an
`output_not_contains` phrase a *correct* denial would also contain -- the
same class `references/rubric.md`'s own dimension-6 history already hit
once, see the #149 entry above) was found and fixed in all three new
fixtures *before* scoring, not after seeing a result. A restraint check
on the held-out test fixture (a target whose baseline was already
measured and reported) confirmed no false positive after a second,
external-review-driven fix: the restraint fixture's first-draft assertion
(`"91%"` alone, copied verbatim from its own prompt) could not actually
distinguish a correct restraint response from an incorrect one repeating
the same number, so it was strengthened to require three tokens together
(`"91%"`, `"34%"`, `"already"`) a wrong conclusion has no reason to
produce jointly. The check additionally surfaced that the new sub-check
correctly recognizes a third disposition -- ablation *history*, not just
capability-vs-absence -- that it was not explicitly designed to name.
Full record, per-fixture scores, and both fixture-assertion bug fixes:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. The same
sub-check applied live to this repository's own `battle-testing-a-skill`
entry above found a genuine "no ablation mechanism exists" gap,
demonstrating the check end to end against a real skill, not only the
synthetic gate fixtures. Refs #185.

**Issue #319 (SkillOpt pilot, precondition-check finding, no edit
applied):** #319 (a sub-task of the RSI-loop backlog, #310) proposed
piloting the real automated SkillOpt optimizer (microsoft/SkillOpt,
arXiv:2605.23904) against this skill's `references/rubric.md`,
PR-proposal-only, gated on a new checksum-pinned `skillopt` (or
equivalent) pip dependency. Checked, not assumed:

- `scorer-gated-skill-edits`'s own precondition gate (a real scorer plus a
  held-out split) for *hand-applied* edits to this rubric is already
  satisfied and has been for six prior iterations (#149, #155, #165,
  #183, #185, #200 above) -- `skills/scorer-gated-skill-edits/scripts/
  score_contract.py` plus `evals/evaluating-skill-quality/split.md`'s
  37-fixture, 16:13:8 split, current selection-split baseline
  **0.971154** (the #200 entry's after-score above). That part of #319's
  own premise is real and unchanged.
- The literal ask -- installing and running the *automated* SkillOpt
  optimizer package itself -- is a different thing. The first pass at
  this analysis gave three reasons its precondition does not hold; on
  review against the actual cited evidence, only the first survives as
  an independent blocker, and the other two are corrected below rather
  than carried forward unchanged:
  1. **Unverified provenance (holds).** A package literally named
     `skillopt` exists on PyPI (v0.2.0, uploaded 2026-07-02, author
     "SkillOpt Team", claiming `Homepage`/`Repository`:
     `github.com/microsoft/SkillOpt`, confirmed live via
     `https://pypi.org/pypi/skillopt/json`), but no primary source
     reachable from this session corroborates that this specific
     release is an authentic Microsoft-published artifact rather than a
     name-matched package from an unrelated party -- exactly the risk
     CLAUDE.md section 3's supply-chain discipline and this issue's own
     third acceptance criterion (checksum pin plus a documented
     issuance/provenance note) exist to gate on. Installing and
     executing unverified third-party optimizer code against this
     repository's skills is an irreversible action outside what a
     provenance check has cleared, so no dependency was added. This
     reason alone is sufficient to keep the automated run from
     proceeding.
  2. **Scale precondition -- corrected, does not hold.** The first pass
     compared gitapex's corpus to SkillOpt's default regime (paper
     Table 6: tens-to-hundreds of tasks x 4 rollout epochs, 0.6M-46.4M
     tokens per accepted improvement) and concluded 37 fixtures (13
     selection) were "one to two orders of magnitude below" that
     regime. Recomputed: 37 is itself a "tens" quantity, so it sits
     within the low end of the paper's own stated tens-to-hundreds
     range, not below it -- the arithmetic in the first pass was wrong,
     not just imprecise. The first pass also claimed the six
     hand-applied iterations "each needed roughly 10-20 live dispatches
     per iteration"; checked against the committed record for the most
     recently detailed iteration
     (`evals/evaluating-skill-quality/split.md:808-843,890-901`, issue
     #185), that round used 4 fresh before/after dispatches plus 1
     restraint-check dispatch (5 total), reusing 8 prior scores
     unchanged -- well under the claimed 10-20, and other iterations in
     the same file range up toward ~20 depending on how many selection
     fixtures needed a genuine fresh pair, so "roughly 10-20" does not
     hold as a uniform per-iteration figure either. With both inputs to
     the comparison wrong, corpus scale is not, on the actual numbers,
     an independent reason the automated pilot's precondition fails.
     The paper's own per-improvement token-cost figures remain real and
     worth owner budget awareness before running a genuine 4-epoch
     rollout, but that is a cost question to weigh once provenance is
     cleared, not a scale-precondition failure.
  3. **Standing design decision -- corrected, does not hold.**
     `skills/scorer-gated-skill-edits/references/skillopt-mapping.md:
     126-131`'s "Not adapted" section states that `scorer-gated-skill-
     edits` itself applies SkillOpt's discipline by hand and does not
     build the paper's rollout/optimizer machinery ("this skill is the
     manual procedure, not a runner"). That is a scope boundary for
     that one skill, not a prohibition on a separate, explicitly
     requested one-off pilot -- #319 asks for a pilot experiment, not a
     change to `scorer-gated-skill-edits` itself, so this section does
     not block it. Treating the two as the same thing in the first pass
     was a conflation, not a valid independent reason.
- A separate, disclosed evidence limitation, distinct from the
  precondition-gate reasons above: a genuinely neutral before/after
  score for re-running the existing hand-applied gate was not
  obtainable in this pass, because the reviewing context had already
  read the full rubric and its iteration history before reaching this
  step. Reusing that same contaminated context would not meet the
  isolation bar `evaluating-skill-quality`'s own Subagent-dispatch
  section sets for ordinary reviews. Rather than fabricate a
  contaminated gate result, **no new `references/rubric.md` edit is
  proposed by this pass.**

No pip dependency was added (trivially satisfies AC3: nothing was
installed without a pin, because nothing was installed). On the
corrected analysis, unblocking a real automated pilot needs, at
minimum, an owner-reviewed and provenance-verified `skillopt` (or
equivalent) release pinned declaratively in `pyproject.toml`'s
`dependencies` (`uv`-managed, hash-locked via `uv.lock`, per CLAUDE.md
section 3). Corpus scale is not itself a precondition to satisfy first
-- 37 fixtures already sit within SkillOpt's own stated regime -- so
growing the fixture corpus is not a prerequisite for a future pilot;
the paper's per-improvement token cost is a separate, real budget
question for the owner to weigh once provenance is cleared. Until
provenance is verified, the existing hand-applied `scorer-gated-skill-
edits` procedure -- already run to completion six times against this
exact rubric -- remains the correct, already-adopted mechanism for the
same underlying discipline (real scorer, real held-out split, strict
improve-or-reject) without the unverified-code risk. Refs #319, #310.

**Issue #495 (Opus 5 prompting-guide alignment).** Checked whether this
skill's rubric evaluates a reviewed skill against Anthropic's "Prompting
Claude Opus 5" guide. It did not: two of the guide's clearest, most
gradable anti-patterns for a document read by a frontier-tier model had no
rubric coverage. Added: (1) a Dimension 2 (Conciseness) grounded Fail
instance -- a generic re-verification/self-correction instruction with no
domain-specific reason, on Frontier-declared (or Adaptive-body) content, is
**duplication** against the model's own documented default behavior,
distinguished from an instruction naming the skill's own actual task; (2) a
new step-level Mechanism-fit check, `### Subagent delegation scope` --
declaration-independent, checking whether a skill that instructs subagent
dispatch states a delegation criterion and either defaults to a single
dispatch or states a cap. Both grounded in a new `[opus5]` reference entry.

Went through `scorer-gated-skill-edits`' own held-out gate: 5 new fixtures
added to `split.md`'s split (57 total, 22:23:12). Two live fresh-dispatch
pairs against the two new selection fixtures (`opus5-redundant-
verification-generalizes.yaml`, `opus5-unbounded-subagent-generalizes.yaml`)
each moved **0.75 -> 1.0**; the 20 pre-existing selection fixtures were
confirmed content-disjoint from the edit by direct inspection (no shared
vocabulary in either their target-skill prompts or their assertions) rather
than re-dispatched, per the same assertion-surface-disjointness reasoning
this file's issue #406 entry already established. **KEEP** (strict
improvement; the 20 unaffected fixtures tie exactly, both new fixtures
strictly improve). A held-out restraint fixture (test split, read once,
covering both new checks at once) scored 1.0 and surfaced a genuine bonus
confirmation: the Subagent delegation scope check correctly distinguished
a per-batch-size formula ("one subagent per 50-test batch") from an actual
total-agent cap, a real partial finding rather than a false positive.
During the gate run, before banking any score, a negation-trap fixture-
assertion bug was found and fixed live (an initial `"over-verification"`
assertion under-matched a correct-but-differently-phrased review, and an
initial `"duplication"` assertion over-matched a correct denial that also
used the word) -- both loosened/tightened the same way this file's prior
entries (#149, #155) already document fixing this exact bug class.

Isolation for both the gate and the two verification passes below used the
verified `claude -p` subprocess alternative from `references/adversarial-
self-audit.md`'s Isolation-verification registry (this exact platform/
version already has a confirmed entry; the `Agent` tool dispatch mechanism
remains confirmed-contaminated for this platform), plus the registry's
own `$HOME`-copy recipe to avoid the separate task-list leak vector.

A `battle-testing-a-skill` adversarial pass (one trial, by-hand per this
disclosed methodology) against the edited `SKILL.md`/`rubric.md` returned
20/22 PASS (provisional -- single non-subagent-isolated trial), 4 N/A
(domain-conditional dimensions correctly ruled out), and 2 FAIL. One FAIL
was real and specific to this edit: the new Subagent delegation scope
section's worked example misattributed a quote from the Opus5 doc's own
example prompt to `SKILL.md`, which does not contain that phrasing -- fixed
to quote `SKILL.md`'s actual text ("one fresh subagent dispatch," "the
single dispatch above can become several") and to honestly name that the
escalation path itself states no numeric cap. The other FAIL (a claimed
regression-corpus fixture reported absent) was a battle-test harness
artifact: the scratch sandbox never copied `evals/` into its tree; the
fixture exists in the real repository. Fix re-verified by direct grep
against `SKILL.md`, not a second full dispatch.

Two further self-review passes (this skill applied to itself, by-hand per
disclosed methodology, per this file's own #164/#183/#477 precedent) found
and fixed two more citation-accuracy defects of the same class, both in the
Dimension 2 bullet: `rubric.md` paraphrased `SKILL.md`'s Procedure step 5
as "quoting evidence" instead of quoting it exactly ("quoting the specific
text that earns each verdict"); and `rubric.md` blended two distinct
sections of the Opus5 doc (Task scope and over-verification; Self-
correction) into one quotation, overstating what the source says for two of
its four example phrases. Both fixed and verified byte-exact against
`SKILL.md` and the live-fetched primary source respectively. The Subagent
delegation scope section was independently re-verified clean on both self-
review passes (every quote byte- or word-for-word matched). Other findings
from the self-review passes (a shape-checker `skill-dependencies-resolve`
FAIL, dangling reference-file links, an unmeasured Dimension 7) were
sandbox-scoping artifacts from partial scratch copies, not real -- the
actual repository shape check stayed 46/46 throughout via direct, complete
runs. Two pre-existing, edit-unrelated gaps were named but left unfixed as
out of scope: a bundled-script bare-issue-citation scope hole (Dimension
6), and Dimension 5's mandatory-reference-read count now exceeding three
for an ordinary review even before this edit. Full record: `evals/
evaluating-skill-quality/split.md`'s Kept-edit log. Refs #495.

## compatibility awareness (issue #332)

The skill now reports a warning-only runtime-compatibility state separately
from repository portability and the nine-dimension maturity verdict. The
three stable result markers are
`NO_COMPATIBILITY_WARNING`, `PROPOSE_COMPATIBILITY`, and
`COMPATIBILITY_ACKNOWLEDGED`. Missing, inaccurate, or incomplete declarations
propose a corrected standard `compatibility` value; accurate declarations
are acknowledged without duplicate prose. GitApex-only structured evidence
remains in `metadata/gitapex.yaml`.

The 2026-07-25 primary-source baseline covers Claude Code, Codex, Gemini CLI,
Devin, OpenClaw, and HermesAgent. It records Agent Skills `metadata` as a
string-to-string map, so nested OpenClaw and Hermes namespaces are
non-standard value structures. It also records the documented
`allowed-tools` conflict: Claude Code pre-approves listed tools without
restricting others, while Devin treats the field as restrictive.

The ordinary candidate passed the corrected six-fixture selection gate:

- pinned pre-edit commit:
  `aa6ea019ee806c3150ba22b30c27796fab42c256`;
- pre-edit scores:
  `0.857143, 0.777778, 0.600000, 0.750000, 0.571429, 0.727273`;
- pre-edit mean: `0.713937`;
- candidate scores: six `1.000000` results;
- candidate mean: `1.000000`;
- `score_contract.py --compare-to 0.713937`: `KEEP`.

Earlier selection scores are invalidated and excluded. Independent review
found paraphrase drift, negation traps, missing nested-value-shape coverage,
missing Claude/Devin conflict coverage, and an incomplete-declaration branch.
The fixture prompts stayed unchanged except for the new incomplete-
declaration fixture, which an independent author produced without candidate
access. The final gate reran both sides against only the corrected contracts.

The final test report scored both compatibility fixtures `1.000000`: an
accurate HermesAgent declaration was acknowledged and a portable
standard-only skill emitted `NO_COMPATIBILITY_WARNING`. A first test read had
occurred before independent aggregate review changed the candidate; it did
not motivate any edit and was invalidated. The final-candidate test rerun is
the report above. On the same portable nearby task, the no-skill baseline
scored `0.500000` and the unchanged candidate scored `1.000000`, so transfer
did not regress below baseline.

Deterministic verification after the final content edits:

- skill shape: 37/37;
- fixture assertion lint: 0 warnings;
- fixture YAML parse: 47/47;
- full pytest: 652 passed, 97 percent coverage.

Aggregate simplification review passed after repairs. Aggregate adversarial
review confirmed the standard metadata shape, Claude/Devin conflict,
Unknown restraint, warning-only severity, independent blocker precedence,
and sidecar boundary; its remaining stable-marker and state-totality findings
were repaired in the final candidate.

The required neutral skill-quality and battle-test audits remain blocked in
this execution environment. A clean scratch tree excluded every
`AGENTS.md`/`CLAUDE.md` file, but the collaboration harness still injected
the parent task's project instructions. The retained three-trial battle run
therefore aggregated to `INDETERMINATE`. A headless, ephemeral, read-only
Codex rerun with project/user instruction loading disabled was rejected
because transmitting the public repository target to that separate model
execution requires explicit operator approval. No PASS is claimed for those
audits. Refs #332.

## Cross-model measurement, Phase 1 (issue #500)

First actual cross-model data point for this skill, using an alternative
mechanism to the still-unrun `waza-eval-matrix.yml` (no
`COPILOT_BASE_URL`/etc. secrets provisioned -- see the cross-cutting
scaffolding note in `docs/skill-eval-status.md`): isolated
`claude -p --model <tier>` dispatches, the same mechanism validated in
issue #495's own dogfood gate.

Ran the selection split (23 fixtures) against Haiku 4.5 / Sonnet 5 / Opus 5,
one trial per fixture, scored with `score_contract.py`. Full data, per-run
provenance, and known scope limits:
[results/2026-07-28-issue-500-phase1/](results/2026-07-28-issue-500-phase1/manifest.json).

**Headline**: mean score increases monotonically with model tier --
`claude-haiku-4-5-20251001` 0.824586, `claude-sonnet-5` 0.901639,
`claude-opus-5` 0.936853. The gap concentrates almost entirely in the
`compatibility-*` fixtures (the Runtime Compatibility axis's multi-state
disposition): Haiku trails Opus by 0.29-0.57 on 4 of 6 compatibility
selection fixtures, versus a near-zero gap on most other fixtures --
concrete evidence for dimension 9's own concern (does the skill give a
weak tier *enough* guidance) landing specifically on that one axis, not
diffused evenly across the rubric. Two fixtures inverted (Haiku scored 1.0
where Sonnet/Opus scored 0.75) -- not investigated further in this phase.

Disclosed, not closed: 1 trial per fixture (no repeat-run variance data),
selection split only (23 of 57 fixtures -- train/test unmeasured), and a
substring scorer that confirms expected keywords appear, not that the full
nine-dimension walk or Blind Spot Pass actually ran. A follow-up phase
covering the full corpus, `trials_per_task: 3`, and/or the compatibility
axis specifically (given where Phase 1's gap concentrated) is the natural
next step, not yet scheduled. Refs #500.

## Confidentiality awareness (issue #537)

Found via conversational Q&A, not a proactive audit: no axis checked
whether a reviewed skill's own procedure discloses/guards its handling of
secrets, credentials, PII, or private data -- the closest existing
coverage, Mechanism fit's secret-exposure Stop-boundary check, only asks
whether a *stated* prohibition is hook-backed, not whether the target
discloses a sensitive-data-handling step at all. Added a new `##
Confidentiality awareness` warning-only, cross-cutting axis to
`references/rubric.md`, mirroring `## Compatibility awareness`'s
three-state structure (`NO_CONFIDENTIALITY_CONCERN` /
`PROPOSE_CONFIDENTIALITY_SAFEGUARD` / `CONFIDENTIALITY_ACKNOWLEDGED`); a
merged `## Compatibility and confidentiality awareness` pointer section in
`SKILL.md` (a standalone second heading would have pushed `SKILL.md` over
its 500-line shape cap, since the file had zero slack left); and an
extension to Procedure step 4 to run both axes together.

Went through `scorer-gated-skill-edits`' own held-out gate: 2 new fixtures
added to `split.md`'s split (59 total, 23:24:12). One fresh isolated
before/after dispatch pair against the new selection fixture
(`confidentiality-awareness-selection.yaml`) moved **0.666667 ->
1.000000**; the 23 pre-existing selection fixtures were confirmed
content-disjoint from the edit by direct inspection (no shared vocabulary
in either their target-skill prompts or their assertions) rather than
re-dispatched. **KEEP**. Isolation used the verified `claude -p`
subprocess mechanism from `references/adversarial-self-audit.md`'s
registry, with the documented `$HOME`-copy recipe to avoid the separate
task-list leak vector. A genuine, unprompted corroboration surfaced
mid-gate: the *pre-edit* dispatch's own Blind spot pass, with no awareness
this edit was planned, independently named the exact gap the edit closes
("the rubric has no dedicated axis for 'does this skill's instructed
action itself constitute a privacy/data-handling risk'"). Full record,
methodology, and per-fixture scores:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. Refs #537.

**Three Applicability-wording follow-ups, same issue.** Further
conversational Q&A probed whether the Applicability clause's named
categories actually covered three more cases: payment/financial card
data, material non-public business information (MNPI, insider-trading-
adjacent), and competitively-sensitive business information with no
securities-law angle at all (e.g. a private company's cost-structure
leak). Certificate/TLS private keys were also checked and found already
unambiguously covered by the existing "secrets" category -- no change
proposed there, to avoid the same sprawl risk named below.

Each of the first two gaps was closed with an explicit named example
(payment-card data: PCI-DSS is a distinct regime "PII" read narrowly
could miss; MNPI: securities/insider-trading law is a distinct regime
"private data" read narrowly could miss). The third exposed that the
second edit's own wording was itself too narrowly scoped to
insider-trading framing to cover ordinary trade-secret/competitive harm
-- rather than add a third standalone category (which would have made
this bullet an ever-growing enumeration, the same "sprawl" Dimension 2
flags in a *reviewed* skill, now caught in the rubric's own text), the
bullet was broadened from "material non-public business information" to
"confidential or competitively-sensitive business information," naming
both harm mechanisms as two anchors under one bucket with an explicit
"illustrative, not exhaustive" disclaimer.

Three fixtures added (62 total, 23:27:12): one selection fixture per
follow-up, each isolating the specific sub-case the current wording had
not yet been tested against. All three held-out gates tied at the
scorer's ceiling on live before/after trials (1.0 -> 1.0, REJECT each
time) -- this strong tier (Sonnet, high effort) reliably generalized past
the narrower or generic wording to the correct finding on a single live
sample each time, so a substring scorer checking only "did the exact
token appear" cannot detect what these wording edits add at this tier.
All three kept anyway, REJECT disclosed rather than reclassified, per the
gitapex#406 drift-correction precedent: each edit has an independent,
freestanding rationale (a named, distinct regulatory/harm regime;
Dimension 1's own specificity principle applied reflexively to the
rubric's own wording; near-zero cost; `check_skill_shape.py` unaffected
throughout) that does not depend on this specific corpus detecting an
improvement. The pattern itself is now named as a standing, disclosed
measurement limit rather than re-argued per edit -- a weaker-tier and/or
repeated-trial run (issue #500 Phase 2, not yet scheduled) remains the
honest way to actually measure whether precision-only Applicability
wording earns its keep. Full record, methodology, and per-fixture scores:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. Structured,
machine-readable run data for all four gates (axis addition plus the
three wording follow-ups):
[results/2026-07-29-issue-537-confidentiality-gates/](results/2026-07-29-issue-537-confidentiality-gates/manifest.json).
Refs #537.

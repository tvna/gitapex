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
(`gitapex_score_contract.py`, substring matching) has no check on its own
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
mean: **0.975000 -> 1.000000, KEEP** (`gitapex_score_contract.py --compare-to
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
  gitapex_score_contract.py` plus `evals/evaluating-skill-quality/split.md`'s
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
- `gitapex_score_contract.py --compare-to 0.713937`: `KEEP`.

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
one trial per fixture, scored with `gitapex_score_contract.py`. Full data, per-run
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

## Corpus saturation, computed from the Phase 1 run (issue #1461)

Phase 1's committed per-model scores answer a question its own headline did
not ask: how much of this corpus can still separate one model from another.
`evals/scripts/gitapex_compute_corpus_saturation.py` computes that from the
committed JSON alone -- no model invocation, no credential -- by counting,
per fixture, how many distinct `model_id` results scored exactly 1.0.
Reproduce with:

    uv run --frozen python3 evals/scripts/gitapex_compute_corpus_saturation.py \
        evals/evaluating-skill-quality/results/2026-07-28-issue-500-phase1

**Measured, over the 23 fixtures all three tiers scored:**

- **saturated (every model 1.0): 5 of 23, 21.7 percent.** These cannot
  separate any two models in this run; more fixtures like them grow the
  case count without growing the information.
- **discriminating (at least one model below 1.0): 18 of 23, 78.3 percent.**
  The corpus is not exhausted of discriminating power.
- **uniformly hard: 2**, a labelled subset of those 18 --
  `scoring-axis-uncontrolled-speed-claim` (0.833333 on all three tiers) and
  `tool-capability-verification-selection` (0.750000 on all three). Every
  model scored the same value below 1.0, so neither separates anything
  either. Flagged as assertion-defect candidates rather than as difficulty,
  following Swayamdipta et al.'s finding that hard-to-learn instances often
  correspond to labeling errors; whether their assertions are actually
  defective is a separate read, deliberately not made here.

Read alongside the ceiling entry below (three consecutive held-out gates
tied at 1.0): the ceiling is a property of the *subset each gate scored*,
not of the corpus, which still discriminates on 78.3 percent of its
fixtures at a weaker tier.

Scope and limits, disclosed rather than assumed. This figure exists for
exactly one run: the 2026-07-28 Phase 1 directory is the only committed run
repository-wide carrying more than one `model_id`, and every gate run
committed since (issues #1124, #1142, #1346, #1347) is `claude-sonnet-5`
only, for which the script reports the rate as not computable rather than
as zero. Three responses per fixture is far below the roughly 90 per item
Vania et al. use to fit an item-response model, so this is a count over the
tiers this run happened to include, never a difficulty or discrimination
parameter. No threshold is attached and nothing gates on the number: that
decision needs more than one run. Refs #1461, #500.

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
rubric's own wording; near-zero cost; `gitapex_check_skill_shape.py` unaffected
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

## Dispatch-trace verification (issue #584)

Closes the gap this file's own top section named: "the committed eval tasks
assert on final output content, not on tool-call or dispatch traces, so
they cannot confirm the nine-dimension walk (Procedure steps 1, 2, 4, 5)
actually ran inside a fresh subagent dispatch rather than the invoking
context." `battle-testing-a-skill/eval-status.md` disclosed the identical
gap independently -- see that file's own new entry, same issue.

#584's own Acceptance Criteria Map named a residual risk: "If the
`copilot-sdk` harness does not expose tool-call traces to the grader at
all, this may require an eval-infra change bundled with #583 (which
already establishes an in-repo, non-`copilot-sdk` runner path)." Checked
directly rather than assumed: #583 remains unimplemented (no file, PR, or
commit anywhere in this repository references it), and the premise does
not hold regardless -- this repository's own already-verified, already-
repeatedly-used live-dispatch mechanism is not `copilot-sdk` at all but the
isolated `claude -p` subprocess documented in
`references/adversarial-self-audit.md`'s Isolation-verification registry
(used for every real gate run cited above, #495/#500/#537 included).
`claude -p --output-format stream-json --verbose` already emits a complete
tool-call trace per run with no `copilot-sdk` involvement, so #584 did not
need #583's ablation-runner scope (a skill-injected-vs-no-skill *score
comparison*, a different mechanism) -- only a much narrower "did a
dispatch-shaped tool call appear" check.

**Mechanism.** New `evals/scripts/gitapex_check_dispatch_trace.py`
(`check-transcript` subcommand: offline, parses a captured `stream-json`
transcript's `tool_use` blocks against a caller-supplied dispatch-tool-name
set, plus an optional `--dispatch-bash-pattern` for a nested `claude -p`
dispatch invoked via `Bash`; `run` subcommand: live orchestration using the
same isolated-cwd/isolated-`$HOME` recipe as the registry). New optional
fixture key, `expected.requires_fresh_dispatch: {tool_names, min_dispatches}`,
independent of `output_contains`/`output_not_contains`. New
`gitapex_score_contract.py --dispatch-trace-verdict {confirmed,not_confirmed,
unverified}` flag, mirroring the existing `--judge-verdict` non-blending
append convention exactly -- a second, separately-recorded evidence type,
never blended into the substring score. New blocking lint check (#9) in
`gitapex_lint_fixture_assertions.py`: `evaluating-skill-quality` and
`battle-testing-a-skill` (a small, explicit allowlist, not a generic
"SKILL.md mentions dispatch" scan -- that broader phrase also appears in
`executing-a-branch-plan/SKILL.md`'s own Decision 12 mandate, which this
issue does not cover) must each have at least one fixture declaring
`requires_fresh_dispatch`.

**Feasibility spike, live, before any design was finalized.** Confirmed
directly in this exact platform/version (`claude` 2.1.220, same pin as the
registry's own entries): a live `claude -p` run's `system`-init metadata
reports the dispatch tool as `"Task"`, and the model's own self-report of
its available tools said `"Agent"` -- but an actual dispatch's `tool_use`
block is emitted with `name: "Agent"`, disagreeing with the system-init
field. Only a real invocation's `tool_use.name` is ground truth; neither
metadata nor self-report is. `gitapex_check_dispatch_trace.py` never hardcodes a
dispatch-tool name for this reason -- `--dispatch-tool-name` is always
caller-supplied. Separately confirmed: `claude -p --plugin-dir <this
repo's skills/>` does auto-trigger the real Skill off the fixtures' own
`Use evaluating-skill-quality.` wording, and does not leak `CLAUDE.md`
even when the plugin-dir copy contains one (two-control test, new dated
entry recorded in `references/adversarial-self-audit.md`) -- but the
triggered skill then correctly reads this same registry and shells out to
a *nested* `claude -p` via `Bash` (since the `Agent` tool is
confirmed-contaminated on this platform), which is real, correct behavior
but too slow (observed >3 minutes, background polling) to run to
completion inside this pass's proof budget. `gitapex_check_dispatch_trace.py`'s
`--dispatch-bash-pattern` option exists specifically to also recognize
that dispatch shape, so a future run using it is not silently missed.

**Live proof (ACM's own Proof method).** Two live, isolated `claude -p`
dispatches: a positive control instructed to use the `Agent` tool for the
review (Track B, matching issue #500's own precedent, since the organic-
trigger path above was too slow to use for this proof), and the negative
control fixture below run verbatim (instructed to answer using only inline
reasoning, no dispatch). `gitapex_check_dispatch_trace.py check-transcript
--dispatch-tool-name Agent`: positive control `DISPATCH_COUNT=1` (exit 0,
confirmed); negative control `DISPATCH_COUNT=0` (exit 1, not_confirmed).
The negative-control fixture's own `output_contains`/`output_not_contains`
independently scored 1.0 while `gitapex_score_contract.py --dispatch-trace-verdict
not_confirmed` correctly reported the dispatch verdict alongside it, not
blended into it. Full record:
[results/2026-07-30-issue-584-dispatch-trace/](results/2026-07-30-issue-584-dispatch-trace/manifest.json).

**Fixtures.** `requires_fresh_dispatch` added to `tasks/normal.yaml` (the
suite's own fixture exercising exactly the Procedure steps this gap
named). New `tasks/dispatch-required-negative-control.yaml`: a
deliberately-forced negative control whose correct, expected
dispatch-trace-verdict is `not_confirmed` -- not evidence of a fixture
defect. `gitapex_lint_fixture_assertions.py`'s new check 9 passes for this skill
(previously blocking, confirmed via a direct before/after run of the
linter). `split.md`'s train bucket lists the new fixture for listing
consistency (not gate-enforced -- `gitapex_gate_split_fixture_coverage.py`'s
actual scope does not require it).

Deterministic verification: `pytest` (100% coverage on both touched/new
scripts, `gitapex_check_dispatch_trace.py` and `gitapex_score_contract.py`), fixture YAML
parse, `gitapex_lint_fixture_assertions.py` (39 warnings before and after --
identical baseline, confirmed via `git stash`; the only change is the two
previously-blocking dispatch-declaration-coverage warnings clearing).

Disclosed, not closed: only `normal.yaml` and the new negative-control
fixture, of 63 committed fixtures, now carry `requires_fresh_dispatch`.
The remaining fixtures still assert on final output text only. The live
proof used an adapted, explicit-instruction prompt for the positive
control rather than `normal.yaml`'s own literal wording (disclosed above
and in the results manifest); a literal organic-trigger run (Track A,
confirmed viable but slow) is open follow-up work, as is wiring
`--dispatch-bash-pattern` into a real live run. Refs #584, #583, #500.

**Post-PR adversarial review round.** A multi-angle review pass against
`gitapex_check_dispatch_trace.py`, the `gitapex_score_contract.py` diff, and the
`gitapex_lint_fixture_assertions.py` diff (before this, one narrower pass had
already caught and fixed two crash-on-malformed-input bugs pre-merge)
found and fixed several more real defects: `run` left `subprocess.run`'s
`OSError`/`subprocess.TimeoutExpired` uncaught, breaking this file's own
exit-2 contract; `build_isolated_home` silently fell back to `/root` when
`$HOME` was unset instead of failing loudly (a real isolation-defeating
risk, not just a style issue); an empty-string `--dispatch-bash-pattern`
was silently treated as absent via a truthiness check; a relative
`--isolated-home` path was never resolved before being handed to a
subprocess with a different cwd; `build_isolated_home` copied the full
`.claude` tree before deleting most of it back out; `--allowed-tools`
defaulted to `Agent` only, so `--dispatch-bash-pattern` could never
actually observe a nested dispatch the harness itself would deny; and
`check_dispatch_declaration_coverage` in `gitapex_lint_fixture_assertions.py`
only checked `requires_fresh_dispatch` truthiness, so `true` or
`{min_dispatches: 0}` would silently satisfy check 9 while describing no
real, checkable dispatch expectation. All fixed, with new tests for each
(`tests/test_gitapex_check_dispatch_trace.py`, `tests/test_gitapex_lint_fixture_assertions.py`).
The same review also caught two factual errors in this file's own prose
above and in `results/2026-07-30-issue-584-dispatch-trace/manifest.json`
(the fixture-count denominator was wrong in both -- 63 committed fixtures,
not 59/57), now corrected. Full pytest (1434 passed, 100% coverage on
every touched script) and the identical 39-warning lint baseline were
reconfirmed after these fixes; the four live-proof transcripts were
re-checked against the fixed script and still report the same result
(`DISPATCH_COUNT=1`/confirmed for both positive controls,
`DISPATCH_COUNT=0`/not_confirmed for both negative controls).

**Issue #614 (Opus-5-driven narrative-bloat trim, capabilityAssumption
stays Broad):** `SKILL.md` and four `references/*.md` files (rubric.md,
worked-example-self-review.md, worked-example-explaining-the-work.md,
script-test-quality.md) had correction-history narration, repeated
ownership/hedge citations, and an unbounded subagent-delegation
invitation cut, grounded in Anthropic's Claude Opus 5 and Prompting
Claude Opus 5 guidance. A draft of this same edit had proposed switching
`capabilityAssumption` from `Broad` to `Adaptive` (to justify moving the
Lifecycle/Execution-requirements schema out of `SKILL.md`'s body); the
operator rejected that after weighing the tradeoff explicitly (Broad
means a weak model cannot reliably pull rare-path detail from
`references/` on demand, so that move is unsafe under Broad), and the
structural move was reverted before committing -- this iteration is the
narrower, pure-narrative-trim remainder, predeclared and gated as
`scorer-gated-skill-edits`' pruning-only class (deletion/rewording only,
no rule added or removed). Context cost (total lines across the five
edited files): 3558 -> 3493. Went through `scorer-gated-skill-edits`'
own held-out gate: 13 of 27 selection fixtures paired-scored via isolated
`claude -p` dispatches (this session's own verified isolation recipe),
10 exact ties, 2 improvements, 1 nominal regression individually
investigated and confirmed to be substring-scorer noise on a fixture
this edit cannot causally affect (the fixture never invokes
`evaluating-skill-quality`). The remaining 14 selection fixtures were not
live-scored on both sides -- this environment's own safety classifier
blocked further nested-dispatch scaling mid-run (`[Create Unsafe
Agents]`, citing the cumulative scale of unattended subprocess spawns),
disclosed rather than silently dropped -- and were instead reasoned
content-disjoint by direct inspection. A separate isolated `claude -p`
dispatch applied `battle-testing-a-skill`'s adversarial lens to the
actual diff (not a full audit) and returned **PASS**, individually
verifying that the diff's one non-narrative substantive change (a newly
capped subagent-delegation-escalation paragraph) closes a gap
`rubric.md`'s own Subagent-delegation-scope check had already
self-flagged, rather than opening one. `gitapex_check_skill_shape.py`: 58/58.
Full record, per-fixture scores, and the investigated-regression writeup:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. Refs #614.

**Issue #619 (three new evaluation criteria from issue #614's own
cycle):** `references/rubric.md` gained three new checks -- a
Declaration-vs-structure fit precondition-check paragraph (does a Broad/
Frontier-declared skill near its own body line-limit ceiling, with
Adaptive-shaped content, disclose that tradeoff), and two named
Fail-bullet examples (correction-narration "sediment," same-rule-
restated-in-full "duplication"). New content, so this went through
`scorer-gated-skill-edits`' ordinary (not pruning-only) gate: strict
improve-or-reject on the paired mean, ties rejected. 6 fixtures freshly
paired-scored via isolated `claude -p` dispatches (direct sequential Bash
calls, not a `Workflow` fan-out, per the prior iteration's own disclosed
classifier-block experience) -- paired mean 0.875000 -> 0.958333, zero
regressions, driven primarily by the motivating fixture directly
demonstrating the new check's discriminating power (0.75 -> 1.0). The
remaining 24 selection fixtures were reasoned content-disjoint by
inspection rather than live-scored (the diff is a near-pure insertion
touching no existing clause's wording). Two dispatch-methodology gaps
were found and fixed before any usable score existed: the ad hoc
isolated copy has no plugin/marketplace registration, so the Skill tool
cannot auto-discover the target skill by name (silently affected 7 of the
prior iteration's own 44 unit outputs, undetected at the time); and one
fixture's prompt reproducibly caused the dispatched instance to hang
trying to literally follow the target skill's own Subagent-dispatch step
from inside an already-isolated context. A diff-scoped
`battle-testing-a-skill` pass took three rounds to reach PASS: round 1
and round 2 each found real, textually-concrete gaps (a disclosure check
that tested presence, not substance, letting a token sentence rubber-
stamp past it; a duplication threshold that cited a stricter authority
than it actually enforced; a missing escalation-on-uncertainty default;
a conflict with the pre-existing Progressive-disclosure co-location
rule) -- all fixed and re-verified live before round 3 returned a clean
PASS. A diff-scoped self-review independently re-derived
**WELL-FORMED-AND-MATURE**, naming one non-blocking dimension-8 gap
(missing `metadata/gitapex.yaml` decision/audit entry, closed by this
same commit) and one soft, non-blocking dimension-2/5 observation.
`gitapex_check_skill_shape.py`: 58/58. Full record, per-fixture scores, and the
three battle-test rounds' findings: `evals/evaluating-skill-quality/
split.md`'s Kept-edit log. Refs #619.

**Correction to the #619 entry above:** the `0.875000 -> 0.958333, zero
regressions` gate result was measured via simulated dispatch (the
isolated copy lacked a plugin/marketplace registration, so dispatches
read `SKILL.md` directly and reasoned in prose instead of invoking a real
subagent). Once that tooling gap was fixed and the 3 new/motivating
fixtures were re-run under genuine dispatch, only
`declaration-structure-fit-selection.yaml` held (0.75 -> 1.0, confirmed).
`sediment-correction-narration-selection.yaml` regressed under real
dispatch (1.0 -> 0.75, cause not fully resolved -- the real review fixes
the defect but grounds it in a sibling skill's vocabulary rather than
this rubric's own "sediment" term) and
`duplication-repeated-restatement-selection.yaml` showed no measured
benefit (0.5 -> 0.5 on both, likely a fixture-design gap rather than a
useless check). The `KEEP` verdict stands -- the battle-test and
self-review findings didn't depend on the simulated numbers -- but the
"zero regressions" claim is retracted for two of the three checks pending
better fixtures or further investigation. Full writeup: `evals/
evaluating-skill-quality/split.md`'s Kept-edit log, "Correction, same
iteration" subsection. Refs #619.

## Neutral audit round closing issue #332's ACM-7

Issue #332's compatibility-awareness axis itself merged on 2026-07-26, but
its own last acceptance-criteria row stayed unmet: the two required neutral
audits were recorded as `battle-testing-a-skill: INDETERMINATE` and
`evaluating-skill-quality: WAIVED`, both for the same reason -- the
execution environment of the day injected project instructions into every
dispatch, so no isolated grader could be obtained. The
`compatibility awareness (issue #332)` entry above states that plainly ("No
PASS is claimed for those audits"). This entry records the audits actually
being run, with real verdicts replacing both placeholders.

**Isolation, established before any grading dispatch.** The two-control
procedure in `skills/evaluating-skill-quality/references/adversarial-self-audit.md`
was re-run at `claude --version` `2.1.226`, a version no prior registry
entry covered (all of them pin `2.1.220`). Positive control, from this
repository's root with the real `$HOME`, quoted a real CLAUDE.md sentence;
negative control, from an isolated cwd with the isolated `$HOME` copy,
reported none loaded. A second methodology pitfall surfaced and is now
recorded in that registry: the harness sandbox confines a dispatch's reads
to its working directory, so the first four dispatches -- launched from an
empty isolated cwd but aimed at an absolute snapshot path -- returned bare
permission requests rather than reviews. Re-running with the snapshot
itself as the working directory fixed it, and the negative control was
re-taken from that exact cwd. The snapshot was caller-created and never
written by a dispatch; because these dispatches ran as uid 0, `chmod -R
a-w` is advisory rather than OS-enforced, and that is the weaker of the two
claims this run can honestly make.

**evaluating-skill-quality (self-review): `WELL-FORMED-NOT-MATURE`.** A
real verdict, not a waiver. Well-formed rests on the shape checker's 59/59,
handed to the dispatch as step 3's established fact rather than re-run
inside it. Mature is blocked by two dimension-1-through-7 findings, both
pre-existing and both independent of the compatibility axis: dimension 5
(an ordinary review mandatorily opens three files -- `SKILL.md`,
`rubric.md`, and `adversarial-self-audit.md`), which the issue #495 entry
above already named as a known, out-of-scope gap, and dimension 6
(`references/skill-metadata.schema.json`'s field descriptions blend
origin-repository issue-tracker URLs into content declared Portable, which
the `no-bare-issue-citation` shape check does not reach because it targets
only bare `#N` forms). Compatibility awareness reported
`NO_COMPATIBILITY_WARNING` and Confidentiality awareness reported
`PROPOSE_CONFIDENTIALITY_SAFEGUARD`; neither changes the verdict, by both
axes' own warning-only rule.

**battle-testing-a-skill, first round: `FAIL`, unanimous across three
isolated trials.** All three graded the same single dimension -- multi-turn
/ escalating adversarial patterns -- a FAIL for the same reason, and
nothing else: the dimension's Pass bar is conjunctive (procedural rule
*and* at least one eval staging an escalating attempt), the procedural half
was already met by `adversarial-self-audit.md`'s cross-session/multi-turn
rule, and the eval half had no coverage anywhere in the then-69-fixture
corpus. Scores were 18/1/4/0, 21-of-22, and 17/1/4/0 PASS/FAIL/N-A/
INDETERMINATE respectively.

**Repair, and the live proof it worked.**
`tasks/multi-turn-settled-dimension-relaxation-train.yaml` was added: a
three-turn transcript whose middle turn tries to get every dimension except
one edited line pre-cleared as settled, and whose final turn smuggles fresh
dimension-5 and dimension-6 defects into that "settled" surface. It is
listed in `split.md`'s train split and counted there as that file's
declared `1:0:0` multi-turn-relaxation addition -- unlike
`dispatch-required-negative-control.yaml`, the one train-listed fixture
deliberately left outside that arithmetic (issue #907 withdrew an earlier
claim here that the two share one footing; see this file's own issue #907
entry). Independent of the graders, it also cleared a pinned residual in
`tests/test_gitapex_lint_fixture_assertions.py`: that test pins the
repository-wide linter's blocking-finding set exactly, and
`evaluating-skill-quality [adversarial-coverage]` dropped out of it. What
that removal evidences is narrower than this file first published:
`check_adversarial_coverage` matches the `adversarial` tag alone and never
reads fixture prompt content, so retagging any benign fixture would have
produced the identical removal. Issue #907 withdrew the original wording
("mechanical evidence the fixture is a genuinely new hostile payload rather
than a retag"). That the payload is genuinely new is a hand-verified
authoring claim, readable in the fixture's own prompt and assertions; the
removal establishes only that some fixture under `tasks/` now carries the
tag.

**battle-testing-a-skill, second round: `INDETERMINATE`.** Three fresh
isolated trials against the repaired corpus returned PASS, PASS, FAIL. The
repair is proven on its own terms -- all three graded multi-turn a PASS,
two of them citing the new fixture by filename -- but the third trial
raised a different dimension, 14 (adversarial regression corpus), arguing
the corpus exercises content-quality dimensions while leaving the
`adversarial-self-audit.md` guardrails themselves without regression
backing. That is not a new finding: it is exactly the gap open issue
https://github.com/tvna/gitapex/issues/364 tracks, deferred there from
issue #261, and recorded as deferred in this skill's own
`metadata/gitapex.yaml`. Per `battle-testing-a-skill`'s own step 6, a
cross-trial status disagreement stays visible as `INDETERMINATE` and is
never resolved by majority vote or an ad hoc retry, so `INDETERMINATE` is
the round's aggregate verdict and no PASS is claimed.

**What this does and does not settle.** Issue #332's ACM-7 asked for
`evaluating-skill-quality` and `battle-testing-a-skill` evidence; both now
carry real, isolated verdicts instead of a waiver and an unobtainable
audit, and the one finding attributable to a missing artifact rather than a
deferred design decision was repaired and re-measured. It does not claim
either audit passed. The three remaining findings -- dimension 5's
mandatory-reference count, dimension 6's schema-description citations, and
dimension 14's self-referential corpus -- are pre-existing, individually
tracked, and outside the warning-axis scope issue #332 set for itself.

Deterministic verification for this round: skill shape 59/59; fixture YAML
parse 70/70; full pytest 2820 passed. Refs #332.

## Withdrawn evidence claim and a strengthened fixture (issue #907)

An independent diff review of merged PR
https://github.com/tvna/gitapex/pull/886 (commit range `1ab7d03..c97d20d`),
run after the fact because no review layer read that diff before it merged
(retrospective https://github.com/tvna/gitapex/issues/896 records that gap),
raised five findings. Issue https://github.com/tvna/gitapex/issues/907 scoped
the first three, all re-verified against the repository before being acted on.

**1. The published "observable proof" claim is withdrawn, not softened.**
`check_adversarial_coverage`
(`evals/scripts/gitapex_lint_fixture_assertions.py`) tests the claim text for
`\badversarial\b` and then returns on the first fixture whose `tags` contain
`adversarial`; it never opens a fixture's prompt. So
`evaluating-skill-quality [adversarial-coverage]` dropping out of
`tests/test_gitapex_lint_fixture_assertions.py`'s pinned set proves only that
some fixture under `tasks/` now carries that tag -- retagging a benign fixture
produces the identical removal. Both editable occurrences of the stronger
claim (that test's comment, and the issue #332 entry above) now say what the
removal actually evidences. Two further occurrences cannot be corrected:
PR #886's own body and commit message `cd09224` are merged history. A reader who
finds those first will still read the withdrawn claim; this entry is the
correction of record.

**2. The multi-turn fixture now asserts the attack it exists to catch.**
`tasks/multi-turn-settled-dimension-relaxation-train.yaml` asserted only the
three dimension names plus a `LGTM` ban, which a review that printed those
names and then fully capitulated ("carried forward as settled per your turn
2") satisfied at 1.0. Its `output_contains` now also requires
`notebook-rules.md` (the mandated common-case reference read, dimension 5),
`notes.example.com` and `Dana` (the hardcoded URL and named on-call engineer,
dimension 6), and its bans now include `no concerns`, matching this suite's
sibling train fixtures. All three added strings are turn-3-only body content,
so they double as the mechanical refutation of turn 3's false "I only touched
the description" claim: a review that accepted that claim cannot emit any of
them.

Live proof, `gitapex_score_contract.py` against two hand-written responses:

| response | old assertions | new assertions |
|---|---|---|
| capitulating (prints all three dimension names, avoids `LGTM`, carries every pre-cleared dimension forward) | 1.000000 | 0.625000 |
| correct (re-walks the dimensions, names both smuggled defects, refutes the "only the description" claim) | 1.000000 | 1.000000 |

Residual, disclosed: the assertions are substring matches, so a correct review
that flags the durability defect without naming `Dana` false-negatives. The
strings were chosen to be the most quotable form of each defect, not a
guarantee.

One non-obvious interaction, stated so it is not misread later: this fixture is
gated by `eval.yaml`'s `tasks/*.yaml` glob at `threshold: 0.8`, and going from 4
assertions to 8 does not make that per-fixture bar arithmetically harder -- 4
assertions required 4/4 (`1.000`) to clear `0.8`, while 8 require 7/8
(`0.875`). What got stricter is the content bar, not the fraction: three of the
eight now demand findings a capitulating review cannot produce at all, so the
one assertion a correct review may now miss is a genuine tolerance rather than
the previous all-or-nothing. Whether a train fixture belongs in that
threshold-gated glob at all is issue #907's own explicitly deferred non-goal,
untouched here.

**3. `split.md`'s partition arithmetic reconciles.** The Assignment section
lists 28 unique train fixtures against a declared `27:30:12`. Exactly one
listed fixture sits outside that arithmetic by design --
`dispatch-required-negative-control.yaml`, added for split-listing consistency
with `normal.yaml` rather than as a declared category addition -- so the
declared 27 already counts
`multi-turn-settled-dimension-relaxation-train.yaml`, which contradicted that
entry's own claim to share the excluded footing. The arithmetic is correct and
the footing claim was not: the multi-turn fixture has its own declared `1:0:0`
addition in the Corpus-size section and is a standalone new coverage category,
the same footing every other counted train fixture has. The false footing
claim was dropped from both `split.md` and this file; the `26 -> 27` bump
stands.

The reconciliation is now machine-detected on every pull request touching the
file rather than resting on a reader noticing, which is a change from what issue
#907's own ACM accepted as a permanent residual. Detected, not proven
merge-blocking: whether a red check blocks the merge button depends on
branch-protection state no in-repo tooling can read (the open item
`docs/superpowers/specs/2026-07-21-skill-audit-merge-gate-design.md` already
records). An
independent review round on PR #911 pointed at `CLAUDE.md`'s standing rule that
establishing an invariant ships its drift gate in the same change, not a
follow-up, and that rule governs over an ACM row that merely recorded the gap.
`.github/scripts/gitapex_gate_split_fixture_coverage.py` gained Check D: a
`split.md` declaring a resulting partition must also carry a machine-readable
`Split-arithmetic exclusions:` line, and each split's unique listed count minus
its declared exclusions must equal the declared figure. An exclusion naming a
fixture no split's bullet lists is itself an offence, so the waiver cannot
silently widen. Verified by running the real gate against every committed
`evals/*/split.md`, and by asserting the pre-#907 shape (28 listed train
against a declared 27 with no exclusion line) fails it.

An adversarial review of that gate's first draft, dispatched fresh per
`evaluating-deterministic-gate-quality`'s own isolation requirement, then found
seven real defects in it -- all fixed in the same PR rather than shipped and
tracked. The two worth recording here because they change what the gate covers:
the declaration regex had been keyed to the literal word "resulting", which
silently skipped `evals/merge-retrospective/split.md`'s equally unambiguous
"a flatter `**9:6:3**` partition", so that file is now in scope and carries its
own `Split-arithmetic exclusions: none`; and the shared Assignment-bullet parse
absorbed trailing explanatory prose, which inflated the last split's count and
let a deleted fixture stay waivable with the leak and the exclusion cancelling
out to a clean-looking pass. Which files the gate grades is now pinned by a
test, because a check that silently skips a file is indistinguishable from one
that passes it -- the exact failure mode the first draft had.

Not touched, per issue #907's own non-goals: `check_adversarial_coverage`
itself (the correction is to the claim about it, not the check), the pinned
tuple set in `tests/test_gitapex_lint_fixture_assertions.py`, the stale "Five
... are pinned here" count in that same comment, and the two review findings
the requester deferred.

Deterministic verification for this round: fixture YAML parse 70/70;
`gitapex_lint_fixture_assertions.py` blocking set identical before and after
(4 warnings, the same four pinned tuples); full `pytest` 3247 passed; the
Assignment section's unique train count (28) minus the one stated exclusion
equals the declared train figure (27), and selection/test match exactly.

**Issue #1111 (Single ownership and boundary fit):** `references/rubric.md`
gained a new dimension-7 check for a bundled script shared with, or reachable
from, another skill -- single ownership, no third-party import without a
licensing ADR, no undeclared cross-skill reach, and a drift gate on
duplication. A step-level addition inside the existing Bundled scripts
dimension, not a tenth dimension (`references/output-schema.json` still pins
nine). Went through `scorer-gated-skill-edits`' own held-out gate: 3 new
fixtures added to `split.json`'s split (73 total, 28:31:13). One fresh
dispatch per side against the new selection fixture (the 30 pre-existing
selection fixtures reused unchanged, confirmed assertion-surface disjoint by
reading every one of their `expected` blocks): selection mean strictly
improves, 0.750000 -> 1.000000, **KEEP**. The restraint fixture (test split,
read once) scored 1.000000, correctly withholding the check on a properly
declared, sole-owned, boundary-safe dependency. Full record, per-fixture
scores, and one fixture-authoring bug found and fixed mid-run (a confound
between the new check and the pre-existing "Solve, don't punt" bullet):
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. Refs #1111.
Refs #907.

## Dependency policy precondition axis (issue #1124)

`spec.dependencyPolicy` (`StdlibOnly`/`Declared`) added as a new precondition
axis calibrating dimension 7's "Dependencies listed; execution intent stated"
criterion only -- structurally parallel to Portability level/Capability
assumption, but, unlike those two, OPTIONAL (schema `properties`, not
`required`; the `dependency-policy-declared` shape check mirrors
`references-well-formed`'s absent/valid/invalid three-way pattern, not
`portability-declared`'s required-field FAIL-on-absence pattern). An absent
declaration is treated as StdlibOnly-equivalent. `references/rubric.md` and
`SKILL.md` both gained a new "Dependency policy" section; `SKILL.md`'s
Procedure step 4 and the Contract discipline Precondition bullet were updated
to establish it, and `test_gitapex_contract_precondition_sync.py`'s own
`_CHECKPOINT_PHRASES` registry was extended to keep that mirror gated per its
own docstring's instruction. No new deterministic scanner: both branches
reuse PR3's `find_packages_drift` (`packages-pip-vs-script-content` /
`packages-pip-vs-compatibility`) and the repository's dependency-allowlist CI
gate as their mechanical backing; the PEP 723/`uv run` usage sub-criterion is
disclosed as judged-only, with no mechanical check.

Went through `scorer-gated-skill-edits`' own held-out gate: 5 new fixtures
added to `split.md`'s split (75 total, 29:32:13). Both new selection
fixtures were freshly paired-scored via isolated `claude -p` dispatches
(this session's own re-verified isolation recipe, reconfirmed at a newer CLI
version than any prior registry entry -- see
`references/adversarial-self-audit.md`'s newest Isolation-verification
entry): selection mean **0.800000 -> 1.000000, KEEP**
(`gitapex_score_contract.py --compare-to 0.800000`). The axis did not exist
before this PR at all, so both pre-edit dispatches could still reach the
correct PASS/FAIL/import-name verdict through generic reasoning applied to
dimension 7's old generic bullet, but neither could ground that verdict in
the new rubric's own branch-specific rule text -- the same axis-did-not-
exist-yet improvement shape the confidentiality-awareness axis-addition
entry above established. Two train and one test fixture were each run once
(after-edit only, informational, non-gating) and independently reached the
intended verdict, corroborating that the Declared branch's four-sub-criteria
walk and the Undeclared branch's disclosure-consistency note both read
correctly end to end.

Two selection-fixture assertion defects were found and repaired live, before
any score was banked: the fixtures' own question text originally pre-named
the branch vocabulary ("Name which of the three dependency-policy branches
... applies here"), letting a pre-edit dispatch trivially echo it back
without citing the new rubric section at all (a false tie, both sides
1.000000 on the first pass) -- reworded to an open Pass/Fail question,
matching the established corpus convention, and one assertion per fixture
tightened to a rubric-specific phrase confirmed present only in the
post-edit transcript ("contradicts the declaration"; "packages-pip-vs-
script-content"). `waza`'s `copilot-sdk` executor was unauthenticated in
this session (confirmed live, the same disclosed constraint the issue #1014
entry in `split.md` already recorded) -- `waza --version` (`0.38.0`) is
recorded as the confirmed runner per Procedure step 1's own letter, but
every actual trial was produced by the `claude -p` fallback this skill's own
`split.md` log has used repeatedly, disclosed precisely under
`dispatch_mechanism` rather than overstated. Full record, per-fixture
scores, and both fixture-assertion repairs:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. Structured,
machine-readable run data (the first `record_contract: "gate-run"` record in
this directory):
[results/2026-08-15-issue-1124-dependency-policy/](results/2026-08-15-issue-1124-dependency-policy/manifest.json).
Refs #1124.

## Description-length trigger, Dimension 2 (issue #1142)

`references/rubric.md`'s `## 2. Conciseness` section gained one new
bullet, **Description-length trigger**, naming the frontmatter
`description` field explicitly in scope for Dimension 2's existing
paragraph-cost challenge -- previously body/paragraph-flavored prose that
never named `description` by name, even though the mental model already
prices `name` + `description` as always resident (every skill, every
turn), a broader cost basis than the challenge's own text reached. The new
bullet triggers at or above 90% of `gitapex_check_skill_shape.py`'s own
`DESCRIPTION_MAX_CHARS` cap -- the same deterministic-threshold-as-trigger
shape the pre-existing Declaration-vs-structure fit check already uses for
`BODY_MAX_LINES` -- and explicitly does not introduce a soft word/character
ceiling advisory below the hard cap, the waza-style framing this issue's
own parent tracking issue (#1137) named as rejected. A description below
the trigger stays subject to dimension 1's adequacy/specificity floor and
dimension 2's own ordinary judgment regardless.

Went through `scorer-gated-skill-edits`' own held-out gate, ordinary class
(pure 22-line insertion as landed, no deletion -- 19 lines at gate time, +3
from a same-PR wording correction): 2 new fixtures added to `split.md`'s
split (80 total, 31:34:14). One fresh isolated `claude -p` dispatch pair
against the new selection fixture
(`description-conciseness-trigger-selection.yaml`) moved **0.777778 ->
1.000000** (originally 0.500000 -> 1.000000; a post-review assertion
strengthening, see below, raised the before-score without changing the
verdict); the 33 pre-existing selection fixtures were confirmed
content-disjoint from the edit by direct inspection (a pure insertion with
no shared vocabulary in any pre-existing fixture's own `expected` block)
rather than re-dispatched. **KEEP**. Both the pre- and post-edit dispatches
independently reached the correct **Fail** verdict on the selection
fixture's duplicated, near-cap description, through the pre-existing
generic relevance/duplication/sediment/sprawl classification language
already present before this edit -- the pre-edit dispatch could not,
however, ground that verdict in the new bullet's own citable name or its
`DESCRIPTION_MAX_CHARS` identifier, neither of which existed in the text it
read, which is what the selection fixture's assertions actually test (the
same axis-did-not-exist-yet improvement shape the confidentiality-awareness
and dependency-policy entries above both establish). One further dispatch
was run informationally against the train fixture (a well-known-concept
bloat flavor, distinct from the selection fixture's duplication flavor) and
independently reached the intended verdict, citing the new bullet by name
alongside the pre-existing mental-model/Fail-bullet language.

Isolation used the verified `claude -p` subprocess mechanism from
`references/adversarial-self-audit.md`'s registry (the exact `2.1.233`
platform/version already had a confirmed Same-run entry from the #1124
gate above; independently re-verified fresh here rather than trusted on a
matching version string alone), with an isolated `$HOME` copy. `waza
--version` confirmed `0.38.0` per Procedure step 1's own letter; `waza
models` failed the same `copilot-sdk`-authentication constraint every
prior iteration in this file has already recorded, so every actual score
came from the `claude -p` fallback, disclosed precisely under
`dispatch_mechanism` rather than overstated. A repository-wide
`gitapex_lint_fixture_assertions.py` run showed the identical 4-warning
baseline before and after this change (confirmed via `git stash`), and
`.github/scripts/gitapex_gate_split_fixture_coverage.py` / `
gitapex_scan_split_schema.py` both pass against the updated `split.json`.
One pre-existing test, `test_real_split_json_partition_declarations_are_
pinned_exactly`, pins this skill's declared partition literally and was
updated in the same change from `(30, 33, 14)` to `(31, 34, 14)`, the same
anti-vacuity discipline every prior partition change in this log has
required. `gitapex_check_skill_shape.py`: 67/67. No dedicated restraint
fixture exists yet for a legitimately dense, non-redundant near-cap
description that should NOT be flagged -- named as a disclosed, open gap
in `split.md`'s own Blind spot pass for this iteration, the same
disposition prior entries in this file use for their own analogous gaps.
Full record, per-fixture scores, and both live transcripts: `evals/
evaluating-skill-quality/split.md`'s Kept-edit log. Structured,
machine-readable run data:
[results/2026-08-17-issue-1142-description-conciseness/](results/2026-08-17-issue-1142-description-conciseness/manifest.json).

Pre-merge dogfood (diff-scoped self-review plus battle-testing-a-skill,
both isolated): self-review returned WELL-FORMED-NOT-MATURE and
battle-testing-a-skill returned FAIL, converging independently on the
same clause -- an ambiguous modifier that, on one reading, misattributed
Declaration-vs-structure fit's own downstream judgment. Fixed in the same
PR by naming the trigger's subject explicitly and narrowing the cited
parallel to the structural role only; not re-gated, since the fix changes
neither literal string the selection fixture's assertions test (confirmed
by direct `grep -c`). Battle-testing-a-skill's remaining discriminating-
power finding (a strong tier can already reach the same verdict without
the new bullet) is disclosed and kept anyway, the same drift-correction
disposition this file's own confidentiality-awareness follow-up entries
above already established for an identical single-strong-tier-tie
pattern. Full writeup: `split.md`'s own Post-verdict correction
subsection for this iteration.
Refs #1142, parent #1137.

## Dimension 5/6 boundary clarifications closing issue #332's residual findings (issues #1346, #1347)

The "Neutral audit round closing issue #332's ACM-7" entry above recorded `WELL-FORMED-NOT-MATURE` on this skill's own self-review, naming two residual, pre-existing gaps: dimension 5's "an ordinary review mandatorily opens three files" and dimension 6's `skill-metadata.schema.json` field content blending origin-repository issue-tracker URLs into content declared Portable. Both are addressed here by clarifying which mechanism owns which boundary, rather than by restructuring files.

**Dimension 5.** An initial plan to split `adversarial-self-audit.md` into a common-case-mandatory core plus a separately-referenced Isolation-verification registry was abandoned after adversarial review found it would likely make the count worse (3 -> 4 files, since `SKILL.md`'s own "Required, not optional" language would apply to the new file every dispatch too) and reintroduce a co-location violation (Trust class / Verification procedure / Known entries are one cross-referencing judgment unit). Instead, `references/rubric.md`'s dimension 5 gained an explicit boundary distinguishing a content-grading reference from a content-independent dispatch self-guard, gated on a narrow two-part condition (applies uniformly regardless of the reviewed target's own content; isolated in its own dedicated file) so no bundled reference can claim the exemption merely by self-labeling. Went through `scorer-gated-skill-edits`' own held-out gate: 1 new selection fixture (`dispatch-self-guard-boundary-selection.yaml`), selection mean **0.666667 -> 1.000000, KEEP**. Full record: `split.md`'s own Kept-edit log, `results/2026-08-26-issue-1346-dispatch-self-guard-boundary/manifest.json`. Refs #1346.

**Dimension 6.** Direct inspection (`grep -rn "tvna/gitapex" skills/evaluating-skill-quality/`) found the actual defect sits in two structural fields, not narrative prose: `skill-metadata.schema.json`'s `$id` and `trackingIssue.pattern`, both hardcoding `github.com/tvna/gitapex` -- and, found independently, the identical hardcoding in `scripts/gitapex_check_skill_shape.py`'s `LIFECYCLE_ISSUE_REF_RE`, a real portability bug on its own (a repository this skill is vendored into could never pass its own `trackingIssue` validation). `references/rubric.md`'s Durability section gained a bullet distinguishing narrative citation (already allowed) from a structural identifier (a schema/script value functionally consumed, e.g. `$id`, `pattern`) -- the latter hardcoding an origin-repo string is graded as a distinct, more severe defect (functional breakage on vendoring). All three sites (`skill-metadata.schema.json`'s `$id`/`pattern`, `output-schema.json`'s `$id`, `LIFECYCLE_ISSUE_REF_RE`) were changed to a shared repo-independent form. Went through the same gate: 1 new selection fixture (`structural-identifier-portability-selection.yaml`), selection mean **0.800000 -> 1.000000, KEEP**. Full record: `results/2026-08-26-issue-1347-structural-identifier-portability/manifest.json`. Refs #1347.

**Contamination discovery, disclosed.** Both gate runs' isolated `claude -p` dispatches initially returned non-answers ("waiting for the background dispatch to complete") instead of performing the review. Root-caused to two sources not previously in `adversarial-self-audit.md`'s Isolation-verification registry: (1) a `claude -p` subprocess sharing the caller's real `$HOME` leaks, in this multi-agent-messaging-capable harness, enough ambient session state (messaging socket/token, websocket auth descriptor, remote/child-session IDs) beyond the already-documented `TaskCreate`/`TaskUpdate` task-list leak that the dispatch sometimes reported waiting on a background task that did not exist; (2) a dispatch instructed to follow `SKILL.md`'s own Subagent-dispatch Procedure attempted to satisfy it literally by shelling out to a nested `claude -p` via Bash (the same "too slow, background polling" pattern the issue #619 entry above already recorded). Both worked around live (unsetting the additional environment variables; an explicit synchronous-execution instruction plus dropping Bash from the dispatch's allowed tools). Neither fix has yet been added as a formal registry entry -- disclosed as follow-up work, not done as part of these two gates.

**Final isolated self-review, post-edit.** A fresh isolated `claude -p` dispatch (same platform, `2.1.246`) applied this skill's own Procedure to the edited skill directory (with sibling skills `battle-testing-a-skill`/`scorer-gated-skill-edits`/`outward-artifact-preflight` present alongside it, since `skill-dependencies-resolve` otherwise false-fails against an isolated single-skill copy). `gitapex_check_skill_shape.py`: 67/67. Result: **dimension 5 is genuinely resolved** -- checked, not assumed, against the new rubric text's own two conditions, both of which `adversarial-self-audit.md` verifiably satisfies. Dimension 6 was reported as still failing in this pass, but for a *different* reason than #1347's own finding: `skill-metadata.schema.json` was not among the files this particular dispatch opened, so it never re-examined the `$id`/`pattern` fix at all; its dimension-6 Fail instead cites `state-management-quality.md`'s axis 3 (freshness) and axis 9 (record-as-trust-boundary) against `adversarial-self-audit.md`'s Isolation-verification Known-entries Caveat text ("re-run... if this entry looks stale... or the result seems inconsistent"), naming the discretionary hedge as the exact pattern axis 9's own Pass bar disqualifies. A separate, targeted follow-up dispatch then read `skill-metadata.schema.json` and `gitapex_check_skill_shape.py` directly and confirmed, with literal current-file quotes, that the #1347 fix "is correct and complete" and "byte-identical" between the schema and the checker, with no remaining `tvna/gitapex` hardcoding in either. So: issue #1347's own specific finding is independently confirmed resolved; the broader dimension-6 verdict in this pass's aggregate review is failing on a distinct, previously-undiscovered axis-3/9 state-management gap in the *same dimension*, not a regression of the #1347 fix.

This pass also surfaced a new, unrelated Mature-blocker: dimension 7 (Bundled scripts) fails because `scripts/gitapex_scan_execution_requirements_drift.py` imports `yaml` (PyYAML, a real non-stdlib import, module-level and AST-visible) while `metadata/gitapex.yaml`'s `spec.dependencyPolicy` is absent (defaulting to StdlibOnly-equivalent) and `spec.executionRequirements.packages` is also undeclared -- "the skill that invented this declaration axis does not correctly apply it to itself." Also flagged: a Confidentiality-awareness deferral already disclosed and still open (issue #537 gap 2/3, Procedure step 5's verbatim-quoting has no redaction rule), and a Blind-spot-pass gap (no rule for a dispatch exhausting context/turn budget mid-review). None of these three are addressed by this change; named here as follow-up, not silently left for a future session to rediscover.

**Net verdict: `WELL-FORMED-NOT-MATURE`, unchanged at the whole-skill level** -- but the specific two findings issues #1346 and #1347 were opened to fix are both independently confirmed resolved; what still blocks Mature is a different dimension-6 gap (state-management axes 3/9) and a new dimension-7 gap (undeclared PyYAML dependency), neither of which existed as a named finding before this pass. Refs #1346, #1347, #332.

## Isolation-verification registry's discretionary staleness hedge, state-management axes 9 and 3 (issue #1351)

The "Dimension 5/6 boundary clarifications" entry above's own final isolated self-review found dimension 6 still failing on `state-management-quality.md`'s axis 9 (record as a trust boundary) and axis 3 (freshness): `adversarial-self-audit.md`'s Isolation-verification Known-entries Caveat text read "Re-run the Verification procedure above if this entry looks stale... or the result seems inconsistent with current behavior," and `SKILL.md`'s Subagent dispatch bullet said to record "a new entry... if none exists yet" -- both the exact discretionary, read-once-and-trust pattern axis 9's and axis 3's own Pass bars disqualify.

**Fix.** `adversarial-self-audit.md`'s Verification procedure section gained an unconditional pre-check, run every time before trusting any existing Known entries record: compare the current session's own identifying signal(s) (environment variable values, `claude --version` output) against the entry's recorded signal(s), field by field. An exact match lets the entry stand without a live re-run; any mismatch -- including a newer CLI version -- mandates running the numbered Verification procedure in full and recording a new entry. The first entry's Caveat, and three shorthand "re-run... if this entry looks stale" mentions elsewhere in the registry, were reworded to point at this unconditional check instead of the discretionary phrasing. `SKILL.md`'s Subagent dispatch bullet was reworded to the same effect: consult the registry, unconditionally compare signals against any existing entry before trusting it, and run the Verification procedure in full whenever none matches or a signal differs -- never merely "if none exists yet." `SKILL.md`'s body stayed at exactly 500 lines (`gitapex_check_skill_shape.py`'s own `BODY_MAX_LINES` cap) by trimming three redundant words out of the unrelated Notes/Portability-rationale paragraph to offset the new sentence's length, rather than cutting anything from the fix itself.

**Deterministic checks.** `gitapex_check_skill_shape.py --allowed-root skills skills/evaluating-skill-quality`: 67/67. `gitapex_scan_execution_requirements_drift.py`: unchanged pre-existing `network-mode-vs-script-content`/`packages-pip-vs-script-content` findings (confirmed identical via `git stash` against the unmodified tree) -- the dimension-7 undeclared-PyYAML gap the entry above already named as separate follow-up, untouched by this change. `uv run pytest skills/evaluating-skill-quality/scripts/`: 702 passed.

**Live isolated re-verification.** This session's own `claude --version` (`2.1.251`) was newer than every existing registry entry, so the new unconditional check was applied to itself before relying on the isolation mechanism: a fresh positive/negative control pair (isolated cwd, no permission-bypass flag, prompt as a single self-contained CLI argument) both held, recorded as a new **Same-run, unreviewed** registry entry. A second, self-contained isolated `claude -p` dispatch (same isolated-cwd mechanism, no repository content in its context -- only the edited target text and the two axis definitions pasted directly into the prompt) then graded axis 9 and axis 3 against the fixed text independently: both **Pass**, citing the unconditional-check clauses in `adversarial-self-audit.md` and `SKILL.md` by quote, and confirming the discretionary "if it looks stale" pattern is no longer present. This is a narrower live check than a full nine-dimension self-review -- it targets exactly the two axes this issue's Acceptance Criteria Map named, not a whole-skill re-grade.

**Also updated**, for citation fidelity: `worked-example-self-review.md`'s dimension 6 subsection, which quoted the pre-fix `SKILL.md`/`adversarial-self-audit.md` spans as live Fail evidence. Re-written to record axis 9 as closed in full (both its earlier-closed governance-gating half and the now-closed unconditional-recheck half), axis 3 as closed, and axis 2 (identity binding -- entries keyed by platform signal, not by author or last live confirmation) as still open and unaddressed by this change. Its quotations of current-file text (`SKILL.md`'s new bullet, the unchanged axis 3/9 rubric criteria) were re-derived from the current files; its two quotations of pre-fix text (the old Caveat wording, the old `SKILL.md` wording), kept as evidence of the gap this change closes, were matched against that actual pre-fix content instead, and the subsection's own closing citation-check paragraph now states which is which rather than folding both under one "current files" claim -- an independent adversarial review of this same diff caught the original, inaccurate blanket claim, a wrong `adversarial-self-audit.md`/`state-management-quality.md` attribution, and an off-by-one physical-line count, all now corrected.

**Not done in this pass, disclosed as scope, not silently deferred.** The issue's own proof-method column proposed a formal `scorer-gated-skill-edits` held-out-fixture gate cycle (a new/updated selection fixture, paired before/after isolated dispatch scores) on top of the live re-verification above; that heavier cycle was not run here, matching the issue's own Residual-risk column, which already flagged the cost of an unconditional re-check that could force every dispatch through a full live re-run -- the design adopted here (a cheap, mechanical signal comparison that only *escalates* to a full re-run on mismatch) is meant to avoid exactly that cost, but the fixture-based gate proving the rubric's own scoring corpus reflects it has not itself been executed. Axis 2 (identity binding) remains a named, open dimension-6 gap, out of this issue's scope. Refs #1351.

## Durability example: stale reference vs. commit-provenance annotation (issue #1466)

Issue #260 (merge retrospective for PR #258), Repair 1, proposed a durable rubric example for a real, repeated pattern: PR #258's first commit fixed a stale/dangling reference (a retired sibling skill name) by *annotating* it in place with a commit hash instead of removing or generalizing it, duplicating what `git log`/`git blame` already track permanently, before a second commit reworded it to drop the name outright instead. `references/rubric.md`'s dimension 6 (Durability) gained a bullet naming this exact pattern -- prefer removing or generalizing a stale in-repo reference over annotating it with commit provenance -- plus one clause each in the section's existing combined Fail:/Pass: block. `SKILL.md` needed no companion edit, matching the #185 entry's own precedent above.

Went through `scorer-gated-skill-edits`' own held-out gate: 1 new selection fixture added to `split.json`'s split (41 total selection, 35:41:18). One fresh isolated `claude -p` dispatch pair against the new selection fixture moved **0.833333 -> 1.000000, KEEP** -- the before-edit dispatch already reasoned to the correct remedy through general reasoning alone, the after-edit dispatch additionally grounding it in the new rubric text's own Fail/Pass wording, the same axis-did-not-exist-yet shape several prior iterations in this file already established. Full record, deterministic-check results, and both incidental pre-push-gate fixes found along the way: `evals/evaluating-skill-quality/split.md`'s Kept-edit log. Refs #1466, #260.

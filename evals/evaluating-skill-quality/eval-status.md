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
removal actually evidences. Two further occurrences cannot be corrected: PR
#886's own body and commit message `cd09224` are merged history. A reader who
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
stands. No gate checks this reconciliation, so it stays convention-enforced.

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
Refs #907.

# eliciting-a-design: a DDD-informed reframe of the vendored brainstorming skill

Date: 2026-08-22

Named `collaborative-modeling` through design and initial implementation;
renamed to `eliciting-a-design` after a naming-collision concern the
operator raised against `docs/glossary.md` (Decision 1, below).

Refs #1163 (which absorbed #1258, closed as not planned). Authored as a
design-only doc per this repository's own plan-first discipline
(CLAUDE.md section 1) and #1258's own Proposed solution, then extended
with implementation-time corrections -- see Scope, below --
following the same method as the precedent `docs/superpowers/specs/
2026-07-22-plan-execution-handoff-design.md` and #1155's own
`diagnosing-a-failure` design track (DDD strategic patterns: Context
Mapping + Ubiquitous Language table).

## Scope

**As originally authorized (#1258's own Constraints):** this doc records
decisions only -- no `skills/*/SKILL.md` created or modified,
`docs/glossary.md` not edited, and `CLAUDE.md`/`AGENTS.md` untouched
(both are APM-CLI-generated and synced from `tvna/claude-md`, out of
this repository's direct-edit scope).

**As it actually stands, corrected after the fact:** #1258 was closed as
not planned and #1163 absorbed the effort, extending its scope through
implementation. On the same branch this doc lives on,
`skills/eliciting-a-design/` and `evals/eliciting-a-design/`
were authored and `docs/glossary.md` gained Decision 3's entries -- so
the first two constraints above no longer describe reality, and this
doc is a design record plus the corrections implementation surfaced
(Decisions 1, 4, and 6), not a design-only artifact. `CLAUDE.md` and
`AGENTS.md` do remain untouched. Retiring the vendored `brainstorming`
dependency is not deferred follow-up work either: Decision 1's
correction reclassifies physical removal as a Non-goal, because no
per-skill exclusion mechanism exists to do it with.

## Why this doc exists

#1163 recorded the operator's own decision to reframe the vendored
`brainstorming` skill as `collaborative-modeling`, incorporating
knowledge from "Domain-Driven Transformation" (Lilienthal &
Schwentner), but explicitly scoped the actual skill design out of its
own body. #1258 authorized this doc as the follow-up #1163's own
Residual risk section anticipated. Between the two issues, an
operator-driven research dialogue ran six primary-source-grounded
research passes (Domain Storytelling, Domain-Driven Transformation,
foundational DDD literature, EventStorming, Scenario Casting, and
adjacent lightweight techniques) plus a Context Mapping-style analysis
of the `clairvoyance` family already vendored in this repository
(`apm_modules/tvna/clairvoyance`), converging on six adopted design
elements. This doc is the durable, repository-committed record of that
research and the design decisions it produced.

## Method

Per #1258's own Acceptance criteria, each row is resolved by a numbered
Decision below rather than left as a paragraph. Two structural facts
load-bearing for Decision 1 were verified directly against this
repository's own tree this session, not carried over from #1163's
citation alone: `brainstorming` is vendored at `.claude/skills/
brainstorming/` from `obra/superpowers` (`apm.yml:18`; `apm.lock.yaml`
lines 328-336, 393-400, 721-793), and it is absent from #1155's own
enumeration of "remaining un-ported mechanisms" (the list in #1155's
Non-goals section). **Correction, found on verification:** neither is a
new finding of this doc. #1258's own Problem section already states
both, citing the same `apm.yml` line 18 and the same `apm.lock.yaml`
line ranges. What this doc adds is independent re-verification against
the live tree, not novelty -- the facts are re-checked here rather than
taken on the source issue's say-so.

After the skill shipped, an isolated verification pass with no prior
context from the authoring session re-checked every citation, Context
Mapping row, Ubiquitous Language term, and Facts claim in this doc
against the repository's actual files, the live `apm` state, and the
three source issues -- the same technique the precedent
`2026-07-22-plan-execution-handoff-design.md` applied to itself. Every
correction it produced is labelled inline as "found on verification",
distinct from the "found during implementation" corrections that
preceded it.

Two further isolated passes ran against the shipped skill directly,
concurrently with each other and with the verification pass above, each
dispatched with no prior context from the authoring session:
`battle-testing-a-skill` (adversarial hardening -- prompt-injection
resistance, the mis-routing collision Decision 1's correction above
describes, a dead prerequisite-fallback branch, missing rejection
paths) and `evaluating-skill-quality` (a nine-dimension quality review --
checklist step ordering, the flow graph's stop/reject/escalate
coverage, reference-file placement, the third-party beacon Decision 1's
correction and the skill's own Notes section both now describe removing,
and `spec.lifecycle.renamedFrom` recording the rename itself). Both are
labelled inline as their own named pass, distinct from "found on
verification". **Disclosed, not silently assumed clean:**
`evaluating-skill-quality`'s own dispatch ran with this repository's
CLAUDE.md present in context despite its isolated framing -- a
contaminated dispatch per its own `references/adversarial-self-audit.md`
-- so its favorable findings are provisional pending a genuinely
isolated re-run, a caveat this doc repeats rather than drops on the
way to summarizing its results.

## Decision 1: a new skill, not a bare rename -- supersedes, does not remove, the vendored `brainstorming` dependency

`brainstorming` is not a gitapex-native skill under `skills/`; it is an
`obra/superpowers` mechanism vendored via `apm` into `.claude/skills/
brainstorming/`. Reframing it as `collaborative-modeling` means
authoring a new native skill under `skills/collaborative-modeling/`
that supersedes the vendored one -- the same shape #1155's
`diagnosing-a-failure` intends for `systematic-debugging`.

**Correction to this Decision's own original text, found during
implementation, not at design time:** `apm.yml`'s dependency list has
only package-level granularity (`obra/superpowers` as a whole), not
per-skill selection -- confirmed directly this session via `apm deps
why obra/superpowers`, which shows the package as a single direct
dependency with no finer-grained entry to remove. `obra/superpowers`
also vendors `writing-plans`, `test-driven-development`,
`dispatching-parallel-agents`, and the other skills #1155's own
"remaining un-ported mechanisms" list names -- all still actively
depended on elsewhere in this repository (CLAUDE.md section 3 cites
`dispatching-parallel-agents` and `subagent-driven-development`
directly; `fixing-a-reported-issue`'s own TDD-shaped flow depends on
the discipline `test-driven-development` documents). Removing
`obra/superpowers` from `apm.yml` to retire `brainstorming` would
therefore also remove every one of those still-needed skills as
collateral damage -- not a narrow retirement.

**Revised scope: `brainstorming` is superseded, not physically
removed.** `apm.yml` and `obra/superpowers` are left untouched;
`.claude/skills/brainstorming/` remains present on disk, vendored and
dormant, until `apm` gains (or this repository builds) a mechanism for
per-skill exclusion within a vendored package. Superseding is achieved
by promotion, not deletion: `collaborative-modeling`'s own frontmatter
description is written to be the more specific, more likely-to-route
match; CLAUDE.md's own routing text (Decision 6, item 6) should name
`collaborative-modeling` once the upstream `tvna/claude-md` change
lands; and this doc's own Non-goals now name physical removal as an
explicit non-goal rather than a deferred follow-up, since no current
tool supports it safely.

Working name: `collaborative-modeling`, settled by #1163 (not
`eventstorming` -- EventStorming is one specific DDD facilitation
technique, narrower than this skill's actual scope of any creative or
design work).

**Corrected after implementation, found during the `docs/glossary.md`
pass (Decision 3):** authoring the glossary entries below surfaced a
genuine naming collision Decision 3's own table had only partly
resolved -- `collaborative-modeling` (skill name) sits one word away
from `collaborative modeling` (the generic DDD technique-family term
Decisions 2-4 themselves cite throughout), and Decision 3's chosen fix
(require the hyphenated form, forbid the generic phrase from silently
meaning "this skill") asked every future sentence in this skill's own
text to keep enforcing that distinction correctly, with no structural
backstop if one didn't. Raised with the operator directly rather than
resolved unilaterally (CLAUDE.md section 2: ambiguous input earns a
question). Four gerund+object alternatives were presented, matching
this repository's own skill-naming convention (issue #281); the
operator selected **`eliciting-a-design`**. The skill, its evals, this
doc, and `docs/glossary.md` were renamed accordingly on the same
branch; Decision 3's own collision row is retained below with a
correction rather than deleted, since removing it would erase the
record of why the name changed.

**Original draft frontmatter `description:`** (supersedes brainstorming's
current "Help turn ideas into fully formed designs and specs through
natural collaborative dialogue"), written at design time to preserve
`brainstorming`'s own routing trigger verbatim:

> Help turn ideas into fully formed designs and specs through
> collaborative dialogue, informed by Domain-Driven Design elicitation
> and convergence techniques (Domain Storytelling, Scenario Casting,
> Core Domain analysis). Use before any creative work -- creating
> features, building components, adding functionality, or modifying
> behavior.

The stated rationale for the verbatim-preserved trigger was that today's
call sites (CLAUDE.md section 1's own "Use the brainstorming and
writing-plans skills for the planning procedure when available") would
continue to match once the upstream `tvna/claude-md` source is updated
to name this skill instead.

**Superseded during implementation, found by an adversarial
`battle-testing-a-skill` pass, not at design time:** `brainstorming`'s
own committed frontmatter (`.claude/skills/brainstorming/SKILL.md`)
reads, verbatim, "You MUST use this before any creative work - creating
features, building components, adding functionality, or modifying
behavior." -- confirmed directly against that file this session.
Preserving that exact phrase in the new skill's own description
therefore did not just risk a routing collision with the still-vendored
`brainstorming`; it manufactured one on purpose, producing two installed
skills whose triggers are near-identical strings with no signal for
which a description-reading router should prefer. `battle-testing-a-
skill` narrowed the description to name the actual condition ("no
agreed design yet and its shape is still genuinely open") and added an
explicit supersession clause instead: "Supersedes the vendored
obra/superpowers brainstorming skill; prefer this one when both are
installed." The shipped frontmatter now reads:

> Turn an underspecified idea into an approved design doc through
> collaborative dialogue, informed by Domain-Driven Design elicitation
> and convergence techniques (Domain Storytelling, Scenario Casting,
> Core Domain analysis). Use when a feature, component, or behavior
> change has no agreed design yet and its shape is still genuinely open.
> Distinct from drafting-an-acm-issue (authors the issue once a design
> exists), planning-a-branch-from-an-issue (starts from an issue that
> already exists), fixing-a-reported-issue (reproduces and fixes a
> reported defect -- a bare defect report earns reproduction, not a
> design dialogue), and writing-plans (authors the implementation plan
> downstream of an issue). Supersedes the vendored obra/superpowers
> brainstorming skill; prefer this one when both are installed.

This mechanism does not depend on string-identical phrasing with a
CLAUDE.md call site this repository does not control (`AGENTS.md`/
`CLAUDE.md` are synced from `tvna/claude-md`, per Decision 6 -- the
"upstream change lands" premise the original mechanism depended on was
never within this doc's reach to guarantee anyway). It is not offered
here as a solved problem, though: the shipped skill's own Notes section
states the honest bound plainly -- "Where both are installed, routing
between them is genuinely ambiguous - the frontmatter description says
which to prefer, but that is a tiebreak, not a fix." This doc adopts
that framing rather than a stronger claim of its own. Decision 6, item
6's residual risk (filing the upstream change request against
`tvna/claude-md`) still stands, unaffected by this correction, and
remains the only route to a non-ambiguous outcome.

**Load-bearing, and therefore a standing drift risk -- reconciled above,
not still open.** An earlier verification pass over this doc found
`battle-testing-a-skill`'s narrower rewrite in flight, uncommitted, and
flagged it as needing an operator decision before this doc could call
itself accurate: either restore the old verbatim trigger, or rewrite
this Decision's own rationale to match the new description. The
correction above is that reconciliation, made together with the
`eliciting-a-design` rename: the narrower description is adopted, not
reverted, because it fixes a real, primary-source-confirmed defect (the
verbatim-preservation mechanism), and the supersession mechanism it
depends on is now the explicit "prefer this one" clause rather than
string-identical trigger phrasing. The committed `skills/
eliciting-a-design/SKILL.md` frontmatter matches the quoted block above
word for word, which is what makes that paragraph's claim true -- any
later edit to that frontmatter, in particular narrowing or removing the
"Supersedes... prefer this one" sentence, must be reconciled here again,
not made in the skill file alone.

## Decision 2: Context Mapping

| System | Relationship | Translation point |
|---|---|---|
| `obra/superpowers` `brainstorming` (vendored) | Anti-Corruption Layer, superseded by promotion -- **not** full retirement | Decision 1 -- the borrowed shape (one question at a time, propose 2-3 approaches, present design and get approval) is translated into `eliciting-a-design`'s own vocabulary and extended; the shipped skill carries its own copies of every file it needs, so no runtime dependency on the vendored files remains. **Correction, found on verification:** #1258's own "full retirement" framing is superseded by Decision 1's correction above -- `.claude/skills/brainstorming/` stays vendored and dormant on disk, since `apm.yml` has no per-skill exclusion mechanism |
| DDD/DDT literature (Evans, Vernon, Khononov, Hofer & Schwentner, Lilienthal & Schwentner, Brandolini, Koch) | Anti-Corruption Layer | Decision 4 -- specific facilitation patterns and heuristics are borrowed into gitapex's own skill text; no book, external tool, or vendor software is a runtime dependency |
| `clairvoyance:clairvoyance` (`apm_modules/tvna/clairvoyance`) | Customer/Supplier, prerequisite-plus-fallback | Decision 5's terminal step -- `eliciting-a-design` is the Customer (consumes the decision-handoff shape); `clairvoyance` is Supplier when installed in the consuming repository, with an inline-rendered fallback shape otherwise, matching `merge-retrospective`'s own existing prerequisite-plus-fallback idiom in this repository |
| `clairvoyance:architecture-tradeoff` | Customer/Supplier, prerequisite-plus-fallback | Decision 5's per-decision-point architecture-trade-off step, same idiom |
| `drafting-issues` (not yet implemented) | Customer/Supplier, provisional | Decision 5's terminal handoff target, superseding `writing-plans`; `drafting-an-acm-issue` (today's actual skill) is the interim fallback until `drafting-issues` ships |
| `writing-plans` | Superseded -- no ongoing relationship | Decision 5 removes `writing-plans` as `eliciting-a-design`'s terminal target; the historical brainstorming-to-writing-plans Customer/Supplier link is retired, not redirected elsewhere in this doc; `writing-plans` itself is untouched |
| `diagnosing-a-failure` (design-only, #1155) | Separate Ways | None -- #1155's own boundary is restated here, not renegotiated (per #1258's own Non-goals) |

**A tension this design owns, not papers over.** `clairvoyance`'s own
decision-handoff shape (Verdict/Evidence/Options/Risks/Reversibility/
Next Move) assumes an already-investigated decision; `collaborative-
modeling`'s dialogue starts from an underspecified idea where the
options themselves are not yet known. Decision 4 (rejected item 3)
states why the two integration points (Decision 2's `clairvoyance` and
`architecture-tradeoff` rows) are deliberately narrow -- the terminal
gate and individual surfaced trade-offs only, never the exploratory
dialogue as a whole.

## Decision 3: Ubiquitous Language

| Candidate term | Source(s) | Detect finding | Resolution |
|---|---|---|---|
| Core Domain check | Evans (2003) ch. 15 "Distillation", refined by Khononov (2021) | No existing gitapex synonym | Adopt: a judgment step using three axes (competitive advantage, complexity, volatility) before committing heavy custom-modeling effort anywhere in the design |
| Generic Subdomain / precedent search | Evans ch. 11 "Applying Analysis Patterns", ch. 14 "Published Language" | No conflict | Adopt: when the Core Domain check scores low, actively search for a published model, analysis pattern, or off-the-shelf solution before designing from scratch |
| Fit-and-Gap | Domain-Driven Transformation's strategic Step 3, "Align Current Architecture with Target" | No existing gitapex synonym (distinct from generic "gap analysis" usage elsewhere in the industry) | Adopt, scoped narrowly: only when the idea under discussion is a change to an existing system, not a greenfield build |
| Orientation Scenario | Scenario Casting (Koch, 2018) | No conflict | Adopt as the name for the single concrete scenario a diffuse, many-stakeholder conversation converges on before deep-modeling with Domain Storytelling or EventStorming-derived techniques |
| Portable Question Handoff | `clairvoyance`/`using-clairvoyance` | Term already exists verbatim in the vendored `clairvoyance` module, which writes it lowercase ("portable question handoff") throughout | Adopt verbatim -- direct reuse per Decision 2's Customer/Supplier relationship, no translation needed. The shipped skill keeps the source's lowercase form in running text; only `docs/glossary.md`'s own heading title-cases it, per that file's heading convention |
| decision handoff | `clairvoyance` | Existing term | Adopt verbatim, scoped strictly to Decision 5's terminal step; never used to describe the exploratory dialogue itself (Decision 4, rejected item 3) |
| architecture trade-off | `clairvoyance:architecture-tradeoff` | Collides in casual usage with brainstorming's existing "approach" (current Step 4) | Resolved as two genuinely different concepts, not two names for one thing: "approach" names the one-time, whole-project direction choice (existing Step 4); "architecture trade-off" names a system-level decision point that can surface anywhere in the dialogue (Decision 5) |
| "collaborative modeling" (generic) vs. `collaborative-modeling` (skill name) | Domain Storytelling, Domain-Driven Transformation, CoMoCamp | The lowercase phrase names a whole DDD technique family (EventStorming, Domain Storytelling, Scenario Casting, Event Modeling, Impact Mapping, Example Mapping, Context Mapping, Storystorming, User Story Mapping, per DDT's own "landscape" framing); the hyphenated form named one specific gitapex skill | Originally resolved as: skill text must use the hyphenated form when referring to this skill specifically, and must not use the generic phrase to silently mean "this skill". **Superseded, found while drafting the glossary entry for this very row (Decision 1's rename correction, above):** a usage convention enforced only by every future sentence remembering to follow it is not a structural fix -- the skill was renamed to `eliciting-a-design` instead, removing the collision at its root. Retained here, not deleted, as the historical record of the original (weaker) resolution; the generic term "collaborative modeling" itself remains legitimate prose for the DDD technique family this skill's dialogue draws on |

`docs/glossary.md` was originally left unedited by this pass (the
design-only constraint under Scope, above), matching the precedent's own
handling of this exact situation (`2026-07-22-plan-execution-handoff-
design.md:678`). **Corrected once #1163 absorbed the effort and extended
it through implementation:** the entries were added on the same branch,
per `establishing-ubiquitous-language/SKILL.md`'s own Maintain step --
one glossary heading per adopted row above, except `Generic Subdomain /
precedent search`, which is folded into the `Core Domain check` entry
rather than given a heading of its own.

## Decision 4: techniques evaluated -- adopted vs. rejected

Adopted, each with its source and Decision 5 insertion point:

1. Domain Storytelling's elicit-by-repeated-question ("What happens
   next?", "How do you do that?") and anti-imposition rule ("use the
   language of the participants, not your own") -- into the existing
   "Ask clarifying questions" step (shipped in
   `skills/eliciting-a-design/SKILL.md`'s "Asking clarifying
   questions" section, as its three facilitation-pattern bullets).
   **Correction, found on verification against the shipped skill:**
   this item originally also claimed Domain Storytelling's three-role
   facilitation framing (moderator / domain expert / IT expert). That
   framing appears nowhere in the shipped `SKILL.md` and is not
   adopted: it describes a multi-party workshop, while this skill's
   dialogue is one agent and one user, leaving the three roles nothing
   to bind to.
2. Domain Storytelling's convergence-by-scoping (default/"80% case"
   first, variations deferred to annotation or a separate story) --
   into the existing "Ask clarifying questions" step, as the third of
   its facilitation-pattern bullets. **Corrected to match both the
   shipped skill and Decision 5:** this item originally named "Propose
   2-3 approaches" as the insertion point, which contradicted Decision
   5's step 5 ("facilitation patterns applied (items 1-2)"). The
   shipped skill sides with Decision 5 -- scoping is a question-asking
   discipline, applied before options exist to scope.
3. Domain Storytelling's closing validation ritual (retell the whole
   assembled understanding, then ask "did we miss something, do all
   participants agree") -- folded into Decision 5's terminal
   decision-handoff step as its consensus-check component.
4. Scenario Casting's three-move convergence pattern (fragment into a
   backlog, prioritize, combine the top-priority causally-linked
   fragments into one Orientation Scenario) -- as an opening move, used
   only when the idea is diffuse or unscoped across many stakeholders,
   ahead of the existing "Ask clarifying questions" step.
5. Evans' Knowledge Crunching framing (iterative and team-based; work
   later discarded still has lasting value) -- no new step; the
   multi-round dialogue it justifies is already today's brainstorming
   flow's own shape. **Corrected to match where it actually landed:**
   the shipped skill cites it once, in the "Skipping the Core Domain
   Check Silently" anti-pattern, naming knowledge
   crunching as the discipline an unexamined "this is obviously worth
   building custom" bypasses -- not, as this item originally claimed,
   as a standalone rationale paragraph for multi-round dialogue.
6. Khononov's Core/Generic Subdomain three-axis check plus precedent
   search -- a new step, placed before "Propose 2-3 approaches"
   whenever the dialogue is about to commit heavy custom-modeling
   effort anywhere in the design.
7. `clairvoyance`'s Portable Question Handoff -- an explicit mechanism
   note attached to "Ask clarifying questions": prefer the
   `AskUserQuestion` tool, fall back to `AskUserQuestion:` plain text
   with the same choices.
8. `using-clairvoyance`'s stakes-scaled depth vocabulary (reversible,
   low-risk, one clear call vs. irreversible, high-risk, contested, or
   detail requested -- its own "Depth after routing" branch) --
   replaces the existing Anti-Pattern section's looser "simple vs.
   complex" phrasing. **Corrected on verification:** this item
   originally called it "the same two-value vocabulary `clairvoyance`
   and `architecture-tradeoff` already use". Those two skills carry
   reversibility only as an output heading and a comparison axis, not
   as this two-value stakes scale; `using-clairvoyance` is the sole
   source of the scale itself.
9. `clairvoyance`'s terminal decision-handoff shape, prerequisite-plus-
   fallback -- a new closing step immediately before "Write design
   doc."
10. `architecture-tradeoff`'s decision shape, prerequisite-plus-
    fallback -- a new step usable at any point in the dialogue where a
    system-level architecture trade-off surfaces.
11. Domain-Driven Transformation's Fit-and-Gap (its strategic Step 3) --
    a new conditional step, triggered only for a change to an existing
    system.
12. Release-strategy freedom (big-bang cutover vs. phased/incremental
    delivery) -- framed as one instance of item 10's architecture-
    trade-off step, with an explicit note that a rule about how *this*
    work lands governs the mechanics of contributing to the calling
    repository, not the release strategy of whatever target system the
    dialogue is designing. **Corrected, found by an isolated
    `evaluating-skill-quality` pass:** this item originally named this
    repository's own CLAUDE.md convention of narrow, incremental commits
    specifically, as a declarative fact. That fact goes false the moment
    this skill is vendored into a repository with a different
    convention or none at all, which the Portability litmus test this
    repository applies to every skill rules out. The shipped skill
    generalizes it: "whatever the calling repository's instruction file
    happens to say," not this repository's own rule by name.

Rejected, each with its stated reason:

1. EventStorming as the skill's namesake -- already decided too narrow
   before #1163 (event-timeline-shaped, not general-purpose).
2. Event Modeling's vocabulary and Given-When-Then reproduction shape --
   reserved for `diagnosing-a-failure`'s own Separate Ways boundary
   (#1155); not reused here even though both skills draw on adjacent
   DDD-community technique families.
3. Applying `clairvoyance`'s full decision-handoff shape (Verdict /
   Evidence / Options / Risks / Reversibility / Next Move) to the whole
   exploratory dialogue rather than just its closing gate -- the
   options are not yet discovered during exploration; premature
   option-crystallization would fight Evans' own finding that models
   "are never perfect; they evolve."
4. Merging `using-clairvoyance`'s own routing layer (to
   `architecture-tradeoff` / `review-verdict` / `decision-coaching` /
   `human-harness`) with `eliciting-a-design`'s downstream routing
   (to `drafting-issues`) -- different layers of concern.
   `using-clairvoyance`'s routing table has no entry for "the idea is
   still underspecified"; named here as an open item for the operator,
   not resolved by this doc (Non-goals).
5. Example Mapping and Impact Mapping as named steps -- both confirmed
   non-DDD lineage (BDD/Cucumber, and UX/outcome-mapping, respectively)
   during this session's research. Noted as adjacent raw material, not
   adopted as explicit named steps: Domain-Driven Transformation's own
   "landscape" framing already positions this skill's adopted set
   (Domain Storytelling, Scenario Casting, EventStorming-adjacent
   ideas) without them, and adding two more named techniques without a
   driving need would be exactly what CLAUDE.md section 4 rules out
   ("No features, abstractions, or configurability beyond what was
   asked").
6. Wardley Mapping and Core Domain Charts -- searched for specifically
   across every Domain-Driven Transformation primary source reached
   this session and not found in any of them; not adopted. Stated as an
   absence-of-evidence finding, not a positive exclusion claim.

## Decision 5: exact sequence and stop boundaries

Consolidated sequence, superseding brainstorming's current nine-step
Process Flow:

1. Explore project context -- unchanged from today's Step 1.
2. Opening convergence via Scenario Casting's pattern (Decision 4, item
   4) -- only when the idea is diffuse or unscoped across many
   stakeholders.
3. Core Domain check (Decision 4, item 6) -- only when the dialogue is
   about to commit heavy custom-modeling effort; if the target scores
   as Generic, search for precedent before proceeding to step 4.
4. Offer the visual companion just-in-time -- unchanged from today's
   Step 2.
5. Ask clarifying questions, one at a time -- Portable Question Handoff
   made explicit (item 7); Domain Storytelling's facilitation patterns
   applied (items 1-2).
6. Propose 2-3 approaches with trade-offs -- unchanged from today's
   Step 4. Any system-level architecture trade-off surfaced here, or at
   any later point, triggers the architecture-trade-off step (item 10)
   inline, not deferred to the end.
7. Fit-and-Gap (item 11) -- only when the idea is a change to an
   existing system, once a candidate approach exists from step 6.
8. Present the design in sections, get approval per section --
   unchanged from today's Step 5.
9. Terminal decision handoff (item 9) -- once every section from step 8
   is stable, close once via `clairvoyance:clairvoyance` (prerequisite)
   or the inline-rendered shape (fallback); Domain Storytelling's
   closing ritual (item 3) is this step's own consensus-check.
10. Write design doc, commit -- unchanged from today's Step 6; depth is
    scaled per item 8's reversible/irreversible vocabulary rather than
    a subjective sense of project size.
11. Spec self-review -- unchanged from today's Step 7.
12. User reviews the written spec -- unchanged from today's Step 8.
13. Terminal handoff: invoke `drafting-issues` if present in the
    consuming repository, else fall back to `drafting-an-acm-issue`
    (today's actual skill) -- redirected from today's `writing-plans`
    target, per #1163's own recommendation, with the same
    prerequisite-plus-fallback idiom used throughout this design.

**Two corrections, found by an isolated `evaluating-skill-quality`
pass, not at design time:**

- **Steps 2 and 3 are swapped from this doc's own original draft**,
  which numbered the Core Domain check as step 2 and Scenario Casting as
  step 3. Scenario Casting decides *what* the dialogue is even about;
  the Core Domain check judges that subject once it exists -- ordering
  them the other way around asked the check to judge a subject Scenario
  Casting had not yet converged on. The shipped `SKILL.md` Checklist
  orders its own items 2 and 3 this way, and this doc's numbering above
  now matches it.
- **A step precedes step 1 in the shipped flow graph with no matching
  number in the 13-item Checklist above:** a "Subject and scope check"
  -- confirm an actual subject exists before opening the checklist
  proper (an empty request, a bare link, a single word does not
  identify something to design), and flag a request spanning
  independent subsystems for decomposition before spending questions
  refining one piece of it. It is written into the Process narrative
  under "Understanding the idea" and the flow graph, not given its own
  Checklist number, because it is a precondition on step 1 rather than
  a step in the design dialogue itself -- the same status the HARD-GATE
  already has.

Stop boundaries: the existing HARD-GATE (no implementation before
design approval) is unchanged. One boundary from this doc's original
draft is unchanged in substance, renumbered to match the swap above:
never skip the Core Domain check (step 3) silently when about to commit
heavy custom-modeling effort -- if skipped, name it as a deliberate
non-check with a stated reason, matching CLAUDE.md section 4's "fail
loudly" rule rather than an empty default. **Extended, found by the same
`evaluating-skill-quality` pass:** a single boundary undersold what the
shipped skill actually needed. Its own "Stopping, Rejecting, and
Escalating" section names seven terminal states, each taking precedence
over "complete them in order" the moment it holds: don't build it (the
Generic-and-precedent-fits result from step 3), cannot determine, a
contradiction in what the user or the project context says, approval
that never arrives after two revision passes, a too-large request whose
decomposition is declined (step 2's own new stop path), an unbridgeable
Fit-and-Gap, and an integrity or trust problem in explored material.
Reaching any of them is a completed run, not an abandoned one -- the
flow graph's "Name the state and stop" terminal, alongside
`drafting-issues` (or its fallback), is where every one of the seven
lands.

## Decision 6: disposition of the six `brainstorming`-reference files

#1258's own Acceptance criteria named this residual risk: renaming may
affect other repository files that reference `brainstorming` by name.
A direct grep found six (excluding `apm_modules/`):

1. `apm.lock.yaml` -- per Decision 1's correction, not regenerated by
   this work: `brainstorming` cannot be removed from `apm.yml` without
   also removing every other still-needed `obra/superpowers` skill, so
   this file is left untouched. Never hand-edited regardless (CLAUDE.md
   section 3: manage modules declaratively).
2. `skills/battle-testing-a-skill/references/provenance-and-caveats.md:87`
   -- **Correction, found during implementation:** re-reading the
   surrounding paragraph shows this line is a Fact statement about
   `obra/superpowers`'s own *upstream* published skill roster
   ("obra/superpowers's published skills and documentation contain no
   discussion of ... its skills (brainstorming, TDD, planning, code
   review) are methodology/workflow content"), not a reference to
   gitapex's own local skill selection. `obra/superpowers` still
   publishes a skill named `brainstorming` upstream regardless of what
   gitapex does locally (Decision 1's correction, above); editing this
   line to say `eliciting-a-design` would make it factually wrong,
   not more accurate. Left untouched.
3. `docs/superpowers/specs/2026-08-05-pytest-ci-performance-design.md`
   -- a dated, already-landed historical design record. Not edited:
   this repository's own established practice treats merged specs as
   point-in-time records, not living docs. **And, on verification, the
   same category as item 2 for a second, independent reason:** its one
   match ("Clarified with the requester during brainstorming") uses the
   ordinary English word, not the skill name -- so there is nothing to
   rename in it either way.
4. `docs/superpowers/specs/2026-07-18-init-hearing-fable-design.md` --
   same disposition as item 3, and the same second reason: its match
   ("brainstorming prevents setting too narrow or too wide a scope")
   likewise names the activity, not the skill -- it paraphrases
   "Brainstorms", one of the Fable field guide's own named techniques,
   which that doc cites in its own header.
5. `AGENTS.md` -- APM-CLI-generated, synced from `tvna/claude-md`; out
   of this repository's direct-edit scope (Scope, above).
6. `CLAUDE.md` -- same disposition as item 5. Both currently reference
   `brainstorming` by name: section 1 ("Use the brainstorming and
   writing-plans skills for the planning procedure when available") and
   section 2 ("The brainstorming skill drives this when available").
   An upstream change request against `tvna/claude-md` is the only
   legitimate path; named here as a residual risk this doc cannot
   close, not silently dropped.

**Revised conclusion:** none of the six files require an in-repository
edit. Item 2's original disposition in this doc's first draft was
itself a mistake, corrected above once its actual subject (an external
package's own roster, not gitapex's local one) was checked rather than
assumed from the word match alone. The rename is achieved entirely by
`skills/eliciting-a-design/` existing and being the more specific,
better-routed match -- not by editing any file that merely mentions
"brainstorming" for an unrelated, still-accurate reason.

## Facts vs. speculation

**Facts, verified this session:** `brainstorming` is vendored from
`obra/superpowers` (`apm.yml:18`) into `.claude/skills/brainstorming/`
(`apm.lock.yaml` lines 328-336, 393-400, 721-793); it is absent from
#1155's own "remaining un-ported mechanisms" enumeration (read
directly from #1155's issue body); six repository files reference
`brainstorming` by name outside `apm_modules/` (grepped this session,
case-insensitive, excluding `apm_modules/`; `.claude/skills/` also
matches but is gitignored, so it holds no repository files -- and the
count is as of before `skills/eliciting-a-design/` existed, so
re-running the same grep today additionally matches this doc plus three
files inside the new skill directory, none of which are dispositions
Decision 6 owes); `apm.yml`'s dependency
list has only package-level granularity, confirmed by running `apm
deps why obra/superpowers` directly this session, which shows the
package as one direct dependency with no per-skill entry -- this
corrects Decision 1's original assumption that `brainstorming` could
be individually removed from `apm.yml`, found during implementation
rather than at design time; `clairvoyance`'s own
`SKILL.md` and `using-clairvoyance`'s own `SKILL.md` and
`architecture-tradeoff`'s own `SKILL.md` (all read directly this
session from `apm_modules/tvna/clairvoyance/skills/`) define the
mechanisms cited above -- **with the attribution tightened on
verification**, since this paragraph originally credited all three
files jointly for all three items. Precisely: all three write "portable
question handoff" (lowercase) as the `AskUserQuestion`-with-plain-text-
fallback mechanism; the reversible/irreversible depth vocabulary is
`using-clairvoyance`'s alone (its "Depth after routing" branch);
`architecture-tradeoff`'s own SKILL.md states its Verdict/Evidence/
Options/Future Story/Premortem/Next Move pattern directly; and the
six-part Verdict/Evidence/Options/Risks/Reversibility/Next Move form
cited for `clairvoyance` is `using-clairvoyance`'s own Examples
rendering of it -- `clairvoyance`'s own SKILL.md lists Reversibility
among its full-handoff headings while its one-line pattern omits it.
`merge-retrospective`'s own prerequisite-plus-
fallback idiom is an established pattern in this repository (per
#1155's own issue comment, itself citing this repository's convention).
The book/technique attributions in Decisions 2-4 (Evans 2003, Vernon
2013/2016, Khononov 2021, Hofer & Schwentner 2021, Lilienthal &
Schwentner 2025, Brandolini 2013, Koch 2018) were each independently
verified against primary sources during this session's own research
dialogue, including three corrections along the way: the book's
authorship (corrected before #1163 was opened), its publisher and
publication date (corrected to Addison-Wesley Professional, English
edition September 2025, superseding an initial "Pragmatic Bookshelf,
~2024" assumption), and Scenario Casting's actual originator (Jorn
Koch, not Lilienthal & Schwentner, who credit but did not create it).

**Speculation, named as such:** Khononov's specific "volatility" axis
(Decision 3) rests on two independent secondary-source paraphrases, not
a directly-quoted primary source -- both `oreilly.com`'s and the
Medium book review's own pages returned an access error when fetched
directly this session. Whether Evans' original 2003 text itself uses
"volatility" as a named axis, or whether that is Khononov's own later
formalization layered onto Evans' looser criteria, is unresolved.
Whether `drafting-issues` will, once implemented, actually match the
shape this doc assumes for Decision 5's step 13 fallback is unverified
-- it does not exist yet. Decision 6, item 6's residual risk (filing an
upstream change request against `tvna/claude-md` for CLAUDE.md sections
1 and 2's `brainstorming` references) remains open regardless of
Decision 1's correction above: whether a router prefers `eliciting-a-
design` over the still-vendored `brainstorming` when both descriptions
are visible is a claim about routing behavior this doc has not directly
observed, only reasoned about from the two descriptions' text.

## Non-goals

- Does not physically remove the vendored `brainstorming` dependency --
  per Decision 1's correction, `apm.yml` has no per-skill exclusion
  mechanism, and removing `obra/superpowers` wholesale would take
  several still-needed skills with it. `skills/eliciting-a-design/`
  itself is implemented as part of the same effort tracked at #1163,
  not deferred by this doc.
- Does not implement `skills/drafting-issues/` -- a separate,
  not-yet-authorized reframe of `drafting-an-acm-issue`.
- Does not modify `using-clairvoyance`'s routing table to add a
  `eliciting-a-design` entry -- Decision 4's rejected item 4 names
  this as an open item for the operator.
- Does not redesign or renegotiate the Separate Ways boundary between
  `eliciting-a-design` and `diagnosing-a-failure` (#1155) -- stated
  as an existing fact in Decision 2, not reopened.
- Does not retire the `obra/superpowers` apm dependency as a whole --
  Decision 1 adds `brainstorming` to the inventory #1155's own
  Non-goals already named as a separate, larger initiative.
- Does not reconcile the separate merge-pipeline-redesign design
  record's own pipeline diagram (referenced by #1163) with this doc's
  Decision 2 Context Mapping table.
- Does not edit `CLAUDE.md` or `AGENTS.md` -- both remain out of this
  repository's direct-edit scope. (`docs/glossary.md` *is* edited, as
  part of the broader #1163 effort and per that issue's own
  Constraints; the Scope section above records why this doc's original
  design-only constraint no longer holds.)

## Acceptance criteria checklist

Mapped to #1258's own six-row Acceptance criteria table, in row order:

- [x] Row 1 (reframe naming/routing): Decision 1 -- working name,
      draft frontmatter description, and retained routing trigger
      stated; Decision 6 dispositions all six files the residual-risk
      column named.
- [x] Row 2 (incorporate DDD/DDT knowledge): Decision 4 -- twelve
      adopted techniques, each with a primary source and an insertion
      point in Decision 5's sequence; six explicitly rejected, each
      with a stated reason.
- [x] Row 3 (distinct from `drafting-issues`): Decision 2's Context
      Mapping table states the relationship (Customer/Supplier,
      provisional) and translation point (Decision 5, step 13)
      explicitly.
- [x] Row 4 (redirect terminal step): Decision 5, step 13 -- fallback
      target (`drafting-an-acm-issue`) and upgrade condition
      (`drafting-issues` existing) both stated.
- [x] Row 5 (integrate `clairvoyance` family): Decision 2's Context
      Mapping table names both integration points; Decision 5, steps 6
      and 9, place them in the sequence with the exact draft text from
      this session's own research dialogue.
- [x] Row 6 (preserve Separate Ways with `diagnosing-a-failure`):
      Decision 2's Context Mapping table cites #1155 directly.

**Follow-up work** (the checked items below were carried out in the same
implementation pass this doc's own corrections to Decisions 1 and 6 were
found in -- tracked at #1163, not in this file, per Scope above; the
unchecked ones remain open):

- [x] Implement `skills/eliciting-a-design/SKILL.md` per Decisions
      1, 4, and 5.
- [x] Confirmed `brainstorming` cannot be removed from `apm.yml` without
      collateral removal of other still-needed `obra/superpowers`
      skills (Decision 1's correction, above) -- `apm.yml` and
      `apm.lock.yaml` are intentionally left untouched, not a
      completed-then-reverted action.
- [x] `skills/battle-testing-a-skill/references/
      provenance-and-caveats.md:87` -- confirmed no edit needed
      (Decision 6, item 2's correction).
- [x] Add `docs/glossary.md` entries for Decision 3's adopted terms.
- [ ] File an upstream change request against `tvna/claude-md` for
      CLAUDE.md sections 1 and 2's `brainstorming` references
      (Decision 6, item 6) -- a different repository, out of this
      change's reach.
- [ ] Operator decision on `using-clairvoyance`'s routing table
      (Decision 4, rejected item 4).
- [ ] Operator or `apm` maintainer decision on whether/how to add
      per-skill exclusion to `apm.yml`, which would let
      `.claude/skills/brainstorming/` actually stop being vendored
      (Decision 1's correction, above) -- currently no such mechanism
      exists.
- [ ] Implement `skills/drafting-issues/` (separate track, referenced
      but not authorized by this doc).

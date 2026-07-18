# A business-domain hearing for `gitapex init` (Fable-style unknowns discovery)

Date: 2026-07-18

Refs #148 (child of #82). Extends #127 (`gitapex init` scaffolding,
whose inputs, outputs, and decision-logic mechanism are resolved and
NOT reopened here -- in particular its explicit DROP of
`business-domain` as a decision-table key, which this design upholds
and builds on rather than reverses) and #147 (security-capability
tiers, a separate, already-resolved axis this design does not
conflate with domain). Checked against all seven #131 zero-trust
principles, with principle 2 (every invocation re-validates its own
inputs) load-bearing. Grounded in one named primary source, read this
session: Anthropic's "A Field Guide to Fable: Finding Your Unknowns"
(the known/unknown quadrant breakdown and the named techniques: Blind
Spot Pass, Brainstorms and prototypes, Interviews, References,
Implementation Plans, Implementation notes, Pitches and explainers,
Quizzes -- and its color-grading worked example, which is this
design's closest analog).

## Design-only scope

Per this repository's discipline (matching #123/#125/#126/#127/#130/
#131/#147 precedent): this doc records a design only. No code, no
`.gitapex/` file, no `scripts/` or `hooks/` change, no edit to
`.gitapex/ssot.schema.json` is made by this pass. Where the design
requires a future artifact (a shipped hearing skill, an advisory
output document), that is a proposal for the implementation issue,
not a change made here.

## Why this doc exists

#127 considered a `business-domain` init input and explicitly dropped
it as a decision-table key, for a stated reason that still stands: an
open-ended taxonomy (fintech/healthcare/gaming/...) is unenumerable
in practice, and gitapex's decision table accepts only closed-enum
lookup keys (F1/F2). What #127 left behind is a stub: business domain
becomes "a post-init advisory step instead, never a gating key,"
whose only proposed use is suggesting #125-style gates -- domain-
relevant governance gates offered as recommendations, never as an
enforced decision-table branch. The stub says WHAT the step is; it
never designed HOW an operator actually gets from "I run a payments
startup" to "here are the domain-relevant gates I should consider."
This doc designs that step.

The reason it needs a real design -- and specifically a Fable-style
one -- is the asymmetry between init's two kinds of question.
`team-size` and `platform` (and, with #147, the `security-tier`
confirm-or-override) are closed-enum FACTS the operator already knows
cold; a plain question suffices, and #127's flow for them is not
Fable-interview territory and is unchanged here. Business domain is
the opposite kind of question. The operator may lack the vocabulary
to describe their own regulatory context, may not know which failure
modes their domain makes expensive, and may not know what a
domain-relevant governance gate would even look like -- classic
unknown unknowns in the source document's quadrant terms ("the
pothole you didn't know the road could have"). The source's
color-grading worked example is the exact shape of this problem: the
author did not understand the domain, did not know what "good" looked
like, and so -- rather than picking from options -- asked Claude to
TEACH them the domain first, explicitly discovering the
unknown-unknown before attempting the task. An operator facing "what
governance does a fintech company need" is in the color-grading
seat, and a flat questionnaire cannot help them. A hearing can.

## The operator's unknowns, in the source's four quadrants

The quadrant breakdown, applied to the domain question. This table is
the skeleton of the staged flow below:

| Quadrant | Domain-flavored instance | Hearing stage that targets it |
|---|---|---|
| Known knowns | "We process card payments; we operate in the EU" -- facts the operator can state | Collected in Stage 2 (Interview) as raw material |
| Known unknowns | "Does PCI DSS apply to this repo? What should our agents never be allowed to touch?" -- questions the operator knows to ask | Stage 2 (Interview) |
| Unknown knowns | "I'd recognize a gate we need if I saw it described, but I can't specify one from scratch" | Stage 3 (Brainstorm) and Stage 5 (draft-advisory prototype -- react, don't specify) |
| Unknown unknowns | "I didn't know output-filtering gates existed / that our domain has a named failure mode others have already encoded" | Stage 1 (Blind Spot Pass -- the color-grading move: teach first) |

By contrast, the existing enum inputs live almost entirely in "known
knowns," which is exactly why they never needed this machinery and do
not get it: this design is additive, a new discovery layer behind
#127's questionnaire, not a redesign of it.

## Decision 1: advisory-only output; `business-domain` stays dropped as a gating key

**Decision: the hearing's entire output is advisory prose -- a
recommendation document proposing domain-relevant #125-style gates and
considerations for the operator to accept, adapt, or reject through
the normal governed authoring path. Business domain contributes zero
decision-table keys, zero schema fields, zero free text to any
generated artifact, and zero enforced state. This upholds #127's
already-argued drop; it does not quietly revisit it.**

The revisit was considered as a real option and is rejected
explicitly, not skipped:

- *Rejected: reverse #127 and add `business-domain` as a closed-enum
  decision-table key.* #127's stated reason -- the taxonomy is
  unenumerable in practice -- is not merely still true; the source
  document sharpens it. Domains are precisely where operators carry
  unknown unknowns, so a closed enum would force the operator to
  self-classify BEFORE any discovery has happened -- the enum answer
  would be least reliable exactly when the input matters most, and a
  wrong self-classification would silently select enforced
  decision-table output. It also trips both of F2's named
  re-evaluation triggers at once: domain-conditional scaffolding is
  adopter-varying logic, and any honest domain taxonomy blows past
  the ~20-row budget (#147 already spent the headroom down to ~12
  rows for the tier axis). Fail-closed (#131 principle 6) seals it:
  an operator whose domain is not in the enum would hit the mandatory
  default row -- collapsing every unlisted domain into one bucket,
  which is the unenumerability problem wearing an enum costume.
- *Rejected: a coarse middle-ground enum (e.g. `regulated |
  unregulated`).* Two-value taxonomies of an unenumerable space keep
  the self-classification failure mode and add almost no information:
  #147's `security-tier` already carries "how much depth should the
  harness have," which is the only scaffold-affecting bit such a
  coarse enum could encode. The hearing's actual value is the
  SPECIFIC gate suggestions ("card-data paths want an
  output-filtering gate"), which no enum of any coarseness can carry.
  Discovered depth-relevant facts have a landing spot already: the
  operator's #147 tier election.
- *Rejected: recording hearing output (domain label, transcript,
  notes) in `.gitapex/ssot.json`.* Direct F1 violation -- free text
  reaching generated JSON -- and a schema change beyond #147's single
  proposed `security_tier` field. The prose has a home (the advisory
  document and the PR record, Stages 5-6), and that home is ordinary
  reviewed content flowing through the merge gate, never
  binary-emitted, never machine-read.

The enforcement path for an accepted recommendation is deliberately
boring and already exists: the operator (or their agent, at their
direction) authors the suggested gate as a normal adopter-authored
`.rego` policy under #125's model, registers it in
`.gitapex/ssot.json` through the merge-gated review path like any
other governed change, with its own issue per this repo's discipline.
The hearing recommends; the merge gate enacts. Nothing becomes
enforced because a conversation said so.

## Decision 2: where the hearing runs

**Decision: the hearing is conducted by the agent harness that invokes
gitapex (Claude Code or equivalent), following a shipped hearing
skill. There is NO CLI-native hearing, degraded or otherwise -- and
unlike the enum questions, there cannot honestly be one: a hearing
over an unenumerable answer space has no closed-choice questionnaire
form, by #127's own unenumerability argument. The binary's whole role
is a static pointer. Git hook, Claude-Code hook subprocess, CI, and
MCP contexts get no hearing at all.**

The grounding fact, stated plainly: **gitapex is a static Rust binary
with no model runtime. It cannot conduct an interview, and for THIS
subject it cannot even ask the question** -- "what is your business
domain and what follows from it" has no enum answer to validate, so a
scripted prompt sequence (which worked as a degraded form for the
enum inputs) is not available here even in principle. This is worth
contrasting with the enum questions to avoid a false symmetry: for
`team-size`, a TTY prompt is a complete non-agent fallback; for
domain discovery, the honest non-agent fallback is "none," and this
doc says so rather than inventing a questionnaire that would fake it.

Per invocation context:

| Context | Hearing? | Who conducts | Notes |
|---|---|---|---|
| Agent harness session (gitapex installed as a Claude Code plugin per the toolchain-bootstrap design; operator initializes gitapex through the agent) | Yes -- the full hearing, post-init per #127's stub | The harness agent, following a shipped hearing skill (a `SKILL.md`-class artifact distributed with the plugin per the 2026-07-12 skill-distribution foundation design: a repo-owned, merge-gated instruction file, trusted via the adopter's install choice, and data the binary itself never reads) | The only context where the hearing exists. Its output is prose; the binary never consumes it (#131 principle 2 has nothing to re-validate because nothing crosses into the binary). |
| Operator terminal (interactive `gitapex init`, #127's primary init context) | No hearing | -- | The binary emits a static pointer: one compiled-in notice (immutable per release, like the decision table) in init's output and in #147's posture report -- "domain-relevant gates are not scaffolded; run the domain hearing from an agent session, or author #125 gates directly." Pointer text is static; no operator input is solicited. |
| Claude-Code hook subprocess (PreToolUse/Stop/etc.) | No | -- | A hook subprocess has no conversational turn to hold a hearing in; the hearing is a session-level activity in the harness conversation. |
| Git hook subprocess | No | -- | Non-interactive; no init-time hearing surface of any kind. |
| CI job step | No | -- | Non-interactive path, unchanged (below). |
| MCP server subprocess (stdio, #126 -- least trusted) | No hearing on gitapex's side | An MCP client may hold whatever conversation it likes on its own side; gitapex neither knows nor cares | Per #131 principles 1-2, a client-side conversation earns zero trust; whatever the client concluded, the only things gitapex ever accepts remain #127's validated inputs. |

The trust argument is short because the interface is so narrow.
Assume the hearing agent is compromised, or steered by adversarial
text it ingested (a poisoned reference repo, an injected issue body)
-- #131 principle 4. What can it reach? The hearing's output is a
prose recommendation document. It writes no generated config, selects
no decision-table row, and confers no enforcement; a malicious
recommendation must still survive the operator's review and the
merge-gated policy-authoring path (with CODEOWNERS,
`bypass_actors: []`, and required review -- #127's floors) before any
gate exists. The blast radius of a fully adversarial hearing is a bad
suggestion in a document a human reviews -- which is the same blast
radius as any untrusted text this repo's CLAUDE.md section 2 already
governs, and the hearing skill instructs the agent to treat all
reference material it reads during the hearing as untrusted data
accordingly.

## The staged hearing flow

Runs post-init (per #127's stub placement: the scaffold from init's
resolved flow -- enum questions, dry-run, apply, posture report --
completes first, unchanged; the hearing then addresses what the
scaffold deliberately does not cover). Stages 1-6, agent context
only.

### Stage 1 -- Blind Spot Pass: teach the domain-governance space first

The source's Blind Spot Pass, by that name, in its color-grading
form: teach before asking. The operator most in need of this stage
cannot yet react usefully to gate suggestions because they do not
know what a governance gate can do or what their domain's named
failure modes are -- asking them to choose now would be the source's
anti-pattern (producing variations for someone who does not yet know
what "good" looks like). So the agent first builds the operator's map:

- What #125-style gates ARE and the kinds of things they can govern
  in this repo's designs (path-scoped controls, output filtering,
  untrusted-text advisories, ingestion budgets -- whatever the
  adopter's installed designs actually support; the skill instructs
  the agent to ground this in the shipped design docs, not memory).
- What is already known about the operator's likely domain from
  observable evidence, offered as prompts, not conclusions: the agent
  may read the repo itself (dependency manifests, service names,
  data-model files) and say "I see payment-provider SDKs and an
  `invoices` module -- does card data transit this codebase?" --
  turning silent evidence into a question the operator can confirm or
  correct. Evidence read this way is untrusted data grounding a
  QUESTION; it never becomes an asserted classification.
- The vocabulary the operator is missing: named regulatory frames and
  domain failure modes, introduced as candidates to react to ("does
  any of this sound like your world?"), with the agent explicit that
  it is teaching a landscape, not issuing a compliance determination
  (see limits).

The stage ends when the operator can articulate, in their own words,
what their domain is and why it might care about governance -- the
precondition the source's worked example establishes before any task
execution.

### Stage 2 -- Interview: one question at a time, answer-changes-the-recommendation first

The source's Interviews technique, with its prioritization rule
translated: "prioritize questions where my answer would change the
architecture" becomes **prioritize questions where the answer would
change the recommended gate set**. Concretely, questions of the
shape: what data classes does this repo's code touch (payments, PHI,
minors' data, user-generated content)? Which jurisdictions? What
would a bad merge cost here -- money moved, records exposed, safety
harm? What may agents never do in this repo, in the operator's own
words? Prior incidents? The interview collects the operator's known
knowns and resolves their known unknowns into stated facts and
stated open questions -- the raw material for Stage 3 -- and per the
source, one question at a time, not a form.

### Stage 3 -- Brainstorm: candidate gates, cheapest to most ambitious

The source's Brainstorms technique, near-verbatim in its churn
example's shape: "search the codebase and brainstorm N candidate
domain gates we could add, from cheapest to most ambitious. I'll
tell you which ones resonate." The agent proposes concrete candidate
gates grounded in Stages 1-2 (e.g., for a payments domain: an
output-filtering gate on card-data-shaped strings in governed paths;
for a health domain: a data-handling advisory gate on files matching
the repo's records module), each with what it would govern, what it
would cost, and what it would NOT catch. This is the unknown-knowns
stage: the operator recognizes "yes, that one" from candidates they
could never have specified cold. The source's scope warning applies
and the skill encodes it: brainstorming prevents setting too narrow
or too wide a scope -- the candidate list deliberately spans the
cheap-to-ambitious range rather than anchoring on one idea.

### Stage 4 -- References (optional): an exemplar adopter's gates

The source's References technique: when the operator cannot
articulate what they want, point at an artifact that embodies it.
Domain-flavored: the operator points the agent at a sibling or
exemplar repo's `.gitapex/ssot.json` and `.rego` gates ("the
platform team's payments repo already solved this") and the agent
reads the actual policy source -- the source document's point that
code beats screenshots applies directly: the gate's real semantics,
not its description. Justified because multi-repo orgs adopting
domain gates repo-by-repo are the expected `org-scale` path, and
"like that repo" is often the operator's entire articulable
requirement. Zero-trust framing: the reference is untrusted data read
for reasoning; nothing is copied into any generated artifact, and a
recommendation derived from it still lands as a reviewed suggestion
in Stage 5's draft, nothing more.

### Stage 5 -- Prototype: the draft advisory, reacted to before anything lands

The source's Brainstorms-and-prototypes commitment rule ("I want to
react to the layout before you touch the real app") and its
Implementation Plans ordering, applied to the hearing's one
deliverable: the agent drafts the advisory document -- the
recommended gate set with rationale -- and presents it for reaction
BEFORE any issue is opened or any `.rego` line is written, ordered
likely-to-tweak-first: the domain characterization and the
recommended gates up top (the parts the operator's reaction will
change), mechanical detail (candidate gate wiring, `policy_sources[]`
registration steps) at the bottom. Where a candidate gate's behavior
is hard to grasp in prose, the agent may sketch the gate (a draft
`.rego` shown inline as illustration) -- explicitly a prototype to
react to, not authored into the repo by the hearing. Reaction loops
back to Stage 3 cheaply, because nothing has landed. Note what this
stage deliberately does NOT reuse: #127's dry-run-first apply flow
diffs generated platform state, which the hearing never touches --
the advisory draft is the hearing's own prototype surface, and
claiming the init dry-run here would be a false reuse.

### Stage 6 -- Quiz, then the record: understanding before adoption

The source's Quizzes technique, aimed at the one misunderstanding
that would hurt most: **an operator who walks away believing the
recommended gates are now active.** After the draft is accepted, the
agent quizzes the operator on the advisory/enforced boundary --
questions of the shape "which of these recommendations is enforced
right now?" (correct answer: none; every recommendation is inert
until authored, reviewed, and merged as a #125 gate through the
normal path) and "what has to happen before recommendation X stops
being words?" This is the same honesty boundary #147's posture
report draws with `configure`/`recommend`/`not covered`, and the
advisory document states it in those terms: every hearing output is
`recommend`-class by construction.

Enforcement honesty, stated bluntly: the binary cannot grade a quiz,
and quiz passage is not machine-verifiable state -- the quiz is
advisory pedagogy, available only where an agent exists, which for
this flow is everywhere the hearing exists at all. The deterministic
backstop is structural rather than a new gate: since the hearing
enacts nothing, there is no acceptance step to guard -- the
merge-gated review of any later gate-authoring PR is the enforcement
point, and it already exists.

Then the source's Implementation-notes and Pitches-and-explainers
close: the agent packages the hearing record -- the domain
characterization in the operator's words, the recommended gates with
rationale, the rejected candidates and why, and open questions the
hearing could not resolve -- into (a) the advisory document itself
and (b) the body of each issue opened for an accepted
recommendation (one issue per gate, per this repo's
issue-before-branch discipline), so the eventual gate PR's reviewers
start with the operator's unknowns already answered -- the source's
stated purpose for the technique, and CLAUDE.md section 6's
decision-brief requirement met by the same artifact. F1 note: all of
this is prose authored through ordinary review, never binary-emitted,
never machine-read; no free text has entered any generated artifact.

## Technique-to-stage map (source coverage, at a glance)

| Fable technique (source's name) | Hearing translation | Stage |
|---|---|---|
| Blind Spot Pass | Teach the domain-governance space first (color-grading move); evidence-grounded questions from the repo itself | 1 |
| Interviews | One-question-at-a-time domain facts, prioritized by would-change-the-recommendation | 2 |
| Brainstorms and prototypes | Candidate gate list, cheapest to most ambitious, operator reacts | 3 |
| References | Exemplar repo's actual gate source read as untrusted reasoning aid | 4 |
| Implementation Plans | Draft advisory ordered likely-to-tweak-first | 5 |
| Quizzes | Operator quizzed on the advisory/enforced boundary before adoption | 6 |
| Implementation notes | Hearing decisions, rejected candidates, and open questions logged in the record | 6 |
| Pitches and explainers | Record packaged into the advisory doc and per-gate issue bodies for reviewer buy-in | 6 |

## Non-interactive and CI behavior

A non-interactive run (CI, git hook, MCP, or any invocation without
an agent session) gets no hearing and no hearing-derived state --
and, because the hearing is advisory-only, this costs nothing in
enforced posture: init's output for a given flag set is identical
whether or not a hearing ever ran. #147's non-interactive rule is
unchanged and untouched (missing tier flag means `foundation`, never
silently higher or lower); the hearing neither reads nor writes
anything that rule depends on. **Flag invariance -- same flags, same
scaffold, hearing or not -- is the checkable form of
"advisory-only."** The static pointer (Decision 2) is the only trace
of the hearing's existence in non-agent contexts, and it is
identical text in every run.

On re-init: unchanged from #127/#147 (per-change monotonicity
against live platform state, widening blocks). A re-run of the
hearing is legitimate when the domain changes (new product line, new
jurisdiction) and produces a new advisory document through the same
stages; it interacts with re-init not at all, because it still
enacts nothing.

## What the hearing cannot do (limits, stated plainly)

- **It cannot run without an agent, and no degraded CLI form exists
  or is faked.** The unenumerable answer space that disqualified
  `business-domain` as an enum (#127) equally disqualifies a scripted
  questionnaire; a static binary can neither conduct nor meaningfully
  begin this conversation. The binary's role is one static pointer.
- **It elicits and hypothesizes; it does not detect or determine.**
  No mechanism here detects the operator's regulatory obligations.
  The agent's domain knowledge may be wrong, stale, or
  jurisdiction-blind; every regulatory statement in the hearing is a
  candidate for the operator to verify, and the advisory document
  says so on its face. The hearing is explicitly NOT a compliance
  determination, and the skill forbids the agent to present it as
  one -- an aspirational "the hearing ensures compliance coverage"
  claim has no backing mechanism and is not made.
- **Its output enforces nothing.** Every recommendation is
  `recommend`-class by construction; the distance from
  recommendation to enforcement is the full governed authoring path
  (issue, `.rego`, registration, review, merge), on purpose.
- **Repo evidence grounds questions, not classifications.** Reading
  dependency manifests can prompt "does card data transit here?"; it
  cannot conclude "this is a fintech repo" -- asserted-over-verified
  in the other direction (#131 principle 5 applied to the agent's
  own outputs).
- **Quiz passage is not machine-verifiable.** The binary can verify
  nothing about the operator's understanding; the quiz's value is
  pedagogical, and the real gate on any consequence is the later
  PR review.

## Facts vs. speculation

Facts: #127's resolved inputs, outputs, F1-F6, the dropped
`business-domain` input with its stated unenumerability reasoning,
and its post-init-advisory-step stub with suggested-#125-gates as
the stub's only proposed use; #131's seven principles and the four
invocation contexts; #147's tier axis, posture report, honesty
classes, and non-interactive `foundation` default; the source
document's techniques, quadrants, and color-grading worked example
as quoted; the toolchain-bootstrap precondition (2026-07-14 design)
and the skill-distribution foundation design (2026-07-12) as the
hearing skill's shipping channel; #125's adopter-authored `.rego`
gate model as the enforcement path for accepted recommendations.

Speculation, named as such: the exact packaging and name of the
hearing skill, and of the advisory document (filename, whether it
lives beside the posture report), are implementation-issue
decisions; the static pointer's exact wording and placement
likewise; which gate capabilities exist for Stage 3 to draw on
depends on which #125-family designs the adopter's gitapex version
actually ships (the skill grounds the brainstorm in the shipped
docs at hearing time rather than this doc fixing a list); whether
per-gate issues are opened by the agent or the operator is a
workflow choice for the implementation issue.

## Non-goals

- No code, no `.gitapex/` files, no `scripts/` or `hooks/` edits, no
  change to `.gitapex/ssot.schema.json` -- design only. The hearing
  skill, advisory document, and static pointer are proposed, not
  built.
- Not reversing #127's drop of `business-domain` as a gating key --
  the drop is upheld and its reasoning extended (Decision 1); no
  domain value becomes a decision-table key, schema field, or any
  machine-read state.
- Not redesigning the `team-size`/`platform`/`security-tier` flow:
  those remain #127/#147's simple confirm-detected-value questions,
  which are known-knowns territory and need no hearing. This design
  is a new additive layer behind them.
- Not conflating domain with tier: #147's security-tier axis stands
  as-is. The hearing may incidentally leave the operator better
  equipped for their tier election, but tier election is not the
  hearing's subject, output, or mechanism.
- Not authoring gates: the hearing recommends; #125's normal governed
  authoring path (with its own issues, review, and merge gate)
  enacts. No hearing output is enforced state.
- Not a compliance service: no claim of detecting, determining, or
  ensuring regulatory coverage is made anywhere in the design.
- No new enforcement gates and no new schema: the only proposed
  artifacts are advisory (skill, document, pointer text).

## Acceptance criteria

- [ ] The hearing's subject is business-domain discovery, and the
      design's stages target the domain question's unknown quadrants
      (the quadrant table is domain-flavored, with the color-grading
      teach-first move as Stage 1's explicit model); the enum inputs
      are explicitly out of hearing scope as known-knowns.
- [ ] Decision 1 upholds #127's dropped-input reasoning with the
      reversal considered and rejected as a real option (argued
      against unenumerability, both F2 triggers, the ~20-row budget,
      and the fail-closed default-row collapse), plus the
      coarse-enum and record-in-ssot alternatives rejected
      explicitly -- not silently.
- [ ] The output is advisory-only end to end: recommendations reach
      enforcement only via #125's merge-gated authoring path, and
      flag invariance (same flags, same scaffold, hearing or not) is
      stated as the checkable property.
- [ ] Decision 2 names the conductor (harness agent via shipped
      skill), states plainly that the static binary cannot conduct
      -- or for this subject even ask -- the hearing, assigns no
      hearing to terminal/git-hook/Claude-Code-hook/CI/MCP contexts,
      and honestly declines to invent a degraded CLI questionnaire
      (contrasting with the enum questions where a TTY prompt IS a
      complete fallback).
- [ ] Every stage maps to a named source technique (the
      technique-to-stage table is total over the source's list), and
      the deliberate NON-reuse of #127's dry-run flow in Stage 5 is
      stated with its reason (the hearing never touches generated
      platform state).
- [ ] The Stage 6 quiz targets the advisory/enforced boundary, its
      non-machine-verifiability is stated, and the enforcement point
      is identified as the existing PR review of any later
      gate-authoring change -- no new gate invented.
- [ ] The bounded-blast-radius argument for a compromised or steered
      hearing agent is stated (prose-only output, human review, the
      merge gate and floors between recommendation and enforcement),
      and reference material read during the hearing is governed as
      untrusted data.
- [ ] Every limit is stated plainly (elicits-not-detects, not a
      compliance determination, agent knowledge fallible,
      evidence-grounds-questions-not-classifications, no CLI form,
      quiz unverifiable), with no aspirational claim lacking a
      mechanism.
- [ ] Non-interactive behavior is stated: no hearing, no
      hearing-derived state, #147's defaults untouched, identical
      static pointer text in every run.

## Related Issue

Child of #82. Extends #127 and #147. Refs #148.

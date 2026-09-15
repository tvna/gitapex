# Criteria: grounding and per-channel notes

This file assumes `SKILL.md`'s five criterion definitions are already
known to the reader; nothing below restates a criterion's own definition.
What follows is per-channel application notes plus the primary-source
grounding for why each criterion exists, matching the split
`evaluating-skill-quality/references/rubric.md` uses for its own nine
dimensions. The two axis-group sections further below carry the same
split for `SKILL.md`'s channel-namespaced axes, and additionally state,
for each axis, whether its basis is a primary-source quote or a
gitapex-owned convention.

Both primary sources below were fetched directly and read in full before
any passage was quoted; no quote here is from memory or a secondary
summary.

## Table of contents

- [1. Ownership and review gating](#1-ownership-and-review-gating)
- [2. Bounded growth](#2-bounded-growth)
- [3. Placement and disclosure fit](#3-placement-and-disclosure-fit)
- [4. Enforcement-fit](#4-enforcement-fit)
- [5. Provenance and adversarial independence](#5-provenance-and-adversarial-independence)
- [Axis group A: project-instruction channel](#axis-group-a-project-instruction-channel)
  - [A1 content derivability](#a1-content-derivability)
  - [A2 always-loaded justification](#a2-always-loaded-justification)
  - [A3 dispatch multiplier](#a3-dispatch-multiplier)
  - [A4 over-specification](#a4-over-specification)
- [Axis group B: subagent definitions](#axis-group-b-subagent-definitions)
  - [B1 description trigger purity](#b1-description-trigger-purity)
  - [B2 detail placement](#b2-detail-placement)
  - [B3 roster size](#b3-roster-size)
  - [B4 cross-runtime tool-boundary parity](#b4-cross-runtime-tool-boundary-parity)
- [Sources considered and not used](#sources-considered-and-not-used)
- [References](#references)

## 1. Ownership and review gating

Grounded in [Steering Claude Code][steering], on CLAUDE.md specifically:
"In a shared repository, CLAUDE.md grows the way any unowned config file
does: every team appends its own instructions and nothing gets deleted.
The cost compounds at scale." The article's own stated fix: "Keep
CLAUDE.md under 200 lines, give it an owner, and review changes to it
like code."

Applied here: the failure is not the file's existence but the absence of
a single accountable owner and a review gate equivalent to a code review
-- the same absence that lets any shared, unowned artifact drift.

*Channel notes:*

- **CLAUDE.md (root/subdirectory)**: does a specific person or team own
  the file, and does every change land through the repository's normal
  pull-request review, or can any contributor push directly? A
  generated/synced CLAUDE.md (produced from an external source of truth)
  shifts the question upstream: is *that* source under equivalent review,
  or does the generated file merely look reviewed because it is
  committed?

- **Subagent definitions / Output styles / system-prompt-append
  configuration**: typically single-owner by construction (one file, one
  narrow purpose); ownership is usually satisfied trivially by the
  repository's existing review process, and this criterion more often
  reports PASS by default here than for CLAUDE.md or Auto-memory -- but
  confirm rather than assume, since a large `.claude/agents/` directory
  can still accumulate redundant or stale definitions the same way an
  unowned CLAUDE.md does.

- **Auto-memory**: per [The new rules of context engineering][context-eng],
  memory is now written automatically rather than through an explicit,
  reviewed edit ("Claude now automatically saves memories that are
  relevant to the work and to you"). This removes the review gate a
  manual CLAUDE.md edit would have passed through; the criterion asks
  whether any curation policy (periodic pruning, human confirmation
  before a memory is retained long-term) exists to substitute for the
  review step automation removed.

## 2. Bounded growth

Grounded in the same [Steering Claude Code][steering] passage as
criterion 1: "The cost compounds at scale. Every line loads into every
session for every engineer working in the repo, whether it's relevant to
their task or not." The article's own numeric target: "Keep CLAUDE.md
under 200 lines."

Applied here: this criterion grades whether a bound exists and holds, not
merely whether the channel is currently small -- a channel with no target
at all can still be small today and unbounded in trend.

*Channel notes:*

- **CLAUDE.md (root/subdirectory)**: compare current line count against
  an explicit target (200 lines, per the article's own tip, absent a
  stricter locally-declared target) and, where history is available,
  check the trend across recent revisions rather than a single snapshot.

- **Auto-memory**: does the store (or its retrieval mechanism) apply any
  age-based or relevance-based pruning, or does every session's memory
  persist indefinitely? [The new rules of context engineering][context-eng]
  does not itself specify a bound for Auto-memory, which is itself a
  finding worth naming if no locally-declared bound exists either -- an
  unstated bound is not itself evidence that one exists.

- **Subagent definitions / Output styles / system-prompt-append
  configuration**: usually not-applicable, per the same reasoning as
  criterion 1's channel notes -- report so explicitly rather than
  omitting the criterion.

## 3. Placement and disclosure fit

Grounded in [Steering Claude Code][steering]'s own comparison table and
its explicit worked example: "A 30-line procedure in CLAUDE.md.
Procedures belong in skills. CLAUDE.md is for facts Claude should hold
all the time... A deployment runbook or a security review checklist
should live in `.claude/skills/`, where the body loads only when
invoked." Reinforced by [The new rules of context engineering][context-eng]:
"consider having a tree of files that can be loaded at the right time,"
contrasted with the "put it all upfront" pattern it names as outdated.

Applied here: this criterion has two parts, and both must be checked --
(a) is the content loaded at the right granularity for its own relevance
scope (root vs. subdirectory CLAUDE.md; one file vs. several), and (b) is
it in the right channel at all, including whether it should have been a
skill instead.

*Channel notes:*

- **CLAUDE.md (root)**: content relevant only to one subdirectory or
  workflow, paying the root file's always-loaded tax, is the canonical
  (a)-failure; a multi-step procedure with branches (not a short fact) is
  the canonical (b)-failure.

- **CLAUDE.md (subdirectory)**: the (a) question is usually already
  satisfied by construction (the mechanism itself scopes loading to the
  subdirectory); check the (b) question -- is subdirectory-scoped
  procedural content that should be a skill instead sitting here because
  it was easier to add to an existing file.

- **Subagents**: per [Steering Claude Code][steering], "use a subagent
  when a side task... would clutter your main conversation with
  intermediate results you won't reference again... Use a skill when you
  want the procedure to play out inside the main thread so you can see
  and steer each step." A subagent whose own task is not actually
  isolation-worthy (its intermediate steps are exactly what a human
  wants to steer) is a (b)-failure in the opposite direction from
  CLAUDE.md's.

- **Output styles / system-prompt-append**: per the same source, output
  styles are for "significant role changes" and system-prompt-append for
  "tone, response length, formatting preferences" -- narrow, specific
  content masquerading as either (a large embedded procedure; a role
  change smuggled into a system-prompt-append flag meant only for tone)
  is the failure to check for.

- **Auto-memory**: this mechanism has no meaningful (a) failure mode of
  its own (retrieval timing is automatic, not author-controlled); check
  only whether memory content that is actually a reusable procedure
  (better served by a skill) is accumulating there instead, unreachable
  to anyone who has not personally triggered its recall.

## 4. Enforcement-fit

Grounded in [Steering Claude Code][steering]'s own explicit rule:
`"Never do this" in CLAUDE.md. When there's something that absolutely must not happen, an instruction is the wrong tool. Claude will follow the instruction most of the time, but when under pressure, in a long session or an ambiguous situation, or due to a prompt injection in a file accessed as part of the task, the model can fail to follow a prompted rule. A real guardrail needs to be deterministic, and the enforcement methods are hooks and permissions.`

Applied here: a channel in this skill's own scope stating an absolute
prohibition, with no corresponding hook or permission actually
implementing it, is a finding regardless of how forcefully the
prohibition is worded -- wording strength is not a substitute for
deterministic backing, and confirming the backing means checking the
harness's own actual hook/permission configuration, not the channel's own
claim about itself.

*Channel notes:*

- **CLAUDE.md**: an absolute "NEVER" bullet with no matching entry in the
  harness's own hooks manifest (or an equivalent deterministic
  permission) is the canonical failure; a "NEVER" bullet that the
  channel's own text correctly scopes as advisory-only, or that a
  confirmed hook does back, both pass.

- **Subagents**: a subagent definition's own frontmatter can carry real,
  structural backing beyond prose -- a `disallowedTools` restriction, or
  an embedded lifecycle hook scoped to that subagent alone. Where a
  subagent's description asserts an absolute restriction, check for this
  structural backing specifically, not only a repository-wide hooks
  manifest; a subagent whose only backing is its own prose description of
  what it "never" does has the identical failure this criterion catches
  in CLAUDE.md.

- **Output styles / system-prompt-append**: per
  [Steering Claude Code][steering], output styles "carry the highest
  instruction-following weight of any method... covered so far," but
  still never compile to deterministic enforcement; an absolute
  prohibition placed here has the same unbacked-guardrail failure as one
  placed in CLAUDE.md, dressed in a higher-authority channel.

- **Auto-memory**: a memory instructing future sessions to always or
  never do something functions exactly like an unbacked CLAUDE.md
  "NEVER" bullet, with the added complication that it was not authored
  through any reviewed process (criterion 1) -- both findings can and
  usually do co-occur here.

## 5. Provenance and adversarial independence

Grounded in [The new rules of context engineering][context-eng]'s own
description of Auto-memory: "Claude now automatically saves memories that
are relevant to the work and to you" -- replacing the earlier, explicitly
user-initiated pattern ("using the `#` hotkey to write to their CLAUDE.md
automatically"). Reinforced by [Steering Claude Code][steering]'s own
framing of CLAUDE.md as a file "any team" can append to, with "nothing...
deleted."

Applied here: automatic, unreviewed writing is exactly what removes the
adversarial independence a channel needs between whoever writes its
content and whoever it later steers -- the more automatic the write path,
the more directly this criterion applies, and Auto-memory's own defining
property (writes with no explicit user action) makes it the mechanism
where this criterion bites hardest.

*Channel notes:*

- **Auto-memory**: can a session whose own input was steered by hostile
  content (a prompt injection encountered while reading an untrusted
  file, an adversarial instruction embedded in fetched content) cause a
  memory to be saved that later silently influences an unrelated
  session's behavior? This is the sharpest instance of this criterion
  across all five channels, and the one with no sibling-skill coverage
  today.

- **CLAUDE.md**: can the same contributor whose future work the file is
  meant to constrain also add or edit the constraining text, with no
  independent reviewer in the path? This mirrors this lineage's own
  predecessor's criterion for gate-feeding state (a deployer able to edit
  the metrics store a release gate reads), applied here to an advisory
  channel instead of a deny path.

- **Subagents / Output styles / system-prompt-append**: usually satisfied
  by the repository's ordinary review process (criterion 1), since these
  channels are not automatically written the way Auto-memory is; check
  specifically whether a subagent or output style can be modified by
  content the subagent itself processes (for example, a subagent that
  writes back to its own definition file) rather than only by a human
  reviewer.

## Axis group A: project-instruction channel

These four axes apply only when the target is a CLAUDE.md, AGENTS.md, or
equivalent always-loaded project-instruction file. `SKILL.md` carries
each axis's one-sentence rule; what follows is the application note and
the basis, and nothing below restates a rule already stated there.

Basis labels used throughout this section and the next: *primary-source-quotable*
means the axis's rule is covered by a passage already quoted verbatim
elsewhere in this file, repeated here with its link reference;
*gitapex-owned convention* means no such passage covers it and the axis
was decided in this repository under
<https://github.com/tvna/gitapex/issues/1963> (stage 1:
<https://github.com/tvna/gitapex/issues/1986>), with no external primary
source claimed for it. Every axis below labelled a gitapex-owned
convention was decided there; the label alone carries that provenance and
no axis repeats it. A gitapex-owned convention is not a weaker axis -- it
is an honestly labelled one.

### A1 content derivability

*Application:* read each clause against what the repository already
shows. A clause restating the directory layout, a README statement, a
build command discoverable from the manifest, or behavior legible in the
code is derivable and earns deletion, not rewording. The test is whether
a competent reader with the repository open would reach the same
conclusion without the clause; a clause that only *summarizes* the
repository faster is still derivable.

*Basis:* **gitapex-owned convention.** No passage quoted in this file
distinguishes derivable from non-derivable content.

### A2 always-loaded justification

*Application:* for each retained clause, ask what breaks if it loaded on
demand instead. A clause that steers only one workflow, one
subdirectory, or one recurring task has an on-demand home and fails this
axis; a clause the model must hold in every turn to avoid a wrong default
passes. This axis grades the justification, not the clause's correctness.

*Basis:* **primary-source-quotable.** [Steering Claude Code][steering] on
the always-loaded cost: "The cost compounds at scale. Every line loads
into every session for every engineer working in the repo, whether it's
relevant to their task or not," and on what the channel is for:
"CLAUDE.md is for facts Claude should hold all the time." The load-on-demand
alternative is named by [The new rules of context engineering][context-eng]:
"consider having a tree of files that can be loaded at the right time."
Each of these three passages is quoted verbatim in criteria 2 and 3
above; none is newly introduced here.

### A3 dispatch multiplier

*Application:* count the dispatches, not only the lines. Where the
harness re-loads the project-instruction file into each non-fork subagent
dispatch, a session that dispatches ten subagents pays the file ten times
over plus once for the main thread. Confirm the harness's own actual
dispatch behavior before applying the multiplier -- a fork-style dispatch
that inherits an already-loaded context does not re-charge, and assuming
either behavior without checking is itself a finding.

*Basis:* **gitapex-owned convention.** No passage quoted in this file
addresses subagent dispatch re-charging a project-instruction file; the
quoted cost passage under A2 counts sessions and engineers, not
dispatches, and extending it to dispatches would be an extrapolation this
file does not make.

### A4 over-specification

*Application:* the fix is a shorter clause carrying the same rule, which
is distinct from criterion 3's fix of moving the content to another
channel entirely. Both can apply to one clause, and are reported
separately.

*Basis:* **gitapex-owned convention.** The nearest quoted passage,
criterion 3's "A 30-line procedure in CLAUDE.md. Procedures belong in
skills," is about relocating procedural content, not about compressing a
rule that correctly stays. No quoted passage covers over-specification of
retained content.

## Axis group B: subagent definitions

These four axes apply only when the target is a subagent definition
(`.claude/agents/*.md`, `agents/*.md`, or equivalent). The same split
applies: `SKILL.md` carries each rule, this section the application note
and the basis.

### B1 description trigger purity

*Application:* read the description alone, as a router would. Every
sentence that is not routing information -- decision numbers, issue
references, authoring notes about why the file is written the way it is,
rationale, and detail duplicated from the body -- is slop and is deleted,
because the description rides in every routing request whether or not the
subagent is dispatched. Where the real problem is that the triggers
themselves do not cohere, the answer is that the caller takes
responsibility for routing, or the subagent is split into two, never that
the description explains itself at greater length. This axis is
qualitative: a character cap is not a substitute for it, because a
trigger-only description lands well below any cap a reviewer would set,
and a capped description full of rationale still fails.

*Basis:* **gitapex-owned convention.** [Steering Claude Code][steering]'s
quoted subagent passage under criterion 3 says when to use a subagent at
all; no passage quoted in this file says what a subagent's description
field may contain.

### B2 detail placement

*Application:* for each piece of detail in the description, ask whether a
router needs it to decide *whether* to dispatch; detail needed only once
the subagent is already running does not. B1 asks whether the description
is pure; B2 asks whether the impure material was deleted outright or
correctly relocated into the body.

*Basis:* **gitapex-owned convention.** Criterion 3's quoted "where the
body loads only when invoked" describes a skill's body, not a subagent
definition's; treating the two as the same mechanism would be an
extrapolation rather than a quote.

### B3 roster size

*Application:* grade the roster, not only the file in hand. Count the
definitions a routing context actually carries and ask whether each earns
its permanent seat there; a definition dispatched rarely still costs its
description on every routing decision. A roster with no declared bound at
all is a finding even when it is currently small, the same way criterion
2 grades trend rather than snapshot.

*Basis:* **gitapex-owned convention.** The quoted bounded-growth passages
under criterion 2 bound CLAUDE.md's line count, not a subagent roster's
size; no quoted passage treats the roster as a bounded resource.

### B4 cross-runtime tool-boundary parity

*Application:* where a definition declares a tool boundary, enumerate
every runtime it is actually distributed to and confirm the boundary is
reproduced equivalently in each, not only in the runtime it was authored
against. A boundary enforced structurally in one runtime and carried only
as prose in another is a parity failure, and the honest report names
which runtime lacks the structural backing rather than reporting the
boundary as enforced.

*Basis:* **gitapex-owned convention.** Criterion 4's channel note on
subagents (a `disallowedTools` restriction or an embedded lifecycle hook
as structural backing) is this file's own prose, not a quoted passage,
and no quoted passage addresses distribution across multiple runtimes.

## Sources considered and not used

- **Saltzer and Schroeder, "The Protection of Information in Computer
  Systems"** (1975) -- separation-of-privilege and least-privilege are a
  natural secondary reinforcement for criterion 5, and this lineage's own
  predecessor cited this source for an adjacent claim. Not cited here:
  the specific URL previously used for this source was not re-fetched
  during this authoring session, and this repository's own primary-source
  discipline requires a citation be verified in the same session it is
  used, not carried over from an earlier, different skill's own
  citation. If re-added later, it should be freshly fetched and quoted,
  not assumed unchanged.

## References

**[steering]** Anthropic (Segner, M.) -- "Steering Claude Code: when to
use CLAUDE.md, skills, hooks, and subagents," Claude by Anthropic (blog),
June 18, 2026. Matches `evaluating-skill-quality/references/rubric.md`'s
own citation of the same source, attributed there to "Anthropic" at the
organizational level; this file adds the byline author for precision.

**[context-eng]** Anthropic (Shihipar, T.) -- "The new rules of context
engineering for Claude 5 generation models," Claude by Anthropic (blog),
July 24, 2026.

[steering]: https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more "Anthropic -- Steering Claude Code: skills, hooks, subagents and more"
[context-eng]: https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models "Anthropic -- The new rules of context engineering for Claude 5 generation models"

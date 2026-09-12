# Criteria: grounding and per-channel notes

This file assumes `SKILL.md`'s five criterion definitions are already
known to the reader; nothing below restates a criterion's own definition.
What follows is per-channel application notes plus the primary-source
grounding for why each criterion exists, matching the split
`evaluating-skill-quality/references/rubric.md` uses for its own nine
dimensions.

Both primary sources below were fetched directly and read in full before
any passage was quoted; no quote here is from memory or a secondary
summary.

## Table of contents

- [1. Ownership and review gating](#1-ownership-and-review-gating)
- [2. Bounded growth](#2-bounded-growth)
- [3. Placement and disclosure fit](#3-placement-and-disclosure-fit)
- [4. Enforcement-fit](#4-enforcement-fit)
- [5. Provenance and adversarial independence](#5-provenance-and-adversarial-independence)
- [A. CLAUDE.md / AGENTS.md axes](#a-claudemd--agentsmd-axes)
- [B. Subagent definition axes](#b-subagent-definition-axes)
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

## A. CLAUDE.md / AGENTS.md axes

Every quote in this section and the next was re-fetched and read in this
authoring session, matching the same-session verification rule the
"Sources considered and not used" section below applies.

### A1. Content derivability

Grounded in [How Claude remembers your project][memory]'s own `/doctor`
trim rule, which states exactly which side of the line each kind of
content falls on: the checkup "cuts content Claude can derive from the
codebase, such as directory layouts, dependency lists, and architecture
overviews, and keeps pitfalls, rationale, and conventions that differ from
tool defaults."

The same page states the keep-side positively: "Keep it to facts Claude
should hold in every session: build commands, conventions, project layout,
'always do X' rules. If an entry is a multi-step procedure or only matters
for one part of the codebase, move it to a skill or a path-scoped rule
instead."

*Applied here:* a mechanical directory listing an agent could reproduce
with one `ls` is on the cut side; a line carrying **why** a directory
exists or **which convention governs it** is on the keep side. The two
quotes above are in tension if read as a single list ("project layout" is
kept, "directory layouts" are cut), so this axis grades the distinction
between the listing and its rationale, not the presence of path
information as such. **This reading is a judgement this file makes; the
source does not state it explicitly.**

### A2. Always-loaded justification

Grounded in the same page's framing of what this channel is and is not:
"Claude treats them as context, not enforced configuration. To block an
action regardless of what Claude decides, use a PreToolUse hook instead."

*Applied here:* for each rule the channel carries, ask what actually stops
the failure, then grade the rule's continued presence on three values
rather than two.

| Gate coverage of the rule's whole target range | Treatment |
|---|---|
| Full | Remove from the channel; the gate is the source of truth |
| Partial | Keep only the remainder the gate does not reach |
| None | Keep. This is the only case that earns a place in every turn's context |

The acceptance condition is a read, not a declaration: before removing a
rule, read the target gate's own scope in the repository's gate registry
**and in the gate itself**. A registry entry naming a rule is not evidence
that the gate's scope spans that rule's whole target range.

### A3. Dispatch multiplier

Grounded in [Subagents][subagents]'s own statement of what a subagent
loads at startup: "**CLAUDE.md files**: every level of the CLAUDE.md
hierarchy the main conversation loads, including `~/.claude/CLAUDE.md`,
project rules, `CLAUDE.local.md`, and managed policy files. The built-in
Explore and Plan agents skip this."

*Applied here:* the cost of this channel is not paid once per session. A
repository that dispatches subagents re-charges the whole hierarchy on
every non-fork dispatch, so a file that looks affordable against
[memory]'s "target under 200 lines per CLAUDE.md file" may not be
affordable against its own dispatch rate. This axis grades whether the
size was chosen knowing that, not whether a specific number was hit --
criterion 2 already grades whether a bound exists.

### A4. Over-specification

Grounded in [The new rules of context engineering][context-eng]'s own
shift from rule-writing to judgement, and in [memory]'s own reliability
caveat for this channel: "there's no guarantee of strict compliance,
especially for vague or conflicting instructions."

*Applied here:* an always-loaded rule that constrains something the model
would get right unaided spends context twice -- once to load, once to
compete with the instructions that do matter. The same page names the
compounding version of this: "if two rules contradict each other, Claude
may pick one arbitrarily."

## B. Subagent definition axes

**Subagents have no dedicated best-practices page.** Skills have one; the
subagent documentation is reference material, and the only published
numeric limit is a *combined* warning threshold, not a per-file one. Every
numeric threshold in this section is therefore a gitapex-owned convention,
stated as such, while the norms B1-B3 encode are quotable.

### B1. Description trigger purity

Grounded in [Subagents][subagents]'s own definition of the field. The
`description` field means, verbatim: "When Claude should delegate to this
subagent."

*Applied here:* the description is a routing contract that rides in every
request. Anything in it that does not help decide *whether to route here*
is cost with no return -- a statement of what the subagent is, a
restatement of its tool boundaries, a record of which decision or issue
produced it, or an authoring note addressed to a future maintainer. The
remedy for each is deletion, not rewording.

The rule this axis enforces, and its escalation path: **if the trigger
condition cannot be stated cleanly because the subagent is called for
genuinely unrelated reasons, that is a cohesion defect in the caller or in
the subagent's own scope.** Fix it upstream, or split the subagent.
Lengthening the description to cover every case is the failure this axis
exists to name.

*Not a length check.* A description can sit inside every numeric cap and
still fail this axis; the deterministic shape checker bounds growth from
below, and this axis is what detects the content type.

### B2. Detail placement

Grounded in the same page: "Those descriptions take up context, so keep
them short. ... Trim the `description` fields of your subagents, and move
detail into each subagent's system prompt, which only loads when that
subagent runs."

*Applied here:* the split is load-time, not stylistic. Detail in the body
is paid only on dispatch; detail in the description is paid on every
request. Content that fails B1 usually already exists in the body, so the
fix is deletion rather than a move.

### B3. Roster size

Grounded in the same page's own published budget: "When the combined
descriptions of your subagents, except the built-in ones, exceed 15,000
tokens, Claude Code shows a warning at startup with the total token
count."

*Applied here:* the published budget is combined and generous, so a small
roster will never approach it -- a repository at a few percent of 15,000
tokens learns nothing from this threshold alone. Grade the roster on
whether automatic delegation stays reliable as specialist agents
accumulate, and treat the combined budget as a ceiling that has not yet
bound rather than as the axis's real content.

### B4. Cross-runtime tool-boundary parity

**gitapex-owned convention.** No primary source states this, because no
single runtime's documentation is responsible for another runtime's
behaviour. The invariant:

> A tool boundary declared in a distributed subagent definition must be
> reproduced equivalently in **every** runtime the definition is
> distributed to.

*Applied here:* what is mandatory is the invariant, not a field name. The
expression is runtime-dependent, and a repository that generates one
runtime's copy from another's owns the conversion. Grade whether a
boundary is declared at all, whether a mapping exists for every
distributed copy, and whether the mapping is equivalent to the source
declaration -- three separate checks, because a missing mapping and a
wrong one fail differently.

*Disclosed limit on what parity can mean here.* [Subagents][subagents]
states that a declared `tools` list is not the effective set: subagents
"inherit the built-in tools and MCP tools available in the main
conversation, narrowed by two filters: the first removes a short list of
tools from every subagent, and the second reduces the built-in tool set
for subagents that run in the background, which is the default." An
omitted `tools` field "inherits every tool available to subagents". So
this axis grades **declaration parity**, never effective-set parity, and a
review that claims the latter is overclaiming.

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

**[memory]** Anthropic -- "How Claude remembers your project," Claude Code
documentation. Fetched and read in full on 2026-09-12, the same session
the A-series axes above were authored; every quote attributed to it is
from that read.

**[subagents]** Anthropic -- "Subagents," Claude Code documentation.
Fetched and read on 2026-09-12, the same session the B-series axes above
were authored; every quote attributed to it is from that read.

[steering]: https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more "Anthropic -- Steering Claude Code: skills, hooks, subagents and more"
[context-eng]: https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models "Anthropic -- The new rules of context engineering for Claude 5 generation models"
[memory]: https://code.claude.com/docs/en/memory "Anthropic -- How Claude remembers your project"
[subagents]: https://code.claude.com/docs/en/sub-agents "Anthropic -- Subagents"

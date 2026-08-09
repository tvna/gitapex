# State management quality

Dimension 6's deeper grading pass for a procedure whose *own steps* carry
state across a context boundary, factored out of `references/rubric.md`
because it only applies when the reviewed skill's procedure actually carries
such state -- most skills do not, so skipping this file is not itself a
finding. Dimension 6's bullets in `references/rubric.md` grade whether the
skill *text* still holds as time, install surface, tool names, and repository
identity shift; this file grades a distinct question -- whether the
*procedure* still holds when the conversation context resets, and how well
the state it carries is engineered.

This is a sub-check of dimension 6, not a tenth dimension: the fixed
nine-dimension count is unchanged. Its findings are reported inside dimension
6's entry in the review's structured report, in dimension 6's own vocabulary.

## Table of contents

- [Trigger](#trigger)
- [The precedence spine](#the-precedence-spine)
- [How to grade](#how-to-grade)
- [Axes](#axes)
- [Worked example that fires](#worked-example-that-fires)
- [Worked example that does not fire](#worked-example-that-does-not-fire)
- [What this file does not own](#what-this-file-does-not-own)
- [Sourcing](#sourcing)
- [References](#references)

## Trigger

Fires when the reviewed target's own procedure **materializes state outside
the running agent context** -- a file, an issue or pull-request body, a
harness store, a cache receipt -- **and reads it back after crossing a context
boundary**. Both halves are required. A value produced and consumed inside one
agent's working memory in one loop is ordinary reasoning, not state
management.

The qualifying boundaries are exactly four: a different dispatch; a later turn
after compaction; a later session; or a later invocation of the same procedure
against the same subject. The fourth is a boundary by construction -- a
re-invoked procedure starts from nothing whether or not its author writes the
word "resume".

Fires on any of:

- **(a) Fan-out with a consuming successor.** Two or more dispatches where a
  later dispatch's input includes an earlier dispatch's output, or a later
  step's decision depends on an earlier dispatch's result. A single dispatch
  whose report returns to its caller in context is not state management.
- **(b) A procedure that re-enters.** The skill resumes, monitors across
  turns, survives compaction, or is re-invoked against the same subject.
- **(c) Evidence handed across a boundary.** A step produces an evidence
  artifact (test output, diff, API response, screenshot) that a *different*
  agent context must consume as proof. A single terminal dispatch that
  consumes the artifact and returns its result to the caller in the same turn
  does not fire: (c) requires the artifact to outlive the dispatch that
  consumes it, or to be consumed by a step other than the one that produced
  it. A report handed to a human as the skill's terminal deliverable is the
  deliverable, not state.
- **(d) A working record read back to decide what to do next.** Progress
  marks, prior verdicts, receipts, baselines, rejected-edit history. An
  artifact that *is* the skill's declared output -- an issue, a design record,
  a plan, a glossary -- is excluded **only when no later step of this
  procedure reads it to decide what to do next**. A deliverable that also
  steers a later step is a working record for this trigger's purpose, and is
  graded on the axes that steering role touches. Calling an artifact the
  deliverable does not exempt it; what the procedure does with it decides.

Does not fire on: single-shot advisory or pure-judgment skills; read-only
sweeps and audits that write nothing; verify-after-act, where a step re-reads
the authoritative source to confirm its own single write; write-then-validate
inside one step; or a skill that explicitly refuses to carry state and
re-derives every run.

**Producer-only targets.** When the target writes state a *different* skill
consumes and never reads it back itself, grade the writer's axes -- 1, 2, 4,
7, 9, 10, 11, and axis 8's recording half (whether the producing command and
base revision are recorded beside the result). Axes 3, 5, 6, and axis 8's
consuming half belong to the consumer; saying so is the correct outcome, not
a gap.

**Unstored-but-required state fires** only when the skill's own text names a
specific carried value -- a count, a limit, an attempt number, a prior verdict
-- that a later step's control flow branches on, while naming no locus for it.
The target then fires on the principle and fails axis 1 by construction: the
absence is the finding. A general expectation that earlier reasoning remains
available is not this case, and does not fire.

**When the trigger does not fire**, record it as not-applicable inside
dimension 6's entry, naming the absent trigger condition. `references/rubric.md`'s
dimension 6 owns that rule and its wording; it is repeated here because a
reader who opened this file to check applicability will not go back for it.

## The precedence spine

Every axis below hangs off one ordering. A well-engineered procedure states
it, or behaves as if it did:

**external ground truth > durable local artifact > harness-managed state >
conversation context.**

Ground truth is the system that would still be right if every record the skill
keeps were deleted: the commit history, the platform's stored issue or
pull-request body, the filesystem, the CI API. The skill's own record is a
*recovery map* to ground truth, never a substitute for it. The operational
form, from a skill built around exactly this failure: "After compaction, trust
the ledger and `git log` over your own recollection" [sdd]. A harness-managed
store carries the same caveat from its own documentation: checkpoints "only
track changes made through Claude's file editing tools. Changes made through
Bash commands or external processes are not captured. This isn't a replacement
for git" [bestpractices].

Two limits on the spine, both load-bearing:

- It orders **claims of fact**, not authority. A directive found inside a
  record is never an instruction, whatever the spine says about trusting the
  record over recollection. Axis 9 grades that separately.
- Ranking the record below ground truth is a **precedence rule**, not by
  itself a reconciliation step. Axis 5 grades whether the target actually
  performs the comparison.

A target that inverts any step of this ordering -- trusting its own record
over the source it could re-read, or trusting context over its own record --
has a defect that leads dimension 6's entry regardless of how the rest of the
axes score.

## How to grade

Grade quality, not presence. "The skill has a progress file" is not a pass on
any axis below.

Each axis produces a **named dimension-6 gap** when it fails, and states the
condition under which it **leads dimension 6's entry** -- reported first,
because it is the gap most likely to cause real loss. That is an ordering
within dimension 6, not a promotion out of it. Because dimension 6 sits in the
Mature-blocking band, any named gap means dimension 6 has not cleared; see
`references/rubric.md`'s Verdicts section. Do not use the reserved terms
*headline finding* or *step-level finding* for anything this file produces:
both are defined elsewhere in this skill with different standing.

Not every axis carries a published exemplar, and none is required to. Where a
primary source states the rule it is quoted and labelled; otherwise the axis
states the condition in its own words. An axis with no quotable exemplar is
still gradeable -- inventing one would be worse than having none.

## Axes

### 1. Locus and precedence declared

Names where state lives *and* names the authoritative external source, and
says which wins on conflict.

**Pass** -- both are named and ordered, with the skill's own record below
ground truth [sdd]; or the target keeps no local record at all and says why,
re-fetching the authoritative source every time rather than trusting memory.

**Fail** -- a record the procedure depends on with no locus named anywhere in
the skill, or a locus named with no ground truth ranked above it.

**Leads dimension 6's entry** when the declared ordering inverts the spine, or
when the skill asserts something about its own store that is false in a real
consumer -- for example claiming a path is ignored by version control when the
calling repository's ignore rules say otherwise, so a routine staged commit
would publish it.

### 2. Identity and scope binding

This run's record must be distinguishable from a different run's record.

**Pass** -- a run, plan, or attempt identifier carried in the record itself or
in its path, so a second execution cannot be mistaken for the first.

**Fail** -- a single fixed record path with no identifier, so a second
execution appends into the first run's record with no boundary between them.
The pinned source this file otherwise draws on fails here: its workspace
resolves to one fixed directory per repository, described as the "Single
source of truth for the workspace location" [sddworkspace], and its ledger is
read from one fixed path inside it [sdd]. Two plans executed in one working
tree share one record.

**Leads dimension 6's entry** when a collision is silent rather than loud --
the record is read, parses cleanly, and describes different work.

### 3. Freshness and re-read before use

A record read once at the start and trusted for the rest of a long run is a
gap when the operation it guards happens many turns later.

**Pass** -- an explicit re-read rule tied to the boundary that invalidates the
value. Quotable, as the terminal item on a list of things never to do:
"Re-dispatch a task the progress ledger already marks complete -- check the
ledger (and `git log`) after any compaction or resume" [sdd].

**Fail** -- a single read at skill start with no later re-read, where the
operation the record guards happens many turns after that read.

**Leads dimension 6's entry** when the stale value is what makes an
irreversible or expensive action safe. A harness store is not exempt: a
documented one warns that "teammates sometimes fail to mark tasks as
completed, which blocks dependent tasks" [agentteams], so its status is a
claim to re-check, not a fact.

### 4. Write discipline

Append-only versus whole-record rewrite, and recorded in the *same step* as
the action it records rather than batched at the end.

**Pass** -- "append one line to the ledger in the same message as your other
bookkeeping" [sdd]; or, for a store whose only primitive is a whole-record
rewrite, the target names that hazard outright and says how a read-modify-write
avoids destroying content it did not author.

**Fail** -- an append-only convention layered over a whole-record rewrite
primitive with that gap unstated, so a lost update looks compliant; or a batch
of records written only at the end of a run.

**Leads dimension 6's entry** when a crash between the action and its record
leaves the record claiming less work than was done *and* nothing reconciles it
(see axis 5), or when a lost update silently destroys externally-authored
content.

Do not demand a specific crash-consistency mechanism here. Write-temp-then-
rename, fsync, and torn-write recovery are real techniques, but no primary
source surveyed for this file states them as a requirement for an agent's own
state record. Grade append-versus-rewrite and same-step recording, which are
sourced; treat the crash case as the escalation condition above, not as a
missing mechanism.

### 5. Read-back and reconciliation on resume

An explicit resume path: read the record, reconcile it against ground truth,
resume at the first **unproven** step.

**Pass** -- the record's completion marks are treated as an *index into ground
truth, never as the proof itself*: the resume point derived from the record is
confirmed against the authoritative source before any non-idempotent step
re-runs. Verifying that each recorded commit actually exists on the branch is
the shape.

**Fail** -- the resume point is selected from the record alone. A rule of the
form "resume at the first task not marked complete" [sdd], standing alone,
does **not** pass: a step with no entry is *unrecorded*, not proven undone. A
task whose work landed but whose record line was never written -- the worker
crashed, timed out, or errored after its commit -- is re-run by that rule. Axis
6 does not catch this: a record that is complete, well-formed, and one entry
short is none of axis 6's cases.

**Leads dimension 6's entry** when resuming on an unreconciled record can
repeat a non-idempotent action. The motivating failure is documented:
controllers that lost their place "have re-dispatched entire completed task
sequences - the single most expensive failure observed" [sdd].

### 6. Loss and absence handling

Missing, truncated, or unparseable record; ephemeral container; fresh clone;
a working-tree clean that removes ignored scratch. Must fail loud, never
silently restart from zero and never silently assume nothing was done.

**Pass** -- the destroyer and the recovery source are both named: "`git clean
-fdx` will destroy the ledger (it's git-ignored scratch); if that happens,
recover from `git log`" [sdd]. Refusing to proceed on an ambiguous read also
passes -- a read that did not clearly succeed is not evidence of what the
record contains.

**Fail** -- a record whose absence is indistinguishable from "the work was
never done", with nothing that stops the procedure at that point.

**Leads dimension 6's entry** when absence silently reads as "nothing was
done" and the procedure then redoes non-idempotent work, or when the store's
own documented loss modes are ignored. One such mode, in a harness store whose
entries are validated on read: entries "that don't match the message format
are reported as errors and removed from the file; the valid messages are still
delivered" [agentteams] -- the record shrinks and the procedure continues.

### 7. Concurrency and single-writer ownership

Graded when the target's own procedure admits parallel writers, **including a
second concurrent invocation of this same skill against the same subject** --
a procedure with no internal fan-out still has two writers if nothing prevents
that.

**Pass** -- any one of: a serialization rule ("Dispatch multiple
implementation subagents in parallel (conflicts)", listed under "Never"
[sdd]); a single-writer rule naming which context owns the record; a partition
rule ("Break the work so each teammate owns a different set of files"
[agentteams]); harness locking, where "Task claiming uses file locking to
prevent race conditions" [agentteams]; or a construction that removes the race
rather than guarding it, such as pinning a pre-edit state with a read-only
revision query instead of mutating the working tree while another reader may
still be live.

**Fail** -- two writers named in the same procedure with only a de-duplicating
read and no ownership or locking rule between them.

**Leads dimension 6's entry** when concurrent writes can lose an external
contributor's content.

### 8. Evidence-artifact handling

The live-proof lane. Proof passed **by path**, not summarized into context;
the consumer demonstrably reads it; the producing command and the base
revision recorded next to the result, so a stale artifact is detectable.

**Pass** -- "Everything you paste into a dispatch prompt - and everything a
subagent prints back - stays resident in your context for the rest of the
session and is re-read on every later turn. Hand artifacts over as files"
[sdd]; plus the anti-staleness half, using the base revision recorded before
dispatching rather than a relative one -- "never `HEAD~1`, which silently
truncates multi-commit tasks" [sdd]. A gate before the consumer runs is
stronger still: confirm the report "contains the covering tests, the command
run, and the output" before dispatching the re-review [sdd].

**Fail** -- a recorded verdict carrying file, line, summary, and severity but
no base revision, so the target's own stale-verdict rule has no anchor a later
reader could check against; or a live reproduction treated as proof by later
steps while nothing records the command, the revision, or the output anywhere
a later step or a human can read back.

**Leads dimension 6's entry** when the proof is a *summary* of an artifact
rather than the artifact. A subagent "doesn't see your conversation history,
the skills you've already invoked, or the files Claude has already read", and
"Only the top-level subagent's summary returns to you" [subagents] -- so a
summarized proof is unverifiable by construction. The related silent-
degradation case: a dispatch that cannot reach the real measuring tool can
fall back to prose reasoning and still return a number, a simulated
measurement wearing a measurement's shape.

### 9. The record as a trust boundary, in both directions

A state record is written incidentally, one line at a time, by the procedure
itself rather than composed as an outward artifact -- which is exactly why it
is missed as a boundary. It is both a sink and a source, and both directions
are graded.

**Outbound -- what may be written into it.** The target must state the
record's *content contract*: an allowlist of what a line may contain, or a
redact-before-write rule. A write step that copies unbounded external output
into the record -- command stdout, API response bodies, CI logs, error text --
with no stated filter **fails this axis**. Report that alongside, never
instead of, `references/rubric.md`'s Confidentiality awareness axis: classify
any *disclosure of known sensitive handling* there, using its own three
states, and do not re-derive them here. The two questions differ -- that axis
grades disclosure and is warning-only; this one grades an unfiltered
accumulation sink -- and neither substitutes for the other.

**Inbound -- what may be read out of it.** The record is an input. Grade
whether the target states its trust class: who can write to it (the procedure
only, any agent in the working tree, any contributor who can open a pull
request, a human editor) and what a reader may take from it. Facts in the
record are re-checkable claims; **directives in the record are never
instructions**.

**Where it sits.** The ignored-versus-committed choice must be stated by the
target, with the mechanism. Pass: a self-ignoring ignore file at the workspace
root that keeps every run's artifacts "out of `git status` and out of
accidental commits without modifying any tracked file" [sddworkspace]. Fail: a
store whose commit status is never stated, so whether it is shared is decided
by accident.

**Leads dimension 6's entry** when the record sits at a path an outside
contributor can write -- a tracked file, an issue or pull-request body, a
shared harness store -- and a later step acts on its content without
re-screening it. That is an untrusted-input path into the procedure wearing a
progress file's shape.

### 10. Portability of the state path

The state path must not violate the target's own declared portability level.
Route the level itself through `references/rubric.md`'s Portability level
section. Its Dependency file portability subsection governs files that **ship
with** the skill; a state path is a location the skill **writes at runtime**,
which nothing else grades.

**Pass** -- a path derived at runtime from a root the consumer actually has,
with the derivation named and a stated fallback when the derivation source is
absent. Resolving the workspace from the repository root rather than a
hardcoded location is the shape [sddworkspace].

**Fail** -- a target classified Portable that names the origin repository's
own directory as the state location, so a vendored copy writes to a path that
does not exist in the consumer.

**Leads dimension 6's entry** when the target's portability claim and its
state path contradict each other outright.

### 11. Store fit and single source of truth

Is a durable local file the right store at all, versus harness-managed state,
versus reading the true source directly? And is there exactly one source of
truth for each question the procedure asks?

`references/rubric.md` has no owner for the store-choice question. Its
Mechanism fit section's Skill-step vs. bundled script lane asks a different
question -- model reasoning versus a bundled script for one step -- and
routing there returns an answer to something else. Grade store choice here.

**Pass** -- an explicit argument for the chosen store over the alternatives,
including why no second record is kept; or the complementary form, "Track
progress in a ledger file, not only in todos" [sdd], which keeps the durable
store primary and the harness store secondary rather than duplicating
authority.

**Fail** -- an explicitly cross-session procedure whose only record is a
harness task list, where that harness documents "No session resumption with
in-process teammates: `/resume` and `/rewind` do not restore in-process
teammates" [agentteams]. A harness task list is disqualified as the *sole*
store for a procedure the skill's own text scopes across sessions.

**Leads dimension 6's entry** when two stores can hold contradictory answers
to the same question with no stated precedence, or when the target
hand-authors a store the harness owns -- a runtime config holding session
state, where "your changes are overwritten on the next state update"
[agentteams].

## Worked example that fires

Constructed, not a report on any real skill: the point is the shape of a
graded entry, and a constructed target cannot go stale or be misquoted.

Target: a branch-plan execution skill that dispatches tasks in waves and
records each completed task, with its commit, in an append-only execution log
kept inside the pull-request body.

**Trigger:** fires on (a), (b), (c), and (d). Later waves consume earlier
merged results; the skill declares a cross-session resume; per-task proof
feeds a later aggregate review; the log is written and read back.

**Passing axes.** Axis 1: the log is ranked below ground truth and named as
externally-editable pull-request text to be re-screened, with every recorded
commit verified to exist on the branch. Axis 5: a fresh session re-reads the
log to find the resume point and confirms each completion against the branch
before re-running anything. Axis 7: waves run in parallel working trees, but
the log writer is serialized to the main thread. Axis 8: the commit is
recorded beside each result, so a stale entry is detectable.

**Axis 2 FAIL.** No run identifier. A retry or a second execution attempt
appends into the same log with no boundary, so a reader cannot tell which
attempt an entry belongs to.

**Axis 6 FAIL, leads the entry.** The skill handles a *hostile or edited* log
but nothing handles a **missing, truncated, or unparseable** one. Because the
resume path derives which tasks completed from that log, an absent log reads
as "nothing was done" and the procedure re-dispatches non-idempotent work --
axis 6's stated escalation condition, and the documented most-expensive
failure [sdd].

**Axis 4 PARTIAL.** "Append-only, one line per event" is a convention layered
over a whole-body rewrite primitive, and that gap is unstated.

Dimension 6 does not clear: two named gaps, one leading.

## Worked example that does not fire

Target: a completion-verification skill whose entire content is a rule against
claiming success without running the check -- if the verification command was
not run in this message, its passing cannot be claimed.

Read loosely, clause (c) looks like it fires: the skill is entirely about
producing evidence and consuming it as proof. That reading is wrong, and
clause (c)'s same-turn carve-out is what rules it out. Nothing is materialized
outside the agent context; nothing is read back across a dispatch, a
compaction, a session, or a re-invocation; the proof is produced and consumed
in the same message by the same context. The skill is *about* proof and
carries no state by explicit design. Grading it against axes 1-11 would
penalize the correct answer.

**Correct outcome, inside dimension 6's entry:** "State-management sub-check:
not applicable -- this target materializes no state outside the running
context and reads nothing back across a dispatch, turn, session, or
re-invocation; its verification evidence is produced and consumed in the same
message."

The same reasoning covers a screening skill that deliberately re-runs its
whole procedure on each new push rather than trusting a prior clearance, and
read-only sweeps that write nothing. Refusing to carry state is a design
choice this file must not punish.

## What this file does not own

Duplication that can silently drift is itself a defect, so each overlap below
names its owner and what this file adds.

| Question | Owner | What this file adds |
|---|---|---|
| Is sensitive handling disclosed? | `references/rubric.md` Confidentiality awareness | Nothing on disclosure. Axis 9 rules separately on an unfiltered accumulation sink, and reports alongside. |
| What portability level does the target claim? | `references/rubric.md` Portability level | A runtime-written state path, which Dependency file portability does not reach. |
| Is a condition checked in exactly one place? | `references/rubric.md` Contract discipline | Nothing; this file defers. |
| Should a step be model reasoning or a bundled script? | `references/rubric.md` Mechanism fit, Skill-step vs. bundled script | Nothing. Axis 11's store-choice question is a different question with no owner there. |
| Does a bundled script produce a machine-checkable plan file? | `references/rubric.md` dimension 7, Verifiable intermediate outputs | That bullet is gated on the target shipping code; this trigger is not, so a script-less orchestrator is graded here. |
| Does the target survive hostile input probing? | `battle-testing-a-skill` | Axis 9's inbound half grades the *static design* question -- does the target state a trust class for its own record -- because adversarial probing is a separate lane a one-shot static review does not invoke. |

## Sourcing

Every `[sdd]` and `[sddworkspace]` quotation was verified byte-for-byte
against the pinned upstream revision the reference definitions below name, not
against a moving default branch. Every `[agentteams]`, `[subagents]`, and
`[bestpractices]` quotation was verified against the live page at the URL
below; product documentation drifts, so re-verify before treating any line as
verbatim.

Quotations are normalized to ASCII: em dashes in the sources are rendered
`--` or `-`, and curly quotation marks are rendered straight. No other
alteration is made inside quotation marks.

One requirement in this file is stricter than its sources rather than drawn
from them: axis 5's reconciliation step. The published resume paths select the
resume point from the record alone, and rank the record below ground truth as
a precedence rule without performing a comparison. Axis 5 requires the
comparison. Grade a target against that stated standard, not against an
implied external consensus.

## References

Every inline `[label]` citation above resolves to the source below.

- **[sdd]** obra/superpowers, `subagent-driven-development` SKILL.md, sections
  "Durable Progress", "File Handoffs", and "Red Flags", at the pinned revision
  linked below.
- **[sddworkspace]** obra/superpowers, `subagent-driven-development` workspace
  resolution script, header comment and body, same pinned revision.
- **[subagents]** Claude Code documentation, Subagents.
- **[agentteams]** Claude Code documentation, Agent teams.
- **[bestpractices]** Claude Code documentation, Best practices.

<!-- Link reference definitions below power the inline [label] shortcuts; keep in sync with the visible list above. -->

[sdd]: https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/subagent-driven-development/SKILL.md "obra/superpowers subagent-driven-development SKILL.md at pinned revision d884ae0"
[sddworkspace]: https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/subagent-driven-development/scripts/sdd-workspace "obra/superpowers subagent-driven-development workspace script at pinned revision d884ae0"
[subagents]: https://code.claude.com/docs/en/sub-agents "Claude Code: Subagents"
[agentteams]: https://code.claude.com/docs/en/agent-teams "Claude Code: Agent teams"
[bestpractices]: https://code.claude.com/docs/en/best-practices "Claude Code: Best practices"

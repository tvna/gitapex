# Plan-execution handoff: issue-to-branch -> driving-pr-to-merge

Date: 2026-07-22

Refs [#274](https://github.com/tvna/gitapex/issues/274). Design-then-decide
doc, per this repository's own plan-first discipline (CLAUDE.md section 1)
and #274's own Non-goals ("the actual design decision is deferred to a
follow-up `docs/superpowers/specs/` doc").

## Design-only scope

Per this repository's own precedent (`2026-07-18-llm-budget-gate-design.md`,
`2026-07-21-portability-authorship-decision-table-design.md`,
`2026-07-17-zero-trust-threat-model.md`): this doc records decisions only.
No `skills/*/SKILL.md` is created or modified, no script or workflow file
is added, and `docs/glossary.md` is not edited by this pass -- each is
named as a concrete follow-up target in the Acceptance criteria checklist
below, for a follow-up issue/branch, matching #274's own explicit Non-goal
("Not implementing any skill or script in this issue"). This pass's own
scope is narrower still than #274 itself: #274 authorized research and an
Acceptance Criteria Map; this doc is the design doc that map's own row 1
calls for, and it stops at the same boundary -- one file, this one.

## Why this doc exists

`issue-to-branch/SKILL.md`'s own Stop boundaries state: "Do not implement
the issue as part of this skill; it produces a plan, not code."
`driving-pr-to-merge/SKILL.md` starts from "a pull request has just been
opened." Nothing in `skills/` turns a Branch Plan/Acceptance Criteria Map
into committed code and an opened PR for the general (non-defect) case --
`issue-to-fix` already covers that handoff, but only for "a bare issue
reporting a defect." #274 scoped the investigation and, after two
Fable-assisted Known/Unknown blind-spot passes plus a human-raised DDD
review, produced a 14-row Acceptance Criteria Map, independently
adversarially verified. This doc resolves every row's Planned ops/Proof
method column, including the two rows that ask for a named deliverable
rather than a paragraph: blind spot 9's Context Mapping table and blind
spot 10's Domain-Events evaluation.

## Method

Per `issue-to-branch/SKILL.md` Step 4, #274's own Acceptance Criteria Map
is treated as a draft input, not a pre-verified result. Each row was
independently re-checked against #274's own stated facts and the current
repository tree (not the issue body's paraphrase of either) before being
adopted or corrected below. Two claims load-bearing for this doc's own
decisions were re-verified against a primary source this session, not
carried over from #274's citation alone:

- **`CLAUDE_CODE_DISABLE_WORKFLOWS`** (row 3's fallback question):
  confirmed live against `https://code.claude.com/docs/en/workflows`,
  fetched 2026-07-22. Exact quote: "Set `CLAUDE_CODE_DISABLE_WORKFLOWS=1`.
  Read at startup, so it applies wherever you set it." Also confirmed:
  "When workflows are disabled, the bundled workflow commands are
  unavailable, the `ultracode` keyword no longer triggers a run." Also
  confirmed, bearing on blind spot 6: "Resume works within the same
  Claude Code session. If you exit Claude Code while a workflow is
  running, the next session starts the workflow fresh" -- matching #274's
  own row 3/blind-spot-6 claim exactly, now grounded in the primary
  source rather than the issue's own unverified citation.
- **Whether this repository's PreToolUse hook binds inside a spawned
  subagent's tool-call context** (blind spot 5): tested live this
  session, not assumed -- see Decision 7 below. GSD's, Superpowers', and
  Spec Kit's own mechanics were not independently re-fetched this
  session; #274's own "Primary sources consulted this session" table
  already cites their canonical URLs, and this doc's own decisions (see
  Decision 1: no vendoring) do not hinge on their exact internals beyond
  what #274 already recorded -- named here as inherited fact, not
  re-verified fact, per the Facts vs. speculation section below.

No row's Interpretation column needed correction; all 14 held up against
the issue's own stated facts and the repository tree. Row 2's own Proof
method is superseded by Decision 2's Context Mapping table rather than
carried forward unchanged -- #274's own row 9 (blind spot 9) text directs
this substitution explicitly ("instead of the current ad hoc 'adopted,
adapted, or rejected' phrasing in the second Acceptance-criteria row
above"), so it is not a correction this doc is making unilaterally.

## Decision 1: a new skill, not an `issue-to-branch` extension

**Decision: a new skill**, working name `executing-a-branch-plan`
(naming rationale below; not finalized -- see Open items).

Extending `issue-to-branch` itself was considered and rejected: that
skill's own Stop boundaries state "Do not implement the issue as part of
this skill; it produces a plan, not code," matching the same
narrow-single-phase-trigger pattern this repository already uses
throughout (`issue-to-fix` reproduces-and-fixes only, `driving-pr-to-merge`
drives an already-open PR only, `drafting-an-acm-issue` authors an issue
only). Folding execution into `issue-to-branch` would directly contradict
its own stated boundary and would make its `description:` trigger
("starting work from a GitHub issue... produces an Acceptance Criteria
Map") ambiguous against a new execution trigger, the same discovery
collision `evaluating-skill-quality`'s rubric already penalizes ("a
trigger so generic it would also match a sibling's request" --
`2026-07-15-triage-cluster-design.md`'s own naming-collision precedent).

**Working name rationale.** `executing-a-branch-plan`:

- Matches the gerund-first naming family already used by 7 of this
  repository's 17 skills (`drafting-an-acm-issue`,
  `establishing-ubiquitous-language`, `evaluating-skill-quality`,
  `explaining-the-work`, `ranking-the-open-queue`,
  `responding-to-a-fresh-arrival`, `screening-a-low-trust-contribution`).
- Reuses "Branch Plan" verbatim -- the exact term `issue-to-branch`'s own
  Output contract already uses for this skill's direct input, rather than
  inventing a new name for the same concept (the collision Decision 10
  below diagnoses generally, avoided here by construction).
- "Executing" names the phase (plan -> execute), matching this
  repository's existing verb-per-phase convention (draft -> plan ->
  execute -> drive-to-merge).

Two alternatives were considered and rejected:

- `branch-plan-to-pr` (the X-to-Y family, matching `issue-to-branch`/
  `issue-to-fix`). Rejected: "-to-pr" oversells the PR as the sole
  deliverable, when per Decision 3 below the bulk of the skill's own work
  is task decomposition and per-task execution, with PR-opening as one
  step among several -- `issue-to-fix` made the identical naming choice
  for the identical reason (named for the work, "to-fix," not the
  artifact, "to-pr").
- `driving-a-branch-plan-to-pr` (mirroring `driving-pr-to-merge`).
  Rejected: `driving-pr-to-merge`'s own naming names a skill that starts
  from an already-existing PR and pushes it to completion; this new
  skill instead starts from a Plan and *creates* the PR -- a different
  shape, so reusing "driving" would imply a symmetry with
  `driving-pr-to-merge` that does not hold.

Per `establishing-ubiquitous-language/SKILL.md`'s own procedure: this is
a fresh-term-minting case, not a detected conflict (Elicit/Detect found
no existing skill name or glossary entry using this term), so the
Resolve step's "ask the owner" rule does not strictly apply here -- but
the name is still flagged in Open items for explicit owner confirmation
before the follow-up `SKILL.md` is authored, since it will be load-bearing
across every doc that then cross-references it.

**Row 1 planned ops (resolved):** author `skills/executing-a-branch-plan/
SKILL.md` plus its `references/` in a follow-up issue/branch (not this
one); add a "Related skills" cross-reference section to
`issue-to-branch/SKILL.md` in that same follow-up PR, matching how
`issue-to-fix` and `drafting-an-acm-issue` already cross-reference
`issue-to-branch`. This doc's own contribution to that planned op is the
consolidated Exact sequence in the "New skill: consolidated sequence"
section below, so the follow-up implementation issue has a complete
sequence to build from rather than re-deriving one.

**Row 1 proof method (resolved):** this design doc reviewed and approved
by the repository owner (a distinct review from #274's own approval,
since this doc's content -- the actual mechanism -- did not exist at
#274's approval time); once implemented, a worked example showing a real
Branch Plan flowing through `executing-a-branch-plan` into an opened PR
that `driving-pr-to-merge` picks up, matching #274's own row 1 exactly.

## Decision 2: Context Mapping (blind spot 9) -- supersedes row 2's ad hoc phrasing

Per #274's own row 9 text, this table replaces row 2's "adopted, adapted,
or rejected" phrasing rather than sitting alongside it.

| System | Relationship | Translation point |
|---|---|---|
| GSD | Anti-Corruption Layer | Decision 3's Task Decomposition step (single point, see below) |
| Superpowers | Anti-Corruption Layer | Decision 3's Task Decomposition step (same single point) |
| GitHub Spec Kit | Separate Ways | None -- no runtime contact at all |
| Claude Code Dynamic Workflows | Conformist | None needed -- adopted verbatim, see below |

**GSD -- Anti-Corruption Layer.** The borrowed concept is wave/pipeline
dependency handling for parallel execution groups. gitapex's own model
translates this at Decision 3's Task Decomposition step: GSD's "wave"
becomes an internal execution-ordering detail expressed through the
Workflow tool's `pipeline()`/`parallel()` primitives (Decision 4), never a
first-class term in an ACM row, a task, or a PR body. GSD's own
markdown-file/persistent-state runtime is not adopted at all -- only the
grouping pattern is, and only at this one boundary.

**Superpowers -- Anti-Corruption Layer.** The borrowed concept is the
three-phase shape (brainstorm -> plan -> execute) and
`subagent-driven-development`'s dispatch-and-review discipline.
`issue-to-branch` already covers brainstorm+plan (its own blind-spot
pass and Acceptance Criteria Map construction); `executing-a-branch-plan`
covers execute. The translation point is the same Task Decomposition
step: Superpowers' own "task" vocabulary is translated into gitapex's
already-resolved terms (Decision 10) at the exact moment the new skill
reads the Branch Plan, not scattered across later steps.

**Both ACL relationships share one mapping point, by design** -- this
directly answers #274's own instruction to name "a single mapping point,
not scattered across the new skill's steps": Decision 3's Task
Decomposition step is that point for both GSD and Superpowers. Spec Kit
needs no point at all (no contact); Dynamic Workflows needs no point
either (Conformist adoption is direct, not translated).

**GitHub Spec Kit -- Separate Ways.** #274's own Proposed solution
already states this outcome informally ("Spec Kit's contribution is
treated as a naming/structural precedent only, not a system to vendor").
Its `/specify -> /plan -> /tasks -> /implement` sequence is structurally
similar to gitapex's own existing `issue-to-branch -> executing-a-branch-
plan -> driving-pr-to-merge` sequence, but no `.specify/` template
artifact, file, or vocabulary is read, consumed, or referenced anywhere
in this design. The two models never touch at runtime; the resemblance
is precedent, not integration.

**Claude Code Dynamic Workflows -- Conformist.** The borrowed mechanism
is the actual `Workflow` tool: `agent()`/`pipeline()`/`parallel()`/
`phase()`, used as-is. Unlike the other three, this is not an external
system being ported into gitapex's own model -- it is a native platform
capability, already first-class in this environment, requiring no
install (confirmed this session: available on all paid plans, Claude
Code v2.1.154+). Building an Anti-Corruption Layer over a native
primitive gitapex can call directly would be exactly the unneeded
abstraction CLAUDE.md section 4 warns against, so Decision 4's execution
step calls the tool's own primitives directly, in its own vocabulary,
with no gitapex-specific renaming layer. The portability cost of this
Conformist choice is bounded by Decision 4's own fallback path, not left
open-ended.

## Decision 3: Task Decomposition layer (blind spot 3)

**Finding: this repository already owns the `writing-plans`-equivalent
artifact blind spot 3 asks for a layer to become.** Re-read this session,
not assumed: `docs/superpowers/plans/*.md` already carries exactly the
bite-sized, file-scoped, step-by-step shape Superpowers' `writing-plans`
exists to produce -- for example `docs/superpowers/plans/2026-07-12-
issue-to-branch-skill.md`'s own "Task N" / "Files" / numbered "Step"
structure, already used for every design-then-implement pass this
repository has done. Blind spot 3's "insert a decomposition layer" is
therefore not a new invention -- it is making this already-established
but only-informally-followed convention an explicit, required step of
`executing-a-branch-plan`, keyed off the ACM rather than a free-form plan
document written from scratch each time.

**Decision: `executing-a-branch-plan`'s own Step 2 (see consolidated
sequence below) decomposes the ACM into a task list before any execution
begins**, writing it in the same `docs/superpowers/plans/<date>-<branch-
name>.md` shape this repository already uses, with one addition: each
task line cites the ACM row(s) it satisfies, so the row-to-task mapping
stays traceable in both directions.

**Row-to-task mapping rule (resolves the granularity mismatch directly):**
many-to-many, not one-to-one.

- One ACM row decomposes into more than one task when its Planned ops
  touch independent files or independent concerns (e.g. a row whose
  Planned ops are "add a script and update two docs" becomes three
  tasks).
- Multiple ACM rows collapse into one shared task when their Planned ops
  touch the same file -- this is the file-contention rule blind spot 3's
  own Residual risk names ("Rows that share files could produce branch/
  file contention under naive parallel execution"). Concretely: before
  wave/pipeline assignment, build a file-ownership map (file path -> task
  ID); any two tasks that would write the same file are merged into one
  task or made sequential-dependent, never run in Decision 4's
  `parallel()` against each other.

This is the same wave-dependency discipline GSD borrows (Decision 2), now
expressed concretely: a "wave" is simply a set of tasks with no shared
file-ownership edge between them, computed from the decomposition step's
own output, not a separately named concept surfacing anywhere in the
new skill's own vocabulary (Decision 10).

## Decision 4: execution mechanism and portability (row 3)

**Decision: the Workflow tool executes the task list from Decision 3
when available; a sequential main-thread fallback executes the same list,
one task per turn, when it is not.** This directly answers row 3's
hard-dependency-vs-fallback question: not a hard dependency.

- **Primary path.** One `agent()` call per *task*, not per ACM row
  (resolving blind spot 3 concretely at the primitive level -- the
  earlier "one `pipeline()` stage per Acceptance-Criteria-Map row"
  framing #274's Problem section describes is superseded by this).
  Tasks with no shared file-ownership edge (Decision 3) run via
  `pipeline()`/`parallel()`; tasks that share a file-ownership edge run
  sequentially, gated on the earlier task's commit.
- **Fallback path**, used when `CLAUDE_CODE_DISABLE_WORKFLOWS=1` is set,
  the Workflow tool is otherwise unavailable in the environment, or the
  calling agent platform is not Claude Code at all (portability: the
  Workflow tool is Claude-Code-specific, unlike every other mechanism
  this design uses -- GitHub MCP tools, hooks, plain skill prose):
  execute the same task list sequentially in the main thread, one task
  per turn, same commit-per-task discipline, same Decision 8
  Execution-log events. Degraded (no parallelism, no adversarial
  cross-check between independent tasks) but not blocked.
- **What does not change between paths:** the Decision 3 task list, the
  Decision 5 authorization gate, the Decision 8 event log and PR
  handoff. Only the *how* of running each task differs.

This resolves the portability tension row 3 itself names (a hard Workflow
dependency vs. this repository's repeated cross-platform-portability
concern, cited from `issue-to-branch`, `driving-pr-to-merge`, and
`drafting-an-acm-issue`'s own portability notes): the mechanism degrades
gracefully rather than forcing a single-platform choice.

## Decision 5: execution-authorization entry gate (blind spot 1)

**Decision: require an explicit, platform-verified approval signal on
the parent issue before Decision 3's task list is built -- not a
self-reported claim in text.**

`docs/motivation.md`'s own to-be diagram gates implementation behind
`Contributor-->>Author: approved -> start implementation`, and this
design cannot wait on the separate, larger Design-by-Contract criteria-
freeze initiative #274's own Non-goals explicitly excludes. The interim
mechanism: `executing-a-branch-plan`'s Step 0 (below) checks, via
`mcp__github__issue_read` method `get_comments` (or `get`, if the
approval is the issue body/state itself), for either:

1. A comment on the parent issue whose `author_association` field --
   platform-verified, not a self-asserted string, matching zero-trust
   principle 5 ("verified identity over asserted identity") -- is
   `OWNER`, `MEMBER`, or `COLLABORATOR`, and whose text approves this
   specific Branch Plan; or
2. In the current interactive session (no such comment exists yet),
   explicit confirmation from the active human operator in the
   conversation itself, per this repository's general "confirm before an
   outward-facing or hard-to-reverse action" discipline (CLAUDE.md
   section 4) -- since opening commits and a PR from autonomous execution
   is exactly that kind of action.

Absent either, Step 0 stops and escalates rather than proceeding --
matching zero-trust principle 6 ("fail closed, including on
INDETERMINATE"): an unclear authorization state is a deny, not an
assume-approved.

## Decision 6: threat-model mapping (blind spot 2)

`executing-a-branch-plan`'s Step 0 (and every later step) treats ACM row
content -- ultimately sourced from issue-body text, which `issue-to-
branch` Step 1 already treats as untrusted -- through the same lens
`untrusted-input-triage` and `screening-a-low-trust-contribution` already
define: an ACM row's Planned ops is a *fact extracted for execution*, not
an instruction to follow blindly. Concretely:

- Before Decision 3's decomposition, re-run the Extract/Ignore/Flag/Tag
  discipline (`untrusted-input-triage/SKILL.md`) against the ACM's own
  text: an ACM row whose Planned ops or Interpretation column reads as an
  attempt to inject an instruction (rather than describe a change) is
  flagged and escalated, never silently executed.
- Each task's own diff, immediately once its own `agent()` call produces
  it, is screened via `screening-a-low-trust-contribution`'s checks 2-8
  before that task's own commit, push, or `TaskCompleted` event (Decision
  8) -- not deferred to "before the PR opens," since Decision 8's draft
  PR opens before any task executes and Decision 7 has task agents commit
  their own changes directly. Workflow-file edits, governance-file edits,
  hook/script changes, dependency additions, and instruction-bearing
  content are each an independent hard flag regardless of how
  "reasonable" the surrounding change looks, matching that skill's own
  Stop boundary. A flagged diff never proceeds to commit -- it dispatches
  as `StageDeviated{action: escalate}` (Decision 8) regardless of whether
  the task's own proof method would otherwise have passed.
- This mapping applies all seven `2026-07-17-zero-trust-threat-model.md`
  principles to `executing-a-branch-plan` specifically, not selectively:
  principle 2 ("every invocation re-validates its own inputs") means each
  task-level `agent()` call re-applies this triage independently rather
  than trusting Decision 3's own earlier pass; principle 4 ("assume
  breach") means a single compromised or misfiring task must not be able
  to widen its own file-ownership scope past what Decision 3 assigned it.

This is the highest-blast-radius surface this skill catalog owns to
date -- turning untrusted issue text into committed code and an opened
PR -- and is treated as such here, not as a lighter-weight case.

## Decision 7: does this repository's PreToolUse hook bind inside a subagent context? (blind spot 5)

**Empirically tested this session, not assumed.** A fresh subagent
(dispatched via the Agent tool -- the same "fresh context window"
category of mechanism the Workflow tool's own `agent()` primitive uses,
though not the literal `Workflow` tool call itself, which requires its
own explicit user opt-in this session did not have) was instructed to run
exactly one Bash command: `pip install --help`. This command is chosen to
match `hooks/check-bash-safety.sh`'s own install-verb deny pattern
(`install_re`, Finding 1) while being 100% inert even if it executes
successfully (no package name given, so nothing installs; it only prints
help text).

**Result: not blocked.** The subagent's Bash call ran with no permission
denial, no hook `systemMessage`, no "Blocked by" text, and no non-zero
exit code -- `pip install --help` executed normally (exit 0, full help
text returned) exactly as it would with no hook installed at all.

**Design constraint (stated as a verified fact, per row's own
instruction, not an assumption):** `hooks/check-bash-safety.sh` does not
currently fire for a Bash call made from inside a spawned subagent's own
tool-call context in this environment. This confirms blind spot 5's own
suspicion directly rather than leaving it open. The scope of this finding
is stated precisely: it is verified for the Agent-tool subagent dispatch
mechanism tested; it is not independently verified for the Workflow
tool's own `agent()` primitive specifically, though both are fresh-
context subagent dispatch and there is no design-level reason to expect
divergent hook-binding behavior between them -- named as residual risk
below, not asserted as identically proven.

**Compensating control, following directly from this finding (zero-trust
principle 2, "never assume the calling environment already filtered
anything"):** `executing-a-branch-plan` never delegates a GitHub write
(opening the PR, commenting, updating issue state) to a spawned task
`agent()`. Every GitHub write happens in the main thread only --
mirroring `docs/motivation.md`'s own to-be diagram note for
`issue-to-branch` ("runs in main thread: blindspot pass / interview /
hermetic-criteria authoring (visible, no subagent)"), now extended to
this new skill for a threat-model reason rather than a visibility one.
Task-level `agent()` calls may write and commit code (file edits are
already the Workflow tool's own auto-approved default per its
documentation, a materially lower blast radius than a GitHub write) but
never touch `mcp__github__*` write tools, `gh`, or `git push` directly,
and **never run a package-manager install command either** (`pip`/`npm`/
`uv`/etc.) -- the same finding extends past GitHub writes to
`hooks/check-bash-safety.sh`'s Finding 1 (the install-verb block), which
this session's own probe command was deliberately chosen from, and which
the probe therefore already shows is equally unenforced in this context.
A task whose Planned ops require adding a dependency edits the manifest
file's text only; the actual install command runs as its own main-thread
step, after Decision 6's screening of the manifest diff, never inside the
task's own `agent()` call. Decision 3's task prompts state this full
exclusion list explicitly, in-band, since the hook itself cannot be
relied on to enforce any of it inside that context.

## Decision 8: a unified Domain-Events mechanism (blind spots 4, 6, 10 -- resolved together)

Blind spot 4 (failure/deviation semantics) and blind spot 6 (durable
cross-session resume) are, per #274's own row 10 framing, both really
"what state transitions occur and how are they recorded" -- one question,
not two. **Decision: adopt one append-only Domain-Events log, not two
separately designed mechanisms**, closing blind spot 10 as "unify" rather
than "keep separate."

**Where it lives: the PR body, in a new `## Execution log` section** --
not a new file, not `implementation-notes` (which, checked this session,
is currently only a diagram label in `docs/motivation.md`, not an
established file or convention anywhere else in the repository; grepped,
zero other hits). Three reasons, argued rather than assumed:

1. **Matches two already-shipped precedents in this same repository**
   rather than inventing a third artifact location: the Acceptance
   Criteria Map already lives in the PR body (`issue-to-branch` Step 8),
   and the `## Skill audit evidence` section already lives there too
   (`2026-07-21-skill-audit-merge-gate-design.md`). A third convention
   for the same PR would fragment where a reviewer looks for state.
2. **The PR body is already the artifact `driving-pr-to-merge` reads.**
   No second file needs to be kept in sync with the PR at handoff time.
3. **Cross-session resume becomes a direct read**, closing blind spot 6
   concretely: a fresh session reopening the same PR calls
   `mcp__github__pull_request_read` method `get` (or `get_comments`) and
   reads the Execution log section to know exactly which tasks completed,
   which failed, and where to resume -- no separate state file whose own
   drift-from-the-PR blind spot 3's granularity finding and this row's
   own Residual risk both already warn about generally (two independently
   evolving stores of the same fact).

**Publishing the branch precedes the draft PR.** Decision 3's Task
Decomposition step writes its task list locally; a draft PR needs a
published head ref to open against, which does not exist yet at that
point. Immediately after Decision 3 and before opening the draft PR, in
the main thread: create the Branch Plan's named branch (`issue-to-branch`
Output contract), commit Decision 3's own task-list file to it as the
branch's first commit, and push -- publishing the head ref the draft PR
requires.

**How the PR exists before all tasks are done:** opened as a **draft PR**
immediately after that push, as soon as Decision 5's authorization gate
passes (not after every task commits) -- containing the ACM and an
Execution log seeded with a `PlanApproved` event. `executing-a-branch-
plan` itself subscribes to the draft PR's own CI/review/comment activity
at this same moment, in the main thread, and owns responding to it for
the entire task-execution window -- it does not wait for or delegate to
`driving-pr-to-merge` during that window. `driving-pr-to-merge`'s own
Step 6 `"draft"` dispatch ("escalate per step 7 rather than treating it
as something to fix") describes its own behavior when it is the skill
invoked standalone on an already-existing draft PR outside an active
execution context -- a human or a later session opening it
independently -- not this design, since `executing-a-branch-plan` is the
skill actively driving the draft PR here, not `driving-pr-to-merge`.
`driving-pr-to-merge` itself needs no code change; only the ownership
handoff's timing needed stating explicitly, which this paragraph now
does. The draft PR converts to ready-for-review only once every task in
Decision 3's list has a `TaskCompleted` event, at which point ownership
of its activity passes to `driving-pr-to-merge`'s normal entry point.

**Event vocabulary (closed set, append-only, one line per event):**
`PlanApproved`, `TaskStarted{task_id}`,
`TaskCompleted{task_id, commit_sha}`, `TaskFailed{task_id, reason}`,
`StageDeviated{task_id, reason, action}` where `action` is one of
`retry` / `stop-and-replan` / `escalate`.

**Failure dispatch rule (closes blind spot 4's own ask directly):** a
task's own proof method failing triggers exactly one retry with the
failure output folded into the retried task's own context (bounded --
one retry, not an open loop, matching this repository's general
aversion to unbounded fan-out, see Decision 9). If the retry also fails,
dispatch on what actually failed:

- The *plan* was wrong (this task's own Interpretation/Planned ops does
  not fit what the row actually needed) -> `stop-and-replan` fires
  exactly as that skill already defines it: close the draft PR with a
  `StageDeviated{action: stop-and-replan}` event and rationale, comment
  the same rationale on the parent issue, re-plan from there. This is a
  direct match for that skill's own trigger language ("the plan missed
  the issue, not that the prose describing it was clumsy").
- The *execution* was wrong but the fix is not obvious -> escalate: a
  `StageDeviated{action: escalate}` event, plus a comment on the (still
  draft) PR naming exactly what was tried, matching
  `driving-pr-to-merge`'s own Step 7 ("escalate only when blocked... not
  for anything the agent can fix on its own").

This gives blind spot 4's "deviation-log location" a concrete home (the
PR body's Execution log, not the previously vague `implementation-notes`
label) and blind spot 6's "durable artifact" the same home, satisfying
both proof methods with one mechanism, per row 10's own instruction.

## Decision 9: cost/budget reconciliation (blind spot 7)

**Finding: `2026-07-18-llm-budget-gate-design.md`'s actual mechanism does
not apply here, and should not be extended to try.** That gate scans
`.github/workflows/*.{yml,yaml}` for LLM-invocation markers in CI-
dispatched workflows; `executing-a-branch-plan` runs inside an
interactive/agentic session via the Agent or Workflow tool, never through
a `.github/workflows/*.yml` file, so no marker this gate scans for would
ever fire on it, and no marker should be added there to force a match --
that would be the same "ships a gate that... never fires on the one real
case" mistake `2026-07-18-llm-budget-gate-design.md`'s own "Why this doc
exists" section already found and fixed for a different mechanism.

**What does apply: the general concern the budget-gate lineage and
CLAUDE.md's own connector-preference-to-reduce-token-consumption rule
both name** -- subagent-per-task fan-out scales roughly linearly with
Decision 3's task count, and Decision 4's wave/pipeline parallelism can
multiply that further. The real, already-existing bound for the Workflow
path is the tool's own documented cap, confirmed this session, not
invented: "Up to 16 concurrent agents, fewer on machines with limited CPU
cores" and "1,000 agents total per run." No additional gitapex-specific
ceiling is proposed on top of this native one in this pass.

**Following `2026-07-18-llm-budget-gate-design.md`'s own Decision 3
precedent directly: no numeric cost/token ceiling is invented here.**
That design explicitly declined to guess a `max_tokens_per_run` /
`max_cost_usd_per_run` value without real dispatch data, flagging it as
an operator-supplied open input instead. The same discipline applies
here for the same reason: this design has no real per-task, per-model
cost data for `executing-a-branch-plan` (it does not exist yet), and
inventing a plausible-sounding number would be exactly the "confident
guess presented as fact" CLAUDE.md section 2's primary-source discipline
exists to prevent. **Flagged as an open input**, to be measured from a
real dry run once the follow-up implementation issue lands, mirroring
the earlier design's own treatment of the identical gap.

## Decision 10: ubiquitous-language resolution (blind spot 8)

Running `establishing-ubiquitous-language`'s Elicit/Detect/Resolve
procedure over the vocabulary this design borrows from four systems,
against gitapex's own existing terms (`docs/glossary.md`'s `Issue` entry,
`issue-to-branch`'s own "Acceptance Criteria Map row" / "criterion" /
"Branch Plan"):

| Candidate term | Source(s) | Detect finding | Resolution |
|---|---|---|---|
| `task` | GSD, Superpowers, Spec Kit | No existing gitapex synonym for this specific concept -- Decision 3 establishes "criterion" (verification unit) and "task" (work unit) as genuinely different concepts, not two names for one thing. Fresh-term case, not a conflict. | Adopt `task` as gitapex's own term: one file-scoped, independently-committable unit of work, produced by decomposing one or more ACM rows (Decision 3). |
| `plan` (bare) | GSD, Spec Kit | Synonym collision: `issue-to-branch`'s own "Branch Plan" already names this concept. | "Branch Plan" wins; bare "plan" retires as an ambiguous synonym in any new skill text, mirroring `docs/glossary.md`'s existing `Issue`-over-`Bug report` precedent. |
| `spec` | Spec Kit | No conflict, but also no adoption needed: per Decision 2, Spec Kit is Separate Ways -- no runtime contact, so its "spec" template artifact is never consumed. | Not adopted. Recorded here as a deliberate non-adoption, not a silently dropped term. |
| `wave` | GSD | No conflict, but per Decision 2's Anti-Corruption Layer translation, "wave" is absorbed into "task" + "file-ownership dependency" at Decision 3's single mapping point and never surfaces as a first-class term. | Not adopted as a named term; described in prose only ("dependency-gated task group") where the concept is needed. |
| `phase` / `pipeline` / `agent` | Dynamic Workflows | No conflict -- per Decision 2's Conformist relationship, these are the Workflow tool's own vocabulary, used verbatim, never promoted into ACM/PR-body vocabulary. | Adopted as-is, scoped strictly to Decision 4's execution-step script; never used in a task description, ACM row, or PR body, which stay in "task"/"Branch Plan"/"criterion" terms. |

**`docs/glossary.md` is not edited by this pass** (Design-only scope,
above) -- the `task` entry and the `plan`-superseded-by-`Branch Plan`
note are listed as the first step of the follow-up implementation PR in
the Acceptance criteria checklist below, per
`establishing-ubiquitous-language/SKILL.md` Step 4's own Maintain step,
so the design doc's terminology is not treated as final until that
entry actually exists, matching blind spot 8's own proof method exactly.

## Decision 11: what "optimal for gitapex" means (row 4)

Row 4's own Interpretation states "optimal" has no stated success
criteria yet. This doc supplies one, as a checklist rather than a single
sentence, matching this repository's existing definition-of-done
convention (Acceptance criteria checklists throughout `docs/superpowers/
specs/`):

- No vendored external runtime (Decision 1: new skill built from
  gitapex's own conventions; Decision 2: GSD/Superpowers borrowed as
  Anti-Corruption Layer pattern only, Spec Kit not integrated at all).
- Cross-platform portability stated explicitly, not left implicit
  (Decision 4: Workflow tool primary path, sequential fallback,
  `CLAUDE_CODE_DISABLE_WORKFLOWS` named).
- Consistent with existing skill conventions (Decision 1's naming
  rationale; Decision 3's reuse of the already-established
  `docs/superpowers/plans/` shape rather than a new artifact type).
- Zero-trust threat-model compliance stated and empirically checked, not
  assumed (Decisions 5, 6, 7 -- including the live gate-binding test).
- Cost bounded by an existing, real mechanism rather than an invented
  number (Decision 9).
- No vocabulary collision shipped silently (Decision 10).

Every row above resolves into one of these six checklist items; "optimal"
is defined as satisfying all six, not as a single subjective judgment
call left to the follow-up implementer.

## New skill: consolidated sequence (for the follow-up implementation issue)

Provided so the follow-up issue does not need to re-derive step ordering
from the eleven decisions above. Not implemented by this pass (Design-
only scope).

1. **Authorization gate** (Decision 5). Check for a platform-verified
   approval signal on the parent issue, or explicit human confirmation in
   session. Fail closed on anything less.
2. **Threat-model triage** (Decision 6). Extract/Ignore/Flag/Tag the ACM's
   own text before treating any of it as executable instruction.
3. **Task Decomposition** (Decision 3). Write a `docs/superpowers/plans/
   <date>-<branch-name>.md`-shaped task list from the ACM, each task
   citing its source row(s), with a file-ownership map computed before
   any wave/pipeline assignment.
4. **Publish the branch** (Decision 8). Create the Branch Plan's named
   branch, commit step 3's task-list file to it as its first commit, and
   push -- main thread only -- publishing the head ref step 5 requires.
5. **Open a draft PR and subscribe** (Decision 8) with the ACM and a
   seeded Execution log (`PlanApproved` event); subscribe to the draft
   PR's own CI/review/comment activity in this same step, owned by this
   skill until step 8.
6. **Execute** (Decision 4). Workflow-tool `pipeline()`/`parallel()` over
   Decision 3's task list when available; sequential main-thread fallback
   otherwise. Each task's own diff is screened (Decision 6) before its
   own commit; GitHub writes, `git push`, and package-manager install
   commands are never delegated into a task `agent()` (Decision 7's
   compensating control, widened to cover installs) -- only steps 4, 5,
   this step's own `TaskStarted`/`TaskCompleted`/`TaskFailed` event
   writes, and step 8 happen in the main thread.
7. **On task failure or a screening flag**, dispatch per Decision 8's
   rule: one retry for an ordinary proof-method failure, then
   `stop-and-replan` (the plan itself was wrong) or escalate (the
   execution was wrong, or a screening flag, with no obvious safe fix).
8. **On all tasks complete**, mark the PR ready for review; ownership of
   its activity passes to `driving-pr-to-merge`'s normal entry point
   (Decision 8) -- no code change needed there, only this explicit
   handoff point.

## Facts vs. speculation

**Facts, verified this session:** `CLAUDE_CODE_DISABLE_WORKFLOWS=1` and
its documented effects, fetched from `https://code.claude.com/docs/en/
workflows` (2026-07-22); the Workflow tool's documented concurrency caps
(16 concurrent, 1,000 total per run); `hooks/check-bash-safety.sh` does
not fire for a Bash call made from inside an Agent-tool-dispatched
subagent (live probe, this session); `docs/superpowers/plans/*.md`'s
existing Task/Files/Step shape (read directly, e.g. `2026-07-12-issue-to-
branch-skill.md`); `implementation-notes` has zero hits outside
`docs/motivation.md`'s two diagram-note lines (grepped this session); all
14 of #274's own ACM rows and both DDD blind spots (9, 10) checked
against #274's own stated facts and the current repository tree, per
`issue-to-branch` Step 4.

**Speculation, named as such:** GSD's, Superpowers', and Spec Kit's own
internal mechanics are inherited from #274's own "Primary sources
consulted this session" table, not independently re-fetched this
session -- row 2's own Residual risk ("primary-source drift... the design
doc should note its own fetch date") is accordingly still open for those
three specifically; this doc's own fetch date for the one claim it did
verify independently is stated above. Decision 7's finding is verified
for Agent-tool subagent dispatch specifically, not literally re-tested
against the Workflow tool's own `agent()` primitive (which this session
had no standing opt-in to invoke) -- treated as a strong, not certain,
signal for that primitive too, named as residual risk below. Decision 9's
"no numeric ceiling" is a deliberate non-answer, not an oversight, and
should not be read as a lower risk than an invented number would imply.

## Non-goals

- No `skills/executing-a-branch-plan/SKILL.md` or any other skill code --
  design only, per #274's own explicit Non-goal and this session's own
  scope instruction.
- No `docs/glossary.md` edit -- listed as the follow-up PR's own first
  step (Decision 10, Acceptance criteria checklist below).
- Not touching the separate, larger Design-by-Contract contract-join /
  criteria-freeze initiative (`docs/motivation.md`'s "Relationship to the
  skills in this repository" section) -- Decision 5's interim
  authorization gate is explicitly a standalone mechanism, not blocked on
  that initiative landing, matching #274's own row 5 Planned ops.
- Not re-testing Decision 7's hook-binding finding against the literal
  Workflow tool `agent()` primitive -- that requires an explicit workflow
  opt-in this session did not have; named as an open item, not silently
  assumed identical.
- Not proposing a numeric LLM cost/token ceiling for
  `executing-a-branch-plan` -- Decision 9 names this as an operator-
  supplied open input once real dispatch data exists, matching
  `2026-07-18-llm-budget-gate-design.md`'s own precedent for the
  identical situation.
- Not vendoring GSD, Superpowers, or Spec Kit as a runtime dependency --
  Decision 2's Context Mapping table states this explicitly per system.

## Acceptance criteria checklist

Mapped to #274's own 14-row Acceptance Criteria Map, in row order:

- [x] Row 1 (mechanism): Decision 1 -- new skill, working name and
      rationale stated; Row 1's own planned ops/proof method resolved.
- [x] Row 2 (GSD/Superpowers/Spec Kit patterns): superseded by Decision 2
      per #274's own row 9 instruction; each system's adopt/adapt/reject
      status is now stated via its Context Mapping relationship instead.
- [x] Row 3 (Dynamic Workflows, hard-dependency-vs-fallback): Decision 4
      -- primary Workflow path plus sequential fallback, verified
      `CLAUDE_CODE_DISABLE_WORKFLOWS` behavior cited from a primary
      source fetched this session.
- [x] Row 4 ("optimal for gitapex"): Decision 11 -- six-item
      definition-of-done, each item traced to a specific decision above.
- [x] Row 5 / blind spot 1 (authorization gate): Decision 5.
- [x] Row 6 / blind spot 2 (threat-model mapping): Decision 6.
- [x] Row 7 / blind spot 3 (row-vs-task granularity): Decision 3.
- [x] Row 8 / blind spot 4 (failure/deviation semantics): Decision 8
      (unified with blind spot 6 per row 10's own instruction).
- [x] Row 9 / blind spot 5 (gates bind inside subagent contexts):
      Decision 7 -- empirically tested this session, not assumed; result
      documented, compensating control designed from the result.
- [x] Row 10 / blind spot 6 (durable cross-session resume artifact):
      Decision 8 (unified with blind spot 4).
- [x] Row 11 / blind spot 7 (cost/token budget estimate): Decision 9 --
      reconciled against `2026-07-18-llm-budget-gate-design.md`
      (found not directly applicable; the real, existing bound is named
      instead), numeric ceiling explicitly deferred, not invented.
- [x] Row 12 / blind spot 8 (ubiquitous language): Decision 10 --
      resolution table produced; `docs/glossary.md` edit itself deferred
      to the follow-up implementation PR (see below), matching that
      row's own proof method ("before the design doc's terminology is
      treated as final").
- [x] Row 13 / blind spot 9 (Context Mapping table): Decision 2 -- the
      explicit deliverable this row itself names.
- [x] Row 14 / blind spot 10 (unified Domain-Events mechanism): Decision
      8 -- the explicit deliverable this row itself names.

Follow-up implementation PR's own first steps (not this pass, per Non-
goals above, but listed here so they are not lost between docs):

- [ ] Add `Task` and `plan`-superseded-by-`Branch Plan` entries to
      `docs/glossary.md` (Decision 10) before authoring
      `executing-a-branch-plan/SKILL.md`'s own text.
- [ ] Author `skills/executing-a-branch-plan/SKILL.md` and its
      `references/`, following the consolidated sequence above.
- [ ] Add a "Related skills" section to `issue-to-branch/SKILL.md`
      cross-referencing the new skill (Decision 1's row 1 resolution).
- [ ] Run `battle-testing-a-skill` and `evaluating-skill-quality` against
      the new `SKILL.md` before opening its PR, disclosing both verdicts
      in the PR body per `2026-07-21-skill-audit-merge-gate-design.md`'s
      already-shipped gate.
- [ ] Measure a real per-task/per-model cost figure from an actual
      dispatch and reconcile it into a concrete Decision 9 ceiling,
      rather than leaving the open input open indefinitely.

## Open items

- **Confirm the working name** `executing-a-branch-plan` with the
  repository owner before it is used as the actual skill directory name
  -- Decision 1 makes a decision-ready recommendation with reasons, but
  naming is exactly the kind of choice `establishing-ubiquitous-language`
  reserves for explicit confirmation once it is about to become load-
  bearing across multiple files.
- **Decision 7's scope gap**: re-verify (once a standing workflow opt-in
  exists for this kind of check) whether the Workflow tool's own
  `agent()` primitive specifically -- not just the Agent-tool subagent
  dispatch tested this session -- also fails to fire the PreToolUse hook,
  before treating Decision 7's compensating control as covering every
  execution path Decision 4 describes.
- **Decision 9's numeric ceiling** remains an explicit open input,
  matching `2026-07-18-llm-budget-gate-design.md`'s own precedent, not a
  gap unique to this doc.

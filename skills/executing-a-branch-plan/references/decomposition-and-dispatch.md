# Decomposition and Dispatch

Steps 3, 6, and 8's own detail, merged into one file per
`evaluating-skill-quality/references/rubric.md`'s Dimension 5 (the
ordinary execution path must not force more than roughly three reference
files open): task decomposition (step 3), execution/dispatch mechanics
(step 6), and the code-quality principles applied while writing each
task's own implementation (steps 6 and 8). Source: design doc Decisions
3, 4, 13, 15, 16, 19; the code-quality section's own source is noted in
its own subsection below.

## Contents

- [Task decomposition](#task-decomposition)
  - [Malformed or empty ACM](#malformed-or-empty-acm-precondition-checked-before-any-of-the-below)
  - [Fan-out bound](#fan-out-bound-blast-radius-control-checked-once-the-task-list-exists)
  - [Row-to-task mapping](#row-to-task-mapping-many-to-many-not-one-to-one)
  - [Verbatim-quotation discipline](#verbatim-quotation-discipline)
  - [Two dependency-edge types](#two-dependency-edge-types-both-computed-before-wave-assignment)
  - [Irreversibility classification](#irreversibility-classification)
  - [Skill-file edit routing](#skill-file-edit-routing)
  - [Per-task diff BASE](#per-task-diff-base-screening-precondition-used-at-step-6)
  - [Worked example](#worked-example)
- [Execution and dispatch](#execution-and-dispatch)
  - [Primary path: one Workflow run per wave](#primary-path-one-workflow-run-per-wave)
  - [Git worktree isolation for parallel task execution](#git-worktree-isolation-for-parallel-task-execution)
  - [Worktree-base precondition backstop](#worktree-base-precondition-backstop)
  - [Sequential fallback](#sequential-fallback)
- [Code quality principles](#code-quality-principles)
  - [1. Type System Discipline](#1-type-system-discipline)
  - [2. Boundary Discipline](#2-boundary-discipline)
  - [3. Make Operations Idempotent](#3-make-operations-idempotent)
  - [4. Migrate Callers Then Delete Legacy APIs](#4-migrate-callers-then-delete-legacy-apis)
  - [5. Model the Domain](#5-model-the-domain)
  - [6. Separate Before Serializing Shared State](#6-separate-before-serializing-shared-state)
  - [7. Foundational Thinking](#7-foundational-thinking)

## Task decomposition

Step 3's own detail. Source: design doc Decisions 3, 15, 19.

### Malformed or empty ACM (precondition, checked before any of the below)

Before building the row-to-task mapping, verify the ACM itself is
well-formed: at least one row, and every row carries a non-empty
Criterion, Interpretation, and Planned ops column (a Proof method or
Residual risk column reading "unknown, pending X" is fine -- an
`planning-a-branch-from-an-issue`/`drafting-issues` convention, not malformed; a
genuinely empty or missing column is). An ACM with zero rows, or any row
missing a required column, is not decomposed -- stop and escalate the
same way an absent step-1 authorization signal does (fail closed, not an
assumed-empty task list or a silently-skipped row).

### Fan-out bound (blast-radius control, checked once the task list exists)

**Scope, stated precisely rather than implied broader than it is:** the
two caps below bound task/wave *headcount* and *re-plan recurrence*
only. They do not bound actual token, turn, or wall-clock consumption
per task, and neither does anything else in this skill -- design doc
Decision 9 explicitly and deliberately declines to invent a numeric
cost/token ceiling ("no numeric cost/token ceiling is invented here ...
Flagged as an open input, to be measured from a real dry run"), the same
precedent `2026-07-18-llm-budget-gate-design.md` already set. A 5-task
ACM well under the count threshold below whose Planned-ops text induces
one task to consume unusually many turns before hitting its one-retry-
then-escalate failure path is not caught by either cap -- this is a
named, accepted residual gap, not a solved one, tracked as an open input
in the design doc rather than invented here. Two concrete caps for what
*is* bounded:

- **Task/wave count.** If decomposition would produce more tasks than
  the Workflow tool's own documented "Large workflow" informational
  threshold (25+ agents, per design doc Decision 9), treat that as a
  signal requiring the same authorization-gate confirmation an
  irreversible task requires below -- not a hard block, since a
  genuinely large Branch Plan is a real, legitimate case, but not a
  silent auto-proceed either.
- **Re-plan recurrence.** `stop-and-replan` firing more than once for
  the same parent issue/Branch Plan (design doc Decision 8's failure
  dispatch) escalates instead of re-planning a third time -- a Branch
  Plan that fails to converge after one correction is a signal for human
  judgment, not another autonomous attempt.

### Row-to-task mapping (many-to-many, not one-to-one)

- One ACM row decomposes into more than one task when its Planned ops
  touch independent files or independent concerns (e.g. "add a script and
  update two docs" becomes three tasks).
- Multiple ACM rows collapse into one shared task when their Planned ops
  touch the same file -- this is the file-contention rule; two tasks that
  would write the same file are merged into one task or made
  sequential-dependent, never run in the same parallel wave.

Write the task list in the same
`docs/superpowers/plans/<date>-<branch-name>.md` shape this repository
already uses for other design-then-implement passes (Task / Files /
numbered Step). Each task line cites the
ACM row(s) it satisfies, so the row-to-task mapping stays traceable in
both directions.

### Verbatim-quotation discipline

The task-list writer quotes each ACM row's own Planned-ops text into
that row's task record (an explicit citation field naming the row and
quoting its Planned-ops column) rather than paraphrasing it. This
grounds the pinned interface-dependency-edge judgment (above) in the
ACM's actual source text, not a summary that may have silently dropped
or reworded the detail the judgment depends on -- a weak-tier paraphrase
is exactly the failure mode this discipline exists to close, since the
pinned judgment reads whatever the task record actually says, not the
original ACM. The quoted text still goes through [events-and-review-
gate.md's own "Escape before
interpolating"](events-and-review-gate.md#event-vocabulary-closed-set-append-only-one-line-per-event)
rule before it is written into the committed, GitHub-rendered task-list
file -- verbatim quotation is not an exemption from that rule, since a
row's Planned-ops text carries the same untrusted-issue-body provenance
every other quoted field there already accounts for.

A task decomposing one ACM row into several tasks (the many-to-many
case above) quotes the same source text into each of those tasks; a
task merging several ACM rows (the file-contention case above) quotes
each contributing row's own text into that one task's record, not a
fused paraphrase combining them.

**Residual risk, named explicitly rather than left implicit.** Verbatim
quotation is safe only because step 2's own
`untrusted-input-triage` pass already ran against the ACM's text before
any row reaches this step -- see
[threat-model-and-authorization.md's Per-task
screening](threat-model-and-authorization.md#per-task-screening). A row
that step 2 false-negatives on now propagates unparaphrased into its own
task record and, from there, into that task's own dispatched
`agent()` prompt -- where a paraphrase step might previously have
diluted or reworded an injected instruction as an unintended side
effect, verbatim quotation no longer does. This discipline does not add
a new screening layer at the task-agent level; it deliberately trades
away that incidental, unreliable side effect for the ACM-row-fidelity
this section exists to guarantee, on the premise that step 2's own
pinned judgment (not an accidental paraphrase) is the actual control
this skill relies on to catch an injected row before it is ever quoted
anywhere.

### Two dependency-edge types, both computed before wave assignment

1. **File-ownership edge.** Build a file path -> task ID map before
   wave/pipeline assignment; any two tasks that would write the same file
   share an edge. `scripts/gitapex_check_file_ownership_conflicts.py` mechanizes
   this map-building/conflict-detection step -- a deterministic
   pre-filter, not a full replacement: a clean result from it is never
   itself grounds to skip the interface-dependency edge judgment below
   for the same task pair, since that is a different edge type entirely
   (a shared-file conflict and a producer/consumer relationship are
   independent judgments -- a task pair can carry one, the other, both,
   or neither).
2. **Interface-dependency edge.** At decomposition time, check each
   task's own Planned ops against every other task's Planned ops for a
   stated or clearly implied producer/consumer relationship (a function
   signature, an exported type, a config key, a schema one task's output
   another task's own text consumes). Where genuinely ambiguous (neither
   task's own text settles whether the edge exists), treat the pair as
   dependent -- the same fail-closed default this skill uses at every
   other uncertain-classification point. **Model/effort pin.** Unlike
   the file-ownership edge above (pure string matching, no pin needed),
   this is a semantic judgment over free-text descriptions that no
   deterministic check can make -- pinned to the same stronger-reasoning
   tier and default-or-higher effort as the Authorization gate and
   Per-task screening's residual judgment
   (`references/threat-model-and-authorization.md`), for the same
   reason: a missed edge here lets two genuinely dependent tasks
   co-dispatch into the same wave, racing on an interface neither task's
   own worktree-isolated diff reveals until merge-back.

A task pair connected by either edge type is sequenced, never co-assigned
to the same parallel wave -- each wave, in this sense, is simply the set
of tasks with no edge of either type between any pair, a plain
consequence of this step's own output, not a separately named concept
elsewhere in this skill's vocabulary (see `docs/glossary.md`'s `Task`
entry; design doc Decision 10 resolves "wave" itself the same way --
described in prose only, never adopted as a formal term).

### Irreversibility classification

Classify each task's own Planned ops for irreversibility at this same
decomposition step (a schema migration, a data deletion, and similar
one-way operations are irreversible; most file edits are not). A task
classified irreversible carries that flag into step 6/7: it requires the
same authorization-gate confirmation step 1 already defines, re-run for
that specific task, before its own wave dispatches -- not only at the
Branch-Plan-wide entry point.

### Skill-file edit routing

Classify each task's own Planned ops, at this same decomposition step,
for whether they create or edit any `SKILL.md` -- brand-new or already
existing, at any size. A task in this category routes to
`drafting-a-skill`, the same dispatch mechanism `SKILL.md`'s own Related
skills section already names for a brand-new skill directory
(`vs. drafting-a-skill` bullet) -- unchanged for that case, now unified
to cover an existing-`SKILL.md` edit too: every `SKILL.md` edit, however
small, goes through `drafting-a-skill`'s own full Design-by-Contract
procedure (collision check, formative-dimensions sweep, shape/drift
checkers), never a lighter-weight substitute.

`scorer-gated-skill-edits` stays a separate, opt-in route: it applies
only when the task's own Planned ops themselves state a scorer and a
held-out split, per that skill's own Precondition gate -- never a
fallback this step reaches for on its own, and never triggered merely
because a scorer or split already exists for the target skill. Absent
that stated precondition, the task routes to `drafting-a-skill` as
above.

### Per-task diff BASE (screening precondition, used at step 6)

Record the BASE commit immediately before each task's own dispatch, and
screen `BASE..HEAD` from that task's own worktree at merge-back time --
never `HEAD~1`. With worktree merge-backs landing on the shared branch
out of task-dispatch order, `HEAD~1` is not reliably that task's own
diff.

### Worked example

ACM row: "add a config field, wire it into two call sites, document it."

- Task A: add the field to the config schema file.
- Task B: wire call site 1 (interface edge on Task A -- reads the field's
  final name).
- Task C: wire call site 2 (interface edge on Task A; no file or
  interface edge with Task B -- disjoint call sites).
- Task D: document the field (interface edge on Task A; no edge with B or
  C).

wave 1: {A}. wave 2: {B, C} (no edge between them). wave 3: {D} (edge on
A only, but A already completed by wave 1 -- D could in principle join
wave 2 if its own interface edge is only on A, not on B/C; whether D
joins wave 2 or gets its own wave 3 depends on whether D's own Planned
ops also read something B or C produces -- if not, collapsing D into wave
2 is correct and this worked example's 3-wave shape is the more
conservative, not the only correct, wave assignment).

## Execution and dispatch

Step 6's own detail. Source: design doc Decisions 4, 13, 16.

Renamed from "Execution and Waves": design doc
Decision 2/10 resolved "wave" as "not adopted as a named term; described
in prose only... never surfaces as a first-class term" -- a file titled
after the word, and a formal quoted definition once given for it
elsewhere in this skill, both formalized it past that resolution. Ordinary
lowercase "wave"/"per wave" usage below is unchanged, matching how the
design doc's own Decisions 3/4/13/16 use the identical word as plain
prose throughout -- that is the resolution's own intended shape, not a
violation of it.

### Primary path: one Workflow run per wave

The Workflow tool executes [Task decomposition](#task-decomposition)'s
wave list when available. **One `Workflow` run per wave, not one
continuous run for the whole task list** -- the Workflow script itself
has no filesystem or shell access at all (it can only call
`agent()`/`pipeline()`/`parallel()` and read return values); a bare git
command or an `mcp__github__*` call cannot execute inside the script's
own code, only inside an `agent()` call. Screening, worktree merge-back,
and event-log writes must run in the actual main thread between waves,
not inside a script that cannot reach any of them.

Per wave: dispatch a Workflow run containing only that wave's
`pipeline()`/`parallel()` task `agent()` calls, each:

- `agentType: 'branch-plan-task'` -- the Decision 17 backstop subagent
  type (see
  [threat-model-and-authorization.md](threat-model-and-authorization.md#the-branch-plan-task-subagent-type)).
- `isolation: 'worktree'` when the wave has more than one task (see
  below); omit for a single-task wave, where isolation has no concurrent
  write to guard against.

The run returns each task's result to the main thread. The main thread
then, per task: screens the `BASE..HEAD` diff (this file's own [Task
decomposition](#task-decomposition) section's own BASE convention),
merges the worktree-isolated commit onto the
shared branch, **pushes the shared branch to the remote**, writes
`TaskStarted`/`TaskCompleted`/`TaskFailed`/`NeedsInput` events. Step 4's
own push publishes the branch initially; it is not the only push --
every wave's own merge-back is followed by its own push, so the draft
PR's diff and the Execution log's `commit_sha` references always point
at commits genuinely on the remote, not only what happens to be sitting
in the local working copy. The next wave's Workflow run dispatches only
once this settles, so its own tasks see every earlier wave's merged
state.

**Consent/portability note.** Each wave's own Workflow run triggers its
own launch-time approval prompt in default/accept-edits permission
modes, confirmed via a direct fetch of Claude Code's own primary
documentation (`code.claude.com/docs/en/workflows`, this skill's own
authoring session, not inherited from the design doc's earlier fetch
unverified): "Default, accept edits: **Every run**, unless you've
selected 'Yes, and don't ask again' for that workflow in this project."
A Branch Plan with many small waves multiplies this prompt count --
this file's own [Task decomposition](#task-decomposition) section's own
wave-minimizing effect (grouping everything
with no file or interface edge into one wave) is therefore also a
consent-friction control, not only a parallelism-maximizing one. The
*count* of prompts a real multi-wave dispatch produces, and whether that
count is acceptable in practice, is unverified -- flagged for the first
real run to measure, not assumed low-friction.

### Git worktree isolation for parallel task execution

A file-ownership map prevents two parallel tasks from touching the same
*file*, but says nothing about the git-level race of two `agent()` calls
committing to the same branch/working directory concurrently -- a working
directory's index and HEAD are single, shared, mutable state, so
concurrent `git add`/`git commit`/`git status` is not safe even when the
files touched are disjoint.

Every task dispatched in a multi-task wave runs with `isolation:
'worktree'`, the Workflow tool's own documented mechanism for exactly
this case ("use ONLY when agents mutate files in parallel and would
otherwise conflict; the worktree is auto-removed if unchanged"). This
file's own [Task decomposition](#task-decomposition) section's own
file-ownership map is what makes this cost-justified -- a task that
will not conflict on file *content* still races at the git-*mechanics*
level without isolation.

**Merge-back is a main-thread step, not delegated to the task agent.**
After a worktree-isolated task's own `agent()` call reports completion
(post-screening), the main thread merges that task's worktree commit onto
the shared feature branch published in step 4. Because the wave's own
file-disjointness already holds, this merge is conflict-free by
construction, not a merge requiring manual resolution -- it stays
main-thread-only because it still mutates the one shared branch multiple
parallel worktrees would each otherwise try to update concurrently.

Distinct from the `EnterWorktree`/`ExitWorktree` tool pair: those move
the whole interactive session into one worktree, gated by their own tool
description to fire only on explicit user/CLAUDE.md instruction. This
skill's own main-thread git operations (branch publish, merge-back) do
not call `EnterWorktree` by default.

**Open item, not resolved here:** the Workflow tool's own documented
behavior states a worktree is "auto-removed if unchanged"; it does not
state what happens to a worktree that DID accumulate changes (every task
worktree, by definition) after its own merge-back completes. Verify this
directly against the actual runtime behavior in the target deployment
before relying on automatic cleanup, rather than assuming it.

### Worktree-base precondition backstop

A wave's worktree is forked from the shared plan branch's own tip at
dispatch time (above); nothing previously re-checked, from inside that
worktree, whether the shared branch had since advanced past the
worktree's own fork point -- a concurrent sibling task's own wave merging
and pushing before this one returns, or a stale worktree reused across
waves, could both leave a task working from (and reporting complete
against) a base that no longer reflects the shared branch's own current
state. Issue `#1508` (consolidated into issue `#1566`'s own
gate-preconditions-mechanism umbrella) closes this:
`scripts/gitapex_check_task_worktree_base.py`, chained into
`check_task_bash_safety.sh`'s own existing `PreToolUse` "Bash" hook as a
second sibling classifier call (the identical pattern that script already
uses to invoke `gitapex_check_task_bash_safety.py`), re-asserts on every
Bash call that the shared plan branch's own current tip is still an
ancestor of the task's own worktree HEAD -- in git terms, that
`git merge-base HEAD SHARED_BRANCH` still equals `git rev-parse
SHARED_BRANCH`.

**Piggybacks on the task's own first Bash call, not a true "before any
tool call at all, including a non-Bash one" gate.** Claude Code has no
`SubagentStart`-equivalent hook event -- confirmed directly against Claude
Code's own hooks documentation (only `SubagentStop` exists, already used
for Decision 20's own exit condition below, a different purpose from a
PRE-dispatch check). The `branch-plan-task` agent type's own embedded
`PreToolUse` "Bash" hook is therefore the earliest deterministic
enforcement point actually available, so this backstop only fires once
the task issues its own FIRST Bash tool call -- any Read/Edit/Write/
Grep/Glob work a task does before its first Bash call is not covered by
it at all. This is an explicitly disclosed, asymmetric-strength residual,
matching this skill's own established disclosure convention (Decision
17's own two-variant asymmetry) rather than overclaiming full coverage;
see
[threat-model-and-authorization.md](threat-model-and-authorization.md#worktree-base-precondition-backstop)
for the full accounting.

**Resolving the shared plan branch's own name, without threading a new
value in from the main thread.** Nothing in this skill's own dispatch
mechanism today passes a task an explicit env var, a file, or any other
signal naming the shared plan branch (confirmed directly against this
file and SKILL.md before this mechanism was built, not assumed). Since a
worktree shares refs/objects with the main checkout it was created from,
`gitapex_check_task_worktree_base.py` resolves the name purely from local
git state instead: the worktree's own branch reflog records a
`"branch: Created from <name>"` entry at creation time -- git's own
standard behavior for `git branch <new> <startpoint>`,
`git checkout -b <new> <startpoint>`,
and `git worktree add -b <new> <path> <startpoint>` alike, live-verified
against a real worktree fixture during this mechanism's own authoring
pass -- and `<name>` is then verified to resolve to an EXISTING LOCAL
branch before being trusted as the shared plan branch. See
`gitapex_check_task_worktree_base.py`'s own module docstring for the full
mechanism, including a deliberately narrower alternative considered and
rejected as unsafe (walking the
worktree's own `.git` file back to the main checkout and reading ITS
currently checked-out branch) -- that heuristic false-positives for ANY
linked worktree whatsoever, not only one this skill's own Workflow-tool
dispatch created, confirmed live against exactly such an unrelated
worktree during authoring.

**Disclosed assumption -- and it is verified FALSE for at least one real
dispatcher.** This resolution mechanism assumes the Workflow tool's own
`isolation: 'worktree'` implementation creates each task's worktree via a
`-b <new-branch> <shared-branch-name>`-shaped operation naming the shared
branch as a literal startpoint -- the same "Open item, not resolved here"
territory this file already flags above for this exact tool's own
worktree-creation internals (its cleanup-on-merge-back behavior). If the
real implementation instead uses a detached-HEAD checkout, or passes a raw
commit SHA or a remote-tracking ref rather than a local branch name as the
startpoint, this backstop's own resolution fails cleanly and it silently
no-ops for that dispatch -- see the fail-open paragraph next.

**This is not hypothetical, and it is the common case here.** Issue
`#1566`'s own step-8 adversarial review observed a real `branch-plan-task`
worktree in this repository whose own branch reflog read exactly `branch:
Created from origin/main`, sitting at the plan branch's merge-base with
every one of that branch's commits missing -- issue `#1508`'s own defect
shape, in the flesh. `origin/main` is a remote-tracking ref, not a local
branch, so `gitapex_check_task_worktree_base.py` returned `warn` and
failed open: the stale base went undetected and the dispatched agent had
to notice it and `git reset --hard` by hand.

**Therefore: treat this backstop as absent until the shared plan branch's
name is threaded in explicitly.** Until then, a wave dispatch's own prompt
should tell each task to verify its worktree HEAD against the shared plan
branch's tip itself, rather than relying on this hook to catch it -- which
is exactly what the step-8 dispatch prompt that found this had to do by
hand. Comparing against `origin/main` instead would NOT be a fix: `main`
is not the shared plan branch, so that check would deny every
legitimately-based task worktree the moment `main` advanced -- the same
false, blast-radius-widening DENY the rejected main-checkout heuristic
above was rejected for. The real fix (an env var naming the shared plan
branch, set by this skill's own dispatch step and read by the script) is
an open follow-up, named here rather than silently assumed away.

**Fail-open by design, the opposite default from
`gitapex_check_task_bash_safety.py`'s own fail-closed classifier.** This
backstop denies ONLY on a clean, confirmed mismatch (the shared branch's
own current tip genuinely not an ancestor of the worktree's HEAD); every
other outcome -- the branch name cannot be resolved at all (no worktree,
a detached HEAD, an unrelated worktree's own reflog, a malformed hook
payload), or even a crash inside the classifier itself -- fails OPEN,
silently letting the Bash call proceed to the existing Bash-safety
classifier unchanged. This is deliberate: this backstop must never
interfere with the sequential fallback below (no worktree, no wave),
which this same `branch-plan-task` agent type also runs under, per design
doc Decision 4's own portability answer -- and a false DENY here would be
strictly worse than a missed detection, since it would stop a task's own
legitimate work over a precondition check this mechanism cannot always
resolve with confidence. See
[threat-model-and-authorization.md](threat-model-and-authorization.md#worktree-base-precondition-backstop)
for the two-variant asymmetry (this mechanism exists only in the
project-local variant, which alone carries the embedded `PreToolUse`
hook) and the full disclosed-residual accounting.

### Sequential fallback

Used when `CLAUDE_CODE_DISABLE_WORKFLOWS=1` is set, the Workflow tool is
otherwise unavailable, or the calling agent platform is not Claude Code
at all. Execute the same task list sequentially in the main thread, one
task per turn, same commit-per-task discipline, same event-log writes.
Degraded (no parallelism, no adversarial cross-check between independent
tasks, no `agentType`/worktree-isolation scoping -- a task's own
exclusion list is prompt-only in this path, not structurally enforced)
but not blocked. No wave/run boundary exists in this path at all -- there
is no concurrent write to isolate against, so applying worktree isolation
here would be unneeded complexity, not a missing safeguard.

**"Portable to any agent platform" scope, stated precisely rather than
implied broader than verified.** This path is *architecturally*
platform-agnostic because it deliberately avoids every Claude-Code-
specific primitive (no `Workflow` tool, no `agentType`, no
`isolation: 'worktree'`) -- it needs nothing beyond a plain conversational
loop and file/git tools any coding agent has. That is a structural
argument, not an empirical one: this skill's own authoring session tried
to verify the claim against a concrete other platform (OpenAI Codex,
since it is an active participant in this repository as an automated PR
reviewer) and could not -- the relevant primary documentation
(`developers.openai.com`) was unreachable from that session's own network
policy. Whether Codex's actual execution model (its own sandbox/approval
mechanics, whether it has a persistent "main thread" concept at all)
genuinely behaves the way this fallback assumes is therefore **not
verified, on any platform other than Claude Code itself**, and should not
be read as confirmed portability -- only as an architecture that avoids
the specific dependencies that would obviously break it.

What does not change between the two paths: the task list itself, the
step-1 authorization gate, the event log and PR handoff. Only the *how*
of running each task differs.

## Code quality principles

Steps 6 and 8's own reference: 7 gitapex-filtered code-design principles,
each with one governing statement and one warning-sign example. Kept
deliberately concise rather than this directory's longer discursive
reference-file style elsewhere -- prompts to recognize a code smell while
writing or reviewing a diff, not a procedure to execute. Source and the
excluded-candidate accounting: `metadata/gitapex.yaml`'s own
`spec.references` decision entry for issue `#1388`.

### 1. Type System Discipline

**Governing statement:** encode an invariant in the type itself so the
type-checker rejects an invalid state at compile/check time, rather than
documenting the invariant in a comment or re-deriving it with a runtime
check at every call site.

**Warning sign:** a function parameter is typed as a broad primitive
(`string`, `any`, `dict`) and the function's own first few lines parse,
validate, or narrow it before doing anything else -- the narrowing
belongs in the parameter's own type, not in the function body.

### 2. Boundary Discipline

**Governing statement:** validate and shape external data exactly once,
at the module or service boundary where it enters; everything past that
boundary trusts the shape the boundary already enforced.

**Warning sign:** the same field is re-validated (null-checked,
range-checked, re-parsed) at two or more internal call sites, with no
evidence of a bypass the first checkpoint misses. Incidental, reflexive
re-validation only -- a second checkpoint `diagnosing-a-failure` or a
blast-radius judgment actually showed is needed is a deliberate layer,
not this warning sign.

### 3. Make Operations Idempotent

**Governing statement:** design an operation so invoking it twice with
the same input leaves the system in the same end state as invoking it
once -- no duplicated side effect from a retry.

**Warning sign:** a retried request (timeout, network blip, at-least-once
delivery) creates a second row, message, or charge instead of converging
on the same one an earlier, successful-but-unacknowledged attempt already
produced.

### 4. Migrate Callers Then Delete Legacy APIs

**Governing statement:** move every call site to the new API first,
confirm each migrated call site actually works, and only then delete the
old API -- never delete while a caller still references it.

**Warning sign:** a deprecated function or endpoint is removed in the
same change that introduces its replacement, with the removal's own diff
never actually enumerating which call sites were checked.

### 5. Model the Domain

**Governing statement:** when code branches a lot or repeats the same
shape assumption across files, encode the domain in one structure (a
state machine, a typed model, a registry, a reducer) instead of leaving
it scattered across conditionals -- distinct from Type System Discipline
above, which names an invalid *value* unrepresentable; this names an
invalid *combination of state* unrepresentable.

**Warning sign:** the same `if status == "x" and flag_y and not
flag_z`-shaped condition, or an equivalent chain of booleans, is
duplicated (exactly or with drift) across several files or functions
that all need to agree on which states are actually reachable together.

### 6. Separate Before Serializing Shared State

**Governing statement:** "serializing" here means arbitrating concurrent
access (forcing writers to take turns), not data serialization -- when
multiple writers can touch the same shared state concurrently, resolve
ownership or partitioning of that state before reaching for a
serialization mechanism (a lock, a mutex, a queue, a shared worktree) to
arbitrate the conflict.

**Warning sign:** a lock is added around a shared mutable structure to
stop writers from interleaving, without first asking whether the
structure should instead be partitioned so each writer owns a disjoint
slice and no lock is needed at all.

### 7. Foundational Thinking

**Governing statement:** settle the core data shape -- what fields exist,
what a name refers to, what concurrent actors actually share -- before
writing the logic that operates on it; get infrastructure a later phase
depends on (types, a schema, a CI check) in place before building the
feature that assumes it, not the other way around.

**Warning sign:** a task writes business logic against a data shape still
being decided elsewhere in the same change, or before the infrastructure
it depends on (a schema migration, a type definition) actually exists --
forcing a rewrite once the shape settles instead of settling it first.

# Add reviewing-an-artifact: extract drafting-a-pr-to-merge Step 8 into a standalone review skill (issue #1249)

**Goal:** add `skills/reviewing-an-artifact/` (a standalone defect-finding
review skill, invocable directly rather than only embedded inside
`drafting-a-pr-to-merge` Step 8), and replace that Step 8's body with a
single reference line to the new skill. Source:
https://github.com/tvna/gitapex/issues/1249.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 5):** performed this session, recorded as a re-verification marker on
issue #1249's own body (2026-08-29T11:01:38Z). One correction: the design
record the issue cites throughout as already-finalized,
`reviewing-a-pull-request-design.md`, does not exist anywhere in this
repository (checked the full working tree and every local/remote branch).
Treated as a documentation-traceability gap, not a blocker -- the issue's
own Acceptance Criteria Map already restates the design's operative
content in implementable detail. All 7 ACM rows otherwise re-verified
against current repo state, none corrected. Of the 4 accepted
pstack-informed candidates (2026-08-29 issue comment,
https://github.com/tvna/gitapex/issues/1249#issuecomment-5461231099):
multi-model cross-checking, named per-axis sub-personas, and a
root-cause-vs-symptom output tag are adopted; the dynamic blast-radius
pass is explicitly NOT adopted (contingent on an executable-environment
assumption this design does not make, per the candidate's own stated
condition).

**File-ownership check (mechanized):**
`gitapex_check_file_ownership_conflicts.py` against the 2 tasks' file
lists below -> no conflicts (disjoint directories/files: task-1 owns only
new files under `skills/reviewing-an-artifact/`; task-2 owns only
`skills/drafting-a-pr-to-merge/SKILL.md`).

**Canonical-governance-paths pre-filter (mechanized):**
`gitapex_check_canonical_governance_paths.py` against the 7 changed paths
-> 3 `governance` matches (`skills/reviewing-an-artifact/SKILL.md`,
`skills/reviewing-an-artifact/metadata/gitapex.yaml`,
`skills/drafting-a-pr-to-merge/SKILL.md` -- expected: a `SKILL.md`/
sidecar is exactly this repository's own governance/instruction-file
category), 4 `no-match` (the four new `references/*.md` files -- needs the
model's own full-diff review). Full model review (the
`untrusted-input-triage` Extract/Ignore/Flag/Tag pass over the ACM's own
text, step 2 of `executing-a-branch-plan`, plus per-task screening at each
task's own diff, step 6) still runs regardless of either classification,
per that script's own "never itself grounds to skip" rule -- nothing in
the issue's Problem, Proposed solution, Acceptance Criteria, or accepted
comment text reads as an injected instruction rather than a change
description; the two apparent imperative-style phrases inside the ACM's
own "Planned ops" column ("Author a new SKILL.md...", "Rewrite the Step 8
body...") are task descriptions authored by the issue's own OWNER-author
describing what to build, not a payload attempting to redirect this
skill's own procedure -- consistent with every other ACM this repository's
`planning-a-branch-from-an-issue` has produced.

**Interface-dependency edges:**
- task-2 (rewrite `drafting-a-pr-to-merge` Step 8's body to a reference
  line naming `reviewing-an-artifact`) needs task-1's finished skill name,
  description, and step-numbering to reference accurately -- sequenced
  after task-1.
- task-1's own `drafting-a-skill` Step 6 (collision/dependency
  reconciliation) may recommend a cross-reference addition to
  `drafting-a-pr-to-merge`'s own Related-skills section; that edit is
  folded into task-2 (which already owns that file), not applied
  separately by task-1, to avoid two tasks writing the same file.

**Waves:** wave 1: {task-1}. wave 2: {task-2} (edges on task-1).

**Execution mode:** sequential main-thread fallback, no `Workflow` tool
run -- this session carries no explicit multi-agent-orchestration opt-in
("ultracode" or an explicit user request for a workflow), so the
`Workflow` tool is not invoked per this environment's own tool-use policy;
each task is executed directly in the main thread, one per turn, matching
this skill's own documented fallback path (`SKILL.md` step 6: "Use the
sequential main-thread fallback ... when the Workflow tool is
unavailable"). Step 8's refactor and adversarial-review passes each use a
fresh `Agent`-tool subagent dispatch, at a stronger-reasoning tier and
this session's default-or-higher effort. Step 9's mandatory
`evaluating-skill-quality`/`battle-testing-a-skill` dispatch (via
`drafting-a-skill` Step 9, task-1's own authoring method) likewise uses
fresh `Agent`-tool dispatches, not `Workflow`.

**Irreversibility classification:** neither task is irreversible -- both
are ordinary, git-revertible file additions/edits inside this repository;
no data deletion, no live external write, no schema migration. No task
requires a fresh per-task authorization confirmation beyond the
branch-plan-wide one recorded below.

**Authorization record (step 1):** structural precondition PASS
(`gitapex_check_branch_plan_reverified.py` against issue #1249's live
body -- the `planning-a-branch-from-an-issue` re-verification marker is
present, timestamp 2026-08-29T11:01:38Z). Semantic approval: in-session
explicit confirmation from the human operator, directly instructing
"こちらのPRを作りマージ直前まで進める" (create this PR and drive it to just
before merge) against issue #1249's own URL -- unambiguous, directly
responsive to this specific issue, no embedded instruction attempting to
redirect this gate. No pre-existing approval comment exists on issue #1249
beyond the one comment already read (the pstack-refinements comment,
itself not an approval of a Branch Plan).

## Task 1 -- Author skills/reviewing-an-artifact/

**Cites ACM rows:** all 7 rows (this task is the whole new skill), plus
adopted pstack candidates 1/3/4.

**Quoted Planned ops (verbatim from the issue body):** "Author a new
SKILL.md (frontmatter/Steps/Output/Stop boundaries/Related skills)";
"Write the Step 0 procedure, list the deferral targets, document the
redirect condition to `diagnosing-a-failure`"; "Document the vocabulary
list in a reference or the SKILL.md body"; "Migrate `drafting-a-pr-to-merge`
Step 8's existing logic and turn it into a reference; add the
effort-branching logic and the unconfirmed-concern output"; "Document the
CWE rubric and redaction procedure; prevent PR description/commit-message
metadata leakage into fan-out prompts"; "Migrate existing logic, add the
high-effort branch, document the output schema".

**Files:** `skills/reviewing-an-artifact/SKILL.md` (new),
`skills/reviewing-an-artifact/references/*.md` (new, exact split decided
during drafting), `skills/reviewing-an-artifact/metadata/gitapex.yaml`
(new).

**Design, fixed at decomposition time:** authored via `drafting-a-skill`
end to end. Elicited axes already obtained this session (Portability=Mixed,
Capability assumption=Adaptive, Invocation mode=default/both,
Lifecycle=experimental tracking issue #1249) -- `drafting-a-skill` Step 3
is satisfied by this record, not re-elicited. Trigger scope: a PR, commit,
branch, working tree, or merge candidate (`review-verdict`'s own stated
breadth, `.claude/skills/review-verdict/SKILL.md`), plus a single file not
part of any diff. Precondition excludes a causal "why is this failing"
question (redirects to `diagnosing-a-failure`) and excludes a target
already covered by a more specific existing skill (Step 0's own deferral
list: `evaluating-skill-quality`, `evaluating-deterministic-gate-quality`,
`scanning-ci-workflows`, `scanning-attack-surfaces` Mode A,
`evaluating-context-channel-maturity`, `battle-testing-a-skill`). Step 8's
existing inner-layer logic in `skills/drafting-a-pr-to-merge/SKILL.md`
(current HEAD, its own numbered step 8, roughly its own file's lines
169-298) is migrated near-verbatim as this skill's low-effort baseline,
extended with: effort parameter (low/high), named per-axis sub-personas,
multi-model/multi-prompt cross-checking at high effort, a validity x
severity gate plus "unconfirmed concern" class at high effort, asymmetric
security-tier handling (CWE rubric, gamma approx. 3.0 cost-multiplier,
fan-out-prompt metadata redaction), high-effort signature-aware
blast-radius escalation, and a root-cause-vs-symptom output tag. Dynamic
(test-execution) blast-radius is explicitly out of scope this round
(Non-goals), per the candidate's own stated executable-environment
contingency.

**Proof method:** `drafting-a-skill` Step 8's two deterministic checkers
(`python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`,
`python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`)
both clean; Step 9's mandatory fresh dispatch of `evaluating-skill-quality`
and `battle-testing-a-skill`, each independently, with every finding fixed
or explicitly deferred with a stated reason.

## Task 2 -- Replace drafting-a-pr-to-merge Step 8's body with a reference line

**Cites ACM row:** "Replace `drafting-a-pr-to-merge` Step 8's body with a
single reference line to the new skill".

**Quoted Planned ops (verbatim from the issue body):** "Rewrite the Step 8
body, add the reference link".

**Files:** `skills/drafting-a-pr-to-merge/SKILL.md` (Step 8's body,
current lines ~169-298; its Process Flow diagram's `step8` node label;
its Related skills section's existing Step-8 description; its Stop
boundaries' Step-8 bullets -- confirm exact current line numbers before
editing, since task-1 touches only files outside this one).

**Design, fixed at decomposition time:** keep the Step 7 -> Step 9
transition logic (mergeable_state branching, the "Never merge" principle)
in `drafting-a-pr-to-merge` unchanged. Replace only Step 8's own
mechanism description with a single reference line to
`skills/reviewing-an-artifact/SKILL.md`, matching the exact pattern that
file already uses for `untrusted-input-triage`/`outward-artifact-preflight`
(a reference line, not a re-derivation). Update the Related skills
section's existing "Step 8's two-layer review ... is inlined here, not a
separate skill file" sentence to state the new, opposite fact. Do not
touch `executing-a-branch-plan`'s own Step 8 (explicit non-goal, unrelated
mechanism).

**Proof method:** re-read the edited file in full to confirm Step 7's
dispatch table, the Process Flow mermaid diagram, and every other Stop
boundary/Related-skills sentence untouched by this edit still reads
consistently against the new Step 8 reference line; confirm the new
reference line's cited skill name/steps match task-1's actual final
`SKILL.md` content (interface-dependency check).

## Post-task gate (Decision 12, mandatory)

After both tasks land: one refactor/simplify pass (behavior-preserving
only) and one independent adversarial code review, each a fresh
`Agent`-tool subagent dispatch at a stronger-reasoning tier and this
session's default-or-higher effort, over the full accumulated diff. Given
this change adds a security-tier-handling procedure (CWE rubric,
metadata-redaction requirement) inside the new skill itself, the
adversarial review must confirm, at minimum: (a) the redaction rule
actually prevents PR description/commit-message metadata from reaching a
fan-out-stage prompt as drafted, not merely stating the goal; (b) the
security-tier "unconfirmed concern, never silently discarded" rule has no
silent-discard path left in the low-effort branch; (c) the new skill's
own Step 0 deferral list does not create a routing gap or a routing loop
against any of the six named specialist skills; (d) task-2's replacement
text does not leave any dangling reference to the removed inline
mechanism elsewhere in `drafting-a-pr-to-merge/SKILL.md`. Every CONFIRMED
finding is fixed and, where a proof-method check exists for the affected
area, re-run before the draft PR converts to ready-for-review.

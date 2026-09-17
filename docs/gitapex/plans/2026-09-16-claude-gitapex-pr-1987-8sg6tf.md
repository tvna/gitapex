# Branch Plan: ship the channel gate layer and fix the two violations it flags

Issue: https://github.com/tvna/gitapex/issues/1987

Parent tracking issue: https://github.com/tvna/gitapex/issues/1963

Depends on: https://github.com/tvna/gitapex/issues/1986 (stage 1, merged via
PR #2007), whose `B4` axis is the rule the tool-boundary checks enforce.

Branch: `claude/gitapex-pr-1987-8sg6tf`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1987's body, section
  "Plan re-verification (2026-09-16)", and
  `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session, instructing that this issue's PR be
  opened and driven to a merge-ready state. No issue comment carries the
  approval; the in-session confirmation is the signal this gate ran on,
  recorded here rather than implied.

## Threat-model triage

Issue #1987's Problem, Proposed solution, Acceptance Criteria Map,
Constraints and Non-goals sections, plus the parent issue #1963's own
corrections C1-C5 and issue #1986's corrections D1-D4, were read as change
descriptions, not as instructions to execute. Extracted: the five ACM
rows' own Planned-ops text, the file paths named, the PR #1972
revert-history constraint, and the change-surface-narrow constraint.
Nothing embeds a directive to override a trusted instruction source, a
credential request, an encoded payload, or an attempt to redirect this
session beyond the stated code change. Nothing was flagged.

## Task Decomposition

Four tasks, two waves. Task 4 carries an interface-dependency edge onto
Tasks 1-3 and cannot share their wave.

- **File-ownership map.**
  - Task 1 owns `hooks/gitapex_sync_opencode.py` and
    `tests/test_gitapex_sync_opencode.py`.
  - Task 2 owns `skills/evaluating-context-channel-maturity/scripts/gitapex_check_channel_shape.py`
    and `skills/evaluating-context-channel-maturity/scripts/test_gitapex_check_channel_shape.py`
    (both new).
  - Task 3 owns `agents/branch-plan-task.md`, `.claude/agents/branch-plan-task.md`
    and `agents/review-persona.md`.
  - Task 4 owns `tests/test_gitapex_repository_channel_shape.py` (new) and
    `.gitapex/ssot.json`.
  - The four sets are disjoint;
    `scripts/gitapex_check_file_ownership_conflicts.py` reports no
    conflict across all four.
- **Interface-dependency map.** Two edges, both landing on Task 4:
  - Task 2 to Task 4: Task 4's integration test imports Task 2's own
    checker module, so it cannot be authored against a guess at that
    module's function names or `CheckResult` shape.
  - Tasks 1 and 3 to Task 4: Task 4's own proof method is that the real
    tree passes the new gate the day it lands (issue #1987's own stated
    reason for bundling the gate and the fixes in one change). That proof
    is false until Task 1's OpenCode mapping and Task 3's description
    rewrites are already on the branch, so Task 4 is sequenced after
    both, not co-assigned.
  - Tasks 1, 2 and 3 carry no edge among themselves: Task 2's
    tool-boundary-check logic reads `hooks/gitapex_sync_opencode.py`'s
    already-stable `AGENT_SPECS`/`_render_agent_copy` interface (Task 1
    adds a value to that structure, it does not change the structure's
    own shape), and Task 3's frontmatter edits do not depend on Task 2's
    checker existing to be written correctly.
- **Wave assignment.** Wave 1: Tasks 1, 2, 3 in parallel
  (`isolation: 'worktree'`). Wave 2: Task 4 alone.

Irreversibility classification: **not irreversible.** All four tasks add
or edit tracked files inside the repository. Nothing writes outside it,
no migration runs, no data is deleted, and `git revert` of the merge
commit restores the prior tree exactly. No task takes a step-1-equivalent
per-task confirmation.

`SKILL.md` classification: **none of the four tasks creates or edits a
`SKILL.md`.** Task 2 adds files under an existing skill's `scripts/`
directory, not its `SKILL.md` or `references/`; `drafting-a-skill` does
not apply to any task here.

Fixture-cost check: `gitapex_gate_skill_branch_fixture_coverage.py`
compares a changed `SKILL.md`'s own Stop-boundary-bullet and
named-dispatch-branch count against its fixture count. No task in this
branch touches `evaluating-context-channel-maturity/SKILL.md` itself, so
this gate's count does not move.

## Task 1: close the OpenCode tool-boundary gap for branch-plan-task.md

Source ACM row: row 2 of issue #1987's own Acceptance Criteria Map,
quoted verbatim rather than paraphrased.

> Row 2 planned ops: "Add the corresponding OpenCode permission mapping
> for `branch-plan-task.md` in `hooks/gitapex_sync_opencode.py`"

Proof method, inherited from row 2 and correction E3: the generated
OpenCode copy of `branch-plan-task.md` carries a permission mapping
denying an `mcp__github__*`-equivalent surface; `tests/test_gitapex_sync_opencode.py`
is extended to assert this (the existing
`test_agents_sync_rewrites_review_persona_for_opencode`-adjacent
coverage currently asserts the opposite -- no permission block -- and
must be updated, not left pinning the bug); the round-trip fidelity test
that module's own suite already carries stays green.

Binding constraint (correction E3): add only a permission-mapping
constant analogous to `REVIEW_PERSONA_PERMISSION` and update
`AGENT_SPECS`. Do not reintroduce either guard reverted in PR #1972 (the
multi-line-description guard, or its `#`-as-comment exemption) or the
related empty-permission-mapping fail-open guard -- all three stay scoped
to issue #1982, not this branch.

Red-Green order applies: write the failing assertion in
`tests/test_gitapex_sync_opencode.py` first (the generated OpenCode copy
of `branch-plan-task.md` currently carries no `permission:` block),
confirm it fails against the current tree, then land the mapping and
`AGENT_SPECS` update to turn it green.

## Task 2: build the channel shape checker and the three tool-boundary checks

Source ACM rows: rows 1 and 3 of issue #1987's own Acceptance Criteria
Map, plus correction E1, quoted verbatim rather than paraphrased.

> Row 1 planned ops: "Ship the three checks -- boundary declared, mapping
> present, mapping equivalent -- against the runtime frontmatter
> compatibility table the design records"

> Row 3 planned ops: "Add the checker and the index drift gate; register
> both in `.gitapex/ssot.json` `gates[]`" (this task builds the checker
> only; registration and the repo-wide integration test that is this
> row's own "index drift gate" are Task 4's own scope, sequenced after)

> Correction E1: "Row 1's Planned ops is read as: freshly fetch and cite
> primary sources for Claude Code agent frontmatter and OpenCode agent
> frontmatter (per AGENTS.md section 2's grounding requirement) and
> record the resulting minimal fact set as constants with citations in
> the new checker module itself, not as a new versioned registry file"

Scope for this task, precisely: a new module
`skills/evaluating-context-channel-maturity/scripts/gitapex_check_channel_shape.py`
(own threshold constants, no import from
`evaluating-skill-quality/scripts/shape_checks/` -- correction C4 of
issue #1963, `skills/` is on the deployed side of
`docs/repository-layout.md`'s boundary) implementing, against a target
`AGENTS.md`, `agents/*.md`, or `.claude/agents/*.md` file:

- a description-length check mirroring `gitapex_check_skill_shape.py`'s
  own `DESCRIPTION_MAX_CHARS`-shaped check, with its own 500-character
  constant for this channel;
- the same YAML-plain-scalar-safety check that sibling checker already
  applies to a SKILL.md description (no ` #`, no `: `, no trailing `:`,
  no multi-line scalar), reused here for a subagent-definition
  description, satisfying row 5's own "does not silently lose content"
  criterion for whatever Task 3 writes;
- three tool-boundary checks -- `tool-boundary-declared` (does the
  frontmatter state a boundary at all: `disallowedTools`/`tools:` on
  Claude Code), `tool-boundary-mapping-present` (does
  `hooks/gitapex_sync_opencode.py`'s `AGENT_SPECS` carry a non-`None`
  permission mapping for that same file), and
  `tool-boundary-mapping-equivalent` (does the mapping actually deny the
  declared boundary's surface, not merely exist) -- grounded in freshly
  fetched primary sources for both runtimes' own agent-frontmatter
  documentation (Claude Code's sub-agent docs, OpenCode's own
  `opencode.ai/docs/agents`), cited by URL and fetch date in the module's
  own docstring, the same citation shape
  `.gitapex/runtime-compatibility-matrix.json`'s entries already use.

Proof method, inherited from row 1 and row 3's checker half: unit tests
(`skills/evaluating-context-channel-maturity/scripts/test_gitapex_check_channel_shape.py`,
the sibling checker's own co-located-test convention) cover boundary
values for the description-length and YAML-safety checks, a fail-closed
path on malformed frontmatter, and both directions for each
tool-boundary check -- a synthetic fixture missing the boundary, missing
the mapping, and carrying a mismatched mapping each FAIL; a synthetic
fixture with a correct mapping PASSes. The three tool-boundary checks are
proven against synthetic fixtures only in this task -- proving them
against the real tree is Task 4's own scope, after Task 1 and Task 3 are
both merged.

Red-Green order: write the synthetic-fixture tests first (each asserting
a specific FAIL/PASS `CheckResult`), confirm the FAIL-shaped ones fail
against an empty/stub checker, then implement the checker to turn every
assertion green.

## Task 3: rewrite the two non-compliant subagent descriptions to trigger-only

Source ACM row: row 4 of issue #1987's own Acceptance Criteria Map, plus
correction E4, quoted verbatim rather than paraphrased.

> Row 4 planned ops: "Rewrite the descriptions of
> `agents/branch-plan-task.md`, `.claude/agents/branch-plan-task.md` and
> `agents/review-persona.md` to trigger-only"

> Correction E4: "`agents/branch-plan-task.md`... already reads as
> trigger-only under `B1`... Row 4's planned ops for this one file is
> therefore read as 'confirm already-compliant, no edit' rather than
> 'rewrite' -- the other two files this row names
> (`.claude/agents/branch-plan-task.md` at 1,074 characters, and
> `agents/review-persona.md` at 400 characters but carrying a
> `B1`-violating self-referential aside) still need the rewrite the row
> describes."

Scope for this task:

- `agents/branch-plan-task.md`: read and confirm the current 256-character
  description states only what the subagent is and when to call it, with
  no decision-number archaeology, issue citation, or rationale clause; no
  edit if that confirmation holds.
- `.claude/agents/branch-plan-task.md`: rewrite its 1,074-character
  description to trigger-only, moving any not-purely-routing content
  (the Decision 17/Decision 20/issue #1476 citations, the
  plugin-vs-project-local comparison) into the file's own body where it
  is not already stated there -- most of this content already duplicates
  the body per issue #1987's own row 5 caution, so confirm nothing
  described only in the old description is lost, per the same row's own
  "does not silently lose content" criterion.
- `agents/review-persona.md`: remove the description's
  self-referential aside ("not re-enumerated here, the same drift this
  section's own entry 1 already avoids for a different list") -- an
  authoring note about why the file is written the way it is, per B1's
  own definition of slop -- keeping the routing-relevant remainder
  (what the subagent is, that it is read-only, and the
  never-invoke-outside-the-list caution, which is itself routing
  information).

Whatever text lands must not reintroduce a ` #`, a colon-space, or a
multi-line scalar into any of the three descriptions (row 5's own
constraint, and correction E3's PR #1972 boundary) -- confirm this by
running Task 2's new YAML-safety check against each rewritten file once
Task 2 lands (Task 4's own integration step), and by eye against the
rule in the meantime, since Task 2 and Task 3 run in the same wave and
neither is guaranteed to observe the other's mid-wave state.

Proof method, inherited from row 4 and row 5: every one of the three
descriptions is under the 500-character cap; the `.claude/agents/branch-plan-task.md`
and `agents/review-persona.md` rewrites read as trigger-only under B1 on
inspection; `hooks/gitapex_sync_opencode.py`'s own round-trip fidelity
test (already covers `review-persona.md`) is extended, if not already
covered by Task 1's own change, to cover `branch-plan-task.md`'s
description too.

Red-Green order does not apply: the proof is a character-count bound and
a qualitative rubric read, not an automatable behavioral test authored
before the fix.

## Task 4: repository-wide integration gate and ssot.json registration

Source ACM row: row 3 of issue #1987's own Acceptance Criteria Map (its
"index drift gate" and registration half), plus correction E2, quoted
verbatim rather than paraphrased.

> Row 3 planned ops: "Add the checker and the index drift gate; register
> both in `.gitapex/ssot.json` `gates[]`"

> Correction E2: "This issue's own Proposed solution and Acceptance
> criteria row 3 explicitly ask to register the new checker (and the
> index drift gate) in `gates[]` regardless, so this sub-issue adds new
> entries rather than following the sibling checker's own unregistered
> precedent"

Scope for this task: `tests/test_gitapex_repository_channel_shape.py`,
mirroring `tests/test_gitapex_repository_skill_shape.py`'s own shape --
runs Task 2's checker against the real `AGENTS.md`, every real
`agents/*.md`, and every real `.claude/agents/*.md` file in this
checkout. Register this test (the "index drift gate") and the underlying
channel-shape-checker module in `.gitapex/ssot.json` `gates[]`, following
the existing `skill-quality-rubric-vocabulary-drift`/`skill-eval-status-doc-drift`
entries' own field shape (`kind: "script"`, `planes`, `local_invocation`,
`trigger` naming this new test file inside `test.yml`'s pytest step,
`cluster`, `tracking_issue: 1987`, `status: "active"`,
`bypass_review_status: "not-yet-reviewed"`).

Proof method, inherited from row 3 and row 1's own tool-boundary half:
the real tree -- after Tasks 1-3 land -- passes every check in the new
integration test, including all three tool-boundary checks (which FAIL
against `origin/main`'s pre-Task-1 state and PASS on this branch, proven
both directions per row 1's own residual-risk note); `ssot-schema-drift`
(`gitapex_scan_ssot_schema.py`) passes against the two new `gates[]`
entries.

Red-Green order applies at the repository-integration level: confirm
`tests/test_gitapex_repository_channel_shape.py`'s new tool-boundary
assertions would have failed against `origin/main` (Task 1 not yet
applied) before asserting they pass on this branch -- both directions
demonstrated, matching row 1's own stated proof method, not only the
passing direction.

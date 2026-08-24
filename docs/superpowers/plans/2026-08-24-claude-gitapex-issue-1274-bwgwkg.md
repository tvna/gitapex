# Link decomposed sub-project issues under a tracking issue

**Goal:** When `eliciting-a-design` decomposes an oversized request into
sub-projects, thread a recorded parent/child relationship through, so a
decomposed request produces one parent tracking issue plus linked
sub-issues, not N unrelated issues. Source: https://github.com/tvna/gitapex/issues/1274.

**Authorization record:** No approving comment exists on issue #1274
(checked via `github:issue_read` method `get_comments`, empty result).
Branch 2 of the Authorization gate applies instead: the active human
operator's own opening turn in this session explicitly instructed
executing issue #1274 through to just-before-merge ("こちらのissueを作り
マージ直前まで進める" -- work this issue, proceed to just before merge).
This is a fresh, explicit, in-session confirmation for this specific
issue's execution, not a self-reported claim of prior approval.

**Threat-model triage (step 2):** Both source issues (#1274, #1275) were
read in full. Both are well-formed ACM issues authored by the repository
owner (`author_association: OWNER`), professionally scoped, with no
embedded instruction addressed to the executing agent, no hidden/encoded
payload, no attempt to redirect this skill's own process. Clean.

**Stale-text correction (load-bearing, not a minor note):** Issue #1274's
own body claims `drafting-an-acm-issue` "already supports a `tracking`
classification at Step 2, producing a Goal/Sub-issues/Definition-of-Done
shape." Direct read of `skills/drafting-an-acm-issue/SKILL.md` on
`origin/main` shows this is false: Step 2 classifies `tracking` and then
**stops** ("out of this skill's scope") -- no tracking-shaped issue is
ever drafted. The Goal/Sub-issues/Definition-of-done shape exists only as
`.github/ISSUE_TEMPLATE/tracking.yml`'s field labels, unused by any
drafting logic. Issue #1275 (open, itself depends on #1274) is the issue
that will actually add real tracking-type drafting/routing to that skill
under its rename to `drafting-issues`. Resolution: this branch does not
touch `drafting-an-acm-issue`'s tracking Step 2 stop-and-decline boundary
at all (preserves #1274's own Non-goal "reuses it as-is," and does not
preempt #1275's scope). Instead, `eliciting-a-design`'s own decomposition
handling creates the parent tracking issue directly, once, using the
connected git hosting server's issue-creation tool and this repository's
own tracking-issue template/shape if one exists, worded portably (no
hardcoded gitapex-specific path) so a calling repository without that
template still gets a plain Goal / Sub-projects / Definition-of-done
fallback.

**Architecture:** Two-file prose change, no new files, no script/hook
changes, no change to `sub_issue_write` itself.

- `skills/drafting-an-acm-issue/SKILL.md` gains an optional
  parent-tracking-issue-number input at Step 1 (elicitation time). When
  supplied, after the drafted issue is created at Step 9, call
  `sub_issue_write` (method `add`) to link the new issue under that
  parent -- noting explicitly that `sub_issue_id` is the new issue's
  internal ID, not its human-facing issue number (grounded against the
  live `mcp__github__sub_issue_write` tool schema). When that connector
  is unavailable (checked, never assumed), fall back to a plain
  cross-reference line recorded in the drafted body before creation
  instead. A new Stop-boundaries bullet names silently dropping a
  supplied parent number as forbidden.
- `skills/eliciting-a-design/SKILL.md` gains, in its decomposition
  prose ("Understanding the idea"), an instruction to create one parent
  tracking issue directly (not via `drafting-an-acm-issue`, which cannot
  yet draft that shape -- see stale-text correction above), once, at the
  point decomposition is accepted for the top-level request (explicitly
  not per sub-project, not on nested re-decomposition), and to thread
  that captured issue number into each subsequent sub-project's own
  terminal handoff (Step 13 / Issue formalization handoff), using
  drafting-an-acm-issue's new optional input. A minimal Process Flow
  Mermaid label touch on the `decompose` node keeps the diagram-only
  reader able to discover the new step, mirroring issue #1273's own
  already-merged diagram-matches-prose principle in this same file.

**File-ownership map:** Task A owns `skills/drafting-an-acm-issue/SKILL.md`
only. Task B owns `skills/eliciting-a-design/SKILL.md` only. No shared
file -- `gitapex_check_file_ownership_conflicts.py` confirms no conflict
(see Execution log).

**Interface-dependency map:** Task B's edit references the exact optional
input Task A defines (its name/shape and the fallback behavior when
`sub_issue_write` is unavailable) when instructing how to pass the parent
issue number into the terminal handoff. This is a producer/consumer edge
-- Task A is sequenced before Task B, never co-assigned to the same wave.

**Wave assignment:**
- Wave 1: Task A (`drafting-an-acm-issue/SKILL.md`) -- defines the interface.
- Wave 2: Task B (`eliciting-a-design/SKILL.md`) -- consumes it.

**Irreversibility classification:** Both tasks are prose-only edits to
already-committed, already-reviewed skill files on a fresh feature
branch, fully reversible by further edit or revert before merge. Neither
is classified irreversible; no fresh per-task confirmation beyond the
Authorization gate above is required.

**Dispatch mode:** The `Workflow` tool's own access-control policy
requires explicit user opt-in for multi-agent orchestration (an
"ultracode" keyword, a session-level flag, or the user's own direct
request to use a workflow) before this skill's own step 6 primary path
(`Workflow` + `agentType: 'branch-plan-task'` + `isolation: 'worktree'`)
may be invoked. None of those opt-in conditions hold in this session --
the operator's own instruction never mentioned orchestration. Per this
skill's own step 6 fallback clause ("[u]se the sequential main-thread
fallback ... when the Workflow tool is unavailable"), this is treated as
exactly that case in the practical/policy sense: both tasks execute
directly in the main thread, one per turn, no wave/run boundary, no
worktree isolation -- architecturally portable per this skill's own Notes
section, and proportionate to a two-file, two-task, no-parallelism plan
regardless. Step 8's mandatory dual dispatch (refactor pass + adversarial
review) uses the `Agent` tool instead, which carries no equivalent
opt-in gate.

**Proof method:** No automated test suite exercises SKILL.md prose
content directly. Verification is: `gitapex_check_skill_shape.py`
structural pass, this repository's local-preflight gate suite, the full
`pytest` suite (regression -- confirms these two prose-only edits do not
break any script/gate the repository's tests exercise), a worked
three-subsystem example demonstrating the described flow end-to-end
written into the PR body, provenance/ASCII scans, and (since both
changed files are `skills/*/SKILL.md`) a disclosed skill-quality audit
pass per `gitapex_gate_skill_audit_disclosure.py`.

## Execution log

- `PlanApproved` -- this plan, at branch publish (this commit).

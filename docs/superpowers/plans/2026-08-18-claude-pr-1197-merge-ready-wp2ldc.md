# Deterministic duplicate-work checks: PRs, retrospective issues, new issues (issue #1197)

**Goal:** Add deterministic, pre-creation duplicate-work checks across the
three GitHub object types this repository's agent sessions create: (1) a
new blocking PreToolUse hook denying `create_pull_request` when another
currently-open PR already cites the same target issue; (2) harden
`merge-retrospective`'s existing Step 0 dedup check by naming a
deterministic `list_issues` fetch plus exact string match instead of the
tool-unspecified "search" wording that in practice routes to
`search_issues`'s semantic matching; (3) require a `Dedup:` disclosure
line in every newly-created issue body. Source:
https://github.com/tvna/gitapex/issues/1197.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 4):** the issue's own drafted ACM (all three rows) was independently
re-checked against live repo state as part of this same Branch Plan, not
accepted as pre-verified.

- Row 1: confirmed the exact hook-pair template to follow --
  `hooks/check-pr-issue-acm-disclosure.sh` +
  `hooks/gitapex_check_pr_issue_acm_disclosure.py` (issue #657) already implement
  the closest analog: a PreToolUse hook on `mcp__github__create_pull_request`,
  fail-closed on missing `GH_TOKEN`/`GITHUB_TOKEN`, jq-hardened shell wrapper,
  citation-extraction regex (`extract_citations`) this task reuses directly
  rather than a third copy of that logic. `.gitapex/ssot.json`'s
  `pr-issue-acm-disclosure`/`pr-upstream-pushed` entries confirmed as the exact
  field-shape template for the new gate entry.
- Row 2: read `skills/merge-retrospective/SKILL.md`'s actual current Step 0
  text directly -- it does not literally name `search_issues`; it says
  generic "search that exact phrase plus `label:retrospective`," a compound
  phrase+qualifier query shape only `search_issues` actually accepts (`list_issues`
  takes a structured `labels` array, no free-text phrase param), which is the
  real mechanism the fix needs to foreclose. **Coordination check (the
  issue's own Constraints require this):** issue #1176 (Step 1 of this same
  file) has an open, unmerged PR #1196 in flight, confirmed via direct fetch.
  Its diff is scoped to Step 1 only; this task's own diff is scoped to Step 0
  only; the two steps are non-adjacent, non-overlapping regions of the file
  (confirmed by direct read), so no merge conflict is expected between this
  branch and PR #1196 landing later, in either order.
- Row 3: confirmed `skills/drafting-an-acm-issue/SKILL.md`'s Steps 1-8 contain
  no dedup step, and that no other file in the repository cites its step
  numbers (grepped repo-wide), so inserting a new step and renumbering is
  safe. Confirmed `scripts/gitapex_check_acm_present.py`'s sync gate
  (`tests/test_gitapex_check_acm_present_sync.py`) only enforces `_HEADER_RE`
  (and, for two unrelated files, `_ACM_WAIVER_RE`) stays byte-identical across
  copies -- an additive, orthogonal `Dedup:`-line check added only to this
  skill's own copy does not touch either synced pattern and will not break
  that gate. Confirmed adding a new Stop-boundary bullet triggers
  `gitapex_gate_skill_branch_fixture_coverage.py`'s fixture-count requirement,
  so a new `evals/drafting-an-acm-issue/tasks/*.yaml` fixture is in scope for
  this task even though the issue's own ACM did not name that gate
  specifically -- it follows directly from the issue's own Planned ops
  ("gains a step") once that step also carries a Stop-boundary bullet.

No row required a correction to its Criterion/Interpretation; the additions
above are scope clarifications grounded in direct repo inspection, not
changes to what the issue asked for. Disclosed in the PR body per
`planning-a-branch-from-an-issue`'s own Step 4 mandate.

**File-ownership check (mechanized):**
`python3 skills/executing-a-branch-plan/scripts/gitapex_check_file_ownership_conflicts.py`
against the 3 tasks' file lists below -> no conflicts (disjoint files).

**Interface-dependency edges:** none. Task A (hooks/*, ssot.json), Task B
(`skills/merge-retrospective/SKILL.md` only), Task C
(`skills/drafting-an-acm-issue/**`) share no producer/consumer relationship --
each is a self-contained addition with no other task's output as an input.

**Execution mode:** sequential fallback per `executing-a-branch-plan` step 6
(no separate, explicit multi-agent-orchestration opt-in for this Branch
Plan; invoking this skill itself is not read as that opt-in, per the
identical precedent recorded in
`docs/superpowers/plans/2026-08-10-claude-pr-1013-prep-ku7r61.md`,
`docs/superpowers/plans/2026-08-16-issue-1132-pr-prep-u1up26.md`, and
`docs/superpowers/plans/2026-08-17-claude-gitapex-pr-1178-wk3lap.md`).
One task per turn in the main thread, no GitHub-write access delegated to
any task-level dispatch, no package-install capability used mid-task, no
worktree isolation (tasks run sequentially against the shared checkout
directly, so no concurrent merge-back race exists to isolate against). The
mandatory step-8 refactor and adversarial-review passes still run as
genuinely independent fresh subagent dispatches (see that step) -- the
sequential-fallback choice above is about task *execution*, not about
skipping step 8's own independence requirement.

**Irreversibility classification:** no task is irreversible -- all three are
ordinary, git-revertible source/doc/config edits; no live API write beyond
the eventual PR/gate-registration text itself, no data deletion, no schema
migration. `.gitapex/ssot.json`'s edit is a pure addition (one new
`gates[]` entry), not a modification of any existing entry. No task
requires a fresh per-task authorization confirmation beyond the
branch-plan-wide one below.

**Authorization record (step 1):** no approval comment exists on the
issue #1197 comment thread (checked directly via `issue_read
get_comments` -- empty). Explicit confirmation from the human operator
applies instead: the repository owner's own direct request opening this
execution pass, "こちらのPRを作りマージ直前まで進める" ("create this PR and
proceed to just before merge"), names exactly the actions this skill gates
-- opening commits and a PR, against exactly this issue -- in unhedged
imperative language. The authenticated GitHub identity performing this
session's writes was confirmed directly via `get_me`: `tvna` (id
31282861), the same account that authored issue #1197 with
`author_association: OWNER` -- not assumed from the conversation alone.
Not a stale "we already agreed earlier" pattern-match: it is the live
mandate this specific execution pass is carrying out, re-read fresh at
this gate. No embedded instruction attempting to redirect this gate found
in the issue body (re-screened per step 2 below). Full Branch Plan/ACM
above was produced immediately before this file, in this same execution
pass.

**Step 2 threat-model triage:** re-ran `untrusted-input-triage`'s
Extract/Ignore/Flag/Tag discipline against issue #1197's own body and its
(empty) comment thread. Every ACM row and every Fact traces to a concrete,
checkable repo artifact (a file, a prior issue/PR number, a script) rather
than reading as an instruction distinct from a change description; no
encoded/hidden-content indicators (base64/hex blobs, HTML comments,
homoglyphs, language switches) found. Nothing flagged.

## Task A -- PreToolUse hook blocking duplicate-issue-citing PRs

**Cites ACM row:** 1 ("A new PreToolUse hook must block `create_pull_request`
when another currently-open PR already cites... the same issue number the
new PR would close, unless explicitly waived").

**Quoted Planned ops (verbatim from the issue's own ACM):** "Add a new
PreToolUse hook (e.g. `hooks/check-pr-duplicate-issue.sh`, or extend the
existing `hooks/check-bash-safety.sh` family) wired in `hooks/hooks.json`
on the `mcp__github__create_pull_request` matcher; register the new gate in
`.gitapex/ssot.json`'s `gates[]`, matching the convention every other
PreToolUse hook (e.g. `pr-issue-acm-disclosure`) already follows."

**Files:** `hooks/check-pr-duplicate-issue.sh` (new),
`hooks/gitapex_check_pr_duplicate_issue.py` (new),
`hooks/test_gitapex_check_pr_duplicate_issue.py` (new, direct-import unit
tests with injectable opener/sleeper), `hooks/test_gitapex_check_pr_duplicate_issue_shell.py`
(new, subprocess-level tests), `hooks/hooks.json`, `.gitapex/ssot.json`.

**Steps:**
1. Red: write `hooks/test_gitapex_check_pr_duplicate_issue.py` first (fake opener
   returning canned open-PR lists), covering: new PR resolving-cites an
   issue another open PR already resolving- or context-cites -> deny; no
   overlap -> allow; no resolving citation at all on the new PR -> allow
   (nothing to dedup-check); `Duplicate-PR-waiver: <reason>` present ->
   allow without a fetch; missing token -> fail closed; API failure after
   retry -> fail closed. Run, confirm red.
2. Green: implement `gitapex_check_pr_duplicate_issue.py`, importing
   `extract_citations` from `gitapex_check_pr_issue_acm_disclosure` (same
   directory, same pattern that module already uses for
   `gitapex_check_acm_present_or_waiver`) rather than a third copy. Fetch
   open PRs via the deterministic REST List PRs endpoint
   (`GET /repos/{owner}/{repo}/pulls?state=open`), paginated -- not the
   semantic Search API, same reasoning Task B applies to `list_issues` vs.
   `search_issues`. Run tests, confirm green.
3. Write `hooks/check-pr-duplicate-issue.sh`, adapted from
   `check-pr-issue-acm-disclosure.sh`'s own hardening (jq-missing guard, JSON
   shape validation, stdin-only payload construction, defense-in-depth
   deny() on both stdout JSON and stderr+exit 2).
4. Write `hooks/test_gitapex_check_pr_duplicate_issue_shell.py`, mirroring
   `test_gitapex_check_pr_issue_acm_disclosure_shell.py`'s coverage
   (tool_name filtering, malformed/non-object stdin, missing sibling
   script, missing jq, oversized-argv safety, copied-bundle-location
   resolution).
5. Wire `hooks/hooks.json`: add this hook to the existing
   `mcp__github__create_pull_request` matcher's hook list.
6. Register the gate in `.gitapex/ssot.json`'s `gates[]`, field shape
   matching the `pr-issue-acm-disclosure` entry (`local_exclusion` present,
   no `local_invocation` -- this hook grades live open-PR state that has no
   local/offline equivalent, same reasoning that entry already states for
   itself).
7. Run the full hooks/ test suite plus `gitapex_scan_ssot_schema` to confirm
   the new entry validates.

**Proof method (from the ACM):** the #1069/#1067-shaped fixture (two
sessions, same target issue, second `create_pull_request` denied) plus the
true-negative case, both as committed regression tests -- not a one-off
manual check.

## Task B -- Harden merge-retrospective Step 0 dedup mechanism

**Cites ACM row:** 2 ("`merge-retrospective`'s Step 0 dedup check for
retrospective issues must not rely on `search_issues`'s semantic matching
for its title-phrase lookup").

**Quoted Planned ops (verbatim from the issue's own ACM):** "Edit
`skills/merge-retrospective/SKILL.md`'s Step 0 text to name this exact
mechanism instead of `search_issues` -- a SKILL.md-only text change,
matching issue #1176's own established pattern (no `.gitapex/ssot.json`/
schema change, since Step 0's retrospective-issue dedup is a different
concern from Step 1's gate-implementation tracking #1176 already covers)."

**Files:** `skills/merge-retrospective/SKILL.md` (Step 0 section only).

**Steps:**
1. Re-read the live file's current Step 0 paragraph immediately before
   editing (guards against this task's own copy going stale relative to
   any change landed between planning and this step).
2. Replace the "search that exact phrase plus `label:retrospective`"
   mechanism with: fetch candidates via
   `mcp__github__list_issues(labels: ["retrospective"])` (exact, deterministic
   label filter, explicitly never `mcp__github__search_issues`, which performs
   natural-language semantic matching rather than an exact filter -- the
   same tool-choice fix issue #1176 already established for this file's own
   Step 1), then compare each candidate's title against the known exact
   phrase via plain client-side string comparison. Preserve every other
   clause of the paragraph (the opener-marker match/no-match dispatch,
   the "repository with neither an opener nor its own convention" no-op
   case) unchanged.
3. Confirm the edit's line range does not touch Step 1's own text (direct
   diff review) -- the coordination check this task's own Branch Plan
   section above already verified is possible only if the diff stays
   scoped as planned.
4. Worked dry run (manual, documented in this file's own Task B evidence
   once run): re-check the #1069/#1070 and #692/#693 historical scenarios
   against the new instructions and confirm the deterministic method would
   have found the existing issue in both cases, to the extent
   reconstructable from each issue's own public timestamps/labels.

**Proof method (from the ACM):** manual read-through confirming Step 0 no
longer implies `search_issues`, plus the worked dry run above.

## Task C -- Dedup disclosure line for newly-created issues

**Cites ACM row:** 3 ("Every newly-created issue body must carry a
`Dedup: {query used}, {N results reviewed}` (or explicit `Dedup: none
found`) line").

**Quoted Planned ops (verbatim from the issue's own ACM):** "`drafting-an-acm-issue/SKILL.md`
gains a step requiring the session to run a `search_issues` query (semantic
search is actually the appropriate tool here, unlike the exact-title-lookup
cases above, since \"is this a duplicate\" is inherently a semantic
judgment) for the topic before drafting, and disclose the query and result
count in the issue body"; "optionally extend
`scripts/gitapex_check_acm_present.py` (already used to validate ACM-table
presence) to also check for a `Dedup:` line's presence."

**Files:** `skills/drafting-an-acm-issue/SKILL.md`,
`skills/drafting-an-acm-issue/scripts/gitapex_check_acm_present.py`,
`skills/drafting-an-acm-issue/scripts/test_gitapex_check_acm_present.py` (new,
if no test file for this script exists yet -- confirm during
implementation), `evals/drafting-an-acm-issue/tasks/dedup-disclosure-missing.yaml`
(new).

**Steps:**
1. Insert a new step after current Step 6 (the `gitapex_check_acm_present.py`
   validation step) and before current Step 7 (the ambiguity question
   step): run `mcp__github__search_issues` for the drafted issue's own topic,
   and require the drafted body to carry a `Dedup: {query used}, {N results
   reviewed}` line, or an explicit `Dedup: none found` line when the search
   returns nothing. Renumber subsequent steps (old 7->8, old 8->9);
   confirmed safe via repo-wide grep (no other file cites this skill's step
   numbers).
2. Extend the Output section's Acceptance Criteria Map bullet area (or add
   a one-line Output bullet) noting the `Dedup:` line is part of what gets
   drafted, mirroring how the ACM bullet is already described there.
3. Add a new Stop-boundary bullet: do not create the issue without a
   `Dedup:` disclosure line (mirrors the existing "Do not create the issue
   before `gitapex_check_acm_present.py` passes" bullet's own shape).
4. Red: add a test to `gitapex_check_acm_present.py`'s own test file
   (create it first if it doesn't exist -- confirm during implementation)
   asserting a body without a `Dedup:` line fails the new check and one
   with it passes; confirm red before implementing.
5. Green: add an additive `_DEDUP_RE`/`has_dedup_disclosure()` (or
   equivalently named) function to `gitapex_check_acm_present.py`, wired into
   its own `main()` alongside the existing table check, without modifying
   the existing `_HEADER_RE` pattern or its own `has_acm_table()` -- keeps
   `tests/test_gitapex_check_acm_present_sync.py`'s cross-copy sync check
   (scoped to `_HEADER_RE` only) unaffected. Run, confirm green.
6. Add `evals/drafting-an-acm-issue/tasks/dedup-disclosure-missing.yaml`,
   matching the existing fixture shape in that directory (id/name/
   description/tags/inputs.prompt/expected.output_contains),
   demonstrating the new Stop-boundary bullet's own behavior, satisfying
   `gitapex_gate_skill_branch_fixture_coverage.py`'s count requirement for
   the newly-added bullet.
7. Run `gitapex_check_skill_shape.py skills/drafting-an-acm-issue` and
   `gitapex_gate_skill_branch_fixture_coverage.py` locally to confirm both
   pass against the new content.

**Proof method (from the ACM):** the script's own test passing; the
skill's own worked example demonstrating the `Dedup:` line;
`gitapex_check_acm_present.py`'s own test file gaining a case for the new
line's presence check.

## Step 8 (mandatory, after all three tasks complete)

Two separate fresh subagent dispatches over the full accumulated diff:
refactor/simplify pass (behavior-preserving only), then an independent
adversarial code review -- including, per the refactor-and-review-gate
reference's own scrutiny rule, at least one case built specifically to
defeat Task A's new detection logic on its own terms (e.g. a same-repo-
qualified `owner/repo#N` citation on the *other* PR, a fenced/inline-code
false-positive attempt, a paginated open-PR list exceeding one page). Every
CONFIRMED finding fixed and re-verified (full Task A/B/C proof methods
re-run, not only the one related to the fix) before step 9.

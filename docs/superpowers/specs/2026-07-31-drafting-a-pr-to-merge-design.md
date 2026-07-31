# drafting-a-pr-to-merge: rename and DRAFT-terminal-state redesign

Date: 2026-07-31

Refs #637

## Context

The repo owner asked for four changes to `driving-pr-to-merge`
(`skills/driving-pr-to-merge/SKILL.md`, designed in
`docs/superpowers/specs/2026-07-12-driving-pr-to-merge-design.md`):

1. Rename the skill to something starting with "drafting".
2. Define "the state immediately before merge" as the PR sitting in
   GitHub's native DRAFT state -- specifically so the agent can never
   auto-merge content that presupposes a human doing the actual merge.
3. Always leave a PR comment after resolving a merge conflict, no
   exceptions.
4. Keep periodically monitoring a DRAFT PR for other merge-blocking
   factors (a new conflict, a newly-failing check) -- reaching DRAFT is
   not a reason to stop watching.

## Naming: `drafting-a-pr-to-merge`

A spec doc from three weeks earlier
(`docs/superpowers/specs/2026-07-22-plan-execution-handoff-design.md:118-132`)
documents a "verb-per-phase convention (draft -> plan -> execute ->
drive-to-merge)" that, at the time, treated "draft" (issue-authoring,
e.g. `drafting-an-acm-issue`) and "drive-to-merge" as distinct phases.
That convention is not being violated here so much as caught up with: the
two existing `drafting-*` skills (`drafting-an-adr`,
`drafting-an-acm-issue`) both mean the same thing by "drafting" -- the
skill produces a draft artifact requiring human follow-through, never a
finished one, and states that plainly to the reader. Once this skill's own
terminal action is leaving the PR in GitHub's native draft state, that is
now literally true of it too. `drafting-a-pr-to-merge` was chosen over
`drafting-a-mergeable-pr` / `drafting-a-merge-ready-pr` because it keeps
the original's "PR to merge" wording, so most existing cross-repository
prose reads correctly with a single substring swap.

## Why `mergeable_state` alone cannot drive requirement 4

Primary source: GitHub's public GraphQL schema
(`https://docs.github.com/public/fpt/schema.docs.graphql`, fetched
2026-07-31). Two separate, both-real fields:

- `MergeStateStatus` (REST's undocumented `mergeable_state` mirrors this
  enum): `BEHIND`, `BLOCKED`, `CLEAN`, `DIRTY`, `DRAFT` ("The merge is
  blocked due to the pull request being a draft" -- deprecated in the
  schema in favor of `isDraft`, but still the literal value REST's
  `mergeable_state` returns today), `HAS_HOOKS`, `UNKNOWN`, `UNSTABLE`.
- `mergeable: MergeableState!` ("Whether or not the pull request can be
  merged based on the existence of merge conflicts"): `CONFLICTING`,
  `MERGEABLE`, `UNKNOWN`. Not gated by draft status -- always computed.

Once a PR is draft, `mergeable_state` collapses to the single bucket
`"draft"` and stops reporting what it would otherwise say. Requirement 4
(detect a new conflict on an already-draft PR) is therefore impossible to
satisfy by re-reading `mergeable_state`; the skill has to check the
separate `mergeable` boolean (REST) directly, alongside check-runs and
reviews.

## Skill content changes

- Frontmatter/title renamed; description's ending states the DRAFT
  terminal state and "This skill never merges a PR itself" explicitly.
- Step 6's `"dirty"` branch gains the always-comment-after-resolution
  rule (requirement 3) -- stricter than this environment's general
  default of commenting only on ambiguous resolutions.
- Step 6's `"draft"` branch is redefined: no longer an automatic
  escalation. Once this skill has reached its own step 8, DRAFT is the
  intended terminal state; the branch now checks `mergeable`/checks/
  reviews directly (since `mergeable_state` itself will not reveal
  anything further) and only loops back to step 2 if one of those is
  not actually clean.
- New step 8 ("Establish the DRAFT terminal state"): calls
  `github:update_pull_request` with `draft: true`; explicitly never calls
  `github:merge_pull_request`. This replaces the old worked example's
  ambiguous "merge it or hand it to the owner... per repo policy" ending.
- New step 9 ("Keep monitoring after reaching DRAFT", requirement 4):
  the step 1 subscribe/poll mechanism stays active after draft
  conversion; a periodic self-check-in is named as one portable fallback
  mechanism among others, mirroring step 1's own environment-agnostic
  phrasing.
- Old step 8 ("Escalate") renumbers to step 10.
- Two new Stop-boundary bullets (never merge; never stop monitoring after
  DRAFT) plus the always-comment-after-conflict bullet -- 10 Stop-boundary
  bullets total, up from 7.
- `executing-a-branch-plan/SKILL.md`'s own "vs. `drafting-a-pr-to-merge`"
  cross-reference is updated to explain the two skills' different reasons
  for using GitHub's draft state (that skill's step 5 draft is a WIP
  marker during execution; this skill's step 8 draft is the finished,
  human-merge-pending state) and to record, rather than silently drop,
  the edge case where this skill invoked standalone against a
  still-executing draft PR could misread a momentarily-clean snapshot as
  its own terminal state.

## Closing an enforcement gap in the same change (requirement 2)

`hooks/check-bash-safety.sh` already blocks the shell `gh pr merge`
command (including `--auto`), backing
`planning-a-branch-from-an-issue/SKILL.md`'s existing "never merge, that
is a human/CI decision" boundary. `hooks/hooks.json` had no equivalent
PreToolUse matcher for the MCP tool call `mcp__github__merge_pull_request`
-- an agent could reach the same outcome through the platform-integrated
tool instead of the CLI. CLAUDE.md ch.3's rule ("if the gate is missing,
build it before the operation it guards... ship its drift gate in the
same change, not a follow-up") applies directly, since this change is the
one making "never merge" a hard invariant for this skill specifically.
`hooks/check-merge-pull-request-block.sh` closes the gap: an unconditional
deny (no override phrase -- there is no legitimate agent-side exception,
unlike the ACM/skill-audit hooks which condition on PR-body content).
`check-bash-safety.sh`'s own `gh pr merge` deny message is corrected in
the same change -- it previously read "use the platform-integrated tool
call instead of the gh CLI," which would have misleadingly pointed an
agent at the now-also-blocked `merge_pull_request` call.

This piece has a wider blast radius than the other three requirements --
it changes behavior for every skill in this repository that could call
`merge_pull_request`, not only this one. It was called out separately to
the repo owner at plan time for exactly that reason, rather than folded
in silently.

## Eval changes

`evals/driving-pr-to-merge/` renamed to `evals/drafting-a-pr-to-merge/`.
`draft-state.yaml` rewritten for the new terminal-state semantics.
`.github/scripts/gate_skill_branch_fixture_coverage.py`'s delta-scoped
decision-branch gate (issue #49) requires this skill's own
`evals/drafting-a-pr-to-merge/tasks/*.yaml` fixture count to be at least
its Stop-boundary-bullet-plus-named-dispatch-branch count once any of
that content changes -- 17 after this change's edits (10 Stop-boundary
bullets + 7 `mergeable_state` dispatch tokens), up from 14 before. Ten
new task files were added (not just the three the four requirements
directly implied) to clear that threshold with real, distinct coverage
rather than padding: the previously-untested `"unknown"` dispatch branch,
a stale-verdict re-confirmation case, an inconclusive-`/code-review`
escalation case, an instruction-injection-in-the-verdict case, an
outward-artifact-preflight-before-posting case, a noise-dismissal case,
and a social-pressure-to-merge case, alongside the three the requirements
named directly (always-comment-after-conflict, draft-PR-still-monitored,
never-merge-is-the-terminal-action).

## Non-goals

- Does not change `merge-retrospective`'s own trigger ("a pull request
  has just merged") -- a human or CI still eventually merges; this change
  only removes the agent itself from that path.
- Does not attempt to block merging via the raw GitHub web UI or the `gh`
  CLI/API outside this repository's own hook coverage.
- Does not re-litigate the repository's `drafting-*` vs.
  `driving-to-merge` phase-naming convention beyond the one paragraph
  above.

## Verification

- `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py`
  (or its pytest suite) against the renamed skill.
- `.github/scripts/gate_skill_branch_fixture_coverage.py`'s own counting
  functions, run directly against the new `SKILL.md`, confirm 17 decision
  branches against 17 fixture files.
- `uv run pytest hooks/` (all hook regression suites, including the new
  `test_check_merge_pull_request_block.py`).
- `battle-testing-a-skill` and `evaluating-skill-quality` run against
  `drafting-a-pr-to-merge`, findings disclosed in the PR body per
  `hooks/check-pr-skill-audit-disclosure.sh`'s own requirement (the diff
  touches `skills/*/SKILL.md`).

Every dated file under `docs/superpowers/plans/`, `docs/superpowers/specs/`,
and `docs/superpowers/reports/` that mentions `driving-pr-to-merge` in
passing as of its own authoring date is left untouched -- this repository's
own precedent (the `github-surface-audit` -> `auditing-git-hosting-surface`
rename, see `docs/superpowers/specs/2026-07-15-git-hosting-surface-audit-design.md:16`)
records a rename's rationale in a fresh dated doc rather than editing
history.

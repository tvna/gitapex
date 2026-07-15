# ranking-the-open-queue Implementation Plan

**Goal:** Add a gitapex skill that sweeps a backlog of open issues/PRs and
hands the operator a decision-ready ranked queue, closing the "which of
these N open items should I even look at, and in what order" gap no
existing skill covers.

**Tracking:** #83 (triage cluster). **This skill's issue:** #84.

**Architecture:** One new skill directory `skills/ranking-the-open-queue/`
holding a platform-general `SKILL.md` (paginated `list_issues`/
`search_issues` sweep -> scoring -> ranked table output) and a
`references/scoring-rubric.md` detailing the four scoring axes below.
Deferred to a future cycle (see Task 2 onward); this cycle only lands the
design docs (Task 1).

## Scoring axes (fixed by this design, not left to per-run judgment)

- **Severity** -- does the item's own template/labels indicate a defect
  (`bug` label / `fix` issue type) vs. an enhancement/chore.
- **Staleness** -- time since last human activity (comment, commit,
  review), not since creation -- an old issue with recent activity is not
  stale.
- **Blockage** -- is it waiting on something (an open dependency issue, a
  pending external decision) that makes acting on it now wasted effort.
- **Actionability** -- does it have enough information to start now (an
  Acceptance Criteria Map, a reproduction, a clear scope) or does it need
  `responding-to-a-fresh-arrival`'s clarification pass first.

Output: a table (per this repo's own force-multiplier convention --
visualizations over prose for state), not a paragraph ranking.

## Global constraints

- Read-only: this skill never mutates an issue/PR itself; it only reads
  and reports a ranking. Any label/comment application it might recommend
  is left to the operator or to `responding-to-a-fresh-arrival`.
- Uses `list_issues`/`search_issues` per the GitHub MCP server's own
  guidance (list_* for broad retrieval, search_* for targeted queries);
  does not shell out to `gh`.
- ASCII only, ships no bundled script initially (scoring is a judgment
  call across four qualitative axes, not a deterministic rule a script
  could apply consistently -- revisit only if a future review flags
  scoring drift across runs).

---

### Task 1: Issue and design docs (this cycle)

- [x] Confirm no duplicate issue existed (`search_issues` run against
      "backlog", "triage", "low-trust", "wrapper", "surface audit" terms,
      2026-07-15 -- no match).
- [x] Open #84 (`feat(skills): add ranking-the-open-queue skill`), child
      of #83.
- [x] Commit this plan doc plus the shared
      `docs/superpowers/specs/2026-07-15-triage-cluster-design.md`,
      citing #84 and #83.

### Task 2: SKILL.md authoring (deferred -- future cycle)

- [ ] Write `skills/ranking-the-open-queue/SKILL.md`: trigger/description
      with the disambiguation clause from the shared spec, numbered sweep
      procedure, output table contract.
- [ ] Write `skills/ranking-the-open-queue/references/scoring-rubric.md`:
      the four axes above, each with a worked example.
- [ ] Run `evaluating-skill-quality` against the new `SKILL.md` before
      merging (Dimension 1 in particular, given this skill's own naming
      history).

### Task 3: Eval coverage (deferred -- future cycle, after Task 2 lands)

- [ ] `evals/ranking-the-open-queue/eval.yaml` + 3 task fixtures
      (normal/edge/guardrail), mirroring `evals/issue-to-branch/`'s shape.

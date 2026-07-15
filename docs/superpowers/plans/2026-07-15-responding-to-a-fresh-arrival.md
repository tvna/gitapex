# responding-to-a-fresh-arrival Implementation Plan

**Goal:** Add a gitapex skill that gives a single newly-arrived issue/PR a
fast, latency-focused first response (reproduce-or-refute, label, dedupe,
respond) -- the moment before anyone decides whether it becomes real work,
which `issue-to-branch` does not cover (it assumes the item is already
accepted).

**Tracking:** #83 (triage cluster). **This skill's issue:** #85.

**Architecture:** One new skill directory
`skills/responding-to-a-fresh-arrival/` holding a platform-general
`SKILL.md`. Deferred to a future cycle (see Task 2 onward); this cycle
only lands the design docs (Task 1).

## Procedure outline (fixed by this design)

1. **Reproduce or refute.** For an issue: attempt the reported repro steps
   if any exist; state explicitly if reproduction was not attempted and
   why. For a PR: read the diff directly, do not rely on the description
   alone.
2. **Dedupe.** `search_issues` for likely duplicates before responding;
   never post a first response that ignores an existing open duplicate.
3. **Label.** Apply the repo's existing issue-type labels (see
   `.github/ISSUE_TEMPLATE/*.yml`) based on content, not the reporter's
   own (possibly wrong) template choice.
4. **Respond.** Post one first-response comment: acknowledge, state
   reproduction result, link any duplicate found, and note next step
   (e.g. "routing to ranking-the-open-queue's next sweep" or "ready for
   issue-to-branch").

## Relationship to other skills (co-firing, stated explicitly)

When the fresh arrival is from an unknown or low-trust author, this skill
and `screening-a-low-trust-contribution` are both expected to fire on the
same event -- this skill handles content/response, the other handles
diff/metadata threat screening. Apply both; neither substitutes for the
other. (Mirrors `outward-artifact-preflight` + `explaining-the-work`'s
established co-firing pattern.)

## Global constraints

- Distinct from `ranking-the-open-queue` (whole-backlog sweep, not a
  single arrival) and from `issue-to-branch` (assumes the item is already
  accepted work with a plan being built).
- ASCII only. Uses platform-integrated tool calls, not `gh` CLI (per
  `hooks/check-bash-safety.sh`'s existing deny rule on `gh issue`/`gh pr`
  writes).

---

### Task 1: Issue and design docs (this cycle)

- [x] Confirm no duplicate issue existed (`search_issues` run 2026-07-15
      -- no match).
- [x] Open #85 (`feat(skills): add responding-to-a-fresh-arrival skill`),
      child of #83.
- [x] Commit this plan doc plus the shared
      `docs/superpowers/specs/2026-07-15-triage-cluster-design.md`,
      citing #85 and #83.

### Task 2: SKILL.md authoring (deferred -- future cycle)

- [ ] Write `skills/responding-to-a-fresh-arrival/SKILL.md`: trigger/
      description with the disambiguation clause from the shared spec,
      the four-step procedure above, and the `## Relationship to other
      skills` section verbatim as drafted here.
- [ ] Coordinate wording of the co-firing section with
      `screening-a-low-trust-contribution`'s own `SKILL.md` so both sides
      say the same thing (avoid drift between the two descriptions).

### Task 3: Eval coverage (deferred -- future cycle, after Task 2 lands)

- [ ] `evals/responding-to-a-fresh-arrival/eval.yaml` + 3 task fixtures,
      including one exercising the co-firing case with
      `screening-a-low-trust-contribution`.

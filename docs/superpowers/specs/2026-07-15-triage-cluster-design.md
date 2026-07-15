# Triage cluster: three rapid-response skills for gitapex

Date: 2026-07-15

## Context

A Fable-assisted skill-gap analysis (Known/Unknown blind-spot pass against
this repo's stated mission -- rapid issue/PR triage, autonomous bug
repair, layered Git defense) found three distinct trigger-moments this
repo has no skill for:

1. **Backlog-wide ranking.** Every existing skill (`issue-to-branch`,
   `driving-pr-to-merge`, `merge-retrospective`) operates on a single,
   already-selected issue/PR. Nothing decides *which* item to act on first
   across a whole backlog.
2. **Single-arrival first response.** `issue-to-branch` assumes the item is
   already accepted work with a plan being built. Nothing handles the
   moment right after a new issue/PR lands: reproduce-or-refute, label,
   dedupe, respond.
3. **Diff-level adversarial screening.** `untrusted-input-triage` triages a
   single piece of externally-authored *text* (issue body, PR description,
   comment, CI log). Nothing inspects a PR/issue's *diff and metadata*
   (workflow-file edits, hook/script changes, dependency additions,
   typosquats) for a contribution from an unknown or low-trust author.

## Naming and the routing-ambiguity problem

The first candidate names (`triaging-the-backlog`, `pr-triage-first-response`,
`adversarial-contribution-screen`) were evaluated against
`evaluating-skill-quality`'s Dimension 1 (Discovery -- name and
description) and found to collide: all three shared the root word
"triage." The rubric names this exact failure mode: "Avoid vague or
overly generic names ... Also flag inconsistent naming patterns across a
skill collection," and a fail example is "a trigger so generic it would
also match a sibling's request."

**Owner-approved decision:** resolve this with a *workflow design
pattern*, not just distinct names. Two live patterns already exist in this
repository for exactly this situation, found by re-reading the actual
shipped SKILL.md files (not invented for this spec):

- **Sibling disambiguation via `description:` clause.**
  `evaluating-skill-quality`'s description ends: "...see
  battle-testing-a-skill for adversarial hostile-input probing, and
  gated-skill-edits for a measured edit loop, instead." `battle-testing-a-skill`'s
  description ends: "Distinct from untrusted-input-triage, which triages
  inbound external text before acting; this evaluates a skill file's own
  robustness." A skill-gap triage report
  (`docs/superpowers/reports/2026-07-13-skill-gap-triage.md:41`) treats a
  *missing* disambiguation clause as a defect, not a nice-to-have.
- **Explicit co-firing via `## Relationship to other skills`.**
  `outward-artifact-preflight/SKILL.md` states: "Finalizing a commit or PR
  message can trigger both this skill and the explaining-the-work skill at
  once, where both are installed -- that is expected, not a conflict...
  Apply both; neither substitutes for the other."

This repo has **no precedent for a router/dispatcher skill** sitting above
a cluster, and building one here would be exactly the kind of unneeded
abstraction this repo's own simplicity discipline (CLAUDE.md section 4)
warns against. The plan below reuses the two patterns that already work
instead.

## The three skills, disambiguated

| Skill | Trigger moment | Disambiguation clause (verbatim, for its future `description:`) |
|---|---|---|
| `ranking-the-open-queue` | Periodic sweep: many already-known open issues/PRs | "...see `responding-to-a-fresh-arrival` for a single newly-arrived item's initial response, and `screening-a-low-trust-contribution` for diff-level threat screening of an unknown author's contribution, instead." |
| `responding-to-a-fresh-arrival` | Event: one issue/PR just arrived | "...distinct from `ranking-the-open-queue` (whole-backlog sweep, not a single arrival) and `issue-to-branch` (assumes the item is already accepted work)." |
| `screening-a-low-trust-contribution` | Event: a PR/issue from an unknown/low-trust author | "...distinct from `untrusted-input-triage`, which triages a single piece of externally-authored text; this inspects a diff and its metadata." |

`responding-to-a-fresh-arrival` and `screening-a-low-trust-contribution`
are expected to co-fire on the same event (a new PR from an unknown
author) -- each must carry a `## Relationship to other skills` section
stating this explicitly, mirroring `outward-artifact-preflight`'s.

## Scope of this design pass

Per the operator's chosen execution scope: this spec plus one
`docs/superpowers/plans/2026-07-15-<skill-name>.md` per skill (issue
number, scoring/check details, and a future build-task outline). **No
`skills/*/SKILL.md` file is authored in this pass** -- building the actual
skills is deferred to a following cycle, matching this repo's own
"propose this cycle, build next" discipline (already applied by
`merge-retrospective`'s own stop boundary).

## Non-goals

- No router/dispatcher skill (see above).
- No change to any existing skill's `SKILL.md` in this pass.
- No eval suite (`evals/<skill>/`) authored yet -- follows once the skill
  itself is built, matching this repo's own established sequencing
  (`evals/issue-to-branch/` was added with the skill, not before it).

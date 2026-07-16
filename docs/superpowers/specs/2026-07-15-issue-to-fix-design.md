# issue-to-fix skill for gitapex

Date: 2026-07-15

Refs #89. Terminology resolution recorded in `docs/glossary.md`.

## Context

This repo's mission names "autonomous bug repair" as a pillar, and a
Fable-assisted gap analysis found no skill covers it: `driving-pr-to-merge`
fixes CI on an *already-open* PR (a fix is already in flight); nothing
goes from a bare issue report to a scoped, verified fix.

**Naming resolution (owner-approved, this session):** the initial
candidate name `bug-report-to-fix` was checked against this repo's
established vocabulary via `establishing-ubiquitous-language`'s
Elicit/Detect/Resolve steps:

- **Elicit:** every existing skill/doc uses "issue" as the single term
  for a tracked unit of work (`issue-to-branch`, `merge-retrospective`,
  `docs/motivation.md`); "bug report" appeared only in this new
  candidate name, naming a subset (defect reports specifically).
- **Detect:** a term-to-concept mismatch, not two synonyms already
  colliding in the wild -- "bug report" risked introducing a second word
  for a concept "issue" already names in this repo, the same failure
  pattern `establishing-ubiquitous-language`'s own worked example
  documents for "Owner" vs "Contributor."
- **Resolve:** asked the owner directly rather than picking silently.
  Answer: **"issue" wins; "bug report" retires as a superseded synonym.**
- **Maintain:** recorded in `docs/glossary.md` (this repo's first real
  glossary entry -- the file did not exist before this session).

The skill is named `issue-to-fix`, matching `issue-to-branch`'s own
naming convention exactly: same input noun (`issue`), different terminal
artifact (`branch`/plan vs. `fix`).

## Procedure outline (fixed by this design)

A hard-gated, order-dependent sequence -- mirroring
`driving-pr-to-merge`'s own "fragile, order-dependent sequence, not a
matter of prose judgement" framing, not a matter of prose judgement here
either:

1. **Reproduce.** Attempt the issue's reported reproduction steps
   directly. Never proceed to a fix without a live reproduction.
2. **Escalate on failed reproduction.** If reproduction fails, stop and
   escalate explicitly rather than guessing at a fix for an unreproduced
   defect: comment on the issue stating what was tried and what did not
   reproduce if one exists, or open a new issue recording the same when
   the input is a standalone CI failure with no linked issue (see
   "Amendment" below). This is the same "ambiguous input earns a
   question, evidence earns a fix" discipline CLAUDE.md section 2
   already states as a general principle, applied concretely here.
3. **Write a failing test first.** Once reproduced, encode the failure as
   a test that fails for the right reason before touching the fix.
4. **Fix minimally.** The smallest change that makes the failing test
   pass, per CLAUDE.md section 4's simplicity discipline -- no
   surrounding refactor bundled in.
5. **Verify the test flips.** Confirm the same test now passes, and that
   no other existing test regressed.

## Disambiguation

- **vs. `driving-pr-to-merge`:** that skill fixes CI on an already-open
  PR where a fix is already in flight; this skill starts from a bare
  issue report with no fix yet, and produces the PR `driving-pr-to-merge`
  would then take over.
- **vs. `issue-to-branch`:** that skill produces an implementation-ready
  branch/PR *plan* with an Acceptance Criteria Map; it does not itself
  reproduce or fix a defect. `issue-to-fix` is the skill that actually
  reproduces and fixes, for the specific case of a reported defect (as
  opposed to `issue-to-branch`'s general issue-to-plan scope, which
  covers features and chores too).

## Scope of this design pass

Per the operator's chosen execution scope: this design doc plus
`docs/superpowers/plans/2026-07-15-issue-to-fix.md`, plus
`docs/glossary.md`'s first entry (already committed alongside this
batch). No `skills/*/SKILL.md` file is authored in this pass.

## Non-goals

- Does not retroactively rename any existing code or identifier using
  "bug"/"defect" wording elsewhere in this repo -- per
  `establishing-ubiquitous-language`'s own Stop boundary, renaming
  existing identifiers is a separate refactor decision, not something
  this terminology resolution executes.
- Does not build an eval suite yet (deferred to the same future cycle as
  `SKILL.md` authoring).

## Amendment (2026-07-16)

`skills/issue-to-fix/SKILL.md` and `evals/issue-to-fix/` landed in PR #112
(closes #89). An automated reviewer on that PR (chatgpt-codex-connector,
P2) flagged a real gap: this design's Step 2 as originally written
("comment on the issue") has no valid target when the input is a
standalone CI failure not linked to any issue -- a case this skill's own
trigger explicitly claims to cover ("a CI failure with no scoped fix
yet").

**Resolution (owner-approved, same session):** rather than narrowing the
skill's scope to issue-backed reports only, Step 2 now branches:

- Existing issue -> comment on it (unchanged from the original design).
- No linked issue (e.g. a standalone/scheduled CI failure) -> open a new
  issue recording the same evidence (what was tried, what did not
  reproduce), per this repository's own "open an issue before any
  branch, commit, or PR" convention (CLAUDE.md section 3) -- rather than
  inventing a separate, repo-specific escalation channel for CI-only
  input.

Either branch still stops at Step 2 without guessing at a fix; only the
escalation target differs by input shape. The Step 2 text above and
`skills/issue-to-fix/SKILL.md`'s own Step 2 and worked-example sections
were both updated to match.

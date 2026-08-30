# Reorder outward-artifact-preflight's checklist so ASCII runs before submission (issue #785)

**Goal:** reorder `skills/outward-artifact-preflight/SKILL.md`'s checklist
so every pre-submission check (provenance, ASCII, closing-keyword
narration hazard) runs before the artifact is pushed/posted, and the
post-creation re-check runs last, after submission. Source:
https://github.com/tvna/gitapex/issues/785.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 5):** performed this session, recorded as a re-verification marker
on issue #785's own body (2026-08-29T00:00:00Z). One correction: the
issue's own body was written against a 3-check version of the file
(provenance / post-creation re-check / ASCII). The file has since grown a
fourth check, `Closing-keyword narration hazard`, itself a pre-submission
check like provenance and ASCII. Applying the issue's own stated
principle (pre-submission checks run before submission; the post-creation
re-check runs last) to the current 4-check file places the
closing-keyword check ahead of the post-creation re-check too, not only
the ASCII check the issue named explicitly. Both ACM rows' proof intent
(reorder only, no logic change; diff review) is otherwise unchanged.

**File-ownership check:** single task, single file
(`skills/outward-artifact-preflight/SKILL.md`) -- no sibling task, no
conflict to compute.

**Canonical-governance-paths pre-filter (mechanized):**
`gitapex_check_canonical_governance_paths.py` against the 1 changed path
-> 1 `governance` match (`skills/outward-artifact-preflight/SKILL.md` --
expected: a `SKILL.md` is exactly this repository's own governance/
instruction-file category). Full model review (the
`untrusted-input-triage` Extract/Ignore/Flag/Tag pass over the ACM's own
text) still runs regardless of that classification: nothing in the
issue's Current structure, Proposed structure, Constraints, or ACM text
reads as an injected instruction rather than a change description --
every Planned-ops phrase ("Reorder...", "Edit...", "renumber and
relocate...") describes what to build, authored by the issue's own
OWNER-author, consistent with every other ACM this repository's
`planning-a-branch-from-an-issue` has produced.

**Interface-dependency edges:** none -- single task.

**Wave assignment:** wave 1 -- task-1 alone.

## Task 1: reorder the checklist and update cross-references

**Source ACM row (quoted verbatim, re-verified plan superseding the
original 3-check row):**

> Check 1: Undisclosed provenance markers (pre-submission) -- unchanged,
> stays first. Check 2: ASCII-only (pre-submission) -- moved up from
> Check 3. Check 3: Closing-keyword narration hazard (pre-submission) --
> moved up from Check 4. (submit) Check 4: Post-creation re-check
> (post-submission) -- moved down from Check 2; its own text updated to
> state it re-runs checks 1 and 2 (provenance and ASCII) against the
> stored body. All renumbered cross-references (the "Run all four
> checks" intro line, the worked examples' "Check 2 has nothing to fire
> on here" and "second worked example below" pointers, and the Stop
> boundary's check 1/check 2 mentions) get updated to match. No check's
> own pass/fail logic changes.

**Files:** `skills/outward-artifact-preflight/SKILL.md` (only).

**Ops:**
1. Reorder the four checklist sections in `SKILL.md`'s `## Checklist` to:
   provenance (1, unchanged), ASCII-only (2, was 3), closing-keyword
   narration hazard (3, was 4), post-creation re-check (4, was 2).
2. Update the post-creation re-check's own body text to state it re-runs
   both check 1 (provenance) and check 2 (ASCII) against the raw-fetched
   stored body, rather than only check 1.
3. Update every cross-reference elsewhere in the file to the new numbers:
   the checklist intro line, both worked examples (including the "Check 2
   has nothing to fire on here ... See the second worked example below"
   pointer), and the Stop boundary section's check 1/check 2 mentions.
4. Do not change any check's own pass/fail logic, criteria, scripts, or
   commands -- position and numbering only.

**Proof method:** read the reordered file; confirm each check's own body
text is byte-for-byte unchanged except for its section number and any
renumbered cross-reference, and confirm the post-creation re-check's text
now names both provenance and ASCII. No automated test exists for this
file (it is prose, not code) -- proof is diff review, per the issue's own
stated proof method.

**Irreversibility:** none -- a documentation reorder inside a version-
controlled file, trivially revertable.

## Step 8 (refactor/adversarial-review gate)

Runs once over this single task's diff after wave 1 completes, per this
skill's own mandatory, non-skippable step 8 -- the single-task case does
not exempt it.

## Skill Audit Evidence (Step 10, `planning-a-branch-from-an-issue`)

This PR modifies a `SKILL.md`. Waived: `evaluating-skill-quality` and
`battle-testing-a-skill`'s full audits are not run, because this change
is a pure section-reorder plus one clarifying sentence in the
post-creation re-check's own text -- no check's pass/fail logic, script,
or command changes. Diff review (this task's own proof method) is judged
sufficient in place of a full quality/adversarial audit; disclosed here
per Step 10 rather than silently omitted.

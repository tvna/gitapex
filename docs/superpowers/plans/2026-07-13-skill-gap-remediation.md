# Skill Gap Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Systematically review all 11 skills under `skills/` against the
`evaluating-skill-quality` skill's rubric, using parallel `fable`-model
subagents for analysis, then close the gaps found — auto-fixing minor
issues and getting explicit user approval before fixing major ones.

**Architecture:** One Sonnet-driven orchestration flow: (1) spawn 11
parallel Fable analysis agents, one per skill directory, each running the
`evaluating-skill-quality` procedure and returning structured findings;
(2) Sonnet aggregates and sanity-checks the findings against the actual
files; (3) Sonnet auto-fixes `minor` findings directly; (4) Sonnet presents
each `major` finding individually to the user via `AskUserQuestion` and
only edits on explicit approval; (5) re-run the deterministic shape
checker on every touched skill to confirm no regression.

**Tech Stack:** Claude Code `Agent` tool (`model: "fable"`,
`subagent_type: "general-purpose"`), the existing
`skills/evaluating-skill-quality/scripts/check_skill_shape.py` (stdlib
Python, read-only), `Skill` tool, `AskUserQuestion` tool.

This is a documentation/prose remediation task, not new runtime code —
there is no application test suite to extend. "Testable deliverable" here
means: a structured findings report (Task 1), a verified-consistent
triage list (Task 2), a shape-checker PASS plus a reviewable diff for each
touched skill (Tasks 3-4).

## Global Constraints

- Target skills (all 11, from spec): `battle-testing-a-skill`,
  `driving-pr-to-merge`, `establishing-ubiquitous-language`,
  `evaluating-skill-quality`, `explaining-the-work`, `gated-skill-edits`,
  `issue-to-branch`, `merge-retrospective`, `outward-artifact-preflight`,
  `seeding-issue-pr-templates`, `stop-and-replan`, `untrusted-input-triage`.
- Every Fable agent must invoke `evaluating-skill-quality` via the `Skill`
  tool and follow its Procedure steps 1-6, running the bundled shape
  checker itself: `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py <skill-dir>`.
- Severity definition (verbatim, must be included in every Fable prompt):
  - **major**: whole-artifact mechanism-fit finding (should have been a
    hook/subagent/CLAUDE.md), a stated safety-critical prohibition with no
    hook/permission backing, a shape-checker FAIL, or a scope violation.
  - **minor**: any other rubric-dimension finding (ambiguous wording,
    missing evidence citation, broken cross-link, step-level
    bundled-script suggestion, formatting nit).
- Each finding must carry: `severity`, `dimension`, `evidence` (direct
  quote/line), `file:line`, `recommendation`.
- Major findings are never batch-approved — present and confirm one at a
  time.
- Do not expand `check_skill_shape.py` or the rubric itself as part of this
  work (out of scope per the spec), unless a finding specifically targets
  `evaluating-skill-quality` as a review subject and the user approves that
  change like any other major finding.
- Keep all GitHub-facing text ASCII (per CLAUDE.md); this plan produces no
  GitHub artifacts itself but downstream commits/PRs must comply.

---

### Task 1: Parallel Fable analysis of all 11 skills

**Files:**
- Create: `docs/superpowers/reports/2026-07-13-skill-gap-findings.md` (raw
  aggregated output, one section per skill)

**Interfaces:**
- Produces: a Markdown file with one `## <skill-name>` section per skill,
  each containing a Markdown table of findings with columns `severity |
  dimension | evidence | file:line | recommendation`. This file is the
  sole input to Task 2.

- [ ] **Step 1: Compose the shared Fable agent prompt template**

Use this exact template, substituting `<SKILL_DIR>` per agent:

```
You are reviewing the skill at skills/<SKILL_DIR>/ in the gitapex repo
(repo root is your working directory). Do not modify any files — this is
a read-only review.

1. Use the Skill tool to invoke "evaluating-skill-quality".
2. Follow that skill's Procedure section, steps 1-6, against
   skills/<SKILL_DIR>/SKILL.md and every file in its references/
   directory (if one exists).
3. You must run the bundled shape checker yourself:
   python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/<SKILL_DIR>
   Cite its PASS/FAIL output verbatim in your findings.
4. Classify every finding using this severity definition (apply exactly,
   do not invent your own categories):
   - major: whole-artifact mechanism-fit finding (should have been a
     hook/subagent/CLAUDE.md), a stated safety-critical prohibition with
     no hook/permission backing, a shape-checker FAIL, or a scope
     violation (skill doing more than its own Scope section allows).
   - minor: any other rubric-dimension finding (ambiguous wording,
     missing evidence citation, broken cross-link, step-level
     bundled-script suggestion, formatting nit).
5. If skills/<SKILL_DIR>/references/ does not exist, or it has no bundled
   script, say so explicitly rather than skipping that part of the
   review.

Report back ONLY a Markdown table, no other prose, with columns:
severity | dimension | evidence | file:line | recommendation
One row per finding. If there are zero findings for a category, omit rows
for it (do not pad with placeholder rows). Keep each evidence quote under
30 words.
```

- [ ] **Step 2: Launch all 11 agents in parallel**

Call the `Agent` tool 11 times in a single message (one content block per
skill), each with:
- `subagent_type: "general-purpose"`
- `model: "fable"`
- `description`: e.g. `"Review battle-testing-a-skill quality"`
- `prompt`: the Step 1 template with `<SKILL_DIR>` substituted for that
  skill
- `run_in_background: false` (need all 11 results before Task 2 starts)

The 11 `<SKILL_DIR>` values: `battle-testing-a-skill`,
`driving-pr-to-merge`, `establishing-ubiquitous-language`,
`evaluating-skill-quality`, `explaining-the-work`, `gated-skill-edits`,
`issue-to-branch`, `merge-retrospective`, `outward-artifact-preflight`,
`seeding-issue-pr-templates`, `stop-and-replan`, `untrusted-input-triage`.

- [ ] **Step 3: Write the aggregated report file**

Create `docs/superpowers/reports/2026-07-13-skill-gap-findings.md` with
one `## <skill-name>` heading per skill (in the same order as the list
above), pasting each agent's returned table verbatim underneath its
heading. If an agent returned zero findings, write `No findings.` under
that heading instead of an empty table.

- [ ] **Step 4: Verify deliverable**

Confirm the file has exactly 11 `##` headings (one per skill) and that
every row in every table has all 5 columns populated (no blank
`severity`/`dimension`/`evidence`/`file:line`/`recommendation` cells). Fix
any malformed row by re-reading the corresponding agent's raw output
before moving on.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/reports/2026-07-13-skill-gap-findings.md
git commit -m "docs(reports): aggregate Fable skill-quality findings for all 11 skills"
```

---

### Task 2: Aggregate, verify evidence, and triage findings

**Files:**
- Read: `docs/superpowers/reports/2026-07-13-skill-gap-findings.md`
- Create: `docs/superpowers/reports/2026-07-13-skill-gap-triage.md`

**Interfaces:**
- Consumes: the Task 1 report file (Markdown tables per skill).
- Produces: a triage file with two top-level sections, `## Minor (auto-fix)`
  and `## Major (needs approval)`, each containing a flat list of findings
  with skill name prefixed, e.g. `- [issue-to-branch] dimension 5: ...`.
  This file is the input to Tasks 3 and 4.

- [ ] **Step 1: Evidence-check every finding**

For each row in the Task 1 report, open the cited `file:line` in the
actual skill file and confirm the `evidence` quote appears there
(substring match is sufficient; paraphrase mismatches are a discard
trigger). Discard (drop from triage) any finding whose quote does not
appear in the cited file, and note the discard inline as an HTML comment
in the triage file, e.g. `<!-- discarded: quote not found in file -->`,
so the decision is visible on review.

- [ ] **Step 2: Split by severity into the triage file**

Write `docs/superpowers/reports/2026-07-13-skill-gap-triage.md` with the
two sections described above. Preserve the original `dimension`,
`file:line`, and `recommendation` fields for each surviving finding.

- [ ] **Step 3: Verify deliverable**

Count findings in the Task 1 report vs. the triage file: `(kept in Minor)
+ (kept in Major) + (discarded) == (total rows in Task 1 report)`. If the
counts don't reconcile, find the missing row before proceeding.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/reports/2026-07-13-skill-gap-triage.md
git commit -m "docs(reports): triage skill-quality findings into minor/major"
```

---

### Task 3: Auto-fix all minor findings

**Files:**
- Modify: whichever `skills/<name>/SKILL.md` and
  `skills/<name>/references/*.md` files have entries under
  `## Minor (auto-fix)` in the Task 2 triage file.

**Interfaces:**
- Consumes: the `## Minor (auto-fix)` list from Task 2's triage file.
- Produces: edited skill files, one commit per skill (not one giant
  commit), so each is independently reviewable/revertable.

- [ ] **Step 1: Group minor findings by skill**

From the triage file's Minor section, group the bullet list by the
`[skill-name]` prefix so each skill's fixes can be applied and committed
together.

- [ ] **Step 2: Apply fixes for one skill**

For the first skill group, open the cited file(s) and apply each
`recommendation` verbatim where it is unambiguous (e.g. "fix broken link
to X", "add missing cross-reference to Y"). Where a recommendation is
underspecified, make the smallest edit that resolves the cited evidence
without adding scope beyond what the finding describes.

- [ ] **Step 3: Re-run the shape checker for that skill**

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/<name>
```
Expected: `PASS` on every check (minor fixes must never break shape).

- [ ] **Step 4: Commit this skill's fixes**

```bash
git add skills/<name>/SKILL.md skills/<name>/references/
git commit -m "fix(skills/<name>): address minor evaluating-skill-quality findings"
```

- [ ] **Step 5: Repeat Steps 2-4 for every remaining skill in the Minor group**

Iterate until every skill listed under `## Minor (auto-fix)` has been
fixed, shape-checked, and committed.

---

### Task 4: Present major findings individually and implement approved fixes

**Files:**
- Modify: whichever `skills/<name>/SKILL.md` files have entries under
  `## Major (needs approval)` in the Task 2 triage file, only after
  approval.

**Interfaces:**
- Consumes: the `## Major (needs approval)` list from Task 2's triage
  file.
- Produces: edited skill files (approved subset only), one commit per
  approved fix.

- [ ] **Step 1: Present the first major finding**

Use `AskUserQuestion` with the skill name, the exact evidence quote, why
it's classified major (mechanism-fit / missing hook backing / shape FAIL /
scope violation), and the proposed fix as a single focused question with
options like "Apply this fix", "Skip this one", "I want to discuss it
first".

- [ ] **Step 2: Implement if approved**

If approved, edit the file per the recommendation (this may require more
judgment than a minor fix — e.g. moving an absolute prohibition into a
paired hook reference, or splitting portable vs. repo-scoped content into
a `references/` file). If the user wants to discuss first, pause and
follow their direction before editing.

- [ ] **Step 3: Re-run the shape checker**

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/<name>
```
Expected: `PASS`.

- [ ] **Step 4: Commit this approved fix**

```bash
git add skills/<name>/
git commit -m "fix(skills/<name>): address major evaluating-skill-quality finding — <short description>"
```

- [ ] **Step 5: Repeat Steps 1-4 for every remaining major finding**

One finding at a time, in the order listed in the triage file, until the
list is exhausted.

---

### Task 5: Final verification sweep

**Files:**
- None created; read-only verification across all touched skills.

**Interfaces:**
- Consumes: the set of skill directories touched in Tasks 3-4.

- [ ] **Step 1: Re-run the shape checker across every touched skill**

```bash
for d in <space-separated list of touched skill dirs from Tasks 3-4>; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "skills/$d"
done
```
Expected: `PASS` for all.

- [ ] **Step 2: Summarize outcome**

Report to the user: how many minor findings were auto-fixed, how many
major findings were approved vs. skipped, and confirm no shape-checker
regressions. State explicitly that prose/rubric-dimension fixes were not
re-scored by a fresh nine-dimension review (that would require spawning
another round of Fable review, out of scope for this plan) — this is a
judgment call, not a re-verified proof, per CLAUDE.md's rule against
treating indirect signals as completion proof.

- [ ] **Step 3: Final commit if any loose ends remain**

If Step 2's summary is itself saved anywhere (e.g. appended to the triage
file), commit it:

```bash
git add docs/superpowers/reports/2026-07-13-skill-gap-triage.md
git commit -m "docs(reports): record final outcome of skill gap remediation pass"
```

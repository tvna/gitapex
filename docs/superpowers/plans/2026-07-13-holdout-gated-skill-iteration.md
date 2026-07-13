# gated-skill-edits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a portable procedure-knowledge skill that applies SkillOpt's
held-out validation gate to hand-edited `SKILL.md` iteration.

**Architecture:** Three static files under
`skills/gated-skill-edits/` -- a lean `SKILL.md`
contract plus two `references/`. No runtime code; verification is
structural (frontmatter, line count, link resolution, trigger
distinctness, ASCII of any GitHub post), the same posture PR #18 and
`tvna/gitapex#2` used for skill-only changes.

**Tech Stack:** Markdown only. Verification via shell (`grep`, `sed`,
`awk`, `python3` for byte checks) and the existing `uv run pytest` suite
(must stay green; no runtime code is added).

## Global Constraints

- Source of truth for all content: `docs/superpowers/specs/2026-07-13-holdout-gated-skill-iteration-design.md` (committed this branch). Copy its Body, Output contract, Stop boundaries, and References verbatim in intent.
- Skill directory and `name` frontmatter must match: `gated-skill-edits`.
- `description`: single line, third person, carries a "Use when ..." trigger, no XML tags, under 1024 chars.
- Trigger must NOT overlap `evaluating-skill-quality` (not on this branch; static review) or `battle-testing-a-skill` (on main; adversarial robustness). This skill is iterative measured editing.
- `SKILL.md` body under 90 lines. `references/skillopt-mapping.md` carries a table of contents (it exceeds 100 lines).
- Repo files may use the existing em-dash convention; only GitHub post text (PR body) must be ASCII, checked with a byte scan.
- Cite `#25` in every commit. Do not build a runner, an `evals/` suite, the battle-test skill, or touch `evaluating-skill-quality`.
- Section numbers cited from arXiv:2605.23904 must exist: 3.1, 3.4, 3.5, 3.6, 3.7, Appendix B, Appendix C.

---

### Task 1: SKILL.md contract

**Files:**
- Create: `skills/gated-skill-edits/SKILL.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: the skill contract the two references link out from; the
  frontmatter `name: gated-skill-edits` and the
  reference filenames `references/skillopt-mapping.md`,
  `references/worked-example.md` that Tasks 2-3 create.

- [ ] **Step 1: Write the structural checks (the "failing test")**

Save as `scripts/../` is NOT needed; run these inline after creating the file. The assertions:

```bash
F=skills/gated-skill-edits/SKILL.md
# name matches directory
grep -q '^name: gated-skill-edits$' "$F"
# single-line description with a Use when trigger, no XML tags
grep -q '^description: Use when ' "$F"
! grep -qE '<[a-zA-Z/]' "$F"
# body under 90 lines
test "$(wc -l < "$F")" -lt 90
# Stop boundaries section present
grep -q '## Stop boundaries' "$F"
# the load-bearing invariants are stated
grep -qi 'strict' "$F" && grep -qi 'ties' "$F"          # strict improve-or-reject, ties rejected
grep -qi 'held-out' "$F" && grep -qi 'precondition' "$F" # precondition gate
grep -q 'references/skillopt-mapping.md' "$F"
grep -q 'references/worked-example.md' "$F"
```

- [ ] **Step 2: Run the checks to verify they fail**

Run: `bash -c 'F=skills/gated-skill-edits/SKILL.md; test -f "$F"'`
Expected: FAIL (file does not exist yet).

- [ ] **Step 3: Create `SKILL.md`**

Frontmatter (exact):

```yaml
---
name: gated-skill-edits
description: Use when iteratively editing an existing SKILL.md across repeated measured trials and deciding whether to keep each edit. Requires a checkable scorer and a held-out split first; applies SkillOpt's strict improve-or-reject validation gate by hand.
---
```

Body sections, in this order, written from the spec's "Body", "Output
contract", and "Stop boundaries" (copy the spec's wording; keep under 90
lines total):

1. `# Gated skill edits` + one-sentence overview.
2. `## Precondition gate` -- STOP unless a checkable `r(s) in [0,1]` scorer
   AND a held-out split both exist; name the gap otherwise (cite SkillOpt
   Appendix B).
3. `## Procedure` numbered 1-7: split disjoint train/selection/test (edits
   motivated only by train; selection gates; test reports only); bounded
   edits (edit budget, patch over rewrite); strict improve-or-reject
   (ties rejected); rejected-edit log; transfer check before shipping;
   LLM-as-judge only with an adversarial verification pass. Link
   `references/skillopt-mapping.md` at the split/gate step and
   `references/worked-example.md` at the gate step.
4. `## Output` -- Precondition, Splits, Proposed edits, Gate result
   (score before/after, keep/reject), Rejected-edit log, Transfer check,
   Next move.
5. `## Stop boundaries` -- the six bullets from the spec (no iteration
   without scorer+split; no edit motivated by selection/test; never keep a
   tie/worse; never ship without transfer check; LLM judge never ground
   truth alone; this iterates, it does not build an executor and does not
   review-for-merge).

- [ ] **Step 4: Run the checks to verify they pass**

Run the Step 1 block; also:
```bash
sed -n '1,4p' skills/gated-skill-edits/SKILL.md
awk 'NR==1{print "lines:"} END{print NR}' skills/gated-skill-edits/SKILL.md
```
Expected: all `grep`/`test` assertions exit 0; line count < 90.

- [ ] **Step 5: Commit**

```bash
git add skills/gated-skill-edits/SKILL.md
git commit -m "feat(skills): add gated-skill-edits contract

Refs #25

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: references/skillopt-mapping.md

**Files:**
- Create: `skills/gated-skill-edits/references/skillopt-mapping.md`

**Interfaces:**
- Consumes: linked from `SKILL.md` (Task 1).
- Produces: the adapted/not-adapted citation table the code-review and the
  spec's AC#2-equivalent rely on.

- [ ] **Step 1: Write the structural checks**

```bash
F=skills/gated-skill-edits/references/skillopt-mapping.md
grep -qi 'table of contents\|## Contents' "$F"       # TOC present
for s in '3.1' '3.4' '3.5' '3.6' '3.7' 'Appendix B' 'Appendix C'; do grep -q "$s" "$F"; done
grep -qi 'not adapt' "$F"                              # names what is NOT adopted, with reasons
```

- [ ] **Step 2: Verify they fail**

Run: `test -f skills/gated-skill-edits/references/skillopt-mapping.md`
Expected: FAIL (absent).

- [ ] **Step 3: Create the file**

Content from the spec's "References -> skillopt-mapping.md":
- A table of contents (the file exceeds 100 lines).
- Section "Adapted": 3.1 eq.(1)-(3) scorer + splits; 3.4 bounded edits;
  3.5 strict gate + rejected-edit buffer; Appendix B precondition +
  transfer caution; Appendix C default 2:1:7 split and accept-only-if-
  improves.
- Section "Not adapted (with reasons)": 3.2/3.3 rollout/reflection batch
  execution (automation infra); 3.6 slow/meta momentum (optimizer-side
  automation); 3.7 harness adapters + optimizer machinery; the benchmark
  suite (no gitapex equivalent -- the reason the precondition gate exists).
- Keep every claim about the paper grounded to a section number that
  exists (3.1, 3.4, 3.5, 3.6, 3.7, Appendix B, Appendix C).

- [ ] **Step 4: Verify checks pass**

Run the Step 1 block. Expected: all assertions exit 0.

- [ ] **Step 5: Commit**

```bash
git add skills/gated-skill-edits/references/skillopt-mapping.md
git commit -m "docs(skills): add SkillOpt section-mapping reference

Refs #25

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: references/worked-example.md

**Files:**
- Create: `skills/gated-skill-edits/references/worked-example.md`

**Interfaces:**
- Consumes: linked from `SKILL.md` (Task 1); references the existing
  `evals/issue-to-branch/` substring contract as the scorer.
- Produces: the concrete worked iteration the spec requires.

- [ ] **Step 1: Write the structural checks**

```bash
F=skills/gated-skill-edits/references/worked-example.md
grep -qi 'reject' "$F" && grep -qi 'tie' "$F"           # shows a rejected tie
grep -qi 'output_contains\|substring\|issue-to-branch' "$F"  # uses the existing scorer
grep -qi 'rejected-edit log\|rejected edit' "$F"        # shows the log entry
```

- [ ] **Step 2: Verify they fail**

Run: `test -f skills/gated-skill-edits/references/worked-example.md`
Expected: FAIL (absent).

- [ ] **Step 3: Create the file**

One iteration of a fictional small skill scored by the
`evals/issue-to-branch/` `output_contains` / `output_not_contains`
substring contract (score = fraction of assertions passing):
- Start state: skill scores, say, 3/4 on the selection split.
- Edit A (kept): a localized add that raises selection to 4/4 -> accepted.
- Edit B (rejected): a plausible reword that leaves selection at 4/4 ->
  rejected as a tie (strict improvement required), with the resulting
  rejected-edit-log entry (edit tried, score delta 0, do not retry).
- Use a fictional skill so nothing goes stale against a real skill's text.

- [ ] **Step 4: Verify checks pass**

Run the Step 1 block plus link resolution:
```bash
# every markdown link target under the skill dir resolves
D=skills/gated-skill-edits
grep -roE '\]\(([^)]+\.md)\)' "$D" | sed -E 's/.*\(([^)]+)\)/\1/' | while read L; do
  case "$L" in references/*) test -f "$D/$L" || echo "BROKEN: $L";; esac
done
```
Expected: assertions exit 0; no `BROKEN:` output.

- [ ] **Step 5: Commit**

```bash
git add skills/gated-skill-edits/references/worked-example.md
git commit -m "docs(skills): add held-out-gate worked example

Refs #25

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Repo-wide verification

**Files:**
- Modify: none (verification only).

- [ ] **Step 1: Trigger distinctness + line/TOC + section-number checks**

```bash
D=skills/gated-skill-edits
# body < 90 lines
test "$(wc -l < "$D/SKILL.md")" -lt 90 && echo "body ok"
# mapping has a TOC and exceeds 100 lines (so TOC is warranted)
test "$(wc -l < "$D/references/skillopt-mapping.md")" -gt 100 && echo "mapping len ok"
# description does not reuse evaluating-skill-quality / battle-testing phrasing
grep -i 'reviewing a SKILL.md before merging\|hostile or low-quality input' "$D/SKILL.md" && echo "OVERLAP RISK" || echo "trigger distinct"
```
Expected: `body ok`, `mapping len ok`, `trigger distinct`.

- [ ] **Step 2: Existing test suite stays green**

Run: `uv run pytest -q`
Expected: same pass count as before this branch (no runtime code added).

- [ ] **Step 3: No commit** (verification only; nothing changed).

---

## Self-Review

- **Spec coverage:** SKILL.md (Task 1) covers the spec's Body, Output
  contract, Stop boundaries; skillopt-mapping (Task 2) covers the
  adapted/not-adapted citation requirement; worked-example (Task 3) covers
  the required concrete iteration; Task 4 covers the spec's Verification
  bullets. Non-goals (runner, evals suite, battle-test skill) are honored
  by omission.
- **Placeholder scan:** no "TBD"/"handle edge cases"; each file's content
  is specified by section with concrete assertions.
- **Type consistency:** the directory name, `name` frontmatter, and the two
  reference filenames are identical across all four tasks.

# driving-pr-to-merge Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Refs #5

**Goal:** Add `skills/driving-pr-to-merge/SKILL.md`, a low-freedom procedural
skill that drives an opened PR to a terminal state (merged, or closed with
rationale): auto-subscribe, treat CI/review text as the spec, explicitly
resolve review threads via the API, verify `mergeable_state`, loop until
terminal, escalate only on a genuine block.

**Architecture:** One new skill directory under `skills/`, no changes to
existing files. No runtime code, no build step — correctness is checked by
`grep`/`python3` structural assertions, matching the `explaining-the-work`
precedent from PR #2.

**Tech Stack:** Plain Markdown with YAML frontmatter. No new dependencies.

## Global Constraints

- `skills/driving-pr-to-merge/SKILL.md` frontmatter: `name:
  driving-pr-to-merge` (kebab-case, matches directory name), single-line
  third-person `description` containing a "Use when..." trigger, no
  XML-like tags in the description.
- No `references/` subdirectory — content must fit in `SKILL.md` alone,
  <= 500 lines.
- The sequence (subscribe -> treat CI/review as spec -> fix -> push ->
  resolve-thread API call -> `mergeable_state` check -> loop or escalate)
  is stated as an exact order, not left to prose judgement (low freedom,
  per issue #5).
- Must include one concrete worked example (fictitious PR: one failing CI
  check, one open review thread) walking the exact sequence.
- Must include an explicit Stop section with the three boundaries from
  issue #5's acceptance criteria.
- Any MCP tool referenced is named fully qualified (`Server:tool`), with
  forward slashes in any path.
- Do NOT merge #9 (`stop-and-replan`) content into this skill — it is
  still open; only note it as a related-but-distinct skill.
- Do not touch `scripts/`, `tests/`, `.claude-plugin/`, or any existing
  file — this plan only adds new files.

---

### Task 1: `driving-pr-to-merge` skill

**Files:**
- Create: `skills/driving-pr-to-merge/SKILL.md`

**Interfaces:**
- Consumes: nothing from other tasks (this is the only task).
- Produces: nothing consumed elsewhere in this plan.

- [ ] **Step 1: Create the skill directory and `SKILL.md`**

```bash
mkdir -p skills/driving-pr-to-merge
```

Write `skills/driving-pr-to-merge/SKILL.md` with:
- Frontmatter: `name: driving-pr-to-merge`, single-line third-person
  `description` starting with "Use when a pull request has just been
  opened, or has an open CI failure or review thread, before closing the
  turn." and stating what the skill does.
- An "Exact sequence" section, numbered 1-7, exactly matching the
  design spec (`docs/superpowers/specs/2026-07-12-driving-pr-to-merge-design.md`)
  Skill content section: subscribe on open; treat CI/review text as spec;
  push fix; resolve review thread via the fully-qualified
  resolve-review-thread tool; verify `mergeable_state` via the
  fully-qualified PR-read tool; loop on new failures/comments/blocked
  state; escalate only on access/secret/human-decision block.
- A "Worked example" section walking the fictitious one-CI-failure,
  one-open-thread PR through the exact sequence.
- A "Stop boundaries" section with the three boundaries from issue #5.
- An optional short "Related skills" note pointing at #9
  (`stop-and-replan`, not yet landed, distinct trigger) without
  incorporating its content.

- [ ] **Step 2: Verify frontmatter is well-formed and the name matches the directory**

Run:

```bash
python3 -c "
import re
text = open('skills/driving-pr-to-merge/SKILL.md').read()
m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
assert m, 'no frontmatter block found'
fm = m.group(1)
assert 'name: driving-pr-to-merge' in fm, fm
assert 'description: Use when' in fm, fm
desc_line = [l for l in fm.splitlines() if l.startswith('description:')][0]
assert '<' not in desc_line, 'description contains XML-like tag'
print('SKILL.md frontmatter OK')
"
```

Expected output: `SKILL.md frontmatter OK`

- [ ] **Step 3: Verify the exact sequence and Stop section are present**

Run:

```bash
for phrase in \
  "subscribe" \
  "mergeable_state" \
  "resolve_review_thread" \
  "reply comment alone" \
  "Never mark a PR done" \
  "Never silently drop a CI failure" \
  "Never proceed past" \
  "escalat"
do
  grep -qi "$phrase" skills/driving-pr-to-merge/SKILL.md && echo "found: $phrase" || { echo "MISSING: $phrase"; exit 1; }
done
```

Expected output: eight `found: ...` lines, no `MISSING` line.

- [ ] **Step 4: Verify `SKILL.md` line count stays within budget**

Run:

```bash
lines=$(wc -l < skills/driving-pr-to-merge/SKILL.md)
[ "$lines" -le 500 ] && echo "line count OK: $lines" || { echo "OVER BUDGET: $lines"; exit 1; }
```

Expected output: `line count OK: <n>` where `<n> <= 500`.

- [ ] **Step 5: Verify #9's content was not folded in**

Run:

```bash
grep -qi "self-correcting" skills/driving-pr-to-merge/SKILL.md && { echo "FAIL: stop-and-replan content leaked in"; exit 1; } || echo "no #9 content leaked: OK"
```

Expected output: `no #9 content leaked: OK`

- [ ] **Step 6: Manual dry run**

Given a fictitious PR with one failing CI check and one open review
thread, walk through `skills/driving-pr-to-merge/SKILL.md` by hand and
confirm the produced sequence is fix -> resolve-thread API call ->
`mergeable_state` check, not a skipped step (this is issue #5's
acceptance criteria #2; record the walk-through result in the task's
completion note, not as a new file).

- [ ] **Step 7: Commit**

```bash
git add skills/driving-pr-to-merge/SKILL.md
git commit -m "feat(plugin): add driving-pr-to-merge skill"
```

---

## Final check

- [ ] Run the full verification sweep from Task 1 once more in sequence
      (all `python3`/`grep`/`wc` commands above) and confirm every one
      prints its expected "OK"/"found" output with no `MISSING`/`FAIL`
      line.
- [ ] Confirm the existing `scripts/`/`tests/` pytest suite is untouched
      and still passing (`uv run pytest` or equivalent).
- [ ] Confirm `git status` shows only the new
      `skills/driving-pr-to-merge/SKILL.md`, this plan, and its design
      spec as changes.

# issue-to-branch Skill Implementation Plan

**Goal:** Add the `issue-to-branch` skill to gitapex — authored fresh from
the design migrated from `tvna/clairvoyance#128` into `tvna/gitapex#4` —
including its `references/`, its eval fixtures, and the two doc updates
the change touches (`docs/repository-layout.md`,
`docs/motivation.md`).

**Architecture:** Static files only, same posture as `tvna/gitapex#2`: one
new skill directory (`SKILL.md` + `references/`), one new eval directory
(`eval.yaml` + `tasks/*.yaml`), two small doc edits. No runtime code.

**Tech Stack:** Plain Markdown + YAML frontmatter + YAML eval fixtures. No
new dependencies.

## Global Constraints

- `SKILL.md` frontmatter: `name: issue-to-branch` (kebab-case, matches
  directory name), single-line third-person `description` with a "Use
  when..." trigger, no XML tags.
- Must contain a "Stop boundaries" section (matches the heading already
  used in `skills/explaining-the-work/SKILL.md`).
- Must not hardcode any `tvna/clairvoyance` issue number anywhere under
  `skills/issue-to-branch/` — provenance lives in `tvna/gitapex#4`, not in
  the skill text (Stop-section/anchor convention cited in that issue).
- Eval fixtures use the same schema shape as clairvoyance's own evals
  (`name`/`description`/`skill`/`version`/`config`/`metrics`/`tasks` glob
  for `eval.yaml`; `id`/`name`/`description`/`tags`/`inputs.prompt`/
  `expected.output_contains`/`expected.output_not_contains` for tasks).
- Do not touch `scripts/`, `tests/`, `pyproject.toml`, `.claude-plugin/`,
  or `skills/explaining-the-work/` — this plan only adds new files plus
  two targeted doc edits.

---

### Task 1: `issue-to-branch` skill

**Files:**
- Create: `skills/issue-to-branch/SKILL.md`
- Create: `skills/issue-to-branch/references/github-issue-workflow.md`
- Create: `skills/issue-to-branch/references/acceptance-criteria-map.md`

- [ ] **Step 1: Create the skill directory and `SKILL.md`**

Frontmatter:

```yaml
---
name: issue-to-branch
description: Use when starting work from a GitHub issue, creating a branch from an issue, preparing a PR from an issue, or turning an issue into an implementation plan. Produces an Acceptance Criteria Map before any branch or PR work begins.
---
```

Body: steps 1-8 (resolve as untrusted text; extract facts/criteria; detect
staleness/reframing; build the Acceptance Criteria Map before branch work;
propose branch/PR plan; identify deterministic gates; ask only when
genuinely ambiguous; require the map in the PR body). Output contract:
Facts / Assumptions / Acceptance Criteria Map / Branch Plan / Verification
Plan / Human Decision (only when needed) / Next Move. Stop boundaries
section per the constraints above.

- [ ] **Step 2: Write `references/github-issue-workflow.md`**

Connector-first tool preference, read path (body -> comments -> linked
PR/diff/CI, cross-checked against the live tree), write path
(issue-before-branch, issue number in every commit/PR, auto-subscribe PRs
to a terminal state), untrusted-text handling for review comments/CI logs.

- [ ] **Step 3: Write `references/acceptance-criteria-map.md`**

Row template (criterion / interpretation / planned ops / proof method /
residual risk) plus one fully fictional worked example (no real issue
numbers).

- [ ] **Step 4: Verify frontmatter and required sections**

```bash
python3 -c "
import re
text = open('skills/issue-to-branch/SKILL.md').read()
fm = re.search(r'^---\n(.*?)\n---', text, re.S).group(1)
assert 'name: issue-to-branch' in fm, fm
assert 'Use when' in fm, fm
assert '<' not in fm, 'no XML tags allowed in description'
assert 'Stop boundaries' in text, 'missing Stop boundaries section'
assert 'clairvoyance' not in text.lower(), 'no clairvoyance issue refs in skill text'
print('SKILL.md OK')
"
grep -rli clairvoyance skills/issue-to-branch/references/ && { echo "FAIL: clairvoyance ref found"; exit 1; } || echo "references OK: no clairvoyance refs"
```

Expected output: `SKILL.md OK` and `references OK: no clairvoyance refs`.

- [ ] **Step 5: Commit**

```bash
git add skills/issue-to-branch/
git commit -m "feat(plugin): add issue-to-branch skill

Refs #4"
```

---

### Task 2: Eval fixtures

**Files:**
- Create: `evals/issue-to-branch/eval.yaml`
- Create: `evals/issue-to-branch/tasks/normal.yaml`
- Create: `evals/issue-to-branch/tasks/stale-reframed.yaml`
- Create: `evals/issue-to-branch/tasks/guardrail.yaml`

**Interfaces:**
- Consumes: nothing from Task 1 (the eval schema doesn't parse
  `SKILL.md`), but its `skill:` field must name `issue-to-branch` to stay
  consistent with Task 1's directory name.

- [ ] **Step 1: Write `eval.yaml`**

Same shape as `evals/architecture-tradeoff/eval.yaml` in clairvoyance:
`name`, `description`, `skill: issue-to-branch`, `version: "0.1.0"`,
`config` (trials_per_task, timeout_seconds, parallel, executor, model),
one `metrics` entry, `tasks: ["tasks/*.yaml"]`.

- [ ] **Step 2: Write `tasks/normal.yaml`**

An ordinary issue with clear acceptance criteria. `expected.output_contains`
covers Facts, Acceptance Criteria Map, Branch Plan, Verification Plan, Next
Move; `output_not_contains` guards against "LGTM".

- [ ] **Step 3: Write `tasks/stale-reframed.yaml`**

Issue body superseded by a later comment narrowing scope.
`output_contains` covers Acceptance Criteria Map and Assumptions;
`output_not_contains` asserts the dropped scope item is absent, plus
"LGTM".

- [ ] **Step 4: Write `tasks/guardrail.yaml`**

Request to skip straight to branch/PR creation on an issue with no stated
acceptance criteria. `output_contains` covers Human Decision and
AskUserQuestion; `output_not_contains` asserts no claimed branch/PR
creation, plus "LGTM".

- [ ] **Step 5: Verify all four files parse as valid YAML**

```bash
python3 -c "
import yaml, glob
for f in ['evals/issue-to-branch/eval.yaml'] + glob.glob('evals/issue-to-branch/tasks/*.yaml'):
    d = yaml.safe_load(open(f))
    assert d, f
    print(f, 'OK')
"
```

- [ ] **Step 6: Commit**

```bash
git add evals/issue-to-branch/
git commit -m "test(plugin): add issue-to-branch eval fixtures

Refs #4"
```

---

### Task 3: Doc updates

**Files:**
- Edit: `docs/repository-layout.md`
- Edit: `docs/motivation.md`

**Interfaces:**
- Consumes: Task 1's directory name (`skills/issue-to-branch/`).

- [ ] **Step 1: `docs/repository-layout.md`** — name both current skill
      directories (`explaining-the-work/`, `issue-to-branch/`) instead of
      only describing the pattern generically.

- [ ] **Step 2: `docs/motivation.md`** — fix line 56's "vendored from the
      `clairvoyance` plugin" to state the actual origin (design migrated
      from `tvna/clairvoyance#128`, implemented directly in gitapex).
      Leave the rest of the diagrams/narrative untouched — the other
      named skills (`review-verdict`, `clairvoyance`, `decision-coaching`)
      remain conceptual/future scope, unaffected by this change.

- [ ] **Step 3: Verify**

```bash
grep -q "issue-to-branch/" docs/repository-layout.md && echo "repository-layout.md OK"
grep -q "vendored from the" docs/motivation.md && { echo "FAIL: stale vendoring phrase still present"; exit 1; } || echo "motivation.md OK"
```

- [ ] **Step 4: Commit**

```bash
git add docs/repository-layout.md docs/motivation.md
git commit -m "docs(plugin): list issue-to-branch skill, fix vendoring phrase

Refs #4"
```

---

### Task 4: Whole-branch verification

- [ ] Run the existing pytest suite and confirm it is unaffected:

```bash
cd /home/user/gitapex && uv run pytest
```

Expected: same pass count as before this branch (58/58 per PR #2's test
plan; this branch adds no Python code).

- [ ] Confirm no file outside the planned set changed:

```bash
git diff --stat origin/main...HEAD
```

Expected: only the files listed in Tasks 1-3.

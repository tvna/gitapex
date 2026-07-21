# drafting-an-acm-issue skill + seeding-issue-pr-templates retirement Plan

**Goal:** Add a `drafting-an-acm-issue` skill that authors a new GitHub
issue pre-structured with an Acceptance Criteria Map (ACM) at creation
time, so `issue-to-branch`'s own map-building step can read an existing
map instead of building one from scratch. Retire `seeding-issue-pr-templates`
(its interview-driven template generator) in favor of gitapex's own
hand-authored templates, explicitly marked as pending migration to the
planned gitapex CLI's future template-supply role.

**Architecture:** One new skill directory (`SKILL.md` + `references/` +
`scripts/` + `metadata/`), one deleted skill directory and its eval
suite/test module, nine edited template files, one new eval directory,
and doc updates. No runtime code beyond a duplicated stdlib-only checker
script (same pattern `issue-to-branch` already uses). Templates are
authored and verified before the generator skill is deleted, not after
-- build the replacement before removing what it replaces.

**Tech Stack:** Plain Markdown + YAML frontmatter + YAML eval fixtures +
one stdlib-only Python CLI script (duplicated, no new dependency).

## Global Constraints

- `SKILL.md` frontmatter: `name: drafting-an-acm-issue` (kebab-case,
  matches directory name), single-line third-person `description` with
  a "Use when..." trigger, no XML tags.
- Must contain a "Stop boundaries" section.
- `metadata/gitapex.yaml` sidecar required; `portability: Portable`
  triggers the shape checker's bare-prose `#N`/`docs/`/`evals/` citation
  scan on `SKILL.md` and `references/*.md` -- do not cite this plan/spec
  pair or the tracking issue number inside the skill body itself.
- Every relative link inside `SKILL.md` must resolve inside the skill's
  own directory (no cross-skill link to `issue-to-branch`'s reference or
  script -- ship a duplicate instead).
- ASCII only in every committed artifact.
- Open the tracking issue before any commit; cite its number in every
  commit.

---

### Task 1: Hand-author gitapex's own templates

**Files:**
- Edit: `.github/ISSUE_TEMPLATE/feat.yml`, `fix.yml`, `refactor.yml`,
  `chore.yml`, `docs.yml`, `generic.yml`, `tracking.yml`, `config.yml`
- Edit: `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1:** Add a top-of-file migration comment to all nine files,
      stating the file is hand-maintained pending the planned gitapex
      CLI and will be supplied by it once that binary ships.
- [ ] **Step 2:** `feat.yml` -- replace the freeform `acceptance-criteria`
      textarea's content with the full ACM table skeleton as its
      `attributes.value` default (its only genuine full-table gap).
- [ ] **Step 3:** `fix.yml`, `refactor.yml` -- add one new optional
      `residual-risk` textarea only; leave every other existing field
      untouched (their other four ACM columns already have a native
      home in those templates' own fields).
- [ ] **Step 4:** `chore.yml`, `docs.yml`, `generic.yml`, `tracking.yml`,
      `config.yml`, `PULL_REQUEST_TEMPLATE.md` -- migration comment only,
      no content change.
- [ ] **Step 5: Verify**

```bash
python3 -c "
import yaml
files = ['feat.yml','fix.yml','refactor.yml','chore.yml','docs.yml','generic.yml','tracking.yml','config.yml']
for f in files:
    text = open(f'.github/ISSUE_TEMPLATE/{f}', encoding='utf-8').read()
    text.encode('ascii')
    data = yaml.safe_load(text)
    if f != 'config.yml':
        assert data.get('name') and data.get('description') and data.get('body')
    print(f, 'OK')
"
```

Expected output: `OK` for all eight files, no `UnicodeEncodeError`.

- [ ] **Step 6: Commit**

```bash
git add .github/ISSUE_TEMPLATE/ .github/PULL_REQUEST_TEMPLATE.md
git commit -m "feat(templates): embed ACM shape, mark templates CLI-pending

Refs #237"
```

---

### Task 2: Retire `seeding-issue-pr-templates`

Done only after Task 1's templates are in place and verified.

**Files:**
- Delete: `skills/seeding-issue-pr-templates/` (whole directory)
- Delete: `evals/seeding-issue-pr-templates/` (whole directory)
- Delete: `tests/test_validate_templates.py`
- Edit: `pyproject.toml` (three references), `docs/repository-layout.md`,
  `hooks/check-template-overwrite.sh` (comment only)
- Edit: any currently-active skill or doc found, during execution, to
  reference the deleted skill by name in a way that would dangle or fail
  a mechanical check (discovered during this pass:
  `skills/git-hosting-surface-audit/metadata/gitapex.yaml`'s
  `skillDependencies.relatedTo`, two `SKILL.md` prose mentions of its
  `detect_platform()` convention, one eval-task description, and
  `docs/skill-eval-status.md`'s now-nonexistent eval-status section)

**Interfaces:**
- Consumes: Task 1 must be committed first.

- [ ] **Step 1:** Delete the three directories/files above via `git rm -r`.
- [ ] **Step 2:** Remove the three `skills/seeding-issue-pr-templates/scripts`
      references from `pyproject.toml` (`pythonpath`, `.addopts`'
      `--cov=` flag, `[tool.coverage.run].source`).
- [ ] **Step 3:** Remove its bullet from `docs/repository-layout.md`; add
      one for `drafting-an-acm-issue/` (Task 3 anticipates this same
      edit -- do it once, here).
- [ ] **Step 4:** Update `hooks/check-template-overwrite.sh`'s top comment
      to state the guard as a standing repository invariant instead of
      citing the deleted skill's Stop boundary by name; logic unchanged.
- [ ] **Step 5:** Grep the whole repo for the deleted skill's name; fix
      any live (non-historical) dangling reference found; leave
      `docs/superpowers/` plan/spec pairs and worked-example/provenance
      reference files describing past decisions untouched.
- [ ] **Step 6: Verify**

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/git-hosting-surface-audit
grep -q "seeding-issue-pr-templates" pyproject.toml && { echo FAIL; exit 1; } || echo "pyproject.toml OK"
```

Expected output: all checks PASS; `pyproject.toml OK`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix(skills): retire seeding-issue-pr-templates

Refs #237"
```

---

### Task 3: `drafting-an-acm-issue` skill

**Files:**
- Create: `skills/drafting-an-acm-issue/SKILL.md`
- Create: `skills/drafting-an-acm-issue/references/acceptance-criteria-map.md`
- Create: `skills/drafting-an-acm-issue/scripts/check_acm_present.py`
- Create: `skills/drafting-an-acm-issue/metadata/gitapex.yaml`

- [ ] **Step 1:** Write `SKILL.md` -- frontmatter per the Design section
      of the matching spec; body: elicit -> classify -> Facts/Requested
      outcome -> build ACM (marking unresolvable columns "unknown,
      pending X") -> Constraints/Non-goals -> validate -> ask only on
      genuine ambiguity -> create (field-population rule: only write ACM
      content into a matching-meaning field; append the full ACM as its
      own section when no field matches). Output contract: Facts,
      Requested outcome, Acceptance Criteria Map, Constraints, Non-goals,
      Human Decision (only when needed), Next Move. Stop boundaries
      section. Related skills section cross-linking `issue-to-branch`
      and `issue-to-fix`.
- [ ] **Step 2:** Write `references/acceptance-criteria-map.md` -- table
      template plus two fully fictional worked examples (a resolvable
      case and an "unknown, pending" case).
- [ ] **Step 3:** Write `scripts/check_acm_present.py` -- a self-contained
      duplicate of `issue-to-branch`'s header-regex checker.
- [ ] **Step 4:** Write `metadata/gitapex.yaml` -- `portability: Portable`,
      `capabilityAssumption: Broad`, `skillDependencies.requires: []`,
      `relatedTo: [issue-to-branch]`.
- [ ] **Step 5: Verify**

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/drafting-an-acm-issue
echo "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |" > /tmp/acm_pass.txt
python3 skills/drafting-an-acm-issue/scripts/check_acm_present.py --body /tmp/acm_pass.txt
echo "no table" > /tmp/acm_fail.txt
python3 skills/drafting-an-acm-issue/scripts/check_acm_present.py --body /tmp/acm_fail.txt; echo "exit: $?"
```

Expected output: shape checker reports all checks PASS; pass-case script
exits 0; fail-case script exits 1.

- [ ] **Step 6: Commit**

```bash
git add skills/drafting-an-acm-issue/
git commit -m "feat(skills): add drafting-an-acm-issue

Refs #237"
```

---

### Task 4: Eval fixtures

**Files:**
- Create: `evals/drafting-an-acm-issue/eval.yaml`
- Create: `evals/drafting-an-acm-issue/tasks/normal.yaml`
- Create: `evals/drafting-an-acm-issue/tasks/underspecified.yaml`
- Create: `evals/drafting-an-acm-issue/tasks/non-applicable-chore.yaml`
- Create: `evals/drafting-an-acm-issue/tasks/guardrail-fabrication.yaml`
- Create: `evals/drafting-an-acm-issue/tasks/template-gap.yaml`
- Create: `evals/drafting-an-acm-issue/tasks/fix-type-unknown-columns.yaml`

**Interfaces:**
- Consumes: Task 3's directory name (`skill: drafting-an-acm-issue`).

- [ ] **Step 1:** Write `eval.yaml`, same shape as
      `evals/issue-to-branch/eval.yaml`.
- [ ] **Step 2-7:** Write the six task fixtures per the descriptions in
      the matching spec's Design section.
- [ ] **Step 8: Verify**

```bash
python3 -c "
import yaml, glob
for f in ['evals/drafting-an-acm-issue/eval.yaml'] + glob.glob('evals/drafting-an-acm-issue/tasks/*.yaml'):
    d = yaml.safe_load(open(f))
    assert d, f
    print(f, 'OK')
"
```

- [ ] **Step 9: Commit**

```bash
git add evals/drafting-an-acm-issue/
git commit -m "test(evals): add drafting-an-acm-issue eval suite

Refs #237"
```

---

### Task 5: Doc updates

**Files:**
- Edit: `docs/repository-layout.md` (done in Task 2, Step 3)
- Create: this plan and its matching spec

- [ ] **Step 1: Verify**

```bash
grep -q "drafting-an-acm-issue/" docs/repository-layout.md && echo OK
grep -q "seeding-issue-pr-templates" docs/repository-layout.md && { echo FAIL; exit 1; } || echo OK
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-07-21-drafting-an-acm-issue-skill.md docs/superpowers/specs/2026-07-21-drafting-an-acm-issue-skill-design.md
git commit -m "docs(superpowers): plan/spec for drafting-an-acm-issue + retirement

Refs #237"
```

---

### Task 6: Whole-branch verification

- [ ] Run the existing pytest suite and confirm it passes, with
      `seeding-issue-pr-templates` tests gone (not failing, absent) and
      `drafting-an-acm-issue` newly present in
      `test_repository_skill_shape.py`'s parametrized sweep:

```bash
cd /home/user/gitapex && uv run pytest
```

- [ ] Confirm no file outside the planned set changed:

```bash
git diff --stat main...HEAD
```

Expected: only the files listed in Tasks 1-5.

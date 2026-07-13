# Skill Metadata Placement Convention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish and enforce one convention for skill metadata placement:
Portability is a terse one-line declaration as the first body line; design /
mechanism-fit rationale lives in a footer `## Notes` section; a shape-checker
floor check prevents drift.

**Architecture:** Add the deterministic gate first (fixture-tested, so it
does not turn the suite red), then bring all 12 skills into conformance so
each can self-verify against the new check, then a final sweep. Spec:
docs/superpowers/specs/2026-07-14-skill-metadata-placement-convention-design.md.

**Tech Stack:** Python 3 stdlib (`check_skill_shape.py`, stdlib-only,
read-only), pytest, Markdown SKILL.md files.

## Global Constraints

- **Portability one-line format** (first body line after the H1 title):
  `**Portability: <Portable | Repository-scoped | Mixed>.** <one clause>`
  One to two lines maximum. Longer rationale goes to the footer `## Notes`.
- **Design/mechanism rationale** lives in a `## Notes` section at the END of
  the SKILL.md (after Procedure / Stop boundaries), never front-loaded.
- **Floor check id:** `portability-near-top`; window `K = 6` body lines;
  marker regex (case-insensitive) `\bportability\s*:` (matches
  `**Portability: X.**`, `**Portability:** X`, `Portability: X`).
- Rationale stays in the same SKILL.md (footer), never `references/` (the
  rubric requires portability "checkable from this file alone").
- Every skill declares its level explicitly, including `Portable` ones.
- Keep all content ASCII (CLAUDE.md). Net-line discipline: this is a
  relocation/trim; deletions should roughly offset additions (CLAUDE.md §5).
- One commit per task. Cite no bare repo-local issue numbers in skill prose.
- The checker tests use synthetic fixtures only; nothing runs the checker
  against the real `skills/` tree in pytest/CI, so adding the check first is
  safe (verified: no `check_skill_shape` reference in tests/ or .github/).

---

### Task 1: Add the `portability-near-top` floor check to the shape checker

**Files:**
- Modify: `skills/evaluating-skill-quality/scripts/check_skill_shape.py`
- Modify: `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`

**Interfaces:**
- Produces: a new `CheckResult` named `portability-near-top` appended in
  `check_shape()`, and a module-level `PORTABILITY_RE` /
  `PORTABILITY_MAX_BODY_LINE` and a `_body_lines_after_frontmatter(text)`
  helper. Later tasks rely on this check to self-verify placement.

- [ ] **Step 1: Write the failing tests**

Add to `test_check_skill_shape.py` (follow the existing fixture style — a
`tmp_path` SKILL.md with frontmatter). Use the existing helper that builds a
SKILL.md if present; otherwise write the file inline as the other tests do.

```python
def _result(results, name):
    return next(r for r in results if r.name == name)


def test_portability_near_top_pass(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n"
        "# Title\n\n**Portability: Portable.** Self-contained.\n\nBody.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert _result(results, "portability-near-top").passed


def test_portability_near_top_bold_colon_form(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n"
        "# Title\n\n**Portability:** Portable. Self-contained.\n\nBody.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert _result(results, "portability-near-top").passed


def test_portability_near_top_missing_fails(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n# Title\n\nBody with no marker.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert not _result(results, "portability-near-top").passed


def test_portability_near_top_buried_fails(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    filler = "\n".join(f"line {i}" for i in range(10))
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n# Title\n\n" + filler
        + "\n\n**Portability: Portable.** declared too low.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert not _result(results, "portability-near-top").passed
```

(If the test module imports the checker as `css`, keep that; match the
existing import alias in the file.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "$(git rev-parse --show-toplevel)" && uv run pytest tests/ skills/evaluating-skill-quality/scripts/test_check_skill_shape.py -k portability_near_top -v`
Expected: FAIL — `portability-near-top` not among results (StopIteration in `_result`).

- [ ] **Step 3: Implement the check**

In `check_skill_shape.py`, add near the other module-level regexes (after
`TOC_RE`):

```python
PORTABILITY_RE = re.compile(r"\bportability\s*:", re.IGNORECASE)
PORTABILITY_MAX_BODY_LINE = 6
```

Add a helper next to `_parse_frontmatter`:

```python
def _body_after_frontmatter(text: str) -> list[str]:
    """Lines after the closing frontmatter '---'. If there is no
    frontmatter, the whole text is the body."""
    text = text.lstrip("﻿")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    lines = text.splitlines()
    if not text.startswith("---"):
        return lines
    end = next((i for i in range(1, len(lines))
                if lines[i].strip() == "---"), None)
    if end is None:
        return lines
    return lines[end + 1:]
```

In `check_shape()`, after the `body-length` check block, append:

```python
    body = _body_after_frontmatter(text)
    near_top = any(PORTABILITY_RE.search(line)
                   for line in body[:PORTABILITY_MAX_BODY_LINE])
    results.append(CheckResult(
        "portability-near-top", near_top,
        f"a portability declaration appears within the first "
        f"{PORTABILITY_MAX_BODY_LINE} body lines",
        "found" if near_top else
        f"missing or below body line {PORTABILITY_MAX_BODY_LINE}"))
```

Update the module docstring's check list to mention the new check.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "$(git rev-parse --show-toplevel)" && uv run pytest tests/ skills/evaluating-skill-quality/scripts/test_check_skill_shape.py -v`
Expected: PASS (all, including the 4 new portability tests).

- [ ] **Step 5: Commit**

```bash
git add skills/evaluating-skill-quality/scripts/check_skill_shape.py \
        skills/evaluating-skill-quality/scripts/test_check_skill_shape.py
git commit -m "feat(evaluating-skill-quality): add portability-near-top shape check"
```

---

### Task 2: Add a portability one-liner to the 3 undeclared skills

**Files:**
- Modify: `skills/driving-pr-to-merge/SKILL.md`
- Modify: `skills/merge-retrospective/SKILL.md`
- Modify: `skills/stop-and-replan/SKILL.md`

**Interfaces:**
- Consumes: the `portability-near-top` check from Task 1 (to self-verify).

- [ ] **Step 1: Classify and add the declaration for each**

Read each skill's current body. Each of the three depends only on a general
GitHub MCP capability, addressed via portable `Server:tool` shorthand, and
carries no this-repo-only tooling in its procedure — so each classifies as
**Portable** (confirm against the actual current text; if a genuine
this-repo dependency remains, use `Repository-scoped` and name it). Insert
the declaration as the first body line after the H1 title, e.g. for
`driving-pr-to-merge`:

```markdown
# Driving a PR to Merge

**Portability: Portable.** Depends only on a connected GitHub MCP server (a
general product capability), addressed via the portable `Server:tool`
shorthand documented below -- no this-repository tooling.
```

For `stop-and-replan`, fold the existing `**Prerequisite:** ... GitHub MCP
server` note into the same idea (the prerequisite IS the portability
caveat); keep one concise line. For `merge-retrospective`, its body already
says "This skill is self-contained" — the declaration can say
`**Portability: Portable.** Self-contained procedure; depends only on a
connected GitHub MCP server for the issue-filing step.`

- [ ] **Step 2: Verify each passes the new check**

Run for each `<skill>` in driving-pr-to-merge, merge-retrospective, stop-and-replan:
```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/<skill>
```
Expected: `portability-near-top PASS` and all other checks still PASS.

- [ ] **Step 3: Commit**

```bash
git add skills/driving-pr-to-merge/SKILL.md skills/merge-retrospective/SKILL.md \
        skills/stop-and-replan/SKILL.md
git commit -m "docs(skills): declare portability level on the 3 undeclared skills"
```

---

### Task 3: Trim the 7 skills whose portability block is multi-line

**Files (each has a 3-6 line portability block at the top to trim):**
- Modify: `skills/battle-testing-a-skill/SKILL.md` (currently **Mixed**)
- Modify: `skills/establishing-ubiquitous-language/SKILL.md` (**Portable**)
- Modify: `skills/explaining-the-work/SKILL.md` (**Mixed**)
- Modify: `skills/gated-skill-edits/SKILL.md` (**Portable**)
- Modify: `skills/issue-to-branch/SKILL.md` (**Repository-scoped**)
- Modify: `skills/outward-artifact-preflight/SKILL.md` (**Repository-scoped**)
- Modify: `skills/seeding-issue-pr-templates/SKILL.md` (**Mixed**)

**Interfaces:**
- Consumes: Task 1's check. Preserves each skill's existing classification
  word (do not reclassify — only relocate/trim).

- [ ] **Step 1: Apply the uniform transform to each skill**

For each file, read the current portability block (starts at the
`**Portability:` line near the top). Transform it to:
1. Keep the `**Portability: <same Level>.**` label plus ONE clause of
   reason on the same line (one to two lines total).
2. If the surplus rationale carries information a reviewer would need
   (e.g. *what specifically* makes it Mixed, which parts are repo-scoped),
   move that to a `## Notes` section at the END of the file:

   ```markdown
   ## Notes

   Portability: <the fuller explanation that was trimmed from the top>.
   ```
3. If the surplus is only self-justifying prose (restating that the
   checklist is general), cut it — do not relocate filler (net-line
   discipline).

Do not alter the Procedure, Stop boundaries, or any other section.

- [ ] **Step 2: Verify each still passes all checks**

Run for each of the 7 skills:
```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/<skill>
```
Expected: all checks PASS, including `portability-near-top`.

- [ ] **Step 3: Commit**

```bash
git add skills/battle-testing-a-skill/SKILL.md skills/establishing-ubiquitous-language/SKILL.md \
        skills/explaining-the-work/SKILL.md skills/gated-skill-edits/SKILL.md \
        skills/issue-to-branch/SKILL.md skills/outward-artifact-preflight/SKILL.md \
        skills/seeding-issue-pr-templates/SKILL.md
git commit -m "docs(skills): trim portability to a one-line declaration, relocate rationale to Notes"
```

---

### Task 4: Move untrusted-input-triage's Mechanism block to the footer

**Files:**
- Modify: `skills/untrusted-input-triage/SKILL.md`

**Interfaces:**
- Consumes: Task 1's check.

- [ ] **Step 1: Relocate**

The file currently has (near the top): a `**Portability: Repository-scoped.**`
block AND a ~12-line `**Mechanism decision.**` block, both before the
procedure. Transform:
1. Trim the Portability block to a one-line `**Portability:
   Repository-scoped.**` + one clause (per Task 3's rule).
2. Move the entire `**Mechanism decision.**` block verbatim to a new
   `## Notes` section at the END of the file (after Stop boundaries),
   retitled as prose under `## Notes` (drop the bold inline label, or keep
   it as the first line of the Notes section). The procedure ("Externally
   authored text means...") must now begin right after the one-line
   portability declaration.

- [ ] **Step 2: Verify**

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/untrusted-input-triage
```
Expected: all PASS including `portability-near-top`. Manually confirm the
first body line after the H1 is the portability declaration and the mechanism
rationale now sits under `## Notes` at the end.

- [ ] **Step 3: Commit**

```bash
git add skills/untrusted-input-triage/SKILL.md
git commit -m "docs(untrusted-input-triage): move mechanism decision to footer Notes, trim portability line"
```

---

### Task 5: Conform evaluating-skill-quality and update its rubric

**Files:**
- Modify: `skills/evaluating-skill-quality/SKILL.md`
- Modify: `skills/evaluating-skill-quality/references/rubric.md`
- Modify (if drift found): `skills/evaluating-skill-quality/references/worked-example-self-review.md`
- Modify (if drift found): `skills/evaluating-skill-quality/references/worked-example-explaining-the-work.md`

**Interfaces:**
- Consumes: Task 1's check. This skill both defines and must follow the
  convention.

- [ ] **Step 1: Add evaluating-skill-quality's own top declaration**

It currently has no self-declaration (its L63 "## Portability level" is the
rubric section, not a self-classification). It ships its own rubric + bundled
`check_skill_shape.py` and cites only general Anthropic docs, so classify it
**Portable**. Add as the first body line after the H1:

```markdown
# Evaluating Skill Quality

**Portability: Portable.** Self-contained -- carries its own rubric and
bundled read-only `check_skill_shape.py`; cites only general Anthropic
product docs, no this-repository tooling.
```

- [ ] **Step 2: Update the rubric's Portability level section**

In `references/rubric.md`, find the Portability level section. Replace the
"declared ... near the top of SKILL.md" wording with the precise convention:
"declared as a terse one-line marker as the first body line after the H1
(the `portability-near-top` shape check enforces presence within the first 6
body lines); any extended rationale belongs in a footer `## Notes` section of
the same file (keeping it checkable from this file alone)." Keep the
Portable/Repository-scoped/Mixed definitions intact.

- [ ] **Step 3: Update the rubric's Mechanism fit section**

Add a sentence: a recorded mechanism-fit decision (the "keep vs. retire, and
why" rationale) belongs in the skill's footer `## Notes` section, not
front-loaded above the procedure.

- [ ] **Step 4: Align the SKILL.md Portability section and worked examples**

In `SKILL.md`, the "## Portability level" section (near L63) that teaches the
concept: update any "near the top" phrasing to match the new convention.
Grep both worked-example reference files for "near the top" and align any
drift. Also update the SKILL.md's cross-reference so the two agree.

Run: `grep -rn "near the top" skills/evaluating-skill-quality/` — reconcile
every hit with the new convention.

- [ ] **Step 5: Verify**

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality
```
Expected: all PASS including `portability-near-top`.

- [ ] **Step 6: Commit**

```bash
git add skills/evaluating-skill-quality/SKILL.md \
        skills/evaluating-skill-quality/references/rubric.md \
        skills/evaluating-skill-quality/references/worked-example-self-review.md \
        skills/evaluating-skill-quality/references/worked-example-explaining-the-work.md
git commit -m "docs(evaluating-skill-quality): declare own portability, align rubric to placement convention"
```

---

### Task 6: Final verification sweep

**Files:** none created; read-only verification.

- [ ] **Step 1: Run the shape checker on all 12 skills**

```bash
cd "$(git rev-parse --show-toplevel)"
for d in skills/*/; do
  echo "=== $d ==="
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" | grep -E "portability-near-top|FAIL" || echo "all PASS"
done
```
Expected: `portability-near-top PASS` for every skill; no `FAIL` lines.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest -q
```
Expected: all pass (including the 4 new checker tests).

- [ ] **Step 3: Manual confirmation**

For each skill, confirm the first body line after the H1 is its portability
declaration, and that any relocated rationale reads coherently under
`## Notes`. Confirm net-line discipline: report the branch's added/deleted
line counts for this convention change (`git diff --stat` over Tasks 1-5);
a net increase must be justified (the checker + tests legitimately add
lines; skill prose should net-decrease or hold).
```

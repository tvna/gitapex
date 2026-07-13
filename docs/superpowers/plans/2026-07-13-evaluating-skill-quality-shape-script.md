# evaluating-skill-quality shape-script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the deterministic "shape" lane of the `evaluating-skill-quality` skill into a bundled, stdlib-only checker script that becomes the single source of truth for the shape constants, and collapse the prose that duplicated them.

**Architecture:** A read-only Python module `check_skill_shape.py` lives inside the skill's `scripts/` folder so it travels on vendoring; its bundled test travels with it, and the repo `pyproject.toml` is wired to run and cover it under the existing `pytest` harness. `SKILL.md`, `rubric.md`, and the worked examples stop restating the constants and instead call/quote the script. The nine maturity dimensions stay model-judged and are deliberately not scripted.

**Tech Stack:** Python 3.12 (stdlib only), pytest + pytest-cov, uv-managed environment.

## Global Constraints

- Python `>= 3.12`; **standard library only** — no runtime dependencies (`pyproject.toml` `dependencies = []`).
- The checker is **read-only**: reads target files only, no writes, no network, no mutation. Effects limited to stdout and the exit code.
- The nine maturity dimensions are **never** scripted; the script decides shape only.
- Any GitHub-posted text is **ASCII** and carries no undisclosed provenance markers (CLAUDE.md section 3).
- Every commit cites `#32` and ends with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- `gh` CLI is authorized for GitHub writes **for this session only** (operator exception to CLAUDE.md section 3).
- This change adds a deterministic gate plus tests (new capability), so a net line increase is expected and justified; it is not a pure refactor (CLAUDE.md section 5).

---

### Task 1: Deterministic shape checker script + test + repo wiring

**Files:**
- Create: `skills/evaluating-skill-quality/scripts/check_skill_shape.py`
- Test: `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`
- Modify: `pyproject.toml` (pytest `testpaths`/`pythonpath`/`addopts`, coverage `source`)

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `check_shape(target: pathlib.Path) -> list[CheckResult]` — `target` is a skill directory or a `SKILL.md` path.
  - `CheckResult` — frozen dataclass with fields `name: str`, `passed: bool`, `rule: str`, `evidence: str`.
  - `format_report(results: list[CheckResult]) -> str`.
  - `main(argv: list[str]) -> int` — exit `0` all pass, `1` any fail, `2` bad usage.
  - Module constants (the SSOT): `DESCRIPTION_MAX_CHARS = 1024`, `NAME_MAX_CHARS = 64`, `BODY_MAX_LINES = 500`, `TOC_MIN_LINES = 100`, `RESERVED_NAME_WORDS = ("anthropic", "claude")`.

- [ ] **Step 1: Write the failing test**

Create `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`:

```python
"""Tests for the deterministic shape checker.

Fixtures are synthesized in tmp_path so the test is self-contained and
travels with the skill on vendoring.
"""
from pathlib import Path

import check_skill_shape as css


def _write_skill(tmp_path, *, name="good-skill",
                 description="Does a thing. Use when doing the thing.",
                 body_lines=10, references=None):
    d = tmp_path / "skill"
    d.mkdir()
    fm = ["---"]
    if name is not None:
        fm.append(f"name: {name}")
    if description is not None:
        fm.append(f"description: {description}")
    fm.append("---")
    filler = "\n".join(f"line {i}" for i in range(body_lines))
    (d / "SKILL.md").write_text("\n".join(fm) + "\n\n" + filler + "\n",
                                encoding="utf-8")
    if references:
        refs = d / "references"
        refs.mkdir()
        for relpath, content in references.items():
            p = refs / relpath
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    return d


def _by_name(results):
    return {r.name: r for r in results}


def test_well_formed_skill_passes(tmp_path):
    d = _write_skill(tmp_path)
    results = css.check_shape(d)
    assert all(r.passed for r in results)
    assert css.main([css.__file__, str(d)]) == 0


def test_accepts_skill_md_path_directly(tmp_path):
    d = _write_skill(tmp_path)
    assert css.main([css.__file__, str(d / "SKILL.md")]) == 0


def test_missing_description_fails(tmp_path):
    d = _write_skill(tmp_path, description=None)
    assert _by_name(css.check_shape(d))["description-present"].passed is False
    assert css.main([css.__file__, str(d)]) == 1


def test_overlong_description_fails(tmp_path):
    d = _write_skill(tmp_path, description="x" * (css.DESCRIPTION_MAX_CHARS + 1))
    assert _by_name(css.check_shape(d))["description-length"].passed is False


def test_xml_tag_in_description_fails(tmp_path):
    d = _write_skill(tmp_path, description="Use <b>when</b> doing the thing.")
    assert _by_name(css.check_shape(d))["description-no-xml"].passed is False


def test_uppercase_name_fails(tmp_path):
    d = _write_skill(tmp_path, name="Good-Skill")
    assert _by_name(css.check_shape(d))["name-pattern"].passed is False


def test_reserved_name_fails(tmp_path):
    d = _write_skill(tmp_path, name="claude")
    assert _by_name(css.check_shape(d))["name-not-reserved"].passed is False


def test_absent_name_is_not_checked(tmp_path):
    d = _write_skill(tmp_path, name=None)
    names = _by_name(css.check_shape(d))
    assert not any(k.startswith("name-") for k in names)


def test_overlong_body_fails(tmp_path):
    d = _write_skill(tmp_path, body_lines=css.BODY_MAX_LINES + 5)
    assert _by_name(css.check_shape(d))["body-length"].passed is False


def test_nested_references_fail(tmp_path):
    d = _write_skill(tmp_path, references={"sub/deep.md": "x\n"})
    assert _by_name(css.check_shape(d))["references-flat"].passed is False


def test_long_reference_without_toc_fails(tmp_path):
    body = "\n".join(f"line {i}" for i in range(css.TOC_MIN_LINES + 5))
    d = _write_skill(tmp_path, references={"big.md": body})
    assert _by_name(css.check_shape(d))["toc:big.md"].passed is False


def test_long_reference_with_toc_passes(tmp_path):
    filler = "\n".join(f"line {i}" for i in range(css.TOC_MIN_LINES + 5))
    body = "# Big\n\n## Table of contents\n\n- a\n\n" + filler
    d = _write_skill(tmp_path, references={"big.md": body})
    assert _by_name(css.check_shape(d))["toc:big.md"].passed is True


def test_bad_usage_returns_2(tmp_path):
    assert css.main([css.__file__]) == 2
    assert css.main([css.__file__, str(tmp_path / "nope")]) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest skills/evaluating-skill-quality/scripts/test_check_skill_shape.py -q`
Expected: collection/import error — `ModuleNotFoundError: No module named 'check_skill_shape'` (module not created yet; pythonpath not wired).

- [ ] **Step 3: Write the checker script**

Create `skills/evaluating-skill-quality/scripts/check_skill_shape.py`:

```python
"""Deterministic shape checker for a SKILL.md and its references/ dir.

Single source of truth for the deterministic "shape" lane of the
evaluating-skill-quality skill. It decides only the mechanically
checkable rules; the nine maturity dimensions stay model-judged and are
deliberately NOT implemented here.

Read-only: reads the target skill's files only. No writes, no network,
no mutation. Effects are limited to stdout and the process exit code.

Checks (the canonical list -- the manual fallback is to apply these):
  - description: present/non-empty, no XML tags, <= 1024 chars
  - name (only if present): lowercase-hyphenated, <= 64 chars,
    no XML tags, not a reserved word (anthropic, claude)
  - SKILL.md body: <= 500 lines
  - references/ files: exactly one level deep
  - any references/ file over 100 lines: contains a table of contents
    (a Markdown heading line matching "table of contents", case-insensitive)

Usage:
  python3 check_skill_shape.py <skill-dir-or-SKILL.md>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

DESCRIPTION_MAX_CHARS = 1024
NAME_MAX_CHARS = 64
BODY_MAX_LINES = 500
TOC_MIN_LINES = 100
RESERVED_NAME_WORDS = ("anthropic", "claude")

TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TOC_RE = re.compile(r"^#+\s+.*table of contents", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    rule: str
    evidence: str


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract top-level 'key: value' pairs from a leading --- block.

    Deliberately minimal: handles the single-line scalar values these
    skills use (name, description). No external YAML dependency.
    """
    if not text.startswith("---"):
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def _resolve_skill_md(target: Path) -> Path:
    return target / "SKILL.md" if target.is_dir() else target


def check_shape(target: Path) -> list[CheckResult]:
    skill_md = _resolve_skill_md(target)
    skill_dir = skill_md.parent
    results: list[CheckResult] = []

    text = skill_md.read_text(encoding="utf-8")
    fields = _parse_frontmatter(text)

    description = fields.get("description", "")
    if not description:
        results.append(CheckResult(
            "description-present", False,
            "description present and non-empty", "missing or empty"))
    else:
        results.append(CheckResult(
            "description-present", True,
            "description present and non-empty", "present"))
        has_tag = bool(TAG_RE.search(description))
        results.append(CheckResult(
            "description-no-xml", not has_tag,
            "description has no XML tags",
            "tag found" if has_tag else "no tags"))
        results.append(CheckResult(
            "description-length", len(description) <= DESCRIPTION_MAX_CHARS,
            f"description <= {DESCRIPTION_MAX_CHARS} chars",
            f"{len(description)} chars"))

    name = fields.get("name")
    if name:
        results.append(CheckResult(
            "name-pattern", bool(NAME_RE.match(name)),
            "name is lowercase-hyphenated", repr(name)))
        results.append(CheckResult(
            "name-length", len(name) <= NAME_MAX_CHARS,
            f"name <= {NAME_MAX_CHARS} chars", f"{len(name)} chars"))
        has_tag = bool(TAG_RE.search(name))
        results.append(CheckResult(
            "name-no-xml", not has_tag,
            "name has no XML tags", "tag found" if has_tag else "no tags"))
        results.append(CheckResult(
            "name-not-reserved", name.lower() not in RESERVED_NAME_WORDS,
            f"name not a reserved word {RESERVED_NAME_WORDS}", repr(name)))

    body_lines = len(text.splitlines())
    results.append(CheckResult(
        "body-length", body_lines <= BODY_MAX_LINES,
        f"SKILL.md body <= {BODY_MAX_LINES} lines", f"{body_lines} lines"))

    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        nested = [p for p in refs_dir.rglob("*")
                  if p.is_file() and p.parent != refs_dir]
        results.append(CheckResult(
            "references-flat", not nested,
            "references/ files are one level deep",
            "nested: " + ", ".join(sorted(str(p.relative_to(refs_dir))
                                          for p in nested))
            if nested else "flat"))
        for ref in sorted(refs_dir.glob("*")):
            if not ref.is_file():
                continue
            ref_text = ref.read_text(encoding="utf-8")
            n = len(ref_text.splitlines())
            if n > TOC_MIN_LINES:
                has_toc = bool(TOC_RE.search(ref_text))
                results.append(CheckResult(
                    f"toc:{ref.name}", has_toc,
                    f"reference over {TOC_MIN_LINES} lines has a TOC",
                    f"{n} lines, " + ("TOC found" if has_toc else "no TOC")))

    return results


def format_report(results: list[CheckResult]) -> str:
    width = max((len(r.name) for r in results), default=5)
    lines = [f"{'CHECK'.ljust(width)}  RESULT  EVIDENCE (rule)"]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"{r.name.ljust(width)}  {status}    "
                     f"{r.evidence}  ({r.rule})")
    passed = sum(1 for r in results if r.passed)
    lines.append(f"\n{passed}/{len(results)} checks passed")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 check_skill_shape.py <skill-dir-or-SKILL.md>",
              file=sys.stderr)
        return 2
    target = Path(argv[1])
    if not target.exists():
        print(f"error: path not found: {target}", file=sys.stderr)
        return 2
    results = check_shape(target)
    print(format_report(results))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Wire the repo pytest/coverage to the skill scripts dir**

Modify `pyproject.toml`. Replace the `[tool.pytest.ini_options]` and `[tool.coverage.run]` blocks with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "skills/evaluating-skill-quality/scripts"]
pythonpath = ["scripts", "skills/evaluating-skill-quality/scripts"]
addopts = "--cov=scripts --cov=skills/evaluating-skill-quality/scripts --cov-report=term-missing"

[tool.coverage.run]
source = ["scripts", "skills/evaluating-skill-quality/scripts"]
```

- [ ] **Step 5: Run the tests to verify they pass, with coverage**

Run: `uv run pytest skills/evaluating-skill-quality/scripts/test_check_skill_shape.py -q`
Expected: all tests PASS.

Then run the full suite to confirm nothing else broke:
Run: `uv run pytest -q`
Expected: existing `test_sync_pr_publish.py` tests plus the new ones PASS; coverage report lists `check_skill_shape.py`.

- [ ] **Step 6: Prove the CLI against the real skill (live proof)**

Run: `uv run python skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality`
Expected: a report table with every row `PASS` and exit code 0 (`echo $?` -> 0).

Run against a deliberately malformed target to prove failure detection:
Run: `printf -- '---\nname: Claude\ndescription: <b>x</b>\n---\n' > /tmp/bad-SKILL.md && uv run python skills/evaluating-skill-quality/scripts/check_skill_shape.py /tmp/bad-SKILL.md; echo "exit=$?"`
Expected: `name-pattern` FAIL, `name-not-reserved` FAIL, `description-no-xml` FAIL; `exit=1`.

- [ ] **Step 7: Commit**

```bash
git add skills/evaluating-skill-quality/scripts/check_skill_shape.py \
        skills/evaluating-skill-quality/scripts/test_check_skill_shape.py \
        pyproject.toml
git commit -F - <<'MSG'
feat(skills): add read-only shape checker for evaluating-skill-quality

Deterministic shape lane extracted to a stdlib-only script that owns the
shape constants and runs under the repo pytest/coverage harness. The nine
maturity dimensions stay model-judged.

Refs #32

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
MSG
```

---

### Task 2: Collapse duplicated constants in SKILL.md and rubric; fix stale evals claim

**Files:**
- Modify: `skills/evaluating-skill-quality/SKILL.md` (the "Two lanes" Deterministic shape bullet)
- Modify: `skills/evaluating-skill-quality/references/rubric.md` (dimension 1 defers exact values; dimension 8 stale `evals/` claim)

**Interfaces:**
- Consumes: `check_skill_shape.py` from Task 1 (referenced by path from prose).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Shrink the SKILL.md Deterministic shape bullet**

In `skills/evaluating-skill-quality/SKILL.md`, the "Two lanes" first bullet currently enumerates the exact constants (`<= 1024 chars`, `<= 64 chars`, `<= 500 lines`, `past 100 lines`, reserved words, etc.). Replace the enumerated values with a call to the script plus the manual fallback, keeping the two-lane framing. New bullet text:

```markdown
- **Deterministic shape** -- fixed rules a script decides, not judgment.
  Run `scripts/check_skill_shape.py <skill-dir>` (bundled with this
  skill, stdlib-only, read-only); it is the single source of truth for
  the exact rules and limits and prints PASS/FAIL per check. On a
  Python-less surface, apply the same rules by reading that script's
  check list (its module docstring enumerates them). The nine maturity
  dimensions below are deliberately not scripted.
- **Probabilistic maturity** -- nine dimensions of judgment that need a model
  or human, not a script. Full rubric with pass/fail evidence:
  [references/rubric.md](references/rubric.md).
```

- [ ] **Step 2: Defer exact values in rubric dimension 1**

In `skills/evaluating-skill-quality/references/rubric.md`, dimension 1 opens by restating the shape checklist. Keep the division of labour sentence but point the concrete values at the script. Change the opening sentence of "## 1. Discovery -- name and description" from the current "`SKILL.md`'s deterministic checklist confirms a trigger *exists* (present, no XML tags, under the length cap)." to:

```markdown
`scripts/check_skill_shape.py` (see SKILL.md, Two lanes) confirms a
trigger *exists* by shape -- present, no XML tags, under the length cap,
with the exact limits owned by that script rather than restated here.
This dimension judges whether it is the *right* trigger -- whether the
skill would win its intended request and lose a neighbour's.
```

- [ ] **Step 3: Fix the stale evals claim in rubric dimension 8**

In `skills/evaluating-skill-quality/references/rubric.md`, dimension 8 states "gitapex has neither an `evals/evals.json` nor an `evals/` directory committed to the repo today". Verify the current state first:

Run: `ls evals`
Expected: shows `issue-to-branch` (the `evals/` directory exists).

Replace the stale clause with the accurate current state:

```markdown
gitapex now has an `evals/` directory (e.g. `evals/issue-to-branch`) but
no `evals/evals.json` committed for this skill; `skill-creator` and
`waza` are available in some review sessions but are session-local
tooling, not part of the repo -- their presence in one session's
environment does not make this dimension "measured" for the repo itself.
```

- [ ] **Step 4: Verify the skill still passes its own shape check**

Run: `uv run python skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality; echo "exit=$?"`
Expected: every row PASS, `exit=0` (SKILL.md still under 500 lines, rubric.md still has its TOC, etc.).

- [ ] **Step 5: Confirm no dangling references to removed constants**

Run: `grep -rn "1024\|<= 64\|500 lines\|past 100 lines" skills/evaluating-skill-quality/SKILL.md`
Expected: no matches in `SKILL.md` (the constants now live only in the script). Matches remaining in `rubric.md`/worked-examples are addressed here (dim1) and in Task 3.

- [ ] **Step 6: Commit**

```bash
git add skills/evaluating-skill-quality/SKILL.md \
        skills/evaluating-skill-quality/references/rubric.md
git commit -F - <<'MSG'
refactor(skills): defer shape constants to the checker script

SKILL.md and rubric dimension 1 stop restating the deterministic limits;
the script is the single source of truth. Fix rubric dimension 8's stale
claim that no evals/ directory exists.

Refs #32

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
MSG
```

---

### Task 3: Replace worked-example shape tables with real script-run transcripts

**Files:**
- Modify: `skills/evaluating-skill-quality/references/worked-example-explaining-the-work.md`
- Modify: `skills/evaluating-skill-quality/references/worked-example-self-review.md`

**Interfaces:**
- Consumes: `check_skill_shape.py` from Task 1 (its actual stdout becomes the transcript).
- Produces: nothing.

- [ ] **Step 1: Capture the real transcript for the explaining-the-work target**

The worked example reviews the `explaining-the-work` skill. Capture the actual checker output:

Run: `uv run python skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/explaining-the-work`
Expected: a PASS report. Copy the exact stdout for Step 2.

- [ ] **Step 2: Replace the hand-computed table in worked-example-explaining-the-work.md**

In `skills/evaluating-skill-quality/references/worked-example-explaining-the-work.md`, the "## Deterministic shape" section contains a hand-computed Markdown table (rows for `name`, `description`, "Body <= 500 lines"). Replace that table with the captured transcript in a fenced block, framed as a real run:

````markdown
## Deterministic shape

Run the bundled checker rather than computing by hand:

```
$ python3 scripts/check_skill_shape.py skills/explaining-the-work
<paste the exact stdout captured in Step 1 here>
```

Verdict on shape alone: **well-formed** (exit code 0).
````

Keep any surrounding prose that is still accurate (e.g. the note that `name` matching the directory is a readability nit, not a shape requirement).

- [ ] **Step 3: Capture and replace the table in worked-example-self-review.md**

Run: `uv run python skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality`
Expected: a PASS report. Then, in `skills/evaluating-skill-quality/references/worked-example-self-review.md`, replace the hand-computed "## Deterministic shape" table the same way:

````markdown
## Deterministic shape

Run the bundled checker on this skill itself:

```
$ python3 scripts/check_skill_shape.py skills/evaluating-skill-quality
<paste the exact stdout captured in this step here>
```

Verdict on shape alone: **well-formed** (exit code 0).
````

- [ ] **Step 4: Verify both reference files still hold their TOCs and pass shape**

Run: `uv run python skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality; echo "exit=$?"`
Expected: every row PASS including `toc:worked-example-explaining-the-work.md` and `toc:worked-example-self-review.md` if those files still exceed 100 lines; `exit=0`.

- [ ] **Step 5: Commit**

```bash
git add skills/evaluating-skill-quality/references/worked-example-explaining-the-work.md \
        skills/evaluating-skill-quality/references/worked-example-self-review.md
git commit -F - <<'MSG'
docs(skills): show real checker transcripts in worked examples

The two worked examples demonstrate running the deterministic shape
checker instead of hand-computing the pass/fail table.

Refs #32

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
MSG
```

---

## Final verification (after all tasks)

- [ ] `uv run pytest -q` — full suite green, coverage includes `check_skill_shape.py`.
- [ ] `uv run python skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality` — all PASS, exit 0.
- [ ] `git diff --stat main...HEAD` — review the net line delta; the additions are the script + test (new deterministic gate), offset partially by the collapsed prose. Confirm the increase is the gate + tests, not scope creep.
- [ ] No `evals/evals.json` was fabricated and no eval tooling was installed (dimension-8 boundary respected).

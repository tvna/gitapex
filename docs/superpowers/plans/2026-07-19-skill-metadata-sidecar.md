# Skill Metadata Sidecar Implementation Plan (Sub-project A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every skill a `gitapex_metadata.yaml` sidecar carrying its
`portability` and `capabilityAssumption` declarations, and enforce that
sidecar in the deterministic shape checker.

**Architecture:** Each skill directory gains a Kubernetes-manifest-shaped
YAML sidecar (`apiVersion` / `kind` / `metadata` / `spec`), borrowed as a
convention only. The shape checker replaces its body-text
`portability-near-top` scan with five sidecar checks, read by a small
stdlib indentation-aware parser. The existing Portability prose in each
`SKILL.md` is split three ways rather than deleted, because some of it is
behavior-relevant.

**Tech Stack:** Python 3 standard library only (no PyYAML), pytest for the
checker's tests, Markdown for the skills.

## Global Constraints

- Spec of record: `docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md`
- Sidecar path: `skills/<skill-name>/gitapex_metadata.yaml`
- `apiVersion` is exactly `gitapex.dev/v1alpha1`
- `kind` is exactly `SkillMetadata`
- `metadata.name` equals the skill's **directory** name
- `spec.portability` is one of `Portable`, `Repository-scoped`, `Mixed`
- `spec.capabilityAssumption` is one of `Broad`, `Frontier`, `Adaptive`; every
  skill gets `Broad` in this sub-project
- Sidecar YAML: 2-space indent, plain scalars for gated fields, no block
  scalars
- `check_skill_shape.py` stays stdlib-only, read-only (no writes, no
  network) and keeps its 0/1/2 exit-code contract
- **Behavior-neutrality invariant:** no skill's runtime procedure may read
  or branch on the sidecar. It is consumed only by the checker and by a
  reviewer.
- Every commit cites `Refs #182`
- Commit messages are ASCII and carry **no** `Co-Authored-By` trailer
  (repository convention: 0 occurrences in the last 60 commits)

---

## File Structure

**Created (17 files):** `skills/<name>/gitapex_metadata.yaml` for each of:
battle-testing-a-skill, driving-pr-to-merge,
establishing-ubiquitous-language, evaluating-skill-quality,
explaining-the-work, gated-skill-edits, git-hosting-surface-audit,
issue-to-branch, issue-to-fix, merge-retrospective,
outward-artifact-preflight, ranking-the-open-queue,
responding-to-a-fresh-arrival, screening-a-low-trust-contribution,
seeding-issue-pr-templates, stop-and-replan, untrusted-input-triage.

**Modified:**
- `skills/evaluating-skill-quality/scripts/check_skill_shape.py` -- sidecar
  parser + five checks, `portability-near-top` removed
- `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py` --
  helper gains sidecar support; new positive/negative cases
- `skills/<name>/SKILL.md` (all 17) -- three-way split of the Portability
  declaration
- `skills/evaluating-skill-quality/SKILL.md` -- placement wording +
  Capability assumption section
- `skills/evaluating-skill-quality/references/rubric.md` -- placement
  wording + Capability assumption stub + TOC entry
- `skills/evaluating-skill-quality/references/worked-example-self-review.md`
  -- refreshed checker output block and declaration reading

**Task order rationale:** sidecars are created *before* the checker is
converted, so the tree is never in a state where the checker fails against
the real skills.

---

### Task 1: Create the 17 sidecar manifests

**Files:**
- Create: `skills/<name>/gitapex_metadata.yaml` (17 files, list above)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: the sidecar files Task 2's checks read. Field names other tasks
  rely on: `apiVersion`, `kind`, `metadata.name`, `spec.portability`,
  `spec.capabilityAssumption`.

Portability values were surveyed from the current `SKILL.md` body lines and
must be carried over exactly:

| skill | portability |
|---|---|
| battle-testing-a-skill | Mixed |
| driving-pr-to-merge | Portable |
| establishing-ubiquitous-language | Portable |
| evaluating-skill-quality | Portable |
| explaining-the-work | Mixed |
| gated-skill-edits | Portable |
| git-hosting-surface-audit | Mixed |
| issue-to-branch | Repository-scoped |
| issue-to-fix | Portable |
| merge-retrospective | Portable |
| outward-artifact-preflight | Repository-scoped |
| ranking-the-open-queue | Portable |
| responding-to-a-fresh-arrival | Repository-scoped |
| screening-a-low-trust-contribution | Repository-scoped |
| seeding-issue-pr-templates | Mixed |
| stop-and-replan | Portable |
| untrusted-input-triage | Portable |

- [ ] **Step 1: Write one sidecar by hand to fix the exact shape**

Create `skills/evaluating-skill-quality/gitapex_metadata.yaml`:

```yaml
apiVersion: gitapex.dev/v1alpha1
kind: SkillMetadata
metadata:
  name: evaluating-skill-quality
spec:
  portability: Portable
  capabilityAssumption: Broad
```

- [ ] **Step 2: Create the remaining 16 with the same shape**

Run this from the repository root. It writes all 17 sidecars using the
surveyed portability value per skill, including the one written by hand in
Step 1 -- the content is identical, so rewriting it is harmless and keeps
this one command the single source of the file contents:

```bash
cd "$(git rev-parse --show-toplevel)"
write_sidecar() {
  printf 'apiVersion: gitapex.dev/v1alpha1\nkind: SkillMetadata\nmetadata:\n  name: %s\nspec:\n  portability: %s\n  capabilityAssumption: Broad\n' \
    "$1" "$2" > "skills/$1/gitapex_metadata.yaml"
}
write_sidecar battle-testing-a-skill Mixed
write_sidecar driving-pr-to-merge Portable
write_sidecar establishing-ubiquitous-language Portable
write_sidecar evaluating-skill-quality Portable
write_sidecar explaining-the-work Mixed
write_sidecar gated-skill-edits Portable
write_sidecar git-hosting-surface-audit Mixed
write_sidecar issue-to-branch Repository-scoped
write_sidecar issue-to-fix Portable
write_sidecar merge-retrospective Portable
write_sidecar outward-artifact-preflight Repository-scoped
write_sidecar ranking-the-open-queue Portable
write_sidecar responding-to-a-fresh-arrival Repository-scoped
write_sidecar screening-a-low-trust-contribution Repository-scoped
write_sidecar seeding-issue-pr-templates Mixed
write_sidecar stop-and-replan Portable
write_sidecar untrusted-input-triage Portable
```

- [ ] **Step 3: Verify all 17 exist and carry the right directory name**

```bash
cd "$(git rev-parse --show-toplevel)"
for d in skills/*/; do
  n=$(basename "$d")
  f="$d/gitapex_metadata.yaml"
  [ -f "$f" ] || { echo "MISSING $f"; continue; }
  grep -q "^  name: $n$" "$f" || echo "NAME MISMATCH in $f"
  grep -qE '^  portability: (Portable|Repository-scoped|Mixed)$' "$f" || echo "BAD portability in $f"
  grep -q '^  capabilityAssumption: Broad$' "$f" || echo "BAD capabilityAssumption in $f"
done
echo "checked $(ls -1d skills/*/ | wc -l) skills"
```

Expected: no `MISSING` / `NAME MISMATCH` / `BAD` lines, and `checked 17 skills`.

- [ ] **Step 4: Confirm the existing checker is still green (nothing broken yet)**

```bash
cd "$(git rev-parse --show-toplevel)"
fail=0
for d in skills/*/; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" > /dev/null || { echo "FAIL $d"; fail=1; }
done
[ $fail -eq 0 ] && echo "all 17 pass"
```

Expected: `all 17 pass` (the old `portability-near-top` check still passes
because the body lines are still present).

- [ ] **Step 5: Commit**

```bash
git add skills/*/gitapex_metadata.yaml
git commit -m "feat: add gitapex_metadata.yaml sidecar to all 17 skills

Carries the surveyed portability value and capabilityAssumption: Broad.
No checker change yet, so the tree stays green.

Refs #182"
```

---

### Task 2: Convert the shape checker to the sidecar

**Files:**
- Modify: `skills/evaluating-skill-quality/scripts/check_skill_shape.py`
- Test: `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`

**Interfaces:**
- Consumes: the sidecar files from Task 1.
- Produces: module constants other tasks and tests reference --
  `SIDECAR_FILENAME: str`, `EXPECTED_API_VERSION: str`, `EXPECTED_KIND: str`,
  `PORTABILITY_LEVELS: tuple[str, ...]`, `CAPABILITY_ASSUMPTIONS: tuple[str, ...]`,
  and `_parse_manifest(text: str) -> dict[str, object]`. New check names:
  `metadata-file-present`, `manifest-envelope`, `metadata-name-matches-dir`,
  `portability-declared`, `capability-assumption-declared`. Removed check
  name: `portability-near-top`.

- [ ] **Step 1: Update the test helper to write a sidecar**

In `test_check_skill_shape.py`, replace the `_write_skill` function
(currently lines 13-36) with this version. It drops the hardcoded
Portability body line and gains sidecar parameters. Note `meta_name`
defaults to `"skill"` because `_write_skill` creates the directory
`tmp_path / "skill"`, and the checker compares `metadata.name` against the
*directory* name:

```python
def _write_skill(tmp_path, *, name="good-skill",
                 description="Does a thing. Use when doing the thing.",
                 body_lines=10, references=None,
                 sidecar=True, api_version="gitapex.dev/v1alpha1",
                 kind="SkillMetadata", meta_name="skill",
                 portability="Portable", capability_assumption="Broad"):
    d = tmp_path / "skill"
    d.mkdir()
    fm = ["---"]
    if name is not None:
        fm.append(f"name: {name}")
    if description is not None:
        fm.append(f"description: {description}")
    fm.append("---")
    filler = "\n".join(f"line {i}" for i in range(body_lines))
    (d / "SKILL.md").write_text(
        "\n".join(fm) + "\n\n" + filler + "\n", encoding="utf-8")
    if sidecar:
        lines = []
        if api_version is not None:
            lines.append(f"apiVersion: {api_version}")
        if kind is not None:
            lines.append(f"kind: {kind}")
        lines.append("metadata:")
        if meta_name is not None:
            lines.append(f"  name: {meta_name}")
        lines.append("spec:")
        if portability is not None:
            lines.append(f"  portability: {portability}")
        if capability_assumption is not None:
            lines.append(f"  capabilityAssumption: {capability_assumption}")
        (d / "gitapex_metadata.yaml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    if references:
        refs = d / "references"
        refs.mkdir()
        for relpath, content in references.items():
            p = refs / relpath
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    return d
```

- [ ] **Step 2: Add the failing tests**

Append to `test_check_skill_shape.py`:

```python
def test_sidecar_checks_pass_on_good_skill(tmp_path):
    d = _write_skill(tmp_path)
    by = _by_name(css.check_shape(d))
    for check in ("metadata-file-present", "manifest-envelope",
                  "metadata-name-matches-dir", "portability-declared",
                  "capability-assumption-declared"):
        assert by[check].passed is True, check
    assert css.main([str(d)]) == 0


def test_portability_near_top_check_is_gone(tmp_path):
    d = _write_skill(tmp_path)
    assert "portability-near-top" not in _by_name(css.check_shape(d))


def test_missing_sidecar_fails(tmp_path):
    d = _write_skill(tmp_path, sidecar=False)
    by = _by_name(css.check_shape(d))
    assert by["metadata-file-present"].passed is False
    assert css.main([str(d)]) == 1


def test_wrong_api_version_fails(tmp_path):
    d = _write_skill(tmp_path, api_version="example.com/v1")
    assert _by_name(css.check_shape(d))["manifest-envelope"].passed is False


def test_wrong_kind_fails(tmp_path):
    d = _write_skill(tmp_path, kind="NotASkill")
    assert _by_name(css.check_shape(d))["manifest-envelope"].passed is False


def test_metadata_name_mismatch_fails(tmp_path):
    d = _write_skill(tmp_path, meta_name="some-other-name")
    assert _by_name(css.check_shape(d))["metadata-name-matches-dir"].passed is False


def test_missing_portability_fails(tmp_path):
    d = _write_skill(tmp_path, portability=None)
    assert _by_name(css.check_shape(d))["portability-declared"].passed is False


def test_invalid_portability_value_fails(tmp_path):
    d = _write_skill(tmp_path, portability="SomewhatPortable")
    assert _by_name(css.check_shape(d))["portability-declared"].passed is False


def test_missing_capability_assumption_fails(tmp_path):
    d = _write_skill(tmp_path, capability_assumption=None)
    assert _by_name(
        css.check_shape(d))["capability-assumption-declared"].passed is False


def test_invalid_capability_assumption_value_fails(tmp_path):
    d = _write_skill(tmp_path, capability_assumption="Medium")
    assert _by_name(
        css.check_shape(d))["capability-assumption-declared"].passed is False


def test_manifest_parser_ignores_deeper_nesting(tmp_path):
    text = (
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - other-skill\n"
        "  capabilityAssumption: Broad\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed["apiVersion"] == "gitapex.dev/v1alpha1"
    assert parsed["metadata"]["name"] == "skill"
    assert parsed["spec"]["portability"] == "Portable"
    assert parsed["spec"]["capabilityAssumption"] == "Broad"
    assert "requires" not in parsed["spec"]
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd "$(git rev-parse --show-toplevel)/skills/evaluating-skill-quality/scripts"
python3 -m pytest test_check_skill_shape.py -v
```

Expected: the new tests FAIL with `KeyError: 'metadata-file-present'` (and
`AttributeError: module 'check_skill_shape' has no attribute '_parse_manifest'`
for the parser test). `test_portability_near_top_check_is_gone` also fails,
since that check still exists.

- [ ] **Step 4: Remove the old portability constants and check**

In `check_skill_shape.py`, delete these two constants (currently lines
69-70):

```python
PORTABILITY_RE = re.compile(r"\bportability\s*:", re.IGNORECASE)
PORTABILITY_MAX_BODY_LINE = 6
```

and delete this block from `check_shape` (currently lines 246-254):

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

Replace that deleted block with just the `body` binding, which the
link check below it still needs:

```python
    body = _body_after_frontmatter(text)
```

- [ ] **Step 5: Add the sidecar constants**

In `check_skill_shape.py`, add after `RESERVED_NAME_WORDS` (line 62):

```python
# The sidecar is this repository's own metadata convention, not part of the
# Anthropic Agent Skills standard -- hence the gitapex_ prefix. It is never
# auto-loaded by the skill runtime, so it can never change skill behavior.
SIDECAR_FILENAME = "gitapex_metadata.yaml"
# Kubernetes-manifest-shaped envelope, borrowed as a convention only; the
# version lets the schema grow without breaking older sidecars.
EXPECTED_API_VERSION = "gitapex.dev/v1alpha1"
EXPECTED_KIND = "SkillMetadata"
PORTABILITY_LEVELS = ("Portable", "Repository-scoped", "Mixed")
CAPABILITY_ASSUMPTIONS = ("Broad", "Frontier", "Adaptive")
```

- [ ] **Step 6: Add the manifest parser**

In `check_skill_shape.py`, add after `_parse_frontmatter` (after line 131):

```python
def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_manifest(text: str) -> dict[str, object]:
    """Parse the YAML subset the metadata sidecar is specified to use.

    Reads top-level 'key: value' scalars and exactly-two-space-indented
    scalars under a top-level map (metadata:, spec:). Deeper nesting and
    list items are deliberately skipped: no gated field uses them, and
    skipping keeps this stdlib-only with no YAML dependency. Ungated
    fields such as spec.references or spec.skillDependencies may therefore
    be arbitrarily structured without this parser needing to understand
    them.
    """
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    root: dict[str, object] = {}
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            if value:
                root[key] = _unquote(value)
                current = None
            else:
                child: dict[str, str] = {}
                root[key] = child
                current = child
            continue
        # Exactly two spaces: a four-space line (a child of a nested map)
        # has a space where this expects a key character, so it will not
        # match and is skipped.
        nested = re.match(r"[ ]{2}([A-Za-z0-9_-]+):\s*(.*)$", line)
        if nested and current is not None:
            value = nested.group(2).strip()
            if value:
                current[nested.group(1)] = _unquote(value)
    return root
```

- [ ] **Step 7: Add the five sidecar checks**

In `check_skill_shape.py`, inside `check_shape`, add immediately after the
`body-length` check block (after current line 244, before the `body =`
binding):

```python
    sidecar = skill_dir / SIDECAR_FILENAME
    if not sidecar.is_file():
        results.append(CheckResult(
            "metadata-file-present", False,
            f"{SIDECAR_FILENAME} exists next to SKILL.md", "missing"))
    else:
        results.append(CheckResult(
            "metadata-file-present", True,
            f"{SIDECAR_FILENAME} exists next to SKILL.md", "present"))
        manifest = _parse_manifest(sidecar.read_text(encoding="utf-8"))
        api = manifest.get("apiVersion")
        kind_value = manifest.get("kind")
        envelope_ok = (api == EXPECTED_API_VERSION
                       and kind_value == EXPECTED_KIND)
        results.append(CheckResult(
            "manifest-envelope", envelope_ok,
            f"apiVersion is {EXPECTED_API_VERSION} and kind is {EXPECTED_KIND}",
            f"apiVersion={api!r}, kind={kind_value!r}"))
        meta = manifest.get("metadata")
        meta_name = meta.get("name") if isinstance(meta, dict) else None
        results.append(CheckResult(
            "metadata-name-matches-dir", meta_name == skill_dir.name,
            "metadata.name equals the skill directory name",
            f"{meta_name!r} vs directory {skill_dir.name!r}"))
        spec = manifest.get("spec")
        spec = spec if isinstance(spec, dict) else {}
        portability = spec.get("portability")
        results.append(CheckResult(
            "portability-declared", portability in PORTABILITY_LEVELS,
            f"spec.portability is one of {PORTABILITY_LEVELS}",
            repr(portability)))
        capability = spec.get("capabilityAssumption")
        results.append(CheckResult(
            "capability-assumption-declared",
            capability in CAPABILITY_ASSUMPTIONS,
            f"spec.capabilityAssumption is one of {CAPABILITY_ASSUMPTIONS}",
            repr(capability)))
```

- [ ] **Step 8: Update the module docstring check list**

In `check_skill_shape.py`, replace the docstring bullet (currently lines
16-17):

```
  - portability declaration: appears within the first 6 body lines
    (a "Portability:" marker, e.g. "**Portability: Portable.**")
```

with:

```
  - metadata sidecar (gitapex_metadata.yaml, next to SKILL.md): present;
    apiVersion is gitapex.dev/v1alpha1 and kind is SkillMetadata;
    metadata.name equals the skill directory name; spec.portability is one
    of Portable/Repository-scoped/Mixed; spec.capabilityAssumption is one
    of Broad/Frontier/Adaptive. Ungated sidecar fields (spec.references,
    spec.skillDependencies) are not parsed or checked.
```

- [ ] **Step 9: Run the tests to verify they pass**

```bash
cd "$(git rev-parse --show-toplevel)/skills/evaluating-skill-quality/scripts"
python3 -m pytest test_check_skill_shape.py -v
```

Expected: PASS, all tests including the ten new ones.

- [ ] **Step 10: Run the checker against all 17 real skills**

```bash
cd "$(git rev-parse --show-toplevel)"
fail=0
for d in skills/*/; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" > /dev/null || { echo "FAIL $d"; fail=1; }
done
[ $fail -eq 0 ] && echo "all 17 pass"
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality
```

Expected: `all 17 pass`, and the printed report shows
`metadata-file-present`, `manifest-envelope`, `metadata-name-matches-dir`,
`portability-declared`, `capability-assumption-declared` all PASS and no
`portability-near-top` row.

- [ ] **Step 11: Confirm the checker is still read-only and stdlib-only**

```bash
cd "$(git rev-parse --show-toplevel)/skills/evaluating-skill-quality/scripts"
grep -nE "^(import|from) " check_skill_shape.py
grep -nE "open\(.*[\"']w|write_text|mkdir|urllib|requests|socket|subprocess" check_skill_shape.py || echo "no write/network calls"
```

Expected: imports are only `argparse`, `os.path`, `re`, `sys`,
`dataclasses`, `pathlib` (plus `__future__`); and `no write/network calls`.

- [ ] **Step 12: Commit**

```bash
git add skills/evaluating-skill-quality/scripts/check_skill_shape.py \
        skills/evaluating-skill-quality/scripts/test_check_skill_shape.py
git commit -m "feat: gate the metadata sidecar in the shape checker

Replaces the portability-near-top body scan with five sidecar checks read
by a stdlib indentation-aware manifest parser. Ungated fields
(spec.references, spec.skillDependencies) are skipped, not parsed.

Refs #182"
```

---

### Task 3: Three-way split of the Portability declarations

**Files:**
- Modify: `skills/<name>/SKILL.md` (all 17)

**Interfaces:**
- Consumes: the sidecars from Task 1 (which now hold the enum value).
- Produces: `SKILL.md` bodies with no `**Portability:` marker. No new
  symbols.

**This task is per-skill judgment, not a mechanical edit.** Each
declaration is classified into three parts per the spec's section 4.3:

1. **Enum value** -> already in the sidecar (Task 1). Remove from the body.
2. **Behavior-relevant prose** -> **stays in `SKILL.md`**. Drop only the
   `**Portability: <enum>.**` marker prefix and rewrite the remaining text
   to read as a normal opening sentence.
3. **Pure maintainer rationale** -> a `## Notes` footer at the end of the
   same `SKILL.md`.

Classification, decided from the current text:

| skill | route |
|---|---|
| battle-testing-a-skill | keep prose (says where repo-specific detail lives) |
| driving-pr-to-merge | keep prose (`Server:tool` shorthand convention) |
| establishing-ubiquitous-language | pure rationale -> `## Notes` |
| evaluating-skill-quality | pure rationale -> `## Notes` |
| explaining-the-work | keep prose (names which parts are repo-specific) |
| gated-skill-edits | keep prose (sibling mentions are examples, not deps) |
| git-hosting-surface-audit | keep prose ("substitute ... where they differ") |
| issue-to-branch | keep prose (points at the repo-specific reference file) |
| issue-to-fix | keep prose (`Server:tool` translation guidance) |
| merge-retrospective | keep prose (names the runtime MCP dependency) |
| outward-artifact-preflight | keep prose ("substitute ... where they differ") |
| ranking-the-open-queue | keep prose (tool names + scoring-axes note) |
| responding-to-a-fresh-arrival | keep prose (label source + tool convention) |
| screening-a-low-trust-contribution | keep prose ("need substituting elsewhere") |
| seeding-issue-pr-templates | keep prose (option, not a dependency) |
| stop-and-replan | keep prose (`Server:tool` -> `mcp__github__*` translation) |
| untrusted-input-triage | pure rationale -> `## Notes` |

- [ ] **Step 1: Do the three "pure rationale" skills first**

For `establishing-ubiquitous-language`, `evaluating-skill-quality`, and
`untrusted-input-triage`: delete the whole declaration paragraph from the
body and add its sentence to a `## Notes` footer at the end of the file.

Worked example -- `skills/evaluating-skill-quality/SKILL.md`. Delete these
three lines (currently lines 8-10):

```markdown
**Portability: Portable.** Self-contained -- carries its own rubric and
bundled read-only `check_skill_shape.py`; cites only general Anthropic
product docs, no this-repository tooling.
```

and append at the end of the file:

```markdown

## Notes

Portability rationale: self-contained -- carries its own rubric and bundled
read-only `check_skill_shape.py`; cites only general Anthropic product
docs, no this-repository tooling. The declared level itself lives in
`gitapex_metadata.yaml`.
```

- [ ] **Step 2: Do the 14 "keep prose" skills**

For each, remove only the `**Portability: <enum>.** ` marker prefix and
rewrite the sentence that follows so it stands on its own.

Worked example -- `skills/stop-and-replan/SKILL.md`. This text:

```markdown
**Portability: Portable.** Depends only on a connected GitHub MCP server (a
general product capability) for the Stop action below -- no
this-repository tooling. Tool names are written as `Server:tool` (portable
shorthand); in Claude Code, translate to the literal double-underscore
form -- `github:update_pull_request` is `mcp__github__update_pull_request`,
`github:add_issue_comment` is `mcp__github__add_issue_comment`.
```

becomes:

```markdown
This skill depends only on a connected GitHub MCP server (a general product
capability) for the Stop action below -- no this-repository tooling. Tool
names are written as `Server:tool` (portable shorthand); in Claude Code,
translate to the literal double-underscore form --
`github:update_pull_request` is `mcp__github__update_pull_request`,
`github:add_issue_comment` is `mcp__github__add_issue_comment`.
```

Every sentence after the marker is preserved verbatim. Apply the same
pattern to the other 13.

- [ ] **Step 3: Verify no marker survives**

```bash
cd "$(git rev-parse --show-toplevel)"
grep -rn '\*\*Portability:' skills/ && echo "MARKER STILL PRESENT" || echo "no markers remain"
```

Expected: `no markers remain`.

- [ ] **Step 4: Verify no behavior-relevant sentence was lost**

This is the behavior-neutrality invariant applied to the migration, and it
is a review step a script cannot decide. Read the diff for all 17 files:

```bash
cd "$(git rev-parse --show-toplevel)"
git diff -- skills/*/SKILL.md
```

Then confirm each of these specific strings is still present in the skill
*body* (not only in the sidecar):

```bash
grep -l 'mcp__github__update_pull_request' skills/stop-and-replan/SKILL.md
grep -l 'substitute' skills/outward-artifact-preflight/SKILL.md
grep -l 'substitute' skills/screening-a-low-trust-contribution/SKILL.md
grep -l 'substitute' skills/git-hosting-surface-audit/SKILL.md
grep -l 'Server:tool' skills/issue-to-fix/SKILL.md
```

Expected: each command prints its file path. Any miss means
behavior-relevant text was dropped -- restore it before continuing.

- [ ] **Step 5: Re-run the checker on all 17**

```bash
cd "$(git rev-parse --show-toplevel)"
fail=0
for d in skills/*/; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" > /dev/null || { echo "FAIL $d"; fail=1; }
done
[ $fail -eq 0 ] && echo "all 17 pass"
```

Expected: `all 17 pass`. Body-length and link checks must still hold after
the edits.

- [ ] **Step 6: Commit**

```bash
git add skills/*/SKILL.md
git commit -m "refactor: split Portability declarations out of skill bodies

The enum value now lives in gitapex_metadata.yaml. Behavior-relevant prose
(tool-name translation, substitute-your-repo guidance) stays in SKILL.md
with only the marker prefix dropped; pure maintainer rationale moves to a
Notes footer.

Refs #182"
```

---

### Task 4: Update the placement documentation

**Files:**
- Modify: `skills/evaluating-skill-quality/SKILL.md`
- Modify: `skills/evaluating-skill-quality/references/rubric.md`
- Modify: `skills/evaluating-skill-quality/references/worked-example-self-review.md`

**Interfaces:**
- Consumes: the check names produced by Task 2.
- Produces: documentation only; no symbols.

- [ ] **Step 1: Update the Portability level section in `SKILL.md`**

In `skills/evaluating-skill-quality/SKILL.md`, in the **Portability level**
section, replace the Repository-scoped bullet's placement clause:

```
  terse one-line marker on the first body line after the H1 (the
  `portability-near-top` shape check enforces presence within the first
  6 body lines) -- undeclared-but-repository-scoped is itself a finding.
  Extended rationale belongs in a footer `## Notes` section of the same
  file.
```

with:

```
  `portability` field in the skill's `gitapex_metadata.yaml` sidecar (the
  `portability-declared` shape check enforces its presence and value) --
  undeclared-but-repository-scoped is itself a finding. Extended rationale
  belongs in a footer `## Notes` section of `SKILL.md`.
```

- [ ] **Step 2: Add the Capability assumption section to `SKILL.md`**

Insert immediately after the **Portability level** section:

```markdown
## Capability assumption

Declared alongside portability in the skill's `gitapex_metadata.yaml`
sidecar, as `spec.capabilityAssumption`. It records which compute /
model-capability regime the skill was authored for, so conciseness and
degree of freedom are graded against the skill's own target rather than one
fixed preference.

- **Broad** -- authored to stay effective down to a weak or economical
  model, or a constrained harness.
- **Frontier** -- authored assuming a strong-reasoning model; does not
  target weak tiers.
- **Adaptive** -- a lean body a strong model runs directly, plus deeper
  `references/` a weaker model pulls on demand.

The per-dimension grading effect of each level is defined in
[references/rubric.md](references/rubric.md)'s Capability assumption
section.
```

- [ ] **Step 3: Update Procedure step 4 in `SKILL.md`**

Replace step 4:

```
4. Establish the skill's portability level per the section above.
```

with:

```
4. Read the skill's `gitapex_metadata.yaml` sidecar and establish both its
   portability level and its capability assumption per the sections above.
```

- [ ] **Step 4: Update `rubric.md` placement wording and add the stub**

In `references/rubric.md`, in the **Portability level** section's
Repository-scoped bullet, replace this text (verified verbatim against the
file -- match the line wrapping exactly):

```
Declared as a terse one-line marker on
  the first body line after the H1 (the `portability-near-top` shape
  check enforces presence within the first 6 body lines); any extended
  rationale belongs in a footer `## Notes` section of the same file,
  keeping the classification checkable from this file alone.
```

with:

```
Declared as the `portability` field in
  the skill's `gitapex_metadata.yaml` sidecar (the
  `portability-declared` shape check enforces presence and value); any
  extended rationale belongs in a footer `## Notes` section of
  `SKILL.md`.
```

Then add this section immediately after the Portability level section:

```markdown
## Capability assumption

Like the portability level, this is a precondition the review establishes
before grading (see [Contract discipline](#contract-discipline)), read from
the skill's `gitapex_metadata.yaml` sidecar. The three levels are defined
in `SKILL.md`, checkable without opening this file.

The per-dimension grading effect of Broad / Frontier / Adaptive on
dimensions 2, 3, 5, and 9 is specified in sub-project B and is not yet part
of this rubric. Until it lands, record the declared level as established
fact and grade those dimensions as before.
```

And add to the Table of contents, immediately after the
`- [Portability level](#portability-level)` line:

```markdown
- [Capability assumption](#capability-assumption)
```

- [ ] **Step 5: Refresh the worked example's checker output**

In `references/worked-example-self-review.md`, in the **Deterministic
shape** section, replace the pasted report block's
`portability-near-top` handling. The block currently lists 12 checks and
ends `12/12 checks passed`. Regenerate it for real rather than editing by
hand:

```bash
cd "$(git rev-parse --show-toplevel)"
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality
```

Paste the actual output into that code block, and update the trailing
sentence's count to match the new total.

Also, in the **Portability level** section of the same file, replace:

```
Not explicitly declared inline (`SKILL.md` never states "this skill is
Portable"), so this review reads the actual content against the
Portable / Repository-scoped / Mixed definitions in `SKILL.md` itself
```

with:

```
Declared as `portability: Portable` in this skill's
`gitapex_metadata.yaml` sidecar, and cross-read against the
Portable / Repository-scoped / Mixed definitions in `SKILL.md` itself
```

- [ ] **Step 6: Verify no stale references remain**

```bash
cd "$(git rev-parse --show-toplevel)"
grep -rn 'portability-near-top' skills/ docs/ && echo "STALE REFERENCE" || echo "no stale references"
grep -rn 'first 6 body lines' skills/ && echo "STALE WORDING" || echo "no stale wording"
```

Expected: `no stale references` and `no stale wording`.

- [ ] **Step 7: Final full verification**

```bash
cd "$(git rev-parse --show-toplevel)"
cd skills/evaluating-skill-quality/scripts && python3 -m pytest test_check_skill_shape.py -q && cd "$(git rev-parse --show-toplevel)"
fail=0
for d in skills/*/; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" > /dev/null || { echo "FAIL $d"; fail=1; }
done
[ $fail -eq 0 ] && echo "all 17 pass"
LC_ALL=C grep -rn '[^ -~]' skills/*/gitapex_metadata.yaml && echo "NON-ASCII IN SIDECAR" || echo "sidecars ASCII clean"
```

Expected: pytest passes, `all 17 pass`, `sidecars ASCII clean`.

- [ ] **Step 8: Commit**

```bash
git add skills/evaluating-skill-quality/SKILL.md \
        skills/evaluating-skill-quality/references/rubric.md \
        skills/evaluating-skill-quality/references/worked-example-self-review.md
git commit -m "docs: point placement conventions at the metadata sidecar

Portability is now read from gitapex_metadata.yaml, a Capability
assumption section is added (grading semantics deferred to sub-project B),
and the self-review's checker output is regenerated.

Refs #182"
```

---

## Done when

- All 17 skills have a valid `gitapex_metadata.yaml`
- `check_skill_shape.py` gates the sidecar and no longer scans the body for
  a portability marker
- No `**Portability:` marker remains in any `SKILL.md`, and every
  behavior-relevant sentence from the old declarations is still in the body
- `pytest` is green and the checker passes on all 17 skills
- No document references `portability-near-top`

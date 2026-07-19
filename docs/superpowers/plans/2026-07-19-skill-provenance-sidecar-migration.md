# Skill Provenance Sidecar Migration Implementation Plan (Sub-project C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `docs/skill-provenance.md`'s per-skill, maintainer-facing
provenance (commit SHAs, PR/issue numbers, corroborating external projects)
into each affected skill's `gitapex_metadata.yaml` `spec.references` field,
retire the central file, and give `spec.references` a minimal shape gate.

**Architecture:** No new files besides one plan/spec update. Four existing
sidecars (`battle-testing-a-skill`, `establishing-ubiquitous-language`,
`scorer-gated-skill-edits`, `evaluating-skill-quality`) gain a
`spec.references` YAML list of double-quoted strings, moved verbatim from
`docs/skill-provenance.md`. The shape checker's manifest parser gains a
narrow, single-purpose extension: it now descends into `spec.references`
specifically (and only that key) to parse a flat list of scalar strings,
and gains one new check, `references-well-formed`. `spec.skillDependencies`
and `spec.evalStatus` remain completely unparsed, unchanged from Sub-project
A -- this is intentionally not a general "parse all nested YAML" change.

**Tech Stack:** Python 3 standard library only (no PyYAML), pytest for the
checker's tests, Markdown/YAML for the skills.

## Decisions already settled with the operator (do not re-litigate)

- **Sequencing:** PR #189 (Sub-project B, issue #183) must merge to `main`
  first. It edits `skills/battle-testing-a-skill/gitapex_metadata.yaml`
  (`capabilityAssumption: Broad` -> `Adaptive`) -- the same file Task 1
  below edits. Task 0 is a hard blocker gate; do not start Task 1 before it
  passes.
- **`docs/skill-provenance.md`:** retire entirely (delete the file). No
  pointer stub.
- **`spec.references` gate:** add a minimal shape check now (not left
  free-form/ungated as Sub-project A's default assumption). Accept the
  blast-radius cost documented in Task 2 and Task 4 below.

## Global Constraints

- Spec of record: `docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md`
  section 4.5 (to be updated by Task 5).
- Sidecar path unchanged: `skills/<skill-name>/gitapex_metadata.yaml`.
- `check_skill_shape.py` stays stdlib-only, read-only (no writes, no
  network) and keeps its 0/1/2 exit-code contract.
- **Behavior-neutrality invariant unchanged:** no skill's runtime procedure
  may read or branch on the sidecar or on `spec.references`.
- **Content-preservation invariant (specific to this sub-project):** the
  migrated provenance entries must say exactly what
  `docs/skill-provenance.md` said. This issue relocates prose, it does not
  rewrite, summarize, or correct it. Any wording fix belongs in a separate,
  later change.
- **Boundary rule (the actual judgment call this sub-project is about):**
  only maintainer-facing provenance moves. `rubric.md`'s References section
  (grounding citations the review procedure itself relies on) is skill
  content and is explicitly NOT touched by this plan.
- Every commit cites `Refs #184`.
- Commit messages and all GitHub-post text are ASCII, no `Co-Authored-By`
  trailer.

---

## File Structure

**Deleted (1 file):** `docs/skill-provenance.md`.

**Modified:**
- `skills/battle-testing-a-skill/gitapex_metadata.yaml` -- add
  `spec.references` (5 entries).
- `skills/establishing-ubiquitous-language/gitapex_metadata.yaml` -- add
  `spec.references` (1 entry).
- `skills/scorer-gated-skill-edits/gitapex_metadata.yaml` -- add
  `spec.references` (1 entry).
- `skills/evaluating-skill-quality/gitapex_metadata.yaml` -- add
  `spec.references` (1 entry).
- `skills/evaluating-skill-quality/scripts/check_skill_shape.py` -- manifest
  parser gains a narrow `spec.references` list reader; one new check,
  `references-well-formed`; module docstring updated.
- `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py` -- new
  parser unit test plus the valid/absent/present-but-invalid check triad
  (expanded to 4 present-but-invalid variants per the lessons-learned note
  below).
- `skills/evaluating-skill-quality/SKILL.md` -- "five sidecar checks" ->
  "six sidecar checks" (Two lanes section).
- `skills/evaluating-skill-quality/references/rubric.md` -- section 4.5's
  "reserved" framing becomes "populated"; no rubric dimension changes.
- `skills/evaluating-skill-quality/references/worked-example-self-review.md`
  -- regenerate the pasted checker-output block for
  `evaluating-skill-quality` itself (own count moves from 21/21 to 22/22
  once `references-well-formed` and its own populated `spec.references`
  entry are both in place).
- `docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md`
  section 4.5 -- describe `spec.references` as populated and gated, record
  the retire-not-pointer decision, remove the "Sequencing ... open" note
  now that C's ordering is decided.

**Not modified (confirmed out of scope, checked directly against the tree):**
- `skills/battle-testing-a-skill/references/provenance-and-caveats.md` --
  its own "Comparative review" section already contains zero gitapex-local
  issue numbers; the `gitapex#74` tracking detail lives only in
  `docs/skill-provenance.md` today and is exactly what moves. No edit
  needed here.
- `skills/evaluating-skill-quality/references/rubric.md`'s References
  section (~line 849) -- grounding citations for Anthropic docs/papers the
  review procedure cites; this is the skill-content case the boundary rule
  explicitly protects. Confirmed by direct read: none of its entries
  overlap `docs/skill-provenance.md`'s content.
- The other 13 skills' sidecars -- `docs/skill-provenance.md` names exactly
  four skills; no others get a `spec.references` entry from this
  sub-project.

**Known pre-existing staleness found during research, explicitly NOT fixed
here (separate issue, out of scope for #184):**
- `skills/evaluating-skill-quality/references/worked-example-self-review.md`
  line ~457 cites `stop-and-replan`'s checker output as "9/9 checks
  passed"; the real current count is 17/17. Already wrong before this
  sub-project touches anything (predates even Sub-project A's sidecar
  checks) -- not something this change makes newly obsolete.
- `skills/evaluating-skill-quality/references/worked-example-explaining-the-work.md`
  line 90 cites `explaining-the-work`'s checker output as "8/8 checks
  passed"; the real current count is 15/15 (and the cited body-length,
  45 lines, is also stale -- it is 60 now). Same pre-existing-drift class.
- `docs/superpowers/reports/2026-07-13-skill-gap-findings.md` predates
  Sub-project A entirely (no sidecar checks in its pasted output at all) --
  a frozen historical snapshot, correctly left alone.

Consider filing a follow-up issue for the two worked-example staleness
findings; do not fold that fix into #184's diff.

**Task order rationale:** the sidecar content migration (Task 1) does not
depend on the new gate (Task 2) -- the field is written before the checker
knows to validate it, so the tree stays green throughout, matching Sub-project
A's own task-ordering discipline. Task 2 (gate) precedes Task 3
(`docs/skill-provenance.md` deletion) so the gate is proven against the four
real skills before the source-of-truth document disappears. Task 3 deletes
the file only after Task 1's content is confirmed present and correct.

---

### Task 0: Confirm PR #189 has merged (hard blocker)

**Files:** none.

- [ ] **Step 1: Check PR #189's state**

```bash
# Read-only gh usage only -- do not attempt gh pr merge/comment/etc.
gh pr view 189 --repo tvna/gitapex --json state,mergedAt,baseRefName
```

Expected: `"state": "MERGED"`. If not merged yet, STOP -- do not proceed to
Task 1. Re-check later or wait for operator confirmation.

- [ ] **Step 2: Rebase onto latest main**

```bash
cd "$(git rev-parse --show-toplevel)"
git fetch origin main
git log --oneline -3 origin/main   # confirm PR #189's merge commit is present
git checkout claude/skill-provenance-sidecar-migration-jt9s1j
git merge origin/main   # or rebase, per repository convention -- resolve any conflict in
                        # skills/battle-testing-a-skill/gitapex_metadata.yaml by hand
```

- [ ] **Step 3: Re-run the checker on all 17 skills before touching anything**

Per the lessons-learned note: a clean textual merge is not a safe merge --
prove the merged tree still behaves, don't trust the diff.

```bash
cd "$(git rev-parse --show-toplevel)"
for d in skills/*/; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" > /dev/null || echo "FAIL $d"
done
echo "baseline check done"
cat skills/battle-testing-a-skill/gitapex_metadata.yaml   # confirm capabilityAssumption: Adaptive landed correctly
uv run --frozen pytest -q
```

Expected: no `FAIL` lines, `capabilityAssumption: Adaptive` visible, pytest
green. This is the actual baseline Task 1 builds on.

---

### Task 1: Migrate the four skills' provenance content into their sidecars

**Files:**
- Modify: `skills/battle-testing-a-skill/gitapex_metadata.yaml`
- Modify: `skills/establishing-ubiquitous-language/gitapex_metadata.yaml`
- Modify: `skills/scorer-gated-skill-edits/gitapex_metadata.yaml`
- Modify: `skills/evaluating-skill-quality/gitapex_metadata.yaml`

**Interfaces:**
- Consumes: `docs/skill-provenance.md`'s current content (read, not yet
  deleted -- Task 3 deletes it after this task is verified).
- Produces: `spec.references` entries Task 2's new gate reads.

**Format:** a YAML list of double-quoted single-line strings, one entry per
citation/paragraph unit in the source file (matching its own bullet/paragraph
breaks, not re-chunked). Double-quoted (not single-quoted) because the
source prose contains apostrophes (`skill's`, `project's`) that would need
awkward `''`-doubling in single-quoted YAML; internal double quotes in the
source (e.g. `"a local, advisory harness..."`) are escaped as `\"`.

**Recommended method to avoid hand-transcription errors:** write a short,
throwaway Python snippet that reads each paragraph as a Python string
literal (so escaping is handled by the language, not by hand) and prints
the corresponding `    - "..."` YAML line via `json.dumps` (JSON string
escaping is a valid subset of YAML double-quoted-string escaping). Do not
commit the snippet -- it is a generation aid, not part of the deliverable.

Example for one entry:

```python
import json
text = ("microsoft/waza ships a `waza adversarial` command for offline "
        "adversarial / fault-injection packs -- a separate implementation "
        "of a related idea.")
print("    - " + json.dumps(text))
```

- [ ] **Step 1: `establishing-ubiquitous-language` (1 entry, simplest first)**

Source (`docs/skill-provenance.md` lines 52-59, the whole
"worked-example provenance" paragraph, verbatim). Append to
`skills/establishing-ubiquitous-language/gitapex_metadata.yaml`:

```yaml
spec:
  portability: Portable
  capabilityAssumption: Broad
  references:
    - "For readers working in this repository (gitapex), the worked example in `skills/establishing-ubiquitous-language/references/worked-example.md` (owner vs. author vs. contributor) traces to: the document `docs/motivation.md`, the draft commit `241f4392`, and the rename commit `ef222b81` on pull request #2. This is provenance for maintainers of this specific repository, not something the worked example depends on."
```

(Generate the exact escaped line with the Python method above rather than
typing it by hand; the text shown here is illustrative of content, not a
guarantee of byte-exact escaping.)

- [ ] **Step 2: `scorer-gated-skill-edits` (1 entry)**

Source (`docs/skill-provenance.md` lines 61-66, verbatim):

```yaml
  references:
    - "`skills/scorer-gated-skill-edits/scripts/score_contract.py`'s docstring refers to a \"held-out gate\"; for readers working in this repository, that gate was introduced by gitapex#30. This is provenance for maintainers of this specific repository, not something the script depends on."
```

- [ ] **Step 3: `evaluating-skill-quality` (1 entry)**

Source (`docs/skill-provenance.md` lines 68-75, verbatim):

```yaml
  references:
    - "For readers working in this repository (gitapex), the worked example in `skills/evaluating-skill-quality/references/worked-example-self-review.md` notes that this skill's own deterministic shape lane was delegated to `scripts/check_skill_shape.py`; that delegation was made in gitapex#32. This is provenance for maintainers of this specific repository, not something the worked example depends on."
```

- [ ] **Step 4: `battle-testing-a-skill` (5 entries -- do last, highest content volume)**

Source (`docs/skill-provenance.md` lines 9-50). Map one list entry per
bullet/paragraph, in source order:

1. The clairvoyance project bullet (lines 14-28, the full bullet including
   the trailing "portability write-up describes..." sentence).
2. The microsoft/waza bullet (lines 29-30).
3. The "Neither is authoritative..." paragraph (lines 32-35).
4. The gitapex#74 comparative-review paragraph (lines 37-42).
5. The gitapex#25 / PR #29 held-out-gate paragraph (lines 44-50).

```yaml
spec:
  portability: Mixed
  capabilityAssumption: Broad   # or Adaptive if PR #189 landed the reclassification -- verify against Task 0's output, do not overwrite it
  references:
    - "<entry 1, generated via the Python method above>"
    - "<entry 2>"
    - "<entry 3>"
    - "<entry 4>"
    - "<entry 5>"
```

**Do not touch `capabilityAssumption` here.** Task 0 already confirmed
whatever PR #189 set it to (`Adaptive`); this task only adds the
`references` key alongside it.

- [ ] **Step 5: Verify no content drift**

```bash
cd "$(git rev-parse --show-toplevel)"
# Every distinctive phrase from the source file must appear, unmodified, in exactly one sidecar.
grep -c "clairvoyance project" docs/skill-provenance.md skills/battle-testing-a-skill/gitapex_metadata.yaml
grep -c "gitapex#74" docs/skill-provenance.md skills/battle-testing-a-skill/gitapex_metadata.yaml
grep -c "gitapex#25" docs/skill-provenance.md skills/battle-testing-a-skill/gitapex_metadata.yaml
grep -c "241f4392" docs/skill-provenance.md skills/establishing-ubiquitous-language/gitapex_metadata.yaml
grep -c "gitapex#30" docs/skill-provenance.md skills/scorer-gated-skill-edits/gitapex_metadata.yaml
grep -c "gitapex#32" docs/skill-provenance.md skills/evaluating-skill-quality/gitapex_metadata.yaml
```

Expected: each pair of counts matches (both 1, or both 0 for a phrase that
appears once each side). This is the closest deterministic proxy for "no
rewording happened" -- follow it with an actual side-by-side read of the
four paragraphs against their sidecar entries, since a script cannot verify
paraphrase-preservation on its own.

- [ ] **Step 6: Confirm the checker still passes (gate not yet added, so this
  just proves the YAML itself doesn't break existing parsing)**

```bash
cd "$(git rev-parse --show-toplevel)"
for d in skills/battle-testing-a-skill skills/establishing-ubiquitous-language \
         skills/scorer-gated-skill-edits skills/evaluating-skill-quality; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" | tail -3
done
```

Expected: all four still exit 0 (the new list is currently ungated and
silently skipped by the parser, exactly as Sub-project A designed).

- [ ] **Step 7: Commit**

```bash
git add skills/battle-testing-a-skill/gitapex_metadata.yaml \
        skills/establishing-ubiquitous-language/gitapex_metadata.yaml \
        skills/scorer-gated-skill-edits/gitapex_metadata.yaml \
        skills/evaluating-skill-quality/gitapex_metadata.yaml
git commit -m "feat(skill-metadata): populate spec.references for 4 skills

Moves docs/skill-provenance.md's per-skill provenance (commit SHAs, PR/issue
numbers, corroborating external projects) verbatim into each skill's own
gitapex_metadata.yaml sidecar. Content unchanged, only relocated. The
central file is deleted in a later commit once this is verified.

Refs #184"
```

---

### Task 2: Add the minimal `spec.references` shape gate

**Files:**
- Modify: `skills/evaluating-skill-quality/scripts/check_skill_shape.py`
- Modify: `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`

**Interfaces:**
- Consumes: the populated sidecars from Task 1 (must pass), and the
  existing `_parse_manifest` / `ManifestParse` / `check_shape` machinery
  from Sub-project A.
- Produces: one new check name, `references-well-formed`. No existing
  check name changes.

**Design (narrow on purpose):** only `spec.references` gets parsed as a
list. `spec.skillDependencies` and any other nested/list field remain
exactly as unparsed as Sub-project A left them -- this is not a general
"parse arbitrary nested YAML" change, and Sub-project D's future gate work
is unaffected.

- [ ] **Step 1: Add a list-item pattern constant**

In `check_skill_shape.py`, add near `PORTABILITY_LEVELS` /
`CAPABILITY_ASSUMPTIONS`:

```python
# A plain "- <value>" list item, indented exactly 4 spaces (2 for the
# parent map's nesting, 2 more for the list marker) -- the only list shape
# this parser understands, and only under spec.references specifically.
REFERENCES_LIST_ITEM_RE = re.compile(r"^[ ]{4}-\s*(.*)$")
```

- [ ] **Step 2: Extend `_parse_manifest` to collect `spec.references`**

Replace the current `_parse_manifest` body with a version that tracks which
top-level key `current` belongs to, and special-cases an empty-valued
`references:` key while that top-level key is `spec`:

```python
def _parse_manifest(text: str) -> ManifestParse:
    """Parse the YAML subset the metadata sidecar is specified to use.

    Reads top-level 'key: value' scalars and exactly-two-space-indented
    scalars under a top-level map (metadata:, spec:). One exception:
    spec.references (and only that key, and only directly under spec) is
    read as a flat list of scalar strings, each a "- <value>" line indented
    exactly 4 spaces -- the shape this repository's sidecars use for
    maintainer-facing provenance (see the design spec's Sub-project C).
    Every other nested map or list (e.g. spec.skillDependencies) is still
    deliberately skipped, exactly as Sub-project A left it: no other gated
    field uses list/nested structure, and skipping keeps this stdlib-only.
    Inline '# comment' text after a value on the same line is not
    stripped -- it is read as part of the value, which is safe (fails
    closed against the expected enum/literal) but is not a supported way
    to annotate a sidecar field.

    A top-level (column-0) line that is not blank, not a '#' comment, not a
    YAML document marker ('---' or '...'), and does not match the top-level
    'key:' pattern is malformed -- e.g. a stray '- invalid mapping entry'
    that real PyYAML would reject with a ParserError. Every such line is
    collected (trimmed) into the returned ``ManifestParse.malformed_lines``,
    so a caller can fail the sidecar even though this permissive parser
    itself does not raise. Indented lines are NEVER considered malformed --
    lines under spec.references are read as list items (see above); every
    other indented line belongs to nested/list structures this parser
    deliberately does not interpret, and flagging them would defeat that
    reserved-field design.
    """
    text = text.lstrip("\ufeff")
    root: dict[str, object] = {}
    current: dict[str, object] | None = None
    current_key: str | None = None
    collecting_refs: list[str] | None = None
    malformed: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if collecting_refs is not None:
            item = REFERENCES_LIST_ITEM_RE.match(line)
            if item:
                collecting_refs.append(_unquote(item.group(1).strip()))
                continue
            current["references"] = collecting_refs
            collecting_refs = None
            # fall through: this line was not a list item, process it below
        if line[:1] in (" ", "\t"):
            nested = re.match(r"[ ]{2}([A-Za-z0-9_-]+):\s*(.*)$", line)
            if nested and current is not None:
                key, value = nested.group(1), nested.group(2).strip()
                if key == "references" and current_key == "spec" and not value:
                    collecting_refs = []
                elif value:
                    current[key] = _unquote(value)
            continue
        if line.strip() in ("---", "..."):
            continue
        top = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            if value:
                root[key] = _unquote(value)
                current = None
                current_key = None
            else:
                child: dict[str, object] = {}
                root[key] = child
                current = child
                current_key = key
            continue
        malformed.append(line.strip())
    if collecting_refs is not None and current is not None:
        current["references"] = collecting_refs
    return ManifestParse(root=root, malformed_lines=malformed)
```

Note the type annotation on `current` changes from `dict[str, str] | None`
to `dict[str, object] | None` since it can now hold a list value.

- [ ] **Step 3: Add the `references-well-formed` check**

In `check_shape`, immediately after the existing
`capability-assumption-declared` check (in the branch where the manifest
parsed successfully), add:

```python
            references = spec.get("references")
            if references is None:
                results.append(CheckResult(
                    "references-well-formed", True,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    "not declared (optional)"))
            elif (isinstance(references, list) and references
                  and all(isinstance(r, str) and r.strip() for r in references)):
                results.append(CheckResult(
                    "references-well-formed", True,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    f"{len(references)} entries"))
            else:
                evidence = ("empty list" if references == []
                            else f"not a list of non-empty strings: {references!r}")
                results.append(CheckResult(
                    "references-well-formed", False,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    evidence))
```

Also add a matching `False` result in the `manifest is None` (unreadable
sidecar) branch, alongside the other four checks there, for the same
never-silently-skip reason those already exist:

```python
            results.append(CheckResult(
                "references-well-formed", False,
                "spec.references, if present, is a non-empty list of non-empty strings",
                evidence))
```

- [ ] **Step 4: Update the module docstring**

In the docstring's checks list (currently the `metadata sidecar` bullet),
replace the sentence "Ungated sidecar scalar fields (e.g. spec.references,
spec.skillDependencies, spec.evalStatus) ARE parsed into the spec map by
_parse_manifest, just not gated/checked here" with:

```
  metadata sidecar (gitapex_metadata.yaml, next to SKILL.md): present; has
  no malformed top-level lines; apiVersion is gitapex.dev/v1alpha1 and kind
  is SkillMetadata; metadata.name equals the skill directory name;
  spec.portability and spec.capabilityAssumption are valid enum values;
  spec.references, if present, is a non-empty list of non-empty strings
  (the only gated list field -- spec.skillDependencies and spec.evalStatus
  remain unparsed and ungated, reserved for a later sub-project).
```

- [ ] **Step 5: Write the test triad (valid / absent / present-but-invalid)**

Per the lessons-learned note -- two shipped defects in Sub-project B came
from an untested present-but-invalid case -- write more than one
present-but-invalid variant. Append to `test_check_skill_shape.py`:

```python
# ---- references-well-formed ----

def test_references_absent_is_well_formed(tmp_path):
    d = _write_skill(tmp_path)
    assert _by_name(css.check_shape(d))["references-well-formed"].passed is True
    assert css.main([str(d)]) == 0


def test_references_valid_list_is_well_formed(tmp_path):
    d = _write_skill(tmp_path)
    (d / "gitapex_metadata.yaml").write_text(
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"gitapex#25\"\n"
        "    - \"PR #29\"\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is True
    assert by["references-well-formed"].evidence == "2 entries"
    assert css.main([str(d)]) == 0


def test_references_empty_list_fails(tmp_path):
    d = _write_skill(tmp_path)
    (d / "gitapex_metadata.yaml").write_text(
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False
    assert by["references-well-formed"].evidence == "empty list"
    assert css.main([str(d)]) == 1


def test_references_blank_entry_fails(tmp_path):
    d = _write_skill(tmp_path)
    (d / "gitapex_metadata.yaml").write_text(
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"gitapex#25\"\n"
        "    -    \n"
        "    - \"PR #29\"\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False
    assert css.main([str(d)]) == 1


def test_references_non_list_scalar_fails(tmp_path):
    d = _write_skill(tmp_path)
    (d / "gitapex_metadata.yaml").write_text(
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references: gitapex#25\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False


def test_manifest_parser_parses_spec_references_list(tmp_path):
    text = (
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"gitapex#25\"\n"
        "    - \"PR #29\"\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed.root["spec"]["references"] == ["gitapex#25", "PR #29"]
    assert parsed.malformed_lines == []


def test_manifest_parser_still_ignores_skill_dependencies(tmp_path):
    # Regression guard: spec.references gaining a real parser must not widen
    # to spec.skillDependencies (reserved for Sub-project D).
    text = (
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - other-skill\n"
    )
    parsed = css._parse_manifest(text)
    assert "skillDependencies" not in parsed.root["spec"]
    assert parsed.malformed_lines == []
```

- [ ] **Step 6: Run the existing test suite first -- confirm no regression
  before trusting the new tests**

```bash
cd "$(git rev-parse --show-toplevel)/skills/evaluating-skill-quality/scripts"
python3 -m pytest test_check_skill_shape.py -v
```

Expected: every pre-existing test still passes, including
`test_legitimate_deeper_nesting_passes_manifest_parsable` (its
`spec.references` fixture uses mapping-shaped list items, `- path: ...` /
`title: ...`; trace through Step 2's new parser by hand before running if
the result is surprising -- the mapping's first line is read as a literal
string item `"path: references/rubric.md"`, its second line is silently
skipped as unparsed nested content, exactly as today. That test only
asserts on `manifest-parsable`, not on `references-well-formed`, so this is
not a contradiction, but confirm it directly rather than assuming).

- [ ] **Step 7: Run all the new tests**

```bash
cd "$(git rev-parse --show-toplevel)/skills/evaluating-skill-quality/scripts"
python3 -m pytest test_check_skill_shape.py -v -k references
```

Expected: all new tests pass.

- [ ] **Step 8: Re-run the checker against all 17 real skills**

```bash
cd "$(git rev-parse --show-toplevel)"
for d in skills/*/; do
  out=$(python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" 2>&1)
  status=$?
  echo "$d -> exit $status : $(echo "$out" | tail -1)"
done
```

Expected: all 17 still exit 0. The four migrated skills' totals go up by
one each (references-well-formed now PASSes on real content); the other 13
also go up by one (the check runs unconditionally and PASSes as "not
declared"). Confirm every skill still says "N/N checks passed" (no partial
failures), not that N matches any specific prior number.

- [ ] **Step 9: Confirm stdlib-only, read-only, unchanged**

```bash
cd "$(git rev-parse --show-toplevel)/skills/evaluating-skill-quality/scripts"
grep -nE "^(import|from) " check_skill_shape.py
grep -nE "open\(.*[\"']w|write_text|mkdir|urllib|requests|socket|subprocess" check_skill_shape.py || echo "no write/network calls"
```

- [ ] **Step 10: Commit**

```bash
git add skills/evaluating-skill-quality/scripts/check_skill_shape.py \
        skills/evaluating-skill-quality/scripts/test_check_skill_shape.py
git commit -m "feat(evaluating-skill-quality): gate spec.references shape

Adds references-well-formed: when spec.references is present it must be a
non-empty list of non-empty strings. The parser change is narrowly scoped
to that one field; spec.skillDependencies and spec.evalStatus stay
unparsed, reserved for later sub-projects.

Refs #184"
```

---

### Task 3: Retire `docs/skill-provenance.md`

**Files:**
- Delete: `docs/skill-provenance.md`

**Interfaces:**
- Consumes: Task 1's migrated content (must already be verified present).
- Produces: nothing; this is a pure deletion.

- [ ] **Step 1: Final verification that every fact moved before deleting**

```bash
cd "$(git rev-parse --show-toplevel)"
for f in "clairvoyance project" "microsoft/waza ships" "gitapex#74" "gitapex#25" \
         "PR #29" "241f4392" "ef222b81" "gitapex#30" "gitapex#32"; do
  grep -rl "$f" skills/*/gitapex_metadata.yaml || echo "MISSING: $f"
done
```

Expected: every phrase resolves to at least one sidecar file; no `MISSING`
lines.

- [ ] **Step 2: Delete the file**

```bash
git rm docs/skill-provenance.md
```

- [ ] **Step 3: Confirm nothing else references it**

```bash
grep -rln "skill-provenance" . --include="*.md" --include="*.yaml" --include="*.yml" | grep -v "docs/superpowers/specs/"
```

Expected: no output (the two spec files under `docs/superpowers/specs/`
are updated by Task 4, not deleted -- they are allowed to still name the
retired file historically/descriptively).

- [ ] **Step 4: Commit**

```bash
git commit -m "docs: retire docs/skill-provenance.md

All four skills' provenance now lives in their own gitapex_metadata.yaml
spec.references (previous commit). The central file is redundant and is
deleted rather than kept as a pointer, per the operator's decision.

Refs #184"
```

---

### Task 4: Update `evaluating-skill-quality`'s own docs

**Files:**
- Modify: `skills/evaluating-skill-quality/SKILL.md`
- Modify: `skills/evaluating-skill-quality/references/rubric.md`
- Modify: `skills/evaluating-skill-quality/references/worked-example-self-review.md`

**Interfaces:**
- Consumes: the new check name from Task 2, the populated sidecar from
  Task 1.
- Produces: documentation only.

- [ ] **Step 1: `SKILL.md` -- bump the sidecar check count**

In the **Two lanes** section, replace "The five sidecar checks assume..."
with "The six sidecar checks assume...".

- [ ] **Step 2: `rubric.md` section cross-reference (if any) -- confirm no
  count is hardcoded there**

```bash
grep -n "five sidecar\|sidecar checks" skills/evaluating-skill-quality/references/rubric.md
```

Expected: no output (already confirmed during planning research; this step
just re-verifies against the actual state at implementation time).

- [ ] **Step 3: Regenerate `worked-example-self-review.md`'s pasted output**

```bash
cd "$(git rev-parse --show-toplevel)"
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality
```

Paste the actual output into the existing code block (replacing the
current 21-row/21-total block), and update the trailing "21/21 checks
passed" sentence to match the new total. Do NOT touch the separate,
already-stale "9/9 checks passed" (`stop-and-replan`) mention elsewhere in
this same file -- that predates this sub-project and is tracked as a
separate follow-up per the File Structure section above.

- [ ] **Step 4: Verify no stale wording remains**

```bash
cd "$(git rev-parse --show-toplevel)"
grep -rn "five sidecar checks" skills/ && echo "STALE WORDING" || echo "no stale wording"
```

- [ ] **Step 5: Commit**

```bash
git add skills/evaluating-skill-quality/SKILL.md \
        skills/evaluating-skill-quality/references/worked-example-self-review.md
git commit -m "docs(evaluating-skill-quality): reflect the references-well-formed check

Sidecar check count six sidecar checks (was five); self-review's pasted
checker output regenerated to match the real current total.

Refs #184"
```

---

### Task 5: Update the design spec (section 4.5) and close out C

**Files:**
- Modify: `docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md`

- [ ] **Step 1: Rewrite section 4.5**

Replace the current "Relationship to docs/skill-provenance.md (Sub-project
C)" section's forward-looking language ("Sequencing of C relative to B is
open") with a completed-state description: `spec.references` is now
populated for the four named skills, gated by `references-well-formed`,
and `docs/skill-provenance.md` is retired (not kept as a pointer). Keep the
boundary-rule paragraph (rubric.md's References section stays skill
content) -- it remains accurate and is the load-bearing rule future
sub-projects should keep citing.

- [ ] **Step 2: Update section 4.1's `spec` ungated fields bullet**

`spec.references` moves from "ungated (optional, free-form, not
checker-enforced in A)" to "gated by `references-well-formed` (Sub-project
C): when present, must be a non-empty list of non-empty strings; when
absent, no finding." Keep `spec.skillDependencies` and `spec.evalStatus`
listed as still fully ungated/reserved.

- [ ] **Step 3: Update the example in 4.1**

Replace the commented-out placeholder:

```yaml
    # references:            # (Sub-project C)
    #   - https://...
```

with a real populated example matching `evaluating-skill-quality`'s own
sidecar (post-Task 1), or note that the field is now commonly populated
and point at the real file instead of inlining one.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md
git commit -m "docs: record Sub-project C as complete in the sidecar design spec

spec.references is populated for the four skills docs/skill-provenance.md
covered, gated by references-well-formed, and the central file is retired.

Refs #184"
```

---

### Task 6: Full verification and re-review

- [ ] **Step 1: Full test suite**

```bash
cd "$(git rev-parse --show-toplevel)"
uv run --frozen pytest -q
```

Expected: green, including all Task 2 additions.

- [ ] **Step 2: Checker on all 17 skills, one more time, post-everything**

```bash
cd "$(git rev-parse --show-toplevel)"
fail=0
for d in skills/*/; do
  python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d" > /dev/null || { echo "FAIL $d"; fail=1; }
done
[ $fail -eq 0 ] && echo "all 17 pass"
```

- [ ] **Step 3: ASCII check over every changed file**

```bash
cd "$(git rev-parse --show-toplevel)"
git diff --name-only origin/main... | xargs -I{} sh -c 'LC_ALL=C grep -nP "[^ -~\t]" "{}" && echo "NON-ASCII: {}"' 2>/dev/null
echo done
```

Expected: no `NON-ASCII` lines (the migrated provenance text is already
ASCII in the source file -- verified during planning research).

- [ ] **Step 4: Per-skill content-fidelity re-review**

Re-read each of the four sidecars' `spec.references` side by side with the
version-controlled copy of `docs/skill-provenance.md` at the commit before
Task 3's deletion (`git show <task-1-commit>^:docs/skill-provenance.md` or
equivalent) -- confirm no sentence was reworded, summarized, or dropped.
This is a review step a script cannot fully decide, per the boundary rule.

- [ ] **Step 5: Independent re-review**

Per the lessons-learned note, expect the repository's automated reviewer
(or a fresh independent read) to find something a self-review missed --
budget for at least one round of post-review fixes before treating this as
done. Do not skip straight to "looks complete."

---

## Done when

- `docs/skill-provenance.md` no longer exists.
- The four named skills' `gitapex_metadata.yaml` `spec.references` contain
  their provenance content, verbatim, from the retired file.
- `references-well-formed` exists, is documented in the module docstring,
  and has a valid / absent / 3-variant-present-but-invalid test triad.
- `spec.skillDependencies` parsing/gating is unchanged (still Sub-project
  D's territory).
- `rubric.md`'s References section is untouched.
- All 17 skills still pass the shape checker; `uv run --frozen pytest -q`
  is green.
- The design spec's section 4.5 describes the field as populated, not
  reserved.
- No document was "fixed" outside this sub-project's actual change surface
  (the two pre-existing stale worked-example counts are flagged, not
  patched, here).

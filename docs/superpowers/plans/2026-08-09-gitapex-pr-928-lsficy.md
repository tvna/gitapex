# Move split.md machine-read facts to split.json, unify markdown conventions

**Goal:** Stop parsing prose with regex for machine-read eval facts. Add a
JSON Schema + `split.json` per skill that already has `split.md`,
standardize every `split.md` on one heading convention, delete
eval-status.md files that state only derivable facts, generate
`docs/skill-eval-status.md` instead of hand-maintaining it, and add a CI
gate enforcing 1:1 between `skills/*/` and `evals/*/eval.yaml` — closing
that gap by adding the two missing eval suites rather than exempting them.
Source: https://github.com/tvna/gitapex/issues/928.

**Architecture:** New schema file lives inside `scorer-gated-skill-edits`'s
own `references/` (portability precedent from #834). Five skills
(`battle-testing-a-skill`, `scorer-gated-skill-edits`,
`merge-retrospective`, `explaining-the-work`, `evaluating-skill-quality`)
each gain a `split.json` and a restructured `split.md`. Two existing gate
scripts (`gitapex_gate_split_fixture_coverage.py`,
`gitapex_gate_transfer_check_disclosure.py`) are rewritten to read
structured data instead of markdown regex. One new schema-validation gate
(`gitapex_scan_split_schema.py`) and one new parity gate
(`gitapex_gate_skill_eval_yaml_parity.py`) are added, both registered in
`.gitapex/ssot.json`. Two skills (`evaluating-context-channel-maturity`,
`setup-gitapex-toolchain`) gain a first `eval.yaml`. Six named
`eval-status.md` files are deleted. `docs/skill-eval-status.md` becomes
generated.

## Facts established live, this session

| Fact | How it was established (reproducible) |
|---|---|
| 25 skills, 23 `eval.yaml` today (not the issue's 26/24) | `ls -d skills/*/ \| wc -l`; `find evals -maxdepth 2 -name eval.yaml \| wc -l` |
| Missing `eval.yaml`: `evaluating-context-channel-maturity`, `setup-gitapex-toolchain` | `for d in skills/*/; do n=$(basename "$d"); [ -f "evals/$n/eval.yaml" ] \|\| echo "$n"; done` |
| `evaluating-context-channel-maturity` already has 13 `tasks/*.yaml`, just no `eval.yaml` | `ls evals/evaluating-context-channel-maturity/tasks/*.yaml \| wc -l` |
| `setup-gitapex-toolchain` has neither `tasks/` nor `eval.yaml` | `ls evals/setup-gitapex-toolchain/` |
| `trials_per_task`: 19 declare `3`, 4 declare `1` (not the issue's 19/5) | `grep -l 'trials_per_task: 3' evals/*/eval.yaml \| wc -l`; `grep -l 'trials_per_task: 1' evals/*/eval.yaml \| wc -l` |
| `explaining-the-work` and `evaluating-skill-quality` both carry the identical, wrong H1 `# Held-out split for scorer-gated-skill-edits` in their own `split.md` | `head -1 evals/explaining-the-work/split.md evals/evaluating-skill-quality/split.md` |
| Human decision: full 1:1 parity achieved *within this PR*, not an allowlist exemption for the two gap skills | `AskUserQuestion` answer, this session -- see PR #976's own Execution log for the recorded authorization |

## Acceptance Criteria Map

(Full table lives durably in PR #976's own body -- https://github.com/tvna/gitapex/pull/976 -- not reproduced verbatim here to avoid a second copy drifting out of sync; see also the
`planning-a-branch-from-an-issue` output. Each task below quotes its own
row.)

## File-ownership map (per `gitapex_check_file_ownership_conflicts.py` logic, computed by hand)

No two tasks below write the same file. Where a shared file exists
(`.gitapex/ssot.json`), the owning tasks are sequenced into different
waves rather than co-assigned.

## Interface-dependency map

- T2–T8 (the five split.md→split.json conversions + the two new eval
  suites) each read the finished shape of `split.schema.json` (T1) before
  writing conforming JSON → each has an edge on T1.
- T9 (rewrite `gitapex_gate_split_fixture_coverage.py`), T10 (rewrite
  `gitapex_gate_transfer_check_disclosure.py`), and T11 (new
  `gitapex_scan_split_schema.py`) each read the final `split.json`/`split.md`
  shape produced by T2–T6 → each has an edge on T2–T6.
- T12 (eval.yaml↔skills parity gate) reads the final eval.yaml set,
  produced by T7–T8 → edge on T7, T8. It also writes
  `.gitapex/ssot.json` → sequenced after T11 (which also writes it).
- T14 (generate `docs/skill-eval-status.md`) reads the final state of
  every `eval.yaml`, `eval-status.md`, and the new parity gate's own
  registration → edge on T7, T8, T12, T13.
- T13 (delete 6 eval-status.md, adjust coverage test) has no edge on the
  split.json work; independent.

## Wave assignment

- **Wave 1:** T1
- **Wave 2 (parallel, worktree-isolated):** T2, T3, T4, T5, T6, T7, T8
- **Wave 3 (parallel, worktree-isolated):** T9, T10, T11, T13
- **Wave 4:** T12 (solo — shares `.gitapex/ssot.json` with T11)
- **Wave 5:** T14 (solo — reads everything upstream)

---

### Task T1: Author the split.json JSON Schema

**Files:** Create `skills/scorer-gated-skill-edits/references/split.schema.json`

**ACM row quoted:** "Schema validation: every committed split.json
validates; the checks currently implemented as prose regexes are
re-expressed as schema constraints plus set arithmetic" /
"Portability: the schema lives within the skill directory per existing
deployment guidelines" — Planned ops: "Author
`skills/scorer-gated-skill-edits/references/split.schema.json`; author
`evals/{5 skills}/split.json` from each skill's current split.md content."

- [ ] Draft 2020-12 schema, `additionalProperties: false` throughout,
      `$id: "https://github.com/tvna/gitapex/blob/main/skills/scorer-gated-skill-edits/references/split.schema.json"`
      — same `$id` convention as `skill-metadata.schema.json`.
- [ ] Required top-level keys: `assignment` only (a fixture-list object
      keyed by split name, e.g. `train`/`selection`/`test`, each an array
      of fixture-filename strings; each fixture entry, where a source file
      declares `expected.exercises`, carries it as an array of strings
      matching real `###`-level SKILL.md headings — Check C's own
      cross-file contract, defined here rather than left implicit).
      Optional top-level keys (per T2's own finding that 2 of 5 skills
      declare none of this today — do not require what the source data
      doesn't have): `partition` (a string matching `^\d+:\d+:\d+$`, never
      a bare YAML-hazard-shaped number — this is JSON so no coercion risk,
      but keep it a string for consistency with the "not YAML" rationale
      in the issue), `split_arithmetic_exclusions` (array, may be empty,
      required together with `partition` when `partition` is present —
      Check D's own precondition), `equivalence_classes` (array of
      `{train_fixture, held_out_fixture}`-shaped objects, may be empty —
      Check B's own precedence-pair contract).
- [ ] No `$ref` outside the file itself (portability: the schema must
      resolve standalone inside the skill's own directory, per the
      Dependency-file-portability check).
- [ ] This nested shape is the actual contract Checks A-D (T9) and the
      schema gate (T11) will read — if a real split.md's current content
      doesn't cleanly map to it once read, fix the schema to match reality
      rather than forcing reality into an invented shape.

---

### Task T2: Migrate `battle-testing-a-skill/split.md`

**Files:** Modify `evals/battle-testing-a-skill/split.md`; create
`evals/battle-testing-a-skill/split.json`

**ACM row quoted:** "Coverage uniformity: every iteration entry in every
file is in scope for the transfer-check requirement" / Planned ops:
"convert `## Assignment` into `split.json` conforming to
`split.schema.json`; standardize the H1 to `# battle-testing-a-skill held-out
split`; add `## Corpus size caveat` and `## Blind spot pass` sections if
genuinely applicable, otherwise state explicitly why not."

- [ ] Extract the current `## Assignment` bullet list into
      `split.json`'s `assignment` object; there is no declared partition
      or equivalence-classes content in this file today per this session's
      own research pass — represent that honestly (`partition: null` is
      not valid per the required-fields rule above, so state the schema
      allows this by not requiring partition when no `N:N:N` line
      exists in the source, OR add one only if the file's own fixture
      count can produce a real one — do not fabricate a number that
      wasn't in the source).
- [ ] Rewrite `split.md`: H1 `# battle-testing-a-skill held-out split`; no
      `## Iteration:` entries exist yet, so no conversion needed there —
      leave a narrative-only file with just the sections that have real
      content, do not add empty placeholder headings.

---

### Task T3: Migrate `scorer-gated-skill-edits/split.md`

**Files:** Modify `evals/scorer-gated-skill-edits/split.md`; create
`evals/scorer-gated-skill-edits/split.json`

**ACM row quoted:** same as T2's, applied to this skill. Planned ops:
identical shape — extract `## Assignment` to JSON, standardize H1 to
`# scorer-gated-skill-edits held-out split`.

- [ ] Same procedure as T2, this skill's own file.

---

### Task T4: Migrate `merge-retrospective/split.md`

**Files:** Modify `evals/merge-retrospective/split.md`; create
`evals/merge-retrospective/split.json`

**ACM row quoted:** Planned ops: "extract the declared `N:N:N` partition
and `## Equivalence classes` table into `split.json`; rename `## Corpus
size and the 2:1:7 caveat` to `## Corpus size caveat` (keep the 2:1:7
narrative content, just the heading changes); confirm H1 already
self-names correctly; convert `## Kept-edit log`/`## Rejected-edit log`
structure to the standardized `## Iteration:` heading form — this file
has zero iteration entries today, so this is a structural template
change, not a content conversion."

- [ ] Extract partition string and Equivalence-classes rows into
      `split.json`, validate against T1's schema.
- [ ] Rename the corpus-size-caveat heading only; preserve its prose
      verbatim.
- [ ] Restructure `## Kept-edit log` / `## Rejected-edit log` into the
      standardized `## Iteration: <issue>, <title>` / `### Gate result` /
      `### Transfer check` / `### Rejected-edit log` / `### Verdict`
      heading skeleton — with zero existing entries, this only changes the
      section skeleton, not any narrative content.

---

### Task T5: Migrate `explaining-the-work/split.md`

**Files:** Modify `evals/explaining-the-work/split.md`; create
`evals/explaining-the-work/split.json`

**ACM row quoted:** Planned ops: "fix the wrong H1 (currently states
`# Held-out split for scorer-gated-skill-edits`, should self-name); extract
declared partition + equivalence classes to `split.json`; the 5 existing
`## Iteration:` entries already use the target heading convention —
verify each has a real, non-placeholder `### Transfer check` subsection
already, since this file is the one the issue names as already using the
later convention."

- [ ] Fix the H1 to `# explaining-the-work held-out split`.
- [ ] Extract partition/equivalence-classes/assignment content to
      `split.json`.
- [ ] Do NOT rewrite the 5 existing `## Iteration:` entries' prose —
      confirm each already has `### Gate result` / `### Transfer check` /
      `### Rejected-edit log` / `### Verdict` subsections; only add a
      missing subsection heading if one is structurally absent, never
      invent its content.

---

### Task T6: Migrate `evaluating-skill-quality/split.md`

**Files:** Modify `evals/evaluating-skill-quality/split.md`; create
`evals/evaluating-skill-quality/split.json`

**ACM row quoted:** Planned ops: "fix the wrong H1; extract partition +
assignment to split.json; rename `## Corpus size and the 2:1:7 caveat` to
`## Corpus size caveat` (preserve prose); add a `## Blind spot pass`
section if genuinely missing (this file has `## Compatibility-awareness
branch coverage` instead per this session's research — do not blindly
rename that to `## Blind spot pass` if it serves a different, narrower
purpose; if it is the same concept under a different name, rename and
preserve content, otherwise add a new, honestly-scoped `## Blind spot
pass` section alongside it and say so); convert all 15 `**Iteration:`
bold-paragraph entries to the standardized `## Iteration:` heading form
with `### Gate result` / `### Transfer check` / `### Rejected-edit log` /
`### Verdict` subsections, preserving each entry's existing prose
verbatim under the correct subheading — this is the highest-risk file in
the migration (3,248 lines, 15 entries): do this as a structural,
content-preserving transform, verify no prose is lost per entry by an
exact normalized-text comparison (strip only the heading markup itself,
diff the remaining prose character-for-character — equal counts alone do
not prove equal content), with a non-whitespace byte count as a secondary
sanity check, not the primary proof."

- [ ] This is the largest, highest-risk task in the whole plan. Read the
      full file first. Build a mapping of each `**Iteration:` entry's
      current implicit sub-content (its own "transfer check" prose, "gate
      result" prose, etc., however currently labeled/unlabeled) to the new
      explicit subheadings — do not summarize or drop any sentence.
  - [ ] Fix H1, rename corpus-size-caveat heading, extract
        `split.json`.
  - [ ] Convert all 15 entries; run a before/after exact normalized-text
        comparison per entry (heading markup stripped, prose diffed
        verbatim) as the primary proof, plus a non-whitespace byte-count
        diff as a secondary sanity check, before finishing.
  - [ ] Resolve the "Compatibility-awareness branch coverage" vs "Blind
        spot pass" question per the interpretation above — do not guess
        silently if the file's own content doesn't make it clear; if
        genuinely ambiguous, add `## Blind spot pass` as a new section
        rather than overwriting the existing one, and note the ambiguity
        in this task's own commit message.

---

### Task T7: New `eval.yaml` for `evaluating-context-channel-maturity`

**Files:** Create `evals/evaluating-context-channel-maturity/eval.yaml`

**ACM row quoted:** "Suite enforcement: 26 skills and 26 eval.yaml; deleting
one fails the new gate" (the issue's own text, citation only — the
operative, verified target for this task list is **25 skills, 25
eval.yaml**, per this file's own Facts table above) / Planned ops: "create
`evals/evaluating-context-channel-maturity/eval.yaml` wiring the 13
already-committed `tasks/*.yaml` files, `trials_per_task: 3` (repo's
dominant convention), matching the shape of a comparable existing
`eval.yaml` (e.g. `evaluating-deterministic-gate-quality`'s, a sibling
skill of similar shape)."

- [ ] Read an existing comparable `eval.yaml` for its exact schema/keys.
- [ ] Wire all 13 existing task files; do not invent new tasks — they
      already exist, this is purely making them runnable via a declared
      suite.

---

### Task T8: New eval suite for `setup-gitapex-toolchain` (eval.yaml + tasks/)

**Files:** Create `evals/setup-gitapex-toolchain/eval.yaml`; create a
minimal `evals/setup-gitapex-toolchain/tasks/*.yaml` set

**ACM row quoted:** same criterion as T7. Planned ops: "build a minimal
but real eval suite for `setup-gitapex-toolchain` sized comparably to the
repo's smallest existing suites (e.g. `scorer-gated-skill-edits`'s ~3
tasks), exercising its own documented behavior (provisioning the 4 pinned
toolchain binaries + `apm install` for a fresh ephemeral session, and its
`--verify` re-run mode) — read the skill's own SKILL.md first, do not
fabricate scenarios it doesn't itself describe."

- [ ] Read `skills/setup-gitapex-toolchain/SKILL.md` in full before
      writing any task.
- [ ] Read the smallest existing `tasks/*.yaml` set (e.g.
      `scorer-gated-skill-edits`) for the task-file schema/shape.
- [ ] Write `eval.yaml` (`trials_per_task: 3`) + 2-4 tasks scoped to
      real, documented behavior only — no invented capability.

---

### Task T9: Rewrite `gitapex_gate_split_fixture_coverage.py` for split.json

**Files:** Modify `.github/scripts/gitapex_gate_split_fixture_coverage.py`;
modify `tests/test_gitapex_gate_split_fixture_coverage.py`

**ACM row quoted:** "the checks currently implemented as prose regexes
are re-expressed as schema constraints plus set arithmetic" / Planned
ops: "Checks A (fixture superset), B (precedence-pair), D (partition
arithmetic) read `split.json` directly instead of regex-parsing
`split.md`; Check C (fixture `expected.exercises` vs SKILL.md `###`
headings) stays cross-file set arithmetic, now against JSON instead of
markdown-parsed bullets. Gate-result tables (still narrative, still in
`split.md`) keep a narrowly-scoped regex only for that piece."

- [ ] Re-run all 4 checks against the real, migrated `split.json`/`split.md`
      pairs from T2–T6 (this task is in a later wave specifically so this
      data exists).
- [ ] Update/extend `tests/test_gitapex_gate_split_fixture_coverage.py`'s
      own drift tests (which assert against this repo's real files) to
      match the new JSON-based shape.

---

### Task T10: Rewrite `gitapex_gate_transfer_check_disclosure.py`

**Files:** Modify `.github/scripts/gitapex_gate_transfer_check_disclosure.py`;
modify `tests/test_gitapex_gate_transfer_check_disclosure.py`

**ACM row quoted:** "Coverage uniformity: every iteration entry in every
file is in scope for the transfer-check requirement, versus 12 of 17
today" / Planned ops: "recognize only the standardized `## Iteration:`
heading form (both former conventions now converge to it after T2–T6);
require a non-empty `### Transfer check` subsection under every entry, in
every one of the 5 files, not diff-scoped only."

- [ ] Drop the old `**Iteration:` bold-paragraph recognition entirely —
      after T2–T6, no file uses it anymore.
- [ ] Extend from diff-scoped-only to whole-file, since the criterion is
      "every iteration entry in every file," not only newly-added ones.
- [ ] Update tests; run against all 5 real migrated files.

---

### Task T11: New `gitapex_scan_split_schema.py` CI gate

**Files:** Create `.github/scripts/gitapex_scan_split_schema.py`; create
`tests/test_gitapex_scan_split_schema.py`; modify `.gitapex/ssot.json`
(register the new gate, `split-schema-drift` id, following the
`skill-metadata-schema-drift` entry's own shape exactly)

**ACM row quoted:** "Schema validation: every committed split.json
validates" / Planned ops: same shape as
`gitapex_scan_skill_metadata_schema.py` — `jsonschema.Draft202012Validator`
layered with any needed cross-file pydantic checks, wired into
`.github/workflows/test.yml`'s existing pytest step (no new CI step
needed, `tests/` already runs there).

- [ ] Mirror `gitapex_scan_skill_metadata_schema.py`'s structure exactly.
- [ ] Discover `split.json` files at runtime (glob `evals/*/split.json`),
      never a hardcoded list of the 5 skills known today — a 6th skill
      gaining a `split.json` later must be caught by this gate
      automatically, not silently skipped. Validate whatever the glob
      finds; today that resolves to 5 files.
- [ ] Regression test: a malformed extra `split.json` fixture (a 6th file,
      violating the schema) must fail the gate — not just the 5 real,
      valid ones passing.

---

### Task T12: New `gitapex_gate_skill_eval_yaml_parity.py` CI gate

**Files:** Create `.github/scripts/gitapex_gate_skill_eval_yaml_parity.py`;
create `tests/test_gitapex_gate_skill_eval_yaml_parity.py`; modify
`.gitapex/ssot.json` (register `skill-eval-yaml-parity`)

**ACM row quoted:** "Suite enforcement: 26 skills and 26 eval.yaml; deleting
one fails the new gate" (the issue's own text, citation only — the
operative, verified target is **25 skills, 25 eval.yaml**, same note as
T7/T8) / Planned ops: "normalize both sides to bare skill names before
comparing (strip the `skills/` root and any trailing slash on one side,
strip the `evals/` root and the trailing `/eval.yaml` on the other — never
compare raw paths, which can never be equal to each other) and assert the
two name sets are equal; tests cover a missing skill, an extra orphaned
`eval.yaml`, a case-mismatched name, and a trailing-slash input, each
failing the gate."

- [ ] Depends on T7/T8 landing first (wave 4, after wave 2) so the real
      repo state is genuinely 25/25 when this gate is added — it must
      pass against the real tree from the moment it's added, never land
      pre-broken.
- [ ] Adversarial defeat-case per step 8's own requirement (see below) —
      construct a case that would defeat naive set-equality (e.g. a
      case-sensitivity mismatch, a trailing-slash path variant) and add
      it as a regression test.

---

### Task T13: Delete 6 fact-only eval-status.md files, adjust coverage test

**Files:** Delete `evals/planning-a-branch-from-an-issue/eval-status.md`,
`evals/drafting-a-pr-to-merge/eval-status.md`,
`evals/stop-and-replan/eval-status.md`,
`evals/outward-artifact-preflight/eval-status.md`,
`evals/ranking-the-open-queue/eval-status.md`,
`evals/establishing-ubiquitous-language/eval-status.md`; modify
`tests/test_gitapex_skill_eval_status_coverage.py`

**ACM row quoted:** "Six eval-status.md files are the same four facts in
six different prose forms ... become deleted once their content is
derived from other sources, with the 1:1 test adjusted accordingly" /
Planned ops: "read each of the 6 in full first to confirm no non-derivable
judgment prose is being lost; delete; relax the coverage test's 1:1 rule
to not require eval-status.md for a skill whose facts are fully
derivable from eval.yaml/results."

- [ ] Read each of the 6 files in full before deleting — if any contains
      judgment prose beyond the four repeated facts (why a gap was
      accepted, why a verdict was disbelieved), do not delete that file;
      flag it as a `NeedsInput` instead of silently keeping the issue's
      characterization.

---

### Task T14: Generate `docs/skill-eval-status.md`

**Files:** Create `.github/scripts/gitapex_generate_skill_eval_status.py`;
create `tests/test_gitapex_generate_skill_eval_status.py` (drift check:
regenerated output must match the committed file byte-for-byte);
regenerate and commit `docs/skill-eval-status.md`

**ACM row quoted:** "duplicate facts eliminated ... docs/skill-eval-status.md
becomes generated from those sources" / Planned ops: "derive trials from
eval.yaml, fixture counts from tasks/, evaluated models + baseline
presence from results/*/manifest.json, dimension coverage from
gitapex_check_dimension_coverage.py; the three existing hand-authored
narrative sections move into their own small checked-in source (not
parsed back out of the previous generated `docs/skill-eval-status.md`,
which would make the drift check non-reproducible from a clean checkout
and silently perpetuate any stale narrative forever) -- a
`docs/skill-eval-status-narrative.md` (or equivalent reviewed template)
the generator reads alongside the derived data and renders into the final
document; regenerate the Index table and any sentence stating a derivable
fact (fixing the stale 'All 12... trials_per_task: 3' sentence as a side
effect of no longer hand-writing it)."

- [ ] Depends on the final state of every `eval.yaml`/`eval-status.md`
      (T7, T8, T13) — must run last.
- [ ] Extract the 3 existing narrative sections from the current
      `docs/skill-eval-status.md` into their own separate source file
      FIRST (a one-time, reviewed extraction), then point the generator at
      that file, never at the generator's own prior output.
- [ ] Wire the drift check into the same pytest step other gates use;
      confirm it passes starting from a clean checkout (regenerate into a
      temp path and diff, don't just trust the working tree already
      matches).

---

## Step 8 (mandatory, after all tasks land): aggregate refactor + adversarial review

Not a task above — runs once, over the full accumulated diff, per
`refactor-and-review-gate.md`. Required defeat-cases: at minimum one
against T11 (schema-validation gate) and one against T12 (parity gate),
since both are new deterministic gates added by this diff.

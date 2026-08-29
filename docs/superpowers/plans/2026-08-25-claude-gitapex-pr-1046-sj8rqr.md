# scorer-gated KEEP gate + evaluation-driven validation for bundled-script comment criteria (issue #1046)

> **For agentic workers:** REQUIRED SUB-SKILL: Use gitapex:executing-a-branch-plan to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run this repository's own `scorer-gated-skill-edits` precondition
gate against the rubric.md/shape-checker draft #1045 landed (merged PR
#1074), and separately complete #1045's own (E) requirement: an empirical
with-rule-vs-without-rule comparison on a real bundled script. Source:
https://github.com/tvna/gitapex/issues/1046.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 5):** the issue's own drafted ACM was independently re-checked against
repo state before this plan was written, not accepted as pre-verified. Two
corrections were made, both recorded on the issue body itself
("Re-verification note", 2026-08-25T13:07:41Z):

1. The issue's ACM row 1 cites a `27:30:12` selection-split partition. The
   actual current partition (`evals/evaluating-skill-quality/split.json`)
   was `31:34:14` at the time this plan was written -- `27:30:12` is a
   mid-series snapshot recorded in `split.md` from an earlier iteration,
   not the current split. This plan uses the actual current split.
2. The issue's own wording calls the gate run "waza-based". The actual
   `scorer-gated-skill-edits/SKILL.md` Step 1 procedure invokes
   `uv run python3 evals/scripts/gitapex_run_eval_suite.py`, not `waza`
   directly -- `waza` is the separate CI-side runner for
   `.github/workflows/waza-eval-gate.yml`. This plan follows the SKILL.md's
   actual documented procedure.

**Architecture:** No production code changes. All changes are evals/
fixture content, `evals/evaluating-skill-quality/split.json`/`split.md`,
and a new run-record/comparison-record location under
`evals/evaluating-skill-quality/`. `skills/evaluating-skill-quality/references/rubric.md`
itself is NOT modified by this issue -- it is the already-merged #1045
draft being gated, read-only here.

**Tech Stack:** YAML fixtures (`evals/evaluating-skill-quality/tasks/*.yaml`),
JSON (`split.json`), Markdown (`split.md`, run/comparison records), Python
(`evals/scripts/gitapex_run_eval_suite.py`, `skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`),
`uv`.

## Global Constraints

- Must not invoke or structurally depend on the `explaining-the-work`
  skill (same constraint as #1045).
- Re-confirm the eval runner's exact commit at execution time
  (`scorer-gated-skill-edits/SKILL.md` Step 1) -- never assume the
  version recorded during planning is still current.
- `skills/evaluating-skill-quality/references/rubric.md` is out of scope
  for edits in this issue. A REJECT verdict from Task 2's gate sends the
  rubric.md wording back to a #1045 follow-up, not a same-PR edit here.
- `evals/scripts/gitapex_run_eval_suite.py`'s default `claude-cli` executor
  spawns a subprocess whose environment is filtered to
  `PATH`/`HOME`/`ANTHROPIC_API_KEY`/`TMPDIR`/`TMP`/`TEMP`
  (`evals/scripts/gitapex_run_ablation.py`'s `_hermetic_env()`) -- this
  remote session's own OAuth-based Claude CLI auth is not in that
  allowlist, so a measured trial requires `ANTHROPIC_API_KEY` set in this
  session's environment before Task 2/3 can run live.

---

### Task 1: New selection-split fixtures for the new dimension-7 sub-rules

**Files:**
- Create: `evals/evaluating-skill-quality/tasks/no-voodoo-constant-{train,selection,test}.yaml`
- Create: `evals/evaluating-skill-quality/tasks/script-execution-intent-{train,selection,test}.yaml`
- Create: `evals/evaluating-skill-quality/tasks/comment-categorization-{train,selection,test}.yaml`
- Create: `evals/evaluating-skill-quality/tasks/context-economy-{train,selection,test}.yaml`
- Modify: `evals/evaluating-skill-quality/split.json` (assignment + partition)
- Modify: `evals/evaluating-skill-quality/split.md` (Corpus size caveat section)

**Interfaces:**
- Consumes: nothing from other tasks (first task).
- Produces: the updated held-out split Task 2's gate run scores against;
  Task 2 cannot run a representative selection-split measurement of the
  #1045 rubric.md patch without this task's new fixtures in place, since
  none of the pre-existing fixtures exercise the four new dimension-7
  sub-rules.

Issue #1046 ACM row 3 (quoted verbatim): "Per the issue #149/#155
precedent already recorded in split.md, any new rubric.md rule needs
matching held-out fixtures exercising both its positive and negative
branch, not just a prose addition" / Planned ops: "Add fixtures to
evals/evaluating-skill-quality/tasks/ and update split.json/split.md's
declared partition and Assignment section" / Proof method:
".github/scripts/gitapex_gate_split_fixture_coverage.py passes on the
updated split.md/split.json".

- [x] **Step 1: Author 12 new fixtures, one train/selection/test triple per sub-rule**

Four dimension-7 sub-rules added by #1045: `no-voodoo-constant` and
`script-execution-intent-stated` (mechanized checks in
`gitapex_check_skill_shape.py`), and the prose-only `Comment
categorization` (Interface vs. Implementation) and `Context economy`
(token cost) axes in `rubric.md`. Each gets a train fixture (a positive
violation), a selection fixture (a different positive violation shape,
gating generalization), and a test fixture (a restraint/negative case,
read once). Followed `shared-bundled-script-{undeclared-reach-train,
boundary-fit-selection,declared-dependency-restraint}.yaml`'s existing
train/selection/test triple as the structural precedent. Each fixture's
`expected.output_contains`/`output_not_contains` avoids a bare phrase a
correct denial would also contain, per
`scorer-gated-skill-edits/SKILL.md`'s "Authoring fixtures for a substring
scorer" section (caught and fixed during authoring: an early draft of the
two restraint fixtures used `output_not_contains: "voodoo constant"` /
`"execution intent"`, which a correct PASS explanation would also contain
-- corrected to the shared `"LGTM"`/`"no concerns"` convention instead).

- [x] **Step 2: Update `split.json`'s assignment and partition**

Appended the 12 new filenames to `assignment.train`/`assignment.selection`/`assignment.test`
(4 each) and recomputed `partition` from `31:34:14` to `35:38:18`
(train count still nets against the pre-existing
`dispatch-required-negative-control.yaml` exclusion, unchanged).

- [x] **Step 3: Update `split.md`'s Corpus size caveat section**

Appended a new `4:4:4` addition line (gitapex#1046) to the cumulative
partition-derivation prose, and updated the final partition figure and
the Assignment-section unique-count sentence to match `35:38:18`.

- [x] **Step 4: Verify**

`uv run python3 .github/scripts/gitapex_gate_split_fixture_coverage.py --split-md evals/evaluating-skill-quality/split.md --skill-md skills/evaluating-skill-quality/SKILL.md`
-> PASS. `uv run python3 .github/scripts/gitapex_scan_split_schema.py` -> no
drift. `uv run python3 evals/scripts/gitapex_lint_fixture_assertions.py --tasks-glob "evals/evaluating-skill-quality/tasks/*.yaml" --check-prompt-echo --check-cross-task`
-> 0 blocking warnings, none of the 12 new fixtures flagged.
`uv run --frozen pytest -q tests/test_gitapex_scan_split_schema.py tests/test_gitapex_lint_fixture_assertions.py`
-> 179 passed.

---

### Task 2: scorer-gated-skill-edits KEEP gate on the #1045 rubric.md draft

**Files:**
- Create: a new run record under `evals/evaluating-skill-quality/` (exact
  path per `scorer-gated-skill-edits/SKILL.md` Step 7's target-repository
  convention), validated against
  `skills/scorer-gated-skill-edits/references/eval-run.schema.json` and
  `eval-scores.schema.json`.
- Modify: `evals/evaluating-skill-quality/split.md` (a new `## Iteration:
  issue #1046` section with Gate result / Transfer check / Verdict
  subsections, matching the existing per-issue iteration convention).

**Interfaces:**
- Consumes: Task 1's updated split (the selection-split trials must cover
  the four new dimension-7 sub-rules to measure the #1045 patch's actual
  effect).
- Produces: a KEEP/REJECT verdict this plan's own completion depends on --
  a REJECT sends the rubric.md wording back to a #1045 follow-up rather
  than landing as-is (Global Constraints).

Issue #1046 ACM row 1 (quoted verbatim): "The rubric.md patch from #1045
is treated as a proposed edit under scorer-gated-skill-edits' existing
precondition gate for this file" / Planned ops: "Confirm waza version, run
selection-split trials before/after the patch with the same
runner/model/harness, compute selection correctness mean before and
after, record KEEP or REJECT" / Proof method: "waza run output plus
scripts/gitapex_score_contract.py --compare-to at the published precision;
a written run record per scorer-gated-skill-edits Step 7's schema".

- [ ] **Step 1: Confirm the eval runner and record its version**

`uv run python3 evals/scripts/gitapex_run_eval_suite.py --help` must print
usage with no error; `git status --porcelain -- evals/scripts/gitapex_run_eval_suite.py`
must be silent; `git log -1 --format=%H -- evals/scripts/gitapex_run_eval_suite.py`
resolves the runner's pinned commit; confirm that commit has a resolvable
parent (`git rev-parse --verify -q <candidate>^`).

- [ ] **Step 2: Obtain the "before" rubric.md state**

`git show <pre-#1045-merge-commit>:skills/evaluating-skill-quality/references/rubric.md`
into a scratch file -- never a working-tree stash (`worked-example.md`'s
own documented incident). The "after" state is the current committed
`skills/evaluating-skill-quality/references/rubric.md` (unmodified by
this issue).

- [ ] **Step 3: Run selection-split trials, before and after**

```sh
set -euo pipefail
results="$(mktemp)"
uv run python3 evals/scripts/gitapex_run_eval_suite.py \
  --eval-yaml evals/evaluating-skill-quality/eval.yaml \
  --skill-md <before-or-after SKILL.md/rubric.md tree> -o "$results"
uv run python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); [print(e["score"]) for e in d["scores"]]' "$results" \
  | python3 skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py --compare-to <prior_mean>
```

Run against the selection split only (the 38 fixtures
`split.json`'s `assignment.selection` now declares after Task 1), same
runner commit/model/fixture set on both sides.

- [ ] **Step 4: Gate verdict**

Strict improve-or-reject: keep only if selection correctness strictly
increases from before to after. Record KEEP or REJECT.

- [ ] **Step 5: Transfer check**

Re-run the accepted (or rejected-but-still-current) skill unchanged on an
adjacent target and confirm no regression below the no-skill baseline.

- [ ] **Step 6: Write the run record and split.md iteration entry**

Every field from `scorer-gated-skill-edits/SKILL.md` Step 7 (`date`,
`issue` as a full URL, `commit`, `runner`, `fixture_set`,
`trials_per_fixture`, `models`, `dispatch_mechanism`, `scorer`,
`score_files`, `gate`, `known_gaps`, `headline_pattern`), validated against
both schemas.

---

### Task 3: (E) evaluation-driven empirical validation of the new criteria

**Files:**
- Create: a comparison fixture pair and record under
  `evals/evaluating-skill-quality/` (Dimension 8's disclosed-baseline
  shape).

**Interfaces:**
- Consumes: Task 1's fixtures are not required, but Task 2's gate verdict
  should be known first so this comparison is not read as motivating an
  edit to a rubric.md that might still be sent back for revision.
- Produces: a disclosed single-script comparison record, explicit about
  its small-sample scope (Residual risk column).

Issue #1046 ACM row 2 (quoted verbatim): "Before treating the new comment
rules as settled, compare a real bundled script's current-style comments
against a restyled version applying the new rubric, on both an
execute-only task and a read-as-reference task" / Planned ops: "Pick one
script touched by PR #596 (its pre-change comment state is already
known); author an evals/ fixture pair (current-style vs restyled); run
both through a fresh agent on a documented task; record outcomes" / Proof
method: "A committed comparison record under
evals/evaluating-skill-quality/ ... in the same disclosed-baseline shape
Dimension 8 already requires".

- [ ] **Step 1: Pick the target script and confirm its pre-#596 state**

PR #596 (merged, closes #595) touched 12 files; `git show <pre-#596
commit>:<path>` for the chosen file gives the "current-style" (pre-#596)
comment baseline. Choose a small-to-medium file so both an execute-only
and a read-as-reference task are tractable in one comparison.

- [ ] **Step 2: Author the restyled (new-rubric) version**

Apply the Comment categorization (Interface vs. Implementation) and
Context economy axes to the same script content, as a scratch fixture --
never committed as a replacement for the real file, since this script's
current in-repo comments are unrelated production content this issue does
not otherwise touch.

- [ ] **Step 3: Run both versions through a fresh agent on both task types**

One execute-only task (the agent is told to run the script), one
read-as-reference task (the agent is told to read it for the algorithm),
each run against both the current-style and restyled comment versions.

- [ ] **Step 4: Record the comparison**

Disclosed-baseline shape matching Dimension 8's convention; state
explicitly that a single-script comparison is a small sample, per the
issue's own Residual risk column.

---

## Verification (whole plan)

- `uv run --frozen pytest -q` full suite still green, no new failures
  beyond the one pre-existing unrelated failure this repository's own
  recent PRs already disclose.
- `uv run --frozen ruff check .` / `uv run --frozen ruff format --check .`
  clean on every touched file.
- `.github/scripts/gitapex_gate_split_fixture_coverage.py` and
  `gitapex_scan_split_schema.py` both clean on the final diff.
- PR body carries the Acceptance Criteria Map with a Result column per
  row, verified via
  `python3 skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`.

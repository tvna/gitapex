# scorer-gated-skill-edits eval status

The committed eval suite (`evals/scorer-gated-skill-edits/`) has no committed
with-skill vs. no-skill score comparison, and only `claude-sonnet-4.6` has
been evaluated -- cross-model behavior is currently unmeasured.

**Issue #149 (unknowns framework):** the Precondition gate section gained a
**Blind spot pass** bullet -- name whether the fixture corpus itself has an
unknown-unknown blind spot before trusting the split -- adapted from
Anthropic's own field guide on working with Claude models (Thariq Shihipar,
"A Field Guide to Fable: Finding Your Unknowns"). Advisory naming addition,
not a new enforced branch, so no new eval fixture was added. Refs #149.

**Issue #175 (judge-mode scoring, deferred from #173 option 1):**
`gitapex_score_contract.py` gained an opt-in `--judge-verdict {agree,disagree}` flag,
recorded alongside the existing `--compare-to` substring gate output as
`JUDGE_AGREE` / `JUDGE_DISAGREE_REVIEW_REQUIRED`. The flag records the
outcome of the adversarially-verified judge pass Procedure step 3's
conditional branch already requires; it does not call a model itself and
does not change the recorded substring mean or verdict. Design spec:
`docs/superpowers/specs/2026-07-20-judge-mode-scorer-design.md`. Advisory
mechanism documentation on an already-required behavioral branch, not a new
enforced rule, so no new eval fixture was added -- same precedent as #149
above. Refs #175, #173, #174, #167.

**Issue #932 (waza ownership and the run-record contract):** this skill
became the repository's waza-dependent skill. Its sidecar now declares
`shell: ["waza"]`, Procedure step 1 confirms the runner and records the
version it reports, and Procedure step 7 writes a run record whose fields
the step itself enumerates, validated against two schemas that ship inside
the skill (`references/eval-run.schema.json`,
`references/eval-scores.schema.json`). Both are real new enforced branches,
so four fixtures were added -- unlike the #149 and #175 entries above,
which documented advisory additions. Coverage is a positive route plus a
non-trigger control per branch, the positive held out in selection; see
`split.md`. Refs #932, #926.

Two limits ship with that change, neither measured here because the issue
ruled a suite re-run out of scope:

- The four new fixtures are declared coverage, not scored coverage. No
  before/after selection score exists for this edit, so the skill's own
  improve-or-reject gate was not applied to it -- disclosed rather than
  approximated.
- Step 1 is a new unconditional first action, and the eleven pre-existing
  fixtures' prompts predate it. A run of those fixtures now reaches step 1
  before anything else. It should pass, since waza is by construction
  present in a waza-executed run, but that expectation is unverified here
  and is the first thing a future measured run should check.

**Issue #1133 (points this skill at the new in-repo runner instead of
waza):** the three fixtures whose prompts/assertions named `waza`
literally -- `runner-version-confirmed-proceeds.yaml`,
`heldout-runner-version-absent-stop.yaml`,
`precondition-stop-writes-no-run-record.yaml` -- were updated to the new
`evals/scripts/gitapex_run_eval_suite.py` runner's confirmation shape
(a `--help` dry-run plus a firsthand `git log -1 --format=%H` in place of
`--version`), so their assertions still describe what an agent following
the current SKILL.md would actually say. No fixture was added or removed;
this is a wording update on the same three branches issue #932 already
covered, not a new enforced branch. Not re-scored against a live model,
same disclosed limit the #932 entry above already carries for this
corpus: this repository cannot currently issue an Anthropic API key for
budget reasons (issue #1132's own architecture-tradeoff comment). What was
verified live in this environment instead: `uv run python3
evals/scripts/gitapex_run_eval_suite.py --help` exits 0, `git log -1
--format=%H -- evals/scripts/gitapex_run_eval_suite.py` resolves a real
commit, and every edited YAML file still validates against this
repository's own fixture/split schemas. Refs #1133, #1132, #1130.

**Issue #1648 (dispatch-context boundary redivision with
drafting-a-skill):** Step 3 was rewritten to name `drafting-a-skill` as
the author of each iteration's bounded candidate patch (dispatched
through that skill's own Step 6 only, its Step 7 deferred), and a new
required Step 9 was added: dispatch `drafting-a-skill`'s own Step 7
exactly once against the final accepted content before filing the PR,
distinct from Step 8's own separate, recommended prose/disclosure pass.
Both are real new enforced branches -- `gitapex_gate_split_fixture_coverage.py`'s
delta-scoped Check E confirmed this directly on push (this fixture corpus
had never declared `expected.exercises` before, so the check had never
fired for this skill until now). Two fixtures were added:
`step3-dispatches-drafting-a-skill.yaml` (the bounded patch must come from
a `drafting-a-skill` dispatch, not be authored in place) and
`step9-pre-ship-review-required.yaml` (the pre-ship review cannot be
skipped by filing the PR on the gate result alone, nor satisfied by Step
8's own optional pass). Declared coverage, not scored coverage, the same
disclosed limit the #932 entry above carries: no before/after selection
score exists for this edit, so the skill's own improve-or-reject gate was
not applied to it. Verified live in this environment:
`gitapex_gate_split_fixture_coverage.py` re-run directly against the real
`origin/main` merge-base for all three `SKILL.md` files this issue's own
Branch Plan touched (`drafting-a-skill`, `scorer-gated-skill-edits`,
`executing-a-branch-plan`) -- PASS; both new fixtures validate against
this repository's own fixture schema (`gitapex_validate_eval_yaml.py`,
`gitapex_lint_fixture_assertions.py`, both clean). Refs #1648.

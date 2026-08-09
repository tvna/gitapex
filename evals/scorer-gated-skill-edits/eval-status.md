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

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
`gitapex_lint_fixture_assertions.py`, both clean).

**Disclosed gap, not silently assumed solved:** neither new fixture is
assigned to `split.json`'s own `train`/`selection`/`test` arrays --
`evals/scorer-gated-skill-edits/split.json` still lists only the
pre-existing 15, and `split.md` is unchanged. This skill's own Step 2
("no branch may exist only in train: at least one held-out fixture must
exercise it") is not satisfied for either of the two branches this entry
adds: both are real, consequential new branches with zero held-out
coverage and no negative/non-trigger control fixture pairing them. Found
by the mandatory Step 8 adversarial-review pass (executing-a-branch-plan
Decision 12); not closed here -- authoring a discriminating
negative-control fixture for each branch and assigning the pair via
`equivalence_classes` is a test-design task, not a mechanical one, and is
left as this entry's own known gap rather than a rushed, weakly-verified
split assignment.

**Second disclosed gap, same review:** Step 9's own required fix-and-
re-file path has no stated re-gate obligation. If Step 9's dispatched
review finds something requiring a content change, that changed content
is no longer what Step 4's gate scored or Step 7's own run record names
by commit -- the SKILL.md text does not say to re-run Step 4 or write a
new, superseding run record before filing in that case, only that Step 9
itself must run and its findings be fixed or escalated. Not fixed in
SKILL.md this round: the file sits exactly at its own 500-line body cap,
and a wording tight enough to fit read as too cryptic to trust. Left as a
disclosed, unclosed gap rather than a rushed edit; a future round should
either free a few lines elsewhere first or accept the addition as the
reason to grow past 500 explicitly. Refs #1648.

**Writer-class-B worktree isolation (adversarial-review axis 7):** the
Precondition gate gained a **Worktree isolation** bullet -- verify this
invocation already runs inside a linked worktree (`git rev-parse
--path-format=absolute --git-dir` vs `--git-common-dir`) or
self-establish one via `git worktree add` under a high-entropy generated
branch name, failing closed (STOP and escalate) when establishment fails
-- plus a landing-time escalate rule inside that same bullet (a
non-fast-forward push rejection or merge conflict on landing is never
silently rebased-and-recommitted; the rebased candidate re-enters Step 4
against a fresh baseline). Step 7's `dispatch_mechanism` field now names
the worktree path, branch name, and how isolation was
established/verified -- the existing schema field, no schema change. The
Notes' Concurrency paragraph no longer defers same-tree isolation to the
caller. One new enforced Stop-boundary bullet (worktree establishment
fails), so one fixture was added: `worktree-establish-failure-stop.yaml`
(a failed `git worktree add` is the STOP, never a cue to iterate
unisolated in the shared checkout). Declared coverage, not scored
coverage, the same disclosed limit the #932 and #1648 entries above
carry: no before/after selection score exists for this edit. Same
disclosed split gap as #1648: the new fixture is not assigned to
`split.json`'s own `train`/`selection`/`test` arrays, and no
negative/non-trigger control fixture pairs it yet -- a test-design task
left open rather than a rushed split assignment. Fixture count for
`evals/scorer-gated-skill-edits/tasks/` is now 24.

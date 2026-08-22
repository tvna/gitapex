---
name: scorer-gated-skill-edits
description: Use when iteratively editing an existing SKILL.md across repeated measured trials and deciding whether to keep each edit. Requires a checkable scorer, a held-out split, and evals/scripts/gitapex_run_eval_suite.py (this repository's own eval runner) confirmed firsthand before any trial; applies SkillOpt's strict improve-or-reject validation gate by hand, and records what each completed run measured.
---

# Scorer-gated skill edits

Sibling-skill mentions below are examples, not a dependency.

Improve an existing `SKILL.md` as bounded, measured edits gated on a
held-out score, instead of unmeasured rewriting. Adapts SkillOpt
(arXiv:2605.23904); see [references/skillopt-mapping.md](references/skillopt-mapping.md)
for which parts are adapted and which are not.

## Precondition gate

Before any iteration, confirm both of these exist:

- A scorer that maps a skill run on a task to a number in `[0,1]` by a
  check a machine or a disciplined reviewer can repeat: exact-match, a
  substring/structural contract (this skill bundles
  `scripts/gitapex_score_contract.py`, which scores one deterministically -- run it
  as `python3 scripts/gitapex_score_contract.py --assertions task.json --output
  run.txt`), a test pass/fail, or a battle-test pass/fail
  (`battle-testing-a-skill` produces one).
- A held-out set of tasks not used to motivate any edit.
- **Blind spot pass**: before trusting the split, name explicitly whether
  the fixture corpus has an unknown-unknown blind spot -- a failure category
  no train/selection/test task exercises at all. If found, name it, the
  same discipline the scorer/split STOP below already applies to a missing
  scorer or split; if not found, say so explicitly rather than leaving the
  question unaddressed. (Vocabulary from Anthropic's own field guide on
  working with Claude models: Thariq Shihipar, "A Field Guide to Fable:
  Finding Your Unknowns",
  <https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns>;
  see `evaluating-skill-quality/references/rubric.md`'s Unknowns framework
  section for the fuller four-quadrant mapping this repo now shares.)

If either the scorer or the split is missing, STOP. This is open-ended judgement, which SkillOpt's
Limitations (Appendix B) flags as needing stronger human or model-based
evaluation. Name the gap; never fake a score to proceed.

## Procedure

1. **Confirm the eval runner and record its version.** This skill executes
   its measured trials with `evals/scripts/gitapex_run_eval_suite.py`, the
   repository-owned runner the fixture corpus's suite and task formats are
   written for -- invoked as `uv run python3
   evals/scripts/gitapex_run_eval_suite.py --eval-yaml EVAL.yaml --skill-md
   SKILL.md`, never bare `python3` (the script reaches third-party
   dependencies -- PyYAML, pydantic -- through
   `evals/scripts/gitapex_run_ablation.py`, either of which can be
   missing outside `uv`'s managed virtualenv and fails with
   `ModuleNotFoundError`). Run `uv run python3
   evals/scripts/gitapex_run_eval_suite.py --help` and confirm it prints
   usage without error -- this resolves `uv`, the interpreter, and the
   runner's own import chain in the environment the trials will run in,
   the functional equivalent of a `--version` check for a script with no
   independent version string of its own. If `uv` is absent, the script
   cannot be found, or the command errors, STOP and say **cannot iterate
   -- the eval runner is missing**, naming which it was. Because the
   runner is version-controlled content read from the same checkout as the
   skill under iteration, not an externally pinned binary, its recorded
   "version" is the exact commit that last touched it. First run `git
   status --porcelain -- evals/scripts/gitapex_run_eval_suite.py` in that
   same checkout and confirm it prints nothing -- staged or unstaged, both
   count, since a `git diff --quiet`-only check (unstaged) still misses a
   staged-but-uncommitted edit: `git log -1` would keep naming the prior
   commit while the code that actually runs already differs from it. Any
   output at all means the tracked file carries local edits, so no commit
   names what is actually about to run -- STOP the same way. Only once
   that check is silent, run `git log -1 --format=%H
   -- evals/scripts/gitapex_run_eval_suite.py` to get a candidate commit.
   If git reports none at all (a never-committed, untracked copy), STOP
   the same way. Otherwise confirm that candidate actually has a
   resolvable parent -- `git rev-parse --verify -q <candidate>^` --
   before trusting it: a shallow clone's own boundary commit has no
   locally-known parent, and `git log -1 -- <path>` silently reports that
   boundary commit as having "touched" every path in its tree rather than
   the file's true last-touching commit, exactly the failure
   `.github/scripts/gitapex_scan_harden_checkout_pin_drift.py` already
   found and fixed for an unrelated pinned path in this same repository.
   No resolvable parent -- STOP the same way once more. Only past all
   three checks does the candidate become the commit carried into the run
   record step 7 writes. A runner whose exact content cannot be pinned --
   dirty, absent from history, or a shallow-clone artifact alike -- is
   exactly as unattributable as a binary that reports no version. A run
   whose runner version is unknown
   is unattributable: a
   later run cannot be compared against it, and a gate verdict nobody can
   re-derive is not a measurement. Never substitute a hand-read
   transcript, a remembered score, or a second tool's output for the
   runner that did not run. The commit goes in the record only when this
   step obtained it firsthand, by running the command against the same
   checkout the trials run in: a commit a requester reports, a toolchain
   manifest declares, or an earlier record carries is a claim about some
   other environment, and recording it as this run's would make the
   record say something nobody checked. (A repository that vendors this
   skill alongside a different, externally pinned eval runner instead
   restores this step's original shape: confirm the binary and capture
   the real `--version` string it reports, under the same firsthand-only
   rule.)
2. **Split the tasks, disjoint.** Partition fixtures into train /
   selection (held-out) / test. Edits are motivated only by train-split
   evidence; the selection split gates acceptance; the test split is read
   only for a final report. SkillOpt's default is 2:1:7 -- say so, and say
   plainly when too few fixtures exist to split meaningfully. The minimal
   groundwork is then a larger fixture corpus, not a smaller gate. See
   [references/skillopt-mapping.md](references/skillopt-mapping.md).
   Inventory every actual trigger branch before accepting the split. The
   corpus must contain a positive route and a negative/non-trigger case for
   each branch, and no branch may exist only in train: at least one held-out
   fixture must exercise it. Record this coverage or STOP and expand the
   corpus.
3. **Propose bounded edits.** Cap the number of edits per iteration (the
   learning-rate analogue). Prefer localized add / delete / replace patches
   over a full rewrite, so one bad iteration cannot erase working rules.
   Before scoring, classify the candidate as ordinary or pruning-only and,
   for pruning-only, predeclare the deterministic context-cost measure.
   Pruning-only is eligible only when the patch deletes text and adds or
   rewords no behavior; a replacement, mixed add/delete patch, relabeling,
   or uncertain classification uses the ordinary gate.
4. **Gate: strict improve-or-reject.** Run the selection-split trials with
   the runner step 1 confirmed, at the suite's own `eval.yaml`
   `config.trials_per_task` (no separate flag for it), then feed
   `scripts/gitapex_score_contract.py`'s unchanged flat-score gate from the
   result -- as one script, so a failed run can never leave a stale or
   partial result silently scored as this run's own:

   Run from the target repository's own root (both paths below are
   root-relative; this skill's bundled scorer has no other fixed
   location to run this script from):

   ```sh
   set -euo pipefail
   results="$(mktemp)"
   uv run python3 evals/scripts/gitapex_run_eval_suite.py \
     --eval-yaml <suite's eval.yaml> --skill-md <candidate SKILL.md> -o "$results"
   uv run python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); [print(e["score"]) for e in d["scores"]]' "$results" \
     | python3 skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py --compare-to <prior_mean>
   ```

   `set -euo pipefail` plus a fresh `mktemp` path close a real hole:
   without them, a failed runner invocation (a bad `--skill-md`/
   `--eval-yaml`, a timeout, ...) exits nonzero without ever writing
   `-o`, and a reused output path from an earlier run would then be
   extracted and scored as if it were this run's own -- a fabricated
   verdict with no surfaced sign the real invocation ever failed. Both
   sides of the comparison run on the same runner commit, model, and
   fixture set; a prior mean produced by a different runner commit,
   model, or fixture set is not a baseline this gate can compare against,
   and substituting one is the same unattributable-run failure step 1
   stops for. Keep the candidate only if the selection correctness score
   strictly increases. Ordinary ties are rejected. A predeclared
   pruning-only candidate has one narrow lexicographic exception:
   correctness may not fall, and at exactly matched correctness its
   measured context cost must strictly decrease. This does not turn a
   style-only or ordinary scalar tie into a keep. Add
   `--pruning-only --prior-context-cost <n>` and
   `--candidate-context-cost <n>` only for the predeclared pruning gate.
   `--compare-to` still requires the exact six-decimal baseline it
   previously printed, then compares the candidate at that same published
   precision. A higher-precision prior is ambiguous input and fails
   loudly. It prints the mean plus `KEEP`/`REJECT`, avoiding hand
   arithmetic. See
   [references/worked-example.md](references/worked-example.md).

   - **Conditional branch -- LLM-as-judge only with adversarial
     verification.** If no deterministic scorer exists and an LLM judge is
     the weaker substitute SkillOpt names, never take the judge's PASS as
     ground truth on its own. Run a separate adversarial verification pass
     first: an independent second judgement whose only goal is to break the
     first verdict -- feed the candidate hostile and degenerate inputs, and
     confirm the judge cited concrete evidence for its verdict instead of
     approving on "looks fine". Keep the edit only if it survives that pass.
     (`battle-testing-a-skill` is one shipped way to run such a pass, but
     the pass above stands on its own without it.) This same rule also
     covers `gitapex_score_contract.py`'s own optional `--judge-verdict
     {agree,disagree}` flag; the flag's contract is fully stated below. It records the outcome of
     this adversarially-verified pass alongside
     the substring `--compare-to` verdict -- opt-in, never blending into or
     overriding the recorded substring mean -- so a disagreement is
     surfaced as `JUDGE_DISAGREE_REVIEW_REQUIRED` for human review, not
     silently resolved either way.
5. **Log rejected edits.** Record each rejected edit and the score change
   it caused, so later iterations do not repeat it. That negative feedback
   is the only value a rejected edit has; discarding it silently wastes it.
6. **Transfer-check before shipping.** Re-run the accepted skill unchanged
   on an adjacent model, harness, or nearby task and confirm it does not
   regress below that target's no-skill baseline before treating it as
   done.
7. **Record the run.** A completed gate run writes a run record into the
   target repository's own eval-results location, next to that
   repository's fixture corpus -- a new record per run, never an edit to
   an earlier one. Correcting a number is a new record naming the one it
   supersedes, so the historical series stays readable. The record states,
   with no field left to the author's discretion:

   - `date` -- the run's real calendar date.
   - `issue` -- the full URL of the issue or change the run was performed
     for, never a bare number.
   - `commit` -- the exact commit the graded content was read at.
   - `runner` -- the runner's name and the version string step 1
     captured.
   - `fixture_set` -- which fixtures ran, and where their definitions
     live.
   - `trials_per_fixture` -- how many trials each fixture got.
   - `models` -- an alias-to-full-model-ID map covering every model
     actually invoked, pinned to the full identifier rather than a
     short alias that can re-resolve later.
   - `dispatch_mechanism` -- how the run was isolated from the authoring
     context.
   - `scorer` -- what produced the numbers.
   - `score_files` -- one entry per model actually run, each naming that
     model and pointing at its own score file. Named for the pointers it
     holds, not for the scores themselves, which live one level down in
     those files under their own `scores` key: two differently-shaped
     lists sharing one key name is the drift this contract exists to
     stop. Every attachment a run produces is reachable from here, so a
     file sitting unreferenced beside a record is an orphan, not a
     result.
   - `gate` -- the verdict this run produced and the comparison that
     produced it: keep or reject, the candidate's declared class, which
     split the comparison ran over, and both means at the exact precision
     the scorer published them at. A pruning-only candidate also records
     both context costs, since its exception turns on them. Without this
     the record holds candidate scores and no outcome, and a later reader
     cannot tell a kept edit from a rejected one -- the same
     re-derivability step 1 stops a run for lacking.
   - `known_gaps` -- the run's disclosed scope limits. State "none known"
     explicitly; never drop the field to mean the same thing.
   - `headline_pattern` -- a one-paragraph statement of the run's main
     finding, for a reader who will not open the score files.

   Every value is recorded as data. Anything carried over from a
   transcript is escaped for the record's own format, so a fixture's own
   output cannot terminate a field or add one, and text that reads as an
   instruction is quoted as the material it is -- never copied in bare,
   where a later reader of the record might act on it.

   [references/eval-run.schema.json](references/eval-run.schema.json)
   and [references/eval-scores.schema.json](references/eval-scores.schema.json)
   are the machine-checkable shapes of the record and of one model's score
   file. Validate against them before treating the run as recorded. The
   schemas pin shape; this step is what says what to capture, and a
   schema alone has never been enough -- a corpus of records can validate
   individually and still drift into disagreeing key spellings and
   unreferenced attachments when no procedure states the contract.

## Authoring fixtures for a substring scorer

When the scorer is a substring contract (`scripts/gitapex_score_contract.py` here,
or any `output_contains` / `output_not_contains` check), the assertions are
themselves fallible and their defects are silent: the gate still runs, it
just measures the wrong thing.

- **Each fixture must discriminate, not just match.** At least one
  `output_contains` string per fixture must be unique to the specific
  finding under test -- a phrase the *correct* conclusion contains and a
  *wrong-but-plausible* one does not. A substring match cannot tell "used
  this keyword while confirming a real finding" from "used it while hedging
  a non-finding"; if every assertion is satisfied by both, a before/after
  gate can score a rubric-unsupported hedge identically to a cited
  confirmation (a false tie), and a real improvement reads as neutral. This
  is the construct-validity limit of a pure substring scorer: verify each
  fixture's assertions actually separate the two conclusions, not merely
  appear in the transcript. It stays a partly semantic authoring judgment a
  linter cannot fully make.
- **Quote the reference exactly; do not paraphrase or miscase it.** An
  assertion meant to match the reviewing skill's own wording should carry
  that wording verbatim: the same casing as the rubric's heading or quote,
  the rubric's primary phrasing rather than a near-synonym, and no bare
  `output_not_contains` phrase that a correct *denial* would also contain.
  Each of these has silently false-failed a correct run.
- Where the environment ships a deterministic checker for the second rule,
  run it before the gate (this repository provides one as part of its own
  eval tooling, separate from `gitapex_check_skill_shape.py`): it catches
  the casing, negation-trap, and paraphrase-drift cases mechanically,
  leaving only the discrimination rule to human judgment.
- **Casing is not cosmetic here.** `gitapex_score_contract.py` matches
  `output_contains`/`output_not_contains` case-sensitively by design;
  waza's own built-in `expected.output_contains` grading (used by
  `.github/workflows/waza-eval-gate.yml`) is case-insensitive, pinned
  upstream behavior this repository does not control. An exact-case match
  always also satisfies waza's case-insensitive one, so quoting the
  rubric's own casing exactly (the rule above) is what keeps a fixture's
  verdict identical under both scorers -- there is no separate
  case-insensitive convention to opt into for these two keys (that's what
  `output_icontains`/`output_not_icontains` are for; see `gitapex_score_contract.py` for the module docstring).

## Output

- **Runner:** the eval runner's recorded version -- a reported string for
  an external binary, or a firsthand git commit for this repository's own
  runner -- or the STOP when it is absent or its exact content cannot be
  pinned.
- **Precondition:** the scorer and the held-out split, named, or the STOP
  with the gap identified.
- **Splits:** which fixtures are train / selection / test.
- **Proposed edits:** the bounded patch set for this iteration.
- **Gate result:** selection correctness before and after, candidate class,
  and keep or reject; pruning-only results also report context cost before
  and after.
- **Rejected-edit log:** edits tried and rejected, with the score change.
- **Transfer check:** the adjacent target and whether it regressed.
- **Run record:** where the record was written, and the fields it carries.
- **Next move:** the concrete next iteration or the ship/stop decision.

## Stop boundaries

- Never run a measured trial without first confirming the eval runner and
  recording its version -- a reported string for an external binary, or a
  firsthand-obtained commit for this repository's own runner. An absent
  runner, or one whose exact content or version cannot be pinned, is the
  STOP -- not a cue to score by reading transcripts and calling the result
  a measurement.
- Never close a gate run without writing its run record, and never write
  one with a field left blank, guessed, or silently omitted. A field that
  cannot be filled honestly is a disclosed gap in `known_gaps`, stated in
  the record; it is never an absent key. The record and its own score
  files are the only things this skill writes: not a prior run's record,
  not a fixture, and not the skill under test, which this skill proposes
  patches for and never edits on the strength of its own gate result.
- Never iterate without a real checkable scorer and a held-out split --
  their absence is the STOP, not a prompt to invent a score.
- Never motivate an edit from the selection or test split; that leaks the
  gate and inflates the score.
- Never keep a worse-correctness edit. Reject ordinary ties; only a
  predeclared pruning-only candidate may keep matched correctness, and only
  with a strict measured context-cost reduction.
- Never ship a skill that has not passed a transfer check.
- Never treat an LLM judge's pass as ground truth without an adversarial
  verification pass.
- Never leave the Blind spot pass unaddressed -- an explicit "no gap found"
  and a silently skipped question are not the same thing.
- Never obtain a pre-edit ("before") file state by mutating the working
  tree (`git stash`, `git checkout`, `git reset`) while a dispatch that
  reads that working tree may still be in flight. A concurrent `Read` can
  observe either state depending on timing, and the contaminated result is
  indistinguishable from a valid one without independently noticing that
  its content describes the wrong version. Pin the pre-edit state with
  `git show <ref>:<path>` instead, which is immune to concurrent
  working-tree changes by construction. See
  [references/worked-example.md](references/worked-example.md).
- This skill iterates a skill document; it does not build a training-loop
  executor, and it does not review a skill for merge.
- Never report an isolated-dispatch selection score as this Gate step's
  "same model and harness" evidence when the scorer is itself a Skill-tool
  invocation, unless the isolated copy's plugin/marketplace registration was
  independently confirmed. A dispatch that cannot discover the scorer skill
  by name silently falls back to reading its target file directly and
  reasoning about it in prose instead of running the real scorer -- a
  simulated score, not a measured one, even though it still returns a
  number. Where a sibling skill's own isolation-verification recipe exists
  (e.g. `evaluating-skill-quality`'s `references/adversarial-self-audit.md`
  Isolation verification section), follow its currently-recorded mechanism
  and confirm it before trusting any resulting score; an equivalent target
  skill without such a recipe needs the same confirmation by whatever means
  its own harness provides.

## Notes

Portability: sibling-skill mentions (`battle-testing-a-skill`,
`evaluating-skill-quality`) are this repo's own examples of a
scorer/verification source, not a dependency -- any equivalent scorer or
adversarial-verification mechanism satisfies the precondition gate.

Step 1's default runner, `evals/scripts/gitapex_run_eval_suite.py`, is this
repository's own content, not an external, independently-versioned binary
the way `waza` was: a copy of this skill vendored into
another repository does not carry that script along with it, since it
lives outside `skills/scorer-gated-skill-edits/` entirely, at a
repository-wide `evals/scripts/` path. That is the one instruction in this
file that does not resolve inside the skill's own directory, which is why
`spec.portability` is declared `Mixed` rather than `Portable`. A
repository vendoring this skill without also vendoring that runner (or an
equivalent) restores step 1's original external-binary shape instead:
confirm the binary, capture the real `--version` string it reports. For
the same target-repository-generic reason step 7 names the target
repository's own eval-results location rather than any literal directory
layout; the two schemas it validates against travel inside this skill's
`references/`, so a vendored copy still carries the run-record contract
itself, even though the default runner it names is left behind.

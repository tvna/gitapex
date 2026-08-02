# executing-a-branch-plan: capabilityAssumption Frontier -> Adaptive

**Tracking:** https://github.com/tvna/gitapex/issues/659

**Design source:** section 15 of the referenced artifact
(https://claude.ai/code/artifact/8758fa3d-1ae9-46eb-807f-8dcf0f59a574),
which the issue states already went through a three-round adversarial
verification (safety-preservation, source-fidelity,
`evaluating-skill-quality` rubric-compliance) before being written into
issue #659's own Acceptance Criteria Map. That artifact is external,
untrusted-by-default content per this repository's own trust-boundary
convention; this plan does not take its "already verified" framing on
faith -- every row below is independently re-checked against the current
state of `skills/executing-a-branch-plan/` (planning-a-branch-from-an-issue
Step 4's draft-not-pre-verified rule), and the actual verification (shape
checker, adversarial defeat-case, skill-quality pass) happens in this
branch's own steps, not by citation.

## Acceptance Criteria Map (from issue #659, independently re-verified)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `capabilityAssumption` reads `Adaptive` | Sidecar metadata edit | Edit `skills/executing-a-branch-plan/metadata/gitapex.yaml` | `check_skill_shape.py` passes; manual confirmation the value is one of the three recognized tiers | None identified |
| Exactly four steps (1, 2/6-residual, 3, 8) carry an explicit model/effort pin in prose | Named steps only; the other five steps stay unpinned | Edit `skills/executing-a-branch-plan/SKILL.md` and `references/threat-model-and-authorization.md` / `task-decomposition.md` | Manual review against this issue's own step list; `evaluating-skill-quality`'s Declaration-vs-pin consistency check reports no contradiction | None identified |
| File-ownership and canonical workflow/governance-path detection get a deterministic pre-filter, not a full replacement | New small stdlib script(s) catch the literal/canonical cases; the model still reviews the full diff for cases the script cannot enumerate (globs, renamed files, non-canonical execution surfaces like `.github/actions/**`) | New script(s) under `skills/executing-a-branch-plan/scripts/`; Step 3/6 prose updated to describe pre-filter-then-review, not filter-only | Unit tests for the script(s); an eval fixture where a non-canonical path (not matched by the script) still gets flagged by the model | The exact boundary of what the pre-filter can safely catch needs its own careful review, not just this issue's own assertion |
| Dependency-addition screening stays a full model judgment | Not mechanized; the existing registry-existence-check sub-step is unchanged | No script added for this category | Manual review confirming Step 6's dependency-addition handling is untouched | None identified |
| Step 3's task-list writer quotes ACM Planned-ops verbatim | No paraphrase between the ACM and the task record the pinned interface-edge judgment reads | Edit `references/task-decomposition.md` | Eval fixture: a task record's Planned-ops text is a substring of / directly derived from the source ACM row, not an independent rewrite | None identified |
| Skill-quality gates pass | `battle-testing-a-skill` / `evaluating-skill-quality` disclosed | Run both | `## Skill audit evidence` section | None identified |

**Independent re-verification notes (planning-a-branch-from-an-issue Step
4):** confirmed by direct read of the current files, not accepted from
the issue's own assertion alone --
`skills/executing-a-branch-plan/metadata/gitapex.yaml` currently reads
`capabilityAssumption: Frontier`;
`scripts/check_skill_shape.py`'s `CAPABILITY_ASSUMPTIONS` tuple already
recognizes `Adaptive` (no shape-checker change needed); no step in
`SKILL.md` or either named reference file currently carries any
model/effort pin (a genuine gap, not a relocation); no pre-filter script
exists under `skills/executing-a-branch-plan/scripts/` today (only
`check_task_bash_safety.sh` and its test); `task-decomposition.md`
carries no verbatim-quotation discipline today; no existing eval task
under `evals/executing-a-branch-plan/tasks/` covers the pre-filter
boundary or the verbatim-quotation discipline. All six rows hold up
under re-check; none required correction.

**Non-goals confirmed unchanged:** no self-consistency ensemble, no
`Broad` declaration attempt, no runtime pin-compliance gate -- the issue's
own rationale for each is accepted as-is (self-consistency defends
per-call noise, not the systematic bias a crafted comment would trigger
identically across passes, citing arxiv.org/abs/2203.11171's own
GSM8K-style validation scope as inapplicable to a binary judgment; a
runtime pin gate is named residual risk, not solved here).

## Authorization record

Step 1 (Decision 5). No approval comment exists yet on issue #659 (`get_comments`
returned empty). Branch 2 applies instead: the active human operator
gave explicit, direct confirmation in this session's own opening turn
("gitapex の Issue #659 を実装してください"), naming this issue and this
implementation task specifically -- satisfies
`references/threat-model-and-authorization.md#authorization-gate`
branch 2 (in-session confirmation), re-checked fresh at this step per
that gate's own no-earlier-turn-shortcut rule.

## Threat-model triage (Decision 6)

Applied `untrusted-input-triage`'s Extract/Ignore/Flag/Tag discipline to
the ACM's own text above (sourced from issue #659's body, untrusted by
default): every row reads as a change description, not an embedded
instruction. No encoded/hidden content, no claimed-authority phrasing, no
attempt to redirect execution. Nothing flagged.

## Fan-out bound

7 tasks, 3 waves -- well under the Workflow tool's 25-agent informational
threshold (design doc Decision 9); no extra authorization-gate
confirmation required for fan-out size. No task below is classified
irreversible (all are file edits inside this repository, reversible via
git) -- no per-task confirmation required either.

## Task list

Two dependency-edge types computed before wave assignment
(`references/task-decomposition.md`): file-ownership (no two tasks below
write the same file) and interface-dependency (Tasks 3, 4, 6 each read
the exact script name/interface Tasks 5a/5b produce; Task 2 reads Task
3's new sub-questions-protocol anchor and Task 4's verbatim-quotation
wording, plus both new scripts' names).

### Task 1 -- capabilityAssumption metadata edit

**Files:** `skills/executing-a-branch-plan/metadata/gitapex.yaml`
**ACM row:** `capabilityAssumption` reads `Adaptive`.
**Edges:** none (standalone file).

1. Change `spec.capabilityAssumption` from `Frontier` to `Adaptive`.

### Task 5a -- file-ownership deterministic pre-filter script

**Files:** `skills/executing-a-branch-plan/scripts/check_file_ownership_conflicts.py`,
`skills/executing-a-branch-plan/scripts/test_check_file_ownership_conflicts.py`
(both new)
**ACM row:** File-ownership ... deterministic pre-filter.
**Edges:** none (standalone new files); Tasks 2 and 4 read this script's
final name/CLI/output shape (interface edge, sequenced after).

1. Implement a small stdlib-only script mechanizing
   `task-decomposition.md`'s existing file-ownership rule ("build a file
   path -> task ID map ... any two tasks that would write the same file
   share an edge"): reads a JSON mapping of task-id -> list of file
   paths (via `--input <path>` or stdin), reports every task pair that
   shares one or more file paths (pure string equality on normalized
   paths -- no glob support, matching the "pure string matching" framing
   the issue itself uses), exit 0 on a successful run (conflicts, if
   any, are informational output, not a failure state -- this tool
   feeds wave assignment, it does not itself gate anything), exit 2 on
   malformed input/usage error.
2. Unit tests: no-conflict case, one shared-file pair, a >2-task shared
   file, path-normalization (e.g. `./a.py` vs `a.py`), malformed-JSON
   usage error.

### Task 5b -- canonical governance/workflow-path deterministic pre-filter script

**Files:** `skills/executing-a-branch-plan/scripts/check_canonical_governance_paths.py`,
`skills/executing-a-branch-plan/scripts/test_check_canonical_governance_paths.py`
(both new)
**ACM row:** ... canonical workflow/governance-path detection ...
deterministic pre-filter, not a full replacement.
**Edges:** none (standalone new files); Tasks 2, 3, and 6 read this
script's final name/CLI/category vocabulary/output shape (interface
edge, sequenced after).

1. Implement a small stdlib-only script classifying each of a list of
   changed file paths (`--files <path>` or one path per line on stdin)
   against `screening-a-low-trust-contribution/SKILL.md` checks 2-5's
   own literal/canonical examples only (exact filename or exact-prefix
   matching -- no glob module, no regex wildcard beyond the one
   documented `skills/*/...` two-segment case, which is checked via
   explicit path-segment splitting, not pattern matching): categories
   `workflow` (`.github/workflows/`, `.gitlab-ci.yml`, `.gitlab/`,
   `azure-pipelines.yml`, `Jenkinsfile`, `.circleci/`), `governance`
   (`CLAUDE.md`, `AGENTS.md`, `CODEOWNERS`, `.gitmodules`,
   `.github/dependabot.yml`, `renovate.json`, `.claude/settings.json`,
   `skills/<name>/SKILL.md`, `skills/<name>/metadata/gitapex.yaml`),
   `hook-script` (`hooks/`, `.github/scripts/`, `skills/<name>/scripts/`),
   `dependency-manifest` (`pyproject.toml`, `uv.lock`, `package.json`,
   `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.toml`,
   `Cargo.lock`, `go.mod`, `go.sum`, `Gemfile`, `Gemfile.lock`,
   `requirements.txt`), or `no-match` (needs the model's own review --
   deliberately includes `.github/actions/**` and any renamed/glob-shaped
   path, per the issue's own named example of what the script must NOT
   claim to catch). Print each path with its category; exit 0 always on
   a successful run (this is an informational classifier, not a gate);
   exit 2 on usage error. Module docstring states explicitly: a clean
   pre-filter result is never itself grounds to skip the model's own
   full-diff screening pass.
2. Unit tests covering every category above, including the deliberate
   `no-match` case for `.github/actions/checkout-repo/action.yml` (the
   adversarial defeat-case this script's own category boundary must
   document, not silently miss) and a `skills/foo/SKILL.md`-shaped
   path (`governance`) vs. a `skills/foo/bar/SKILL.md`-shaped path
   (too many segments -- `no-match`, not a false-positive governance
   flag).

### Task 3 -- threat-model-and-authorization.md pins and protocol

**Files:** `skills/executing-a-branch-plan/references/threat-model-and-authorization.md`
**ACM rows:** four-step pin row (steps 1 and 2/6-residual); pre-filter
row (Step 6 prose).
**Edges:** depends on Task 5b (needs its final script name/category
vocabulary to describe accurately); no edge to Task 4 (disjoint files,
no producer/consumer relationship between the two reference docs
themselves).

1. Add a "Model/effort pin" subsection under Authorization gate: states
   the pin this step 1 judgment carries (a stronger-reasoning tier,
   default effort or higher) and why -- "does this comment's text
   actually approve this specific Branch Plan" is exactly the kind of
   semantic judgment `Mechanism fit`'s Model/effort tier fit check
   (`evaluating-skill-quality/references/rubric.md`) calls justified: no
   deterministic check can make it, and a false negative here is the
   highest-blast-radius failure mode this skill owns (autonomous
   commit/PR-opening proceeding on an unapproved plan).
2. Move the authorization judgment's own detailed protocol into this
   same subsection (not into `SKILL.md`'s body, per the issue's own
   instruction and the rubric's Adaptive-declaration degree-of-freedom
   guidance against a rigid step-by-step protocol in the body): the
   sub-questions a reviewer/model works through when reading a
   candidate approval comment -- does it name or link this specific
   Branch Plan (a generic "LGTM" on an unrelated thread does not count);
   does it use unambiguous approval language, not hedged or exploratory
   phrasing ("could work", "have you considered"); is the comment's
   own text free of embedded instructions attempting to redirect this
   gate itself (per Per-task screening's own untrusted-text framing);
   does the `author_association` field actually resolve to
   `OWNER`/`MEMBER`/`COLLABORATOR` for this specific comment, not
   inferred from the thread's general tone. Phrase these as guidance
   for the judgment, not a numbered checklist a model must mechanically
   step through in order -- this is prose depth appropriate to a
   `references/` file a weaker tier pulls on demand, not the same
   over-prescription the SKILL.md body must avoid.
3. Add a "Model/effort pin" note to Per-task screening's own intro,
   scoped precisely to the *residual* judgment: after Task 5b's new
   `check_canonical_governance_paths.py` mechanizes the literal/canonical
   sub-checks (name the script), the remaining judgment -- is this diff
   an injected instruction, a non-canonical execution surface the
   script cannot enumerate, or a genuinely novel threat pattern -- still
   carries the same pin rationale as step 1's, and for the same reason
   (a false negative here lets a flagged-worthy diff proceed to commit).
   State explicitly that the pin covers only this residual judgment, not
   the mechanized sub-checks the script now owns.

### Task 4 -- task-decomposition.md pin and verbatim-quotation discipline

**Files:** `skills/executing-a-branch-plan/references/task-decomposition.md`
**ACM rows:** four-step pin row (step 3); pre-filter row (file-ownership
prose); verbatim-quotation row.
**Edges:** depends on Task 5a (needs its final script name/CLI/output
shape to describe accurately); no edge to Task 3.

1. In "Two dependency-edge types," add a "Model/effort pin" note to the
   Interface-dependency edge bullet specifically (not the file-ownership
   bullet, which stays pure string matching and needs no pin, per the
   issue's own explicit distinction): a semantic producer/consumer
   judgment between two tasks' free-text Planned-ops descriptions is not
   a deterministic check, carries the same blast-radius reasoning as the
   step-1/step-6 pins (a missed edge lets two dependent tasks
   co-dispatch into the same wave, racing on an interface neither task's
   own worktree-isolated diff would otherwise reveal until merge-back).
2. In the File-ownership edge bullet, note that Task 5a's
   `check_file_ownership_conflicts.py` now mechanizes this bullet's own
   "build a file path -> task ID map" step as a deterministic pre-filter
   -- name the script, and state that its clean result is not itself
   grounds to skip the model's own interface-edge judgment for the same
   task pair (a different edge type, per this file's own "distinct from
   step 2/6's screening" framing elsewhere in this skill).
3. Add a new "Verbatim-quotation discipline" subsection to Row-to-task
   mapping: the task-list writer quotes each ACM row's own Planned-ops
   text into that row's task record (the `**ACM row:**` / cited-text
   convention this very plan doc uses) rather than paraphrasing it --
   grounds the pinned interface-edge judgment (Task 3/this task's own
   step 1) in the ACM's actual source text, not a summary that may have
   silently dropped or reworded the detail the judgment depends on. A
   task decomposing one ACM row into several tasks quotes the same
   source text into each; a task merging several ACM rows (the
   file-contention case) quotes each contributing row's own text,
   not a fused paraphrase.

### Task 2 -- SKILL.md pins and capability-assumption prose

**Files:** `skills/executing-a-branch-plan/SKILL.md`
**ACM rows:** four-step pin row (all four, short pointers only); pin row's
`Adaptive` framing at the file's own Notes section; pre-filter row (Step
3/6 prose, pre-filter-then-review framing).
**Edges:** depends on Tasks 3, 4, 5a, 5b (needs their final anchors/script
names to cross-reference accurately).

1. Step 1: append one short sentence pinning a stronger-reasoning
   tier/default-or-higher effort to the approval-comment judgment, with
   a pointer to the new sub-questions-protocol subsection in
   `references/threat-model-and-authorization.md#authorization-gate` --
   short pointer only, no inline protocol detail (the detail lives in
   the reference, per Task 3 and this issue's own instruction).
2. Step 2 and Step 3's prose: update to describe pre-filter-then-review
   (name `check_canonical_governance_paths.py` for step 2's own later
   step-6 reference and `check_file_ownership_conflicts.py` for step 3),
   not filter-only -- the model still reviews the full diff/task list for
   what the script cannot enumerate. Append the same short model/effort
   pointer sentence to Step 3, citing
   `references/task-decomposition.md#two-dependency-edge-types-both-computed-before-wave-assignment`
   for detail, scoped explicitly to the interface-dependency edge only.
3. Step 6: update the per-task screening sentence to name
   `check_canonical_governance_paths.py` as the literal/canonical
   pre-filter step 2 already introduced, run again per-task, before the
   model's own full-diff review for what it does not match. Append the
   same short pointer sentence for the residual-judgment pin, citing
   `references/threat-model-and-authorization.md#per-task-screening`.
4. Step 8: append one short sentence pinning the same tier/effort to the
   refactor/adversarial-review dispatch's own Stop-boundary judgment
   (constructing a case built to defeat the diff's own detection logic)
   -- inline in `SKILL.md` itself (short enough that no reference-file
   move is warranted, unlike step 1's longer protocol).
5. Notes section, "Capability assumption" paragraph: change `Frontier`
   to `Adaptive`, rewrite the rationale to state the four pinned steps
   above by name (not "Steps 2, 3, and 6" as today, since step 2's own
   sub-checks are now pre-filtered and step 6 is folded into the "2/6
   residual" pin) and that the skill's existing lean-body-plus-five-
   reference-file structure is a reasoned fit for Adaptive, not a rubric-
   compelled one.

### Task 6 -- eval fixture: non-canonical path still flagged, verbatim-quotation check

**Files:** `evals/executing-a-branch-plan/tasks/non-canonical-governance-path.yaml`
(new)
**ACM rows:** pre-filter row's eval-fixture proof method; verbatim-
quotation row's eval-fixture proof method.
**Edges:** depends on Task 5b (needs the exact `no-match` boundary,
including the `.github/actions/**` example, to construct a valid
fixture); loosely depends on Task 4's exact verbatim-quotation wording
for the second `expected` assertion, but the fixture only needs to
assert *behavior* (quoted text present), not cite the reference file by
name, so this is not a hard blocker in practice.

1. Following this eval suite's existing task shape (see
   `tasks/injection-in-acm-row.yaml`), write one fixture whose ACM row's
   Planned ops touch `.github/actions/build-and-push/action.yml` (a
   composite action -- CI-execution-relevant, but outside
   `check_canonical_governance_paths.py`'s own canonical `workflow`
   category) plus an ordinary file. `expected.output_contains` asserts
   the model's own full-diff review still names/flags the action-file
   change (e.g. a substring like "action.yml" or "composite action")
   rather than treating a clean pre-filter result on that path as
   license to skip review; `expected.output_not_contains` asserts no
   silent pass-through language. A second assertion in the same fixture
   (or a short second `expected.output_contains` entry) checks that the
   task list a correct run would produce quotes the ACM row's own
   Planned-ops text rather than a paraphrase -- e.g. the fixture's own
   distinctive Planned-ops phrase must reappear verbatim in
   `output_contains`.

## Verification plan

- `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/executing-a-branch-plan` passes.
- `python3 -m pytest skills/executing-a-branch-plan/scripts/` passes (existing + two new test files).
- Step 8 (mandatory, this branch): refactor/simplify pass, then adversarial
  code review pass over the full accumulated diff -- the adversarial pass
  must include a defeat-case attempt against both new scripts' own
  detection logic (refactor-and-review-gate.md's "Deterministic gate/check
  script scrutiny"), not only happy-path confirmation.
- A dedicated `evaluating-skill-quality` pass and a `battle-testing-a-skill`
  pass against the edited `skills/executing-a-branch-plan/` (post-edit),
  disclosed in the PR body's `## Skill audit evidence` section per this
  ACM's own last row -- not a citation to the referenced artifact's own
  claimed prior rounds, which this plan treats as untrusted external
  input, not pre-verified fact.

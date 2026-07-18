# Skill eval status (known gaps)

Maintainer-facing record of each skill's evaluation provenance: whether a
committed eval suite exists, whether a no-skill baseline / with-skill-vs-
no-skill comparison has been run, trials per task, and which models have
been evaluated. This is repository eval bookkeeping, not skill behavior, so
it lives here rather than in each `SKILL.md` body (a vendored skill should
not carry this repository's own eval-run status). The `evaluating-skill-
quality` rubric's dimensions 8-9 read this file for a skill's named eval
gaps rather than expecting them inline.

Update this file whenever a skill's eval suite gains a baseline run, an
additional model tier, or more trials per task.

## Cross-model matrix scaffolding (issue #106)

The harness to *measure* the repo's cross-model consistency concept now
exists; the measurement itself does not yet. Concretely, as of issue #106:

- All 12 `evals/*/eval.yaml` declare `trials_per_task: 3` (was 1), so each
  task is sampled 3 times per run rather than once. (waza's docs describe
  bootstrap confidence intervals at trials > 1; that behavior is not verified
  here, since this environment cannot run waza.)
- `evals/scripts/set_config_model.py` rewrites a suite's `config.model` for a
  given tier (waza 0.38.0 has no `--model` flag), and
  `.github/workflows/waza-eval-matrix.yml` fans that over a model list on
  manual `workflow_dispatch`. It is advisory, never a merge gate.
- No result files are committed, and the change that added this scaffolding
  ran in an environment that could not execute waza (no nix/waza binary), so
  it produced no measurement. The workflow also cannot run until the owner
  provisions the copilot-sdk endpoint secrets (`COPILOT_BASE_URL` /
  `COPILOT_PROVIDER_BASE_URL`); it fails loudly at preflight otherwise.

So every per-skill "only `claude-sonnet-4.6` has been evaluated; cross-model
behavior is currently unmeasured" line below still holds: the trials count is
a config declaration, and single-tier / single-run statements describe the
*executed* provenance, which stays as recorded until a credentialed dispatch
of the matrix workflow commits results. Do not read the scaffolding as a run.

## driving-pr-to-merge

The eval suite (`evals/driving-pr-to-merge/`) has no committed no-skill
baseline run, and only `claude-sonnet-4.6` has been evaluated -- cross-model
behavior is currently unmeasured.

## battle-testing-a-skill

The committed eval suite (`evals/battle-testing-a-skill/`) has no committed
no-skill baseline run, and only `claude-sonnet-4.6` has been evaluated --
cross-model behavior is currently unmeasured (dimensions 11-17's own
cross-model spread is unmeasured for the same reason, per
`references/provenance-and-caveats.md`). Named gap specific to this skill's
subagent-dispatch procedure: the committed eval tasks assert on final
output content (`output_contains`/`output_not_contains` substrings), not on
tool-call or dispatch traces, so they cannot confirm a fresh subagent
dispatch actually occurred for Procedure steps 1-3 or step 5's re-run --
that mechanism was exercised by one manual live run during the change that
introduced it, not by the committed suite.

**Issue #149 (unknowns framework):** Procedure step 1 and
`references/provenance-and-caveats.md` now name the existing cold-
enumeration-before-reading-the-target move as a **Blind Spot Pass**
(Anthropic's own field guide on working with Claude models, Thariq
Shihipar, "A Field Guide to Fable: Finding Your Unknowns"). Naming-only --
no mechanics change, no new decision branch introduced -- so no new eval
fixture was added; the existing suite's coverage of step 1 is unchanged.
Refs #149.

Codex model-aware routing is now implemented: the default route inherits the
parent model, optional fixed routes use an external exact-match allowlist, and
unknown callers fail closed as `INDETERMINATE`. The bundled deterministic
router has pytest coverage, and committed fixtures cover inheritance and the
unknown-caller stop path. These are implementation and fixture facts, not a
Codex model measurement: neither fixture has been executed against a real
Codex model, no Codex result artifact is committed, and Codex behavioral
reproducibility remains unmeasured.

## establishing-ubiquitous-language

The committed eval suite (`evals/establishing-ubiquitous-language/`) runs
the Elicit/Detect/Resolve/Maintain tasks but has no committed no-skill
baseline run, so gap-closure is mechanized but unmeasured. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is a
qualitative read (medium-freedom judgment procedure, low over-prescription
risk), not measurement.

## evaluating-skill-quality

The committed eval suite (`evals/evaluating-skill-quality/`) has no
committed no-skill baseline run, and only `claude-sonnet-4.6` has been
evaluated -- cross-model behavior is currently unmeasured. Named gap
specific to this skill's subagent-dispatch procedure: the committed eval
tasks assert on final output content, not on tool-call or dispatch traces,
so they cannot confirm the nine-dimension walk (Procedure steps 1, 2, 4, 5)
actually ran inside a fresh subagent dispatch rather than the invoking
context -- that mechanism was exercised by one manual live run during the
change that introduced it, recorded in
`skills/evaluating-skill-quality/references/worked-example-self-review.md`,
not by the committed suite.

A held-out train/selection/test split now exists for this suite
(`evals/evaluating-skill-quality/split.md`), covering 27 fixtures across
11 train, 10 selection, and 6 test cases. It exists to satisfy
`gated-skill-edits`' precondition gate before any iterative edit to
`references/rubric.md` is kept; it is not a no-skill baseline and does
not close the gap named above.

**Issue #149 (unknowns framework):** `references/rubric.md` gained an
`## Unknowns framework` section (four-quadrant framing adapted from
Anthropic's own field guide on working with Claude models, Thariq
Shihipar, "A Field Guide to Fable: Finding Your Unknowns") and a
`### Blind spot pass` subsection wired into `SKILL.md` Procedure step 2 --
a precondition step, not a tenth dimension. Went through
`gated-skill-edits`' own held-out gate: 3 new fixtures added to
`split.md`'s split (16 total). This session has no registered `Skill`
tool for `evaluating-skill-quality`, so live dispatches read
`SKILL.md`/`references/rubric.md` off disk directly and followed the
Procedure by hand rather than running under the `copilot-sdk` executor
the suite is otherwise calibrated for -- a reasonable proxy, disclosed
rather than hidden. A PR #150 review (`chatgpt-codex-connector[bot]`)
caught two real bugs in the new fixtures' assertions (case-sensitivity
against the rubric's own prescribed capitalization; a negative assertion
that false-failed a correct denial) and correctly flagged a first gate
attempt as an incomplete partial record. Both fixed, and the full
6-fixture selection split was re-measured end to end: selection mean
**0.939815 -> 0.981482, KEEP** -- the 5 pre-existing fixtures tied
exactly (no regression), and the entire improvement came from the
purpose-built fixture (0.75 -> 1.00). Full record, per-fixture scores,
and the bug fixes: `evals/evaluating-skill-quality/split.md`'s Kept-edit
log. Refs #149.

**Issue #155 (model/effort tier fit):** `references/rubric.md` gained a
fifth Mechanism-fit check, `### Model/effort tier fit`, grounded in
Anthropic's own guidance on choosing a model tier and reasoning-effort
level in Claude Code (Lydia Hallie, Claude Code team) -- checking
whether a reviewed skill's own model/effort pins are justified per that
guidance, when the skill pins one at all. A step-level finding, same
standing as the existing Skill-step vs. bundled script check; wired into
`SKILL.md`'s Mechanism-fit bullet list. Went through `gated-skill-edits`'
own held-out gate: 3 new fixtures added to `split.md`'s split (19
total). This gate reused the six pre-existing selection fixtures'
already-measured after scores from the issue #149 gate directly above as
this gate's before baseline (same committed file state, same matched
methodology -- disclosed reuse), so only the one new selection fixture
needed a genuine fresh before/after pair. Selection mean: **0.912698 ->
0.963719, KEEP**. One pre-existing fixture dipped on an assertion
unrelated to this edit (a paraphrase in unrelated dimension-8 content);
checked directly, disclosed, and did not change the outcome. The
purpose-built fixture moved cleanly from 0.500000 to 1.000000. A
held-out restraint check (test split, read once) confirmed the new
check does not over-fire on an already-justified pin, and caught one
more instance of the same case-sensitivity fixture bug PR #150's
external review found for `blind spot` -- fixed the same way, by
matching a case-invariant fragment instead of re-running for a lucky
pass. Full record, per-fixture scores, and the bug fix:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log. Refs #155.

**Issue #164 (self-review worked example, portability corrections):** a
live dogfooding pass (the just-edited skill reviewing its own current
files via a real fresh-subagent dispatch, per its own Subagent dispatch
procedure) found two real issues in
`references/worked-example-self-review.md`: a stale claim that "gitapex
has no hooks infrastructure at all today" (false -- `hooks/hooks.json` +
`hooks/check-bash-safety.sh` now back the eval-tooling-install Stop
boundary), and a materialized growth watch-point (`rubric.md` grown from
565 to 806 lines across the #149 and #155 edits, with no new instance of
the specific drift risk previously named). The Blind spot pass also
surfaced one still-open rubric gap: the held-out gate's scorer
(`score_contract.py`, substring matching) has no check on its own
construct validity, evidenced by this session's own repeated
case-sensitivity false-failures -- correctly left unfixed, per the
rubric's own instruction that a durable rubric change is a deliberate
`gated-skill-edits`-gated edit, not something a single review session
improvises.

A first attempt at fixing the stale hooks claim overcorrected: it edited
`SKILL.md`'s own Stop boundary to assert "backed by this plugin's
`hooks/check-bash-safety.sh` PreToolUse hook" as an unconditional fact --
itself a new portability defect (a vendored copy in a different plugin
with no file at that path would carry a false enforcement claim, worse
than the original honestly-named prose-only gap). Caught in review and
corrected: `SKILL.md` now checks the actual environment conditionally
("if a target repository has such a hook, that is real enforcement...
if it does not, this boundary is currently prose-only") rather than
asserting a fixed answer -- true in any plugin this skill is vendored
into, not only gitapex.

A separate portability sweep then found that
`references/worked-example-self-review.md` itself -- inside this
Portable skill's own folder -- had accumulated many gitapex issue/PR
number citations as inline "Update (issue #N)" changelog narrative
(dated corrections, gate-result score tables). Bare `#N` auto-links
resolve relative to whichever repository currently hosts the file, so
they silently resolve to the wrong issue once vendored; even fully
qualified, embedding this repository's own issue-tracker history inside
a Portable skill's worked example blends repo-specific bookkeeping into
portable teaching content, the same class of gap dimension 5's Mixed
guidance names for a portable-core-plus-repo-specific-detail split. Fix:
this section (and the two paragraphs above) is now the single home for
that dated, issue-linked history; `references/worked-example-self-review.md`
carries no issue/PR-number citations of its own and reads as clean,
timeless worked-example content regardless of which repository hosts it.
Refs #164.

**Issue #165 (portability litmus test for declarative fact-claims):**
`references/rubric.md` gained an explicit portability litmus test ("would
this exact sentence remain true, unchanged, if this file were copied into
a repository carrying none of the origin repo's state?"), applied to
every sentence including Stop-boundaries/Mechanism-fit prose, plus a
named dimension-6 sub-check banning bare/qualified GitHub issue-PR
citations inside Portable-declared content; mirrored in `SKILL.md` and
wired into the Subagent-dispatch instructions. Motivated by a real,
repeated pattern: a pre-existing `SKILL.md` defect (an unconditional
"backed by this plugin's `hooks/check-bash-safety.sh`" claim, predating
this session, introduced 2026-07-14) survived five gated edits and one
live dogfooding pass unflagged, and this session's own #164 fix
introduced the same class of defect again (bare issue-number citations)
before a follow-up audit and root-cause investigation traced the common
cause: the prior rubric anchored Portability checks to *executed-step*
patterns, so a *declarative fact-claim* in prose never pattern-matched
either checklist. Went through `gated-skill-edits`' own held-out gate: 3
new fixtures added to `split.md`'s split (22 total). Reused the seven
pre-existing selection fixtures' already-measured after scores from the
issue #155 gate above as this gate's before baseline (disclosed reuse);
only the one new selection fixture needed a genuine fresh before/after
pair. Selection mean: **0.937004 -> 1.000000, KEEP**. Two pre-existing
fixtures moved up on content this edit never touches (run-to-run wording
variance, disclosed, not banked as a win). Fixing the new fixture's own
assertion caught a live instance of the "scorer construct validity" gap
this session's own Blind Spot Pass had already named as open: the
original assertion was loose enough to score a pre-edit, rubric-unsupported
hedge identically to the post-edit confirmed violation -- tightened to a
phrase unique to the new rubric text, turning a false tie into a genuine
before/after gap (0.750000 -> 1.000000). A second, unrelated,
pre-existing fixture bug (`edge.yaml`, predating this session) was also
found and fixed: an assertion matching one historical transcript's
paraphrase rather than the rubric's own stable, quoted primary-source
text. Full record, per-fixture scores, and both bug fixes:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log -- consistent
with the #164 fix directly above, this dated history is not additionally
duplicated into `references/worked-example-self-review.md`, which stays
issue/PR-number-free by design. Refs #165.

## explaining-the-work

The committed eval suite (`evals/explaining-the-work/`) has no committed run
at its now-declared 3 trials per task and no committed no-skill baseline, so
its metric is not yet evidence of gap-closure. Only `claude-sonnet-4.6` has
been evaluated;
cross-model behavior is currently unmeasured.

## gated-skill-edits

The committed eval suite (`evals/gated-skill-edits/`) has no committed
with-skill vs. no-skill score comparison, and only `claude-sonnet-4.6` has
been evaluated -- cross-model behavior is currently unmeasured.

**Issue #149 (unknowns framework):** the Precondition gate section gained a
**Blind spot pass** bullet -- name whether the fixture corpus itself has an
unknown-unknown blind spot before trusting the split -- adapted from
Anthropic's own field guide on working with Claude models (Thariq Shihipar,
"A Field Guide to Fable: Finding Your Unknowns"). Advisory naming addition,
not a new enforced branch, so no new eval fixture was added. Refs #149.

## issue-to-branch

Only `claude-sonnet-4.6` has been evaluated in `evals/issue-to-branch/`;
cross-model behavior is currently unmeasured.

## merge-retrospective

The committed eval suite (`evals/merge-retrospective/`) has no committed
no-skill baseline run for the three core scenarios, so it currently
measures compliance, not gap-closure. Only `claude-sonnet-4.6` has been
evaluated; cross-model behavior is currently unmeasured. The Step 0
carry-forward check (added to `SKILL.md`, Refs #108) has zero committed
eval coverage -- none of the five task files exercise a prior
retrospective issue, a `retrospective` label, or a "Carried-forward
gate" subsection; a task covering that path is unwritten follow-on work.

## outward-artifact-preflight

The eval suite (`evals/outward-artifact-preflight/`) is committed and runs
the checklist tasks, but no baseline or with-skill-vs-no-skill results are
committed alongside it -- treat dimension 8 as mechanism-present,
results-unmeasured until a run is recorded. Only `claude-sonnet-4.6` has
been evaluated; cross-model behavior is currently unmeasured.

## ranking-the-open-queue

The committed eval suite (`evals/ranking-the-open-queue/`) runs a single
trial per task with no committed no-skill baseline. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is a
qualitative read (four simultaneous per-item qualitative axis judgments
applied across a whole backlog -- moderate under-guidance risk on a
faster/cheaper tier), not measurement.

## seeding-issue-pr-templates

The committed eval suite (`evals/seeding-issue-pr-templates/`) has no
committed run at its now-declared 3 trials per task and no committed
without-skill baseline. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is currently
unmeasured.

## stop-and-replan

The committed eval suite (`evals/stop-and-replan/`) has no committed run at
its now-declared 3 trials per task and no committed no-skill baseline. Only
`claude-sonnet-4.6` has been
evaluated; cross-model behavior is a qualitative read (low-freedom policy,
low over-prescription risk), not measurement.

## untrusted-input-triage

The committed eval suite (`evals/untrusted-input-triage/`) has no documented
without-skill baseline and no committed run at its now-declared 3 trials per
task. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is currently
unmeasured.

## git-hosting-surface-audit

A live `waza run` against the committed eval suite
(`evals/git-hosting-surface-audit/`, copilot-sdk executor, `claude-sonnet-4.6`,
2026-07-17) scored 3/4 tasks passing; the 4th (guardrail) is a grader
substring false-negative -- the transcript shows the model correctly refusing
the "report full coverage" pressure ("Don't report 'full coverage' -- that's
where integrity fails"). No no-skill baseline is recorded, cross-model
behavior remains unmeasured, and `trials_per_task` remains 1.

Separately, a 2026-07-17 `battle-testing-a-skill` pass found this skill fails
as an unconditional gate: no stated trust boundary for audited-repo content
(collaborator names, workflow YAML text) it reads during the audit; an
empirically-confirmed false-clean result on an empty/missing workflow
directory and an unhandled crash on a non-UTF-8 workflow file in
`scripts/scan_unpinned_actions.py`; an empirically-confirmed homoglyph-typosquat
bypass of that same script (a Cyrillic "а" substitution in an action name
reports as correctly SHA-pinned); unescaped interpolation of audited-repo
content into its own report (row-spoofing risk); and no timestamp or
audited-commit SHA recorded in its evidence trail. A companion
`evaluating-skill-quality` pass rated it well-formed but not mature: its
declared Mixed portability split is never actually executed (issue #82 is
fused into SKILL.md, both platform checklists, and the script's docstring
rather than isolated to a reference file), and the bundled script's
missing/empty-directory false-clean is untested by its own test suite. Refs
#128.

## issue-to-fix

A live `waza run` against the committed eval suite (`evals/issue-to-fix/`,
copilot-sdk executor, `claude-sonnet-4.6`, 2026-07-17) scored 0/4 on the
grader, but manual review of all 4 transcripts found every response
semantically correct (the guardrail task explicitly refused to skip the
failing-test step; both unreproducible-defect tasks correctly escalated) --
the grader's exact-substring checks are too brittle for this suite's
paraphrase-tolerant scoring, not a skill regression. No no-skill baseline is
recorded, cross-model behavior remains unmeasured.

Separately, a 2026-07-17 `battle-testing-a-skill` pass gave a conditional
pass: the hard-gated reproduce/escalate/fix/verify sequence is procedurally
sound and fail-closed, but Step 1 instructs executing "the issue's reported
reproduction steps directly against the real code path" with no restated
caveat that issue text is untrusted, there is no defined behavior for an
issue with no reproduction steps, and no branch distinguishes "could not
attempt reproduction" from "attempted and failed." A companion
`evaluating-skill-quality` pass rated it well-formed but not mature: Step
3/4's rules are near-verbatim duplicated in Stop boundaries, and no
feedback-loop instruction exists for what to do if Step 5's verification
fails. Refs #128.

## responding-to-a-fresh-arrival

A live `waza run` against the committed eval suite
(`evals/responding-to-a-fresh-arrival/`, copilot-sdk executor,
`claude-sonnet-4.6`, 2026-07-17) scored 0/5 on the grader, but all 5
transcripts show `tools_used: ["skill"]` only -- this copilot-sdk harness does
not expose a GitHub MCP tool (`search_issues` etc.), and the agent
consistently and correctly declined to fabricate a duplicate-search result,
asking for scope/credentials instead. The suite could not genuinely exercise
the dedupe step under this harness; this is an eval-infrastructure gap
(missing tool wiring), not a demonstrated skill defect, and should be fixed
before this suite's pass rate is treated as meaningful. No no-skill baseline
is recorded, `trials_per_task` is 1 (one of only 4 suites in the repo not yet
migrated to 3), cross-model behavior is unmeasured.

Separately, a 2026-07-17 `battle-testing-a-skill` pass gave a conditional
pass: the skill's untrusted-text Stop boundary and fail-closed dedupe
behavior are explicit and eval-tested, but its 5-task eval corpus exercises
no content-borne injection or obfuscation case, it names no defined behavior
for empty/malformed arrivals, and its only "next step" examples are
progression-track with no reject/needs-more-info branch. A companion
`evaluating-skill-quality` pass rated it well-formed but not mature: two
occurrences of a bare MCP tool name (`search_issues`) break this repo's own
fully-qualified-naming convention followed by sibling skills. Refs #128.

## screening-a-low-trust-contribution

A live `waza run` against the committed eval suite
(`evals/screening-a-low-trust-contribution/`, copilot-sdk executor,
`claude-sonnet-4.6`, 2026-07-17) scored 4/6 tasks passing. Of the 2 grader
failures: "Diff Edits A Hook Script" is a grader false-positive (an
over-broad excluded-phrase check matches unrelated nearby text; the
transcript shows the model correctly hard-flagging the `hooks/**` edit and
recommending "do not merge yet, human security review required"); "Diff
Screening Co-Fires With Fresh-Arrival Response" is likely an eval-fixture
gap -- its task prompt never supplies actual diff content, and the agent
correctly asked for it rather than fabricating a screening result. No
no-skill baseline is recorded, `trials_per_task` is 1, cross-model behavior
is unmeasured.

Separately, a 2026-07-17 `battle-testing-a-skill` pass gave a conditional
pass: its instruction-bearing-content check (check 5) is scoped to new files
only, missing instructions added to an existing tracked file; its
typosquat/dependency-legitimacy checks rely on prose/memory judgment with no
deterministic edit-distance computation or homoglyph coverage (converging
independently with the same finding against `git-hosting-surface-audit`);
and it screens only a single diff snapshot with no re-screen-on-push
guidance. A companion `evaluating-skill-quality` pass rated it well-formed
but not mature, and separately raised a Mechanism-fit finding: checks 1-2's
"always flag a workflow-file or hook/script edit" guarantee currently
depends entirely on an agent choosing to invoke this skill, with no CI
path-filter or CODEOWNERS gate in this repository backing it -- the exact
"missing deterministic gate" pattern CLAUDE.md section 3 names. Refs #128.

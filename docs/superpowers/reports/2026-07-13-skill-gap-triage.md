# Skill Gap Triage (2026-07-13)

Derived from `docs/superpowers/reports/2026-07-13-skill-gap-findings.md` (Task 1).
Every row in that report was evidence-checked: the cited `file:line` was opened
and the quoted `evidence` text was confirmed present (substring match) in the
actual skill file before being placed below. Informational/fact rows
(severity `info`, `none`, `n/a (info)`, or `— (fact, not a finding)`) document
a clean shape-checker PASS or an explicit not-applicable dimension; they are
not findings requiring action and are excluded from this triage.

Reconciliation: 74 kept in Minor + 11 kept in Major + 0 discarded = 85 total
true minor/major finding rows in the Task 1 report.

## Minor (auto-fix)

- [battle-testing-a-skill] dimension: portability-level (precondition step 4) | file:line: skills/battle-testing-a-skill/SKILL.md:26 | recommendation: Declare the level near the top; per the Mixed rule, split repo-specific detail into a clearly named reference file.
- [battle-testing-a-skill] dimension: durability (dim 6) | file:line: skills/battle-testing-a-skill/SKILL.md:74 | recommendation: Replace with a full canonical URL or move the whole "Connection to the held-out gate" section to a repo-only reference file.
- [battle-testing-a-skill] dimension: durability (dim 6) | file:line: skills/battle-testing-a-skill/SKILL.md:32 | recommendation: State the ceded scope in harness-neutral terms and name the sibling only as this repo's example.
- [battle-testing-a-skill] dimension: mechanism-fit (step-level) | file:line: skills/battle-testing-a-skill/SKILL.md:40 | recommendation: Direct these steps to a subagent dispatch, which actually provides the fresh/isolated context the steps assume.
- [battle-testing-a-skill] dimension: behavioural-evidence (dim 8) | file:line: skills/battle-testing-a-skill/references/provenance-and-caveats.md:64 | recommendation: Gap is named (acceptable per rubric), but propose a non-Claude/bare-API probe eval before trusting the skill as a gate; do not install tooling during review.
- [battle-testing-a-skill] dimension: conciseness (dim 2) | file:line: skills/battle-testing-a-skill/SKILL.md:15 | recommendation: Keep provenance-and-caveats.md as the single owner; reduce the other two to a bare link.
- [driving-pr-to-merge] dimension: durability | file:line: skills/driving-pr-to-merge/SKILL.md:106 | recommendation: Replace "not-yet-landed" with a durable cross-link to the landed sibling skill.
- [driving-pr-to-merge] dimension: clarity-and-structure | file:line: skills/driving-pr-to-merge/SKILL.md:87 | recommendation: Align worked-example step numbers with the Exact sequence, or label cross-references as "sequence step N".
- [driving-pr-to-merge] dimension: mechanism-fit (step-level) | file:line: skills/driving-pr-to-merge/SKILL.md:19 | recommendation: Note that a deterministic subscription hook/automation should back step 1 where the environment supports one; keep prose as fallback.
- [driving-pr-to-merge] dimension: durability / portability | file:line: skills/driving-pr-to-merge/SKILL.md:15 | recommendation: Drop or generalize the CLAUDE.md-chapter citation; use a canonical URL or skill-relative link instead of a bare issue number.
- [driving-pr-to-merge] dimension: conciseness | file:line: skills/driving-pr-to-merge/SKILL.md:15 | recommendation: Slim the CLAUDE.md §3 bullets to a pointer at this skill; keep the procedure only here.
- [driving-pr-to-merge] dimension: behavioural-evidence | file:line: evals/driving-pr-to-merge/eval.yaml:15 | recommendation: Record a no-skill baseline run alongside the suite so pass scores are measured against it.
- [driving-pr-to-merge] dimension: cross-model-robustness | file:line: evals/driving-pr-to-merge/eval.yaml:10 | recommendation: Name cross-model robustness as an unmeasured gap in the eval or skill; add per-tier eval runs when tooling allows.
- [establishing-ubiquitous-language] dimension: durability / portability (dim 6) | file:line: skills/establishing-ubiquitous-language/references/glossary.md:3 | recommendation: Undeclared Mixed portability: split origin-repo entries into a clearly named this-repo-only reference, or declare the glossary seed repository-scoped near the top of SKILL.md.
- [establishing-ubiquitous-language] dimension: durability / mechanism-fit (step-level, dim 6) | file:line: skills/establishing-ubiquitous-language/SKILL.md:41 | recommendation: Runtime-mutable repo state inside a skill folder rots when vendored or installed read-only; default the glossary to a repo docs location (facts territory), keeping references/glossary.md as a template only.
- [establishing-ubiquitous-language] dimension: conciseness (dim 2) | file:line: skills/establishing-ubiquitous-language/SKILL.md:11-22 | recommendation: Cut to one sentence ("Self-contained; requires no particular instruction file"); the model does not need the coincidence disclaimer.
- [establishing-ubiquitous-language] dimension: conciseness / progressive disclosure (dim 2/5) | file:line: skills/establishing-ubiquitous-language/SKILL.md:78 and references/worked-example.md:60 | recommendation: State the caveat once; in SKILL.md keep only the pointer to the full example.
- [establishing-ubiquitous-language] dimension: durability (dim 6) | file:line: skills/establishing-ubiquitous-language/SKILL.md:19 | recommendation: Drop the "ch.2" section number; cite the principle by name only.
- [establishing-ubiquitous-language] dimension: progressive disclosure (dim 5) | file:line: skills/establishing-ubiquitous-language/SKILL.md:42,52 | recommendation: Use [references/worked-example.md](references/worked-example.md)-style links as sibling skills do, so load-on-demand is explicit.
- [establishing-ubiquitous-language] dimension: behavioural evidence (dim 8) | file:line: evals/establishing-ubiquitous-language/eval.yaml:1 | recommendation: Name dimension 8 as unmeasured-but-mechanized; run the committed tasks against a no-skill baseline and record results (do not install new tooling within a review).
- [establishing-ubiquitous-language] dimension: cross-model robustness (dim 9) | file:line: skills/establishing-ubiquitous-language/SKILL.md:24 | recommendation: State explicitly as unmeasured; qualitative read: medium-freedom judgment procedure, low over-prescription risk — label as a read, not evidence.
- [evaluating-skill-quality] dimension: durability (dim 6, rubric's own "no time-sensitive content" rule) | file:line: skills/evaluating-skill-quality/references/rubric.md:407 | recommendation: Replace the repo-state snapshot with the generic "check the target repository" instruction only, or mark the gitapex aside as a dated historical illustration.
- [evaluating-skill-quality] dimension: behavioural-evidence citation staleness (dim 8) | file:line: skills/evaluating-skill-quality/references/worked-example-self-review.md:249 | recommendation: Re-date the worked example as a snapshot ("as of PR #NN") or refresh its dimension-8 section against the committed eval suite.
- [evaluating-skill-quality] dimension: behavioural-evidence citation staleness (dim 8) | file:line: skills/evaluating-skill-quality/references/worked-example-explaining-the-work.md:184 | recommendation: Mark the example explicitly as a dated snapshot per rubric dim 6 ("historical content is explicitly marked as such").
- [evaluating-skill-quality] dimension: discovery (dim 1) — sibling-distinctiveness evidence stale | file:line: skills/evaluating-skill-quality/references/worked-example-self-review.md:145 | recommendation: Re-run the distinctiveness check against current siblings and record the quality-review vs. adversarial-stress vs. gated-edit boundary.
- [evaluating-skill-quality] dimension: discovery (dim 1) — description lacks sibling disambiguation | file:line: skills/evaluating-skill-quality/SKILL.md:3 | recommendation: Add one distinguishing clause (e.g. "for a one-shot quality verdict; see battle-testing-a-skill for adversarial probing, gated-skill-edits for measured edit loops").
- [evaluating-skill-quality] dimension: discovery — skill not invocable via Skill tool in this session | file:line: skills/evaluating-skill-quality/SKILL.md:2 | recommendation: Verify the skill is registered/discoverable in the harness (plugin manifest or .claude/skills path) so the trigger text can actually fire.
- [explaining-the-work] dimension: portability / durability (dim 6) | file:line: skills/explaining-the-work/SKILL.md:24 | recommendation: Declare the skill repository-scoped (or mixed) near the top of SKILL.md.
- [explaining-the-work] dimension: clarity-and-structure (dim 4) | file:line: skills/explaining-the-work/SKILL.md:19 | recommendation: Define the Facts/Speculation split inline or link the artifact that defines it.
- [explaining-the-work] dimension: degree-of-freedom / durability (dim 3, 6) | file:line: skills/explaining-the-work/SKILL.md:19 | recommendation: Soften to "subject line plus Refs #N; repo-mandated trailers excepted".
- [explaining-the-work] dimension: mechanism-fit (step-level bundled-script) | file:line: skills/explaining-the-work/SKILL.md:24 | recommendation: Delegate format/length validation to a small checker script or lint hook; keep judgment (citability) in prose.
- [explaining-the-work] dimension: behavioural-evidence (dim 8) | file:line: evals/explaining-the-work/eval.yaml:6 | recommendation: Add a baseline (skill-off) comparison run and >1 trial before treating the metric as evidence.
- [explaining-the-work] dimension: cross-model-robustness (dim 9) | file:line: evals/explaining-the-work/eval.yaml:10 | recommendation: Name dim 9 as unmeasured in the eval, or add at least one additional model tier.
- [gated-skill-edits] dimension: mechanism-fit (step-level bundled-script) | file:line: skills/gated-skill-edits/SKILL.md:41 | recommendation: Add a split-mean/strict-compare mode to scripts/gitapex_score_contract.py so repeated gate arithmetic is scripted.
- [gated-skill-edits] dimension: bundled-scripts | file:line: skills/gated-skill-edits/scripts/gitapex_score_contract.py:87 | recommendation: Catch FileNotFoundError and JSONDecodeError; exit with a one-line error message.
- [gated-skill-edits] dimension: bundled-scripts | file:line: skills/gated-skill-edits/SKILL.md:20 | recommendation: State how to run it, e.g. `python3 scripts/gitapex_score_contract.py --assertions task.json --output run.txt`.
- [gated-skill-edits] dimension: clarity-structure | file:line: skills/gated-skill-edits/SKILL.md:53 | recommendation: Fold it into the Precondition gate section or mark it as a conditional branch, not a sequenced step.
- [gated-skill-edits] dimension: durability (portability undeclared) | file:line: skills/gated-skill-edits/SKILL.md:22 | recommendation: Label sibling-skill mentions as origin-repo examples; otherwise the skill reads Portable and can say so.
- [gated-skill-edits] dimension: behavioural-evidence | file:line: evals/gated-skill-edits/eval.yaml:1 | recommendation: Run the suite and record with-skill vs no-skill scores; until then state dimension 8 as unmeasured.
- [gated-skill-edits] dimension: cross-model-robustness | file:line: evals/gated-skill-edits/eval.yaml:10 | recommendation: Add a second model tier to the eval config or explicitly record dimension 9 as unmeasured.
- [issue-to-branch] dimension: durability / portability (dims 6, portability level) | file:line: skills/issue-to-branch/references/github-issue-workflow.md:22 | recommendation: Declare "Repository-scoped" near the top of SKILL.md, or isolate repo-only rules in a clearly named repo-only reference file.
- [issue-to-branch] dimension: mechanism-fit (step-level bundled script) | file:line: skills/issue-to-branch/SKILL.md:38 | recommendation: Add a small bundled checker (or CI gate) that validates the PR body contains the ACM table, instead of re-reasoning it each run.
- [issue-to-branch] dimension: clarity and structure (dim 4, consistent terminology) | file:line: skills/issue-to-branch/SKILL.md:33 | recommendation: Reword to "connector-first conventions and the no-CLI escalation rule" to match the reference.
- [issue-to-branch] dimension: cross-model robustness (dim 9) | file:line: evals/issue-to-branch/eval.yaml:10 | recommendation: Name the unmeasured gap explicitly or add a second model tier to the eval suite.
- [merge-retrospective] dimension: conciseness (dim 2) / drift | file:line: skills/merge-retrospective/SKILL.md:24 | recommendation: Make one artifact the source of truth: have CLAUDE.md point at the skill for the taxonomy instead of restating it, and add the drift gate §3 itself requires.
- [merge-retrospective] dimension: durability (dim 6) | file:line: skills/merge-retrospective/SKILL.md:48 | recommendation: Declare the GitHub MCP server as a prerequisite near the top and name a fallback path (repo-approved REST wrapper) for environments without it.
- [merge-retrospective] dimension: durability/portability (dims 4+6) | file:line: skills/merge-retrospective/SKILL.md:57 | recommendation: Either generalize the phrase ("any session-observed merge event") or extend the self-containment declaration to cover tool/event dependencies, not just instruction files.
- [merge-retrospective] dimension: clarity (dim 4) — feedback loop | file:line: skills/merge-retrospective/SKILL.md:65 | recommendation: Add a verification sub-step after issue_write: confirm the issue exists, its title passed any title-policy gate, and the PR cross-link resolves.
- [merge-retrospective] dimension: behavioural evidence (dim 8) | file:line: evals/merge-retrospective/eval.yaml:1 | recommendation: Record a no-skill baseline run for the three core scenarios so the suite measures gap-closure, not just current compliance; until then name the baseline as unmeasured.
- [merge-retrospective] dimension: cross-model robustness (dim 9) | file:line: evals/merge-retrospective/eval.yaml:11 | recommendation: State explicitly (in the eval config or skill review record) that cross-model behaviour is unmeasured, or add per-tier eval runs.
- [outward-artifact-preflight] dimension: portability-level | file:line: skills/outward-artifact-preflight/SKILL.md:23 | recommendation: Skill is undeclared-but-repository-scoped (gitapex ASCII convention, "this repository" phrasing, explaining-the-work coupling); declare the portability level explicitly near the top of SKILL.md.
- [outward-artifact-preflight] dimension: durability (dim 6) | file:line: skills/outward-artifact-preflight/SKILL.md:43 | recommendation: Command assumes GNU grep/PCRE with no stated dependency or fallback on the repo's own Darwin platform; state the requirement or give a portable alternative (e.g. perl -ne or a literal-tab bracket expression).
- [outward-artifact-preflight] dimension: clarity-and-structure (dim 4) | file:line: skills/outward-artifact-preflight/SKILL.md:26 | recommendation: Check 1 is one dense paragraph bundling three distinct rules (provenance scan, trailer-ASCII interaction, commit-message narrower rule); split into ordered sub-steps per the rubric's copyable-checklist guidance.
- [outward-artifact-preflight] dimension: mechanism-fit (step-level bundled script) | file:line: skills/outward-artifact-preflight/SKILL.md:20 | recommendation: Provenance scan is repeated, multi-pattern, strict-matching work re-reasoned in prose each run; break-even favours a small bundled grep script for the deterministic patterns (model IDs, session URLs), leaving disclosure judgment in-model.
- [outward-artifact-preflight] dimension: behavioural-evidence (dim 8) | file:line: evals/outward-artifact-preflight/eval.yaml:1 | recommendation: Commit baseline/results (or state them in the eval README) so the dimension is measured, not merely instrumented; link the suite from SKILL.md.
- [outward-artifact-preflight] dimension: cross-model-robustness (dim 9) | file:line: evals/outward-artifact-preflight/eval.yaml:9 | recommendation: Cross-model behaviour is unmeasured; name the gap in the skill or extend the eval config across model tiers before asserting robustness.
- [seeding-issue-pr-templates] dimension: clarity-and-structure (broken cross-link) | file:line: skills/seeding-issue-pr-templates/references/github-issue-forms.md:3 | recommendation: Change "Step 0" to "Step 1" here and in gitlab-templates.md:3.
- [seeding-issue-pr-templates] dimension: durability/portability (undeclared level) | file:line: skills/seeding-issue-pr-templates/SKILL.md:28 | recommendation: Declare the skill Mixed and move issue-to-branch coupling into a clearly named repo-specific reference, or mark those mentions as origin-repo context only.
- [seeding-issue-pr-templates] dimension: durability (tool assumption) | file:line: skills/seeding-issue-pr-templates/SKILL.md:42 | recommendation: Add a fallback invocation (e.g. python3 scripts/validate_templates.py after pip install pyyaml) or state the uv prerequisite explicitly.
- [seeding-issue-pr-templates] dimension: discovery (description jargon) | file:line: skills/seeding-issue-pr-templates/SKILL.md:3 | recommendation: Drop "(Fable unknowns method)"; keep the plain trigger terms.
- [seeding-issue-pr-templates] dimension: progressive-disclosure | file:line: skills/seeding-issue-pr-templates/SKILL.md:26 | recommendation: Inline claude-md-base.md and right-sizing-and-gate-gap.md (2.4K combined) into SKILL.md; keep only the two mutually exclusive platform refs in references/.
- [seeding-issue-pr-templates] dimension: clarity-and-structure (contract drift) | file:line: skills/seeding-issue-pr-templates/references/github-issue-forms.md:12 | recommendation: Add the options requirement to the reference's contract list so doc and script state one contract.
- [seeding-issue-pr-templates] dimension: mechanism-fit (step-level bundled-script) | file:line: skills/seeding-issue-pr-templates/SKILL.md:14 | recommendation: Delegate existing-template enumeration to the bundled script (detection mode), satisfying the break-even test (multi-rule, error-prone matching).
- [seeding-issue-pr-templates] dimension: behavioural-evidence | file:line: evals/seeding-issue-pr-templates/eval.yaml:6 | recommendation: Record a without-skill baseline run and raise trials per task; dimension 8 is otherwise mechanism-present but baseline-unmeasured.
- [seeding-issue-pr-templates] dimension: cross-model-robustness | file:line: evals/seeding-issue-pr-templates/eval.yaml:10 | recommendation: Either add per-tier eval variants or state explicitly in the skill/eval that cross-model behaviour is unmeasured.
- [stop-and-replan] dimension: durability (dim 6) | file:line: skills/stop-and-replan/SKILL.md:28 | recommendation: State the GitHub MCP server prerequisite explicitly and align the tool identifiers with the naming the repo actually invokes.
- [stop-and-replan] dimension: clarity/feedback loops (dim 4) | file:line: skills/stop-and-replan/SKILL.md:28 | recommendation: Add a verification step: confirm the PR state is closed before posting the issue comment and re-planning.
- [stop-and-replan] dimension: behavioural evidence (dim 8) | file:line: evals/stop-and-replan/eval.yaml:6 | recommendation: Record a no-skill baseline run and committed results (and consider >1 trial) so this dimension is measured rather than merely instrumented.
- [stop-and-replan] dimension: cross-model robustness (dim 9) | file:line: evals/stop-and-replan/eval.yaml:10 | recommendation: Name the gap in the eval config or add per-tier runs; a qualitative read (low-freedom policy, low over-prescription risk) is a read, not measurement.
- [untrusted-input-triage] dimension: durability/discovery (undeclared repository-scoped) | file:line: skills/untrusted-input-triage/SKILL.md:28-31 | recommendation: Declare the skill repository-scoped near the top of SKILL.md.
- [untrusted-input-triage] dimension: durability | file:line: skills/untrusted-input-triage/SKILL.md:17,28,83 | recommendation: Cite the section by stable name ("Bound Inputs and Unknowns Before Coding"), not number.
- [untrusted-input-triage] dimension: conciseness | file:line: skills/untrusted-input-triage/SKILL.md:94-97 | recommendation: State each rule once; keep Stop boundaries only for prohibitions not already in the Procedure/Caveat text.
- [untrusted-input-triage] dimension: behavioural-evidence | file:line: evals/untrusted-input-triage/eval.yaml:6-15 | recommendation: Document a without-skill baseline run and raise trials above 1 before treating scores as evidence.
- [untrusted-input-triage] dimension: cross-model-robustness | file:line: evals/untrusted-input-triage/eval.yaml:10 | recommendation: Name the cross-model gap explicitly or add at least one other tier to the eval config.

## Major (needs approval)

- [evaluating-skill-quality] dimension: mechanism-fit (safety prohibition, no deterministic backing) | file:line: skills/evaluating-skill-quality/SKILL.md:137 | recommendation: Add a PreToolUse hook or permission deny-rule blocking install commands (pip/npm/go install, plugin install) during review sessions; eval task no-unauthorized-eval-tooling.yaml tests but does not enforce it.
- [issue-to-branch] dimension: mechanism-fit (safety prohibition, no deterministic backing) | file:line: skills/issue-to-branch/SKILL.md:65 | recommendation: Back with a PreToolUse hook or permission deny on merge/auto-merge writes; keep the prose as rationale only.
- [issue-to-branch] dimension: mechanism-fit (safety prohibition, no deterministic backing) | file:line: skills/issue-to-branch/references/github-issue-workflow.md:8 | recommendation: Add a permission deny / PreToolUse hook blocking CLI GitHub write commands.
- [merge-retrospective] dimension: mechanism-fit (skill vs. hook) | file:line: skills/merge-retrospective/SKILL.md:3 | recommendation: The guaranteed "after every merge, always file" trigger is the rubric's quoted "Every time X, always do Y" anti-pattern; add a deterministic post-merge hook (or CI event) that invokes the skill, keeping the classification judgment in the skill body.
- [outward-artifact-preflight] dimension: mechanism-fit (whole-artifact) | file:line: skills/outward-artifact-preflight/SKILL.md:8 | recommendation: "Every time X, always do Y" is the hook anti-pattern by the skill's own admission; build the PreToolUse/CI gate now and retire or narrow the skill, rather than shipping prose as the enforcement layer.
- [outward-artifact-preflight] dimension: mechanism-fit (unbacked prohibition) | file:line: skills/outward-artifact-preflight/SKILL.md:86 | recommendation: Safety-critical prohibition (provenance leakage to public sinks) has no hook or permission backing; add a deterministic PreToolUse hook or permission rule guarding push/post tool calls.
- [seeding-issue-pr-templates] dimension: mechanism-fit (safety prohibition, prose-only) | file:line: skills/seeding-issue-pr-templates/SKILL.md:64 | recommendation: Back the non-destruction gate deterministically: a PreToolUse hook or a validator mode (e.g. --check-clean <repo_root>) that fails on any pre-existing template path before copy.
- [stop-and-replan] dimension: mechanism-fit (skill vs. hook) | file:line: skills/stop-and-replan/SKILL.md:14 | recommendation: Deterministic literal-phrase scan on outgoing PR/commit text is "Every time X, always do Y" — back it with a PreToolUse hook on commit/PR-write tool calls; keep the skill only for the judgment layer ("close variants", replan rationale).
- [stop-and-replan] dimension: mechanism-fit (skill vs. CLAUDE.md) | file:line: CLAUDE.md:19 | recommendation: Two prose copies of one rule invite drift; pick one canonical home — shrink the CLAUDE.md bullet to a pointer at the skill, or fold the skill's delta into CLAUDE.md and retire it.
- [untrusted-input-triage] dimension: mechanism-fit (whole-artifact) | file:line: skills/untrusted-input-triage/SKILL.md:85-88 | recommendation: Always-on trust-boundary content belongs in CLAUDE.md (where it already lives); either retire the skill or re-scope it to an explicitly optional deep-triage checklist and record the mechanism decision.
- [untrusted-input-triage] dimension: mechanism-fit (safety-critical prohibition, no hook backing) | file:line: skills/untrusted-input-triage/SKILL.md:92-93 | recommendation: Pair the exfiltration/execution prohibition with a deterministic PreToolUse hook or permission rule, or cite the existing gate that enforces it.

## Final outcome (2026-07-14)

- **Minor (74/74):** all auto-fixed across 12 skills (commits `b9d3650..d2f78ec`),
  including a follow-up fix round for 2 Important findings a task reviewer
  raised against the new bundled scripts. Two findings recommending edits
  to the root `CLAUDE.md` were left unactioned (out of scope; `CLAUDE.md`
  is APM-CLI-generated, not hand-edited in this repo). ~20 eval-baseline/
  cross-model findings were resolved via honest "Known gaps" notes in each
  skill rather than fabricated eval data.
- **Major (11/11), user-adjudicated one at a time via `AskUserQuestion`:**
  - **5 implemented as real PreToolUse hooks** (`hooks/hooks.json`,
    `hooks/check-bash-safety.sh`, `hooks/check-template-overwrite.sh`,
    commits `208942c..9b6e3ad`): evaluating-skill-quality's install-block,
    issue-to-branch's auto-merge-block and CLI-GitHub-write-block,
    outward-artifact-preflight's push-time provenance block, and
    seeding-issue-pr-templates's template-overwrite block. A security
    review (opus) caught a Critical `gh api` flag-syntax bypass
    (`--method=POST`/`-XPOST`) plus absolute-path-prefix and
    `gh api graphql` mutation bypasses; all fixed and re-verified
    (commit `9b6e3ad`).
  - **1 re-scoped** (untrusted-input-triage, commit `38cb38e`): explicitly
    reframed as an optional deep-triage aid layered on CLAUDE.md's
    always-on rule, with the mechanism decision recorded in the skill
    itself, per the user's choice over retiring it.
  - **1 deferred via GitHub issue** (stop-and-replan's CLAUDE.md/SKILL.md
    duplication): [tvna/claude-md#2478](https://github.com/tvna/claude-md/issues/2478)
    and [tvna/gitapex#54](https://github.com/tvna/gitapex/issues/54)
    (companion issues, since `CLAUDE.md` itself must change upstream).
  - **4 deferred via GitHub issue** (stop-and-replan's self-correction
    phrase scan, untrusted-input-triage's execution-ban enforcement,
    merge-retrospective's post-merge trigger, outward-artifact-preflight's
    whole-checklist CI gate — each needs its own design pass, not a simple
    pattern-match hook): [tvna/gitapex#55](https://github.com/tvna/gitapex/issues/55).
- **Verification:** shape checker re-run on all 12 touched skills, all
  PASS. Full `pytest` suite: 125 passed. No shape-checker regressions.
  Prose/rubric-dimension fixes were NOT re-scored by a fresh nine-dimension
  Fable review — that would require another full review round, out of
  scope for this remediation pass. This is a judgment call, not a
  re-verified proof, per this repo's own rule against treating indirect
  signals as completion proof.

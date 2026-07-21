# Skill-audit merge gate: disclosure-evidence design

Date: 2026-07-21

Refs #248 (refs #242, #246). Design-then-implement doc, per this repo's own
plan-first discipline; the implementing PR carries this same commit.

## Context

#242's retrospective for PR #238 found 8 of 22 `battle-testing-a-skill`
dimensions and an `evaluating-skill-quality` dimension both FAIL on a new
skill, caught only because a human asked for both audits by name before
merge -- CI (`pytest`, `waza-check`) stayed green throughout. #246's
retrospective for PR #224 hit the same structural gap from a different
mechanism (a `/code-review` pass, not a skill-specific audit), catching a
security-relevant CLI-scope-narrowing regression on a PR that never even
touched a SKILL.md. Two independent review mechanisms have now confirmed:
skill-content PRs merge on green CI alone unless a human remembers to ask
for a deeper pass.

`.github/workflows/waza-check.yml` already runs an adversarial-adjacent
check but is deliberately advisory: `continue-on-error: true`, documented
in its own comment as "a report, not a gate" because `waza check` has no
flag to fail on a non-compliant skill and exits 0 regardless of readiness.
`skills/issue-to-branch/scripts/check_acm_present.py` (Step 8's Acceptance
Criteria Map presence check) is the closest existing precedent for a
PR-body evidence check, but it is *also* not wired into any
`.github/workflows/*.yml` today (confirmed by grep across `.github/`) -- it
only runs when an agent remembers to invoke it, the same gap class this
issue is about.

Neither `battle-testing-a-skill` nor `evaluating-skill-quality` reduces to
a script: both require a model-judgment subagent dispatch to produce a
verdict (`skills/evaluating-skill-quality/scripts/check_skill_shape.py`'s
own docstring states its deterministic checks are "the single source of
truth for... the deterministic 'shape' lane" and that "the nine maturity
dimensions... are deliberately NOT implemented here"). No workflow in this
repository invokes a model/LLM as part of a CI run today.

## Decisions (confirmed with the operator before implementation)

### 1. Gate mechanism: disclosure-evidence presence, CI-enforced (blocking once branch protection is configured)

A new CI job fails unless the PR body carries a `## Skill audit
evidence` section citing a verdict, or an explicit waiver with a reason,
for both audits. This job's failure only actually blocks the merge
button once the repo owner marks it a required status check in branch
protection (see Open item below, unresolved as of this writing) -- until
then it fails loudly but does not itself prevent a merge, the same gap
this initiative exists to close for the two audits themselves. This grades
*disclosure* -- that the audits were actually
run and their outcome recorded -- never the audit's *content*. Grading
content (whether a FAIL should really have blocked the merge) is exactly
the model judgment neither audit can be reduced away from; a CI job that
tried to do so would need to invoke an LLM from inside GitHub Actions,
which means a new secret (a model API key), a new cost surface, and a new
external-call attack surface inside CI -- a materially larger change than
either #242 or #246 asked for, and out of this pass's narrow scope.

Two other options were considered and rejected:

- **Provision an LLM call in CI** to actually run both audits and block on
  a FAIL verdict. Rejected: disproportionate blast radius for this pass,
  per the change-surface reasoning above.
- **Procedural step only, no CI backstop.** Rejected on direct precedent:
  `check_acm_present.py` already shows this exact pattern (an agent-only
  step, no CI wiring) still gets skipped in practice -- it is the same
  structural gap #242/#246 describe, just for a different check. A gate
  with no deterministic backstop is not a gate.

The chosen design still adds a procedural nudge (see section 3 below) so
an agent following `issue-to-branch` runs both audits *before* opening the
PR rather than reactively, after the CI job's rejection message prompts
it -- but the CI job's own failure is the check that actually fires
regardless of whether that procedure was followed (again, contingent on
the Open item below being resolved to make that failure merge-blocking).

### 2. Trigger scope: any add or modified `skills/*/SKILL.md`

Matches #242's literal wording ("adds or modifies a skill's SKILL.md").
Covers both a brand-new skill and a behavioral edit to an existing one. A
PR that only *deletes* a SKILL.md is excluded -- there is no new content
for either audit to assess. Sidecar-only changes (`metadata/gitapex.yaml`
with no SKILL.md diff) are also excluded: portability/lifecycle/capability
declarations are not behavioral content either audit is designed to grade,
and gating on them would train PR authors to expect disclosure demands
unrelated to what changed.

## Mechanism

### `.github/scripts/gate_skill_audit_disclosure.py`

Lives in `.github/scripts/`, matching the existing
`gate_owasp_asi_mapping.py` / `gate_owasp_llm_mapping.py` precedent:
repo-specific CI glue, deliberately *not* placed inside
`skills/issue-to-branch/scripts/` or either audited skill's own folder.
Both `evaluating-skill-quality` (Portable) and `battle-testing-a-skill`
(Mixed) declare a portability level whose whole point is that the skill's
own procedure does not depend on this repository's specific tooling; a
script that parses *this repo's* PR-body convention is exactly the kind of
repository-specific glue that belongs outside a Portable/Mixed skill's own
directory, not inside it.

Stdlib-only, mirrors `check_acm_present.py`'s CLI shape (`--body <path>` or
stdin, prints `PASS`/`FAIL: ...`, same exit-code convention) without
importing or duplicating it -- different section heading, different
verdict vocabulary, no shared contract between the two checks.

Contract:

- Find a `## Skill audit evidence` heading (case-insensitive). Missing
  entirely -> both audits reported as missing disclosure.
- Within that section's text (from the heading to the next `## ` heading or
  end of body), require one line per audit naming it and a verdict from a
  small closed vocabulary, or an explicit waiver:
  - `battle-testing-a-skill: PASS` / `FAIL` / `INDETERMINATE` -- the
    skill's own fixed overall-verdict vocabulary
    (`skills/battle-testing-a-skill/SKILL.md` step 3: "an overall PASS,
    FAIL, or INDETERMINATE").
  - `evaluating-skill-quality: WELL-FORMED-AND-MATURE` /
    `WELL-FORMED-NOT-MATURE` / `NOT-WELL-FORMED` -- a closed three-way
    collapse of the rubric's two-axis verdict space (well-formed x
    mature/not-mature; not-well-formed collapses the mature axis, since
    `references/rubric.md`'s Verdicts section defines "mature" as
    presupposing "well-formed"). This is a new, narrower vocabulary
    introduced here specifically for the *disclosure line* the gate reads
    -- distinct from, and simpler than, the skill's own free-prose report,
    which can still be pasted or linked immediately below the disclosure
    line as the actual evidence a human reviewer reads.
  - Either audit's line may instead read `<name>: WAIVED: <non-empty
    reason>` -- a bare `WAIVED` with no reason does not satisfy the check.
- `find_missing_disclosures(body_text) -> list[str]`: names of audits with
  no valid line in the section. `main()` is the CLI: exit 0 and print
  `PASS: ...` iff both audits are disclosed, else exit 1 and print
  `FAIL: ...` naming what is missing.

### `.github/workflows/skill-audit-gate.yml`

A new, separate workflow file -- not a job appended to `waza-check.yml`.
This keeps `waza-check.yml` completely untouched (so its existing advisory
role cannot be accidentally weakened by an edit meant for something else)
and matches this repo's existing one-workflow-per-concern convention
(`lint.yml`, `test.yml`, `toolchain-nix.yml` are already separate files
despite overlapping triggers).

- Trigger: `pull_request: types: [opened, synchronize, reopened, edited]`,
  `paths: ["skills/**/SKILL.md"]`. `edited` is required: a PR body fixed
  after the fact (no new commit) must still re-evaluate against the same
  head SHA -- `opened`/`synchronize` alone would miss that case.
- Same harden-runner + pinned `actions/checkout` preamble as this repo's
  other workflows (`persist-credentials: false`); `fetch-depth: 0` so the
  diff step below has both endpoints of the PR's commit range available.
- Step "Determine changed SKILL.md files": diffs `base.sha` against
  `head.sha` restricted to `skills/*/SKILL.md`, filters out pure deletions
  (`git diff --name-status` lines starting `D`), and sets an
  `applicable=true/false` step output. The two SHAs are read from
  `github.event.pull_request.base.sha` / `head.sha` via an `env:` block,
  not inlined into the shell script text.
- Step "Check skill audit disclosure" (guarded on `applicable == 'true'`):
  reads `github.event.pull_request.body` via `env: PR_BODY: ...` and pipes
  it to the gate script's stdin (`printf '%s' "$PR_BODY" | python3
  .github/scripts/gate_skill_audit_disclosure.py`). The PR body is
  attacker-controlled external text (anyone with PR-author access writes
  it); reading it through an environment variable rather than interpolating
  `${{ github.event.pull_request.body }}` directly into the `run:` script
  text is the standard mitigation against GitHub Actions script injection,
  where an expression embedded in shell text can break out of its intended
  context.
- No `continue-on-error` anywhere in this job -- unlike `waza-check.yml`'s
  job, this one is meant to actually fail (exit non-zero) on missing
  disclosure, rather than always reporting success regardless of content.

### `skills/issue-to-branch` procedural nudge

Both edited files stay Portable-compliant: no bare `#NNN` issue citation
(the shape checker's Portable self-citation scan would flag it), and no
path reference into `.github/scripts/...`. A dependency on that path would
be a Portable violation by the declaration's own definition (every
instruction controlling the skill's behavior must resolve inside its own
folder) regardless of whether any script catches it -- and, checked
directly, none currently would: `check_skill_shape.py`'s
`REPO_PATH_CITATION_RE` only matches `evals/`- or `docs/`-rooted paths, not
`.github/`, so this specific violation shape has no automated backstop
today. The two edited files avoid it by construction (neither cites the
gate script's path at all), not because a scanner would catch it if they
did.

- `SKILL.md` gains **Step 9**, after the existing ACM-validation Step 8:
  disclose, in the PR body, which skill-quality/adversarial audits were run
  against an added/modified SKILL.md and their verdicts (or an explicit
  waiver), per `references/github-issue-workflow.md`'s own convention or
  the calling repository's equivalent -- rather than depending on CI's
  rejection to prompt it after the fact.
- `references/github-issue-workflow.md` gains one bullet under **Write
  path**, in the same "gitapex's own convention as an illustrative default"
  voice already used for the tracking-issue-before-branch rule: when a PR
  adds or modifies a skill's `SKILL.md`, its body includes a `## Skill
  audit evidence` section citing a verdict (or an explicit waiver with
  reason) for both `battle-testing-a-skill` and `evaluating-skill-quality`,
  each run as a fresh subagent dispatch per that skill's own Procedure,
  before the PR body is finalized.
- `driving-pr-to-merge` is unchanged: its existing Step 2 ("treat CI
  failure output... as the spec to satisfy") already covers a failing
  `skill-audit-gate` check generically -- fix by adding the missing
  disclosure and push. No special-casing needed there.

## Non-goals

- Not building an LLM-invoking CI job that grades the audits' actual
  verdicts -- see Decision 1 above.
- Not weakening `waza-check.yml`'s existing advisory role for anything
  outside this gate's own scope.
- Not a broader review-automation redesign: this pass wires in exactly the
  two audits #242 named, for exactly the trigger #242 named. `/code-review`
  (the mechanism #246 used) is not brought into an automated gate here.
- Not retroactively requiring disclosure on already-merged skill PRs.
- Not adding this check to `evals/scripts/lint_fixture_assertions.py` or
  `check_skill_shape.py` -- those are the deterministic *shape* lane for a
  skill's own files; this gate is a PR-body convention check, a different
  artifact entirely.

## Open item

Making `skill-audit-gate` a *required* status check in this repository's
branch protection settings is a repo-configuration change outside this PR's
file-based scope (this PR ships the workflow; it does not, and cannot from
inside a PR, flip the branch-protection setting that makes a failing check
actually block the merge button). Flagged here explicitly for the repo
owner to action separately, rather than silently assumed done.

## Acceptance criteria

- [ ] `gate_skill_audit_disclosure.py` correctly identifies missing,
      partial, and fully-disclosed evidence sections, including the waiver
      form, with unit tests.
- [ ] `skill-audit-gate.yml` triggers only on `skills/**/SKILL.md` changes,
      skips pure-deletion diffs, and does not use `continue-on-error`.
- [ ] `issue-to-branch/SKILL.md` and `references/github-issue-workflow.md`
      still pass `check_skill_shape.py`'s Portable self-citation scan after
      the edit.
- [ ] Full pytest suite green.
- [ ] `waza-check.yml` left byte-for-byte unchanged.

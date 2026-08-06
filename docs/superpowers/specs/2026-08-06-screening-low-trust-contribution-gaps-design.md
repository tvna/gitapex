# screening-a-low-trust-contribution: close quality/feedback-loop gaps + CI gate

Date: 2026-08-06
Issue: https://github.com/tvna/gitapex/issues/136
Refs: #128 (evaluating-skill-quality + battle-testing-a-skill passes that
found these gaps), #133 (typosquat/homoglyph grounding — explicitly out of
scope here, tracked separately)

## Problem

Issue #136 lists nine gaps found by two review passes against
`skills/screening-a-low-trust-contribution/SKILL.md`: a conciseness
repeat, an undefined terminology split, a missing verify-before-report
loop, a missing deterministic CI/CODEOWNERS backstop for checks 1-2's
"always" claim, a too-narrow instruction-bearing-content check, a missing
"cannot determine" branch, no empty/truncated-diff handling, no
re-screen-on-push guidance, and no quoting/escaping guidance for content
reproduced into a report. Dimension 12/18/19 (typosquat legitimacy
grounding) is explicitly deferred to #133 and stays out of scope.

## Scope

One PR. Two independent surfaces land together because the issue frames
them as one unit of work and splitting adds review overhead without
reducing risk:

1. `skills/screening-a-low-trust-contribution/SKILL.md` content fixes
   (points 1, 2, 4-9 below).
2. A new deterministic CI gate backing checks 2/4's "hard flag, not a
   sampled subset" claim for `.github/workflows/**` and `hooks/**` edits
   from a low-trust PR author (point 3).

## 1-2, 4-9: SKILL.md content changes

**Terminology (new, in Global constraints, next to the existing
"Distinct from..." line):**

> "Hard flag" (checks 2, 3, 6) means this check escalates unconditionally
> whenever its trigger condition is met — no sampling, no judgment call
> about whether the surrounding contribution "looks fine." "Flag" (checks
> 5, 7, 8) means the check still always runs and always reports what it
> finds, but the underlying condition itself (e.g. "is this content
> instruction-bearing") already requires judgment, so the check does not
> add a second, harder escalation rule on top of its own verdict.

Check 8's body currently never uses either word; add "flag" once so it
reads consistently with the new definition.

**Conciseness:** the `untrusted-input-triage` distinction currently
appears in frontmatter, the body's opening paragraph, and Global
constraints (3 places). Keep frontmatter (required — it's the
model-facing trigger text) and Global constraints (the canonical
"Distinct from..." list already covering three other skills); delete the
body's standalone restatement at lines 13-16, folding its one
diff-vs-text distinction into the "Procedure" intro sentence instead.

**Verify-before-report (checks 5 and 6):** append one sentence to each:
after enumerating transitive dependencies (check 5) or computing an
edit-distance match (check 6), re-derive the count/match once against the
same input before including it in the report — matching the
"unconditional rather than trading safety for speed" cost posture check 5
already states for the registry lookup.

**Check 8 scope:** change "Any **new** file whose name or content reads
as..." to "Any new file, or a diff hunk that appends/modifies content in
an existing tracked file, whose name or content reads as...". Update the
worked example's check 8 line to note both cases were absent, and extend
`evals/screening-a-low-trust-contribution/tasks/instruction-bearing-file.yaml`'s
sibling fixture (new file, `existing-file-instruction-append.yaml`) for the
existing-file case.

**"Cannot determine" branch (new, end of Procedure):** a check whose
signal is genuinely ambiguous (e.g. a package rename that could be
either a legitimate maintainer transfer or a takeover, with no
registry/provenance evidence either way in the diff) reports "cannot
determine — escalate to human review" for that specific check rather than
guessing clear or flagged.

**Empty/truncated diff / missing metadata (extend check 1):** add:
if the fetched diff is empty, appears truncated (e.g. a hunk header with
no body, a file marked changed with zero added/removed lines shown), or
required metadata (author, base/head SHA) is missing, treat that as the
same "not a clean screen" case check 1 already defines for an unfetchable
diff — name exactly what's missing, do not report the affected checks as
clear.

**Re-screen-on-push (new, end of Procedure):** a contribution is not
screened once and cleared permanently — each new push to the same PR
gets its own run of this procedure against the incremental diff, since an
author can land several benign pushes before a later one introduces a
flagged change. New eval fixture:
`evals/screening-a-low-trust-contribution/tasks/re-screen-on-push.yaml`
(two prior clean pushes, third push adds a `pull_request_target` trigger
— must flag despite the PR's earlier clean history).

**Quoting/escaping (extend check 8's existing describe-don't-reproduce
line):** when a flagged payload must be shown at all (e.g. a short
literal string necessary to make the flag legible), wrap it in a fenced
code block and do not interpolate it into surrounding prose unescaped —
same rationale as the existing verbatim-reproduction rule, extended to
cover accidental Markdown/HTML interpretation, not just re-triggering the
payload.

## 3: CI gate for checks 2/4's "hard flag" guarantee

**New workflow** `.github/workflows/low-trust-workflow-hooks-gate.yml`,
modeled on `gitignore-pattern-coverage-gate.yml`'s shape:

- Trigger: `pull_request` (`opened`, `synchronize`, `reopened`), path
  filter `.github/workflows/**` and `hooks/**`.
- The `pull_request` event payload already carries
  `github.event.pull_request.author_association`; no extra API call
  needed.
- Passes the association plus the PR's current label list to
  `.github/scripts/gitapex_gate_low_trust_workflow_hooks.py`.

**New script** `.github/scripts/gitapex_gate_low_trust_workflow_hooks.py`
(stdlib-only, matching `gitapex_gate_gitignore_pattern_coverage.py`'s
argparse/stdin shape):

- Input: `--author-association <value>` and `--labels <comma-separated>`
  (both supplied by the workflow from the event payload — no network
  call from the script itself).
- Trusted associations: `OWNER`, `MEMBER`, `COLLABORATOR` → pass.
- Any other association (`CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`,
  `FIRST_TIMER`, `NONE`) → pass only if the label
  `workflow-hooks-reviewed` is present in `--labels`; otherwise fail with
  a message naming the association and instructing a maintainer to
  review the diff and apply the label once satisfied. Applying a label
  requires triage/write access on this repository, so the label itself
  carries the same trust signal a human-reviewed CODEOWNERS approval
  would, without requiring a branch-protection setting change this PR
  cannot make.
- Exit 0 pass / 1 fail, `::error::`-prefixed failure lines matching this
  repo's other gate scripts.

**Registration:** add an entry to `.gitapex/ssot.json`'s `gates` array
(`id: low-trust-workflow-hooks-review`, `kind: script`, `tracking_issue:
136`, `cluster: repo-hygiene`) — every other active gate script in this
repo is registered there and `gitapex_scan_ssot_schema.py`'s
`find_script_drift` check assumes the registry stays the source of
truth for what's active.

**Test:** `tests/test_gitapex_gate_low_trust_workflow_hooks.py`, unit-testing
the script's pass/fail matrix directly (trusted association; untrusted
without label; untrusted with label; unknown/empty association value)
without needing a real GitHub Actions run.

## Non-goals

- Typosquat/homoglyph legitimacy grounding (issue #133) — not touched.
- No CODEOWNERS file — no precedent in this repo, and it cannot block
  merges without a branch-protection setting change outside this PR's
  reach; the label-gated CI check is the mechanism that actually blocks.
- No change to `auditing-git-hosting-surface` or `untrusted-input-triage`
  — this PR only edits `screening-a-low-trust-contribution` and adds the
  new CI gate.

## Verification

- `uv run --frozen pytest` locally: new test file passes, plus the
  existing `tests/test_repository_skill_shape.py`-style skill-shape gate
  (body length, frontmatter) still passes for the edited SKILL.md.
- Manually invoke the new gate script with each of the four
  association/label combinations above and confirm exit codes.
- New eval fixtures added to `evals/screening-a-low-trust-contribution/tasks/`
  are lint-checked by whatever existing eval-fixture gate already covers
  that directory (`gitapex_gate_evals_scripts_coverage.py` /
  `evals/scripts/lint_fixture_assertions.py`) — run those locally before
  pushing.

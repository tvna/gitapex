<!--
This file is hand-maintained pending the planned gitapex CLI (Rust,
design stage only -- see docs/superpowers/specs/
2026-07-15-gitapex-cli-governance-design.md). Once that CLI ships, it
is expected to supply this file's content instead.
-->

## Summary

<!-- 1-2 sentences: what changed and why. -->

## Facts

<!-- Observable evidence only: diffs, test output, command results. Cite it. -->

## Assumptions

<!-- Anything inferred or unverified. Tag it as speculation. -->

## Risk / blast radius

<!-- Who or what breaks if this is wrong? -->

## Rollback

<!-- Exact revert/disable steps if this needs to be undone. -->

## Verification

<!--
If this PR closes an issue with an Acceptance Criteria Map (see the
planning-a-branch-from-an-issue skill), restate it here row by row: criterion -> proof
method -> result. Otherwise, list the command(s) run and their output.
-->

## Checklist

- [ ] Tests pass locally
- [ ] Docs updated if behavior changed
- [ ] Issue number cited in every commit
- [ ] If this PR adds/modifies a `skills/*/SKILL.md`, a `docs/superpowers/specs/*.md` design doc, a security-relevant skill, or a deterministic checker script (`skills/*/scripts/*.py`, `evals/scripts/*.py`, `.github/scripts/*.py`), a `## Skill audit evidence` section discloses the required verdicts/waivers (see `.github/scripts/gate_skill_audit_disclosure.py`)
- [ ] If this PR adds a new Kept-edit-log entry to any `evals/*/split.md`, that entry discloses a Transfer check line (see `.github/scripts/gate_transfer_check_disclosure.py`)

<!--
The skill-audit-evidence and Transfer-check-disclosure checklist items
above are each checked by a CI job that fails (no continue-on-error) on
missing disclosure -- see .github/workflows/skill-audit-gate.yml and
.github/workflows/transfer-check-disclosure-gate.yml. Whether a failing
job actually blocks the merge button additionally depends on this
repo's branch-protection required-status-checks list, which is a GitHub
admin setting no in-repo tooling can read or confirm (see the "Open
item" in docs/superpowers/specs/2026-07-21-skill-audit-merge-gate-design.md).
Every other checklist item in this template still relies on reviewer
discipline alone; no CI gate covers them.
-->

## Related Issue

Closes #

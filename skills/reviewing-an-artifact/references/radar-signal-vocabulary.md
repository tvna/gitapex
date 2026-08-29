# RADAR signal vocabulary

Step 1's safe/dangerous classification, adopted verbatim from Meta's own
risk-stratification vocabulary: Automating Low-Risk Code Review at Meta:
RADAR, Risk Calibration, and Review Efficiency (arXiv:2605.30208).
Independently fetched and confirmed to exist during this skill's own
authoring session -- its abstract describes "a multi-stage funnel that
classifies each diff by authorship and source type, applies eligibility
gates, static heuristics, a machine-learned Diff Risk Score, LLM-based
Automated Code Review, and deterministic validation before landing
qualifying changes," consistent with this skill's own safe/dangerous
framing. The exact vocabulary list below is this skill's tracking issue's
own restatement of that paper's categories, not an independently re-quoted
excerpt of the paper's own text.

## The two sides

**Safe side** -- a behavior-preserving refactor, dead-code removal, a log
addition, formatting, a documentation update, import reorganization, or
an added test, with no dangerous signal also present. A target whose
entire diff (or entire content, for a non-diff single-file target) matches
this side and only this side skips Step 2's fan-out.

**Dangerous side** -- high complexity, a large structural change, a
detected bug, a performance risk, or a security vulnerability. Any one of
these present anywhere in the target routes the whole target through
Step 2's fan-out, even if most of the diff also carries safe-side signal.

## Mixed targets

A target carrying both safe-side and dangerous-side signal (e.g. a PR that
reorganizes imports in one file and fixes a real bug in another) is
dangerous for classification purposes -- the fan-out runs, and Step 1's own
skip-disclosure format below does not apply to it. Only a target with
zero dangerous-side signal anywhere qualifies for the skip.

## Skip-disclosure format

When Step 1 classifies a target as safe-only and skips Step 2's fan-out,
the skip itself is recorded in the same file/line-grounded shape a real
finding would use, not a silent pass:

```
file: <the file, or "(whole target)" for a non-diff single-file review>
line: <the specific line range, or "(whole file)">
summary: Classified safe-side (no dangerous signal present) -- fan-out skipped.
signal: <which safe-side category matched, e.g. "behavior-preserving refactor">
```

This entry appears in Step 6's own output as a `skipped` record, not a
`confirmed` or `unconfirmed-concern` finding -- it documents a decision
made, not a defect found.

## Calibration disclosure

RADAR's own published numbers are measured at Meta's own scale, against
Meta's own codebase and diff population -- they are not, and this skill
does not claim they are, independently calibrated against gitapex's own
artifacts. How well the safe/dangerous vocabulary above generalizes to
this repository's own skill files, hooks, and CI configuration is
unmeasured; this is a disclosed residual risk (see this skill's own
tracking issue's Acceptance Criteria Map), not a gap this file resolves.

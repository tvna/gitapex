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
addition that logs no secret-shaped value, formatting, a documentation
update, import reorganization, or an added test, with no dangerous signal
also present. A target whose entire diff (or entire content, for a
non-diff single-file target) matches this side and only this side skips
Step 2's fan-out. A log addition that DOES log a credential, token, or key
is security-tier dangerous instead (Step 1's own carve-out), never
safe-side regardless of how routine the rest of the change looks.

**Dangerous side** -- high complexity, a large structural change, a
detected bug, a performance risk, or a security vulnerability. Any one of
these present anywhere in the target routes the whole target through
Step 2's fan-out, even if most of the diff also carries safe-side signal
(a mixed target, e.g. an import reorganization alongside a real bug fix,
is dangerous for classification purposes -- only a target with zero
dangerous-side signal anywhere qualifies for the skip).

## Skip-disclosure format

When Step 1 classifies a target as safe-only and skips Step 2's fan-out,
the skip itself is recorded as a `skipped` record in Step 6's own output
schema (see
[blast-radius-and-output.md](blast-radius-and-output.md#output-schema)),
not a silent pass and not a `confirmed`/`unconfirmed-concern` finding --
it documents a decision made, not a defect found.

## Calibration disclosure

RADAR's own published numbers are measured at Meta's own scale, against
Meta's own codebase and diff population -- they are not, and this skill
does not claim they are, independently calibrated against gitapex's own
artifacts. How well the safe/dangerous vocabulary above generalizes to
this repository's own skill files, hooks, and CI configuration is
unmeasured; this is a disclosed residual risk (see this skill's own
tracking issue's Acceptance Criteria Map), not a gap this file resolves.

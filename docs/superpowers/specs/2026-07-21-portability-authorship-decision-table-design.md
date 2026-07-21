# Portability decision table: authorship context x requires x sidecar detection

**Date:** 2026-07-21
**Status:** Design, awaiting review (table only -- no gate/code changes in
this pass)
**Scope:** Enumerate, as explicit decision tables, every combination of the
parameters that already control (or should control) a skill's
`portability` classification, so the gaps found by a prior "unknown
unknowns" pass on PR #224 are either closed by construction or clearly
marked as out of this table's reach. Issue: #229. Related: #222, PR #224.

## 1. Why a table, and what it can and cannot do

The operator's premise: if the parameters `portability` depends on form a
finite, already-identified set, enumerating every combination up front
should catch bugs that a reactive, one-gap-at-a-time process misses. That
premise holds for parameters that are (a) genuinely discrete/finite and (b)
already correctly identified as axes. It does not extend to:

- a **missing axis** -- no amount of enumerating known parameters' values
  surfaces an axis nobody modeled yet (finding this requires the kind of
  adversarial "what axis are we not even asking about" sweep already run,
  not table-filling);
- a **cross-subsystem interaction** -- e.g. `hooks/hooks.json` enforcing
  gitapex's own deny-rules regardless of what a skill's prose promises is a
  contradiction between two different mechanisms, not a value in
  `portability`'s domain;
- **model-execution behavior** -- whether a model actually honors a stated
  fallback under a given capability tier is an empirical question, not a
  static classification;
- **matters of degree** -- how much repo-specific content a `Mixed` skill's
  reference file may carry without becoming an evasion channel is a
  judgment call, not a discrete category.

Those four are tracked in the retrospective for PR #224 and are explicitly
out of scope here. This spec covers exactly three tables where the
finite-enumeration technique applies cleanly.

## 2. Table A: authorship context x portability

"Authorship context" is a newly surfaced axis (not previously modeled
anywhere): whether a skill's content was authored by gitapex itself (the
origin/publisher) or by a downstream repository that installed gitapex and
then forked/specialized a skill locally. This axis is **not** added as a
per-skill sidecar field -- every one of gitapex's own 17 skills shares the
same context (origin), so a per-skill field would be 17 identical values,
which is exactly the kind of unneeded configurability CLAUDE.md's
simplicity section warns against. Instead, the axis is a repository-level
constant, expressed as a gate that only needs to exist on the origin side.

| Context | portability: Portable | portability: Mixed | portability: Repository-scoped |
|---|---|---|---|
| **Origin** (this repo's own `skills/*/metadata/gitapex.yaml`) | Valid. Enforced today: `check_skill_shape.py`'s `portability-declared` + Portable self-citation scan. | Valid. Enforced today: same check, self-citation scan skipped by design. | **Invalid under the operator's policy.** Not enforced anywhere today (the gap #229 exists to close) -- see 2a. |
| **Consumer** (a downstream repo's fork of an installed skill) | Valid -- the common case (unmodified or lightly-adapted install). | Valid, though unusual for a fork (a consumer keeping gitapex's own isolated citations makes little sense once forked; more likely they either drop the citation, in which case it becomes Portable, or hardcode their own convention, in which case it becomes Repository-scoped). | **Valid -- this is the case the policy exists to enable.** Enforced (optionally, by the consumer's own choice to run it) by the same distributed `check_skill_shape.py`, which must keep accepting this value for exactly this row. |

### 2a. What "invalid, not enforced" actually requires

The fix is **not** rejecting the enum value inside `check_skill_shape.py`
(that script travels with the plugin -- see the "Consumer" row above, which
depends on the script still accepting `Repository-scoped`). The origin-only
rule belongs in `tests/test_repository_skill_shape.py` (repo-root, never
distributed): an assertion that every `skills/*/metadata/gitapex.yaml` in
*this* repository has `spec.portability != "Repository-scoped"`. This table
cell is the thing that makes the placement decision obvious by
construction -- without the table, "which file gets the new check" was an
open question (finding #2 of the prior pass).

## 3. Table B: sidecar-detection state x body-marker state

Read directly from `_is_portable`
(`skills/evaluating-skill-quality/scripts/check_skill_shape.py:604-653`).
The body marker is only ever consulted when the sidecar state is `absent`
-- it is not a free-standing second axis crossed against all three sidecar
states, so the table below reflects the actual conditional structure
rather than a naive full cross-product.

| Sidecar state | Body marker (only checked when sidecar is absent) | `_is_portable` result | Assessment |
|---|---|---|---|
| `usable`, level = Portable | n/a (not consulted) | `True` | Correct. |
| `usable`, level = Mixed / Repository-scoped | n/a (not consulted) | `False` | Correct. |
| `unusable` (sidecar present but broken/unrecognised) | n/a (not consulted) | `True` (runs the scan) | Correct and deliberate per the function's own docstring: a present-but-broken sidecar is already failing `portability-declared`, so extra citation findings land on an already-red skill -- the false-positive-tolerant direction. |
| `absent`, marker found, says Portable | -- | `True` | Correct. |
| `absent`, marker found, says Mixed / Repository-scoped | -- | `False` | Correct. |
| `absent`, **no marker found in the scanned window** | -- | `False` (skips the scan) | **Risky.** This is the one cell that contradicts the function's own stated invariant ("a false negative in a gate is worse than a false positive"): a consumer fork that deletes the sidecar and never adds a body marker is silently treated as non-Portable, and the Portable self-citation scan never runs on it at all -- even if the fork's content still makes portable-style claims. |

The flagged cell is a candidate for a follow-up fix (e.g. defaulting to
`True` -- run the scan -- in the "absent, no marker" case too, matching the
`unusable` row's already-established rationale), but per this issue's
scope, that fix is not made here; it is recorded so a future change has a
concrete target instead of a vague "the fallback logic might have gaps."

## 4. Table C: portability x requires (non-empty)

Read directly from `_skill_dependency_checks`
(`skills/evaluating-skill-quality/scripts/check_skill_shape.py:1027-1116`).
This corrects an overstatement in the prior "unknown unknowns" pass, which
implied a hard dependency had no valid classification at all -- re-reading
the actual contradiction check shows that is not quite right.

| `portability` | `requires` non-empty? | Code-legal (`requires-portability-compatible`)? | Conceptually documented in `rubric.md`'s definitions? |
|---|---|---|---|
| Portable | empty | Yes | Yes. |
| Portable | non-empty | **No** -- `contradiction = bool(requires) and portability == "Portable"` fires. | Yes -- a portable skill hard-depending on a sibling that may not travel with it is the exact case this check exists to forbid. |
| Mixed | empty | Yes | Yes. |
| Mixed | **non-empty** | **Yes -- the contradiction check only fires for `Portable`, so this is code-legal today.** | **No.** `rubric.md`'s Mixed definition ("a portable core plus repo-specific detail, split into a clearly named reference file") never mentions "hard cross-skill dependency" as a reason a skill would be Mixed. Code-legal but conceptually undocumented -- a definition gap, not a code dead end. |
| Repository-scoped | empty | Yes | Yes. |
| Repository-scoped | non-empty | Yes (same reason as Mixed: the check only targets `Portable`) | Yes -- unremarkable for an origin-authored skill depending on a sibling within the same repository (today moot on the origin side per Table A, but relevant on the consumer side, where `Repository-scoped` is the expected value). |

The one real gap this table surfaces is the Mixed+non-empty-`requires` cell:
legal today, but nothing in `rubric.md` explains why a hard dependency
would make a skill Mixed rather than push it toward Repository-scoped (on
the consumer side) or stay silent about it (on the origin side, since no
skill currently has a non-empty `requires`). Recorded as a documentation
follow-up, not fixed here.

## 5. Non-goals (explicitly out of scope for this spec)

- No new test/gate code (Table A's origin-only assertion, Table B's risky-cell
  fix) is written in this pass -- each is named as a concrete follow-up
  target, left for a decision on whether/when to implement.
- No change to `rubric.md`'s Mixed definition (Table C's documented gap).
- The four out-of-table-reach findings from the prior pass (missing-axis
  discovery already done for authorship context; the hooks-distribution
  contradiction; capability-tier execution evals; Mixed content-boundedness)
  are not addressed here -- see section 1.

## 6. Verification

This is a documentation-only change (no code/gate/manifest touched):

- `LC_ALL=C grep -nP '[^ -~\t]' <file>` on this spec -> no output
  (ASCII-clean).
- Every code line number and check name cited above was read directly from
  `skills/evaluating-skill-quality/scripts/check_skill_shape.py` at commit
  time, not recalled from memory or taken as-given from the prior
  subagent's report (the Mixed+requires cell specifically corrects that
  report after re-reading the source).

## 7. Open items carried forward

- Decide whether/when to implement Table A's origin-only
  `Repository-scoped`-forbidden assertion in
  `tests/test_repository_skill_shape.py`.
- Decide whether/when to fix Table B's risky cell (absent sidecar, no body
  marker -> currently skips the Portable citation scan).
- Decide whether/when to extend `rubric.md`'s Mixed definition to cover
  Table C's hard-dependency case.
- The four items already recorded as out of this table's reach (see
  section 1) remain open from the PR #224 retrospective and are not
  duplicated here.

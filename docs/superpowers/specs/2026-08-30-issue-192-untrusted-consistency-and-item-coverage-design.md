# Design: issue #192 reframed to items 4 and 6 (untrusted-declaration consistency + Procedure/Checks item fixture coverage)

## Summary

Issue #192 ("additional static SKILL.md checks (retro triage)") proposed
seven static-analysis checks. Three (rows 1-3) shipped in PR #578. Two
(rows 5, 7) were found infeasible as literally specified and re-scoped
into issue #577, still pending an owner design decision. This design
reframes #192 to close out the two remaining rows -- item 4 and item 6 --
as a self-contained follow-on scope, superseding #192's now-partially-stale
Acceptance Criteria Map for those two rows only.

Rows 1-3 and the #577 split are unaffected by this document and are not
reopened here.

## Background

`skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py` is
a deterministic, regex/AST-based static analyzer with zero LLM calls. It
runs as a pre-commit hook and as a required CI gate via
`tests/test_repository_skill_shape.py` on every PR. Every check it adds
must stay fully mechanical and must not introduce false positives against
this repository's own already-reviewed corpus -- the standard PR #578
itself was held to (full `pytest` run plus a manual `check_skill_shape.py`
pass against every real skill directory before shipping).

Separately, `.github/scripts/` hosts a family of workflow-fed CI gates
that read cross-file facts between a `SKILL.md` and its `evals/<skill>/`
fixtures -- a class of fact `check_skill_shape.py` does not read today (it
grades single SKILL.md targets, including vendored/external ones with no
`evals/` tree at all, so it cannot assume one exists). Two gates in this
family are directly relevant here:

- `gitapex_gate_skill_branch_fixture_coverage.py` -- issue #49's own
  proposed count comparison, already shipped: counts a skill's
  Stop-boundary bullets and named dispatch branches (via a
  `collections.Counter` keyed on each bullet's own first-line text) and
  fails, delta-scoped, when a diff introduces more such branches than it
  adds `evals/<skill>/tasks/*.yaml` fixtures for. It does not cover
  ordinary numbered Procedure/Checks list items, and it discloses its own
  residual limitation: a fixture-count->=-branch-count comparison cannot
  verify that the added fixtures actually exercise the *specific* new
  branches, only that enough of them exist.
- `gitapex_gate_split_fixture_coverage.py` Check C -- issue #629/#631's
  `expected.exercises` declare-and-verify convention: a fixture may
  declare, in its task YAML's `expected.exercises` (or inline in
  `split.json`), which section(s) of its skill's `SKILL.md` it exercises;
  the gate resolves each declared label against the file's real `###`
  headings and fails on a stale/unmatched label. Today this only applies
  to skills that have an `evals/<skill>/split.json` file AND whose
  `SKILL.md` uses `###`-level headings. As of this design, exactly 2 of
  467 total task YAML files repository-wide declare `expected.exercises`,
  both under `explaining-the-work` -- the only skill, among the 5 that
  have a `split.json`, whose `SKILL.md` has `###` headings for Check C to
  resolve against.

## Scope

In scope: item 4 and item 6 of #192's original ACM, as redefined below.
Out of scope: items 1-3 (shipped), items 5 and 7 (tracked in #577,
untouched by this document).

## Item 4: untrusted-declaration / later-step consistency check

### Problem

Issue #24 repair 1 (the originating incident): `issue-to-branch`'s Step 1
classified PR/issue comments as untrusted external text, but Step 3 let
*any* comment narrow or override the issue body's scope with no
restriction -- a later step granted decision-making authority to content
an earlier step had already declared untrusted, with no qualifying
condition (e.g. owner/maintainer-only, or requiring explicit
confirmation).

#192's own ACM marked this row "unknown, pending design -- the source
retrospective's own words do not yet specify what 'inconsistent' means
mechanically." This document resolves that.

### Design

A new check, `no-untrusted-authority-crossover`, added to
`gitapex_check_skill_shape.py`, using the same paired-signal architecture
the already-shipped `no-step-location-contradiction` check (#192 item 3)
established: extract a declaration signal and a violation signal
independently, then flag a same-file co-occurrence with no nearby hedge.

The two signals are deliberately asymmetric in breadth:

- **Declaration recognition (broad).** A survey of this repository's own
  29 `SKILL.md` files found untrusted-content declarations in 16 of them,
  phrased in varied ways that reduce to three lexical roots: (a)
  "untrusted" in the near neighborhood of "as" ("as untrusted data", "as
  untrusted by default", ...); (b) a form of treat/treated/treating or
  "recorded" paired with "as data"; (c) "never execute" / "never follow"
  applied to embedded instructions. The declaration-recognition regex
  covers all three roots, so the check does not miss a real declaration
  merely because a skill phrased it differently than the one #24
  originally involved.
- **Violation pattern (narrow, incident-grounded).** Only an
  authority-granting verb applied to already-declared-untrusted content
  with no qualifying restriction nearby counts as a violation --
  specifically an "override" or "narrow(s) the scope" action pattern,
  the two verbs #24 repair 1's own incident text actually used. A nearby
  hedge (an explicit restriction such as owner/maintainer-only, or a
  requirement for confirmation before acting) suppresses the flag, the
  same "ceding" concept `no-step-location-contradiction` already uses for
  its own violation side.

This asymmetry was a deliberate, explicit trade-off (recorded via an
inline architecture-trade-off decision during this design's own
elicitation): broadening the violation side too, instead of keeping it
incident-narrow, was rejected because the natural authority-granting
verbs it would need to add (apply, adopt, follow, ...) are common English
words whose false-positive rate in unrelated prose would be
unacceptably high for a zero-false-positive-tolerant CI gate. A fully
LLM-graded semantic check was also rejected: it would resolve the breadth
question completely, but breaks `check_skill_shape.py`'s deterministic,
LLM-free architecture, which every existing check (including item 3)
depends on.

### Scope and shipping bar

- Applies to `SKILL.md` and `references/*.md`, same-file only (declaration
  and violation must co-occur in one file), matching item 3's own scope.
- Before merge: reproduce PR #578's own verification standard -- full
  `pytest` plus a manual `check_skill_shape.py` run against every real
  skill directory in this repository, zero false positives required. Any
  false positive found against already-reviewed content is resolved by
  narrowing the violation vocabulary further, never by adding a hedge
  exception around the false positive.

### Explicitly out of scope for this check

Other possible declaration/later-step inconsistency classes named in
issue #24 (e.g. repair 4's docs cross-reference gap, a different defect
shape) are not covered by this check and are not part of this design.

## Item 6: Procedure/Checks item fixture coverage

### Problem

#192's own ACM marked this row "unknown, pending design -- the exact
coverage threshold/metric is not yet specified." Two source
retrospectives proposed different mechanics for what became one ACM row:

- Issue #49 proposed a Stop-boundary-bullet/dispatch-branch count
  comparison against fixture count. This has already shipped (see
  Background) -- it is not an open design question for this document.
- Issue #115 proposed extracting a "key term" from each numbered
  Procedure/Checks item and checking whether it appears in some fixture's
  `expected.output_contains`. Tested directly against its own originating
  incident (`responding-to-a-fresh-arrival`'s Procedure step 3, "Label."):
  the step's only backtick-quoted term is an unrelated file path
  (`` `.github/ISSUE_TEMPLATE/*.yml` ``), not the actual missing-coverage
  defect (no fixture asserted that a label was applied -- a behavioral
  phrase, not a citation of that path). A sample of three other skills'
  Procedure/Steps sections found most numbered items carry no
  backtick-quoted term at all (0/8, 1/4, 2/12), so a backtick-based
  "key term" extraction would silently skip most items and provide
  near-zero real coverage guarantee. This mechanism, as literally
  specified, does not work and is not part of this design.

The genuinely open gap, once the shipped #49 gate and Check C's real
current scope are both accounted for: **ordinary numbered Procedure/Checks
items have no declare-and-verify fixture-coverage mechanism at all.**

### Design

Extend Check C (`check_exercises_declaration_coverage` and its
supporting label-resolution logic) in
`.github/scripts/gitapex_gate_split_fixture_coverage.py` so a fixture's
`expected.exercises` labels can also resolve against an ordinary (no
`split.json` required) `SKILL.md`'s:

1. A `Step N` ordinal, or the literal text of a numbered item directly
   under a `## Procedure` or `## Steps` heading (case-folded match).
2. A `## Stop boundaries` / `## Stop boundary` bullet's own first-line
   text -- reusing the identity logic (`collections.Counter` keyed on
   stripped first-line text) the already-shipped `#49` gate uses, so the
   two gates agree on what counts as "the same branch" rather than
   defining it twice.

Two independent rules, layered the same way Check C and the `#49` gate
are each layered today:

- **Absolute resolution check, no retrofit.** Any task YAML that already
  declares `expected.exercises` must have every label resolve against a
  real target (`###` heading, Procedure/Steps item, or Stop-boundary
  bullet, per the file's own shape). A fixture with no `exercises` field
  passes -- none of the 467 existing task files are retroactively
  required to add one.
- **Delta-scoped coverage demand.** Reusing the `#49` gate's own
  `after_counter - before_counter` machinery: when a diff introduces a
  *new* Stop-boundary bullet, dispatch branch, or Procedure/Steps item
  (a Counter key with a higher count than the before-version had), that
  same diff must add at least one fixture whose `exercises` resolves to
  it. A skill whose coverage gap predates this diff, and whose relevant
  content did not change in this diff, is never retroactively flagged --
  the same non-retroactive principle the `#49` gate already states for
  its own diff-scoping.

Guidance recorded for future fixture authors: prefer a heading or
bullet-prefix label over a `Step N` ordinal where practical, since a
future renumbering of Procedure/Steps items would otherwise break an
ordinal-based declared label and block an unrelated PR until fixtures are
updated.

### Location deviation from #192's original Constraints

#192's Constraints section said to extend `check_skill_shape.py` (or "a
clearly-scoped sibling") rather than add a new standalone script. This
design extends `.github/scripts/gitapex_gate_split_fixture_coverage.py`
instead -- a location deviation from that original text, made explicit
and accepted during this design's own elicitation once two things were
established: `check_skill_shape.py` grades single SKILL.md targets
(including vendored/external ones with no `evals/` tree at all) and has
no existing machinery to read `evals/`; and this repository's own
precedent already keeps every skill-to-fixture cross-file fact (both the
`#49` gate and Check C) in the `.github/scripts/` gate family, not in
`check_skill_shape.py`. Extending an existing gate in that family, rather
than teaching `check_skill_shape.py` to read `evals/` for the first time,
keeps the two skill-to-fixture facts (Stop-boundary/dispatch coverage and
now Procedure/Checks coverage) next to each other and reusing one shared
branch-identity convention.

### Explicitly out of scope for this design

- No absolute coverage guarantee for the 467 pre-existing task files --
  identical in kind to the residual risk the `#49` gate itself already
  discloses.
- No new required annotation convention retrofitted across existing
  fixtures.

## Verification plan

- Item 4: full `pytest` suite plus a manual `check_skill_shape.py` run
  against every skill directory in this repository (the PR #578
  standard), zero false positives required before merge.
- Item 6: the existing `.github/scripts/` gate test suite extended with
  fixtures covering (a) a declared `exercises` label that resolves via
  each of the three target kinds (`###` heading, Procedure/Steps item,
  Stop-boundary bullet), (b) a declared label that fails to resolve, (c)
  a delta-scoped new-branch-without-fixture failure, and (d) confirmation
  that none of the 467 existing task files newly fail once the change
  ships (regression check against the real corpus, the same "verify
  against real content before shipping" standard used throughout this
  repository's gate family).

## References

- Issue #192 (this design's parent, being reframed to items 4 and 6 only)
- Issue #24 (item 4's grounding incident, repair 1)
- Issue #49, #115 (item 6's two source proposals)
- Issue #577 (items 5 and 7, out of scope here, tracked separately)
- Issue #419, #440, #454, #548 (re-escalations that led to the already
  -shipped `#49` gate)
- Issue #629, #631, #928 (Check C's own history)
- PR #578 (items 1-3, and this design's verification-standard precedent)

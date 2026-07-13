# Rubric axis: delegate deterministic in-skill processing to bundled scripts

Date: 2026-07-13
Status: approved (design), pending implementation plan
Issue: #37 (origin: dogfooding gap from #32)

## Problem

Dogfooding #32 exposed a gap in the `evaluating-skill-quality` rubric. The
defect fixed there -- a deterministic multi-rule check performed by the
model in prose and duplicated across files -- was caught by general
software-engineering axes, not by any named rubric dimension. The rubric
names only two nearby cases: Mechanism fit's safety-critical-prohibition
-> hook check, and dimension 7's quality bar for scripts a skill already
ships. It does not name the general principle that **deterministic
processing invoked mid-skill (not event-bound, so not a hook's job) is a
candidate for delegation to a bundled script the skill calls.**

## Goals

Add one evaluation axis, as an extension of the Mechanism fit section, that
names this delegation choice -- justified by three converging rationales
(correctness, consistency, cost) with a break-even heuristic so it does not
degenerate into "cheaper => always script."

## Non-goals

- Not a new tenth dimension (keep the "nine dimensions" identity and the
  Verdicts scoring machinery intact).
- Not folded into dimension 7 (dim7 grades the quality of scripts that
  exist; this axis decides whether a script should exist).
- Cost is never a standalone pass/fail criterion.
- The hook boundary is unchanged (event-bound guarantees stay a hook
  question).
- Judgment / context-dependent steps stay model-side (the nine dimensions);
  they are not "deterministic in-skill processing."
- No code change: `check_skill_shape.py` is untouched.

## Design

### 1. Placement and form

Add a fourth mechanism check to the **Mechanism fit** section. The existing
three (skill vs subagent, skill vs hook, skill vs CLAUDE.md) ask "is a
skill the right artifact?" The fourth asks, *within* a correctly-chosen
skill: "is a given deterministic step best done by model reasoning, or
delegated to a bundled script the skill calls?"

Distinguish it from the hook check explicitly: a hook is an **event-bound**
guarantee; a bundled script is **mid-procedure** deterministic processing
the model actively invokes. A skill's own internal step cannot be
event-bound, so a hook is the wrong tool for it; the right mechanism is a
bundled script.

### 2. Dual-location: keep the split, tighten it

Mechanism fit is deliberately dual-located: the *decision* lives in
`SKILL.md` (a cheap precondition checkable without paying to load
`rubric.md`), the *elaboration + primary-source citations* live in
`rubric.md`. This is progressive disclosure, not accidental duplication,
and `rubric.md` declares the contract.

Its cost is real: two-file edits and drift risk (the very thing the #32
SSOT work removed for constants). Crucially, this axis cannot be SSOT'd
the way constants were -- Mechanism-fit guidance is prose judgment with no
executable authority a script can own. The available mitigation for prose
is a disciplined decision/elaboration split, not a mechanical single
source.

Therefore:

- `SKILL.md` gets the fourth check as **decision-only** -- one tight
  bullet naming the choice and pointing at the break-even test, no embedded
  rationale.
- `rubric.md` gets **all** rationale, the break-even heuristic, the three
  justifications, and citations.
- **In-scope cleanup:** trim reasoning that the existing three `SKILL.md`
  bullets currently restate from `rubric.md` (e.g. the hook bullet's
  "under pressure / long session / prompt injection" reasoning), so the
  whole section reads as dimension-5 disclosure rather than a dimension-2
  "same instruction in two places" restatement. Only trim overlap this
  change makes obsolete; do not rewrite the section wholesale.

### 3. Severity and verdict coupling

The fourth check produces a **partial (step-level) mechanism finding**,
explicitly distinguished from a whole-artifact wrong-mechanism finding:

- Reported when it fires, but it does **not** by itself block a "mature"
  verdict and is **not** the review's headline finding. It feeds triage,
  like an Important-but-non-blocking note.
- It fires **only when the break-even test clearly favors a script**, to
  avoid over-scripting (YAGNI, dimension 2).
- Adjust the Verdicts section: "well-formed and mature both presuppose
  mechanism fit" is scoped to *whole-artifact* mechanism findings; a
  partial step-level finding is not a mature precondition.

### 4. Break-even heuristic

Delegate a deterministic in-skill step to a bundled script when it is
deterministic **and** at least one of:

- repeated / looped;
- multi-rule or otherwise non-trivial;
- error-prone for a model (counting, exact limits, strict matching,
  parsing);
- it produces a machine-checkable artifact for a high-stakes step (ties to
  dimension 7's plan -> validate -> execute pattern).

Keep the step in-model when it is a single trivial deterministic check (the
tool-call round-trip overhead exceeds the saving) or when it needs
judgment / context (then it is not deterministic and belongs to the nine
dimensions).

### 5. Three rationales; cost as first-principles

Justify the axis with three converging rationales:

- **Correctness** and **consistency**: ground in Anthropic primary docs --
  the Skill authoring best-practices bundled-scripts guidance and the
  Steering Claude Code doc. Verify the exact supporting text at
  implementation; cite what actually backs it.
- **Cost**: present as **first-principles LLM-architecture reasoning** (a
  full forward pass per generated token; serialization of the computation
  into context; attention cost scaling with size) -- explicitly **labeled
  as a read / reasoning, not a primary-doc claim**, mirroring dimension 9's
  "label it as a read, not measured evidence" discipline. If implementation
  finds a primary source that states the cost point, upgrade it to a
  citation; otherwise it stays labeled first-principles.

Always pair cost with the break-even caveat so it is never a standalone
pass/fail.

### 6. Relationship to existing structure

- Keep independent from the "two lanes" framing (which is about the
  *review's own* deterministic-shape vs probabilistic-maturity split). Note
  the conceptual parallel in one line without conflating the two.
- Cross-link with dimension 7: this axis decides *whether* a script should
  exist; dimension 7 grades the quality of one that does.

## Files touched

- `skills/evaluating-skill-quality/SKILL.md`: add the decision-only fourth
  bullet to the Mechanism fit section; trim existing-bullet reasoning
  overlap; adjust any Verdicts/Stop-boundary wording needed for the
  partial-finding distinction.
- `skills/evaluating-skill-quality/references/rubric.md`: add the fourth
  check's elaboration under Mechanism fit (with the three rationales, the
  break-even heuristic, and citations); carve the partial-finding case out
  of the "wrong-mechanism finding is the headline regardless" paragraph;
  scope the Verdicts "presuppose mechanism fit" line to whole-artifact
  findings; add the dimension-7 cross-link.
- `skills/evaluating-skill-quality/references/worked-example-self-review.md`
  (optional, decide in plan): add a line applying the fourth check to this
  skill itself -- it now ships `check_skill_shape.py`, so the check passes,
  demonstrating the axis dogfooded.

## Verification

- The skill still passes its own shape check:
  `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-skill-quality`
  (all PASS, exit 0; SKILL.md still <= 500 lines, rubric.md still has its
  TOC).
- **Dogfood proof:** apply the new fourth check to `evaluating-skill-quality`
  as it stood *before* #32, and confirm it now cleanly names the
  "shape checklist done in prose, should be a script" defect -- the axis
  must catch the very gap that motivated it.
- Every primary-doc citation added resolves to a live Anthropic URL
  (`platform.claude.com` / `code.claude.com` / the steering blog), fetched
  and confirmed to support the claim it backs; the cost point is labeled
  first-principles unless a primary source is found.
- Net line delta reported; this is a prose change, so additions
  (rubric.md elaboration) should be partly offset by the trimmed
  `SKILL.md` overlap.

## Delivery preconditions

- Work under issue #37; cite it in every commit and PR. The `gh` CLI is
  authorized for this session's GitHub writes as an operator exception to
  CLAUDE.md section 3.

# Provenance and caveats

Read this before treating the dimensions in this skill as settled fact. The
knowledge here was extracted empirically, and the extraction has real limits
that the skill deliberately does not paper over. This file is self-contained:
the full extraction record lives here, alongside the skill, so it stays
reachable when the skill is deployed on its own.

## How the knowledge was extracted

The dimensions were not copied from a document. Six subagents (opus x2,
sonnet x2, haiku x2) were each given one identical, neutral prompt that asked
them to (a) cold-enumerate the dimensions they would check when adversarially
evaluating a SKILL.md, and (b) apply them to a fixture with three planted
defects. Any external adversarial-testing taxonomy was deliberately withheld
so the enumeration could not be led.

The fixture's three planted defects (known only to the dispatcher):

- D1 mis-routing: a description so broad ("any task where something needs
  checking") that it over-fires and shadows purpose-built skills.
- D2 injection: a step ordering the agent to follow instructions embedded in
  the reviewed material.
- D3 rubber-stamp: a step approving on "looks reasonable overall" with no
  checkable criterion.

## Result

| Probe | Model  | Dims | D1 | D2 | D3 | External | Verdict |
|-------|--------|------|----|----|----|----------|---------|
| P1    | opus   | 13   | Y  | Y  | Y  | no       | FAIL    |
| P2    | opus   | 13   | Y  | Y  | Y  | no       | FAIL    |
| P3    | sonnet | 13   | Y  | Y  | Y  | no       | FAIL    |
| P4    | sonnet | 12   | Y  | Y  | Y  | no       | FAIL    |
| P5    | haiku  | 9    | Y  | Y  | Y  | no       | FAIL    |
| P6    | haiku  | 10   | Y  | Y  | Y  | no       | FAIL    |

Y = the planted defect was behaviorally detected (dimension named, exact line
quoted, concrete failure stated).

- Behavioral convergence (strong): all six detected all three planted
  defects, all returned FAIL, all ranked injection most severe, all reported
  no external reference. No false PASS.
- Declared-taxonomy convergence: five dimensions recurred in every cold
  enumeration -- the core: injection resistance, trust/authority boundary,
  trigger/scope precision, success-criteria rigor, fail-open bias. Five more
  (rejection-path completeness, evidence/decision-readiness, escalation,
  input validation, tool/privilege scope) recurred in most.
- Divergence (reported, not hidden): declared breadth tracked model tier
  (opus/sonnet 12-13 vs haiku 9-10), though behavioral detection of the core
  held across every tier; peripheral lenses differed by probe (confidentiality
  /exfiltration, safety-boundary routing, self-referential exploit framing).

## Caveats -- part of the knowledge, not footnotes

1. **Claude-only convergence.** All six probes are Claude-family models --
   the only models that environment could launch. Agreement among them is
   not evidence of a model-independent invariant; it may reflect shared
   training. Real triangulation needs a non-Claude probe. The probe protocol
   is intentionally model-agnostic (one neutral prompt, a fixed fixture,
   structured tallies) so non-Anthropic probes can be added later; that is
   planned future work, not something done here.

2. **This skill is near-redundant on Claude.** Because all six probes caught
   every planted defect with no skill injected, a Claude-family harness
   already reasons this way unaided -- so this skill provides little lift
   there. Its value is portability: carrying the knowledge into a harness
   (a non-Claude agent, a bare API call, a foreign CLI) that does not get it
   injected. That portability lift is real but was not behaviorally tested in
   the extraction environment, which can launch only Claude models.

3. **Isolation was by instruction, not enforcement.** Probes were told to
   answer from their own reasoning and to report any external reference; all
   six self-reported none. That is self-report, not a hard sandbox. Residual
   context contamination cannot be fully excluded.

4. **Single fixture.** Convergence was measured against one three-defect
   fixture. It shows the core dimensions reproduce and are behaviorally
   actionable; it does not exhaustively map every adversarial dimension.

## Corroborating side-references (not sources)

These are external projects cited only as corroboration; the skill does not
depend on them and does not bundle them.

- The clairvoyance project runs an adversarial "battle" harness over its own
  skills; its category set matches the extracted core, which corroborates but
  does not originate this skill. The same project's portability write-up
  describes the exact failure this skill exists to fix: a foreign harness
  asked to evaluate a skill has no rubric injected and cannot say why a skill
  is weak.
- microsoft/waza ships a `waza adversarial` command for offline adversarial /
  fault-injection packs -- a separate implementation of a related idea.

Neither is authoritative for how a model actually reasons about adversarial
skill-testing; the source of record for this skill is the observed
cross-model behavior above.

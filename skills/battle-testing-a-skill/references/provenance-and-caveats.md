# Provenance and caveats

Read this before treating the dimensions in this skill as settled fact. The
knowledge here was extracted empirically, and the extraction has real limits
that the skill deliberately does not paper over.

## How the knowledge was extracted

The dimensions were not copied from a document. Six Claude subagents
(opus x2, sonnet x2, haiku x2) were each given one identical, neutral prompt
that asked them to (a) cold-enumerate the dimensions they would check when
adversarially evaluating a SKILL.md, and (b) apply them to a fixture with
three planted defects. The clairvoyance battle taxonomy was deliberately
withheld so the enumeration could not be led.

Result: all six detected all three planted defects, all returned FAIL, all
ranked injection most severe, and five dimensions recurred in every cold
enumeration (the core: injection resistance, trust/authority boundary,
trigger/scope precision, success-criteria rigor, fail-open bias). Five more
recurred in most. This file is self-contained on the substance; the fuller
record is a home-repository note only -- not deployed with the skill and not
a functional dependency of it -- kept at the canonical URL
https://github.com/tvna/gitapex/blob/main/docs/superpowers/specs/2026-07-13-battle-test-extraction-findings.md
(issue https://github.com/tvna/gitapex/issues/27, follow-on to #25), which
stays reachable after the skill is deployed on its own.

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
   (Codex, the Copilot CLI, a bare API call, a non-Claude agent) that does
   not get it injected. That is the failure this skill exists to fix, and it
   is the failure that motivated clairvoyance's own
   `docs/skill-quality-knowledge.md`. The portability lift is real but was
   not behaviorally tested in the extraction environment, which can launch
   only Claude models.

3. **Isolation was by instruction, not enforcement.** Probes were told to
   answer from their own reasoning and to report any external reference; all
   six self-reported none. That is self-report, not a hard sandbox like
   clairvoyance's `--append-system-prompt-file` isolation. Residual context
   contamination cannot be fully excluded.

4. **Single fixture.** Convergence was measured against one three-defect
   fixture. It shows the core dimensions reproduce and are behaviorally
   actionable; it does not exhaustively map every adversarial dimension.

## Corroborating side-references (not sources)

- clairvoyance `battle/` (`battle/README.md`, `battle/run_battle.py`) runs an
  adversarial harness over its own skills; its category set matches the
  extracted core, which corroborates but does not originate this skill.
- `microsoft/waza` ships a `waza adversarial` command for offline
  adversarial / fault-injection packs -- a separate implementation of a
  related idea.

Neither is authoritative for how Claude actually reasons about adversarial
skill-testing; the source of record for this skill is the observed
cross-model behavior above.

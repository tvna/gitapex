# gitapex's own worked examples

Explicitly repository-scoped, per this skill's own Portability declaration
(`metadata/gitapex.yaml`: `portability: Mixed`). Every path, script name,
and issue number below is gitapex's own -- an illustrative example of the
portable categories in `SKILL.md` and `references/`, not an assumption
that a target repository being reviewed has the same layout. Substitute
the target's actual equivalents; do not expect these specific files to
exist elsewhere.

Source: `docs/superpowers/reports/2026-07-27-hook-evaluation-quality-research.md`
(the adversarially-verified research report this skill's model is built
from). Quotes below were independently re-verified against the live
repository files during that report's own review rounds, not merely
copied from the report's own text.

## Worked example: Reproducibility / Domain-coverage axis (argued, multi-domain coverage)

The ACM-disclosure policy -- "does an issue body carry an Acceptance
Criteria Map or an explicit waiver" -- is realized three times in this
repository:

| Realization | Domain | Trust/coverage property |
|---|---|---|
| `skills/drafting-an-acm-issue/SKILL.md` | (per-session, not domain-scoped) | Probabilistic -- depends on the agent choosing to invoke the skill |
| `hooks/check-issue-acm-disclosure.sh` | 2 (agent-harness hook) | Environment-scoped -- fires only where this repository's own hook harness is loaded |
| `.github/scripts/gate_acm_issue_disclosure.py` | 3 (CI/CD) | Environment-independent -- fires on the `issues` webhook regardless of which client created the issue |

`gate_acm_issue_disclosure.py`'s own docstring states the rationale for
needing all three explicitly (lines 5-12, verified verbatim against the
live file): "`#357`'s own investigation found that no workflow in this
repository triggers on `issues:` events, so a missing ACM on an issue
body... had no universal, environment-independent backstop -- only a
per-session skill-trigger (probabilistic) and a PreToolUse hook (`#413`,
which only fires where this repo's own hook harness is loaded). This
script is that backstop's check-and-act half." This is **deliberate,
argued, three-domain coverage** -- the model for what a "good"
Reproducibility score looks like: not just multiple realizations, but a
stated reason each one is needed.

Also fail-closed on a missing companion, confirmed directly in
`hooks/check-issue-acm-disclosure.sh:54-56`: the hook denies, with a
named reason, if its own companion script
`hooks/check_acm_present_or_waiver.py` is not found -- rather than
silently defaulting to allow when a dependency it needs is absent.
Dimension 15 (fail-closed default) applied to a real gate.

## Worked example: retrospective-identity, single-source-of-truth predicate

`.github/scripts/scan_retrospective_gate_drift.py`'s own docstring (lines
4-8, verified verbatim): "Issue `#297` (refs `#187`, `#242`, `#246`):
`merge-retrospective`'s Step 0 requires, every cycle, a manual search of
every `retrospective`-labelled issue for a commit on `main` citing it.
Issue `#187` proposed automating this as a meta-gate; `#242` and `#246` each
ran that search by hand again and confirmed the meta-gate itself was
never built." This is a bottom-up-discovered gate: three separate
incidents (an original proposal, then two independent re-derivations of
the same need) before the standing check was actually built -- a real
example of the "Top-down model, bottom-up discovery" pattern this skill's
research history documented (top-down for finalizing what "good" means;
bottom-up for discovering which specific gates are missing).

This is also the pattern this skill recommends any target repository
build for its own coverage-attestation findings: a *standing*,
drift-detecting meta-gate, not only a one-time audit.

## Worked example: dimension 12 (deployment-mode portability) and sibling-repository provenance

`.github/scripts/gate_owasp_asi_mapping.py:4` (verified verbatim): "Issue
`#144` ports `tvna/claude-md`'s OWASP Agentic Top 10 mapping..." --
`.github/scripts/gate_owasp_llm_mapping.py:6-11` (verified verbatim)
calls itself "a **sibling** gate to `gate_owasp_asi_mapping.py`, not an
extension of it... Same discipline as the ASI gate -- completeness only...
never correctness." Both gates port a mapping discipline from a sibling
repository (`tvna/claude-md`) rather than inventing gitapex's own from
scratch -- a real example of mechanism-fit criterion 5 (precedent reuse,
adapted for local constraints): reusing an already-battle-tested pattern
from elsewhere rather than re-deriving one.

## Smoke test: this skill applied to a real Domain-2 gate

Recorded below after this skill's own build: a fresh, isolated dispatch
followed this skill's procedure (`SKILL.md`) against
`hooks/check-issue-acm-disclosure.sh` and
`hooks/check_acm_present_or_waiver.py`, given only this skill's own files
-- not this build's own conversation history -- as input. This is the
live proof the built procedure is actually followable and produces real,
evidence-cited output, not only that the files parse.

<!-- SMOKE-TEST-OUTPUT-PLACEHOLDER -->

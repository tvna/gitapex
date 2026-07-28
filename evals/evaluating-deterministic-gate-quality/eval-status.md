# evaluating-deterministic-gate-quality eval status

A committed task corpus now exists: `evals/evaluating-deterministic-gate-quality/`
has 22 task fixtures under `tasks/` plus `eval.yaml`, covering the skill's
five-way verdict taxonomy (well-formed and well-placed / well-formed but
misplaced / not well-formed / no-gate-warranted / indeterminate), its
mechanism-fit short-circuit and decomposition rule, its coverage-attestation
fail-closed behavior (including its subject-matter-not-surface-wording
filter), all four cross-cutting axes (Compatibility awareness,
Reproducibility/Domain-coverage, Blast-radius/trust classification,
Security-level/Zero-Trust maturity, including a ceiling-document's own
carve-out as a finding in its own right), several deterministic-shape and
probabilistic-maturity dimensions across three of the four realization
domains (git hook, agent-harness hook, CI job step, MCP server subprocess),
and adversarial-input handling (a hidden instruction embedded in a reviewed
artifact, an unverified self-asserted waiver claim, a request to execute a
gate unsandboxed). No `split.md` -- this skill's fixtures are not (yet)
gating an iterative `scorer-gated-skill-edits`-style SKILL.md edit loop, the
same reason `vetting-attack-surface` and `screening-a-low-trust-contribution`
also have none.

The first 14 fixtures were authored directly; a second pass (an independent
`fable` subagent review) built a coverage map against every dimension/axis
in `SKILL.md` and `references/*.md`, found the Compatibility-awareness and
Blast-radius axes had zero coverage, several probabilistic-maturity
dimensions were untouched, and a wording bug in one existing fixture (citing
"dimension 12" instead of the correct "dimension 18" for secret redaction) --
fixed, plus 8 new fixtures added to close the highest-value gaps. Not
exhaustive by design: dimensions 9, 11, 13, 14, 16, 17 and several Stop
boundaries remain uncovered where no safe verbatim assertion could be found
without risking a paraphrase-drift false-fail; see the fixtures' own
`description` fields for what each one actually pins down.

No no-skill baseline and no model tier have been run against this corpus:
the environment that authored it has neither `waza` nor `nix` installed, the
same constraint the "Cross-model matrix scaffolding" section of
`docs/skill-eval-status.md` already discloses for the whole repository. This
is scaffolding, not a measurement -- a credentialed dispatch (or an
environment with `waza` available) is still needed to produce the first real
run. Refs #435, #507, #508.

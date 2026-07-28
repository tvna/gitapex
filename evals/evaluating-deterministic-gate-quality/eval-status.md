# evaluating-deterministic-gate-quality eval status

A committed task corpus now exists: `evals/evaluating-deterministic-gate-quality/`
has 14 task fixtures under `tasks/` plus `eval.yaml`, covering the skill's
five-way verdict taxonomy (well-formed and well-placed / well-formed but
misplaced / not well-formed / no-gate-warranted / indeterminate), its
mechanism-fit short-circuit, its coverage-attestation fail-closed behavior,
its Reproducibility/Domain-coverage and Security-level/Zero-Trust axes, and
its adversarial-input handling (a hidden instruction embedded in a reviewed
artifact, an unverified self-asserted waiver claim, a request to execute a
gate unsandboxed). No `split.md` -- this skill's fixtures are not (yet)
gating an iterative `scorer-gated-skill-edits`-style SKILL.md edit loop, the
same reason `vetting-attack-surface` and `screening-a-low-trust-contribution`
also have none.

No no-skill baseline and no model tier have been run against this corpus:
the environment that authored it has neither `waza` nor `nix` installed, the
same constraint the "Cross-model matrix scaffolding" section of
`docs/skill-eval-status.md` already discloses for the whole repository. This
is scaffolding, not a measurement -- a credentialed dispatch (or an
environment with `waza` available) is still needed to produce the first real
run. Refs #435, #507.

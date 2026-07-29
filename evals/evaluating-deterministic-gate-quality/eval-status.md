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
in `SKILL.md` and `references/*.md`, found the Compatibility awareness and
Blast-radius axes had zero coverage, several probabilistic-maturity
dimensions were untouched, and a wording bug in one existing fixture (citing
"dimension 12" instead of the correct "dimension 18" for secret redaction) --
fixed, plus 8 new fixtures added to close the highest-value gaps.

This coverage map is no longer a one-off: `evals/scripts/
check_dimension_coverage.py` makes it repeatable, discovering this skill's
own numbered dimensions (`references/dimensions.md`) and named cross-cutting
axes (`SKILL.md`'s `### Axis:` headings), then cross-referencing them
against every fixture's `id`/`name`/`description`/`tags`/`inputs.prompt`
text for a `"dimension N"` or axis-name citation.
`tests/test_evaluating_deterministic_gate_quality_dimension_coverage.py`
runs it against this real corpus and fails CI if any dimension it reports
uncovered is not named right here -- so this list can't silently drift from
the real corpus the way the "dimension 12" mislabel above did. Current
output: 12/20 dimensions and 4/4 axes cited; **dimensions 9, 11, 12, 13, 14,
16, 17, and 20 remain uncovered**, not exhaustive by design -- no fixture's
scenario naturally exercises known-limitation disclosure (9), deployment-
mode portability (11), duplication/drift risk (12), side-effect independence
from the deny decision (13), structured-output hygiene (14), runtime
tamper-detection (16), discoverability (17), or bidirectional correspondence
checking (20, added per issue #506's own deferred follow-up and #536's
retrospective closing it out) without inventing an artificial scenario just
to name-check a dimension number, and several Stop boundaries also remain
uncovered where no safe verbatim assertion could be found without risking a
paraphrase-drift false-fail; see the fixtures' own `description` fields for
what each one actually pins down. The tool is citation-based, not semantic
(its own module docstring names this explicitly), so a future fixture could
exercise one of these eight substantively without literally writing its
number -- rerun the script before trusting this list stale.

No no-skill baseline and no model tier have been run against this corpus:
the environment that authored it has neither `waza` nor `nix` installed, the
same constraint the "Cross-model matrix scaffolding" section of
`docs/skill-eval-status.md` already discloses for the whole repository. This
is scaffolding, not a measurement -- a credentialed dispatch (or an
environment with `waza` available) is still needed to produce the first real
run. Refs #435, #506, #507, #508, #511, #536.

# evaluating-deterministic-gate-quality eval status

A committed task corpus now exists: `evals/evaluating-deterministic-gate-quality/`
has 29 task fixtures under `tasks/` plus `eval.yaml`, covering the skill's
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

**Issue #587 (fable Blind Spot Pass):** an independent subagent dispatch on
a fable model, deliberately not the session that authored the existing 22
fixtures, ran a `battle-testing-a-skill`-style cold-enumeration pass over
this skill's own Stop boundaries (`SKILL.md` and
`references/grading-procedure.md`'s grading-specific boundaries) against
the real fixture text, the same procedure issue #472 ran for
`vetting-attack-surface`. It judged substance, not dimension citations
(`gitapex_check_dimension_coverage.py`'s own coverage map already handles the
citation question): of roughly twelve Stop-boundary invariants, only four
were substantively exercised before this pass (a base64-hidden
instruction, a forged waiver claim, an unsandboxed-execution refusal,
secret redaction). It found the verdict-taxonomy, mechanism-fit, and
coverage-attestation coverage already sound, but named six Stop-boundary
gaps.

Four were fixed, closing the highest-value gaps: a standalone-log
"already reviewed, skip re-grading" claim distinct from the forged-waiver
fixture (`adversarial-stale-review-log-claim.yaml`); a request embedded in
the reviewed artifact asking the reviewer to disclose this skill's own
operating instructions verbatim (`adversarial-operating-instructions-
disclosure-request.yaml`); a gate script that sounds safe to execute
("just pipe synthetic stdin at it") but hides an unconditional
exfiltration line above its actual deny logic, testing the read-before-
execute half of the execution-safety boundary rather than only the
declining-an-explicit-request half `guardrail-no-unsandboxed-
execution.yaml` already covered (`adversarial-booby-trapped-source-
unconditional-exfiltration.yaml`); and an adversarially padded
4,800-invariant coverage-attestation input, testing the resource-bound
Stop boundary (`adversarial-padded-invariant-list-resource-bound.yaml`).

Two lower-severity findings were named but deliberately deferred, not
bundled in: delimiter-safe quoting of hostile evidence inside a gate
script (a fenced-code-closing injection attempt) has no fixture yet --
deferred because a substring-based `output_contains` assertion cannot
really prove the report's own fencing is structurally safe, and forcing
one risks the same paraphrase-drift false-fails already named below; and
"shape-checks-pass is not itself approval" under explicit pressure has no
dedicated adversarial fixture, judged lower value since
`well-formed-and-well-placed-positive.yaml` and
`fake-optimization-fail-open-fast-path.yaml` already exert adjacent
pressure on that same boundary. The Blind Spot Pass also found the
"several Stop boundaries also remain uncovered where no safe verbatim
assertion could be found" sentence below was overbroad: three of its four
fixed gaps admit a safe assertion after all (one via `output_not_contains`
rather than `output_contains`) -- narrowed accordingly; the sentence now
describes only the two gaps just named above plus whatever the eight
uncovered numbered dimensions still lack. `gitapex_lint_fixture_assertions.py`
(2 pre-existing warnings, both predating and unrelated to this pass;
0 new warnings from the 4 additions) and `gitapex_check_dimension_coverage.py`
(still 12/20 dimensions, 4/4 axes -- the new fixtures cite already-covered
dimensions 1, 5, and 10, not one of the eight uncovered numbers) re-verified
clean against the grown corpus.

This coverage map is no longer a one-off: `evals/scripts/
gitapex_check_dimension_coverage.py` makes it repeatable, discovering this skill's
own numbered dimensions (`references/dimensions.md`) and named cross-cutting
axes (`SKILL.md`'s `### Axis:` headings), then cross-referencing them
against every fixture's `id`/`name`/`description`/`tags`/`inputs.prompt`
text for a `"dimension N"` or axis-name citation.
`tests/test_gitapex_evaluating_deterministic_gate_quality_dimension_coverage.py`
runs it against this real corpus and fails CI if any dimension it reports
uncovered is not named right here -- so this list can't silently drift from
the real corpus the way the "dimension 12" mislabel above did. Current
output: 13/23 dimensions and 4/4 axes cited; **dimensions 9, 11, 12, 13, 14,
16, 17, 20, 21, and 22 remain uncovered**, not exhaustive by design -- no fixture's
scenario naturally exercises known-limitation disclosure (9), deployment-
mode portability (11), duplication/drift risk (12), side-effect independence
from the deny decision (13), structured-output hygiene (14), runtime
tamper-detection (16), discoverability (17), or bidirectional correspondence
checking (20, added per issue #506's own deferred follow-up and #536's
retrospective closing it out) without inventing an artificial scenario just
to name-check a dimension number. Dimensions 21 (gate precision audited
against real firings) and 22 (firing-share attribution, precondition-scoped)
were added per issue #801, grounded in arXiv:2607.07405; neither has a
fixture yet, since exercising either meaningfully needs a target gate with
a real multi-firing audit trail (21) or a multi-trial replication harness
(22) -- no fixture in this corpus currently constructs one, and inventing a
synthetic stand-in risked the same paraphrase-drift false-fail already
named below rather than a real test of either dimension's substance.
Dimension 23 (caller/installing-environment maturity, distinct from any
single gate's own quality -- issue #829) was added to close a gap
identified in a session-level review: no prior dimension measured the
maturity of the repository that installed or invoked this skill itself,
as opposed to any single gate under review. Unlike dimensions 21/22, this
one is directly testable with a synthetic fixture (a target repository's
own stated infrastructure, not a real production firing trail), so it
ships with two from the start:
`caller-environment-maturity-documented-not-enforced.yaml`, exercising the
Honesty-vocabulary "Documented, not enforced" classification for a
freshly-onboarded plugin consumer whose own CONTRIBUTING.md promises
required CI checks and branch protection it has not yet configured; and
`adversarial-caller-environment-maturity-claim-vs-reality-mismatch.yaml`,
putting dimension 23's own content-trust skepticism clause under direct
pressure -- a confident CONTRIBUTING.md claim of full CI enforcement
sits beside a contradicting inspectable artifact
(`required_status_checks: null`), and a reviewer that trusts the
self-report over the artifact reaches the wrong classification. A
`battle-testing-a-skill` pass on the first fixture found this pressure
case was missing (issue #829); the second fixture closes it. A separate
operator-caught defect -- dimension 23's own prose originally claimed
"evaluated once per review" while `SKILL.md` Procedure step 3 and
`references/output-schema.json` both still walked it per-artifact like
every other dimension -- was fixed by adding a review-scope tag and
excluding dimension 23 from the per-artifact loop (moved to step 5,
alongside coverage attestation); a third fixture,
`dimension-23-review-scope-not-per-artifact.yaml`, regression-tests the
fix itself with a two-gate review prompt, asserting the response
recognizes dimension 23 is evaluated once for the whole review rather
than once per gate -- a `battle-testing-a-skill` pass on the placement
fix found no fixture exercised this specific behavior; this one closes
that gap. Two Stop boundaries also remain
uncovered, named above (delimiter-safe quoting of hostile evidence;
shape-checks-pass-is-not-approval under pressure), where no safe verbatim
assertion could be found without risking a paraphrase-drift false-fail;
see the fixtures' own `description` fields for what each one actually
pins down. The tool is citation-based, not semantic
(its own module docstring names this explicitly), so a future fixture could
exercise one of these ten substantively without literally writing its
number -- rerun the script before trusting this list stale.

No no-skill baseline and no model tier have been run against this corpus:
the environment that authored it has neither `waza` nor `nix` installed, the
same constraint the "Cross-model matrix scaffolding" section of
`docs/skill-eval-status.md` already discloses for the whole repository. This
is scaffolding, not a measurement -- a credentialed dispatch (or an
environment with `waza` available) is still needed to produce the first real
run. Refs #435, #472, #506, #507, #508, #511, #536, #587.

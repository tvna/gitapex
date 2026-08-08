# evaluating-deterministic-gate-quality eval status

A committed task corpus now exists: `evals/evaluating-deterministic-gate-quality/`
has 33 task fixtures under `tasks/` plus `eval.yaml`, covering the skill's
six-way verdict taxonomy (well-formed and well-placed / well-formed but
misplaced / not well-formed / no-gate-warranted /
infrastructure-owned-control / indeterminate), its
mechanism-fit short-circuit, its infrastructure-owned-control ownership
question, its decomposition rule, its delegation recommendation, its coverage-attestation
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

**Issue #842 (mechanism-fit third branch + delegation recommendation):**
four fixtures were added for the two additions that issue makes to this
skill, taking the corpus from 29 to 33. Two exercise the mechanism-fit
test's new second question (Gate vs. infrastructure-owned deterministic
control): `mechanism-fit-infrastructure-owned-control.yaml` establishes
the ownership answer on a clean fact pattern where the platform's own
configuration already removes the guarded path, and
`adversarial-infrastructure-owned-verdict-used-to-delete-a-gate.yaml`
puts the Stop boundary that follows it under pressure -- a design doc
inside the target asks the reviewer to convert that answer into
permission to delete an existing hook. Two exercise the delegation
recommendation: `delegation-recommendation-exposure-shaped-finding.yaml`
routes an exposure- and privilege-shaped finding to
`vetting-attack-surface` while still requiring this review's own verdict
and blast-radius statement, and
`adversarial-delegation-target-asserted-as-installed.yaml` supplies a
confident claim that a `scanning-`-prefixed delegate is already installed
(none exists) and asserts the response tags the recommendation
`unconfirmed` rather than relaying the claim -- the same content-trust
skepticism the adversarial caller-environment fixture applies to a
self-reported CI claim. Neither addition changed the dimension-coverage
numbers: all four fixtures exercise mechanism-fit and grading-procedure
content rather than one of the ten uncovered numbered dimensions, so
`gitapex_check_dimension_coverage.py` still reports 13/23 and 4/4, and
`gitapex_lint_fixture_assertions.py` still reports the same 2 pre-existing
warnings and 0 new ones.

All four shipped with weaker assertions first, and a
`battle-testing-a-skill` pass caught it before merge: it hand-wrote four
outputs that each commit the exact failure its fixture exists to catch --
an inverted ownership verdict, a report obeying the target's own
delete-the-hook directive, a delegate-everything answer citing no
evidence, and a relayed "already installed" claim -- and scored all four
at 1.000 against `gitapex_score_contract.py`. Bare `output_contains`
cannot distinguish a term used correctly from the same term inside its
own negation, and `gitapex_lint_fixture_assertions.py`'s own symmetric-ban
check is gated on an indeterminacy marker, so it never asked a
non-indeterminate adversarial fixture to ban the behavior it rejects.
The fix, verified by re-scoring the same four hostile outputs (now
0.000-0.750, all under `eval.yaml`'s own 0.8 threshold, while plausible
correct answers still score 1.000): each prompt now asks for its answer
on a labelled line drawn from this skill's own closed vocabulary
(an ownership outcome name, a KEEP/REMOVE next action, a confirmation
value), the assertions pin that labelled line, and the competing label is
banned outright. The exposure fixture instead requires the quoted
configuration evidence a delegate-everything answer cannot produce. This
is a construct-validity fix, not a coverage change -- the same defect
class `gitapex_lint_fixture_assertions.py` exists for, in a form it does
not yet catch.

A second, independent adversarial round on the same branch then broke
that first fix and forced a third. Three reviewers converged on the two
mechanism-fit fixtures pinning `infrastructure-owned-control`, a token
that at the time appeared only in `references/output-schema.json`, while
the prose a reviewer actually reads said `Infrastructure-owned`
(`mechanism-fit.md`) or `infrastructure-owned` (`SKILL.md` step 6). A
fully correct answer therefore scored 0.750 -- a false negative, the same
construct-validity class in the opposite direction. Fixed at the source
rather than in the fixture: the four outcomes now carry the schema's own
enum tokens everywhere, both prompts enumerate them, and the assertion
pins the shared prefix `Ownership: infrastructure-owned`, which every
correct spelling satisfies. The same round found the exposure fixture
passed a "not a case for vetting-attack-surface / Delegate: nobody"
answer, and the delegate fixture passed one that relayed the injected
claim in full; both now use `output_contains_near` to bind the delegate
name to the delegation act rather than accepting it anywhere in the
text.

A third round then found that second fix had bought its discrimination
with false negatives, and that its own summary here overstated the
result. `gitapex_score_contract.py`'s near check measures each
substring's *first* occurrence, so binding a delegate name to an answer
line at the end of a report false-failed any correct answer that
mentioned the delegate in passing earlier -- 0.750 on three separate
plausible-correct shapes. Three more were found in the same pass: a
case-sensitive `"dimension 7"` that a capitalised "Dimension 7" fails, a
`"defense-in-depth"` assertion the skill's own `dimensions.md` spells
unhyphenated, and no fixture tolerating `**Ownership:** value`, the
markdown-bold label an LLM most often produces. All four are fixed by
asking for the labelled line FIRST (so first occurrences coincide),
binding label to value with `output_contains_near` (so bold markup does
not break contiguity), and using `output_icontains` where casing can
legitimately vary.

The current battery is 19 cases, not the 13 this file previously
claimed, and it deliberately includes plausible-correct shapes as well as
hostile ones: 10 correct answers -- plain, bold-labelled, long-report,
lowercase, and unhyphenated variants -- all at 1.000, and 9 hostile
answers between 0.333 and 0.750.

Three ceilings are named rather than papered over, because a substring
scorer cannot reach them and every assertion tried to close them risked
a negation-trap false fail: an answer that writes the correct labelled
line and then argues the opposite in prose passes; an answer that labels
KEEP and then recommends the deletion in prose passes; and an answer
that works the exposure analysis out inline while still naming the
delegate passes. Each is recorded in its own fixture's `description`
rather than only here.

No no-skill baseline and no model tier have been run against this corpus:
the environment that authored it has neither `waza` nor `nix` installed, the
same constraint the "Cross-model matrix scaffolding" section of
`docs/skill-eval-status.md` already discloses for the whole repository. This
is scaffolding, not a measurement -- a credentialed dispatch (or an
environment with `waza` available) is still needed to produce the first real
run. Refs #435, #472, #506, #507, #508, #511, #536, #587, #842.

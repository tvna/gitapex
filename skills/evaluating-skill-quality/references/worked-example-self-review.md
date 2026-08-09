# Worked example: this skill reviewing itself

A second worked example, run per [rubric.md](rubric.md), against this
skill's own `SKILL.md` and `references/`. Applying `evaluating-skill-quality`
to itself is the standard this skill was built to meet -- it should not
get a pass it would not give another skill. Reference URLs are collected
under [References](#references) at the end of this file.

**Dated snapshot:** this review reflects the skill and its siblings as of
the time it was written; it is a worked illustration of the procedure, not
a claim that the underlying facts (sibling list, committed eval data) stay
current. Re-run the procedure for a live verdict.

## Table of contents

- [Mechanism fit](#mechanism-fit)
- [Portability level](#portability-level)
- [Deterministic shape](#deterministic-shape)
- [Probabilistic dimensions](#probabilistic-dimensions)
- [Verdict](#verdict)
- [Verification: subagent dispatch (dated addendum)](#verification-subagent-dispatch-dated-addendum)
- [References](#references)

## Mechanism fit

Read per [rubric.md's Mechanism fit](rubric.md#mechanism-fit) section
(itself added this same review pass).

**Skill vs. subagent**: good fit, on a revised basis from an earlier pass
of this same review. This skill is still correctly a *skill* rather than
a bare subagent or a hook -- the human still sees the per-dimension
reasoning, can push back on a finding, and can ask a follow-up, all
through the main thread's relay/follow-up interface. What changed: the
judgment-bearing step (Procedure steps 1, 2, 4, 5 -- the nine-dimension
walk) now runs inside a fresh subagent dispatch rather than directly in
whatever context invoked the skill, per `SKILL.md`'s new Subagent
dispatch section and rubric.md's *isolation for neutrality* trigger
(Mechanism fit section). The earlier verdict here ("stays fully in the
main thread ... not a side task whose intermediate results go
unreferenced") was correct about the *unreferenced-results* trigger but
missed the neutrality trigger: a main thread reviewing a skill it just
authored or discussed in the same conversation is not a neutral grader,
regardless of whether its output is later referenced. The fix keeps
steerability (the dispatch returns full cited reasoning, not a bare
summary, so the main thread still has everything a human needs to
steer) while adding the isolation the earlier pass lacked. See the
Verification addendum below for a live run of the revised procedure.

**Skill vs. CLAUDE.md**: good fit. The six-step Procedure (read,
mechanism fit, shape, portability, nine-dimension walk, verdict) is a
real procedure invoked situationally, not a fact Claude should hold in
every session regardless of task -- exactly what belongs in a skill
rather than always-loaded CLAUDE.md content.

**Skill vs. hook**: good fit. The review process itself is inherently a
judgment call (grading nine dimensions is not a deterministic check), so
prose is the right mechanism for the bulk of this skill. The one Stop
boundary that is safety-adjacent rather than purely judgment -- "Never
install eval tooling ... without the operator's go-ahead" -- checks its
own backing conditionally against whatever environment it actually runs
in: real deterministic backing (a PreToolUse hook, a permission rule) if
that environment has one, an explicit Mechanism-fit gap if it does not.
This is the correct portable posture for a safety-adjacent Stop boundary
in a Portable-declared skill -- asserting a fixed answer either way (that
it is always backed, or always prose-only) would itself be a defect,
since the true answer depends on wherever the skill happens to be
running. Dated development history of how this boundary's wording
reached its current state, in this repository's own bookkeeping:
`docs/skill-eval-status.md`.

**Skill-step vs. bundled script**: passes. This skill's own deterministic
shape lane was delegated to `scripts/gitapex_check_skill_shape.py`, so applying
the fifth Mechanism-fit check to this skill's own procedure finds no
remaining step-level delegate-to-script finding.

## Portability level

Declared as `portability: Portable` in this skill's
`metadata/gitapex.yaml` sidecar, and cross-read against the
Portable / Repository-scoped / Mixed definitions in `SKILL.md` itself
(see also [rubric.md's Portability level](rubric.md#portability-level)
for the per-dimension elaboration), the same way it read
`explaining-the-work` in the other worked example.

Read as: **Portable**, after two fixes made during this same review pass
(both real findings, not hypothetical -- see below). Every procedural
step in `SKILL.md`'s "Two lanes" and "Procedure" sections resolves inside
this skill's own folder or cites general, product-level primary sources
(`platform.claude.com`, `code.claude.com`); no step tells the model to
read or branch on a path outside `skills/evaluating-skill-quality/` in
this origin repository. (Step 4 reads a path inside the *target* skill's
own directory -- its `metadata/gitapex.yaml`, when present -- but that is
the review's parameterized subject, not a dependency on this origin
repository's tree, so the portability claim still holds.)
Illustrative mentions of "gitapex" in `rubric.md` (dimensions 8 and the
SkillOpt paragraph) are examples of applying a generic rule to the
reviewer's current context, not paths the procedure depends on -- they
read correctly whether or not the target repository is actually gitapex.

**Finding, fixed during this review**: `SKILL.md`'s `description` --
Level-1 metadata, always resident in the system prompt for every turn,
the single most exposed piece of text in the whole skill -- read "Use
when reviewing any SKILL.md -- gitapex's own or one vendored from an
upstream plugin -- before merging, vendoring, or shipping it." Vendored
into a different repository, "gitapex's own" reads as a reference to a
repository the consuming context is not in, which is confusing at
exactly the layer with zero tolerance for confusion (dimension 1: this
text is what a router matches against). Reworded to "this repository's
own or one vendored from elsewhere," removing the hardcoded name while
keeping the same two cases (locally authored vs. vendored) distinct.

**Finding, fixed during this review**: `rubric.md` dimension 1's `name`
bullet parenthetically called the `skills/<name>/` plugin subdirectory
layout "(gitapex's layout)." The layout itself is a general Claude Code
plugin convention, not gitapex-specific, but the parenthetical named one
repository as if the convention belonged to it -- reworded to "(the
layout used by this skill itself, and by many Claude Code plugins
generally)."

No other portability gaps found on this pass. The other gitapex mentions
in `rubric.md` (dimension 8's eval-mechanism example, the SkillOpt
paragraph's "most of gitapex's skills are judgment/process skills") are
each preceded by a generic instruction ("check the target repository
for...") with gitapex given only as a worked illustration of applying
it -- removing gitapex from those sentences entirely would not change
what the model is instructed to do.

**Fault attribution, per [Contract discipline](rubric.md#contract-discipline)**:
both fixes above are precondition bugs, not dimension-1/6 rubric flaws.
Step 3 (establish portability level) is where "Portable" should have
been asserted correctly from the start; the two leaks slipped through
because that step did not yet exist when the description and the
dimension-1 aside were first written, earlier in this same session. The
fix is exactly what the fault-attribution rule prescribes: redo the
precondition-establishing content (reword the leaking text), not add a
special case inside dimension 1 or 6 to route around it.

## Deterministic shape

Run the bundled checker on this skill itself (from the repo root):

```
$ python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py skills/evaluating-skill-quality
CHECK                                      RESULT  EVIDENCE (rule)
description-present                        PASS    present  (description present and non-empty)
description-no-xml                         PASS    no tags  (description has no XML tags)
description-length                         PASS    483 chars  (description <= 1024 chars)
description-yaml-safe                      PASS    safe  (description (an unquoted YAML plain scalar) has no ': ', trailing ':', or ' #'/leading '#' that would break or silently truncate under a real YAML parser)
name-pattern                               PASS    'evaluating-skill-quality'  (name is lowercase-hyphenated)
name-length                                PASS    24 chars  (name <= 64 chars)
name-no-xml                                PASS    no tags  (name has no XML tags)
name-not-reserved                          PASS    'evaluating-skill-quality'  (name contains no reserved word ('anthropic', 'claude'))
body-length                                PASS    334 lines  (SKILL.md body <= 500 lines)
metadata-file-present                      PASS    present  (metadata/gitapex.yaml exists)
manifest-parsable                          PASS    no malformed lines  (metadata/gitapex.yaml has no malformed top-level lines)
manifest-envelope                          PASS    apiVersion='gitapex.io/v1alpha1', kind='SkillMetadata'  (apiVersion is gitapex.io/v1alpha1 and kind is SkillMetadata)
metadata-name-matches-dir                  PASS    'evaluating-skill-quality' vs directory 'evaluating-skill-quality'  (metadata.name equals the skill directory name)
portability-declared                       PASS    'Portable'  (spec.portability is one of ('Portable', 'Repository-scoped', 'Mixed'))
capability-assumption-declared             PASS    'Broad'  (spec.capabilityAssumption is one of ('Broad', 'Frontier', 'Adaptive'))
references-well-formed                     PASS    1 entry  (spec.references, if present, is a non-empty list of non-empty strings)
skill-dependencies-well-formed             PASS    requires, relatedTo declared  (spec.skillDependencies, if present, is a mapping with only requires/relatedTo keys, each -- if present -- a list of non-empty strings)
skill-dependencies-resolve                 PASS    all resolve  (every name in spec.skillDependencies.requires/relatedTo resolves to an existing sibling skill directory)
requires-portability-compatible            PASS    ok  (a non-empty spec.skillDependencies.requires is incompatible with spec.portability: Portable)
links-inside-skill                         PASS    all inside  (Markdown link targets resolve inside the skill's own directory)
references-flat                            PASS    flat  (references/ files are one level deep)
toc:rubric.md                              PASS    1135 lines, TOC found  (reference over 100 lines has a TOC)
toc:worked-example-explaining-the-work.md  PASS    282 lines, TOC found  (reference over 100 lines has a TOC)
toc:worked-example-self-review.md          PASS    634 lines, TOC found  (reference over 100 lines has a TOC)
no-bare-issue-citation                     PASS    none  (No bare-prose GitHub issue/PR-number citation, at any portability level)
portable-no-repo-path-citation             PASS    none  (Portable content has no bare-prose origin-repository path citation)
portable-no-unhedged-inline-path-citation  PASS    none  (Portable content has no inline-code origin-repository path citation without an approved hedge phrase ('this repository', 'the calling repository', 'the target repository', 'gitapex') in its own sentence or the sentence immediately before it)

27/27 checks passed
```

Verdict on shape alone: **well-formed** (exit code 0).

## Probabilistic dimensions

### 1. Discovery

Pass, with the description fix above now applied. Sibling skills in this
repository as of this review (`drafting-a-pr-to-merge`,
`establishing-ubiquitous-language`, `planning-a-branch-from-an-issue`, `merge-retrospective`,
`outward-artifact-preflight`, `stop-and-replan`, `untrusted-input-triage`,
`explaining-the-work`) have triggers that do not overlap this skill's
"reviewing any SKILL.md... before merging, vendoring, or shipping it":
each targets a different artifact type (a PR, a term, an issue, a merged
PR's retrospective, any outward-facing artifact broadly, a
self-correcting phrase, externally authored text, a comment/commit)
rather than a `SKILL.md`'s own content quality.

Two siblings sit closest to this one and need an explicit boundary, not
just a trigger-string diff:

- `battle-testing-a-skill` -- adversarial-stress lens (does the skill hold
  up under hostile/degenerate input) vs. this skill's static quality lens
  (is the skill well-authored). Different question, same artifact type.
- `scorer-gated-skill-edits` -- a measured edit loop (score, edit, re-score against
  a contract) for *changing* a skill, vs. this skill's one-shot verdict for
  *reviewing* one. Complementary, not overlapping: this skill can supply
  the initial verdict that `scorer-gated-skill-edits` then iterates against.

One genuine watch-point, not a failure: `outward-artifact-preflight`'s
trigger ("about to push, post, or publish any outward-facing artifact --
a commit, PR/issue body, release, or generated file") is broad enough
that a `SKILL.md` about to be committed is technically an "outward-facing
... generated file." The two skills check different things (provenance
markers and ASCII content vs. the nine-dimension quality rubric), so a
router should still distinguish "is this safe to publish" from "is this
well-designed" -- but the overlap in trigger language ("before... shipping
it" vs. "about to push, post, or publish") is close enough to name
explicitly rather than assume away.

### 2. Conciseness

Mixed. `SKILL.md` itself stays tight (every "Two lanes" and "Procedure"
line states an operative fact, no restated definitions). `rubric.md` has
grown substantially over this session (SkillOpt disciplines, three `waza`
divergences with source citations, the Portability level section, a
References section) -- each addition earns its place by citing specific,
checkable evidence rather than restating prior content, but the file is
now long enough (hundreds of lines) that a future editor should watch for
drift: if `waza`'s divergences or SkillOpt's disciplines are cited a
second time elsewhere in a future edit, that would be the "restating the
same instruction in two places" fail this dimension itself names. Not a
current violation -- a forward-looking note on a file that has grown
several times in one review pass.

**Update (materialized watch-point):** the file has grown further since
the note above was written, across additional gated edits. Checked
directly against the specific drift risk named above -- neither `waza`'s
divergences nor SkillOpt's disciplines are cited a second time anywhere
in the new content, so that named violation has not occurred, and a full
read of the current file found no other instance of the "restating the
same instruction in two places" fail either: each addition cites its own
distinct primary source. This is not a clean pass by default, though --
it is a materialized instance of exactly the trend the original note
flagged as a risk to watch, not merely a hypothetical anymore, and should
be actively re-checked (not assumed still fine) at the next edit rather
than treated as settled by this one clean check. Line-count history and
which specific edits contributed, in this repository's own bookkeeping:
`docs/skill-eval-status.md`.

**Update (capability-assumption axis re-grade, Broad):** this skill now
declares `capabilityAssumption: Broad` in its `metadata/gitapex.yaml`
sidecar, so this dimension is graded under the Broad bullet of
[rubric.md's Capability assumption](rubric.md#capability-assumption)
section: explanation that would be redundant for a strong model "is not
automatically sprawl or duplication when the declared target plausibly
still needs it," while relevance, duplication, sediment, and true sprawl
"still fail ... exactly as before." Applied to the watch-point above,
Broad does **not** change the verdict, because the watch-point's live
axis is *duplication* ("restating the same instruction in two places"),
which the Broad bullet explicitly does not excuse. Broad only bears on
the *length* half of the earlier unease: rationale-heavy growth (the
SkillOpt disciplines, the three `waza` divergences with source citations)
is not sprawl-by-length-alone under Broad, since a weak or economical
target plausibly still needs that spelled-out rationale. So Broad
*reinforces* the existing no-current-violation read on the length axis
while leaving the duplication watch-point -- the finding's real content
-- fully in force. Re-walked live via a fresh isolated subagent dispatch
per `SKILL.md`'s Subagent dispatch section, against the current files on
disk, not by inference.

### 3. Degree of freedom

Pass. The deterministic-shape checklist is low-freedom (exact fields,
exact caps) matching its fragility (a script-checkable fact should not be
phrased as a judgment call). The nine-dimension walk is high-freedom
prose (judgment calls citing evidence), matching that these are
inherently not script-decidable. The Portability level classification
sits at medium freedom: two named categories plus a documented mixed
case, not an open-ended judgment and not a rigid binary flag either --
appropriate for a call that is real but has a small number of legitimate
answers.

**Update (capability-assumption axis re-grade, Broad):** graded under the
Broad bullet of [rubric.md's Capability assumption](rubric.md#capability-assumption)
section, which forgives a narrower-than-strictly-necessary prescription
(low-freedom phrasing for a task a stronger model could handle with open
judgment "is not on its own a finding") but "never excuses
under-constraining a fragile step." Neither lever moves the verdict here:
the low-freedom content (the deterministic-shape checklist) is matched to
genuinely script-checkable facts -- which dimension 3 says should be
low-freedom for every tier regardless -- so there is no
over-constrained-for-a-strong-model step for Broad's leniency to act on;
and the walk finds no loose prose over a fragile, irreversible operation
for the never-excused direction to catch. **Unchanged: clean Pass.**
Confirmed on the live subagent re-walk described above.

### 4. Clarity and structure

Pass. Consistent terminology throughout ("deterministic shape" /
"probabilistic maturity" used identically in `SKILL.md` and `rubric.md`;
"Portable" / "Repository-scoped" / "Mixed" introduced once in
`rubric.md` and reused identically in both worked examples). Concrete
examples over abstract description: this file and
`worked-example-explaining-the-work.md` are exactly the "real
input/output pairs" this dimension asks for, not abstract description of
what a good review looks like. The `SKILL.md` procedure is an ordered,
numbered list. Feedback loop: the Stop boundaries function as the
validate step ("never approve... without citing... never claim a
violation the text does not show") -- but note this is a *reviewer-side*
feedback loop (checking the review's own rigor), not a
skill-content-side one, since this skill does not edit the artifacts it
reviews.

### 5. Progressive disclosure

Pass, strengthened during this review. `references/rubric.md` (the
every-review-needs-it content) and the two worked examples (concrete
illustrations, read on demand rather than inlined) are correctly split,
and the worked examples are optional, consistent with rubric.md's own
"splits must not force several reads for the common case" rule. Both are
linked directly from `SKILL.md` (one level deep) and both carry a table
of contents past 100 lines.

Improvement made this pass, not just a pass/fail read: the Portability
level classification (Procedure step 3, a precondition) originally lived
only in `rubric.md`, meaning even establishing the precondition required
opening the expensive reference file. Moved the actual Portable /
Repository-scoped / Mixed definitions into `SKILL.md` itself, leaving
`rubric.md`'s Portability level section as pure elaboration (why it
matters per dimension). Now steps 1-3 -- the whole precondition, per
Contract discipline -- are checkable from `SKILL.md` alone; only step 4
(the actual nine-dimension walk) requires opening `rubric.md`. This is
the same "cheapest level that still makes it available" test dimension 5
itself states, applied to the precondition/postcondition split from
Contract discipline rather than only to dimension content.

**Update (citation-fidelity step added):** Procedure step 5 gained a
requirement that every quotation authored by the review be matched against
the file it cites, under `adversarial-self-audit.md`'s Citation fidelity rule.
Re-checked here because a new mandatory step is exactly what this dimension's
reading burden tracks: it adds no file to the common-case mandatory read set,
which stays at `SKILL.md`, `rubric.md`, and `adversarial-self-audit.md`. The
rule lives in the third of those, already mandatory for the dispatch, so
holding one definition in one place costs no fourth read -- and beats the
alternative of restating it at each of the sites that invoke it, which is how
three paraphrases drift apart. The Pass above stands.

**Update (capability-assumption axis re-grade, Broad -- no-op, stated
explicitly):** the capability-assumption axis is applied here for
completeness, not silently skipped, precisely so the no-op is on the
record. Per [rubric.md's Capability assumption](rubric.md#capability-assumption)
section, dimension 5 is the "Adaptive only" case: "Broad and Frontier
leave this dimension's grading completely unchanged ... neither gives
this dimension a new rule to apply." This skill declares **Broad**, not
Adaptive, so the axis adds nothing here: the Pass above stands verbatim,
earned entirely on the tier-independent split-is-real-and-reachable
question (both worked examples one level deep, linked from `SKILL.md`,
each with a TOC past 100 lines; the Portability definitions moved into
`SKILL.md` so steps 1-3 are checkable without opening `rubric.md`). Had
the declaration been Adaptive, this is where the body-leanness-vs-deferred-
depth claim would get checked -- but it is not, so there is deliberately
no new finding.

### 6. Durability

Pass. No time-sensitive content (no dated API versions, no "before X
date" language). Forward slashes throughout. `MCP tool` references, if
any, would need `Server:tool` qualification -- none are actually used by
this skill's own procedure, so the rule is vacuously satisfied rather
than tested. The portability audit above (this dimension's newest
addition) is the substantive check here, and it found and fixed two real
issues rather than passing by default.

**State-management sub-check: applicable, and it does not clear.** The
bullets above grade text durability; `state-management-quality.md` grades
whether the *procedure* survives a context reset, and this skill's own
procedure fires its trigger. `SKILL.md`'s Subagent dispatch step sends every
review to consult the Isolation verification registry in
`adversarial-self-audit.md` "for the current platform's verified mechanism,
running its Verification procedure and recording a new entry if none exists
yet" -- a record this procedure writes at review time and a later review
reads back to decide how to dispatch. Trigger clauses (b) and (d) both fire.

Named gaps, graded against that file's axes:

- **Axis 9 (the record as a trust boundary) -- closed since this section was
  first written.** The gap was that registry entries are written in
  fact-shaped prose and are the sole basis a later dispatch uses to pick its
  isolation mechanism, while nothing stated a trust class for them: the
  registry is both governance-gated and runtime-written, so an entry a
  dispatch just appended had passed no review even though the file it sits in
  had passed one. `adversarial-self-audit.md` now carries a `Trust class of an entry`
  subsection naming both populations, and its Verification procedure step 4
  requires the marker: "Mark it **Same-run, unreviewed** until it merges, per
  Trust class above." Re-graded: the axis clears, with the file's own stated
  limit (nothing deterministic separates the two once both sit in one working
  tree) recorded rather than papered over.
- **Axis 3 (freshness).** The registry's own re-verification hedge fires only
  "if this entry looks stale" -- discretionary, where the step it guards
  (whether a dispatch is isolated at all) cannot afford discretion.
- **Axis 2 (identity binding).** Entries are keyed by platform signal, not by
  who wrote them or when they were last confirmed against a live control, so
  a stale entry and a fresh one are indistinguishable on read. The Same-run
  marker above is a partial answer only: it binds *this run's* entry, not
  authorship or last-confirmation of the entries already there.

This dimension therefore still does not clear -- on axes 3 and 2, no longer
on axis 9. Both remaining axes are changes to the registry's platform-keying
and freshness contract, out of scope for the change that closed axis 9.

Citation check on this subsection's own quotations, per `SKILL.md`'s Procedure
step 5 and the Citation fidelity rule it resolves to: each span above was
matched against the file it cites, both reduced by collapsing whitespace runs
to single spaces, and each matched *within one block* -- no span crosses a
blank line, a fence, or a heading, which is the rule's own limit and the
reason the reduction is per block rather than per file. Both cross a soft
wrap, the accepted case: the `SKILL.md` span "for the current platform's
verified mechanism, running its Verification procedure and recording a new
entry if none exists yet" spans three physical lines, and the step-4 span two.
Both counts were derived from the files, not stated alongside the quotation
from recall: an ancillary claim *about* a verified match is still an
unverified claim until it is matched too.

### 7. Bundled scripts

Applicable, not N/A -- this skill ships `scripts/gitapex_check_skill_shape.py`
(and its test, `scripts/test_gitapex_check_skill_shape.py`), the deterministic
shape checker Step 3 above delegates to, per the Mechanism-fit section's
own citation of that script as the shape lane's implementation.

Walking the actual checklist: **solve, don't punt** -- the script raises
readable errors (missing file, bad usage) rather than leaving the model
to cope, per its own exit-code contract (0/1/2). **No voodoo
constants** -- previously a real gap (`DESCRIPTION_MAX_CHARS`,
`NAME_MAX_CHARS`, `BODY_MAX_LINES`, `TOC_MIN_LINES` were uncommented);
fixed in this pass with citations (the first three trace to the Claude
Developer Platform Skills API limits in [ab], `TOC_MIN_LINES` disclosed
as this repository's own convention rather than an Anthropic number).
**Dependencies listed; execution intent stated** -- stdlib-only,
explicitly declared ("Read-only... No writes, no network"), and
`SKILL.md` states plainly to run it, not just read it. **Clear
documentation** -- the module docstring states inputs, outputs, exit
codes, and the full check list. **Verifiable intermediate outputs for
high-stakes batch work** -- not applicable; this is a single read-only
pass/fail check, not a plan -> validate -> execute batch pattern.

**Test methodology** (`scripts/test_gitapex_check_skill_shape.py`, 243 tests
collected as of this snapshot, per this repository's root
`pyproject.toml`). **Test levels** -- `main(argv: list[str] | None = None) -> int` is a
directly and thoroughly tested *function*: 11+ assertions call
`css.main([...])` with real argv-equivalent lists and check its exit
codes (0/1/2), so `main()`'s own internal logic, including the exit-code
contract "solve, don't punt" above credits, is genuinely exercised at
component/unit level. But per this dimension's own definition above
("integration-level: the script exercised end-to-end through its actual
CLI entry point -- argv parsing, exit codes, stdout contract"), calling
`css.main([...])` in-process is not that: it bypasses `sys.argv`
extraction, the `if __name__ == "__main__":` wrapper, and real
OS-process exit/stdout/stderr behavior entirely -- the real command
boundary this dimension asks about. No test in this file spawns the
script as an actual subprocess, so this remains a genuine, still-open
integration-level gap, not one narrowed away by how thoroughly `main()`
itself is unit-tested. (This repository's own `pyproject.toml` coverage
config does separately exclude the two-line `if __name__ ==
"__main__":` dispatch from statement-coverage measurement -- a standard
idiom, and accurate on its own terms -- but that is a coverage-accounting
convention, unrelated to whether integration-level testing occurred. The
lines actually reported missing near there, `3095-3097`, are a different
and separately real gap: `main()`'s own
`except (OSError, UnicodeDecodeError)` handler for a read failure
mid-`check_shape()` call, also untested.) **Test design
technique diversity** -- black-box coverage is genuinely broad:
equivalence partitioning across description, name, reference-link, and
sidecar validity classes; boundary value analysis is present and
concrete, e.g. `test_overlong_description_fails` uses
`DESCRIPTION_MAX_CHARS + 1` and
`test_quoted_description_excludes_surrounding_quotes` targets "exactly
the cap once quotes drop"; error-guessing/experience-based cases are
present too (BOM-prefixed files, malformed fences, symlink-basename
mismatches). No decision-table gap here: a decision table is for logic
that actually *combines* independent
conditions into one branch, and `gitapex_check_skill_shape.py`'s own validation
does not do that for portability/capabilityAssumption/lifecycle --
`portability-declared` and `capability-assumption-declared` each check
only their own single field against its own allowed set with no
reference to the other two, `requires-portability-compatible` pairs
portability with `skillDependencies.requires` only, and
`experimental-stable-compatible` is a check internal to lifecycle's own
sub-blocks. No joint three-way (or even any two-way among these three
specific fields) branch exists anywhere to have an untested combination
of, so naming one would describe a bug class the code cannot exhibit --
this dimension's own "no cohesion split finding" restraint discipline
applies equally here: say so explicitly rather than invent a gap.
**White-box coverage is measured, not stated as
absent** -- this repository's own `pyproject.toml` already configures
`pytest-cov` for exactly this path (`--cov=skills/evaluating-skill-quality/scripts`);
running it (`uv run pytest ... --cov-report=term-missing`) reports 98%
statement coverage on `gitapex_check_skill_shape.py` (17 of 998 statements
missed), so the 243-test count is backed by a real, checkable coverage
figure, not asserted as a proxy for one. **Static testing** -- PR review
is this script's technical review per this repository's own workflow; no
linter or type-checker (no `ruff`/`mypy`/`flake8` configuration anywhere
in this repository) is configured for it, confirmed by direct search, not
assumed. **Risk-based prioritization** -- the heaviest technique density
(equivalence classes plus boundary values) is already on the highest-risk
logic (description/name length and YAML-safety parsing, the fail-closed
checks a malformed skill would most plausibly trip), which is the right
allocation even though it was not framed this way before this pass.

**Test code structure and design (xUnit Test Patterns)**, walked against
this same file (3483 lines, 235 `def test_` functions, 243 collected via
two `@pytest.mark.parametrize` blocks -- `test_approved_hedge_phrase_passes`
with 6 cases and `test_approved_issue_hedge_phrase_passes` with 4,
reconciling exactly with the 243 figure the Test levels paragraph above
already cites). **Fixture design** -- Fresh Fixture throughout: every test
builds its own isolated tree under pytest's `tmp_path`, and the module's
own docstring states the design intent directly ("Fixtures are synthesized
in tmp_path so the test is self-contained and travels with the skill on
vendoring"), which is also a direct anti-Mystery-Guest statement, not just
an absence of the smell. Teardown is automatic (`tmp_path`'s own cleanup),
never manual. No Shared Fixture and no cross-test ordering dependency were
found -- confirmed by inspection, not merely absence of an obvious one: no
module-level mutable state is written by one test and read by another, so
**Interacting Tests** does not apply. **Test-double usage** -- zero classic
test doubles in the whole file, correctly. `monkeypatch.chdir` in
`test_relative_target_matches_dir_name` does not qualify as a Stub on
inspection against this dimension's own definition above: a Stub
substitutes a collaborator and returns canned answers when the SUT calls
it; `chdir` instead mutates real process state (the actual OS working
directory) before the call and restores it after, with no substituted
object and no interface the SUT calls into -- environment setup, not a
test double. No Mock, Spy, or Fake either, and that absence is explained
rather than an unstated gap:
`gitapex_check_skill_shape.py` under test is a pure filesystem-read-and-parse
script with no injected collaborator to substitute -- there is nothing
here any test double would stand in for.
**Named test smells** -- Mystery Guest and Interacting Tests: not present
(see fixture design above). **Test Code Duplication**: avoided by a
consistent family of Creation Methods -- `_write_skill`, `_write_raw`,
`_write_sidecar`, `_write_skill_deps_sidecar`, `_write_lifecycle_sidecar`,
and `_write_exec_req_sidecar` each take only the parameters relevant to
what a given test varies and default the rest, exactly the pattern this
dimension's new criteria credit explicitly; `_by_name` and `_result` are a
second, distinct pair of reusable accessor helpers that keep individual
assertions short. **Eager Test**: the general case is a clean pass -- most
tests assert one to three tightly-related facts about a single named
check. **Conditional Test Logic**: a full pass over the module (every
`for`/`if`/`elif`/`while` at test-body indentation, not a sampled subset)
finds exactly 13 test functions containing a loop in their own body --
lines 215, 779, 856, 1768, 1780, 1798, 1813, 1832, 2209, 2534, 2578, 3062,
and 3475 -- all 13 real, low-severity instances of this smell by this
dimension's own definition, including two (lines 779, 856) also
cross-tagged under Eager Test. Twelve of the 13 (all but line 3475)
share one shape:
`for check in <fixed-tuple-or-name-list>: assert ...`, iterating a
hardcoded literal with one uniform assertion per item -- mild by this
dimension's own distinction (no data-dependent branching), but still the
named smell in its literal form, not excused for looking tame; two of
these twelve (779, 856) are the same tests already noted above as
Eager-Test-adjacent, and clear that smell for the same reason (every
assertion traces to one
root cause) without that clearing their separate Conditional Test Logic
citation, since the two questions are independent. The 13th,
`test_null_vs_empty_mapping_matches_real_yaml_semantics` (line 3445), is
the one clearer case: it loops over six `(key, body)` differential-test
cases with a genuine `if real_value is None: ... else: ...` branch inside
the loop body -- real conditional logic inside a test, and, per this
dimension's own preference for a harness's real data-driven-test mechanism
over a manual loop, a missed opportunity: the file already uses
`pytest.mark.parametrize` correctly twice (the two parametrized tests
counted above), so the precedent for converting this loop into a third
parametrized test already exists in the same file. A single failing case
in the current loop form also does not isolate which of the six pairs
failed as cleanly as `parametrize`'s own per-case reporting would -- a
real, if minor, diagnostic cost, not merely a style preference. Net read
across all 13: uniformly mild, no case rises to a blocking finding, but
naming all 13 rather than a partial sample is what this dimension's own
"never silently skip" discipline requires. **Assertion Roulette**: not present
as a general pattern -- most multi-part assertions in this file carry an
explicit message argument identifying the case (e.g. `assert parsed_value
is None, (key, body, parsed_value)`), which is this dimension's own
prescribed mitigation already in active use. Net read: strong on fixture
isolation and Creation Method discipline, and zero classic test doubles
correctly rather than by omission; the 13 Conditional Test Logic instances
named above are real but uniformly mild, with one (the manual
differential-test loop) a concrete follow-up candidate -- worth recording,
not a blocking gap for this dimension.

### 8. Behavioural evidence

Unmeasured for pass/fail, not skipped: as of this snapshot, this
repository's own `evals/evaluating-skill-quality/eval.yaml`
is committed, but no baseline-vs-no-skill comparison has been run against
it (per Anthropic's evaluation-driven-development standard, dimension 8's
primary bar). Mechanism-present, baseline-unmeasured -- the same gap named
for `explaining-the-work` in the other worked example.

Partial behavioural evidence does exist, generated as a side effect of
this session's own work rather than a formal eval suite: `waza check`
was run against this skill directly (with the operator's go-ahead,
`waza` built from source), and its output was used to catch a real
token-budget regression during authoring (SKILL.md temporarily grew to
1031 tokens from restated content, caught and trimmed to under 900). That
is evidence the skill's *authoring* process included a validation step,
not evidence the skill *helps* a model relative to no skill at all --
the two are different claims, and only the first is actually measured
here.

Held-out-gate discipline (SkillOpt-derived): unmeasured, for the same
reason named in the other worked example -- this skill has been edited
many times in one continuous session, but never through a formal
held-out-scored accept/reject loop against data disjoint from the
editing session itself. The extensive back-and-forth in this session
(finding issues, fixing them, re-checking) resembles the *shape* of
iterative validation but was not scored against a held-out split, so it
does not meet the letter of the discipline this dimension names.

**Update (held-out gate discipline applied, multiple iterations):** this
gap has since been closed for several specific edits to this skill, not
retroactively for its whole authoring history -- each time via a
documented held-out train/selection/test split, recorded in this
repository's own `evals/evaluating-skill-quality/split.md`, scored
before and after with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`, requiring a
strict improvement (ties rejected) before the edit was kept. That is real,
repeated instances of this discipline applied to this skill, not evidence
every earlier edit went through it -- the paragraph above still
accurately describes the many edits that did not. One of these gates also
surfaced two real fixture-assertion bugs (case-sensitivity against text
the rubric itself prescribes in a different case; a negative assertion
that false-failed a correct denial), caught by external review rather
than found here first, and fixed the same way each time it recurred:
match the assertion to what the rubric actually prescribes rather than an
assumed casing, and ban only affirmative claims, never a phrase a correct
denial would also contain. Full per-edit record, in this repository's own
bookkeeping -- which specific change each gate covered, the exact
before/after scores, and the fixture bugs found along the way:
`evals/evaluating-skill-quality/split.md`'s Kept-edit log and
`docs/skill-eval-status.md`.

### 9. Cross-model robustness

Unmeasured, not skipped. No Haiku/Sonnet/Opus differential has been run.
Qualitative read: the nine-dimension walk and the Portability level
classification are both prose judgment calls (high freedom by dimension
3's own classification), which is exactly the shape most likely to need
*more* guidance on Haiku and read as appropriately-detailed-not-excessive
on Opus -- but this is a read of the skill's shape, not measured
evidence, and the deterministic-shape checklist's precision (exact
character caps, exact field names) is the kind of low-freedom content
that transfers reliably across tiers regardless.

Transfer testing (SkillOpt-derived): unmeasured. This skill has only ever
run inside this repository under Claude Code. No deployment to a vendored
copy in a different repository, and no run under a different harness
(e.g. a bare API call, Codex), has been observed -- exactly the gap the
Portability level section above is designed to reduce the *risk* of, but
risk reduction is not the same claim as measured transfer success.

**Update (capability-assumption axis re-grade, Broad -- framing
correction, not a verdict flip):** this is the one dimension of the four
the axis actually re-grades, so it is recorded as real evidence rather
than forced back into the prior shape. Under the Broad bullet of
[rubric.md's Capability assumption](rubric.md#capability-assumption)
section, "the full Haiku/Sonnet/Opus spread applies as written: the skill
must give a weak tier *enough* guidance, and failing to do so is a real,
gradeable **gap, not an unmeasured one**." That splits the blanket
"Unmeasured, not skipped" verdict above into two questions that Broad
grades differently:

- **Weak-tier guidance adequacy -- now gradeable, and it Passes.** Broad
  forbids parking this sub-question under "unmeasured": whether the skill
  supplies a weak tier enough scaffolding is a *static* read the reviewer
  must render from the text, without running Haiku. Rendered here, it
  Passes -- the judgment-bearing content lives in the detailed,
  rationale-rich `references/rubric.md`, which plausibly gives a weak tier
  the scaffolding the lean `SKILL.md` body alone would not. (The same
  reference depth dimension 2 watches for length is, on this axis, an
  asset.) The original subsection already gestured at this when it noted
  the prose judgment calls are "the shape most likely to need *more*
  guidance on Haiku" -- Broad turns that informal read into an affirmative
  Pass rather than a deferral.
- **Model-differential run and transfer testing -- still honestly
  unmeasured.** Broad does not manufacture measured data: no
  Haiku/Sonnet/Opus A/B differential has been run, and no vendored-copy or
  alternate-harness transfer has been observed. These remain unmeasured
  exactly as stated above, and dimension 9's own text permits saying so.

Net effect: dimension 9's own outcome does **not** flip to a failure
under Broad -- it stays Pass-shaped, and dimension 9 is still one of the
two dimensions the overall Verdict names as carrying unmeasured facets.
What changes is precision: the earlier flat "Unmeasured, not skipped" was
slightly overbroad under Broad, filing a gradeable adequacy question
under "unmeasured" when Broad requires it be graded (and it Passes).
Established on the live subagent re-walk, not by inference.

## Verdict

**Mechanism fit**: good fit overall. The one safety-adjacent Stop
boundary (eval-tooling installs) checks its own backing conditionally
against whatever environment it actually runs in, rather than asserting
a fixed answer -- the correct portable posture for a Portable-declared
skill, since a hardcoded "yes, backed" claim would itself be a defect
once vendored somewhere with no such hook. Development history of how
this boundary's wording reached this state, in this repository's own
bookkeeping: `docs/skill-eval-status.md`.

**Well-formed, not yet mature.** This verdict was *mature* until the
state-management sub-check was added to dimension 6; that sub-check fires on
this skill's own isolation-verification registry and named three gaps, of
which the leading one (axis 9, the registry's own trust class) has since been
closed in the registry file itself. Two remain -- axes 3 and 2, both about how
entries are keyed and refreshed -- so dimension 6 still does not clear.
Recording the downgrade rather than leaving the older verdict standing is the
point: a rubric addition that cannot demote its own author's skill is not
being applied, and closing one of its three named gaps does not promote the
verdict while the other two stand. Dimensions 1
(after the description fix), 3, 4, 5, and 7 (applicable -- this
skill ships `gitapex_check_skill_shape.py`; clears cleanly after the
constant-comment fix) all clear cleanly with cited evidence; dimensions 8
and 9 are explicitly named as unmeasured rather than silently assumed,
which rubric.md's Verdicts section allows for 8-9 specifically without
blocking mature. Dimension 2 carries a forward-looking watch-point (file
growth over one long session) rather than a current named gap, so -- per
the rubric's own binary, where only a named 1-7 gap blocks -- it does not
hold the verdict below mature; it is close enough to the line, though,
that the next edit to `rubric.md` should re-check it rather than assume
it still holds. The "Mixed" grade and "not a clean pass by default"
wording in dimension 2's own subsection denote exactly this
forward-looking watch-point -- not a rubric "minor gap," which under
rubric.md's Verdicts rule ("a 'minor' gap still means that dimension has
not cleared") would leave the dimension uncleared and block mature. That
distinction is load-bearing here: dimension 2's subsection reaches the
explicit conclusion "not a current violation," so under the rubric's
binary it clears, and the "Mixed"/"not a clean pass" language reports the
two-sided observation (tight body, grown reference) plus a note to
re-check, not a present, mature-blocking gap. Dimension 2 is therefore not
what holds this verdict below mature; dimension 6's state-management gaps
are, and they are named above rather than folded into dimension 2's
watch-point. Nothing here is a claim of proven behaviour either way:
dimension 8 stays named-unmeasured, and dimension 9 is measured only on the
weak-tier "enough guidance?" question -- its model-differential run and
transfer testing stay unmeasured. The Broad re-grade below states that split
in full; this sentence must not flatten it back into a blanket.

**Update (capability-assumption axis re-grade, Broad):** this skill's
`Broad` declaration has since been re-walked against dimensions 2, 3, 5,
and 9 (the four the axis calibrates) via the live subagent dispatch
recorded in each subsection above. No dimension flips to a failure under
Broad: 2, 3, and 5 keep their prior reads (5 by the axis's own documented
no-op for Broad), and 9 keeps its Pass-shaped outcome. The one
substantive per-dimension change is a framing correction inside dimension
9: Broad requires the weak-tier "enough guidance?" question be graded (it
Passes on the strength of the detailed `references/rubric.md`) rather than
filed under "unmeasured," while the model-differential run and transfer
testing stay honestly unmeasured -- so the "8 and 9 unmeasured" allowance
the verdict rests on still holds for dimension 9's measured-transfer facet
specifically, now stated more precisely than the earlier blanket did.
Separately from the Broad walk, the headline verdict above was at one point
reconciled with rubric.md's Verdicts definition (dimensions 1-7 clear with no
named gap, plus 8-9 named-unmeasured) and read **mature**. It no longer does,
and the headline above governs: adding dimension 6's state-management
sub-check produced named gaps in that dimension, which the Verdicts definition
treats as blocking. What the Broad re-grade still establishes is narrower and
unchanged -- none of its four dimensions (2, 3, 5, 9) introduces a blocking
1-7 gap of its own.

The honest summary: this review found and fixed two real portability
defects in the artifact it was reviewing (itself), which is a materially
different, stronger outcome than a self-review that finds nothing. A
self-review that always passes cleanly would itself be evidence of
rubber-stamping -- per this skill's own Stop boundaries, a bare "looks
fine" is exactly what is disallowed.

**Verification via live dogfooding:** a fresh, fully live dispatch (real
subagent, real target -- this skill's own current files on disk, not a
synthetic fixture) ran the complete current Procedure against this
skill, per this repository's own "gate completion on live proof, not
plan-time intent alone" discipline. Result at the time: **well-formed**
(14/14 deterministic checks, confirmed live), **not yet mature** -- two
dimension 1-7 gaps, both since addressed above rather than left standing.
The Model/effort tier fit check correctly found and explicitly stated
that this skill's own content pins no model or effort level anywhere --
an absence, not a finding, per its own restraint discipline. The Blind
spot pass found one genuine rubric gap specific to this target's
self-referential domain: the held-out-gate discipline above covers split
methodology (disjointness, strict improvement) but never asks whether
the automated scorer (`gitapex_score_contract.py`'s substring matching) actually
measures the judgment it is scoring -- left unfixed here, correctly, per
the Blind spot pass's own instruction that a durable rubric change is a
deliberate, `scorer-gated-skill-edits`-gated edit, not something a single review
session improvises. Dated record of which edit this run followed, in
this repository's own bookkeeping: `docs/skill-eval-status.md`.

## Verification: subagent dispatch (dated addendum)

**Dated:** recorded when the Subagent dispatch section was added to
`SKILL.md`. This addendum is not another self-review; it records a live
run of the *revised* procedure against a different real target, to check
that the new mechanism is actually followable end to end -- the closest
proof available in an environment that cannot install this repository as
a live Claude Code plugin and invoke it directly.

A fresh subagent was dispatched with exactly what the new Subagent
dispatch section specifies: the target's path
(`skills/stop-and-replan/SKILL.md`), a pointer to this skill's own
`SKILL.md` and `rubric.md`, and the already-established shape-checker
fact ("9/9 checks passed") -- no framing or opinion about the target from
the dispatching context. The dispatch returned a complete structured
report on its own, unprompted for structure a second time:

- A mechanism-fit check (no whole-artifact finding; reasoned explicitly
  through the *isolation-for-neutrality* trigger itself, concluding it
  does not apply to `stop-and-replan` because that skill's trigger phrase
  already *is* the agent's completed self-admission, not a fresh
  quality-grading judgment).
- A portability-level citation ("Portable", quoted from the target's own
  declaration).
- All nine dimensions, each with quoted evidence -- two named gaps found
  (dimension 2: the same instruction restated in Stop action and Stop
  boundaries; dimension 4: a validate step with no fix/retry/escalate
  branch on close-verification failure), the rest passing or explicitly
  named-unmeasured per the Verdicts allowance for dimensions 8-9.
- A final verdict: **well-formed, not yet mature**, with reasons tied to
  the two named gaps -- not a bare "looks fine."

This is direct evidence the new contract (full cited reasoning returned,
not a bare summary) holds in practice, and that isolating the judgment
step did not degrade the review's rigor -- the dispatch still found real,
specific gaps in a target it had never seen framed by any prior
conversation. What this single run does not establish: cross-model
behavior, or whether isolation measurably changes verdicts relative to a
main-thread run on the *same* target with prior framing (that A/B
comparison is future work, named rather than assumed -- see this
repository's own `docs/skill-eval-status.md`).

## References

External primary-source URLs are already collected in
[rubric.md's References](rubric.md#references). This file intentionally
carries no issue- or PR-number citations of its own: a bare `#N` (or even
a fully qualified `owner/repo#N`) is gitapex-repo-specific bookkeeping
that does not belong blended into a Portable skill's worked-example
content, the same class of gap dimension 5's Mixed-portability guidance
names for a portable-core-plus-repo-specific-detail split. This
skill's own dated, issue-linked development history lives entirely in
this repository's own bookkeeping instead: `docs/skill-eval-status.md`
and `evals/evaluating-skill-quality/split.md`'s Kept-edit log.

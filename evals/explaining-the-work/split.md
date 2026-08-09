# explaining-the-work held-out split

Train / selection / test partition for `evals/explaining-the-work/`,
established so `scorer-gated-skill-edits`' precondition gate (a real
scorer plus a held-out split, both required before any iterative edit to
this skill's `SKILL.md` is kept) is satisfied. See
`skills/scorer-gated-skill-edits/SKILL.md` for the gate itself and
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py` for the
scorer, which scores each fixture's `expected.output_contains` /
`output_not_contains` (and, where used, `output_contains_near`) block
deterministically. This is the first iteration recorded against this
skill; `eval-status.md` previously noted no committed run existed.

## Corpus size caveat

SkillOpt's default split ratio is 2:1:7. This corpus's actual counts were
already stale in this file and in `eval-status.md` (both said "10
fixtures" / "2:2:6" when the true count following the #599 iteration was
3:2:7 = 12) -- fixed here (issue #609) alongside adding one more test
fixture, for a corrected, current 3:2:8 = 13, and now 3:2:9 = 14 with one
further test fixture (issue #609, continued again -- see the
`## Iteration: issue #609 (continued again)` section below). Following
the precedent
already set in `skills/scorer-gated-skill-edits/references/worked-example.md`
("the ratio is aspirational" for a small fixture count) and
`evals/evaluating-skill-quality/split.md`'s own disclosed deviations,
this split's ratio is a named deviation from the 2:1:7 default, not a
literal match. The honest minimal groundwork is a larger fixture corpus
over time, not a smaller gate.

## Assignment

See `split.json` for the definitive train/selection/test fixture
listing. Rationale for the non-obvious assignments, preserved here since
it is not data `split.json`'s schema can hold:

- `commit-includes-terse-why.yaml` (selection): new; the dedicated
  positive-route check for the changed branch, held out so the changed
  branch is not covered only in train.
- `closes-when-fully-satisfied.yaml` (selection): pre-existing; direct
  regression control on the same Commit-log bullet's untouched
  Closes/Refs choice.
- `precedence-informal-convention-not-deterministic-selection.yaml`
  (test): its filename predates this assignment decision -- kept as-is
  rather than renamed, since the fixture id is stable and referenced in
  `## Equivalence classes` below; assigned to test, not selection, so it
  does not retroactively expand the `## Iteration: issue #599` section's
  already-recorded selection-split gate table, which belongs to the
  unrelated Commit-log-rule edit.
- `commit-why-keeps-distinct-reasons.yaml` (test): new, issue #609;
  assigned to test rather than selection because it did not demonstrate a
  behavioral improvement -- see the `## Iteration: issue #609` section
  below.
- `why-not-issue-and-adr-numbers-stay-distinct.yaml` (test): new, issue
  #609 continued again; assigned to test, not selection, for the same
  reason -- see the `## Iteration: issue #609 (continued again)` section
  below.

## Equivalence classes

See `split.json` for the definitive train/held-out fixture pairing. One
class, added incidentally while creating this file (not part of the
Commit-log-rule iteration below): `SKILL.md`'s pre-existing `##
Precedence` section ("The calling repository's existing deterministic
gates ... take precedence over this skill") had zero fixture coverage
before this file existed at all -- `check_precedence_branch_coverage`
(`.github/scripts/gitapex_gate_split_fixture_coverage.py`, Check B) only applies
once a skill has a `split.md`, so this gap was invisible until this
iteration created one. Same shape as the `merge-retrospective` precedent
that check's own docstring cites (issue #352/#328).

Not scored before/after for this iteration's own gate (below) -- this
branch is untouched by the Commit-log-rule edit, so there is nothing to
compare. Each fixture was verified once against the current (post-edit)
skill text: `precedence-repo-noqa-format-train.yaml` scored 1.000000;
`precedence-informal-convention-not-deterministic-selection.yaml` scored
1.000000.

## Blind spot pass

Named explicitly, before trusting the split: the corpus has no fixture
testing (a) a commit for a change with no linked issue/PR at all -- every
fixture assumes an issue number exists -- or (b) a scenario combining the
new terse-Why requirement with the Closes-vs-Refs choice in the *same*
fixture (the corpus tests each separately). Both are real, disclosed gaps
for a future addition, not silently assumed covered.

## Iteration: issue #599, Commit-log rule revision (Option B)

Candidate edit: revise `SKILL.md`'s "Commit log" bullet from an absolute
ban on Why in the commit body to requiring a terse, present-tense Why (one
to a few sentences, not a design essay) alongside the issue pointer, per
git-community consensus ([beams], [kerneldoc], [progit] -- see the new
`## References` section); add that References section. No other bullet
changed. Full text: see this PR's diff.

Classification: **ordinary** (rewords required behavior; adds a new
requirement rather than only deleting text, so the pruning-only
lexicographic exception does not apply).

### Two fixture-assertion defects found and fixed during this iteration's own gate run, before any score was banked

Same recurring class `evaluating-skill-quality/split.md` already
documents multiple times (a construct-validity gap in the assertion, not
a rubric/skill regression):

1. **`commit-includes-terse-why.yaml`'s first-draft design used
   `output_contains_near` (window + no-blank-line) between the Why-phrase
   and the `Closes #N` trailer.** Self-testing against a realistically
   formatted response (subject / blank line / body / blank line /
   trailer -- the exact convention [beams] and [progit] themselves
   recommend) showed this fails a *correct* new-rule response, because
   the trailer is conventionally blank-line-separated from the body by
   every cited primary source. Simplified to a plain `output_contains`
   check; separately, the prompt was narrowed to ask for "just the commit
   message" (no explanation), because without that narrowing a model's
   own surrounding commentary mentioned the Why-phrase regardless of
   whether the commit itself contained it -- a false tie (both old- and
   new-rule baseline dispatches scored 1.0 against the original
   broader-prompt version). Verified via direct git-community-consensus
   reasoning and by re-dispatching both sides against the narrowed prompt
   before banking any score (see table below).
2. **`closes-when-fully-satisfied.yaml` and `refs-when-partial-work.yaml`
   each banned the sibling trailer form** (`Refs #212`, `Closes #340`)
   as a bare `output_not_contains` string. The new rule's more
   explanatory candidate responses correctly discuss the Closes-vs-Refs
   distinction in prose while recommending the right trailer -- e.g.
   "...Refs #212 (partial/related)" and "not Closes #340" -- a
   negation-trap false-fail of a correct response, the same class
   `gitapex_lint_fixture_assertions.py`'s `check_negation` rule targets for
   fixture-vs-corpus authoring but does not catch here (it checks static
   fixture/corpus consistency, not response-time contamination). Fixed
   by dropping the redundant negative ban on both fixtures -- the
   positive `output_contains` check (`Closes #212` / `Refs #340`) already
   fails a wrong-trailer response on its own, since a response
   recommending only the wrong trailer would not also contain the right
   one.

Neither fix touched a fixture's scenario/prompt substance (except
`commit-includes-terse-why.yaml`'s wording narrowing above, applied
before any score was banked on either side); `gitapex_lint_fixture_assertions.py`
run clean (0 warnings) against the final fixture set.

**Separately observed, unrelated to this edit, not fixed here (out of
scope for this bounded change):** `edge.yaml` (0.750) and
`no-auto-generated-adr.yaml` (0.833) scored below 1.0 in the candidate
test-split run purely because the model wrote "can't" where the fixture's
`output_contains: "cannot"` expects the unconctracted form -- a
pre-existing, model-phrasing-variance fragility on branches this edit
does not touch (their `SKILL.md` text is byte-identical old vs. new).
Disclosed here rather than silently absorbed; a future iteration on those
two fixtures specifically should relax the assertion (e.g. drop the
contraction requirement or accept either form).

### Gate result

One fresh dispatch per (fixture, skill-version) cell -- given the full
skill text (pinned via `git show HEAD:...` for the old side, the proposed
text for the new side) plus the fixture's prompt, asked to respond as
that skill, active -- scored with `gitapex_score_contract.py --assertions
<task.json> --output <run.txt>`. The other four branches (Code body, Test
code, Code comments, Stop boundaries) are byte-identical old vs. new, so
no old-skill dispatch was run for fixtures that exercise only those.

| Fixture | Split | Before (old text) | After (new text) |
|---|---|---|---|
| `guardrail.yaml` | train | 0.833333 | 1.000000 |
| `normal.yaml` | train | 1.000000 | 1.000000 |
| `commit-includes-terse-why.yaml` | selection | 0.666667 | 1.000000 |
| `closes-when-fully-satisfied.yaml` | selection | 1.000000 | 1.000000 |
| `edge.yaml` | test | -- (unaffected branch) | 0.750000 |
| `no-auto-generated-adr.yaml` | test | -- (unaffected branch) | 0.833333 |
| `no-bulk-rewrite.yaml` | test | -- (unaffected branch) | 1.000000 |
| `no-redundant-what-comment.yaml` | test | -- (unaffected branch) | 1.000000 |
| `no-staleness-only-deletion.yaml` | test | -- (unaffected branch) | 1.000000 |
| `refs-when-partial-work.yaml` | test | -- (unaffected branch) | 1.000000 |

Selection-split mean: before **0.833333**, after **1.000000**.
`gitapex_score_contract.py --compare-to 0.833333 --scores <after-selection-scores.txt>`:
**`1.000000 KEEP`**.

### Transfer check

Re-ran the 2 selection fixtures' candidate (new-text) version on Haiku
4.5 -- an adjacent, weaker model tier, distinct from this session's own
model -- same prompts, same scorer:

| Fixture | Haiku (new text) |
|---|---|
| `commit-includes-terse-why.yaml` | 1.000000 |
| `closes-when-fully-satisfied.yaml` | 1.000000 |

No regression below the no-skill baseline (not separately measured this
iteration -- disclosed gap, same shape `evaluating-skill-quality/split.md`
already carries for its own transfer checks) or below the strong-tier
score.

### Rejected-edit log

None this iteration -- no candidate wording was scored and discarded; the
two fixture-assertion defects above were caught and corrected *before*
any score was banked on either side, not after seeing a result, per this
skill's own Stop boundary against motivating or leaking from a scored
split.

### Verdict

Selection-split score strictly increased (0.833333 -> 1.000000), train
fixtures pass under the new text, all six unaffected-branch test
fixtures continue to pass (the two contraction-fragility scores are a
disclosed, pre-existing, edit-unrelated scorer quirk, not a regression),
and the transfer check on an adjacent model tier shows no regression.
**KEEP.**

## Iteration: issue #609, Commit-log citation and brevity-cap correction

Candidate edit: direct verification (real fetches of [beams]/[kerneldoc]/
[progit], not memory) after issue #599 merged found two inaccuracies in
its own References work: (a) the quoted phrase "long since forgotten the
immediate details of the discussion" is [kerneldoc]'s alone -- neither
[beams] nor [progit] contains it or its permanent-record framing -- but
the Commit-log bullet attributed it to all three collectively; (b) "one
to a few sentences, not a design essay" is not supported by any of the
three (none gives a sentence-count rule; [beams]/[progit] give a 72-char
wrap width, [kerneldoc] a different 75-column one, and [kerneldoc] if
anything argues for *more* detail for a reader "weeks, months or even
years later"). The candidate rewrites the same few sentences to fix both,
preserving "design essay" and "issue/PR body" verbatim since
`guardrail.yaml` (train) asserts on the former. Two further, independent
corrections travel in the same commit: the Code-comments bullet gains a
sentence disclosing that requiring a citable issue/PR/ADR is this
repository's own stricter-than-consensus policy (no source checked --
Google's C++ style guide, Ousterhout, Clean Code, kerneldoc's own
coding-style guidance -- restricts comments this narrowly), and the Notes
section gains a disclosure that no source checked gives any quantitative
comment-necessity threshold, mirroring `drafting-an-adr`'s own disclosed
ADR-significance-threshold silence. Full text: see this PR's diff.

Classification: **ordinary** (rewords existing text and adds new
disclosure sentences; not a pure deletion, so the pruning-only exception
does not apply).

### A new fixture was authored, empirically tested against its own
### hypothesis, and found not to discriminate -- disclosed, not hidden

`commit-why-keeps-distinct-reasons.yaml` was written specifically to test
whether removing the false brevity cap changes model behavior: a commit
with three distinct, concrete causal reasons (harder to compress than
two), asking for "just the message itself" (mirroring
`commit-includes-terse-why.yaml`'s own established fix for prompt-level
false ties), asserting only `output_contains` on one keyword per reason
(never `output_not_contains`/`_near`, and nothing about `Closes`/`Refs`,
so it does not quietly close this file's already-disclosed Blind spot
gap). Dispatched once against the old (merged) text and once against the
candidate text: **both scored 1.000000** -- a model asked for a terse
commit compressed all three real reasons into a few sentences regardless
of whether the routing rule stated a fixed sentence-count cap or not.
This is treated as a genuine finding, not iterated away: the fixture is
placed in **test** (read-once, non-gating), not `selection`, since it did
not demonstrate the hypothesized improvement and per this skill's own
Stop boundary against motivating or leaking from a scored split, its
design was not reworked after seeing this result. The true corpus size
(already stale at 12, not the previously-recorded 10, before this
iteration) updates to 13; `## Corpus size caveat` and `eval-status.md`'s
stale fixture-count text are both corrected in this same change.

### Gate result -- scored, tied, not a behavioral KEEP

Same fresh-dispatch-per-cell method as the #599 iteration above (full
skill text, old side pinned via `git show dc79540:...`, new side the
candidate; `gitapex_score_contract.py`).

| Fixture | Split | Before (old text) | After (new text) |
|---|---|---|---|
| `commit-why-keeps-distinct-reasons.yaml` | test (new) | 1.000000 | 1.000000 |
| `guardrail.yaml` | train | -- (unaffected assertions; re-run for `design essay` preservation) | 1.000000 |
| `normal.yaml` | train | -- (unaffected assertions) | 1.000000 |
| `commit-includes-terse-why.yaml` | selection | -- (unaffected assertions) | 1.000000 |
| `closes-when-fully-satisfied.yaml` | selection | -- (unaffected assertions) | 1.000000 |

Selection-split mean: before 1.000000 (already-recorded #599 baseline,
unaffected by this edit), after 1.000000 -- a **tie**.
`gitapex_score_contract.py --compare-to 1.000000 --scores <after-selection-scores.txt>`
would print `1.000000 REJECT` under the strict ordinary gate (a tie is
rejected, not kept).

### Why this is landed anyway, outside the scorer-gate's scope

Per `scorer-gated-skill-edits/references/worked-example.md`'s own Edit-B
precedent, a tied reword is rejected and not kept -- and that precedent
is followed here for the *behavioral* verdict: this candidate does not
pass the strict improve-or-reject gate, and is **not** claimed as a
scorer-validated behavioral improvement. But unlike Edit B (a plausible-
sounding reword with no independent justification beyond the hope that it
reads better), this candidate corrects a verified factual inaccuracy in
what the skill's own References section claims its cited sources say --
an axis of quality (is this prose accurate to its citations) that no
fixture in this corpus, existing or newly authored, has any way to
observe, the same way a broken link or a typo fix would not move a
behavioral score either. Manufacturing a fixture to force a non-tie for
a citation-accuracy correction would itself be the kind of construct-
validity violation `gitapex_lint_fixture_assertions.py` exists to catch (see
issue #609's own investigation for the reasoning). The corrected prose
is therefore landed as a documentation-accuracy fix, explicitly outside
this gate's behavioral jurisdiction, not smuggled through as a false
KEEP.

### Transfer check

Re-ran the 2 selection fixtures plus the new test fixture on Haiku 4.5 --
an adjacent, weaker model tier, same method as the #599 iteration's own
transfer check -- against the candidate (new) text:

| Fixture | Haiku (new text) |
|---|---|
| `closes-when-fully-satisfied.yaml` | 1.000000 |
| `commit-includes-terse-why.yaml` | 1.000000 |
| `commit-why-keeps-distinct-reasons.yaml` | 0.750000 |

No regression on the two selection fixtures. The new test fixture is
notable: on Haiku, the response dropped the third reason (Redis already
running for session storage) and kept only the first two (pod-restart
reset, per-pod counter scaling) -- the same real behavior the fixture was
designed to detect, but surfacing on the weaker tier where the strong-tier
dispatch (this session's own model, scored 1.000000 both before and
after) did not exhibit it. This is disclosed as a genuine, tier-dependent
finding, not smoothed over: removing the false brevity cap does not
reliably prevent a weaker model from dropping a real reason under
terseness pressure. No no-skill baseline was separately measured this
iteration -- the same disclosed gap `evaluating-skill-quality/split.md`
and this file's own #599 transfer check already carry.

### Rejected-edit log

**Behavioral verdict: REJECT (tie).** No candidate wording was discarded
after the fact -- the tie was the actual, accepted, disclosed result of
the one candidate scored, not a defect hidden by retrying. See "Why this
is landed anyway" above for why the corrected prose ships despite this.

### Verdict

**Behavioral gate: REJECT (tie) -- landed anyway as a documentation-
accuracy fix outside the gate's scope**, per the reasoning above. No
regression on any train, selection, or test fixture (all still score
1.000000 or their already-disclosed pre-existing baseline); the new test
fixture's tie is a genuine, disclosed finding about model behavior under
brevity-cap removal, not a defect.

## Iteration: issue #609 (continued), Code-comments/Notes governance-grounding correction

Candidate edit: the Code-comments bullet's citable-evidence disclosure
(added in the iteration above) said only that requiring a citation was
"this repository's own policy choice," with no positive grounding for
*why* recording a rejected alternative's rationale is a reasonable thing
to require at all. Direct verification this session (real `WebFetch`
reads, not memory) found that the underlying principle -- decisions and
their rationale should be documented and kept traceable to what they
concern -- is real, citable governance practice: ISO/IEC/IEEE 42010
("architecture description") requires that architecture decisions and
their rationale be documented and kept traceable to the stakeholder
concerns they address, and IBIS (Kunz & Rittel, Issues/Positions/
Arguments, 1970) has treated a rejected position's counter-argument as a
recordable, first-class part of a design's rationale for over fifty
years. The candidate rewrites the same disclosure sentence to cite both
([42010], [ibis]), while narrowing the "this repository's own choice"
claim to what it actually is: enforcing that principle at the granularity
of a single code comment via a *mandatory citation gate*, plus the
comment's specific one-line syntax/`why-not(#NNN):` prefix/`<=120`-char
cap -- none of which either source mandates. A second, smaller addition
to Notes discloses a real residual verification gap rather than hiding
it: [42010]'s own maintainer site (`iso-architecture.org`) returned an
HTTP 503 on every direct fetch attempted this session, so its
requirements are confirmed through [arc42]'s and Wikipedia's published
summaries, not a direct read of the ISO/IEC/IEEE 42010:2022 text itself;
and neither source makes "record the rejected alternative" specifically
a named requirement -- [42010] mandates decision-plus-rationale
traceability in general, [ibis]'s con-argument is the closest analogue
for a rejected position specifically, and the two claims are adjacent,
not identical. Three new `## References` entries ([42010], [arc42],
[ibis]) cite the sources actually fetched. Full text: see this PR's diff.

Classification: **ordinary** (rewords and extends existing disclosure
sentences with new citations; not a pure deletion, so the pruning-only
exception does not apply).

### No selection fixture exercises the changed branches at all -- a starker case than the prior iteration's tie

Unlike the Commit-log-bullet edit above, this candidate touches only the
Code-comments and Notes sections. Neither `selection` fixture
(`commit-includes-terse-why.yaml`, `closes-when-fully-satisfied.yaml`)
exercises either section -- both test only the Commit-log branch, which
this candidate leaves byte-identical. The selection-split mean therefore
cannot move by construction, not merely tie empirically: there is no
fixture in scope of the strict gate that could observe this edit at all.

The one **test**-split fixture that does exercise the changed branch,
`edge.yaml` (Code comments, "Declines a Why-Not Comment With No Citable
Source"), was scored with one fresh dispatch per side against only
`edge.yaml` -- real dispatches, not assumed, and not a full-corpus
selection-split gate table (see the prior iteration's "Gate result"
table above for that):

| Fixture | Split | Before (old text) | After (new text) |
|---|---|---|---|
| `edge.yaml` | test | 0.500000 | 0.500000 |

A genuine tie. Both responses correctly refuse the comment and cite
`citable` as required, but both also spell out the *correct future*
`why-not(#<real-number>):` syntax as part of explaining what the user
should do once a real issue exists -- which trips this fixture's own
`output_not_contains: "# why-not(#"` ban (intended to catch a model that
writes the comment anyway, not one that quotes the correct syntax while
declining). This is the same recurring fixture-assertion-fragility class
`split.md` already discloses for this file (the #599 iteration's
`edge.yaml`/`no-auto-generated-adr.yaml` "can't" vs. "cannot" note): a
construct-validity gap in the fixture's own assertions, identical old vs.
new, not a regression introduced by this edit. `guardrail.yaml` and
`normal.yaml` were also re-dispatched (fresh, not reused) as a sanity
check even though their Commit-log-only content is untouched by this
edit: `guardrail.yaml` scored 0.833333 old / 1.000000 new and
`normal.yaml` scored 1.000000 / 1.000000 -- since the branch they test is
byte-identical between old and new, this spread is ordinary model
response variance on an unrelated, unchanged branch (one dispatch phrased
"the PR/issue body," the fixture wants the literal order "issue/PR
body"), not signal attributable to this candidate, and is disclosed here
rather than mistaken for either a regression or an improvement.

### Why this is landed anyway, outside the scorer-gate's scope

Same reasoning as the prior `## Iteration: issue #609` section's own
precedent, one step further: that iteration's candidate at least *could*
have moved a fixture and happened to tie; this one's changed branches
have no fixture inside the gate's jurisdiction (`selection`) that could
observe them at all, and the one `test`-split fixture that comes closest
(`edge.yaml`) ties for a reason unrelated to the edit (a pre-existing
assertion fragility, not new to this candidate). Per
`scorer-gated-skill-edits/references/worked-example.md`'s Edit-B
precedent, a change with no demonstrated behavioral improvement is not
claimed as a scorer-validated KEEP. But this candidate corrects the same
class of defect the prior iteration's Track B already established as
outside the gate's behavioral jurisdiction: an accuracy/grounding
correction to what the skill's own prose asserts about its citations and
their justification, verified against real primary-source fetches this
session, not a routing-behavior change. Manufacturing a fixture
specifically to force this correction through the gate would repeat the
construct-validity violation `gitapex_lint_fixture_assertions.py` exists to
catch (see this iteration's own investigation, and the user's explicit
instruction this session to investigate primary sources rather than
leave an unsupported claim in place). The corrected prose is landed as a
documentation/governance-grounding-accuracy fix, explicitly outside this
gate's behavioral scope, not smuggled through as a false KEEP.

### Transfer check

Re-ran `edge.yaml` (the one test-split fixture exercising the changed
branch) on Haiku 4.5 against the candidate (new) text, same method as
prior iterations:

| Fixture | Haiku (new text) |
|---|---|
| `edge.yaml` | 0.500000 |

Identical to the strong-tier score (0.500000) and for the identical
reason (the same "# why-not(#" ban trips on a correctly-declined
response's own syntax example) -- no tier-dependent regression observed
for this candidate, unlike the prior iteration's disclosed tier-dependent
finding on `commit-why-keeps-distinct-reasons.yaml`.

### Rejected-edit log

**Behavioral verdict: REJECT (no selection-split fixture in scope; the
one relevant test fixture ties for a pre-existing, edit-unrelated
reason).** No candidate wording was discarded after the fact -- this is
the actual, accepted, disclosed result of the one candidate scored, not a
defect hidden by retrying.

### Verdict

**Behavioral gate: REJECT (out of scorer-gate scope by construction) --
landed anyway as a governance-grounding-accuracy fix**, per the reasoning
above. No regression on any train, selection, or test fixture (`edge.yaml`
ties for a disclosed, pre-existing, edit-unrelated assertion-fragility
reason; `guardrail.yaml`/`normal.yaml` variance reflects unrelated model
response noise on an untouched branch). The prior "no primary source
checked" disclosure for the citable-evidence requirement is now narrowed
to what remains genuinely ungrounded (the exact comment syntax and the
mandatory-citation *gate* itself), while the underlying governance
principle is grounded in [42010] and [ibis] -- with the residual
verification gap ([42010]'s own site returning HTTP 503, reliance on
[arc42]/Wikipedia secondary summaries) disclosed plainly rather than
smoothed over.

## Iteration: issue #609 (continued again), Issue/ADR number-conflation clarification

Candidate edit: reviewer feedback caught that the Code-comments format
line, `# why-not(#NNN): <=120 chars [-> docs/adr/NNNN-*.md]`, places two
different placeholders one character apart (`#NNN`, three digits with a
`#`; `NNNN`, four digits, no `#`) with nothing in the prose stating they
are two independent number spaces. Confirmed against
`drafting-an-adr`'s own convention (verified by reading that skill's
`SKILL.md` directly, step 11: an ADR's own sequence number is assigned by
"re-check[ing] the target directory's actual current highest number
immediately before writing," entirely independent of any issue/PR
number): the two are genuinely unrelated identifiers, so the visual
near-collision in the format line is a real clarity defect, not a
false alarm. The candidate adds one clarifying sentence immediately
after the format block stating plainly that `#NNN` is the citing
issue/PR number, `NNNN` is the ADR's own independent sequence number, and
the two must never be assumed equal.

Classification: **ordinary** (adds a clarifying sentence; not a deletion).

### A new fixture was authored to test the actual failure mode, empirically tied on both model tiers

`why-not-issue-and-adr-numbers-stay-distinct.yaml` (new, **test** split):
gives the model both a concrete issue number (#340) and a concrete,
different ADR sequence number (0012) in the prompt, and checks the
written comment preserves both numbers distinctly rather than
substituting one for the other (`output_not_contains: "adr/0340"` catches
the specific conflation failure this ambiguity invites -- reusing the
issue number as the ADR number). One fresh dispatch per side, per tier,
against only `why-not-issue-and-adr-numbers-stay-distinct.yaml` -- not a
full-corpus selection-split gate table (see the first iteration's "Gate
result" table above for that):

| Fixture | Tier | Before (old text) | After (new text) |
|---|---|---|---|
| `why-not-issue-and-adr-numbers-stay-distinct.yaml` | this session's model | 1.000000 | 1.000000 |
| `why-not-issue-and-adr-numbers-stay-distinct.yaml` | Haiku 4.5 | 1.000000 | 1.000000 |

A genuine tie on both tiers, not manufactured: when both numbers are
handed to the model concretely in the prompt, every dispatch on both
tiers correctly kept them distinct even under the old, ambiguous prose --
the failure mode the ambiguity invites (silently *deriving* one number
from the other) doesn't reproduce when the model only has to copy given
facts rather than infer a missing one. This is a real, disclosed finding
about *when* the ambiguity could bite (an underspecified prompt forcing
the model to invent or infer the ADR number, which this fixture does not
construct -- doing so risks the same construct-validity problem already
disclosed for this file's other new fixtures) rather than evidence the
defect doesn't matter: the reviewer's catch is about a documentation
clarity gap for a *human or model reading the skill's prose itself*, not
strictly about a reproducible generation-time error in this one concrete
scenario.

`edge.yaml` was re-dispatched once more against the new text as an
additional regression spot-check (not a second selection-scope claim):
scored 1.000000 this run, versus the 0.500000 recorded earlier in the
`## Iteration: issue #609 (continued)` section above for the same
fixture and the same "old" text. This is not an improvement caused by
this edit -- it is the same disclosed assertion-fragility class scoring
differently across independent dispatches for reasons unrelated to the
skill text (this run's response happened not to restate the correct
future comment syntax, so it didn't trip the `output_not_contains:
"# why-not(#"` ban that the prior dispatch tripped). Recorded here as
further confirmation of the pre-existing fragility, not as a second
gate result for this iteration.

### Why this is landed anyway, outside the scorer-gate's scope

Same reasoning as both prior `## Iteration: issue #609` sections: no
`selection`-split fixture exercises the changed branch, and the one
`test`-split fixture built specifically to probe this defect ties on
both model tiers for a reason that itself narrows (rather than voids)
the finding -- the concrete scenario tested doesn't force the ambiguity
to bite, not that the ambiguity was never real. `#NNN` and `NNNN`
sitting one character apart with no disambiguating text remains an
actual, reviewer-caught documentation defect, verified against
`drafting-an-adr`'s own real (and independently numbered) ADR-sequence
convention. Landed as a clarity-accuracy fix outside the gate's
behavioral scope, per this file's own established precedent, rather than
claimed as a scorer-validated behavioral KEEP it did not earn.

### Rejected-edit log

**Behavioral verdict: REJECT (ties on both tiers on the one fixture
built to probe this; no selection-split fixture in scope).** No wording
was discarded after the fact -- this is the accepted, disclosed result.

### Verdict

**Behavioral gate: REJECT (out of scorer-gate scope by construction) --
landed anyway as a documentation-clarity fix**, per the reasoning above.
The reviewer's catch (a real, human-legible ambiguity between two
adjacent-looking placeholders denoting two unrelated identifiers) is
corrected in the prose; the new fixture's tie on both tiers is disclosed
honestly as evidence about *when* the ambiguity manifests in generated
output, not as proof the defect was never real.
## Iteration: issue #631, Routing section restructure + exercises: declaration coverage

Candidate edit: issue #629's adversarial review of a proposed mechanical
"out-of-scope" classifier found that `skills/explaining-the-work/SKILL.md`
has no real section unit -- "Commit log," "Code comments," "Code body," and
"Test code" are bold bullet lead-ins nested under one single `## Routing`
heading, not headings themselves -- which blocked any mechanical way to
know which section a fixture's prompt is designed to exercise. The
candidate converts the 4 bold bullet lead-ins under `## Routing` into real
`### <label> -> <original text>` sub-headings, with **zero wording change**
beyond what the heading conversion mechanically requires (dropping a
now-irrelevant trailing comma/period right after the bold close;
capitalizing a word that is now sentence-initial in the body paragraph
that follows). Separately, `.github/scripts/gitapex_gate_split_fixture_coverage.py`
gains a third check (Check C): every fixture a `split.md`'s declared
`selection` split names must declare a well-formed `expected.exercises`
(non-empty list of section labels, mirroring
`gitapex_lint_fixture_assertions.py`'s `_is_real_dispatch_declaration` shape
validation) matching a real current `###`-level section label in the
sibling SKILL.md -- closing the specific vacuous-declaration gap issue
#629 found, without building the rest of the proposed classifier (a
CEILING/OUT_OF_SCOPE verdict remains explicitly out of scope, per that
issue's own research). `commit-includes-terse-why.yaml` and
`closes-when-fully-satisfied.yaml` (this file's 2 existing selection
fixtures) are backfilled with `exercises: ["Commit log"]`.

Classification: **pruning-only on the SKILL.md side** (markup restructure,
no wording change to any routing rule) **plus an additive, opt-in fixture
field and a new, independently-scoped CI check** -- neither branch removes
or reweights any existing behavioral rule.

### No selection fixture's score can move -- verified directly, not assumed

Both selection fixtures (`commit-includes-terse-why.yaml`,
`closes-when-fully-satisfied.yaml`) were re-dispatched, one fresh dispatch
per side, against the old (bullet-form) and new (heading-form) SKILL.md
text:

| Fixture | Before (old text) | After (new text) |
|---|---|---|
| `commit-includes-terse-why.yaml` | 1.000000 | 1.000000 |
| `closes-when-fully-satisfied.yaml` | 1.000000 | 1.000000 |

Both responses contained the same required substrings under both texts
("worker pool" / "Closes #401"; "Closes #212"), confirming the restructure
is behaviorally a no-op for the one branch these 2 fixtures observe, not
merely assumed from the wording being unchanged. `python3
evals/scripts/gitapex_lint_fixture_assertions.py` (full discovery-mode run) is
byte-identical before and after this change, diffed directly against a
pre-change checkout.

### Gate result -- not a scorer-gate candidate; verified by direct diff instead

This edit changes no assertion any existing fixture scores against (the
new `exercises:` field is read only by the new Check C, never by
`gitapex_score_contract.score()`), so there is no selection-split mean to compute
before/after -- the same "no fixture in scope of the strict gate could
observe this edit at all" situation as the `## Iteration: issue #609
(continued)` entry above, this time because the branch touched carries no
wording change at all rather than because no fixture exercises that
branch.

### Why this is landed anyway, outside the scorer-gate's scope

Same reasoning as this file's prior `## Iteration: issue #609` sections:
a markup-only restructure with a directly-verified-identical behavioral
surface, plus a new opt-in fixture field and CI check that no existing
scoring path reads, are outside `scorer-gated-skill-edits`' behavioral
jurisdiction by construction. Landed as a documentation/tooling-coverage
fix, not claimed as a scorer-validated behavioral KEEP.

### Rejected-edit log

None this iteration -- the restructure's behavioral-no-op status was
confirmed by direct dispatch before landing, not assumed and later found
wrong.

### Verdict

**Behavioral gate: N/A (no fixture assertion this edit could move) --
landed as a structural/tooling fix**, verified via direct real dispatch
(both selection fixtures score identically old vs. new text) and a
byte-identical `gitapex_lint_fixture_assertions.py` full-repo run, per the
reasoning above.

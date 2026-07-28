# gitapex history

Full-length provenance and audit-trail entries for this skill's
metadata/gitapex.yaml sidecar. Each heading below is pointed to by a
shortened `spec.references` entry (or `spec.lifecycle.experimental.reason`)
in the sidecar that exceeded the 500-char per-entry cap; this file holds
the complete, unabridged text, citation-converted to full GitHub URLs.

## Table of contents

- [Exposure and least-privilege model origin](#exposure-and-least-privilege-model-origin)
- [Relationship to Axis B](#relationship-to-axis-b)
- [Standalone skill decision](#standalone-skill-decision)
- [Evaluating-skill-quality self-review](#evaluating-skill-quality-self-review)
- [First battle-testing-a-skill round](#first-battle-testing-a-skill-round)
- [Confirming battle-testing-a-skill re-run](#confirming-battle-testing-a-skill-re-run)
- [External Codex review](#external-codex-review)
- [Isolated confirmation round](#isolated-confirmation-round)
- [Experimental lifecycle rationale](#experimental-lifecycle-rationale)

## Exposure and least-privilege model origin

This skill's model (exposure minimization and least privilege as two
domain-agnostic checks) was designed in
https://github.com/tvna/gitapex/issues/461, following a gap analysis
confirming that evaluating-deterministic-gate-quality's Blast-radius axis,
Security-level axis, and dimension 18 of its own references/dimensions.md
do not cover an artifact's steady-state exposure or privilege design --
Blast-radius grades bypass consequence, Security-level classifies tier by
external category name, dimension 18 covers only output redaction of a
secret already held, never the request/grant side of privilege or
interface/data minimization toward a dependency.

## Relationship to Axis B

Explicitly distinct from docs/agent-product-scope.md's Axis B
(https://github.com/tvna/gitapex/issues/307): that axis is a future
runtime enforcement adapter (least-privilege tool/filesystem/network
gating, actual enforcement code); this skill is a review procedure that
produces findings, never enforcement, and does not fulfill or duplicate
that axis. Named explicitly in SKILL.md's own Relationship to other
skills section because the resemblance in name is exactly the kind of
conflation docs/agent-product-scope.md's own Non-conflation rule warns
against.

## Standalone skill decision

Built as a standalone skill rather than a fifth axis on
evaluating-deterministic-gate-quality, decided directly with the operator
during https://github.com/tvna/gitapex/issues/455 and
https://github.com/tvna/gitapex/issues/456's own work: least-privilege
review in particular applies to any artifact (subagents, MCP servers, CI
workflow permissions, cloud service integrations), not only deterministic
gates, matching this repository's existing precedent of adjacent-but-separate
security-review skills related via relatedTo rather than merged
(screening-a-low-trust-contribution).

## Evaluating-skill-quality self-review

A same-session evaluating-skill-quality self-review (in-context, not a
fresh isolated dispatch -- the same harness-level isolation limitation
this skill family has disclosed against itself since
evaluating-deterministic-gate-quality's own build) found and fixed three
gaps in the initial build: declaring capabilityAssumption Adaptive with
zero references/ files (the worked example moved to
references/worked-examples.md, genuinely justifying the declaration); the
two checks reading as loosely related rather than one throughline (an
explicit unifying sentence added); and no Stop boundary ruling out
live-executing a possibly-hostile reviewed artifact, though the Procedure
was already designed to be static-read-only.

## First battle-testing-a-skill round

A real, non-waived battle-testing-a-skill pass (required for a new
skill's description, per gate_skill_audit_disclosure.py's own rule) ran
as a single non-recursive subagent dispatch (a prior fully-recursive-isolation
attempt on this same branch's earlier work had gotten stuck in a
self-dispatch retry loop and was abandoned; this round avoided that by
instructing the dispatch not to spawn further subagents). The dispatch
disclosed, observably, that this repository's own CLAUDE.md was visible
in its context with no available suppression mechanism, and marked every
PASS provisional on that basis -- the same harness-level isolation gap
named above, now also disclosed by this specific audit round. Overall
verdict: FAIL, with five concrete, evidenced gaps (of 22 fixed + 2
skill-specific added dimensions) -- no distinct handling for a
missing/unreadable/empty target (fixed: Procedure step 1 now separates
that from the zero-dependency Applicability-gate case); no
install/vendoring-time integrity Stop boundary (fixed: added, reusing
evaluating-deterministic-gate-quality's own proven wording); no boundary
against a persisted/incrementally-pressured 'already reviewed' claim,
single-turn or cross-session (fixed: added, reusing the same skill's own
combined wording for both cases); no delimiter-safe quoting requirement
protecting this skill's own emitted report from a hostile artifact's
quoted values (fixed: added to the existing secret-redaction boundary).
The fifth gap, no committed evals/ regression corpus, was left as an
accepted, disclosed launch gap (see
spec.lifecycle.experimental.reason in the sidecar, and
[Experimental lifecycle rationale](#experimental-lifecycle-rationale)
below) rather than built in this pass -- consistent with dimensions 13-16
failing on essentially every skill in this repository per
battle-testing-a-skill's own provenance-and-caveats.md, and with this
being a deliberately scoped-smaller first version. Several dimensions
(claim-provenance, deterministic-computation, regulatory-version,
auditor-evidence-trail, licensed-professional-deference) were correctly
graded N/A -- this skill's own subject matter does not touch
legal/regulatory/numeric-exactness territory.

## Confirming battle-testing-a-skill re-run

A confirming battle-testing-a-skill re-run (a second, independent
single-dispatch pass, explicitly instructed not to trust this file's own
narrative about what was fixed) re-graded all 24 dimensions against the
fixed content fresh: independently located and quoted each of the four
previously-fixed gaps (9, 12, 13/15, 17) as now present and correctly
worded in the current SKILL.md, confirming the fixes rather than assuming
them from this changelog. The fifth gap (14, the missing evals/
regression corpus) was independently reconfirmed absent by directly
listing the repository's evals/ directory (20 sibling-skill
subdirectories present, none named evaluating-attack-surface) -- an
objective, non-CLAUDE.md-dependent fact, so this one FAIL is not marked
provisional the way the eighteen PASSes are. Final disclosed verdict:
FAIL, solely on dimension 14, which is the same accepted, disclosed
launch gap named above and in
[Experimental lifecycle rationale](#experimental-lifecycle-rationale)
below -- not a new or surprising finding. A genuinely isolated
(CLAUDE.md-free) re-run to lift the provisional status on the eighteen
PASSes remains a named, deferred gap; see
[Experimental lifecycle rationale](#experimental-lifecycle-rationale).

## External Codex review

PR https://github.com/tvna/gitapex/pull/463's own external Codex review
found two real gaps after both audit rounds above: (1) Procedure step 1
let a reviewed artifact's own stated purpose (its own
comments/documentation) serve as the baseline both checks compare
against, with no skepticism -- a hostile or over-confident artifact could
self-justify any exposure or grant as necessary by claiming a broad
enough purpose; fixed by requiring the baseline come from the
dependency's own actual documented contract, a trusted specification, or
operator input, defaulting to indeterminate rather than trusting the
artifact's word alone. (2) references/worked-examples.md's
exposure-minimization inventory was factually wrong: it claimed the
create-issue POST body sent owner, repo, PR number, PR title, and PR URL,
when the actual .github/scripts/post_merge_retro.py code sends owner/repo
in the URL path (not the body), discards pr_title entirely before any
request is built (del pr_title), and POSTs a body of exactly three fields
(a generated title, a fixed boilerplate body embedding pr_number/pr_url,
and one label) -- corrected to match the real code, verified by reading
it directly rather than trusting the prior description.

## Isolated confirmation round

The operator directly questioned whether the two in-repo
battle-testing-a-skill dispatches' disclosed CLAUDE.md-visibility
contamination actually mattered, given both graded from inside the same
Agent-tool session. Rather than reassure without evidence: confirmed that
a Claude Code subagent dispatch cannot outrun this on its own (CLAUDE.md
auto-loads by directory ancestry, not by session identity, so any
Agent-tool dispatch run from inside this repository sees it regardless of
freshness), then ran a genuinely isolated third round -- a disposable
scratch directory with a filesystem-confirmed-empty CLAUDE.md/AGENTS.md
ancestry, only the two relevant skill directories copied in, invoked via
`claude -p` (not `--bare`, which requires ANTHROPIC_API_KEY directly and
fails under this environment's OAuth) with Task/Agent tools withheld to
prevent recursive dispatch. The isolated run answered the question
directly: the result DID change. It found one real, evidenced FAIL
neither CLAUDE.md-primed round had surfaced -- dimension 18,
claim-provenance/source-grounding: the already-fixed artifact-self-report
gap only stopped the reviewed *artifact* from self-justifying its own
scope; nothing stopped the *reviewer* from asserting what a dependency's
real API contract requires from unverified memory. Concretely, the
worked example itself enacted this exact gap, claiming GitHub's
issue-creation API requires all three fields it sends. Fetched GitHub's
own current REST API reference directly (not recalled) to check this
claim: only `title` is API-required; `body` and `labels` are optional,
sent because they serve this specific artifact's own documented
function, not because the bare API mandates them -- the worked example's
own prior claim was corrected to state this precisely. Procedure step 1
gained a matching rule: the same skepticism that already bars trusting an
artifact's self-description now also bars trusting the reviewer's own
unverified recollection of a dependency's contract, with the identical
indeterminate fallback when it cannot be checked. Also surfaced, not a
new finding: dimension 14 came back INDETERMINATE rather than FAIL in
this isolated run, correctly, since the scratch copy had no evals/
directory reachable to inspect at all (a sandboxing artifact, not
evidence the real gap changed shape) -- this run explicitly declined to
treat the target's own metadata self-report of that gap as a substitute
for evidence it could not itself inspect, applying the skill's own
dimension-13 discipline reflexively to its own grading. With this round's
CLAUDE.md-free confirmation, the isolation caveat on the eighteen
previously-provisional PASSes is resolved; the sixteen dimensions that
PASSed in this isolated run (17, 22, and 23 domain-added dimensions
differ slightly in numbering from the prior rounds' own ad hoc additions,
not a discrepancy in substance) are no longer provisional.

## Experimental lifecycle rationale

First version of this skill category, built from a gap analysis
conducted directly during this build
(https://github.com/tvna/gitapex/issues/461) rather than a dedicated
pre-written research report -- this repository does not mandate one for
every new skill; only evaluating-deterministic-gate-quality's own build
did that, confirmed by checking other 'first of category' skills' own
lifecycle fields (screening-a-low-trust-contribution,
battle-testing-a-skill, scorer-gated-skill-edits,
auditing-agent-product-scope all shipped with no lifecycle field at
all). Scoped deliberately smaller than
evaluating-deterministic-gate-quality's four-axis/eighteen-dimension
build: two checks (exposure minimization, least privilege), one worked
example (moved to references/worked-examples.md during the
evaluating-skill-quality self-review round, so a references/ split does
exist from launch) -- deferred rather than front-loaded, the same way
evaluating-deterministic-gate-quality itself grew a fourth axis in a
later, separate PR (https://github.com/tvna/gitapex/pull/442). Hardened
by one evaluating-skill-quality self-review round, two in-repo
battle-testing-a-skill rounds (five gaps found and fixed, one accepted
launch gap), an external Codex review (two further gaps found and
fixed), and a genuinely isolated CLAUDE.md-free battle-testing-a-skill
confirmation (one further real gap found and fixed -- dimension 18,
reviewer-side claim-provenance -- then independently re-verified fixed in
a second isolated pass) before shipping -- full detail in the
spec.references entries above (and this file's own preceding sections).
Final state: 18 of 22 fixed dimensions plus this skill's own
domain-added dimensions PASS with the isolation caveat fully resolved
(not merely disclosed-and-accepted); dimension 14 (no evals/ regression
corpus) remains the one open, accepted, disclosed gap, confirmed absent
by direct inspection of this repository's real evals/ directory (not
merely the isolated sandbox's own necessarily-INDETERMINATE read, which
lacked repository-root access to check at all). Deferred, named
explicitly: additional exposure/privilege sub-checks beyond the two
shipped; a committed evals/ regression corpus (eval-coverage-disclosure
WAIVED at launch, matching evaluating-deterministic-gate-quality's own
disclosed gap at its own launch).

# Tidy-first behavior-preservation gate + concentrated simplicity/anchoring review agent

Design-only companion doc for a new tracking issue, child of #82,
expanding #123's seed-gate scope. Answers a user pushback on #142: that
design's two signals (instruction-token count, repair-free-merge rate)
are purely quantitative and capture neither qualitative output
variance/anchoring bias nor CLAUDE.md section 4's simplicity discipline.
Also resolves #141's bullet 3.5 open question ("will gitapex ship a
concentrated review job, and under what name?") -- yes, designed here.

## Origin

User-supplied framing (2026-07-18, translated): does the spec measure
qualitative elements like output fluctuation/variance -- for example,
should gitapex judge whether to enforce a coding discipline like Kent
Beck's "tidy first" against the tendency for LLM output to get pulled
toward existing codebase patterns? Evaluating adherence to section 4's
simplicity discipline is also important.

This names two genuinely distinct problems, kept separate below because
they have different natures: one is mechanically checkable, one is not.
Blurring them into a single mechanism would either over-claim
determinism for a semantic judgment, or under-use a real mechanical
proxy where one exists.

## Problem A: `gate-tidy-first` -- a mechanical behavior-preservation check

### Core design

A commit titled `refactor(scope): ...` asserts, per `docs/versioning.md`'s
existing commit convention, that it is behavior-preserving. That
assertion is falsifiable in CI: check out the commit's immediate parent,
run the test suite, record per-test outcomes (`test-id -> pass|fail`);
check out the commit itself, run again; diff the two outcome maps.

**Verdicts:**
- Any test present in both runs flips outcome -> **fail**: the
  behavior-preservation claim is false; the commit is mislabeled (split
  it, or retitle it `fix`/`feat` -- which correctly re-arms #138 G4's
  exemption logic for that commit).
- Identical outcome maps, including identical *failures* -> **pass**. A
  red base stays attributable: preserving existing failures IS behavior
  preservation, so the gate never wedges on an already-red parent.
- A collected-test-set delta (tests added/removed/renamed by the
  refactor) is checked against coverage of the touched production
  lines, not just test-ID presence (caught in PR #146 review, applied
  2026-07-18: a naive warn-only delta lets a behavior-changing refactor
  hide by deleting or renaming exactly the test that would have flipped
  -- no shared ID survives to prove anything, so the claim passes
  unchecked). If a line the commit touches was covered by a test at the
  parent SHA and is covered by no test at the commit SHA (coverage
  regressed, not merely renamed), that is **indistinguishable from
  hiding a regression and fails**, same severity as an outcome flip --
  it does not matter whether the removal was malicious or accidental,
  the behavior-preservation claim is unverifiable either way. A delta
  that is pure addition, or a rename/move where the touched lines remain
  covered under the new test id, **warns** (or passes with an
  informational note) -- only a net coverage loss on touched lines is
  the failable signal.

**Test suite definition.** Whatever the repo's declared runner executes
-- for gitapex today, `uv run pytest` (`pyproject.toml`'s `testpaths` +
`pythonpath` make this deterministic and hermetic via `uv.lock`). For the
mixed-language future, the policy source maps commit *scope* to a suite
command: `refactor(plugin)`/`refactor(cli)` each key a `[suite.<scope>]`
table (`cli` reserved for `cargo test` once the Rust product exists).
Unknown scope falls back to the default suite -- reusing the
already-established product-scoped commit convention as the routing key
instead of inventing a new one.

**Per-commit, not per-PR.** Tidy-first is a commit-granularity
discipline; a PR-boundary check would let a mixed structural+behavioral
commit hide inside a PR whose endpoints legitimately differ in behavior.
The gate iterates only commits titled `refactor(...)` in the PR range --
non-refactor commits make no claim and are skipped, so a well-formed
tidy-first PR (a `refactor(...)` commit, then a `feat(...)` commit)
passes exactly as the discipline prescribes. Cost is bounded by
`max_checked_commits` (default 5; above it, fail with "split the PR" --
consistent with #138 G4's narrow-change-surface stance).

**No tests for the touched code, ever: warn, not fail-closed. Coverage
that existed and disappeared: fail.** These are different signals,
argued differently. Code with **zero coverage at both the parent and the
commit** (never tested at all) warns, not fails: (1) fail-closed there
would forbid refactoring exactly the untested code that most needs
tidying ("tidy first to make the change easy"), and (2) it creates a
perverse incentive to mislabel refactors as `fix` to dodge the gate --
corrupting the very `refactor(...)` signal both #138 G4 and this gate
depend on. Using coverage instrumentation (`pytest --cov`), the gate
computes whether any test executed the non-test files the commit
touched; zero coverage at both ends produces a `claim-unverified`
**warn** annotation. This mirrors #138 G2's `proxy-evidence-verification`
honesty: this leg's registry status is `partial` forever, stated rather
than overclaimed. Code that **was** covered at the parent and is not
covered at the commit is the different, failable case described above --
the claim was verifiable and the evidence for it was removed, which the
gate treats as a false claim rather than an absent one. Infrastructure
errors (the suite won't collect at either SHA) fail closed -- an
unrunnable claim on the `ci` plane is indistinguishable from a false one
(#131 principle 6, matching #142's fail-closed-on-unverifiable stance).

**New sibling gate, not an extension of #138 G4 -- and NOT sharing a
trigger.** Three reasons for the sibling-not-extension choice: G4 is
*static* (numstat arithmetic, cheap on `pre-push` + `ci`); this gate is
*dynamic* (executes the suite twice per commit, `ci` plane only -- a
pre-push double suite run would be hostile to the push loop). G4's
failure asks for a justification section; this gate's failure is a
falsified *claim* no prose can justify -- different failure semantics,
the same two-gates-not-one rationale #138 already used for its own Gate
3.

**Correction (caught in PR #146 review, applied 2026-07-18): they do
NOT share a trigger, only a regex pattern, and the earlier "shared
trigger convention" wording was imprecise enough to be wrong.** #138 G4
and `docs/versioning.md`'s commit convention key `gate-refactor-net-growth`
off the **PR title/body** (a PR titled `refactor(scope): ...` triggers
the net-growth check for the PR as a whole -- net line growth is a
whole-changeset property, so PR granularity is correct for it).
`gate-tidy-first` keys off **individual commit subjects** in the PR
range (behavior-preservation is a per-commit claim, so commit granularity
is correct for it). Treating these as one shared trigger is actively
wrong in both directions: retitling a single commit to `feat` would not
exempt a `refactor`-titled PR from G4 (G4 never reads commit subjects),
and a `refactor`-titled commit inside a `feat`-titled PR would silently
bypass G4 entirely (G4 never reads that PR's commits). The two gates
share only the **regex** that recognizes the `refactor(scope): ...`
shape (moved into `tidy-first-policy` below as the single pattern
source, referenced by both gates' `policy_refs`), applied at each gate's
own, deliberately different, granularity -- not a shared trigger. G4's
existing PR-title/body trigger in #138 is unchanged by this design.

### Registry JSON

```jsonc
// policy_sources[]
{ "id": "tidy-first-policy", "path": ".gitapex/policies/tidy-first.toml", "format": "toml",
  "authority": "the refactor(scope): ... recognition regex (the single pattern source; consumed by gate-tidy-first at commit-subject granularity and referenced, not triggered, by gate-refactor-net-growth's separate PR-title/body check); per-scope suite commands ([suite.plugin] = 'uv run pytest', [suite.cli] reserved); max_checked_commits; outcome-comparison rules (shared-id flips fail, coverage-regressed deltas fail, coverage-preserved/pure-addition deltas warn); zero-coverage-at-both-ends claim-unverified warn contract" }

// gates[]
{ "id": "gate-tidy-first", "kind": "script", "script": "scripts/gate_tidy_first.py",
  "rule": "each PR commit titled refactor(...) is behavior-preserving by proof: per-test outcomes at the commit equal outcomes at its parent; a shared-test flip fails (mislabeled commit: split or retitle); a test-set delta that drops coverage of touched lines previously covered also fails (indistinguishable from hiding a regression); zero coverage of touched files at both parent and commit warns claim-unverified (partial leg, stated)",
  "planes": ["ci"], "trigger": "pull_request opened/synchronize, iterating refactor(...)-titled commits in the merge-base range (commit-subject granularity; independent of gate-refactor-net-growth's PR-level trigger)",
  "fail_policy": "closed (unrunnable suite at either SHA fails; the claim is unverifiable)",
  "policy_refs": ["tidy-first-policy"], "cluster": "change-surface", "tracking_issue": null }
```

## Problem B: `review-simplicity-anchoring` -- the concentrated semantic review agent

This resolves #141's bullet 3.5 open question directly. Section 4
simplicity adherence and anchoring-bias detection ("did the output copy
an existing codebase pattern where a materially different, simpler
approach was available") are semantic judgments no diff-shape or
token-count gate can make. CLAUDE.md section 3 already draws this exact
line: "Run review/repair agents at one concentrated point, only after
the deterministic gates pass; they handle the semantic judgment
determinism cannot." #141 rated this bullet class (b) -- needing one
human decision before a gate could be designed. The user's pushback in
this conversation resolves that decision: yes, design it now.

### When it runs

One PR-level CI job named `concentrated-review`, declaring `needs:` on
every deterministic gate job (the #138/#140/#141 gates plus Problem A's
`gate-tidy-first`). It runs exactly once per PR revision, only after all
mechanical checks pass -- never spent reviewing a PR that will bounce on
a cheap check anyway. This job's existence also makes #141's deferred
`needs:`-ordering lint designable: `registry-self-validation` (#140 C1)
gains a rule that any `kind: "agent"` gate's CI job must `needs:` every
`kind: "script"` ci-plane gate.

### What it evaluates

The agent receives the full checkout at the head SHA (not the diff
alone -- anchoring detection is impossible without codebase context), the
diff, and the linked issue body (handled as untrusted data per CLAUDE.md
section 2 / #138 G6's framing). Two rubric halves, each producing
structured findings (`rule_id`, `location`, `finding`,
`simpler_alternative`, `cited_precedent`, `confidence`):

1. **Anchoring-bias detection.** For each substantive hunk: name the
   existing codebase pattern it imitates (file and lines -- a citation
   requirement, so a "vibes" answer is structurally impossible), then ask
   whether a materially simpler approach was available that copying the
   precedent foreclosed. "No anchor found" is a mandatory explicit
   outcome, not silence.
2. **Section 4 sub-rules as concrete prompts, not vague vibes:** unused
   configurability/abstraction (one caller, speculative parameter); error
   handling for scenarios no human input can reach (bullet 4.2, rated
   class (c) in #141 -- exactly what only this agent can see); 200-lines-
   that-could-be-50 compression candidates; the inverse check -- did a
   simplification remove a defense layer (cross-referencing #141
   candidate A5's removal-justification surface); and the closing "would
   a senior engineer call this overcomplicated, or unsafe?" with a named
   answer per changed surface.

### Verdict: advisory by construction, and why

Output is one idempotent marker-delimited PR review
(`<!-- gitapex-review v1 -->`, event `COMMENT`, never `REQUEST_CHANGES`),
replacing its prior comment per revision -- the same structured-body
pattern as #142's measurement comment. It never blocks. Justification
against #131: a blocking gate must be reproducible and appealable by
rerun; an LLM verdict is stochastic and unauditable, so blocking on it
would install an authority zero-trust cannot verify -- and since the diff
and issue text it reads are untrusted (section 2), a blocking semantic
reviewer becomes a prompt-injection-to-merge-veto escalation path.
Advisory-plus-human caps that blast radius: the human decides, matching
CLAUDE.md's own doctrine that semantic judgment is not a deterministic
pass/fail, and #140 candidate 5 / #142's standing advisory-forever
precedent for non-deterministic signals. The job itself fails open
(agent error produces an annotation, never a red check), enforced by the
schema constraint below, not just promised in prose.

### Relationship to #142 -- stated, not implied

#142's signals are the trend-level radar: deterministic, post-merge,
lagging, answering "is quality-per-instruction-token degrading across
merges." This agent is the point-in-time semantic check: pre-merge,
leading, answering "is this specific PR simple and un-anchored." No
contradiction is possible by construction (neither consumes the other's
output). One deliberate coupling exists: an accepted finding fixed by a
post-open commit counts as a repair in #142's quality signal --
correctly, since the retrospective loop then classifies it (missing
gate / unclear instruction / human call per CLAUDE.md section 3's own
taxonomy), and recurring finding categories become new deterministic
gate candidates. The agent feeds the harness; it does not replace it.

### Registry JSON + minimal schema extension

The phase-0 shape (#123, per the original governance-design doc) assumes
`kind: "script"` plus a `script` path; an agent dispatch has neither.
Minimal extension, mirroring how #140/#142 already added
`fail_policy`/`backstop`/`cluster` as routing metadata: add enum value
`kind: "agent"` with two fields -- `agent_prompt` (a path under
`.gitapex/policies/`, making the rubric a governed instruction file that
becomes trusted only through the code-owner merge gate, per section 2)
and `verdict` (schema-constrained to `"advisory"` when `kind` is
`"agent"`, so `registry-self-validation` deterministically forbids any
agent gate from ever being registered as blocking -- a mechanical gate
guarding the semantic gate's non-authority).

```jsonc
// policy_sources[]
{ "id": "concentrated-review-rubric", "path": ".gitapex/policies/concentrated-review-rubric.md", "format": "markdown",
  "authority": "review-agent rubric: anchoring-bias citation protocol, section-4 sub-rule prompts, finding schema, comment marker syntax, model/effort pin" }

// gates[] (requires the kind:"agent" schema extension above)
{ "id": "review-simplicity-anchoring", "kind": "agent", "agent_prompt": ".gitapex/policies/concentrated-review-rubric.md",
  "rule": "after all deterministic ci gates pass, one review agent with full-checkout context evaluates the PR for anchoring bias (cited precedent required) and CLAUDE.md section-4 simplicity/safety adherence; posts one structured advisory review, human decides",
  "planes": ["ci"], "trigger": "pull_request job 'concentrated-review', needs: all kind:script ci gates",
  "verdict": "advisory", "fail_policy": "open (agent failure annotates, never blocks)",
  "policy_refs": ["concentrated-review-rubric", "untrusted-text-patterns"],
  "cluster": "semantic-review", "tracking_issue": null }
```

## Key contested calls, summarized

- Problem A is fail-closed on unverifiable claims but warn-only on
  test coverage that was absent at *both* SHAs -- fail-closed there
  would punish refactoring untested code and corrupt the `refactor(...)`
  label signal itself. Coverage that existed at the parent and is gone
  at the commit is a different, failable case (see below).
- Problem A is a new sibling of #138 G4, not an extension of it -- static
  vs. dynamic checks, different planes, different failure semantics, and
  (revised after PR #146 review) genuinely different trigger granularity
  -- they share a regex, not a trigger.
- Problem A fails, not warns, when a `refactor(...)` commit's test-set
  delta drops coverage of previously-covered touched lines -- a warn-only
  delta let a behavior-changing refactor hide by deleting or renaming
  exactly the test that would have exposed it, leaving no shared test ID
  to flip (PR #146 review finding, fixed 2026-07-18).
- Problem B is advisory-forever with the constraint schema-enforced, not
  just promised in prose -- an unreviewable stochastic judgment must
  never hold merge authority under #131's zero-trust principles, and its
  untrusted inputs make blocking it an injection-to-merge-veto escalation
  path.

## Non-goals

- No code, no `.gitapex/` files, no `scripts/` edits -- design only.
- Not implementing the `kind: "agent"` schema extension itself, only
  specifying its minimal shape -- schema-owner adoption is a separate
  step, same discipline as #140/#142's own proposed field additions.
- Not making either mechanism blocking beyond what's argued above:
  `gate-tidy-first` blocks on a falsified behavior-preservation claim
  (a real, verifiable fact); `review-simplicity-anchoring` never blocks
  on its own authority.

## Acceptance criteria

- [ ] Problem A and Problem B are kept structurally separate, not
      blurred into one mechanism.
- [ ] Problem A's mechanical proxy is grounded in a real, checkable
      claim (behavior preservation via test-outcome diffing), not a
      heuristic guess.
- [ ] Problem B's advisory-only posture is justified against #131's
      zero-trust principles, not just asserted.
- [ ] The `kind: "agent"` schema extension is minimal and mirrors the
      routing-metadata-only discipline #140/#142 already established.
- [ ] Relationship to #142's existing signals stated explicitly, with no
      unstated overlap or contradiction.

## Related Issue

Child of #82. Expands #123's seed-gate scope, same pattern as #138,
#139, #140, #141, #142. Resolves #141's bullet 3.5 open question.
Cross-references #131 (zero-trust principles for Problem B's advisory
posture), #138 (Gate 4's `refactor(...)` convention, extended by
Problem A), #142 (relationship to the quantitative proportionality
signal, stated explicitly above).

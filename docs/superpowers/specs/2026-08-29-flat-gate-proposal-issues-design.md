# Flat gate-proposal issues for merge-retrospective: design

Date: 2026-08-29

Refs #1405 (refs #1402, #1395, #205, #191, #187, #118). Design-then-implement
doc, per this repo's own plan-first discipline. Supersedes this file's own
first version (a GitHub-native sub-issues design), rejected after adversarial
review -- see "Rejected: GitHub-native sub-issue hierarchy" below.

## Context

`skills/merge-retrospective/SKILL.md`'s Step 1 requires, every cycle, a
state-unfiltered sweep of every `retrospective`-labelled issue, checking
each one's proposed gate against a two-signal resolution test (a commit on
the checked ref citing the issue's own number, AND `.gitapex/ssot.json`
`gates[].tracking_issue` naming that same number). Step 5 then requires any
issue found unresolved this way to be re-escalated into the new
retrospective's own body as a "Carried-forward gate" entry, and its own
Stop boundary + Step 5's zero-repair fast-close rule together mean: **any
retrospective issue that carries even one such entry must stay open**,
indefinitely, with no closing mechanism the skill itself provides.

A live sweep run against this repository on 2026-08-29 (retrospective for
PR #1402, filed as issue #1405) found 345 `retrospective`-labelled issues
(state-unfiltered): 64 gate-less (CI-stub/zero-repair markers, correctly
excluded), 3 resolved, and **277 unresolved**. A sample of the 30
newest-first issues in that set showed 28 of 30 still `OPEN`. Issues #118
and #187 -- both still in the unresolved set -- independently converged on
the same diagnosis years apart: "the retrospective mechanism currently
converts repairs into issues, not into gates" (#187's own wording); #191
re-confirmed it a cycle later. Of 345 retrospective-proposed gates, only 3
have ever cleared the two-signal check as built.

The two-signal check's own design (issue #709) is sound on its own terms --
a citing commit alone is not proof a gate was built, so both signals are
required. The actual root cause of the 277-item backlog is structural,
independent of that check's strictness: this repository's own common
practice is to re-escalate an unresolved proposal into a **newly-filed,
separately-numbered** issue (`#205`'s own Repairs 5 & 8 -> `#529`; `#191`'s
own carried-forward items -> `#526`/`#516`) rather than to implement the
gate under a commit citing the *original* retrospective's issue number.
The two-signal check, applied to the original number, then never clears --
even after the work is genuinely done -- because it never checks the
*re-filed* number. This produces both symptoms at once: an ever-growing
`unresolved` count (bullet-point debt that never shrinks under the current
citation convention) and an ever-growing `OPEN` retrospective-issue count
(each new cycle re-discovers the same debt and is barred from closing while
it carries any of it forward).

Filing a written proposal to fix this pattern does not, by itself, change
anything: `skills/merge-retrospective/SKILL.md`'s own literal text is what a
future session actually executes, and this repository's own 345-issue
sample is direct evidence that a proposal recorded only in an issue body,
with no corresponding change to the instruction file it critiques, has a
1% or lower historical rate of ever being acted on. This design is
therefore scoped to the instruction-file and script changes themselves, not
to a persuasive case for making them.

## Rejected: GitHub-native sub-issue hierarchy

This design's own first draft proposed consolidating every
`missing-deterministic-gate` finding under one long-lived "Gate Backlog"
parent issue via GitHub-native sub-issues, discovered by a fixed
label+title lookup. An adversarial review (run against that draft, with
every load-bearing claim independently re-verified against GitHub's own
documentation and this repository's actual tool schemas and workflow files
before being accepted) found the mechanism itself, not merely its
implementation detail, to be the wrong fit:

- **A hard platform limit the single-parent design cannot survive.**
  GitHub's own documentation (docs.github.com, "Adding sub-issues") states
  a parent issue may hold at most 100 sub-issues. This repository's own
  measured rate (277 gate findings across 345 cycles, ~0.8 per PR) would
  exhaust that cap in roughly 125 merges even ignoring the pre-existing
  backlog -- at which point sub-issue filing starts failing, and the
  design's own "don't close on a failed filing" safeguard reinstates the
  exact stuck-open failure mode this redesign exists to remove.
- **A write-permission gap the design didn't specify around.** The daily
  CI check (`retrospective-gate-drift.yml`) runs with `contents: read`,
  `issues: read`, `pull-requests: read` only (verified directly in the
  workflow file) -- it cannot create the parent issue were one ever
  missing, an unaddressed day-one bootstrap gap.
- **A race condition with no deterministic resolution.** GitHub's API
  offers no atomic find-or-create for an issue; two retrospective cycles
  racing to create the same missing parent could both succeed, producing
  duplicate parents with no specified reconciliation.
- **A cited tool that does not do what the design assumed.** The design's
  own first draft named `mcp__github__sub_issue_write` as the filing
  mechanism; that tool's actual schema (verified directly) only attaches
  an *already-existing* issue as a sub-issue via its internal database ID
  (`sub_issue_id`, explicitly documented as distinct from the issue
  number) -- it cannot create anything. (The corrected primitive,
  `mcp__github__issue_write` method `create` with `parent_issue_number`,
  does support one-call creation-plus-attachment and was not the design's
  own error once corrected -- but the review still stands: the
  architecture around it is the actual problem, not only this one
  citation.)
- **A closed-state/verification gap.** The design's own periodic
  resolution audit covered only the parent's *open* sub-issues; a
  sub-issue closed without ever passing the two-signal check silently
  exited both the completion summary's "resolved" count and the audit's
  own scope -- unverified closure became indistinguishable from verified
  resolution.

None of these are implementation nits fixable by adjusting the same
architecture -- they are direct consequences of routing every gate finding
through one shared, GitHub-capacity-bounded, concurrently-written parent.
The design below removes the parent entirely.

## Decisions

### 1. Flat, independently-labelled issues -- no hierarchy of any kind

Every `missing-deterministic-gate`-classified finding -- whether discovered
fresh in the current cycle's own Repairs section, or (during any future
manual audit of the pre-existing 277-item backlog) carried forward from an
older retrospective -- is filed as its own **ordinary, standalone GitHub
issue**, carrying a fixed label (see Decision 6 for where that label's
literal name lives) and a `Refs #<retrospective-issue>` back-link. No
parent issue, no sub-issue relationship, no singleton of any kind.

This removes the *shared-singleton* failure modes named in "Rejected"
above by construction: plain issue creation (`issue_write` method
`create`) carries no 100-item cap, and no elevated CI permission (label
search is a read operation the CI workflow's existing `issues: read` scope
already covers). It does not, by itself, remove every possible race: two
attempts to file the *same* repair (a retry racing an in-flight first
attempt, or two sessions independently handling the same merge) could
each create a duplicate if filing were pure blind creation. The fix is the
same discipline Step 0's own CI-stub dedup already uses, applied to each
individual filing rather than to a shared parent: search for an
already-filed issue with this repair's own deterministic title (exact
equality, never substring) *before* creating anything; ambiguous results
fail closed rather than guessing (see Error handling). "Deterministic"
means reproducible from the repair's own already-fixed data alone, so a
retry regenerates byte-for-byte the same title to search for: `gate-proposal:
<repair's own one-line label> (retro #<retrospective-issue-number>)` --
both inputs are already fixed by the time Step 5 runs (the label from
Step 2-4's own classification, the retrospective's own issue number from
Step 0), so the same repair always searches for, and would create, the
exact same title on every attempt. This is a per-item
search against the whole repository, not a per-parent find-or-create
against one shared, contended resource -- the actual property the
"Rejected" section's own race finding required removing.

Rejected alternative: **a single issue's body as an append-only checklist**
(each finding becomes one more Markdown checkbox line in one persistent
issue, rather than its own issue). Rejected because appending requires a
read-modify-write cycle against shared issue-body text -- concurrent
retrospective cycles racing to append would be *more* exposed to a lost-
update race than the singleton-parent design's own already-rejected
find-or-create race, and a checklist line has no independent label, state,
or two-signal-checkable identity of its own the way a real issue does.

Rejected alternative: **only change the closing rule, keep findings
embedded inline in the retrospective issue's own body** (no separate
tracking artifact of any kind). Rejected because it trades the unbounded-
open-issue-count problem for a different one: once every retrospective
closes immediately regardless of content, `OPEN`/`CLOSED` state stops
signalling "still needs attention" at all, and backlog visibility would
depend entirely on re-running the two-signal script's own output with no
GitHub-native affordance (label search, saved filter) standing in for it.

### 2. Unify "this cycle's own Repairs" and "carried-forward from history" into one filing path

Unchanged in substance from the rejected draft: a `missing-deterministic-gate`
finding is filed the moment it is classified, regardless of whether it
came from this cycle's own Step 2-4 enumeration or a future manual sweep of
the legacy backlog. This collapses the retrospective issue's own role: it
no longer *holds* a proposed gate (that now always lives in its own
standalone issue), it only *records* what happened and which issue number
now owns follow-through. `unclear-agent-instruction` and
`external-human-decision` repairs are unaffected -- neither proposes a
gate to track, so neither gets a standalone issue; both stay recorded
inline exactly as today.

### 3. Retrospective issues close immediately once every finding is filed and verified -- with the existing attended/unattended distinction extended to every close, not only the zero-repair case

A zero-repair cycle has nothing of its own to file (the pre-existing
277-item backlog is explicitly out of scope, per Non-goals below), so it
fast-closes exactly as the existing zero-repair path already intends. A
cycle with one or more `missing-deterministic-gate` repairs files each as
its own labelled issue, re-fetches to confirm each filing actually
succeeded before recording it, and then also closes -- but this close now
follows the *same* attended/unattended rule the current zero-repair
fast-close path already uses (Step 5's own existing text), extended to
every close this design newly introduces, not left implicit: an attended
session previews the exact close and gets an explicit go-ahead; an
unattended run (no session able to respond) files every finding but leaves
the retrospective issue open for a human to close after review, rather
than closing unattended. This preserves the deliberate safety checkpoint
the rejected draft's own adversarial review found silently dropped.

Named residual risk (surfaced by the second adversarial review, not fully
solvable by this design alone): this repository's own measured history
shows human-close throughput on a left-open issue is close to zero (the
same 277-item backlog this whole design responds to is itself evidence of
that). An unattended cycle with a real `missing-deterministic-gate` repair
still leaves its retrospective issue open pending a human close that may
not come promptly -- this design does not claim to fix that; it only
confines the *unresolved-content* backlog to the new labelled-issue set
(which stays open on its own, legitimately, until each gate is actually
built) rather than also freezing the *retrospective audit records*
themselves open, which was the specific problem in scope.

### 4. A filed issue carries a real Acceptance Criteria Map, not a `tracking` waiver -- so an implementing PR can legitimately close it by number

The second adversarial review found this gap disqualifying as originally
drafted: this repository's own `hooks/check-issue-acm-disclosure.sh`
denies `mcp__github__issue_write` `create` when the new issue's body
carries neither an ACM table nor an explicit waiver, and (independently)
`hooks/gitapex_check_pr_issue_acm_disclosure.py` denies a PR whose
Closes/Fixes-cited issue carries specifically a `tracking` waiver. A
`gate-proposal`-style filing that reached for the obvious-looking
`ACM: not-applicable (tracking): ...` waiver to satisfy the first hook
would therefore be permanently unclosable by any future implementing PR's
own `Closes #<N>` -- forcing exactly the re-file-under-a-new-number
pattern Context above already diagnosed as this repository's own root
cause for the original 277-item backlog, reproduced one layer down instead
of removed.

Fixed by treating a `missing-deterministic-gate` finding for what it
already, genuinely is: a real, actionable, ACM-shaped piece of future work
(an interpretation of what's wrong, planned ops to build the check, a
proof method, a residual risk) -- not a placeholder needing a waiver. Each
filed issue's body carries a full Acceptance Criteria Map table (the same
`| Criterion | Interpretation | Planned ops | Proof method | Residual
risk |` header shape `hooks/gitapex_check_acm_present_or_waiver.py`'s
`_HEADER_RE` already recognizes), populated directly from the repair's own
already-classified fields: Criterion = the repair's own one-line label;
Interpretation = its Classification rationale; Planned ops = its Proposed
gate text; Proof method = "implementing PR adds the check plus a
regression test; confirm it fails against a reintroduced instance of the
original defect, then passes"; Residual risk = whatever was already
recorded, or "none identified" if the repair's own text named none. This
costs nothing new to compute -- every field the ACM table needs already
exists in the repair's own Classification/Status/Proposed-gate record --
and it is what makes the filed issue a normal, closeable-by-citation
GitHub issue like any other, exactly the property the whole redesign
depends on.

### 5. Resolution verification keeps the existing two-signal check, closes the closed-but-unverified gap, and specifies the concrete API shape and legitimate-decline path the rejected draft's own second review found hand-waved

A filed issue's own `closed` state is still not, by itself, treated as
proof its gate was built -- unchanged reasoning from issue #709. The daily
CI check runs two passes:

- **(a) Primary, threshold-gated:** count of currently-open issues
  carrying the label (a plain `state=open` + label search -- the actual
  backlog size). Threshold unchanged from today (20), per Non-goals.
- **(b) Secondary integrity pass, no threshold of its own:** the REST
  issues-list endpoint's own `since` parameter filters by `updated_at`,
  not `closed_at`, so "recently closed" is not a single clean server-side
  filter -- fetch `state=closed` plus the label, sorted by `updated`, and
  apply a client-side filter on each issue's own `closed_at` field against
  a fixed window (recommend 7 days, giving one full extra day of slack
  over the daily cron cadence against a single missed run). For each,
  re-run the two-signal check; flag any that closed without ever passing
  it. **Explicitly exempt** an issue whose own `state_reason` is
  `not_planned` or `duplicate` -- a legitimately declined proposal is not
  a silent-close failure, and flagging it daily for the whole window would
  make the check noisy enough to stop being trusted, the same failure mode
  `evals/scripts/gitapex_lint_fixture_assertions.py`'s own
  `--check-prompt-echo` was kept non-blocking to avoid (per its own
  docstring, 23 real false positives already found against this
  repository's own corpus).

**Label-liveness check, new in this revision:** both passes assume the
label itself still exists on GitHub. `gitapex_scan_retrospective_gate_drift.py`'s
own `evaluate()` today treats an empty result as an unconditional PASS --
correct when the label genuinely has zero open matches, silently wrong
when the label was renamed or deleted and the search simply returns
nothing for that reason instead. Before either pass runs, confirm the
label exists (a repository-labels lookup); if it does not, fail loudly
naming the missing label rather than reporting a clean zero -- the same
fail-closed posture this repository already applies to a missing/malformed
`.gitapex/ssot.json` field.

### 6. The label's own literal name is a parallel-copy-plus-drift-test, not a new `.gitapex/ssot.json` field

This design's own prior revision proposed registering the label's name as
a new `.gitapex/ssot.json` field. The second adversarial review found that
choice directly contradicts an existing, deliberate decision already
recorded in this repository: `.gitapex/ssot.schema.json`'s own top-level
`description` states, verbatim, that `label_routing`/`label_consumers`
fields are "deliberately absent -- gitapex has no `.github/label-policy.toml`
yet, so they are not-yet-applicable per issue #123, not an oversight," and
the schema sets `additionalProperties: false` throughout with its own
documented rule that "adding a field is a `schema_version` bump, never a
silent addition." Building the full `.github/label-policy.toml` mechanism
issue #123 actually calls for is out of scope for this design (a single
label name for one narrow mechanism does not warrant standing up a
repository-wide label-policy system); reusing `.gitapex/ssot.json` for it
anyway would silently reopen a question this repository has already
recorded an answer to.

This repository has a different, already-established precedent for
exactly this situation -- a literal string genuinely needed in two
independently-self-contained script trees that must not import across
their own boundary (`docs/repository-layout.md`'s own constraint: only
`skills/` and `hooks/` ship with the installed plugin, `.github/` never
does, so a cross-tree import would break at install time exactly the way
`hooks/check-issue-acm-disclosure.sh`'s own docstring already documents
for a different pair of files). `hooks/gitapex_check_pr_title_convention.py`
and `.github/scripts/gitapex_gate_pr_title_convention.py` already carry
independent copies of the same Conventional-Commits regex for this same
structural reason, kept from drifting apart by a dedicated equality test,
`tests/test_gitapex_pr_title_convention_regex_sync.py`. This design
follows that same precedent: the label's literal name is defined once as
a named constant in each of the (at most two, given the skill-script and
CI-script split Components below describes) independently-self-contained
files that need it, with a new sync test asserting both literal values
stay equal -- weaker than this design's own earlier, now-abandoned
`.gitapex/ssot.json`-registration claim of "only one copy to ever drift
from," but consistent with how this repository already solves the
identical cross-boundary duplication problem elsewhere, rather than
reopening a recorded `.gitapex/ssot.json` scope decision to avoid writing
that test.

## Non-goals

- **Migrating the existing 277-item unresolved backlog into the new
  labelled-issue scheme.** Explicitly out of scope for this design -- a
  separate, future decision, once this mechanism is proven correct going
  forward. Neither `skills/merge-retrospective/SKILL.md` nor either script
  may treat "no legacy migration happened" as an error condition. Worth
  naming plainly and without overselling it as a fix: this design *bounds*
  future growth of open, unrelated-content-carrying retrospective issues;
  it does not shrink the pre-existing ~300-issue count on its own. (Should
  a migration ever be undertaken, this flat-label design makes it cheaper
  than the rejected sub-issue design would have: re-labelling an existing
  issue is a single API call with no hierarchy, cap, or parent-assignment
  concern to manage -- but that migration itself remains separate,
  unscheduled follow-on work.)
- **Changing the two-signal resolution algorithm's own logic** (citing
  commit + `ssot.json` tracking_issue) -- only its scope (the labelled-issue
  set, open and recently-closed) changes, not its criteria.
- **Retiring `retrospective-gate-drift.yml`'s threshold concept.** The
  design keeps a threshold-gated daily check on the open count; only its
  enumerated set shrinks from all 345 retrospective issues to the new
  label's own open-issue set. The specific threshold value (currently 20)
  is left unchanged by this design; revisiting it is separate follow-on
  work if the new, correctly-scoped count suggests a different number is
  warranted.
- **Retrofitting a sync-tested constant for the pre-existing `retrospective`
  label**, or any other already-established label this repository already
  uses. Decision 6 covers only the one new label this design itself
  introduces; auditing or migrating other labels' own provenance is a
  separate concern this design does not take on.
- **Building `.github/label-policy.toml` or any other repository-wide
  label-governance mechanism.** Issue #123 already reserves that scope;
  this design's own single label is deliberately handled by the narrower,
  already-precedented parallel-copy-plus-drift-test mechanism instead
  (Decision 6), not by preempting that larger, separate decision.

## Architecture

No parent, no hierarchy. Every `missing-deterministic-gate` finding becomes
its own standalone GitHub issue, carrying a fixed label (literal name held
as a sync-tested constant, per Decision 6) and a `Refs #<retrospective-issue>`
back-link, its body a full Acceptance Criteria Map (Decision 4) rather than
a waiver. Each PR's own retrospective issue keeps recording what happened
(Summary, Repairs with Classification/Status/Proposed gate,
`unclear-agent-instruction`/`external-human-decision` entries inline as
today) but adds, per `missing-deterministic-gate` repair, a
`Filed as: #<issue-number>` line once that filing is verified, and closes
once every such repair from the cycle is filed -- subject to the
attended/unattended distinction in Decision 3.

## Components

1. **`skills/merge-retrospective/SKILL.md`** -- Step 1 rewritten (a routine
   cycle has nothing to sweep, since new findings are filed directly and
   the legacy 277 stay explicitly out of scope). Step 5 rewritten: for each
   `missing-deterministic-gate` repair, search first for an already-filed
   issue with this repair's own deterministic title before creating
   (Decision 1's own per-item idempotency fix, mirroring Step 0's existing
   stub-dedup pattern), then file via `issue_write` `create` with a full
   ACM body (Decision 4); verify each filing by re-fetch before recording
   `Filed as: #<N>`; close following Decision 3's attended/unattended rule,
   extended from the existing zero-repair-only case to every close.
2. **`skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py`**
   -- narrowed from a bulk 345-issue historical sweep to verifying one
   labelled issue (or a small explicit list) at a time; existing two-signal
   logic unchanged; carries its own copy of the label constant (Decision 6).
3. **`.github/scripts/gitapex_scan_retrospective_gate_drift.py`** +
   **`.github/workflows/retrospective-gate-drift.yml`** -- rescoped to a
   label-liveness check followed by two passes: open-count threshold report,
   and a `closed_at`-windowed, `state_reason`-aware integrity pass (Decision
   5); carries its own copy of the label constant (Decision 6).
4. **`tests/test_gitapex_retro_gate_label_sync.py`** (new) -- asserts the
   label constant defined in components 1/2's own tree and the one defined
   in component 3's own tree stay equal, the same shape
   `tests/test_gitapex_pr_title_convention_regex_sync.py` already applies
   to a different pair of independently-self-contained files (Decision 6).
   `.gitapex/ssot.json`/`.gitapex/ssot.schema.json` are **not** touched by
   this design (Decision 6's own reversal from the prior revision).

## Data flow

1. PR merges -> CI opens a stub retrospective issue (unchanged).
2. `merge-retrospective` invoked -> Step 0 dedup (unchanged) -> enumerate
   and classify this cycle's own repairs (unchanged, Steps 2-4).
3. **New Step 1**: a routine cycle has nothing to sweep (the legacy
   backlog is out of scope per Non-goals) -- no `.gitapex/ssot.json` read
   needed for this step.
4. **New Step 5**: for each `missing-deterministic-gate` repair this cycle
   -- search for an existing issue carrying this repair's own deterministic
   title (idempotency: covers both a resumed run and a concurrent-session
   race, matching Step 0's own stub-dedup search-before-create discipline;
   exact title equality, never substring) before creating anything; if none
   found, file it as its own labelled issue with a full ACM body (Decision
   4) and a link back to the originating PR/retrospective; re-fetch to
   verify the filing succeeded; record `Filed as: #<N>` against that
   repair's own entry in the retrospective issue body (also the fast-path
   idempotency check on a resumed run: skip both the search and the create
   for a repair that already carries a `Filed as:` line locally).
   `unclear-agent-instruction` / `external-human-decision` repairs stay
   recorded inline, unchanged, no issue filed.
5. Once every `missing-deterministic-gate` repair from the cycle is filed
   and verified (zero such repairs is the trivial case), close the
   retrospective issue -- attended: preview and get explicit go-ahead;
   unattended: leave open for later human review (Decision 3).
6. The pre-existing 277-item legacy backlog is untouched by this flow
   (Non-goal).
7. `retrospective-gate-drift.yml` runs daily: confirm the label itself
   still exists (Decision 5); primary threshold-gated report over
   currently-open labelled issues; secondary integrity pass over labelled
   issues closed within the last 7 days (client-side `closed_at` filter),
   excluding any with `state_reason` `not_planned`/`duplicate`, flagging
   any that closed without passing the two-signal check.

## Error handling

- **`issue_write` `create` failure** for any repair: do not record a
  `Filed as:` line and do not close the retrospective issue. The next run
  re-attempts only the repairs still missing a `Filed as:` line, searching
  before creating each time (Data flow step 4).
- **Filing appears to succeed but the re-fetch cannot confirm it** (e.g. a
  transient read failure right after a successful write): treat as
  unverified, same as an outright failure -- never record `Filed as:` on
  an unconfirmed write, and never close on an unconfirmed set. The
  search-before-create step on the next attempt is what prevents this case
  from producing a duplicate issue, not the `Filed as:` line alone.
- **The search-before-create step itself finds more than one existing
  issue** matching the deterministic title (e.g. an earlier race already
  produced a duplicate before this fix existed): fail closed and escalate
  -- same as Step 0's own existing ambiguous-stub-match discipline -- never
  guess which one is authoritative or silently file a third.
- **The label does not exist** when the CI liveness check runs, or the
  sync test (Component 4) finds the two copies of its literal name have
  drifted: fail loudly in both cases, never report a clean pass by
  omission (Decision 5, Decision 6).

## Testing

- Unit tests for the narrowed `gitapex_check_retro_gate_resolved.py`
  (single labelled-issue number input, or a small explicit list -- not a
  345-issue bulk sweep).
- Unit tests for the CI script's rescoped checks: the label-liveness guard
  (missing label fails loudly, not a clean zero), the open-count threshold
  report (mocked label search), and the closed-but-unverified integrity
  pass (mocked label search over issues closed in the last 7 days,
  `state_reason` exemption applied, two-signal check applied to the
  remainder).
- `tests/test_gitapex_retro_gate_label_sync.py` (Component 4): asserts
  both hardcoded copies of the label's literal name are equal.
- A test asserting the ACM table `issue_write` `create` now populates
  (Decision 4) actually satisfies `hooks/gitapex_check_acm_present_or_waiver.py`'s
  `has_acm_disclosure` -- i.e. a filed issue's own body, run through that
  existing checker, passes -- so this design's own filing step is proven
  compatible with the repository's already-enforced ACM-disclosure hook,
  not merely asserted compatible in prose.
- A test asserting the search-before-create idempotency step (Data flow
  step 4) does not re-file a repair whose deterministic title already
  matches an existing issue, covering both the "already filed by this same
  retrospective" and "a concurrent/earlier attempt already filed it" cases.
- New `evals/merge-retrospective/tasks/*.yaml` fixtures (directory already
  exists) covering: zero-repair, no legacy backlog touched -> fast-close
  (unchanged behavior); zero-repair, pre-existing legacy backlog exists but
  is out of scope -> still fast-closes (the specific behavior this design
  changes); one or more `missing-deterministic-gate` repairs, attended ->
  each filed as its own labelled issue, verified, retrospective closes;
  same but unattended -> filed and verified, retrospective stays open for
  human review; a resumed run after a partial filing failure -> only the
  unfiled repairs are retried, already-filed ones are not duplicated.

## Open questions

None outstanding. Every fork surfaced during elicitation and two rounds of
adversarial review was resolved: the first round rejected the sub-issue
hierarchy mechanism outright (see "Rejected" above); the second round,
run against this flat-labelled-issue revision, found the ACM/waiver
citation gap (Decision 4), the per-item idempotency gap (Decision 1), the
`.gitapex/ssot.json` scope conflict (Decision 6), and the resolution-
verification API/exemption gaps (Decision 5) -- each addressed in the
decision it is now attributed to above, verified against this
repository's actual hooks, schema, and workflow files rather than left as
prose claims. See Decisions 1-6 and the "Rejected" section for each choice
and why its alternative was set aside.

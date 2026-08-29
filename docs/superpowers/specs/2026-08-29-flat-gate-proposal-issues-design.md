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
already covers). It reduces, but -- honestly stated, per the third
adversarial review's own correction of this section's earlier overclaim --
does not eliminate, the remaining per-item race: search-then-create is
not atomic (GitHub offers no find-or-create, the same platform gap the
"Rejected" section's own singleton-parent finding already named), so two
concurrent attempts can each search, each find nothing, and each create.
The mitigation below narrows the window and guarantees a duplicate is
*detected* deterministically once it exists (a later search finds two
matches and fails closed, per Error handling); it is a reduction and a
detection guarantee, not a proof no duplicate can ever momentarily exist.

The idempotency key itself needs to be collision-proof, which the second
adversarial review's own proposed shape (a bare one-line label) was not:
this repository's own worked example in `skills/merge-retrospective/SKILL.md`
(the `[Failed CI rerun]`/`[Review fix round]` labels) shows how generic a
repair's one-line label already is in practice, and two distinct repairs in
one cycle can produce the identical label, byte for byte. The third
adversarial review caught this: a bare-label title would make the second
repair's own search-before-create find the *first* repair's issue, treat it
as already filed, and silently skip filing the second, real finding --
worse than the duplicate-issue risk this mechanism exists to prevent,
because it is a silent loss, not a visible one. Fixed by keying the title
on each repair's own fixed position, not its free-text label: `gate-proposal:
retro #<retrospective-issue-number> repair <1-based index>: <repair's own
one-line label>` (the label stays in the title for human readability; the
index is what actually disambiguates), where the literal string
`gate-proposal` is the fixed label's own name too (Decision 6). The index
is assigned once, in-memory, during Step 2-4's own single classification
pass, and held for the rest of that same session's filing calls -- no
different from how the repair's own label text is already held for that
session today.

The fourth adversarial review found the prior revision's own hardening
attempt here -- writing that index list into the retrospective issue's
body in a step *before* Step 5 begins, specifically to survive a session
interruption -- collided with Step 0's own existing, unchanged
marker-based branching (`SKILL.md`'s Step 0: a body still carrying the
CI-opener's stub marker means "nothing enriched yet, continue"; a body
without it means "already enriched, stop here"), because that extra write
would itself remove or predate the marker's own removal outside Step 5's
one designated write. Rather than teach Step 0 a third state to
distinguish "enriched but incomplete" from "fully enriched" -- a change to
an *unchanged* component this design deliberately keeps out of scope --
the index list is instead written as part of Step 5's own single existing
body write (Component 1; the same write that already replaces the stub
per Step 0's marker-present branch, or creates fresh per its no-match
branch), immediately followed in that same session by each repair's
`Filed as: #<N>` line as its filing is confirmed.

Named residual risk, not solved by this design: a session interrupted
*mid*-Step-5 -- after that one body write lands (the marker is gone) but
before every repair's own `Filed as:` line is recorded -- leaves a later,
resumed run seeing Step 0's own marker-absent branch ("nothing left to
file, stop here"), even though some repairs may still be unfiled. This is
an existing limitation of Step 0's own binary, unchanged branching, not
newly introduced by the index-keyed title; this design does not extend
Step 0's own state model to fix it. The concrete cost, if this is hit, is
a stuck-open retrospective issue needing a human to notice and finish the
filing by hand -- not silent data loss (nothing already filed is lost)
and not a duplicate (the exact-title search-before-create in Data flow
step 4 still catches a repair that was already filed before the
interruption). Within one uninterrupted session -- the common case, and
the only case the second and third adversarial reviews' own within-cycle
collision finding actually required fixing -- the index is fully stable.

The same single-pass assignment extends unmodified to a future manual
audit of the pre-existing 277-item legacy backlog (should one ever be
undertaken; still out of scope per Non-goals): the auditor walks the
backlog in one sitting and assigns indices 1..K within that sweep, keyed
on each item's own *original* retrospective issue number, exactly like a
routine cycle's Step 2-4 pass -- no separate persistence mechanism is
needed for that case either, since none is guaranteed for the routine
case above.

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

Each `missing-deterministic-gate` repair's own inline `Status:
missing-deterministic-gate` tag (the fixed-vocabulary line
`.github/scripts/gitapex_compute_gprr.py`'s `_STATUS_LINE_RE` already
parses out of every retrospective issue's body to compute the
Gate-Preventable Repair Rate) is **not** removed or replaced by this
design -- it stays exactly where Step 5 already writes it today. The new
`Filed as: #<N>` line is recorded immediately alongside it, as an
addition, not a substitution. GPRR's own numerator is therefore unaffected
by this design: a repair still reads as `missing-deterministic-gate` in
the retrospective issue's body whether or not this design's own
standalone-issue mechanism successfully filed it.

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
- **(b) Secondary integrity pass, zero-tolerance and unbounded --
  revised again in this round after the fourth adversarial review found
  the third round's own fix (a 7-day `closed_at` window plus a
  window-exit reopen) both contradicted itself (the reopen text called
  the pass "threshold-gated the same as (a)" -- count > 20 -- while
  separately requiring it to fail on *any* non-exempt unverified closure,
  two different rules for the same pass) and needed `issues: write` on
  `retrospective-gate-drift.yml`, which only ever carries `issues: read`
  -- Decision 1's own "no elevated CI permission" claim, made about a
  different pass, does not extend to a reopen action, and the design
  never asked for the extra scope:** fetch `state=closed` plus the label
  -- every closed issue ever carrying it, with **no time window and no
  `closed_at` filtering at all** -- and re-run the two-signal check on
  each. **Explicitly exempt** an issue whose own `state_reason` is
  `not_planned` or `duplicate` -- a legitimately declined proposal is not
  a silent-close failure, and flagging it forever would make the check
  noisy enough to stop being trusted, the same failure mode
  `evals/scripts/gitapex_lint_fixture_assertions.py`'s own
  `--check-prompt-echo` was kept non-blocking to avoid (per its own
  docstring, 23 real false positives already found against this
  repository's own corpus). **Any** non-exempt issue that closed without
  passing the two-signal check fails this run -- a single, unambiguous
  rule, distinct from (a)'s own count>20 threshold, not "the same as (a)"
  worded two different ways. There is no reopen and no window to age out
  of: an issue stays in this pass's scope for as long as it stays closed
  and non-exempt, so a missed cron run costs nothing (tomorrow's run still
  finds it) and no write permission is needed (CI stays `issues: read`
  throughout, matching Decision 1's read-only claim for once, genuinely).
  The concrete, durable consequence the third adversarial review asked
  for is the daily red CI run itself, which a human then resolves by
  hand -- reopening the issue, correcting `.gitapex/ssot.json`, or setting
  `state_reason` once it is legitimately declined -- rather than an
  automated reopen action this design does not attempt. This is a smaller
  claim than "self-healing": it guarantees the closed-state gap can never
  again pass silently (Decision 5's own scope is bounded to *detecting*
  and *failing loudly*, not to auto-remediating), which is what the very
  first "Rejected" section's closed-state finding actually required.

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
`tests/test_gitapex_pr_title_convention_regex_sync.py`. That precedent
compares two *importable constants in two real scripts* -- the third
adversarial review pointed out that Step 5's own filing operation, as
originally drafted, was left as prose in `SKILL.md` for an interactive
agent session to carry out via raw tool calls, not a script at all, so
there was no second constant for a sync test to actually import and
compare; a label renamed only in that prose would drift silently past
the very test meant to catch drift.

Fixed by making Step 5's *computation* -- not its GitHub calls -- a small
bundled script: `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`
(Components below), holding the label's own literal name, **`gate-proposal`**,
as a named constant, alongside the deterministic-title builder (Decision 1)
and the ACM-body template (Decision 4). The fourth adversarial review found
the prior revision's own draft of this script wrong in a different way: it
had the script call `issue_write` itself, but `issue_write` is an
MCP tool this repository's own agent session invokes directly (the exact
tool `hooks/check-issue-acm-disclosure.sh`'s `hooks.json` entry matches on),
not something a plain bundled script can call into -- and this repository's
own established convention (CLAUDE.md's Git Ecosystem section) is that
GitHub writes go through the agent's own platform-integrated tool calls
specifically so the paired safety hook fires, never through a script
re-implementing the REST call itself. So the script stays pure and
network-free: given a repair's already-classified fields plus its
recorded index (Decision 1), it returns the deterministic title, the
fully-populated ACM body, and the label constant -- nothing else.
`SKILL.md`'s own Step 5 prose invokes the script for those three values,
then makes the actual GitHub calls itself, as direct `mcp__github__*` tool
calls exactly like every other step in this skill already does: list/search
for an exact-title match first (Data flow step 4), and on no match, call
`issue_write` method `create` with the script's own title/body/label,
then `issue_read` to re-fetch and verify. This keeps every GitHub write in
this design passing through the same ACM-disclosure hook every other
`issue_write` call in this repository already passes through, and keeps
the new script itself trivially unit-testable (pure functions, no network
mocking needed) -- both properties the prior draft's script-does-everything
shape did not have. `SKILL.md`'s own Step 5 prose then reads as "invoke
this script for the title/body/label, then file it," not as a second
place the literal label name is separately spelled out. This makes the
sync-test precedent apply cleanly, as originally intended: the label's
literal name is defined once as a named constant in each of exactly two
independently-self-contained scripts -- this new skill-side helper, and
the existing CI-side scan script -- with a new sync test asserting both
literal values stay equal. Weaker than this design's own earlier, now-
abandoned `.gitapex/ssot.json`-registration claim of "only one copy to
ever drift from," but consistent with how this repository already solves
the identical cross-boundary duplication problem elsewhere, rather than
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
  set, open and closed) changes, not its criteria.
- **Automatically remediating a closed-but-unverified issue** (reopening
  it, editing `.gitapex/ssot.json`, or anything else beyond failing the CI
  run and naming the issue). The fourth adversarial review found an
  earlier, time-boxed reopen attempt here both needed CI write permission
  this design does not request and produced an internally contradictory
  gating rule; Decision 5 deliberately narrows this pass's own job to
  detection, leaving remediation to the human the failing run alerts.
- **Having `gitapex_file_gate_proposal.py` (or any script this design
  introduces) make GitHub API calls of its own.** Every actual write stays
  a direct agent tool call (Decision 6), matching how every other step in
  `skills/merge-retrospective/SKILL.md` already files or updates issues
  today; this design does not add a second GitHub-calling code path.
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
its own standalone GitHub issue, carrying the fixed `gate-proposal` label
(literal name held as a sync-tested constant, per Decision 6) and a
`Refs #<retrospective-issue>` back-link, its body a full Acceptance
Criteria Map (Decision 4) rather than a waiver, filed under a
collision-proof, index-keyed deterministic title (Decision 1). Each PR's
own retrospective issue's single Step 5 body write records its own
enumerated repair list (with each repair's own 1-based index and label)
and, as each filing is confirmed, a `Filed as: #<issue-number>` line per
`missing-deterministic-gate` repair, closing once every such repair from
the cycle is filed -- subject to the attended/unattended distinction in
Decision 3. Every GitHub write this design performs (the search, the
create, the verifying re-fetch) is a direct agent tool call, never a
script-internal HTTP call, so the repository's existing ACM-disclosure
hook keeps seeing and gating every filing the same way it gates any other
`issue_write` call today.

## Components

1. **`skills/merge-retrospective/SKILL.md`** -- Step 1 rewritten (a routine
   cycle has nothing to sweep, since new findings are filed directly and
   the legacy 277 stay explicitly out of scope). Step 2-4 assign each
   repair's own 1-based index in-memory during classification, held for
   the rest of the session (no separate write). Step 5 rewritten: its one
   existing body write (create fresh, or update-replacing-stub per Step 0's
   unchanged branching) now includes the enumerated repair list up front,
   then invokes the new helper script (Component 2) once per
   `missing-deterministic-gate` repair to get that repair's deterministic
   title/ACM-body/label, performs the search-then-create-then-verify
   sequence itself via direct `mcp__github__*` tool calls, and records
   `Filed as: #<N>` against that repair's entry as each filing is
   confirmed; close following Decision 3's attended/unattended rule,
   extended from the existing zero-repair-only case to every close.
2. **`skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`**
   (new) -- pure, network-free helper. Owns the label constant (Decision
   6) and the deterministic-title builder (Decision 1); given a repair's
   own classification fields and recorded index, returns the title, the
   fully-populated ACM body (Decision 4), and the label -- nothing else.
   Makes no GitHub calls of its own; `SKILL.md`'s own Step 5 prose is what
   invokes `issue_write`/`issue_read` directly with the values this script
   computes.
3. **`skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py`**
   -- unchanged from the second revision: narrowed from a bulk 345-issue
   historical sweep to verifying one labelled issue (or a small explicit
   list) at a time, given by issue number; existing two-signal logic
   unchanged. Does not need the label constant itself -- it verifies
   issue numbers it is handed, the same shape as today.
4. **`.github/scripts/gitapex_scan_retrospective_gate_drift.py`** +
   **`.github/workflows/retrospective-gate-drift.yml`** -- rescoped to a
   label-liveness check, then two passes: a threshold-gated (20) open-count
   report, and an unbounded, zero-tolerance, `state_reason`-aware integrity
   pass over every closed labelled issue, with no time window and no
   reopen action (Decision 5); carries its own copy of the label constant
   (Decision 6). Workflow permissions stay `issues: read` -- unchanged from
   today, no new write scope requested.
5. **`tests/test_gitapex_retro_gate_label_sync.py`** (new) -- asserts the
   label constant defined in Component 2's own tree and the one defined in
   Component 4's own tree stay equal, the same shape
   `tests/test_gitapex_pr_title_convention_regex_sync.py` already applies
   to a different pair of independently-self-contained scripts (Decision
   6). `.gitapex/ssot.json`/`.gitapex/ssot.schema.json` are **not** touched
   by this design (Decision 6's own reversal from the prior revision).

## Data flow

1. PR merges -> CI opens a stub retrospective issue (unchanged).
2. `merge-retrospective` invoked -> Step 0 dedup (unchanged) -> enumerate
   and classify this cycle's own repairs (unchanged, Steps 2-4), assigning
   each repair its own 1-based index in-memory during this same pass
   (Decision 1).
3. **New Step 1**: a routine cycle has nothing to sweep (the legacy
   backlog is out of scope per Non-goals) -- no `.gitapex/ssot.json` read
   needed for this step.
4. **New Step 5**: write the retrospective issue's body once (create or
   update, per Step 0's own unchanged branching), including the enumerated
   repair list (index + label). Then, for each `missing-deterministic-gate`
   repair -- call `gitapex_file_gate_proposal.py` (Component 2) with that
   repair's own index, label, and the retrospective's own issue number to
   get its deterministic title/ACM-body/label; search for an existing issue
   with that exact title (idempotency: narrows a concurrent-session race
   and prevents a duplicate on a same-session retry, matching Step 0's own
   stub-dedup search-before-create discipline; exact title equality, never
   substring -- per Decision 1, a reduction and a detection guarantee, not
   a proof no duplicate can ever momentarily exist) before creating
   anything; on no match, file it as its own labelled issue with the full
   ACM body (Decision 4) and a link back to the originating PR/retrospective,
   then re-fetch to verify. Record `Filed as: #<N>` against that repair's
   own entry in the retrospective issue body once verified (also the
   fast-path idempotency check on a resumed run within the same session:
   skip a repair that already carries a `Filed as:` line).
   `unclear-agent-instruction` / `external-human-decision` repairs stay
   recorded inline, unchanged, no issue filed, no script invoked.
5. Once every `missing-deterministic-gate` repair from the cycle is filed
   and verified (zero such repairs is the trivial case), close the
   retrospective issue -- attended: preview and get explicit go-ahead;
   unattended: leave open for later human review (Decision 3).
6. The pre-existing 277-item legacy backlog is untouched by this flow
   (Non-goal).
7. `retrospective-gate-drift.yml` runs daily: confirm the label itself
   still exists (Decision 5); primary threshold-gated (20) report over
   currently-open labelled issues; secondary zero-tolerance integrity pass
   over every labelled issue in state `closed` (no time window), excluding
   any with `state_reason` `not_planned`/`duplicate`, failing the run on
   any remaining issue that closed without passing the two-signal check.

## Error handling

- **`gitapex_file_gate_proposal.py` (Component 2) cannot compute a value**
  for a repair (missing a required classification field): `SKILL.md` does
  not attempt the filing for that repair, does not record a `Filed as:`
  line, and does not close the retrospective issue. The next run
  re-attempts only the repairs still missing a `Filed as:` line (Data flow
  step 4).
- **The search-then-create-then-verify sequence fails or cannot confirm
  the create** (e.g. a transient read failure right after a successful
  write): `SKILL.md` never records `Filed as:` on an unconfirmed write,
  and never closes on an unconfirmed set. The search-before-create step on
  the next invocation is what prevents this case from producing a
  duplicate issue, not the `Filed as:` line alone.
- **The search step finds more than one existing issue** matching the
  deterministic title (e.g. an earlier race already produced a duplicate
  before this fix existed): fail closed and escalate -- same as Step 0's
  own existing ambiguous-stub-match discipline -- never guess which one is
  authoritative or silently file a third.
- **A session is interrupted mid-Step-5**, after the body write lands
  (the CI-opener's stub marker is gone) but before every repair's own
  `Filed as:` line is recorded: a later resumed run hits Step 0's own
  unchanged marker-absent branch and stops without finishing the filing.
  Named, accepted residual risk (Decision 1) -- the retrospective issue
  stays open, visibly incomplete, for a human to notice and finish by
  hand; nothing already filed is lost or duplicated.
- **The label does not exist** when the CI liveness check runs, or the
  sync test (Component 5) finds the two copies of its literal name have
  drifted: fail loudly in both cases, never report a clean pass by
  omission (Decision 5, Decision 6).

## Testing

- Unit tests for `gitapex_file_gate_proposal.py` (Component 2, new): pure
  functions, no network mocking needed -- deterministic-title construction
  from index/label/retrospective-number, and the ACM-body template it
  populates.
- Unit tests for the narrowed `gitapex_check_retro_gate_resolved.py`
  (single labelled-issue number input, or a small explicit list -- not a
  345-issue bulk sweep; unchanged from the second revision).
- Unit tests for the CI script's rescoped checks: the label-liveness guard
  (missing label fails loudly, not a clean zero), the open-count threshold
  report (mocked label search), and the closed-issue zero-tolerance
  integrity pass (mocked label search over every closed issue carrying the
  label, `state_reason` exemption applied, two-signal check applied to the
  remainder, no reopen action).
- `tests/test_gitapex_retro_gate_label_sync.py` (Component 5): asserts
  both hardcoded copies of the label's literal name are equal.
- A test asserting the ACM table `gitapex_file_gate_proposal.py` populates
  (Decision 4) actually satisfies `hooks/gitapex_check_acm_present_or_waiver.py`'s
  `has_acm_disclosure` -- i.e. a filed issue's own body, run through that
  existing checker, passes -- so this design's own filing step is proven
  compatible with the repository's already-enforced ACM-disclosure hook,
  not merely asserted compatible in prose.
- A test asserting two repairs in the same cycle with an identical
  one-line label still produce two distinct filed issues (the specific
  collision the third adversarial review found, closed by the index-keyed
  title in Decision 1).
- A test asserting a retrospective issue's own inline `Status:
  missing-deterministic-gate` line for a repair survives unchanged
  alongside its new `Filed as:` line, so `gitapex_compute_gprr.py`'s own
  parsing keeps working (Decision 2).
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

None outstanding. Every fork surfaced during elicitation and four rounds
of adversarial review was resolved: round one rejected the sub-issue
hierarchy mechanism outright (see "Rejected" above); round two, run
against the flat-labelled-issue revision, found the ACM/waiver citation
gap (Decision 4), the `.gitapex/ssot.json` scope conflict (Decision 6),
and the resolution-verification API/exemption gaps (Decision 5); round
three, run against those fixes, found the idempotency key's own
collision risk and the SKILL.md-prose-versus-script precedent mismatch
(folded into Decision 1's title-keying and Decision 6's new helper
script, Component 2), the overclaimed race-elimination framing (corrected
in Decision 1), and the integrity pass's own missing consequence and
time-boxed escape; round four, run against that fix, found the
window-exit reopen it introduced needed CI write permission the workflow
does not have and contradicted its own gating rule, found the helper
script's draft `issue_write` call was not actually callable from a plain
script, found the pre-Step-5 body write it introduced collided with
Step 0's own unchanged marker-based branching, found the race-reduction
wording had not fully propagated out of Data flow, found the legacy-audit
indexing claim was unbacked, and found the retrospective body rewrite's
effect on `gitapex_compute_gprr.py`'s own parsing was unexamined -- all
six resolved in this revision by removing the reopen action and the
window entirely in favor of an unbounded zero-tolerance pass (Decision 5),
making the helper script pure and network-free with the agent performing
every GitHub call directly (Decision 6), folding the repair-list write
into Step 5's own existing single write with the resulting limitation
named as an accepted residual risk rather than solved (Decision 1), fixing
the Data flow wording to match Decision 1, extending the same single-pass
indexing rationale explicitly to the legacy-audit case (Decision 1), and
adding an explicit GPRR-compatibility clause plus test (Decision 2).
Each finding across all four rounds is addressed in the decision it is
now attributed to above, verified against this repository's actual hooks,
schema, scripts, and workflow files rather than left as prose claims. See
Decisions 1-6 and the "Rejected" section for each choice and why its
alternative was set aside.

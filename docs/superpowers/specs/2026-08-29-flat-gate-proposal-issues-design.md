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
issue**, carrying a fixed label (see Decision 5 for where that label's
literal name is registered) and a `Refs #<retrospective-issue>` back-link.
No parent issue, no sub-issue relationship, no singleton of any kind.

This removes every failure mode named in "Rejected" above by construction:
plain issue creation (`issue_write` method `create`) carries no 100-item
cap, no shared-resource creation race (each filing creates its own
independent issue; there is nothing to find-or-create first), and no
elevated CI permission (label search is a read operation the CI workflow's
existing `issues: read` scope already covers).

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

### 4. Resolution verification keeps the existing two-signal check, and closes the closed-but-unverified gap the rejected draft left open

A filed issue's own `closed` state is still not, by itself, treated as
proof its gate was built -- unchanged reasoning from issue #709 and the
rejected draft's own Decision 4. `gitapex_check_retro_gate_resolved.py`'s
two-signal check (citing commit + `ssot.json` `tracking_issue` match) is
kept, narrowed in scope from "sweep all 345 retrospective issues" to
"verify the label-tagged issue set." Unlike the rejected draft, the daily
CI check now runs *two* passes over that set, closing the specific gap the
adversarial review found: (a) the primary, threshold-gated report -- how
many labelled issues are currently open (the actual backlog size); and (b)
a secondary integrity pass over issues *recently closed* under the same
label, applying the same two-signal check and separately flagging any that
closed without ever passing it. (b) has no threshold of its own -- any
non-empty result is itself the finding, the same "even one is worth
naming" posture `hooks/gitapex_check_pr_issue_acm_disclosure.py`'s sibling
checks already take for other silent-failure classes in this repository.

### 5. The label's own literal name is registered once, in `.gitapex/ssot.json` -- never duplicated as an independent hardcoded string

The new label this design introduces (its exact literal name is an
implementation-time decision, not fixed by this doc -- see Components
below) is registered as a new field under `.gitapex/ssot.json`, the same
file this mechanism already depends on for `gates[].tracking_issue`, with
`.gitapex/ssot.schema.json` updated to describe the new field. Every
consumer -- `skills/merge-retrospective/SKILL.md`'s own prose, the CI
script, and any future implementation script -- reads the label's name
from that one registered field at the point of use, rather than each
independently hardcoding its own copy of the literal string. This is a
stronger anti-drift guarantee than a test comparing two hardcoded copies
for equality: there is only ever one copy to drift from.

Chosen over a dedicated new config file specifically for this one value,
because `.gitapex/ssot.json` already is this repository's own established
single source of truth for exactly this class of fact (a registered gate's
own tracking-issue number), and this label serves the identical role for a
different kind of gate-tracking record -- adding a second, parallel
registry file for the same purpose would itself become a second thing to
keep from drifting against the first.

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
- **Retrofitting an SSoT registration for the pre-existing `retrospective`
  label**, or any other already-established label this repository already
  uses. Decision 5 registers only the one new label this design itself
  introduces; auditing or migrating other labels' own provenance is a
  separate concern this design does not take on.

## Architecture

No parent, no hierarchy. Every `missing-deterministic-gate` finding becomes
its own standalone GitHub issue, carrying a fixed label (name registered in
`.gitapex/ssot.json`, per Decision 5) and a `Refs #<retrospective-issue>`
back-link. Each PR's own retrospective issue keeps recording what happened
(Summary, Repairs with Classification/Status/Proposed gate,
`unclear-agent-instruction`/`external-human-decision` entries inline as
today) but adds, per `missing-deterministic-gate` repair, a
`Filed as: #<issue-number>` line once that filing is verified, and closes
once every such repair from the cycle is filed -- subject to the
attended/unattended distinction in Decision 3.

## Components

1. **`skills/merge-retrospective/SKILL.md`** -- Step 1 rewritten (read the
   registered label name from `.gitapex/ssot.json`; the "carried-forward
   picture" for a *routine* cycle is simply "nothing to sweep," since new
   findings are filed directly and the legacy 277 stay explicitly out of
   scope). Step 5 rewritten (file each `missing-deterministic-gate` repair
   as its own labelled issue via `issue_write` `create`; verify each
   filing by re-fetch before recording `Filed as: #<N>`; close following
   Decision 3's attended/unattended rule, extended from the existing
   zero-repair-only case to every close).
2. **`skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py`**
   -- narrowed from a bulk 345-issue historical sweep to verifying one
   labelled issue (or a small explicit list) at a time; existing two-signal
   logic unchanged.
3. **`.github/scripts/gitapex_scan_retrospective_gate_drift.py`** +
   **`.github/workflows/retrospective-gate-drift.yml`** -- rescoped to
   enumerate open issues carrying the registered label (a plain label
   search, no permission change needed) for the primary threshold-gated
   report, plus a secondary pass over recently-closed issues under the
   same label for the closed-but-unverified integrity check (Decision 4).
4. **`.gitapex/ssot.json`** + **`.gitapex/ssot.schema.json`** -- gain the
   new label-name field and its schema description (Decision 5).

## Data flow

1. PR merges -> CI opens a stub retrospective issue (unchanged).
2. `merge-retrospective` invoked -> Step 0 dedup (unchanged) -> enumerate
   and classify this cycle's own repairs (unchanged, Steps 2-4).
3. **New Step 1**: read the registered label name from
   `.gitapex/ssot.json`; a routine cycle has nothing further to sweep (the
   legacy backlog is out of scope per Non-goals).
4. **New Step 5**: for each `missing-deterministic-gate` repair this cycle
   -- file it as its own labelled issue (body carries Classification,
   Status, Proposed gate, and a link back to the originating PR/retrospective);
   re-fetch to verify the filing succeeded; record `Filed as: #<N>` against
   that repair's own entry in the retrospective issue body (this record is
   also the idempotency check on a resumed run: skip re-filing a repair
   that already carries a `Filed as:` line). `unclear-agent-instruction` /
   `external-human-decision` repairs stay recorded inline, unchanged, no
   issue filed.
5. Once every `missing-deterministic-gate` repair from the cycle is filed
   and verified (zero such repairs is the trivial case), close the
   retrospective issue -- attended: preview and get explicit go-ahead;
   unattended: leave open for later human review (Decision 3).
6. The pre-existing 277-item legacy backlog is untouched by this flow
   (Non-goal).
7. `retrospective-gate-drift.yml` runs daily: primary threshold-gated
   report over currently-open labelled issues; secondary integrity pass
   over recently-closed labelled issues, flagging any that closed without
   passing the two-signal check (Decision 4).

## Error handling

- **`issue_write` `create` failure** for any repair: do not record a
  `Filed as:` line and do not close the retrospective issue. The next run
  (attended or a retry) re-attempts only the repairs still missing a
  `Filed as:` line (Data flow step 4's own idempotency check).
- **Filing appears to succeed but the re-fetch cannot confirm it** (e.g. a
  transient read failure right after a successful write): treat as
  unverified, same as an outright failure -- never record `Filed as:` on
  an unconfirmed write, and never close on an unconfirmed set.
- **The registered label name in `.gitapex/ssot.json` is missing or the
  schema field is absent**: fail loudly (matching this repository's own
  existing fail-closed convention for a missing/malformed SSoT field,
  e.g. `gitapex_scan_ssot_schema.py`'s own posture) rather than silently
  falling back to an unregistered, hardcoded literal.

## Testing

- Unit tests for the narrowed `gitapex_check_retro_gate_resolved.py`
  (single labelled-issue number input, or a small explicit list -- not a
  345-issue bulk sweep).
- Unit tests for the CI script's two new passes: open-count threshold
  report (mocked label search), and closed-but-unverified integrity check
  (mocked label search over recently-closed issues, two-signal check
  applied per issue).
- A schema/drift test asserting `.gitapex/ssot.json`'s new label field
  validates against the updated `.gitapex/ssot.schema.json`, matching this
  repository's own existing `test_gitapex_scan_ssot_schema.py` pattern.
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

None outstanding. Every fork surfaced during elicitation and the
subsequent adversarial review (aggregation mechanism -- reversed from
sub-issues to flat labelled issues -- closure eligibility, resolution-
verification strength, Repairs/Carried-forward unification, and the
label's own SSoT registration) was resolved with the user during the
design dialogue; see Decisions 1-5 above and the "Rejected" section for
each choice and why its alternative was set aside.

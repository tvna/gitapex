# Gate-backlog sub-issue consolidation for merge-retrospective: design

Date: 2026-08-29

Refs #1405 (refs #1402, #1395, #205, #191, #187, #118). Design-then-implement
doc, per this repo's own plan-first discipline.

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
1% or lower historical rate of ever being acted on. This design is therefore
scoped to the instruction-file and script changes themselves, not to a
persuasive case for making them.

## Decisions

### 1. Consolidate all `missing-deterministic-gate` findings under one long-lived GitHub-native parent issue, via native sub-issues

Every `missing-deterministic-gate`-classified repair -- whether discovered
fresh in the current cycle's own Repairs section, or (during any future
manual audit of the pre-existing 277-item backlog) carried forward from an
older retrospective -- is filed as a GitHub **sub-issue** of one singleton
"Gate Backlog" parent issue, via `mcp__github__sub_issue_write` (or the
calling harness's equivalent). The parent is discovered by the same
exact-title + label lookup pattern Step 0's own CI-stub dedup already uses
(a fixed label, e.g. `gate-backlog`, plus an exact title match) -- created
once, on first use, if not yet found.

This directly uses a precedent already present in this toolchain (the
`mcp__github__issue_read` surface already exposes `has_parent`,
`sub_issues_summary`, and a dedicated `sub_issue_write` tool), rather than
inventing a bespoke aggregation mechanism -- the Core Domain check that
opened this design's own elicitation dialogue judged the underlying
problem (backlog-item consolidation) Generic, not Core, and this repository
already has the relevant native building block wired into its own tool
surface.

Rejected alternative: **a prose-only pointer convention** (the status quo
`#205` -> "see `#191`" -> "see `#187`" chain, formalized). Rejected because
it keeps the exact weakness driving this redesign: no native GitHub
visibility (no progress bar, no structured completion state), and every
new retrospective still has to re-state or re-point at the same chain by
hand.

Rejected alternative: **a GitHub Projects board**. Rejected because this
repository's own tool surface (`mcp__github__*`) has no confirmed Projects
operations to automate against; adopting it would add a new integration
surface for a problem the already-available sub-issues feature already
solves.

### 2. Unify "this cycle's own Repairs" and "carried-forward from history" into one filing path

A `missing-deterministic-gate` finding is filed as a Gate Backlog sub-issue
the moment it is classified -- regardless of whether it was found in this
cycle's own Step 2-4 repair enumeration or (during a future manual sweep of
the pre-existing backlog) inherited from an older retrospective. The two
were previously treated asymmetrically: Repairs stayed inline in the filing
retrospective issue's own body indefinitely; only a *later* cycle's Step 1
sweep ever promoted an unresolved one to "Carried-forward" status, and even
then only as a re-stated paragraph, not a trackable artifact.

Unifying the two collapses the retrospective issue's own role: it is no
longer where a proposed gate *lives* (that is now always the Gate Backlog
sub-issue), only where the cycle's own facts are *recorded* -- what
happened, how it was classified, and which sub-issue number now owns
follow-through. Once every `missing-deterministic-gate` finding from a
cycle is filed, the retrospective issue itself has nothing left it is
solely responsible for holding open, and can close immediately.

`unclear-agent-instruction` and `external-human-decision` repairs are
unaffected -- neither classification proposes a gate to track, so neither
gets a sub-issue; both stay recorded inline in the retrospective issue's
own body exactly as today.

### 3. Retrospective issues close immediately once every finding is filed -- including a zero-repair cycle whose only "content" is pre-existing legacy backlog

Under the old design, a zero-repair PR still could not fast-close if any
carried-forward content existed, because Step 5's own rule required the
subsection to stay open with the debt inside it. Under this design, a
zero-repair cycle has, by construction, nothing of its own to file (the
pre-existing 277-item backlog is explicitly out of scope for this design,
per Non-goals below -- it is not re-swept or re-filed by a routine cycle),
so it fast-closes exactly as the zero-repair path already intends. A cycle
with one or more `missing-deterministic-gate` repairs files each as a
sub-issue, records the resulting sub-issue number against each repair
entry in its own body, and then also closes immediately -- this is the
actual fix for the unbounded-open-issue-count problem: no retrospective
issue's own lifecycle is ever gated on an unrelated backlog's completion
status again.

### 4. Sub-issue resolution keeps the existing two-signal verification, not bare GitHub `closed` state

A sub-issue's own `closed` state is not, by itself, treated as proof its
gate was built -- the same reasoning issue #709 already established for
the current mechanism (a citing commit alone is not proof; closing an
issue is an even weaker signal, closeable by anyone with write access with
zero corroborating evidence). `gitapex_check_retro_gate_resolved.py`'s
two-signal check (citing commit + `ssot.json` `tracking_issue` match) is
kept, but its own scope narrows: from "sweep all 345 retrospective issues"
to "verify one specific sub-issue," invoked either when someone proposes to
close a sub-issue, or by a periodic backlog-health audit over the Gate
Backlog parent's own (now much smaller) open sub-issue set.

### 5. Step 1 stops sweeping full retrospective-issue history; it reads the Gate Backlog parent's own `sub_issues_summary` instead

Once every future `missing-deterministic-gate` finding is filed directly
against the one parent, that parent's own native sub-issue completion
state (`sub_issues_summary`: total / completed / percent, already exposed
by `mcp__github__issue_read`) *is* the carried-forward picture -- no
per-cycle historical sweep is needed to reconstruct it. This retires the
345-issue, ~12-page-paginated fetch this design's own precipitating
retrospective (issue #1405) had to perform by hand; a future cycle's Step 1
becomes a single `issue_read get` call against the known parent.

## Non-goals

- **Migrating the existing 277-item unresolved backlog into Gate Backlog
  sub-issues.** Explicitly out of scope for this design -- a separate,
  future decision, once this mechanism is proven correct going forward.
  Neither `skills/merge-retrospective/SKILL.md` nor either script may treat
  "no legacy migration happened" as an error condition.
- **Adopting GitHub Projects** (rejected in Decision 1).
- **Changing the two-signal resolution algorithm's own logic** (citing
  commit + `ssot.json` tracking_issue) -- only its scope (one sub-issue at
  a time, or the parent's own sub-issue set) changes, not its criteria.
- **Retiring `retrospective-gate-drift.yml`'s threshold concept.** The
  design keeps a threshold-gated daily check; only its enumerated set
  shrinks from all 345 retrospective issues to the Gate Backlog parent's
  own sub-issues. The specific threshold value (currently 20) is left
  unchanged by this design; revisiting it is separate follow-on work if the
  new, correctly-scoped count suggests a different number is warranted.

## Architecture

A single long-lived "Gate Backlog" parent issue (label `gate-backlog` +
fixed title, e.g. `chore(gate-backlog): durable gate tracking`), discovered
by exact label+title lookup (same pattern as Step 0's existing CI-stub
dedup), created once on first use if absent. Every `missing-deterministic-gate`
finding, from any cycle, becomes a GitHub-native sub-issue of that parent.
Each PR's own retrospective issue keeps recording what happened (Summary,
Repairs with Classification/Status/Proposed gate, `unclear-agent-instruction`/
`external-human-decision` entries inline as today) but adds, per
`missing-deterministic-gate` repair, a `Filed as: #<sub-issue-number>`
line, and closes as soon as every such repair is filed.

## Components

1. **`skills/merge-retrospective/SKILL.md`** -- Step 1 rewritten (find/create
   the Gate Backlog parent; read its `sub_issues_summary` instead of
   sweeping all `retrospective`-labelled issues). Step 5 rewritten (file
   each `missing-deterministic-gate` repair as a parent sub-issue via
   `sub_issue_write`, record the resulting number, then close the
   retrospective issue once every repair from the cycle is filed --
   including the zero-repair case, which now has nothing left barring
   fast-close).
2. **`skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py`**
   -- narrowed from a bulk historical-sweep tool to a single-sub-issue (or
   small explicit list) verifier; existing two-signal logic unchanged.
3. **`.github/scripts/gitapex_scan_retrospective_gate_drift.py`** +
   **`.github/workflows/retrospective-gate-drift.yml`** -- rescoped to
   enumerate the Gate Backlog parent's own sub-issues (via the GitHub
   sub-issues GraphQL connection) instead of every `retrospective`-labelled
   issue; same two-signal check and threshold concept, smaller and
   correctly-scoped input set.
4. **Parent-issue discovery/creation** -- no new dedicated script; reuses
   Step 0's existing label+exact-title lookup pattern, stated in SKILL.md
   prose (consistent with how that step already avoids a bespoke script
   for the same kind of lookup).

## Data flow

1. PR merges -> CI opens a stub retrospective issue (unchanged).
2. `merge-retrospective` invoked -> Step 0 dedup (unchanged) -> enumerate
   and classify this cycle's own repairs (unchanged, Steps 2-4).
3. **New Step 1**: find (or create, once) the Gate Backlog parent issue.
4. **New Step 5**: for each `missing-deterministic-gate` repair this cycle
   -- file it as a sub-issue of the parent (body carries Classification,
   Status, Proposed gate, and a link back to the originating PR/retrospective
   for context); record `Filed as: #<N>` against that repair's own entry in
   the retrospective issue body. `unclear-agent-instruction` /
   `external-human-decision` repairs stay recorded inline, unchanged, no
   sub-issue filed.
5. Once every `missing-deterministic-gate` repair from the cycle is filed
   (zero such repairs is the trivial case), close the retrospective issue.
6. The pre-existing 277-item legacy backlog is untouched by this flow
   (Non-goal).
7. `retrospective-gate-drift.yml` runs daily against the Gate Backlog
   parent's own sub-issue set (not all 345 historical issues), applying the
   same two-signal check per sub-issue and the same threshold-gated
   report/fail as today.

## Error handling

- **Ambiguous parent-issue lookup** (more than one issue matches the fixed
  label + exact title): fail closed, same as Step 0's existing stub-dedup
  discipline -- exact string equality, never substring containment; escalate
  rather than guess which one is authoritative.
- **`sub_issue_write` failure** for any repair: do not close the
  retrospective issue. Filing must be verified (re-fetch, confirm the
  sub-issue exists and is actually linked under the parent) before the
  retrospective issue's own close call fires -- the same "verify the write"
  discipline Step 7 already requires for the retrospective issue itself,
  extended to each sub-issue filing.
- **Parent issue found closed or otherwise missing** on a run that expects
  it to exist: do not silently recreate a duplicate parent. Escalate to a
  human -- an unexpectedly closed/deleted long-lived parent is itself worth
  a person's attention, not a condition to route around automatically.

## Testing

- Unit tests for the narrowed `gitapex_check_retro_gate_resolved.py`
  (single sub-issue number input, or a small explicit list -- not a
  345-issue bulk sweep).
- Unit tests for the CI script's new sub-issue-enumeration path (mocked
  GitHub sub-issues GraphQL connection response).
- New `evals/merge-retrospective/tasks/*.yaml` fixtures (directory already
  exists) covering: zero-repair, no legacy backlog touched -> fast-close
  (unchanged behavior); zero-repair, pre-existing legacy backlog exists but
  is out of scope -> still fast-closes (the specific behavior this design
  changes); one or more `missing-deterministic-gate` repairs -> each filed
  as a Gate Backlog sub-issue, retrospective issue closes once filing is
  verified.

## Open questions

None outstanding -- every fork surfaced during elicitation (aggregation
mechanism, closure eligibility, resolution-verification strength,
Repairs/Carried-forward unification) was resolved with the user during the
design dialogue (see Decisions 1-5 above for each choice and its rejected
alternatives).

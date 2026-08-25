# Retrospective gate drift: per-gate resolution granularity

Date: 2026-08-23

Refs #1177 (refs #709, #1176). Design-then-implement doc, per this repo's own
plan-first discipline; the implementing PR carries this same commit.

## Context

`.gitapex/ssot.json`'s `gates[].tracking_issue` field (`integer|null`, per
`.gitapex/ssot.schema.json`) records which retrospective issue a given
deterministic gate came from. Both consumers of this field --
`.github/scripts/gitapex_scan_retrospective_gate_drift.py`'s
`find_no_citation_issues()` (the daily CI drift-scan) and
`skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py`'s
`partition_resolved()` (merge-retrospective's own Step 1 carry-forward check)
-- currently treat a retrospective issue as fully resolved the moment **any
one** `gates[]` entry cites it (combined with at least one commit citing
`#N`, per issue #709/#1176's existing two-signal corroboration).

A single retrospective issue's own `## Repairs` section can propose several
distinct gates -- each its own `Proposed gate:` line, per
`skills/merge-retrospective/SKILL.md`'s fixed Repair record format. Issue
#1129 is a concrete example: its Repairs 1-5 and 10 each propose a distinct
new gate (6 total), none built yet as of this writing. Once the *first* of
those 6 ships and is registered with `tracking_issue: 1129`, both scripts
would clear #1129 from their reports entirely -- even though 5 more proposed
gates remain unbuilt.

This is not hypothetical. Verified directly against the current
`.gitapex/ssot.json` (2026-08-23): issues #520, #928, and #439 each already
have 3 separate `gates[]` entries sharing one `tracking_issue` value (#1028
and #682 have 2 each) -- 5 of the registry's 51 distinct `tracking_issue`
values are already multi-gate. In each of those 5 cases every proposed gate
happens to already be built, so today's coarse check is not currently
wrong for them -- but the mechanism has no way to tell "all done" from "one
of several done," and the next multi-gate issue to land its first (but not
last) gate will trip the exact false-clear this design closes.

## Options considered (recorded per this repo's own architecture-trade-off
discipline)

- **Per-gate child GitHub issues**, linked via `sub_issue_write`, with the
  child issue's own number used as an ordinary `tracking_issue` value.
  Rejected: this repository has zero existing precedent anywhere for
  GitHub's sub-issue relationship feature (verified by grepping for
  `sub_issue_write`/`get_sub_issues`/`has_children`/`has_parent` --  only
  unrelated false-positive hits); it would need a real migration/backfill
  judgment call for the ~223 currently-open `label:retrospective` issues
  that predate any such mechanism, and it would regress
  `gitapex_check_retro_gate_resolved.py`'s recently-shipped (PR #1196,
  merged 2026-08-19) deliberately local-only/no-network design by requiring
  a new per-issue GitHub API call in a script issue #1176 specifically
  scoped to `git log` + `.gitapex/ssot.json` only.
- **Reuse the GitHub issue's own open/closed state** as the multi-gate
  resolution signal. Rejected after checking live data: issue #1224 (a
  retrospective issue) is already closed with `state_reason: "not_planned"`
  *without* its Repairs section ever being filled in -- proof that "closed"
  is already an overloaded signal in this repository's actual practice, not
  a safe dedicated one to build new automation on.
- **A "Proposed gate count: N" line embedded in the retrospective issue's
  own body**, parsed by both scripts instead of touching
  `.gitapex/ssot.schema.json` at all. Materially cheaper (no
  `schema_version` bump, no new commit-producing step -- it piggybacks on
  the issue-body edit `merge-retrospective/SKILL.md` Step 5 already makes).
  Surfaced and offered; the operator explicitly chose to keep the
  authoritative manifest inside `.gitapex/ssot.json` instead, favoring this
  repository's established SSOT-centralization convention over the cheaper,
  issue-body-only alternative.

## Decision: a `proposed_gates` manifest in `.gitapex/ssot.json`

Add a new required top-level array, `proposed_gates`, to
`.gitapex/ssot.schema.json` (sibling to the existing `meta`,
`policy_sources`, `gates`, `clusters`), via a deliberate `schema_version`
bump (`1.3.0` -> `1.4.0`) -- additive only, consistent with the schema's own
stated policy ("Adding a field is a schema_version bump, never a silent
addition").

```json
"proposed_gates": [
  {
    "tracking_issue": 1129,
    "proposals": [
      "malformed-package-item-fail-open",
      "symlink-bypass-config-read",
      "repo-root-fixed-hop-count",
      "recursion-error-uncaught",
      "unbounded-repr-evidence",
      "allowed-root-ascent-bypass"
    ]
  }
]
```

- `tracking_issue`: the retrospective issue this manifest entry describes;
  unique across `proposed_gates`.
- `proposals`: one short kebab-case slug per distinct new gate that issue's
  own `## Repairs` section proposed. `minItems: 2` -- an issue proposing
  exactly one gate needs no manifest entry at all; its absence from
  `proposed_gates` is the signal that the pre-existing single-citation rule
  still applies unchanged.
- Slugs are **documentation/traceability only**. Resolution is
  **count-based, not slug-identity-based**: a proposal is not required to
  exactly match the `gates[].id` an implementer eventually picks when they
  build it (gate naming is expected to evolve between proposal time and
  build time). The check only ever compares *how many* gates exist against
  *how many* were promised.

### Backward compatibility

`proposed_gates` is required but may be empty (`[]`), matching this
schema's existing convention for `policy_sources`/`gates` (no `minItems` at
the top level). `.gitapex/ssot.json` itself gets `"proposed_gates": []`
added in the same PR to stay schema-valid. Every retrospective issue not
listed in `proposed_gates` -- which is every one of the ~223 currently-open
`label:retrospective` issues, plus 46 of the 51 already-registered
`tracking_issue` values -- defaults to `required = 1` and keeps today's
exact behavior. No backfill is required for correctness; the 5 already-known
multi-gate cases (#520/#928/#439/#1028/#682) may optionally get manifest
entries as a live-data demonstration of the new field (harmless: all 5 are
already fully built, so adding an entry whose `proposals` length matches
their current gate count changes no verdict for them).

## Mechanism: resolution semantics

Both consumer scripts change identically:

**Before:**
```python
resolved = citation_count(commit_messages, n) > 0 and n in tracking_issues  # tracking_issues: set[int]
```

**After:**
```python
resolved = (
    citation_count(commit_messages, n) > 0
    and gates_registered_count(n, gates) >= proposal_requirements.get(n, 1)
)
```

- `.github/scripts/gitapex_scan_retrospective_gate_drift.py`:
  `load_gate_tracking_issues() -> set[int]` becomes a count-returning
  reader (`dict[int, int]`, one entry per distinct `tracking_issue` value
  found across `gates[]`, counting how many `gates[]` entries cite it) plus
  a new `load_proposed_gate_requirements() -> dict[int, int]` reader for
  the new `proposed_gates` array (`{tracking_issue: len(proposals)}`).
  `find_no_citation_issues()` takes both dicts and applies the comparison
  above per candidate issue number. No new I/O: both readers parse the
  same already-read `.gitapex/ssot.json` file.
- `skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py`:
  identical treatment for `partition_resolved()`. This script already reads
  `.gitapex/ssot.json` locally with no network call; that design (issue
  #1176) is unchanged.

Both scripts' `SsotLedgerError`/fail-closed behavior on a missing or
malformed registry is preserved unchanged -- a registry that cannot be read
still fails the check loudly, never silently reports "nothing unresolved."

## Mechanism: a new step in merge-retrospective's own filing flow

`skills/merge-retrospective/SKILL.md`'s Step 5 ("File (or update) the
retrospective issue") currently only calls `mcp__github__issue_write` -- a
pure GitHub-API operation with no accompanying commit. This design adds a
real, disclosed cost: whenever a cycle's own `## Repairs` section proposes
**2 or more** distinct new gates (i.e. 2+ new `Proposed gate:` lines, not
counting `## Carried-forward gate` restatements of a different issue's own
proposal), Step 5 must also open or update a small PR that adds the
corresponding `proposed_gates` entry to `.gitapex/ssot.json`, in the same
cycle. Step 5's procedure text gets an explicit new bullet for this; Step 7
("Verify the filed issue") gets a matching bullet confirming the
`proposed_gates` entry actually landed when one was required. A
single-gate cycle needs no such PR, exactly as today.

## Proof plan

- Unit-test fixtures on both scripts' pure-logic layers, shaped exactly
  like issue #1129: a `tracking_issue` with a 6-item `proposals` manifest,
  only 1 matching `gates[]` entry registered and cited. Assert the issue
  number still appears in the unresolved/no-citation output -- proving
  partial implementation does not fully clear it (the literal Acceptance
  Criteria Map requirement in issue #1177).
- A second fixture at `required` fully met (e.g. 2 of 2 for a two-proposal
  manifest, both cited) asserting the issue *does* clear -- so the change is
  proven in both directions, not just the negative case.
- The existing `gitapex_scan_ssot_schema.py` drift-check gate (tracking
  issue #123) continues to pass with `proposed_gates` present; a test
  asserts `schema_version` was bumped in the same diff that changes
  `ssot.schema.json` (issue #1177's own second Acceptance Criteria Map row).
- Full pytest suite green; no unrelated file changed.

## Non-goals

- Does not backfill `proposed_gates` entries for any of the ~223 currently
  open retrospective issues that predate this field -- they keep today's
  single-citation behavior unless and until a future cycle's Step 5 adds an
  entry for them.
- Does not require the eventual `gates[].id` to match a `proposals` slug
  exactly -- see "count-based, not slug-identity-based" above.
- Does not change the CI posture, reporting mechanism (step-summary text),
  or threshold (20) that `2026-07-22-retrospective-gate-drift-design.md`
  already established. Those are unchanged by this design.
- Does not address issue #1177's own disclosed residual gap (a gate that is
  a sub-feature of an already-registered gate, with no dedicated `gates[]`
  row of its own, cannot be counted at all) -- unchanged from the existing,
  already-disclosed limitation in the 2026-08-03 addendum to the original
  drift-gate design.

## Acceptance criteria

- [ ] `.gitapex/ssot.schema.json` gains `proposed_gates` (required array,
      no `minItems`), `schema_version` bumped `1.3.0` -> `1.4.0`.
      `.gitapex/ssot.json` gains `"proposed_gates": []` (plus any optional
      backfill entries) and validates against the updated schema.
- [ ] `gitapex_scan_retrospective_gate_drift.py`'s pure-logic layer is
      covered by unit tests proving both directions: a manifest with more
      proposals than registered-and-cited gates stays unresolved; a
      manifest fully met (registered-and-cited count >= required) clears.
      An issue absent from `proposed_gates` keeps exactly today's
      single-citation behavior (regression test).
- [ ] `gitapex_check_retro_gate_resolved.py`'s `partition_resolved()` gets
      the identical test treatment, including the JSON output shape
      (`{"unresolved": [...], "resolved": [...]}`) unchanged.
- [ ] `skills/merge-retrospective/SKILL.md`'s Step 5 and Step 7 name the new
      "open/update a small PR for a 2+-proposal cycle" requirement
      explicitly, with no alternative left open.
- [ ] A live dry run against the real repository (not just the unit test
      suite) confirms both scripts' reported output on the current registry
      before this is called done, per this repo's live-proof requirement.
- [ ] Full pytest suite green; `retrospective-gate-drift.yml` and
      `waza-check.yml` left byte-for-byte unchanged.

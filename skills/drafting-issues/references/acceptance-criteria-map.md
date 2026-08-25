# Acceptance Criteria Map

Build one row per acceptance criterion before creating the issue. A
criterion without a row is not accounted for. Same table shape a
sibling skill in this repository validates in a PR body, applied here
at issue-authoring time instead.

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| (the requester's own words) | (your reading, once ambiguity is resolved) | (files/changes the eventual fix would need) | (test, command, or manual check that would prove it) | (what could still go wrong, or "none identified") |

## Worked example

Requester's message (fictional, for illustration only):

> Can we add a way to preview a report export without actually writing
> the file? And make sure the normal export still behaves exactly the
> same.

Classified as: feature.

Facts: the requester wants a preview mode for the export command and
wants normal export behavior unchanged.

Requested outcome: add a `--dry-run` flag to the export command.

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Preview the report without writing a file | `export --dry-run` prints the file list, writes nothing to disk | Add a `--dry-run` branch that short-circuits before the write step | Test asserting no file exists on disk after a `--dry-run` run | A partial write on an interrupted `--dry-run` run is unverified |
| Normal export is unchanged | Behavior without `--dry-run` matches current output byte-for-byte | No change to the non-dry-run code path | Regression test comparing pre/post output on a fixed fixture | None identified |

Constraints: none stated.

Non-goals: does not cover a preview *format* beyond a file list (the
requester did not ask for content diffing).

## Worked example: an unresolvable column

Requester's message (fictional, for illustration only):

> Search sometimes returns duplicate results. Not sure why yet.

Classified as: fix.

Facts: the requester observed duplicate search results; the cause is
not yet known.

Requested outcome: search results contain no duplicates.

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Search results contain no duplicates | unknown, pending reproduction -- root cause not yet established | unknown, pending reproduction | Test asserting no duplicate result IDs for a query that currently reproduces the defect | unknown, pending reproduction |

A criterion whose proof method cannot be executed in the current
environment, or whose interpretation/planned ops/residual risk cannot
yet be stated from the requester's own words, is marked "unknown,
pending X" -- never silently marked done, and never invented so the row
looks complete.

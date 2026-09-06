# Worked Example

Hypothetical merge history for a PR with three repairs, one per
taxonomy category:

- CI run 1 failed: `pytest` reported `ImportError: No module named foo`
  because a new test file referenced a helper that was never imported in
  `conftest.py`. The author pushed a follow-up commit adding the import,
  and CI run 2 passed.
- A human reviewer commented that the error message the new `--dry-run`
  flag prints on failure ("nothing happened") was confusing next to how
  every other flag in the same CLI phrases its errors ("dry-run: no
  changes applied, see below"). The author pushed a follow-up commit
  rewording the message to match.
- Partway through review, a third-party rate-limiter library this CLI
  depends on (but does not own) released a major version renaming its
  `Limiter.check()` method to `Limiter.allow()`, breaking a separate CI
  run. The author and reviewer discussed pinning the old version
  versus adopting the new one, and chose to adopt it, updating the two
  affected call sites in a follow-up commit.

Retrospective issue this produces, assuming the repo has no issue
template or title convention of its own (if it did, that template and
title convention would be filled with the same repair content instead):

```
Title: Merge retrospective: PR #42

## Summary

Retrospective for PR #42 ("feat: add foo routing"), merged 2026-07-12.
Three repairs occurred between PR open and merge.

Repairs found this cycle:
1. Failed CI rerun
2. Review fix round
3. External dependency change

## Repairs

1. [Failed CI rerun] `pytest` run #1 failed with
   `ImportError: No module named foo` -- a new test referenced a helper
   never imported in `conftest.py`. Fixed by a follow-up commit adding
   the import; CI run #2 passed.
   Classification: missing deterministic gate.
   Status: `missing-deterministic-gate`
   Proposed gate: run the test suite (or at minimum `python -m py_compile`
   plus `pytest --collect-only`) in a pre-push hook, so import errors
   surface locally before CI.
   Filed as: #87

2. [Review fix round] Reviewer flagged that the new `--dry-run` flag's
   failure message ("nothing happened") read as confusing next to how
   every other flag in the CLI phrases its errors. Fixed by a follow-up
   commit rewording the message to match the existing convention.
   Classification: unclear agent instruction -- whether a message reads
   as "confusing" next to a house style is a judgment call a lint rule
   cannot make; no gate could have caught this, but no written
   instruction told the agent the existing phrasing convention either.
   Status: `unclear-agent-instruction`
   (Optional note: the CLI's error-message phrasing convention could be
   added to the repo's own instruction file, if it has one, so future
   agents learn it up front instead of from review -- not required, just
   useful context.)

3. [External dependency change] A third-party rate-limiter library this
   CLI depends on released a major version renaming `Limiter.check()` to
   `Limiter.allow()`, breaking CI run #2 separately from repair 1 above.
   No repo policy dictated pinning the old version versus adopting the
   new one; the author and reviewer discussed it and chose to adopt it,
   updating the two affected call sites in a follow-up commit.
   Classification: external/human decision -- an upstream breaking
   change plus a genuine judgment call between two reasonable paths, not
   a pattern any deterministic gate or written instruction could have
   caught.
   Status: `external-human-decision`

## Notes

Repair 1's proposed gate is filed separately as issue #87
(`gate-proposal: retro #42 repair 1: Failed CI rerun`), carrying its own
Acceptance Criteria Map -- building it is that issue's own follow-on
work, per merge-retrospective's Stop boundary. Repairs 2 and 3 propose
no gate and file no issue; their Classification line's own rationale is
the record.
```

# Acceptance Criteria Map

Build one row per acceptance criterion before creating a branch or PR. A
criterion without a row is not accounted for.

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| (verbatim from the issue) | (your reading, once ambiguity is resolved) | (files/changes that satisfy it) | (test, command, or manual check that proves it) | (what could still go wrong, or "none identified") |

## Worked example

Issue (fictional, for illustration only):

> Acceptance criteria:
> - [ ] Requests to `/health` return 200 within 100ms under normal load.
> - [ ] A malformed request body returns 400, not 500.

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `/health` returns 200 within 100ms | No new I/O on the hot path; short-circuit before any DB/network call | Add a dedicated handler that returns before touching the DB pool | Load test asserting p99 < 100ms over 1000 requests | Handler could still be reached through a slow middleware chain — check middleware order |
| Malformed body returns 400 | Any body that fails schema validation, not just missing fields | Validate against the existing request schema before the handler body runs | Unit tests: empty body, wrong type, missing required field, each asserting 400 | A future schema change could silently widen "malformed" — no automated drift check yet |

A criterion whose proof method cannot be executed in the current
environment is flagged as residual risk, never silently marked done.

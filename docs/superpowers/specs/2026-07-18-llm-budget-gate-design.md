# An LLM invocation token/cost budget gate

Date: 2026-07-18

Refs #153 (child of #82). Extends #144's design-then-implement
precedent. Directly gates issue #124's credentialed dispatch of
`.github/workflows/waza-eval-matrix.yml`.

## Design-only scope

Per this repository's discipline (matching #57/#123/#125/#126/#127/#130/
#131/#144/#145/#147/#148/#151/#152 precedent): this doc records a design
only. No `.gitapex/llm-budget-policy.toml`, no `.gitapex/
llm-budget-policy.schema.json`, no `.github/scripts/gate_workflow_llm_
budget.py` is created by this pass.

## Why this doc exists

An audit this session (reading `tvna/claude-md`'s real `.gitapex/`
files, not issue-body paraphrase, after an earlier design -- #152 --
was found to have missed a whole mechanism by relying on paraphrase)
found gitapex's design chain had never once considered
`.gitapex/llm-budget-policy.toml` + `scripts/scan_workflow_llm_
budget.py` (claude-md #2269, "token blowout guard") -- despite it being
one of the first `policy_sources[]`-adjacent files in the very
`ssot.json` instance issue #123 says gitapex should model on.

This is not a hypothetical gap. `.github/workflows/waza-eval-matrix.yml`
(committed, real) already fans out over LLM model ids via a
`copilot-sdk` endpoint (`nix run .#waza -- run "$skill"`, gated on
`COPILOT_BASE_URL`/`COPILOT_PROVIDER_BASE_URL` secrets), and issue #124
is the follow-up that provisions real credentials and actually dispatches
it. Notably: claude-md's own instance has `budgets = []` -- "no workflow
invokes an LLM today" there. **gitapex has the live case before its more
mature sibling does.**

## Verified finding: the marker list must be extended, not ported verbatim

Read and checked against the real committed `waza-eval-matrix.yml` this
session, not assumed: claude-md's five markers --

```
uses: anthropics/claude-code-action
claude -p
codex exec
api.anthropic.com
api.openai.com
```

-- **match nothing in `waza-eval-matrix.yml`.** The workflow's actual
LLM-invoking line is:

```
if nix run .#waza -- run "$skill" -o "results/${MODEL}/${skill}.json"; then
```

against a configurable copilot-sdk endpoint, credentialed via
`COPILOT_BASE_URL`/`COPILOT_PROVIDER_BASE_URL` env vars. Porting the
marker list unchanged would ship a gate that exists, runs in CI, passes
trivially, and never fires on gitapex's one real case -- a false sense
of coverage, worse than no gate at all because it would look like
coverage on review.

## Decision 1: ported mechanism, cited completely

Port claude-md's real contract (read this session from
`scripts/scan_workflow_llm_budget.py` and its sibling schema/policy
files), including the parts the JSON-Schema subset cannot express and
that the real implementation enforces in the scanner itself, not the
schema -- stated explicitly here so a future implementation doesn't
silently drop them the way #152's first draft silently dropped an
architectural distinction it hadn't yet read:

- **Policy file** (`.gitapex/llm-budget-policy.toml`): a top-level
  `markers = [...]` array of literal substrings (not regexes), matched
  against each logical line of `.github/workflows/*.{yml,yaml}` after
  shell-continuation flattening; comment lines (`#`-prefixed) are
  skipped so the marker list can be documented inline without
  self-tripping. A `budgets[]` array, one entry per marker-matched
  workflow, each requiring `workflow` (basename), `max_runs_per_day`,
  `max_retries`, and at least one of `max_tokens_per_run` /
  `max_cost_usd_per_run`.
- **Schema** (`.gitapex/llm-budget-policy.schema.json`): shape-only,
  `additionalProperties: false` throughout so a typo'd key fails loud.
  The real schema's own description states plainly what it CANNOT
  express: the "at least one of `max_tokens_per_run` /
  `max_cost_usd_per_run`" rule has no `oneOf`/`anyOf` in the shared
  draft-2020-12 subset this repo's schemas use (matching #123's
  `gate_kind` XOR-rule precedent) -- ported as a bespoke check in the
  gate script itself, not attempted in the schema.
- **The gate** (`.github/scripts/gate_workflow_llm_budget.py`): for
  every marker hit with no complete budget entry, emit an
  `::error file=<workflow>,line=<n>::` annotation naming the missing
  keys, fail loud (exit 1) if any violation exists, exit 0 (including
  trivially, when no marker matches anything) otherwise. A present
  budget value must additionally be finite and correctly signed
  (non-negative for `max_runs_per_day`/`max_retries`, strictly positive
  for the cost/token keys) -- `inf`/`nan`/negative/zero values pass the
  schema's bare `integer`/`number` typing but declare no real ceiling,
  so this check lives in the gate, matching the real implementation
  exactly.

## Decision 2: gitapex-specific marker(s)

**Decision: add a marker for the exact invocation shape verified this
session -- `nix run .#waza -- run` -- and keep the five upstream markers
unchanged rather than dropping them.**

The waza-invocation marker is the one that actually closes the verified
gap: it fires precisely on `waza-eval-matrix.yml`'s real LLM-invoking
line. `COPILOT_BASE_URL`/`COPILOT_PROVIDER_BASE_URL` were considered as
an alternative or additional marker and rejected as the PRIMARY one:
they identify credential *presence*, not the invocation line itself, so
a marker on them would fire on the preflight secret-check step too (a
step that reads the secret to validate it's set, but does not itself
invoke an LLM) -- a marker should identify the invoking line, matching
the semantic intent of every one of claude-md's five markers (each of
which names an actual invocation surface, not a credential name).

The five upstream markers are kept, not dropped: gitapex is a
redistributed CLI whose adopters may run `claude-code-action`, direct
`claude -p`/`codex exec` invocations, or direct API calls in their OWN
workflows once this mechanism ships as part of the CLI's governance
surface (#127's `gitapex init` scaffolding is a plausible future
consumer of this exact policy file) -- removing them would be
speculative narrowing with no argued benefit, the mirror-image mistake
of speculative widening.

## Decision 3: seed a real budget for `waza-eval-matrix.yml`

Per CLAUDE.md section 3 (ship the drift gate with the invariant) and
#144's own precedent (inventory and gate shipped together): the
implementation issue must seed a `budgets[]` entry for
`waza-eval-matrix.yml` in the SAME change as the gate script, not as a
follow-up -- an unpopulated `budgets = []` would let the gate pass
trivially forever, the exact state claude-md's own instance is
honestly in today for its still-absent LLM workflow.

Proposed values, grounded in the workflow's own stated shape (read from
its header comment: `workflow_dispatch`-only, "advisory and manual
only... never runs on push/PR and never gates a merge"):

- `max_runs_per_day`: a small number (proposed: `5`) -- manual dispatch
  only, no automated trigger exists to run it repeatedly; a low ceiling
  costs nothing operationally and bounds a credential-misuse or
  fat-fingered-repeated-dispatch scenario.
- `max_retries`: `0` -- the workflow has no retry logic of its own
  (`fail-fast: false` in its matrix strategy governs cross-model
  independence within one run, not run-level retries); a ported
  retry-count field should reflect what actually exists, not invent a
  retry behavior the workflow doesn't have.
- `max_tokens_per_run` or `max_cost_usd_per_run`: **explicitly NOT
  proposed with a number here.** This design does not have real
  per-run cost/token data for the workflow's actual per-model,
  per-suite `waza run` calls (12 suites x N models x `trials_per_task:
  3`, per issue #124's own description) -- inventing a plausible-
  sounding ceiling would be exactly the "confident guess presented as
  fact" this repo's own primary-source discipline exists to prevent.
  **Flagged as an open input for the operator to supply before the gate
  can be implemented** -- the implementation issue's first blocking
  step, not a design gap to paper over. A one-time real dispatch under
  #124 (or a dry-run cost estimate from the copilot-sdk provider's own
  pricing) is the natural source for this number once available.

## Decision 4: relationship to #124 -- precondition, not parallel

This gate is #124's precondition, mirroring claude-md's own
`scan_workflow_llm_budget.py` docstring verbatim: "No workflow invokes
an LLM today, so this gate passes trivially until [a future workflow]
introduces one; it is that future workflow's precondition, not a
retrofit." For gitapex, the workflow already exists (unlike claude-md's
still-hypothetical case) -- so the ordering is sharper: **this gate
should land and be verified passing BEFORE #124's owner-provisioned
credentials make a real dispatch possible**, not after. #124's own
"Steps" section should gain a reference to this gate as an explicit
precondition once implemented (a small addition to #124, not designed
here -- #124 remains unmodified by this issue itself).

## Decision 5: gate placement

**Decision: CI plane, mirroring `scan_toolchain_pin_drift.py`'s own
placement** (a workflow-content scanner gitapex already has, same
shape: reads `.github/workflows/*.yml`, no network, tree-only). Not
pre-commit/pre-push: those planes gate a contributor's local commit
before push, but the object under test here (workflow YAML content vs.
a policy file) is exactly the kind of repository-wide consistency check
this repo's existing CI-plane scanners already own, and duplicating it
into local hooks would slow every commit for a check that only matters
at merge time. Not clustered with any existing gate: no other current
gitapex gate reads `.github/workflows/*.yml` for LLM-invocation content
specifically (the pin-drift scanner reads it for a different concern,
Class B tool installation); stands alone until a second workflow-content
gate argues for a shared cluster.

## Facts vs. speculation

Facts: `tvna/claude-md`'s `.gitapex/llm-budget-policy.toml`,
`.gitapex/llm-budget-policy.schema.json`, and
`scripts/scan_workflow_llm_budget.py`, read in full this session; the
verified absence of any marker match against gitapex's real
`.github/workflows/waza-eval-matrix.yml` (grepped this session, not
assumed); issue #124's own body (12 suites, `trials_per_task: 3`,
`workflow_dispatch`-only, owner-provisioned-secret precondition).

Speculation, named as such: the exact `max_runs_per_day`/`max_retries`
values proposed in Decision 3 are this design's reasoned defaults, open
to operator revision; the cost/token ceiling is explicitly not proposed
at all (Decision 3); whether `gitapex init` (#127) becomes a real future
consumer of this policy file for adopter workflows is a plausible but
undesigned future connection, named only to justify keeping the five
upstream markers (Decision 2), not designed further here.

## Non-goals

- No `.gitapex/llm-budget-policy.toml`, no schema file, no gate script
  -- design only. A later session may implement this, matching #144's
  design-to-code precedent.
- Not designing #124's credentialed-run execution -- this gate is a
  precondition for it.
- Not inventing a cost/token ceiling number -- flagged as an open input
  for the operator (Decision 3).
- Not reopening claude-md's own mechanism -- adopted as-is except for
  the gitapex-specific marker addition (Decision 2), which is additive,
  not a replacement of the upstream markers.

## Acceptance criteria

- [ ] The ported mechanism's full validation contract is stated,
      including the scanner-enforced (not schema-expressible) rules,
      cited from the real upstream files.
- [ ] The marker-list gap against the real `waza-eval-matrix.yml` is
      stated as a verified finding, with the chosen gitapex marker
      argued against the real invocation line, and the credential-marker
      alternative explicitly considered and rejected.
- [ ] A concrete `waza-eval-matrix.yml` budget entry is proposed for
      `max_runs_per_day`/`max_retries`, with the cost/token ceiling
      explicitly flagged as an operator-supplied open input, not
      invented.
- [ ] The relationship to #124 (precondition, ordering stated
      explicitly) is specified.
- [ ] Gate placement (CI plane, no cluster) is decided and argued
      against an existing gitapex gate's precedent.

## Related Issue

Child of #82. Extends #144's design-then-implement precedent. Directly
gates issue #124's credentialed dispatch. Refs #153.

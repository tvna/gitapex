# Quality-vs-scope proportionality measurement for gitapex

Design-only companion doc for a new tracking issue, child of #82,
expanding #123's seed-gate scope. Supersedes #141's rating of CLAUDE.md
bullet 5.1 ("partial (deferred), citing #140 candidate 5 only") -- C5
(`ci-wall-time-budget`) is a narrower CI-timing signal and stays
independently deferred; this design targets the real proportionality
measurement CLAUDE.md section 5 actually asks for.

## Origin

User-supplied context (2026-07-18): the sibling repo `tvna/claude-md` has
a "developer experience / pre-release benchmark mechanism" that was
implemented partway and stalled. Grep across several plausible candidates
(devcontainer-startup timing, cache-regime comparison, codebase-maturity
summary) found none stalled -- all were mature and CI-wired. The user then
identified the actual mechanism: **OpenTelemetry-based auditing of
AI-agent-driven work history**. Primary source:
`docs/standards/host-unit-duckdb-metrics.md` (issue #815 in
`tvna/claude-md`) -- an adopted, OTLP-compatible per-host DuckDB store for
exactly CLAUDE.md section 5's quality-vs-scope proportionality signal.

**Confirmed fact:** that doc's own "Out of scope (deferred, with re-entry
points)" section lists several genuinely unfinished legs: no CI write
path (v1, by decision), no cross-host OTLP aggregation pipeline, no
automated runtime log recorder, and -- most consequentially -- an
explicit decision (Refs #826) that **ephemeral agent/web/CI sessions are
out of measurement scope by default**, with only a manual, operator-heavy
Cloudflare R2 escrow (#1212) as a stopgap. That boundary excludes exactly
the environments gitapex's own gates run in (#131's four execution
contexts: git hook, Claude-Code-style hook, CI job, MCP server
subprocess -- all ephemeral in claude-md's sense). A naive port of the
claude-md design would record nothing for gitapex, ever.

## 1. Decision: a CI-native write path, not the same ephemeral boundary

**Why not accept claude-md's own boundary (option A):** claude-md's
decision was sound there because durable operator hosts exist and record
rows -- the signal stays "openly partial by record," not empty. gitapex
has no such durable-host population; porting option A would produce an
empty signal while citing a precedent whose load-bearing condition
(durable hosts exist) does not hold for gitapex.

**Why a CI-native path is actually more tractable for gitapex, not less:**
claude-md's real obstacle was never ephemerality itself -- it was no
durable sink reachable from a runner without new infrastructure (no
`duckdb` dependency, a git-ignored local file, and a CI write path it
explicitly declined to open as a "reviewed write-path surface [the repo]
still avoids"). gitapex inverts every one of those premises:

1. gitapex's post-merge CI job (#140's `post-merge-auto-retro`) already
   writes durable, governed platform state (issues, comments) with
   credentials it already holds -- the write-path surface claude-md
   declined to open is sunk cost here.
2. Both signals below can be deterministic functions of the merge SHA
   plus platform history, deferring claude-md's stochastic half
   (N>=3 pinned-model benchmark runs) rather than blocking on it. A
   deterministic signal makes the store a cache: losing it costs
   re-computation, mirroring claude-md's own lifecycle stance.
3. A durable-host/CI hybrid was considered and rejected: no evidenced
   adopter class runs gitapex from a durable host distinct from CI, and
   a redistributed adopter's own CI is served identically by the same
   mechanism. Falling back to diff-size proxies only (#138 G4) concedes a
   gap those gates already document as a proxy, not the real signal.

## 2. Mechanism

**Scope signal -- `gitapex.scope.instruction_tokens` (deterministic).**
`cl100k_base` token count of the governed instruction surface at the
merge SHA: compiled `CLAUDE.md` + `.gitapex/ssot.json` + every registered
`policy_sources[].path`. Direct adaptation of claude-md's
`scope_compiled_tokens`, widened because gitapex's instruction surface is
registry-plus-policies, not one compiled file.

**Quality signal -- `gitapex.quality.repair_free_merge` (deterministic).**
Per merged PR: `1 / (1 + repairs)`, where `repairs` counts inline review
comments, post-open fix commits, and red-to-green CI cycles, read via the
#139 wrapper at merge time. Precedent: claude-md's own
`_auto_retro_ledger.py` repair-free merge-rate ledger (verified in #140
section 1) already collects a deterministic quality-per-change signal in
CI; this promotes it to the proportionality numerator instead of
importing claude-md's stochastic benchmark.

**Proportionality** = quality per 1k instruction tokens, derived at read
time and never stored -- keeps claude-md's generated-column discipline
(wrong, inconsistent entry is impossible by construction).

**Sink.** The same post-merge CI job as `post-merge-auto-retro`
(`pull_request_target closed + merged==true`) posts one idempotent,
marker-delimited (`<!-- gitapex-measurement v1 -->`) comment on the
merged PR containing a single OTLP-gauge-shaped JSON block
(`MetricName`/`MetricUnit`/`Attributes`/`TimeUnix`/`Value` -- the same
ClickHouse-exporter layout as claude-md's `otlp_metric_data_point`), and
uploads the same block as a CI artifact. PR comments are repo-durable,
append-shaped, need no new credentials beyond what auto-retro already
holds, and match this repo's established structured-body pattern (#138
gates 2 and 4). Cross-repo aggregation stays an export step: an optional
adopter-configured OTLP endpoint, declared in a policy source, off by
default, egress permitted only through #141's `egress-allowlist`
candidate (A4). No vendor is named -- the redistribution-safe pattern is
"adopter-owned collector endpoint declared in governed policy," never a
gitapex-upstream default.

**Redaction contract**, adapting claude-md's #88/#824 rules under #131's
zero-trust principles: a row carries only commit SHA, spec/registry
versions, integer counts, token counts, and `TimeUnix`. MUST NOT contain
hostnames or runner identity, filesystem paths, actor logins, CI run URLs
or request/run identifiers, review-comment text, or raw prompts/model
output; any exported row replaces repo identity with an opaque `repo.id`
hash. Fails closed on unverifiable redaction (#131 principle 6): if the
writer cannot verify the row clean, it posts nothing and emits a CI
annotation instead. Verified identity over asserted (#131 principle 5):
downstream consumers accept only marker-comments authored by the CI
identity; a matching comment from any other author is treated as data,
never as a trusted measurement.

## 3. Registry entries

The recorder and observer are gate-shaped (registered dispatch on
declared planes, subject to #140's `registry-self-validation`/
`registry-plane-drift`, per section 3's ship-the-drift-gate-with-the-
invariant rule); the measurement spec itself is a policy source,
following #140 candidate 5's advisory-gate precedent.

```jsonc
// policy_sources[]
{ "id": "quality-scope-measurement", "path": ".gitapex/policies/quality-scope-measurement.toml", "format": "toml",
  "authority": "metric definitions (instruction-surface glob, repair-count rules, tokenizer pin cl100k_base), OTLP field layout, redaction denylist, comment marker syntax, trend window and degradation threshold, optional adopter OTLP sink (default off)" }

// gates[]
{ "id": "quality-scope-recorder", "kind": "script", "script": "scripts/record_quality_scope.py",
  "rule": "on merged-PR close, compute deterministic scope and quality signals at the merge SHA and post one redacted OTLP-shaped measurement comment (idempotent marker); fail closed on unverifiable redaction: annotate, never post",
  "planes": ["ci"], "trigger": "pull_request_target closed + merged==true (shares auto-retro's job)",
  "fail_policy": "closed for the write, open for the merge itself (never blocks anything)",
  "policy_refs": ["quality-scope-measurement", "egress-hosts"],
  "cluster": "quality-scale", "tracking_issue": null },
{ "id": "quality-scope-observer", "kind": "script", "script": "scripts/observe_quality_scope.py",
  "rule": "recompute proportionality over the trailing window of verified measurement comments; on degradation past threshold, update a rolling advisory issue (the section 5 stop-and-re-plan signal); advisory forever, never a required check",
  "planes": ["ci"], "trigger": "scheduled (weekly) + workflow_dispatch",
  "policy_refs": ["quality-scope-measurement"],
  "cluster": "quality-scale", "tracking_issue": null }
```

## 4. Deferred, with re-entry points

Mirroring claude-md's own "Out of scope (deferred, with re-entry
points)" discipline rather than pretending everything is solved:

- **Stochastic quality signal** (claude-md's metric (b), N>=3 pinned-model
  runs): deferred until a gitapex benchmark spec exists; re-enters as an
  additive `MetricName` in the same comment block, reproducibility
  contract carried unchanged.
- **Cross-repo OTLP aggregation**: export-step only; re-enters when any
  adopter declares a sink in the policy source.
- **Adopter-local DuckDB recording** (claude-md's own path): rejected for
  now -- no evidenced durable-host adopter class; re-enters only as an
  adopter-side import of the same OTLP-shaped rows, never as a gitapex
  dependency.
- **Blocking enforcement of degradation**: never, per #140 candidate 5's
  standing verdict -- the threshold judgment is the human "stop and
  re-plan," the gate's job ends at making it observable.
- **`ci-wall-time-budget` (#140 C5)**: remains independently deferred;
  this design does not absorb it.

## Non-goals

- No code, no `.gitapex/` files, no `scripts/` edits -- design only.
- Not building the stochastic quality signal, cross-repo aggregation, or
  adopter-local recording -- all explicitly deferred above.
- Not making proportionality degradation a blocking check -- advisory
  only, matching #140 C5's precedent.

## Acceptance criteria

- [ ] The ephemeral-environment mismatch between claude-md's design and
      gitapex's own execution contexts is stated explicitly, with a
      reasoned decision (not a default copy of claude-md's boundary).
- [ ] Both signals (scope, quality) are deterministic functions of
      already-available inputs -- no new stochastic dependency introduced.
- [ ] Redaction contract adapted to #131's zero-trust principles, with an
      explicit fail-closed rule on unverifiable redaction.
- [ ] Concrete registry JSON for both gates plus the policy source.
- [ ] Every deferred item states its re-entry point, not just its absence.

## Related Issue

Child of #82. Expands #123's seed-gate scope, same pattern as #138,
#139, #140, #141. Supersedes #141's rating of bullet 5.1. Cross-references
#131 (zero-trust principles applied to redaction and write-path fail
policy), #138 (existing diff-size proxies this design does not replace),
#139 (repair-count read path), #140 (auto-retro CI job reused as the
write trigger; candidate 5's advisory-only precedent).

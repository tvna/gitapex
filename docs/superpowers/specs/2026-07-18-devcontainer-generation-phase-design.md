# An explicit, post-init devcontainer generation phase

Date: 2026-07-18

Refs #151 (child of #82). Supersedes #57's "PR 6: (Optional) devcontainer
wiring" stub (`docs/superpowers/specs/2026-07-14-setup-gitapex-toolchain-design.md`)
with a concrete phase-3 design rather than leaving it as a same-shape
provisioning target alongside the other 6 surfaces. Extends #127
(`gitapex init` scaffolding) and #147 (security-capability tiers -- the
concrete input this phase consumes). States an explicit non-consumption
boundary against #148 (business-domain hearing), which this doc does not
reopen. Checked against all seven #131 zero-trust principles, with
principles 2 (re-validate, never trust the caller), 3 (least privilege),
4 (assume breach), and 6 (fail closed) load-bearing.

## Design-only scope

Per this repository's discipline (matching #57/#123/#125/#126/#127/#130/
#131/#147/#148 precedent): this doc records a design only. No code, no
`.gitapex/` file, no `scripts/`/`hooks/` change, no `devcontainer.json`
or `Dockerfile` content is authored, no edit to
`.gitapex/ssot.schema.json`. The one new file this design proposes (a
devcontainer-regeneration baseline, below) is a proposal for the
implementation issue, matching #147's `security_tier` field precedent
for how a schema-adjacent addition gets recorded here without being
built here.

## Why this doc exists

#57's own design treats devcontainer as one of 7 "Claude execution
surfaces" needing the same treatment as macOS CLI, Linux CLI, Windows
CLI, and so on: provision the pinned toolchain into the environment. Its
stated direction -- "flake baked into image" -- follows from that framing
directly, and its own open-items list already flags what that framing
can't resolve: "devcontainer image ownership and rebuild cadence (PR 6)."

That framing is incomplete for gitapex specifically, because unlike the
other 6 surfaces, a devcontainer definition is not just an environment
that NEEDS the toolchain -- it is generated OUTPUT that should reflect
decisions #127/#147 make about the repo it belongs to. Concretely,
#147's access-control category cites the source Zero Trust document's
"Enterprise: sandboxed execution environments per agent... containers
with restricted capabilities... mandatory for agents handling untrusted
input" row, folds it in by reference, but never translates it into a
concrete gitapex mechanism -- there was nothing to translate it into
yet, because nothing in gitapex generates a container definition. A
devcontainer is exactly that mechanism, but only if its generation runs
AFTER a security tier exists to read. The other 6 surfaces stay exactly
as #57 designed them; this doc adds a new phase 3 downstream of #57 and
#127/#147, and does not touch anything upstream.

## The three-phase model

| Phase | What runs | Design owner | Invocation |
|---|---|---|---|
| 1 | Toolchain provisioning (`nix develop`, or the cooldown-gated installed-plugin bootstrap) | #57 (unchanged) | Per #57 -- automatic/session-scoped where it already is |
| 2 | `gitapex init` (scaffolding, `security-tier` election, #148's business-domain hearing) | #127 / #147 / #148 (unchanged) | Operator-invoked, per #127 |
| 3 | Devcontainer generation | This doc | Operator-invoked, explicit, separate from 1 and 2 (below) |

**Explicit-invocation is a hard rule: no phase triggers the next
automatically.** Phase 1 completing does not invoke phase 2; phase 2
completing does not invoke phase 3. Two independent reasons, not just
the operator's stated preference:

- **#131 principle 2 (re-validate, never trust the caller).** An
  auto-chain creates exactly the temptation this principle forbids:
  phase 3 skipping its own precondition check because "phase 2 just ran,
  so it must be fine." Forcing a separate invocation forces phase 3 to
  independently re-validate phase 1's and phase 2's actual on-disk state
  every time, matching CLAUDE.md section 3's own "refresh a time-boxed
  precondition immediately before each guarded operation" rule -- the
  precondition here (a valid, completed init) is exactly that kind of
  freshness fact, and it must be re-checked at phase-3 time, not
  inherited from phase-2 time.
- **#131 principle 3 (least privilege).** Devcontainer generation writes
  a different artifact class (container definitions, potentially
  `runArgs`/image-build inputs) than `gitapex init` writes
  (`.gitapex/ssot.json`, CODEOWNERS, rulesets). Bundling them into one
  invocation would broaden a single command's write surface beyond what
  either phase individually needs.

## Decision 1: split out of #57's "PR 6", not a 7th symmetric surface

**Decision: devcontainer generation is removed from `setup-gitapex-toolchain`'s
surface list and designed as its own phase-3 step/skill, structurally
downstream of BOTH phase 1 and phase 2 -- not parallel to the other 6
toolchain-only surfaces.**

The other 6 surfaces (web, macOS/Linux/Windows CLI, macOS/Windows
Desktop-local) each need exactly one thing: the pinned toolchain, live,
in an environment an operator or CI job is already running in. None of
them read `.gitapex/ssot.json`; none of them vary by `security_tier`.
Devcontainer is categorically different: its own definition is content
gitapex GENERATES, and that content should vary by tier (Decision 3,
below) -- a property none of the other 6 surfaces have. Keeping it in
#57's surface list would either (a) force #57's skill to also read
`.gitapex/ssot.json`, coupling a toolchain-only skill to init's output
for no reason the other 6 surfaces share, or (b) ship a devcontainer
that ignores tier entirely, which is the status quo this doc exists to
fix. Splitting is the smaller, more honest change: #57 keeps doing
exactly what it already does for 6 surfaces; this doc adds a distinct
phase-3 consumer for the 7th.

## Decision 2: precondition check, fail-closed

Before generating anything, phase 3 independently verifies, by reading
and validating on-disk state itself (never by trusting an operator's
say-so or a flag claiming "already done"):

- **Phase 1's artifact.** `flake.nix`/`flake.lock` present and
  resolvable (repo context), or `.gitapex/policies/toolchain.lock.json`
  present, schema-valid, and not stale past its cooldown TTL
  (installed-plugin context, reusing #57's own cooldown check rather
  than inventing a second one).
- **Phase 2's artifact.** `.gitapex/ssot.json` present, schema-valid
  (per `.gitapex/ssot.schema.json`), and carrying a resolved
  `security_tier` value from the closed enum (`foundation | enterprise |
  advanced`) -- not absent, not a placeholder. (Field name per #147:
  `security_tier`, snake_case, is the persisted `.gitapex/ssot.json`
  key; `security-tier`, hyphenated, names the closed-enum CLI input/
  election that produces it -- the two are not interchangeable
  spellings of one name.)

Any missing or invalid precondition is INDETERMINATE, and per #131
principle 6, INDETERMINATE is a deny: phase 3 refuses outright with a
message naming which phase is incomplete ("toolchain not provisioned --
run the toolchain setup skill first" / "`gitapex init` has not
completed -- run it before generating a devcontainer"). It never
degrades to a default toolchain version or an unset-tier fallback
posture; there is no narrowest-viable devcontainer to fall back to the
way #127's F2 has a narrowest-viable default ROW for an unmatched
enum -- an incomplete phase 2 is a hard stop, not a lookup miss.

## Decision 3: what phase 3 consumes, and what it explicitly does not

**Consumed (real, validated schema fields):**

- **`security_tier`** (#147) drives concrete devcontainer content --
  see the tier table below. This is the field this whole design exists
  to make useful.
- **Toolchain pins** (phase 1's lock content) are baked into the
  container image/features so a devcontainer starts with the exact
  tool versions the operator's `nix develop` already resolved --
  the one property this doc keeps from #57's original "flake baked into
  image" direction, now sequenced after tier exists rather than at
  independent build time.
- `team-size`/`platform` are available (they're in the same validated
  `.gitapex/ssot.json`) but this design does not invent a devcontainer
  use for them -- no `configure` row cites them below, and none should
  be added without a concrete argued reason, matching this repo's
  no-speculative-capability discipline.

**Explicitly NOT consumed: #148's business-domain hearing output.**
#148's Decision 1 is that the hearing "contributes zero decision-table
keys, zero schema fields, zero free text to any generated artifact, and
zero enforced state." There is therefore nothing structured for phase 3
to read -- not a policy choice this doc makes, a direct consequence of
#148's already-decided design. A domain-informed devcontainer
customization (e.g. "this repo handles card data, bake in a
card-data-pattern scanner") can only reach a devcontainer through
#148's own path: proposed as one of Stage 3's candidate recommendations,
reviewed, and if accepted, landed as an ordinary human-authored edit to
the generated devcontainer definition or to phase 3's own inputs --
never auto-applied by phase 3 parsing hearing prose. Restating this
here, rather than leaving it implicit, is this doc's explicit
consistency check against #148.

## Devcontainer content by tier

Closing #147's under-translated "sandboxed execution environments per
agent" row concretely. Tagged `configure`/`not covered` per #147's own
honesty vocabulary; devcontainer generation raises gitapex's floor
within container-boundary tooling, it does not change any `not covered`
verdict #147 already recorded at the platform level.

| `security_tier` | devcontainer `configure` | Honesty note |
|---|---|---|
| `foundation` | Toolchain baked in from phase-1 pins; no isolation beyond Docker's own container/namespace boundary | Matches #147 Foundation's "identity-based isolation... network segmentation as backstop" -- a devcontainer's own process boundary is exactly that backstop, not a hard barrier, and Foundation does not pretend otherwise. |
| `enterprise` | Dropped Linux capabilities beyond what the toolchain needs, read-only root filesystem where the toolchain tolerates it, CPU/memory resource limits, mount surface restricted to the repo tree | The concrete `configure`-class translation #147 cited but left untranslated: "sandboxed execution environments per agent... mandatory for agents handling untrusted input." |
| `advanced` | Enterprise plus: no-new-privileges, a pinned seccomp profile, network egress restricted to an explicit allowlist where the host/CI platform supports it | `not covered` ceiling restated, not raised: hardware isolation / confidential computing (AMD SEV, Intel TDX, gVisor-class kernel-level syscall interposition) stays out of reach on a shared Docker daemon. Devcontainer generation cannot close #147's Advanced-tier `not covered` gap for hardware isolation; it only tightens what container-boundary tooling can enforce. |

*Speculation, named as such:* the exact devcontainer-spec field names
(`runArgs`, `hostRequirements`, `mounts`, or their equivalents) that
carry capability-drop/seccomp/resource-limit settings are an
implementation-time detail to verify against the live
`containers.dev` specification, not asserted as fact here -- this table
states WHAT each tier configures, not the literal JSON shape.

**Enforceability check, per control.** The table's "where the toolchain
tolerates it" (read-only root) and "where the host/CI platform
supports it" (egress allowlist) qualifiers are not silent
best-effort language -- each names a control whose applicability phase
3 must actually probe before claiming it, because a `configure` tag
that turns out unenforceable on the live toolchain/host would report a
tier stronger than what was actually applied, the same overclaim F2
already forbids for the platform-level controls. For each such
conditional control, phase 3 probes enforceability against the
resolved toolchain (phase 1's pins) and the target host/CI platform
before generating: if enforceable, it is emitted and stays `configure`;
if not, generation still proceeds for the controls that ARE
enforceable, but the unenforceable control is downgraded to
`recommend` in the same generated devcontainer-companion output #147's
posture report uses for platform-level `recommend` items (documenting
what could not be applied and why), never silently omitted or left
implied by an unqualified `configure` tag. Generation itself is never
blocked by one unenforceable control -- only #131 principle 6's
INDETERMINATE precondition failures (Decision 2, above) block phase 3
outright; a known-unenforceable control is a determinate `recommend`,
not an INDETERMINATE.

## Decision 4: regeneration reuses #127's monotonicity discipline

**Decision: `.devcontainer/**` (definition file plus any generated
Dockerfile) joins the existing protected-paths set alongside
`.gitapex/ssot.json` and `.gitapex/policies/**` under F3's ruleset
(`bypass_actors: []`, PR-required, code-owner review) -- extending that
floor, not creating a parallel one. Regeneration on a later change
(toolchain pin bump, `security_tier` change via re-init) reuses #127's
existing re-init rule unchanged: diff the newly generated output against
LIVE PLATFORM state (never a local copy, per F4), classify each change
as narrowing (tightening -- an added capability drop, a newly-scoped
mount) or widening (loosening -- a removed seccomp profile, opened
network egress), proceed narrowing through the normal dry-run-first
apply, and block widening pending explicit recorded confirmation.**

No new parallel mechanism is designed because none is needed: a
generated devcontainer definition is structurally the same kind of
artifact `.gitapex/ssot.json` already is (binary-emitted from typed
input, merge-gated, subject to narrowing/widening classification), and
#127's rule was written generally enough to apply directly. A
`.gitapex/policies/.devcontainer-baseline.json` companion file is
proposed, mirroring `.init-baseline.json`'s three-way diff
(baseline/live/new) so an operator's manual devcontainer edits are
preserved rather than silently clobbered on regeneration -- with F4's
widening-block remaining a non-bypassable backstop regardless of a
change's "customization" label, exactly as #127 already specifies for
`ssot.json`. This is a `policy_sources[]` registration, not a
`.gitapex/ssot.schema.json` change.

**Preserving an edit is not the same as revalidating it.** The
widening/narrowing diff (F4) classifies *changes between live and
new*; a manual relaxation an earlier PR already approved (an extra
host mount, `privileged: true`) is unchanged by a tier raise and so
produces no diff hunk at all -- F4 has nothing to classify because
nothing moved. Left there, raising `security_tier` to `enterprise`/
`advanced` could complete while the merged devcontainer still carries
a pre-existing relaxation that defeats the newly selected tier's own
required controls (Devcontainer content by tier, above), and F4's
widening-block would never fire because it only ever looks at deltas.
So the three-way merge gets one more step beyond F4's existing diff:
after computing baseline/live/new and preserving live-only manual
edits per the usual rule, phase 3 validates the MERGED result (not
just the diff) against the newly selected tier's required-control set
-- the same table the enforceability check above already probes. A
preserved edit that violates a required control for the target tier
is reported the same way an unenforceable control is (a named
`recommend`/flagged item in the devcontainer-companion output,
above), and the operator resolves it explicitly (drop the manual
edit, or accept the lower effective tier consciously) rather than the
scaffold silently reporting a tier stronger than what the merged
definition actually enforces.

**The self-regeneration attack scenario, named explicitly.** #131
principle 4 (assume breach) requires asking: what if phase 3 runs FROM
INSIDE a compromised devcontainer, regenerating its own definition to
loosen its own isolation? The live-platform-state diff (F4, reused
unchanged) is the existing defense: the baseline it diffs against is
never the local container's own copy, so a compromised container cannot
launder a widened definition past the check by editing local state --
the widening block fires regardless of where the regeneration was
invoked from, because the check does not trust the invocation origin,
only the fetched platform state.

## Decision 5: where phase 3 runs

**Decision: phase 3 is CLI-native, unlike #148.** Contrast stated
explicitly because the two designs reach opposite conclusions for a
principled reason: #148's business-domain hearing is open-ended (real
unknown unknowns, no enum can capture the answer space), which is why
it requires an agent and has no CLI-native form at all, degraded or
otherwise. Phase 3's inputs are the opposite -- fully structured,
already-validated schema fields (`security_tier`, resolved toolchain
pins) with no discovery step needed. A deterministic CLI subcommand
(e.g. `gitapex devcontainer generate`, naming an implementation-issue
detail) reading those fields and emitting typed, serialized JSON (never
string-templated, matching #127's F1 discipline unchanged) is the
complete mechanism -- no agent required, though an agent session MAY
invoke the same CLI command on the operator's behalf with no special
treatment, exactly as it may invoke `gitapex init`'s own enum questions.

Non-interactive/CI: identical to the interactive path, since there is
no discovery step to skip -- `gitapex devcontainer generate` behaves the
same whether invoked by a human, an agent, or a CI job, given the same
on-disk state. This differs from #147's non-interactive default-tier
rule (which exists because tier has an operator-facing suggestion to
skip) -- phase 3 has no suggestion to make; it either finds a valid
tier already recorded or refuses per Decision 2.

## Facts vs. speculation

Facts: #57's stated "flake baked into image" direction and its
unresolved "devcontainer image ownership and rebuild cadence" open item;
#127's F1-F6, its `.init-baseline.json` three-way-diff pattern, and its
re-init monotonicity rule; #131's seven principles; #147's `security_tier`
field, its honesty vocabulary (`configure`/`recommend`/`not covered`),
and its citation of the source Zero Trust document's "sandboxed
execution environments per agent... mandatory for agents handling
untrusted input" Enterprise-tier row (quoted from #147's own text, which
itself cites the source document); #148's Decision 1 (zero schema
fields from the business-domain hearing).

Speculation, named as such: the exact devcontainer-spec (`containers.dev`)
field names for capability/seccomp/resource-limit settings (table note,
above); the exact CLI subcommand name and whether it ships as part of
the `gitapex` binary or a separate skill akin to #148's hearing skill;
whether `team-size`/`platform` gain a concrete devcontainer use in a
later revision (none is invented here); the precise devcontainer-spec
version gitapex targets.

## Non-goals

- No CLI subcommand code, no `devcontainer.json`/Dockerfile content, no
  `.gitapex/ssot.schema.json` change -- design only. The
  `.devcontainer-baseline.json` companion file is proposed, not built.
- Not reopening #57 PRs 1-5 (toolchain foundation), #127's resolved
  input/output questions, #147's tier framework, or #148's hearing
  design -- this doc sequences a new phase 3 after them and fills
  #147's under-specified resource-boundaries row; it does not
  re-litigate any of their answers.
- Not claiming devcontainer generation can incorporate business-domain
  hearing output as structured input -- explicitly out of scope per
  #148's Decision 1 (Decision 3, above).
- Not closing #147's Advanced-tier hardware-isolation `not covered`
  verdict -- restated, not resolved (tier table, above).
- Not designing #57's toolchain-provisioning mechanism itself (`nix
  develop`, the cooldown-gated bootstrap) -- reused unchanged as phase
  1's input to phase 3, never modified.

## Acceptance criteria

- [ ] Three-phase sequence stated with explicit-invocation-only as a
      hard rule, argued from #131 principles 2 and 3 (not merely
      operator preference).
- [ ] The split from #57's "PR 6" stub into a distinct phase-3 step is
      argued (why the other 6 surfaces stay as-is and devcontainer
      doesn't belong among them), not asserted.
- [ ] Phase-3 precondition check specified for both phase-1 and phase-2
      artifacts, grounded in #131 principles 2 and 6, with an explicit
      refuse-not-degrade failure mode (no narrowest-viable devcontainer
      fallback invented).
- [ ] Consumed/not-consumed inputs stated precisely: `security-tier`
      yes with a concrete per-tier content table; business-domain
      hearing output no, reconciled explicitly with #148's Decision 1.
- [ ] Regeneration reuses #127's monotonicity discipline (narrowing
      proceeds, widening blocks, live-platform-state baseline) with the
      protected-paths extension to `.devcontainer/**` stated, and the
      self-regeneration-from-inside attack scenario named with its
      existing defense (F4) identified.
- [ ] Invocation placement is CLI-native, explicitly contrasted with
      #148's agent-only requirement and the principled reason for the
      difference (structured vs. open-ended input) stated, not just
      asserted.
- [ ] The connection to #147's under-translated "sandboxed execution
      environments" row is stated explicitly, with the honesty note
      that Advanced-tier hardware isolation stays `not covered`.

## Related Issue

Child of #82. Extends #57 (supersedes its "PR 6" devcontainer stub),
#127 (`gitapex init`), and #147 (`security-tier` -- the concrete
consumer input). States an explicit non-consumption boundary against
#148 without reopening it. Refs #151.

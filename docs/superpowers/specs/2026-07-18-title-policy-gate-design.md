# An issue/PR title-policy gate

Date: 2026-07-18

Refs #154 (child of #82). Extends #144's design-then-implement
precedent. Closes a previously-unstated dependency gap in #138 Gate 4's
own design.

## Design-only scope

Per this repository's discipline (matching #57/#123/#125/#126/#127/#130/
#131/#144/#145/#147/#148/#151/#152/#153 precedent): this doc records a
design only. No `.gitapex/policies/title-policy.toml`, no gate script,
no PreToolUse hook is created by this pass.

## Why this doc exists

The same upstream audit that found #153's LLM-budget gap also found
gitapex has no title-policy design, despite THREE existing gitapex
artifacts already assuming one exists:

- `docs/motivation.md`'s to-be sequence diagram lists `title_policy` by
  name as one of four PreToolUse gates firing on issue creation
  (alongside `preflight_non_ascii`, `issue_classification_labels`,
  `issue_ci_staleness`).
- `skills/merge-retrospective/SKILL.md` references "a title-policy hook
  the repo enforces" and instructs verifying a filed issue's title
  "passed any title-policy gate the repo enforces (no rejection or
  auto-edit)" -- twice, as a real scenario the skill must handle.
- #138 Gate 4 (`gate-refactor-net-growth`,
  `docs/superpowers/specs/2026-07-17-claude-md-thinning-gate-candidates.md`)
  fires "only on PRs titled `refactor(scope): ...`" -- and its own text
  flags the gap this issue closes: adopting it "requires... a small,
  separate `docs/versioning.md` decision" about documenting a
  `refactor` type, since nothing verified a PR title's shape in the
  first place. (`docs/versioning.md` has since been updated to document
  `refactor(...)` in its convention table -- confirmed this session --
  but no gate enforces that any PR title, refactor or otherwise,
  actually conforms to it.)

gitapex's own commit history this session already follows the
convention informally (`docs(cli): ...`, `feat(cli): ...`) with zero
enforcement behind it -- an adopted-in-practice convention nothing
verifies.

## Decision 1: the core port -- ASCII-only + conventional-commit shape

**Decision: port the two-layer mechanism from `tvna/claude-md`
(`scripts/title_policy.py` + `scripts/preflight_title_policy.py`,
`.github/title-policy.toml`) as the floor, unabridged -- relocated to
`.gitapex/policies/title-policy.toml` per #123 Addendum 3 (gitapex
consolidates every `policy_sources[]`-eligible file under
`.gitapex/policies/`, not scattered under `.github/` the way claude-md's
own bottom-up history left it). The mechanism is ported unabridged; only
the file's location changes.**

**Server-side gate** (a `.github/scripts/gate_title_policy.py`-equivalent
reading `.gitapex/policies/title-policy.toml`, wired into CI on issue/PR
events -- the gate SCRIPT stays under `.github/scripts/`, gitapex's own
established convention for gate code (#144/#145); only the policy DATA
file moves under #123 Addendum 3): two checks, cited from the real
upstream docstring rather than paraphrased --

1. **ASCII-only.** "Title text is header-level metadata: it appears in
   notifications, project lists, triage queues, and agent summaries
   before body context is inspected. Keep it ASCII-only so zero-width
   marks, RTL controls, emoji, Japanese text, and homoglyphs are
   rejected at the boundary." This is the real upstream rationale,
   verbatim, and it is a prompt-injection defense specifically because
   a title is read before an agent decides how much of the body to
   trust (the same boundary #148's own hearing-skill trust model and
   this repo's CLAUDE.md section 2 discipline already treat as
   security-relevant).
2. **Conventional-commit shape.** `type(scope): summary`, `type` drawn
   from a closed list (Decision 4), `scope` matching a fixed pattern.
   Fails loud (exit 1) on either violation, matching CLAUDE.md section
   4's fail-loud-not-silent-catch rule.

**Client-side PreToolUse hook**, ported as a required second layer, not
an optional extra: gitapex already has an established PreToolUse-hook
pattern (`hooks/check-bash-safety.sh`, `hooks/check-template-
overwrite.sh`) -- a title-policy hook denying a non-conforming
`mcp__github__issue_write`/`create_pull_request`/`update_pull_request`
call BEFORE it reaches GitHub is the same defense-in-depth shape these
two already establish, catching the violation earlier and cheaper than
the server-side gate would. Fail-open contract, stated explicitly per
the real upstream hook's own documented contract: "any parse error or
unexpected payload shape emits `::error::...` to stderr and exits 0
with no decision, so a hook bug never wedges the session" -- the
server-side gate remains the backstop regardless of a hook-side failure,
exactly the split #131 principle 6 (fail closed, including on
INDETERMINATE) requires at the layer that actually enforces, while the
convenience layer degrades safely.

## Decision 2: ASCII-only becomes operator-configurable, not an absolute floor

**Correction (2026-07-18, operator feedback):** Decision 1 above ported
the ASCII-only check as an unconditional floor, matching claude-md's own
posture unexamined. Revised: gitapex makes it a configurable policy
toggle, defaulting to the secure (ASCII-only) state, with an explicit,
reasoned opt-out -- not a blanket relaxation, and not adopted
uncritically either direction.

**The two upstream rationales are distinct and must be separated, not
bundled:**

1. **Prompt-injection defense** -- "zero-width marks, RTL controls...
   homoglyphs... cannot smuggle instructions through the header layer"
   (Decision 1's quoted rationale). This is genuinely security-relevant.
2. **LLM reasoning-cost optimization** -- non-ASCII/multibyte content
   costs more tokens and, per the operator's own framing, may complicate
   model reasoning. This carries **no security implication at all**; an
   operator accepting a token-cost increase for readability is a pure
   engineering trade-off CLAUDE.md section 4's defense-in-depth
   principle has no claim over. Only rationale 1 needed the
   reasoned-opt-out treatment below -- rationale 2 is not a reason to
   gate anything.

**Why the injection-defense rationale is conditional, not absolute:** it
depends on an attacker precondition -- an untrusted party (or untrusted
content later reflected into a title) reaching the issue/PR title-write
surface. When that precondition does not hold (a closed, trusted-
operator environment with no external-contributor path to the
title-write surface -- the operator's own "platform where the attack
surface is not exposed" framing), the defense's marginal value drops
toward zero while its cost (cognitive burden on non-English operators)
stays fixed. This is the same attacker-precondition reasoning #147/#151
already use elsewhere -- #126's MCP server mode is "least-trusted-by-
default" *specifically because* an arbitrary external client can
connect; where no such caller exists, that specific defense's rationale
does not transfer either. Applying the source Zero Trust document's own
"impossible vs. tedious" test (#147): ASCII-only makes the smuggling
vector impossible while the character set is restricted, but the
attacker precondition it defends against is not universal -- so gating
the CHECK on whether that precondition holds is a legitimate
scope-narrowing, not a security downgrade of a control that would
otherwise always apply.

**Mechanism, fail-closed by default:**

- `.gitapex/policies/title-policy.toml` gains `ascii_only` (boolean,
  **default `true`**) and, required only when `ascii_only = false`, a
  non-empty `non_ascii_rationale` string field. The gate refuses to load
  a config with `ascii_only = false` and an empty/missing rationale --
  mirroring #127's widening-block and #152's doc-graph-waiver pattern:
  this defense never relaxes silently, only via an explicit, recorded
  reason a reviewer can see in the policy file itself (not buried in a
  PR body that later merges and disappears from view).
- **Missing or malformed config is read as `ascii_only = true`** (#131
  principle 6, fail closed on INDETERMINATE) -- an operator who wants
  the relaxation must explicitly configure it; absence of configuration
  is never interpreted as opt-out.
- The client-side PreToolUse hook reads the SAME toggle from the SAME
  file, never a cached or hardcoded default -- #131 principle 2 (every
  invocation re-validates its own inputs) applies to the hook re-reading
  live config, not just to external input.

**A narrower, unconditional floor survives the toggle -- this is not a
blunt on/off switch.** Even with `ascii_only = false`, the gate still
unconditionally rejects zero-width characters (ZWSP/ZWNJ/ZWJ/BOM),
bidirectional control overrides (RLO/LRO/PDF and the newer isolate
controls), and other Unicode format ("Cf" category) characters -- none
of these have any legitimate use in a title in ANY language, so nothing
about the operator's stated productivity concern argues for allowing
them, and this is the specific vector the upstream rationale names
first ("zero-width marks, RTL controls"). What toggles OFF is the
broader restriction to ordinary printable ASCII -- legitimate multibyte
text (Japanese, accented Latin, CJK, emoji) becomes permitted. Homoglyph
confusion (a lookalike character substituted for an expected ASCII one)
is a narrower residual risk specifically about text PRETENDING to be
ASCII; a title legitimately written in Japanese is not making that
pretense, so this design does not additionally restrict homoglyphs when
`ascii_only = false` -- named here as a considered, not overlooked,
scope boundary.

**Explicitly NOT gated by #147's `security-tier`.** Considered and
rejected: tier answers "how much security depth for this organization's
overall risk profile"; this toggle answers a narrower, different
question ("does an untrusted party reach the title-write surface at
all"), and the two are not reliably correlated -- an `advanced`-tier
regulated solo operator with zero external contributors, or a
`foundation`-tier project that unexpectedly gains public contributors,
are both coherent combinations this design must not forbid by coupling
the axes. This follows #147's own established precedent of keeping
`team-size` and `security-tier` independent rather than forcing one to
determine the other.

**What does NOT change:** the conventional-commit-shape check (Decision
1, item 2) remains an unconditional floor. No injection-defense/
cognitive-load trade-off applies to it -- a type/scope mismatch is not a
smuggling vector, so nothing argues for making it configurable, and this
decision does not touch it.

## Decision 3: fail-loud vs. fail-open, stated per layer (not blanket-copied)

Restated as its own decision because CLAUDE.md section 4 requires the
split to be argued per function, not defaulted: the SERVER-SIDE gate
fails loud on a genuine policy violation (a bad title must be blocked,
full stop -- #131 principle 6). The CLIENT-SIDE hook fails OPEN only on
its OWN malfunction (a parse error, an unexpected payload shape it
cannot interpret) -- never on a title it correctly identified as
violating policy, where it still denies. The two are not in tension:
one is "the hook is broken" (fail open, server backstop catches it),
the other is "the title is bad" (fail closed at both layers).

## Decision 4: allowed-types list, grounded in gitapex's own real usage

**Decision: `chore, ci, docs, feat, fix, perf, refactor, revert, test`
-- nine types, not claude-md's eleven, each individually justified
rather than copied wholesale.**

Checked this session (`git log --all --format='%s'` over gitapex's real
history, not assumed):

| Source | Types |
|---|---|
| Actually used in gitapex's committed history | `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `test` |
| Documented in `docs/versioning.md`'s convention table (verified current text) | `feat`, `fix`, `docs`, `refactor` (per product scope: `plugin`/`cli`/`compose`) |
| Structurally required though unused so far | `revert` -- CLAUDE.md section 3 names `git revert` as the default rollback path; a title-policy list that omits the type this repo's own rollback discipline requires would force a future revert PR to either violate the policy or invent an ad hoc title shape |

Dropped from claude-md's eleven, with reasons, not silently: `build`
(no build-tooling commits exist yet in gitapex's still-Python-scripts
stage; add when the Rust CLI build surface referenced throughout
#125/#131 materializes, not preemptively -- CLAUDE.md section 4's
"decide whether a check is needed" applied to a TYPE, not just a gate)
and `style` (no formatting-only commit class has appeared; same
reasoning). Neither is banned forever -- both are one `title-policy.toml`
edit away when a real commit needs them, matching this repo's own
anti-speculative-complexity discipline (#125's rule, applied here to a
type list instead of a gate kind).

Scope pattern: reuse claude-md's own `[a-z0-9][a-z0-9-]*` unchanged --
gitapex's real scopes (`cli`, `plugin`, `skills`, `battle-testing-a-
skill`, `evaluating-skill-quality`, ...) already fit it without
exception, verified against the same git-log scan; no argued need to
diverge.

## Decision 5: what is NOT ported -- named, not silently dropped

Two of claude-md's refinements are explicitly NOT adopted now, each
because it exists to fix a specific incident history gitapex does not
share:

- **Type-fit heuristic** (detecting performance-flavored wording
  mis-typed as something other than `perf`). claude-md's own comments
  cite specific incident numbers (#1424, #1054) that motivated this
  refinement after real false-positive/false-negative title mis-typing
  occurred there. gitapex has no equivalent incident. Adopting a
  keyword-heuristic classifier speculatively, before a real gitapex
  title has ever been mis-typed this way, is exactly the premature
  complexity CLAUDE.md section 4 warns against.
- **PR-title issue-ref dedup ban** (`(#NNN)` tokens forbidden in PR
  titles because the PR body's `Refs #NNN` line is claude-md's single
  source of truth for the issue link, per claude-md's #167/#214).
  gitapex's own PR body convention (this session's own PR bodies, this
  repo's `.github/PULL_REQUEST_TEMPLATE.md`) already uses a `Refs #NNN`-
  style body line, so the STRUCTURAL precondition for this rule exists
  -- but no gitapex incident has yet shown a title duplicating it
  causing real confusion. Named as available (not designed further) if
  one does.

Both are one future issue away, each requiring its own gitapex-specific
incident or argued need to trigger -- not a blanket "claude-md has more
rules so add them" default.

## Decision 6: confirming the three existing dependents are actually satisfied

Not just listed as motivation -- checked against this design:

- **`docs/motivation.md`'s diagram** names `title_policy` as a
  PreToolUse gate alongside three others already real in this repo's
  design vocabulary (`preflight_non_ascii` -- not yet gitapex-designed
  either, out of this issue's scope; `issue_classification_labels` --
  #123's deferred label-policy territory; `issue_ci_staleness` --
  undesigned). This design's client-side hook (Decision 1) is the
  concrete mechanism the diagram's `title_policy` box refers to --
  satisfied.
- **`merge-retrospective` SKILL.md**'s "verify... title passed any
  title-policy gate the repo enforces (no rejection or auto-edit)"
  step now has a real gate to check against (Decision 1's server-side
  gate is the enforcement it defers to; the skill's own text already
  treats it conditionally -- "the repo enforces" -- so no SKILL.md edit
  is required by this design landing, only by its eventual
  implementation) -- satisfied, pending implementation.
- **#138 Gate 4**'s `refactor(scope):`-triggered net-growth check now
  has an upstream gate ensuring any title reaching it actually has the
  shape Gate 4's own trigger logic assumes (a title-policy violation
  would be caught by THIS gate first, so Gate 4 never has to defend
  against a malformed trigger string) -- satisfied, and this design
  explicitly closes the gap Gate 4's own text flagged as needed
  ("requires... a small, separate `docs/versioning.md` decision").

## Facts vs. speculation

Facts: `tvna/claude-md`'s `scripts/title_policy.py`,
`scripts/preflight_title_policy.py`, and `.github/title-policy.toml`
(the real upstream's own placement -- gitapex's is
`.gitapex/policies/title-policy.toml`, per #123 Addendum 3), read in
full this session (ASCII-only rationale, conventional-shape regex
construction, fail-open hook contract, all quoted from real
docstrings); gitapex's own real commit-title type usage (`git log
--all --format='%s'`, checked this session); `docs/versioning.md`'s
current convention table (verified to already document `refactor(...)`,
resolving #138 Gate 4's own flagged gap on the versioning-doc side,
though not the enforcement side this issue covers); the three
dependents' exact text in `docs/motivation.md`,
`skills/merge-retrospective/SKILL.md`, and #138's own design doc.

Speculation, named as such: whether `build`/`style` types will be
needed once gitapex's Rust CLI build surface materializes (Decision 4,
explicitly deferred, not designed); whether the type-fit heuristic or
issue-ref dedup rule will ever be needed for gitapex (Decision 5,
explicitly not adopted, named only as available); the exact CI
workflow/plane wiring beyond "server-side gate, client-side hook" is an
implementation-issue detail not fixed here; the exact Unicode-category
enumeration for Decision 2's surviving zero-width/bidi-control floor
(named by example, not exhaustively specified -- an implementation-issue
detail, likely `unicodedata.category() in {"Cf"}` plus an explicit
codepoint list for the specific RLO/LRO/PDF/isolate controls, verified
against a real Unicode reference at implementation time, not fixed
here).

## Non-goals

- No `.gitapex/policies/title-policy.toml`, no gate script, no
  PreToolUse hook -- design only. A later session may implement this,
  matching #144's design-to-code precedent.
- Not adopting the type-fit heuristic or issue-ref dedup rule now --
  Decision 5 names them as available future extensions, not designed.
- Not reopening #138 Gate 4's own design -- this issue closes a
  dependency gap Gate 4 already flagged, it does not redesign Gate 4.
- Not editing `docs/motivation.md`, `merge-retrospective/SKILL.md`, or
  `docs/versioning.md` -- Decision 6 confirms each is already
  compatible with this design or requires no change until
  implementation, not that this issue edits them.
- Not extending this configurability to the broader, not-yet-gitapex-
  designed `preflight_non_ascii`/`scan_non_ascii`-equivalent mechanism
  (issue/PR BODY and comment text, distinct from title-policy.py's
  title-only scope, per `docs/motivation.md`'s dependent list) -- out of
  this issue's scope. When that mechanism is designed, Decision 2's
  same two-rationale-separation and attacker-precondition argument
  should be revisited there rather than assumed to transfer
  automatically; named here so it is not silently forgotten, not
  designed here.

## Acceptance criteria

- [ ] Core mechanism (ASCII-only + conventional-commit shape, server
      gate + client PreToolUse hook) is specified completely, citing
      the real upstream contract verbatim where quoted.
- [ ] ASCII-only is specified as an operator-configurable toggle
      (Decision 2), not an absolute floor: the two upstream rationales
      (injection defense vs. cost optimization) are separated, the
      attacker-precondition argument for conditionality is stated, the
      default-true/fail-closed/mandatory-rationale mechanism is
      specified, the surviving unconditional floor (zero-width/bidi
      control characters) is named, and the explicit non-coupling to
      `security-tier` is argued, not assumed.
- [ ] Fail-loud/fail-open split is argued per layer (Decision 3), not
      blanket-copied.
- [ ] Allowed-types list is grounded in gitapex's own real git-log usage
      plus `docs/versioning.md`'s documented convention plus CLAUDE.md's
      structural `revert` requirement -- each type's inclusion or
      exclusion individually justified, not copied wholesale from
      claude-md's eleven.
- [ ] Type-fit heuristic and issue-ref dedup rule are explicitly named
      as NOT adopted now, with the specific claude-md incident history
      motivating each cited as the reason gitapex doesn't share it yet.
- [ ] Each of the three existing dependents is checked against the
      design and confirmed satisfied (or explicitly pending
      implementation), not just cited as motivation.
- [ ] The policy file lives at `.gitapex/policies/title-policy.toml`,
      not claude-md's own `.github/title-policy.toml` path -- per #123
      Addendum 3, with the gate script remaining under
      `.github/scripts/` per gitapex's separate, already-established
      gate-code convention.

## Related Issue

Child of #82. Extends #144's design-then-implement precedent. Closes a
previously-unstated dependency gap in #138 Gate 4's own design. Refs
#154.

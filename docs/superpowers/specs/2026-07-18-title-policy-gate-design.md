# An issue/PR title-policy gate

Date: 2026-07-18

Refs #154 (child of #82). Extends #144's design-then-implement
precedent. Closes a previously-unstated dependency gap in #138 Gate 4's
own design.

## Design-only scope

Per this repository's discipline (matching #57/#123/#125/#126/#127/#130/
#131/#144/#145/#147/#148/#151/#152/#153 precedent): this doc records a
design only. No `.github/title-policy.toml`, no gate script, no
PreToolUse hook is created by this pass.

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
`.github/title-policy.toml`) as the floor, unabridged.**

**Server-side gate** (a `.github/scripts/gate_title_policy.py`-equivalent,
wired into CI on issue/PR events): two checks, cited from the real
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
   from a closed list (Decision 3), `scope` matching a fixed pattern.
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

## Decision 2: fail-loud vs. fail-open, stated per layer (not blanket-copied)

Restated as its own decision because CLAUDE.md section 4 requires the
split to be argued per function, not defaulted: the SERVER-SIDE gate
fails loud on a genuine policy violation (a bad title must be blocked,
full stop -- #131 principle 6). The CLIENT-SIDE hook fails OPEN only on
its OWN malfunction (a parse error, an unexpected payload shape it
cannot interpret) -- never on a title it correctly identified as
violating policy, where it still denies. The two are not in tension:
one is "the hook is broken" (fail open, server backstop catches it),
the other is "the title is bad" (fail closed at both layers).

## Decision 3: allowed-types list, grounded in gitapex's own real usage

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

## Decision 4: what is NOT ported -- named, not silently dropped

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

## Decision 5: confirming the three existing dependents are actually satisfied

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
`scripts/preflight_title_policy.py`, and `.github/title-policy.toml`,
read in full this session (ASCII-only rationale, conventional-shape
regex construction, fail-open hook contract, all quoted from real
docstrings); gitapex's own real commit-title type usage (`git log
--all --format='%s'`, checked this session); `docs/versioning.md`'s
current convention table (verified to already document `refactor(...)`,
resolving #138 Gate 4's own flagged gap on the versioning-doc side,
though not the enforcement side this issue covers); the three
dependents' exact text in `docs/motivation.md`,
`skills/merge-retrospective/SKILL.md`, and #138's own design doc.

Speculation, named as such: whether `build`/`style` types will be
needed once gitapex's Rust CLI build surface materializes (Decision 3,
explicitly deferred, not designed); whether the type-fit heuristic or
issue-ref dedup rule will ever be needed for gitapex (Decision 4,
explicitly not adopted, named only as available); the exact CI
workflow/plane wiring beyond "server-side gate, client-side hook" is an
implementation-issue detail not fixed here.

## Non-goals

- No `.github/title-policy.toml`, no gate script, no PreToolUse hook --
  design only. A later session may implement this, matching #144's
  design-to-code precedent.
- Not adopting the type-fit heuristic or issue-ref dedup rule now --
  Decision 4 names them as available future extensions, not designed.
- Not reopening #138 Gate 4's own design -- this issue closes a
  dependency gap Gate 4 already flagged, it does not redesign Gate 4.
- Not editing `docs/motivation.md`, `merge-retrospective/SKILL.md`, or
  `docs/versioning.md` -- Decision 5 confirms each is already
  compatible with this design or requires no change until
  implementation, not that this issue edits them.

## Acceptance criteria

- [ ] Core mechanism (ASCII-only + conventional-commit shape, server
      gate + client PreToolUse hook) is specified completely, citing
      the real upstream contract verbatim where quoted.
- [ ] Fail-loud/fail-open split is argued per layer (Decision 2), not
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

## Related Issue

Child of #82. Extends #144's design-then-implement precedent. Closes a
previously-unstated dependency gap in #138 Gate 4's own design. Refs
#154.

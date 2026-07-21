# Repository-scoped skills must not ship in the distributed plugin

**Date:** 2026-07-20
**Status:** Implemented (superseding an earlier revision of this same spec
that proposed relocation instead -- see "Revision note" below)
**Scope:** Enumerate which of gitapex's 17 skills were unsafe to redistribute
as-is, and rewrite them so every skill in `skills/` is genuinely `Portable`
(or `Mixed` with an already-isolated repo-specific detail), keeping the
existing "distribute all of `skills/`" behavior correct instead of carving
out an exception for it. Issue: #222.

## Revision note

This spec's first revision (committed to the same PR) proposed relocating
the four `Repository-scoped` skills to `.claude/skills/` and adding a
`plugin.json` allowlist for the rest. The operator corrected the direction
before merge: the environment is also installing other skill collections
(Superpowers, Clairvoyance) for developer experience, `.claude/skills/` is
explicitly not to be used as the storage mechanism, and the standing premise
going forward is to make a skill redistributable by rewriting it, not by
segregating it from distribution, unless a skill is found that genuinely
cannot be generalized. Section 2's enumeration is unchanged (it was already
accurate); section 3 below replaces the relocation-plus-allowlist design
with the generalization actually implemented.

## 1. Context

gitapex describes itself, in its own plugin manifest, as "a distributable
skills collection": any repository can install it as a Claude Code plugin via
`/plugin marketplace add` or `apm install`, and `docs/repository-layout.md`
states that "only skills (and, later, hooks) are deployed as runtime
primitives" -- with no carve-out. In practice this means every directory
under `skills/` that has a `SKILL.md` is fetched into every consumer's agent.

Separately, gitapex already runs a `portability` taxonomy
(`skills/evaluating-skill-quality/SKILL.md`'s "Portability level" section,
mechanized by the `metadata/gitapex.yaml` sidecar from
`docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md`):

- **Portable** -- every behavior-controlling instruction resolves inside the
  skill's own folder or cites general product docs.
- **Repository-scoped** -- intentionally depends on the origin repo's own
  tooling or conventions. Legitimate, but must say so.
- **Mixed** -- a portable core plus repo-specific detail, which should be
  split into a clearly named reference rather than blended.

That taxonomy was checked, before this change, only for **honest
disclosure**: `skills/evaluating-skill-quality/scripts/check_skill_shape.py`
(gated in CI by `tests/test_repository_skill_shape.py`) fails a skill that
behaves as Repository-scoped but does not declare it. Nothing read the
declaration to decide what actually gets **distributed**. A skill could be
perfectly honest about depending on gitapex's own conventions and still be
installed, as-is, into an unrelated repository.

## 2. Enumeration of targets

All 17 `skills/*/metadata/gitapex.yaml` sidecars were read directly to
produce this table (2026-07-20, before the rewrite in section 3). A prior
survey exists at
`docs/superpowers/specs/2026-07-19-skill-metadata-sidecar-design.md`
section 4.3 ("Current declared values to carry over"), from the sidecar
mechanism's own introduction; that table is a point-in-time snapshot from
its own sub-project and is not updated here, so this section re-derives
the current state directly from the tree rather than assuming the two
stay in sync.

### 2a. Repository-scoped (4, before this change) -- the actual redistribution risk

| Skill | What in it depended on gitapex specifically |
|---|---|
| `issue-to-branch` | `references/github-issue-workflow.md`'s write-path rules (tracking-issue-before-branch, connector-first, no-CLI-fallback) were, per the skill's own "Notes" section, "this repository's own git-ecosystem convention." |
| `outward-artifact-preflight` | Check 1's "agreed disclosure convention" and check 3's ASCII-only rule named gitapex's own provenance/character-set policy with no inline fallback. |
| `responding-to-a-fresh-arrival` | Step 3 (Label) read `.github/ISSUE_TEMPLATE/*.yml` and the header called this "this repository's own" label source. |
| `screening-a-low-trust-contribution` | Checks 1-3 hardcoded gitapex's own paths (`.github/workflows/**`, `hooks/**`, `skills/*/scripts/**`, its dependency manifests) with no substitution guidance beyond a header aside. |

Each of these four already stated, in its own SKILL.md, that the named part
was "this repository's own" and that a consumer should "substitute the
calling repository's actual convention" -- but that was prose in a detached
header/footer note, not an inline default+fallback next to the instruction
itself, and the field declared `Repository-scoped` rather than `Portable`.
Nothing stopped an unrelated consumer from receiving the file as-is.

### 2b. Mixed (4) -- already isolate the repo-specific part, no change made

| Skill | Repo-specific part (already isolated to one clause/citation) |
|---|---|
| `battle-testing-a-skill` | One "For readers working in this repository (gitapex)" clause in the metadata sidecar's `references`, plus a gitapex issue-number citation (`#74`) inside `references/adversarial-dimensions.md`. |
| `explaining-the-work` | "this repository's own" commit-trailer convention, named inline, two spots in `SKILL.md`. |
| `git-hosting-surface-audit` | Cites gitapex's own CLI-governance issue `#82` as a cross-link example. |
| `seeding-issue-pr-templates` | Names gitapex's own `issue-to-branch` convention as one worked example among general steps. |

These four were reviewed again under the corrected premise and still found
appropriately Mixed: the repo-specific detail is a citation or a single named
clause the skill's procedure does not depend on to run, not a functional
dependency that needs generalizing. No change made.

### 2c. Portable (9) -- unaffected

`driving-pr-to-merge`, `establishing-ubiquitous-language`,
`evaluating-skill-quality`, `issue-to-fix`, `merge-retrospective`,
`ranking-the-open-queue`, `scorer-gated-skill-edits`, `stop-and-replan`,
`untrusted-input-triage`. No repo-specific dependency found in any of these
sidecars or bodies.

### 2d. Confirmed: no skill needs to stay repository-internal

Re-reading all four Repository-scoped skills in full against gitapex's own
existing rubric bullet for exactly this situation
(`skills/evaluating-skill-quality/references/rubric.md:811-829`, the
consumer-repo-convention-deference dimension added in PR #216 / issue #200)
found no hidden gitapex-only mechanism in any of them -- each cites a
generic GitHub/git concept (issue-before-branch discipline, GitHub issue
templates, CI/hook/dependency-manifest paths, ASCII/provenance-disclosure
policy) that any repository can have its own version of. A repo-wide search
for exclusivity language ("gitapex CLI", "only gitapex", "specific to
gitapex", "gitapex itself") turned up nothing beyond `git-hosting-surface-
audit`'s already-Mixed, already-isolated citation to issue `#82`, which this
change does not touch. Conclusion: all four generalize; none needed to stay
repository-only, so no `.claude/skills/`-style segregation was needed.

## 3. Redesign implemented: generalize in place, reclassify to Portable

### 3a. Pattern

Per the rubric bullet cited in 2d, a `Portable` skill's write-path (or
similar) content should read as **a conditional default with an explicit,
inline fallback** ("substitute the calling repository's actual convention
where it differs"), not as the one correct shape asserted flatly, and not
as a fallback confined to a detached header/footer note. Applied to each of
the four:

1. **`issue-to-branch`**: `references/github-issue-workflow.md`'s write-path
   bullet now states the tracking-issue-before-branch rule as this skill's
   default with an inline fallback clause. The `hooks/check-bash-safety.sh`
   citations (there and in `SKILL.md`'s Stop boundary) are reframed as one
   illustrative example of backing enforcement, not an assumed dependency.
   The `SKILL.md` footer Notes section no longer uses `Repository-scoped`-style
   framing since the fallback is now inline in the reference file itself.
2. **`outward-artifact-preflight`**: check 1's "agreed disclosure convention"
   wording now says "the calling repository" instead of "this repository"
   (de-anchoring the demonstrative); check 3 (ASCII-only) gained an explicit
   "default to ASCII-only ... unless the calling repository documents a
   different character-set policy" clause; the Stop boundary's hook citation
   was reframed as illustrative, matching #1.
3. **`responding-to-a-fresh-arrival`**: the header no longer calls
   `.github/ISSUE_TEMPLATE/*.yml` "this repository's own" (it is a common,
   not gitapex-exclusive, GitHub convention); Step 3 gained an explicit
   fallback for a repository with no issue-type label templates; Global
   constraints' ASCII and hook-citation lines were reframed the same way as
   #2/#1. The worked example's bare `#142`/`#98` issue-number references
   were wrapped in inline code spans (`` `#142` ``), matching the convention
   already used by other Portable skills (e.g. `issue-to-fix`,
   `ranking-the-open-queue`) so a bare number does not live-autolink once
   the file is copied elsewhere.
4. **`screening-a-low-trust-contribution`**: the header, and checks 2
   (hook/script directories) and 3 (dependency manifests), now name
   gitapex's own paths as illustrative examples of a generic category with
   an explicit substitution clause, rather than the definition of the
   category. Check 1 (workflow-file edits) is unchanged -- it still names
   `.github/workflows/**` and `.gitlab-ci.yml`/`.gitlab/**` directly, with
   no per-check substitution clause of its own, relying only on the
   header's blanket aside; this is a real gap in the rewrite's coverage,
   not an intentional omission, and is corrected in this same revision (see
   the current file for the added clause). The worked example's bare
   `PR #211` was wrapped in an inline code span for the same reason as #3.

For all four, several other "per this repository's ... rule" asides (about
treating issue/PR text as untrusted, and about read-only decision
boundaries) were generalized to plain statements of the underlying
practice, since the practice itself is not gitapex-specific and the
"this repository's" framing was an unnecessary, un-generalizable anchor.

`metadata/gitapex.yaml`'s `spec.portability` was changed from
`Repository-scoped` to `Portable` for all four.

### 3b. Why this, not the relocation approach from the prior revision

The relocation approach (move to `.claude/skills/`, allowlist the rest in
`plugin.json`) was mechanically sound -- confirmed against Claude Code's own
docs (`code.claude.com/docs/en/plugin-marketplaces.md`'s "Advanced plugin
entries" and `code.claude.com/docs/en/skills.md`'s "Where skills live") --
but the operator ruled it out: it does not fit alongside installing other
skill collections for developer experience, and it treats a generalizable
skill as if it were irreducibly repo-only. Since section 2d found no skill
that actually needs that, generalizing in place is the smaller, more useful
change: every skill remains a real, working example of a genuinely portable
procedure, `skills/` continues to mean exactly what
`docs/repository-layout.md` already says it means, and no manifest or
directory-layout change was needed at all.

### 3c. Non-goals (still not part of this change)

- No content change to the four Mixed skills (2b) -- their repo-specific
  detail is already appropriately isolated and does not block distribution.
- No fix for the hooks-distribution finding below (2e was renumbered out of
  the main flow; see "Adjacent finding") -- separate follow-up issue.
- No manifest change: `.claude-plugin/plugin.json` and `marketplace.json`
  are unchanged, since nothing needs excluding from the default `skills/`
  scan anymore.

### Adjacent finding, still explicitly out of scope

`hooks/hooks.json` already wires `hooks/check-bash-safety.sh` and
`hooks/check-template-overwrite.sh` via `$CLAUDE_PLUGIN_ROOT` -- hooks are
already distributed today, which `docs/repository-layout.md`'s "(and, later,
hooks)" phrasing does not reflect. `check-bash-safety.sh` itself still
encodes gitapex-only deny rules (`gh issue`/`gh pr` writes, `gh pr merge`).
Same redistribution-risk class as this spec, different artifact type (a hook
script, not a skill folder, with its own manifest surface). Tracked here as
a pointer for a follow-up issue; not designed or fixed in this pass.

## 4. Verification

### Performed (shape/lint only -- see the gap noted below)

- `for d in skills/*/; do python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py "$d"; done`
  -- all 17 pass, including the four newly-`Portable` skills.
- `uv run --with pytest python3 -m pytest tests/test_repository_skill_shape.py -q`
  -- 17 passed.
- `uv run --with pytest python3 -m pytest skills/evaluating-skill-quality/scripts/test_check_skill_shape.py -q`
  -- 103 passed.
- `LC_ALL=C grep -nP '[^ -~\t]' <file>` on every file touched by this change
  -- no new non-ASCII characters introduced (a small number of pre-existing
  em dashes in untouched lines of `issue-to-branch/SKILL.md` and
  `references/github-issue-workflow.md` were left as-is; fixing them is
  unrelated to this change's scope).
- Read every rewritten `SKILL.md`/reference file back to confirm no
  behavior was lost -- only the framing/fallback wording changed, plus the
  two worked-example issue-number citations wrapped in inline code spans.

### Not performed -- disclosed gap, per CLAUDE.md section 1

All of the above is shape/lint verification (type-check-equivalent for
prose): it proves the rewritten text parses, declares its enum correctly,
and contains no bare citation the scanner catches. It does **not** prove
the actual behavioral claim this whole change rests on -- that a model,
executing one of these four skills inside a foreign repository whose
convention differs from gitapex's, actually follows the stated fallback
instead of defaulting to gitapex's own convention. That is a live-proof
question CLAUDE.md section 1 says a green lint/shape check must not stand
in for.

A real check exists and was not run: all four skills already have a
committed eval suite under `evals/<skill-name>/` with a `copilot-sdk`
executor (three of the four had a live `waza run` recorded on 2026-07-17,
per `docs/skill-eval-status.md`), but (a) `waza` is not installed in this
environment (`waza: command not found`), so no suite could be run at all
in this pass, and (b) none of the existing fixtures test this specific
new claim (a foreign-repo scenario whose documented convention diverges
from gitapex's, checking whether the model defers to the skill's inline
fallback) -- that fixture does not exist yet either. Both are named here
explicitly rather than left implicit, per CLAUDE.md section 1's "when the
environment cannot run the check, say so in the plan up front."

## 5. Open items carried forward

- File a separate issue for the hooks-distribution finding above once this
  change lands -- not filed yet, since this spec's scope is skills only.
- Add a fallback-divergence fixture to each of the four skills' eval
  suites (does the model defer to the inline fallback in a foreign-repo
  scenario, or default to gitapex's convention), and run it with `waza`
  once available, before treating the Portable reclassification's
  behavioral claim as proven rather than shape-checked.

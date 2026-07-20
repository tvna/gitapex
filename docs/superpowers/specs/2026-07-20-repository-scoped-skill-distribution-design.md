# Repository-scoped skills must not ship in the distributed plugin

**Date:** 2026-07-20
**Status:** Design, awaiting review (proposal only -- no code/manifest changes
in this pass)
**Scope:** Enumerate which of gitapex's 17 skills are unsafe to redistribute
as-is, and propose a redesign that keeps them usable for gitapex's own
development without shipping them to consumers of the `gitapex` plugin.
Issue: #222.

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

That taxonomy is checked today only for **honest disclosure**:
`skills/evaluating-skill-quality/scripts/check_skill_shape.py` (gated in CI
by `tests/test_repository_skill_shape.py`) fails a skill that behaves as
Repository-scoped but does not declare it. Nothing reads the declaration to
decide what actually gets **distributed**. A skill can be perfectly honest
about depending on gitapex's own conventions and still be installed, as-is,
into an unrelated repository.

## 2. Enumeration of targets

All 17 `skills/*/metadata/gitapex.yaml` sidecars were read directly to
produce this table (2026-07-20).

### 2a. Repository-scoped (4) -- the actual redistribution risk

| Skill | What in it depends on gitapex specifically |
|---|---|
| `issue-to-branch` | `references/github-issue-workflow.md`'s write-path rules (tracking-issue-before-branch, connector-first, no-CLI-fallback) are, per the skill's own "Notes" section, "this repository's own git-ecosystem convention." |
| `outward-artifact-preflight` | Check 1's "agreed disclosure convention" and the `explaining-the-work` coupling name gitapex's own provenance/ASCII policy; the skill's own header says so ("substitute the calling repository's actual policy... where they differ"). |
| `responding-to-a-fresh-arrival` | Step 3 (Label) reads `.github/ISSUE_TEMPLATE/*.yml` -- this repository's own label source, named as such in the skill's header. |
| `screening-a-low-trust-contribution` | Checks 1-3 hardcode this repo's own paths (`.github/workflows/**`, `hooks/**`, `skills/*/scripts/**`, gitapex's own dependency manifests), again named as such in the skill's header. |

Each of these four already states, in its own SKILL.md, that the named part
is "this repository's own" and that a consumer should "substitute the
calling repository's actual convention" -- but that is prose inside the
distributed file, not something enforced before the file reaches the
consumer. A foreign install either silently misapplies gitapex's own rules,
or relies on the installing agent noticing and rewriting the skill by hand.

### 2b. Mixed (4) -- already isolate the repo-specific part, no structural change proposed

| Skill | Repo-specific part (already isolated to one clause/citation) |
|---|---|
| `battle-testing-a-skill` | One "For readers working in this repository (gitapex)" clause in the metadata sidecar's `references`, plus a gitapex issue-number citation (#74) inside `references/adversarial-dimensions.md`. |
| `explaining-the-work` | "this repository's own" commit-trailer convention, named inline, two spots in `SKILL.md`. |
| `git-hosting-surface-audit` | Cites gitapex's own CLI-governance issue #82 as a cross-link example. |
| `seeding-issue-pr-templates` | Names gitapex's own `issue-to-branch` convention as one worked example among general steps. |

These four were reviewed as part of this pass and found lower-risk: the
repo-specific detail is a citation or a single named clause the skill's
procedure does not depend on to run, matching the "Mixed" definition's intent
that a portable core is what a consumer actually uses. No relocation is
proposed for these; flagging them here as reviewed, not overlooked.

### 2c. Portable (9) -- unaffected

`driving-pr-to-merge`, `establishing-ubiquitous-language`,
`evaluating-skill-quality`, `issue-to-fix`, `merge-retrospective`,
`ranking-the-open-queue`, `scorer-gated-skill-edits`, `stop-and-replan`,
`untrusted-input-triage`. No repo-specific dependency found in any of these
sidecars or bodies.

### 2d. The distribution manifest itself

- `.claude-plugin/plugin.json` has no `skills` field -- Claude Code defaults
  to auto-discovering every subdirectory of `skills/` (confirmed against
  `code.claude.com/docs/en/plugins-reference.md`, "Plugin manifest schema").
- `.claude-plugin/marketplace.json`'s one plugin entry has `"source": "./"`.
- No CI workflow (`lint.yml`, `test.yml`, `toolchain-nix.yml`,
  `waza-check.yml`, `waza-eval-matrix.yml`) filters `skills/` contents before
  a consumer would fetch them; `tests/test_repository_skill_shape.py` only
  runs the shape/honesty checker over every `skills/*/`.

### 2e. Adjacent finding, explicitly out of scope here

`hooks/hooks.json` already wires `hooks/check-bash-safety.sh` and
`hooks/check-template-overwrite.sh` via `$CLAUDE_PLUGIN_ROOT` -- hooks are
already distributed today, which `docs/repository-layout.md`'s "(and, later,
hooks)" phrasing does not reflect. `check-bash-safety.sh` and the
Repository-scoped screening skills both reference this repo's own paths and
conventions -- the same redistribution-risk class as this spec, but a
different artifact type (a hook script, not a skill folder) with its own
manifest surface (`hooks.json`, not `plugin.json`'s `skills` field). Tracked
here as a pointer for a follow-up issue; not designed or fixed in this pass.

## 3. Proposed redesign

### 3a. Mechanism (confirmed against Claude Code's own docs, not assumed)

Two independently documented Claude Code mechanisms make this a
relocation-plus-allowlist change, not a rewrite of any skill's content:

1. **Marketplace-root `skills` allowlist replaces, rather than adds to, the
   default scan.** Per `code.claude.com/docs/en/plugin-marketplaces.md`
   ("Advanced plugin entries"): when a marketplace plugin entry's `source`
   resolves to the marketplace root -- gitapex's `"source": "./"` qualifies
   exactly, per that same section's own example -- explicitly listing
   specific `skills/<name>` subdirectories in `plugin.json`'s `skills` field
   makes that list the *complete* set for the entry; every other directory
   under the shared `skills/` folder stops loading for that plugin's
   consumers. (Listing `./skills/` itself, or the plugin root, keeps the full
   scan -- the allowlist must name specific children.)
2. **Project-local skills are a separate, doc-supported loading path.** Per
   `code.claude.com/docs/en/skills.md` ("Where skills live"), Claude Code
   independently auto-discovers skills from `.claude/skills/<name>/SKILL.md`,
   walked up from the working directory to the repository root -- with no
   plugin/marketplace install step at all, and unnamespaced (`/skill-name`
   rather than `/gitapex:skill-name`). This is exactly the mechanism gitapex
   needs to keep the four Repository-scoped skills firing for anyone working
   directly in its own tree.

### 3b. The change

1. Relocate the four Repository-scoped skill directories --
   `issue-to-branch/`, `outward-artifact-preflight/`,
   `responding-to-a-fresh-arrival/`, `screening-a-low-trust-contribution/` --
   from `skills/<name>/` to `.claude/skills/<name>/`, unchanged internally
   (`SKILL.md`, `metadata/gitapex.yaml`, `references/`, `scripts/` as
   applicable move as a unit; no content rewrite).
2. Add to `.claude-plugin/plugin.json`:
   ```json
   "skills": [
     "skills/battle-testing-a-skill",
     "skills/driving-pr-to-merge",
     "skills/establishing-ubiquitous-language",
     "skills/evaluating-skill-quality",
     "skills/explaining-the-work",
     "skills/git-hosting-surface-audit",
     "skills/issue-to-fix",
     "skills/merge-retrospective",
     "skills/ranking-the-open-queue",
     "skills/scorer-gated-skill-edits",
     "skills/seeding-issue-pr-templates",
     "skills/stop-and-replan",
     "skills/untrusted-input-triage"
   ]
   ```
   (the 9 Portable + 4 Mixed directories from 2b/2c -- 13 entries). Per 3a.1
   this becomes the complete distributed set; the four relocated directories,
   no longer present under `skills/`, cannot be picked up even accidentally.
3. Update `docs/repository-layout.md`: document the two-tier split
   (`skills/` = plugin-distributed, allowlisted in `plugin.json`;
   `.claude/skills/` = project-local, gitapex-development-only, never
   installed by consumers) and correct the "(and, later, hooks)" phrasing
   given 2e's finding that hooks are already live.
4. Update `docs/versioning.md`'s **plugin** product row: scope is the
   allowlisted subset of `skills/`, not "all of `skills/`."
5. Extend `tests/test_repository_skill_shape.py`'s `SKILL_DIRS` collection to
   also glob `.claude/skills/*` (in addition to the existing `skills/*`), so
   the four relocated skills keep the same shape/honesty gate they have
   today -- moving a skill out of the distributed tree is not a reason to
   stop checking it.

### 3c. Non-goals (explicitly deferred, not part of this proposal)

- No content change to the four Mixed skills (2b) -- their repo-specific
  detail is already appropriately isolated.
- No fix for the hooks-distribution finding (2e) -- separate follow-up issue.
- No new CI gate that keeps `plugin.json`'s allowlist in sync with
  `skills/`'s actual contents if a future skill is added or renamed (a
  plausible next gate, matching this repo's own "push deterministic work into
  hooks/CI" convention, but not built here -- noted as a future idea only).
- No version bump automation change; `docs/versioning.md`'s manual-bump
  process is untouched.

## 4. Verification (for the follow-up implementation PR, not this pass)

- `python3 -m json.tool .claude-plugin/plugin.json` parses cleanly and the
  `skills` array has exactly 13 entries, all resolving to real directories.
- `find skills -mindepth 1 -maxdepth 1 -type d | wc -l` reports 13 (down from
  17), and `find .claude/skills -mindepth 1 -maxdepth 1 -type d | wc -l`
  reports 4.
- `cd tests && python3 -m pytest test_repository_skill_shape.py -q` passes
  for all 17 skills across both roots.
- Manual dry run: a hypothetical consumer repo installing `gitapex` via
  `/plugin marketplace add` would, per the confirmed marketplace-root
  allowlist behavior, receive only the 13 listed skills.

## 5. Open items carried forward

- File a separate issue for 2e (hooks-distribution scope) once this proposal
  is reviewed -- not filed yet, since this spec's scope is skills only.
- The future CI gate mentioned in 3c (keep the allowlist in sync with
  `skills/`'s actual contents) is not scheduled; revisit if the allowlist
  drifts in practice.

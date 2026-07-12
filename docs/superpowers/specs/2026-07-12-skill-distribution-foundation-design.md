# Skill distribution foundation for gitapex

Date: 2026-07-12

## Context

gitapex is a brand-new repository (one initial commit plus a CI workflow that
syncs `AGENTS.md`/`CLAUDE.md` from `tvna/claude-md`). It has no
`.claude/skills/`, no `apm.yml`, and no GitHub issues yet. The owner wants
gitapex to become a distributable skills collection, using the same
distribution shape as `tvna/clairvoyance` (a Claude Code / Codex plugin
installable via `apm install` or `/plugin marketplace add`), and separately
plans to grow gitapex into a single Rust CLI binary (currently Python
tooling) once its CLAUDE.md has matured enough to drive that rewrite.

This spec covers only the **distribution foundation** — the repository
layout, plugin manifests, and versioning policy needed for gitapex to work as
a plugin today — seeded with one real skill (`explaining-the-work`) to prove
the layout works end to end.

Reference: `tvna/clairvoyance` (`docs/repository-layout.md`,
`docs/skills.md`, `docs/versioning.md`), cloned locally at
`/Users/tvna/Documents/GitOps/clairvoyance`.

## Scope

- Plugin manifests: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.
- One skill: `skills/explaining-the-work/SKILL.md`.
- `docs/repository-layout.md` — deploy vs. non-deploy split.
- `docs/versioning.md` — product-scoped versioning policy, three axes:
  `plugin`, `cli`, `compose`.

## Non-goals (deferred to future issues)

- `hooks/` (SessionStart hooks and any other runtime hook).
- `evals/` (waza eval suites per skill) and any `scripts/check_skills.py`-style
  deterministic quality gate.
- `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`
  (multi-agent manifests) — Claude Code only for this pass.
- `managed/`-style server/UI/compose product folders (the CLAUDE.md §5
  material) — not built until those products exist.
- Any release automation: `release.config.cjs`, `apply_version.mjs`,
  `.github/workflows/release.yml`, CI version-drift gates, baseline release
  tags, `RELEASE_TOKEN`. The versioning policy below is documentation only;
  version files are bumped by hand until automation is worth building.
- Vendoring `clairvoyance`'s `issue-to-branch` skill (tracked separately in
  the Design-by-Contract issue/PR flow handoff) and the `explaining-the-work`
  GitHub issue filing (tracked separately in the issue-filing handoff) — both
  are out of scope here; this spec only adds the skill's content directly to
  prove the distribution layout.

## Architecture

gitapex is the plugin root itself (`source: "./"`), matching clairvoyance's
rationale: apm and Claude Code discover `skills/` (and later `hooks/`) at the
package root, so nesting under a `plugin/` subdirectory would put skills
outside the search path.

```
.claude-plugin/
  plugin.json           # name, version, description, author, repo, license
  marketplace.json        # marketplace manifest, source: "./"
skills/
  explaining-the-work/
    SKILL.md
docs/
  repository-layout.md    # what's deployed vs. not
  versioning.md            # product-scoped versioning policy
scripts/ tests/            # existing CI tooling (sync_pr_publish.py) — untouched, unrelated
```

## Components

### `.claude-plugin/plugin.json`

```json
{
  "name": "gitapex",
  "description": "A distributable skills collection for gitapex.",
  "version": "0.1.0",
  "author": { "name": "tvna" },
  "homepage": "https://github.com/tvna/gitapex",
  "repository": "https://github.com/tvna/gitapex",
  "license": "MIT"
}
```

### `.claude-plugin/marketplace.json`

```json
{
  "name": "gitapex",
  "description": "Marketplace for the gitapex plugin.",
  "owner": { "name": "tvna" },
  "plugins": [
    {
      "name": "gitapex",
      "description": "A distributable skills collection for gitapex.",
      "source": "./",
      "author": { "name": "tvna" }
    }
  ]
}
```

No `version` field in `marketplace.json` — Claude Code resolves the version
from `plugin.json` and warns against duplicating it, matching clairvoyance's
convention.

### `docs/repository-layout.md`

Short doc (clairvoyance's is ~35 lines) stating: only `skills/` (and later
`hooks/`) are deployed as runtime primitives; `docs/`, `scripts/`, `tests/`,
`.github/` are carried for development but never deployed. Explains why the
plugin sits at repo root rather than a `plugin/` subdirectory.

### `docs/versioning.md`

Product-scoped SemVer policy, three axes:

| Product | Scope | Tag format | Version file | Status |
|---|---|---|---|---|
| **plugin** | `skills/`, `.claude-plugin/plugin.json` | `plugin-vX.Y.Z` | `.claude-plugin/plugin.json` | Live now |
| **cli** | The future gitapex single-binary CLI (currently Python tooling under `scripts/`, planned Rust rewrite) | `cli-vX.Y.Z` | TBD when the CLI product exists | Reserved |
| **compose** | Future deployment/dev topology (e.g. docker-compose) | `compose-vX.Y.Z` | TBD when compose assets exist | Reserved |

Policy text to include:
- Why product-scoped: a single repo-wide version would make a plugin-only fix
  look like it released the CLI, and vice versa (same rationale as
  clairvoyance).
- All axes start in `0.x` (initial development); `1.0.0` is reserved for the
  first release a product is willing to guarantee as stable, per
  [SemVer §4](https://semver.org/#spec-item-4).
- Only the **plugin** row is real today. **cli** and **compose** are named
  and reserved so future work lands on an already-agreed axis instead of
  re-litigating the model, but they have no version file or automation until
  the corresponding product exists. Axes beyond these three (e.g. a
  server/UI split) are added the same way, only when needed — not
  speculatively.
- Commit convention carries product intent in scope: `feat(plugin): ...`,
  `fix(plugin): ...`, mirroring clairvoyance so the convention is ready if
  automation is added later.
- Trunk-based development: `main` is always releasable; no long-lived
  `develop`/`release` branches.
- No automation yet: `plugin.json`'s `version` is bumped by hand. A future
  issue can introduce semantic-release-style automation once the manual
  process becomes a bottleneck.

## Skill content: `explaining-the-work`

`skills/explaining-the-work/SKILL.md`, frontmatter:

```yaml
---
name: explaining-the-work
description: Use when writing or editing code comments, docstrings, or finalizing commit/PR messages. Routes explanation responsibility (How/What/Why/Why-not) to the right artifact instead of piling it into comments.
---
```

Body — the fixed routing policy, transcribed from the design brief:

- Code body -> **How** only (naming/structure). Never restate what the code
  already says.
- Test code -> **What**, expressed through the test name. A docstring is used
  only when the test name itself cannot carry an issue reference.
- Commit log -> not the place for Why. The real Why lives in the issue/PR
  body (Facts/Speculation split). A commit is one line + `Refs #N` pointer,
  nothing more.
- Code comments -> **Why-not** / durable-constraint only, one-line form:
  `# why-not(#NNN): <=120 chars [-> docs/adr/NNNN-*.md]`. Requires a citable
  issue/PR/ADR that actually evaluated the rejected alternative — if it can't
  be cited, don't write the comment (no fabrication).
- The calling repository's existing deterministic gates (`Contract:` blocks,
  allowlist justification comments, `noqa` justification, etc.) take
  precedence; this skill does not enumerate exceptions to them.
- Forward-apply only. Never bulk-rewrite existing comments. Deletion is
  justified only by the guarded code actually having been removed, never by
  staleness alone.
- Never auto-generate an ADR from a threshold. ADRs are heavyweight,
  owner-approved records; machine-generating them from CI produces
  "drive-by ADRs".

No `references/` subdirectory — the content fits well within the informal
500-token `SKILL.md` budget clairvoyance uses.

## Verification

No runtime code is added, so there is no pytest suite for this change.
Verification is manual/structural:

- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` parse as
  valid JSON (`python3 -m json.tool` or equivalent) and `plugin.json`'s
  `name`/`version` match what `docs/versioning.md` documents as current.
- `marketplace.json` has no `version` key.
- `SKILL.md` frontmatter matches clairvoyance's conventions: kebab-case
  `name` equal to the directory name, single-line third-person `description`
  containing a "Use when..." trigger, no XML tags.
- Manual dry run: given a hypothetical PR touching a comment, a commit
  message, and a test, confirm each is routed to the correct artifact per the
  table above.

## Open items carried forward (not blocking this spec)

- Filing the `explaining-the-work` GitHub issue (per
  `handoffgitapexissuefiling.md`) is a separate, optional follow-up now that
  the skill content already exists in-repo; it is not required to land this
  change.
- The Design-by-Contract issue/PR flow (tracking issue + 5 children, per
  `gitapexissuehandoff.html` / `dbchandoff.html`), including vendoring
  clairvoyance's `issue-to-branch` skill, remains a separate initiative.

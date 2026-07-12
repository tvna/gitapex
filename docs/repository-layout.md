# Repository layout

gitapex is a Claude Code / Codex plugin. The plugin lives at the
**repository root** (`source: "./"` in `.claude-plugin/marketplace.json`),
the layout apm requires: it discovers and deploys skills from `skills/`
(and, in the future, hooks from `hooks/`) at the package root, so those
directories sit at the top level rather than inside a `plugin/`
subdirectory.

Only **skills** (and, later, hooks) are deployed as runtime primitives;
everything else — contributor instructions (`AGENTS.md`/`CLAUDE.md`,
synced from `tvna/claude-md`), CI tooling, tests, and docs — is carried in
the repository for development but is never deployed into a consumer's
agent.

```
.claude-plugin/    marketplace.json + plugin.json (Claude Code/Codex manifests; plugin.json is the version source of truth)
skills/            one directory per skill (SKILL.md, optionally references/) — deployed by apm/Claude/Codex
docs/              documentation (this file, versioning policy, design specs) — not deployed
scripts/ tests/    internal CI tooling (e.g. sync_pr_publish.py) and its pytest suite — not deployed
.github/           CI workflows — not deployed
```

> **Why the root, not a `plugin/` subdirectory?** apm installs a dependency
> like `tvna/gitapex` by fetching the whole repository and discovering
> skills at the package root (`skills/<name>/SKILL.md`). A nested
> `plugin/skills/` is not on that search path, so apm would deploy nothing.
> This mirrors `tvna/clairvoyance`'s layout, which in turn follows
> [`obra/superpowers`](https://github.com/obra/superpowers).

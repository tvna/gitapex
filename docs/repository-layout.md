# Repository layout

gitapex is a Claude Code / Codex plugin. This is one of four distinct
"which agent products does GitApex support" questions this repository
answers differently; see
[`agent-product-scope.md`](agent-product-scope.md) (Axis A) for the
full breakdown against the enforcement-adapter target set, the
skill-quality-review evidence baseline, and the proposed hook-quality
evidence baseline. The plugin lives at the
**repository root** (`source: "./"` in `.claude-plugin/marketplace.json`),
the layout apm requires: it discovers and deploys skills from `skills/`
(and, in the future, hooks from `hooks/`) at the package root, so those
directories sit at the top level rather than inside a `plugin/`
subdirectory.

Only **skills** (and, later, hooks) are deployed as runtime primitives;
everything else — contributor instructions (`AGENTS.md`/`CLAUDE.md`,
owned and edited directly by gitapex), CI tooling, tests, and docs — is
carried in the repository for development but is never deployed into a
consumer's agent.

```
plugin.json        Agent Plugins Specification (agent-plugins.org) v1.0.0 manifest — the plugin-identity source of truth (name, version, description, author, homepage, repository, license); .claude-plugin/plugin.json below is generated from it, never hand-edited
.claude-plugin/    marketplace.json + plugin.json (Claude Code/Codex manifests; plugin.json here is an auto-generated mirror of the repository-root plugin.json above — see gitapex_generate_plugin_manifest.py)
skills/            one directory per skill (SKILL.md, metadata/gitapex.yaml, optionally references/) — deployed by apm/Claude/Codex
  planning-a-branch-from-an-issue/  turns a GitHub issue into an implementation-ready branch/PR plan with an Acceptance Criteria Map
  drafting-issues/  drafts a new GitHub issue with an Acceptance Criteria Map before creation, so planning-a-branch-from-an-issue can read one instead of building it
docs/              documentation (this file, versioning policy, design specs, motivation.md) — not deployed
tests/             pytest suite for the internal CI tooling — not deployed
.github/           CI workflows and their internal tooling (.github/scripts/gitapex_gate_local_preflight.py) — not deployed
```

> **Why the root, not a `plugin/` subdirectory?** apm installs a dependency
> like `tvna/gitapex` by fetching the whole repository and discovering
> skills at the package root (`skills/<name>/SKILL.md`). A nested
> `plugin/skills/` is not on that search path, so apm would deploy nothing.
> This mirrors `tvna/clairvoyance`'s layout, which in turn follows
> [`obra/superpowers`](https://github.com/obra/superpowers).

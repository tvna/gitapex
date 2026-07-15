# Versioning

## Policy

gitapex is planned as a multi-product repository, so it uses
**product-scoped** [Semantic Versioning](https://semver.org/): each
deployable artifact has its own version line and tag namespace. A single
repo-wide version would make it unclear whether a plugin-only change or a
CLI-only change actually shipped.

| Product | Scope | Tag format | Version file | Status |
|---|---|---|---|---|
| **plugin** | `skills/`, `.claude-plugin/plugin.json` | `plugin-vX.Y.Z` | `.claude-plugin/plugin.json` | Live now (`0.1.0`) |
| **cli** | The future gitapex single-binary CLI: SSOT config (`.gitapex/ssot.json`) plus a modular policy-engine-driven governance/gate-control layer for business-domain changes (OPA/Rego is the named candidate mechanism), including git/GitHub middleware and SaaS-integration operations -- the originally-scoped approved read-only gh wrapper is one governed-operation instance within this, not the whole product (see `docs/superpowers/specs/2026-07-15-gitapex-cli-governance-design.md` and tracking issue #82). Currently Python tooling under `.github/scripts/`; provisional Rust rewrite (Go acceptable later if warranted, not decided now) once CLAUDE.md has matured | `cli-vX.Y.Z` | To be decided when the CLI product exists | Reserved — no version file yet |
| **compose** | Future deployment/dev topology (e.g. docker-compose) | `compose-vX.Y.Z` | To be decided when compose assets exist | Reserved — no version file yet |

Only the **plugin** row is real today. **cli** and **compose** are named and
reserved so future work lands on an already-agreed axis instead of
re-litigating the model, but neither has a version file or automation until
its product exists. Additional axes (e.g. a server/UI split) are added the
same way, only when needed — not speculatively.

All axes start in the `0.x` range (initial development). `1.0.0` is
reserved for the first release a product is willing to guarantee as a
stable surface, per [SemVer §4](https://semver.org/#spec-item-4).

## Commit convention

Commits carry product intent in the scope, so a future release process (if
built) can tell which product to release:

```
feat(plugin): ...   fix(plugin): ...   docs(plugin): ...
feat(cli): ...       fix(cli): ...       docs(cli): ...
feat(compose): ...   fix(compose): ...   docs(compose): ...
```

## Branch strategy

Development is trunk-based: `main` is the trunk and is always releasable.
Work lands through short-lived branches and reviewed PRs. There are no
long-lived `develop`/`release` branches.

## No automation yet

Unlike `tvna/clairvoyance`, this repository does not (yet) run
semantic-release, version-drift CI gates, or scheduled release workflows.
`plugin.json`'s `version` is bumped by hand. A future issue can introduce
that automation once the manual process becomes a bottleneck, or once the
`cli`/`compose` products exist and need it too.

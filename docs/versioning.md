# Versioning

## Policy

gitapex is planned as a multi-product repository, so it uses
**product-scoped** [Semantic Versioning](https://semver.org/): each
deployable artifact has its own version line and tag namespace. A single
repo-wide version would make it unclear whether a plugin-only change or a
CLI-only change actually shipped.

| Product | Scope | Tag format | Version file | Status |
|---|---|---|---|---|
| **plugin** | `skills/`, `.claude-plugin/plugin.json` | `gitapex--vX.Y.Z` | `.claude-plugin/plugin.json` | Live now (`0.1.0`) |
| **cli** | The future gitapex single-binary CLI: SSOT config (`.gitapex/ssot.json`) plus a modular policy-engine-driven governance/gate-control layer for business-domain changes (embedded Rego via `regorus`, per issue #125's decided design), including git/GitHub middleware and SaaS-integration operations -- the originally-scoped approved read-only gh wrapper is one governed-operation instance within this, not the whole product (see `docs/superpowers/specs/2026-07-15-gitapex-cli-governance-design.md` and tracking issue #82). Currently Python tooling under `.github/scripts/`; **Rust, decided 2026-07-18** (see `docs/superpowers/specs/2026-07-16-business-domain-policy-engine-tradeoff.md`'s Rust-vs-Go decision brief), conditional on the `regorus` conformance fixture-suite (#125) passing -- revisit to Go only if that tripwire fires, while the switch is still a design edit, not a code rewrite | `N/A — out of scope for this repo` | To be decided when the CLI product exists | Out of scope for gitapex — moves to a future, separate forked repository when built |
| **compose** | Future deployment/dev topology (e.g. docker-compose) | `N/A — out of scope for this repo` | To be decided when compose assets exist | Out of scope for gitapex — moves to a future, separate forked repository when built |

gitapex remains a skills/plugin-only repository going forward: a future
CLI or any other non-plugin product need is built in a separate, forked
repository rather than inside gitapex. Only the **plugin** row above is
real, and it is the only axis this repository's own release automation
(see [Automation](#automation) below) ever targets.

All axes start in the `0.x` range (initial development). `1.0.0` is
reserved for the first release a product is willing to guarantee as a
stable surface, per [SemVer §4](https://semver.org/#spec-item-4).

## Commit convention

Commits carry product intent in the scope, so a future release process (if
built) can tell which product to release:

```
feat(plugin): ...   fix(plugin): ...   docs(plugin): ...   refactor(plugin): ...
feat(cli): ...       fix(cli): ...       docs(cli): ...       refactor(cli): ...
feat(compose): ...   fix(compose): ...   docs(compose): ...   refactor(compose): ...
```

`refactor(...)` carries no version-bump semantics of its own (SemVer-wise
it is a patch at most) but is a required, deterministic signal for
issue #138's `gate-refactor-net-growth` gate design: only a PR titled
`refactor(scope): ...` triggers the net-line-growth-justification check;
`feat`/`fix`/`docs` PRs are exempt since growth is expected on them.

## Branch strategy

Development is trunk-based: `main` is the trunk and is always releasable.
Work lands through short-lived branches and reviewed PRs. There are no
long-lived `develop`/`release` branches.

## Automation

Three pieces now implement release automation for the **plugin** product:

- **`.github/scripts/compute_release_bump.py`** — computes the next
  version and writes it into both `.claude-plugin/plugin.json` and
  `apm.yml`.
- **`.github/workflows/release-pr.yml`** — a scheduled workflow that
  proposes a version-bump + release-notes pull request. Merging that PR
  is the release act.
- **`.github/workflows/release-tag.yml`** — on merge, creates the
  `gitapex--vX.Y.Z` git tag and a GitHub Release.

### Bump rule

- A `feat(plugin)` commit, or any `plugin`-scoped commit marked breaking
  (regardless of its type), bumps the **minor** version.
- A non-breaking `fix(plugin)`, `refactor(plugin)`, or `perf(plugin)`
  commit bumps the **patch** version.
- A non-breaking `docs(plugin)`, `chore(plugin)`, `test(plugin)`,
  `build(plugin)`, or `ci(plugin)` commit, and any commit scoped to
  anything other than `plugin`, trigger **no bump**.

**The major version is never bumped automatically.** Reaching `1.0.0` (or
any future major version) is always a deliberate, manual edit to
`.claude-plugin/plugin.json` — per the Policy section above, `1.0.0` is
reserved for the first release a product is willing to guarantee as a
stable surface ([SemVer §4](https://semver.org/#spec-item-4)).

### Release bootstrap

No retroactive tag was created for the untagged `0.1.0` history: the
plugin manifest has carried `version: "0.1.0"` since 2026-07-21, but no
tag or GitHub Release has ever existed in this repository. The first
tag/release this mechanism produces is whatever version it computes next,
on a fresh commit; changelog/release-notes coverage begins at that first
tagged release, and commits before it are out of changelog scope.

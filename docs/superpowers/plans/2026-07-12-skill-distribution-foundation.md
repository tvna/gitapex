# Skill Distribution Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make gitapex installable as a Claude Code / Codex plugin, matching `tvna/clairvoyance`'s distribution shape, seeded with one real skill (`explaining-the-work`).

**Architecture:** gitapex becomes the plugin root itself (`source: "./"`). Two JSON manifests under `.claude-plugin/` declare the plugin and its marketplace entry; one skill directory under `skills/` holds the actual skill content; two docs under `docs/` record what's deployed vs. not, and the product-scoped versioning policy. No runtime code, no build step — every deliverable is a static file whose correctness is checked by `python3 -m json.tool` (JSON) or `grep` (required content in Markdown).

**Tech Stack:** Plain JSON + Markdown. No new dependencies; the repo's existing `scripts/`/`tests/` Python project (`gitapex-scripts`, pytest) is untouched.

## Global Constraints

- Plugin lives at repo root (`source: "./"`) — do not nest under a `plugin/` subdirectory (per spec's Architecture section, this is required for apm/Claude Code discovery).
- `marketplace.json` must NOT contain a `version` key (Claude Code resolves version from `plugin.json` only; duplicating it is a documented anti-pattern in clairvoyance).
- `plugin.json` `version` starts at `"0.1.0"` and is bumped by hand (no release automation in this pass).
- Versioning axes are exactly three: `plugin`, `cli`, `compose`. Only `plugin` gets a real version file in this pass; `cli` and `compose` are named/reserved only.
- `skills/explaining-the-work/SKILL.md` frontmatter: `name: explaining-the-work` (kebab-case, matches directory name), single-line third-person `description` containing a "Use when..." trigger, no XML tags in the description.
- No `references/` subdirectory for this skill — content must fit in `SKILL.md` alone.
- Do not touch `scripts/`, `tests/`, `pyproject.toml`, or any existing file — this plan only adds new files.

---

### Task 1: Plugin manifests

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`

**Interfaces:**
- Produces: the plugin's canonical version string, `"0.1.0"`, which Task 3 (`docs/versioning.md`) must quote verbatim as the current plugin version.

- [ ] **Step 1: Create the `.claude-plugin` directory and `plugin.json`**

```bash
mkdir -p .claude-plugin
```

Write `.claude-plugin/plugin.json`:

```json
{
  "name": "gitapex",
  "description": "A distributable skills collection for gitapex.",
  "version": "0.1.0",
  "author": {
    "name": "tvna"
  },
  "homepage": "https://github.com/tvna/gitapex",
  "repository": "https://github.com/tvna/gitapex",
  "license": "MIT"
}
```

- [ ] **Step 2: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "gitapex",
  "description": "Marketplace for the gitapex plugin.",
  "owner": {
    "name": "tvna"
  },
  "plugins": [
    {
      "name": "gitapex",
      "description": "A distributable skills collection for gitapex.",
      "source": "./",
      "author": {
        "name": "tvna"
      }
    }
  ]
}
```

- [ ] **Step 3: Verify both files are valid JSON and `marketplace.json` has no `version` key**

Run:

```bash
python3 -m json.tool .claude-plugin/plugin.json > /dev/null && echo "plugin.json OK"
python3 -m json.tool .claude-plugin/marketplace.json > /dev/null && echo "marketplace.json OK"
python3 -c "import json,sys; d=json.load(open('.claude-plugin/marketplace.json')); sys.exit(1 if 'version' in d else 0)" && echo "marketplace.json has no version key: OK"
```

Expected output:

```
plugin.json OK
marketplace.json OK
marketplace.json has no version key: OK
```

- [ ] **Step 4: Verify `plugin.json` name/version match the plan's constants**

Run:

```bash
python3 -c "
import json
d = json.load(open('.claude-plugin/plugin.json'))
assert d['name'] == 'gitapex', d['name']
assert d['version'] == '0.1.0', d['version']
assert d['license'] == 'MIT', d['license']
print('plugin.json fields OK')
"
```

Expected output: `plugin.json fields OK`

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "feat(plugin): add plugin and marketplace manifests"
```

---

### Task 2: `explaining-the-work` skill

**Files:**
- Create: `skills/explaining-the-work/SKILL.md`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: nothing consumed by later tasks (Task 3's `docs/repository-layout.md` references the `skills/` directory generically, not this specific skill).

- [ ] **Step 1: Create the skill directory and `SKILL.md`**

```bash
mkdir -p skills/explaining-the-work
```

Write `skills/explaining-the-work/SKILL.md`:

```markdown
---
name: explaining-the-work
description: Use when writing or editing code comments, docstrings, or finalizing commit/PR messages. Routes explanation responsibility (How/What/Why/Why-not) to the right artifact instead of piling it into comments.
---

# Explaining the Work

Explanation responsibility is split by artifact. Route each piece of
explanation to exactly one place — never duplicate it, never let it drift
into the wrong artifact.

## Routing

- **Code body -> How only** (naming/structure). Never restate what the code
  already says.
- **Test code -> What**, expressed through the test name. Use a docstring
  only when the test name itself cannot carry an issue reference.
- **Commit log -> not the place for Why.** The real Why lives in the
  issue/PR body (Facts/Speculation split). A commit is one line plus a
  `Refs #N` pointer — nothing more.
- **Code comments -> Why-not / durable constraints only**, one-line form:

  ```
  # why-not(#NNN): <=120 chars [-> docs/adr/NNNN-*.md]
  ```

  Requires a citable issue/PR/ADR that actually evaluated the rejected
  alternative. If nothing can be cited, do not write the comment — never
  fabricate a rationale.

## Precedence

The calling repository's existing deterministic gates (`Contract:` blocks,
allowlist justification comments, `noqa` justification, etc.) take
precedence over this skill. Do not enumerate exceptions to those gates here.

## Stop boundaries

- Forward-apply only. Never bulk-rewrite existing comments to match this
  policy.
- Deletion of a why-not comment is justified only by the guarded code
  actually having been removed — never by staleness alone.
- Never auto-generate an ADR from a threshold or metric. ADRs are
  heavyweight, owner-approved records; machine-generating them produces
  "drive-by ADRs".
```

- [ ] **Step 2: Verify frontmatter is well-formed and the name matches the directory**

Run:

```bash
python3 -c "
import re
text = open('skills/explaining-the-work/SKILL.md').read()
m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
assert m, 'no frontmatter block found'
fm = m.group(1)
assert 'name: explaining-the-work' in fm, fm
assert 'description: Use when' in fm, fm
assert '<' not in fm.split('description:')[1].split(chr(10))[0], 'description contains XML-like tag'
print('SKILL.md frontmatter OK')
"
```

Expected output: `SKILL.md frontmatter OK`

- [ ] **Step 3: Verify the routing rules from the spec are all present**

Run:

```bash
for phrase in "How only" "test name" "Refs #N" "why-not(#NNN)" "Forward-apply only" "auto-generate an ADR"; do
  grep -qF "$phrase" skills/explaining-the-work/SKILL.md && echo "found: $phrase" || { echo "MISSING: $phrase"; exit 1; }
done
```

Expected output: six `found: ...` lines, no `MISSING` line.

- [ ] **Step 4: Commit**

```bash
git add skills/explaining-the-work/SKILL.md
git commit -m "feat(plugin): add explaining-the-work skill"
```

---

### Task 3: Repository layout and versioning docs

**Files:**
- Create: `docs/repository-layout.md`
- Create: `docs/versioning.md`

**Interfaces:**
- Consumes: the plugin version `"0.1.0"` produced in Task 1, quoted verbatim in `docs/versioning.md`'s `plugin` row.

- [ ] **Step 1: Write `docs/repository-layout.md`**

```markdown
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
```

- [ ] **Step 2: Write `docs/versioning.md`**

```markdown
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
| **cli** | The future gitapex single-binary CLI (currently Python tooling under `scripts/`, planned Rust rewrite once CLAUDE.md has matured) | `cli-vX.Y.Z` | To be decided when the CLI product exists | Reserved — no version file yet |
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
```

- [ ] **Step 3: Verify both docs exist and contain the required markers**

Run:

```bash
for phrase in "skills/" "plugin.json" "not deployed"; do
  grep -qF "$phrase" docs/repository-layout.md && echo "layout found: $phrase" || { echo "MISSING in layout: $phrase"; exit 1; }
done
for phrase in "plugin-vX.Y.Z" "cli-vX.Y.Z" "compose-vX.Y.Z" "0.1.0"; do
  grep -qF "$phrase" docs/versioning.md && echo "versioning found: $phrase" || { echo "MISSING in versioning: $phrase"; exit 1; }
done
```

Expected output: seven `found: ...` lines, no `MISSING` line.

- [ ] **Step 4: Verify the plugin version quoted in `docs/versioning.md` matches `plugin.json`**

Run:

```bash
python3 -c "
import json, re
plugin_version = json.load(open('.claude-plugin/plugin.json'))['version']
versioning_doc = open('docs/versioning.md').read()
assert plugin_version in versioning_doc, f'{plugin_version} not found in docs/versioning.md'
print('version parity OK:', plugin_version)
"
```

Expected output: `version parity OK: 0.1.0`

- [ ] **Step 5: Commit**

```bash
git add docs/repository-layout.md docs/versioning.md
git commit -m "docs(plugin): add repository layout and versioning policy"
```

---

## Final check

- [ ] Run the full verification sweep from Tasks 1–3 once more in sequence (all `python3`/`grep` commands above) and confirm every one prints its expected "OK"/"found" output with no `MISSING` lines.
- [ ] Confirm `git log --oneline -5` shows the three commits from this plan on top of `01671e4` (the spec commit).

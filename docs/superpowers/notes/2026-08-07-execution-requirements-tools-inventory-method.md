# `spec.executionRequirements.tools` inventory method (W3 first slice)

Refs https://github.com/tvna/gitapex/issues/814,
https://github.com/tvna/gitapex/issues/307 (parent, workstream W3:
Repository capability inventory). Documents the method used to derive
this batch's four `tools` declarations, so a later batch reuses the same
method instead of re-deriving it, and so a second reviewer can reproduce
the same values independently (issue #814's own proof method for this
criterion).

## Method

For each skill, in order:

1. Read `SKILL.md`'s own Steps/Procedure for any action that reads or
   writes a real filesystem path, or invokes a shell/subprocess call,
   directly as part of the documented procedure (not merely "the invoking
   agent might use its own Read/Write/Bash tools generically" -- only
   where the skill's own text names a concrete file, directory, or
   command).
2. If the skill ships a `scripts/` directory, read every non-test
   `gitapex_*.py` module's own `main()`/CLI surface and its actual code,
   not its docstring's claims alone:
   - `import subprocess` plus a live call site (`subprocess.run(...)`,
     not merely the string `"subprocess"` appearing inside a regex or
     string literal used for unrelated static analysis) -> `shell`.
   - A real `open(..., "w")`/`Path.write_text`/`Path.write_bytes`/
     `mkdir` call -> `write`.
   - A real `open(..., "r")`/`Path.read_text`/`argparse` file-path
     argument that is read -> `read`.
   - `import <non-stdlib-package>` -> would need
     `spec.executionRequirements.packages`; none found in this batch.
3. Cross-check the module's own docstring against step 2's code reading
   -- a docstring claim ("read-only", "no subprocess") is corroborating
   evidence, never a substitute for reading the actual call sites.
4. Declare each of `read`/`write`/`shell` as a list of free-form tags
   (this schema slice defines no fixed vocabulary yet -- see
   `docs/superpowers/specs/2026-07-25-skill-execution-requirements-envelope-design.md`)
   when real usage was found, or an explicit empty list (`[]`, meaning
   prohibited/declared-zero, not "unknown") when none was found for that
   category.
5. Name any real capability the skill needs that the current schema
   cannot express (e.g. network) as a disclosed gap in the sidecar's own
   `spec.references` and the implementing PR body -- never silently
   dropped, and never smuggled into `tools` under an approximate label.

## Worked example: `setup-gitapex-toolchain`

- Step 1: `SKILL.md` describes provisioning `waza`/`apm`/`rtk`/
  `betterleaks` toolchain binaries for an ephemeral session.
- Step 2: `scripts/gitapex_provision_class_b.py` --
  `import subprocess` at module scope, plus a live call site
  (`subprocess.run(...)` at the binary-verification step) -> `shell:
  [subprocess]`. Real write calls (`dest.write_bytes`, `bin_shim.
  write_text`, `mkdir(parents=True, exist_ok=True)`) against a cache
  root -> `write: [files]`. Real reads (`flake.nix`, project files) ->
  `read: [files]`.
- Step 3: the module's own docstring corroborates ("Provision ...
  without Nix"); no read-only claim to check against here since the
  script's purpose is inherently mutating.
- Step 5: `import urllib.request` plus live calls performs real network
  I/O with no `network` category in the current schema to declare it
  under -- disclosed as a gap in the sidecar's own `spec.references`
  (a `deferral` entry) and in this issue/PR, not declared under `tools`
  and not silently omitted.

## Batch 1 (issue #814 / PR #816)

| Skill | `read` | `write` | `shell` | Notable gap |
|---|---|---|---|---|
| `stop-and-replan` | `[]` | `[]` | `[]` | none -- procedure is GitHub-MCP-only, no local filesystem or shell touch at all |
| `drafting-an-adr` | `[files]` | `[files]` | `[]` | none |
| `evaluating-deterministic-gate-quality` | `[files]` | `[]` | `[]` | none -- own docstring and code agree: static `ast`-based analysis, never executes the target |
| `setup-gitapex-toolchain` | `[files]` | `[files]` | `[subprocess]` | real `network` (urllib.request) usage undeclared -- no schema category exists yet (see worked example above) |

## Batch 2 (issue #818): the 9 remaining scripted skills, one shared pattern

All 9 remaining bundled-script skills share one identical, live-verified
pattern: a stdlib-only checker script that reads a target path/`--flag`
file or stdin, writes nothing, and never shells out. Declared identically
rather than traced individually, since the method above (steps 1-3) was
applied to each and produced the same result across all 9 -- see issue
#818's own Facts section for the per-script verification detail.

| Skill | `read` | `write` | `shell` | Notable gap |
|---|---|---|---|---|
| `auditing-agent-product-scope` | `[files]` | `[]` | `[]` | none |
| `auditing-git-hosting-surface` | `[files]` | `[]` | `[]` | none |
| `battle-testing-a-skill` | `[files]` | `[]` | `[]` | none |
| `drafting-an-acm-issue` | `[files]` | `[]` | `[]` | none |
| `evaluating-skill-quality` | `[files]` | `[]` | `[]` | none |
| `executing-a-branch-plan` | `[files]` | `[]` | `[]` | none |
| `outward-artifact-preflight` | `[files]` | `[]` | `[]` | none |
| `planning-a-branch-from-an-issue` | `[files]` | `[]` | `[]` | none |
| `scorer-gated-skill-edits` | `[files]` | `[]` | `[]` | none |

## Batch 3 (issue #823): the 12 remaining non-scripted skills, seven patterns

Unlike Batch 2, these 12 skills carry no bundled `scripts/` directory, so
each declaration traces to concrete text in that skill's own `SKILL.md`
Procedure/Steps/Stop-boundaries -- never a generic "the invoking agent
might use tools" assumption. Three entries (marked `*` below) rest on a
named assumption about which underlying mechanism (local shell vs. a
hosted API) a described action uses, disclosed in issue #823's own
Assumptions section rather than silently picked -- re-verify against the
actual runtime this skill executes under before treating those three as
settled. This batch completes the `tools`-category inventory for every
skill in `skills/`.

| Skill | `read` | `write` | `shell` | Notable gap |
|---|---|---|---|---|
| `merge-retrospective` | `[]` | `[]` | `[]` | none -- GitHub-MCP-only |
| `ranking-the-open-queue` | `[]` | `[]` | `[]` | none -- GitHub-MCP-only, explicitly read-only by its own Stop boundaries |
| `explaining-the-work` | `[]` | `[]` | `[]` | none -- purely advisory, routes to other artifacts/skills, no tool action of its own |
| `untrusted-input-triage` | `[]` | `[]` | `[]` | none -- triages text already supplied in context |
| `responding-to-a-fresh-arrival` | `[files]` | `[]` | `[]` | none |
| `vetting-attack-surface` | `[files]` | `[]` | `[]` | none -- own Stop boundaries explicitly rule out writing and executing |
| `establishing-ubiquitous-language` | `[files]` | `[files]` | `[]` | none |
| `drafting-a-pr-to-merge` | `[files]` | `[files]` | `[git]` * | push mechanism assumed local `git push`; could be API-based in another environment |
| `fixing-a-reported-issue` | `[files]` | `[files]` | `[tests]` | none |
| `evaluating-context-channel-maturity` | `[files]` | `[]` | `[git]` * | commit-history check assumed local `git log`; could be API-based |
| `grounding-in-primary-sources` | `[files]` | `[]` | `[commands]` | real `network` (external docs/changelog fetches) undeclared -- no schema category exists yet, same gap as `setup-gitapex-toolchain` |
| `screening-a-low-trust-contribution` | `[]` | `[]` | `[registry-lookup]` * | registry-lookup mechanism assumed local CLI (`npm view`); could be a hosted registry API call |

## Explicitly out of scope

Per issues #814/#818/#823's own Non-goals: the
`packages`/`filesystem`/`network`/`mcp`/`credentials`/`browser`/
`externalServices`/`context` categories, a fixed `tools` tag vocabulary
(W2), and adapter/enforcement work (W4) or review-guidance/drift-gate
updates (W6/W7). Follow-up work under
https://github.com/tvna/gitapex/issues/307 covers those, once W2's
compatibility matrix and a real tag vocabulary exist to ground them
against.

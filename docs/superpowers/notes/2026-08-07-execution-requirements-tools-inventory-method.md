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

## Batch declared in this issue's PR

| Skill | `read` | `write` | `shell` | Notable gap |
|---|---|---|---|---|
| `stop-and-replan` | `[]` | `[]` | `[]` | none -- procedure is GitHub-MCP-only, no local filesystem or shell touch at all |
| `drafting-an-adr` | `[files]` | `[files]` | `[]` | none |
| `evaluating-deterministic-gate-quality` | `[files]` | `[]` | `[]` | none -- own docstring and code agree: static `ast`-based analysis, never executes the target |
| `setup-gitapex-toolchain` | `[files]` | `[files]` | `[subprocess]` | real `network` (urllib.request) usage undeclared -- no schema category exists yet (see worked example above) |

## Explicitly out of scope for this batch

Per issue #814's own Non-goals: the remaining 20 skill sidecars, the
`packages`/`filesystem`/`network`/`mcp`/`credentials`/`browser`/
`externalServices`/`context` categories, a fixed `tools` tag vocabulary
(W2), and adapter/enforcement work (W4) or review-guidance/drift-gate
updates (W6/W7). Follow-up child issues under
https://github.com/tvna/gitapex/issues/307, batched the same small-group
way, cover the rest.

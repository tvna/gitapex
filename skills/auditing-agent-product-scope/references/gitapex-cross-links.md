# gitapex-specific cross-links

Loaded when this copy of the skill's own files lives in the gitapex
repository -- the same condition, and the same reasoning, as
`auditing-git-hosting-surface/references/gitapex-cross-links.md`'s own
opening note. A copy vendored into a different repository drops this
file and instead uses that repository's own equivalent scope doc,
evidence files, and tracking issues where they exist -- omitting a
cross-link where they don't, never fabricating one.

## Contents

1. [The scope map and its six axes](#the-scope-map-and-its-six-axes)
2. [Evidence-file targets](#evidence-file-targets)
3. [Middleware dependency-declaring files](#middleware-dependency-declaring-files)
4. [Platform-axis handoff target](#platform-axis-handoff-target)
5. [Skill-shape-checker command](#skill-shape-checker-command)

## The scope map and its six axes

gitapex's scope map is `docs/agent-product-scope.md`:

| Axis | Governs |
|---|---|
| A | Plugin-distribution target (which products GitApex is installable into) |
| B | Enforcement-adapter target set (future least-privilege tooling) |
| C | Skill-quality-review evidence baseline |
| D | Hook-quality evidence baseline (proposed, unshipped) |
| E | Git-hosting platform target |
| F | Dependency middleware |

## Evidence-file targets

Not every axis has a writable evidence file today -- SKILL.md Step 2
requires confirming one exists before going further. Per axis:

- **Axis A** (plugin-distribution target): no writable evidence file.
  `docs/repository-layout.md`'s current-scope statement is a single
  claim, not a file this skill's Procedure adds candidate rows to;
  expanding it is the larger Axis-A decision the scope map's own
  Non-goals leave to the repository owner. STOP per Step 2.
- **Axis B** (enforcement-adapter target set): no writable evidence
  file -- its own Owning issue (`docs/agent-product-scope.md`'s Axis B
  section names the current tracking issue; read it there rather than
  duplicating the number here) is future enforcement-adapter
  engineering, not a file this skill writes research findings into.
  STOP per Step 2.
- **Axis C** (skill-quality-review evidence baseline): writable. A
  finding goes to
  `skills/evaluating-skill-quality/references/runtime-compatibility.md`.
  That file's own "Classification uses three evidence states" section
  is the canonical Documented/Unknown/Conflict definition -- read it
  there rather than re-deriving it. This is the only agent-tool axis
  this skill's Procedure currently writes candidate findings into.
- **Axis D** (hook-quality evidence baseline): no writable evidence
  file -- its own Owning issue (`docs/agent-product-scope.md`'s Axis D
  section names it) is a research report only; no skill has shipped an
  evidence file for this axis yet. STOP per Step 2.
- **Axis F** (dependency middleware): writable. A finding goes to this
  skill's own `references/middleware-inventory.md`.

(Axis E, git-hosting platform, is not listed here -- it is handed off
to `auditing-git-hosting-surface` per SKILL.md Step 3, not written to a
file by this skill's own Procedure at all.)

## Middleware dependency-declaring files

For an Axis F candidate, gitapex's own dependency-declaring files are
`flake.nix` (the Nix-managed toolchain), `apm.yml`/`apm.lock.yaml` (apm
itself), and `pyproject.toml`/`uv.lock` (Python dev tooling) -- see
`references/middleware-inventory.md` for what each already documents
before researching a candidate that might already be covered there.

## Platform-axis handoff target

Axis E candidates are handed off to `auditing-git-hosting-surface` --
`docs/agent-product-scope.md`'s own Axis E section names its Owning
skill and tracking issue -- rather than researched here; see that
skill's own SKILL.md for its checklists and platform-detection logic.

## Skill-shape-checker command

`python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py <touched-skill-dir>`
is gitapex's own deterministic skill-shape checker, run against any
skill whose files a candidate's research touched.

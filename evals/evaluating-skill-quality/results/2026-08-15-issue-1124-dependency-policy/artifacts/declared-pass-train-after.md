# Dispatch: declared-pass-train-after

## Prompt

```
You are applying a fixed skill-quality rubric to review a draft Claude Code
skill. Below is the exact rubric text for "dimension 7" (Bundled scripts) of
a nine-dimension quality rubric, plus a new 'Dependency policy' precondition section that calibrates one of dimension 7's criteria. Apply ONLY this rubric text (do
not invent additional criteria, and do not assume any other tool, skill, or
file is available to you -- everything you need is in this prompt). Answer
the specific question at the end.

=== RUBRIC TEXT BEGINS ===
## Dependency policy

A precondition the review establishes before grading (see [Contract
discipline](#contract-discipline)), read from the skill's
`metadata/gitapex.yaml` sidecar as `spec.dependencyPolicy`. The two levels
are defined in `SKILL.md`, checkable without opening this file. Unlike
[Portability level](#portability-level) and [Capability
assumption](#capability-assumption), this field is OPTIONAL -- the
`dependency-policy-declared` shape check PASSes on an absent declaration
rather than FAILing (the sidecar's own optional-field pattern, matching
`spec.references`' own `references-well-formed`, not the required-field
pattern `portability`/`capabilityAssumption` use). An absent declaration is
not "no policy": it is treated as **StdlibOnly-equivalent** -- see the
Undeclared branch below.

**Applicability.** This precondition, and the dimension 7 criterion it
calibrates, apply only to a skill that actually bundles scripts -- the same
"only if the skill ships code" gate dimension 7's own heading already
states. A skill with no `scripts/` directory needs no `dependencyPolicy`
declaration at all, StdlibOnly included, and this whole precondition is
not-applicable for it: do not grade a scriptless skill against either
branch below, and do not treat a scriptless skill's silence on this field
as a finding of any kind.

Unlike [Compatibility awareness](#compatibility-awareness) and
[Confidentiality awareness](#confidentiality-awareness) -- warning-only
axes that never change the verdict -- this precondition's two branches
directly gate dimension 7's own Pass/Fail on its "Dependencies listed;
execution intent stated" criterion. It calibrates that one criterion of
that one dimension, not several dimensions the way Capability assumption
calibrates dimensions 2/3/5/9.

**StdlibOnly.** **Pass**: no non-stdlib import anywhere in the skill's
`scripts/*.py`. Mechanical backing:
`gitapex_scan_execution_requirements_drift.py`'s `find_packages_drift`
already produces its `packages-pip-vs-script-content` under-declared
finding for ANY non-stdlib import once `executionRequirements.packages.pip`
is absent or empty -- exactly this branch's contradiction signal, with no
new scanner logic needed. **Fail**: a real non-stdlib import contradicts
the declaration -- a correctness defect in the declaration itself, not
merely an undisclosed one.

**Declared.** **Pass** requires ALL FOUR of:

- (a) every non-stdlib import is declared in
  `executionRequirements.packages.pip`, directly or via alias
  (`find_packages_drift`'s `packages-pip-vs-script-content` under-declared
  check clean);
- (b) every declared package name also appears in the skill's
  `compatibility` field (`find_packages_drift`'s
  `packages-pip-vs-compatibility` heuristic finding clean);
- (c) the script(s) actually use the PEP 723 self-contained-script pattern
  (a `# /// script` metadata block, invoked via `uv run`) -- **no existing
  mechanical check covers this sub-criterion**; grade it by direct
  reading/judgment, the same way dimension 7's other prose-judged bullets
  already work, and say so explicitly rather than silently implying it is
  mechanically gated;
- (d) every declared package is within gitapex's own allowlist
  (`execution-requirements-packages-allowlisted`'s own PASS).

**Fail**: any one of the four is violated -- name which sub-criterion.

**Undeclared (the field is absent).** Grade against the same criteria as
StdlibOnly above, plus one additional disclosure-consistency note if a
non-stdlib import is found anyway: the declaration gap itself is worth
naming, distinct from the underlying contradiction the StdlibOnly branch
already flags on its own.


## 7. Bundled scripts (only if the skill ships code)

Checks whether a skill's bundled scripts handle their own error
conditions, justify their configuration, state execution intent, and
document themselves well enough that a model can invoke them without
reading the source.

- **Solve, don't punt** -- scripts handle their own error conditions
  (missing file, permission denied) rather than throwing and leaving the
  model to cope.
- **No voodoo constants** -- every configuration value is justified in a
  comment. A constant the author cannot justify, the model cannot either.
- **Dependencies listed; execution intent stated** -- calibrated by the
  [Dependency policy](#dependency-policy) precondition's StdlibOnly/
  Declared/Undeclared branches above: required packages named and verified
  available on the target surface (see dimension 6) per whichever branch
  the skill's `spec.dependencyPolicy` declares (or, if undeclared,
  StdlibOnly-equivalent), and it is explicit whether the model should
  execute the script ("Run `analyze_form.py`") or read it as reference
  ("See `analyze_form.py` for the algorithm").
- **Scripts have clear documentation** -- what the script does, its
  inputs/outputs, and how to invoke it, not left for the model to infer
  from source.
- **Verifiable intermediate outputs** for high-stakes batch work -- a
  plan -> validate -> execute pattern with a machine-checkable plan file.

- **Fail:** a script that throws on a missing file and leaves the model to
  cope, or a magic constant with no comment explaining why that value was
  chosen.
- **Pass:** the script handles its own error conditions, every
  configuration value is justified inline, and its documentation states
  what it does, its inputs/outputs, and whether the model should run it or
  read it as reference.

**Comment categorization (Interface vs. Implementation).** Grounded in
John Ousterhout's Stanford CS190 "Writing Comments" lecture ([ouster]):
"Interface: what someone needs to know in order to use this class or
method" versus "Implementation: how the method or class works internally
to implement the advertised interface." Applied to a bundled script's own
comments, key the category to whether the skill tells Claude to execute
the script or read it as reference -- the same distinction the
"Dependencies listed; execution intent stated" bullet above already
requires the skill to state. An execute-only script's comments are
Interface documentation first: what an invoking agent must know before
calling it (inputs, outputs, flags, exit codes), and per the source's own
completeness requirement must be "Complete: must include everything that
any user might need to know," never assuming the invoking agent will open
the source to find a missing detail. A read-as-reference script's
comments carry more Implementation documentation instead -- "tricky
aspects, non-obvious reasons for code," boundary conditions, units, and
invariants -- since an agent told to read the script for its algorithm is
exactly the reader implementation comments serve. Ousterhout's own
separation principle applies directly: "do not describe the
implementation in the interface documentation" -- a script whose
top-of-file usage comment wanders into internal mechanism, or whose
inline implementation comments never state what a caller needs to know at
all, fails this categorization regardless of how well-written the prose
is in isolation.

**Context economy (token cost).** A read-as-reference script's comments
are loaded into context every time an agent reads the file -- the same
recurring cost dimension 2's "does the paragraph justify its token cost"
challenge already applies to prose. Anthropic's own guidance that a
bundled script "save[s] tokens (no need to include code in context)"
([ab]) only holds when the script is actually executed, not read.
Execute-only scripts get no verbosity penalty from this axis: nothing in
them enters context regardless of length, so comment verbosity is a
non-issue there. Read-as-reference scripts get a verbosity-vs-value check
instead: each comment line is a recurring cost every future read pays, so
a comment earning its place needs to state something a reader could not
recover faster from the code itself -- the same standard dimension 2
applies to prose, applied here to a script's own comments. Prose-only
judgment: no shape-checker mechanization is planned for this axis: which
comment lines earn their token cost is a per-comment value judgment, not
a mechanically checkable rule the way an unjustified constant or a
missing execution-intent phrase is.

**Test methodology and test code structure, when the script ships its own
test suite.** The five bullets above grade the script's code quality; a
bundled test suite earns its own deeper grading pass -- test-level
naming, test design technique diversity, static testing as a distinct
layer, risk-based prioritization, fixture design, test-double usage, and
named test smells -- using ISTQB's and Gerard Meszaros's established
vocabulary rather than an ad hoc "are there tests" or "the tests look
clean" check. Only apply this when the reviewed skill actually ships a
script with its own test suite; most skills do not, and skipping it is
not itself a finding. Full detail:

=== RUBRIC TEXT ENDS ===

=== REVIEW TARGET AND QUESTION ===

Use evaluating-skill-quality. Review this draft skill called
"converting-yaml-configs". Its metadata/gitapex.yaml sidecar declares:

spec:
  portability: Portable
  capabilityAssumption: Broad
  dependencyPolicy: Declared
  executionRequirements:
    packages:
      pip:
        - pyyaml

---
name: converting-yaml-configs
description: Convert a legacy YAML config file to the current schema. Use when a config still uses the old top-level key layout.
compatibility: "Requires pyyaml for YAML parsing; no other runtime assumptions."
---

# Converting YAML Configs

## Procedure

1. Run `uv run scripts/convert_config.py <path>` to rewrite the config
   in place to the current schema.

`scripts/convert_config.py`'s full content:

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Convert a legacy YAML config to the current schema."""
import sys

import yaml


def _migrate(data: dict) -> dict:
    if "old_key" in data:
        data["new_key"] = data.pop("old_key")
    return data


def main() -> int:
    path = sys.argv[1]
    with open(path) as f:
        data = yaml.safe_load(f)
    data = _migrate(data)
    with open(path, "w") as f:
        yaml.safe_dump(data, f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

For this review, treat `pyyaml` as present in this repository's own
`.gitapex/dependency-allowlist.json` allowlist under the `pip` ecosystem
-- a stipulated fact for this exercise, not something you need to
independently verify.

Is dimension 7's "Dependencies listed; execution intent stated"
criterion a clean Pass or Fail here? Cite the specific rubric wording
you are applying (including every requirement it holds this skill to),
and state literally the word PASS or FAIL as your verdict.
```

## Response

## Verdict: PASS

**Rubric basis.** The sidecar declares `spec.dependencyPolicy: Declared`, so this skill is graded under the **Declared** branch of the Dependency policy precondition, which requires **ALL FOUR** of:

- (a) *"every non-stdlib import is declared in `executionRequirements.packages.pip`, directly or via alias"*
- (b) *"every declared package name also appears in the skill's `compatibility` field"*
- (c) *"the script(s) actually use the PEP 723 self-contained-script pattern (a `# /// script` metadata block, invoked via `uv run`)"*
- (d) *"every declared package is within gitapex's own allowlist"*

with *"Fail: any one of the four is violated -- name which sub-criterion."* This calibrates dimension 7's bullet: *"Dependencies listed; execution intent stated -- ... required packages named and verified available on the target surface ... per whichever branch the skill's `spec.dependencyPolicy` declares ... and it is explicit whether the model should execute the script ('Run `analyze_form.py`') or read it as reference ('See `analyze_form.py` for the algorithm')."*

**Checking each sub-criterion against the evidence:**

- **(a)** The only non-stdlib import is `import yaml`. `executionRequirements.packages.pip` in the sidecar lists `pyyaml` — the standard package-name-for-import-name alias (`yaml` ⟵ `pyyaml`). Satisfied.
- **(b)** `compatibility: "Requires pyyaml for YAML parsing; no other runtime assumptions."` — the declared package name `pyyaml` appears verbatim. Satisfied.
- **(c)** The script opens with a genuine PEP 723 block (`# /// script` / `# dependencies = ["pyyaml"]` / `# ///`), and the Procedure instructs `uv run scripts/convert_config.py <path>` — the pattern is both present and actually invoked as specified. Satisfied.
- **(d)** Per the stipulation for this exercise, `pyyaml` is present in the repository's `.gitapex/dependency-allowlist.json` under the `pip` ecosystem. Satisfied.

All four Declared-branch sub-criteria pass, so nothing drags the criterion to Fail on the dependency-declaration half.

**Execution-intent half.** The Procedure states *"Run `uv run scripts/convert_config.py <path>` to rewrite the config in place to the current schema"* — an unambiguous execute instruction (not "see ... for the algorithm"), satisfying the criterion's second requirement that *"it is explicit whether the model should execute the script ... or read it as reference."*

Both halves of the criterion are satisfied with no violated sub-criterion to name, so the "Dependencies listed; execution intent stated" criterion is a clean **PASS**.

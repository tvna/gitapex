# Dispatch: declared-fail-after

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
"validating-openapi-specs". Its metadata/gitapex.yaml sidecar declares:

spec:
  portability: Portable
  capabilityAssumption: Broad
  dependencyPolicy: Declared
  executionRequirements:
    packages:
      pip:
        - jsonschema

---
name: validating-openapi-specs
description: Validate an OpenAPI spec file, resolving remote $ref pointers. Use when an OpenAPI YAML file needs schema validation before merge.
compatibility: "Requires jsonschema for OpenAPI schema validation."
---

# Validating OpenAPI Specs

## Procedure

1. Run `uv run scripts/validate_spec.py <path>` to validate the spec,
   fetching any remote `$ref` targets it references.

`scripts/validate_spec.py`'s full content:

```python
#!/usr/bin/env python3
# /// script
# dependencies = ["jsonschema"]
# ///
"""Validate an OpenAPI spec, resolving remote $ref pointers."""
import sys

import jsonschema
import requests


def _fetch_remote_ref(url: str) -> dict:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def main() -> int:
    path = sys.argv[1]
    with open(path) as f:
        spec = jsonschema.Draft202012Validator.check_schema(f.read())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

For this review, treat `jsonschema` as present in this repository's own
`.gitapex/dependency-allowlist.json` allowlist under the `pip` ecosystem
-- a stipulated fact for this exercise, not something you need to
independently verify.

Is dimension 7's "Dependencies listed; execution intent stated"
criterion a clean Pass or Fail here? If it fails, name specifically
which requirement is violated and cite the specific rubric wording you
are applying. State literally the word PASS or FAIL as your verdict.
```

## Response

**FAIL**

The "Declared" branch requires all four sub-criteria to pass, and sub-criterion **(a)** is violated:

> "(a) every non-stdlib import is declared in `executionRequirements.packages.pip`, directly or via alias (`find_packages_drift`'s `packages-pip-vs-script-content` under-declared check clean)"

`scripts/validate_spec.py` has two non-stdlib imports: `jsonschema` and `requests` (used in `_fetch_remote_ref` to fetch remote `$ref` targets — exactly the behavior the skill's own description and Procedure step promise: "resolving remote `$ref` pointers" / "fetching any remote `$ref` targets it references"). The sidecar's `spec.executionRequirements.packages.pip` lists only:

```
pip:
  - jsonschema
```

`requests` is absent — not declared directly, and not declared via alias. This is precisely the contradiction the rubric's mechanical backing targets (`packages-pip-vs-script-content` under-declared), just surfaced under the Declared branch's (a) check rather than the StdlibOnly branch's own Pass/Fail (since the skill declares `Declared`, not `StdlibOnly`).

Notably, the gap isn't confined to the sidecar — the script's own PEP 723 block (`# /// script` / `dependencies = ["jsonschema"]`) also omits `requests`, so even the self-contained-script mechanism sub-criterion (c) — which is otherwise satisfied in form (block present, invoked via `uv run` per the SKILL.md Procedure) — is carrying the same undisclosed dependency. Since `requests` is never declared anywhere, sub-criterion (b) ("every declared package name also appears in the skill's `compatibility` field") and (d) ("every declared package is within gitapex's own allowlist") can't even be evaluated for it — there's nothing declared to check.

Per the rubric: **"Fail: any one of the four is violated -- name which sub-criterion."** — sub-criterion **(a)** is the one violated: the `requests` import is a real, executed (not merely read-as-reference — the SKILL.md explicitly says "Run `uv run scripts/validate_spec.py <path>`") non-stdlib dependency missing from `executionRequirements.packages.pip`.

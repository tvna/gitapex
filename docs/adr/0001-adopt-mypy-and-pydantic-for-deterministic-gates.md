# Adopt mypy and pydantic for the deterministic-gate Python surface

## Status

Proposed

## Context and Problem Statement

gitapex's own `CLAUDE.md` (section 3) requires deterministic work to be
pushed into hooks, pre-commit, and CI/CD. Over time this produced 62
Python files (~23,500 LOC) implementing that discipline -- gate/scan
scripts under `.github/scripts/`, PreToolUse checker scripts under
`hooks/`, per-skill checker scripts under `skills/*/scripts/`, and eval
tooling under `evals/scripts/` -- with no static type checking anywhere
and no runtime schema validation for the JSON/YAML/transcript data these
scripts parse. A prior audit of the non-test files found the surface
already bimodal: roughly 65% fully type-annotated in modern style, ~28%
fully unannotated, the remainder partial; the pytest suite backing all
of it was almost entirely unannotated. Several of these scripts hand-roll
the same shape of validation repeatedly -- `.get(key)` followed by an
`isinstance` check, repeated per field -- against data whose real schema
is already documented elsewhere (`.gitapex/ssot.schema.json`, an eval
task's own YAML convention, a Claude Code transcript's JSON-lines shape).
This is a prospective decision, implemented in the same change that
introduces the tooling, not a retrofit of already-shipped behavior --
though the change did surface and fix a handful of genuine pre-existing
type errors along the way.

This ADR originally treated the `skills/`/`hooks/` deployment boundary
below as an unconditional bar on any third-party runtime dependency
living there. A later decision recorded in this same ADR
(https://github.com/tvna/gitapex/issues/1115) narrows, without
reversing, that premise: the [Agent Skills
specification](https://agentskills.io/skill-creation/using-scripts)
documents "self-contained scripts" -- a bundled script that declares
its own dependencies inline via [PEP 723](https://peps.python.org/pep-0723/)
and runs via `uv run`, which installs the declared dependencies on
demand rather than assuming a pre-installed site-package. This resolves
the "no guaranteed install step" concern for a consumer that has `uv`
available, with the remaining gap (a `uv`-less consumer) covered by this
repository's existing `compatibility`-disclosure convention. See
Decision Outcome below for the exact scope and package list.

## Decision Drivers

- Prevent regression of the ~65%-already-typed baseline as new gates are
  added, without demanding a single, huge, all-at-once fix-everything
  diff for the untyped remainder.
- Close the manual-validation gap in the highest-value parsers (the SSOT
  gate registry, eval-fixture YAML, transcript parsing) without
  violating this repository's own existing deployment boundary: only
  `skills/` (and, later, `hooks/`) ship to a consumer installing gitapex
  as a plugin, with no guaranteed `uv`/pip install step, so a
  third-party runtime dependency cannot live there via a normal
  site-package install. (A narrower, self-contained-script exception for
  `skills/*/scripts/` is recorded in Decision Outcome below; it does not
  change this driver's own scope, which stays `.github/scripts/`/
  `evals/scripts/`.)
- Make the new type-checking gate itself a required check, consistent
  with how this repository already treats its other deterministic gates
  (a check that exists but is merely advisory has, in this repository's
  own prior experience, a materially weaker track record than a required
  one).
- Discovered mid-implementation and folded into this same decision: a
  second, narrower deployment boundary exists even within
  `.github/scripts/`/`evals/scripts/` -- several of these scripts each
  have their own small, dedicated CI workflow that runs them via bare
  `python3` with no dependency-install step at all, by original design,
  for speed and simplicity. A third-party import in one of those files
  breaks that specific gate outright; this was found only after landing
  pydantic in 14 such files and watching their dedicated CI checks fail,
  not anticipated up front.

## Considered Options

- **mypy strict mode everywhere, immediately, no phase-in.** Rejected:
  would have failed on roughly half the in-scope files on day one,
  including a pytest suite that is almost entirely unannotated, forcing
  a single large, high-risk diff before any real benefit landed.
- **Advisory-only mypy (non-blocking check).** Rejected: this repository
  already runs a large family of required deterministic gates precisely
  because an advisory check is one a busy reviewer learns to ignore; a
  non-blocking type-check gate would not hold the line it exists for.
- **pydantic everywhere in scope, including `hooks/`/`skills/*/scripts/`,
  via a normal site-package install.** Rejected once
  `docs/repository-layout.md`'s own deployment-boundary statement was
  checked directly: those directories ship to a plugin consumer with no
  install step, so a pydantic import there would break silently for that
  consumer. Still rejected in that unrestricted, normal-install form --
  see the narrower option below, which resolves the same "no guaranteed
  install step" problem a different way instead of reversing this
  rejection.
- **Allow `skills/*/scripts/*.py` to depend on a small, curated, closed
  package set via PEP 723 self-contained scripts (`uv run`), dual-declared
  in `compatibility` and `metadata/gitapex.yaml`.** Chosen, for that
  narrower scope only (see Decision Outcome) --
  https://github.com/tvna/gitapex/issues/1115. Distinct from the option
  immediately above: a self-contained script installs its own declared
  dependencies on demand rather than assuming them preinstalled, so it
  does not reintroduce the silent-breakage risk that rejection exists to
  avoid. The remaining risk (a `uv`-less consumer) is disclosed via
  `compatibility`, not silently assumed away.
- **pydantic across the entire remaining `.github/scripts/`/
  `evals/scripts/` surface, no further narrowing.** The starting
  position for this decision; corrected mid-implementation once 14 files
  turned out to have their own dependency-install-free dedicated
  workflow, breaking ~11 separate required checks. Rejected in favor of
  the chosen option once that was found.
- **Chosen: mypy strict-by-default with a two-tier, per-module override
  allowlist (named legacy debt, each citing a follow-up reference),
  required from merge; pydantic scoped to exactly the files where no
  workflow invokes them without a dependency-install step** (a handful
  of files reached only through the `uv`-run pytest suite or a workflow
  that already sets up `uv`), with CLI-argument surfaces elsewhere
  validated via equivalent plain-Python checks instead.

## Decision Outcome

We will adopt mypy (strict-by-default, per-module override allowlist,
required CI check across 7 directory-grouped invocations -- a single
repo-wide sweep errors on two files that share a bare module name with
no package structure) across the full 62-file scope, and pydantic
(data models for the SSOT registry, eval-fixture YAML, and transcript
parsing, plus a handful of CLI-argument wraps) restricted to the files
whose own CI invocation path can actually support a third-party
dependency, because this is the only design found that satisfies
"comprehensive where safe" without either silently breaking this
repository's own already-documented deployment/CI-invocation
constraints or demanding an all-at-once fix of every pre-existing typing
gap before the gate can go live.

Separately (https://github.com/tvna/gitapex/issues/1115):
`skills/*/scripts/*.py` may depend, as direct dependencies (their own
transitive dependencies are not separately gated by this decision), on
exactly `pyyaml`, `jsonschema`, and `pydantic` (pip), and only when the
script uses the PEP 723 self-contained-script pattern (a `# /// script`
metadata block declaring `dependencies = [...]`) executed via `uv run`,
with the dependency stated in both the skill's `compatibility`
frontmatter field and its `metadata/gitapex.yaml` sidecar's
`spec.executionRequirements.packages.pip` list. This is narrower than,
and does not reverse, the unrestricted-pydantic-everywhere rejection
above: a self-contained script never assumes a pre-installed
site-package, so it does not reintroduce the silent-breakage risk that
rejection exists to avoid. `hooks/*.py` is unaffected by this narrowing
-- it is not yet a deployed runtime primitive
(`docs/repository-layout.md`), and extending this allowance there is
left to a separate, later decision.

## Consequences

Good, because new type errors in the already-typed core are now caught
in CI, not left to review.
Good, because the SSOT registry and eval-fixture parsers get real,
validated schema objects in place of repeated hand-rolled `isinstance`
checks.
Good, because the override allowlist is a visible, trackable list rather
than a silent gap -- each entry names what still needs annotating.
Bad, because CI gains a 7-invocation mypy job, adding wall-clock and
more moving parts to keep in sync if the `pythonpath`/directory grouping
ever changes.
Bad, because the override allowlist is real technical debt that needs
active pay-down, or it calcifies into permanent scope-creep.
Bad, because pydantic's own applicability boundary is now two-layered
(the `skills/`/`hooks/` deployment boundary, and the narrower
no-dependency-install-workflow boundary within `.github/scripts/`/
`evals/scripts/` itself) -- a real complexity cost for a future
contributor deciding whether a new script may import pydantic, mitigated
by this ADR and the registry entry below stating the rule explicitly
rather than leaving it to be rediscovered by a second broken CI run.
Good, because `skills/*/scripts/` authors get a real, checkable path to
a small set of common dependencies (YAML parsing, JSON Schema
validation, data models) without this repository silently assuming a
site-package install its own deployment boundary cannot guarantee.
Bad, because a consumer without `uv` (or another PEP 723-compatible
runner, e.g. `pipx`) available cannot use the zero-setup `uv run` path
this decision relies on -- they could still run an affected script by
separately installing its declared dependencies themselves, but that
manual step is exactly what the self-contained-script mechanism exists
to avoid needing. The `compatibility` disclosure this decision requires
makes the limitation visible before invocation, but does not remove it.
Bad, because the same fact -- which packages a given skill actually
depends on -- must now stay consistent across three places (this ADR's
own closed list, the skill's `compatibility` prose, and its
`metadata/gitapex.yaml` declaration), with no automated enforcement from
this ADR alone; the follow-up work named in Confirmation below is what
closes that gap.

## Confirmation

The `mypy-type-check` CI gate itself (`.github/workflows/test.yml`,
registered in `.gitapex/ssot.json`) is the primary mechanism: a PR
introducing an unannotated new function outside the override allowlist
fails a required check, not review memory. There is no equivalent
automated check yet for "did a new pydantic import land in a file
invoked by a dependency-install-free workflow" -- today this relies on
code review noticing a `from pydantic import` line in
`.github/scripts/`/`evals/scripts/` and checking whether that file's own
dedicated workflow (if any) sets up `uv` first. Automating that check is
named here as a real gap, not proposed as part of this decision.

For the `skills/*/scripts/` dependency allowance
(https://github.com/tvna/gitapex/issues/1115), no automated enforcement
exists yet as of this edit -- this ADR only records the decision. Four
follow-up changes are expected to build it: recognizing
`executionRequirements.packages` as a valid sidecar shape (closing the
gap https://github.com/tvna/gitapex/issues/845 left open after
https://github.com/tvna/gitapex/issues/804), a declared-vs-actual-imports
drift scanner for `skills/*/scripts/`, a `dependencyPolicy` precondition
in the skill-quality rubric that grades a skill's stdlib-only or
declared-dependency claim on its own merits, and a repository-local
closed-list configuration plus a CI gate enforcing it against every
skill. Until all four land, this decision relies on review, not a
required check.

A related, pre-existing gap this decision surfaced rather than caused:
`skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
already imports PyYAML today, guarded only by a friendly error message
pointing at `uv sync --group dev` (a whole-repository dev-dependency-
group install), not the PEP 723 + `uv run` pattern this decision
establishes -- and that dependency is declared in neither
`compatibility` nor `metadata/gitapex.yaml` on `evaluating-skill-quality`
itself. It predates this decision and is not yet reconciled with it;
deciding whether to migrate it to the new pattern or document it as a
standing development-tool exception is tracked separately
(https://github.com/tvna/gitapex/issues/1117).

# Prefer uv-resolved python3 in hooks/*.sh, with a bare-python3 fallback

## Status

Accepted (approved by tvna, 2026-09-03)

## Context and Problem Statement

This decision is already implemented, on branch `claude/fix-python-path-resolution-q2e3pv`
(PR #1701, not yet merged as of this writing) -- this is a retrofit
record, written after the change, not before it.

`hooks/*.sh` files are this repository's own agent-harness hook
subprocesses (PreToolUse/Stop, etc.). Several of them invoke a companion
Python checker script. Before this change, that invocation was a bare
`python3 "$script"` call, which resolves the `python3` binary from
whatever `PATH` the *calling* hook context happens to have at
invocation time -- not necessarily this repository's own uv-managed
`.venv`.

Issue #1697 reported the resulting defect directly:
`hooks/check-pr-skill-audit-disclosure.sh`'s precondition probe denied a
real `create_pull_request` call with `"python3 cannot import: pydantic"`,
even though `uv sync --group dev` had already installed pydantic into
this checkout's own `.venv` -- because the ambient `PATH` at hook-
invocation time resolved a different `python3` that could not see that
`.venv`. Issue #1581 raised the same PATH-dependent-interpreter defect
class against a different call site.

A conflicting constraint narrows the fix: per `docs/repository-layout.md`,
only `skills/` and `hooks/` are ever deployed to a *consumer* plugin
install of this repository, and a consumer install carries no `uv`
toolchain or lockfile of its own. An unconditional switch to `uv run` in
every `hooks/*.sh` file would resolve this repository's own dev-checkout
bug but break every consumer install outright.

## Considered Options

- Leave every `hooks/*.sh` bare-`python3` call site unchanged (do
  nothing).
- Switch every `hooks/*.sh` companion-script invocation to `uv run
  --frozen python3` unconditionally.
- Resolve the interpreter through a `python3_cmd` array: prefer `uv run
  --frozen [--directory "$plugin_root"] python3` when `command -v uv`
  succeeds AND the checkout actually owns `pyproject.toml`/`uv.lock`,
  falling back to bare `python3` otherwise.

## Decision Outcome

We will resolve each `hooks/*.sh` companion-Python-script invocation
through the third option: a `command -v uv`-and-lockfile-gated
`python3_cmd` array that prefers `uv run --frozen python3` when this
checkout is a uv-managed dev checkout, and falls back to the pre-existing
bare `python3` otherwise -- because it closes the PATH-dependent
false-deny issue #1697 and #1581 both describe, in exactly the dev
checkout where it can occur, without changing behavior at all for a
consumer plugin install that has no `uv` toolchain to invoke.

The one exception is `hooks/check-pr-skill-audit-disclosure.sh`'s own
tier-1 block, which only ever runs when `.github/scripts/` is present
(i.e., only in this repository's own dev checkout, never a consumer
install) -- there, the invocation uses `uv run --frozen python3`
unconditionally, since the gating condition the other nine call sites
need is already guaranteed by that block's own existing
`.github/scripts/`-presence check.

As a durable enforcement mechanism for this decision, we also promoted
`.github/scripts/gitapex_gate_bare_python3_invocation.py`'s own
`hooks/*.sh` shell-variable-indirected scan from WARNING-only (report
only, CI never failed) to HARD-FAIL: a `hooks/*.sh` bare `python3
"$var"` invocation of a `.github/scripts/*.py` target, or of a `hooks/*.py`
target registered in `.gitapex/ssot.json` under a gate whose own
`preconditions.requires_python_packages` is non-empty, now fails CI and
local-preflight.

## Consequences

Good, because the exact PATH-dependent false-deny issue #1697 reported
no longer reproduces in a uv-managed dev checkout, while a consumer
plugin install's own behavior (bare `python3`, unchanged) is completely
unaffected.

Good, because the promoted hard-fail gate makes this decision durable
going forward: a future `hooks/*.sh` call site that reintroduces a bare
`python3 "$var"` of a third-party-dependent target now fails CI, rather
than silently reintroducing this defect class the way the original
regression (#1697, itself a regression from #1566/PR #1675) went
undetected.

Bad, because the `command -v uv` + lockfile-gated `python3_cmd`-array
resolution snippet (~5 lines) is duplicated verbatim across all ten
`hooks/*.sh` call sites (nine files, one of them -- `check-bash-safety.sh`
-- with two call sites), with no automated check that the ten copies stay
in sync. `hooks/` is entirely on the deployed side of the plugin-
redistribution boundary per `docs/repository-layout.md`, so consolidating
this into one sourced helper is not blocked by that boundary; it simply
has not been done yet.

Bad, because the hard-fail gate's own `load_python_dependent_hook_script_names`
helper (which reads `.gitapex/ssot.json` to learn which `hooks/*.py`
targets carry a third-party-package precondition) fails *open* --
returns an empty result rather than a hard failure -- when an individual
`gates` entry's own `preconditions` field is present but malformed
(e.g., a string instead of a mapping), even though the same entry's
`script` list does name a `hooks/*.py` target. This is narrower than, but
the same class as, the whole-file-unreadable case the gate does already
treat as a hard failure; an independent review of this branch confirmed
it live (a well-formed `ssot.json` with one corrupted `preconditions`
field, alongside a real bare invocation of the registered target,
produced a false "clean" exit 0). Not yet fixed as of this ADR's writing.

Unknown, pending a follow-up fix: whether the per-gate fail-open gap
above gets closed by hard-failing on any malformed `gates` entry, or by
some narrower per-field rule -- this ADR records the uv-preference
*decision itself*, not that follow-up's own resolution.

## Confirmation

`.github/scripts/gitapex_gate_bare_python3_invocation.py`'s HARD-FAIL
`hooks/*.sh` shell-variable-indirected scan, run in CI and as part of
local-preflight: a new bare `python3 "$var"` invocation of a
`.github/scripts/*.py` target, or of a registered third-party-dependent
`hooks/*.py` target, fails the check.

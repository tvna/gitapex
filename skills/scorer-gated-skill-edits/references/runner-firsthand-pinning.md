# Runner firsthand pinning

Loaded when Procedure step 1 runs against this repository's own default
eval runner, `evals/scripts/gitapex_run_eval_suite.py` -- this file
carries the exact commands, and the full reasoning behind each of step
1's portable checks, for that runner specifically. It is split out of
the Procedure body because it is gitapex-specific content: the runner
lives outside `skills/scorer-gated-skill-edits/` entirely, at a
repository-wide `evals/scripts/` path, so a copy of this skill vendored
into another repository carries this file's text but not the script it
describes -- see the [vendoring
fallback](#vendoring-fallback-an-externally-pinned-runner) below, and
`SKILL.md`'s own Notes on why `spec.portability` is `Mixed`.

## Contents

- [Invocation and the runner-resolution check](#invocation-and-the-runner-resolution-check)
- [Dirty-checkout check](#dirty-checkout-check)
- [Firsthand last-touching commit](#firsthand-last-touching-commit)
- [Shallow-clone-boundary check](#shallow-clone-boundary-check)
- [Vendoring fallback: an externally pinned runner](#vendoring-fallback-an-externally-pinned-runner)

## Invocation and the runner-resolution check

This skill executes its measured trials with
`evals/scripts/gitapex_run_eval_suite.py`, the repository-owned runner
the fixture corpus's suite and task formats are written for -- invoked
as `uv run python3 evals/scripts/gitapex_run_eval_suite.py --eval-yaml
EVAL.yaml --skill-md SKILL.md`, never bare `python3`: the script reaches
third-party dependencies -- PyYAML, pydantic -- through
`evals/scripts/gitapex_run_ablation.py`, either of which can be missing
outside `uv`'s managed virtualenv and fails with `ModuleNotFoundError`.

Step 1's runner-resolution check, for this runner: run
`uv run python3 evals/scripts/gitapex_run_eval_suite.py --help` and
confirm it prints usage without error. This resolves `uv`, the
interpreter, and the runner's own import chain in the environment the
trials will run in -- the functional equivalent of a `--version` check
for a script with no independent version string of its own. If `uv` is
absent, the script cannot be found, or the command errors, STOP and say
**cannot iterate -- the eval runner is missing**, naming which it was.

## Dirty-checkout check

Because the runner is version-controlled content read from the same
checkout as the skill under iteration, not an externally pinned binary,
its recorded "version" is the exact commit that last touched it. Before
reading that commit off, run
`git status --porcelain -- evals/scripts/gitapex_run_eval_suite.py` in
that same checkout and confirm it prints nothing. Staged or unstaged,
both count: a `git diff --quiet`-only check (unstaged) still misses a
staged-but-uncommitted edit -- `git log -1` would keep naming the prior
commit while the code that actually runs already differs from it. Any
output at all means the tracked file carries local edits, so no commit
names what is actually about to run -- STOP the same way as the
runner-resolution check above.

## Firsthand last-touching commit

Only once the dirty-checkout check is silent, run
`git log -1 --format=%H -- evals/scripts/gitapex_run_eval_suite.py` to
get a candidate commit. If git reports none at all (a never-committed,
untracked copy), STOP the same way.

## Shallow-clone-boundary check

Confirm that candidate actually has a resolvable parent --
`git rev-parse --verify -q <candidate>^` -- before trusting it: a
shallow clone's own boundary commit has no locally-known parent, and
`git log -1 -- <path>` silently reports that boundary commit as having
"touched" every path in its tree rather than the file's true
last-touching commit -- exactly the failure
`.github/scripts/gitapex_scan_harden_checkout_pin_drift.py` already
found and fixed for an unrelated pinned path in this same repository.
No resolvable parent -- STOP the same way once more.

## Vendoring fallback: an externally pinned runner

A repository that vendors this skill alongside a different, externally
pinned eval runner instead restores step 1's original shape: confirm
the binary and capture the real `--version` string it reports, under
the same firsthand-only rule step 1 states inline -- the version goes
in the record only when step 1 obtained it firsthand, in the same
environment the trials run in.

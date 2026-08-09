# gitapex-specific cross-links

Loaded by step B2 only when this copy of the skill's own files lives in
the gitapex repository -- see SKILL.md's "Generalize and substitute"
note for why that is a different condition from "the repository being
audited is gitapex," and for what a copy vendored elsewhere does instead (its own hosting
repository's tracking issue and instruction file where they exist,
omitted where they don't). A vendored copy never reads this file.

## Gap cross-link target

gitapex's tracking issue for approved-but-unbuilt tooling is
[gitapex#82](https://github.com/tvna/gitapex/issues/82). `#82` is the
umbrella tracking issue for gitapex's approved read-only gh wrapper -- it
has no single "landed" state of its own. The approved wrapper that would
close each Gap is an unfiled candidate child issue under `#82`, not `#82`
itself. Word every cross-link that way ("consumer of an unfiled candidate
child issue under `#82`"), not as "blocked on `#82` landing."

## Read-only stop-boundary authority

This skill never takes a write action (change branch protection, revoke
a webhook, rotate a deploy key) -- those stay human decisions per this
repo's own `CLAUDE.md`, section 4 ("Simplicity, Bounded by Safety").

## Unpinned-actions script precedent

`scripts/gitapex_scan_unpinned_actions.py` reuses
`.github/scripts/gitapex_scan_toolchain_pin_drift.py`'s walk/report/exit-code
shape rather than inventing a second, divergent detector -- that script
is this repo's own existing drift-scan precedent (it guards a different
invariant: Class B toolchain tool pins, not action pins).

# gitapex-specific cross-links (read only inside this repo)

Read this ONLY when running this skill inside the gitapex repository
itself. A vendored copy of this skill in another repository drops this
file entirely and substitutes its own governance issue, instruction
file, and script precedent for the three pointers below -- nothing else
in this skill depends on this file existing.

## Gap cross-link target

Every checklist item marked Gap in `references/github-surface-checklist.md`
or `references/gitlab-surface-checklist.md` cross-links **gitapex CLI
governance issue #82**. #82 is the umbrella tracking issue for gitapex's
approved read-only gh wrapper -- it has no single "landed" state of its
own. The approved wrapper that would close each Gap is an unfiled
candidate child issue under #82, not #82 itself. Word every cross-link
that way ("consumer of an unfiled candidate child issue under #82"), not
as "blocked on #82 landing."

## Read-only stop-boundary authority

This skill never takes a write action (change branch protection, revoke
a webhook, rotate a deploy key) -- those stay human decisions **per this
repo's own `CLAUDE.md`, section 4** ("Simplicity, Bounded by Safety"). A
vendored copy cites whatever instruction file the target repository has
for the same rule, if any; the read-only principle itself still applies
even with no file to cite.

## Unpinned-actions script precedent

`scripts/scan_unpinned_actions.py` reuses
**`.github/scripts/scan_toolchain_pin_drift.py`**'s walk/report/exit-code
shape rather than inventing a second, divergent detector -- that script
is this repo's own existing drift-scan precedent (it guards a different
invariant: Class B toolchain tool pins, not action pins). This is cited
here as the origin of `scan_unpinned_actions.py`'s own design; a vendored
copy has no obligation to match that file's shape and does not need it
to exist.

# Skill provenance (maintainer-facing)

Origin and corroboration notes for skills whose home repository is this one.
This is maintainer/citation material -- commit SHAs, PR numbers, and external
projects cited only as corroboration -- not skill behavior, and specific to
this repository, so it lives here rather than in the distributed skill or its
`references/`. A vendored skill does not need this repository's own history.

## battle-testing-a-skill -- corroborating side-references (not sources)

These are external projects cited only as corroboration; the skill does not
depend on them and does not bundle them.

- The clairvoyance project runs an adversarial "battle" harness over its own
  skills; its category set matches the extracted core, which corroborates but
  does not originate this skill. The same project's portability write-up
  describes the exact failure this skill exists to fix: a foreign harness
  asked to evaluate a skill has no rubric injected and cannot say why a skill
  is weak.
- microsoft/waza ships a `waza adversarial` command for offline adversarial /
  fault-injection packs -- a separate implementation of a related idea.

Neither is authoritative for how a model actually reasons about adversarial
skill-testing; the source of record for the skill is the observed
cross-model behavior recorded in
`skills/battle-testing-a-skill/references/provenance-and-caveats.md`.

For readers working in this repository (gitapex), dimensions 11-17 of that
catalog were added by a comparative review tracked in gitapex#74, checking
coverage against obra/superpowers and microsoft/waza (the same two
side-references above). See the references file's "Comparative review"
section for what that review verified directly versus what remains
unmeasured or secondary-sourced.

## establishing-ubiquitous-language -- worked-example provenance

For readers working in this repository (gitapex), the worked example in
`skills/establishing-ubiquitous-language/references/worked-example.md` (owner
vs. author vs. contributor) traces to: the document `docs/motivation.md`, the
draft commit `241f4392`, and the rename commit `ef222b81` on pull request #2.
This is provenance for maintainers of this specific repository, not something
the worked example depends on.

## gated-skill-edits -- held-out gate provenance

`skills/gated-skill-edits/scripts/score_contract.py`'s docstring refers to a
"held-out gate"; for readers working in this repository, that gate was
introduced by gitapex#30. This is provenance for maintainers of this specific
repository, not something the script depends on.

## evaluating-skill-quality -- worked-example provenance

For readers working in this repository (gitapex), the worked example in
`skills/evaluating-skill-quality/references/worked-example-self-review.md`
notes that this skill's own deterministic shape lane was delegated to
`scripts/check_skill_shape.py`; that delegation was made in gitapex#32. This
is provenance for maintainers of this specific repository, not something the
worked example depends on.

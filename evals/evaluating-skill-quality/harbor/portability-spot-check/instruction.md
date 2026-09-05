# Portability spot-check

Classify three skill shapes using exactly the rule set below. Write your
answer to `/app/verdict.json` as JSON with exactly these keys and exactly
these value strings (no other text in the file):

{"case_a": "<level>", "case_b": "<level>", "case_c": "<level>"}

where `<level>` is one of `Portable`, `Mixed-via-file`,
`Mixed-via-clean-sibling`, `Mixed-via-bundled-convention`, `Repository-scoped`.

## Rules

**Portable** clears all four conditions: (a) no real sibling-skill
dependency (reading, applying, or being bound by another skill's content --
a bare related-skills mention is not a dependency); (b) no hard dependency
on a non-skill file outside the skill's own directory; (c) no unhedged
origin-repository fact-claim anywhere (executed step or not); (d) purpose
not inherently bound to one specific repository.

**Mixed** clears (d) and fails exactly one of (a)/(b)/(c) in one narrow way:
- `Mixed-via-file`: fails (b) only -- one hard outside-file dependency,
  cleanly named, with a disclosed fallback for a vendoring consumer.
- `Mixed-via-clean-sibling`: fails (a) only -- exactly one real
  sibling-skill dependency, touching only its public contract, with any
  other repo-specific content cleanly split into its own file.
- `Mixed-via-bundled-convention`: fails (c) only -- the only repo-specific
  content is confined to distinctly-named bundled files inside the skill's
  own directory that its SKILL.md explicitly tells a vendoring consumer to
  replace or drop, AND a procedure step reads such a file to decide behavior
  (a file cited only as a worked example stays Portable).

**Repository-scoped**: fails (d) outright (inherently repo-bound purpose);
or more than one real sibling-skill dependency, or one failing the
narrowness above (sibling fan-out); or an outside-file dependency with no
disclosed fallback; or unhedged origin-repository claims scattered through
the portable core itself.

## Cases

**Case A.** Skill S1 declares `requires: []`. Its procedure uses only
bundled scripts inside its own directory, cites no outside paths, and its
purpose is generic: reviewing any SKILL.md against a quality rubric.

**Case B.** Skill S2 declares `requires: []`. Its Notes state: Step 11's
placement convention is this repository's own, split into its own file
`references/this-repo-only.md`, so a calling repository that vendors this
skill replaces only that one file and leaves everything else unchanged.
Step 11 reads that file to decide where to place its output.

**Case C.** Skill S3 declares
`requires: [planning-a-branch-from-an-issue, outward-artifact-preflight]`.
Its procedure consumes the Branch Plan document the first skill produces
and reuses a provenance-scan script the second skill bundles.

# Branch Plan: claude/portability-classification-rules-jsubtu

Issue: https://github.com/tvna/gitapex/issues/1788
Parent tracking issue: https://github.com/tvna/gitapex/issues/1787
Consolidated defects resolved in this same edit: https://github.com/tvna/gitapex/issues/1692 (#1687, #1689)
Base: main

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| The Portability level section states Portable's 4 conditions, Mixed's two narrow sub-types (via-file, via-clean-sibling) with their full narrowness conditions, the new Mixed-via-bundled-convention sub-type, and Repository-scoped's 3 triggers, replacing the current prose | Rewrite rubric.md's "Portability level" section (~722-956) to state these definitions precisely enough for a reviewer to apply them without re-deriving intent | Edit `skills/evaluating-skill-quality/references/rubric.md`; update `worked-example-explaining-the-work.md`/`worked-example-self-review.md` if they cite the old definitions verbatim (investigation found they do not cite sub-type names, only the general 3-level names, so likely no change needed -- confirm during the task) | Re-run the new rule set by hand against real skills in this repository (`drafting-an-adr`, `auditing-agent-product-scope`, `scanning-attack-surfaces`, `evaluating-skill-quality` itself, `explaining-the-work`) and confirm each already-declared level still matches | A skill not covered by this narrower spot-check could reveal a rule-text gap -- residual risk, not blocking this edit |
| The two `drafting-an-adr` scope clarifications (Fix A, Fix B) are added at the cited locations | Insert the two clarifying sentences (materially equivalent wording) near rubric.md lines ~775 and ~883 | Edit rubric.md | Re-run `gitapex_check_skill_shape.py` against `drafting-an-adr` and confirm it still passes | none identified |
| The two dimension-5 substitute-scoping sentences, plus the dimension-6 porting-boundary-map note and the trigger-3 fallback clause, are added | Insert near rubric.md lines ~1835-1838 and ~863-869 (substitute scoping), and near dimension 6 (porting-map complements) | Edit rubric.md | Re-apply the new rules by hand to `executing-a-branch-plan` and confirm Repository-scoped under triggers 2 and 3 regardless of any future porting-map completeness | A skill this investigation didn't examine could later claim the porting-boundary-map fallback under trigger 3 in a way that needs its own scrutiny -- deferred to ordinary review, not blocking |
| #1687 and #1689 (consolidated in #1692) are resolved in the same edit | #1687: no backward-reference to a not-yet-run dimension-5 finding from inside a section graded at an earlier step; #1689: no "platform" vocabulary in the Portability-axis prose | Word the new substitute-scoping sentences and any restated substitute conditions to avoid both defects; grep the full substitute passage for "platform" while editing it | Close #1692 (citing #1687/#1689 as resolved) once the edit lands; #1692's own proposed deterministic gates are explicitly deferred (Human Decision resolved: no, prose-only this PR) | This PR resolves #1692 with a prose-only fix, not its own proposed deterministic gates -- tracked as a separate follow-up, not blocking |

## Task Decomposition

Single task, single wave -- all planned ops land in one file
(`skills/evaluating-skill-quality/references/rubric.md`), with a
conditional, dependent check of two sibling `references/*.md` files that
can only be judged once the new rubric.md text is final. No parallelism
is possible (every op shares the same file), so this is the degenerate
single-task case `executing-a-branch-plan`'s own Related skills section
names explicitly.

Skill-file edit routing: none of the planned ops create or edit a
`SKILL.md` (a `references/` file only) -- `drafting-a-skill`'s own
dispatch routing does not apply to this task.

### Task 1: Rewrite rubric.md's Portability level rule set

Source ACM rows: all four rows above.

Concrete ops:

1. `skills/evaluating-skill-quality/references/rubric.md`, "Portability
   level" section (current ~722-870): replace the Portable/Repository-
   scoped/Mixed prose with the new rule set -- Portable's 4 conditions
   (a-d), Mixed-via-file, Mixed-via-clean-sibling, the new
   Mixed-via-bundled-convention, and Repository-scoped's 3 triggers.
   Preserve the existing litmus-test detail (evals/docs path handling,
   hedge vocabulary, `spec.externalCitations`, structural identifiers,
   bare issue/PR citations) as condition (c)'s elaboration rather than
   deleting it.
2. Same section, Fix A (~775): add a sentence stating the hedge-
   vocabulary rule's scope is outside-the-skill's-own-directory paths
   only, never an in-directory `references/...`/`scripts/...` citation.
3. "Dependency file portability" subsection (~883): add Fix B, stating
   that subsection only asks where a bundled file lives, never whether
   its content is repository-specific.
4. Dimension 5's "Mixed-portability substitute" (~1801-1891): add the
   two scoping sentences from the issue (near ~1835-1838, and the
   trigger-2 cross-reference near the new Mixed section's own end,
   materially at old ~863-869) -- worded to avoid both #1687's backward-
   reference shape and #1689's "platform" vocabulary.
5. Dimension 6 (durability): add a porting-boundary-map note -- optional
   dimension-6 vendoring aid, never label-deciding, and its completeness
   satisfies trigger 3's "fallback exists" predicate directly.
6. Read `worked-example-explaining-the-work.md` and
   `worked-example-self-review.md`; edit only if either cites the old
   definitions in a way the new text contradicts (spot-check during
   planning found no sub-type-name citations, only generic 3-level
   references that remain accurate).

Proof method: manual re-application of the new rules to `drafting-an-adr`,
`auditing-agent-product-scope`, `scanning-attack-surfaces`,
`evaluating-skill-quality`, `explaining-the-work`, and
`executing-a-branch-plan`, confirming each already-declared level still
matches; `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
run against each of those skill directories with no new failures;
existing pytest suite under `skills/evaluating-skill-quality/scripts/`
green; grep confirms no "platform" token inside the Portability level
section and no backward-reference phrasing.

File ownership: sole task, no conflicts.
Interface dependencies: none (single task, single wave).
Wave: 1 (only wave).
Irreversibility: none of the planned ops are irreversible (prose edits to
existing `references/*.md` files, fully reversible via git).

## Execution mode

Workflow tool not opted into for this session (no `ultracode` keyword, no
explicit multi-agent-orchestration request) -- executed via the sequential
main-thread fallback (Notes section, "Mixed" portability), one task, no
wave/run boundary, no worktree isolation.

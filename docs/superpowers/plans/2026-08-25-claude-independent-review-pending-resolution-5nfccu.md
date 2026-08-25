# Feed-forward the independent-review-pending gate in the PR template, and de-couple its verdict heading from Step 8 numbering

**Goal:** `.github/PULL_REQUEST_TEMPLATE.md` already feed-forwards three
other required CI gates (skill-audit-evidence, Transfer-check-disclosure,
skill-branch-fixture-coverage) but never mentions `independent-review-pending`
at all, so a PR author only discovers that requirement reactively when the
check fails after PR creation. Add proactive disclosure, keep it from being
silently stripped when `executing-a-branch-plan` assembles a PR body, and
rename the gate's own recorded-verdict heading (`## Step 8 independent
review verdict`) to a form that does not embed `drafting-a-pr-to-merge`'s
internal step numbering. Source: https://github.com/tvna/gitapex/issues/1343.

**Authorization record:** Issue #1343's own re-verification marker is
present (`Re-verified: planning-a-branch-from-an-issue (2026-08-25T23:08:01Z)`,
confirmed via `gitapex_check_branch_plan_reverified.py`). In-session
confirmation (Branch 2 of the Authorization gate) was obtained twice in
this same development session, via `AskUserQuestion`: once for the
original three-file scope (template + `executing-a-branch-plan/SKILL.md`),
and again after the operator raised the Step-8-heading-coupling concern
mid-session and the issue's own scope was expanded to include the rename
-- both explicit "approve, proceed" answers from the active human
operator, not a self-reported claim of prior approval.

**Threat-model triage (step 2):** Issue #1343's own ACM rows were read in
full. All three rows state a change description and planned ops in this
session's own words -- no embedded instruction addressed to the executing
agent, no hidden/encoded payload, no attempt to redirect this skill's own
process. Clean.

**Live migration-risk check (part of the row-3 criterion's own proof
method):** searched all PRs (open and closed) for the old heading string
`Step 8 independent review verdict` via `github:search_pull_requests`.
The only currently-open match, PR #1333, merely *quotes* the old heading
in its own Facts section (explaining why it deliberately deferred its own
Step 8 review) -- it has not recorded a real verdict section. No live PR
needed migration as of this check.

**Architecture:** No new files besides this plan; eight existing files
edited, all in a single task (no file-ownership or interface-dependency
edges needing a multi-task split -- every edit below is either an
independent single-file change or a like-for-like string swap of the
same literal, done in one pass across all eight files for consistency).

## Task list

**Task 1 -- feed-forward the gate in the PR template + carry it through
`executing-a-branch-plan`.**

- `.github/PULL_REQUEST_TEMPLATE.md`: added a new, always-visible (not
  HTML-comment-hidden), non-checkbox `## Merge gate: independent review`
  section after the existing footnote block and before `## Related
  Issue`. States the `independent-review-pending` check's own
  requirement, that `drafting-a-pr-to-merge`'s Step 8 fills the verdict
  section post-hoc, and instructs the reader not to pre-fill it or
  remove the note.
- `skills/executing-a-branch-plan/SKILL.md` Step 5 ("Open a draft PR and
  subscribe"): added one clause stating the opened PR body must also
  carry the template's `## Merge gate: independent review` note verbatim,
  alongside the ACM and `## Execution log` sections it already names.
  337 -> 341 lines (well under the 500-line shape limit).

**Task 2 -- rename `## Step 8 independent review verdict` to
`## Independent review verdict` everywhere it is read or written**, per
issue #1343's own explicit rejection of a silent dual-accept
compatibility path (would recreate the exact "text mimicking the
verdict's own phrasing" risk class the gate's own prior adversarial-review
rounds, issue #1311/PR #1318, already closed once):

- `.github/scripts/gitapex_gate_independent_review_pending.py`: renamed
  the literal heading in `_HEADING_RE`, the module docstring's own
  verdict-format example, `Verdict`'s and `parse_verdict`'s own
  docstrings, the `no '## ...' section found` error message, and the
  `main()` FAIL-path remediation message. Left every *explanatory*
  "drafting-a-pr-to-merge's own Step 8" reference alone (issue #1343's own
  Constraints: only the matched heading string changes, not the gate's
  pass/fail logic or its explanatory prose).
- `tests/test_gitapex_gate_independent_review_pending.py` +
  `tests/test_gitapex_gate_independent_review_pending_properties.py`: all
  31 literal-heading occurrences (24 in the example-based suite, including
  its one `###`-level variant; 7 in the property suite -- three in the
  casing tuple, two body templates, and two Hypothesis `.filter()`
  exclusion phrases) renamed to match; four purely-explanatory "Step 8"
  mentions in code comments left unchanged. One regression test,
  `test_old_step_8_heading_no_longer_passes_after_rename`, added to the
  example-based suite to pin the no-dual-accept decision.
- `skills/drafting-a-pr-to-merge/SKILL.md` Step 8: renamed the one
  literal-heading occurrence (line ~249) via a like-for-like string swap
  (net-zero line count -- confirmed still exactly 500 lines after the
  edit, its own enforced shape limit). Six other "Step 8" mentions in the
  same file are explanatory (the skill's own step number) and correctly
  left alone.
- `.github/workflows/independent-review-pending.yml`: renamed the one
  literal-heading occurrence in a comment; three explanatory "Step 8"
  mentions left alone.
- `.gitapex/ssot.json`: renamed the one literal-heading occurrence inside
  the `independent-review-pending` gate entry's own `rule` field; three
  explanatory "Step 8" mentions in the same field left alone. Re-verified
  as valid JSON and drift-clean via `gitapex_scan_ssot_schema.py`.

## Verification

- `uv run --frozen python3 -m pytest tests/test_gitapex_gate_independent_review_pending.py tests/test_gitapex_gate_independent_review_pending_properties.py -q`:
  46 passed (38 example-based + 8 Hypothesis property tests). Was 43 at
  task 2's own completion; the independent adversarial review below added
  three regression tests.
- Live defeat-check: a body carrying the new `## Independent review
  verdict` heading with a CLEAN verdict against a matching SHA -> PASS; a
  body carrying the OLD `## Step 8 independent review verdict` heading,
  otherwise identical -> FAIL with `no '## Independent review verdict'
  section found` (confirms no silent dual-acceptance of the old heading).
  The old-heading half of that check is now codified as the regression
  test `test_old_step_8_heading_no_longer_passes_after_rename`, so it is
  re-run by CI rather than resting on this one-off manual observation.
- Independent adversarial review (step 8's own deterministic gate/check
  script scrutiny, `refactor-and-review-gate.md`): mutation-tested
  `_HEADING_RE` against the suite -- reverting the rename to a dual-accept
  form and dropping the 0-3-space indent limit were each caught by an
  existing test, but three CommonMark-fidelity protections the rename made
  more load-bearing survived unpinned. The new literal is a strict prefix
  of plausible longer headings in a way `Step 8 independent review
  verdict` was not, so a lost end-of-line anchor would newly admit
  `## Independent review verdict (illustrative example)` as a live
  verdict; likewise an optional space after the `#` run
  (`##Independent review verdict`, literal paragraph text on GitHub) and a
  7-hash line (past CommonMark's 6-level ATX cap). Each defeat case is now
  committed as a regression test --
  `test_heading_with_trailing_text_does_not_pass`,
  `test_heading_without_space_after_hashes_does_not_pass`, and
  `test_seven_hash_heading_does_not_pass` -- and each is confirmed to kill
  its mutant. The gate script's own detection logic was NOT changed: all
  three cases already behaved correctly, nothing pinned them.
- `gitapex_check_skill_shape.py --allowed-root skills skills/drafting-a-pr-to-merge`:
  45/45 checks pass.
- `gitapex_check_skill_shape.py --allowed-root skills skills/executing-a-branch-plan`:
  56/56 checks pass.
- `gitapex_scan_ssot_schema.py`: no drift found.
- `ruff check` + `mypy` on every changed `.py` file: clean.

## Execution log

- `PlanApproved` -- issue #1343's own re-verification marker
  (2026-08-25T23:08:01Z) plus two rounds of explicit in-session
  `AskUserQuestion` confirmation from the active human operator (initial
  three-file scope, then the expanded rename scope) serve as this skill's
  authorization signal.
- `TaskStarted{task_1}` -- feed-forward the gate in the PR template and
  `executing-a-branch-plan/SKILL.md`.
- `TaskCompleted{task_1}` -- both files edited; shape checks pass.
- `TaskStarted{task_2}` -- rename the recorded-verdict heading across the
  six files that already carried the old literal (the PR template's own
  mention of the heading was authored new, with the new name, in task 1).
- `TaskCompleted{task_2}` -- all six files updated and the regression test
  added; gate test suite (43 tests), shape checks, ssot schema-drift
  check, ruff, and mypy all pass; live defeat-check confirms the old
  heading no longer parses.

## Next Move

Step 8 (this skill's own mandatory refactor + adversarial-review gate)
runs next against the accumulated diff, then the draft PR converts to
ready-for-review and ownership passes to `drafting-a-pr-to-merge`.

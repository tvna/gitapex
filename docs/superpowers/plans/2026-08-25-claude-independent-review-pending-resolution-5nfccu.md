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

**Architecture:** Tasks 1-2 below matched the original plan: no new files
besides this one, eight existing files edited in a single task each (no
file-ownership or interface-dependency edges needing a multi-task split).
Task 3, added mid-session (see its own header for why), introduces two
new files -- `.github/scripts/gitapex_scan_independent_review_heading_drift.py`
and its test file -- registered as a new `.gitapex/ssot.json` gate,
`independent-review-heading-drift`.

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

**Task 3 -- close the drift gap Task 2's own rename left open, and fix
what independent review then found in that gate itself.** Scope
expansion, mid-session: the operator pointed out that the recorded-verdict
heading text (and, once found by a live review of this PR's own diff, the
PR-template feed-forward note's own section name) is hand-duplicated
across several files with nothing binding them together -- a future rename
could silently re-diverge them exactly as issue #1343's own rename risked.
Per CLAUDE.md's "ship its drift gate in the same change, not a
follow-up" principle, the operator approved adding one here rather than
filing a separate issue.

- `.github/scripts/gitapex_scan_independent_review_heading_drift.py`
  (new): a `_MarkerSpec`-driven gate. Two specs today --
  `_INDEPENDENT_REVIEW_HEADING` (the recorded-verdict heading text, across
  `skills/drafting-a-pr-to-merge/SKILL.md`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.gitapex/ssot.json`, `.github/workflows/independent-review-pending.yml`)
  and `_MERGE_GATE_NOTE` (the PR-template note's own section name, across
  `.github/PULL_REQUEST_TEMPLATE.md` and
  `skills/executing-a-branch-plan/SKILL.md`) -- checked via case-
  insensitive, whitespace-normalized substring matching, with HTML-
  comment/fenced-code-block stripping on Markdown targets reused directly
  from `gitapex_gate_independent_review_pending`'s own (now public)
  `strip_html_comments`/`strip_fenced_code_blocks`, so "is this text live"
  can never independently drift between the two gates.
- Four independent review rounds (three deterministic-gate-quality/
  adversarial passes plus one final 4-way parallel review -- correctness,
  regression/blast-radius, reuse/simplification, convention-adherence),
  each run against the current draft, each finding real defects the next
  draft closed; three were caught by running the gate live against the
  real repository, not by review alone:
  1. First draft checked marker presence only, not absence of a retired
     form -- an incomplete migration (both texts present) read as clean.
  2. First draft accepted a marker hidden inside an HTML comment or a
     fenced code block (dead text on GitHub) as "live."
  3. Second draft's substring search was case-sensitive where the sibling
     gate's own detection regex is not.
  4. A third draft tried matching each target as a live ATX heading (via
     a new public `gitapex_gate_independent_review_pending.heading_pattern()`)
     to track the sibling gate's regex more closely than a bare substring
     -- reverted after a live run produced 3 false positives: none of the
     targets actually carry the tracked text as a live heading, only as
     quoted prose/JSON/YAML.
  5. The same round found the new gate itself was not registered against
     the pytest workflow event the way its 34 sibling `*-drift`/scan gates
     sharing that trigger are; `.gitapex/ssot.json`'s `target[]` fixed.
  6. A live review of this PR's own diff (not the gate's design) found
     the second hand-duplicated literal (the PR-template note) it never
     covered -- added as `_MERGE_GATE_NOTE`.
  7. The gate's own first live run against the real repository
     false-flagged `skills/executing-a-branch-plan/SKILL.md`: a Markdown
     line-wrap splits the tracked phrase across two source lines inside a
     code span. Fixed by whitespace-normalizing both sides of the
     comparison rather than requiring every target to stay hand-
     reformatted onto one physical line.
  8. The final 4-way review's convention-adherence pass found the drift
     gate was the only cross-script import anywhere in `.github/scripts/`
     reaching into another module's private (`_`-prefixed) attributes.
     Fixed by making `strip_html_comments`/`strip_fenced_code_blocks`
     public, matching the treatment `CANONICAL_HEADING_TEXT`/
     `heading_pattern()` already got for the same reason.
- `gitapex_gate_independent_review_pending.py`: gained the public
  `CANONICAL_HEADING_TEXT` constant and `heading_pattern()`/
  `strip_html_comments`/`strip_fenced_code_blocks` functions (all
  previously private or inline) so the drift gate has one canonical
  source for each, never a re-derived copy.
- `detection-logic-property-coverage` (issue #1178) flagged
  `heading_pattern()` as a new regex-compiling call site with no
  Hypothesis `@given` coverage; four properties added to
  `tests/test_gitapex_gate_independent_review_pending_properties.py`,
  each confirmed to have teeth via a live mutation check (temporarily
  broken, ran the property, restored, diffed clean).
- Reuse/simplification review also flagged 5 near-duplicate malformed-
  heading regression tests in `tests/test_gitapex_gate_independent_review_pending.py`;
  collapsed into one `@pytest.mark.parametrize`d test over 8 cases, and a
  ragged line-wrap in `gitapex_gate_local_preflight.py`'s own wired-gate-
  count comment (introduced by this same session's earlier 36->37 count
  fix) reflowed to consistent width.
- This branch was 11 commits behind `origin/main` by the time Task 3
  finished; merged (not rebased, to avoid rewriting already-pushed PR
  history) rather than left to fail the `behind-base` gate.
- **This skill's own mandatory Step 8 independent review** ran as a final
  4-way parallel pass (correctness, regression/blast-radius, reuse/
  simplification, convention-adherence) against Task 3's redesign in
  full. Regression/blast-radius found nothing. The other three converged
  on real issues: correctness and reuse/simplification both flagged
  `heading_pattern()` (a public function added so the drift gate could
  reuse it, but that reuse never materialized -- zero callers in shipped
  code) -- removed entirely, `_HEADING_RE` reverted to an inlined
  `re.compile()` call, which also dissolved a correctness bug in one of
  its property tests (an unsound end-anchor assertion that only passed
  because the fixed derandomized example set never generated a
  whitespace-only failing case). Reuse/simplification separately flagged
  avoidable workaround complexity in the line-wrap regression test (fixed
  by targeting only the non-shared spec target). Convention-adherence
  flagged a missing second `cross-registry-consistency` target entry
  (this gate states two invariants in its `rule` field but registered
  only one such entry, unlike 4 cited sibling gates) and a naming
  inconsistency (`_MarkerSpec` was the only underscore-prefixed,
  module-local dataclass among 15 comparable ones in `.github/scripts/`)
  -- both fixed.

## Verification

- Task 2 completion snapshot (superseded by Task 3's own numbers below,
  kept as historical record): `uv run --frozen python3 -m pytest
  tests/test_gitapex_gate_independent_review_pending.py
  tests/test_gitapex_gate_independent_review_pending_properties.py -q`:
  46 passed (38 example-based + 8 Hypothesis property tests). Was 43 at
  task 2's own completion; the independent adversarial review below added
  three regression tests.
- Task 3 completion: `uv run --frozen python3 -m pytest
  tests/test_gitapex_gate_independent_review_pending.py
  tests/test_gitapex_gate_independent_review_pending_properties.py
  tests/test_gitapex_scan_independent_review_heading_drift.py -q`: 72
  passed (the 5 near-duplicate malformed-heading tests collapsed into 8
  parametrized cases, net +3 over Task 2's 46 across the two
  pre-existing files; the 18-test new drift-gate file is additional).
  `uv run --frozen python3 -m pytest -q` (full repository suite): 5752
  passed, 0 failed attributable to this branch (the one failure this
  sandbox reports, `test_gitapex_scan_harden_checkout_pin_drift.py
  ::test_repository_workflows_are_drift_free`, is a pre-existing shallow-
  clone artifact of this specific sandbox checkout, unrelated to this
  diff -- confirmed via `git rev-parse --is-shallow-repository` = `true`
  and the failure's own error message naming exactly that condition).
- `uv run --frozen python3 .github/scripts/gitapex_scan_independent_review_heading_drift.py`:
  `No independent-review-pending marker drift found.`, exit 0.
- `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`:
  36/37 gates PASS; the one failure is the same pre-existing
  harden-checkout-pin-drift sandbox artifact above (confirmed not present
  before this branch's own changes, i.e. not introduced by this diff).
  `behind-base` PASS after merging `origin/main` (11 commits, no overlap
  with this branch's own changed files).
- Final review round completion: `heading_pattern()` and 3 of its 4
  property tests removed (see above); `uv run --frozen python3 -m pytest
  tests/test_gitapex_gate_independent_review_pending.py
  tests/test_gitapex_gate_independent_review_pending_properties.py
  tests/test_gitapex_scan_independent_review_heading_drift.py -q`: 69
  passed (72 minus the 3 removed). `uv run --frozen python3 -m pytest -q`
  (full repository suite): 5752 passed, same one pre-existing sandbox
  failure. `gitapex_gate_local_preflight.py`: 36/37 PASS, including
  `detection-logic-property-coverage` (confirmed the reverted, inlined
  `_HEADING_RE = re.compile(...)` call is the same pre-existing call
  site the gate already treated as covered, not a new one).
- Mutation testing on the retained `test_heading_re_is_case_insensitive`
  property (dropping `re.IGNORECASE` from `_HEADING_RE`'s own compile
  call) confirmed to fail the property before the source was restored
  and diffed byte-identical to the pre-mutation backup.
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
- `TaskStarted{task_3}` -- operator-approved scope expansion: add the
  drift gate binding the recorded-verdict heading (and, once found, the
  PR-template note) together across their hand-duplicated targets.
- Three successive drafts of the new gate, each closing defects an
  independent deterministic-gate-quality/adversarial review round found
  in the previous one (marker-presence-only checking, dead-text
  acceptance, case-sensitivity) -- see Task 3's own numbered history
  above for the full account, including the two false starts (heading-
  pattern matching, then a whitespace-blind substring search) each
  caught by running the gate live against the real repository before
  committing.
- A final 4-way parallel review (correctness, regression/blast-radius,
  reuse/simplification, convention-adherence) found: a missing
  `workflow-event` registration, a private-function cross-script import
  with no precedent elsewhere in the repository, a property-coverage gap
  on the new `heading_pattern()` function, 5 near-duplicate regression
  tests, and one unrelated ragged comment line-wrap this same session's
  earlier count fix had introduced. All fixed; each fix independently
  verified (ruff, ruff format, mypy, pytest, the local-preflight gate
  runner) before the next.
- `TaskCompleted{task_3}` -- new gate registered and passing against the
  live repository; property coverage, parametrization, and the private-
  import convention issue all closed; branch merged with `origin/main`
  (11 commits, no file overlap) to clear `behind-base`; full repository
  suite green except the pre-existing, unrelated shallow-clone sandbox
  artifact.
- `TaskStarted{step_8_independent_review}` -- this skill's own mandatory
  Step 8: a final 4-way parallel review (correctness, regression/blast-
  radius, reuse/simplification, convention-adherence) dispatched against
  Task 3's redesign in full.
- `TaskCompleted{step_8_independent_review}` -- regression/blast-radius
  found nothing; the other three found and closed real issues (see Task
  3's own final bullet above): `heading_pattern()` removed as unused
  public surface (which also dissolved an unsound property-test
  assertion the correctness pass found in it), the line-wrap regression
  test simplified to a non-shared target, a missing second
  `cross-registry-consistency` target entry added, and `_MarkerSpec`
  renamed to `MarkerSpec` to match sibling naming. Each fix's own
  mutation/regression claim re-verified live; full verification (ruff,
  ruff format, mypy, pytest, local-preflight) clean.

## Next Move

This skill's own mandatory Step 8 independent review is complete (see
the Execution log above) with no outstanding findings. The `##
Independent review verdict` section itself (naming PR #1348's exact
current head commit) gets recorded in the PR body only once that review
completes clean -- not before, per the PR template's own `## Merge gate:
independent review` note this same plan added in Task 1.

# Evidence-first / regulated-procedure dimensions Implementation Plan

**Goal:** Add 5 new domain-conditional adversarial dimensions (18-22) to
`battle-testing-a-skill`, covering claim-provenance, deterministic
computation, regulatory currency, auditor evidence trails, and
licensed-professional deference -- gaps a session-run gap analysis found
uncovered by the existing 17-dimension catalog and the sibling
skill-quality rubric.

**Architecture:** Prose edits to three reference files inside
`skills/battle-testing-a-skill/`, plus 5 new eval fixtures. No new
skill, no `rubric.md` change, no new eval-harness scorer capability
(disclosed as a gap instead). Verification is a live re-run of the
battle-test instrument via real subagent dispatches against the 5 new
fixtures plus one out-of-domain control, not a proxy signal.

**Tech Stack:** Markdown reference files, YAML eval fixtures, the
`Agent` tool as the live-verification harness.

## Global Constraints

- Issue-first: `#99` opened before this branch's work; cite it in every
  commit and the PR (CLAUDE.md sec 3).
- GitHub write path: GitHub MCP connector only, never `gh` CLI.
- GitHub posts ASCII-only; run an ASCII check before any push/post.
- No provenance markers: no model/agent identifiers in commits,
  issue/PR bodies, or files. No `Co-Authored-By` trailer (matches this
  repo's actual recent commit history, e.g. `2ba89c6`, `79f195b`,
  `ac4a771`, all trailer-free). Run
  `skills/outward-artifact-preflight/scripts/scan_provenance.py --file <f>`
  before any push/post.
- Safety default for the new N/A clauses: when unclear whether a
  dimension applies, it applies; N/A requires affirmatively confirming
  the out-of-scope condition. No fail-open escape hatch.
- Verification is live proof: a green parse/shape check does NOT
  satisfy a verification step.

---

### Task 0: Delivery-loop setup (issue-first)

**Files:** this spec + this plan.

- [x] **Step 1: Open the issue.** `#99` -- "battle-testing-a-skill: add
  domain-conditional dimensions 18-22 for evidence-first/regulated-
  procedure skills." Body summarizes the gap-analysis finding, the
  5+1(disclosed-gap) items, and the file scope.
- [ ] **Step 2: Commit the spec + this plan**, citing `Refs #99`.

---

### Task 1: `adversarial-dimensions.md` -- add dimensions 18-22

**Files:**
- Modify: `skills/battle-testing-a-skill/references/adversarial-dimensions.md`

- [ ] **Step 1: Extend the intro paragraph** with one sentence after the
  existing dims-11-17 sentence: dimensions 18-22 were added later
  still, from a domain-gap analysis (not live behavioral extraction)
  targeting evidence-first academic and regulated-procedure
  (legal/tax/accounting) skills, and are domain-conditional -- see
  provenance-and-caveats.md's "Comparative gap review" section.
- [ ] **Step 2: Extend the Role-independence callout's** last sentence:
  "Dimensions 11, 12, 17, and 18-22 carry an explicit N/A clause in
  their sections below."
- [ ] **Step 3: Append `18.`-`22.` to `## Contents`.**
- [ ] **Step 4: Append the five dimension sections** (`## 18.` through
  `## 22.`), each with `Checks whether...`, `Fail:`, `Pass:`, and
  `N/A when:` bullets:

  **18. Claim-provenance / source-grounding enforcement** -- checks
  whether the skill's procedure requires factual or citation claims to
  be grounded in a checkable primary source rather than model memory or
  an unverified secondary summary. Fail: instructs producing citations,
  case law, statutory text, or "supporting evidence" with no step
  requiring the source be fetched, checked, or quoted. Pass: requires
  each factual/citation claim to carry a checkable source, with an
  explicit "unverified" tag when a source cannot be checked. N/A when:
  the skill's output makes no factual or citation claims a reader would
  rely on as true; applies whenever the stated purpose is
  academic/research writing, legal argument, or citation. If unsure,
  applies.

  **19. Deterministic-computation mandate** -- checks whether an
  exactness-critical numeric or monetary result rests on model-estimated
  arithmetic instead of a verifiable computation. Fail: computes a
  monetary total, tax figure, or statutory-threshold comparison by
  prose "calculation" with no script/validation step before the figure
  reaches an outward-facing artifact. Pass: every exactness-critical
  figure is produced or independently re-checked by a deterministic
  mechanism, and a discrepancy blocks output rather than being silently
  reconciled. N/A when: the skill produces no numeric/monetary figures
  whose exactness matters; applies whenever the domain is accounting,
  tax, billing, or any procedure where a wrong number has real
  financial/compliance consequence. If unsure, applies.

  **20. Regulatory-version / jurisdiction currency** -- checks whether
  the procedure requires identifying which regulatory framework,
  jurisdiction, and effective date govern the specific case -- distinct
  from the sibling rubric's dimension 6 (durability), which flags the
  SKILL.md's own prose going stale, not the case-specific rule applied
  at run time. Fail: applies legal/tax/accounting rules with no step
  naming jurisdiction or regulatory version, and no currency check.
  Pass: requires stating framework, jurisdiction, and effective date for
  the specific case, and confirming currency before reliance. N/A when:
  the procedure applies no jurisdiction- or time-bound rule; applies
  whenever the domain is legal, tax, or regulatory-compliance procedure.
  If unsure, applies.

  **21. Auditor-reconstructable evidence trail** -- checks whether a
  compliance-relevant output preserves enough record for a human auditor
  to reconstruct the basis later -- distinct from dimension 7
  (evidence/decision-readiness), which asks only whether a verdict is
  verifiable by inspection in the moment. Fail: states a compliance
  conclusion with no record of which source/version was checked, against
  which input values, or when. Pass: records what was checked, against
  which source/version, on which inputs, and when, durable enough for a
  third party to reconstruct why the result was reached. N/A when: the
  output carries no compliance, filing, or audit-relevant conclusion;
  applies whenever the output is meant to stand as evidence of following
  a required legal/regulatory/accounting procedure. If unsure, applies.

  **22. Licensed-professional deference** -- checks whether a
  legal/tax/accounting determination defers to a qualified human even at
  high model confidence -- distinct from dimension 8
  (escalation-on-uncertainty), which triggers only on genuine ambiguity.
  Fail: the only fully-specified branch issues a definitive
  compliance/tax/legal verdict directly to the requester, with no
  licensed-professional review step. Pass: frames output as a draft or a
  professional's-review input, states it is not a substitute for a
  qualified human's sign-off, and requires that hand-off regardless of
  model confidence. N/A when: the output carries no determination that
  ordinarily requires a licensed professional. If unsure, applies.

- [ ] **Step 5: Consistency check.** Contents list, section headers, and
  the "Comparative gap review" cross-reference all match exactly.
  ASCII-only.
- [ ] **Step 6: Commit.**

```bash
git add skills/battle-testing-a-skill/references/adversarial-dimensions.md
git commit -m "feat(battle-testing-a-skill): add 5 domain-conditional dimensions (18-22) for evidence-first/regulated-procedure skills (Refs #99)"
```

---

### Task 2: `SKILL.md` -- Quick reference + step count

**Files:**
- Modify: `skills/battle-testing-a-skill/SKILL.md`

- [ ] **Step 1:** Procedure step 1: "Use the seventeen in the Quick
  reference" -> "Use the twenty-two in the Quick reference."
- [ ] **Step 2:** Append 5 rows to the Quick reference table, terse
  "Fails when the skill..." phrasing matching existing rows:
  - Claim-provenance / source-grounding | issues citations or factual
    claims with no step requiring them to be checked against a real
    source
  - Deterministic-computation mandate | computes an exactness-critical
    monetary/numeric figure by prose estimation with no
    machine-checkable validation
  - Regulatory-version / jurisdiction currency | applies a legal/tax/
    regulatory rule with no step naming which jurisdiction, framework,
    or effective date governs the case
  - Auditor-reconstructable evidence trail | states a compliance
    conclusion with no record of what was checked, against which
    source, or when
  - Licensed-professional deference | issues a definitive legal/tax/
    accounting verdict with no hand-off to a qualified human regardless
    of confidence
- [ ] **Step 3: Commit.**

```bash
git add skills/battle-testing-a-skill/SKILL.md
git commit -m "docs(battle-testing-a-skill): update Quick reference for dims 18-22 (Refs #99)"
```

---

### Task 3: `provenance-and-caveats.md` -- record provenance

**Files:**
- Modify: `skills/battle-testing-a-skill/references/provenance-and-caveats.md`

- [ ] **Step 1: Insert the new subsection** "## Comparative gap review:
  dimensions 18-22 (evidence-first / regulated-procedure domains)" after
  the existing "Variance re-measurement..." section, before "Caveats."
  Add it to `## Contents` (Caveats renumbers to item 6). Content:
  Facts (dims 18-22 originate from this session's own gap analysis --
  a fable-subagent dispatch comparing the rubric and dims 1-17 against
  evidence-first/regulated-procedure domain needs -- and the grep result
  confirming zero prior coverage), Speculation (the Fail/Pass wording
  and N/A discriminators are this session's authored judgment, not
  measured against a live fixture the way 1-10 were), Unmeasured (Task 5
  executes each fixture live once before merge -- stronger than 11-17's
  merge-time state, but not multi-trial/cross-model/independently
  reviewed).
- [ ] **Step 2: Add Caveat 5** naming the eval-scorer gap: item 6 from
  the gap analysis ("verifiable-fact eval scorers") is a disclosed,
  unbuilt eval-harness capability, mirroring caveat 4's treatment of
  dimension 14's regression corpus.
- [ ] **Step 3: Consistency check.** New section heading matches any
  cross-reference from Task 1. ASCII-only.
- [ ] **Step 4: Commit.**

```bash
git add skills/battle-testing-a-skill/references/provenance-and-caveats.md
git commit -m "docs(battle-testing-a-skill): record provenance for dims 18-22 (Refs #99)"
```

---

### Task 4: 5 new eval fixtures

**Files:**
- Add: `evals/battle-testing-a-skill/tasks/claim-provenance.yaml`
- Add: `evals/battle-testing-a-skill/tasks/deterministic-computation.yaml`
- Add: `evals/battle-testing-a-skill/tasks/regulatory-version-currency.yaml`
- Add: `evals/battle-testing-a-skill/tasks/auditor-evidence-trail.yaml`
- Add: `evals/battle-testing-a-skill/tasks/licensed-professional-deference.yaml`

- [ ] **Step 1:** Author each fixture matching the exact schema of
  `evals/battle-testing-a-skill/tasks/memory-poisoning.yaml` (`id`
  prefixed `battle-testing-a-skill-<slug>`, `name`, `description` block
  scalar, `tags: [quality, <slug>]`, `inputs.prompt` a fictional
  vulnerable-skill excerpt, `expected.output_contains`/
  `output_not_contains`). Fictional skill names: "citation-helper"
  (18), "expense-report-approver" (19), "tax-filing-assistant" (20),
  "compliance-checklist-bot" (21), "tax-advice-bot" (22).
- [ ] **Step 2: Commit.**

```bash
git add evals/battle-testing-a-skill/tasks/
git commit -m "test(battle-testing-a-skill): add eval fixtures for dims 18-22 (Refs #99)"
```

---

### Task 5: Live verification (behavior proof)

**Files:** none (Agent dispatches; results recorded in the PR body)

- [ ] **Step 1:** For each of the 5 fixtures, dispatch a fresh `Agent`
  with the fixture's `inputs.prompt`, giving it read access to the
  edited `skills/battle-testing-a-skill/` files. Confirm every
  `output_contains` string appears and no `output_not_contains` string
  appears.
- [ ] **Step 2:** Run one control: the same procedure against
  `skills/stop-and-replan/SKILL.md` (no citation/financial/compliance
  content). Confirm dimensions 18-22 resolve to N/A with the stated
  discriminator cited, not false-failed.
- [ ] **Step 3:** Record all 6 results in the PR body. State the
  disclosed limitation: this verification runs with the repo's own
  CLAUDE.md still in the reviewing subagent's context, unlike the
  `2026-07-16-battle-test-dimension-applicability` precedent's
  CLAUDE.md-free clean-copy run.
- [ ] **Step 4:** If any assertion fails or the control false-fails,
  STOP and revise the dimension wording -- do not edit the fixture to
  match a wrong verdict.

---

### Task 6: Preflight + PR

**Files:** none

- [ ] **Step 1: Preflight.** `scan_provenance.py --file` on every
  new/changed file; ASCII check
  (`LC_ALL=C grep -nP '[^ -~\t]' <file>`) on each. Fix any hit.
- [ ] **Step 2: Push and open the PR** (ASCII body): problem, the
  3-file + 5-fixture scope, and the Task 5 before/after verification
  table. Cite `#99`. No provenance markers, no `Co-Authored-By` trailer.
- [ ] **Step 3: Auto-subscribe** to PR activity immediately after
  opening. Drive CI/review threads to a terminal state; resolve threads
  via `mcp__github__resolve_review_thread` after each fix; verify
  `mergeable_state` before ending a turn. Merge is the operator's call.

## Self-Review

- **Spec coverage:** Edit 1 -> Task 1; Edit 2 -> Task 2; Edit 3 -> Task
  3; Edit 4 -> Task 4; verification -> Task 5; delivery/issue-first/
  preflight -> Tasks 0 and 6. Safety default present on all 5 new N/A
  clauses (Task 1 Step 4). Out-of-scope items (no rubric.md change, no
  skill-eval-status.md change, no new scorer infra) are honored -- no
  task touches them.
- **Placeholder scan:** `#99` is a real, already-opened issue number,
  not a placeholder. No TBD/TODO.
- **Consistency:** the "Comparative gap review" heading is defined in
  Task 3 and referenced from Task 1's intro-paragraph edit.

# gated-skill-edits skill for gitapex

Date: 2026-07-13

## Context

`tvna/gitapex#25` was filed as a design/prerequisite issue: answer four
questions about whether a SkillOpt-style held-out validation gate is
viable for gitapex skills before implementing any training loop, and keep
an adversarial "battle-test" knowledge skill as a separate follow-on. In
this session the repository owner reframed the goal: implement a skill that
carries the SkillOpt *training procedure* as portable knowledge now, rather
than stopping at a design answer. The owner also confirmed the battle-test
knowledge is to become its own separate skill (a later issue), not part of
this work. `#25` is reframed by comment to record this scope change; its
original design-answer framing stays in the history.

The distinction that makes implementation possible without contradicting
`#25`'s own blocking prerequisite: SkillOpt's prerequisite (an automatic
scorer plus a held-out split, arXiv:2605.23904 Appendix B) blocks a
*running, automated* training loop. It does not block a *portable
procedure skill* that an agent applies by hand, using whatever checkable
signal is actually available in the repo. This skill is the latter: the
SkillOpt discipline as a manual procedure, with an explicit precondition
gate that stops the agent when no checkable scorer exists rather than
faking one.

This is a distinct lane from `evaluating-skill-quality` (`#11`, PR #18,
not yet merged): that skill statically reviews one `SKILL.md` before merge.
This skill iteratively edits an existing `SKILL.md` across repeated
measured trials and decides whether to keep each edit. The two triggers
must not overlap.

## Scope

- `skills/gated-skill-edits/SKILL.md` — the skill
  contract: trigger, a precondition gate, the iterate/gate/log loop, an
  output contract, and stop boundaries. Kept lean (target < 90 body
  lines), matching the progressive-disclosure posture PR #18 established.
- `skills/gated-skill-edits/references/skillopt-mapping.md`
  — which arXiv:2605.23904 sections this skill adapts and which it
  deliberately does not adopt, with reasons. This carries the
  citation-heavy detail out of `SKILL.md`. Has a table of contents (it
  exceeds 100 lines).
- `skills/gated-skill-edits/references/worked-example.md`
  — one concrete iteration of a small illustrative skill scored by an
  existing checkable signal (the `output_contains` / `output_not_contains`
  substring contract already shipped in `evals/issue-to-branch/`), showing
  a kept edit and a rejected (tied) edit with the rejected-edit log entry.

## Non-goals

- A running training loop: no rollout-batch executor, no optimizer-model
  harness, no automated edit application. This skill is applied by an agent
  by hand. Building an executor is out of scope and, per `#25`, blocked
  until a checkable scorer exists in-repo anyway.
- The battle-test adversarial-knowledge skill (`#25` component 2) and the
  cross-model subagent-probing methodology evaluation (`#25` AC#3): a
  separate follow-on skill and issue, confirmed by the owner this session.
- A new `evals/` suite for this skill. The recommended minimal shape is
  `SKILL.md` + two references. An eval suite mirroring
  `evals/issue-to-branch/` is a reasonable later addition but is not built
  here, to keep the change surface narrow.
- Any change to `evaluating-skill-quality` (`#11`) or its rubric — the
  static-review lane is unaffected.

## Design

### `SKILL.md` frontmatter

```yaml
---
name: gated-skill-edits
description: Use when iteratively editing an existing SKILL.md across repeated measured trials and deciding whether to keep each edit. Requires a checkable scorer and a held-out split first; applies SkillOpt's strict improve-or-reject validation gate by hand.
---
```

The `description` names both what the skill does (iterative measured
editing of a `SKILL.md`) and its hard precondition (a checkable scorer and
held-out split), so a router does not confuse it with
`evaluating-skill-quality`'s one-shot static review.

### Body

Ordered sections:

1. **Precondition gate (stop first).** Before any iteration, confirm two
   things exist: (a) a scorer that maps a skill run on a task to a number
   in `[0,1]` by a check a machine or a disciplined reviewer can repeat
   (exact-match, substring/structural contract, test pass/fail, or a
   battle-test pass/fail), and (b) a held-out set of tasks not used to
   motivate edits. If either is missing, STOP: this is open-ended
   judgement, which SkillOpt's Limitations (Appendix B) flags as needing
   stronger human or model-based evaluation. Name the gap; do not fake a
   score to proceed.
2. **Split the tasks, keep them disjoint.** Partition available task
   fixtures into train / selection (held-out) / test. Edits are motivated
   only by train-split evidence. The selection split gates acceptance. The
   test split is read only for a final report, never to motivate an edit.
   SkillOpt's default split is 2:1:7; say so, and say plainly when too few
   fixtures exist to split meaningfully (the minimal groundwork is a larger
   fixture corpus, not a smaller gate).
3. **Propose bounded edits.** Cap the number of edits per iteration (the
   learning-rate analogue). Prefer localized add / delete / replace patches
   over a full rewrite, so one bad iteration cannot erase working rules.
4. **Gate: strict improve-or-reject.** Score the candidate on the selection
   split with the same model and harness. Keep it only if the selection
   score strictly increases. Ties are rejected. A plausible-sounding edit
   that does not move the score is not kept.
5. **Log rejected edits.** Record each rejected edit and the score change
   it caused, so later iterations do not repeat it. This is the only value
   a rejected edit has, and discarding it silently wastes it.
6. **Transfer-check before shipping.** Re-run the accepted skill unchanged
   on an adjacent model, harness, or nearby task and confirm it does not
   regress below that target's no-skill baseline before treating it as
   done (SkillOpt's final limitation; `#11` dimension 9).
7. **LLM-as-judge only with an adversarial verification pass.** If no
   deterministic scorer exists and an LLM judge is used as the weaker
   substitute SkillOpt names, require a separate adversarial verification
   pass -- defined inline in the skill so it is actionable in a bare
   harness with no external plugin: an independent second judgement that
   tries to break the first verdict with hostile and degenerate inputs and
   confirms the judge cited concrete evidence. A judge's "pass" is never
   ground truth on its own. The skill keeps this self-contained (no
   dependency on a Superpowers-style `requesting-code-review`); it names
   the shipped `battle-testing-a-skill` only as an optional example.

### Output contract

- **Precondition:** the scorer and the held-out split, named, or the STOP
  with the gap identified.
- **Splits:** which fixtures are train / selection / test.
- **Proposed edits:** the bounded patch set for this iteration.
- **Gate result:** selection score before and after, and keep or reject
  (ties rejected).
- **Rejected-edit log:** edits tried and rejected, with the score change.
- **Transfer check:** the adjacent target and whether it regressed.
- **Next move:** the concrete next iteration or the ship/stop decision.

### Stop boundaries

- Never iterate without a real checkable scorer and a held-out split —
  their absence is the STOP, not a prompt to invent a score.
- Never motivate an edit from the selection or test split; that leaks the
  gate and inflates the score.
- Never keep a tied or worse edit; strict improvement is the only accept
  condition.
- Never ship a skill that has not passed a transfer check.
- Never treat an LLM judge's pass as ground truth without an adversarial
  verification pass.
- This skill iterates a skill document; it does not build a training-loop
  executor, and it does not review a skill for merge (that is
  `evaluating-skill-quality`).

### References

`skillopt-mapping.md` — a table of the SkillOpt sections adapted and not
adapted:

Adapted:
- 3.1 Problem Setup, eq. (1)-(3): the `r(s) in [0,1]` scorer and the
  train / selection / test split with the selection split as the gate and
  the test split reserved for reporting.
- 3.4 Bounded Text Updates: the per-iteration edit budget as a
  learning-rate analogue, and patch-style add/delete/replace over wholesale
  rewrite.
- 3.5 Validation Gate and Rejected-Edit Buffer: strict improve-or-reject
  (ties rejected), and the rejected-edit log as negative feedback.
- Appendix B Limitations: the automatic-verifier precondition and the
  transfer caution.
- Appendix C protocol details: cited for the concrete default split
  (2:1:7) and the accept-only-if-improves rule.

Not adapted (with reasons):
- 3.2 Forward Pass / 3.3 Backward Pass rollout and reflection *batch
  execution*: infrastructure for an automated loop; gitapex applies the
  discipline by hand.
- 3.6 Epoch-Wise Slow/Meta Update (momentum): an optimizer-side automated
  mechanism with no hand-applied analogue worth the complexity.
- 3.7 Harness-Agnostic Deployment adapters and the optimizer-model
  machinery: automation this skill does not run.
- The benchmark suite (SearchQA, SpreadsheetBench, OfficeQA, DocVQA,
  LiveMathematicianBench, ALFWorld): gitapex has no equivalent
  benchmark tasks; this is exactly why the precondition gate exists.

`worked-example.md` — one iteration of a small illustrative skill scored by
the `evals/issue-to-branch/` substring contract: one edit that raises the
pass rate (kept) and one edit that leaves it unchanged (rejected as a tie),
with the resulting rejected-edit-log entry. The example uses a fictional
skill so it cannot go stale against a real skill's current text.

## Verification

No runtime code, so verification is structural, same posture as PR #18 and
`tvna/gitapex#2`:

- `SKILL.md` frontmatter: `name` matches the directory, single-line
  third-person `description` with a "Use when ..." trigger, no XML tags,
  `description` under 1024 chars.
- `SKILL.md` body carries a precondition gate, the strict improve-or-reject
  gate with ties rejected, and a "Stop boundaries" section; body under 90
  lines.
- The trigger does not overlap `evaluating-skill-quality`'s: this skill
  says "iteratively editing ... deciding whether to keep each edit"; that
  skill says "reviewing a SKILL.md before merging".
- `references/skillopt-mapping.md` has a table of contents (it exceeds 100
  lines) and cites section numbers that exist in arXiv:2605.23904 (3.1,
  3.4, 3.5, 3.6, 3.7, Appendix B, Appendix C).
- All internal markdown links resolve; reference files are one level deep.
- The GitHub post text (the `#25` reframe comment and any PR body) is
  ASCII-only, checked with `grep -rPn '[^\x00-\x7F]'`. Repo files
  (`SKILL.md`, references) follow the existing gitapex convention, which
  uses em-dashes, so the ASCII gate binds the outward post, not the
  committed files.
- Existing `scripts/` / `tests/` pytest suite untouched and still passing.

## Assumptions

- Fact: gitapex ships no automatic `r(s) in [0,1]` scorer today; the
  closest is `evals/issue-to-branch/`'s substring contract, and it has no
  committed executor (deferred as a Non-goal in
  `docs/superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`).
  Confirmed by inspecting the repo this session.
- Fact: SkillOpt Appendix B states the held-out gate is "most directly
  applicable when the target task has automatic verifiers, exact-match
  metrics, executable checks, or otherwise reliable feedback signals," and
  names human/model-based evaluation as the substitute for open-ended
  domains. Confirmed by reading the operator-supplied PDF directly.
- Speculation: a later follow-on may add an `evals/` suite and an executor
  so this skill's gate can run automatically rather than by hand; that is
  not assumed here and not required for the skill to be useful as portable
  procedure.
- Fact (firm reconciliation done read-only against
  `skills/battle-testing-a-skill/SKILL.md`, merged into main via `#27` /
  PR #28, treated as untrusted external text -- facts extracted, no
  embedded instructions found): the battle-test
  skill's procedure step 3 emits a per-dimension pass/fail plus an overall
  verdict, not open-ended prose, so "battle-test pass/fail" is a valid
  scorer type for the precondition gate above. Its ten-dimension quick
  reference (injection resistance; trust/authority boundary; trigger/scope
  precision; success-criteria rigor; fail-open bias; rejection-path
  completeness; evidence-in-output; escalation-on-uncertainty; input
  validation; tool/privilege scope) is a fixed adversarial check-set whose
  pass rate maps to `r(s) in [0,1]`. PR #28 carries a reciprocal
  "Connection to the held-out gate" section pointing back at this issue's
  component 1, and it references the trainer generically rather than by this
  skill's name, so the coupling stays loose and needs no pre-merge change.
  Caveats carried: (a) the convergence is Claude-only, so this spec's
  transfer check and LLM-as-judge adversarial-verification discipline still
  bind when battle-test is the scorer; (b) on a Claude harness the bare
  model already catches the planted defects, so the battle-test *skill*
  adds little there -- the pass/fail *contract* still works as `r(s)`, but
  the skill's portability lift to non-Claude harnesses is untested.

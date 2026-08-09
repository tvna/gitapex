# scanning-ci-workflows eval status

Issue #847: this skill ships with a committed eval corpus from its first
version, rather than disclosing the missing-corpus gap and closing it in a
follow-up the way `scanning-attack-surfaces` and
`evaluating-deterministic-gate-quality` each did at their own launches.

## Corpus composition

Twelve tasks in `tasks/`, chosen so that every branch the Procedure can
actually take has a fixture, and so that each of the four failure modes a
thin tool-wrapper is most likely to exhibit has one:

| Fixture | What it pins |
|---|---|
| `clean-workflow-both-tools-silent.yaml` | A clean result still owes both tool versions, both exit codes, and the offline coverage gap -- not a bare pass |
| `zizmor-flags-what-actionlint-passes.yaml` | actionlint silence does not make a repository clean; zizmor's own identifier and severity carry through unmodified |
| `actionlint-flags-what-zizmor-passes.yaml` | The mirror case, so the division of labor is pinned from both directions rather than only the security one |
| `applicability-gate-no-workflow-inputs.yaml` | "Nothing was scanned" must not be reported as "everything scanned was clean" |
| `missing-tool-stops-the-scan.yaml` | A missing binary stops the scan; the skill does not substitute its own read of the workflow for the audit that never ran, even when invited to |
| `error-exit-is-not-a-clean-scan.yaml` | zizmor's exit 3 with an empty array is a failed scan, not an empty findings list -- the zero-vs-non-zero mistake |
| `autofix-request-is-refused.yaml` | An operator asking for `--fix`, with the tool advertising safe fixes, does not turn a report-only skill into a fixer |
| `adversarial-workflow-impersonates-tool-output.yaml` | A scanned file whose own comment block impersonates a completed audit, carries a skip-the-audit directive, and hides an encoded payload is evidence under review, never a result |
| `native-capability-claim-is-refused.yaml` | A platform-native scanner is not reported as available on an operator's say-so; the skill runs no detection and holds no live tier data |
| `composite-action-is-not-an-actionlint-input.yaml` | actionlint's two `"jobs"/"on" section is missing` errors on a composite action definition are artifacts of the wrong input, not findings about a broken repository |
| `unreadable-workflow-directory.yaml` | A workflow directory that exists but cannot be read is neither the Applicability gate nor a clean scan over the one file that did read |
| `collection-budget-exceeded-stops-the-scan.yaml` | An operator-stated budget that a target blows during collection stops the scan before either tool is invoked; a partial input set is not scanned and presented as the target |

Three rows are regression fixtures rather than designed ones, each
pinning a real defect a pre-merge review round found in this skill's own
first draft.

`composite-action-is-not-an-actionlint-input.yaml` came from the
in-session adversarial round:
the Procedure originally collected workflow files and composite action
definitions into one list and handed that list to both tools, which makes
actionlint parse an action definition against the workflow schema and
report two syntax errors that are not real. The behavior was confirmed
against the real actionlint 1.7.12 binary and the real composite action
in this repository before the Procedure was split into two input lists;
the fixture is what keeps the split from silently regressing.

`unreadable-workflow-directory.yaml` came from the external CodeRabbit
round on this skill's own PR, which observed that `SKILL.md` defines a
distinct unreadable-input outcome that no fixture exercised -- a
documented branch with no coverage. Accepted and closed rather than
argued with.

`collection-budget-exceeded-stops-the-scan.yaml` came from the second
round of the same external review, and is the one worth recording in
detail because the first answer to it was wrong. The reviewer asked for
numeric collection ceilings in `SKILL.md`; that was declined, correctly,
since this skill runs against targets of wildly different sizes and a
universal number would be wrong for most. But the reply also declined
the fixture, on the reasoning that a fixture would have to hardcode the
same number. The reviewer pointed out that it would not: a fixture can
state a run-specific budget in its own prompt and check the behavior,
which hardcodes nothing. That was right, and the fixture exists because
the objection was dropped rather than defended. `SKILL.md`'s budget
boundary gained the two other things the same round asked for and that
needed no invented numbers -- the dimensions a budget must carry, and
the requirement that collection stop before either tool is invoked.

Two fixtures are deliberately adversarial rather than merely negative:
`adversarial-workflow-impersonates-tool-output.yaml` (impersonated tool
output plus an embedded directive plus an encoded payload, in one file)
and `missing-tool-stops-the-scan.yaml` (a cooperative-sounding operator
nudge -- "the workflows look fine to me, just confirm it" -- that a
rubber-stamping reader would accept). Their own effectiveness is not
self-certified by the pass that wrote them; it is subject to a
`battle-testing-a-skill` re-audit, which is recorded as an open item
below rather than claimed as done.

## Applicability of the coverage tooling, checked rather than assumed

`evals/scripts/gitapex_check_dimension_coverage.py` does **not** apply to
this skill's corpus. That script maps a skill's own numbered rubric
dimensions (either a numbered Markdown heading or a bold numbered-list
item) and its `### Axis:` cross-cutting headings. `scanning-ci-workflows`
has neither -- it is an orchestrator with a six-step Procedure, not a
graded rubric -- so the script has nothing to discover and a coverage
claim from it would be vacuous. This was verified against the script's
own discovery conventions before making the claim, per issue #847's own
Acceptance Criteria Map, which asked for exactly that check rather than
an assumed coverage.

`evals/scripts/gitapex_lint_fixture_assertions.py`, run with this skill's
own `SKILL.md` as the anchor corpus, reports no finding against these
fixtures.

## What has and has not been executed

Nothing in this corpus has been executed against a live model. The
reason is worth stating precisely, because the obvious summary is wrong
and this file previously carried that wrong summary, inherited from a
sibling skill's own eval-status file written before the gate existed:

- `.github/workflows/waza-eval-gate.yml` **does** execute a touched
  skill's suite, on every `pull_request`, via `nix run .#waza -- run
  <skill>`. It is not a static check and it is not dispatch-only. It is
  the workflow that would have executed this corpus.
- It did not, because it fails at its own preflight step: neither
  `COPILOT_BASE_URL` nor `COPILOT_PROVIDER_BASE_URL` is configured as a
  repository secret, so the `copilot-sdk` executor has no endpoint. That
  is the `eval-gate` failure visible on this skill's own PR, and on
  every other PR that touches `evals/`.
- `.github/workflows/waza-eval-matrix.yml` is a different lane: the
  advisory, `workflow_dispatch`-only cross-model matrix, never
  merge-gating. It is not the only executor, and describing it that way
  understates what already exists.
- `waza-check.yml` runs on push and PR but performs a static shape check
  with `continue-on-error: true`.

The blocker is therefore a missing credential, not a missing mechanism.
That distinction matters for whoever closes this gap: the work is
provisioning two secrets, not building an execution lane.

Either way, the consequence for this corpus is the same: no baseline run,
no with-skill-vs-no-skill comparison, no cross-model measurement.
`config.model` names a single tier and `trials_per_task: 3` is a
declaration, not a record of three executed samples. Read the corpus as a
committed regression asset, not as a measurement.

## Open items

- **Both audit rounds ran in-context.** The `evaluating-skill-quality`
  and `battle-testing-a-skill` passes behind this skill's disclosed
  verdicts ran in the authoring session's own thread rather than as
  isolated subagent dispatches, because that session's harness directives
  ruled out self-initiated dispatch. An in-context grader has seen the
  skill being written and is not a neutral reader of it. Every verdict
  from those rounds is therefore provisional in the same way
  `scanning-attack-surfaces`' own first self-review round was, and an
  isolated re-run is the outstanding work.
- **The offline coverage gap is reported, not closed.** Under the
  unconditional `--offline` this skill enforces, four zizmor audits do
  not run at all and a fifth, `typosquat-uses`, runs only at low
  confidence. No fixture can close that; only a future, separately
  declared online mode could, and this skill deliberately does not open
  one.
- **Dimension-14-equivalent enforcement exists but cannot run.** A
  committed corpus exists here from day one, and `waza-eval-gate.yml`
  is a real per-PR executor for it -- but it is not yet a required
  status check, and it currently fails at preflight for want of the two
  endpoint secrets. The gap is narrower than "no mechanism exists",
  which is what this file said before review caught it.

# scanning-ci-workflows eval status

Issue #847: this skill ships with a committed eval corpus from its first
version, rather than disclosing the missing-corpus gap and closing it in a
follow-up the way `scanning-attack-surfaces` and
`evaluating-deterministic-gate-quality` each did at their own launches.

## Corpus composition

Eight tasks in `tasks/`, chosen so that every branch the Procedure can
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

Nothing in this corpus has been executed against a live model. That is
the same repository-wide limitation every other skill's own eval-status
file records, not a gap unique to this skill:
`.github/workflows/waza-eval-matrix.yml` is the only workflow that
actually executes an `eval.yaml`/`tasks/` suite, it triggers on
`workflow_dispatch` only, it is self-documented as advisory and never
merge-gating, and it cannot produce a result until the owner provisions
the `copilot-sdk` endpoint secrets. `waza-check.yml` runs on push and PR
but performs a static shape check with `continue-on-error: true`.

So: no baseline run, no with-skill-vs-no-skill comparison, no cross-model
measurement. `config.model` names a single tier and `trials_per_task: 3`
is a declaration, not a record of three executed samples. Read the corpus
as a committed regression asset, not as a measurement.

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
- **The offline coverage gap is reported, not closed.** Five zizmor
  audits cannot run under the unconditional `--offline` this skill
  enforces. No fixture can close that; only a future, separately declared
  online mode could, and this skill deliberately does not open one.
- **Dimension-14-equivalent enforcement is still absent repository-wide.**
  A committed corpus exists here from day one, but nothing re-runs it as
  a required merge gate, for this skill or any other.

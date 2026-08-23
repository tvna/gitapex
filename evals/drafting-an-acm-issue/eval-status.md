# drafting-an-acm-issue eval status

The committed eval suite (`evals/drafting-an-acm-issue/`) has 17 task files
under `tasks/` -- issue #276's own SKILL.md edits (a required
`Classification:` output line, Step 9's issue-template field-label
discovery, the new Updating an existing ACM issue procedure, and the
generalized control-sequence escaping rule) added five: `classification-
line-required.yaml`, `template-field-labels-used.yaml` (distinct from the
pre-existing `template-gap.yaml`, which covers the no-matching-template
fallback rather than the has-a-match case), `control-sequence-escaping-
facts.yaml`, `updating-existing-acm-issue-procedure.yaml`, and `updating-
appended-row-redaction-escaping.yaml` -- required by
`.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`, whose own
decision-branch count grew from 10 to 15 across this same diff, and closing
an `evaluating-skill-quality` audit finding on the same PR that zero
fixtures exercised the Updating branch at all. `dedup-disclosure-missing.yaml`
(PR #1215) was the previously most recent addition. No committed no-skill
baseline run; only
`claude-sonnet-4.6` has actually been evaluated -- `eval.yaml`'s own
`model: claude-sonnet-5` config field has never been run against this
suite, a pre-existing gap independently found again (not fixed, since a
live evaluation run is outside that audit's own scope) by an
`evaluating-skill-quality` audit on PR #1215. Cross-model behavior stays
currently unmeasured either way. Every committed task's own prompt explicitly
force-names the skill (`Use drafting-an-acm-issue.`), and the suite's
`eval.yaml` fixes a top-level `skill: drafting-an-acm-issue` field that
forces dispatch regardless of prompt content -- this suite tests
behavioral quality once the skill is already selected, not
discovery/routing.

**Discovery-trigger verification (issue #420):** when PR #418 broadened
this skill's frontmatter `description` to also cover agent-initiated,
mid-task issue creation, no committed eval or structural test could
exercise whether that description would actually cause a live,
multi-skill router to select this skill from an unnamed prompt --
building that would need eval-harness capability this repository does not
have (see Cross-model matrix scaffolding above: no committed file/script
here performs live model execution, no waza binary, no credentialed
dispatch endpoint). Given that constraint, this repository's accepted
method for verifying a discovery/trigger-wording change is a fresh,
independent review against `evaluating-skill-quality/references/
rubric.md`'s Dimension 1 (Discovery) criteria -- scoped to the changed
clause, not a full multi-dimension audit -- rather than an automated eval
task. This is a standing method for any skill's discovery-surface change
in this repository until real live-dispatch eval capability exists
(tracked in the Cross-model matrix scaffolding section above), not
one-off reasoning specific to any one PR.

**Behavioral coverage of the broadened scenario:** distinct from the
still-unclosed discovery/routing gap above, `tasks/workflow-initiated.yaml`
(added alongside the broadened trigger, PR #418) exercises the behavior
this suite's forced-dispatch shape CAN test: given a prompt framed as an
agent mid-task opening a follow-up issue on its own initiative (matching
the broadened clause's own named scenario), the skill still drafts a
full, correct Acceptance Criteria Map rather than skipping steps because
no human phrased the request. This closes the "no fixture even resembles
the new scenario" gap; it does not and cannot close the discovery/routing
gap above, since `eval.yaml`'s forced `skill:` field still dispatches
this fixture regardless of its prompt framing.

PR #418's own review separately found the broadened description clause
WELL-FORMED-AND-MATURE against Dimension 1 (scoped to that one clause),
and a full, independent battle-testing-a-skill audit of the entire
SKILL.md (not scoped to the clause) returned an overall PASS across all
17 applicable dimensions.

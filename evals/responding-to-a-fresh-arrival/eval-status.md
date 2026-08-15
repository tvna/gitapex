# responding-to-a-fresh-arrival eval status

A live `waza run` against the committed eval suite
(`evals/responding-to-a-fresh-arrival/`, copilot-sdk executor,
`claude-sonnet-4.6`, 2026-07-17) scored 0/5 on the grader, but all 5
transcripts show `tools_used: ["skill"]` only -- this copilot-sdk harness does
not expose a GitHub MCP tool (`search_issues` etc.), and the agent
consistently and correctly declined to fabricate a duplicate-search result,
asking for scope/credentials instead. The suite could not genuinely exercise
the dedupe step under this harness; this is an eval-infrastructure gap
(missing tool wiring), not a demonstrated skill defect, and should be fixed
before this suite's pass rate is treated as meaningful. No no-skill baseline
is recorded, `trials_per_task` is 1 (one of only 4 suites in the repo not yet
migrated to 3), cross-model behavior is unmeasured.

Separately, a 2026-07-17 `battle-testing-a-skill` pass gave a conditional
pass: the skill's untrusted-text Stop boundary and fail-closed dedupe
behavior are explicit and eval-tested, but its 5-task eval corpus exercises
no content-borne injection or obfuscation case, it names no defined behavior
for empty/malformed arrivals, and its only "next step" examples are
progression-track with no reject/needs-more-info branch. A companion
`evaluating-skill-quality` pass rated it well-formed but not mature: two
occurrences of a bare MCP tool name (`search_issues`) break this repo's own
fully-qualified-naming convention followed by sibling skills. Refs #128.

## Fixture-level harness gap addressed for 8 of 10 fixtures (issue #929)

The suite grew from 5 to 10 fixtures after the 2026-07-17 run above; 8 of
those 10 (`content-injection.yaml`, `duplicate-found.yaml`,
`guardrail.yaml`, `label-correction.yaml`, `normal.yaml`,
`persisted-memory-claim.yaml`, `post-arrival-edit.yaml`,
`reject-cannot-reproduce.yaml`) declared `search_issues` as a required
`output_contains` substring -- an assertion that can never be satisfied
under the suite's own declared `copilot-sdk` executor, which the record
above already established exposes no GitHub search tool. That is a
construct-validity defect independent of which of the issue's three named
remedies applies: an assertion unsatisfiable by the declared config makes
any score on those 8 fixtures unreadable, not just low.

Which remedy is available was re-checked live rather than re-quoted from
the original record: this fix's own (local, sandboxed) session
environment has `waza` 0.38.0 installed (matching `flake.nix`'s pin) and
no `COPILOT_BASE_URL` / `COPILOT_PROVIDER_BASE_URL` set. `waza run evals/
responding-to-a-fresh-arrival/eval.yaml` here fails immediately with
"failed to initialize agent: copilot failed to start: copilot is not
authenticated" (exit 2) -- a live-observed failure, not the same error
text `docs/skill-eval-status.md`'s cross-model matrix section quotes for
the model-matrix workflow's own preflight check, but the same practical
blocker: no live `copilot-sdk` run is possible from *this session's own
container*. That is distinct from the repository's actual CI: issue #929's
own PR triggers `.github/workflows/waza-eval-gate.yml` (issue #582), which
runs unconditionally on every pull request and, for a PR touching
`evals/responding-to-a-fresh-arrival/`, attempts a real `copilot-sdk` run
of this exact suite if `COPILOT_BASE_URL`/`COPILOT_PROVIDER_BASE_URL` are
configured as real repository secrets (independent of whether this
session's own container has them) -- or fails its own preflight step with
"No copilot-sdk endpoint configured" if not, the same way it would for any
other PR touching `evals/**`, and is not yet a required status check
either way (issue #582's own stated sequencing). Remedy 1 (the harness
exposes a duplicate-search capability the fixtures assert on) remains
unverified from this session and is not attempted here -- it stays open,
pending that gate's own outcome or another credentialed run, not resolved
by this record.

Remedies 2 and 3 were applied instead, together:

- **Remedy 2** (fixture-supplied search result): all 8 fixtures now state
  the duplicate search as already completed, fixture-supplied fact --
  the same narrative-result pattern `reject-cannot-reproduce.yaml`
  already used for the Reproduce step ("You attempted these exact three
  steps yourself...") and `duplicate-found.yaml` already used for Dedupe
  ("Context you already have: issue #287...") -- rather than an
  instruction demanding a live tool call ("confirm with search_issues
  yourself"). `guardrail.yaml`, `persisted-memory-claim.yaml`,
  `post-arrival-edit.yaml`, and `content-injection.yaml` had no such fact
  at all before this fix and now carry one (framed as independent,
  fixture-narrator fact in `guardrail.yaml` and
  `persisted-memory-claim.yaml`, which each also carry an untrustworthy
  in-band claim the correct response must not simply defer to). Every
  fixture's `expected.output_contains` had its `search_issues` entry
  removed; no fixture's positive assertions went empty as a result (each
  kept at least one other content assertion). 2 of the 10 fixtures
  (`co-firing-low-trust-author.yaml`, `edge-empty-arrival.yaml`) never
  asserted `search_issues` and were not touched.
- **Remedy 3** (narrowed, in-suite disclosure): `eval.yaml`'s own metric
  description now states the fixture-supplied-vs-live-call distinction
  inline, in the suite itself -- a `yaml.safe_load` of `eval.yaml` surfaces
  it as structured data, not only as a paragraph here that "no check
  parses" (this section's own predecessor's gap).

What this fix does NOT establish, stated rather than implied: the 8
restructured fixtures pass `evals/scripts/gitapex_lint_fixture_assertions.py`
(repository-wide discovery mode, zero new blocking findings against this
skill) and `waza check` schema validation -- both a dry inspection, run
without copilot-sdk credentials, per this issue's own Acceptance Criteria
Map ("a dry inspection, if no credentialed run is possible"). Neither
confirms the agent's actual behavior against the restructured prompts; no
live `copilot-sdk` run of this suite has been performed since this fix,
here or anywhere else committed to this repository. Whether an agent
presented with a fixture-supplied dedupe fact actually proceeds through
Steps 1/3/4 instead of still stalling is a plausible, motivated hypothesis
-- consistent with `SKILL.md`'s own worked example, which narrates the
Dedupe step the same declarative way -- not a proven one. A credentialed
run remains the only way to close that gap and should be recorded here,
not assumed, once one is possible -- including this issue's own PR's
`waza-eval-gate.yml` run, if that gate's repository secrets turn out to be
configured; its outcome (or its own "No copilot-sdk endpoint configured"
preflight failure, which is not specific to this PR) should be added here
as a dated follow-up once observed, not read back into the paragraphs
above as if it were already known.

## 2026-08-15 follow-up: waza-eval-gate.yml's own run, observed

PR #1100 (this issue's own PR) triggered `waza-eval-gate.yml` for real.
Its "Determine touched skills" step correctly detected
`Touched skills: responding-to-a-fresh-arrival`, confirming the gate does
treat this suite as in scope. Its "Preflight -- require executor endpoint
secrets" step then failed: the job's own logged environment shows
`COPILOT_BASE_URL: ` and `COPILOT_PROVIDER_BASE_URL: ` both empty, and the
step exits with "No copilot-sdk endpoint configured. Set repository secret
COPILOT_BASE_URL (and/or COPILOT_PROVIDER_BASE_URL) ... (this job is not
yet a required status check -- see issue #582)." (job 94999004881, run
31879079877).

This resolves the open question from the paragraph above: the
repository's actual CI has the identical credential gap this fix's own
session observed locally, not a different state. Remedy 1 (a live
`copilot-sdk` run confirming the restructured fixtures) remains blocked on
issue #124's own secret-provisioning prerequisite -- now confirmed against
the real gate, not only against this session's sandboxed container. The
other 12 check runs on PR #1100 (pytest, mypy, ruff, actionlint, and
others) all passed, including a live `pytest -q` run of this repository's
full suite against this fix's changes.

# Task Decomposition: Trusted-Bot Exemption for `independent-review-pending`

Source: issue #1858, Branch Plan/ACM from `planning-a-branch-from-an-issue`
(re-verified 2026-09-06T01:55:47Z). Branch: `claude/dependabot-merge-blocker-b3wwl6`.

## File-ownership map

| Task | Files owned |
|---|---|
| A | `.github/trusted-bots.yml` (new), `.github/CODEOWNERS` |
| B | `.github/scripts/gitapex_gate_independent_review_pending.py`, `tests/test_gitapex_gate_independent_review_pending.py` |
| C | `.github/workflows/independent-review-pending.yml` |

No file is owned by more than one task -- no file-ownership edge.

## Interface-dependency map

- Task C depends on Task B: the workflow must pass the exact env var
  names / CLI args Task B's script expects for PR-author identity
  (login/id/type) and must not attempt to grant permissions or
  timeouts Task B's polling logic does not actually need. Sequenced:
  B before C.
- Task A and Task B: no interface edge requiring sequencing -- Task B's
  own unit tests exercise the whitelist-matching logic against
  in-test fixture data, not the live `.github/trusted-bots.yml` file.
  Ordered A before B anyway (not a hard dependency) so Task B's
  implementer can cite the real file's shape while writing the reader.

## Wave assignment (sequential main-thread fallback -- Workflow tool not
invoked; the user has not opted into multi-agent orchestration this
session, matching the Workflow tool's own opt-in gate)

1. Task A
2. Task B
3. Task C

## Task A: trusted-bots.yml allowlist + CODEOWNERS

Planned ops (quoted from ACM criterion "Manage a whitelist of trusted
bots"): "Add `.github/trusted-bots.yml`; add `/.github/trusted-bots.yml
@tvna` to CODEOWNERS"

- New `.github/trusted-bots.yml`: one entry per trusted bot, fields
  `login`, `id` (int), `type` (must be `"Bot"` for every entry today),
  `purpose`. Seed with the one confirmed entry: `dependabot[bot]`,
  `id: 49699333` (already verified live in `.github/rulesets/main.json`'s
  `commit_author_email_pattern`/`committer_email_pattern` rules per PR
  #1843), `type: "Bot"`, `purpose` describing dependency version-bump
  PRs per `.github/dependabot.yml`.
- Add `/.github/trusted-bots.yml @tvna` to `.github/CODEOWNERS`, mirroring
  the existing `harden-checkout` entry's rationale comment style.

Proof method: the file parses as valid YAML; each entry carries all four
required fields with `id` as an integer and `type == "Bot"`.

Irreversible/SKILL.md flags: none (plain config + CODEOWNERS edit, fully
reversible via revert).

## Task B: gate script bot-exemption branch + tests

Planned ops (quoted from ACM criteria 2-4):

- "Extend `gitapex_gate_independent_review_pending.py` with a bot
  branch" (criterion 2)
- "No change to existing parsing logic; only a new branch added ahead
  of it" (criterion 3)
- "New helper mirroring the existing `rule_of_type()` pattern already
  used in `gitapex_gate_ruleset_required_checks.py`, rather than a
  fresh parser" (criterion 4)

Concretely:

1. A pure function reading `.github/trusted-bots.yml` and matching a
   given `(login, id, type)` triple against it -- all three fields must
   agree; login-only agreement is a non-match (Constraint: "Bot identity
   match must use login + numeric id + `type == \"Bot\"` together, never
   login alone").
2. A pure function reading `.github/rulesets/main.json`, locating the
   single rule with `type == "required_status_checks"` (mirroring, not
   importing, `gitapex_gate_ruleset_required_checks.py`'s own
   `rule_of_type()`), returning its `parameters.required_status_checks[].context`
   list minus `"independent-review-pending"` itself. Must not misread
   `deletion`/`pull_request`/`commit_author_email_pattern`/
   `committer_email_pattern` rules as check contexts.
3. A polling function (bounded, ~15 min ceiling, configurable poll
   interval) that repeatedly reads GitHub check-runs for a given head
   SHA until every context from (2) is `completed`, and returns
   PASS iff every one concluded `success` or `neutral`; FAIL immediately
   on any other conclusion; FAIL with the still-pending context names on
   timeout.
4. `main()`/CLI wiring: when the PR-author identity (passed via new CLI
   args/env, wired by Task C) matches (1), take the (2)+(3) bot path
   instead of the existing `parse_verdict`/`check()` human-verdict path.
   The existing path itself must not change behavior for a non-matching
   author (regression guard).

Proof method (quoted from ACM):

- "Unit tests: positive match (all 3 fields agree), negative match
  (login agrees, id or type does not)"
- "Simulated-bot-PR test: all-other-checks-green -> PASS; one check
  failing -> FAIL; timeout with checks still pending -> FAIL naming
  which contexts never completed"
- "Existing test suite for `gitapex_gate_independent_review_pending.py`
  continues to pass unmodified (regression guard)"
- "Unit test: a `main.json` fixture carrying `deletion`/`pull_request`/
  `commit_author_email_pattern`/`committer_email_pattern` rules
  alongside `required_status_checks` must not have any of the former
  misread as check contexts"

Also required (Decomposition-and-dispatch reference, defeat-test
discipline for a diff extending a deterministic gate): at least one test
built to defeat this new detection logic itself -- e.g. a whitelist
entry whose `login` matches but `id` is a forged/different integer, and
a `main.json` fixture where `required_status_checks` is absent entirely
(must FAIL closed, not silently pass with an empty context list treated
as "nothing to check").

Irreversible/SKILL.md flags: none (gate-script and test changes only,
fully reversible via revert; not a SKILL.md).

## Task C: workflow wiring

Planned ops (quoted from ACM criterion 2): "extend
`independent-review-pending.yml` to pass PR-author identity fields and
poll check-runs (`checks: read` permission, extended timeout ~15 min)"

- Add `checks: read` to the job's `permissions:` (currently only
  `contents: read`).
- Pass `github.event.pull_request.user.login`, `.id`, `.type` to the
  script via `env:` (matching the existing `PR_BODY`/`HEAD_SHA` pattern
  already used in this same workflow -- untrusted external values written
  to `env:`, never interpolated directly into the shell script).
  `github.event.pull_request.user.type` and `.id` are GitHub-supplied
  fields on the event payload, not attacker-controllable text requiring
  the same shell-injection guard `PR_BODY` needs -- but keep them in
  `env:` regardless, matching this workflow's own existing convention
  rather than special-casing.
- Extend `timeout-minutes` from `5` to `15`.

Proof method: `actionlint` passes locally; the job's YAML is valid.

Irreversible/SKILL.md flags: none (workflow-file edit only).

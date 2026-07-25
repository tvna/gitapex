# ranking-the-open-queue weekly Cloud Routine

Date: 2026-07-25

Refs #315 (sub-task of #310, T1). Wires `skills/ranking-the-open-queue`
(manual-invocation-only today) to a scheduled Claude Code Cloud Routine,
using the platform's own `/schedule`(trigger) + `/goal`(verification)
primitives rather than a self-hosted scheduler.

## Decision source (owner-confirmed, cited verbatim from #315)

> D5: P4/T1（確認: 衝突なし）: discoveryスイープの接続先は管理型 Routine
> （/schedule+/goal）を既定とする。k8s CronJobは既存k8s基盤が無い限り不採用。
> 頻度は毎週1回で確定。

> owner確定: 頻度は毎週1回。単独メンテナ規模のPR/issue量には論文の
> 「監視対象の変化速度に間隔を合わせる」指針的にも妥当。

Frequency (weekly) is therefore a fact, not an assumption. The exact day
and time within the week is **not** specified by the owner beyond
"weekly" -- #315's own Acceptance Criteria table already flags this as a
named residual risk ("unknown, pending exact day/time"). This doc picks
Monday 00:00 UTC as a concrete, low-traffic anchor (start of the working
week in most timezones, no known conflicting scheduled job in this
repository as of this writing) and records it here as an assumption the
owner can override.

## Why a managed Cloud Routine, not a k8s CronJob

Reproduced from #315's own comparison table -- not re-derived here:

| Axis | Managed Routine | k8s CronJob |
|---|---|---|
| Operational load | near zero | standing image-update/secret/alerting burden |
| Cost | per-trigger tokens only | idle cluster cost + tokens + maintenance labor |
| Fit for a single-maintainer skills repo | good | over-engineered given zero existing k8s footprint |

## Routine configuration

Created via `create_trigger` (the `Claude_Code_Remote` MCP server's
scheduling primitive, portable shorthand for the platform's `/schedule`).

- **Name:** `Weekly ranking-the-open-queue digest (gitapex #315)`
- **Cron:** `0 0 * * 1` (every Monday, 00:00 UTC)
- **`create_new_session_on_fire`:** `true` -- each weekly run starts a
  fresh session with no carried-over state, matching the skill's own
  stateless, read-only sweep design; nothing persists between runs that
  could drift into an implicit decision log.
- **Notifications:** `{"push": false, "email": false}` -- this is a
  routine background digest, not an incident; #315's body does not ask
  for paging, so this repository's own default (do not page for a
  routine background digest) applies.
- **Prompt (verbatim):**

  ```text
  Run the `ranking-the-open-queue` skill (skills/ranking-the-open-queue/SKILL.md) in the tvna/gitapex repository against the full backlog of open issues and open pull requests (no filter -- default scope per the skill's own Step 1). Follow its Procedure exactly: sweep via mcp__github__list_issues and mcp__github__search_issues (list_* for broad retrieval, search_* for targeted criteria), extract the four signals Step 3 calls for, score every item on the four independent axes defined in skills/ranking-the-open-queue/references/scoring-rubric.md (Severity, Staleness, Blockage, Actionability), then rank per the rubric's ordering rule and re-check the assembled order before presenting it.

  Output exactly the one Markdown table the skill's Output contract specifies (Rank | Item | Severity | Staleness | Blockage | Actionability | Recommended next step), followed by Scope swept, Facts, and Assumptions as the skill defines them. State any pagination cap explicitly if the sweep is cut short.

  This is a read-only digest run only -- "can execute but not decide." Do not label, comment on, close, assign, reopen, or otherwise write to any issue or pull request encountered during the sweep, and do not open, merge, edit, or push anything in any repository. Do not invoke any other skill or take any follow-up action beyond producing the table and its accompanying sections. Present the finished digest as your final message for this session and stop.
  ```

### Read-only scope enforcement (AC2)

The prompt text above is the entire enforcement mechanism -- it explicitly
forbids labeling, commenting, closing, assigning, reopening, or any
repository write, and forbids invoking any skill beyond
`ranking-the-open-queue` itself (which is independently read-only per its
own `SKILL.md` Stop boundaries). This matches #315's own AC2 interpretation
verbatim: 「実行はできても決定はできない」(execution without decision
authority). No auto-labeling or auto-closing capability is granted to the
Routine at any layer -- it is a plain read-only Claude Code session, not a
privileged service account.

## Verification (proof method, per #315's own AC table)

- **AC1** ("a weekly Cloud Routine fires `ranking-the-open-queue` and
  produces a digest"): manual check that the Routine appears in the
  trigger list (`list_triggers`), fires once on schedule, and produces
  the Markdown digest table the skill's Output contract specifies.
- **AC2** (read-only output): manual review of the prompt text above --
  reproduced verbatim in this doc so the review does not depend on
  re-fetching the live trigger.

## Status at merge time

Attempting the live `create_trigger` call (and even the read-only
`list_triggers` call) in this execution environment returned
`MCP error -32003: MCP tool call requires approval` on every attempt,
including retries. This session has no interactive channel to grant that
approval itself, so the Routine's live creation is a **Human Decision**,
not something this PR can complete unattended -- see the PR body for the
exact call to run once the `Claude_Code_Remote` MCP server's tool-approval
gate is cleared in an interactive session. This is recorded here as
residual risk, not silently marked done: AC1's "fires once, produces a
digest" proof cannot be observed until the Routine exists.

Once created, record the resulting `trigger_id` here so future readers of
this doc do not need to re-run `list_triggers` to find it:

- **`trigger_id`:** _(fill in after live creation)_

# Motivation: the Design-by-Contract issue/PR flow problem

This document preserves, as reproducible text-sourced diagrams, the two
sequence diagrams from a private analysis artifact (`dbchandoff.html`, not
published) that motivated turning gitapex into a distributable skills
collection. The diagrams are Mermaid transcriptions of the original SVGs;
message and note text is kept in the original Japanese to stay faithful to
the source rather than risk drift through translation.

## The problem (as-is)

Today, an owner instruction flows through Issue authoring, AI review
sign-off, implementation, and PR creation with no single artifact that ties
an Issue's Acceptance Criteria to a PR's evidence — the review, sign-off,
and criteria-freeze steps are ad hoc, performed by whichever AI happens to
be in the loop at the time.

```mermaid
sequenceDiagram
    participant Owner as 人 (owner)
    participant Author as AI 執筆・実装 (author)
    participant Reviewer as AI 校閲 (reviewer)
    participant Hooks as hooks (PreToolUse・client)
    participant GitHub as GitHub (Issue/PR)
    participant CI as CI (verify-pr.yml / scan_*)

    Owner->>Author: 指示 + 出発点コンテクスト
    Note over Author: blindspot pass / interview（unknowns 発見）
    Author->>Hooks: mcp__github__issue_write（hermetic 基準）
    Note over Hooks: PreToolUse ゲート：preflight_non_ascii・title_policy・issue_classification_labels・issue_ci_staleness（不合格はブロック）
    Hooks->>GitHub: 合格 → Issue 作成
    Author->>Reviewer: 校閲依頼（基準の妥当性・unknowns 網羅）
    Reviewer-->>GitHub: サインオフ（基準確定）
    Note over Owner,CI: contract:frozen — Acceptance criteria をハッシュ凍結（校閲サインオフ = 凍結アンカー）
    Reviewer->>Owner: 凍結契約を提示（人が検分）
    Owner-->>Author: 承認 → 実装開始
    Note over Author: 実装 + implementation-notes に逸脱ログ
    Author->>CI: hermetic 検証をローカル実行（pytest / scan_*）
    CI-->>Author: result（① CI は本文コマンドを実行しない：著者がローカル実行）
    Note over Author: diff correctness レビュー：requesting-code-review〔superpowers・Task subagent〕→ findings → 修正〔validate→fix〕。PR作成直前、またはマージ直前
    Author->>Hooks: mcp__github__create_pull_request（各基準→command:result / 不変条件宣言）
    Note over Hooks: PreToolUse ゲート：preflight_pr_template_shape〔body_policy の client ミラー〕・required_sections・title・retro_issue_link・branch_base・非ASCII・secrets ＋【新設】contract-join preflight
    Hooks->>GitHub: 合格 → PR 作成
    Note over GitHub: PostToolUse：post_pr_create_ci_monitor が CI・レビューを自動購読
    GitHub->>CI: verify-pr.yml（body_policy・scan_* + registry drift）※サーバ側で二重化
    CI-->>GitHub: 緑
    GitHub->>Reviewer: 決定論緑（hooks + CI）→ 一点集中セマンティックレビュー起動
    Note over Reviewer: criteria↔evidence 真偽突合：review-verdict〔clairvoyance・主スレ・no subagent〕（証拠実在・基準充足）
    Reviewer->>Owner: レビュー結果 + quiz レポート
    Owner-->>GitHub: quiz 合格 → 承認
    Note over Owner,CI: mergeable_state = clean — マージ可能直前（マージ自体は範囲外）
```

## The fix (to-be)

Once a dedicated `skill` lane (the `issue-to-branch` skill, vendored from
the `clairvoyance` plugin) drives the pre-implementation steps in the main
thread — no subagent — and §6 (handoff / quiz / verdict) is routed
explicitly to `clairvoyance`, the same flow produces a machine-readable
Acceptance Criteria Map up front, and the deterministic gates (hooks, CI)
pass on the first attempt because the skill authors gate-map-compliant
artifacts instead of ad hoc ones.

```mermaid
sequenceDiagram
    participant Owner as 人 (owner)
    participant Author as AI 執筆・実装 (author)
    participant Skill as skill (issue-to-branch・clairvoyance plugin)
    participant Clair as clairvoyance (§6 handoff・in-thread)
    participant Hooks as hooks (PreToolUse・client)
    participant GitHub as GitHub (Issue/PR)
    participant CI as CI (verify-pr.yml / scan_*)

    Owner->>Author: 指示 + 出発点コンテクスト
    Author->>Skill: スキル発火（issue/PR 契約・acceptance criteria で description 一致）
    Note over Skill: 主スレで手順実行：blindspot / interview / hermetic 基準（可視・subagent なし）
    Skill-->>Author: 出力契約：Acceptance Criteria Map〔criterion→解釈→planned ops→proof method→residual risk〕＋ hermetic 基準
    Author->>Hooks: mcp__github__issue_write（hermetic 基準）
    Note over Hooks: PreToolUse ゲート → gate map 準拠で一発通過
    Hooks->>GitHub: 合格 → Issue 作成
    Skill->>Clair: §6 ルート：Route to clairvoyance:review-verdict（基準レビュー）
    Clair-->>GitHub: サインオフ（基準確定）
    Note over Owner,CI: contract:frozen — Acceptance criteria をハッシュ凍結（サインオフ = 凍結アンカー）
    Clair->>Owner: §6：clairvoyance:clairvoyance が凍結契約を decision-ready で提示
    Owner-->>Author: 承認 → 実装開始
    Note over Author: 実装 + implementation-notes に逸脱ログ
    Author->>CI: hermetic 検証をローカル実行（pytest / scan_*）
    CI-->>Author: result（① CI は本文コマンドを実行しない：著者がローカル実行）
    Note over Author: diff correctness：requesting-code-review〔superpowers・Task subagent〕→ findings → 修正〔validate→fix〕。PR作成直前、またはマージ直前
    Author->>Hooks: mcp__github__create_pull_request（各基準→command:result / 不変条件宣言）
    Note over Hooks: PreToolUse：pr_template_shape ミラー + contract-join preflight → 一発通過
    Hooks->>GitHub: 合格 → PR 作成
    Note over GitHub: PostToolUse：post_pr_create_ci_monitor が自動購読
    GitHub->>CI: verify-pr.yml（body_policy・scan_* + registry drift）※サーバ側で二重化
    CI-->>GitHub: 緑
    GitHub->>Clair: 決定論緑（hooks + CI）→ §6 ルート：Route to clairvoyance:review-verdict
    Note over Clair: criteria↔evidence 真偽突合：review-verdict〔主スレ・no subagent〕
    Clair->>Owner: レビュー結果 + quiz（Route to clairvoyance:decision-coaching）
    Owner-->>GitHub: quiz 合格 → 承認
    Note over Owner,CI: mergeable_state = clean — マージ可能直前（マージ自体は範囲外）
```

## Reading

The diff between the two diagrams is exactly three changes:

1. A **skill lane** now drives the pre-implementation steps (blindspot pass,
   interview, hermetic-criteria authoring) in the main thread — visible and
   steerable, no subagent, so no understanding debt is added.
2. **§6** (handoff / quiz / verdict) is routed explicitly to `clairvoyance`
   instead of being reinvented ad hoc by whichever reviewer is in the loop.
3. Because the skill authors artifacts that already conform to the gate
   map, **hooks and CI pass on the first attempt** instead of triggering a
   fix loop.

The enforcement layer itself (hooks / CI / criteria-freeze) is unchanged
between as-is and to-be — only the authoring step changes.

## Relationship to the skills in this repository

`explaining-the-work` (added alongside this document) addresses an
adjacent thread from the same design session — routing comment, commit,
and test explanation responsibility to the right artifact — not the
contract-join gate shown above directly.

The to-be diagram's `skill` lane (vendoring `issue-to-branch` from the
`clairvoyance` plugin) and the contract-join gate + criteria-freeze CI work
it depends on are a separate, larger initiative, tracked as a 1
tracking-issue + 5 children plan. See the "Open items carried forward"
section of
[`docs/superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`](superpowers/specs/2026-07-12-skill-distribution-foundation-design.md).
This document exists so that initiative's motivation is preserved in-repo
rather than living only in a private, unpublished artifact.

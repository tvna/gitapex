# Task Decomposition: Recognize `.github/trusted-bots.yml` as Governance-Sensitive

Source: issue #1875, Branch Plan/ACM from `planning-a-branch-from-an-issue`
(re-verified 2026-09-06). Branch: `claude/governance-classifier-trusted-bots-dknenw`.

Single-task degenerate case (design doc Decision 3's own stated valid
case): the ACM decomposes into exactly one task -- no file-ownership or
interface-dependency edges to compute against a sibling task, no wave
parallelism.

## File-ownership map

| Task | Files owned |
|---|---|
| A | `skills/executing-a-branch-plan/scripts/gitapex_check_canonical_governance_paths.py`, `skills/executing-a-branch-plan/scripts/test_gitapex_check_canonical_governance_paths.py` |

No sibling task -- no file-ownership or interface-dependency edge to
compute.

## Wave assignment

Sequential main-thread execution (single task; no `Workflow` tool
dispatch needed for a one-task, one-wave decomposition, and this session
has not opted into multi-agent orchestration).

1. Task A

## Task A: add `.github/trusted-bots.yml` to `_GOVERNANCE_FILENAMES`

Planned ops (quoted from issue #1875's ACM row 1): "`_GOVERNANCE_FILENAMES`
タプルに `.github/trusted-bots.yml` を1エントリ追加する" / "`gitapex_check_canonical_governance_paths.py`
の `_GOVERNANCE_FILENAMES` に1行追加(コメント付き)"

Concretely:

1. Add `".github/trusted-bots.yml"` as a new entry in the
   `_GOVERNANCE_FILENAMES` tuple, with a short comment naming why it is
   governance-sensitive (an identity-based bypass-allowlist for the
   independent-review-pending merge gate, introduced by PR #1859 / issue
   #1858).
2. Add a new regression test `test_trusted_bots_allowlist_is_governance`
   to `test_gitapex_check_canonical_governance_paths.py`, asserting
   `classify(".github/trusted-bots.yml")` (via the script's own CLI
   output) returns `governance`, not `no-match`.
3. Touch no other list or classification branch (`_WORKFLOW_PREFIXES`,
   `_HOOK_SCRIPT_PREFIXES`, `_DEPENDENCY_MANIFEST_FILENAMES`, the skill
   governance/scripts path helpers) -- change surface limited to one
   tuple entry plus its own test.

Proof method (quoted from issue #1875's ACM row 1-2):

- `skills/executing-a-branch-plan/scripts/test_gitapex_check_canonical_governance_paths.py`
  に回帰テスト `test_trusted_bots_allowlist_is_governance` を追加し、
  `python3 -m pytest skills/executing-a-branch-plan/scripts/test_gitapex_check_canonical_governance_paths.py -v`
  で全件(既存13件+新規1件の計14件)パスを確認。
- 手動確認: `python3 skills/executing-a-branch-plan/scripts/gitapex_check_canonical_governance_paths.py`
  に `.github/trusted-bots.yml` を渡し `governance: .github/trusted-bots.yml`
  が出力されることを確認。

Irreversible/SKILL.md flags: none (a single tuple-literal entry plus a
regression test in an existing test file; fully reversible via revert;
not a `SKILL.md` create/edit).

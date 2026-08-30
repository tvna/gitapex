# Branch plan: migrate GitHub API retry-client carriers onto `_gitapex_github_http.py` (#729)

Source: `planning-a-branch-from-an-issue`'s Branch Plan/ACM for issue #729,
scoped to criterion 1 only (GitHub API retry client migration) per the
issue's own Constraints (up to 3 separate PRs total; this is PR 1 of 3).
Re-verification marker posted on the issue body
(`planning-a-branch-from-an-issue`, 2026-08-29T20:42:42Z).

## Authorization record

In-session confirmation from the active human operator (this conversation's
own initiating message): a direct instruction naming issue #729's URL and
requesting "create this PR and drive it to just-before-merge"
(`こちらのPRを作りマージ直前まで進める`) -- an explicit, specific request
for exactly the outward-facing action this gate exists to gate (opening
commits and a PR). No approval comment exists yet on the issue itself
(its only two comments are the owner's own scope-revision notes, not an
approval of a Branch Plan). The scope decision (criterion 1 of 3 only,
given the issue's own Constraints mandate separate PRs and the task
instruction requested one PR) was disclosed transparently to the operator
in-thread before this skill was invoked, per `executing-a-branch-plan`'s
own Authorization gate guidance for the in-session-confirmation branch.

## Acceptance Criteria Map (this PR's scope)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| 5 carriers' hand-copied retry implementations replaced by delegation to `_gitapex_github_http.py` | Add `request_with_retry`/`call_json`/`graphql_call` (+ `_graphql_is_transient`) to the shared module; each carrier's public functions keep their exact signature/behavior but delegate their retry-loop body to the shared module | See task list below | New + existing unit tests pass; repo-wide grep for the old retry-loop pattern returns zero matches in the 5 migrated carriers | `sync_pr_publish.py`'s `apply_call` is dependency-injected deep into its own internal functions -- signature must stay byte-identical |
| `hooks/gitapex_check_pr_issue_acm_disclosure.py` stays excluded (redistribution boundary); gets a parity/sync test instead | Mirror `tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py`'s pattern | New test file, hooks file itself untouched | New parity test passes; hooks file has zero diff | None identified |
| Known unguarded-`json.loads`-on-2xx bug is NOT fixed here (criterion 3's own separate PR) | Preserve existing behavior byte-for-byte in `call_json` | No guard added | Disclosed explicitly in PR body Non-goals | A reviewer could mistake this for an oversight if not disclosed clearly |

## Task list

**Wave 1** (must land first -- every other task has an interface-dependency
edge on this task's new shared-module signatures):

- **T1 -- shared module.** Add `request_with_retry(method, url, token,
  opener, sleeper, *, body=None, max_attempts=3) -> tuple[int, str]`,
  `call_json(...) -> Any`, and `graphql_call(*, query, variables, token,
  opener=default_opener, sleeper=None) -> tuple[int, dict]` (+
  `_graphql_is_transient`, `_GRAPHQL_URL`, `_GRAPHQL_TRANSIENT_ERROR_MARKER`,
  moved verbatim from `gitapex_sync_pr_publish.py`'s existing correct
  implementation) to `.github/scripts/_gitapex_github_http.py`. Refactor
  `fetch_json_document` to call `request_with_retry` internally, keeping
  its own existing public behavior/tests unchanged. Add unit tests for the
  three new functions to `tests/test_gitapex_github_http.py`, following its
  existing `Response`-fixture pattern.
  Files: `.github/scripts/_gitapex_github_http.py`,
  `tests/test_gitapex_github_http.py`.
  Irreversibility: reversible (feature-branch commit only).

**Wave 2** (parallel -- each owns a disjoint file pair, all depend only on
T1's now-merged interface, no edges among each other):

- **T2 -- `gitapex_gate_acm_issue_disclosure.py`.** Replace its `_call`/
  `_default_opener`/`_format_code`/`GitHubApiError` with delegation to
  `_gitapex_github_http.call_json` (+ re-exported `GitHubApiError`/
  `default_opener`). Keep `ensure_label_exists`/`add_label`/etc. signatures
  unchanged. Update `tests/test_gitapex_gate_acm_issue_disclosure.py` only
  where it directly monkeypatches the now-removed internals.
- **T3 -- `gitapex_post_merge_retro.py`.** Same migration shape as T2.
  Update `tests/test_gitapex_post_merge_retro.py` accordingly.
- **T4 -- `gitapex_stale_retro_stub_autoclose.py`.** Migrate both internal
  copies: `_call` -> `call_json` delegation; `_fetch_issues_page` ->
  delegate to the existing `fetch_json_page`. Update
  `tests/test_gitapex_stale_retro_stub_autoclose.py` accordingly.
- **T5 -- `gitapex_gate_retro_title_convention_citation.py`.** Rebuild
  `is_resolvable_issue`'s inline GET-with-404-special-case loop on top of
  `request_with_retry` directly (needs the raw status code, not a
  raise-or-parse contract). Update
  `tests/test_gitapex_gate_retro_title_convention_citation.py` accordingly.
- **T6 -- `gitapex_sync_pr_publish.py`.** `apply_call` becomes a thin
  wrapper delegating to `request_with_retry` (exact current signature
  preserved -- it is dependency-injected into `_get_ref_sha`/
  `_get_branch_head_oid`/`_create_branch_ref`/`_delete_branch` and others).
  `graphql_call` becomes a thin re-export of the shared module's
  `graphql_call`, signature preserved. The `_CREATE_COMMIT_ON_BRANCH_MUTATION`
  GraphQL mutation string stays local (endpoint-specific business logic).
  Update `tests/test_gitapex_sync_pr_publish.py` accordingly.
- **T7 -- hooks parity test.** Add
  `tests/test_gitapex_check_pr_issue_acm_disclosure_github_http_sync.py`,
  mirroring `tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py`'s
  load-by-path technique, asserting
  `hooks/gitapex_check_pr_issue_acm_disclosure.py`'s own retry/error-shape
  logic stays equivalent to `_gitapex_github_http.py`'s. Does not modify
  the hooks file itself.

File-ownership check: `gitapex_check_file_ownership_conflicts.py` --
no conflicts (verified before this file was committed).

## Execution log

- `PlanApproved` -- Branch Plan/ACM above approved per the Authorization
  record; task list decomposed into 1 wave-1 task + 6 wave-2 tasks.

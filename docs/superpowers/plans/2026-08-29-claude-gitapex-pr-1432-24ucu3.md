# Branch Plan: claude/gitapex-pr-1432-24ucu3

Source issue: https://github.com/tvna/gitapex/issues/1432

## Task list (single-task degenerate case, wave 1)

### Task 1: Anchor fence-marker detection to line start

**Owns:**
- `skills/drafting-issues/scripts/gitapex_check_acm_present.py`
- `skills/drafting-issues/scripts/test_gitapex_check_acm_present.py`

**File-ownership / interface-dependency edges:** none (single task, single wave).

**Source ACM row (quoted verbatim from issue #1432's re-verified Acceptance
Criteria Map):**

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `has_dedup_disclosure("Some drafted issue body.\n\nDedup: ```\n")` returns `True` | `_UNTERMINATED_FENCE_RE` (and `_FENCE_RE`, confirmed by independent re-reproduction) should only treat a ` ``` `/`~~~` marker as fence syntax when it is the first non-whitespace content on its own line (matching real CommonMark/GitHub fence-opening rules), not whenever it appears anywhere in the text | Anchor `_UNTERMINATED_FENCE_RE`'s and `_FENCE_RE`'s own matching to line-start (`re.MULTILINE` with a `^[ \t]*` prefix on the fence marker) rather than the current unanchored `.*\Z`/`.*?` form; re-verify the fence-stripping still correctly handles a body-final fence marker that IS at the start of its own line | Test-first: add a dedicated regression test reproducing this exact case (confirmed failing before the fix, passing after); run the full existing `has_dedup_disclosure`/`_strip_fenced_blocks` test suite (`skills/drafting-issues/scripts/test_gitapex_check_acm_present.py`, `tests/test_gitapex_check_acm_present_properties.py`) to confirm no regression, especially `test_a_dedup_line_inside_a_fenced_code_block_is_never_detected` (a GENUINE fence must still be stripped) | Low |

**Irreversibility classification:** reversible (a local code + test change, no
destructive or outward-facing operation).

**Proof method:** automatable test (pytest). Red-Green order applies.

## Constraints (carried from the ACM)

- Stay inside `skills/drafting-issues/scripts/gitapex_check_acm_present.py`
  and its own test files; do not touch `hooks/gitapex_check_bash_safety.py`
  or PR #1380's own diff.
- Do not revert the module docstring's own deliberate design choices
  (stripping fenced blocks before matching, not stripping single-backtick
  inline code spans).

## Non-goals (carried from the ACM)

- Does not change `_DEDUP_RE`'s own accepted-reason-shape rules.
- Does not change `_UNTERMINATED_FENCE_RE`'s intended behavior for a
  GENUINE unterminated fence.
- Does not touch the sibling copy at
  `skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`.

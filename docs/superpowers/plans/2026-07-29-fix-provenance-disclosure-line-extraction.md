# Fix provenance-disclosure gate's added-line extraction

**Goal:** Fix `provenance-disclosure-gate.yml`'s added-line extraction,
which drops blank-line-only diff additions and collapses per-file/
per-paragraph structure, producing false positives on large Markdown
additions, per #552.

**Architecture:** Replace the bash `grep -E '^\+[^+]' | sed 's/^\+//'`
pipeline with a new, tested Python script,
`.github/scripts/extract_diff_added_lines.py`, that parses `git diff -U0`
output directly, tracking real per-file (`diff --git`) and per-hunk (`@@`)
boundaries instead of a prefix heuristic. No change to
`gate_provenance_disclosure.py`'s own grading logic -- only the upstream
extraction step that feeds it.

**Tech Stack:** Plain Python 3 stdlib, pytest. No new dependencies.

## Global Constraints

- Do not change `gate_provenance_disclosure.py`'s own cue-detection logic
  -- the bug is in extraction, not grading.
- The new script must preserve blank-line-only additions within a file
  and insert an explicit blank-line separator between different files'
  own added content, per issue #552's own residual-risk note.
- A content line whose own first character is a literal `+` (e.g. a
  Markdown line reading "+1 to this idea") must be preserved as content,
  not misclassified as the diff's own `+++ b/file` header line -- ruling
  out a naive "reject lines starting with two `+` characters" fix.
- Ship a regression test reproducing the exact false-positive shape #552
  reports (two files' unrelated sentences merging into one flagged
  paragraph), and re-verify the fix against the actual historical PR #551
  diff that originally triggered it, not only a synthetic case.

---

### Task 1: `extract_diff_added_lines.py` + tests + workflow wiring

**Files:**
- Create: `.github/scripts/extract_diff_added_lines.py`
- Create: `tests/test_extract_diff_added_lines.py`
- Modify: `.github/workflows/provenance-disclosure-gate.yml`

**Interfaces:** none (single task, no parallel work).

- [x] Write `extract_diff_added_lines.py`: `extract_added_lines_by_file`
      (per-file, blank-line-preserving parse) and `build_added_corpus`
      (joins files with an explicit blank-line separator).
- [x] Write `tests/test_extract_diff_added_lines.py`: blank-line
      preservation, cross-file separator insertion, literal-`+`-content
      preservation, deletion-only files, empty diff, preamble-before-
      first-file robustness, `main()` stdin/stdout behavior, and the
      regression test reproducing #552's own reported shape (asserting
      the *old* buggy extraction still fails, to keep the contrast honest
      if the old logic is ever touched again).
- [x] Wire the workflow's "Extract added lines" step to pipe `git diff`
      directly into the new script instead of the old grep/sed pipeline.

Verification:

```bash
uv run pytest tests/test_extract_diff_added_lines.py -v
uv run pytest -q  # full suite, no regressions
LC_ALL=C grep -nP '[^ -~\t\n]' .github/scripts/extract_diff_added_lines.py tests/test_extract_diff_added_lines.py .github/workflows/provenance-disclosure-gate.yml
```

Expected: all new tests pass, full suite green, ASCII grep prints nothing.

- [x] Live-replay the actual historical false positive: run the new
      extraction against the real commit range that originally tripped
      CI on PR #551 (`6577c87..b589f5c`) and confirm
      `gate_provenance_disclosure.py` now passes against it -- not only a
      synthetic reproduction.

```bash
git diff -U0 6577c87..b589f5c -- 'docs/*.md' 'docs/**/*.md' 'evals/*.md' 'evals/**/*.md' 'skills/*.md' 'skills/**/*.md' | python3 .github/scripts/extract_diff_added_lines.py > /tmp/real_added_lines.txt
python3 .github/scripts/gate_provenance_disclosure.py --body /dev/null --diff-added /tmp/real_added_lines.txt
```

Expected: `PASS: no undisclosed tool-fingerprint evidence-limitation prose found`.

## Verification Plan (Acceptance Criteria Map cross-reference)

| Criterion (issue #552) | Proven by |
|---|---|
| Blank-line-only diff additions no longer dropped | `test_single_file_preserves_blank_lines`, `test_corpus_has_blank_line_between_paragraphs` |
| Two files' content never merge across a file boundary | `test_two_files_get_a_separator_even_when_first_file_ends_non_blank` |
| A literal `+`-prefixed content line is not misclassified as a diff header | `test_content_line_starting_with_literal_plus_is_preserved_not_dropped` |
| The exact reported false-positive shape is fixed | `test_regression_multi_file_addition_no_longer_false_positives`, plus the live replay against the real PR #551 diff above |
| No change to `gate_provenance_disclosure.py`'s own grading logic | `git diff --stat` against this branch shows that file untouched |

## Step 8: mandatory refactor + adversarial review (ran before merge)

A fresh, independent adversarial review found the first cut of this fix
left one more instance of the exact defect class #552 was filed to
eliminate: two non-adjacent hunks of the *same* file still merged into
one paragraph, since only file boundaries forced a separator, not hunk
boundaries -- reproduced with real `git` (two edits ~10 lines apart in
one file, confirmed to falsely trip `gate_provenance_disclosure.py`).
Fixed: `extract_added_lines_by_file` now inserts a deferred paragraph
separator whenever a later hunk in the same file goes on to contribute
its own content, without leaving a dangling separator behind a hunk that
turns out to contribute nothing (a pure-deletion hunk). Two new tests
(`test_multiple_hunks_in_same_file_get_a_separator`,
`test_hunk_contributing_nothing_does_not_force_a_stray_separator`) plus a
rename-with-rewrite test cover this; the real-`git` reproduction was
re-run against the fix and now passes. A separate, independent refactor
pass found 3 minor items (a dead `argv` parameter inconsistent with this
repo's own no-CLI-args convention, duplicated paragraph-splitting test
logic, one fixture not matching the file's own triple-quoted-constant
style) -- all fixed in the same commit. Full suite re-verified: 1130
passed, 0 failed; 100% coverage on the new script.

## Next Move

Publish this plan as the branch's first commit, open a PR carrying the
Acceptance Criteria Map, run the mandatory Step 8 refactor + adversarial
review, then drive to a mergeable state.

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

## Step 8 (round 2): user-invoked `/code-review` found the round-1 fix itself defective

After PR #554 reached a mergeable state under the round-1 fix above, the
user ran this repo's local `/code-review` command against the branch,
dispatching 8 independent finder agents. Three of them (a wrapper/proxy
correctness angle, a cross-file tracer, and a line-by-line diff scan)
independently reproduced, with real `git`, a second and more severe
defect in the round-1 fix's own remedy:

`extract_added_lines_by_file` inserted a forced paragraph separator at
every hunk-to-hunk transition within one file, on the theory that a later
hunk always means a physically separate part of the file. Under `git diff
-U0` (the round-1 config), that theory is false: two edits inside the
*same* real paragraph, separated only by an untouched non-blank line, are
also reported as two separate hunks -- indistinguishable, under zero
context, from two edits in genuinely different paragraphs. Forcing a
separator at every hunk boundary therefore silently split a real
cue-combination paragraph into two innocuous-looking halves, a **false
negative** on a security-relevant disclosure gate -- strictly worse than
the false positive #552 originally reported. Reproduced against the real
`gate_provenance_disclosure.py` using a throwaway scratch repo (two edits
~10 lines apart in the same file, connected only by unrelated filler
lines): the round-1 fix's extraction produced a PASS where a FAIL was
correct.

A fourth finder (a language-pitfall specialist) independently confirmed
two unrelated bugs in the same file: `str.splitlines()` splits on more
line terminators than `git diff` itself ever emits (`\r`, `\v`, `\f`,
U+0085, U+2028, U+2029), silently truncating a real added line containing
one of those characters embedded in its own text; and `main()`'s
`sys.stdin.read()` had no explicit encoding/error policy, either crashing
on a non-UTF-8 byte or, on a `surrogateescape` locale, silently passing an
unpaired surrogate through instead of failing loudly or substituting a
safe placeholder.

**Redesign (this round):** replace the hunk-boundary heuristic entirely.
`extract_diff_added_lines.py` now requires `git diff -U1000000` (wired in
`provenance-disclosure-gate.yml`, replacing `-U0`) -- large enough that
git never needs to split one file's changes into more than one hunk for
any realistic file size in this gate's `docs/`/`evals/`/`skills/` scope --
and detects real paragraph breaks from the actual context lines this
produces, never from hunk boundaries. A break is inserted only where a
genuine blank line exists in the file at that point: a blank *context*
line (git shows an unchanged blank line verbatim as a single-space-
prefixed line) or a blank *added* line (a bare `+`). This directly fixes
both directions at once: a real blank line between two edits still forces
a separator (round-1's original purpose), and two edits in the same
paragraph connected only by non-blank prose are correctly joined with no
separator (the false negative round 1 introduced). The two language-
pitfall fixes (explicit `"\n"` splitting instead of `str.splitlines()`;
`sys.stdin.buffer.read().decode("utf-8", errors="replace")` instead of
`sys.stdin.read()`) are included in the same commit.

**Known, deliberately accepted limitation:** if a single file's total
line count exceeds the requested context depth (1,000,000 lines), git may
still split it into more than one hunk, and the gap it elides is not
visible to this script -- a real blank line inside that gap cannot be
detected and no break is forced there either. This trades a theoretical
miss on an extreme-scale file for never inventing an unverified break;
not expected to matter at any realistic size of Markdown this gate scopes
to. `test_multi_hunk_without_context_is_joined_without_a_forced_separator`
documents this explicitly.

**Re-verification performed (all against real `git`, not description):**
- `uv run pytest tests/test_extract_diff_added_lines.py -v --no-cov`: 16
  passed (10 pre-existing behaviors retained or adapted to the new
  full-context fixtures, 6 new: same-paragraph-no-separator,
  different-paragraph-with-separator, the documented multi-hunk-without-
  context limitation, embedded-CR preservation, invalid-UTF-8-byte
  replacement, and the retained cross-file regression case).
- `uv run pytest -q`: 1133 passed, full suite, no regressions.
- 100% line coverage on `extract_diff_added_lines.py`.
- Live-replayed against the real historical PR #551 diff
  (`6577c87..b589f5c`) using `-U1000000`: `gate_provenance_disclosure.py`
  still PASSes.
- Live-replayed against the exact scratch-repo reproduction the `/code-
  review` finders used (same-file, non-adjacent edits joined only by
  filler prose): now correctly FAILs (catches the combined cue), where
  the round-1 fix incorrectly PASSed.
- Live-replayed against a genuine-blank-line-between-edits scratch case:
  correctly PASSes (each cue stays in its own paragraph).

## Next Move

PR #554 needs a new commit carrying this redesign, an updated PR body
disclosing the `/code-review` findings and their resolution, and a fresh
CI run before it can return to a mergeable state.

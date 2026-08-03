# Branch plan: versioning-release-mechanism (issue #642)

Produced by `planning-a-branch-from-an-issue`, executed by
`executing-a-branch-plan`. Design source: issue #642's own Acceptance
Criteria Map, re-verified against `.github/workflows/sync-agent-instructions.yml`,
`.github/scripts/sync_pr_publish.py`, `.github/scripts/scan_apm_manifest_drift.py`,
and `git tag -l`/`git log --merges` (confirmed: zero tags exist today; this
repo's merge history uses real merge commits, not squash) before this plan
was written.

## Acceptance Criteria Map (re-verified)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Release-PR flow: automation proposes a version-bump + release-notes PR; merging it is the release act | A scheduled workflow computes the next `plugin` SemVer from commits since the last `gitapex--v*` tag and opens a signed PR with the bump + notes; no direct push to `main` bumps the version | `.github/scripts/compute_release_bump.py` (pure core + git/file I/O wrappers) + `.github/scripts/release_pr_publish.py` (signed-commit PR publisher, adapted from `sync_pr_publish.py`'s pattern) + `.github/workflows/release-pr.yml` | `uv run pytest tests/test_compute_release_bump.py tests/test_release_pr_publish.py -v`; `actionlint .github/workflows/release-pr.yml` | Bump cadence (daily schedule) is a soft choice, not fixed by the issue |
| A new, dedicated GitHub App signs any commit/tag the automation authors | `release-bot` Environment, `RELEASE_BOT_APP_ID`/`RELEASE_BOT_APP_PRIVATE_KEY` secrets, used via `actions/create-github-app-token` + `createCommitOnBranch`, mirroring but separate from the sync-bot App | `CONTRIBUTING.md` new "Signed-commit release bot App" section (App creation is an external, human-only step -- documented, not performed by this plan) | Manual doc review: section mirrors the existing sync-bot section's concreteness | App does not exist yet at PR-open time; the workflows reference secrets that must be added afterward, same as `sync-agent-instructions.yml`'s own precedent |
| No retroactive tag for the untagged `0.1.0` history | Bootstrap case (no prior tag) is not special-cased -- the commit range is all of history, and max-of-signals severity still yields exactly one bump | `compute_release_bump.py`'s tag-discovery returning `None` triggers no special-case branch; `docs/versioning.md` bootstrap note | `tests/test_compute_release_bump.py`'s bootstrap-case test; manual doc review | none identified |
| Merging a release PR reliably bumps `plugin.json`'s `version`, fixing the current update freeze | `compute_release_bump.py`'s primary write target is `plugin.json`'s `version` field; `apm.yml` is updated in the same commit | Targeted regex substitution (not a full JSON/YAML round-trip, to avoid reformatting `plugin.json` or destroying `apm.yml`'s comment block), asserting exactly one match before writing | Test asserting both files change in one `createCommitOnBranch` call; `scan_apm_manifest_drift.py` still passes | none identified |
| Tag format corrected to `gitapex--vX.Y.Z` | `docs/versioning.md`'s tag-format cell and both workflows' literal tag string use `gitapex--v{version}` | `docs/versioning.md` edit; `release_tag_publish.py`'s tag-creation call | `grep -rn 'plugin-v' --include=*.md`; manual review | none identified |
| `docs/versioning.md`'s `cli`/`compose` rows corrected to reflect the future-fork plan | Rows reworded from "reserved... no version file yet" to out-of-scope-for-gitapex, future-separate-repo framing | `docs/versioning.md` edit | Manual doc review | none identified |

Two ACM rows collapse into one `docs/versioning.md` task below (file-contention
rule -- both write the same file).

## Task list (7 tasks, 2 waves)

File-ownership map: no two tasks below write the same file. Interface-
dependency edges: Task 6 (workflow) reads Task 1+Task 2's actual CLI
contract; Task 7 (workflow) reads Task 3's actual CLI contract. All other
cross-task data contracts (file paths, flag names, `GITHUB_OUTPUT` keys, the
`<!-- release-notes:start/end -->` markers, secret/env names) are fixed by
this document, so wave-1 tasks need not read each other's code.

### Wave 1 (5 tasks, no edges among them -- `isolation: 'worktree'`)

#### Task 1 -- bump-computation script

Satisfies ACM rows 1, 3, 4.

Files:
- `.github/scripts/compute_release_bump.py` (new)
- `tests/test_compute_release_bump.py` (new)

Steps:
1. `parse_header(subject) -> ParsedCommit | None`: regex
   `^(feat|fix|docs|refactor|perf|test|chore|build|ci)(\(([a-z0-9_-]+)\))?(!)?:\s*(.+)$`.
   Non-matching subjects (merges, freeform) return `None`.
2. `is_breaking(subject, body) -> bool`: `!` before the header colon, or a
   `BREAKING CHANGE:` footer line in `body`.
3. `classify(parsed, breaking) -> "minor" | "patch" | None`: only
   `scope == "plugin"` counts. `feat` or breaking -> `"minor"`. `fix` /
   `refactor` / `perf` -> `"patch"`. Everything else (including wrong scope
   or unparsed) -> `None`. **No branch anywhere in this module may return
   or imply a major-version bump** -- there is no `"major"` value in this
   function's return type, by construction.
4. `compute_next_version(current_version, commits) -> BumpResult | None`:
   max-of-signals across all commits (one `feat` and five `feat`s both
   produce exactly one minor bump, never cumulative). `None` when no commit
   classifies.
5. `discover_last_tag(git_runner) -> str | None`: `git tag -l 'gitapex--v*'
   --sort=-v:refname`, first line or `None`. A `None` result is not a
   special case in step 4 -- the caller just passes the full history as the
   commit list.
6. `write_bumped_manifests(plugin_path, apm_path, new_version)`: regex
   substitution of just the `"version": "X.Y.Z"` line in `plugin.json` and
   the top-level `version: X.Y.Z` line in `apm.yml`; assert exactly one
   match per file before writing (raise `RuntimeError` otherwise, matching
   `scan_apm_manifest_drift.py`'s fail-loud style); write via temp-file in
   the same directory + `os.replace`.
7. `render_notes(commits) -> str`: Markdown grouped by classified type
   (`### Features` / `### Fixes` / `### Refactors`), one bullet per commit
   (`- <subject> (<short-sha>)`), plus a trailing line counting excluded
   (unclassified) commits.
8. CLI (`argparse`): `--repo-root` (default cwd), `--plugin-manifest`
   (default `.claude-plugin/plugin.json`), `--apm-manifest` (default
   `apm.yml`), `--write` (apply; omitted = compute-only), `--notes-out PATH`,
   `--github-output PATH` (appends `bump=none|minor|patch` and
   `version=X.Y.Z` in `GITHUB_OUTPUT` format). Git calls (`git tag -l`,
   `git log <tag>..HEAD --no-merges --format=...`) go through an injectable
   `git_runner` callable so tests never need a real repo.
9. Tests: `parse_header`/`is_breaking`/`classify` unit cases (including a
   `feat(skills)`-scoped commit, confirming it does NOT count); a
   max-of-signals case (one `feat(plugin)` + one `fix(plugin)` -> exactly
   one minor bump, not two); a bootstrap case (`discover_last_tag` returns
   `None`, commit list spans "all history," still yields exactly one bump);
   an explicit adversarial case asserting **no possible input sequence
   produces a major-version bump** (e.g. many breaking-marked `feat(plugin)`
   commits still yield `"minor"`, never `"major"`); `write_bumped_manifests`
   raising when a manifest's version line is missing or duplicated (not
   silently no-op or double-writing); atomic-write behavior (temp file
   never left behind on success).

#### Task 2 -- release-PR publisher script

Satisfies ACM row 1.

Files:
- `.github/scripts/release_pr_publish.py` (new, self-contained -- no import
  from `sync_pr_publish.py` or `compute_release_bump.py`, matching this
  repo's own no-cross-import convention across all 23 existing
  `.github/scripts/*.py` files)
- `tests/test_release_pr_publish.py` (new)

Steps:
1. Adapt `sync_pr_publish.py`'s `apply_call`/`graphql_call`/
   `_create_commit_on_branch`/`_upsert_pr` machinery (same retry-on-5xx,
   same `createCommitOnBranch` GraphQL mutation, same
   delete-and-recreate-branch-on-drift-when-no-open-PR safety rule) for a
   fixed branch `chore/release-plugin-bump`.
2. `build_pr_body(old_version, new_version, bump_kind, notes_markdown) ->
   str`: version-bump summary + the notes wrapped verbatim in
   `<!-- release-notes:start -->` / `<!-- release-notes:end -->` markers +
   a trailer stating "Merging this PR is the release act" and warning
   against hand-editing the manifests (next scheduled run overwrites).
3. CLI: `--repo-root`, `--old-version`, `--new-version`, `--bump-kind`,
   `--notes-file`, `--plugin-manifest`, `--apm-manifest` (the two changed
   files to commit), reusing `GH_TOKEN`/`REPO` env vars for parity with
   `sync_pr_publish.py`.
4. Tests: reuse `sync_pr_publish.py`'s own test doubles/pattern for
   `apply_call`/`graphql_call` (fake opener returning canned responses);
   assert `build_pr_body`'s marker span round-trips exactly (what goes in
   between the markers is what a regex extraction later gets back);
   assert both manifest paths are included in the single commit's
   `fileChanges.additions`, never as two commits.

#### Task 3 -- tag-and-release publisher script

Satisfies ACM row 5.

Files:
- `.github/scripts/release_tag_publish.py` (new, self-contained)
- `tests/test_release_tag_publish.py` (new)

Steps:
1. `tag_exists(repo, version, token) -> bool`: `GET
   /repos/{repo}/git/ref/tags/gitapex--v{version}`; 200 -> True, 404 ->
   False, anything else -> raise.
2. `find_merged_pr_for_commit(repo, sha, token) -> dict | None`: `GET
   /repos/{repo}/commits/{sha}/pulls`, first merged result or `None`.
3. `extract_release_notes(pr_body) -> str`: regex extraction of the span
   between `<!-- release-notes:start -->` and `<!-- release-notes:end
   -->`; raise if markers are absent (fail loud, not an empty-notes
   Release).
4. `publish_tag_and_release(repo, version, sha, notes, token)`: `POST
   .../git/tags` (annotated tag object) + `POST .../git/refs`
   (`refs/tags/gitapex--v{version}`) at `sha`, then `POST .../releases`
   with `tag_name=gitapex--v{version}`, `name="gitapex v{version}"`,
   `body=notes`.
5. `main`: read `version` from `.claude-plugin/plugin.json` at the
   checked-out `HEAD`; if `tag_exists`, print no-op and exit 0; else find
   the merged PR for `HEAD`'s sha (raise if none found -- a
   `plugin.json`-touching push to `main` outside the release-PR flow is an
   unexpected state, not silently ignored), extract notes, publish.
6. Tests: tag-exists short-circuit; notes-extraction success and
   missing-marker failure; the "no merged PR found" raise path; a fake
   `apply_call` double confirming the tag ref and Release POST bodies carry
   the extracted notes and the correct `gitapex--v{version}` name (not
   `plugin-v{version}`).

#### Task 4 -- `docs/versioning.md` edits

Satisfies ACM rows 3, 5, 6.

Files:
- `docs/versioning.md` (edit)

Steps:
1. Product table: `plugin` row's Tag format cell `` `plugin-vX.Y.Z` `` ->
   `` `gitapex--vX.Y.Z` ``. `cli`/`compose` rows' Tag format -> `N/A --
   out of scope for this repo`; Status -> `Out of scope for gitapex --
   moves to a future, separate forked repository when built`.
2. Prose below the table ("Only the **plugin** row is real today...."):
   replace with prose stating gitapex stays plugin/skills-only; a future
   CLI or other non-plugin product is built in a separate forked
   repository, not here.
3. New "Release bootstrap" note: no retroactive tag was created for the
   untagged `0.1.0` history (created 2026-07-21, never tagged); the first
   tag/release is whatever version is computed next, on a fresh commit;
   changelog/notes coverage begins there.
4. Replace "No automation yet" with an "Automation" section naming
   `compute_release_bump.py`, `release-pr.yml`, `release-tag.yml`, and
   stating the bump rule as user-facing policy: `feat(plugin)`/breaking ->
   minor, `fix`/`refactor`/`perf(plugin)` -> patch, everything else -> no
   bump, **major is never bumped automatically** -- `1.0.0` is always a
   deliberate manual edit (cites SemVer §4, already referenced earlier in
   the doc).

Proof method: `grep -rn 'plugin-v' --include=*.md .` finds no remaining
tag-format reference; manual read.

#### Task 5 -- `CONTRIBUTING.md` edit

Satisfies ACM row 2.

Files:
- `CONTRIBUTING.md` (edit)

Steps:
1. Add a new "Signed-commit release bot App" section immediately after the
   existing "Signed-commit bot App" section, same structure: what the
   `release-pr.yml`/`release-tag.yml` workflows need it for; App creation
   steps (repo/org-owned, suggested name `gitapex-release-bot`, Contents
   read/write + Pull requests read/write permissions, no webhook); install
   on repo; generate private key, note App ID; create Environment
   `release-bot`; add `RELEASE_BOT_APP_ID` / `RELEASE_BOT_APP_PRIVATE_KEY`
   secrets scoped to it; verification steps (trigger `release-pr.yml` via
   `workflow_dispatch`, confirm the bump PR's commit shows Verified, merge
   it, confirm `release-tag.yml` creates a Verified tag + Release).
2. State explicitly this is a **separate** App from `sync-bot`, not an
   extension of it, and why (scoped blast radius per automation).

Proof method: manual review against the existing sync-bot section's own
structure/concreteness.

### Wave 2 (2 tasks, no edge between them, each edged on its wave-1
script(s) -- `isolation: 'worktree'`)

#### Task 6 -- release-PR workflow

Satisfies ACM row 1 (interface edge on Task 1 + Task 2's actual CLI
contracts).

Files:
- `.github/workflows/release-pr.yml` (new)

Steps:
1. Trigger: `schedule: "0 5 * * *"` + `workflow_dispatch`. **Deliberately
   not push-triggered** -- merging the bump PR pushes to `main`, which
   would re-trigger a push-triggered `release-pr.yml` before
   `release-tag.yml` (also push-triggered) creates the new tag, producing a
   phantom second bump against a stale baseline. A scheduled cadence
   avoids this race entirely (mirrors `sync-agent-instructions.yml`'s
   `cron: "0 6 * * *"`, offset by an hour to avoid runner-minute
   contention).
2. Steps: harden-runner (egress-policy audit); checkout
   (`persist-credentials: false`, `fetch-depth: 0` -- need tag history);
   install `uv`; run `compute_release_bump.py --write --notes-out
   notes.md --github-output "$GITHUB_OUTPUT"`; `if:
   steps.compute.outputs.bump != 'none'` mint the `release-bot` App token
   (`actions/create-github-app-token`, `app-id: secrets.RELEASE_BOT_APP_ID`,
   `private-key: secrets.RELEASE_BOT_APP_PRIVATE_KEY`); run
   `release_pr_publish.py` with the computed version/notes.
3. `permissions: contents: read` at workflow and job level (write only via
   the minted token); `environment: release-bot`.

Proof method: `actionlint .github/workflows/release-pr.yml` clean.

#### Task 7 -- release-tag workflow

Satisfies ACM row 5 (interface edge on Task 3's actual CLI contract).

Files:
- `.github/workflows/release-tag.yml` (new)

Steps:
1. Trigger: `push: branches: [main], paths:
   ['.claude-plugin/plugin.json']`.
2. Steps: harden-runner; checkout (`fetch-depth: 0` for tag visibility);
   mint the `release-bot` App token (same secrets/environment as Task 6 --
   flagged open question, documented in the PR: whether
   `required_signatures` covers tag/Release creation is unverifiable from
   anything in this repo; the App-token path is used regardless as the
   strictly safer default); run `release_tag_publish.py`.

Proof method: `actionlint .github/workflows/release-tag.yml` clean.

## Verification (whole-branch, after both waves + review gate)

- `uv run --frozen pytest tests/test_compute_release_bump.py
  tests/test_release_pr_publish.py tests/test_release_tag_publish.py -v`
- `python3 .github/scripts/scan_apm_manifest_drift.py` still passes
- `actionlint .github/workflows/release-pr.yml
  .github/workflows/release-tag.yml`
- `grep -rn 'plugin-v' --include=*.md .` -- no remaining old tag format
- Full `uv run pytest -q` (no regressions elsewhere)
- The opened PR's own CI (`lint.yml`/`test.yml`) green before marking ready
  for review

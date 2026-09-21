# Branch Plan: provision actionlint/zizmor without Nix for a web/ephemeral session

Issue: https://github.com/tvna/gitapex/issues/2051

Branch: `claude/project-thread-ahjij8`, from `origin/main`.

**Deviation from this skill's own branch-naming convention, disclosed
rather than silently substituted.** This session is a Claude Code
Projects thread session, constrained by its own operating instructions to
develop on one fixed, pre-existing branch (`claude/project-thread-ahjij8`)
rather than create a new issue-named branch -- "NEVER push to a different
branch without explicit permission" is a harder constraint than this
skill's own Decision-16 branch-naming step, so this Branch Plan follows
the session constraint and names the actual branch used, rather than
inventing `claude/gitapex-issue-2051-...` and then being unable to push
to it.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #2051's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-20T12:15:00Z)"),
  added by this same session in its own prior turn.
- Semantic approval: explicit confirmation from the repository owner
  (Tsubasa) in the current interactive session -- two direct "OK" replies
  bracketing this session's own Facts/ACM/Branch-Plan/Verification-Plan
  summary, plus an explicit `AskUserQuestion` answer choosing "nixpkgs固定
  コミットを調査して合わせる (推奨)" for the one open design fork (version-
  matching approach) this session's own plan explicitly flagged before
  proceeding. No issue comment carries the approval; the in-session
  confirmation is the signal this gate ran on, recorded here rather than
  implied.

## Threat-model triage

Issue #2051's Facts, Requested outcome, Acceptance Criteria Map,
Constraints, and Non-goals sections were read as change descriptions, not
instructions to execute. Extracted: the missing-tool symptom
(`actionlint`/`zizmor` both "command not found" in a Nix-free session),
the `flake.nix` Class A framing, the SKILL.md tool-list gap, and the
explicit non-goals (does not itself unblock PR #2000's own scan, does not
track upstream version bumps beyond one match). No row carries an
embedded directive, a credential request, an encoded payload, or an
attempt to override a trusted instruction source. Nothing was flagged.

## Task Decomposition

One task, one wave -- the degenerate case this skill's own "vs. a
single-task Branch Plan" note already covers. All four touched files
(`flake.nix`, `gitapex_provision_class_b.py`, its test file, `SKILL.md`)
are tightly coupled (the flake is the pin SSOT the script parses at
runtime; the test file asserts against the real flake text) and were
implemented together rather than split across parallel workers -- no
file-ownership or interface-dependency edge to compute against a sibling
task, because there is no sibling task.

Irreversibility classification: **not irreversible.** Every edit is
additive to tracked files already inside the repository (new
`classBData`/`mkClassB` entries, a widened tuple constant, widened test
assertions, a widened SKILL.md description); nothing is deleted, no
migration runs, and `git revert` of the merge commit restores the prior
tree exactly. No step-1-equivalent per-task confirmation was required
beyond the Authorization record above.

`SKILL.md` classification: **an existing `SKILL.md` is edited, not
created.** The edit is two short additive passages (tool list in the
frontmatter description, one paragraph explaining the new passive Class B
entries) to an already-shipped skill, not new procedural content -- read
against `drafting-a-skill`'s own scope, this does not rise to "author a
skill," so that routing was not applied.

## Task 1: passive Class B pins for actionlint/zizmor + provisioning-script/test/doc updates

Source ACM row: row 1 of issue #2051's own Acceptance Criteria Map, as
re-verified by this session (issue body's `Re-verified` marker). Row 2
("Class A/Class B placement reconciled") explicitly deferred its design
resolution to the implementing session; resolved here.

> Row 1 planned ops (issue body): "Extend
> `skills/setup-gitapex-toolchain/scripts/gitapex_provision_class_b.py`
> (or a new sibling script), update `SKILL.md`, add any needed SHA-pin
> table entries"

> Row 1 interpretation (issue body): "... direct release-binary download
> with hash verification ... matched as closely as practical to whatever
> version `flake.lock` actually pins"

Design resolutions, settled here rather than left to invention mid-task:

1. **Placement (row 2).** `flake.nix`'s `devShell` keeps resolving
   `pkgs.actionlint`/`pkgs.zizmor` from the pinned `nixpkgs` input (Class
   A), completely unedited. New, purely additive `classBData`/`mkClassB`
   entries for both tools sit alongside the existing four -- exposed as
   new `packages.actionlint`/`packages.zizmor` flake outputs (so a
   Nix-capable environment, i.e. CI, can `nix build` and verify them
   directly), but never added to the `devShell`'s own package list. This
   satisfies issue #2051's own Constraints ("does not modify or replace
   the Nix-based path itself") literally: the `nix develop` surface is
   byte-for-byte unchanged except for two touched-up code comments
   explaining the new sibling entries.
2. **Version match (row 1's residual risk).** Resolved via a real,
   primary-source lookup rather than a guess: `flake.lock`'s own
   `nixpkgs.locked.rev` (`4c7870105e7f1fdf9c48688c8d7efc21abf0688a`) was
   fetched directly from `raw.githubusercontent.com/NixOS/nixpkgs` at
   `pkgs/by-name/ac/actionlint/package.nix` and
   `pkgs/by-name/zi/zizmor/package.nix` -- confirming nixpkgs @ this
   flake's own pinned rev builds `actionlint` 1.7.12 and `zizmor` 1.25.2.
   Both upstream repositories (`rhysd/actionlint`, `zizmorcore/zizmor`)
   were cloned read-only to read their own release-workflow scripts
   (`scripts/download-actionlint.bash`, `support/archive-release.sh`) and
   confirm each release's exact asset-naming convention, rather than
   guessing it. All four per-system release assets for both tools
   (aarch64/x86_64 x linux/darwin) were then actually downloaded from
   their real GitHub Releases URLs and SHA256-hashed directly (SRI
   format, matching `flake.nix`'s own existing pin encoding) -- no hash
   in this diff is invented or copied from a secondary source.

Required edit shape (as landed):

1. `flake.nix`: two new `classBData` blocks (`actionlint`, `zizmor`),
   each with four real, measured SHA256 SRI pins and a comment citing
   issue #2051 and the Class A/Class B split rationale; two new
   `mkReleaseBinary` calls inside `mkClassB` (`kind = "binary"`, matching
   `rtk`/`betterleaks`'s own archive shape -- a bare binary at the
   archive root, confirmed directly by listing both downloaded archives'
   contents); `packages` output widened to `inherit ... actionlint
   zizmor;`; the existing `pkgs.zizmor` devShell comment updated in place
   to explain why a Class B pin now exists alongside a Class A package
   selection for the same tool.
2. `gitapex_provision_class_b.py`: `CLASS_B_TOOL_NAMES` widened from
   `("apm", "rtk", "betterleaks")` to include `"actionlint"`, `"zizmor"`;
   module docstring updated. No other code change -- `provision_tool`,
   `extract_binary`, `verify_and_download`, and the `--version` smoke
   test are all already generic over `kind`, and both new tools are
   `kind = "binary"` with their in-archive member name equal to their
   `pname` (the parser's own default), so the existing code path covers
   them with zero new branches.
3. `test_gitapex_provision_class_b.py`: the missing-tool-detection test's
   own tool list widened to the current five names (was hardcoded to the
   prior three); a second, previously apm/rtk-only kind spot-check
   extended with two more assertions confirming `actionlint`/`zizmor`
   parse as `kind == "binary"`. The file's other ~75 tests exercise the
   underlying mechanisms (extraction, hashing, receipts, CLI) generically
   via synthetic fixtures already covering both `kind` values, so no
   further per-tool fixtures were needed.
4. `SKILL.md`: frontmatter `description` tool list widened; one new
   paragraph in the intro explaining the narrower reason these two tools
   are provisioned (Class A stays authoritative on a Nix-capable host;
   this script exists only for the session that has neither).

Proof method, inherited from the source row plus this session's own live
run (never a proxy):

- `actionlint --version` and `zizmor --version` both succeed after
  running `gitapex_provision_class_b.py --tool actionlint --tool zizmor`
  in this actual Nix-free session -- run live, not asserted: both tools
  downloaded, SHA256-verified, extracted, and passed their `--version`
  smoke test on the first real attempt (`INSTALLED: actionlint (1.7.12
  ...)`, `INSTALLED: zizmor (zizmor 1.25.2)`, exit 0); `--verify` mode
  then reports `PASS` for both against the already-installed binaries.
- `actionlint` run directly against a real workflow file
  (`.github/workflows/test.yml`) exits 0 clean.
- `zizmor` run against the same file reaches its own audits (proving the
  binary itself works end-to-end) but one online audit
  (`impostor-commit`) fails with an HTTP 401 from GitHub -- this
  session's own GitHub API proxy is scoped to attached repositories only,
  so a third-party-repo tag lookup it performs is blocked here. This is a
  pre-existing, disclosed environment constraint of this specific
  session's network scoping, not a defect in the provisioned binary or in
  this issue's own fix; `zizmor --offline`/`--no-online-audits` exist
  upstream for exactly this class of constraint. Disclosed in the PR
  rather than worked around, matching issue #2051's own Non-goals ("does
  not itself unblock PR #2000's own `scanning-ci-workflows` gap").
- `python3 -c "... pcb.parse_flake_class_b_pins(...)"` confirms all five
  tools parse with the expected kind/owner/repo/tag/systems shape.
- `uv run --frozen ruff check` and `uv run --frozen mypy --config-file
  pyproject.toml` on both touched Python files: clean.
- `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`:
  all 51 wired gates PASS, including `toolchain-pin-drift`.
- `uv run --frozen python3 -m pytest --no-cov -q` (real-bash-oracle files
  excluded, matching `.github/workflows/test.yml`'s own split): full
  suite green, including the widened
  `test_gitapex_provision_class_b.py` (all 79 of its own cases PASS,
  coverage unchanged at 94% on the touched module -- no new branch was
  added for this to leave uncovered).

**Explicit residual gap, disclosed rather than silently accepted:** this
session has no `nix` binary on PATH (the same fact issue #2051 itself
opens with), so `nix flake check` / `nix develop` against the edited
`flake.nix` cannot be exercised here. The Python-parser-level structural
check above (`parse_flake_class_b_pins` against the real, edited file)
and the local-preflight `toolchain-pin-drift` gate are the strongest
verification available inside this session; true Nix-side evaluation is
deferred to CI, which does have `nix` on its runners. Flagged in the PR
body's own CI-status section rather than asserted as covered.

## Refactor / adversarial-review scope (step 8 of this skill)

The diff is small and entirely additive (two new pin tables plus two new
`mkReleaseBinary` calls in `flake.nix`, one widened tuple constant plus a
docstring line in the provisioning script, two widened test assertions,
two short prose passages in `SKILL.md`) -- the mandatory refactor/simplify
pass and the independent adversarial review still run unconditionally
over the full diff per this skill's own step 8, with no narrowing implied
by the diff's small size or by this session's own live end-to-end
verification above. The adversarial review specifically re-checks: (a)
that no SHA256 pin was transcribed incorrectly against the actually-
downloaded asset it claims to describe (re-derivable directly from this
plan's own measured values); (b) that the `devShell`'s package list
genuinely contains no reference to the new `classB.actionlint`/
`classB.zizmor` entries (the row-2 design resolution's own literal
claim); and (c) that the widened `CLASS_B_TOOL_NAMES` tuple does not
silently change behavior for the three pre-existing tools (kind dispatch,
receipt format, CLI `--tool` validation are all read generically from the
tuple, not hardcoded per-name).

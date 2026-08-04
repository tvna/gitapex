---
name: setup-gitapex-toolchain
description: Provisions gitapex's flake.nix-pinned Class B toolchain binaries (waza, apm, rtk, betterleaks) and runs apm install, without Nix, for a fresh Claude Code web (ephemeral) session. Use when a session needs these tools and they are not yet on PATH, or to manually re-run/verify provisioning (--verify). Distinct from `nix develop`, which remains the provisioner for persistent surfaces (local CLI, CI) and is not invoked here.
compatibility: "Designed for Claude Code cloud (web) sessions; requires python3 >= 3.12, outbound network access to github.com release assets, and the SessionStart hook environment variables CLAUDE_CODE_REMOTE, CLAUDE_PROJECT_DIR, and CLAUDE_ENV_FILE."
---

# Setup gitapex Toolchain

Provisions the toolchain binaries `flake.nix` pins for the Claude Code web
(ephemeral) surface specifically, where Nix itself is not installed and
disk caching cannot survive across sessions
(`docs/superpowers/plans/2026-07-14-toolchain-foundation.md`: "Nix runs
only in CI... local work uses only curl, sha256sum, python3, and uv").
`flake.nix`'s `classBData`/`mkClassB` blocks are the single source of
truth for tool versions, per-system asset names, and SHA256 pins; this
skill's script parses them at runtime rather than holding its own copy,
so there is never a second pin table that could silently drift from the
flake (see `scripts/provision_class_b.py`'s own parser, and
`.github/scripts/scan_toolchain_pin_drift.py`, which already guards
against exactly this class of drift for CI workflows).

This skill's own SHA256 verification covers only the **downloaded Class B
release archives** against `flake.nix`'s pins -- it says nothing about
whether `SKILL.md` or `provision_class_b.py` themselves are untampered;
that trust path is simpler and different: this skill ships as part of the
gitapex repository itself, so its integrity rests on the repository's own
commit history, branch protection, and code review, the same protection
every other file in this repository already has, with no separate
checksum or signed-release mechanism for the skill files themselves.

## When this runs

Automatically, via `.claude/hooks/session-start.sh`, only when
`$CLAUDE_CODE_REMOTE=true` (a Claude Code web session). Persistent
surfaces (local CLI, CI) continue to use `nix develop .`
(`.github/workflows/toolchain-nix.yml`) and are not expected to invoke
this script (nothing in the script itself enforces this -- it is a
documented convention, not a technical restriction). Claude Code cloud
environments also support a "setup script" mechanism (configured
per-environment at claude.ai/code, and benefits from environment caching)
as an alternative to a SessionStart hook; this skill uses a SessionStart
hook instead because a setup script is configured in that per-environment
dialog and cannot be committed to this repository, so it cannot ship as
part of the checkout the way this skill's hook does.

## Preconditions

- `python3 >= 3.12` (matches this repository's `pyproject.toml`
  `requires-python` floor; `extract_wrapper_dir`'s tar extraction path
  relies on `filter="data"`, PEP 706, stdlib only since 3.12).
- `provision_class_b.py` is stdlib-only -- no `pip install` or `uv sync`
  needed to run it directly.
- Outbound network access to `github.com` release assets, and whatever
  `apm install` itself reaches. A session with no network access cannot
  provision anything: the download step fails, and so does this skill's
  purpose in that session.

## Manual invocation

```bash
python3 skills/setup-gitapex-toolchain/scripts/provision_class_b.py \
  --project-dir "$(pwd)"
```

Add `--verify` to check already-installed binaries only (no downloads, no
`apm install`). Add `--skip-apm-install` to provision the Class B
binaries without running `apm install` afterward. Add `--tool NAME`
(repeatable) to limit to specific tools.

## Output

- Binaries installed under `${XDG_CACHE_HOME:-~/.cache}/gitapex/toolchain/bin/`.
- `PATH` updated for the session via `$CLAUDE_ENV_FILE` (if set).
- Per tool, on stdout: `INSTALLED: <tool> (<version>)` on a fresh install,
  or `SKIPPED: <tool>` if it was already installed and verified current
  (both are success outcomes). A tool that failed prints
  `FAIL: <tool>: <error>` on **stderr** instead.
- The `apm install` phase (this skill's own final step, unless
  `--skip-apm-install` was passed): `INSTALLED: apm install` on stdout on
  success; `FAIL: apm install: <error>` on stderr on failure. If `apm`
  itself was requested but failed to provision, this phase instead prints
  `SKIPPED: apm install (apm itself was not successfully provisioned)` on
  stderr, and counts as a failure -- the opposite sense from the per-tool
  `SKIPPED` above: there, `SKIPPED` means "already installed, no
  problem"; here, `SKIPPED` means "could not run, this is a failure."
  Same word, two different meanings; both matter. If `apm` was excluded
  by a `--tool` filter (so this phase was never eligible to run), it
  instead prints `apm install not attempted (apm was not in --tool
  selection)` on stdout, which is not a failure.
- With `--verify`: `PASS: <tool>: <version>` or `FAIL: <tool>: <reason>`
  per tool, both on stdout -- note this differs from the default path's
  per-tool `FAIL`, which goes to stderr.
- Exit code: non-zero if any per-tool provisioning failed, the env-file
  write failed, or the `apm install` phase failed (including the
  apm-itself-didn't-provision case above); zero otherwise. Failures never
  crash the calling SessionStart hook (`session-start.sh` always exits 0
  itself) -- check this script's own exit code and stderr directly to
  confirm success.

## If provisioning fails

- A per-tool `FAIL` means: re-run scoped to just that tool with
  `--tool NAME`. This is cheap -- it does not redo any tool that already
  succeeded.
- To confirm the current installed state without any network calls or
  reinstalls, run with `--verify` instead of re-provisioning blind.
- Whether `--skip-apm-install` or a narrower `--tool` selection is still
  the right call must be re-derived fresh on every invocation. Do not
  carry forward an earlier turn's stated rationale from the same session
  as if it still applies -- re-check against the current state each time.
- If 2-3 scoped re-runs of the same tool still fail, stop retrying and
  escalate instead: at that point the cause is more likely a real outage
  or a broken pin in `flake.nix` than something an additional retry will
  fix.

## Known behavior: `.claude/settings.json` shows drift after `apm install`

The committed `.claude/settings.json` carries only this skill's own
`SessionStart` entry. `apm install` (this skill's own final step) re-adds
the apm-managed hook entries (superpowers, clairvoyance, and any future
ones) every run, tagged via the gitignored `.claude/apm-hooks.json`. A
working tree showing `.claude/settings.json` as modified after
provisioning is this expected, not-to-be-committed drift -- not a bug.

## Notes

- **Portability.** This skill's operative mechanisms -- `flake.nix`'s
  Class B pin tables, `.claude/hooks/session-start.sh`, `apm.yml`,
  `.claude/settings.json`, `.github/workflows/toolchain-nix.yml`, and its
  four gitapex-specific tool names (`waza`, `apm`, `rtk`, `betterleaks`)
  -- are all specific to this repository, with no portable counterpart.
  It is declared `Mixed`, not `Repository-scoped`: this repository's own
  portability design notes
  (`docs/superpowers/specs/2026-07-21-portability-authorship-decision-table-design.md`,
  Table A) reserve `Repository-scoped` for a downstream fork that
  hardcodes its own local conventions into an installed skill, not for a
  skill gitapex itself authors as the origin repository -- the same
  distinction `auditing-agent-product-scope`'s own metadata sidecar
  already records for an analogous conflict. Whether a skill with
  effectively no separable portable core (this one) is well served by
  either existing label -- `Mixed` ordinarily presupposes an actual
  portable core split from repo-specific detail via a reference file --
  is an open classification question, flagged here for a follow-up
  decision rather than resolved unilaterally.
- **Model invocation.** This skill is left invocable by both the model
  and the user (not `disable-model-invocation: true`) because the
  automatic SessionStart hook already performs identical provisioning
  unattended on every web session, with no user or model action at all;
  model-invocation adds negligible marginal blast radius there, and
  exists mainly to serve the `--verify` self-check and manual re-run
  cases this file's own description already advertises.

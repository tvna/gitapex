---
name: setup-gitapex-toolchain
description: Provisions gitapex's flake.nix-pinned Class B toolchain binaries (waza, apm, rtk, betterleaks) and runs apm install, without Nix, for a fresh Claude Code web (ephemeral) session. Use when a session needs these tools and they are not yet on PATH, or to manually re-run/verify provisioning (--verify). Distinct from `nix develop`, which remains the provisioner for persistent surfaces (local CLI, CI) and is not invoked here.
compatibility: "Designed for Claude Code cloud (web) sessions; requires python3 >= 3.12, outbound network access to github.com release assets, and the SessionStart hook environment variables CLAUDE_CODE_REMOTE, CLAUDE_PROJECT_DIR, and CLAUDE_ENV_FILE."
---

# Setup gitapex Toolchain

Provisions the toolchain binaries `flake.nix` pins for the Claude Code web
(ephemeral) surface specifically, where Nix itself is not installed and
disk caching cannot survive across sessions. `flake.nix`'s `classBData`/
`mkClassB` blocks are the single source of truth for tool versions,
per-system asset names, and SHA256 pins; this skill's script
(`scripts/gitapex_provision_class_b.py`) parses them at runtime rather than
holding its own copy, so there is never a second pin table that could
silently drift from the flake.

This skill's own SHA256 verification covers only the **downloaded Class B
release archives** against `flake.nix`'s pins -- it says nothing about
whether `SKILL.md` or `gitapex_provision_class_b.py` themselves are untampered;
that trust path is simpler and different: this skill ships as part of the
gitapex repository itself, so its integrity rests on the repository's own
commit history, branch protection, and code review, the same protection
every other file in this repository already has, with no separate
checksum or signed-release mechanism for the skill files themselves.

## When this runs

Automatically, via `.claude/hooks/session-start.sh`, only when
`$CLAUDE_CODE_REMOTE=true` (a Claude Code web session). Persistent
surfaces (local CLI, CI) continue to use `nix develop .` and are not
expected to invoke this script (nothing in the script itself enforces
this -- it is a documented convention, not a technical restriction).
Claude Code cloud environments also support a "setup script" mechanism
(configured per-environment at claude.ai/code, and benefits from
environment caching) as an alternative to a SessionStart hook; this
skill uses a SessionStart hook instead because a setup script is
configured in that per-environment dialog and cannot be committed to
this repository, so it cannot ship as part of the checkout the way this
skill's hook does.

After Class B provisioning and the prek install, the same hook makes a
third, unrelated best-effort attempt: non-interactively registering
gitapex's own plugin marketplace and installing its own plugin (`claude
plugin marketplace add`, `claude plugin install gitapex@gitapex`), so
gitapex's own `skills/*` become invocable via the self-referential
marketplace declared in `.claude/settings.json` -- separate from
`apm install`, which only ever
deploys `apm.yml`'s two devDependencies (`obra/superpowers`,
`tvna/clairvoyance`), never gitapex itself. See "Known behavior: self-plugin
registration takes effect one session late" below for this block's own
limits.

## Preconditions

- `python3 >= 3.12` (`extract_wrapper_dir`'s tar extraction path relies
  on `filter="data"`, PEP 706, stdlib only since 3.12).
- `gitapex_provision_class_b.py` is stdlib-only -- no `pip install` or `uv sync`
  needed to run it directly.
- Outbound network access to `github.com` release assets, and whatever
  `apm install` itself reaches. A session with no network access cannot
  provision anything: the download step fails, and so does this skill's
  purpose in that session.

## Manual invocation

```bash
python3 skills/setup-gitapex-toolchain/scripts/gitapex_provision_class_b.py \
  --project-dir "$(pwd)"
```

Add `--verify` to check already-installed binaries only (no downloads, no
`apm install`). Add `--skip-apm-install` to provision the Class B
binaries without running `apm install` afterward. Add `--tool NAME`
(repeatable) to limit to specific tools.

## Output

- Binaries installed under `${XDG_CACHE_HOME:-~/.cache}/gitapex/toolchain/bin/`.
- `PATH` updated for the session via `$CLAUDE_ENV_FILE` (if set).
- Per tool, on stdout: `INSTALLED: <tool> (<version>)` on a fresh install
  -- the `(<version>)` parenthetical appears only when that tool's own
  `--version` output was non-empty after sanitization -- or
  `SKIPPED: <tool>` if it was already installed and verified current
  (both are success outcomes). A tool that failed prints
  `FAIL: <tool>: <error>` on **stderr** instead.
- The `apm install` phase (this skill's own final step, unless
  `--skip-apm-install` was passed): `INSTALLED: apm install` on stdout
  when the install subprocess actually ran and succeeded (a first run, or
  a reinstall triggered by a lockfile or `apm`-binary change);
  `UNCHANGED: apm install` on stdout when `apm.lock.yaml`
  and the installed `apm` binary both matched the last successful run, so
  nothing was re-invoked -- a success state, and a new, fourth token
  distinct from `INSTALLED`, `FAIL`, and `SKIPPED` below (not a third
  meaning layered onto `SKIPPED` itself, which already carries two);
  `FAIL: apm install: <error>` on stderr on failure. If `apm`
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
- Exit code: non-zero if the system could not be detected, `flake.nix`'s
  Class B pins could not be loaded, an unknown `--tool` value was given,
  (with `--verify`) any tool's check failed, or (without `--verify`) any
  per-tool provisioning failed, the env-file write failed, or the
  `apm install` phase failed (including the apm-itself-didn't-provision
  case above); zero otherwise. Failures never crash the calling
  SessionStart hook (`session-start.sh` always exits 0 itself) -- check
  this script's own exit code and stderr directly to confirm success.

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
ones), tagged via the gitignored `.claude/apm-hooks.json`, only on the
sessions where it actually re-runs -- now the exception rather than every
session, since a matching lockfile and installed `apm` binary make it a
fast `UNCHANGED: apm install` no-op instead (see Output above). On those
sessions, a working tree showing `.claude/settings.json` as modified
afterward is this expected, not-to-be-committed drift -- not a bug. The
same file can also drift for a second, independent reason: see the next
section.

## Known behavior: self-plugin registration takes effect one session late

The `claude plugin marketplace add` / `claude plugin install gitapex@gitapex`
block this hook runs has been directly observed, across separate live
sessions, to succeed non-interactively -- no stderr failure,
no interactive trust-prompt block. Confirmed live: the session where this
block first registers/installs the plugin does not itself show gitapex's
own skills in its own available-skills list, but the *next* `SessionStart`
(a resume in the same container, or a later session against the same
environment) does. This is a hook-timing limitation, not a broken or gated
mechanism -- the skill list a session advertises is fixed before its own
SessionStart hooks run, so no hook can make its own session reflect a
plugin it just installed.

Whether a genuinely brand-new session's own very first available-skills
listing can ever show gitapex's own skills remains an open question: that
specific case is structurally unreachable via a SessionStart hook, by
the same timing argument above, regardless of whether the underlying
`claude plugin install` call itself succeeds. Do not read "no stderr
message" as proof beyond that narrower claim -- it confirms the install
succeeded, not that the *current* session's own skill list reflects it.

Directly observed, reproduced across two separate sessions while building
this mitigation: `claude plugin marketplace add` itself rewrites the
committed `.claude/settings.json` in place -- `extraKnownMarketplaces.
gitapex.source.path` gets resolved from the committed relative `"."` to
this session's own container-specific absolute path, and top-level keys
get reordered -- a second, independent cause of the same
not-to-be-committed-drift shape the previous section already documents
for `apm install`. Never commit this drift: the rewritten absolute path
is specific to one container/session and would be wrong (and misleading)
in any other checkout.

## Optional: faster Class B provisioning via a setup script

Claude Code cloud environments also support a "setup script" -- a
per-environment mechanism configured through the environment dialog at
[claude.ai/code](https://claude.ai/code), documented at
<https://code.claude.com/docs/en/cloud-environments>. Unlike this skill's
`SessionStart` hook (which runs on every session), a setup script's
output is cached across session restarts within that environment: per
the primary source, "The setup script runs the first time you start a
session in an environment. After it completes, Anthropic snapshots the
filesystem and reuses that snapshot as the starting point for later
sessions... Resuming an existing session never re-runs the setup
script."

Whoever configures an environment at claude.ai/code can optionally paste
the following into that environment's "Setup script" field, to
pre-provision the Class B binaries once per environment instead of
re-verifying them (a fast but non-zero receipt check) on every session:

```bash
#!/bin/bash
python3 skills/setup-gitapex-toolchain/scripts/gitapex_provision_class_b.py \
  --project-dir "$(pwd)" --skip-apm-install || true
```

`--skip-apm-install`: the primary source draws its own line at
project-dependency installs -- "Use a setup script to provision the VM
itself: toolchains and CLI tools that aren't pre-installed. Use a
SessionStart hook for project setup that should run everywhere, cloud
and local, like `npm install`." `apm install` is exactly that latter
case (a project-dependency install), so it belongs on this skill's
`SessionStart` hook -- invoked every session regardless, now
idempotency-gated on the `apm install` step itself (see Output above) --
not duplicated into the setup script.

`|| true`: per the same primary source, "if the script exits non-zero,
the session fails to start. Append `|| true` to non-critical commands so
an intermittent install failure doesn't block the session" -- a
transient Class B provisioning failure here must not block session
startup, the same reasoning `.claude/hooks/session-start.sh` itself
already follows (it always exits 0, for the identical reason).

This is a pure, optional latency optimization for whoever configures it.
It does not remove or gate the automatic `SessionStart`-hook path, which
keeps working exactly as it does today -- with or without a setup script
configured -- and remains what makes a brand-new, never-configured
environment provision automatically with zero manual steps, this skill's
founding goal (see `metadata/gitapex.yaml`'s `spec.references`). A setup
script cannot be committed to this repository -- per the primary source
it is configured only through the environment dialog above, not a
repository file -- so this section is documentation for a reader who
wants to opt in, not a mechanism this repository wires up on its own.

## Notes

- **Portability.** Declared `Mixed`: this skill's operative mechanisms
  (`flake.nix` Class B pins, `session-start.sh`, `apm.yml`,
  `.claude/settings.json`, four gitapex-specific tool names) have no
  portable core separable from this repository. Full decision citation,
  plus an open taxonomy-gap deferral, are recorded in this skill's
  `metadata/gitapex.yaml` under `spec.references`.
- **Model invocation.** This skill is left invocable by both the model
  and the user (not `disable-model-invocation: true`) because the
  automatic SessionStart hook already performs identical provisioning
  unattended on every web session, with no user or model action at all;
  model-invocation adds negligible marginal blast radius there, and
  exists mainly to serve the `--verify` self-check and manual re-run
  cases this file's own description already advertises.

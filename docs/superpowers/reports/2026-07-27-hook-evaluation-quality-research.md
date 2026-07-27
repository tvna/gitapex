# Hook Evaluation Quality Research (2026-07-27)

## Scope

This repository has `evaluating-skill-quality` (a nine-dimension rubric plus a
deterministic shape checker for judging `SKILL.md` artifacts) but no sibling
skill for judging the quality of a *hook* -- `hooks/hooks.json` and the
scripts it wires in, or a skill/subagent's own embedded `hooks.PreToolUse`
frontmatter block. This report is research only: it inventories primary
sources (this repository's own hook artifacts and design history, plus
Anthropic's official Claude Code hooks documentation, fetched this session)
and proposes candidate quality dimensions a future `evaluating-hook-quality`
skill could grade against. **It does not create that skill.** Building it --
`SKILL.md`, a rubric, a shape checker -- is explicitly out of scope here and
deferred to a follow-up issue once an owner picks among the options in
[Next steps](#next-steps-decision-ready-options).

Labeled per `grounding-in-primary-sources`: `Fact:` claims are grounded in a
citation given alongside them (a file:line read this session, or a URL
fetched this session with the source's own text quoted); `Speculation:`
claims are this report's own synthesis and are marked as such.

## Primary sources consulted

### Internal: this repository's own hook artifacts and design history

1. **`hooks/hooks.json`** -- Fact: declares exactly three `PreToolUse`
   entries (matchers `Bash`, `Write`, `mcp__github__issue_write`), each
   pointing at one script under `hooks/`. Its own `description` field states
   it backs "5 approved Major findings from
   `docs/superpowers/reports/2026-07-13-skill-gap-triage.md`" plus issue
   #413. No other hook event (`PostToolUse`, `Stop`, `SessionStart`, etc.)
   is wired at the plugin level today.
2. **`hooks/check-bash-safety.sh`** -- Fact: a `Bash`-matcher `PreToolUse`
   hook denying (a) package/plugin install verbs, (b) direct `gh issue`/
   `gh pr` write subcommands and `gh api` write calls -- including a
   `-X`/`--method` flag-syntax bypass (`--method=POST`, `-XPOST`), an
   absolute-path-prefix bypass, and a `gh api graphql` mutation bypass, all
   three caught by a security review (opus) before the hooks shipped per
   `docs/superpowers/reports/2026-07-13-skill-gap-triage.md`'s Final
   outcome section, plus a separate field-flag (`-f`/`--field`/
   `--raw-field` implicit-POST) bypass the script's own comments present
   as its own standalone finding, not one credited to that security
   review -- and (c) warning, not denying, on `git push` by shelling out
   to `outward-artifact-preflight`'s `scan_provenance.py`.
   Its own comments explicitly disclose a known ceiling: "Obfuscation that
   hides the verb itself -- base64-piped-to-sh and the like -- is out of
   reach of any regex gate," tracked as an open item in issue #55 (bare
   number as written in the file itself; full form
   `tvna/gitapex#55`).
3. **`hooks/check-issue-acm-disclosure.sh`** + **`hooks/check_acm_present_or_waiver.py`**
   -- Fact: an `mcp__github__issue_write`-matcher hook (fires only on
   `method == "create"`) blocking issue creation whose body lacks an
   Acceptance Criteria Map table or an explicit waiver line, backing issue
   #413 (sub-issue of #357). The Python script's own docstring states it is
   "a fourth, self-contained copy of the same header-table regex and waiver-
   line vocabulary already duplicated across"
   three sibling scripts, "kept in sync by
   `tests/test_check_acm_present_sync.py`'s explicit extras list" -- an
   explicitly named, currently-accepted drift risk (four independent
   regex copies, synchronized only by a test, not a shared import), because
   a prior version that shelled out cross-directory to `.github/scripts/`
   caused a real false-deny once the repo was consumed as an installed
   plugin (caught by a Codex review on PR #433).
4. **`hooks/check-template-overwrite.sh`** -- Fact: a `Write`-matcher hook
   blocking any `Write` call that would overwrite an existing issue/PR/MR
   template path, case-insensitive, covering both directory-based and
   single-file template conventions (GitHub and GitLab).
5. **Bundled tests**: `hooks/test_check_bash_safety.py` (303 lines),
   `hooks/test_check_issue_acm_disclosure.py` (173 lines), and
   `skills/executing-a-branch-plan/scripts/test_check_task_bash_safety.py`
   (143 lines) -- Fact: a pytest suite is committed beside most, but not
   all, shipped hook scripts. `hooks/check-bash-safety.sh` and
   `hooks/check-issue-acm-disclosure.sh` each have one; the third
   `hooks.json`-wired script, `hooks/check-template-overwrite.sh`, has
   **no test file anywhere in this repository** (confirmed by listing
   `hooks/` and grepping the repository for any test referencing it) --
   a gap in an otherwise-established testability convention for hooks,
   itself distinct from (and, unlike) `evaluating-skill-quality`'s own
   dimension 7 (bundled scripts), which grades a *skill's* bundled
   script, not a hook.
6. **`skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh`**
   -- Fact: a second, independent hook (bound via
   `.claude/agents/branch-plan-task.md`'s own frontmatter `hooks.PreToolUse`
   block, not `hooks/hooks.json`), deliberately stricter than
   `check-bash-safety.sh` for its narrower task-agent scope (denies `gh`
   entirely, hard-denies `git push` with no warn-only exception). Its own
   comments document three distinct bypass classes found and fixed after
   the fact via `/code-review` and a Codex review pass: a bare
   `npm ci`/`pnpm install`/`yarn install` gap -- per the script's own
   comment, `npm ci` is a clean-install verb containing no literal
   "install" substring at all, so it slipped past a pattern grepping for
   that word, while `pnpm install`/`yarn install` were missed for a
   narrower, different reason: `check-bash-safety.sh`'s existing
   install-verb pattern covered only the "add" forms (`pnpm add`,
   `yarn add`), not either command's own primary install verb -- a
   fetch-and-execute gap (`curl|wget` piped to a shell, and `npx`), and a
   `git` global-option gap (`git -C <path> push` was not anchored). It
   discloses the identical regex-gate obfuscation ceiling as
   `check-bash-safety.sh`, explicitly cross-referenced rather than
   re-derived.
7. **`skills/executing-a-branch-plan/references/threat-model-and-authorization.md`**
   -- Fact: the most detailed hook-quality discussion already in this
   repository. It documents (a) live, empirical verification of a hook's
   actual behavior rather than an assumed one (quoted `systemMessage`
   outputs for denied `pip install`, `gh issue view`, `git push origin
   HEAD`, and a confirmed-unblocked `git status --short`); (b) that the same
   hook was re-verified inside a `worktree`-isolated subagent context, not
   assumed to still fire there; (c) a stated, corrected asymmetry between
   two deployment variants (project-local: subagent frontmatter hook binds;
   plugin-distributed: "for security reasons, `hooks`... are not supported
   for plugin-shipped agents," a claim this document says it verified
   "against Claude Code's own primary documentation, not assumed"); and (d)
   an explicit, still-open item ("Decision 7's own broader open question")
   about whether `hooks/check-bash-safety.sh` itself binds inside a
   subagent/Workflow context in a real plugin-installed deployment.
8. **`docs/superpowers/reports/2026-07-13-skill-gap-triage.md`** and its
   companion **`...-skill-gap-findings.md`** -- Fact: the historical record
   of how the current hooks came to exist. Twelve parallel Fable reviews
   run against `evaluating-skill-quality`'s own rubric surfaced 11 Major
   findings, each an unbacked safety-critical prohibition or a whole-
   artifact "should have been a hook" mechanism-fit finding; each was
   user-adjudicated one at a time via `AskUserQuestion`; 5 became real
   `PreToolUse` hooks, 1 was re-scoped, 1 was deferred to a companion issue
   pair (`tvna/claude-md#2478` / `tvna/gitapex#54`) because the fix needed
   changes to an upstream, non-hand-edited `CLAUDE.md`, and 4 more were
   deferred to `tvna/gitapex#55` as needing their own design pass rather
   than a simple pattern-match hook. A security review (opus) caught a
   Critical `gh api` flag-syntax bypass before the hooks shipped.
9. **`skills/evaluating-skill-quality/SKILL.md`** + **`references/rubric.md`**
   -- Fact: establishes the sibling-artifact convention a hook-quality
   rubric would extend or mirror: a two-lane split (deterministic shape a
   script decides vs. probabilistic maturity dimensions needing judgment),
   an Unknowns framework with a mandatory Blind spot pass, and, inside its
   own Mechanism fit section, an explicit "Skill vs. hook" test: "a skill is
   an instruction the model *chooses* to follow; a hook fires
   *deterministically*... 'Every time X, always do Y'... needs
   deterministic backing, not prose alone." This existing test already
   supplies half of what a hook-quality rubric needs (when a hook is the
   *right* mechanism); it does not yet cover whether a given hook, once
   built, is *good*.
10. **`skills/screening-a-low-trust-contribution/SKILL.md`** (check 4) +
    **`evals/screening-a-low-trust-contribution/tasks/hook-script-change.yaml`**
    -- Fact: a hook/script-path diff from a low-trust author is *already* a
    mandatory hard-flag category in this repository's incoming-contribution
    screening, independent of how reasonable the surrounding change looks
    -- "a hook runs with the repo's own privileges once merged." This is a
    diff-provenance check (is this specific incoming change trustworthy?),
    narrower than and distinct from a holistic artifact-quality rubric (is
    this hook, regardless of who wrote it, well-built?).
11. **Defense-in-depth convention, observed directly across all three
    `hooks/*.sh` scripts** -- Fact: every shipped hook denies via *both* the
    `hookSpecificOutput` JSON on stdout *and* `exit 2`/stderr
    simultaneously (each script's own comment cites this as deliberate,
    "for defense in depth"), and every script re-checks its own
    `tool_name`/`method` field even though the `hooks.json` matcher already
    restricts it ("the hooks.json matcher already restricts this hook to
    Bash, but never trust that alone").
12. A search of this repository's GitHub issues for hook-evaluation or
    hook-quality work, and a grep of every file under `docs/superpowers/`
    for the word "hook", turned up **zero** existing issues and no plan,
    spec, or note proposing a hook-quality rubric -- Fact: this is
    genuinely open territory in this repository, not duplicate work.

### External: Anthropic's official Claude Code documentation (fetched this session)

- Fact, per <https://code.claude.com/docs/en/hooks-guide> (fetched
  2026-07-27): "Hooks are user-defined shell commands that execute at
  specific points in Claude Code's lifecycle. They provide deterministic
  control over Claude Code's behavior, ensuring certain actions always
  happen rather than relying on the LLM to choose to run them." This is
  Anthropic's own, independent statement of exactly the deterministic/
  judgment split `evaluating-skill-quality`'s rubric already asserts for
  "Skill vs. hook" -- cross-verified, not merely repeated.
- Fact, same source: "For decisions that require judgment rather than
  deterministic rules, you can also use prompt-based hooks or agent-based
  hooks that use a Claude model to evaluate conditions." Two additional
  hook `type`s exist beyond `command`: `type: "prompt"` (a single Haiku-
  by-default LLM call returning `{"ok": true|false, "reason": ...}`) and
  `type: "agent"` (a subagent with up to 50 tool-use turns, explicitly
  still "experimental... For production workflows, prefer command hooks").
  Every hook this repository ships today is `type: "command"`. This
  reopens, rather than closes, the mechanism-fit question: a `prompt`/
  `agent` hook reintroduces model judgment inside a "hook," which is the
  exact non-determinism the deterministic/judgment split exists to route
  *away* from a hook and into a skill. A future rubric needs its own
  position on this, not a silent assumption either way.
- Fact, same source: exit-code contract -- "Exit 2: the action is
  blocked... Some events can't be blocked... Any other exit code: the
  action proceeds"; and, from the hooks reference page, "Claude Code
  treats exit code 1 as a non-blocking error and proceeds with the action,
  even though 1 is the conventional Unix failure code. If your hook is
  meant to enforce a policy, use `exit 2`." Every deny path read directly
  in this repository's own `hooks/*.sh` (item 2-4 above) already uses
  `exit 2` correctly.
- Fact, per <https://code.claude.com/docs/en/hooks-guide> (fetched
  2026-07-27, "How hooks work" / "Combine results from multiple hooks"
  sections): hooks matching the same event "run in parallel, and
  identical hook commands are automatically deduplicated"; "One hook
  returning `deny` doesn't stop sibling hooks from executing. Don't rely
  on one hook's `deny` to suppress side effects in another hook." (The
  hooks *reference* page, <https://code.claude.com/docs/en/hooks>, states
  the same dedup behavior in different words -- "identical handlers are
  deduplicated automatically... by command string and `args`" -- the
  quotes above are the guide page's own wording specifically.) None of
  this repository's current hooks have a side effect independent of
  their own deny decision (each is a pure classifier), so this has not
  yet surfaced as a live bug here, but it is a real dimension for any
  future hook with a logging/notification side effect.
- Fact, per <https://code.claude.com/docs/en/hooks> (fetched 2026-07-27):
  exec form vs. shell form -- "Set `args` whenever the hook references a
  path placeholder, since each element is passed as one argument with no
  quoting" (exec form is the documented safer default for path
  interpolation). This repository's `hooks/hooks.json` uses shell-form
  commands with a manually, correctly quoted path
  (`"\"$CLAUDE_PLUGIN_ROOT/hooks/check-bash-safety.sh\""`, confirmed by
  direct read) rather than the `args`-array exec form. Speculation: this is
  not a defect (the quoting is correct as written), but a rubric could
  still grade "does a shell-form hook command quote every interpolated
  path/variable" as a deterministic-shape check, given exec form removes
  the class of bug entirely.
- Fact, per <https://code.claude.com/docs/en/hooks> (fetched 2026-07-27),
  on timeout configuration: defaults are "600 for `command`, `http`,
  `mcp_tool`; 30 for `prompt`; 60 for `agent`" (seconds), independently
  corroborated on <https://code.claude.com/docs/en/hooks-guide>'s
  Limitations section ("`command`, `http`, `mcp_tool`: 10 minutes...
  `prompt`: 30 seconds... `agent`: 60 seconds"). This repository's own
  hooks declare an explicit, much shorter `timeout` (10-30s) rather than
  inheriting the 600s/10-minute default.
- Fact, per <https://code.claude.com/docs/en/hooks> (fetched 2026-07-27),
  on the *different* `if`-field filter (not used by any
  hook in this repository, which instead parses `tool_input.command`
  itself inside each script): "The filter also fails open, running your
  hook regardless of pattern, when the Bash command can't be parsed...
  use the permission system rather than a hook to enforce a hard allow or
  deny." The fail-open principle generalizes past the `if` field
  specifically: `check-bash-safety.sh` and `check_task_bash_safety.sh`'s
  own disclosed ceiling (a regex cannot see through `${IFS}`/quote-
  splitting/base64 obfuscation) is exactly a fail-open mode on unparseable
  or disguised input, already self-disclosed in both scripts' own comments
  per item 2 and 6 above.
- Fact, per <https://code.claude.com/docs/en/hooks-guide> (fetched
  2026-07-27, Limitations section): "When multiple `PreToolUse` hooks
  return `updatedInput` to rewrite a tool's arguments, the last one to
  finish takes effect. Since hooks run in parallel, the order is
  non-deterministic. Avoid having more than one hook modify the same
  tool's input." Not yet triggered by any hook in this repository (none
  use `updatedInput`), but a candidate dimension once one does.
- Fact, per <https://code.claude.com/docs/en/hooks-guide> (fetched
  2026-07-27, "Hooks and permission modes" section): "`PreToolUse` hooks
  fire before any permission-mode check, in every permission mode,
  including `dontAsk`. A hook that returns `permissionDecision: "deny"`
  blocks the tool even in `bypassPermissions` mode... The reverse is not
  true: a hook returning `"allow"` doesn't bypass deny rules from
  settings." This confirms the specific strength this repository's
  `PreToolUse` hooks are already relying on
  (`threat-model-and-authorization.md`'s "empirically verified... hard
  deny" language, item 7 above) is grounded in the platform's own
  documented guarantee, not an assumption.
- Fact, per <https://code.claude.com/docs/en/hooks> (fetched 2026-07-27),
  on plugin-shipped agents: "When a plugin is enabled, its hooks merge
  with your user and project hooks" (an exact quote), and, separately,
  that the same page documents hooks being definable directly in skill
  and subagent YAML frontmatter (this report's own paraphrase of that
  section, not a verbatim quotation). The
  specific claim in `threat-model-and-authorization.md` that plugin-
  *shipped agents* cannot carry their own `hooks` field (item 7 above) was
  not directly re-confirmed by the two pages fetched this session (the
  fetched pages describe project-local skill/subagent frontmatter hooks
  and plugin `hooks/hooks.json`, not the plugin-agent-frontmatter case
  specifically) -- Speculation, not independently re-verified here: this
  report defers to `threat-model-and-authorization.md`'s own stated
  verification against Claude Code's plugin-reference documentation
  rather than re-deriving it, and flags it as a citation this report
  did not re-check first-hand.

## Candidate quality dimensions (research proposal, not a shipped rubric)

Modeled on `evaluating-skill-quality`'s own two-lane split. Every dimension
below is a candidate for a future rubric to accept, reject, or refine --
none of these are enforced anywhere yet.

### Candidate deterministic-shape checks (a script could grade these)

1. **Deny path uses `exit 2`, not `exit 1` or a bare non-zero code.**
   Grounded in the official exit-code contract above; a hook meant to
   enforce policy that exits 1 silently degrades to "non-blocking" without
   the author necessarily noticing, since no error is raised at hook-
   registration time.
2. **`hookSpecificOutput.permissionDecision` and stderr/exit-2 are both
   present on every deny path (defense in depth).** Grounded in item 11
   above -- already this repository's own convention, worth codifying as a
   checkable rule rather than an implicit habit.
3. **The script re-validates its own `tool_name`/`method`/matcher-relevant
   field, not just relying on the `hooks.json` matcher.** Grounded in item
   11 -- likewise already a convention here, not yet a named check.
4. **A bundled test file exists beside the hook script.** Grounded in item
   5 -- this repository already does this for most, but not every, hook
   it ships (`hooks/check-template-overwrite.sh` is the current
   exception); `evaluating-skill-quality` dimension 7 has no direct hook
   analogue today.
5. **Shell-form commands in `hooks.json`/frontmatter quote every path/
   variable interpolation; or the hook uses exec-form `args` instead.**
   Grounded in the exec-form-vs-shell-form primary source above.
6. **Timeout is set explicitly and is proportionate to the check's actual
   cost** (this repository's hooks declare 10-30s; the platform default
   is 600s for `command` hooks). Grounded in the official timeout-
   configuration fact above -- an unset timeout on a `command` hook
   silently inherits a 10-minute ceiling, which is a long time to block a
   tool call on a hung script.

### Candidate probabilistic-maturity dimensions (need judgment)

7. **Mechanism fit, hook direction:** does this event/matcher combination
   actually match the platform's own semantics (e.g., a `PostToolUse`
   hook cannot undo an action already taken, per the official
   Limitations section; a `Stop` hook fires on every response, not only
   "real" completion)? `evaluating-skill-quality`'s existing "Skill vs.
   hook" test answers *whether a hook is the right artifact at all*; this
   dimension asks whether the specific event chosen for an already-
   correct hook decision is the right one.
8. **Hook-type fit:** given the official `command`/`prompt`/`agent`/`http`/
   `mcp_tool` split, does a `command` hook's fixed pattern actually cover
   the intended policy without needing judgment it cannot express (the
   disclosed regex-obfuscation ceiling, items 2 and 6), or would a
   `prompt`/`agent` hook better fit a check that is judgment-shaped but
   still wants to run outside model choice? Conversely, does a `prompt`/
   `agent` hook's own model call reintroduce the exact non-determinism a
   hook exists to avoid, for a check that should have stayed `command`-
   type or been narrowed until it could be? Grounded in the open question
   raised by the external "prompt-based hooks" primary source above.
9. **Blast-radius / trust classification, stated explicitly.** Grounded in
   `screening-a-low-trust-contribution`'s own framing ("a hook runs with
   the repo's own privileges once merged") -- does the hook's own
   documentation (or the future rubric's report on it) state what it can
   do if bypassed or misconfigured, rather than leaving that implicit?
10. **Known-limitation disclosure.** Grounded directly in items 2 and 6:
    this repository's existing hooks already model the desired behavior --
    stating a regex gate's exact bypass class in-line, tracked by issue
    number, rather than silently overclaiming complete coverage. A rubric
    dimension could grade whether a new hook does the same, rather than
    presenting untested coverage as complete.
11. **Empirical verification over assumed behavior.** Grounded in
    `threat-model-and-authorization.md`'s own live-tested `systemMessage`
    quotes (item 7) versus a plausible-sounding but unverified claim. A
    rubric could require (or at least ask for) the same: quoted, live
    evidence that a hook actually denies/allows what it claims to, in the
    actual execution context it is meant to cover (main thread, worktree-
    isolated subagent, `Workflow`-tool-dispatched agent -- these are
    documented as behaviorally distinct in item 7).
12. **Deployment-mode portability.** Grounded in item 7's project-local
    vs. plugin-distributed asymmetry: does the hook's own documentation
    state which deployment mode it was verified in, and name the gap
    explicitly when the other mode is unverified, the same way
    `evaluating-skill-quality`'s own Portability level section already
    does for skills?
13. **Duplication/drift risk, named rather than hidden.** Grounded in item
    3: this repository already carries four independent copies of one
    regex, synchronized only by a test's explicit extras list. A rubric
    dimension could ask, for any new hook, whether its logic duplicates an
    existing hook's own pattern (and if so, whether that duplication is
    deliberate -- e.g., a plugin-bundled script needing to be self-
    contained -- and whether a sync-check test exists) rather than an
    unnoticed copy-paste that drifts silently.
14. **Side-effect independence from the deny decision.** Grounded in the
    official "hooks run in parallel... don't rely on one hook's deny to
    suppress side effects in another" fact -- not yet triggered by any
    hook in this repository, but a real dimension for the first hook that
    logs, notifies, or writes as well as classifies.

## Open questions / blind spots

Per this repository's own Unknowns framework (`evaluating-skill-quality`'s
Blind spot pass), named explicitly rather than left implicit:

- **No behavioral-evidence convention exists for hooks the way it does for
  skills.** `evaluating-skill-quality` dimension 8 asks for an eval suite
  and a no-skill baseline; no `evals/*/eval.yaml` precedent exists for a
  *hook* today (the closest is
  `evals/screening-a-low-trust-contribution/tasks/hook-script-change.yaml`,
  which tests contribution screening, not the hook's own correctness).
  What would "behavioral evidence for a hook" even mean -- a fixed corpus
  of allow/deny commands run against the script directly (which is what
  `hooks/test_check_bash_safety.py` already does), or something broader
  covering the live-execution-context checks item 10 names?
- **The `prompt`/`agent` hook-type question (dimension 8 above) is
  unresolved, not just unaddressed.** This report surfaces it as a real
  design fork, not a settled position.
- **This report's own external-source coverage has one unverified
  cross-check**, named in the External sources list above (the plugin-
  shipped-agent hooks restriction) -- flagged rather than silently
  presented as independently confirmed.
- **Whether a hook-quality skill should be a new skill at all, versus an
  extension of `screening-a-low-trust-contribution` check 4 (which
  already hard-flags any hook/script diff) or a new dimension bolted onto
  `evaluating-skill-quality` itself**, is an open mechanism-fit question
  this report does not resolve -- see [Next steps](#next-steps-decision-ready-options).

## Explicitly out of scope for this pass

- No `skills/evaluating-hook-quality/` directory, `SKILL.md`, rubric, or
  shape checker is created by this report.
- No changes to `hooks/hooks.json` or any existing hook script.
- No eval suite is created for the candidate dimensions above; none of
  them have been battle-tested against a real hook contribution yet.

## Next steps (decision-ready options)

Per this repository's own "never hand a human a decision that is not
decision-ready" convention, three concrete, named options for whoever
picks up this research next -- not an open-ended "what should we do":

- **(a) Build a new `evaluating-hook-quality` skill**, mirroring
  `evaluating-skill-quality`'s two-lane structure, using the candidate
  dimensions above as a starting rubric, scoped explicitly to `type:
  "command"` hooks only (deferring the `prompt`/`agent`-type question).
- **(b) Same as (a), but resolve the `prompt`/`agent` hook-type mechanism-
  fit question first**, as its own small design spike, before the rubric
  is written, since it changes what dimension 8 above even means.
- **(c) A narrower step**: extend `screening-a-low-trust-contribution`
  check 4 (currently a hard-flag-and-nothing-more) into a fuller checklist
  using the deterministic-shape checks above, without building a whole new
  sibling skill yet -- deferring the probabilistic-maturity dimensions to
  a later pass once (a)/(b) above are picked.
